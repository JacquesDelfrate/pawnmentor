from __future__ import annotations

from dataclasses import dataclass

import chess

from app.engine.pool import EnginePool
from app.services.chess_com import current_position, resolve_player_color

DEFAULT_ADVICE_DEPTH = 20


class AdvisorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BestMoveAdvice:
    """Engine recommendation for the live position of a game.

    `best_move_san` is None whenever there is nothing to recommend -- the
    game is finished, or the opponent is on move -- rather than the caller
    having to infer that from the flags.
    """

    fen: str
    player_color: chess.Color
    is_player_turn: bool
    is_game_over: bool
    best_move_san: str | None
    score_cp: int | None
    mate_in: int | None
    pv_san: tuple[str, ...]


def advise_best_move(
    pool: EnginePool,
    pgn: str,
    white_username: str,
    black_username: str,
    player_username: str,
    *,
    depth: int = DEFAULT_ADVICE_DEPTH,
) -> BestMoveAdvice:
    """Engine's pick for the position a game currently stands in.

    Distinct from the review pipeline, which only ever looks backwards at
    moves already played. This looks at the position as it stands now.
    """
    color = resolve_player_color(white_username, black_username, player_username)
    if color is None:
        raise AdvisorError(f"{player_username!r} is not a player in this game")

    board = current_position(pgn)

    if board.is_game_over():
        return _no_advice(board, color, is_game_over=True, is_player_turn=False)
    if board.turn != color:
        return _no_advice(board, color, is_game_over=False, is_player_turn=False)

    analysis = pool.analyse(board, depth)
    if not analysis.best_move_uci:
        raise AdvisorError("Engine returned no move for a position that has legal moves")

    return BestMoveAdvice(
        fen=board.fen(),
        player_color=color,
        is_player_turn=True,
        is_game_over=False,
        best_move_san=board.san(chess.Move.from_uci(analysis.best_move_uci)),
        score_cp=analysis.score_cp,
        mate_in=analysis.mate_in,
        pv_san=_pv_to_san(board, analysis.pv_uci),
    )


def _no_advice(
    board: chess.Board, color: chess.Color, *, is_game_over: bool, is_player_turn: bool
) -> BestMoveAdvice:
    return BestMoveAdvice(
        fen=board.fen(),
        player_color=color,
        is_player_turn=is_player_turn,
        is_game_over=is_game_over,
        best_move_san=None,
        score_cp=None,
        mate_in=None,
        pv_san=(),
    )


def _pv_to_san(board: chess.Board, pv_uci: tuple[str, ...]) -> tuple[str, ...]:
    """SAN needs the position each move is played from, so the line is
    replayed as it is converted. Stops at the first move that doesn't fit
    rather than raising -- a truncated line is still useful, and a partial
    PV should not take down the whole recommendation.
    """
    working = board.copy(stack=False)
    san_moves: list[str] = []
    for uci in pv_uci:
        move = chess.Move.from_uci(uci)
        if move not in working.legal_moves:
            break
        san_moves.append(working.san(move))
        working.push(move)
    return tuple(san_moves)
