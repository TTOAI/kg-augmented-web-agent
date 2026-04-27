#!/usr/bin/env bash
# Round 1 measurement — 3 tasks × V0/V1 × 3 trials = 18 runs.
#
# Tasks (active task_cards/<COND>_<task_id>.md):
#   H2  102 (NAV) — pilot 1 trial showed V1=15 vs V0=29; stabilize with 3 trials.
#   L1  418 (MUT) — newly selected after task 411 L1 hypothesis was refuted.
#   Null1 44 (NAV) — smoke 1 trial each showed V0=V1=2 step; active control.
#
# Per round_protocol.md:
#   - V1−tc not measured.
#   - All trial outcomes reported regardless of result.
#   - NAV+RET back-to-back; MUT env restart between every trial AND variant boundary.
set -u
export NODE_OPTIONS=""
export LLM_PROVIDER=openai
export OPENAI_MODEL=gpt-5.4-mini

TASKS_FILE=output/tasks.gitlab.json
CONFIG=config/webarena_verified.json
ROOT=output/characterization
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

NAV_TASKS="44 102"
MUT_TASKS="418"
TRIALS=3

restart_env() {
    echo "[$(date +%H:%M:%S)] === restart gitlab env ==="
    .venv/bin/webarena-verified env stop --site gitlab 2>&1 | tail -1
    .venv/bin/webarena-verified env start --site gitlab 2>&1 | tail -1
    .venv/bin/python scripts/kg/utils/refresh_auth.py 2>&1 | tail -1
}

run_trial() {
    local variant="$1" tid="$2" trial="$3"
    local kg_enabled kg_mode
    case "$variant" in
        v0) kg_enabled=0; kg_mode=auto    ;;
        v1) kg_enabled=1; kg_mode=minimal ;;
        *) echo "unknown variant: $variant" >&2; return 1 ;;
    esac
    local run_root="$ROOT/${variant}/${tid}/trial_${trial}"
    local log="$LOG_DIR/${variant}_${tid}_t${trial}.log"
    mkdir -p "$run_root"
    echo "[$(date +%H:%M:%S)] --- ${variant} task ${tid} trial ${trial} ---"
    KG_ENABLED=$kg_enabled KG_MODE=$kg_mode \
        .venv/bin/python run_with_timeout.py 1200 \
        .venv/bin/python run_webarena_verified.py \
        --tasks-file "$TASKS_FILE" --task-id "$tid" \
        --config "$CONFIG" --run-root "$run_root" \
        > "$log" 2>&1
    # run_webarena_verified writes to <run_root>/<task_id>/, but we want trial_N/
    # to BE the trial dir. Move artifacts up one level.
    if [ -d "$run_root/$tid" ]; then
        mv "$run_root/$tid"/* "$run_root/" 2>/dev/null || true
        rmdir "$run_root/$tid" 2>/dev/null || true
    fi
    echo "[$(date +%H:%M:%S)]   done — $log"
}

echo "================================================"
echo "Round 1 start — $(date)"
echo "================================================"

# NAV tasks: 44 then 102. variant boundary needs env restart for clean storage state.
# Within a variant, NAV tasks can run back-to-back without env restart (no server mutation).
for variant in v0 v1; do
    restart_env
    for trial in $(seq 1 $TRIALS); do
        for tid in $NAV_TASKS; do
            run_trial "$variant" "$tid" "$trial"
        done
    done
done

# MUT task 418: per round_protocol + memory rule, env restart before EACH trial of MUT.
for tid in $MUT_TASKS; do
    for variant in v0 v1; do
        for trial in $(seq 1 $TRIALS); do
            restart_env
            run_trial "$variant" "$tid" "$trial"
        done
    done
done

echo "================================================"
echo "Round 1 done — $(date)"
echo "================================================"
echo "Next: scripts/eval/extract_signals.py output/characterization/{v0,v1}/{44,102,418}/trial_*"
echo "Then: scripts/eval/aggregate_cells.py output/characterization"
echo "Then: scripts/eval/render_figures.py output/characterization"
