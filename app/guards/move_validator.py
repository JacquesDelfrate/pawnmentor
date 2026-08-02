from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import chess

_MOVE_TOKEN_PATTERN = re.compile(
    r"""
    \b(?:
        [a-h][1-8][a-h][1-8][qrbn]? |
        O-O(?:-O)?[+\#]? | 0-0(?:-0)?[+\#]? |
        [KQRBN][a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+\#]? |
        [a-h]x[a-h][1-8](?:=[QRBN])?[+\#]? |
        [a-h][1-8](?:=[QRBN])?[+\#]?
    )\b
    """,
    re.VERBOSE,
)


class MoveValidationError(ValueError):
    def __init__(self, offending_tokens: Sequence[str]) -> None:
        self.offending_tokens = list(offending_tokens)
        super().__init__(
            "LLM output contains unverified move-shaped token(s): "
            + ", ".join(self.offending_tokens)
        )


def validate_llm_output(
    text: str, board: chess.Board, verified_moves: Iterable[chess.Move]
) -> None:
    acceptable = _acceptable_tokens(board, verified_moves)
    offending = [
        token for token in _extract_move_tokens(text) if _normalize(token) not in acceptable
    ]
    if offending:
        raise MoveValidationError(offending)


def _acceptable_tokens(board: chess.Board, verified_moves: Iterable[chess.Move]) -> set[str]:
    acceptable: set[str] = set()
    for move in verified_moves:
        acceptable.add(_normalize(move.uci()))
        acceptable.add(_normalize(board.san(move)))
    return acceptable


def _extract_move_tokens(text: str) -> list[str]:
    return [match.group(0) for match in _MOVE_TOKEN_PATTERN.finditer(text)]


def _normalize(token: str) -> str:
    token = token.rstrip("+#")
    token = token.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    return token
