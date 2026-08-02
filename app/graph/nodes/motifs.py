from __future__ import annotations

import chess

from app.analysis.fork import find_forks
from app.analysis.hanging_piece import find_hanging_pieces
from app.analysis.pin import find_pins
from app.graph.state import MotifReport, MotifState


def classify_motifs(state: MotifState) -> dict[str, MotifReport]:
    board = chess.Board(state["fen"])
    color = state["color"]
    report = MotifReport(
        color=color,
        hanging_pieces=tuple(find_hanging_pieces(board, color)),
        pins=tuple(find_pins(board, color)),
        forks=tuple(find_forks(board, color)),
    )
    return {"motifs": report}
