from __future__ import annotations

import os

import pytest


@pytest.fixture
def stockfish_path() -> str:
    path = os.environ.get("STOCKFISH_PATH")
    if not path:
        pytest.skip("STOCKFISH_PATH not set")
    return path
