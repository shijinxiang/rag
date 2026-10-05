"""Celery application and idempotent document processing task."""
import asyncio
import time
import uuid

from celery import Celery
from celery.signals import worker_init

from app.config import settings

celery_app = Celery(
    "rag_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])


@worker_init.connect
def start_worker_metrics(**kwargs):
    if settings.PROMETHEUS_ENABLED:
        from prometheus_client import start_http_server
        start_http_server(8001)


@celery_app.task(name="rag.process_document", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def process_document(document_id: str) -> str:
    """Run parsing, chunking, and embedding for a previously stored upload."""
    from sqlalchemy import delete, select

    from app.core.metrics import DOCUMENT_PROCESSING_SECONDS, TASKS_TOTAL
    from app.db.session import _get_session_factory, close_db
    from app.db.vector_store import get_vector_store
    from app.models.document import Document, DocumentStatus
    from app.rag.loader import DocumentLoader
    from app.rag.splitter import TextSplitter
    from app.services.embedding_service import EmbeddingService

    async def run() -> str:
        factory = _get_session_factory()
        async with factory() as db:
            doc_id = uuid.UUID(document_id)
            doc = (await db.execute(select(Document).where(Document.id == doc_id).with_for_update())).scalar_one_or_none()
            if doc is None or doc.status == DocumentStatus.READY:
                return document_id
            doc.status = DocumentStatus.PROCESSING
            doc.error_message = None
            started = time.perf_counter()
            try:
                loaded = DocumentLoader.load_document(doc.file_path, doc.file_type)
                chunks = TextSplitter().split_documents(loaded, str(doc.id), doc.title)
                if not chunks:
                    raise ValueError("Document produced no chunks")
                embeddings = await EmbeddingService().embed_documents([chunk.page_content for chunk in chunks])
                from app.models.document import DocumentChunk
                await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
                records = []
                for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                    chunk_id = uuid.uuid5(doc.id, str(index))
                    chunk.metadata.update({"doc_id": str(doc.id), "doc_title": doc.title, "chunk_id": str(chunk_id), "department": doc.department, "access_level": doc.access_level})
                    records.append(DocumentChunk(
                        id=chunk_id,
                        document_id=doc.id,
                        chunk_index=index,
                        content=chunk.page_content,
                        page_number=chunk.metadata.get("page"),
                        chunk_metadata={**chunk.metadata, "chunk_index": index, "chunk_count": len(chunks)},
                        embedding=embedding,
                    ))
                db.add_all(records)
                store = get_vector_store()
                store.delete_by_doc_id(document_id)
                store.store.add_embeddings(texts=[c.page_content for c in chunks], embeddings=embeddings, metadatas=[c.metadata for c in chunks], ids=[str(r.id) for r in records])
                doc.status = DocumentStatus.READY
                doc.chunk_count = len(chunks)
                await db.commit()
                DOCUMENT_PROCESSING_SECONDS.observe(time.perf_counter() - started)
                TASKS_TOTAL.labels(task="process_document", status="success").inc()
                return str(doc.id)
            except Exception as exc:
                await db.rollback()
                doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
                doc.status = DocumentStatus.ERROR
                doc.error_message = str(exc)[:4000]
                await db.commit()
                DOCUMENT_PROCESSING_SECONDS.observe(time.perf_counter() - started)
                TASKS_TOTAL.labels(task="process_document", status="failure").inc()
                raise

    async def run_and_close() -> str:
        try:
            return await run()
        finally:
            # Celery tasks own separate event loops; do not reuse pooled async connections.
            await close_db()

    return asyncio.run(run_and_close())
