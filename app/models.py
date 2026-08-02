from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Game(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source: str
    external_id: str = Field(index=True)
    pgn: str
    white_username: str
    black_username: str
    created_at: datetime = Field(default_factory=_utcnow)


class Review(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id", index=True)
    player_username: str
    player_color: bool
    player_rating: int
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=_utcnow)


class FlaggedErrorRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    review_id: int = Field(foreign_key="review.id", index=True)
    ply: int
    fen_before: str
    move_san: str
    best_move_san: str
    delta_cp: int
    category: str
    coaching_text: str
    created_at: datetime = Field(default_factory=_utcnow)


class LLMCallLogRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    review_id: int | None = Field(default=None, foreign_key="review.id", index=True)
    prompt: str
    output: str
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime = Field(default_factory=_utcnow)
