#!/usr/bin/env bash
# 1 task per category sweep — v1 (KG), part 1/2 (first 10 tasks).
#
# 흐름: [task i 시작] → [container reset] → [agent run + HAR 기록]
#       → 반복 → 모든 HAR 수집 후 → [eval-tasks 오프라인 채점]
set -u
export NODE_OPTIONS=""
export LLM_PROVIDER=openai
export OPENAI_MODEL=gpt-5.4-mini

TASKS_FILE=output/tasks.gitlab.json
CONFIG=config/webarena_verified.json
ROOT=output/1taskpercategories/runs
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

VARIANT=v1
PART=1
TASK_IDS="441 45 446 590 411 523 475 480 293 658"

restart_env() {
    echo "[$(date +%H:%M:%S)] === restart gitlab env ==="
    .venv/bin/webarena-verified env stop  --site gitlab 2>&1 | tail -1
    .venv/bin/webarena-verified env start --site gitlab 2>&1 | tail -1
    .venv/bin/python scripts/kg/utils/refresh_auth.py 2>&1 | tail -1
}

run_trial() {
    local tid="$1"
    local kg_enabled=1 kg_mode=minimal
    local run_root="$ROOT/${VARIANT}"
    local log="$LOG_DIR/${VARIANT}_${tid}.log"
    mkdir -p "$run_root"
    echo "[$(date +%H:%M:%S)] --- ${VARIANT} task ${tid} ---"
    KG_ENABLED=$kg_enabled KG_MODE=$kg_mode \
        .venv/bin/python run_with_timeout.py 1200 \
        .venv/bin/python run_webarena_verified.py \
        --tasks-file "$TASKS_FILE" --task-id "$tid" \
        --config "$CONFIG" --run-root "$run_root" \
        > "$log" 2>&1
    echo "[$(date +%H:%M:%S)]   done — $log"
}

echo "================================================"
echo "${VARIANT} part ${PART} sweep start — $(date)"
echo "================================================"
for tid in $TASK_IDS; do
    restart_env
    run_trial "$tid"
done

echo "================================================"
echo "Offline eval start — $(date)"
echo "================================================"
.venv/bin/webarena-verified eval-tasks \
    --task-ids $TASK_IDS \
    --output-dir "$ROOT/${VARIANT}" \
    --config "$CONFIG" \
    > "$LOG_DIR/eval_${VARIANT}_${PART}.log" 2>&1
echo "[$(date +%H:%M:%S)] eval done — $LOG_DIR/eval_${VARIANT}_${PART}.log"

echo "================================================"
echo "${VARIANT} part ${PART} done — $(date)"
echo "================================================"
