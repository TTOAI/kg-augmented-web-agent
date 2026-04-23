#!/bin/bash
set -u
cd "$(dirname "$0")"

# MUTATE(390)를 마지막으로. 중간엔 env reset 없이 연속 실행.
TASKS=(44 45 102 132 156 169 205 258 259 293 308 339 357 390)
TIMEOUT=600
RUN_ROOT="output/smoke_14"
MAIN_LOG="$RUN_ROOT/main.log"
mkdir -p "$RUN_ROOT"
echo "===== smoke 14 started $(date) =====" > "$MAIN_LOG"

for t in "${TASKS[@]}"; do
  echo "===== TASK $t (start: $(date +%H:%M:%S)) =====" >> "$MAIN_LOG"
  .venv/bin/sitekg-agent \
    --tasks-file output/tasks.14.json --task-id "$t" \
    --config config/webarena_verified.json \
    --run-root "$RUN_ROOT" >> "$MAIN_LOG" 2>&1 &
  PID=$!
  (sleep "$TIMEOUT" && kill -9 "$PID" 2>/dev/null && echo "===== TIMEOUT $t ($(date +%H:%M:%S)) =====" >> "$MAIN_LOG") &
  KILLER=$!
  wait "$PID" 2>/dev/null
  kill "$KILLER" 2>/dev/null
  echo "===== TASK $t done ($(date +%H:%M:%S)) =====" >> "$MAIN_LOG"
done

# MUTATE(390) 이후 env reset (다음 측정 대비)
webarena-verified env stop --site gitlab >> "$MAIN_LOG" 2>&1 || true
webarena-verified env start --site gitlab >> "$MAIN_LOG" 2>&1
echo "===== ALL DONE $(date) =====" >> "$MAIN_LOG"
