from __future__ import annotations

import chess

PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

_ASCENDING_VALUE_ORDER: tuple[chess.PieceType, ...] = (
    chess.PAWN,
    chess.KNIGHT,
    chess.BISHOP,
    chess.ROOK,
    chess.QUEEN,
    chess.KING,
)


def _least_valuable_attacker(
    board: chess.Board, color: chess.Color, square: chess.Square, occupied: chess.Bitboard
) -> tuple[chess.Square, chess.PieceType] | None:
    # board._attackers_mask ANDs its result against the board's real per-color
    # occupancy, not the `occupied` we pass in for ray-blocking, so a piece
    # already consumed by an earlier ply and cleared from `occupied` would
    # otherwise be re-detected as available. The extra "& occupied" fixes that.
    attackers = board._attackers_mask(color, square, occupied) & occupied
    if not attackers:
        return None
    for piece_type in _ASCENDING_VALUE_ORDER:
        candidates = attackers & board.pieces_mask(piece_type, color)
        if candidates:
            return chess.lsb(candidates), piece_type
    return None


def static_exchange_eval(board: chess.Board, move: chess.Move) -> int:
    """Centipawn value of the capture sequence starting with `move`, from the mover's side.

    Standard SEE limitation, shared with Stockfish's own implementation: pins and
    king-capture legality aren't modeled, so a pinned defender still counts as able
    to recapture.
    """
    mover_color = board.turn
    moving_piece = board.piece_at(move.from_square)
    if moving_piece is None:
        raise ValueError(f"No piece on {chess.square_name(move.from_square)} to move")

    occupied = board.occupied

    if board.is_en_passant(move):
        captured_value = PIECE_VALUES[chess.PAWN]
        captured_square = move.to_square + (-8 if mover_color == chess.WHITE else 8)
        occupied &= ~chess.BB_SQUARES[captured_square]
    else:
        captured_piece = board.piece_at(move.to_square)
        captured_value = PIECE_VALUES[captured_piece.piece_type] if captured_piece else 0

    occupied &= ~chess.BB_SQUARES[move.from_square]
    occupied &= ~chess.BB_SQUARES[move.to_square]

    gains = [0] * 32
    gains[0] = captured_value

    current_piece_type: chess.PieceType = (
        move.promotion if move.promotion else moving_piece.piece_type
    )
    if move.promotion:
        gains[0] += PIECE_VALUES[move.promotion] - PIECE_VALUES[chess.PAWN]
    current_value = PIECE_VALUES[current_piece_type]

    side = not mover_color
    depth = 0

    while True:
        found = _least_valuable_attacker(board, side, move.to_square, occupied)
        if found is None:
            break
        attacker_square, attacker_piece_type = found

        depth += 1
        gains[depth] = current_value - gains[depth - 1]
        if max(-gains[depth - 1], gains[depth]) < 0:
            break

        occupied &= ~chess.BB_SQUARES[attacker_square]
        current_value = PIECE_VALUES[attacker_piece_type]
        side = not side

    while depth > 0:
        gains[depth - 1] = -max(-gains[depth - 1], gains[depth])
        depth -= 1

    return gains[0]
