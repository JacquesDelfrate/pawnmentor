from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass(frozen=True, slots=True)
class Pin:
    pinned_square: chess.Square
    pinned_piece_type: chess.PieceType
    color: chess.Color
    pinner_square: chess.Square
    pinner_piece_type: chess.PieceType


def find_pins(board: chess.Board, color: chess.Color) -> list[Pin]:
    pins: list[Pin] = []
    for square in chess.SquareSet(board.occupied_co[color]):
        piece = board.piece_at(square)
        assert piece is not None
        if piece.piece_type == chess.KING:
            continue
        if not board.is_pinned(color, square):
            continue

        pinner_square = _find_pinner(board, color, square)
        pinner_piece = board.piece_at(pinner_square)
        assert pinner_piece is not None

        pins.append(
            Pin(
                pinned_square=square,
                pinned_piece_type=piece.piece_type,
                color=color,
                pinner_square=pinner_square,
                pinner_piece_type=pinner_piece.piece_type,
            )
        )
    return pins


def _find_pinner(board: chess.Board, color: chess.Color, square: chess.Square) -> chess.Square:
    for candidate in board.pin(color, square):
        piece = board.piece_at(candidate)
        if piece is not None and piece.color != color:
            return candidate
    raise AssertionError(
        f"is_pinned reported a pin on {chess.square_name(square)} but no pinning piece was found"
    )
