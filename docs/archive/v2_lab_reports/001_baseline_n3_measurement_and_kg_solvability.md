# Lab Report v2-001 — Baseline N=3 측정 + KG-solvability 분석

**날짜**: 2026-04-12
**목적**: lab 005 baseline (+ memo 강화 + extract verification) 위에 14 task × N=3 회 측정을 수행하고, 각 fail의 *원인*을 분석하여 **본 연구의 KG가 baseline의 약점을 *얼마나* 해결할 수 있는지를 측정 시작 전에 데이터로 backing**한다. 이는 본 연구의 가치 명제(KG가 baseline을 향상시킨다)를 *측정 후 사후 정당화*가 아니라 *측정 전 사전 검증*으로 만든다.

**Baseline branch**: `baseline/lab005-restoration` (commit `a5e5f8d` 시점)
- lab 005 v3 코어 (Tool Use API + sub-goal/checkpoint/retry/replan/verification + 6단계 클릭 매칭 + DOM 안정화 + NAVIGATE final URL check + graduated retry)
- + 2026-04-12 memo 강화 (action tool optional `memo` field + `_verify_done`의 task_notes 검토)
- + 2026-04-12 extract verification (4-step format check + plural-aware inclusion)

---

## 측정 환경

- **에이전트**: baseline branch HEAD (`a5e5f8d`)
- **LLM**: OpenAI gpt-5-codex (`LLM_PROVIDER=openai`, `OPENAI_MODEL=gpt-5-codex`)
- **벤치마크**: WebArena-Verified GitLab 14 task
  - task IDs: 44, 45, 102, 132, 156, 169, 205, 258, 259, 293, 308, 339, 357, 390
- **반복**: N=3 (3 trials)
- **task 사이 env reset**: *모든 task 사이에 `webarena-verified env start --site gitlab` 실행* — 이전 task가 남긴 sort/filter/state 영향을 제거하고 *공정한 측정* 보장
- **모드**: headless
- **평가**: `webarena-verified eval-tasks`로 NetworkEventEvaluator + AgentResponseEvaluator

---

## 결과 매트릭스

| Task | t1 | t2 | t3 | pass/3 | type | intent (요약) |
|---|---|---|---|---|---|---|
| 44 | ✅ | ✅ | ✅ | **3/3** | NAVIGATE | Open my todos |
| 45 | ❌ | ❌ | ❌ | **0/3** | NAVIGATE | filtered open issues |
| 102 | ❌ | ❌ | ❌ | **0/3** | NAVIGATE | open issues for byteblaze/a11y-syntax-highlighting |
| 132 | ✅ | ✅ | ✅ | **3/3** | RETRIEVE | how many commits did kilian make to a11yproject |
| 156 | ✅ | ✅ | ✅ | **3/3** | NAVIGATE | merge requests assigned |
| 169 | ❌ | ❌ | ❌ | **0/3** | RETRIEVE | project_id(s) most stars |
| 205 | ✅ | ✅ | ✅ | **3/3** | RETRIEVE | how many commits did kilian make for current project |
| 258 | ❌ | ❌ | ❌ | **0/3** | NAVIGATE | public projects listing |
| 259 | ✅ | ✅ | ✅ | **3/3** | RETRIEVE | RSS feed token |
| 293 | ❌ | ✅ | ✅ | **2/3** | RETRIEVE | SSH clone URL |
| 308 | ❌ | ❌ | ❌ | **0/3** | RETRIEVE | username with most commits to primer/design |
| 339 | ✅ | ✅ | ❌ | **2/3** | NAVIGATE | bug filter open issues |
| 357 | ✅ | ✅ | ✅ | **3/3** | NAVIGATE | merge requests for review |
| 390 | ✅ | ✅ | ✅ | **3/3** | MUTATE | Post "lgtm" |

**Overall: 25/42 = 59.5%**

**Stable PASS** (3/3): 44, 132, 156, 205, 259, 357, 390 = **7 task**
**Stable FAIL** (0/3): 45, 102, 169, 258, 308 = **5 task**
**비결정적**: 293 (2/3), 339 (2/3) = **2 task**

### 비교 (참고)

| 측정 | 성공률 |
|---|---|
| lab 005 v5 (4 task subset만) | 4/4 (편향) |
| lab 006 Compact Prior | 8/14 = 57.1% |
| lab 006 Improved Prior | 5/14 = 35.7% |
| **본 baseline (lab 005 + memo + extract verification)** | **25/42 = 59.5%** (task 단위 7-9/14) |

본 baseline은 lab 006 Compact Prior와 동등하거나 약간 향상. KB layer를 모두 제거한 *순수 v3 baseline + cognitive aid 강화*가 lab 006 *Prior 주입* baseline을 따라잡거나 능가함을 보여줌.

---

## 실패 원인 분석 + KG-solvability 분류

각 fail task의 evaluator failure data + agent log를 분석하여 *정확한 원인*을 식별하고, 본 연구의 *Hierarchical SiteKG*가 그 원인을 해결할 수 있는지 카테고리로 분류:

- **A (KG-solvable HIGH)** — KG의 직접 정보 (PageNode description / WidgetNode locator+side_effect / NavigationEdge)가 명시되면 *바로* 해결
- **B (KG-solvable MID)** — KG가 plan 구조 또는 widget 후보를 강화하지만 LLM reasoning이 여전히 필요
- **C (KG-unsolvable)** — task ambiguity, LLM 본질적 한계, baseline 한계 — KG로 해결 안 됨

### Task 45 (NAVIGATE — filtered open issues) → A

**원인 (deterministic, 3/3)**: agent가 매 trial에서 *동일하게* `?sort=created_date&state=opened&first_page_size=20` query를 추가. expected는 query 없는 기본 issues 페이지.

**왜**: lab 006 PageType description ("Default already shows open issues, newest first")이 폐기됐고, baseline은 issues 페이지의 *기본 상태가 이미 open + newest*임을 모름. 그래서 *명시적으로* sort/state filter를 추가.

**KG로 어떻게 해결**: `issues_list` PageNode의 description에 "기본이 open + newest first 정렬"을 명시. LLM이 plan 단계에서 *추가 sort/filter sub-goal 생성을 회피*. 직접 KG-solvable.

### Task 102 (NAVIGATE — byteblaze/a11y-syntax-highlighting의 open issues) → B

**원인 (deterministic, 3/3)**: agent가 *현재 프로젝트* (`a11yproject/a11yproject.com`)의 issues로 navigate. task가 명시한 `byteblaze/a11y-syntax-highlighting`로 안 감. 두 번째 evaluator는 `label_name[]=help wanted` filter도 요구.

**왜**: agent가 task intent의 *프로젝트 식별*을 부분 수행. 또한 label filter 적용 못 함.

**KG로 어떻게 해결**: 두 layer.
- *프로젝트 navigation*: NavigationEdge `dashboard → project_overview` + URL placeholder `/{ns}/{project}`. KG가 *path 형태*를 명시하면 LLM이 url 구성 가능. 단 *어느 프로젝트인지*는 task intent 해석 필요 → LLM 영역.
- *Label filter*: project_overview 또는 issues_list page의 `Label filter` widget을 명시. KG-solvable.

부분적 KG-solvable. 프로젝트 식별 단계는 LLM 의존.

### Task 169 (RETRIEVE — project_id of personal projects with most stars) → B

**원인 (deterministic, trial별 다른 잘못된 ID)**:
- t1: `[182]`
- t2: `[183]`
- t3: `[179]`
- 정답: `[187, 183]`

매 trial에서 잘못된 프로젝트 페이지에서 ID 추출. t2가 부분 정답 (183 포함)이지만 187 누락. *비결정성 + 일관된 잘못된 프로젝트 선택*.

**왜**: agent가 personal projects 페이지에서 별점이 가장 높은 두 프로젝트(empathy-prompts, millennials-to-snake-people)를 식별하지만, 그 *프로젝트 페이지를 실제로 방문*하지 않거나 *잘못된 프로젝트*로 감. project_id는 페이지 방문 후 *Copy project ID* 영역에서만 보임.

**KG로 어떻게 해결**: NavigationEdge `personal_projects → project_overview` 명시 + WidgetNode `Copy project ID` 명시 + WidgetNode side_effects에 "project ID는 project_overview 페이지에서만 보임"을 자연어 명시. plan 단계에서 LLM이 *각 후보 프로젝트마다 visit sub-goal*을 자연스럽게 포함하도록 유도.

단, *비결정성*은 LLM 본질적 한계. KG가 *plan 구조*를 강화하지만 *완전 결정성*은 어려움. 부분 KG-solvable.

### Task 258 (NAVIGATE — public projects listing) → A

**원인 (deterministic, 3/3)**: agent가 매 trial에서 `?visibility_level=20` query를 *못 추가*. expected는 `/explore?visibility_level=20`.

**왜**: lab 006 ActionSchema description ("Use goto /explore?visibility_level=20")이 폐기됐고, baseline은 *visibility filter*가 query parameter로만 지정 가능함을 모름. 페이지 내 visibility filter widget을 안 찾음.

**KG로 어떻게 해결**: `explore_projects` PageNode의 url_patterns에 `/explore?visibility_level=20` 형태 명시 또는 별도 PageNode `explore_projects_public`을 정의. WidgetNode `Public visibility filter`의 side_effect에 "URL에 ?visibility_level=20 추가"를 명시. 직접 KG-solvable.

### Task 293 (RETRIEVE — SSH clone URL) → A

**원인 (비결정성, 1/3 fail)**: t1에서 HTTPS clone URL (`http://...convexegg/...`)을 SSH로 잘못 추출. t2/t3는 PASS (정확한 SSH URL).

**왜**: project_overview 페이지의 clone 영역에 *HTTPS와 SSH 두 옵션*이 함께 있음. agent가 *어느 readonly input이 SSH인지* 비결정적으로 선택. baseline의 readonly input 관측이 두 input의 차이를 *형식*으로 구분 못 함.

**KG로 어떻게 해결**: `project_overview`에 `Clone with SSH` 와 `Clone with HTTPS`를 *별도 WidgetNode*로 명시 + 각각의 description에 protocol 형식 명시. LLM이 task의 "SSH"를 widget description과 *deterministic 매칭*. 비결정성 → 결정성. 직접 KG-solvable.

### Task 308 (RETRIEVE — username with most commits to primer/design) → C

**원인 (deterministic, 3/3)**: agent가 매 trial에서 *display name* 반환:
- t1, t3: `["Cole Bemis"]`
- t2: `["Mike Perrotti", "Cole Bemis", "Emily Brick"]`
- 정답: `"shawn.allen@github.com"` (이메일 형식)

**왜**: 두 가지 문제.
1. task가 "username"을 요구하는데 정답이 *email 형식*. WebArena의 GitLab 인스턴스에서 "username"을 email로 정의한 듯하지만 task intent에는 안 명시. *task 자체의 ambiguity*.
2. agent가 most commits 결정도 부정확 (실제 정답인 shawn.allen이 nominee 아님).

**KG로 어떻게 해결**: contributors page widget이 *who* 식별을 부분 도움. 그러나 *username 형식 결정* (display name vs handle vs email)은 task intent 해석. KG가 도움 안 됨. *task ambiguity가 baseline 한계가 아니라 task 정의의 약점*.

KG-unsolvable. baseline의 *intrinsic limitation*.

### Task 339 (NAVIGATE — bug filter open issues) → B

**원인 (비결정성, 1/3 fail)**: t1/t2 PASS. t3에서 label filter 적용 안 함 — issues 페이지에 도달했지만 `?label_name[]=bug` query 없음.

**왜**: agent가 label filter widget을 *대부분 사용*하지만 가끔 빠뜨림. baseline의 label filter 사용이 *비결정적*.

**KG로 어떻게 해결**: `issues_list` page의 `Label filter` widget을 명시 + 그 side_effect에 "URL에 ?label_name[]= 추가"를 명시. plan 단계에서 LLM이 *label filter 사용 sub-goal*을 더 일관되게 생성. 비결정성 감소.

부분 KG-solvable.

---

## 분류 요약

| 카테고리 | task | 카운트 | 비율 |
|---|---|---|---|
| **A — KG-solvable HIGH** (직접 해결) | 45, 258, 293 | 3 | 43% (of fails) |
| **B — KG-solvable MID** (plan 구조 강화) | 102, 169, 339 | 3 | 43% (of fails) |
| **C — KG-unsolvable** (task ambiguity / LLM 한계) | 308 | 1 | 14% (of fails) |
| **합계 (fail task)** | | **7** | 100% |

**fail 7 task 중 6 task (86%)가 KG로 해결 가능** (A 또는 B). 그 중 3 task (43%)는 *직접 KG-solvable* — KG 정보만 추가하면 즉시 해결되는 종류.

---

## 본 연구 가치 명제와의 관계

본 연구의 가설(`docs/v2_lab_reports/01_skg_web_agent_proposal.md` §2 H1'):
> Hierarchical SiteKG (page graph + widget graph + selective retrieval)가 baseline 위에 적용되면 GitLab 14 task의 평균 성공률이 통계적으로 유의미하게 향상된다.

본 측정은 이 가설을 *측정 시작 전부터* 데이터로 backing:
1. baseline의 fail은 *대부분 deterministic* — 비결정성 핑계가 아니라 *systemic weakness*
2. systemic weakness의 *대부분*은 KG의 4가지 minimum viable 정보 (connectivity / conditional state / causal effects / stable references)로 해결 가능
3. *직접 해결 가능한 3 task* (45, 258, 293)만 가정해도 baseline 50% → 71%로 향상 예상
4. *전체 6 KG-solvable이 모두 해결*되면 baseline 50% → 93%까지 향상 가능 (이론 상한)

이는 본 연구의 KG가 *진짜* baseline의 약점을 다룬다는 *independent evidence*. 측정 후 사후 정당화가 아니라 *측정 전 사전 검증*.

### 정직한 caveat

1. **N=3은 여전히 작음**. 본 측정 후 §5의 정식 측정 (각 조건 × 14 task × N=3 = 42 측정점)으로 확정 검증 필요.
2. **카테고리 A/B 분류는 *추정***. 실제 KG 적용 후 측정 결과가 분류와 다를 수 있음. 특히 카테고리 B는 LLM reasoning에 의존이 커서 이론적 잠재력만 보여줌.
3. **이론 상한 93%은 비현실적**. 실제로 KG가 모든 약점을 *완벽히* 다루지 않음. 카테고리 B의 부분적 효과 + 새 회귀 (KG가 noise를 추가) 가능성 있음.
4. **task 308 (C 카테고리)**는 본 baseline의 *intrinsic limitation*. KG로도 해결 안 되며 *전체 14 task의 천장이 13/14 = 93%*임을 시사.

---

## 다음 단계

### M0 plan 다듬기 (즉시)

본 측정의 분석 결과를 M0 plan에 반영:
1. **gitlab.yaml 시드의 widget 우선순위**: A 카테고리 task부터 (45 → issues_list base description, 258 → explore_projects url filter, 293 → SSH/HTTPS clone widgets 별도)
2. **B 카테고리 task의 KG 정보**: NavigationEdge (102, 169) + Label filter widget (339)
3. **M0 검증**: M0 자체는 *데이터 구조 + 시드 작성*만이고, *측정*은 별도. 그러나 시드 작성 시 *실패 task 중심*으로 우선순위.
4. **C 카테고리 (308)**는 시드에 박지 않음 — KG로 해결 안 되는 task.

### 정식 측정 (M1+ 또는 별도)

M0 후 M1에서 Phase 1 retrieval + 조건 B-F 통합. 그 후 6 조건 × 14 task × N=3 정식 측정.

### 본 lab report의 데이터

`output/14task_t1`, `output/14task_t2`, `output/14task_t3`에 raw 측정 데이터 보존. 추후 reviewer 검증 가능.

---

## 부록 — 상세 데이터

상세 trial별 fail 원인 (evaluator 출력 + agent 결과):

```
Task 45 (3/3 fail, NetworkEventEvaluator):
  expected: /a11yproject/a11yproject.com/-/issues query_params {}
  actual (all 3 trials): /a11yproject/a11yproject.com/-/issues/?sort=created_date&state=opened&first_page_size=20

Task 102 (3/3 fail, NetworkEventEvaluator):
  expected: ^/byteblaze/a11y-syntax-highlighting/-/issues.* + label_name[]=help wanted
  actual (all 3): /a11yproject/a11yproject.com/-/issues (잘못된 프로젝트)

Task 169 (3/3 fail, AgentResponseEvaluator):
  expected: [187, 183]
  actual: t1=[182], t2=[183], t3=[179]

Task 258 (3/3 fail, NetworkEventEvaluator):
  expected: /explore?visibility_level=20
  actual (all 3): /explore (또는 /explore/projects), query_params {}

Task 293 (1/3 fail, AgentResponseEvaluator):
  expected: git@__SSH_HOST__:convexegg/super_awesome_robot.git
  actual t1: http://metis.lti.cs.cmu.edu:8023/convexegg/super_awesome_robot.git (HTTPS)
  t2/t3: PASS

Task 308 (3/3 fail, AgentResponseEvaluator):
  expected: shawn.allen@github.com
  actual: t1/t3 = ["Cole Bemis"], t2 = ["Mike Perrotti", "Cole Bemis", "Emily Brick"]

Task 339 (1/3 fail, NetworkEventEvaluator):
  expected: /-/issues + label_name[]=bug
  actual t3: /-/issues query_params {}
  t1/t2: PASS
```
