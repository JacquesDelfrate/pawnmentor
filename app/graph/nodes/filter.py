from __future__ import annotations

from dataclasses import dataclass

import chess

from app.engine.cache import signed_cp
from app.engine.pool import EnginePool
from app.engine.trajectory import MoveEval

MIN_RATING_FOR_THRESHOLD = 400
MAX_RATING_FOR_THRESHOLD = 2400
MAX_MAGNITUDE_THRESHOLD_CP = 500
MIN_MAGNITUDE_THRESHOLD_CP = 100

DEFAULT_REACHABILITY_THRESHOLD_CP = 150
DEFAULT_MAX_FLAGGED_ERRORS = 3


@dataclass(frozen=True, slots=True)
class FlaggedError:
    move_eval: MoveEval
    reachability_gap_cp: int


def magnitude_threshold_cp(rating: int) -> int:
    """Eval-delta magnitude (centipawns) a move must exceed to be a flagging candidate.

    Scales with rating: weaker players only get flagged for outright
    blunders (a high threshold), stronger players get flagged for smaller
    inaccuracies, since that's what's actually left for them to improve.
    Linear between MIN_RATING_FOR_THRESHOLD and MAX_RATING_FOR_THRESHOLD,
    clamped outside that range.
    """
    rating = max(MIN_RATING_FOR_THRESHOLD, min(MAX_RATING_FOR_THRESHOLD, rating))
    span = MAX_RATING_FOR_THRESHOLD - MIN_RATING_FOR_THRESHOLD
    fraction = (rating - MIN_RATING_FOR_THRESHOLD) / span
    threshold_span = MAX_MAGNITUDE_THRESHOLD_CP - MIN_MAGNITUDE_THRESHOLD_CP
    return round(MAX_MAGNITUDE_THRESHOLD_CP - fraction * threshold_span)


def reachability_gap_cp(
    peer_pool: EnginePool,
    full_pool: EnginePool,
    move_eval: MoveEval,
    depth: int,
) -> int:
    """How much worse a peer-strength engine's own choice is than the true best move.

    Near 0: a player of this rating would plausibly have found (or nearly
    found) the best move too -- reachable, worth coaching. Large: even a
    peer-strength engine can't find it either, so criticizing the human for
    missing it isn't fair or pedagogically useful (Recipe R5).
    """
    board = chess.Board(move_eval.eval_before.fen)
    peer_choice = peer_pool.analyse(board, depth)

    best_move_uci = move_eval.eval_before.analysis.best_move_uci
    if peer_choice.best_move_uci == best_move_uci:
        return 0

    peer_move = chess.Move.from_uci(peer_choice.best_move_uci)
    trial = board.copy(stack=False)
    trial.push(peer_move)
    after_peer_move = full_pool.analyse(trial, depth, use_cache=False)

    best_value = signed_cp(move_eval.eval_before.analysis)
    peer_move_value = -signed_cp(after_peer_move)
    return max(0, best_value - peer_move_value)


def filter_errors(
    move_evals: list[MoveEval],
    player_color: chess.Color,
    player_rating: int,
    peer_pool: EnginePool,
    full_pool: EnginePool,
    depth: int,
    *,
    max_errors: int = DEFAULT_MAX_FLAGGED_ERRORS,
    reachability_threshold_cp: int = DEFAULT_REACHABILITY_THRESHOLD_CP,
) -> list[FlaggedError]:
    """Rule 1's two gates. More than `max_errors` surfaced is worse, per spec."""
    threshold = magnitude_threshold_cp(player_rating)

    candidates = [
        move_eval
        for move_eval in move_evals
        if move_eval.mover == player_color and -move_eval.delta_cp > threshold
    ]
    candidates.sort(key=lambda move_eval: move_eval.delta_cp)

    flagged: list[FlaggedError] = []
    for move_eval in candidates:
        if len(flagged) >= max_errors:
            break
        gap = reachability_gap_cp(peer_pool, full_pool, move_eval, depth)
        if gap <= reachability_threshold_cp:
            flagged.append(FlaggedError(move_eval=move_eval, reachability_gap_cp=gap))
        # else: Recipe R5 -- not a pedagogically useful mistake, discarded silently.

    return flagged
