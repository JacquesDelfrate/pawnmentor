from __future__ import annotations

import chess
import pytest

from app.engine.pool import EnginePool
from app.engine.trajectory import eval_trajectory

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}
DEPTH = 10

pytestmark = pytest.mark.engine


@pytest.fixture
def pool(stockfish_path: str):
    p = EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS, default_timeout=15.0)
    yield p
    p.close()


def test_basic_shape(pool: EnginePool) -> None:
    board = chess.Board()
    moves = [chess.Move.from_uci(u) for u in ("e2e4", "e7e5", "g1f3")]

    result = eval_trajectory(pool, board, moves, depth=DEPTH)

    assert [m.ply for m in result] == [1, 2, 3]
    assert [m.move for m in result] == moves
    assert [m.mover for m in result] == [chess.WHITE, chess.BLACK, chess.WHITE]


def test_adjacent_positions_are_reused(pool: EnginePool) -> None:
    board = chess.Board()
    moves = [chess.Move.from_uci(u) for u in ("e2e4", "e7e5", "g1f3")]

    result = eval_trajectory(pool, board, moves, depth=DEPTH)

    assert result[0].eval_after == result[1].eval_before
    assert result[1].eval_after == result[2].eval_before


def test_clear_blunder_has_strongly_negative_delta(pool: EnginePool) -> None:
    # Same "padded, non-sparse" lesson as the hanging-piece/fork engine
    # tests: wing pawns on both sides keep this a normal material count.
    # The knight jumps from a safe square to one attacked by an undefended
    # black pawn -- hangs it for nothing.
    board = chess.Board("6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1")
    move = chess.Move.from_uci("c3d5")

    result = eval_trajectory(pool, board, [move], depth=DEPTH)

    assert len(result) == 1
    assert result[0].delta_cp < -200


def test_mate_transition_produces_massive_negative_delta(pool: EnginePool) -> None:
    # Fool's Mate prefix: after White's g4, Black has forced mate in 1
    # (Qh4#). Stops one move short of the actual checkmate position, which
    # UCI engines don't handle gracefully (no legal moves to search).
    board = chess.Board()
    moves = [chess.Move.from_uci(u) for u in ("f2f3", "e7e5", "g2g4")]

    result = eval_trajectory(pool, board, moves, depth=DEPTH)

    last = result[-1]
    assert last.mover == chess.WHITE
    assert last.eval_after.analysis.mate_in is not None
    assert last.eval_after.analysis.mate_in > 0  # Black (side to move) mates
    assert last.delta_cp < -50_000


def test_reasonable_opening_move_has_small_delta(pool: EnginePool) -> None:
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")

    result = eval_trajectory(pool, board, [move], depth=12)

    assert len(result) == 1
    assert abs(result[0].delta_cp) < 50
