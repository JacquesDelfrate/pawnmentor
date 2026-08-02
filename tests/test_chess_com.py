from __future__ import annotations

from unittest.mock import MagicMock, patch

import chess
import pytest

from app.services.chess_com import (
    ChessComError,
    fetch_archived_games,
    fetch_current_games,
    parse_game_moves,
    player_color,
)

SAMPLE_PGN = """[Event "Live Chess"]
[White "alice"]
[Black "bob"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 *
"""


def _mock_response(payload: dict[str, object]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_fetch_current_games_returns_the_games_list() -> None:
    with patch(
        "app.services.chess_com.requests.get",
        return_value=_mock_response({"games": [{"url": "g1"}]}),
    ) as mock_get:
        games = fetch_current_games("alice")

    assert games == [{"url": "g1"}]
    assert "alice" in mock_get.call_args.args[0]


def test_fetch_current_games_rejects_unexpected_shape() -> None:
    with patch(
        "app.services.chess_com.requests.get", return_value=_mock_response({"games": "not-a-list"})
    ):
        with pytest.raises(ChessComError):
            fetch_current_games("alice")


def test_fetch_archived_games_builds_the_month_url() -> None:
    with patch(
        "app.services.chess_com.requests.get", return_value=_mock_response({"games": []})
    ) as mock_get:
        fetch_archived_games("alice", 2026, 3)

    assert mock_get.call_args.args[0] == "https://api.chess.com/pub/player/alice/games/2026/03"


def test_player_color_matches_white_username() -> None:
    game = {"white": {"username": "Alice"}, "black": {"username": "Bob"}}
    assert player_color(game, "alice") == chess.WHITE
    assert player_color(game, "bob") == chess.BLACK


def test_parse_game_moves_returns_starting_board_and_moves() -> None:
    board, moves = parse_game_moves(SAMPLE_PGN)

    assert board.fen() == chess.Board().fen()
    assert [m.uci() for m in moves] == ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]


def test_parse_game_moves_rejects_unparseable_pgn() -> None:
    with pytest.raises(ChessComError):
        parse_game_moves("")
