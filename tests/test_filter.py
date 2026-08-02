from __future__ import annotations

import chess
import pytest

from app.engine.peer import build_peer_pool
from app.engine.pool import EnginePool
from app.engine.trajectory import eval_trajectory
from app.graph.nodes.filter import (
    MAX_MAGNITUDE_THRESHOLD_CP,
    MIN_MAGNITUDE_THRESHOLD_CP,
    filter_errors,
    magnitude_threshold_cp,
    reachability_gap_cp,
)

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}
DEPTH = 10


def test_magnitude_threshold_clamped_below_range() -> None:
    assert magnitude_threshold_cp(100) == MAX_MAGNITUDE_THRESHOLD_CP


def test_magnitude_threshold_clamped_above_range() -> None:
    assert magnitude_threshold_cp(3000) == MIN_MAGNITUDE_THRESHOLD_CP


def test_magnitude_threshold_decreases_as_rating_increases() -> None:
    assert magnitude_threshold_cp(500) > magnitude_threshold_cp(1200) > magnitude_threshold_cp(2200)


@pytest.fixture
def full_pool(stockfish_path: str):
    p = EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS, default_timeout=15.0)
    yield p
    p.close()


@pytest.mark.engine
def test_reachability_gap_is_small_for_an_obvious_blunder_avoidance(
    stockfish_path: str, full_pool: EnginePool
) -> None:
    # Padded, non-sparse position (same lesson as earlier engine tests):
    # White to move, about to consider Nc3-d5 which hangs the knight to the
    # c6 pawn. Avoiding an outright free piece is basic enough that even a
    # peer-strength engine should land close to the true best move in value.
    board = chess.Board("6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1")
    moves = [chess.Move.from_uci("c3d5")]
    trajectory = eval_trajectory(full_pool, board, moves, depth=DEPTH)

    with build_peer_pool(stockfish_path, 1200, default_timeout=15.0) as peer_pool:
        gap = reachability_gap_cp(peer_pool, full_pool, trajectory[0], depth=DEPTH)

    assert gap < 150


@pytest.mark.engine
def test_filter_flags_a_clear_reachable_blunder(stockfish_path: str, full_pool: EnginePool) -> None:
    board = chess.Board("6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1")
    moves = [chess.Move.from_uci("c3d5")]
    trajectory = eval_trajectory(full_pool, board, moves, depth=DEPTH)

    with build_peer_pool(stockfish_path, 1200, default_timeout=15.0) as peer_pool:
        flagged = filter_errors(trajectory, chess.WHITE, 1200, peer_pool, full_pool, depth=DEPTH)

    assert len(flagged) == 1
    assert flagged[0].move_eval.move == moves[0]


@pytest.mark.engine
def test_filter_ignores_moves_by_the_other_color(
    stockfish_path: str, full_pool: EnginePool
) -> None:
    board = chess.Board("6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1")
    moves = [chess.Move.from_uci("c3d5")]
    trajectory = eval_trajectory(full_pool, board, moves, depth=DEPTH)

    with build_peer_pool(stockfish_path, 1200, default_timeout=15.0) as peer_pool:
        flagged = filter_errors(trajectory, chess.BLACK, 1200, peer_pool, full_pool, depth=DEPTH)

    assert flagged == []


@pytest.mark.engine
def test_filter_respects_max_errors_cap(stockfish_path: str, full_pool: EnginePool) -> None:
    # max_errors=0 on a trajectory containing a real, otherwise-flaggable
    # blunder proves the cap actually gates the output -- without it, this
    # exact candidate is flagged (see test_filter_flags_a_clear_reachable_blunder).
    board = chess.Board("6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1")
    moves = [chess.Move.from_uci("c3d5")]
    trajectory = eval_trajectory(full_pool, board, moves, depth=DEPTH)

    with build_peer_pool(stockfish_path, 1200, default_timeout=15.0) as peer_pool:
        flagged = filter_errors(
            trajectory, chess.WHITE, 1200, peer_pool, full_pool, depth=DEPTH, max_errors=0
        )

    assert flagged == []
