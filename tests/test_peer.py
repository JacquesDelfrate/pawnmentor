from __future__ import annotations

import pytest

from app.engine.peer import MAX_UCI_ELO, MIN_UCI_ELO, build_peer_pool


def test_rating_clamped_to_min() -> None:
    pool = build_peer_pool("unused-path", 400)
    assert pool._uci_options["UCI_Elo"] == MIN_UCI_ELO
    assert pool._uci_options["UCI_LimitStrength"] is True


def test_rating_clamped_to_max() -> None:
    pool = build_peer_pool("unused-path", 4000)
    assert pool._uci_options["UCI_Elo"] == MAX_UCI_ELO


def test_rating_within_range_passes_through() -> None:
    pool = build_peer_pool("unused-path", 1500)
    assert pool._uci_options["UCI_Elo"] == 1500


@pytest.mark.engine
def test_peer_pool_can_analyse(stockfish_path: str) -> None:
    import chess

    with build_peer_pool(stockfish_path, 1200) as pool:
        result = pool.analyse(chess.Board(), depth=8)

    assert result.best_move_uci
