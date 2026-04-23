#!/bin/bash
# 본 논문의 baseline 첫 공식 측정.
# 50 task stratified sample × N=3 repetition × 1 variant (Baseline)
# = 150 runs.
#
# Scope 근거: docs/kg_design/07_scope_and_justifications.md
# Baseline 정의: Hook A/B/C/D 모두 off (KG 없음), LLM_TEMPERATURE=0 고정.

set -u
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# 0. 환경 고정 — 실험 재현성
# ---------------------------------------------------------------------------
export LLM_TEMPERATURE=0

TASKS_FILE="output/tasks.50.json"
RUN_ROOT="output/baseline_n3"
TIMEOUT=600
MAIN_LOG="$RUN_ROOT/main.log"

mkdir -p "$RUN_ROOT"
echo "===== baseline_n3 started $(date) =====" > "$MAIN_LOG"
echo "LLM_TEMPERATURE=$LLM_TEMPERATURE" >> "$MAIN_LOG"
echo "LLM_PROVIDER=${LLM_PROVIDER:-<from .env>}" >> "$MAIN_LOG"
echo "OPENAI_MODEL=${OPENAI_MODEL:-<default>}" >> "$MAIN_LOG"
echo "ANTHROPIC_MODEL=${ANTHROPIC_MODEL:-<default>}" >> "$MAIN_LOG"

# ---------------------------------------------------------------------------
# 1. task_type pre-classification (heuristic) — MUTATE 후 env reset 용
# ---------------------------------------------------------------------------
TYPES_FILE="$RUN_ROOT/task_types.txt"
.venv/bin/python3 - <<'PYEOF' > "$TYPES_FILE"
import json, re
tasks = json.load(open("output/tasks.50.json"))
MUTATE_RX = re.compile(r'\b(create|add|post|submit|delete|remove|rename|change|merge|assign|upload|invite|fork|close|reopen|star|unstar|follow|unfollow|comment|approve|disapprove|set|make|send|publish|archive|update|modify|edit)\b', re.IGNORECASE)
RETRIEVE_RX = re.compile(r'\b(get |find |how many|what is|what are|who |tell me|count|number of|latest|most recent|highest|which |where |how much)\b', re.IGNORECASE)
for t in tasks:
    i = t['intent']
    if MUTATE_RX.search(i):
        tt = 'MUTATE'
    elif RETRIEVE_RX.search(i):
        tt = 'RETRIEVE'
    else:
        tt = 'NAVIGATE'
    print(f"{t['task_id']}\t{tt}")
PYEOF

TASK_IDS=$(awk '{print $1}' "$TYPES_FILE")

# ---------------------------------------------------------------------------
# 2. 시작 전 환경 clean start — 이전 state 영향 제거
# ---------------------------------------------------------------------------
echo "----- initial env reset $(date +%H:%M:%S) -----" >> "$MAIN_LOG"
.venv/bin/webarena-verified env stop --site gitlab >> "$MAIN_LOG" 2>&1 || true
.venv/bin/webarena-verified env start --site gitlab >> "$MAIN_LOG" 2>&1
sleep 3

# ---------------------------------------------------------------------------
# 3. N=3 sequential rounds, 각 round 내 50 task sequential
# ---------------------------------------------------------------------------
for N in 1 2 3; do
  ROUND_ROOT="$RUN_ROOT/N${N}"
  mkdir -p "$ROUND_ROOT"
  echo "===== ROUND N=$N started $(date +%H:%M:%S) =====" >> "$MAIN_LOG"

  for t in $TASK_IDS; do
    t_type=$(awk -v id="$t" '$1==id {print $2}' "$TYPES_FILE")
    echo "===== N=$N TASK $t ($t_type) start $(date +%H:%M:%S) =====" >> "$MAIN_LOG"
    .venv/bin/python3 run_with_timeout.py "$TIMEOUT" \
      .venv/bin/python3 run_webarena_verified.py \
      --tasks-file "$TASKS_FILE" --task-id "$t" \
      --config config/webarena_verified.json \
      --run-root "$ROUND_ROOT" >> "$MAIN_LOG" 2>&1
    rc=$?
    echo "===== N=$N TASK $t done $(date +%H:%M:%S) rc=$rc =====" >> "$MAIN_LOG"

    # MUTATE 후 env reset — 다음 task 영향 제거
    if [ "$t_type" = "MUTATE" ]; then
      echo "----- env reset after MUTATE N=$N $t $(date +%H:%M:%S) -----" >> "$MAIN_LOG"
      .venv/bin/webarena-verified env stop --site gitlab >> "$MAIN_LOG" 2>&1 || true
      .venv/bin/webarena-verified env start --site gitlab >> "$MAIN_LOG" 2>&1
      sleep 3
    fi
  done

  # 라운드 종료 시 env reset — 다음 round의 state는 라운드 내 MUTATE 누적 없이 시작
  echo "----- end-of-round env reset N=$N $(date +%H:%M:%S) -----" >> "$MAIN_LOG"
  .venv/bin/webarena-verified env stop --site gitlab >> "$MAIN_LOG" 2>&1 || true
  .venv/bin/webarena-verified env start --site gitlab >> "$MAIN_LOG" 2>&1
  sleep 3
  echo "===== ROUND N=$N done $(date +%H:%M:%S) =====" >> "$MAIN_LOG"
done

echo "===== ALL DONE $(date) =====" >> "$MAIN_LOG"
