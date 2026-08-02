from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Settings:
    stockfish_path: str
    engine_pool_size: int = 2
    engine_timeout_seconds: float = 10.0
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_model: str = ""
    llm_timeout_seconds: float = 60.0
    database_url: str = "sqlite:///./pawnmentor.db"

    @classmethod
    def from_env(cls) -> Settings:
        stockfish_path = os.environ.get("STOCKFISH_PATH")
        if not stockfish_path:
            raise ConfigError(
                "STOCKFISH_PATH environment variable must be set to the Stockfish binary path."
            )
        pool_size = int(os.environ.get("ENGINE_POOL_SIZE", "2"))
        timeout_seconds = float(os.environ.get("ENGINE_TIMEOUT_SECONDS", "10.0"))
        vllm_base_url = os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1")
        vllm_model = os.environ.get("VLLM_MODEL", "")
        llm_timeout_seconds = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60.0"))
        database_url = os.environ.get("DATABASE_URL", "sqlite:///./pawnmentor.db")
        return cls(
            stockfish_path=stockfish_path,
            engine_pool_size=pool_size,
            engine_timeout_seconds=timeout_seconds,
            vllm_base_url=vllm_base_url,
            vllm_model=vllm_model,
            llm_timeout_seconds=llm_timeout_seconds,
            database_url=database_url,
        )
