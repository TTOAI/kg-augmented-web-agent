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

## Branch status

- `main`: V2.5 baseline
- `baseline/clean`: V2.5 baseline (pinned for measurement)
- `feature/kg-v2`: KG redesign in progress (current branch)

KG design discussion and decisions are accumulated as numbered documents in `docs/kg_design/` (01~06). Baseline code stays untouched; the KG module will live alongside it.

## Architecture (current branch: V2.5 baseline)

Benchmark execution pipeline:

```
webarena-verified CLI → run_webarena_verified.py
                              ↓
            WebArenaVerifiedAdapter (benchmarks/webarena_verified/adapter.py)
                              ↓
                    run_agent() (agent/core.py)
                              ↓
                    AgentRunResult (agent/types.py)
```

### Agent layer (`site_adaptive_webagent/agent/`)

- `core.py` — `run_agent()` entrypoint: `analyze_intent()` → `build_plan()` → sub-goal loop with tool-use LLM → `_verify_done()`.
- `types.py` — `AgentRunResult` and its `TaskType`/`TaskStatus` literals. This is the benchmark contract written as `agent_response.json`.

### Runtime layer (`site_adaptive_webagent/runtime/`)

- `types.py` — `IntentPlan`, `PageObservation`, `ExecutionOutcome`, `SubGoal` dataclasses + `TaskType`/`TaskStatus` literals.
- `browser.py` — Playwright observation helpers (`observe_page`, `try_click_target`, `try_fill_target`, `try_search`).
- `executor.py` — sub-goal orchestration loop + `_verify_done` (hard rule + LLM judge).
- `llm.py` — `LLMClient` + `build_plan` + `build_observation_message` + `build_tool_use_system_prompt`.
- `tools.py` — tool schemas for LLM tool-use (click/fill/goto/goback/search/done).
- `intent.py` — rule-based intent analysis (TaskType classification + target phrase extraction).

### Benchmark adapter (`benchmarks/webarena_verified/`)

`adapter.py` owns the full benchmark harness: auth setup (UI login or header-based per site), Playwright browser/context lifecycle, HAR recording, `agent_response.json` output, and output validation. `runner.py` is the CLI entry point that parses args and calls the adapter.

### Output contract

Each task run produces `output/<task_id>/agent_response.json` (task_type, status, retrieved_data, error_details) and `output/<task_id>/network.har`. Re-running backs up the existing directory to `<task_id>_bkp_N`.

## KG layer (planned, not yet implemented)

Will be added under `site_adaptive_webagent/kg/` with 4 integration hooks into the baseline agent loop. Design details: `docs/kg_design/05_implementation_architecture.md`. Schema + trust decisions: `docs/kg_design/02_open_questions.md`. Site-specific config skeleton: `config/sites/gitlab/`.

## Commit format

Follow the **Lore Commit Protocol** from `AGENTS.md`: the first line is *why* (not what), followed by optional structured trailers (`Constraint:`, `Rejected:`, `Directive:`, `Tested:`, `Not-tested:`).
