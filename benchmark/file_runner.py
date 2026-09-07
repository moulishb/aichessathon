"""Harness protocol runner for an agent stored under an arbitrary filename."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType


def load_agent(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("benchmark_candidate_agent", path.resolve())
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load agent from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    protocol = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    agent = load_agent(Path(sys.argv[1]))
    protocol.write(json.dumps({"ready": True}) + "\n")
    protocol.flush()
    for line in sys.stdin:
        request = json.loads(line)
        move = agent.get_move(request["fen"], request["time_left_ms"])
        protocol.write(json.dumps({"move": move}) + "\n")
        protocol.flush()


if __name__ == "__main__":
    main()
