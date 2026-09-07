"""Small deterministic opening set used symmetrically in benchmark pairs."""

import chess

OPENINGS: tuple[tuple[str, str], ...] = (
    ("startpos", chess.STARTING_FEN),
    ("Italian", "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 4 4"),
    ("QueensGambit", "rnbqkb1r/pp2pppp/2p2n2/3p4/2PP4/5N2/PP2PPPP/RNBQKB1R w KQkq - 2 4"),
    ("Sicilian", "r1bqkbnr/pp1ppppp/2n5/2p5/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 2 3"),
    ("French", "rnbqkbnr/pp3ppp/2p1p3/3pP3/3P4/2P5/PP3PPP/RNBQKBNR w KQkq - 0 4"),
    ("CaroKann", "rnbqkbnr/pp2pppp/2p5/3p4/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3"),
)
