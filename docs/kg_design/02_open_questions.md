# 02. 설계 쟁점과 결정 로그

`docs/kg_design/01_references_summary.md §4`에서 뽑은 4개 쟁점을 정리한다. 각 쟁점에 대해 결정이 내려진 상태, 결정 근거, 남은 하위 문제를 기록한다.

순서는 B(주장 먼저): #2 → #3 → #1 → #4.

---

## 쟁점 #2 — "planning substrate"의 조작적 정의

**질문**: KG가 planner에게 제공하는 것이 retrieval과 어떻게 구별되는가. 어느 축에서 차별성을 주장할 것인가.

### 2-1. (a) 정보 종류 — 결정

- **결정**: KG는 declarative facts retrieval이 아니라 **procedural/executable site knowledge**를 제공한다. 구체적으로는 **A2(state-transition + URL schema + canonical route)** 계열.
- **Level A1(procedural UI click sequence)은 채택하지 않음**. 근거: Phase 1 pilot에서 LLM이 click sequence는 대체로 스스로 찾아냄(task 339의 sub-goal 2·3 verified). 이는 현세대 LLM이 DOM을 보고 저수준 UI action을 합성할 수 있음을 시사.
- **Level B(grounding hint)는 보조 역할로만**. 근거: pilot 6건 중 pure grounding 실패는 169 하나. B의 가치 공간이 좁음.
- 근거 문서: `docs/kg_design/04_baseline_failure_analysis.md §3~5`.

### 2-2. (c) 시점 — 결정

- **결정**: task 단위 1회 retrieval이 아니라 **plan 생성 단계와 sub-goal 경계의 runtime 단계 양쪽에서** KG를 질의한다.

### 2-3. (b) planner가 KG 출력을 사용하는 방식 — 결정

- **결정**: **(b) Plan rewrite를 주 메커니즘으로 + (c) 실행 중 early-termination validation을 얹는 hybrid**. 순수 (a) retrieval-style은 채택하지 않음.
- **근거**:
  1. m0-sitekg가 사실상 (a) retrieval-style 주입이었고 net negative로 끝남. 본 연구 자체 데이터로 (a)는 기각.
  2. (b)는 구현 risk가 제한적이고, AWM·AutoGuide와 차별성이 분명. "plan을 재구조화하는 KG 변환자"는 기존 memory 계열에 없는 역할.
  3. (c) 단독은 plan 시점 지식이 필요한 case(task 308의 `/-/graphs/<branch>` route)를 커버하지 못함. 단 runtime validation의 이점(task 339의 redundant sub-goal 조기 종료)은 포기하기 아까움.
  4. hybrid의 "planning substrate" 조작적 정의:
     - KG 출력이 facts가 아니라 **plan 자체에 대한 structural operator**(rewrite)와 **상태 판정자**(validate)
     - retrieval과 구별되는 핵심은 **KG 출력물이 LLM context에 삽입되는 지식이 아니라 plan tree에 적용되는 연산**이라는 점

- 근거 문서: `docs/kg_design/04_baseline_failure_analysis.md`, 2026-04-15 설계 대화.

### 2-4. 조건부

- **KG 신뢰도 경계가 스키마의 1급 시민이 되어야 함**. 잘못된 rewrite는 plan을 악화시킴 → verified/unverified 표식이 schema에 필수.
- Level B는 보조로 유지 여지만 열어둠. 최소 viable KG 단계에선 포함하지 않고, 필요성이 추가 증거로 지지되면 나중에 붙임.

### 2-5. 잠정성

- 위 결정은 개발 초기 pilot(비공식 baseline, 14 task failure 6건)에서 나온 개발 로그 근거. 이 pilot은 **paper에 인용되지 않는다**(`docs/kg_design/04_baseline_failure_analysis.md` §경고 참조).
- 새 baseline의 첫 공식 측정에서 (a)(c) 차원 가설이 크게 뒤집히면 재검토.

### 2-6. "planning substrate"의 최종 조작적 정의 (3요소)

KG의 출력은 planner의 context에 삽입되는 facts가 아니라 다음 세 가지로 구성된다:

1. **Structural operator**: plan tree에 적용되는 연산 (b) rewrite. sub-goal sequence를 변형·축약·삽입한다.
2. **State predicate**: 실행 중 sub-goal 경계에서 호출되는 (c) state_matches 판정자. LLM context에 삽입되지 않고 실행 제어만 바꾼다.
3. **Adaptive intervention policy**: trust 레벨에 따라 rewrite 개입 강도를 modulate. verified → aggressive, declared → rewrite + validate, inferred → 보류. Retrieval 시스템에 대응물 없음.

이 세 요소 중 어느 것도 일반 retrieval 시스템에서 다루지 않는다는 것이 "planning substrate"의 핵심 근거.

### 2-7. 예상 비판과 5축 반박 — "rewrite-collapses-to-navigate_to"

**예상 비판**: "KG의 실질 기여는 canonical URL 계산에 불과하며 'planning substrate'는 과장이다. 특히 WebArena NAVIGATE 편향 때문에 URL emission만으로 성능이 나오는 것으로 보인다."

**인정할 부분**:
- Simple NAVIGATE task에서 rewrite 출력이 `navigate_to(URL)`로 축약되는 비율이 높을 것으로 예상.
- WebArena-Verified GitLab subset이 NAVIGATE 편향인 것은 사실.
- 따라서 표면상 "URL emission 최적화"로 보일 수 있음.

**반박 5축**:
1. Collapse 자체가 `route_to` + `final_state` + `state_matches` + `emit_url` + URL 정규화의 산출물. 단순 fact retrieval은 이 중 어느 연산도 수행하지 않음.
2. Trust-driven adaptive rewrite 정책(2-6 §3)은 retrieval의 어느 프레임에도 자연스럽게 매핑되지 않음.
3. Runtime validation (c)는 **LLM context에 어떤 것도 삽입하지 않음** → retrieval 프레임 밖임을 가장 분명히 보이는 축.
4. Collapse는 URL이 target을 fully identify하는 특수 케이스에서만 발생. MUTATE, AJAX, session-dependent 상태에서는 multi-step rewrite 유지됨 → 논문에서 NAVIGATE·MUTATE subset 분리 분석으로 드러냄.
5. Trust evolution(실행 성공·실패로 승격·강등)은 retrieval에 대응물 없는 online planning 요소.

### 2-8. Empirical commitment — 필수 ablation

쟁점 #2의 주장을 empirical로 지지하려면 다음 ablation이 필수:

- **Ablation "URL-emission-only"**: baseline + "intent → KG 조회 → canonical URL 한 번 goto" 만 추가한 가장 단순 변형.
  - 이 ablation과 본 연구의 full (b)+(c) hybrid 성능이 **크게 차이나면** planning substrate 주장 지지.
  - 비슷하면 주장 약화.
- NAVIGATE subset / MUTATE subset 분리 보고 필수. NAVIGATE에서 collapse 비율 공개.
- Continual 셋업(같은 사이트 반복 배포) 결과는 본 실험 단계에서 보고.

### 2-9. Plan B — 실험이 위 주장을 지지하지 않을 경우

Empirical 결과가 위를 지지하지 않으면(특히 URL-emission-only ablation이 match하면), **"planning substrate" 프레이밍을 포기하고 "KG-guided canonical URL emission for web agents"로 retreat**. 이 경우 기여는 여전히 유효하나 범위가 좁아짐. 논문을 방어적으로 작성하기보단 실험 결과에 따라 claim의 폭을 조정하는 원칙.

---

---

## 쟁점 #3 — Minimum viable KG 스키마 (진행 중)

**질문**: (b) plan rewrite와 (c) early-termination validation을 실제로 지원하는 최소 KG 스키마는 무엇인가. 과거 m0-sitekg의 `PageNode / WidgetNode / NavigationEdge / InteractionEdge`와 무엇이 같고 무엇이 달라져야 하는가.

### 3-1. Primitive 질의 집합 — 결정

쟁점 #2의 (b)+(c) hybrid가 필요로 하는 질의를 정리하면 4개:

| 질의 | 입력 | 출력 | 비고 |
|---|---|---|---|
| `route_to(target_info)` | InfoType 또는 intent | sub-goal sequence / URL 목록 | primitive |
| `final_state(plan)` | sub-goal sequence | 예측 StatePattern 인스턴스 | primitive |
| `state_matches(current, target)` | URL + DOM, target spec | (bool, bindings) | primitive |
| `emit_url(state_pattern, bindings)` | StatePattern + bindings | 실제 URL | primitive(pilot에서 추가). evaluator 호환 URL을 emit하기 위해 필요 |

`can_merge(plan)`은 `final_state + state_matches`로 derive 가능하므로 primitive에서 제외.

### 3-2. State 표현 해상도 — 결정

- **Level 1 (URL only)** 채택. StatePattern = (URL path template, identity query param schema).
- Level 2(observable predicates)는 스키마에 **확장 슬롯만** 남기고 지금은 채우지 않음. MUTATE in-place AJAX 패턴이 새 baseline 측정에서 다수 관찰되면 해당 StatePattern에 한해 promotion.
- 근거: pilot 6건 모두 URL-resolvable. Minimum viable KG 원칙("DOM이 표현 못 하는 것만 박는다")과 정합.

### 3-3. URL 정규화 — 결정

- **Site config + StatePattern schema의 hybrid**로 분산.
- 8차원을 다음처럼 배분:

| 차원 | 저장 위치 |
|---|---|
| path parameter 추출 | StatePattern.path_params |
| query param 순서 무관 | 연산 기본 동작 |
| URL encoding 정규화 | site_config.url_decode (aggressive) |
| default value | StatePattern.identity_query_params[*].default |
| parameter role 분리 | StatePattern.identity_query_params (identity만 명시) + site_config.decorative_params (사이트 공통 denylist) |
| multi-value array param | StatePattern.identity_query_params[*].type=multi_string |
| identity token 치환 | site_config.identity_tokens (런타임 치환) |
| path alias | site_config.path_aliases |

- `emit_url`은 StatePattern.canonical_emit_order를 따라 직렬화. default와 같은 값은 생략하지 않음(evaluator 호환 보수적 선택).
- 초기 구축은 **3단계 hybrid pipeline**:
  1. **Playwright auto-crawl** → url_template·path/query param 이름·관찰된 leads_to 엣지를 수집. 결과는 `source="crawl"` → `trust="verified"`.
  2. **LLM-assisted derivation** → 관찰된 URL schema로부터 InfoType 후보와 `realizes` 매핑, 사이트 공통 일반화를 추출. 결과는 `source="llm"` → `trust="inferred"`.
  3. **Manual verification** → 1·2단계 산출물을 사람이 검증·보정·승격. default 값·role·alias·identity token 등 직접 관찰이 어려운 항목은 이 단계에서 채움. 결과는 `source="manual"` → `trust="declared"`.
- 시간 추정은 기재하지 않음. 퀄리티 기준(커버리지·trust 분포·빌드 메타데이터 재현성)이 구축 완료의 판정 기준이다.

### 3-4. InfoType 범위와 매칭 — 결정

- **Granularity**: 도메인 명사구 수준 (β). 파라미터·상태 필터는 InfoType 자체가 아니라 **realizes 호출의 bindings**로 전달.  
  예: `issues_list`, `merge_requests_list`, `commits_history`, `profile_settings` 등. 사이트당 약 15~25개 추정.
- **Intent → InfoType 매칭**: LLM classification (후보 2). intent + InfoType 카탈로그를 LLM에게 주고 `(InfoType, parameter_bindings)`를 동시에 받음. 1 LLM 호출/task 수용. 쟁점 #1(executable query)의 입력측과 통합됨.
- **InfoType ↔ StatePattern 관계**: **1:N**. 같은 추상 개념이 파라미터에 따라 여러 구체 상태로 실현됨. realizes 엣지는 binding context에 의해 해소.
- **초기 구축**: GitLab 전체 표면을 커버하는 **포괄 catalog (~20~30 InfoType, ~30~50 StatePattern)를 baseline 측정 전에 확정**. 이후 실험 task 실패를 보고 catalog를 수정하지 않는다 (hindsight bias 차단). Catalog 작성 범위는 실험 task 분포가 아니라 사이트의 주요 기능 표면이 기준.
- **커버리지 보고 의무**: 50 task 중 Hook A가 tool을 성공적으로 호출하는 비율(= KG-addressable subset 크기)을 결과에 명시. catalog가 task에 맞춰져 있지 않음을 드러내는 objectivity 지표 (`06_evaluation_protocol.md §3` 참조).

### 3-5. Action의 범위와 파라미터화 — 결정

- **KG action의 경계**: **state-transition을 일으키는 action만** KG에 포함. URL 변경 또는 추적 대상 observable 변경이 기준. 순수 UI 조작(scroll, hover, intermediate click)은 executor에게 위임하고 KG 밖.
- **파라미터화**: **후보 Z (template action + 파라미터 스키마 + request-level binding context)**. Action은 type만 선언하고 필요한 파라미터 이름을 명시. Action의 파라미터 이름과 target StatePattern의 슬롯 이름이 같으면 자동 바인딩. 값은 intent 파싱 시점의 request-level binding context로 공급되어 plan 전체에 threaded.
- **Granularity: fine**. 한 action당 파라미터 하나 원칙. 복합 filter 같은 명시적 예외만 coarse 허용.
- **(b) rewrite의 주 출력 패턴**: multi-step action sub-goals를 `navigate_to(emit_url(...))` 단일 action으로 축약. 축약 불가능한 case(MUTATE form 등)는 multi-step 유지.

### 3-6. 플래그 — 쟁점 #2 마무리 시 다듬을 사항

- **"rewrite가 대부분 `navigate_to`로 귀결된다"는 비판에 대한 프레이밍**. 실질 기여가 "emit_url + 직접 navigation"으로 축소 해석될 위험. 반박 근거를 쟁점 #2 마무리에 추가할 것(state 표현·state_matches·emit_url의 세 축이 함께 있어야 이 단순한 귀결도 가능했다는 논지 등).

### 3-7. KG 신뢰도(trust) 표기 — 결정

- **Trust 값 집합**: `{verified, declared, inferred}` 세 레벨.
  - `verified`: Playwright crawl 또는 agent 실행 중 실제 관찰로 확인됨.
  - `declared`: 사람 또는 문서 기반 수동 기재.
  - `inferred`: LLM 추정, 다른 사이트·패턴 일반화.
- **부착 위치**: 네 곳에만 분산 부착 (제약된 R 구조).
  1. StatePattern.url_template_trust — URL 구조 자체
  2. StatePattern.identity_query_params[*].default_trust — default 값
  3. leads_to 엣지의 trust — action 전이가 실제로 이 상태로 가는가
  4. realizes 엣지의 trust — InfoType ↔ StatePattern 매핑
- **Rewrite 정책 (functional)**: trust는 query/rewrite 실행 시점에 실제로 읽혀 정책 분기에 쓰인다. dead 필드 아님.
  - `emit_target_url`: 동일 InfoType에 대한 realizes 엣지가 복수 존재하면 `verified > declared > inferred` 우선순위로 선택.
  - `rewrite_plan`: target StatePattern의 `url_template_trust`가 `inferred`면 rewrite 보류(원 plan 유지) — 신뢰 낮은 URL을 emit하지 않음.
  - 경로상 모든 엣지가 verified면 aggressive rewrite. declared면 rewrite + runtime validate 보정.
- **Runtime validation과 결합**: `state_matches` 결과가 true라도 target의 url_template_trust가 inferred면 2차 검증 요구.
- **Trust 진화**: 실행 성공/실패 피드백으로 trust 승격(inferred → declared → verified) 또는 강등(verified → declared). Introduction 초안 주장 7("continual site adaptation")을 trust 동적 업데이트로 구현. AWM과의 추가 차별점.
- **Source → trust 기본 매핑**: `crawl → verified`, `manual → declared`, `llm → inferred`. source 필드는 스키마 1급 시민으로 모든 노드·엣지에 부착 (`kg/types.py`).

### 3-8. 쟁점 #3 closing — 최소 스키마 요약

**노드 타입**
- `InfoType` — 추상 정보 카테고리. 자연어 intent의 착지점. GitLab ~15~25개.
- `StatePattern` — 사이트 상태의 formal 표현. URL pattern + identity query param schema + trust.
- `Action` — 상태 전이 template. 파라미터 스키마 선언. fine granularity(한 action당 파라미터 하나 원칙).

**엣지 타입**
- `realizes: InfoType → StatePattern` (+ bindings, trust) — 1:N 허용
- `leads_to: StatePattern --Action--> StatePattern` (+ 파라미터 바인딩 전달, trust)
- `url_template: StatePattern → URLTemplate` (+ path_params, identity_query_params, canonical_emit_order, url_template_trust)

**사이트 공통 config (별도 영역)**
- `decorative_params` denylist
- `identity_tokens` 런타임 치환 규칙
- `path_aliases`
- `url_decode / trailing_slash / case_sensitivity` 규칙

**Primitive 연산**
- `route_to(InfoType, bindings) → action sequence` — realizes + leads_to BFS
- `final_state(plan, initial_state, bindings) → StatePattern instance` — leads_to 시뮬레이션
- `state_matches(current_url, target_state_pattern, bindings) → (bool, bindings)` — 정규화 + 패턴 매칭
- `emit_url(state_pattern, bindings) → url` — 정규화 규칙 역방향 적용

**m0-sitekg 대비 본질적 차이**
1. StatePattern에 파라미터 바인딩이 1급 시민. m0의 NavigationEdge는 파라미터 개념이 희박했음.
2. InfoType ↔ StatePattern의 realizes 엣지로 intent의 추상 개념과 구체 URL 상태를 연결. m0엔 이 추상 레벨 없었음.
3. leads_to가 Action 레이블 + 파라미터 바인딩 전달을 포함 → 상태 전이 시뮬레이션 가능. m0는 단순 링크 수준.
4. **Trust 레이블이 스키마 1급 시민**. rewrite 정책이 trust에 따라 aggressive/보수/보류로 분기. m0는 trust 개념 부재.

**구축 파이프라인 (3단계 hybrid — baseline 측정 전에 완료)**
1. **Playwright auto-crawl** (`source=crawl` → `trust=verified`): url_template, path/query param 이름, 관찰 가능한 leads_to 엣지를 자동 수집.
2. **LLM-assisted derivation** (`source=llm` → `trust=inferred`): 관찰된 URL schema로부터 InfoType 후보·description·realizes 매핑, 사이트간 공통 패턴 일반화.
3. **Manual verification** (`source=manual` → `trust=declared`): decorative/alias/token, default 값, InfoType catalog를 사람이 검토·승격. 1·2단계에서 잘못된 항목은 이 단계에서 강등되거나 제거.

**구축 판정 기준 (시간 추정 아님)**
- 포괄 catalog: GitLab 주요 기능 표면을 커버하는 ~20~30 InfoType, ~30~50 StatePattern.
- Source 다양성: `SiteKG.source_mix`에 세 source 모두 0이 아닌 분포.
- Build metadata: `build_timestamp`, `builder_version`이 SiteKG에 기록되어 재현 가능.
- Baseline 독립성: catalog는 baseline 측정 **전**에 freeze. 실험 task 실패를 보고 수정 금지.

---

---

## 모델 및 예산 결정

- **본 실험 주 모델**: gpt-5.4-full (또는 제출 시점 동급 최상 모델).
- **보조 모델**: gpt-5.4-mini — 필요 시 scaling ablation(2 variants × N=3 × 50 task)용.
- **예산 상한**: **$150**. 새 baseline 첫 공식 측정 후 실제 token 사용량을 기준으로 full 전환 시 본 실험 규모 조정.
- **예산 초과 시 축소 옵션**: N=2로 축소, ablation 4→3개 축소, task 50→30 축소 중 택일.
- **Token 기록**: 새 baseline 측정 로그에서 task당 평균 token + 호출 수 추출 → 본 실험 비용 추정 문서 따로 작성.

### 쟁점 관련 영향

- 쟁점 #1의 **tool use 정확도 위험**은 full 모델에선 크게 감소 (enum-제약 JSON 준수율이 mini보다 훨씬 높음).
- 쟁점 #4의 ablation 변형들은 **모두 full 모델로 primary 측정**. mini 데이터는 scaling ablation에서만 사용.
- **폐기된 개발 pilot**(비공식 baseline으로 돌린 14+26 task)은 paper에 인용되지 않으며 측정치로도 쓰지 않는다 (`04_baseline_failure_analysis.md` 경고 참조).

---

## 쟁점 #1 — Executable query의 정체 (결정)

### 1-1. Query 형식 — 결정

- **Structured JSON via tool use (후보 3)**. LLM이 Anthropic/OpenAI function-call API에서 tool schema에 맞는 JSON을 생성. SPARQL 채택 안 함.
- **주 tool은 단일 `plan_to_info(target_infotype, bindings)`**. `route_to` primitive에만 노출. 나머지 3 primitive(`final_state`, `state_matches`, `emit_url`)는 KG 시스템 내부 pipeline이 자동 호출.

### 1-2. 입력 제약 — 결정

- **target_infotype은 InfoType 카탈로그로 제한된 enum**. JSON schema 검증으로 schema-linking 오류 원천 차단.
- **bindings는 자유 object + 런타임 검증**. 각 InfoType의 required bindings는 tool description에 포함. identity token(`me` 등)은 site_config로 런타임 치환.

### 1-3. 매칭 실패·다중 후보 — 결정

- **No-tool-call fallback**: LLM이 tool을 부르지 않으면 baseline의 일반 plan 생성에 맡김. KG 개입 보류.
- **다중 후보**: tool output이 후보 list인 경우 각 후보에 route_to 수행 → 가장 trust 높은 경로 선택. inferred만 나오면 rewrite 보류(쟁점 #3 adaptive 정책과 일치).

### 1-4. KG-QA 실패 모드와의 관계

- **entity linking 오류**: InfoType enum으로 탐색 공간 축소. 완전 차단 아니지만 크게 감소.
- **schema linking 오류**: enum 검증으로 **구조적 차단**.
- **text-to-SPARQL 문법 오류**: 본 연구는 SPARQL 아님. JSON 생성 오류율이 훨씬 낮음.
- Related Work에 "enum-제약 JSON tool use로 KG-QA 주된 실패 모드를 구조적으로 차단한다"는 주장 명시.

---

---

## 쟁점 #4 — Ablation 설계 (결정, scope 축소됨)

**결정 요약**: 본 논문(국내 3-page)에서는 **2-variant 비교 (Baseline vs Full KG)** 만 수행. 세분 ablation(compute-matched / URL-emission-only / KG-retrieval / scaling / continual)은 **future work로 분리**. 전체 scope 근거는 `07_scope_and_justifications.md`에 정리됨.

### 4-1. 본 논문의 실험 구성 (확정)

| # | variant | 정의 |
|---|---|---|
| 1 | **Baseline** | 버그 수정된 새 baseline (29건 수정 반영, Hook A/B/C/D 전부 off, LLM_TEMPERATURE=0) |
| 2 | **Full KG** | Baseline + Hook A/B/C/D 전부 on (trust-adaptive rewrite + early-termination validate) |

양자 비교 구성:
- 단일 가설 H1: Full KG success rate > Baseline success rate (paired McNemar, α=0.05)
- 측정: 50 task stratified × N=3 × 2 variants = 300 runs
- 보고: success rate + token/step/wall-time + task_type subset + failure mode 분포

### 4-2. Future work로 분리된 ablation (본 논문에서 수행하지 않음)

아래 5개 ablation 아이디어는 이전 설계 과정(2-7, 2-8 §이전 버전)에서 논의됐으나 3-page 분량 제약으로 드랍. 각각은 후속 연구에서 수행:

- **Compute-matched no-KG**: "단순 compute 증가 아님" 분리. 본 논문에선 token/step 수치 함께 보고로 대체.
- **URL-emission-only**: "plan rewrite/validate 기여" 분리. 쟁점 #2의 planning substrate 주장 세분 검증용.
- **KG-retrieval (fact injection)**: "retrieval vs structural operator" 분리. 본 논문에선 "KG 도입 전체"로 주장.
- **Scaling (mini + full)**: 모델 크기 invariance.
- **Continual replay (3 rounds)**: trust evolution 효과.

방어 논거: `07 §1 의도적 제외`, `07 §5 2-variant 방어`, `07 §11 Out-of-scope`.

### 4-3. 폐기된 쟁점 #2 Plan B 관련

2-7의 "planning substrate" framing과 2-9의 "Plan B retreat"는 **KG-retrieval ablation 결과에 좌우**되는 설계였다. 본 논문에서 해당 ablation을 수행하지 않으므로 Plan B 트리거가 없다. 대신:

- 논문 주장 자체를 **"site-specific KG 도입"** 수준으로 narrow (07 §1 참조)
- "planning substrate ≠ retrieval" 세분 주장은 future work로 유예
- 이 narrow 주장은 Baseline vs Full KG 단일 비교로 충분히 뒷받침됨

### 4-4. 예산 및 축소 정책

- 기본: 50 task × N=3 × 2 variants = 300 runs (~$11 mini, ~$90 full)
- 예산 초과 시 축소 순서: task 50→30 (runs 180), N=3→2 (runs 120), 이후는 주장 유지 불가
- 상세는 `07 §12 실험 규모 총합`.
