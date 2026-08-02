FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    STOCKFISH_PATH=/usr/local/bin/stockfish

# Linux Stockfish build -- the binary already in this repo (stockfish-windows-x86-64-avx2.exe)
# is Windows-only and gitignored, so the container needs its own. AVX2 is a safe baseline for
# modern x86-64 hosts; sf_18 matches the version already used for local dev.
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -sL https://github.com/official-stockfish/Stockfish/releases/download/sf_18/stockfish-ubuntu-x86-64-avx2.tar -o /tmp/stockfish.tar && \
    tar -xf /tmp/stockfish.tar -C /tmp && \
    mv /tmp/stockfish/stockfish-ubuntu-x86-64-avx2 "$STOCKFISH_PATH" && \
    chmod +x "$STOCKFISH_PATH" && \
    rm -rf /tmp/stockfish.tar /tmp/stockfish && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install dependencies before copying app code so this layer stays cached across code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY app ./app
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
