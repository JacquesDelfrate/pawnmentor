from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import ConfigError, Settings
from app.llm.vllm_client import VLLMClient, build_vllm_client


def test_build_vllm_client_requires_model() -> None:
    settings = Settings(stockfish_path="unused", vllm_model="")
    with pytest.raises(ConfigError):
        build_vllm_client(settings)


def test_build_vllm_client_constructs_with_configured_model() -> None:
    settings = Settings(stockfish_path="unused", vllm_model="Qwen/Qwen3-8B-Instruct")
    client = build_vllm_client(settings)
    assert client._model == "Qwen/Qwen3-8B-Instruct"


def _fake_openai_response(text: str, prompt_tokens: int, completion_tokens: int) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.mark.asyncio
async def test_complete_extracts_text_and_tokens() -> None:
    client = VLLMClient("http://localhost:8000/v1", "qwen3")
    client._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
        return_value=_fake_openai_response("hello", prompt_tokens=10, completion_tokens=3)
    )

    result = await client.complete("hi", max_tokens=50, temperature=0.2)

    assert result.text == "hello"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 3
    client._client.chat.completions.create.assert_awaited_once_with(
        model="qwen3",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=50,
        temperature=0.2,
    )


@pytest.mark.asyncio
async def test_complete_raises_on_missing_content() -> None:
    client = VLLMClient("http://localhost:8000/v1", "qwen3")
    client._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
        return_value=_fake_openai_response(None, prompt_tokens=0, completion_tokens=0)  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError):
        await client.complete("hi")


@pytest.mark.asyncio
async def test_complete_defaults_tokens_to_zero_without_usage() -> None:
    client = VLLMClient("http://localhost:8000/v1", "qwen3")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))], usage=None
    )
    client._client.chat.completions.create = AsyncMock(return_value=response)  # type: ignore[method-assign]

    result = await client.complete("hi")

    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
