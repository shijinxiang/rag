"""
=============================================================================
Queries API — Q&A endpoints with SSE streaming support
=============================================================================
"""
import json
import logging

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_authenticated_user, get_query_service, user_filters
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.query import (
    AgentQueryRequest,
    QueryRequest,
    QueryResponse,
    RetrieveRequest,
    RetrieveResponse,
    RetrieveResult,
)
from app.services.query_service import QueryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/queries", tags=["Queries"])


@router.post(
    "",
    response_model=QueryResponse,
    responses={400: {"model": ErrorResponse}},
)
async def ask_question(
    body: QueryRequest,
    query_service: QueryService = Depends(get_query_service),
    user: User = Depends(get_authenticated_user),
):
    """
    Ask a question and get an answer with source citations.

    The system will:
    1. Retrieve relevant document chunks via vector similarity
    2. Build a prompt with the retrieved context
    3. Generate an answer with citations via LLM
    """
    result = await query_service.ask(
        question=body.question,
        top_k=body.top_k,
        filters=user_filters(user),
        stream=False,
    )
    from app.core.metrics import QUERY_REQUESTS_TOTAL, RETRIEVAL_DOCUMENTS
    QUERY_REQUESTS_TOTAL.labels(status="success").inc()
    RETRIEVAL_DOCUMENTS.observe(result.retrieval_count)

    return QueryResponse(
        query_id=result.query_id,
        question=result.question,
        answer=result.answer,
        sources=result.sources,
        retrieval_count=result.retrieval_count,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        review_status=result.review_status,
    )


@router.post("/stream")
async def ask_question_stream(
    body: QueryRequest,
    request: Request,
    query_service: QueryService = Depends(get_query_service),
    user: User = Depends(get_authenticated_user),
):
    """
    Ask a question and stream the answer via Server-Sent Events (SSE).

    Events:
    - `sources`: Citation list sent before the answer starts.
    - `token`: A chunk of generated text.
    - `done`: End of stream with final metadata.
    - `error`: Error information.
    """
    result = await query_service.ask(
        question=body.question,
        top_k=body.top_k,
        filters=user_filters(user),
        stream=True,
    )
    from app.core.metrics import QUERY_REQUESTS_TOTAL, RETRIEVAL_DOCUMENTS
    RETRIEVAL_DOCUMENTS.observe(result.retrieval_count)

    async def event_generator():
        try:
            # Send sources first
            yield {
                "event": "sources",
                "data": json.dumps(result.sources, ensure_ascii=False),
            }

            # Stream tokens
            async for chunk in result.stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    yield {
                        "event": "token",
                        "data": token,
                    }

                # Check for client disconnect
                if await request.is_disconnected():
                    QUERY_REQUESTS_TOTAL.labels(status="cancelled").inc()
                    return

            # Send completion event
            QUERY_REQUESTS_TOTAL.labels(status="success").inc()
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "query_id": result.query_id,
                        "retrieval_count": result.retrieval_count,
                    },
                    ensure_ascii=False,
                ),

            }
        except Exception as exc:
            logger.exception("Streaming error")
            QUERY_REQUESTS_TOTAL.labels(status="failure").inc()
            yield {
                "event": "error",
                "data": json.dumps({"message": str(exc)}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_only(
    body: RetrieveRequest,
    query_service: QueryService = Depends(get_query_service),
    user: User = Depends(get_authenticated_user),
):
    """
    Retrieve relevant documents without generating an answer.
    Useful for debugging and evaluating retrieval quality.
    """
    results = await query_service.retrieve_only(
        question=body.question,
        top_k=body.top_k,
        filters=user_filters(user),
    )
    from app.core.metrics import QUERY_REQUESTS_TOTAL, RETRIEVAL_DOCUMENTS
    QUERY_REQUESTS_TOTAL.labels(status="success").inc()
    RETRIEVAL_DOCUMENTS.observe(len(results))

    return RetrieveResponse(
        query=body.question,
        results=[RetrieveResult(**r) for r in results],
        count=len(results),
    )


@router.post("/agent", response_model=QueryResponse)
async def ask_agent(
    body: AgentQueryRequest,
    query_service: QueryService = Depends(get_query_service),
    user: User = Depends(get_authenticated_user),
):
    """
    Ask a question using the LangGraph Agent.

    The agent will:
    1. Classify the question intent (retrieval_qa, general_chat, document_operation)
    2. For retrieval_qa: rewrite → hybrid retrieve → rerank → generate
    3. For general_chat: answer directly without retrieval
    4. Return answer with source citations
    """
    result = await query_service.ask_with_agent(
        question=body.question,
        top_k=body.top_k,
        filters=user_filters(user),
    )
    from app.core.metrics import QUERY_REQUESTS_TOTAL, RETRIEVAL_DOCUMENTS
    QUERY_REQUESTS_TOTAL.labels(status="success").inc()
    RETRIEVAL_DOCUMENTS.observe(result.retrieval_count)

    return QueryResponse(
        query_id=result.query_id,
        question=result.question,
        answer=result.answer,
        sources=result.sources,
        retrieval_count=result.retrieval_count,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        review_status=result.review_status,
    )


def _build_filters(department: str | None = None) -> dict | None:
    """Build metadata filter dict for vector search."""
    if department:
        return {"department": department}
    return None
