from __future__ import annotations

import chess
import pytest

from app.engine.pool import EnginePool
from app.services.advisor import AdvisorError, advise_best_move
from app.services.chess_com import resolve_player_color

FIXED_UCI_OPTIONS = {"Threads": 1, "Hash": 16}

# 1. e4 e5 2. Nf3 -- Black to move.
PGN_BLACK_TO_MOVE = '[White "alice"]\n[Black "bob"]\n\n1. e4 e5 2. Nf3 *'
# Fool's mate, already finished.
PGN_FINISHED = '[White "alice"]\n[Black "bob"]\n\n1. f3 e5 2. g4 Qh4# 0-1'


def test_resolve_player_color_is_case_insensitive() -> None:
    assert resolve_player_color("Alice", "Bob", "alice") == chess.WHITE
    assert resolve_player_color("Alice", "Bob", "BOB") == chess.BLACK


def test_resolve_player_color_returns_none_for_a_spectator() -> None:
    assert resolve_player_color("alice", "bob", "carol") is None


@pytest.fixture
def pool(stockfish_path: str):
    p = EnginePool(stockfish_path, pool_size=1, uci_options=FIXED_UCI_OPTIONS, default_timeout=30.0)
    yield p
    p.close()


@pytest.mark.engine
def test_recommends_a_legal_move_when_it_is_the_players_turn(pool: EnginePool) -> None:
    advice = advise_best_move(pool, PGN_BLACK_TO_MOVE, "alice", "bob", "bob", depth=12)

    assert advice.is_player_turn
    assert not advice.is_game_over
    assert advice.best_move_san is not None
    # SAN only parses against the position it belongs to, so this doubles as
    # a check that the returned FEN really is the position advised on.
    board = chess.Board(advice.fen)
    assert board.parse_san(advice.best_move_san) in board.legal_moves
    assert advice.pv_san


@pytest.mark.engine
def test_no_recommendation_when_the_opponent_is_on_move(pool: EnginePool) -> None:
    advice = advise_best_move(pool, PGN_BLACK_TO_MOVE, "alice", "bob", "alice", depth=12)

    assert not advice.is_player_turn
    assert advice.best_move_san is None
    assert advice.pv_san == ()


@pytest.mark.engine
def test_no_recommendation_once_the_game_is_over(pool: EnginePool) -> None:
    # Engines handle a mated position poorly, so this must be caught before
    # anything is handed to Stockfish.
    advice = advise_best_move(pool, PGN_FINISHED, "alice", "bob", "bob", depth=12)

    assert advice.is_game_over
    assert not advice.is_player_turn
    assert advice.best_move_san is None


@pytest.mark.engine
def test_rejects_a_username_that_is_not_in_the_game(pool: EnginePool) -> None:
    with pytest.raises(AdvisorError):
        advise_best_move(pool, PGN_BLACK_TO_MOVE, "alice", "bob", "carol", depth=12)
