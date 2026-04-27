#!/usr/bin/env bash
# Round 2 measurement — 4 tasks × V0/V1 × 3 trials = 24 runs.
#
# Tasks (active task_cards/<COND>_<task_id>.md):
#   H1  309 (RET) — single URL template, RET task-type breadth for H archetype.
#   H3  156 (NAV) — scope disambiguation, different H mechanism than H2/102.
#   L2  568 (MUT) — non-ARIA modal contribution loss; different L type than 411/418.
#   Null2 664 (MUT) — text-content-dominated; Null breadth into MUT task-type.
#
# Per round_protocol.md:
#   - V1−tc not measured.
#   - All trial outcomes reported.
#   - NAV+RET back-to-back; MUT env restart between every trial.
set -u
export NODE_OPTIONS=""
export LLM_PROVIDER=anthropic
export ANTHROPIC_MODEL=claude-sonnet-4-6

TASKS_FILE=output/tasks.gitlab.json
CONFIG=config/webarena_verified.json
ROOT=output/characterization
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

NAV_RET_TASKS="156 309"
MUT_TASKS="568 664"
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
    if [ -d "$run_root/$tid" ]; then
        mv "$run_root/$tid"/* "$run_root/" 2>/dev/null || true
        rmdir "$run_root/$tid" 2>/dev/null || true
    fi
    echo "[$(date +%H:%M:%S)]   done — $log"
}

echo "================================================"
echo "Round 2 start — $(date)"
echo "================================================"

# NAV+RET tasks: 156, 309. variant boundary needs env restart.
for variant in v0 v1; do
    restart_env
    for trial in $(seq 1 $TRIALS); do
        for tid in $NAV_RET_TASKS; do
            run_trial "$variant" "$tid" "$trial"
        done
    done
done

# MUT tasks: env restart per trial AND per task AND per variant.
for tid in $MUT_TASKS; do
    for variant in v0 v1; do
        for trial in $(seq 1 $TRIALS); do
            restart_env
            run_trial "$variant" "$tid" "$trial"
        done
    done
done

echo "================================================"
echo "Round 2 done — $(date)"
echo "================================================"
echo "Next: extract_signals → aggregate_cells → render_figures (output/characterization)"
