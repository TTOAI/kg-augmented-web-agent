# Phase 3.E — Task-driven scaffolding findings

phase_c_180/baseline 실패 분석으로 도출한 scaffolding 결함을 task 단위로 진단·수정·측정한 기록. 각 iteration은 (a) 진단 (b) 일반화 가능한 fix (c) target task 재측정 (d) 회귀 체크 로 구성.

---

## Iter P1.1 — Task 479 (MUTATE, "Set up a new, empty repository awesome_webagent")

### 진단 (phase_c_180/baseline N1-3)

**Intent**: "Set up a new, **empty** repository with the name awesome_webagent"

**Evaluator expected post_data**:
- `project[name]: awesome_webagent`
- `project[initialize_with_readme]: '0'`

**Actual post_data (pre-fix)**:
- `project[name]: awesome_webagent` ✓
- `project[initialize_with_readme]: '1'` ✗ (default checked)

**근본 원인**:
1. **Observation gap**: `browser.py::observe_page`의 `_INPUT_SELECTORS`가 text inputs만 포함. Checkbox / radio 상태가 observation에 노출되지 않음 → agent가 "empty" qualifier를 어느 form 필드와 매핑해야 할지 알 수 없음.
2. **Click gap**: `try_click_target`이 link + button만 탐색. `<label>` 요소 (checkbox toggle 경로) 누락 → agent가 intent의 non-default qualifier를 form과 연결할 방법이 없음.
3. (부가) `build_observation_message`의 MUTATE 관련 form-review 가이드 부재.

### Fix (일반화 가능)

| # | 파일 | 변경 | 영향 |
|---|---|---|---|
| 1 | `browser.py::observe_page` + 신규 `extract_toggle_states` | Checkbox/radio 상태를 `[checked]/[unchecked] label` + `radio_group: opt1 ✓ \| opt2` 포맷으로 `inputs` 앞에 삽입 | 모든 MUTATE form에 checkbox/radio 상태 노출 |
| 2 | `browser.py::try_click_target` | 검색 selector에 `label` 추가 | 모든 페이지에서 label 클릭 → 연결된 checkbox toggle |
| 3 | `llm.py::build_observation_message` | task_type=="MUTATE" AND form inputs 있을 때 form-submission checklist 섹션 주입 (empty/private/guest/state/reviewer 등 qualifier 예시 명시) | MUTATE 모든 task에 qualifier alignment 가이드 |

### 재측정 결과 (env fresh + single run)

- **Pre-fix run** (phase_c_180/baseline): `initialize_with_readme='1'` → evaluator failure
- **Post-fix run** (phase_3e_iter_479/label_click_n1):
  - Agent `click target='Initialize repository with a README'` (label click 경로 작동)
  - `initialize_with_readme` 필드가 **post_data에서 사라짐** (HTML 표준: unchecked checkbox는 submit 안 함)
  - Evaluator는 literal `'0'` 기대 → **여전히 failure**

### 판정

- **Agent semantic outcome**: 정확 (empty repo 실제 생성됨). Scaffolding fix 성공.
- **Evaluator strict-match**: missing key ≠ '0'. `eval_exclusions.md` 후보 (broken evaluator: unchecked checkbox form 동작과 expected post_data 불일치).

### Regression check

- Task 44 (NAVIGATE, "Open my todos"): SUCCESS 유지

### Commit

각 변경 commit 시 해당 task의 evaluator-match 실패는 broken evaluator 표시 후 기록.

---

## Iter P1.2 — (TBD)

다음 target: Task 742 (MUTATE, "Create private project and add members") — visibility radio + role select qualifier. P1.1의 toggle_states 노출로 visibility radio는 지원. Role select (dropdown)은 추가 fix 필요할 가능성.
