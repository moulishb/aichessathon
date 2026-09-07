"""Convenience entry point for a balanced new-vs-old agent match."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, default=ROOT / "agent.py")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--tc", choices=("fast", "tournament"), default="fast")
    args = parser.parse_args()
    command = [
        sys.executable,
        str(ROOT / "benchmark" / "run_benchmark.py"),
        "--opponent",
        "previous",
        "--previous",
        str(args.old),
        "--agent",
        str(args.new),
        "--games",
        str(args.games),
        "--tc",
        args.tc,
    ]
    raise SystemExit(subprocess.run(command, check=False).returncode)


if __name__ == "__main__":
    main()
