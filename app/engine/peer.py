from __future__ import annotations

from app.engine.pool import EnginePool

MIN_UCI_ELO = 1320
MAX_UCI_ELO = 3190


def build_peer_pool(
    path: str,
    player_rating: int,
    *,
    pool_size: int = 1,
    default_timeout: float = 10.0,
) -> EnginePool:
    """A Stockfish pool strength-limited to approximate a player of `player_rating`.

    Exists solely to answer "would a player of this strength find this move
    too" (Rule 1's reachability gate / Recipe R5) -- never used as a source
    of coaching truth, only as a second opinion for filtering.
    """
    elo = max(MIN_UCI_ELO, min(MAX_UCI_ELO, player_rating))
    return EnginePool(
        path,
        pool_size=pool_size,
        uci_options={"UCI_LimitStrength": True, "UCI_Elo": elo},
        default_timeout=default_timeout,
    )
