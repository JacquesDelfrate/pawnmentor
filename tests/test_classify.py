from __future__ import annotations

import chess
import pytest

from app.engine.pool import EnginePool
from app.engine.trajectory import eval_trajectory
from app.graph.nodes.classify import classify_error
from app.graph.nodes.diagnosis import diagnose_error
from app.graph.nodes.filter import FlaggedError
from app.graph.nodes.taxonomy import ErrorCategory

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}

pytestmark = pytest.mark.engine


@pytest.fixture
def pool(stockfish_path: str):
    p = EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS, default_timeout=20.0)
    yield p
    p.close()


def _classify(pool: EnginePool, fen: str, move_uci: str) -> ErrorCategory:
    board = chess.Board(fen)
    trajectory = eval_trajectory(pool, board, [chess.Move.from_uci(move_uci)], depth=12)
    flagged = FlaggedError(move_eval=trajectory[0], reachability_gap_cp=0)
    diagnosis = diagnose_error(pool, flagged, depth=16)
    return classify_error(diagnosis).category


def test_bad_trade(pool: EnginePool) -> None:
    # Same position/move as test_see.py's test_losing_trade_bishop_takes_defended_pawn
    # (SEE = -230 for Bxb5). BAD_TRADE must win over HUNG_PIECE here even
    # though the resulting bishop is also technically "hanging" -- that's
    # the exact same fact restated, so the priority order in classify_error
    # picks the more precise diagnosis.
    category = _classify(pool, "4k3/8/p7/1p6/2B5/8/8/4K3 w - - 0 1", "c4b5")
    assert category == ErrorCategory.BAD_TRADE


def test_hung_piece(pool: EnginePool) -> None:
    # Same padded position as the trajectory/filter blunder tests: a quiet
    # knight move (not a capture) that hangs the knight for nothing.
    category = _classify(pool, "6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1", "c3d5")
    assert category == ErrorCategory.HUNG_PIECE


def test_allowed_fork(pool: EnginePool) -> None:
    # One ply before test_fork.py's GENUINE_FORK_FEN: Black's pawn push
    # g7-g6 is what actually creates the fork (walks the second pawn onto
    # one of the knight's attack squares) -- diagnosing Black's move should
    # find White's knight now forking both pawns.
    category = _classify(pool, "k7/6p1/2p5/4N3/8/8/8/K7 b - - 0 1", "g7g6")
    assert category == ErrorCategory.ALLOWED_FORK


def test_walked_into_pin(pool: EnginePool) -> None:
    # Nb1-c3 walks the knight onto the pin (bishop b4 - knight c3 - king e1).
    # A pawn on b2 defends c3 so the knight isn't also "hanging" (SEE for
    # Bxc3 is -10, not profitable) -- isolates the pin from hung-piece.
    category = _classify(pool, "4k3/8/8/8/1b6/8/1P6/1N2K3 w - - 0 1", "b1c3")
    assert category == ErrorCategory.WALKED_INTO_PIN
