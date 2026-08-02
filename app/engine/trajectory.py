from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.engine.cache import AnalysisResult, signed_cp
from app.engine.pool import EnginePool


@dataclass(frozen=True, slots=True)
class PositionEval:
    ply: int
    fen: str
    analysis: AnalysisResult


@dataclass(frozen=True, slots=True)
class MoveEval:
    ply: int
    move: chess.Move
    mover: chess.Color
    eval_before: PositionEval
    eval_after: PositionEval
    delta_cp: int


def eval_trajectory(
    pool: EnginePool, board: chess.Board, moves: Sequence[chess.Move], depth: int
) -> list[MoveEval]:
    working = board.copy(stack=False)
    current = _evaluate_position(pool, working, depth, ply=0)

    move_evals: list[MoveEval] = []
    for ply, move in enumerate(moves, start=1):
        mover = working.turn
        working.push(move)
        after = _evaluate_position(pool, working, depth, ply=ply)

        move_evals.append(
            MoveEval(
                ply=ply,
                move=move,
                mover=mover,
                eval_before=current,
                eval_after=after,
                delta_cp=-signed_cp(after.analysis) - signed_cp(current.analysis),
            )
        )
        current = after

    return move_evals


def _evaluate_position(pool: EnginePool, board: chess.Board, depth: int, ply: int) -> PositionEval:
    analysis = pool.analyse(board, depth)
    return PositionEval(ply=ply, fen=board.fen(), analysis=analysis)
