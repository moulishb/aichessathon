"""The submission entrypoint. The platform imports this file and calls get_move."""

import time
from collections import Counter
from typing import NamedTuple

import chess

# Constants
INF = 200000
MATE_SCORE = 190000
MATE_THRESHOLD = 180000
MAX_QUIESCENCE_PLY = 8
QUIESCENCE_CHECK_PLIES = 2
MAX_EXTENSIONS = 2
MAX_TT_ENTRIES = 100_000
REPETITION_CONTEMPT = 60                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
LOSING_SCORE = -150                                                                                                                                                                                                                                                                                                                                                
EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2


class SearchTimeout(Exception):
    """Raised when search should stop due to time constraint."""

    pass

# ==============================================================================
# PIECE VALUES
# ==============================================================================
PAWN = 100
KNIGHT = 320
BISHOP = 330
ROOK = 500
QUEEN = 900

PIECE_VALUES: dict[int, int] = {
    chess.PAWN: PAWN,
    chess.KNIGHT: KNIGHT,
    chess.BISHOP: BISHOP,
    chess.ROOK: ROOK,
    chess.QUEEN: QUEEN,
    chess.KING: 0,  # King value not used in material evaluation
}

# ==============================================================================
# PIECE-SQUARE TABLES
# ==============================================================================
# Tables are from Black's perspective (a1=0, h8=63) and get flipped for Black.

PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]

KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]

BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

ROOK_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, 10, 10, 10, 10, 5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    0, 0, 0, 5, 5, 0, 0, 0,
]

QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]

KING_MIDDLEGAME = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20,
]

KING_ENDGAME = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]

PST: dict[int, list[int]] = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_MIDDLEGAME,
}

# ==============================================================================
# EVALUATION FUNCTION
# ==============================================================================

def evaluate(board: chess.Board, *, check_terminal: bool = True) -> int:
    """Evaluate the position from the perspective of the side to move.

    Positive = advantage for side to move
    Negative = disadvantage for side to move
    """
    # Terminal positions are uncommon here, but quiescence can reach them.
    if check_terminal:
        if board.is_checkmate():
            return -INF
        if board.is_stalemate() or board.is_insufficient_material():
            return 0

    middlegame_score = 0
    endgame_score = 0
    phase = 0
    piece_map = board.piece_map()

    phase_weights = {
        chess.KNIGHT: 1,
        chess.BISHOP: 1,
        chess.ROOK: 2,
        chess.QUEEN: 4,
    }

    # Material and both phase PST scores are accumulated in one occupied-square pass.
    for square, piece in piece_map.items():
        piece_value = PIECE_VALUES[piece.piece_type]
        phase += phase_weights.get(piece.piece_type, 0)
        # Flip for white's perspective (tables stored with rank 8 at index 0)
        pst_index = (
            chess.square_mirror(square)
            if piece.color == chess.WHITE
            else square
        )
        middlegame_value = piece_value + PST[piece.piece_type][pst_index]
        endgame_table = KING_ENDGAME if piece.piece_type == chess.KING else PST[piece.piece_type]
        endgame_value = piece_value + endgame_table[pst_index]

        if piece.color == chess.WHITE:
            middlegame_score += middlegame_value
            endgame_score += endgame_value
        else:
            middlegame_score -= middlegame_value
            endgame_score -= endgame_value

    phase = min(24, phase)

    # King safety fades continuously as material comes off. King activity is
    # represented by the endgame PST and proximity to enemy pawns.
    middlegame_score += evaluate_king_safety(board, chess.WHITE, False)
    middlegame_score -= evaluate_king_safety(board, chess.BLACK, False)
    endgame_score += evaluate_endgame_king(board, chess.WHITE)
    endgame_score -= evaluate_endgame_king(board, chess.BLACK)

    pawn_score = evaluate_pawn_structure(board, chess.WHITE)
    pawn_score -= evaluate_pawn_structure(board, chess.BLACK)
    middlegame_score += pawn_score
    endgame_score += pawn_score

    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        middlegame_score += 30
        endgame_score += 30
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        middlegame_score -= 30
        endgame_score -= 30

    score = (middlegame_score * phase + endgame_score * (24 - phase)) // 24

    # Perspective: return from side-to-move perspective
    if board.turn == chess.BLACK:
        score = -score

    return score


def evaluate_endgame_king(board: chess.Board, color: bool) -> int:
    """Reward an active king that approaches enemy pawns."""
    king_sq = board.king(color)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    if king_sq is None or not enemy_pawns:
        return 0
    closest = min(chess.square_distance(king_sq, pawn_sq) for pawn_sq in enemy_pawns)
    return max(0, 7 - closest) * 4


def is_endgame_position(board: chess.Board) -> bool:
    """Heuristic: endgame if total material is low."""
    total_material = 0
    for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        count = len(board.pieces(piece_type, chess.WHITE)) + len(
            board.pieces(piece_type, chess.BLACK)
        )
        total_material += count * PIECE_VALUES[piece_type]
    return total_material < 1500


def evaluate_king_safety(
    board: chess.Board, color: bool, is_endgame: bool | None = None
) -> int:
    """Evaluate king safety for the given color."""
    score = 0

    king_sq = board.king(color)
    if king_sq is None:
        return 0

    # Reward an actually castled king and the pawns shielding it. Castling
    # rights alone are only potential and disappear when castling succeeds.
    home_rank = 0 if color == chess.WHITE else 7
    shield_rank = 1 if color == chess.WHITE else 6
    king_file = chess.square_file(king_sq)
    if chess.square_rank(king_sq) == home_rank and king_file in (2, 6):
        score += 30
        for file_offset in (-1, 0, 1):
            shield_file = king_file + file_offset
            if 0 <= shield_file < 8:
                shield = board.piece_at(chess.square(shield_file, shield_rank))
                if shield == chess.Piece(chess.PAWN, color):
                    score += 8

    # Penalize enemy control around the king.
    king_zone = chess.SquareSet(chess.BB_KING_ATTACKS[king_sq] | chess.BB_SQUARES[king_sq])
    score -= 5 * sum(board.is_attacked_by(not color, sq) for sq in king_zone)

    # King in centre (bad in middlegame, good in endgame)
    if is_endgame is None:
        is_endgame = is_endgame_position(board)
    if not is_endgame:
        king_rank = chess.square_rank(king_sq)
        centre_distance = abs(king_file - 3.5) + abs(king_rank - 3.5)
        if centre_distance < 3:
            score -= 50

    return score


def evaluate_pawn_structure(board: chess.Board, color: bool) -> int:
    """Evaluate pawn structure for the given color."""
    score = 0
    pawns = list(board.pieces(chess.PAWN, color))
    enemy_pawns = list(board.pieces(chess.PAWN, not color))
    file_counts = [0] * 8
    for sq in pawns:
        file_counts[chess.square_file(sq)] += 1

    for sq in pawns:
        # Passed pawns
        rank = chess.square_rank(sq)
        file = chess.square_file(sq)
        is_passed = not any(
            abs(chess.square_file(enemy_sq) - file) <= 1
            and (
                chess.square_rank(enemy_sq) > rank
                if color == chess.WHITE
                else chess.square_rank(enemy_sq) < rank
            )
            for enemy_sq in enemy_pawns
        )
        if is_passed:
            relative_rank = rank if color == chess.WHITE else 7 - rank
            passed_bonus = (0, 0, 10, 20, 35, 60, 210, 0)[relative_rank]

            # Protected and connected passers support one another.
            if board.attackers(color, sq) & board.pieces(chess.PAWN, color):
                passed_bonus += 25
            if any(
                abs(chess.square_file(other) - file) == 1
                and abs(chess.square_rank(other) - rank) <= 1
                for other in pawns
            ):
                passed_bonus += 20

            forward_rank = rank + (1 if color == chess.WHITE else -1)
            if 0 <= forward_rank < 8:
                forward_sq = chess.square(file, forward_rank)
                if board.piece_at(forward_sq) is not None:
                    passed_bonus //= 2

            enemy_king = board.king(not color)
            if enemy_king is not None:
                passed_bonus += max(0, 5 - chess.square_distance(enemy_king, sq)) * 5

            for rook_sq in board.pieces(chess.ROOK, color):
                if chess.square_file(rook_sq) == file and (
                    chess.square_rank(rook_sq) < rank
                    if color == chess.WHITE
                    else chess.square_rank(rook_sq) > rank
                ):
                    passed_bonus += 25
                    break
            for rook_sq in board.pieces(chess.ROOK, not color):
                if chess.square_file(rook_sq) == file and (
                    chess.square_rank(rook_sq) < rank
                    if color == chess.WHITE
                    else chess.square_rank(rook_sq) > rank
                ):
                    passed_bonus -= 25
                    break

            score += passed_bonus

        # Doubled pawns
        if file_counts[file] > 1:
            score -= 20

        # Isolated pawns
        left_empty = file == 0 or file_counts[file - 1] == 0
        right_empty = file == 7 or file_counts[file + 1] == 0
        if left_empty and right_empty:
            score -= 20

    return score


def is_passed_pawn(board: chess.Board, sq: int, color: bool) -> bool:
    """Check if a pawn is passed."""
    rank = chess.square_rank(sq)
    file = chess.square_file(sq)

    opponent_color = not color
    check_ranges = (
        range(rank + 1, 8) if color == chess.WHITE else range(rank - 1, -1, -1)
    )

    for r in check_ranges:
        for f in [file - 1, file, file + 1]:
            if 0 <= f <= 7:
                check_sq = chess.square(f, r)
                piece = board.piece_at(check_sq)
                if (
                    piece
                    and piece.piece_type == chess.PAWN
                    and piece.color == opponent_color
                ):
                    return False
    return True


def is_isolated_pawn(board: chess.Board, sq: int, color: bool) -> bool:
    """Check if a pawn is isolated."""
    file = chess.square_file(sq)
    pawns = board.pieces(chess.PAWN, color)

    for adj_file in [file - 1, file + 1]:
        if 0 <= adj_file <= 7:
            for rank in range(8):
                check_sq = chess.square(adj_file, rank)
                if check_sq in pawns:
                    return False
    return True


# ==============================================================================
# MOVE ORDERING
# ==============================================================================

def order_moves(
    board: chess.Board,
    moves: list[chess.Move],
    preferred_move: chess.Move | None = None,
    *,
    ply: int = 0,
    score_checks: bool = True,
) -> list[chess.Move]:
    """Order moves cheaply, putting a known principal-variation move first."""

    def move_score(move: chess.Move) -> int:
        if move == preferred_move:
            return 1_000_000

        if board.is_capture(move):
            attacker = board.piece_at(move.from_square)
            assert attacker is not None

            if board.is_en_passant(move):
                victim_value = PAWN
            else:
                victim = board.piece_at(move.to_square)
                victim_value = (
                    PIECE_VALUES[victim.piece_type] if victim else 0
                )

            attacker_value = PIECE_VALUES[attacker.piece_type]
            # MVV-LVA puts high-value victims captured by low-value attackers first.
            return 100_000 + victim_value * 16 - attacker_value

        if move.promotion:
            return 90_000 + PIECE_VALUES[move.promotion]

        killers = search_state.killer_moves.get(ply, [])
        if move in killers:
            return 80_000 - killers.index(move) * 1_000

        if score_checks and board.gives_check(move):
            return 50_000

        return search_state.history.get(
            (board.turn, move.from_square, move.to_square), 0
        )

    return sorted(moves, key=move_score, reverse=True)


# ==============================================================================
# NEGAMAX WITH ALPHA-BETA PRUNING
# ==============================================================================

class TTEntry(NamedTuple):
    depth: int
    score: int
    flag: int
    best_move: chess.Move | None
    generation: int


class SearchState:
    def __init__(self) -> None:
        self.nodes_searched = 0
        self.start_time = 0.0
        self.time_budget_ms = 0.0
        self.generation = 0
        self.transposition_table: dict[tuple[object, int], TTEntry] = {}
        self.evaluation_cache: dict[object, int] = {}
        self.killer_moves: dict[int, list[chess.Move]] = {}
        self.history: dict[tuple[bool, int, int], int] = {}

    def should_stop(self) -> bool:
        """Check if we should stop searching."""
        if self.time_budget_ms <= 0:
            return False
        elapsed = (time.monotonic() - self.start_time) * 1000
        return elapsed >= self.time_budget_ms

    def reset_for_search(self) -> None:
        """Reset search state for a new search."""
        self.nodes_searched = 0

    def check_timeout(self) -> None:
        """Interrupt periodically without paying for a clock read at every node."""
        if (self.nodes_searched & 1023) == 0 and self.should_stop():
            raise SearchTimeout

    def add_killer(self, ply: int, move: chess.Move) -> None:
        """Remember up to two quiet beta-cutoff moves at each ply."""
        killers = self.killer_moves.setdefault(ply, [])
        if move in killers:
            killers.remove(move)
        killers.insert(0, move)
        del killers[2:]

    def prepare_new_search(self) -> None:
        """Age persistent search data and keep it within the memory budget."""
        self.generation += 1
        self.evaluation_cache.clear()
        if len(self.transposition_table) >= MAX_TT_ENTRIES:
            oldest_allowed = self.generation - 2
            self.transposition_table = {
                key: entry
                for key, entry in self.transposition_table.items()
                if entry.generation >= oldest_allowed
            }
            if len(self.transposition_table) >= MAX_TT_ENTRIES:
                self.transposition_table.clear()
        if self.history and max(self.history.values()) > 1_000_000:
            self.history = {key: value // 2 for key, value in self.history.items()}


search_state = SearchState()
position_counts: Counter[object] = Counter()


def position_key(board: chess.Board) -> tuple[object, int]:
    """Return a compact TT key, including the fifty-move state."""
    return (board._transposition_key(), board.halfmove_clock)


def repetition_key(board: chess.Board) -> object:
    """Return the FIDE position identity, excluding move counters."""
    return board._transposition_key()


def repetition_score(score: int, prior_occurrences: int) -> int:
    """Value voluntarily completing a third occurrence at the root."""
    if prior_occurrences < 2:
        return score
    if score < LOSING_SCORE:
        return 0
    return min(score, -REPETITION_CONTEMPT)


def static_evaluate(board: chess.Board) -> int:
    """Reuse static scores reached through transpositions in one search."""
    key = repetition_key(board)
    cached = search_state.evaluation_cache.get(key)
    if cached is None:
        cached = evaluate(board, check_terminal=False)
        search_state.evaluation_cache[key] = cached
    return cached


def score_to_tt(score: int, ply: int) -> int:
    """Normalize mate scores so persistent TT entries are root-independent."""
    if score > MATE_THRESHOLD:
        return score + ply
    if score < -MATE_THRESHOLD:
        return score - ply
    return score


def score_from_tt(score: int, ply: int) -> int:
    """Convert a normalized TT mate score to the current root distance."""
    if score > MATE_THRESHOLD:
        return score - ply
    if score < -MATE_THRESHOLD:
        return score + ply
    return score


def quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    q_ply: int = 0,
    search_ply: int = 0,
) -> int:
    """Search forcing moves until the position is tactically quiet."""
    search_state.check_timeout()
    search_state.nodes_searched += 1

    in_check = board.is_check()
    if q_ply >= MAX_QUIESCENCE_PLY:
        return static_evaluate(board)

    moves = list(board.legal_moves)
    if not moves:
        return -MATE_SCORE + search_ply if in_check else 0
    if board.is_insufficient_material():
        return 0

    if not in_check:
        stand_pat = static_evaluate(board)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

    if not in_check:
        moves = [
            move
            for move in moves
            if board.is_capture(move)
            or move.promotion
            or (q_ply < QUIESCENCE_CHECK_PLIES and board.gives_check(move))
        ]

    for move in order_moves(board, moves, ply=search_ply, score_checks=False):
        board.push(move)
        try:
            score = -quiescence(
                board,
                -beta,
                -alpha,
                q_ply + 1,
                search_ply + 1,
            )
        finally:
            board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    ply: int = 0,
    extensions_left: int = MAX_EXTENSIONS,
    recapture_square: int | None = None,
) -> int:
    """Negamax search with alpha-beta pruning.

    Returns the score from the perspective of the side to move.
    Positive = advantage; Negative = disadvantage.
    """
    search_state.check_timeout()
    search_state.nodes_searched += 1

    in_check = board.is_check()
    if in_check and extensions_left > 0:
        depth += 1
        extensions_left -= 1
    if depth == 0:
        return quiescence(board, alpha, beta, search_ply=ply)

    key = position_key(board)
    alpha_original = alpha
    entry = search_state.transposition_table.get(key)
    preferred_move: chess.Move | None = None
    if entry is not None:
        preferred_move = entry.best_move
        if entry.depth >= depth:
            if entry.flag == EXACT:
                return score_from_tt(entry.score, ply)
            tt_score = score_from_tt(entry.score, ply)
            if entry.flag == LOWERBOUND:
                alpha = max(alpha, tt_score)
            else:
                beta = min(beta, tt_score)
            if alpha >= beta:
                return tt_score

    best = -INF
    best_move: chess.Move | None = None
    moves = order_moves(board, list(board.legal_moves), preferred_move, ply=ply)
    if not moves:
        return -MATE_SCORE + ply if in_check else 0
    if board.is_insufficient_material():
        return 0

    for move in moves:
        is_capture = board.is_capture(move)
        child_depth = depth - 1
        child_extensions = extensions_left
        if (
            is_capture
            and move.to_square == recapture_square
            and child_extensions > 0
        ):
            child_depth += 1
            child_extensions -= 1
        board.push(move)
        try:
            score = -negamax(
                board,
                child_depth,
                -beta,
                -alpha,
                ply + 1,
                child_extensions,
                move.to_square if is_capture else None,
            )
        finally:
            # A timeout can be raised at any recursive depth. Always restore the
            # board while the exception unwinds so the previous completed
            # iterative-deepening result remains usable.
            board.pop()

        if score > best:
            best = score
            best_move = move

        if score > alpha:
            alpha = score

        if alpha >= beta:
            if not is_capture and move.promotion is None:
                search_state.add_killer(ply, move)
                history_key = (board.turn, move.from_square, move.to_square)
                search_state.history[history_key] = (
                    search_state.history.get(history_key, 0) + depth * depth
                )
            break

    flag = EXACT
    if best <= alpha_original:
        flag = UPPERBOUND
    elif best >= beta:
        flag = LOWERBOUND
    old_entry = search_state.transposition_table.get(key)
    if old_entry is None or depth >= old_entry.depth:
        search_state.transposition_table[key] = TTEntry(
            depth,
            score_to_tt(best, ply),
            flag,
            best_move,
            search_state.generation,
        )

    return best


def is_critical_position(board: chess.Board, moves: list[chess.Move]) -> bool:
    """Detect forcing positions that should be allowed to reach the hard limit."""
    if board.is_check():
        return True
    if sum(board.is_capture(move) for move in moves) >= 3:
        return True
    king_sq = board.king(board.turn)
    if king_sq is None:
        return False
    king_zone = chess.SquareSet(
        chess.BB_KING_ATTACKS[king_sq] | chess.BB_SQUARES[king_sq]
    )
    return sum(board.is_attacked_by(not board.turn, sq) for sq in king_zone) >= 3


def find_best_move(
    board: chess.Board,
    max_depth: int,
    soft_limit_ms: float,
    hard_limit_ms: float,
) -> chess.Move | None:
    """Find the best move using iterative deepening.

    Returns the best move found, or None if search was interrupted.
    """
    search_state.start_time = time.monotonic()
    search_state.time_budget_ms = hard_limit_ms
    search_state.prepare_new_search()
    moves = order_moves(board, list(board.legal_moves))
    best_move: chess.Move | None = moves[0] if moves else None
    base_critical = is_critical_position(board, moves)
    endgame_with_few_moves = is_endgame_position(board) and len(moves) <= 12
    previous_depth_move: chess.Move | None = None
    previous_depth_score: int | None = None
    stable_depths = 0

    for depth in range(1, max_depth + 1):
        try:
            search_state.reset_for_search()
            root_entry = search_state.transposition_table.get(position_key(board))
            preferred_move = root_entry.best_move if root_entry is not None else best_move
            moves = order_moves(board, list(board.legal_moves), preferred_move)

            best_depth_move: chess.Move | None = None
            best_depth_score = -INF
            alpha = -INF

            for move in moves:
                if search_state.should_stop():
                    raise SearchTimeout

                board.push(move)
                try:
                    score = -negamax(
                        board,
                        depth - 1,
                        -INF,
                        -alpha,
                        ply=1,
                    )
                    repeats_for_third_time = position_counts[repetition_key(board)] >= 2
                finally:
                    board.pop()

                if repeats_for_third_time:
                    # A draw rescues a clearly lost position. Otherwise apply
                    # contempt so an equal or winning engine keeps playing.
                    score = repetition_score(score, 2)

                if score > best_depth_score:
                    best_depth_score = score
                    best_depth_move = move
                if score > alpha:
                    alpha = score

            # Reaching here means every root move completed successfully.
            if best_depth_move is not None:
                best_move = best_depth_move
                score_change = (
                    abs(best_depth_score - previous_depth_score)
                    if previous_depth_score is not None
                    else INF
                )
                if best_depth_move == previous_depth_move and score_change < 50:
                    stable_depths += 1
                else:
                    stable_depths = 0

                print(
                    f"depth={depth}, nodes={search_state.nodes_searched}, "
                    f"best={best_depth_move}, score={best_depth_score}"
                )

                unstable = score_change >= 100 or best_depth_move != previous_depth_move
                sufficiently_stable = stable_depths >= 1 and depth >= 4
                if base_critical or endgame_with_few_moves or unstable:
                    search_state.time_budget_ms = hard_limit_ms
                elif sufficiently_stable:
                    search_state.time_budget_ms = soft_limit_ms

                elapsed_ms = (time.monotonic() - search_state.start_time) * 1000
                if sufficiently_stable and elapsed_ms >= soft_limit_ms:
                    break

                previous_depth_move = best_depth_move
                previous_depth_score = best_depth_score

        except SearchTimeout:
            # Timeout at this depth; use result from previous depth
            break

    return best_move


# ==============================================================================
# TIME MANAGEMENT
# ==============================================================================

def calculate_time_budget(time_left_ms: int) -> tuple[int, int, int]:
    """Return maximum depth plus adaptive soft and hard limits."""
    if time_left_ms > 100_000:
        max_depth, soft_limit, hard_limit = 12, 1800, 3500
    elif time_left_ms > 70_000:
        max_depth, soft_limit, hard_limit = 12, 1500, 3000
    elif time_left_ms > 40_000:
        max_depth, soft_limit, hard_limit = 11, 1000, 2200
    elif time_left_ms > 20_000:
        max_depth, soft_limit, hard_limit = 10, 600, 1400
    else:
        max_depth = 9
        soft_limit = max(50, min(200, time_left_ms // 20))
        hard_limit = max(100, min(600, time_left_ms // 8))

    return max_depth, soft_limit, hard_limit


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

def get_move(fen: str, time_left_ms: int) -> str:
    """Return a legal move in UCI notation.

    fen           the position to move in; your colour is the side to move
    time_left_ms  your clock before this move, in milliseconds
    returns       "e2e4", or "e7e8q" for a promotion

    The process stays alive between your moves, so state you keep on a module or in a
    closure survives to the next call. It does not survive to the next game.

    print() is safe. Your stdout is redirected away from the protocol stream, discarded
    during rated games and shown back to you in the validation log.
    """
    board = chess.Board(fen)
    position_counts[repetition_key(board)] += 1

    # Handle trivial cases
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 0:
        # Should not happen, but handle gracefully
        raise RuntimeError("No legal moves available")
    if len(legal_moves) == 1:
        only_move = legal_moves[0]
        board.push(only_move)
        position_counts[repetition_key(board)] += 1
        return only_move.uci()

    # Time management
    max_depth, soft_limit_ms, hard_limit_ms = calculate_time_budget(time_left_ms)

    # Search for best move
    best_move = find_best_move(board, max_depth, soft_limit_ms, hard_limit_ms)

    if best_move is None:
        best_move = order_moves(board, legal_moves)[0]

    board.push(best_move)
    position_counts[repetition_key(board)] += 1
    return best_move.uci()
