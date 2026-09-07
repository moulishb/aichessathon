"""The submission entrypoint. The platform imports this file and calls get_move."""

import time

import chess

# Constants
INF = 200000


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

def evaluate(board: chess.Board) -> int:
    """Evaluate the position from the perspective of the side to move.

    Positive = advantage for side to move
    Negative = disadvantage for side to move
    """
    # Checkmate is a terminal state, handle separately
    if board.is_checkmate():
        return -200000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0

    # Material
    for piece_type in chess.PIECE_TYPES:
        white_pieces = board.pieces(piece_type, chess.WHITE)
        black_pieces = board.pieces(piece_type, chess.BLACK)
        piece_value = PIECE_VALUES[piece_type]
        score += len(white_pieces) * piece_value
        score -= len(black_pieces) * piece_value

    # Piece-square tables
    is_eg = is_endgame_position(board)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue

        pst = PST[piece.piece_type]
        # Flip for white's perspective (tables stored with rank 8 at index 0)
        pst_index = (
            chess.square_mirror(square)
            if piece.color == chess.WHITE
            else square
        )
        value = pst[pst_index]

        # In endgame, use king endgame table
        if piece.piece_type == chess.KING and is_eg:
            eg_index = (
                chess.square_mirror(square)
                if piece.color == chess.WHITE
                else square
            )
            value = KING_ENDGAME[eg_index]

        if piece.color == chess.WHITE:
            score += value
        else:
            score -= value

    # King safety
    score += evaluate_king_safety(board, chess.WHITE)
    score -= evaluate_king_safety(board, chess.BLACK)

    # Pawn structure
    score += evaluate_pawn_structure(board, chess.WHITE)
    score -= evaluate_pawn_structure(board, chess.BLACK)

    # Perspective: return from side-to-move perspective
    if board.turn == chess.BLACK:
        score = -score

    return score


def is_endgame_position(board: chess.Board) -> bool:
    """Heuristic: endgame if total material is low."""
    total_material = 0
    for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        count = len(board.pieces(piece_type, chess.WHITE)) + len(
            board.pieces(piece_type, chess.BLACK)
        )
        total_material += count * PIECE_VALUES[piece_type]
    return total_material < 1500


def evaluate_king_safety(board: chess.Board, color: bool) -> int:
    """Evaluate king safety for the given color."""
    score = 0

    king_sq = board.king(color)
    if king_sq is None:
        return 0

    # Castling rights
    if color == chess.WHITE:
        if board.has_kingside_castling_rights(chess.WHITE):
            score += 30
        if board.has_queenside_castling_rights(chess.WHITE):
            score += 30
    else:
        if board.has_kingside_castling_rights(chess.BLACK):
            score += 30
        if board.has_queenside_castling_rights(chess.BLACK):
            score += 30

    # King in centre (bad in middlegame, good in endgame)
    if not is_endgame_position(board):
        king_file = chess.square_file(king_sq)
        king_rank = chess.square_rank(king_sq)
        centre_distance = abs(king_file - 3.5) + abs(king_rank - 3.5)
        if centre_distance < 3:
            score -= 50

    return score


def evaluate_pawn_structure(board: chess.Board, color: bool) -> int:
    """Evaluate pawn structure for the given color."""
    score = 0
    pawns = board.pieces(chess.PAWN, color)

    for sq in pawns:
        # Passed pawns
        if is_passed_pawn(board, sq, color):
            rank = chess.square_rank(sq)
            # Reward based on how close to promotion
            relative_rank = rank if color == chess.WHITE else 7 - rank
            advance_bonus = relative_rank * 15
            score += 20 + advance_bonus

        # Doubled pawns
        file = chess.square_file(sq)
        file_pawns = sum(1 for p in pawns if chess.square_file(p) == file)
        if file_pawns > 1:
            score -= 20

        # Isolated pawns
        if is_isolated_pawn(board, sq, color):
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
    board: chess.Board, moves: list[chess.Move]
) -> list[chess.Move]:
    """Order moves using MVV-LVA and other heuristics."""

    def move_score(move: chess.Move) -> tuple[int, int]:
        # Checkmate moves first
        board.push(move)
        is_checkmate = board.is_checkmate()
        board.pop()
        if is_checkmate:
            return (-4, 0)

        # Checks second
        board.push(move)
        is_check = board.is_check()
        board.pop()
        if is_check:
            return (-3, 0)

        # Captures: MVV/LVA (Most Valuable Victim / Least Valuable Attacker)
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
            return (-2, -victim_value + attacker_value // 32)

        # Promotions
        if move.promotion:
            return (-1, 0)

        # Quiet moves
        return (0, 0)

    return sorted(moves, key=move_score)


# ==============================================================================
# NEGAMAX WITH ALPHA-BETA PRUNING
# ==============================================================================

class SearchState:
    def __init__(self) -> None:
        self.nodes_searched = 0
        self.start_time = 0.0
        self.time_budget_ms = 0.0
        self.last_completed_move: chess.Move | None = None

    def should_stop(self) -> bool:
        """Check if we should stop searching."""
        if self.time_budget_ms <= 0:
            return False
        elapsed = (time.monotonic() - self.start_time) * 1000
        return elapsed > self.time_budget_ms * 0.9  # Stop at 90% of budget

    def reset_for_search(self) -> None:
        """Reset search state for a new search."""
        self.nodes_searched = 0


search_state = SearchState()


def negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
) -> int:
    """Negamax search with alpha-beta pruning.

    Returns the score from the perspective of the side to move.
    Positive = advantage; Negative = disadvantage.
    """
    # Check time periodically
    if (search_state.nodes_searched & 1023 == 0) and search_state.should_stop():
        raise SearchTimeout

    search_state.nodes_searched += 1

    # Terminal nodes
    if depth == 0 or board.is_game_over():
        return evaluate(board)

    best = -INF
    moves = order_moves(board, list(board.legal_moves))

    for move in moves:
        board.push(move)
        try:
            score = -negamax(board, depth - 1, -beta, -alpha)
        finally:
            # A timeout can be raised at any recursive depth. Always restore the
            # board while the exception unwinds so the previous completed
            # iterative-deepening result remains usable.
            board.pop()

        if score > best:
            best = score

        if score > alpha:
            alpha = score

        if alpha >= beta:
            break

    return best


def find_best_move(
    board: chess.Board, max_depth: int, time_budget_ms: float
) -> chess.Move | None:
    """Find the best move using iterative deepening.

    Returns the best move found, or None if search was interrupted.
    """
    search_state.start_time = time.monotonic()
    search_state.time_budget_ms = time_budget_ms
    best_move: chess.Move | None = None

    for depth in range(1, max_depth + 1):
        try:
            search_state.reset_for_search()
            moves = order_moves(board, list(board.legal_moves))

            best_depth_move: chess.Move | None = None
            best_depth_score = -INF

            for move in moves:
                if search_state.should_stop():
                    raise SearchTimeout

                board.push(move)
                try:
                    score = -negamax(board, depth - 1, -INF, INF)
                finally:
                    board.pop()

                if score > best_depth_score:
                    best_depth_score = score
                    best_depth_move = move

            # Reaching here means every root move completed successfully.
            if best_depth_move is not None:
                best_move = best_depth_move

        except SearchTimeout:
            # Timeout at this depth; use result from previous depth
            break

    return best_move


# ==============================================================================
# TIME MANAGEMENT
# ==============================================================================

def calculate_time_budget(time_left_ms: int) -> tuple[int, int]:
    """Calculate search depth and time budget based on remaining time."""
    if time_left_ms > 90000:
        # Opening with lots of time
        max_depth = 5
        search_time_ms = 1500
    elif time_left_ms > 60000:
        max_depth = 5
        search_time_ms = 1000
    elif time_left_ms > 30000:
        max_depth = 4
        search_time_ms = 700
    elif time_left_ms > 10000:
        max_depth = 3
        search_time_ms = 400
    else:
        # Low on time
        max_depth = 2
        search_time_ms = 100

    return max_depth, search_time_ms


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

    # Handle trivial cases
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 0:
        # Should not happen, but handle gracefully
        raise RuntimeError("No legal moves available")
    if len(legal_moves) == 1:
        return legal_moves[0].uci()

    # Time management
    max_depth, search_time_ms = calculate_time_budget(time_left_ms)

    # Search for best move
    best_move = find_best_move(board, max_depth, search_time_ms)

    if best_move is None:
        # Fallback to first legal move
        best_move = legal_moves[0]

    return best_move.uci()