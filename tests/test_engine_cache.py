from __future__ import annotations

from app.engine.cache import AnalysisResult, EngineResultCache


def _result(move: str = "e2e4") -> AnalysisResult:
    return AnalysisResult(best_move_uci=move, score_cp=25, mate_in=None, pv_uci=(move,))


def test_miss_returns_none() -> None:
    cache = EngineResultCache()
    assert cache.get("fen", 10, "stockfish") is None


def test_set_then_get_returns_stored_result() -> None:
    cache = EngineResultCache()
    result = _result()
    cache.set("fen", 10, "stockfish", result)
    assert cache.get("fen", 10, "stockfish") == result


def test_distinct_keys_do_not_collide() -> None:
    cache = EngineResultCache()
    cache.set("fen-a", 10, "stockfish", _result("e2e4"))
    cache.set("fen-a", 12, "stockfish", _result("d2d4"))
    cache.set("fen-b", 10, "stockfish", _result("g1f3"))
    assert cache.get("fen-a", 10, "stockfish") == _result("e2e4")
    assert cache.get("fen-a", 12, "stockfish") == _result("d2d4")
    assert cache.get("fen-b", 10, "stockfish") == _result("g1f3")


def test_clear_empties_cache() -> None:
    cache = EngineResultCache()
    cache.set("fen", 10, "stockfish", _result())
    cache.clear()
    assert len(cache) == 0
    assert cache.get("fen", 10, "stockfish") is None


def test_len_counts_entries() -> None:
    cache = EngineResultCache()
    assert len(cache) == 0
    cache.set("fen", 10, "stockfish", _result())
    assert len(cache) == 1
