from __future__ import annotations

import chess
import pytest

from app.engine.pool import EnginePool
from app.engine.trajectory import eval_trajectory
from app.graph.nodes.classify import classify_error
from app.graph.nodes.diagnosis import diagnose_error
from app.graph.nodes.dialogue import (
    MAX_DIALOGUE_ATTEMPTS,
    EmptyDialogueError,
    generate_dialogue,
)
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


class _ScriptedLLMClient:
    """Returns a different canned response per call, recording each prompt."""

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.prompts: list[str] = []

    async def complete(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        self.prompts.append(prompt)
        text = self.texts[min(len(self.prompts) - 1, len(self.texts) - 1)]
        return LLMResponse(text=text, prompt_tokens=10, completion_tokens=10)


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


@pytest.mark.asyncio
async def test_reasoning_block_is_stripped_before_delivery(hung_piece_classification) -> None:
    # Reasoning models emit internal scratch work first. It must never reach
    # the user, and it must not be validated -- real Qwen3 output deliberated
    # over squares the final answer never used, which failed the validator on
    # text that was never going to be shown.
    llm = _FakeLLMClient(
        "<think>\nThe player hung the knight on d5. Maybe mention Qh5 or e4 as ideas.\n</think>\n\n"
        "Your knight ended up somewhere it had no defenders, so Nd5 gave it away.\n\n"
        "What could you check about a square before moving a piece onto it?"
    )

    message = await generate_dialogue(llm, hung_piece_classification, player_rating=1200)

    assert "<think>" not in message.text
    assert "Qh5" not in message.text
    assert message.text.startswith("Your knight ended up")


@pytest.mark.asyncio
async def test_retries_when_output_contains_a_bare_square(hung_piece_classification) -> None:
    # A bare square like "d5" is indistinguishable from a pawn-push claim to
    # the validator, and a 14B model emits them despite the prompt banning
    # it. The retry quotes the rejected token back rather than loosening the
    # guard or editing the model's text to sneak it through.
    llm = _ScriptedLLMClient(
        "You moved your knight to d5 where nothing defended it.",
        "You moved your knight somewhere nothing defended it, so Nd5 lost it.\n\n"
        "What might you check about a square before moving onto it?",
    )

    message = await generate_dialogue(llm, hung_piece_classification, player_rating=1200)

    assert len(llm.prompts) == 2
    assert "previous attempt was rejected" in llm.prompts[1]
    assert "d5" in llm.prompts[1]
    assert message.text.startswith("You moved your knight somewhere")


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts_rather_than_delivering(
    hung_piece_classification,
) -> None:
    # Failing closed is the point: a model that never complies must not get
    # its unverified text shown to the player.
    llm = _ScriptedLLMClient("Try Qh5 instead, it wins on the spot.")

    with pytest.raises(MoveValidationError):
        await generate_dialogue(llm, hung_piece_classification, player_rating=1200)

    assert len(llm.prompts) == MAX_DIALOGUE_ATTEMPTS


@pytest.mark.asyncio
async def test_output_that_is_only_reasoning_raises(hung_piece_classification) -> None:
    # Truncation mid-reasoning leaves nothing behind once the block is cut;
    # surfacing that beats returning an empty coaching message.
    llm = _FakeLLMClient("<think>\nStill thinking about it...\n</think>")

    with pytest.raises(EmptyDialogueError):
        await generate_dialogue(llm, hung_piece_classification, player_rating=1200)
