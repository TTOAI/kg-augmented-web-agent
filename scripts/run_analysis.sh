#!/bin/bash
# Phase C 측정 종료 후 1-command post-measurement analysis pipeline.
#
# Usage:
#   bash scripts/run_analysis.sh output/phase_c_180
#
# 입력 구조 (run_phase_c_180.sh 산출):
#   <RUN_ROOT>/
#     baseline/N1/<task_id>/{agent_response.json, eval_result.json, webarena_verified.log}
#     baseline/N2/...
#     baseline/N3/...
#     kg_full/N1/...
#     kg_full/N2/...
#     kg_full/N3/...
#
# 출력 구조:
#   <RUN_ROOT>/
#     baseline/task_types.txt     (tasks.30.task_types.txt 복사)
#     baseline/analysis/{raw.csv, paired.csv, summary.md}
#     kg_full/task_types.txt
#     kg_full/analysis/{raw.csv, paired.csv, summary.md}
#     paired_stats.md             (overall + per-type McNemar/Wilcoxon)
#     coverage.md
#     failure_template.csv        (수동 라벨링 대상)
#     final_report.md             (Phase D 요약)
#     docs/paper/table1_filled.md (make_paper_tables.py 산출)

set -eu

RUN_ROOT="${1:-output/phase_c_180}"
TASK_TYPES_SRC="output/tasks.30.task_types.txt"
FROZEN_KG="config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json"

if [ ! -d "$RUN_ROOT" ]; then
    echo "[error] RUN_ROOT $RUN_ROOT not found" >&2
    exit 2
fi
if [ ! -f "$TASK_TYPES_SRC" ]; then
    echo "[error] task types file $TASK_TYPES_SRC not found" >&2
    exit 2
fi

echo "===== [0/6] eval-tasks — per (variant, round) 배치 evaluator 실행 ====="
# 원 측정 script(run_phase_c_180.sh)는 agent_response.json만 생성.
# eval_result.json은 webarena-verified eval-tasks 별도 호출로만 생성되므로
# analysis 진입 직전에 배치 실행 (180 runs × LLM 무호출, deterministic).
for variant in baseline kg_full; do
    for round in N1 N2 N3; do
        RDIR="$RUN_ROOT/$variant/$round"
        if [ ! -d "$RDIR" ]; then
            continue
        fi
        # eval_result.json이 이미 모든 task에 있으면 skip
        agent_count=$(find "$RDIR" -maxdepth 2 -name "agent_response.json" 2>/dev/null | wc -l | tr -d ' ')
        eval_count=$(find "$RDIR" -maxdepth 2 -name "eval_result.json" 2>/dev/null | wc -l | tr -d ' ')
        if [ "$agent_count" -eq 0 ]; then
            echo "[warn] $RDIR agent_response empty — skipping"
            continue
        fi
        if [ "$eval_count" -eq "$agent_count" ]; then
            echo "[ok] $RDIR eval_result.json already complete ($eval_count/$agent_count)"
            continue
        fi
        echo "[eval-tasks] $RDIR ($eval_count/$agent_count existing eval results)"
        .venv/bin/webarena-verified eval-tasks \
            --output-dir "$RDIR" \
            --config config/webarena_verified.json 2>&1 | tail -5
    done
done

echo ""
echo "===== [1/6] analyze_baseline.py — per variant raw/paired/summary ====="
# task_types.txt를 variant 디렉토리에 배포. source가 하나이므로 baseline/kg_full이
# 같은 파일을 받음 — paired 분석의 task_type 일관성 보장.
for variant in baseline kg_full; do
    VAR_DIR="$RUN_ROOT/$variant"
    if [ ! -d "$VAR_DIR" ]; then
        echo "[warn] $VAR_DIR missing — skipping"
        continue
    fi
    cp "$TASK_TYPES_SRC" "$VAR_DIR/task_types.txt"
    .venv/bin/python3 scripts/analyze_baseline.py \
        --baseline-dir "$VAR_DIR" \
        --output-dir "$VAR_DIR/analysis"
done

# Sanity: baseline/kg_full task_types.txt 동일성 검증 — 분석 전 abort-on-mismatch
if [ -f "$RUN_ROOT/baseline/task_types.txt" ] && [ -f "$RUN_ROOT/kg_full/task_types.txt" ]; then
    if ! diff -q "$RUN_ROOT/baseline/task_types.txt" "$RUN_ROOT/kg_full/task_types.txt" > /dev/null; then
        echo "[error] baseline/task_types.txt vs kg_full/task_types.txt mismatch — aborting" >&2
        diff "$RUN_ROOT/baseline/task_types.txt" "$RUN_ROOT/kg_full/task_types.txt" | head -20 >&2
        exit 3
    fi
    echo "[ok] task_types.txt consistent across variants"
fi

echo ""
echo "===== [2/5] paired_stats.py — McNemar + Wilcoxon (overall + per-type) ====="
.venv/bin/python3 scripts/paired_stats.py \
    --variant baseline="$RUN_ROOT/baseline/analysis" \
    --variant kg_full="$RUN_ROOT/kg_full/analysis" \
    --output "$RUN_ROOT/paired_stats.md"

echo ""
echo "===== [3/5] coverage.py — KG-addressable coverage per type ====="
.venv/bin/python3 scripts/coverage.py \
    --variant baseline="$RUN_ROOT/baseline" \
    --variant kg_full="$RUN_ROOT/kg_full" \
    --frozen "$FROZEN_KG" \
    --output "$RUN_ROOT/coverage.md"

echo ""
echo "===== [4/5] failure_mode.py template — 라벨링 대상 CSV ====="
.venv/bin/python3 scripts/failure_mode.py template \
    --variant baseline="$RUN_ROOT/baseline" \
    --variant kg_full="$RUN_ROOT/kg_full" \
    --output "$RUN_ROOT/failure_template.csv"
echo "     → 이 CSV를 수동으로 2명 rater가 라벨링 후 (rater1.csv / rater2.csv):"
echo "       .venv/bin/python3 scripts/failure_mode.py kappa \\"
echo "           --rate1 $RUN_ROOT/failure_rater1.csv \\"
echo "           --rate2 $RUN_ROOT/failure_rater2.csv \\"
echo "           --output $RUN_ROOT/failure_kappa.md"

echo ""
echo "===== [5/5] make_paper_tables.py — Table 1 fill-in ====="
if [ -f scripts/make_paper_tables.py ]; then
    .venv/bin/python3 scripts/make_paper_tables.py \
        --paired-stats "$RUN_ROOT/paired_stats.md" \
        --baseline-summary "$RUN_ROOT/baseline/analysis/summary.md" \
        --kg-summary "$RUN_ROOT/kg_full/analysis/summary.md" \
        --coverage "$RUN_ROOT/coverage.md" \
        --template docs/paper/table1_template.md \
        --output docs/paper/table1_filled.md
else
    echo "[warn] scripts/make_paper_tables.py not present — skipping Table 1 fill"
fi

echo ""
echo "===== Writing final_report.md ====="
{
    echo "# Phase C — Final Report"
    echo ""
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "RUN_ROOT: \`$RUN_ROOT\`"
    echo ""
    echo "## 산출 파일"
    echo "- \`$RUN_ROOT/baseline/analysis/{raw,paired}.csv\`, \`summary.md\`"
    echo "- \`$RUN_ROOT/kg_full/analysis/{raw,paired}.csv\`, \`summary.md\`"
    echo "- \`$RUN_ROOT/paired_stats.md\` (overall + per-type McNemar/Wilcoxon)"
    echo "- \`$RUN_ROOT/coverage.md\` (Hook A coverage per task_type)"
    echo "- \`$RUN_ROOT/failure_template.csv\` (수동 라벨링 대상)"
    echo "- \`docs/paper/table1_filled.md\` (논문 Table 1)"
    echo ""
    echo "## 다음 단계"
    echo "1. \`failure_template.csv\`를 2명 rater가 독립적으로 라벨링 → rater1/rater2 CSV"
    echo "2. \`failure_mode.py kappa\` → Cohen's κ"
    echo "3. \`docs/paper/draft.md\`의 placeholder를 \`table1_filled.md\`로 치환"
    echo "4. \`docs/08\` scenario matrix에서 측정 결과 pattern에 해당하는 §4.3 narrative 선택"
} > "$RUN_ROOT/final_report.md"

echo "[ok] wrote $RUN_ROOT/final_report.md"
echo ""
echo "===== All done ====="
