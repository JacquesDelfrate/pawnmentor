from __future__ import annotations

import chess

from app.graph.graph import build_motifs_graph
from app.graph.nodes.motifs import classify_motifs
from app.graph.state import MotifState


def test_quiet_position_has_no_motifs() -> None:
    state: MotifState = {"fen": chess.Board().fen(), "color": chess.WHITE}
    result = classify_motifs(state)
    report = result["motifs"]
    assert report.hanging_pieces == ()
    assert report.pins == ()
    assert report.forks == ()


def test_hanging_piece_reaches_the_report() -> None:
    # Same FEN as test_hanging_piece.py::test_single_hanging_piece_detected.
    state: MotifState = {"fen": "k7/8/8/8/3n4/4P3/8/K7 w - - 0 1", "color": chess.BLACK}
    report = classify_motifs(state)["motifs"]
    assert len(report.hanging_pieces) == 1
    assert report.hanging_pieces[0].square == chess.D4


def test_pin_reaches_the_report() -> None:
    # Same FEN as test_pin.py::test_diagonal_pin_detected.
    state: MotifState = {"fen": "4k3/8/8/8/1b6/2N5/8/4K3 w - - 0 1", "color": chess.WHITE}
    report = classify_motifs(state)["motifs"]
    assert len(report.pins) == 1
    assert report.pins[0].pinned_square == chess.C3


def test_fork_reaches_the_report() -> None:
    # Same FEN as test_fork.py's GENUINE_FORK_FEN.
    state: MotifState = {"fen": "k7/8/2p3p1/4N3/8/8/8/K7 w - - 0 1", "color": chess.WHITE}
    report = classify_motifs(state)["motifs"]
    assert len(report.forks) == 1
    assert report.forks[0].forker_square == chess.E5


def test_compiled_graph_runs_end_to_end() -> None:
    state: MotifState = {"fen": "k7/8/8/8/3n4/4P3/8/K7 w - - 0 1", "color": chess.BLACK}

    direct = classify_motifs(state)["motifs"]

    graph = build_motifs_graph()
    result = graph.invoke(state, config={"configurable": {"thread_id": "test"}})

    assert result["motifs"] == direct
