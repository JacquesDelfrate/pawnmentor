from __future__ import annotations

from dataclasses import dataclass

import chess

from app.analysis.see import static_exchange_eval


@dataclass(frozen=True, slots=True)
class Fork:
    forker_square: chess.Square
    forker_piece_type: chess.PieceType
    color: chess.Color
    forked_squares: tuple[chess.Square, ...]
    king_threatened: bool


def find_forks(board: chess.Board, color: chess.Color) -> list[Fork]:
    opponent_color = not color
    attacker_board = board if board.turn == color else _with_turn(board, color)
    defender_board = board if board.turn == opponent_color else _with_turn(board, opponent_color)

    king_square = board.king(opponent_color)

    forks: list[Fork] = []
    for forker_square in chess.SquareSet(board.occupied_co[color]):
        forker_piece = board.piece_at(forker_square)
        assert forker_piece is not None

        piece_targets = _profitable_targets(attacker_board, forker_square)
        king_threatened = king_square is not None and king_square in board.attacks(forker_square)

        if len(piece_targets) + (1 if king_threatened else 0) < 2:
            continue

        if not _survives_every_response(
            defender_board, forker_square, forker_piece.piece_type, color, piece_targets
        ):
            continue

        forks.append(
            Fork(
                forker_square=forker_square,
                forker_piece_type=forker_piece.piece_type,
                color=color,
                forked_squares=tuple(sorted(piece_targets)),
                king_threatened=king_threatened,
            )
        )

    return forks


def _profitable_targets(board: chess.Board, forker_square: chess.Square) -> set[chess.Square]:
    targets: set[chess.Square] = set()
    for move in board.legal_moves:
        if move.from_square != forker_square:
            continue
        if board.piece_at(move.to_square) is None:
            continue
        if static_exchange_eval(board, move) > 0:
            targets.add(move.to_square)
    return targets


def _survives_every_response(
    defender_board: chess.Board,
    forker_square: chess.Square,
    forker_piece_type: chess.PieceType,
    color: chess.Color,
    piece_targets: set[chess.Square],
) -> bool:
    for response in defender_board.legal_moves:
        trial = defender_board.copy(stack=False)
        trial.push(response)

        forker_now = trial.piece_at(forker_square)
        if (
            forker_now is None
            or forker_now.color != color
            or forker_now.piece_type != forker_piece_type
        ):
            return False

        if not _profitable_targets(trial, forker_square) & piece_targets:
            return False

    return True


def _with_turn(board: chess.Board, color: chess.Color) -> chess.Board:
    working = board.copy(stack=False)
    working.turn = color
    return working
