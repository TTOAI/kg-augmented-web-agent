#!/bin/bash
set -u
cd "$(dirname "$0")"

TASKS=(44 45 102 132 156 169 205 258 259 293 308 339 357 390)
TIMEOUT=600
RUN_ROOT="output/baseline_clean_n1"
MAIN_LOG="$RUN_ROOT/main.log"
mkdir -p "$RUN_ROOT"
echo "===== baseline/clean N=1 started $(date) =====" > "$MAIN_LOG"

for t in "${TASKS[@]}"; do
  echo "===== TASK $t start $(date +%H:%M:%S) =====" >> "$MAIN_LOG"
  .venv/bin/python3 run_with_timeout.py "$TIMEOUT" \
    .venv/bin/python3 run_webarena_verified.py \
    --tasks-file output/tasks.14.json --task-id "$t" \
    --config config/webarena_verified.json \
    --run-root "$RUN_ROOT" >> "$MAIN_LOG" 2>&1
  echo "===== TASK $t done $(date +%H:%M:%S) rc=$? =====" >> "$MAIN_LOG"
done

webarena-verified env stop --site gitlab >> "$MAIN_LOG" 2>&1 || true
webarena-verified env start --site gitlab >> "$MAIN_LOG" 2>&1
echo "===== ALL DONE $(date) =====" >> "$MAIN_LOG"
