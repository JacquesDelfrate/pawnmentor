from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401  -- registers table models on SQLModel.metadata


def _connect_args(database_url: str) -> dict[str, bool]:
    # check_same_thread is SQLite-specific (needed because FastAPI can hand a
    # request to a different thread than the one that opened the
    # connection). Everything else about this module is plain
    # SQLModel/SQLAlchemy, no SQLite-only dialect features, so swapping
    # DATABASE_URL to Postgres needs no code change here -- split out so
    # this branch is testable without a Postgres driver installed (building
    # a real postgresql:// engine eagerly imports psycopg2).
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, connect_args=_connect_args(database_url))


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


def get_session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session
