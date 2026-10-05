"""
=============================================================================
Embedding Service — OpenAI text-embedding-3 with batching + retry
=============================================================================
"""
import asyncio
import logging

from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)

# Batch size for embedding API calls
EMBEDDING_BATCH_SIZE = 100


class EmbeddingService:
    """Generates embeddings for documents and queries using OpenAI."""

    MAX_DIMENSIONS_BY_MODEL = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }

    def __init__(self, client: AsyncOpenAI | None = None):
        self._client = client or AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=settings.OPENAI_MAX_RETRIES,
            timeout=settings.OPENAI_TIMEOUT,
        )
        self._model = settings.OPENAI_EMBEDDING_MODEL
        self._dimensions = settings.OPENAI_EMBEDDING_DIMENSIONS

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((Exception,)),
    )
    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Call OpenAI embeddings API for a batch of texts."""
        params = {
            "model": self._model,
            "input": texts,
        }
        # dimensions param is only supported by text-embedding-3 models
        if self._model.startswith("text-embedding-3"):
            params["dimensions"] = self._dimensions

        response = await self._client.embeddings.create(**params)

        # Sort by index to preserve order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of document texts (batched)."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[i : i + EMBEDDING_BATCH_SIZE]
            logger.debug("Embedding batch %d-%d of %d", i, i + len(batch), len(texts))
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.extend(batch_embeddings)
            # Small delay between batches to respect rate limits
            if i + EMBEDDING_BATCH_SIZE < len(texts):
                await asyncio.sleep(0.2)

        return all_embeddings

    async def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query string."""
        embeddings = await self._embed_batch([query])
        return embeddings[0]
