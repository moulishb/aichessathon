"""Run stored FEN regressions against current and optional previous agents."""

import argparse
import importlib.util
import json
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import chess

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CaseResult:
    category: str
    name: str
    move: str
    elapsed_ms: float
    passed: bool
    previous_move: str | None


def load_agent(path: Path, module_name: str) -> ModuleType:
    file = path if path.is_file() else path / "agent.py"
    spec = importlib.util.spec_from_file_location(module_name, file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_move(module: ModuleType, fen: str, time_left_ms: int) -> tuple[str, float]:
    started = time.monotonic()
    move = module.get_move(fen, time_left_ms)
    elapsed = (time.monotonic() - started) * 1000
    board = chess.Board(fen)
    parsed = chess.Move.from_uci(move)
    if parsed not in board.legal_moves:
        raise RuntimeError(f"agent returned illegal move {move}")
    return move, elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", type=Path, default=ROOT / "agent.py")
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--time-left-ms", type=int, default=120_000)
    args = parser.parse_args()
    current = load_agent(args.agent, "benchmark_current_agent")
    previous = load_agent(args.previous, "benchmark_previous_agent") if args.previous else None
    results: list[CaseResult] = []
    for path in sorted((ROOT / "benchmark" / "regression").glob("*.json")):
        cases = json.loads(path.read_text(encoding="utf-8"))
        for case in cases:
            move, elapsed = run_move(current, case["fen"], args.time_left_ms)
            old_move = run_move(previous, case["fen"], args.time_left_ms)[0] if previous else None
            bad_moves = set(case.get("bad_moves", []))
            good_moves = set(case.get("good_moves", []))
            passed = move not in bad_moves and (not good_moves or move in good_moves)
            results.append(
                CaseResult(
                    case.get("category", path.stem), case["name"], move, elapsed, passed, old_move
                )
            )
    print("REGRESSION SUITE")
    print("=" * 72)
    categories = sorted({result.category for result in results})
    for category in categories:
        selected = [result for result in results if result.category == category]
        print(f"{category}: {sum(result.passed for result in selected)}/{len(selected)} passed")
        for result in selected:
            status = "PASS" if result.passed else "FAIL"
            previous_text = f", previous={result.previous_move}" if result.previous_move else ""
            print(
                f"  {status} {result.name}: {result.move} "
                f"({result.elapsed_ms:.0f} ms{previous_text})"
            )
    print(f"\nOverall: {sum(result.passed for result in results)}/{len(results)} passed")
    print(f"Known catastrophic moves repeated: {sum(not result.passed for result in results)}")


if __name__ == "__main__":
    main()
