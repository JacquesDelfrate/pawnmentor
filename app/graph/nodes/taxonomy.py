from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    """Categories the classification node assigns a confirmed error to.

    Deliberately scoped to what the deterministic detectors can actually
    verify (`app/analysis/`) -- this is a lookup over engine-verified facts,
    not a judgment anything invents. Each category below documents the fact
    pattern in `Diagnosis` that justifies it.

    Note that the motif categories key off `motifs_introduced`, not
    `motifs_after`: a weakness that already existed before the move is not
    something the move did. OTHER_TACTICAL_OVERSIGHT exists because the
    detectors don't cover every pattern (no skewer or discovered-attack
    detector, no positional evaluation beyond eval_cp), and an honest
    fallback beats forcing a specific mechanism that was never confirmed.
    """

    HUNG_PIECE = "hung_piece"
    """diagnosis.motifs_introduced.hanging_pieces is non-empty -- a piece of
    the mover's became capturable that was not before."""

    ALLOWED_FORK = "allowed_fork"
    """diagnosis.motifs_introduced.forks is non-empty -- the move handed the
    opponent a fork that did not exist beforehand."""

    WALKED_INTO_PIN = "walked_into_pin"
    """diagnosis.motifs_introduced.pins is non-empty -- the move created the
    pin. A pin that predates the move never lands here."""

    BAD_TRADE = "bad_trade"
    """The move itself was a capture with static_exchange_eval < 0 -- the
    material loss is explained directly by the trade, not by what it
    exposed afterward."""

    MISSED_EXISTING_THREAT = "missed_existing_threat"
    """diagnosis.motifs_unresolved is non-empty -- the move created nothing
    new, but left a pre-existing weakness standing that the engine's move
    would have cleared. The "would have cleared" half is what makes this a
    verified claim rather than a guess: without it, every move played in an
    already-awkward position would be blamed for the awkwardness."""

    OTHER_TACTICAL_OVERSIGHT = "other_tactical_oversight"
    """The eval swing is confirmed (deep_delta_cp) but no detector matched --
    honest fallback, not a specific claim about the mechanism."""
