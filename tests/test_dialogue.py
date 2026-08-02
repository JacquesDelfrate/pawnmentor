from __future__ import annotations

import chess
import pytest

from app.engine.pool import EnginePool
from app.engine.trajectory import eval_trajectory
from app.graph.nodes.classify import classify_error
from app.graph.nodes.diagnosis import diagnose_error
from app.graph.nodes.dialogue import generate_dialogue
from app.graph.nodes.filter import FlaggedError
from app.guards.move_validator import MoveValidationError
from app.llm.client import LLMResponse

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}

pytestmark = pytest.mark.engine


class _FakeLLMClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.last_prompt: str | None = None

    async def complete(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        self.last_prompt = prompt
        return LLMResponse(text=self.text, prompt_tokens=10, completion_tokens=10)


@pytest.fixture
def pool(stockfish_path: str):
    p = EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS, default_timeout=20.0)
    yield p
    p.close()


@pytest.fixture
def hung_piece_classification(pool: EnginePool):
    board = chess.Board("6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1")
    moves = [chess.Move.from_uci("c3d5")]
    trajectory = eval_trajectory(pool, board, moves, depth=10)
    flagged = FlaggedError(move_eval=trajectory[0], reachability_gap_cp=0)
    diagnosis = diagnose_error(pool, flagged, depth=16)
    return classify_error(diagnosis)


@pytest.mark.asyncio
async def test_generate_dialogue_happy_path(hung_piece_classification) -> None:
    llm = _FakeLLMClient(
        "Your knight jumped to a square where it's not defended, so Nd5 just gives "
        "it away for nothing. The engine preferred a quieter move instead.\n\n"
        "Before your next piece move, what's worth checking about the square it's landing on?"
    )

    message = await generate_dialogue(llm, hung_piece_classification, player_rating=1200)

    assert message.text == llm.text
    assert llm.last_prompt is not None
    assert "undefended and can be captured for free" in llm.last_prompt


@pytest.mark.asyncio
async def test_generate_dialogue_rejects_hallucinated_move(hung_piece_classification) -> None:
    llm = _FakeLLMClient("You should have played Qh5 instead, threatening mate.")

    with pytest.raises(MoveValidationError):
        await generate_dialogue(llm, hung_piece_classification, player_rating=1200)
