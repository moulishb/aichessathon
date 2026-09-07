# Local engine benchmark

This directory is local test infrastructure. It is not part of the Chessathon submission.
The packaging command scans only root-level Python files and explicitly included weight paths.

## Setup

Run the repository setup as usual:

```bash
make setup
```

The Python fallback runner uses the existing `python-chess` dependency and Chessathon harness.
`cutechess-cli` is optional and is not required. On Ubuntu it can usually be installed with:

```bash
sudo apt install cutechess
```

Stockfish is detected from `PATH` or `/usr/games/stockfish`. Its `UCI_Elo` values are reported
as Stockfish configuration settings only; they are not Chessathon, Chess.com, or Lichess ratings.

## Commands

```bash
make benchmark-quick
make benchmark-full
make regression

python benchmark/run_benchmark.py --opponent greedy --games 20
python benchmark/run_benchmark.py --opponent stockfish-1600 --games 20
python benchmark/run_benchmark.py --opponent sunfish --games 20
python benchmark/run_benchmark.py --tc tournament --opponent minimax --games 2

python benchmark/compare_versions.py \
  --old benchmark/agents/v3/agent.py --new agent.py --games 100
```

Every game count must be even. Games are paired by opening with the current agent playing each
colour. Results are written below `benchmark/results/<timestamp>/` as `summary.txt`,
`summary.json`, `results.csv`, `games.pgn`, `config.json`, and per-opponent PGNs.

## Saving and comparing versions

Before replacing the current submission, create a directory such as
`benchmark/agents/v3/` and copy that version's `agent.py` into it. The benchmark discovers the
version through `--previous`; no benchmark code is copied into the submission.

To add a Python opponent, place an `agent.py` implementing the Chessathon contract in its own
directory and add its name/path to `BASELINES` in `run_benchmark.py`. UCI opponents can use the
`UCIEngineAgent` adapter.

## Sunfish

Sunfish is not bundled or downloaded automatically. Obtain it from its official repository,
<https://github.com/thomasahle/sunfish>, review its license, and place its UCI-capable
UCI entry point at `benchmark/external/sunfish/uci.py`. It remains local-only. Keep the entire
checkout in that directory so the UCI entry point can import its companion source files.

## Regression positions

Add JSON cases under `benchmark/regression/`. A case may list `bad_moves`, `good_moves`, or both.
The runner checks legality, records elapsed time, and can show a previous version's move:

```bash
python benchmark/run_regression.py \
  --previous benchmark/agents/v3/agent.py
```

These tests answer whether a known move recurs; they do not claim engine-best play and do not
require Stockfish.

## Elo estimates

The report uses `D = -400 * log10((1 / score) - 1)`, clipping perfect scores to avoid infinity.
Small samples have very wide uncertainty. A performance rating is shown only when an opponent
provides a documented/configured rating, and different rating pools are not directly comparable.
Use this benchmark primarily for consistent A/B comparisons under identical openings and clocks.

## Suites

`quick` covers random, greedy, minimax, and a previous version when present. `full` adds numba,
more version games, and Sunfish when installed. Missing optional opponents are clearly skipped.
Use `--games` to override counts and `--tc fast|tournament` to select `2+0.5` or `120+0.5`.
