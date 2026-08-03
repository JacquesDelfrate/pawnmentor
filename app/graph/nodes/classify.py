from __future__ import annotations

from dataclasses import dataclass

import chess

from app.analysis.see import static_exchange_eval
from app.graph.nodes.diagnosis import Diagnosis
from app.graph.nodes.taxonomy import ErrorCategory


@dataclass(frozen=True, slots=True)
class Classification:
    category: ErrorCategory
    diagnosis: Diagnosis


def classify_error(diagnosis: Diagnosis) -> Classification:
    """Assigns an ErrorCategory purely by checking which already-verified fact
    is present -- a lookup over deterministic tool output, not a judgment
    call, so there's no reason to route it through the LLM (Rule 0: no chess
    logic in the LLM applies just as much to "was this a bad trade" as it
    does to "is this piece hanging").

    Reads `motifs_introduced` rather than `motifs_after`, which is the whole
    point of the three-position comparison in diagnose_error: a weakness
    already on the board before the move is not something the move did, and
    reporting it as one told players they had walked into pins that predated
    their move.

    Priority order matters, and both overlaps below are the same shape: the
    more specific category is checked before the generic HUNG_PIECE
    fallback, because HUNG_PIECE would otherwise win every time and the more
    specific one would never be reachable.

    - A losing capture (BAD_TRADE) necessarily also leaves the captured-into
      piece "hanging" by definition of SEE (the opponent's profitable
      recapture *is* what a negative SEE means).
    - A confirmed fork (ALLOWED_FORK) necessarily also leaves 2+ pieces
      independently "hanging", since find_forks' own profitability check
      for each forked target is the exact same SEE > 0 threshold
      find_hanging_pieces uses.

    MISSED_EXISTING_THREAT comes last among the substantive categories: it
    only applies when the move created nothing, so it can never mask a
    weakness the move actually caused.
    """
    move_eval = diagnosis.flagged_error.move_eval
    introduced = diagnosis.motifs_introduced

    board_before = chess.Board(move_eval.eval_before.fen)
    if _is_bad_trade(board_before, move_eval.move):
        category = ErrorCategory.BAD_TRADE
    elif introduced.forks:
        category = ErrorCategory.ALLOWED_FORK
    elif introduced.pins:
        category = ErrorCategory.WALKED_INTO_PIN
    elif introduced.hanging_pieces:
        category = ErrorCategory.HUNG_PIECE
    elif not diagnosis.motifs_unresolved.is_empty():
        category = ErrorCategory.MISSED_EXISTING_THREAT
    else:
        category = ErrorCategory.OTHER_TACTICAL_OVERSIGHT

    return Classification(category=category, diagnosis=diagnosis)


def _is_bad_trade(board_before: chess.Board, move: chess.Move) -> bool:
    is_capture = board_before.piece_at(move.to_square) is not None or board_before.is_en_passant(
        move
    )
    if not is_capture:
        return False
    return static_exchange_eval(board_before, move) < 0
