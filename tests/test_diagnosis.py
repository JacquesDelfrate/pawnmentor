from __future__ import annotations

import chess
import pytest

from app.engine.pool import EnginePool
from app.engine.trajectory import eval_trajectory
from app.graph.nodes.diagnosis import diagnose_error
from app.graph.nodes.filter import FlaggedError

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}

pytestmark = pytest.mark.engine


@pytest.fixture
def pool(stockfish_path: str):
    p = EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS, default_timeout=20.0)
    yield p
    p.close()


def test_diagnosis_confirms_blunder_at_deeper_depth_and_finds_the_hanging_piece(
    pool: EnginePool,
) -> None:
    board = chess.Board("6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1")
    moves = [chess.Move.from_uci("c3d5")]
    trajectory = eval_trajectory(pool, board, moves, depth=10)
    flagged = FlaggedError(move_eval=trajectory[0], reachability_gap_cp=0)

    diagnosis = diagnose_error(pool, flagged, depth=16)

    assert diagnosis.deep_delta_cp < -200
    assert any(hp.square == chess.D5 for hp in diagnosis.motifs_after.hanging_pieces)
