from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int


class LLMClient(Protocol):
    """Provider-agnostic interface graph nodes depend on; no chess logic here."""

    async def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse: ...
