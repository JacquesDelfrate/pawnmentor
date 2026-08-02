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
    motifs_after: MotifReport


def diagnose_error(pool: EnginePool, flagged_error: FlaggedError, depth: int) -> Diagnosis:
    """Re-confirms a filter-flagged error at diagnosis depth (20-22, not the
    bulk-scan depth) and attaches the motif facts for the resulting position
    -- what the mistake actually exposed (hanging pieces, pins, forks the
    opponent can now exploit), not just the raw eval swing.
    """
    move_eval = flagged_error.move_eval

    board_before = chess.Board(move_eval.eval_before.fen)
    deep_before = pool.analyse(board_before, depth, use_cache=False)

    board_after = chess.Board(move_eval.eval_after.fen)
    deep_after = pool.analyse(board_after, depth, use_cache=False)

    # find_hanging_pieces/find_pins treat `color` as the potential *victim*;
    # find_forks treats `color` as the *forking* side -- opposite roles for
    # the same parameter name, since each detector was built independently.
    # What "exposed by the mover's mistake" needs is: is the mover's own
    # piece hanging/pinned, and does the *opponent* now fork the mover.
    opponent = not move_eval.mover
    motifs_after = MotifReport(
        color=move_eval.mover,
        hanging_pieces=tuple(find_hanging_pieces(board_after, move_eval.mover)),
        pins=tuple(find_pins(board_after, move_eval.mover)),
        forks=tuple(find_forks(board_after, opponent)),
    )

    return Diagnosis(
        flagged_error=flagged_error,
        deep_eval_before=deep_before,
        deep_eval_after=deep_after,
        deep_delta_cp=-signed_cp(deep_after) - signed_cp(deep_before),
        motifs_after=motifs_after,
    )
