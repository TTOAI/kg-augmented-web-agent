# Stage A.f Step 2' — Frontier-BFS expansion report

**Date**: 2026-04-21
**Protocol**: CDIP v0.2 (Option 1 frontier-BFS + step/within-step separation)

## Goal

Step 1 완료 후 진정한 Option 1 frontier-BFS로 새 영역 탐색. Step 1 BFS tree의 leaves에서 시작해 children 수집 → 새 URL pool accumulate → rule 일반화 검증.

## Method

1. **Frontier 추출**: `output/validation/stage_a_f/classified.json`에서 `depth == max_depth` URL 454개
2. **Phase A** (outbound link 추출): 각 frontier URL 재방문 → `<a href>` 추출 → pool에 없는 URL만 queue
3. **Phase B** (BFS from children): depth 0~4, max 1500 URL, known-cap 2
4. **Classification**: `final_url` → rule 적용 → matched/unmatched
5. **Unmatched cluster → annotate → rule 재추출 → re-classify** (필요 시)

## Results

### Crawl metrics
- Frontier seeds: 454
- Phase A: 338 new children enqueued
- Phase B: 238 records visited (budget 1500 대비 일찍 queue 소진)
- HTTP 200: 162
- Depth 분포: 대부분 depth 1-2 (새 영역)

### Initial classification (with step 1's 141 rules)
- Matched: 155/162 = 95.7%
- Unmatched: 7

### Unmatched cluster
- `/{ns}/{proj}/-/new/master` (5) — 기존 `project/file_new_form`과 같은 class (main vs master branch)
- `/-/ide/project/{ns}/{proj}/edit/master/-` (2) — 기존 `ide/edit_view`와 같은 class

→ **새 structural class 아님, 단지 branch generalization 이슈**

### Rule 일반화 (iter 5 patch)

2개 master-branch 인스턴스를 ANNOTATIONS에 추가:
- `iter5_project_file_new_master` → project/file_new_form
- `iter5_ide_edit_master` → ide/edit_view

Rule extractor의 `_derive_from_multi`가 main/master 차이 자동 감지 → `{branch}` slot 생성.

### Final classification (with 141 rules post-iter5)

- Step 1 pool (1457): **1457/1457 = 100.0%** (회귀 없음)
- Step 2' pool (162): **162/162 = 100.0%** (branch variant 해결)
- Combined (1619): **1619/1619 = 100.0%**

### Self-validation

190 annotations (188 + 2 iter5) re-rule 자기 일관성: **190/190 = 100%**

## Convergence

**Step 2' convergence criteria**:
- ✅ 새 structural class = 0 (branch variant 2개는 기존 class의 instance 추가)
- ✅ Unmatched = 0 (combined pool)
- ✅ Rule self-validation = 100%
- ✅ Step 1 pool 회귀 없음

→ **Stage A.f CONVERGED**. True Option 1 frontier-BFS 방식으로 증명.

## Taxonomy final

- **Scopes**: 7 (project, dashboard, explore, user, account, global, ide)
- **Unique classes**: 138
- **Rules**: 141
- **Annotations**: 190
- **URLs in pool**: 1695 (step 1: 1457 + step 2': 238)

### Scope 분포

| Scope | Classes |
|---|---:|
| project | 85 |
| account | 14 |
| global | 10 |
| user | 9 |
| dashboard | 7 |
| explore | 5 |
| ide | 3 |

## Next steps (Stage A 완료)

- Stage A.g retrospective (이 보고서 + protocol doc으로 자동 정리)
- Stage B — action catalog (각 class의 navigation action 수집)
- Stage C — class 간 edge (action → target class)
- Solution 2 MVP — KG BFS simulation + agent hint
