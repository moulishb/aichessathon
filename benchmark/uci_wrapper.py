"""Expose a Chessathon get_move agent through the UCI protocol."""

import argparse
import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import TextIO

import chess


class UCIWrapper:
    def __init__(self, agent_dir: Path) -> None:
        self.agent_dir = agent_dir.resolve()
        self.board = chess.Board()
        self.agent = self._load_agent()

    def _load_agent(self) -> ModuleType:
        sys.path.insert(0, str(self.agent_dir))
        sys.modules.pop("agent", None)
        return importlib.import_module("agent")

    def new_game(self) -> None:
        self.board.reset()
        self.agent = self._load_agent()

    def set_position(self, tokens: list[str]) -> None:
        if not tokens:
            raise ValueError("position requires startpos or fen")
        index = 0
        if tokens[0] == "startpos":
            self.board.reset()
            index = 1
        elif tokens[0] == "fen":
            try:
                moves_index = tokens.index("moves")
            except ValueError:
                moves_index = len(tokens)
            self.board = chess.Board(" ".join(tokens[1:moves_index]))
            index = moves_index
        else:
            raise ValueError("unsupported position command")
        if index < len(tokens) and tokens[index] == "moves":
            for uci in tokens[index + 1 :]:
                move = chess.Move.from_uci(uci)
                if move not in self.board.legal_moves:
                    raise ValueError(f"illegal position move: {uci}")
                self.board.push(move)

    def go(self, tokens: list[str]) -> str:
        values: dict[str, int] = {}
        for index, token in enumerate(tokens[:-1]):
            if token in {"wtime", "btime", "winc", "binc", "movetime"}:
                values[token] = int(tokens[index + 1])
        side_key = "wtime" if self.board.turn == chess.WHITE else "btime"
        time_left = values.get("movetime", values.get(side_key, 1_000))
        move_text = self.agent.get_move(self.board.fen(), max(1, time_left))
        move = chess.Move.from_uci(move_text)
        if move not in self.board.legal_moves:
            raise ValueError(f"agent returned illegal move: {move_text}")
        return move.uci()


def send(protocol: TextIO, message: str) -> None:
    protocol.write(message + "\n")
    protocol.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-dir", type=Path, default=Path.cwd())
    args = parser.parse_args()

    protocol = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    wrapper = UCIWrapper(args.agent_dir)

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        command, *tokens = line.split()
        try:
            if command == "uci":
                send(protocol, "id name Chessathon Python Agent")
                send(protocol, "id author local")
                send(protocol, "uciok")
            elif command == "isready":
                send(protocol, "readyok")
            elif command == "ucinewgame":
                wrapper.new_game()
            elif command == "position":
                wrapper.set_position(tokens)
            elif command == "go":
                send(protocol, f"bestmove {wrapper.go(tokens)}")
            elif command == "stop":
                continue
            elif command == "quit":
                return
        except Exception as exc:
            print(f"UCI wrapper error for {line!r}: {exc}", file=sys.stderr)
            send(protocol, "bestmove 0000")


if __name__ == "__main__":
    main()
