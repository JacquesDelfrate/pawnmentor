from __future__ import annotations

from dataclasses import dataclass
from typing import NotRequired, TypedDict

import chess

from app.analysis.fork import Fork
from app.analysis.hanging_piece import HangingPiece
from app.analysis.pin import Pin


@dataclass(frozen=True, slots=True)
class MotifReport:
    color: chess.Color
    hanging_pieces: tuple[HangingPiece, ...]
    pins: tuple[Pin, ...]
    forks: tuple[Fork, ...]

    def is_empty(self) -> bool:
        return not (self.hanging_pieces or self.pins or self.forks)


class MotifState(TypedDict):
    """State for the standalone single-position motif-check graph."""

    fen: str
    color: bool
    motifs: NotRequired[MotifReport]
