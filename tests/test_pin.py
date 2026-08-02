from __future__ import annotations

import chess

from app.analysis.pin import Pin, find_pins


def test_diagonal_pin_detected() -> None:
    # Bb4 pins Nc3 to Ke1 along the a5-e1 diagonal.
    board = chess.Board("4k3/8/8/8/1b6/2N5/8/4K3 w - - 0 1")
    assert find_pins(board, chess.WHITE) == [
        Pin(
            pinned_square=chess.C3,
            pinned_piece_type=chess.KNIGHT,
            color=chess.WHITE,
            pinner_square=chess.B4,
            pinner_piece_type=chess.BISHOP,
        )
    ]


def test_file_pin_detected() -> None:
    # Re8 pins Ne4 to Ke1 along the e-file.
    board = chess.Board("k3r3/8/8/8/4N3/8/8/4K3 w - - 0 1")
    assert find_pins(board, chess.WHITE) == [
        Pin(
            pinned_square=chess.E4,
            pinned_piece_type=chess.KNIGHT,
            color=chess.WHITE,
            pinner_square=chess.E8,
            pinner_piece_type=chess.ROOK,
        )
    ]


def test_attacked_piece_not_in_line_with_king_is_not_a_pin() -> None:
    # The knight is attacked (hanging, even) but the king isn't behind it on
    # any ray from the attacking pawn -- being attacked isn't being pinned.
    board = chess.Board("k7/8/8/8/3n4/4P3/8/K7 w - - 0 1")
    assert find_pins(board, chess.BLACK) == []


def test_second_blocker_prevents_pin_on_either_piece() -> None:
    # Pawn e3 and knight e5 are both between king e1 and rook e8 -- removing
    # either one alone still leaves the other blocking, so neither is
    # actually pinned.
    board = chess.Board("k3r3/8/8/4N3/8/4P3/8/4K3 w - - 0 1")
    assert find_pins(board, chess.WHITE) == []


def test_two_independent_pins_both_detected() -> None:
    # Bb4 pins Nc3 along the diagonal; Ra1 pins Qd1 along the back rank.
    # Different rays from the same king, no interaction between them.
    board = chess.Board("4k3/8/8/8/1b6/2N5/8/r2QK3 w - - 0 1")
    result = find_pins(board, chess.WHITE)
    assert set(result) == {
        Pin(
            pinned_square=chess.C3,
            pinned_piece_type=chess.KNIGHT,
            color=chess.WHITE,
            pinner_square=chess.B4,
            pinner_piece_type=chess.BISHOP,
        ),
        Pin(
            pinned_square=chess.D1,
            pinned_piece_type=chess.QUEEN,
            color=chess.WHITE,
            pinner_square=chess.A1,
            pinner_piece_type=chess.ROOK,
        ),
    }


def test_pinned_pawn_detected() -> None:
    board = chess.Board("k3r3/8/8/8/4P3/8/8/4K3 w - - 0 1")
    assert find_pins(board, chess.WHITE) == [
        Pin(
            pinned_square=chess.E4,
            pinned_piece_type=chess.PAWN,
            color=chess.WHITE,
            pinner_square=chess.E8,
            pinner_piece_type=chess.ROOK,
        )
    ]


def test_turn_independence() -> None:
    board_white_to_move = chess.Board("k3r3/8/8/8/4N3/8/8/4K3 w - - 0 1")
    board_black_to_move = chess.Board("k3r3/8/8/8/4N3/8/8/4K3 b - - 0 1")
    result = find_pins(board_white_to_move, chess.WHITE)
    assert result != []
    assert result == find_pins(board_black_to_move, chess.WHITE)
