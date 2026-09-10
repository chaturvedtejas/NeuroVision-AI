"""
NeuroVision AI - Smart Alert Engine & AI Incident Reporting
Generates intelligent alerts with natural language summaries
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from app.action.recognizer import ActionPrediction, ActionType
from app.anomaly.detector import AnomalyResult
from config.settings import settings


# ─── Alert cooldown tracker ───────────────────────────────────────────────────

class CooldownManager:
    """Prevents alert spam by tracking per-camera, per-type cooldowns."""

    def __init__(self):
        self._last_alert: Dict[str, float] = {}

    def can_alert(self, camera_id: str, alert_type: str, cooldown_sec: int) -> bool:
        key = f"{camera_id}:{alert_type}"
        now = time.time()
        last = self._last_alert.get(key, 0)
        if now - last >= cooldown_sec:
            self._last_alert[key] = now
            return True
        return False

    def reset(self, camera_id: str) -> None:
        keys = [k for k in self._last_alert if k.startswith(f"{camera_id}:")]
        for k in keys:
            del self._last_alert[k]


# ─── Alert definitions ────────────────────────────────────────────────────────

SEVERITY_MAP = {
    ActionType.FIGHTING: "critical",
    ActionType.FALLING: "high",
    ActionType.FALLEN: "critical",
    ActionType.RUNNING: "medium",
    ActionType.LOITERING: "medium",
    ActionType.SUSPICIOUS: "medium",
}

ANOMALY_SEVERITY = {
    "zone_intrusion": "high",
    "abandoned_object": "high",
    "statistical_motion": "medium",
}


# ─── Incident reporter ────────────────────────────────────────────────────────

INCIDENT_TEMPLATES = {
    ActionType.FIGHTING: (
        "Physical altercation detected between persons #{track_ids} "
        "at {camera_name}. Confidence: {confidence:.0%}."
    ),
    ActionType.FALLING: (
        "Person #{track_id} appears to be falling at {camera_name}. "
        "Immediate assistance may be required."
    ),
    ActionType.FALLEN: (
        "Person #{track_id} has fallen and remains on ground at {camera_name}. "
        "Medical attention may be required. Duration: {duration:.0f}s."
    ),
    ActionType.LOITERING: (
        "Suspicious loitering detected — person #{track_id} has remained "
        "in the area for {duration:.0f} seconds at {camera_name}."
    ),
    ActionType.SUSPICIOUS: (
        "Suspicious movement pattern detected for person #{track_id} "
        "at {camera_name}. Motion anomaly score: {confidence:.0%}."
    ),
    ActionType.RUNNING: (
        "Running detected — person #{track_id} moving at elevated speed "
        "at {camera_name}."
    ),
}

ANOMALY_TEMPLATES = {
    "zone_intrusion": (
        "INTRUSION ALERT: Person #{track_id} entered restricted zone '{zone_name}' "
        "at {camera_name}. Unauthorized access detected."
    ),
    "abandoned_object": (
        "ABANDONED OBJECT: {class_name} (track #{track_id}) has been unattended "
        "for {alone_time_sec} seconds at {camera_name}."
    ),
    "crowd_congestion": (
        "CROWD ALERT: Crowd density exceeds safe threshold at {camera_name}. "
        "{person_count} persons detected. Congestion score: {congestion:.0%}."
    ),
}


class IncidentReportGenerator:
    """
    Generates natural language incident summaries.
    Uses template-based generation (production builds can use LLM).
    """

    def generate(
        self,
        incident_type: str,
        camera_name: str,
        context: Dict[str, Any],
    ) -> str:
        """Generate human-readable incident description."""
        try:
            # Try action-based template
            if incident_type in ActionType.__members__.values():
                action = ActionType(incident_type)
                template = INCIDENT_TEMPLATES.get(action)
                if template:
                    return template.format(camera_name=camera_name, **context)

            # Try anomaly template
            template = ANOMALY_TEMPLATES.get(incident_type)
            if template:
                return template.format(camera_name=camera_name, **context)

        except (KeyError, ValueError) as e:
            logger.debug(f"Template formatting error: {e}")

        return (
            f"Security event detected at {camera_name}. "
            f"Type: {incident_type}. Review footage for details."
        )

    def generate_full_report(
        self,
        incidents: List[Dict],
        camera_name: str,
        time_window_sec: int = 300,
    ) -> str:
        """Generate a multi-incident summary report."""
        if not incidents:
            return f"No incidents detected at {camera_name} in the last {time_window_sec}s."

        summary_lines = [
            f"NEUROVISION AI — INCIDENT REPORT",
            f"Camera: {camera_name}",
            f"Analysis window: {time_window_sec}s",
            f"Total incidents: {len(incidents)}",
            "─" * 40,
        ]

        severity_counts: Dict[str, int] = defaultdict(int)
        for inc in incidents:
            severity_counts[inc.get("severity", "medium")] += 1

        for sev in ("critical", "high", "medium", "low"):
            count = severity_counts.get(sev, 0)
            if count > 0:
                summary_lines.append(f"  [{sev.upper()}] {count} incident(s)")

        summary_lines.append("─" * 40)

        for i, inc in enumerate(incidents, 1):
            summary_lines.append(
                f"{i}. [{inc.get('severity', 'MEDIUM').upper()}] "
                f"{inc.get('title', 'Unknown incident')}"
            )
            if inc.get("description"):
                summary_lines.append(f"   {inc['description']}")

        return "\n".join(summary_lines)


# ─── Alert Engine ─────────────────────────────────────────────────────────────

@dataclass
class AlertEvent:
    camera_id: str
    camera_name: str
    alert_type: str
    severity: str
    title: str
    description: str
    track_ids: List[int] = field(default_factory=list)
    confidence: float = 0.0
    snapshot_path: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "track_ids": self.track_ids,
            "confidence": round(self.confidence, 3),
            "snapshot_path": self.snapshot_path,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class SmartAlertEngine:
    """
    Central alert processing engine.
    Evaluates conditions, applies cooldowns, and dispatches alerts.
    """

    def __init__(self):
        self._cooldown = CooldownManager()
        self._reporter = IncidentReportGenerator()
        self._alert_handlers: List = []  # Callback functions
        self._alert_history: List[AlertEvent] = []
        self._max_history = 1000

    def register_handler(self, handler) -> None:
        """Register an async alert handler callback."""
        self._alert_handlers.append(handler)

    async def process_actions(
        self,
        camera_id: str,
        camera_name: str,
        actions: List[ActionPrediction],
    ) -> List[AlertEvent]:
        """Process action predictions and generate alerts."""
        alerts = []
        alert_actions = {
            ActionType.FIGHTING, ActionType.FALLING, ActionType.FALLEN,
            ActionType.LOITERING, ActionType.SUSPICIOUS,
        }

        for action_pred in actions:
            if action_pred.action not in alert_actions:
                continue
            if action_pred.confidence < 0.55:
                continue

            cooldown = settings.alerts.zone_alert_cooldown
            if not self._cooldown.can_alert(camera_id, action_pred.action.value, cooldown):
                continue

            severity = SEVERITY_MAP.get(action_pred.action, "medium")
            context = {
                "track_id": action_pred.track_id,
                "track_ids": [action_pred.track_id],
                "confidence": action_pred.confidence,
                "duration": action_pred.supporting_evidence.get("time_in_scene_sec", 0),
            }

            if action_pred.action == ActionType.FIGHTING:
                other = action_pred.supporting_evidence.get("other_track")
                context["track_ids"] = [action_pred.track_id, other] if other else [action_pred.track_id]

            title = f"{action_pred.action.value.replace('_', ' ').title()} Detected"
            description = self._reporter.generate(
                action_pred.action.value, camera_name, context
            )

            event = AlertEvent(
                camera_id=camera_id,
                camera_name=camera_name,
                alert_type=action_pred.action.value,
                severity=severity,
                title=title,
                description=description,
                track_ids=context["track_ids"],
                confidence=action_pred.confidence,
                metadata=action_pred.supporting_evidence,
            )

            alerts.append(event)
            await self._dispatch(event)

        return alerts

    async def process_anomalies(
        self,
        camera_id: str,
        camera_name: str,
        anomalies: List[AnomalyResult],
    ) -> List[AlertEvent]:
        """Process anomaly detection results and generate alerts."""
        alerts = []

        for anomaly in anomalies:
            cooldown = settings.alerts.zone_alert_cooldown
            if not self._cooldown.can_alert(camera_id, anomaly.anomaly_type, cooldown):
                continue

            severity = ANOMALY_SEVERITY.get(anomaly.anomaly_type, "medium")
            context = {
                "track_id": anomaly.track_id,
                **anomaly.details,
            }

            description = self._reporter.generate(
                anomaly.anomaly_type, camera_name, context
            )
            title = anomaly.anomaly_type.replace("_", " ").title() + " Alert"

            event = AlertEvent(
                camera_id=camera_id,
                camera_name=camera_name,
                alert_type=anomaly.anomaly_type,
                severity=severity,
                title=title,
                description=description,
                track_ids=[anomaly.track_id],
                confidence=anomaly.anomaly_score,
                metadata=anomaly.details,
            )

            alerts.append(event)
            await self._dispatch(event)

        return alerts

    async def process_crowd(
        self,
        camera_id: str,
        camera_name: str,
        person_count: int,
        congestion_score: float,
    ) -> Optional[AlertEvent]:
        """Alert on crowd congestion."""
        if congestion_score < 0.8:
            return None
        if not self._cooldown.can_alert(camera_id, "crowd_congestion", 60):
            return None

        context = {
            "person_count": person_count,
            "congestion": congestion_score,
        }
        description = self._reporter.generate("crowd_congestion", camera_name, context)

        event = AlertEvent(
            camera_id=camera_id,
            camera_name=camera_name,
            alert_type="crowd_congestion",
            severity="high" if congestion_score > 0.9 else "medium",
            title="Crowd Congestion Alert",
            description=description,
            confidence=congestion_score,
            metadata=context,
        )

        await self._dispatch(event)
        return event

    async def _dispatch(self, event: AlertEvent) -> None:
        """Dispatch alert to all registered handlers."""
        self._alert_history.append(event)
        if len(self._alert_history) > self._max_history:
            self._alert_history.pop(0)

        for handler in self._alert_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

        # Webhook delivery
        if settings.alerts.webhook_url:
            asyncio.create_task(self._webhook_deliver(event))

    async def _webhook_deliver(self, event: AlertEvent) -> None:
        """Deliver alert to webhook endpoint."""
        try:
            async with httpx.AsyncClient(timeout=settings.alerts.webhook_timeout) as client:
                await client.post(
                    settings.alerts.webhook_url,
                    json=event.to_dict(),
                )
        except Exception as e:
            logger.warning(f"Webhook delivery failed: {e}")

    def get_recent_alerts(self, n: int = 50) -> List[AlertEvent]:
        return self._alert_history[-n:]

    def reset_camera_cooldowns(self, camera_id: str) -> None:
        self._cooldown.reset(camera_id)
