from __future__ import annotations

from openai import AsyncOpenAI

from app.config import ConfigError, Settings
from app.llm.client import LLMResponse


class VLLMClient:
    """LLMClient implementation targeting a local vLLM OpenAI-compatible server.

    vLLM serves an OpenAI-compatible /v1/chat/completions endpoint, so this
    is just the openai SDK pointed at a custom base_url -- no vLLM-specific
    package needed. `local models must remain drop-in swappable`: only this
    file and its construction (build_vllm_client) know a specific provider
    exists; graph nodes depend on the LLMClient protocol only.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout: float = 60.0,
        api_key: str = "not-needed",
    ) -> None:
        self._model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("vLLM response contained no content")

        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage is not None else 0
        completion_tokens = usage.completion_tokens if usage is not None else 0

        return LLMResponse(
            text=content, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        )


def build_vllm_client(settings: Settings) -> VLLMClient:
    if not settings.vllm_model:
        raise ConfigError(
            "VLLM_MODEL environment variable must be set to the model id vLLM is serving."
        )
    return VLLMClient(
        settings.vllm_base_url, settings.vllm_model, timeout=settings.llm_timeout_seconds
    )
