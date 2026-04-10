# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup

```bash
# Install project in editable mode (required for tests and the runner)
pip install -e .

# Install Playwright and browser
pip install playwright
playwright install chromium

# Copy and edit the benchmark config
cp config/webarena_verified.example.json config/webarena_verified.json
```

### Tests

```bash
# Run all tests (tests/ is a package — must set top-level dir)
.venv/bin/python -m unittest discover -t . -s tests/ -v

# Run a specific test file
.venv/bin/python -m unittest tests.test_runtime_contracts

# Run a specific test class or method
.venv/bin/python -m unittest tests.test_runtime_contracts.StrategyRouterTests
.venv/bin/python -m unittest tests.test_runtime_contracts.StrategyRouterTests.test_selects_fast_path_when_all_conditions_are_met
```

### Benchmark workflow

```bash
# 1. Start benchmark environment (example: shopping site)
webarena-verified env start --site shopping

# 2. Export task inputs
webarena-verified agent-input-get \
  --task-ids 44 \
  --config config/webarena_verified.json \
  --output output/tasks.demo.json

# 3. Run agent
python3 run_webarena_verified.py \
  --tasks-file output/tasks.demo.json \
  --task-id 44 \
  --config config/webarena_verified.json \
  --run-root output \
  --headed

# 4. Evaluate
webarena-verified eval-tasks \
  --task-ids 44 \
  --output-dir output \
  --config config/webarena_verified.json
```

## Architecture

The project is structured around a benchmark execution pipeline:

```
webarena-verified CLI → run_webarena_verified.py
                              ↓
            WebArenaVerifiedAdapter (benchmarks/webarena_verified/adapter.py)
                              ↓
                    run_agent() (agent/core.py)
                              ↓
                    AgentRunResult (agent/types.py)
```

### Two distinct layers

**Agent layer** (`site_adaptive_webagent/agent/`): The web agent policy.
- `core.py` — the full baseline agent: `run_agent()` → `analyze_intent()` → `execute_plan()`. Takes a natural-language `intent` and Playwright `pages`, returns `AgentRunResult`. Intent is classified into one of three `TaskType`s (RETRIEVE / NAVIGATE / MUTATE), then dispatched to the corresponding shallow Playwright execution path.
- `types.py` — `AgentRunResult` and its `TaskType`/`TaskStatus` literals. This is the benchmark contract: the adapter writes it as `agent_response.json`.

**Runtime layer** (`site_adaptive_webagent/runtime/`): Site-adaptive knowledge base (KB) and execution routing.
- `types.py` — dataclasses for `SiteProfile`, `PageType`, `ActionSchema`, `ValidatorRule`, `PolicyRule`, `FailurePattern`, `KBBundle`, and execution records (`TaskRun`, `StepRecord`, etc.). `PageType` and `ActionSchema` form the site graph (nodes and edges). `ActionSchema.source_page_key → target_page_key` makes transitions explicit.
- `enums.py` — all enum values (`RouteKind`, `TaskRunStatus`, `KBConfidence`, etc.).
- `schema.py` — SQLite DDL for two groups: *KB store* (site knowledge) and *execution memory* (run history). Initialized via `bootstrap_runtime_schema(connection)`.
- `router.py` — `StrategyRouter.route()` implements a deterministic decision table: `FAST_PATH` (all conditions met) → `PARTIAL_KB` (active site, but KB/task mismatch) → `FALLBACK` (site not active or page type unresolved) → `APPROVAL_FIRST` (policy requires it, overrides everything).

### Benchmark adapter (`benchmarks/webarena_verified/`)

`adapter.py` owns the full benchmark harness: auth setup (UI login or header-based per site), Playwright browser/context lifecycle, HAR recording, `agent_response.json` output, and output validation. `runner.py` is the CLI entry point that parses args and calls the adapter.

### Output contract

Each task run produces `output/<task_id>/agent_response.json` (task_type, status, retrieved_data, error_details) and `output/<task_id>/network.har`. Re-running backs up the existing directory to `<task_id>_bkp_N`.

## Commit format

Follow the **Lore Commit Protocol** from `AGENTS.md`: the first line is *why* (not what), followed by optional structured trailers (`Constraint:`, `Rejected:`, `Directive:`, `Tested:`, `Not-tested:`).
