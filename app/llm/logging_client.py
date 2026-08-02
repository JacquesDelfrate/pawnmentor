from __future__ import annotations

import logging
import time

from app.llm.client import LLMClient, LLMResponse

logger = logging.getLogger("app.llm")


class LoggingLLMClient:
    """Wraps any LLMClient, logging input, output, latency, and tokens for
    every call, per project convention. Implements LLMClient itself, so it's
    a transparent decorator -- graph nodes hold a LoggingLLMClient without
    knowing or caring which concrete provider is underneath.
    """

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner

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

        logger.info(
            "llm_call",
            extra={
                "prompt": prompt,
                "output": response.text,
                "latency_seconds": latency_seconds,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        return response
