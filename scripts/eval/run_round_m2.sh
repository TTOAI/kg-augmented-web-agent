#!/usr/bin/env bash
# Measurement 2 (characterization) — 7 tasks × baseline/KG × 3 trials = 42 runs.
#
# Variant identifiers in output paths: v0=baseline, v1=KG.
# Picks are rough purposeful (docs/evaluation/measurement_2_tasks.md) — NOT a
# pre-registered confirmatory test. All trial outcomes reported regardless.
#
# Tasks:
#   #308 (RET) — KG 도움 예상: commits → contributor graph path 단축
#   #357 (NAV) — scope 특성: dashboard MR scope disambiguation
#   #102 (NAV) — replication: M1 H2 (KG 도움) 재현 확인
#   #44  (NAV) — replication: M1 Null1 (무영향) 재현 확인
#   #419 (MUT) — KG 무효/미묘: status 기능이 KG 매핑돼 있음에도?
#   #480 (MUT) — KG 한계: invite-members modal 내부 KG 공백
#   #664 (MUT) — replication: M1 Null2. leading-verb 규칙은 NAV로 분류하나
#                의미상 create-issue(서버 mutation) → env reset 위해 MUT 취급.
#
# Notes:
#   - NAV+RET back-to-back; MUT env restart between every trial AND variant.
#   - --record-video: task 수행 .webm (adapter, Item 1.2).
set -u
export NODE_OPTIONS=""
export LLM_PROVIDER=openai
export OPENAI_MODEL=gpt-5.4-mini

TASKS_FILE=output/m2/tasks.json
CONFIG=config/webarena_verified.json
ROOT=output/m2
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

NAV_RET_TASKS="44 102 308 357"
MUT_TASKS="419 480 664"
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
        --config "$CONFIG" --run-root "$run_root" --record-video \
        > "$log" 2>&1
    if [ -d "$run_root/$tid" ]; then
        mv "$run_root/$tid"/* "$run_root/" 2>/dev/null || true
        rmdir "$run_root/$tid" 2>/dev/null || true
    fi
    echo "[$(date +%H:%M:%S)]   done — $log"
}

echo "================================================"
echo "Measurement 2 start — $(date)"
echo "================================================"

# NAV+RET tasks: 44, 102, 308, 357. variant boundary needs env restart.
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
echo "Measurement 2 done — $(date)"
echo "================================================"
echo "Next: extract_signals → aggregate_cells → render_figures (output/m2)"
echo "Then: 서술 렌즈(measurement_2_plan.md §4) 적용 + M1 vs M2 특성 narrative"
