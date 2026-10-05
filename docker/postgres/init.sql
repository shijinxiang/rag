-- =============================================================================
-- PostgreSQL Initialization — RAG Agent Database
-- =============================================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text search

-- Verify extensions
DO $$
BEGIN
    RAISE NOTICE 'Extensions enabled: vector, uuid-ossp, pg_trgm';
    RAISE NOTICE 'Database extensions initialized; Alembic creates application tables.';
END $$;
