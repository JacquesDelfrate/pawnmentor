"""
Chess.com Daily Game Advisor
Fetches your active daily games and suggests the best move using Stockfish.

Requirements:
    pip install python-chess stockfish requests

Stockfish binary:
    Download from https://stockfishchess.org/download/
    Set STOCKFISH_PATH below to its location.
"""

import sys
import requests
import chess
import chess.pgn
import io
from stockfish import Stockfish

# --- Configuration ---
CHESS_COM_USERNAME = "zakatis"
STOCKFISH_PATH = r"D:\Programming\chess\stockfish-windows-x86-64-avx2.exe"
ANALYSIS_DEPTH = 18
MULTIPV = 3  # number of best moves to show
# ---------------------

HEADERS = {"User-Agent": "chess-advisor/1.0 (contact: you@email.com)"}


def fetch_daily_games(username: str) -> list[dict]:
    url = f"https://api.chess.com/pub/player/{username}/games"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json().get("games", [])


def pgn_to_board(pgn_str: str) -> chess.Board:
    game = chess.pgn.read_game(io.StringIO(pgn_str))
    board = game.board()
    for move in game.mainline_moves():
        board.push(move)
    return board


def get_player_color(game: dict, username: str) -> str:
    white = game.get("white", "")
    if isinstance(white, dict):
        white = white.get("username", "")
    if white.lower().endswith(username.lower()):
        return "white"
    return "black"


def analyze_position(sf: Stockfish, board: chess.Board, multipv: int) -> list[dict]:
    sf.set_fen_position(board.fen())
    return sf.get_top_moves(multipv)


def format_move(board: chess.Board, move_uci: str) -> str:
    move = chess.Move.from_uci(move_uci)
    return board.san(move)


def main():
    if CHESS_COM_USERNAME == "your_username_here":
        print("Set CHESS_COM_USERNAME in the script before running.")
        sys.exit(1)

    print(f"Fetching daily games for '{CHESS_COM_USERNAME}'...")
    try:
        games = fetch_daily_games(CHESS_COM_USERNAME)
    except requests.HTTPError as e:
        print(f"Failed to fetch games: {e}")
        sys.exit(1)

    if not games:
        print("No active daily games found.")
        return

    print(f"Found {len(games)} active game(s).\n")

    try:
        sf = Stockfish(path=STOCKFISH_PATH, depth=ANALYSIS_DEPTH)
    except Exception as e:
        print(f"Could not start Stockfish at '{STOCKFISH_PATH}': {e}")
        sys.exit(1)

    for i, game in enumerate(games, 1):
        white = game.get("white", "?").split("/")[-1]
        black = game.get("black", "?").split("/")[-1]
        url = game.get("url", "")
        pgn = game.get("pgn", "")
        turn_color = "white" if game.get("turn") == "white" else "black"
        my_color = get_player_color(game, CHESS_COM_USERNAME)

        print(f"Game {i}: {white} vs {black}")
        print(f"  URL   : {url}")
        print(f"  Your color : {my_color}")
        print(f"  Turn  : {turn_color}")

        if turn_color != my_color:
            print("  (Waiting for opponent)\n")
            continue

        if not pgn:
            print("  No PGN available.\n")
            continue

        board = pgn_to_board(pgn)

        if board.is_game_over():
            print(f"  Game over: {board.result()}\n")
            continue

        top_moves = analyze_position(sf, board, MULTIPV)

        print(f"  Position FEN: {board.fen()}")
        print(f"  Best moves (depth {ANALYSIS_DEPTH}):")
        for rank, m in enumerate(top_moves, 1):
            uci = m.get("Move", "")
            centipawns = m.get("Centipawn")
            mate = m.get("Mate")

            san = format_move(board, uci)
            if mate is not None:
                score_str = f"Mate in {mate}"
            elif centipawns is not None:
                score_str = f"{centipawns / 100:+.2f}"
            else:
                score_str = "?"

            print(f"    {rank}. {san:<8} ({score_str})")
        print()


if __name__ == "__main__":
    main()
