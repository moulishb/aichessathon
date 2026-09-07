"""Run reproducible local matches and write reports, CSV, JSON, and PGNs."""

import argparse
import csv
import io
import json
import math
import shutil
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import chess  # noqa: E402
import chess.engine  # noqa: E402
import chess.pgn  # noqa: E402

from benchmark.openings import OPENINGS  # noqa: E402
from harness.referee import Outcome, play_match  # noqa: E402
from harness.sandbox import Agent, AgentFailure, local  # noqa: E402

RESULTS_ROOT = ROOT / "benchmark" / "results"
FILE_RUNNER = ROOT / "benchmark" / "file_runner.py"
TC = {"fast": (2_000, 500), "tournament": (120_000, 500)}
BASELINES = {
    "random": ROOT / "baselines" / "random",
    "greedy": ROOT / "baselines" / "greedy",
    "minimax": ROOT / "baselines" / "minimax",
    "numba": ROOT / "baselines" / "numba",
}
SUITES = {
    "quick": {"random": 10, "greedy": 10, "minimax": 10, "previous": 20},
    "full": {
        "random": 20,
        "greedy": 20,
        "minimax": 30,
        "numba": 30,
        "previous": 100,
        "stockfish-1320": 30,
        "stockfish-1400": 30,
        "stockfish-1600": 30,
        "stockfish-1800": 30,
        "stockfish-2000": 30,
        "stockfish-2200": 30,
        "sunfish": 50,
    },
}
STOCKFISH_LEVELS = {f"stockfish-{elo}": elo for elo in (1320, 1400, 1600, 1800, 2000, 2200)}


class MatchAgent(Protocol):
    def start(self, init_budget_s: float) -> None: ...
    def move(self, fen: str, time_left_ms: int) -> str: ...
    def stop(self) -> None: ...


class UCIEngineAgent:
    """Adapter from a local UCI executable to the Chessathon harness interface."""

    def __init__(
        self,
        command: list[str],
        options: dict[str, str | int | bool | None] | None = None,
    ) -> None:
        self.command = command
        self.options = options or {}
        self.engine: chess.engine.SimpleEngine | None = None

    def start(self, init_budget_s: float) -> None:
        del init_budget_s
        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.command, timeout=10.0)
            if self.options:
                self.engine.configure(self.options)
        except (OSError, TimeoutError, chess.engine.EngineError):
            raise AgentFailure("init") from None

    def move(self, fen: str, time_left_ms: int) -> str:
        if self.engine is None:
            raise RuntimeError("UCI engine moved before start")
        board = chess.Board(fen)
        try:
            result = self.engine.play(
                board,
                chess.engine.Limit(time=max(0.01, min(0.25, time_left_ms / 20_000))),
            )
        except (TimeoutError, chess.engine.EngineError):
            raise AgentFailure("crash") from None
        if result.move is None:
            raise RuntimeError("UCI engine returned no move")
        return result.move.uci()

    def stop(self) -> None:
        if self.engine is not None:
            try:
                self.engine.quit()
            except (TimeoutError, chess.engine.EngineError):
                self.engine.close()
            self.engine = None


@dataclass
class OpponentResult:
    opponent: str
    rating: int | None
    rating_note: str
    games: int
    wins: int
    draws: int
    losses: int
    white_score: float
    black_score: float
    average_plies: float
    estimated_elo_difference: float
    estimated_performance_rating: float | None

    @property
    def score(self) -> float:
        return (self.wins + self.draws / 2) / self.games


def elo_difference(score: float) -> float:
    clipped = min(0.999, max(0.001, score))
    return -400 * math.log10((1 / clipped) - 1)


def agent_directory(path: Path) -> Path:
    resolved = path.resolve()
    return resolved.parent if resolved.is_file() else resolved


def local_candidate(path: Path) -> Agent:
    """Load a normal agent directory or an arbitrary Python agent filename."""
    resolved = path.resolve()
    if resolved.is_dir():
        return local(resolved)
    if resolved.name == "agent.py":
        return local(resolved.parent)
    return Agent([sys.executable, str(FILE_RUNNER), str(resolved)])


def opponent_factory(
    name: str, previous: Path | None
) -> tuple[Callable[[], Agent], int | None, str]:
    if name in BASELINES:
        return (lambda path=BASELINES[name]: local(path)), None, "unknown"
    if name == "previous":
        if previous is None or not previous.exists():
            raise ValueError("previous agent unavailable; pass --previous PATH")
        return (lambda: local_candidate(previous)), None, "unknown"
    if name in STOCKFISH_LEVELS:
        executable = shutil.which("stockfish") or "/usr/games/stockfish"
        if not Path(executable).exists():
            raise ValueError("Stockfish is not installed")
        elo = STOCKFISH_LEVELS[name]
        return (
            lambda: cast(
                Agent,
                UCIEngineAgent(
                    [executable],
                    {"UCI_LimitStrength": True, "UCI_Elo": elo, "Threads": 1, "Hash": 16},
                ),
            ),
            elo,
            "Stockfish UCI_Elo setting; not Chessathon/online Elo",
        )
    if name == "sunfish":
        script = ROOT / "benchmark" / "external" / "sunfish" / "uci.py"
        if not script.exists():
            raise ValueError("Sunfish unavailable; see benchmark/README.md")
        return (
            lambda: cast(Agent, UCIEngineAgent([sys.executable, str(script)])),
            None,
            "unknown",
        )
    raise ValueError(f"unknown opponent: {name}")


def add_headers(pgn: str, opponent: str, opening: str, agent_white: bool) -> str:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise RuntimeError("harness produced invalid PGN")
    game.headers["Event"] = "Local Chessathon Benchmark"
    game.headers["Opening"] = opening
    game.headers["White"] = "current" if agent_white else opponent
    game.headers["Black"] = opponent if agent_white else "current"
    return str(game)


def run_opponent(
    name: str,
    games: int,
    current: Path,
    previous: Path | None,
    base_ms: int,
    increment_ms: int,
    pgn_path: Path,
) -> tuple[OpponentResult, list[dict[str, object]]]:
    if games < 1:
        raise ValueError("games must be positive")
    if games % 2:
        print("warning: odd game count gives current one extra White game")
    factory, rating, rating_note = opponent_factory(name, previous)
    wins = draws = losses = white_games = black_games = 0
    white_points = black_points = total_plies = 0.0
    rows: list[dict[str, object]] = []
    pgns: list[str] = []
    for index in range(games):
        opening_name, fen = OPENINGS[(index // 2) % len(OPENINGS)]
        agent_white = index % 2 == 0
        ours = local_candidate(current)
        theirs = factory()
        white, black = (ours, theirs) if agent_white else (theirs, ours)
        outcome: Outcome = play_match(white, black, base_ms, increment_ms, start_fen=fen)
        won = outcome.result == ("white" if agent_white else "black")
        lost = outcome.result == ("black" if agent_white else "white")
        points = 1.0 if won else 0.0 if lost else 0.5
        wins += int(won)
        losses += int(lost)
        draws += int(not won and not lost)
        if agent_white:
            white_games += 1
            white_points += points
        else:
            black_games += 1
            black_points += points
        game = chess.pgn.read_game(io.StringIO(outcome.pgn))
        plies = game.end().ply() if game is not None else 0
        total_plies += plies
        pgns.append(add_headers(outcome.pgn, name, opening_name, agent_white))
        rows.append(
            {
                "opponent": name,
                "game": index + 1,
                "colour": "white" if agent_white else "black",
                "opening": opening_name,
                "result": "win" if won else "loss" if lost else "draw",
                "termination": outcome.termination,
                "plies": plies,
            }
        )
        print(f"{name} {index + 1}/{games}: {rows[-1]['result']} by {outcome.termination}")
    pgn_path.write_text("\n\n".join(pgns) + "\n", encoding="utf-8")
    score = (wins + draws / 2) / games
    difference = elo_difference(score)
    result = OpponentResult(
        name,
        rating,
        rating_note,
        games,
        wins,
        draws,
        losses,
        white_points / white_games,
        black_points / black_games,
        total_plies / games,
        difference,
        rating + difference if rating is not None else None,
    )
    return result, rows


def write_reports(
    output: Path,
    results: list[OpponentResult],
    rows: list[dict[str, object]],
    config: dict[str, object],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(
        json.dumps([asdict(result) | {"score": result.score} for result in results], indent=2)
        + "\n",
        encoding="utf-8",
    )
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["opponent"])
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "=" * 72,
        "CHESSATHON ENGINE BENCHMARK",
        "=" * 72,
        "Opponent              Rating     W   D   L   Score   Elo diff   Perf",
        "-" * 72,
    ]
    for result in results:
        rating = str(result.rating) if result.rating is not None else "unknown"
        perf = (
            f"{result.estimated_performance_rating:.0f}"
            if result.estimated_performance_rating is not None
            else "-"
        )
        lines.append(
            f"{result.opponent:<21} {rating:>7} {result.wins:>3} "
            f"{result.draws:>3} {result.losses:>3} {result.score:>7.1%} "
            f"{result.estimated_elo_difference:>+10.0f} {perf:>7}"
        )
    lines.append("")
    for result in results:
        lines.append(
            f"{result.opponent}: white score {result.white_score:.1%}, "
            f"black score {result.black_score:.1%}, "
            f"average length {result.average_plies:.1f} plies"
        )
    lines.extend(
        [
            "Elo differences are estimates from this match result, clipped at 0.1/99.9%.",
            "Ratings are local engine settings, not Chessathon, Chess.com, or Lichess Elo.",
            "Average thinking time: unavailable from the current harness.",
        ]
    )
    summary = "\n".join(lines) + "\n"
    (output / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=SUITES, default="quick")
    parser.add_argument("--opponent", action="append")
    parser.add_argument("--games", type=int)
    parser.add_argument("--tc", choices=TC, default="fast")
    parser.add_argument("--base-ms", type=int)
    parser.add_argument("--increment-ms", type=int)
    parser.add_argument("--agent", type=Path, default=ROOT)
    parser.add_argument(
        "--previous", type=Path, default=ROOT / "benchmark" / "agents" / "v3" / "agent.py"
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_ms, increment_ms = TC[args.tc]
    base_ms = args.base_ms or base_ms
    increment_ms = args.increment_ms if args.increment_ms is not None else increment_ms
    requested = args.opponent or list(SUITES[args.suite])
    counts = {name: args.games or SUITES[args.suite].get(name, 10) for name in requested}
    output = args.output or RESULTS_ROOT / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    (output / "pgn").mkdir(parents=True, exist_ok=True)
    results: list[OpponentResult] = []
    rows: list[dict[str, object]] = []
    skipped: dict[str, str] = {}
    for name, count in counts.items():
        try:
            result, game_rows = run_opponent(
                name,
                count,
                args.agent,
                args.previous,
                base_ms,
                increment_ms,
                output / "pgn" / f"vs_{name}.pgn",
            )
        except ValueError as exc:
            skipped[name] = str(exc)
            print(f"skipping {name}: {exc}")
            continue
        results.append(result)
        rows.extend(game_rows)
    config = {
        "suite": args.suite,
        "agent": str(args.agent),
        "previous": str(args.previous),
        "base_ms": base_ms,
        "increment_ms": increment_ms,
        "opponents": counts,
        "skipped": skipped,
    }
    write_reports(output, results, rows, config)
    combined = "\n".join(
        (output / "pgn" / f"vs_{result.opponent}.pgn").read_text(encoding="utf-8")
        for result in results
    )
    (output / "games.pgn").write_text(combined, encoding="utf-8")
    print(f"results: {output}")


if __name__ == "__main__":
    main()
