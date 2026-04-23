#!/bin/bash
set -u
cd "$(dirname "$0")"

TASKS=(44 45 102 132 156 169 205 258 259 293 308 339 357 390)
TIMEOUT=600
MAIN_LOG="output/smoke_n3_main.log"
echo "===== smoke N=3 started $(date) =====" > "$MAIN_LOG"

for N in 1 2 3; do
  RUN_ROOT="output/smoke_n3/N${N}"
  mkdir -p "$RUN_ROOT"
  for t in "${TASKS[@]}"; do
    echo "===== N=$N TASK $t start $(date +%H:%M:%S) =====" >> "$MAIN_LOG"
    .venv/bin/python3 run_with_timeout.py "$TIMEOUT" \
      .venv/bin/sitekg-agent \
      --tasks-file output/tasks.14.json --task-id "$t" \
      --config config/webarena_verified.json \
      --run-root "$RUN_ROOT" >> "$MAIN_LOG" 2>&1
    echo "===== N=$N TASK $t done $(date +%H:%M:%S) rc=$? =====" >> "$MAIN_LOG"
  done
  # MUTATE(390) 후 env reset — 다음 N 영향 최소화
  webarena-verified env stop --site gitlab >> "$MAIN_LOG" 2>&1 || true
  webarena-verified env start --site gitlab >> "$MAIN_LOG" 2>&1
  sleep 2
  echo "===== N=$N done $(date +%H:%M:%S) =====" >> "$MAIN_LOG"
done

echo "===== ALL DONE $(date) =====" >> "$MAIN_LOG"
