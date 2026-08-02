from __future__ import annotations

import logging

import pytest

from app.llm.client import LLMResponse
from app.llm.logging_client import LoggingLLMClient


class _FakeLLMClient:
    def __init__(self, response: LLMResponse) -> None:
        self._response = response
        self.calls: list[tuple[str, int, float]] = []

    async def complete(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        self.calls.append((prompt, max_tokens, temperature))
        return self._response


@pytest.mark.asyncio
async def test_logging_client_passes_through_response() -> None:
    fake = _FakeLLMClient(LLMResponse(text="hello", prompt_tokens=5, completion_tokens=2))
    client = LoggingLLMClient(fake)

    result = await client.complete("prompt text", max_tokens=100, temperature=0.5)

    assert result.text == "hello"
    assert fake.calls == [("prompt text", 100, 0.5)]


@pytest.mark.asyncio
async def test_logging_client_logs_call_details(caplog: pytest.LogCaptureFixture) -> None:
    fake = _FakeLLMClient(LLMResponse(text="hello", prompt_tokens=5, completion_tokens=2))
    client = LoggingLLMClient(fake)

    with caplog.at_level(logging.INFO, logger="app.llm"):
        await client.complete("prompt text", max_tokens=100, temperature=0.5)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.prompt == "prompt text"
    assert record.output == "hello"
    assert record.prompt_tokens == 5
    assert record.completion_tokens == 2
    assert record.latency_seconds >= 0
