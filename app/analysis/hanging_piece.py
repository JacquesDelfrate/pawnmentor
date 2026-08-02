from __future__ import annotations

from dataclasses import dataclass

import chess

from app.analysis.see import static_exchange_eval


@dataclass(frozen=True, slots=True)
class HangingPiece:
    square: chess.Square
    piece_type: chess.PieceType
    color: chess.Color
    best_capture: chess.Move
    see_value: int


def find_hanging_pieces(board: chess.Board, color: chess.Color) -> list[HangingPiece]:
    attacker_color = not color
    attacker_board = board if board.turn == attacker_color else _with_turn(board, attacker_color)

    hanging: list[HangingPiece] = []
    for square in chess.SquareSet(board.occupied_co[color]):
        piece = board.piece_at(square)
        assert piece is not None
        if piece.piece_type == chess.KING:
            continue

        best_move: chess.Move | None = None
        best_value = 0
        for move in attacker_board.legal_moves:
            if move.to_square != square:
                continue
            value = static_exchange_eval(attacker_board, move)
            if best_move is None or value > best_value:
                best_move, best_value = move, value

        if best_move is not None and best_value > 0:
            hanging.append(
                HangingPiece(
                    square=square,
                    piece_type=piece.piece_type,
                    color=color,
                    best_capture=best_move,
                    see_value=best_value,
                )
            )

    return hanging


def _with_turn(board: chess.Board, color: chess.Color) -> chess.Board:
    working = board.copy(stack=False)
    working.turn = color
    return working
