# Evaluation setup

## Benchmark

WebArena-Verified (GitLab site). Task inputs are exported with `webarena-verified agent-input-get` and fed to `run_webarena_verified.py`. Task outcomes are scored by `webarena-verified eval-tasks`.

## Variants

| Variant | KG | Purpose |
|---|---|---|
| V0 | `KG_ENABLED=0` | Baseline. No KG hints injected. |
| V1 | `KG_ENABLED=1 KG_CASCADE=1 KG_REPLAN=1 KG_EXPOSE_ACTIONS=1` | Full KG integration: target-class inference, path finder + cascade fallback, per-step hint replanning, in-class action catalog + filter-category exposure. |

Form-shortcut exposure (`KG_FORM_SHORTCUT`) is off by default; it is kept as a toggle for separate ablation.

## Task selection

Stratified random sample over task types (NAVIGATE / RETRIEVE / MUTATE) in target proportions. The selected IDs and stratification ratios are recorded in the measurement output directory's `tasks.json` for reproducibility.

## Metrics

- **Success rate** per variant (primary).
- **Paired McNemar's test** on discordant pairs (same task set, two variants).
- **Wilcoxon signed-rank** on per-task step count (efficiency).
- **Failure-mode breakdown** (per [evaluation/eval_exclusions.md](eval_exclusions.md)) reporting how many failures stem from evaluator strict-match issues vs. agent reasoning vs. KG misdirection.

## Environment handling

- MUTATE tasks run with `webarena-verified env stop` + `env start` between tasks to ensure a clean container state.
- NAVIGATE / RETRIEVE tasks run back-to-back without reset (they do not mutate server state).
- Each task has a hard wall-clock timeout of 20 minutes (`run_with_timeout.py`).

## Budget

The agent runtime is configured with:

- `MAX_RETRIES_PER_GOAL=8`
- `MAX_REPLANS_PER_TASK=3`
- `LLM_CALL_LIMIT_PER_TASK=450`
- `MAX_STEPS_PER_TASK=60`

These values were chosen to match the conditions under which initial exploratory measurements were made, to keep subsequent comparisons on like-for-like terms.
