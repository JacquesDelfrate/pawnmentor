from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    best_move_uci: str
    score_cp: int | None
    mate_in: int | None
    pv_uci: tuple[str, ...]


MATE_SENTINEL_CP = 100_000


def signed_cp(analysis: AnalysisResult) -> int:
    """A single finite centipawn value for an AnalysisResult, mate scores included.

    Mate scores become a large but finite sentinel (sign per which side
    mates) since "any forced mate" is maximally severe regardless of the
    exact mate-in-N -- callers that need the exact number still have it via
    `analysis.mate_in`.
    """
    if analysis.mate_in is not None:
        return MATE_SENTINEL_CP if analysis.mate_in > 0 else -MATE_SENTINEL_CP
    assert analysis.score_cp is not None
    return analysis.score_cp


CacheKey = tuple[str, int, str]


class EngineResultCache:
    def __init__(self) -> None:
        self._store: dict[CacheKey, AnalysisResult] = {}
        self._lock = Lock()

    def get(self, fen: str, depth: int, engine_name: str) -> AnalysisResult | None:
        with self._lock:
            return self._store.get((fen, depth, engine_name))

    def set(self, fen: str, depth: int, engine_name: str, result: AnalysisResult) -> None:
        with self._lock:
            self._store[(fen, depth, engine_name)] = result

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
