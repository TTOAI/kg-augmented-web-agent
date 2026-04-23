#!/bin/bash
set -u
cd "$(dirname "$0")"

# Phase 2: stratified sample of 50 gitlab tasks (baseline/clean N=1)
# MUTATE tasks are reset after each to prevent env leakage.

TASKS_FILE="output/tasks.50.json"
RUN_ROOT="output/phase2_baseline_n1"
MAIN_LOG="$RUN_ROOT/main.log"
TIMEOUT=600

mkdir -p "$RUN_ROOT"
echo "===== phase2 baseline N=1 started $(date) =====" > "$MAIN_LOG"

# Pre-classify tasks: MUTATE vs others (same heuristic as sampling)
python3 - <<'PYEOF' > "$RUN_ROOT/task_types.txt"
import json, re
tasks = json.load(open("output/tasks.50.json"))
def classify(intent):
    i = intent.lower()
    if re.search(r'\b(create|add|post|submit|delete|remove|rename|change|merge|assign|upload|invite|fork|close|reopen|star|unstar|follow|unfollow|comment|approve|disapprove|set|make|send|publish|archive)\b', i):
        return 'MUTATE'
    if re.search(r'\b(get |find |how many|what is|what are|who |tell me|count|number of|latest|most recent|highest|which |where |how much)\b', i):
        return 'RETRIEVE'
    return 'NAVIGATE'
for t in tasks:
    print(f"{t['task_id']}\t{classify(t['intent'])}")
PYEOF

TASK_IDS=$(awk '{print $1}' "$RUN_ROOT/task_types.txt")

for t in $TASK_IDS; do
  t_type=$(awk -v id="$t" '$1==id {print $2}' "$RUN_ROOT/task_types.txt")
  echo "===== TASK $t ($t_type) start $(date +%H:%M:%S) =====" >> "$MAIN_LOG"
  .venv/bin/python3 run_with_timeout.py "$TIMEOUT" \
    .venv/bin/python3 run_webarena_verified.py \
    --tasks-file "$TASKS_FILE" --task-id "$t" \
    --config config/webarena_verified.json \
    --run-root "$RUN_ROOT" >> "$MAIN_LOG" 2>&1
  rc=$?
  echo "===== TASK $t done $(date +%H:%M:%S) rc=$rc =====" >> "$MAIN_LOG"

  # Reset env only after MUTATE
  if [ "$t_type" = "MUTATE" ]; then
    echo "----- env reset after MUTATE $t $(date +%H:%M:%S) -----" >> "$MAIN_LOG"
    .venv/bin/webarena-verified env stop --site gitlab >> "$MAIN_LOG" 2>&1 || true
    .venv/bin/webarena-verified env start --site gitlab >> "$MAIN_LOG" 2>&1
  fi
done

# Final reset for clean state
.venv/bin/webarena-verified env stop --site gitlab >> "$MAIN_LOG" 2>&1 || true
.venv/bin/webarena-verified env start --site gitlab >> "$MAIN_LOG" 2>&1
echo "===== ALL DONE $(date) =====" >> "$MAIN_LOG"
