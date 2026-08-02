from __future__ import annotations

from enum import StrEnum


class ErrorCategory(StrEnum):
    """Categories the classification node assigns a confirmed error to.

    Deliberately scoped to what the deterministic detectors can actually
    verify (`app/analysis/`) -- this is a lookup the LLM performs over
    engine-verified facts, not a judgment it invents. Each category name
    below documents the fact pattern in `Diagnosis` that justifies it;
    OTHER_TACTICAL_OVERSIGHT exists because our motif detectors don't cover
    every possible pattern (no skewer/discovered-attack detector, no
    positional evaluation beyond eval_cp), and the classifier must have a
    truthful fallback rather than being forced to fabricate a specific
    mechanism that was never actually confirmed.
    """

    HUNG_PIECE = "hung_piece"
    """diagnosis.motifs_after.hanging_pieces is non-empty for the mover."""

    ALLOWED_FORK = "allowed_fork"
    """diagnosis.motifs_after.forks is non-empty against the mover."""

    WALKED_INTO_PIN = "walked_into_pin"
    """diagnosis.motifs_after.pins is non-empty against the mover."""

    BAD_TRADE = "bad_trade"
    """The move itself was a capture with static_exchange_eval < 0 -- the
    material loss is explained directly by the trade, not by what it
    exposed afterward."""

    OTHER_TACTICAL_OVERSIGHT = "other_tactical_oversight"
    """The eval swing is confirmed (deep_delta_cp) but no detector matched --
    honest fallback, not a specific claim about the mechanism."""
