from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.llm.client import LLMResponse
from app.main import app

pytestmark = pytest.mark.engine

SAMPLE_GAMES_PAYLOAD = {
    "games": [
        {
            "url": "https://www.chess.com/game/live/1",
            "white": {"username": "alice"},
            "black": {"username": "bob"},
            # 2. Ne5?? hangs the knight for free to Nc6 -- nothing else
            # defends e5 at this point.
            "pgn": '[White "alice"]\n[Black "bob"]\n\n1. Nf3 Nc6 2. Ne5 *',
        }
    ]
}


class _FakeLLMClient:
    async def complete(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float = 0.0
    ) -> LLMResponse:
        return LLMResponse(
            text="Your knight landed on an undefended square.\n\nWhat's worth checking first?",
            prompt_tokens=5,
            completion_tokens=5,
        )


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_games_stores_and_dedupes() -> None:
    with (
        patch("app.main.fetch_current_games", return_value=SAMPLE_GAMES_PAYLOAD["games"]),
        TestClient(app) as client,
    ):
        first = client.post("/games/ingest", json={"username": "alice"})
        second = client.post("/games/ingest", json={"username": "alice"})

    assert first.status_code == 200
    body = first.json()
    assert len(body) == 1
    assert body[0]["white_username"] == "alice"
    assert body[0]["black_username"] == "bob"

    assert second.status_code == 200
    assert second.json()[0]["id"] == body[0]["id"]


def test_review_404_for_unknown_game() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/reviews", json={"game_id": 999_999, "player_username": "alice", "player_rating": 1200}
        )
    assert response.status_code == 404


def test_review_get_404_for_unknown_review() -> None:
    with TestClient(app) as client:
        response = client.get("/reviews/999999")
    assert response.status_code == 404


def test_review_503_when_llm_not_configured() -> None:
    with (
        patch("app.main.fetch_current_games", return_value=SAMPLE_GAMES_PAYLOAD["games"]),
        TestClient(app) as client,
    ):
        ingested = client.post("/games/ingest", json={"username": "alice"}).json()
        response = client.post(
            "/reviews",
            json={
                "game_id": ingested[0]["id"],
                "player_username": "alice",
                "player_rating": 1200,
            },
        )
    assert response.status_code == 503


def test_review_end_to_end_with_fake_llm() -> None:
    with (
        patch("app.main.fetch_current_games", return_value=SAMPLE_GAMES_PAYLOAD["games"]),
        patch("app.main.build_vllm_client", return_value=_FakeLLMClient()),
        TestClient(app) as client,
    ):
        ingested = client.post("/games/ingest", json={"username": "alice"}).json()
        response = client.post(
            "/reviews",
            json={
                "game_id": ingested[0]["id"],
                "player_username": "alice",
                "player_rating": 1200,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert len(body["flagged_errors"]) == 1
    assert body["flagged_errors"][0]["category"] == "hung_piece"
