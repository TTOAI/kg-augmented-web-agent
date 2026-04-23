# V1 Protocol Spec — Site-Adaptive Class Taxonomy Construction

**Date**: 2026-04-18
**Protocol version**: 0.6 (provisional; revise on change, log in Part C)
**Status**: Stage A mid-execution, to be finalized at Stage A retrospective
**Scope**: Site-agnostic protocol. GitLab은 하나의 worked example.

## Positioning

본 문서는 **class taxonomy 자체**의 범용성을 주장하지 않는다. 대신 **분류 process의 reproducibility**를 명세한다 — 같은 protocol을 다른 사이트에 적용하면 site-specific하지만 일관된 taxonomy가 도출되어야 한다.

유비: 식물/동물 taxonomy는 이름이 다르나 phylogenetic method는 공유.

**Empirical scope**: 현재 GitLab 1 사이트에서만 실행됨. "Cross-site reproducibility"는 **future work**로 남김 (다른 사이트 적용·비교는 본 연구 범위 밖).

---

## Part A. Confirmed (Stage A.a-c 실행 완료)

### Step 1. Observation layer

**Input**: 사이트 base URL + authenticated storage state (auth 필요 페이지 수집에는 필수)
**Output**: 각 URL에 대해 `{name, url, final_url, title, http_status, axtree}`

**수집 방법**:
- Playwright `page.goto(url, wait_until="networkidle")` + 1.5s 대기
- DOM walk based AXTree proxy (`page.evaluate(JS)`):
  - INTERACTIVE tag set: `a, button, input, select, textarea, form, nav, main, header, footer, aside, section, article, h1-h6, ul, ol, li, table, tr, td, th`
  - Label priority: aria-label > alt > title > innerText > `[href:…]` fallback
  - Max depth 20
- HTTP status는 `response.status`로 기록

**Artifacts**:
- `scripts/validation/v1_a_collect_axtrees.py` (수집기)
- `output/validation/V1_pages/{group}/{name}.json` (per-page)

**알려진 한계** (deferred, `V1_deferred_issues.md` 참조):
- D1 href 손실, D2 accname 미계산, D3 lazy content 누락, D4 title 변동성

---

### Step 2. Class criterion

**채택**: **Action repertoire equivalence** + **Core widget identity**

#### Terminology (본 문서 전역 정의)

본 protocol의 **본질 모델은 2-level**:

| 용어 | 정의 |
|---|---|
| **Class** | Hierarchical tree의 node. Internal이든 leaf이든 모두 class. Parent는 자식에게 chrome 상속. |
| **Variant** | Leaf class 내부의 action-axis sub-division (filter/sort/state 차이). `/`-suffix 표기. |
| **Instance** | 같은 class(또는 variant)에 속하는 구체 URL (path param·비-variant query 차이). |

**별명 (특정 depth의 class 지칭, 편의상)**:
- **Scope class** — tree root 직하위 class. 공유 chrome(sidebar/header)으로 식별. 예: `project`, `dashboard`, `account`
- **Intermediate class** — 중간 depth의 내부 node. 현재 sample엔 없음 (조건 충족 못 함). 있다면 `project/settings` 같은 것.
- **Leaf class** — tree 잎. 구체 페이지 클래스. 이전엔 "widget"이라 부르던 것. 예: `project/issue_list`, `account/preferences`.

**주의**:
- "scope"/"widget" 등은 **class의 depth별 역할 별명**이지 독립 tier 개념이 아님
- Depth는 가변(empirical 조건으로 추가 결정) — `{scope}/{widget}[/{variant}]` 고정 3-tier로 오해하면 안 됨
- Leaf class 이름은 통상 "core widget" 속성(`_list`, `_detail`, `_form` 등)을 따름 → 편의상 leaf class = widget으로 부르기도 함

#### 구조 — Recursive class inheritance tree

Taxonomy는 **root(site)부터 leaf(concrete page)까지의 tree**. 각 node는 class이고, child는 parent의 UI chrome을 상속 + 자신의 것 추가.

```
site (root; top-nav header 등 전역 chrome)
├── dashboard (헤더 28 action)
│   ├── issue_list
│   ├── merge_request_list
│   ├── group_list
│   ├── todo_list/pending, todo_list/done        ← variant
│   └── project_list/yours, /starred             ← variant
├── project (사이드바 57 action)
│   ├── main
│   ├── activity_list, file_list, commit_list, fork_list, label_list, milestone_list, member_list
│   ├── issue_list, issue_board, issue_detail, issue_new_form
│   ├── merge_request_list, merge_request_detail, mr_new_form
│   └── settings_general, settings_repository, settings_ci_cd, settings_integrations, settings_access_tokens
├── explore
│   ├── project_list, topic_list
├── user (public user view, /byteblaze 같은 URL)
│   └── profile
├── account (로그인한 사용자 본인의 계정 관리, /-/profile/* — 14 action 전용 사이드바)
│   ├── edit, preferences, notifications, ...
└── global (특정 scope 외 페이지)
    ├── help_landing, new_project_form, snippet_list, search_page
```

**표기**: path-style `{scope}/{…}/{leaf}[/{variant}]` — root `site`는 관례상 생략.

**Depth 추가 empirical 조건** (한 level 추가하려면 모두 충족):
1. 해당 level 아래 **2개 이상 자식** 존재
2. 자식들이 parent에 없는 **새로운 공유 chrome** 보유 (sub-nav, breadcrumb tab 등)
3. 그 chrome이 **action set에 기여** (단순 장식 아님)

**Empirical basis** (2026-04-18, broader selector 기준):
- Project scope 5 URL: 공유 사이드바 action (100% 일치)
- Dashboard scope 6 URL: 공유 헤더 28 action (28/29 일치)
- Account scope 3 URL (`/-/profile/*`): 공유 사이드바 14 action, 다른 scope엔 부재
- Project 내 settings sub-tree / issues sub-tree: 재측정 결과 **전용 sub-nav 없음** (project 사이드바 항목일 뿐 — flat 유지)

#### Class vs Variant 분리 기준

**Variant** — 같은 core widget + 같은 item schema, action 차이가 **filter/sort/state-selection** 축에만 존재
- 예: `project_list/yours` vs `/starred` (같은 project card, filter bar 차이)
- 예: `todo_list/pending` vs `/done` (같은 todo row, state gating 차이)

**Different class (sibling in tree)** — 다른 core widget OR 근본 action(create/edit/delete/lifecycle) 차이
- 예: `project/issue_list` vs `project/issue_board` (list widget vs kanban widget)
- 예: `project/settings/general` vs `/repository` (form field + save logic 다름)

**Different class (다른 parent)** — scope/chrome level에서 이미 분기
- 예: `dashboard/issue_list` vs `project/issue_list`

**판정 알고리즘** (sibling 2 page):
```
Q1. Core widget(반복 구조 + item schema) 동일?
    No → Different class
    Yes → Q2
Q2. Action 차이가 filter/sort/state 축뿐?
    Yes → Variant
    No  → Different class
```

**Rule of thumb**:
- "같은 것들 중 어떤 것을 보여줄지" 차이 → **variant**
- "무엇을 할 수 있는지" 자체의 차이 → **different class**

#### Level별 정리

| Level | 의미 | 예 |
|---|---|---|
| **Internal node** | Shared UI chrome을 제공하는 parent class (abstract) | `site`, `project`, `project/settings` |
| **Leaf node** | Concrete page class | `project/main`, `project/settings/general`, `dashboard/issue_list` |
| **Variant** (`/`-suffix) | Leaf의 action sub-division | `project_list/yours`, `todo_list/pending` |
| **Instance** | 같은 class 다른 URL | `/issues/1`, `/issues/2` |

#### Hierarchy semantics (bottom-up, derived)

- **Grouping이 먼저, parent는 derived**: URL 수집 → chrome + action set 실측 → scope별 grouping → scope 내 widget별 grouping → widget 내 variant별 grouping
- 각 level의 parent는 **abstract** (실 URL 없음). 모든 URL은 exactly one leaf node(variant 또는 widget)에 귀속.
- 상위 level action set ⊆ 하위 level action set (포함 관계)
- 일부 하위의 action set = 상위 가능 (추가 0개). URL space가 구분되면 여전히 별 node.

#### 5 Core principles

1. **Template-level만 본다, content-level은 보지 않는다**
   - 페이지 item이 0개든 100개든 class는 동일
   - 실증 (2026-04-18): `/dashboard/issues`의 "New issue" 버튼 부재는 issue 0개라서가 아니라 template에 **애초에 없음** (DOM inspection으로 확인)
   - 분류 근거는 "template에 무엇이 포함되는가" 이지 "지금 무엇이 렌더링되는가" 아님

2. **Core widget 정의**
   - Repeating (`li/tr/card` N회) → `_list`
   - Repeating + 계층 (폴더 → 폴더) → `_list` (각 페이지는 flat; 계층은 navigation 차원)
   - Single form → `_form`
   - Single entity detail/landing → `_detail` / `_main`
   - Multi-section (각 section 독립) → `_landing`
   - User/org entity + sub-sections → `_profile`

3. **Action set — 무엇을 count하고 무엇을 제외하는가**

   **Count 대상**:
   - `<button>`
   - `<a href=...>` (navigation 포함)
   - `<a role=button>`
   - 독립 `<input>`, `<select>` (widget 역할)

   **Count 제외**:
   - Filter dropdown 개별 option 값 ("Yes/No/Any" 같은 filter value는 action 아님)
   - Template artifact (`{{ title }}` 같은 unrendered placeholder)
   - Tooltip/aria-description만 있는 non-interactive

4. **Variant boundary는 template-dependent, state-dependent 아님**
   - **Template 상 존재 여부**가 variant 경계 기준 (예: dashboard issues에 "New issue" template 자체에 없음)
   - **State-gated 존재**(특정 data 상태에서만 노출)는 variant 경계로 쓰지 않음
     - 판단: empty state에서 DOM 확인 → DOM에 있으면 template, 없으면 state-gated
     - State-gated 차이는 instance-level metadata로 기록
   - 예외: URL/query가 state를 명시적으로 라우팅하는 경우(예: `?state=done`) → variant로 취급 (라우팅 자체가 template 변형)

5. **URL은 확인 단서일 뿐, 정의 기준이 아니다**
   - URL pattern 같다고 같은 class 보장 없음 (`/explore/projects`와 `/explore/projects/topics`는 prefix 공유하나 다른 class)
   - URL pattern 달라도 같은 class 가능 (`/dashboard`와 `/dashboard/projects`는 동일 template)
   - URL은 rule extraction(Step 5)에서 pattern 키로 사용하되, 분류 정의는 core widget + action set으로

#### 경계 case 처리

- **Template에 있지만 state로 숨겨짐** (state-gated): empty state에서 DOM 체크로 판별. Gated는 variant 경계로 쓰지 않음.
- **Lazy-rendered (hover/click mount)**: 단일 snapshot으로 못 봄. Stage A에서는 deferred (D3, Stage B에서 stateful crawl).
- **Empty class**: 페이지 존재(HTTP 200) + template DOM 존재 → class 유효. 현재 데이터 없음은 instance-level 특성.

#### Instance variance 판정 원칙 (v0.6 신규)

같은 class의 여러 instance 간 action 비교 시 **raw action set의 Jaccard 사용 금지** — instance-level data(파일명, commit SHA, project 이름, 사용자 이름, 숫자 count, 날짜 등)가 action label에 섞여 artifact 유발.

**올바른 방법: template 교집합 사용**
- Class의 canonical action set = 모든 instance의 action **교집합** (N≥2 instance 필요)
- Template이 비어있거나 trivial하면 class 주장 약함
- 같은 class 주장 검증: 새 instance의 action set과 기존 template의 **공유 비율** (template coverage ratio)

**실증 (2026-04-21, Stage A verify)**:
- `project/issue_list` (3 instances): template 15 action, variance instance의 template coverage 0.75
- `project/merge_request_list` (2 instances): template 7 action, variance coverage 0.64
- `project/main` (3 instances): template 17 action, coverage 0.24-0.30 — 낮음은 main 영역에 파일 목록이 노출되어 instance data 유입. Template 자체는 정상 (Clone/Fork/Find file 등 진짜 structural action)
- 결론: 낮은 raw Jaccard는 대부분 측정 artifact. Template-based 비교가 canonical.

#### Leaf name 재사용 원칙 (v0.6 신규)

**같은 leaf 이름이 여러 scope에 존재 가능**. Scope chrome이 다르면 full path(`user/activity_list` vs `project/activity_list`)는 별 class.

- 같은 concept(event list, snippet list 등)은 각 scope의 chrome 아래에서 독립적 class로 존재
- Widget 재사용 가능성은 Stage B action catalog에서 cross-scope widget identity로 별도 분석 가능
- **예시**: `snippet_list`(global, project), `activity_list`(user, project), `project_list`(dashboard, explore)

#### Grounded observation signals (Stage A.a-c에서 실제로 쓴 것)

- Core widget 단서: `h1/h2` 내용, `li`/`tr` 반복 개수, `form`/`table` 존재 및 개수
- **Action set selector** (broader-first, 2026-04-18 v0.5부터 정식):
  - 1차 기본: `a, button, [role=button], [role=tab]` (**모든 anchor 포함**)
  - 좁은 selector(`button, .gl-button`)는 sidebar anchor를 miss해 artifact 유발 — v0.3~v0.4의 Settings/Issues sub-nav false positive 원인
- Template vs state-gated 판별: empty state에서 DOM inspection (비교 실측)

#### Methodology notes (측정 방법론)

**False-positive 방지 체크리스트** (새 pattern 발견 시):
1. **Broader selector로 재측정** — narrow selector가 artifact 만들었을 가능성 항상 먼저 확인
2. **복수 독립 instance에서 확인** — 같은 pattern이 다른 project·scope에서도 관찰되는지
3. **Sidebar vs main content 구분** — 해당 element가 공통 chrome인지 page-specific인지 DOM container 확인
4. **Empty state와 비교** — data 없을 때도 동일 구조인지 확인 (template level 보장)

**Evolution 원칙** (2026-04-18 v0.5):
- 새 pattern 발견 → **기존 측정 재검증 먼저** → correction vs extension 구분
- **Correction** (이전 틀림): retract + 원인 기록
- **Extension** (이전 옳고 새 pattern 추가): spec 확장, 기존 유지
- 두 경우 모두 version history에 흔적 남김 — spec에서 내용 **삭제 금지, 확장만**

#### 아직 형식화되지 않은 것 (Part C에 기록)

- Core widget 판정 threshold (반복 N 하한 등)
- Action set equality 정의 (label/type tuple vs 집합 등)
- Filter dropdown option vs action 구분의 엄밀한 정의 (현재는 경험적 "option list는 제외")
- 대안 criterion과의 정량 비교

#### Criterion 성격 재확인

- Application은 mechanical/reproducible
- Criterion 선택은 design choice (over-claim 금지)
- 대안 criterion(URL-pattern equivalence, widget-only equivalence 등)과의 trade-off는 Step 8 retrospective에서 기록

---

### Step 3. Naming convention

**Leaf class 이름의 구조 접미사**:
- `_list`: flat 반복 항목 (issue_list, merge_request_list, commit_list, pipeline_list, branch_list, tag_list, ...)
- `_detail`: 단일 entity view (issue_detail, blob_detail, commit_detail, merge_request_detail, tag_detail)
- `_new_form`: 생성 form (issue_new_form, merge_request_new_form, branch_new_form, tag_new_form)
- `settings_*`: settings 관련 form (settings_general, settings_repository, settings_ci_cd, settings_integrations, settings_access_tokens)
- `main`: entity root/landing (project/main)
- `_landing`: multi-section home (global/help_landing)
- 기타: `profile`, `preferences`, `notifications`, `edit`, `wiki`, `topic_list`, `search_page`, `issue_board` 등

**명명 우선순위 (v0.6)**:
1. **우리 convention 우선** — 구조 접미사(`_list`/`_detail`/`_new_form`/`settings_*`)가 적합하면 반드시 적용
2. **그 안에서 페이지 자체 label 존중** — 접두사·중간어는 UI에 노출된 탭·섹션 이름 사용 (agent가 페이지 직접 관측할 때 이름 통일)
   - 예: `dashboard/project_list/yours` — "Yours" 탭 label 존중
   - 예: `dashboard/todo_list/pending` — state 라벨 존중
   - 예: `project/issue_new_form` — "New issue" 버튼 label
   - 예: `account/preferences` — "Preferences" sidebar 항목 label
3. Agent 친화성 목적: 페이지에 보이는 label과 class 이름이 매칭되면 observation-based reasoning 수월

접미사 **선택 경계는 empirical**. 연구자가 각 페이지의 구조 보고 판단. 형식적 decision tree는 현재 없음 → Part C에 기록.

**접두사**: Scope class 이름이 경로의 상위에 놓이므로 leaf class 이름에는 site-prefix 불필요. `project/issue_list`(O) / `project/project_issue_list`(X).

**계층 경로 표기 (path-style)**:
- `{scope-class}/{…}/{leaf-class}[/{variant}]` — root `site` 생략
- Variant 없는 leaf는 variant suffix 생략 (`project/file_list`, `project/commit_list`)
- Variant label은 **site semantic term 차용 허용** (가독성). 분류 기준은 action set이지 label 이름 아님.

**Reason 작성 우선순위**:
1. URL pattern (deterministic, primary)
2. Main content 구조 (h1/h2/li/form/table count, 반복 패턴)
3. Specific UI markers (class 고유 element)

**금지**: title 단독 근거 (SPA back-nav 복원 이슈), h1 단독 (project명 등 공통 텍스트 문제)

---

## Part B. Planned (Stage A.d-g 미실행)

### Step 4. Annotation validation

**Stage A.d — Sample annotation 품질 검증 (rule 추출 전)**

**측정**:
- Group M (수동) vs Group L (LLM) 일치율
- Class 라벨 일치: Cohen's κ
- Reason 품질: 근거 source(URL/구조/widget) 분류 후 분포 확인
- 불일치 case는 근거 비교 후 확정

**Gate** (threshold는 Stage A.d 실행 **직전** pre-commit):
- κ 임계값, 그 선택 근거(literature convention이면 citation), 미달 시 조치(sample 확장/criterion 재검토) 모두 사전 명시
- Post-hoc tuning 금지 — 결과 본 뒤 threshold 맞추는 것은 reviewer-proof 아님
- 현재 어떤 threshold를 쓸지는 결정되지 않음 (Part C)

---

### Step 5. Rule extraction

**Stage A.e — Confirmed annotation → rule 도출**

**중요**: Extraction **방법**(regex·query key·action signature 도출 절차)은 site-agnostic. 결과 **rule**은 site-specific.

**Output**:
- URL path regex dict: `{base_class: compiled_regex}`
- Variant-making query key dict: `{base_class: [query_keys]}`
- Action signature matcher (variant boundary 판정용, 선택)

**절차**:
- Sample의 최종 class → URL path 공통 패턴 추출
- Variant별 query key 수집
- Core widget 특성(li count threshold 등)은 **보조 signal**로만, rule primary는 URL

---

### Step 6. Rule application

**Stage A.f — Frozen KG 3,040 StatePattern에 rule 적용**

**Input**: `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json`의 state_patterns list
**Output**: 각 SP에 class path 태그 (`{sp_id: class}`)

**처리**:
- 각 SP의 `url_template` + `identity_query_params`에 rule 적용
- Unmatched SP는 `None` 태그 후 별도 리스트화 → Stage A.f.post에서 분석

---

### Step 7. Rule output validation

**Stage A.f.post — Rule 결과 자체의 품질 검증**

**Metrics**:
- Coverage: 전체 SP 중 class 부여된 비율 (%)
- Compression ratio: |URLs| / |classes|
- Per-family distribution: class family별 SP 수
- Unmatched analysis: 미분류 SP 샘플링 후 rule gap 파악
- Consistency: 같은 input으로 rule 재실행 시 동일 output (deterministic 확인)

**Gate** (threshold는 Stage A.f.post 실행 **직전** pre-commit):
- Coverage / compression 최소치 사전 명시
- Post-hoc tuning 금지
- 현재 어떤 threshold를 쓸지는 결정되지 않음 (Part C)

---

### Step 8. Protocol retrospective

**Stage A.g — 실행 전체 회고 + protocol 최종 정리**

**기록**:
- Stage A.a-f 실행 중 발견된 decision points
- Alternative criterion 고려 이력
- Deferred issues 최종 목록
- 다른 사이트에 적용 시 요구되는 prerequisite (auth, rate limit, SPA 여부)

---

## Part C. Open decisions / discovered during execution

### Version history

- **0.6 (2026-04-21)** — Stage A verify 결과 반영. (1) Instance variance 판정 원칙 추가 — raw Jaccard 대신 template 교집합 사용. (2) Leaf name 재사용 원칙 — 같은 이름이 여러 scope에 독립적으로 존재 가능. (3) Step 3 명명 우선순위 확정: convention 접미사 first, 페이지 UI label respect second (agent 친화성 목적).
- **0.5 (2026-04-18)** — `account` scope 신설 (`/-/profile/*`의 14-action 전용 사이드바 확인). Settings/Issues sub-nav 주장 retract (broader-selector 재측정으로 artifact 판명). Methodology notes 추가 (broader-selector first, false-positive 체크리스트, correction vs extension 구분).
- **0.4 (2026-04-18)** — Step 2 Recursive class inheritance tree로 일반화 (고정 3-tier → 가변 N-tier, empirical 조건 명시). Class vs Variant 분리 기준 추가(Q1 core widget → Q2 action 축 판정).
- **0.3 (2026-04-18)** — Step 2 Scope-first 3-tier 체계 전환. 실증 근거(project sidebar 57 shared, dashboard header 28 shared). 23 annotation 재명명.
- **0.2 (2026-04-18)** — Step 2 확장: level별 분류 표, parent-variant semantics(bottom-up derived), 5 core principles, 경계 case 처리.
- **0.1 (2026-04-18)** — initial provisional draft.

### Correction log

- **[2026-04-18, v0.4→v0.5]** "Settings sub-nav 존재" 주장 **retract**
  - 원인: v0.3~v0.4의 action set selector(`button, a[role=button], .gl-button`)가 일반 `<a>` anchor miss → project 사이드바 링크가 base 측정에서 누락 → settings 페이지에서 같은 링크가 "beyond base"로 잘못 측정
  - 재측정(broader selector `a, button, [role=button], [role=tab]`): `General`, `Integrations`, `Merge requests`, `Usage Quotas`, `Webhooks`, `Access Tokens` 전부 project 모든 페이지 사이드바에 S1로 존재 → 전용 sub-nav 아님
  - 수정: `project/settings_*` flat 유지, internal node 없음
- **[2026-04-18, v0.4→v0.5]** "Issues family sub-nav 존재" 주장 **retract**
  - 원인: 동일
  - 재측정: `List`, `Boards`, `Milestones`, `Service Desk`, `Labels` 전부 project 모든 페이지 사이드바에 S1 → 전용 sub-nav 아님
  - 수정: `project/issue_list`, `project/issue_board`, `project/issue_detail`, `project/issue_new_form` flat
- **[2026-04-18, v0.4→v0.5]** Profile sub-nav 주장 **confirmed (extension)**
  - 재측정: `/-/profile/*` 3페이지에서 14 action 전용 사이드바 확인 (Account/Applications/SSH Keys 등), `/byteblaze`·`/dashboard`·`project_main`에는 부재
  - 확장: 새 scope `account/` 신설 (`user/`와 구분 — public view vs own settings)

- **[2026-04-21, Stage A verify → v0.6]** Instance variance 분류 **confirmed (measurement methodology correction)**
  - 원인: Broader selector가 instance-level data(파일명, SHA, 사용자명, count) 포함 → raw Jaccard 낮게 나옴
  - 재측정: Template(교집합) 기반 비교 — `project/issue_list` template 15, coverage 0.75 (webring/a11yproject instance); `project/main` template 17 (Clone/Fork/Find file 등 진짜 structural)
  - 수정: 분류 변경 없음. 측정 원칙만 바꿈 (raw Jaccard → template 교집합 기반)
- **[2026-04-21, v0.5→v0.6]** `user_activity` class 위치 **confirmed**
  - 실증: `/byteblaze`(Overview tab)와 `/users/byteblaze/activity`(Activity tab)는 user scope 내 동등한 leaf (둘 다 user profile의 탭)
  - 측정: `user/profile` vs `user/activity_list` widget 차이 확인 (Q1: 다른 core widget → sibling 분류 정당)
  - 수정: 분류 변경 없음 (sibling leaf 구조 유지)

---

**Pre-commit 결정 필요**:

1. **[Stage A.d 직전]** Annotation validation κ threshold + 근거 citation + 미달 조치 — 사전 명시 후 Stage A.d 실행
2. **[Stage A.f.post 직전]** Rule output coverage 최소치 + compression 기대치 — 사전 명시 후 Stage A.f.post 실행

**Stage A.d-g 진행 중 해소 예정**:

3. Core widget 판정 threshold (반복 N 하한, label 일치 기준 등) — 현재 직관, Stage A.d 불일치 case에서 도출
4. Action set equality 정의 — (label, element_type) tuple 집합 equality? 순서 무관? invisible button 포함?
5. 접미사 decision tree — `_list` vs `_landing` vs `_main` 판정 경계
6. 대안 criterion (URL-pattern-only, widget-only)과의 trade-off 정량 비교 — Step 8 retrospective에서 기록
7. Filter dropdown option vs action 구분의 엄밀 정의 (현 경험적 제외 규칙을 structural rule로 변환)
8. Empty state DOM inspection 자동화 — 현재 ad-hoc Playwright 스크립트

**Role division**:

7. 각 Step에 대해 자동화 script vs 연구자 판단 vs LLM assistance 비율 명시 — Stage A.g에서 retrospective로 정리

---

## Appendix A. Process diagram

```
[Site URLs]
    ↓  (Step 1: Observation)
[Per-URL AXTree + metadata]
    ↓  (manual / LLM-assisted annotation)
[Sample annotations with class labels]
    ↓  (Step 4: Annotation validation)
[Confirmed sample]
    ↓  (Step 5: Rule extraction)
[URL regex + variant rules]
    ↓  (Step 6: Rule application)
[Full-site class taxonomy]
    ↓  (Step 7: Rule output validation)
[Validated taxonomy + metrics]
    ↓  (Step 8: Retrospective)
[Protocol v1 finalized]
```

## Appendix B. Traceability

| Protocol Step | Script / Artifact |
|---|---|
| Step 1 | `scripts/validation/v1_a_collect_axtrees.py`, `output/validation/V1_pages/` |
| Step 2-3 | `docs/validation/V1_annotation_filled.md` (convention), `docs/validation/V1_deferred_issues.md` |
| Step 4 | (TBD: `scripts/validation/v1_d_agreement.py`) |
| Step 5 | (TBD: `scripts/validation/v1_e_rule_extract.py`) |
| Step 6 | (TBD: `scripts/validation/v1_f_apply_rules.py`) |
| Step 7 | (TBD: `scripts/validation/v1_f_post_validate.py`) |
| Step 8 | (TBD: `docs/validation/V1_g_retrospective.md`) |
