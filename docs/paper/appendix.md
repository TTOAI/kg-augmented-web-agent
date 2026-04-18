# Appendix — Reproducibility Materials

## A. Task Sample (seed=42, per-type equal N=10)

WebArena-Verified GitLab 180 task 모집단에서 `scripts/sample_tasks_per_type.py`로
seed=42 균등 샘플링 결과. `output/tasks.30.task_types.txt`의 내용을 그대로 공개한다.

### A.1 NAVIGATE (10 tasks)
`44, 102, 103, 104, 339, 340, 342, 343, 665, 669`

### A.2 RETRIEVE (10 tasks)
`46, 168, 171, 179, 180, 259, 312, 784, 786, 788`

### A.3 MUTATE (10 tasks)
`411, 414, 421, 479, 483, 536, 576, 594, 668, 742`

### Generation command
```bash
python scripts/sample_tasks_per_type.py \
    --input <WebArena-Verified 180-task pool> \
    --seed 42 \
    --per-type 10 \
    --output output/tasks.30.json \
    --types-output output/tasks.30.task_types.txt
```

---

## B. Frozen KG Metadata

**Artifact**: `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json`

| 항목 | 값 |
|---|---|
| Build timestamp | 2026-04-16T16:46:55Z |
| Git rev at build | `534c49d` |
| Builder version | `0.1.0-hybrid` |
| Source mix (node + edge counts) | crawl=33150, llm=593, manual=0 |
| InfoType count | 37 |
| StatePattern count | 3040 |
| ARI (3-run group-level) | **0.9264** |
| Crawl dir | `output/crawl/20260416_231931_v4` |
| Derivation dir | `output/derivation/20260417_011348_v9_run1` |

**Note on manual=0**: 본 evaluation에서 Stage 3 (manual verification)는 수행하지 않음.
Architecture에 포함되나 본 연구 scope에서 자동 pipeline만 적용
(`docs/kg_design/07 §14` 참조).

---

## C. Broken Evaluator Exclusions

Strict match evaluator 결함으로 정상 agent 행동이 fail 기록되는 task는 수동 검증 후
분리 보고. 판정 기준 (`docs/kg_design/eval_exclusions.md §판정 기준`):

1. Agent `verify_done` = SUCCESS (`agent_response.json.status == "SUCCESS"`)
2. Evaluator strict match (`NetworkEventEvaluator` URL, `AgentResponseEvaluator` 문자열) 실패
3. 수동 로그 검증에서 의미적 target state 도달 확인

**양 variant (Baseline, Full KG)에 동일 적용**으로 McNemar pair 공정성 확보.

측정 종료 후 이 섹션에 task_id별 사유 + 로그 참조 기재 예정 (`docs/kg_design/
eval_exclusions.md` 테이블을 그대로 인용).

---

## D. Domain Prior Disclosure

`docs/kg_design/07 §14`의 disclosure table 재게재. Pipeline 코드·LLM prompt에 박혀 있는
generic web-engineering prior (site vocabulary 아님):

| 위치 | Prior 내용 | 정당화 |
|---|---|---|
| `playwright_crawler.py` | download ext blocklist (.zip/.tar/.ics/.pdf…) | 일반 web 표준 |
| `crawl_to_kg.py` | form.action_url → cross-target edge | HTML form spec |
| `post_enrich.py` D1 | bindings ↔ slot/query exact match + `[]` variant | URL convention |
| `post_enrich.py` D2 | `*_path → path_segments`, else `segment` | path slot naming |
| `post_enrich.py` D3 | optional_bindings → query param backfill | web query convention |
| `post_enrich.py` D6 | InfoType prefix ≥2 공유 → category clustering | taxonomy heuristic |
| `llm_derivation.py` Call 1 prompt | "list/index page는 filter/sort/pagination 받는다" | web app convention |

**사이트 어휘 (GitLab-specific URL, vocabulary, UI label) 박지 않음** — memory
`feedback_no_task_site_bias` 원칙 준수.

---

## E. Evaluation Protocol Details (reference)

본문 §4.1에서 요약한 protocol의 상세는 `docs/kg_design/06_evaluation_protocol.md` 참조.

### E.1 Per-run paired binarization (`06 §4-5`)
각 (variant, task) 쌍에서 N=3 run의 `eval_status` 중 majority vote (SUCCESS ≥ 2/3) →
binary 1, else 0. `all3_success` / `any_success`도 함께 보고.

### E.2 McNemar exact test (`06 §4-3`)
- Null: `b = c` (discordant 대칭)
- Two-tailed exact binomial on `min(b, c) | b+c`
- Overall α=0.05, per-type α=0.0167 (Bonferroni 3)

### E.3 Wilcoxon signed-rank (continuous)
- Input: per-task paired mean of N=3 runs (token, step, wall-time)
- Self-contained implementation (`scripts/paired_stats.py`) — scipy 의존성 없음

### E.4 Wilson 95% CI
- Success rate point estimate + CI

---

## F. Command Cheatsheet

```bash
# Full measurement (~11h)
bash run_phase_c_180.sh

# Background monitor
nohup python3 scripts/monitor_phase_c.py \
    --run-root output/phase_c_180 \
    --total-runs 180 \
    > output/phase_c_180/monitor_console.log 2>&1 &

# Post-measurement analysis (one command)
bash scripts/run_analysis.sh output/phase_c_180

# Fill paper tables
python scripts/make_paper_tables.py \
    --baseline-analysis output/phase_c_180/baseline/analysis \
    --kg-analysis output/phase_c_180/kg_full/analysis \
    --template docs/paper/table1_template.md \
    --output docs/paper/table1_filled.md
```

---

## G. Related Files Index

| 용도 | Path |
|---|---|
| 논문 draft | `docs/paper/draft.md` |
| Table template | `docs/paper/table1_template.md` |
| Figures source (mermaid) | `docs/paper/figures/*.mmd` |
| Task sample | `output/tasks.30.json`, `output/tasks.30.task_types.txt` |
| Frozen KG | `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json` |
| Broken eval list | `docs/kg_design/eval_exclusions.md` |
| Reproducibility doc | `docs/kg_design/09_reproducibility.md` |
| Contribution scenarios | `docs/kg_design/08_contribution_scenarios.md` |
| Evaluation protocol | `docs/kg_design/06_evaluation_protocol.md` |
| Scope justifications | `docs/kg_design/07_scope_and_justifications.md` |
| Implementation architecture | `docs/kg_design/05_implementation_architecture.md` |
