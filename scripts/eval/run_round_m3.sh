#!/usr/bin/env bash
# Measurement 3 — M1 task clean replication, 1 trial each.
#   4 tasks × {v0,v1} × 1 trial = 8 runs.
#
# 목적: M1 동일 task를 **직접 OpenAI**(게이트웨이 미사용 → endpoint confound 0)
# 로 재측정해 M1 characterization 재현 여부 확인 + 대표 demo 영상 확보.
# --record-video → viewport 1280x720 (M1 800x600과 다름 = viewport confound
# 1건, plan §5 caveat 문서화). endpoint·task confound는 0.
#
# Tasks (M1 condition → task):
#   #44  (NAV, Null1)  — control parity 재현
#   #102 (NAV, H2)     — M1 유일 깨끗한 KG 도움(15→9) 재현되나?
#   #309 (RET, H1)     — M1 refuted(19→21) 재현?
#   #664 (MUT, Null2)  — control + baseline 분산(14,12,37) 재현?
set -u
export NODE_OPTIONS=""
export LLM_PROVIDER=openai
export OPENAI_MODEL=gpt-5.4-mini

TASKS_FILE=output/m2/tasks.json
CONFIG=config/webarena_verified.json
ROOT=output/m3
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

NAV_RET_TASKS="44 102 309"
MUT_TASKS="664"
TRIALS=1

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
echo "Measurement 3 (M1 clean replication) start — $(date)"
echo "================================================"

for variant in v0 v1; do
    restart_env
    for trial in $(seq 1 $TRIALS); do
        for tid in $NAV_RET_TASKS; do
            run_trial "$variant" "$tid" "$trial"
        done
    done
done

for tid in $MUT_TASKS; do
    for variant in v0 v1; do
        for trial in $(seq 1 $TRIALS); do
            restart_env
            run_trial "$variant" "$tid" "$trial"
        done
    done
done

echo "================================================"
echo "Measurement 3 done — $(date)"
echo "================================================"
echo "Next: extract_signals → aggregate_cells (output/m3) → M1 대조"
