from __future__ import annotations

import time

from sqlmodel import Session

from app.llm.client import LLMClient, LLMResponse
from app.models import LLMCallLogRecord


class DBLoggingLLMClient:
    """Wraps any LLMClient, persisting one LLMCallLogRecord row per call.

    Composes with LoggingLLMClient rather than duplicating it -- wrap the
    structured-logging client with this one (or vice versa) to get both the
    log line and the durable DB record from a single call site.
    """

    def __init__(self, inner: LLMClient, session: Session, review_id: int | None) -> None:
        self._inner = inner
        self._session = session
        self._review_id = review_id

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        start = time.monotonic()
        response = await self._inner.complete(
            prompt, max_tokens=max_tokens, temperature=temperature
        )
        latency_seconds = time.monotonic() - start

        record = LLMCallLogRecord(
            review_id=self._review_id,
            prompt=prompt,
            output=response.text,
            latency_seconds=latency_seconds,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )
        self._session.add(record)
        self._session.commit()

        return response
