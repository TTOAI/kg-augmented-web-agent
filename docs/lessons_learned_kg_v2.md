# KG v2 회고 — 핵심 전략·결과·실패 기록

**작성일**: 2026-04-19
**목적**: 본 브랜치(`feature/kg-v2`)에서 수행한 SiteKG 도입 시도의 핵심 전략·실험 결과·실패 패턴을 보존. 관련 소스·문서 삭제 후에도 향후 KG 재설계 시 같은 실수를 반복하지 않기 위함.

---

## 1. 원래 문제 설정

### 1.1 관찰한 한계

LLM 웹 에이전트(GPT-4o/SeeAct/Agent-E/Browser-use 등)가 단일 페이지 DOM은 잘 읽지만, **사이트-수준의 구조적 지식**이 없어 복잡한 task에서 실패한다는 가설. "An Illusion of Progress" (Xue et al., COLM 2025)가 WebArena baseline 대비 후속 agent들의 상당수가 SeeAct 수준을 넘지 못한다는 재측정 결과를 제시한 흐름 위에서 출발.

### 1.2 DOM으로 얻지 못한다고 주장한 4가지 지식 (Minimum Viable KG 원칙)

1. **Connectivity** — 어느 페이지에서 어느 페이지로 갈 수 있는가
2. **Conditional state** — 어떤 조건이 충족돼야 그 기능이 활성화되는가
3. **Causal effect** — 한 액션이 다른 페이지에 어떤 효과를 미치는가
4. **Stable reference** — 어떤 식별자가 변하지 않고 재사용 가능한가

**삼가한 것**: type/category 추론(DOM에 위임), task semantic(LLM에 위임). KG는 위 4가지만 박는다는 원칙.

---

## 2. 선행 실험 (lab 001~006) — 교훈

### 2.1 lab 006 — Page-level prior 주입 실패

- 9 PageType + 5 ActionSchema를 자연어로 system prompt에 주입
- 결과: 50% → **47.6%** (향상 없음, 오히려 미묘한 하락)
- 당시 해석: "주입 방식이 비효율적 → selective retrieval / dynamic construction 필요"
- **실제 교훈 (회고)**: 표면 해석이었음. 단순 context 주입의 한계 자체를 직시했어야. 이 "주입 방식만 바꾸면 된다"는 해석이 이후 KG v2 설계의 낙관 편향 원인.

### 2.2 post-006 조치

- KG 계열 전부 폐기 + lab 005 baseline(tool use 전환) 복원 + `memo` field + `_verify_done`의 `task_notes` 검토만 추가
- memo 보강은 LLM working memory 외부화의 가벼운 구현 (system prompt는 task-agnostic 유지)
- 이 상태에서 KG v2 설계 시작

---

## 3. KG v2 — 핵심 설계

### 3.1 Schema (5 primitive)

| 노드/엣지 | 역할 |
|---|---|
| **StatePattern** | URL 패턴 + path_params + query_params (canonical 사이트 상태) |
| **InfoType** | 사이트가 제공하는 정보 종류 (issue_list, project_page, todo_list 등) + required/optional bindings |
| **Action** | 상태 전이 연산 (click/submit/navigate, fine granularity — action당 파라미터 1개) |
| **RealizesEdge** | InfoType → StatePattern 실현 가능성 (binding_map 포함) |
| **LeadsToEdge** | StatePattern → Action → StatePattern 전이 (from_bindings/to_bindings) |
| **Trust** | verified (crawl) / declared (doc/manual) / inferred (LLM) |

**설계 원칙 (이후 "Flat graph" 원칙으로 정립)**:
- End-to-end connectivity 우선, 노드 수 풍부보다 연결성 풍부
- description/display_name/tags **폐기** — 구조만 남기고 의미 해석은 LLM·DOM에 위임
- Playwright 자동 수집 우선 (LLM 의존 최소)

### 3.2 3-stage 자동 구축 파이프라인

```
[Stage 1 — Crawler]
Playwright BFS crawl → signature dedupe → GET form input → query URL 큐 확장
→ CrawlResult[] → (crawl_to_kg) → verified layer SiteKG

[Stage 2 — LLM derivation]
crawled + manual seed → 3-call decomposition (Responses API + reasoning_effort=low):
  Call 1: state pattern grouping
  Call 2: InfoType + realize (group_id 참조)
  Call 3: action renames
→ inferred layer SiteKG

[Stage 2.5 — Post-enrichment]
LLM 재호출 없이 schema 결함 보강 (binding_map, path_params, query_params, category)
source 유지: inferred

[Stage 3 — Freeze]
manual + crawl + derivation + post_enrich 통합 → immutable snapshot
config/sites/<site>/frozen_kg/<ISO_ts>.json
```

최종 GitLab frozen KG (2026-04-16T16-46-55Z.json, 12MB, git_rev=534c49d):
- 3,040 StatePatterns, 37 InfoTypes, 4,109 Actions, 26,503 LeadsToEdges, 0 RealizesEdges (derivation 후 post_enrich에서도 실제로 채워지지 못함)
- source_mix: crawl 33,150 / llm 593 / manual 0
- ARI=0.9264 (3-run consistency) — 형식적 sanity는 통과

---

## 4. 활용 전략 — 4 Hook 구조

### 4.1 Hook 설계 의도

`docs/kg_design/02 §2-6`에서 "planning substrate의 3요소"로 정식화:

1. **Structural operator** — plan tree에 적용되는 연산 (Hook B rewrite)
2. **State predicate** — 실행 중 호출되는 상태 판정자 (Hook C validator). LLM context에 삽입하지 않음
3. **Adaptive intervention policy** — trust 레벨에 따라 rewrite 개입 강도 조절

### 4.2 4 Hook 배치

| Hook | 위치 | 역할 |
|---|---|---|
| **A** `plan_to_info` | `analyze_intent` 직후, `build_plan` 전 | intent → InfoType 분류 + bindings 추출 (LLM tool_use) |
| **B** `rewrite_plan` | `build_plan` 후 | InfoType + StatePattern → URL 템플릿으로 sub-goal 재작성 |
| **C** `target_reached` | sub-goal 루프 매 step | 현재 URL이 목표 StatePattern에 도달? → early SUCCESS |
| **D** `trust_update` | 실행 후 | edge trust 업데이트 (**설계만, 구현은 logging-only no-op**) |

### 4.3 AWM/RAG 계열과의 의도적 차별점

- AWM: trajectory-level workflow 자연어 텍스트 → context injection
- 본 연구: state-transition graph → **structural operator** (Hook B plan rewrite)
- 본 연구만의 차별점이라 주장한 것:
  - "context에 주입하는 facts가 아니라 plan tree에 적용되는 연산"
  - Hook C validator는 **context 개입 0**
  - Trust evolution이 retrieval에 대응물 없음

---

## 5. Phase 별 실험 결과·실패

### 5.1 Phase C 180-run (2026-04-17) — 결정적 결함

**설계**: 30 task × 3 variants(baseline / kg_full / kg_info_ignored) × N=3 = 180 runs. paired McNemar.

**관측**:
- Overall: Baseline **20%** (6/30) ≡ Full KG **20%** (6/30) — **동일**
- NAV: 20% ≡ 20% / RET: 30% ≡ 30% / MUT: 10% ≡ 10%
- McNemar two-tailed p = **1.0000**, Wilcoxon p > 0.6
- `[KG]` 로그 라인: Full KG 90 runs 전체에서 **0건**

**원인 (postmortem)**:
- `run_phase_c_180.sh` 등 스크립트에서 **`SITEKG_ENABLED=1` env 누락**
- `adapter._maybe_load_kg_context`가 즉시 None 반환 → kg_context=None
- `run_agent`의 Hook A 진입 조건(`kg_context is not None`) 실패 → baseline 경로로 silent fallback
- **baseline vs baseline 비교**가 되어버림

**교훈**:
1. 신규 script 작성 시 기존 작동 script의 env var set을 diff 검증하는 절차 부재
2. Silent fallback은 실험을 무효화한다 — KG 활성 실패 시 **fail-loud**하게 바꿔야
3. CI·smoke 단계에서 `[KG]` 로그 emission count를 assertion으로 검증하는 장치가 없었음

### 5.2 Phase 2B "Option B" (2026-04-18) — Hook B trust 확장

**설계**: Hook B rewrite가 trust=inferred edge에서 skip되던 보수 정책을 완화. Hook B malformed URL guard 추가. Hook C를 NAV만 활성 (RET/MUT suppress).

**Smoke (6 task × 2 variants)**:
- baseline NET: 1/5 (broken eval 168 제외) = 20%
- kg_full NET: 1/5 = 20%
- Hook B applied 4/6, Hook C early SUCCESS 3건

**해석**: AR(AgentResponseEvaluator) 기준 kg_full이 5/6(83%)로 보였지만 NET 기준은 baseline과 동일. **AR=success / NET=failure** 불일치 패턴 첫 관측.

### 5.3 Phase 2C-β (C1 rollback + C2 유지)

**설계**:
- C1: Hook A prompt에 path_slot hint 추가 → MUT task에서 Hook B malformed URL skip 감소 목적
- C2: runtime_context auto-fill (agent의 현재 URL에서 path_params 자동 추출하여 emit_url fallback)

**문제 관측 (C1)**: Hook A가 path_slot hint를 받으면 **rich-but-wrong bindings**를 생성 → agent를 잘못된 URL로 유도 (예: `project_page`로 MUT 오분류). C1 **rollback**. C2는 유지.

**Smoke β (6 task × 2 variants)**:
- baseline NET: 2/5 = 40%
- kg_full NET: 1/3 = 33% (MUT 2건은 kg_full에서 agent timeout, eval_result 없음)
- AR: kg_full 100% vs NET 20-33%

**핵심 관찰**: Hook C의 URL-only early SUCCESS가 **bindings 완전성 검증 없이** 발동 → agent는 SUCCESS 선언했지만 실제 target 미도달. "5/6 승리"는 **환상**.

### 5.4 R3-α (Hook B/C 제거, Hook A only + passive context injection)

**동기**: Phase 2C β의 AR/NET gap이 Hook C false positive에서 온다는 가설. Hook B/C를 완전 제거하고 Hook A 결과를 system prompt에 passive context로만 주입.

**설계**:
- `SITEKG_MODE=alpha` env gate
- Hook A는 유지, kg_lookup을 `format_kg_context_for_prompt`로 structured block 생성
- system prompt에 "Site knowledge: InfoType `issue_list`, URL patterns `/...`, required context ...." append
- Hook B/C 호출 지점에 mode guard 추가 → skip
- 명령이 아닌 informational ("Use this as hints. You decide how to navigate.")

**Smoke α2 (6 task × 2 variants, 올바른 env)**:
- baseline NET: 2/4 = 50% (44·46 성공; 411 timeout 제외, 414·102 실패)
- kg_alpha NET: 1/5 = **20%** (44만 성공; **46 regression**)
- Hook A injection 로그 6/6 발동 확인, Hook B/C 로그 0건 확인

**핵심 관찰**:
1. **AR/NET gap 해소 실패** — Hook C 제거 후에도 gap 지속 (kg_alpha AR 5/5 vs NET 1/5)
2. **Hook C가 gap의 유일 원인이 아님** — `_verify_done`의 LLM judge 자체가 over-permissive. agent가 target 미도달 상태에서도 "done" 선언
3. **Passive context 주입만으로도 regression** — task 46에서 baseline success → kg_alpha fail. kg_context block이 agent의 자연스러운 navigation을 방해하거나, Hook A의 InfoType 오분류가 잘못된 힌트로 유도

### 5.5 전 period 수치 요약

| 측정 | baseline NET | kg_full/alpha NET | 비고 |
|---|---|---|---|
| baseline_m5 N=1 (33 task) | 10/33 = 30.3% | — | baseline-only 최고 |
| baseline_n3 N=3 (150 run) | 7/150 = 4.7% | — | N2/N3 OpenAI quota로 오염 (100건 UNKNOWN_ERROR). N1만 취하면 7/44 ≈ 16% |
| Phase C 180 (30×3) | 6/30 = 20% | 6/30 = 20% | Hook 미활성 (SITEKG_ENABLED 누락) |
| smoke_option_b (γ) | 1/5 = 20% | 1/5 = 20% | Option B trust 확장 |
| smoke_option_beta (β) | 2/5 = 40% | 1/3 = 33% | C1 rollback + C2. MUT 2건 timeout |
| smoke_option_alpha (α2) | 2/4 = 50% | 1/5 = 20% | Hook B/C off, Hook A only |

**공통 패턴**: NET 기준 KG가 baseline을 의미 있게 이긴 적 **한 번도 없음**. 작은 승리는 전부 AR(자가선언)에서 옴 → Hook C 발동 또는 _verify_done permissiveness의 부작용.

---

## 6. 실패 mode 분류

### 6.1 아키텍처 결함 (3-coupled defect)

1. **Hook B = command (suggestion 아님)** — agent의 plan을 강제로 URL로 rewrite. Hook A 오분류 시 잘못된 URL로 이동. agent가 거부할 경로 없음
2. **Hook C = URL-only validation** — bindings 완전성 검증 없이 URL 패턴만 매칭하면 early SUCCESS. "패턴은 맞지만 실제론 다른 페이지" 케이스 구분 불가
3. **Hook A = context-blind** — intent만 보고 분류. 현재 페이지 상태나 실패 이력 무시. 오분류 시 Hook B/C로 오류 전파

이 세 결함은 **coupled** — 하나만 고쳐도 나머지가 유해. R3-β(3 모두 수술)는 ceiling 낮음, R3-α(Hook B/C 제거)는 시도했으나 `_verify_done` 문제가 남음.

### 6.2 데이터/파이프라인 결함

- **RealizesEdges = 0** — final frozen KG에 realizes 엣지가 0건. InfoType → StatePattern 매핑이 비어 있어 Hook B가 URL을 emit할 수단이 사실상 기대치보다 적었음 (post_enrich가 auto_fill_binding_map을 시도하지만 실제 채움은 미미)
- **source_mix: manual 0** — manual seed가 실질적으로 비어 있음. crawler + LLM이 전부 채움 → 오류 검증 인간 루프 없음
- **v9 derivation = multi-call** — 3-call decomposition으로 품질 개선 시도했으나 ARI만 올라갔을 뿐 agent 성능에 영향 못 줌

### 6.3 측정·재현성 결함

- Phase C 180 env 변수 누락 (§5.1) — SiteSilent fallback 설계가 실험 무효화
- `scripts/analyze_baseline.py:63` — `llm_calls = len(re.findall(r"\[LLM\] step=", text))` 은 API call이 아닌 log line count. 과대 집계
- broken eval (task 168) — evaluator schema bug (`Schema type must be 'array', got: 'null'`)로 error 처리. 모든 smoke에서 동일하게 발생했으나 초기엔 이를 "KG의 이득"으로 오해하는 분석 있었음
- `agent_response.status=SUCCESS` vs `eval_result.status=SUCCESS` 혼동 — 분석 초기 몇 주 동안 agent 자가선언을 공식 점수로 썼음. 발견 후 전체 재집계

### 6.4 Framing 결함

- "패러다임 전환", "structural operator", "planning substrate" 같은 강한 표현을 설계 초기에 채택 — 측정 결과가 나오기 전에 narrative를 너무 강하게 잡아서 yellow/red 결과가 나왔을 때 재framing 부담 커짐
- Triple contribution (C1 정확도 / C2 효율 / C3 methodology) + dual H1a/H1b two-tailed로 "any-result-valuable" 장치 마련했으나, 실제 red 상황에선 C3(methodology)만 남고 C1/C2는 null/negative로 약화

---

## 7. 다음 설계 시 상기할 원칙

### 7.1 측정·재현성

1. **Silent fallback 금지** — KG 활성 실패는 warning 아니라 **fail-loud**. CI에 `[KG]` 로그 emission count assertion 포함
2. **Env var 체크리스트** — 신규 script 작성 시 기존 작동 script의 env set을 diff 검증. 자동화
3. **AR vs NET 분리 보고 default** — agent 자가선언(AR)과 eval 판정(NET)을 항상 분리. AR만 보고 결론짓지 말 것. `NetworkEventEvaluator` 기준이 실제 행위 증거
4. **N=1 smoke로 결론짓지 말 것** — baseline 자체의 run-to-run variance가 10-20%p 수준. variance 측정 없이 단일 run 비교는 의미 약함

### 7.2 아키텍처

5. **Hook이 command면 agent가 거부할 경로를 설계에 포함** — 강제 rewrite는 오분류 시 유해. suggestion mode 또는 confidence gate 필요
6. **validator는 다축 검증** — URL 패턴 매칭만으로는 부족. bindings 완전성, DOM 존재성, task type 고려 필수
7. **Hook A는 context-aware** — intent만 쓰지 말고 현재 페이지 상태·이전 실패 이력·blacklist 루프 포함
8. **passive context 주입도 해로울 수 있음** — prompt length 증가 + LLM 주의 분산. 주입 전후 비교로 실측 필요

### 7.3 방법론

9. **설계 framing은 측정 결과를 본 후 잠정적 언어로** — "structural operator", "planning substrate" 같은 강한 카테고리화는 positive 결과 확인 후에 사용. 사전에는 "KG-augmented agent" 수준으로 유보
10. **첫 시도는 passive retrieval부터** — 가장 단순한 "KG를 document로 주입" 부터 시작하고 positive 확인 후에만 structural hook 확장. 역순으로 접근하면 복잡도에 갇힘
11. **lab 006 해석 오류 재발 금지** — "주입 방식만 바꾸면 된다"는 낙관 편향을 조심. 단순 주입이 안 되면 **주입 자체가 답이 아닐 가능성**을 먼저 고려
12. **compute-matched control variant(info_ignored)는 유지** — "KG가 compute 더 쓴 거 아니냐" 공격 차단에 유효

### 7.4 데이터

13. **RealizesEdges 채움 정책을 처음부터 명시** — InfoType ↔ StatePattern 매핑이 empty면 Hook B는 무력. schema 정의 시점에 채움 책임 소재(manual / crawl / LLM) 명확화
14. **Manual seed를 실질적으로 채울 것** — source_mix에서 manual=0이면 인간 검증 루프 부재. 검증 없는 LLM 산출물은 품질 위험
15. **frozen snapshot size의 의미** — 12MB에 3,040 StatePatterns이 agent task 분포를 얼마나 포괄하는지 별개 검증 필요. crawl coverage ≠ task coverage

---

## 8. 보존되는 자산 (이번 삭제 후)

- **collector 코드** (`site_adaptive_webagent/kg/seed/` + `kg/{types,store,urlnorm}.py`) — 수집 전략 자체는 재검토 후 판단
- **seed 소스** (`config/sites/gitlab/{site_config.yaml, infotypes.yaml, kg_seed.json}`) — 수동 작성분
- **현재 frozen KG** (`config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json`) — collector 산출물, 재분석 대상
- **본 회고 문서** (이 파일)

---

## 9. 삭제되는 것 (요지)

- agent-side 활용 로직 전부 (`agent/kg_integration.py`, `kg/{query,rewrite,validator}.py`)
- executor/core/adapter의 KG 배선
- KG variant scripts (phase_c_*, smoke_option_*)
- 설계 문서 (`docs/kg_design/` 전체, `docs/paper/`, `docs/v2_lab_reports/`)
- 편향성 memory (feedback_research_kg_*, feedback_sitekg_design_principles)

git history에는 전부 남으므로 필요 시 `git log --all` + `git show <rev>:<path>`로 복원 가능.

---

**이 파일이 남아 있는 이유**: "Hook 구조 재도입" 또는 "KG 활용 전략 재설계" 시 이 문서부터 읽고 §7 원칙을 체크리스트로 활용할 것. 특히 §7.3-10 ("첫 시도는 passive retrieval부터")과 §7.1-3 ("AR vs NET 분리")는 측정 투입 전에 반드시 재확인.
