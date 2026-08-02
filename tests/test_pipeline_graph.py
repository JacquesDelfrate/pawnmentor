from __future__ import annotations

import chess
import pytest

from app.engine.pool import EnginePool
from app.graph.graph import build_pipeline_graph
from app.llm.client import LLMResponse

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}

pytestmark = pytest.mark.engine


class _FakeLLMClient:
    async def complete(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        return LLMResponse(
            text="Your piece was left undefended and lost for nothing.\n\n"
            "What square-safety check is worth making before every move?",
            prompt_tokens=10,
            completion_tokens=10,
        )


@pytest.fixture
def full_pool(stockfish_path: str):
    p = EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS, default_timeout=20.0)
    yield p
    p.close()


@pytest.mark.asyncio
async def test_pipeline_flags_and_explains_a_clear_blunder(
    stockfish_path: str, full_pool: EnginePool
) -> None:
    board = chess.Board("6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1")
    graph = build_pipeline_graph(full_pool, stockfish_path, _FakeLLMClient(), scan_depth=10)

    result = await graph.ainvoke(
        {
            "fen": board.fen(),
            "moves_uci": ["c3d5"],
            "player_color": chess.WHITE,
            "player_rating": 1200,
        },
        config={"configurable": {"thread_id": "test-pipeline"}},
    )

    assert len(result["move_evals"]) == 1
    assert len(result["flagged_errors"]) == 1
    assert len(result["diagnoses"]) == 1
    assert result["classifications"][0].category.value == "hung_piece"
    assert len(result["coaching_messages"]) == 1
    assert "undefended" in result["coaching_messages"][0].text
