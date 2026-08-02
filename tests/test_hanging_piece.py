from __future__ import annotations

import chess
import pytest

from app.analysis.hanging_piece import HangingPiece, find_hanging_pieces
from app.engine.pool import EnginePool

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}


def test_starting_position_has_no_hanging_pieces() -> None:
    board = chess.Board()
    assert find_hanging_pieces(board, chess.WHITE) == []
    assert find_hanging_pieces(board, chess.BLACK) == []


def test_single_hanging_piece_detected() -> None:
    board = chess.Board("k7/8/8/8/3n4/4P3/8/K7 w - - 0 1")
    result = find_hanging_pieces(board, chess.BLACK)
    assert result == [
        HangingPiece(
            square=chess.D4,
            piece_type=chess.KNIGHT,
            color=chess.BLACK,
            best_capture=chess.Move.from_uci("e3d4"),
            see_value=320,
        )
    ]


def test_two_independent_hanging_pieces_both_detected() -> None:
    # Knight on d4 (attacked only by the e3 pawn) and knight on h4 (attacked
    # only by the g3 pawn) -- squares chosen so neither knight's own attack
    # squares reach either white pawn, and neither knight attacks the other.
    board = chess.Board("k7/8/8/8/3n3n/4P1P1/8/K7 w - - 0 1")
    result = find_hanging_pieces(board, chess.BLACK)
    assert set(result) == {
        HangingPiece(
            square=chess.D4,
            piece_type=chess.KNIGHT,
            color=chess.BLACK,
            best_capture=chess.Move.from_uci("e3d4"),
            see_value=320,
        ),
        HangingPiece(
            square=chess.H4,
            piece_type=chess.KNIGHT,
            color=chess.BLACK,
            best_capture=chess.Move.from_uci("g3h4"),
            see_value=320,
        ),
    }


def test_defended_piece_not_flagged_when_trade_is_bad_for_attacker() -> None:
    # Same position as test_losing_trade_bishop_takes_defended_pawn in
    # test_see.py (SEE = -230 for Bxb5) -- capturing here loses material for
    # White, so the pawn must not be reported as hanging.
    board = chess.Board("4k3/8/p7/1p6/2B5/8/8/4K3 w - - 0 1")
    assert find_hanging_pieces(board, chess.BLACK) == []


def test_hanging_despite_single_defender_when_trade_still_favors_attacker() -> None:
    # Same position as test_good_trade_pawn_takes_defended_knight in
    # test_see.py (SEE = +220 for exd5) -- one defender isn't enough when the
    # attacker is cheaper than the defended piece.
    board = chess.Board("4k3/8/2p5/3n4/4P3/8/8/4K3 w - - 0 1")
    result = find_hanging_pieces(board, chess.BLACK)
    assert result == [
        HangingPiece(
            square=chess.D5,
            piece_type=chess.KNIGHT,
            color=chess.BLACK,
            best_capture=chess.Move.from_uci("e4d5"),
            see_value=220,
        )
    ]


def test_color_selectivity_exercises_turn_flip() -> None:
    # Same board as the two-hanging-pieces test, but checking White's own
    # pieces while it's White's turn requires find_hanging_pieces to flip to
    # Black internally to look for attackers -- neither white pawn is
    # actually attacked by either black knight, so this should come back empty.
    board = chess.Board("k7/8/8/8/3n3n/4P1P1/8/K7 w - - 0 1")
    assert find_hanging_pieces(board, chess.WHITE) == []


@pytest.mark.engine
def test_engine_agrees_the_detected_hanging_piece_is_worth_taking(stockfish_path: str) -> None:
    # A bare king+pawn vs king+knight position turned out to be a bad choice
    # here: with so few pieces left, Stockfish's evaluation is dominated by
    # pawn-race/king-activity endgame technique rather than material, so it
    # didn't uniquely prefer the capture even though the capture is fine.
    # Symmetric wing pawns on both sides keep this a normal-ish middlegame
    # material count, where grabbing a whole free knight is unambiguous.
    board = chess.Board("6k1/pp3ppp/8/8/3n4/4P3/PP3PPP/6K1 w - - 0 1")
    result = find_hanging_pieces(board, chess.BLACK)
    assert len(result) == 1

    with EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS) as pool:
        analysis = pool.analyse(board, depth=12, use_cache=False)

    assert analysis.best_move_uci == result[0].best_capture.uci()
