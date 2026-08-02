from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.db import create_db_engine, init_db
from app.llm.client import LLMResponse
from app.llm.db_logging_client import DBLoggingLLMClient
from app.models import LLMCallLogRecord


class _FakeLLMClient:
    async def complete(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        return LLMResponse(text="the answer", prompt_tokens=7, completion_tokens=3)


@pytest.mark.asyncio
async def test_db_logging_client_persists_a_record(tmp_path: Path) -> None:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)

    with Session(engine) as session:
        client = DBLoggingLLMClient(_FakeLLMClient(), session, review_id=None)
        result = await client.complete("what happened", max_tokens=10, temperature=0.1)

        assert result.text == "the answer"

        stored = session.exec(select(LLMCallLogRecord)).one()
        assert stored.prompt == "what happened"
        assert stored.output == "the answer"
        assert stored.prompt_tokens == 7
        assert stored.completion_tokens == 3
        assert stored.review_id is None
