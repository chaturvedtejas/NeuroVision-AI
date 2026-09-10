-- NeuroVision AI — Database Initialization
-- This file runs once when the PostgreSQL container is first created

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- For fuzzy text search

-- Set default timezone
SET timezone = 'UTC';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE neurovision TO neurovision;

-- Log
DO $$
BEGIN
    RAISE NOTICE 'NeuroVision AI database initialized at %', NOW();
END$$;
