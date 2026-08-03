from __future__ import annotations

from dataclasses import dataclass

import chess

from app.analysis.fork import find_forks
from app.analysis.hanging_piece import find_hanging_pieces
from app.analysis.pin import find_pins
from app.engine.cache import AnalysisResult, signed_cp
from app.engine.pool import EnginePool
from app.graph.nodes.filter import FlaggedError
from app.graph.state import MotifReport


@dataclass(frozen=True, slots=True)
class Diagnosis:
    flagged_error: FlaggedError
    deep_eval_before: AnalysisResult
    deep_eval_after: AnalysisResult
    deep_delta_cp: int

    motifs_before: MotifReport
    """Weaknesses already on the board before the move -- never caused by it."""

    motifs_after: MotifReport
    """Everything standing after the move, caused or not."""

    motifs_introduced: MotifReport
    """After minus before: what this move actually created."""

    motifs_unresolved: MotifReport
    """Pre-existing weaknesses the engine's move would have cleared but this
    one left standing. Distinguished from motifs_before because "you failed
    to deal with this" is only a fair charge when dealing with it was
    demonstrably available."""


def diagnose_error(pool: EnginePool, flagged_error: FlaggedError, depth: int) -> Diagnosis:
    """Re-confirms a filter-flagged error at diagnosis depth and works out
    which weaknesses the move is actually answerable for.

    Comparing three positions rather than just looking at the one after the
    move: before it, after it, and after the engine's recommendation
    instead. Reporting only the position after the move meant any weakness
    that already existed got blamed on the move -- a real game produced
    "walked into a pin" for a pin that predated the move by several plies,
    which teaches the player something false.

    Two verified claims come out of the comparison. A motif absent before
    and present after was caused by this move. A motif present before and
    after, but absent had the engine's move been played, is one the move
    failed to resolve when resolving it was available. Anything else stays
    unattributed rather than being pinned on the move.
    """
    move_eval = flagged_error.move_eval
    mover = move_eval.mover

    board_before = chess.Board(move_eval.eval_before.fen)
    deep_before = pool.analyse(board_before, depth, use_cache=False)

    board_after = chess.Board(move_eval.eval_after.fen)
    deep_after = pool.analyse(board_after, depth, use_cache=False)

    board_if_best = board_before.copy(stack=False)
    board_if_best.push(chess.Move.from_uci(move_eval.eval_before.analysis.best_move_uci))

    motifs_before = _motifs_against(board_before, mover)
    motifs_after = _motifs_against(board_after, mover)
    motifs_if_best = _motifs_against(board_if_best, mover)

    introduced = _subtract(motifs_after, motifs_before)
    survived = _subtract(motifs_after, introduced)
    unresolved = _subtract(survived, motifs_if_best)

    return Diagnosis(
        flagged_error=flagged_error,
        deep_eval_before=deep_before,
        deep_eval_after=deep_after,
        deep_delta_cp=-signed_cp(deep_after) - signed_cp(deep_before),
        motifs_before=motifs_before,
        motifs_after=motifs_after,
        motifs_introduced=introduced,
        motifs_unresolved=unresolved,
    )


def _motifs_against(board: chess.Board, mover: chess.Color) -> MotifReport:
    # find_hanging_pieces/find_pins treat `color` as the potential *victim*;
    # find_forks treats `color` as the *forking* side -- opposite roles for
    # the same parameter name, since each detector was built independently.
    # What matters here is: is the mover's own piece hanging/pinned, and does
    # the *opponent* fork the mover.
    return MotifReport(
        color=mover,
        hanging_pieces=tuple(find_hanging_pieces(board, mover)),
        pins=tuple(find_pins(board, mover)),
        forks=tuple(find_forks(board, not mover)),
    )


def _subtract(report: MotifReport, other: MotifReport) -> MotifReport:
    """Motifs in `report` that have no counterpart in `other`.

    Identity is the geometry, not the object: a hanging piece is the same
    one if the same piece type sits on the same square, a pin is the same if
    both ends match, a fork is the same if the forking piece and every
    forked square match. That is what lets a motif be tracked across the
    move that may or may not have caused it.
    """
    other_hanging = {(hp.square, hp.piece_type) for hp in other.hanging_pieces}
    other_pins = {(p.pinned_square, p.pinner_square) for p in other.pins}
    other_forks = {(f.forker_square, f.forked_squares, f.king_threatened) for f in other.forks}

    return MotifReport(
        color=report.color,
        hanging_pieces=tuple(
            hp for hp in report.hanging_pieces if (hp.square, hp.piece_type) not in other_hanging
        ),
        pins=tuple(p for p in report.pins if (p.pinned_square, p.pinner_square) not in other_pins),
        forks=tuple(
            f
            for f in report.forks
            if (f.forker_square, f.forked_squares, f.king_threatened) not in other_forks
        ),
    )
