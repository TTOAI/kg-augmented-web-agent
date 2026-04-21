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

## Iter P1.2 — Task 742 (MUTATE "Create private project and add members")

### Intent + Expected
- "Create a new **private** project 'planner' and add **Abishek, Vinta** as members"
- Evaluator expects 3 network events: (1) `{name: 'planner', visibility: 'private'}` (2) `{user_id: 5, access_level: 30}` (3) `{user_id: 278, access_level: 30}`

### 진단 (baseline N1 + post-P1.1 re-run)

- **Name field doubling (baseline)**: fill이 3회 호출되며 "plannerplanner" 제출 가능성. Post-P1.1 run에선 개선 (URL=byteblaze/planner 정상). 원인 불명 (stochastic 또는 P1.1 toggle_states 관련 변화로 추측).
- **Members 페이지 미발견 (주 blocker)**: Agent가 `/byteblaze/planner/edit`(settings) 머물고 Members link 미노출 → NOT_FOUND_ERROR로 종료.
  - GitLab Members URL: `/{project}/-/project_members`
  - 현 project settings sidebar만 노출 (General, Integrations, Webhooks, CI/CD 등). Members는 sidebar의 "Project information" 하위에 있으나 **collapsed 상태**.
  - `observe_page`는 visible text만 추출 → collapsed menu item 안 잡힘.

### 구조적 이슈

**Sub-menu discovery**: Collapsed navigation menu의 하위 링크가 observation에 없어 agent는 존재를 모름. 영향 범위: members / audit / security 등 "top-level 네비 아래 숨은" 페이지 전반.

### 이 iteration의 scope 결정

Sub-menu discovery는 P1 (MUTATE form submission)과 P3 (NAVIGATE URL state) 모두에 걸치며, 단일 iteration fix로 해결 어려움. **별도 P4로 분리 대상**:
- Option X-A: `observe_page`에서 collapsed nav를 expand 후 재추출 (side-effect 위험)
- Option X-B: URL 추정 가이드 prompt 추가 (site-specific knowledge 의존)
- Option X-C: KG의 class_catalog에서 해당 class의 URL template 활용 (KG 의존 → baseline V0 개선엔 기여 안 함)

결정: **P1.2는 scaffolding fix 없이 종료**. Sub-menu discovery는 post-Phase 3.E 또는 KG 의존 변경 (Option X-C)으로 이관. 742는 현재 scope에선 not-improvable.

### 재측정 결과
- Post-P1.1 fixes 적용 상태로 실행: 60 step 후 NOT_FOUND_ERROR. Project는 생성됨 (URL=`byteblaze/planner`) but 멤버 추가 sub-goal 실패.
- Evaluator 기준 failure (baseline과 동일 outcome; 진전 없음).

### 교훈

- P1.1의 toggle_states + label click은 단일 form 내 qualifier 매핑에만 유효. Multi-step MUTATE (form → sub-page → form ...)의 chained discovery 문제는 별도 scope.
- 일부 MUTATE는 "scaffolding 개선"만으로 해결 불가 — site structure discovery (KG 또는 URL 추정) 필요.

---

## Iter P1.3 — Task 414 (MUTATE "Change LICENSE to MIT")

### 진단
- Intent: "Change the LICENSE for repo byteblaze/dotfiles to an MIT license"
- Evaluator expects: POST to `/byteblaze/dotfiles/-/update/main/LICENSE` with MIT content
- Actual (3 baseline runs): POST to `/byteblaze/dotfiles/-/create/main` — create flow 사용
- 근본 원인: Agent가 "change" verb를 parsing 하지 못하고 GitLab의 "Add LICENSE" 버튼 shortcut (UI affordance)를 따라 `/new/` flow로 진입. 기존 LICENSE 파일 overwriting 대신 새 파일 create → evaluator strict URL match 실패.

### Fix (generalizable, P1.1 checklist 확장)

`build_observation_message`의 `_MUTATE_FORM_CHECKLIST`에 **verb routing** 섹션 추가:
  - "change/update/modify/edit/rename/replace/delete" → existing resource locate → Edit action
  - "create/add/new/set up" → Create form

### 재측정 결과
- 45.1s 19 step, agent_response SUCCESS
- 그러나 actual POST = `/-/create/main` (create flow) — evaluator failure 유지
- URL trail: agent는 `/new/?file_name=LICENSE`로 이동 후 CREATE POST 실행, 이후 `/blob/main/LICENSE`로 재방문 (verify). 체크리스트 존재하지만 GitLab의 "Add LICENSE" 버튼 affordance가 우세.

### 판정

- **Fix는 valid generalizable**: 다른 MUTATE task에서 "change" 의미 명확히 하는 데 기여 가능 (현재 task 414에는 agent가 override).
- **Task 414 specific blocker**: UI affordance ("Add LICENSE" 버튼)가 prompt 이김. 이건 agent에 "UI suggestion vs task semantics 충돌 시 semantics 우선" 원칙을 심어야 함 — 더 strong intervention 필요 (system prompt / planner 수정).
- **이 iteration에서 추가 intervention 보류**: Risk vs reward 불확실. Checklist 확장은 kept.

### 교훈

- Prompt-level verb guidance는 agent의 1st-order reasoning에 소폭 영향. UI affordance가 명확할 때 2nd-order override 필요.
- 일부 MUTATE는 evaluator strict URL match (create vs update endpoint) 때문에 "agent가 semantic 올바르게 했어도" fail. Broken evaluator 아니고 scaffolding이 해결해야 할 영역. KG의 "edit endpoint" 정보 노출 시 해결 가능성 (future work).

---

## Iter P3.1 — Task 339 (NAVIGATE "opened issues that report bugs")

### 진단
- Intent: "Go to the list of all opened issues that report bugs"
- Evaluator expects referer URL query_params: `{state: 'opened', label_name[]: 'bug'}` — ONLY these two, no extras
- Actual (3 baseline runs): URL has `search=bug`(or `label:bug state:opened`) + `state=opened` + `label_name[]=bug` + `sort=created_date` + `first_page_size=20`. `label_name[]=bug` is present (good), but `search=`와 extras 때문에 evaluator strict query_params match 실패.
- 원인: Agent가 상단 검색 바에 filter 구문 타이핑 → GitLab이 filter params로 parse + raw `search=` 보존

### Fix 시도: NAVIGATE filter checklist 주입 (UI dropdown 우선 가이드)

Prompt에 "검색 바 대신 Label dropdown / status tab 사용" 가이드 추가.

### 재측정 결과 (revert 사유)
- N1: agent "label widget is not exposed" → declare_error (더 나빠짐)
- N2: state=opened만 tab으로 적용, label dropdown 사용 실패 → `label_name[]=bug` 없음
- N3: filter 전혀 적용 안 됨, /-/issues 블랭크

**근본 원인**: `observation.dropdown_options`는 OPEN 상태의 dropdown 항목만 노출. Collapsed Label dropdown은 agent에게 보이지 않음. Checklist가 "dropdown 사용" 권장했으나 agent가 dropdown을 찾을 수 없음 → search 회피 + dropdown 미사용 → URL 빈 상태 → evaluator 실패. Regression.

### Revert

NAVIGATE checklist 제거. Observation layer (collapsed dropdown 노출) 또는 KG의 filter URL 템플릿 제공 없이는 prompt-level 단독 guidance로 해결 불가.

### 교훈

- Prompt guidance는 **observation이 노출하는 범위 안에서만** 유효. "X 하라" 권장하면서 X 수단이 observation에 없으면 agent는 교착.
- 이 task의 해결 경로:
  1. **Observation 확장**: Collapsed dropdown 내 항목 사전 노출 (side-effect 위험)
  2. **KG filter template**: Target class의 "정규 filter URL" 템플릿을 hint로 제공. 예: `/{ns}/{proj}/-/issues?state=opened&label_name[]=bug`. Agent가 직접 goto 가능.
  3. **Stronger intent parsing**: "bugs" → label_name[]=bug, "opened" → state=opened 규칙 기반 URL 구성 후 goto.

Option 2는 Solution 2 KG의 자연 확장 — 별도 phase에서 검토 가치.

### 판정

**이 iteration**: fix 없음 (revert). Finding 기록으로 Solution 2 (KG) 측 contribution 영역 확인.

---

## Iter P3.2 — (next: 상태 점검 후 결정)
