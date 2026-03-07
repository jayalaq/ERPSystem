-- PostgreSQL initialization script
-- Creates extensions needed by the ERP system

CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- Fuzzy text search
CREATE EXTENSION IF NOT EXISTS unaccent;     -- Accent-insensitive search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation
