SHELL := /bin/bash

.PHONY: setup play arena zip gate benchmark benchmark-quick benchmark-full compare-v3 regression

setup:
	uv sync

play:
	uv run python -m harness.play --white . --black baselines/greedy $(if $(FEN),--fen "$(FEN)")

arena:
	uv run python -m harness.arena --opponent baselines/greedy --games 20

zip:
	uv run python -m harness.package

gate:
	uv run ruff check .
	uv run mypy
	uv run python -m harness.arena --opponent baselines/random --games 2 --base-ms 5000

benchmark: benchmark-quick

benchmark-quick:
	uv run python benchmark/run_benchmark.py --suite quick
	uv run python benchmark/run_regression.py

benchmark-full:
	uv run python benchmark/run_benchmark.py --suite full
	uv run python benchmark/run_regression.py

compare-v3:
	uv run python benchmark/compare_versions.py --old benchmark/agents/v3/agent.py --new agent.py --games 100

regression:
	uv run python benchmark/run_regression.py
