#!/usr/bin/env bash
# Pilot — H2 (NAV 102) + L1 (MUT 411) × V0/V1/V1-tc × 1 trial each.
#
# Purpose: 본측정 전에 (1) V1이 실제로 의미 있는 KG 힌트를 주입하는지,
# (2) L1의 inferrer가 wrong-class로 confident routing하는지 확인.
# Pilot 결과 기반으로 hypothesis card 최종 lock 여부 결정.
#
# Output: output/pilot/{v0,v1,v1_tc}/<task_id>/{agent_response.json, network.har, webarena_verified.log}
set -u
export NODE_OPTIONS=""
export LLM_PROVIDER=anthropic
export ANTHROPIC_MODEL=claude-sonnet-4-6

TASKS_FILE=output/tasks.gitlab.json
CONFIG=config/webarena_verified.json
ROOT=output/pilot
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

restart_env() {
    echo "[$(date +%H:%M:%S)] === restart gitlab env ==="
    .venv/bin/webarena-verified env stop --site gitlab 2>&1 | tail -1
    .venv/bin/webarena-verified env start --site gitlab 2>&1 | tail -1
    .venv/bin/python scripts/kg/utils/refresh_auth.py 2>&1 | tail -1
}

run_task() {
    local variant="$1" tid="$2"
    local kg_enabled kg_mode disable_tc
    case "$variant" in
        v0)     kg_enabled=0; kg_mode=auto;     disable_tc=0 ;;
        v1)     kg_enabled=1; kg_mode=minimal;  disable_tc=0 ;;
        v1_tc)  kg_enabled=1; kg_mode=minimal;  disable_tc=1 ;;
        *) echo "unknown variant: $variant" >&2; return 1 ;;
    esac
    local run_root="$ROOT/${variant}"
    local log="$LOG_DIR/${variant}_${tid}.log"
    mkdir -p "$run_root"
    echo "[$(date +%H:%M:%S)] --- ${variant} task ${tid} ---"
    KG_ENABLED=$kg_enabled KG_MODE=$kg_mode KG_DISABLE_TARGET_INFERRER=$disable_tc \
        .venv/bin/python run_with_timeout.py 1200 \
        .venv/bin/python run_webarena_verified.py \
        --tasks-file "$TASKS_FILE" --task-id "$tid" \
        --config "$CONFIG" --run-root "$run_root" \
        > "$log" 2>&1
    echo "[$(date +%H:%M:%S)]   done — $log"
}

echo "================================================"
echo "Pilot start — $(date)"
echo "================================================"

# H2 (NAV 102) — no inter-variant env reset (NAV doesn't mutate server)
restart_env
for variant in v0 v1 v1_tc; do
    run_task "$variant" 102
done

# L1 (MUT 411) — env reset before each variant (MUTATE may persist state)
for variant in v0 v1 v1_tc; do
    restart_env
    run_task "$variant" 411
done

echo "================================================"
echo "Pilot done — $(date)"
echo "================================================"
echo "Next: scripts/eval/extract_signals.py output/pilot/{v0,v1,v1_tc}/{102,411}"
echo "Then: scripts/eval/aggregate_cells.py output/pilot"
echo "Then: scripts/eval/render_figures.py output/pilot"
