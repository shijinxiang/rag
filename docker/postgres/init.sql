-- =============================================================================
-- PostgreSQL Initialization — RAG Agent Database
-- =============================================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text search

-- GIN index for pg_trgm fuzzy text search (BM25 / sparse retrieval)
CREATE INDEX IF NOT EXISTS idx_document_chunks_content_trgm
ON document_chunks USING GIN (content gin_trgm_ops);

-- Verify extensions
DO $$
BEGIN
    RAISE NOTICE 'Extensions enabled: vector, uuid-ossp, pg_trgm';
    RAISE NOTICE 'Indexes created: idx_document_chunks_content_trgm';
END $$;
