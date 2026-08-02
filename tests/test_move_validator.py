from __future__ import annotations

import chess
import pytest

from app.guards.move_validator import MoveValidationError, validate_llm_output


def test_verified_move_written_as_san_passes() -> None:
    board = chess.Board()
    verified = [chess.Move.from_uci("e2e4")]
    validate_llm_output("Playing e4 grabs the center.", board, verified)


def test_verified_move_written_as_uci_passes() -> None:
    board = chess.Board()
    verified = [chess.Move.from_uci("e2e4")]
    validate_llm_output("Best is e2e4 here.", board, verified)


def test_unverified_but_legal_move_raises() -> None:
    board = chess.Board()
    verified = [chess.Move.from_uci("e2e4")]
    with pytest.raises(MoveValidationError) as exc_info:
        validate_llm_output("Playing e4 is good, but also consider Nf3.", board, verified)
    assert exc_info.value.offending_tokens == ["Nf3"]


def test_unverified_illegal_move_also_raises() -> None:
    # Queen can't reach h5 from the starting position in one move -- Qh5 is
    # not even a legal SAN token here. The validator never parses/checks
    # legality of extracted tokens, only membership, so this must fail via
    # the exact same path as a legal-but-unverified move.
    board = chess.Board()
    with pytest.raises(MoveValidationError) as exc_info:
        validate_llm_output("Qh5 wins immediately.", board, [])
    assert exc_info.value.offending_tokens == ["Qh5"]


def test_prose_with_no_move_tokens_passes() -> None:
    board = chess.Board()
    validate_llm_output(
        "Both sides should focus on king safety before opening the center.",
        board,
        [],
    )


def test_check_suffix_normalization() -> None:
    # e4 gives no check, so board.san won't include "+", but the text adds a
    # spurious one -- normalization must still recognize it as the same move.
    board = chess.Board()
    verified = [chess.Move.from_uci("e2e4")]
    validate_llm_output("e4+ opens the center.", board, verified)


def test_castling_zero_notation_normalization() -> None:
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    verified = [chess.Move.from_uci("e1g1")]
    validate_llm_output("0-0 secures the king.", board, verified)


def test_concatenated_uci_token_not_fragmented() -> None:
    board = chess.Board()
    with pytest.raises(MoveValidationError) as exc_info:
        validate_llm_output("e2e4", board, [])
    assert exc_info.value.offending_tokens == ["e2e4"]


def test_multiple_offending_tokens_all_reported() -> None:
    board = chess.Board()
    verified = [chess.Move.from_uci("e2e4")]
    with pytest.raises(MoveValidationError) as exc_info:
        validate_llm_output("You could try Nf3, or maybe e4 is fine, but not Qh5.", board, verified)
    assert exc_info.value.offending_tokens == ["Nf3", "Qh5"]
