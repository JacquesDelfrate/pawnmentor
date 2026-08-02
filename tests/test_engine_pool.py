from __future__ import annotations

from collections.abc import Iterator

import chess
import pytest

from app.engine.pool import EnginePool, EngineTimeoutError

pytestmark = pytest.mark.engine

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}


@pytest.fixture
def pool(stockfish_path: str) -> Iterator[EnginePool]:
    p = EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS, default_timeout=15.0)
    yield p
    p.close()


def test_analyse_returns_a_legal_best_move(pool: EnginePool) -> None:
    board = chess.Board()
    result = pool.analyse(board, depth=8)
    assert result.best_move_uci
    move = chess.Move.from_uci(result.best_move_uci)
    assert move in board.legal_moves


def test_cache_hit_avoids_second_engine_call(pool: EnginePool) -> None:
    board = chess.Board()
    first = pool.analyse(board, depth=8)
    created_after_first = pool._created

    second = pool.analyse(board, depth=8)

    assert second == first
    assert pool._created == created_after_first


def test_pool_reuses_the_same_engine_process(pool: EnginePool) -> None:
    board = chess.Board()
    pool.analyse(board, depth=6, use_cache=False)
    assert pool._created == 1
    pool.analyse(board.mirror(), depth=6, use_cache=False)
    assert pool._created == 1


def test_timeout_raises_and_pool_recovers(pool: EnginePool) -> None:
    board = chess.Board()
    with pytest.raises(EngineTimeoutError):
        pool.analyse(board, depth=20, timeout=0.001, use_cache=False)
    assert pool._created == 0

    result = pool.analyse(board, depth=6, use_cache=False)
    assert result.best_move_uci
