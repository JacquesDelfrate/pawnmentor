from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.config import ConfigError, Settings
from app.db import create_db_engine, get_session, init_db
from app.engine.pool import EnginePool
from app.llm.vllm_client import build_vllm_client
from app.models import FlaggedErrorRecord, Game, Review
from app.services.advisor import AdvisorError, advise_best_move
from app.services.chess_com import ChessComError, fetch_current_games
from app.services.review import ReviewError, run_review


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.from_env()
    app.state.settings = settings
    app.state.engine_pool = EnginePool(
        settings.stockfish_path,
        pool_size=settings.engine_pool_size,
        default_timeout=settings.engine_timeout_seconds,
    )
    app.state.db_engine = create_db_engine(settings.database_url)
    init_db(app.state.db_engine)
    try:
        yield
    finally:
        app.state.engine_pool.close()


app = FastAPI(title="PawnMentor", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def get_db_session() -> Iterator[Session]:
    yield from get_session(app.state.db_engine)


DbSession = Annotated[Session, Depends(get_db_session)]


class IngestRequest(BaseModel):
    username: str


class IngestedGame(BaseModel):
    id: int
    external_id: str
    white_username: str
    black_username: str


@app.post("/games/ingest", response_model=list[IngestedGame])
def ingest_games(request: IngestRequest, session: DbSession) -> list[Game]:
    try:
        games = fetch_current_games(request.username)
    except ChessComError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    ingested: list[Game] = []
    for raw in games:
        external_id = str(raw.get("url", ""))
        if not external_id:
            continue

        existing = session.exec(
            select(Game).where(Game.external_id == external_id)
        ).first()
        if existing is not None:
            ingested.append(existing)
            continue

        white = raw.get("white", "")
        black = raw.get("black", "")
        white_username = white.get("username", "") if isinstance(white, dict) else str(white)
        black_username = black.get("username", "") if isinstance(black, dict) else str(black)

        game = Game(
            source="chess.com",
            external_id=external_id,
            pgn=str(raw.get("pgn", "")),
            white_username=white_username.rsplit("/", 1)[-1],
            black_username=black_username.rsplit("/", 1)[-1],
        )
        session.add(game)
        session.commit()
        session.refresh(game)
        ingested.append(game)

    return ingested


class BestMoveResponse(BaseModel):
    game_id: int
    fen: str
    is_player_turn: bool
    is_game_over: bool
    best_move_san: str | None
    score_cp: int | None
    mate_in: int | None
    pv_san: list[str]


@app.get("/games/{game_id}/best-move", response_model=BestMoveResponse)
def best_move(game_id: int, username: str, session: DbSession) -> BestMoveResponse:
    """Engine recommendation for where the game stands right now.

    Separate from /reviews rather than folded into it: this is fast (one
    engine call) where a review is slow (a full-game scan plus an LLM call
    per flagged error), and it goes stale the moment the opponent replies,
    so it wants recomputing on demand rather than being persisted alongside
    a review.
    """
    game = session.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    try:
        advice = advise_best_move(
            app.state.engine_pool,
            game.pgn,
            game.white_username,
            game.black_username,
            username,
        )
    except AdvisorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BestMoveResponse(
        game_id=game_id,
        fen=advice.fen,
        is_player_turn=advice.is_player_turn,
        is_game_over=advice.is_game_over,
        best_move_san=advice.best_move_san,
        score_cp=advice.score_cp,
        mate_in=advice.mate_in,
        pv_san=list(advice.pv_san),
    )


class ReviewRequest(BaseModel):
    game_id: int
    player_username: str
    player_rating: int


class FlaggedErrorResponse(BaseModel):
    ply: int
    fen_before: str
    move_san: str
    best_move_san: str
    delta_cp: int
    category: str
    coaching_text: str


class ReviewResponse(BaseModel):
    id: int
    status: str
    player_username: str
    player_rating: int
    flagged_errors: list[FlaggedErrorResponse]


@app.post("/reviews", response_model=ReviewResponse)
async def create_review(request: ReviewRequest, session: DbSession) -> ReviewResponse:
    game = session.get(Game, request.game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")

    settings: Settings = app.state.settings
    try:
        llm = build_vllm_client(settings)
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        review = await run_review(
            session,
            app.state.engine_pool,
            settings.stockfish_path,
            llm,
            game,
            request.player_username,
            request.player_rating,
        )
    except ReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _review_response(session, review)


@app.get("/reviews/{review_id}", response_model=ReviewResponse)
def get_review(review_id: int, session: DbSession) -> ReviewResponse:
    review = session.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return _review_response(session, review)


def _review_response(session: Session, review: Review) -> ReviewResponse:
    assert review.id is not None
    errors = session.exec(
        select(FlaggedErrorRecord).where(FlaggedErrorRecord.review_id == review.id)
    ).all()
    errors = sorted(errors, key=lambda e: e.ply)
    return ReviewResponse(
        id=review.id,
        status=review.status,
        player_username=review.player_username,
        player_rating=review.player_rating,
        flagged_errors=[
            FlaggedErrorResponse(
                ply=e.ply,
                fen_before=e.fen_before,
                move_san=e.move_san,
                best_move_san=e.best_move_san,
                delta_cp=e.delta_cp,
                category=e.category,
                coaching_text=e.coaching_text,
            )
            for e in errors
        ],
    )
