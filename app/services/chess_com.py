from __future__ import annotations

import io

import chess
import chess.pgn
import requests

HEADERS = {"User-Agent": "pawnmentor/0.1 (contact: set-a-real-contact-email)"}
_TIMEOUT_SECONDS = 10


class ChessComError(RuntimeError):
    pass


def fetch_current_games(username: str) -> list[dict[str, object]]:
    """In-progress games for `username` (chess.com's "current games" endpoint --
    the natural fit for correspondence games, which can run for days/weeks).
    """
    url = f"https://api.chess.com/pub/player/{username}/games"
    response = requests.get(url, headers=HEADERS, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    games = response.json().get("games", [])
    if not isinstance(games, list):
        raise ChessComError(f"Unexpected response shape from {url}")
    return games


def fetch_archived_games(username: str, year: int, month: int) -> list[dict[str, object]]:
    """Completed games for `username` in a given month (chess.com's monthly archive)."""
    url = f"https://api.chess.com/pub/player/{username}/games/{year:04d}/{month:02d}"
    response = requests.get(url, headers=HEADERS, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    games = response.json().get("games", [])
    if not isinstance(games, list):
        raise ChessComError(f"Unexpected response shape from {url}")
    return games


def player_color(game: dict[str, object], username: str) -> chess.Color:
    white = game.get("white", "")
    if isinstance(white, dict):
        white = white.get("username", "")
    return chess.WHITE if str(white).lower().endswith(username.lower()) else chess.BLACK


def resolve_player_color(
    white_username: str, black_username: str, player_username: str
) -> chess.Color | None:
    """Which side `player_username` is playing, or None if they aren't in the
    game at all. Takes plain usernames rather than a Game row so it stays
    usable from anywhere without dragging the DB models along.
    """
    target = player_username.lower()
    if white_username.lower() == target:
        return chess.WHITE
    if black_username.lower() == target:
        return chess.BLACK
    return None


def current_position(pgn: str) -> chess.Board:
    """The live position: every move in the PGN replayed onto the board."""
    board, moves = parse_game_moves(pgn)
    for move in moves:
        board.push(move)
    return board


def parse_game_moves(pgn: str) -> tuple[chess.Board, list[chess.Move]]:
    """The game's starting position and its move list, in playing order --
    what eval_trajectory needs (it replays moves onto `board` itself).
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise ChessComError("Could not parse PGN")
    return game.board(), list(game.mainline_moves())
