from __future__ import annotations

import queue
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import contextmanager

import chess
import chess.engine

from app.engine.cache import AnalysisResult, EngineResultCache

ENGINE_NAME = "stockfish"


class EngineTimeoutError(RuntimeError):
    pass


class EnginePool:
    def __init__(
        self,
        path: str,
        *,
        pool_size: int = 2,
        uci_options: dict[str, str | int | bool | None] | None = None,
        default_timeout: float = 10.0,
        cache: EngineResultCache | None = None,
    ) -> None:
        self._path = path
        self._uci_options = uci_options or {}
        self._default_timeout = default_timeout
        self._cache = cache if cache is not None else EngineResultCache()
        self._idle: queue.Queue[chess.engine.SimpleEngine] = queue.Queue()
        self._lock = threading.Lock()
        self._created = 0
        self._pool_size = pool_size
        self._executor = ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="engine-pool")

    def _spawn(self) -> chess.engine.SimpleEngine:
        engine = chess.engine.SimpleEngine.popen_uci(self._path)
        if self._uci_options:
            engine.configure(self._uci_options)
        return engine

    def _acquire_engine(self) -> chess.engine.SimpleEngine:
        try:
            return self._idle.get_nowait()
        except queue.Empty:
            pass
        with self._lock:
            if self._created < self._pool_size:
                self._created += 1
                return self._spawn()
        return self._idle.get()

    def _release_engine(self, engine: chess.engine.SimpleEngine) -> None:
        self._idle.put(engine)

    def _discard_engine(self, engine: chess.engine.SimpleEngine) -> None:
        with self._lock:
            self._created -= 1
        try:
            engine.quit()
        except Exception:
            pass

    @contextmanager
    def acquire(self) -> Iterator[chess.engine.SimpleEngine]:
        engine = self._acquire_engine()
        released = False
        try:
            yield engine
            self._release_engine(engine)
            released = True
        finally:
            if not released:
                self._discard_engine(engine)

    def analyse(
        self,
        board: chess.Board,
        depth: int,
        *,
        timeout: float | None = None,
        use_cache: bool = True,
    ) -> AnalysisResult:
        fen = board.fen()
        if use_cache:
            cached = self._cache.get(fen, depth, ENGINE_NAME)
            if cached is not None:
                return cached

        effective_timeout = timeout if timeout is not None else self._default_timeout

        with self.acquire() as engine:
            future = self._executor.submit(engine.analyse, board, chess.engine.Limit(depth=depth))
            try:
                info = future.result(timeout=effective_timeout)
            except FutureTimeoutError as exc:
                raise EngineTimeoutError(
                    f"Engine analysis exceeded {effective_timeout}s at depth {depth}"
                ) from exc
            if isinstance(info, list):
                info = info[0]

        result = _analysis_result_from_info(board, info)
        if use_cache:
            self._cache.set(fen, depth, ENGINE_NAME, result)
        return result

    def close(self) -> None:
        self._executor.shutdown(wait=True)
        while True:
            try:
                engine = self._idle.get_nowait()
            except queue.Empty:
                break
            try:
                engine.quit()
            except Exception:
                pass

    def __enter__(self) -> EnginePool:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _analysis_result_from_info(board: chess.Board, info: chess.engine.InfoDict) -> AnalysisResult:
    pv = info.get("pv", [])
    pv_uci = tuple(move.uci() for move in pv)
    best_move_uci = pv_uci[0] if pv_uci else ""

    score = info.get("score")
    score_cp: int | None = None
    mate_in: int | None = None
    if score is not None:
        pov_score = score.pov(board.turn)
        mate_in = pov_score.mate()
        if mate_in is None:
            score_cp = pov_score.score()

    return AnalysisResult(
        best_move_uci=best_move_uci,
        score_cp=score_cp,
        mate_in=mate_in,
        pv_uci=pv_uci,
    )
