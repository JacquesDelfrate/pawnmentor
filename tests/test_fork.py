from __future__ import annotations

import chess

from app.analysis.fork import Fork, find_forks

# Knight forks two undefended pawns (c6, g6). Pawns are deliberately chosen
# over higher-value pieces here: a queen or rook target initially seemed
# fine by hand but turned out to have a real escape I'd missed -- Qc6-c1+
# is a zwischenzug check that buys Black a tempo (White's knight can't
# capture anything while it must respond to check, so the one-ply-response
# check correctly refuses to call it a proven fork). Pawns have no
# check-giving range and can't reposition to defend a piece elsewhere, which
# rules out that whole category of escape by construction, and their
# limited moves (one step forward, no other options here) are small enough
# to enumerate by hand.
GENUINE_FORK_FEN = "k7/8/2p3p1/4N3/8/8/8/K7 w - - 0 1"


def test_genuine_fork_confirmed() -> None:
    board = chess.Board(GENUINE_FORK_FEN)
    assert find_forks(board, chess.WHITE) == [
        Fork(
            forker_square=chess.E5,
            forker_piece_type=chess.KNIGHT,
            color=chess.WHITE,
            forked_squares=(chess.C6, chess.G6),
            king_threatened=False,
        )
    ]


def test_refuted_when_forker_itself_is_capturable() -> None:
    # Same shape as the genuine fork, but a black pawn on f6 attacks e5:
    # Black can just take the knight, which refutes the fork regardless of
    # whether that trade is actually good for Black.
    board = chess.Board("k7/8/2p2pp1/4N3/8/8/8/K7 w - - 0 1")
    assert find_forks(board, chess.WHITE) == []


def test_not_a_fork_with_only_one_real_target() -> None:
    # Nxc6 (undefended queen) is profitable (SEE = +900). Nxd7 is a knight
    # captures knight trade where the only defender is the king: SEE = 0
    # (attacker and defender have equal value), not > 0, so it's not a real
    # threat. That leaves only one qualifying target -- below the
    # 2-target threshold, so this returns [] without even needing to check
    # Black's responses.
    board = chess.Board("4k3/3n4/2q5/4N3/8/8/8/K7 w - - 0 1")
    assert find_forks(board, chess.WHITE) == []


def test_refuted_when_opponent_saves_both_with_one_move() -> None:
    # Knight forks an undefended pawn (c6) and an undefended rook (g6), and
    # the knight itself isn't attacked by anything (unlike the previous
    # refutation test) -- this isolates the "opponent finds a non-obvious
    # save" mechanism specifically. Black's Rg6-d6 escapes the rook (d6
    # isn't among e5's knight-attack squares) *and* newly defends c6 along
    # the rank, dropping Nxc6's SEE from +100 to -220 (knight for pawn,
    # rook recaptures). After that single move nothing remains profitable,
    # so the fork must be refuted.
    board = chess.Board("k7/8/2p3r1/4N3/8/8/8/K7 w - - 0 1")
    assert find_forks(board, chess.WHITE) == []


def test_royal_fork_confirmed() -> None:
    # Classic Nc7 fork on Ke8/Ra8. The king must respond to check, knight
    # attacks can't be blocked, and none of the king's escape squares are
    # adjacent to a8, so the rook remains lost no matter what Black plays.
    board = chess.Board("r3k3/2N5/8/8/8/8/8/K7 w - - 0 1")
    assert find_forks(board, chess.WHITE) == [
        Fork(
            forker_square=chess.C7,
            forker_piece_type=chess.KNIGHT,
            color=chess.WHITE,
            forked_squares=(chess.A8,),
            king_threatened=True,
        )
    ]


def test_turn_independence() -> None:
    board_white_to_move = chess.Board(GENUINE_FORK_FEN)
    board_black_to_move = chess.Board(GENUINE_FORK_FEN.replace(" w ", " b "))
    result = find_forks(board_white_to_move, chess.WHITE)
    assert result != []
    assert result == find_forks(board_black_to_move, chess.WHITE)


# No engine-marked sanity test here, unlike static_exchange_eval and
# find_hanging_pieces. Both attempts at one kept surfacing near-equal
# evaluations (even at depth 18) on sparse, artificially-constructed
# positions like these -- Stockfish's NNUE doesn't track raw material
# cleanly once a position is this far outside the distribution of real
# games, so "does the engine agree" isn't a reliable signal here the way it
# was for the other two detectors. Correctness for this phase rests on the
# hand-derived test cases above instead, each with explicit game-theoretic
# reasoning for its expected outcome.
