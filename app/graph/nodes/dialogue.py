from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chess

from app.graph.nodes.classify import Classification
from app.graph.nodes.taxonomy import ErrorCategory
from app.guards.move_validator import validate_llm_output
from app.llm.client import LLMClient

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "dialogue_v1.md"


@dataclass(frozen=True, slots=True)
class CoachingMessage:
    classification: Classification
    text: str


async def generate_dialogue(
    llm: LLMClient,
    classification: Classification,
    player_rating: int,
) -> CoachingMessage:
    """Generates the Socratic explanation for a classified error -- Rule 0's
    remaining LLM jobs (dialogue, explanations). Every move the LLM is given
    license to mention is passed in as an already-verified fact, and the
    output is checked by move_validator before being trusted; category
    details are deliberately phrased with piece names rather than square
    coordinates to avoid move_validator false-positiving on ordinary prose
    ("the knight on e5" is SAN-shaped enough to get flagged as an unverified
    move token by the same regex that's supposed to catch hallucinations).
    """
    diagnosis = classification.diagnosis
    move_eval = diagnosis.flagged_error.move_eval
    board_before = chess.Board(move_eval.eval_before.fen)

    move_played = move_eval.move
    best_move = chess.Move.from_uci(move_eval.eval_before.analysis.best_move_uci)

    prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        player_rating=player_rating,
        mover_color="White" if move_eval.mover == chess.WHITE else "Black",
        move_played_san=board_before.san(move_played),
        best_move_san=board_before.san(best_move),
        delta_cp_abs=abs(move_eval.delta_cp),
        category_details=_category_details(classification),
    )

    response = await llm.complete(prompt, max_tokens=400, temperature=0.4)

    validate_llm_output(response.text, board_before, [move_played, best_move])

    return CoachingMessage(classification=classification, text=response.text)


def _category_details(classification: Classification) -> str:
    diagnosis = classification.diagnosis
    motifs = diagnosis.motifs_after
    category = classification.category

    if category == ErrorCategory.HUNG_PIECE and motifs.hanging_pieces:
        hp = motifs.hanging_pieces[0]
        return (
            f"Your {chess.piece_name(hp.piece_type)} is now undefended "
            "and can be captured for free."
        )
    if category == ErrorCategory.ALLOWED_FORK and motifs.forks:
        fk = motifs.forks[0]
        return (
            f"The opponent's {chess.piece_name(fk.forker_piece_type)} now attacks two "
            "of your pieces at the same time -- you can only save one."
        )
    if category == ErrorCategory.WALKED_INTO_PIN and motifs.pins:
        pin = motifs.pins[0]
        return (
            f"Your {chess.piece_name(pin.pinned_piece_type)} is now pinned against "
            f"your king by the opponent's {chess.piece_name(pin.pinner_piece_type)}."
        )
    if category == ErrorCategory.BAD_TRADE:
        return "The capture you played loses material once the full exchange is played out."
    return (
        "The evaluation dropped significantly here, though it doesn't match one of "
        "the specific patterns this coach checks for."
    )
