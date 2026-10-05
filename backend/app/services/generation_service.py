"""
=============================================================================
Generation Service — LLM answer generation with citations
=============================================================================
"""
import logging

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个企业知识库助手。请严格根据以下提供的文档片段回答用户的问题。

## 规则
1. 如果文档中有相关信息，请准确引用并回答。
2. 如果文档中没有相关信息，请如实告知"根据现有文档无法确认"，不要编造内容。
3. 回答时在引用文档的地方标注来源编号，如 [1]、[2]。
4. 如果涉及流程或步骤，按顺序列出。
5. 使用中文回答，保持专业、清晰、简洁。

## 参考文档
{context}"""


class GenerationService:
    """LLM answer generation with streaming and citation support."""

    def __init__(self, client: AsyncOpenAI | None = None):
        self._client = client or AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=settings.OPENAI_MAX_RETRIES,
            timeout=settings.OPENAI_TIMEOUT,
        )
        self._model = settings.OPENAI_MODEL

    def build_prompt(self, question: str, contexts: list["ContextDoc"]) -> tuple[str, str]:
        """
        Build system and user prompts from retrieved contexts.

        Args:
            question: User's question.
            contexts: List of ContextDoc with content and metadata.

        Returns:
            (system_prompt, user_prompt) tuple.
        """
        context_parts = []
        for i, ctx in enumerate(contexts, 1):
            header = (
                f"--- [来源 {i}] 文档: {ctx.doc_title} | "
                f"页码: {ctx.page_number or 'N/A'} | "
                f"chunk_id: {ctx.chunk_id} ---"
            )
            context_parts.append(f"{header}\n{ctx.content}")

        context_text = "\n\n".join(context_parts)
        system_prompt = SYSTEM_PROMPT.format(context=context_text)
        user_prompt = f"用户问题：{question}\n\n请根据以上参考文档回答。"
        return system_prompt, user_prompt

    async def generate(
        self,
        question: str,
        contexts: list["ContextDoc"],
        temperature: float = 0.3,
        stream: bool = False,
    ) -> "GenerationResult":
        """
        Generate an answer using LLM.

        Args:
            question: User's question.
            contexts: Retrieved context documents.
            temperature: LLM temperature (lower = more factual).
            stream: If True, return an async iterator for SSE streaming.

        Returns:
            GenerationResult with answer, citations, and token usage.
        """
        system_prompt, user_prompt = self.build_prompt(question, contexts)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if stream:
            # Return the async stream for SSE handling at API layer
            stream_response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            return GenerationResult(
                answer="",
                citations=self._build_citations(contexts),
                stream=stream_response,
            )

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            stream=False,
        )

        answer = response.choices[0].message.content or ""
        usage = response.usage

        return GenerationResult(
            answer=answer,
            citations=self._build_citations(contexts),
            stream=None,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

    def _build_citations(self, contexts: list["ContextDoc"]) -> list[dict]:
        """Build citation metadata from context documents."""
        return [
            {
                "index": i + 1,
                "doc_title": ctx.doc_title,
                "doc_id": ctx.doc_id,
                "chunk_id": ctx.chunk_id,
                "page_number": ctx.page_number,
                "score": ctx.score,
                "excerpt": ctx.content[:200] + "..." if len(ctx.content) > 200 else ctx.content,
            }
            for i, ctx in enumerate(contexts)
        ]


class ContextDoc:
    """A retrieved context document with metadata."""

    def __init__(
        self,
        content: str,
        doc_title: str = "Unknown",
        doc_id: str = "",
        chunk_id: str = "",
        page_number: int | None = None,
        score: float = 0.0,
        metadata: dict | None = None,
    ):
        self.content = content
        self.doc_title = doc_title
        self.doc_id = doc_id
        self.chunk_id = chunk_id
        self.page_number = page_number
        self.score = score
        self.metadata = metadata or {}


class GenerationResult:
    """Result of an LLM generation."""

    def __init__(
        self,
        answer: str,
        citations: list[dict],
        stream=None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ):
        self.answer = answer
        self.citations = citations
        self.stream = stream
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
