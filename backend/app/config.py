"""
=============================================================================
Application Configuration — pydantic-settings
=============================================================================
Centralizes all configuration from environment variables and .env files.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    APP_NAME: str = "Enterprise Knowledge RAG Agent"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"  # development | staging | production
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    SECRET_KEY: str = "change-me-to-a-random-string-at-least-32-chars"
    LOG_LEVEL: str = "INFO"

    # ---- Database (PostgreSQL) ----
    DATABASE_URL: str = "postgresql+asyncpg://rag_user:rag_password@localhost:5432/rag_agent"
    DATABASE_URL_SYNC: str = "postgresql://rag_user:rag_password@localhost:5432/rag_agent"

    # ---- OpenAI ----
    OPENAI_API_KEY: str = "sk-your-api-key-here"
    OPENAI_MODEL: str = "gpt-4o"  # Default for MVP; use gpt-5.5 in production
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536
    OPENAI_FALLBACK_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_RETRIES: int = 3
    OPENAI_TIMEOUT: int = 60

    # ---- Vector Store ----
    VECTOR_STORE_TYPE: str = "pgvector"  # pgvector | milvus | chroma
    VECTOR_STORE_DIMENSIONS: int = 1536
    VECTOR_STORE_INDEX_TYPE: str = "hnsw"  # hnsw | ivfflat

    # ---- Redis / Celery ----
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ---- MinIO / S3 ----
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "rag-documents"
    MINIO_USE_SSL: bool = False

    # ---- JWT Auth ----
    JWT_SECRET_KEY: str = "change-me-to-a-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---- CORS ----
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # ---- RAG Configuration ----
    RAG_TOP_K: int = 10
    RAG_RERANK_TOP_K: int = 5
    RAG_CHUNK_SIZE: int = 1000
    RAG_CHUNK_OVERLAP: int = 200
    RAG_HYBRID_SEARCH_ENABLED: bool = False  # Enable in stage 2
    RAG_RERANKER_ENABLED: bool = False  # Enable in stage 2
    RAG_RERANKER_PROVIDER: str = "cohere"  # cohere | bge | jina

    # ---- LangSmith ----
    LANGSMITH_ENABLED: bool = False
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "rag-agent"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    # ---- Prometheus ----
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090

    # ---- Rate Limiting ----
    RATE_LIMIT_ENABLED: bool = False  # Enable in stage 4
    RATE_LIMIT_PER_MINUTE: int = 60

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()


settings = get_settings()
