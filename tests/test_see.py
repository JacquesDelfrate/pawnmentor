from __future__ import annotations

import chess
import pytest

from app.analysis.see import static_exchange_eval
from app.engine.pool import EnginePool

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}


def test_free_capture_no_recapture() -> None:
    board = chess.Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("e4d5")
    assert static_exchange_eval(board, move) == 100


def test_losing_trade_bishop_takes_defended_pawn() -> None:
    board = chess.Board("4k3/8/p7/1p6/2B5/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("c4b5")
    assert static_exchange_eval(board, move) == 100 - 330


def test_good_trade_pawn_takes_defended_knight() -> None:
    board = chess.Board("4k3/8/2p5/3n4/4P3/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("e4d5")
    assert static_exchange_eval(board, move) == 320 - 100


def test_declines_losing_continuation_despite_more_attackers() -> None:
    # White pawn d4 takes the knight on e5. Black can recapture with the f6
    # pawn; White *could* then recapture with the rook on e1, but that would
    # only net a pawn before Black's rook on e8 wins the exchange (losing a
    # rook for a pawn), so White should stop after the first recapture.
    # Optimal line: dxe5 fxe5, White declines further. Net for White:
    # +320 (knight) - 100 (own pawn) = +220.
    board = chess.Board("k3r3/8/5p2/4n3/3P4/8/8/K3R3 w - - 0 1")
    move = chess.Move.from_uci("d4e5")
    assert static_exchange_eval(board, move) == 220


def test_en_passant_capture() -> None:
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    move = chess.Move.from_uci("e5d6")
    assert board.is_en_passant(move)
    assert static_exchange_eval(board, move) == 100


def test_promotion_capture_undefended() -> None:
    board = chess.Board("r3k3/1P6/8/8/8/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("b7a8q")
    assert static_exchange_eval(board, move) == 500 + (900 - 100)


def test_hanging_piece_via_quiet_move() -> None:
    # Knight moves to an empty, undefended square attacked by a pawn: this is
    # the case the coach must catch even though the move isn't a capture.
    board = chess.Board("k7/8/2n5/8/8/4P3/8/K7 b - - 0 1")
    move = chess.Move.from_uci("c6d4")
    assert static_exchange_eval(board, move) == -320


def test_defended_piece_is_not_hanging_for_the_attacker() -> None:
    # Same shape as the losing-trade case, phrased from the "would this be a
    # hanging piece" angle: capturing a defended pawn with a bishop is bad
    # for the attacker, so a caller using SEE to flag hanging pieces must not
    # treat the defended pawn as free material.
    board = chess.Board("4k3/8/p7/1p6/2B5/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("c4b5")
    assert static_exchange_eval(board, move) < 0


@pytest.mark.engine
def test_see_agrees_with_engine_choice_on_good_capture(stockfish_path: str) -> None:
    # A full-depth "before vs after" eval swing doesn't work as a sanity check
    # here: search at the pre-move position already assumes best play, which
    # *is* this exact capture, so the swing collapses to ~0 regardless of
    # SEE's verdict. Comparing against the engine's own best-move choice
    # sidesteps that: a materially decisive capture should be what a strong
    # engine actually plays.
    board = chess.Board("4k3/8/2p5/3n4/4P3/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("e4d5")
    assert static_exchange_eval(board, move) > 0

    with EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS) as pool:
        result = pool.analyse(board, depth=12, use_cache=False)

    assert result.best_move_uci == move.uci()


@pytest.mark.engine
def test_see_agrees_with_engine_choice_on_hanging_piece(stockfish_path: str) -> None:
    board = chess.Board("k7/8/2n5/8/8/4P3/8/K7 b - - 0 1")
    move = chess.Move.from_uci("c6d4")
    assert static_exchange_eval(board, move) < 0

    with EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS) as pool:
        result = pool.analyse(board, depth=12, use_cache=False)

    assert result.best_move_uci != move.uci()
