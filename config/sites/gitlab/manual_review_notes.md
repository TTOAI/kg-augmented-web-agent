# Manual Review Notes — site=gitlab

3-stage hybrid 구축 파이프라인의 **수동 검증 단계(M4-C)** 결정 로그.
사람이 직접 작성. baseline 측정 전에 catalog freeze하기 위한 의사 결정 근거.

관련 docs: `docs/kg_design/07 §14`, `docs/kg_design/02 §3-7`.

---

## Freeze 이력

| timestamp (ISO UTC) | git_rev | source_mix | 노트 |
|---|---|---|---|
| _(첫 freeze 후 채움)_ | _ | _ | _ |

`config/sites/gitlab/frozen_kg/INDEX.md`도 자동 갱신됨 (run_freeze.py).

---

## 수동 검토 결정 로그

`run_review_diff.py`로 manual + crawl + derived 3-source diff를 본 후, 항목별로
승격(예: inferred → declared) / 강등 / 제거 결정과 근거를 기록.

### StatePatterns

| id | source(검토 전) | source(검토 후) | 결정 | 근거 |
|---|---|---|---|---|
| _(예시)_ `crawl:dashboard__abc123` | crawl/verified | manual/declared | 승격 | URL 패턴 정확, default값 보강 |

### InfoTypes

| name | source(전) | source(후) | 결정 | 근거 |
|---|---|---|---|---|
| _(예시)_ `dashboard_overview` | llm/inferred | manual/declared | 승격 | 도메인 명사구로 합의됨 |

### Actions

| name | source(전) | source(후) | 결정 | 근거 |
|---|---|---|---|---|

### LeadsToEdges / RealizesEdges

| key | source(전) | source(후) | 결정 | 근거 |
|---|---|---|---|---|

---

## 검토 원칙 (재현성)

1. catalog는 **사이트 일반 기능 표면 기준**으로 검토. 실험 task ID·실험 task 분포를
   참고해 항목을 추가/제거하지 않는다 (memory `feedback_no_task_site_bias`).
2. crawl/llm 산출물 중 한 번이라도 manual로 승격된 항목은 `source=manual` 로 직접
   `infotypes.yaml` / `kg_seed.json`에 기록한다.
3. 잘못된 inferred 항목은 derived_kg.json에는 남겨두되 freeze 시 manual 우선순위로
   덮이거나 표시하지 않는다 (store.merge가 처리).
4. 검토 후 catalog freeze는 `run_freeze.py`로 immutable snapshot 생성. 수정이 필요
   하면 새 timestamp로 다시 freeze (이전 snapshot은 그대로 보존).
