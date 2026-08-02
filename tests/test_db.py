from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.db import _connect_args, create_db_engine, init_db
from app.models import FlaggedErrorRecord, Game, LLMCallLogRecord, Review


def test_init_db_creates_tables_and_roundtrips_a_review(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{db_path}")
    init_db(engine)

    with Session(engine) as session:
        game = Game(
            source="chess.com",
            external_id="https://www.chess.com/game/live/123",
            pgn="1. e4 e5",
            white_username="alice",
            black_username="bob",
        )
        session.add(game)
        session.commit()
        session.refresh(game)
        game_id = game.id

        review = Review(
            game_id=game_id,
            player_username="alice",
            player_color=True,
            player_rating=1200,
            status="complete",
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        review_id = review.id

        error = FlaggedErrorRecord(
            review_id=review_id,
            ply=1,
            fen_before="6k1/pp3ppp/2p5/8/8/2N5/PP3PPP/6K1 w - - 0 1",
            move_san="Nd5",
            best_move_san="Nb1",
            delta_cp=-320,
            category="hung_piece",
            coaching_text="Your knight jumped to an undefended square.",
        )
        log = LLMCallLogRecord(
            review_id=review_id,
            prompt="explain this",
            output="Your knight jumped to an undefended square.",
            latency_seconds=1.2,
            prompt_tokens=50,
            completion_tokens=20,
        )
        session.add(error)
        session.add(log)
        session.commit()

    with Session(engine) as session:
        stored_review = session.exec(select(Review)).one()
        assert stored_review.player_username == "alice"
        assert stored_review.game_id == game_id

        stored_errors = session.exec(select(FlaggedErrorRecord)).all()
        assert len(stored_errors) == 1
        assert stored_errors[0].category == "hung_piece"

        stored_logs = session.exec(select(LLMCallLogRecord)).all()
        assert len(stored_logs) == 1
        assert stored_logs[0].prompt_tokens == 50


def test_connect_args_only_set_for_sqlite() -> None:
    # Postgres-swappable: the only per-dialect branch in create_db_engine is
    # this one, and it's empty for non-sqlite URLs -- tested directly rather
    # than via a real postgresql:// engine, since constructing one eagerly
    # imports the psycopg2 driver, which isn't installed (and doesn't need
    # to be, since the app runs on SQLite by default).
    assert _connect_args("sqlite:///./pawnmentor.db") == {"check_same_thread": False}
    assert _connect_args("postgresql://user:pass@localhost/dbname") == {}
