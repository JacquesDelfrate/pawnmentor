from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import chess

from app.graph.nodes.classify import Classification
from app.graph.nodes.taxonomy import ErrorCategory
from app.graph.state import MotifReport
from app.guards.move_validator import MoveValidationError, validate_llm_output
from app.llm.client import LLMClient

logger = logging.getLogger("app.graph.dialogue")

_PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "dialogue_v2.md"

MAX_DIALOGUE_ATTEMPTS = 3

# Reasoning models (Qwen3 among them) wrap internal scratch work in <think>
# tags ahead of the real answer. That text is never coaching output, so it is
# cut before anything else happens to the response -- otherwise it would be
# rendered to the user verbatim, and its move-by-move deliberation would trip
# the validator on notation the final answer never actually uses.
_REASONING_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class EmptyDialogueError(RuntimeError):
    pass


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
    delivered text is checked by move_validator before being trusted.

    Bare square names are the practical hazard here: move_validator cannot
    tell "your knight moved to g5" (prose) from "g5" (a pawn-push claim), and
    it correctly fails closed on the ambiguity. Rule 0 forbids loosening the
    validator or allowlisting around it, and rewriting the model's text to
    slip past the guard would defeat the guard, so the only honest lever is
    to make the model comply: dialogue_v2.md bans bare coordinates, and a
    rejected attempt is retried with the offending tokens quoted back. A
    14B model breaks the rule often enough that prompt wording alone did not
    hold up in practice. If every attempt fails the review still fails --
    unverified move text never reaches the user.
    """
    diagnosis = classification.diagnosis
    move_eval = diagnosis.flagged_error.move_eval
    board_before = chess.Board(move_eval.eval_before.fen)

    move_played = move_eval.move
    best_move = chess.Move.from_uci(move_eval.eval_before.analysis.best_move_uci)
    verified = [move_played, best_move]

    base_prompt = _PROMPT_PATH.read_text(encoding="utf-8").format(
        player_rating=player_rating,
        mover_color="White" if move_eval.mover == chess.WHITE else "Black",
        move_played_san=board_before.san(move_played),
        best_move_san=board_before.san(best_move),
        delta_cp_abs=abs(move_eval.delta_cp),
        category_details=_category_details(classification),
    )

    last_rejection: MoveValidationError | None = None
    for attempt in range(MAX_DIALOGUE_ATTEMPTS):
        prompt = base_prompt
        if last_rejection is not None:
            prompt += (
                "\n\n## Your previous attempt was rejected\n"
                "It contained these forbidden tokens: "
                f"{', '.join(last_rejection.offending_tokens)}.\n"
                "Rewrite the two paragraphs conveying the same coaching without them. "
                "Describe squares in words only."
            )

        # Budget covers a reasoning model's scratch work plus the two
        # paragraphs that survive it; too low and the answer is truncated
        # mid-<think>, leaving nothing once the block is stripped.
        response = await llm.complete(prompt, max_tokens=900, temperature=0.4)

        coaching_text = _REASONING_BLOCK.sub("", response.text).strip()
        if not coaching_text:
            raise EmptyDialogueError("LLM returned no coaching text outside its reasoning block")

        try:
            validate_llm_output(coaching_text, board_before, verified)
        except MoveValidationError as rejection:
            last_rejection = rejection
            logger.warning(
                "dialogue_rejected",
                extra={"attempt": attempt + 1, "offending_tokens": rejection.offending_tokens},
            )
            continue

        return CoachingMessage(classification=classification, text=coaching_text)

    assert last_rejection is not None
    raise last_rejection


def _category_details(classification: Classification) -> str:
    """Plain-language statement of the one verified fact behind the category.

    Drawn from `motifs_introduced` for the caused-by-this-move categories and
    `motifs_unresolved` for the one about failing to act, so the wording can
    honestly say "now" or "still" -- describing a pre-existing weakness as
    something the move just created is exactly the bug this avoids.
    """
    diagnosis = classification.diagnosis
    introduced = diagnosis.motifs_introduced
    unresolved = diagnosis.motifs_unresolved
    category = classification.category

    if category == ErrorCategory.HUNG_PIECE and introduced.hanging_pieces:
        hp = introduced.hanging_pieces[0]
        return (
            f"Your {chess.piece_name(hp.piece_type)} is now undefended "
            "and can be captured for free."
        )
    if category == ErrorCategory.ALLOWED_FORK and introduced.forks:
        fk = introduced.forks[0]
        return (
            f"The opponent's {chess.piece_name(fk.forker_piece_type)} now attacks two "
            "of your pieces at the same time -- you can only save one."
        )
    if category == ErrorCategory.WALKED_INTO_PIN and introduced.pins:
        pin = introduced.pins[0]
        return (
            f"Your {chess.piece_name(pin.pinned_piece_type)} is now pinned against "
            f"your king by the opponent's {chess.piece_name(pin.pinner_piece_type)}."
        )
    if category == ErrorCategory.BAD_TRADE:
        return "The capture you played loses material once the full exchange is played out."
    if category == ErrorCategory.MISSED_EXISTING_THREAT:
        return _unresolved_details(unresolved)
    return (
        "The evaluation dropped significantly here, though it doesn't match one of "
        "the specific patterns this coach checks for."
    )


def _unresolved_details(unresolved: MotifReport) -> str:
    """Wording for a weakness that predates the move and survived it.

    Phrased as "already"/"still" throughout: the player did not create this,
    they declined a chance to deal with it, and the coaching has to say so
    or it repeats the misattribution in gentler words.
    """
    if unresolved.hanging_pieces:
        hp = unresolved.hanging_pieces[0]
        return (
            f"Your {chess.piece_name(hp.piece_type)} was already undefended before this "
            "move and still is -- the engine's move dealt with that, yours left it."
        )
    if unresolved.forks:
        fk = unresolved.forks[0]
        return (
            f"The opponent's {chess.piece_name(fk.forker_piece_type)} was already attacking "
            "two of your pieces at once, and still is after this move -- the engine's "
            "move broke that up."
        )
    if unresolved.pins:
        pin = unresolved.pins[0]
        return (
            f"Your {chess.piece_name(pin.pinned_piece_type)} was already pinned against your "
            f"king by the opponent's {chess.piece_name(pin.pinner_piece_type)} before this "
            "move, and still is -- the engine's move relieved the pin, yours did not."
        )
    return (
        "A weakness that was already on the board survived this move, though the "
        "engine's move would have dealt with it."
    )
