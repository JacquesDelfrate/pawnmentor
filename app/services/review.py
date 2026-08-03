from __future__ import annotations

import chess
from sqlmodel import Session

from app.engine.pool import EnginePool
from app.graph.graph import build_pipeline_graph
from app.llm.client import LLMClient
from app.llm.db_logging_client import DBLoggingLLMClient
from app.llm.logging_client import LoggingLLMClient
from app.models import FlaggedErrorRecord, Game, Review
from app.services.chess_com import parse_game_moves, resolve_player_color


class ReviewError(RuntimeError):
    pass


async def run_review(
    session: Session,
    full_pool: EnginePool,
    stockfish_path: str,
    base_llm: LLMClient,
    game: Game,
    player_username: str,
    player_rating: int,
    *,
    scan_depth: int = 16,
    diagnosis_depth: int = 20,
) -> Review:
    """Orchestrates one full review: runs the pipeline graph, then flattens
    its results into FlaggedErrorRecord rows. The graph itself only holds
    the rich in-memory dataclasses (Diagnosis, Classification, ...) -- this
    is the one place that translates them into what actually gets persisted.
    """
    color = resolve_player_color(game.white_username, game.black_username, player_username)
    if color is None:
        raise ReviewError(f"{player_username!r} is not a player in game {game.id}")

    review = Review(
        game_id=game.id,
        player_username=player_username,
        player_color=color,
        player_rating=player_rating,
        status="running",
    )
    session.add(review)
    session.commit()
    session.refresh(review)

    llm = DBLoggingLLMClient(LoggingLLMClient(base_llm), session, review.id)
    board, moves = parse_game_moves(game.pgn)
    graph = build_pipeline_graph(
        full_pool, stockfish_path, llm, scan_depth=scan_depth, diagnosis_depth=diagnosis_depth
    )

    try:
        result = await graph.ainvoke(
            {
                "fen": board.fen(),
                "moves_uci": [move.uci() for move in moves],
                "player_color": color,
                "player_rating": player_rating,
            },
            config={"configurable": {"thread_id": f"review-{review.id}"}},
        )
    except Exception:
        review.status = "failed"
        session.add(review)
        session.commit()
        raise

    for classification, message in zip(
        result["classifications"], result["coaching_messages"], strict=True
    ):
        move_eval = classification.diagnosis.flagged_error.move_eval
        board_before = chess.Board(move_eval.eval_before.fen)
        best_move = chess.Move.from_uci(move_eval.eval_before.analysis.best_move_uci)
        session.add(
            FlaggedErrorRecord(
                review_id=review.id,
                ply=move_eval.ply,
                fen_before=board_before.fen(),
                move_san=board_before.san(move_eval.move),
                best_move_san=board_before.san(best_move),
                delta_cp=move_eval.delta_cp,
                category=classification.category.value,
                coaching_text=message.text,
            )
        )

    review.status = "complete"
    session.add(review)
    session.commit()
    session.refresh(review)
    return review
