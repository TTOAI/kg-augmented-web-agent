# 연구 기여 방향 제안서

**작성일**: 2026-04-19
**입력 자료**:
- 초기 방향 설정: `docs/kg_design/references/` (Introduction 초안 + KG/Web Agent 기본 문헌 정리)
- Field landscape: `docs/papers/00_survey_notes.md` + 5개 논문 분석 (01_step / 02_walt / 03_colorbrowseragent / 04_avenir_web / 05_lcow)
- 과거 시도 회고: `docs/lessons_learned_kg_v2.md`

---

## 1. 초기 연구 방향 (references 기반)

### 1.1 KG 측면의 관점 (`kg_01~03`)
- KG = **RDF (facts) → RDFS (schema) → OWL (semantics) → SPARQL (queries)** 4층 구조
- LLM 시대 KG 재부상 5가지 이유:
  1. **업데이트성** — 학습 후 갱신 가능
  2. **Hallucination 완화 + 근거 제시** — 외부 명시 지식원
  3. **관계 중심 질의 + 다단계 추론** — 일반 RAG가 약한 relational 정보 강점
  4. **컨텍스트 압축** — subgraph/path/triplet만 추출해 입력 길이 감소
  5. **통제 가능성 + 검사 가능성** — 잘못된 답의 원인 추적이 parametric LLM 대비 쉬움
- LLM vs KG가 아니라 **LLM + KG 하이브리드** 방향

### 1.2 Web Agent 측면의 관점 (`web_01~03`)
- 표준 3-loop: **Perception → Planning & Reasoning → Execution**
- 실무 5-block 재구성: Planning / Memory / Tools / Guardrails / Evaluator
- 최근 연구 발견: 병목이 **grounding보다 planning** 쪽이라는 분석

### 1.3 Introduction 초안의 핵심 논지
- 웹 planning은 **inherently relational** (page transition, constraint, entity relation)
- 기존 agent는 이 relational 구조를 prompt에 암묵적으로 두고 매 task마다 재발견
- 제안: **site-specific executable KG**를 planning substrate로 사용
  - Natural language intent → executable graph query
  - Query 결과 (subgraph, path) → planner context
- 3 contributions 제안:
  1. Executable intent-to-query planning layer
  2. Site-specific executable KG for web planning
  3. 평가 프로토콜 (cold-start + continual adaptation + failed-task replay)

### 1.4 초기 방향에서 검증 대상으로 둔 두 질문
1. **Executable query-guided graph evidence**가 text-only planning 대비 성능 향상하는가?
2. **Incremental graph augmentation**이 site adaptation에 도움이 되는가?

---

## 2. 5개 논문 Landscape (경쟁·공백 매트릭스)

### 2.1 각 논문 1줄 요약

| # | 논문 | 날짜 | 핵심 | 성능 |
|---|---|---|---|---|
| 1 | **SteP** | 2024-08 | 14 수동 natural language policy + dynamic stack composition | WebArena 33.5% |
| 2 | **WALT** | 2025-10 | Site functionality reverse-engineering → 50+ invocable tool (URL param promotion + agentic fallback) | WebArena 50.1% / GitLab 57% |
| 3 | **ColorBrowserAgent** | 2026-01 | Human-in-loop 52 tips (operational logic) + O(1) summarization | WebArena **71.2%** / GitLab 65.7% |
| 4 | **AVENIR-WEB** | 2026-02 | EIP online search (procedural) + MoGE visual + Checklist + Adaptive Memory | Online-Mind2Web 53.7% open-source SOTA |
| 5 | **LCoW** | ICLR 2025 | Observation preprocessing module (trained LM) | WebShop 62.8% (human 초과) |

### 2.2 Knowledge Taxonomy 4-axis (누적 정리)

| 종류 | 예시 | Graph 적합성 | SKG와 관계 |
|---|---|---|---|
| **Perception preprocessing** | LCoW | 낮음 | **Orthogonal** (결합 가능) |
| **Procedural (how-to)** | AVENIR EIP, AWM workflow | 낮음 | Orthogonal |
| **Operational (logic/rules)** | CBA 52 tips, SteP policy | 중간 | Partial overlap |
| **Structural (topology)** | 과거 SKG, WALT URL promotion | **높음** | SKG 고유 영역 |

### 2.3 5개 논문이 다루지 않거나 약한 영역

각 논문이 커버 못 하는 부분 (graph-friendly 영역 집중):

| 공백 | SteP | WALT | CBA | AVENIR | LCoW |
|---|---|---|---|---|---|
| **Cross-tool/state connectivity** | 부분 (stack 재귀만) | ❌ (tool 독립) | ❌ (flat tip) | ❌ (single plan) | ❌ |
| **State invariants (조건부 가용성)** | ❌ | ❌ | ❌ (condition 미표현) | ❌ | ❌ |
| **Failure trajectory 활용** | ❌ | ❌ (success 기반 retry만) | 부분 (failure 감지 후 human intervention) | 부분 (failure reflection buffer) | ❌ (success trajectory만 train) |
| **Offline + Cheap** | — | GPT-5 고비용 | Human 1일 | GPT-4급+online search | GPT-4o trained |
| **Executable intent-to-query** | ❌ | ❌ | ❌ (flat keyword search) | ❌ | ❌ |

### 2.4 주목할 수치 (benchmark bar)

| Benchmark | SOTA | Open-source SOTA | 이 연구의 현재 baseline |
|---|---|---|---|
| WebArena overall | CBA 71.2% | CBA 71.2% | baseline 20-30% (GPT-4o-mini) |
| WebArena GitLab | CBA 65.7% | CBA 65.7% | 해당 |
| Online-Mind2Web | Yutori Navigator 64.7% | AVENIR 53.7% | 미측정 |
| WebShop | LCoW 62.8% | LCoW 62.8% | 미측정 |

---

## 3. 5개 논문이 재설계에 주는 교훈

### 3.1 공통 교훈 (5개 논문에서 일관된 신호)

1. **Agent가 KG를 호출** > **KG가 agent를 명령** (SteP, WALT 모두)
2. **Validation loop 필수** (WALT iterative demonstrate-generate-validate, CBA hybrid detector)
3. **Long-horizon은 직교 관심사** (CBA summarizer, AVENIR adaptive memory)
4. **Benchmark 이동 중** — WebArena → Online-Mind2Web, real-world
5. **Passive retrieval이 field 관행** (survey 확인)

### 3.2 Framing 교훈 (`lessons_learned §7.3` 강화)

- "Planning substrate" / "structural operator" 같은 **강한 framing 금지**
- Survey taxonomy에 제 SKG는 "LTM (graph-structured)"로 격하됨
- Novelty는 **empirical trade-off 비교**로 확보해야지 개념적 구분으로 확보 안 됨

### 3.3 생존 확인된 영역 (5개 논문 대조 후)

Graph representation이 자연스럽고, 5개 논문이 다루지 않은 영역:

1. **Cross-node connectivity** (LeadsToEdge) — WALT/CBA는 flat list
2. **State invariants** — WALT tool은 precondition 무시, CBA tip은 조건부 context 약함
3. **Failure knowledge** — AWM/ASI는 success only, CBA도 failure는 trigger로만 사용
4. **Graph-compressed context** — 긴 AXTree를 subgraph로 압축 (LCoW와 상보)
5. **Offline low-cost construction** — CBA는 human 1일, WALT는 GPT-5 expensive

---

## 4. 가능한 기여 방향 (6 candidates)

각 방향에 대해:
- **Idea**: 핵심 아이디어
- **Novelty vs 5 papers**: 어떤 공백을 메우는가
- **Reviewer-proof 방어 3축**: 예상 공격과 방어
- **Feasibility**: 3-page scope + GPT-4o-mini 예산 내 가능 여부
- **Risk**

---

### Direction A: **Cross-State Connectivity Graph**

**Idea**:
- WALT/CBA/SteP 모두 **tool/tip/policy 간 전이 관계**를 명시하지 않음
- KG의 LeadsToEdge를 **"tool A 다음에 어떤 tool/policy"** 그래프로 재정의
- Agent가 현재 완료한 action을 주면 **가능한 다음 action 집합**을 graph로 제공

**Novelty vs 5 papers**:
- SteP stack 재귀는 recursive call, 직접 전이 그래프 아님
- WALT tools are independent; 호출 순서는 agent가 추론
- CBA tips는 flat, 순서 관계 없음
- **이 공백이 가장 명확**

**Reviewer-proof 방어**:
1. "왜 필요한가?" → multi-step task에서 agent가 현재 state에서 "다음 가능한 action이 무엇인가"를 추론하는 부담 감소
2. "SteP stack으로 충분?" → SteP은 policy composition이지 state-level transition 아님. DB 예: 로그인 후 일부 action 활성화되는 조건부 가용성
3. "Measurement?" → baseline vs KG-aware agent에서 step count 감소 + redundant exploration 감소 측정

**Feasibility**: ⭐⭐⭐ 높음. 기존 kg/seed/의 LeadsToEdge 26,503개 재활용
**Risk**: Graph 정확도. 26,503개 edge 중 agent-useful은 일부일 수 있음

---

### Direction B: **State Invariants / Conditional Availability**

**Idea**:
- "이 action은 로그인 후에만 가능", "admin 권한이 필요", "장바구니 비어있지 않아야" 같은 **precondition**
- KG 엣지에 condition attribute 추가: `edge.precondition = "user.logged_in AND cart.items > 0"`
- Agent가 action 시도 전 precondition 확인 → useless action 회피

**Novelty vs 5 papers**:
- WALT tool은 static, precondition 없음
- CBA tip은 "when to use"를 자연어로만 표현
- **5개 논문 모두 조건부 가용성 명시 안 함**

**Reviewer-proof 방어**:
1. "왜 필요한가?" → Agent가 로그인 필요한 action을 시도해 404/permission error 낭비하는 failure mode 현존. 자체 smoke에서도 관찰
2. "Human task에 precondition 많은가?" → WebArena task의 다수가 user state dependent
3. "Measurement?" → Precondition-aware variant vs baseline의 error trajectory 비율 비교

**Feasibility**: ⭐⭐ 중간. Precondition annotation을 KG에 자동 추출하는 로직 신규 필요
**Risk**: Precondition 추출의 정확도. Manual seed 필요할 수 있음

---

### Direction C: **Failure Trajectory 기반 Incremental KG Update**

**Idea**:
- AWM/ASI는 success trajectory만 mining. Failure는 버림
- Failure는 "이 경로는 막다른 길" 이라는 **귀중한 정보**
- Graph에 **anti-edge** (예: `blacklist_edge: state X → action Y는 고비용/실패`) 추가
- Incremental update: agent가 task 수행 중 실패 경험을 KG에 반영

**Novelty vs 5 papers**:
- Introduction 초안의 **"continual adaptation + failed-task replay"** 문제의식과 정합
- CBA는 failure를 human intervention trigger로만 사용, KG에 반영 안 함
- **Failure-from-learning이 KG-friendly 영역**

**Reviewer-proof 방어**:
1. "Success로 충분?" → AWM은 WebArena 35.5%에 머묾. Failure-aware agent가 ceiling을 올릴 가능성
2. "Empirical 설계?" → t0 session에서 K개 task 실행 → failure KG update → t1에서 같은 task 재시도. Performance delta 측정
3. "Measurement cost?" → 동일 task subset의 2-round 측정만 필요. $상대적으로 저렴

**Feasibility**: ⭐⭐ 중간. Incremental update infrastructure 설계 필요
**Risk**: Failure signal noise. 실제 실패 vs 일시적 오류 구분 어려움

---

### Direction D: **Graph-Compressed Context (KG + LCoW Complementary)**

**Idea**:
- LCoW: raw AXTree → 자연어 요약
- Direction D: **KG graph → 현재 task에 관련된 subgraph/path만 추출** → agent context에 주입
- 제공 정보: 현재 page의 canonical state + 관련 adjacent state + 가능한 action 목록
- LCoW가 "현재 페이지 내용" 요약이라면, 이것은 "현재 페이지의 graph 근방"

**Novelty vs 5 papers**:
- LCoW는 perception layer, 이것은 memory layer → **orthogonal, 결합 가능**
- 기존 SKG는 전체 graph를 load. 이것은 **task-relevant subgraph**만 추출 (관계 중심 RAG)
- Introduction 초안의 "subgraph evidence" 주장과 정합

**Reviewer-proof 방어**:
1. "전체 prompt 주입과 차이?" → context length 감소. Agent attention dilution 완화 (SteP Flat-8k 한계와 동일 논리)
2. "LCoW vs Direction D 중복?" → 정보 종류 다름 (LCoW: 현재 페이지 / D: graph 근방)
3. "Reproducibility?" → Subgraph 추출 알고리즘 deterministic하면 재현 가능

**Feasibility**: ⭐⭐⭐ 높음. 기존 SKG의 query.py 일부 재활용 가능
**Risk**: Subgraph 추출의 과/부족. 과도하면 noise, 부족하면 정보 없음

---

### Direction E: **Offline KG as Bootstrap for Online Methods**

**Idea**:
- WALT는 GPT-5 기반 iterative site exploration 비용 높음
- CBA는 human 1일
- **Offline crawled KG가 WALT tool discovery의 "seed candidate"** 역할
- WALT 5-10 iteration 대신 KG 기반 1-2 iteration으로 근사 성능

**Novelty vs 5 papers**:
- 새 method는 아니고 **기존 WALT의 bootstrap/warm-start**
- 연구 방향: "Cheap offline KG가 expensive online method의 시작점"
- **Reproducibility + cost에 기여**

**Reviewer-proof 방어**:
1. "WALT re-implementation 가능?" → WALT 코드 공개 여부 확인 (WebArena repo에 있음). 재현 가능
2. "Measurement?" → WALT (full) vs WALT (KG-warmstart)의 iteration count + final SR 비교
3. "Scope?" → 3-page에선 WALT 완전 재현이 과함. Partial tool discovery만

**Feasibility**: ⭐ 낮음. WALT 재현 + 수정 대규모 작업. 3-page scope 초과
**Risk**: Scope 부담 큼

---

### Direction F: **Intent-to-Query Executable KG (초기 방향의 정제)**

**Idea**:
- Introduction 초안의 원래 방향
- Natural language intent → **constrained executable graph query** (SPARQL 경량 버전)
- Query result (subgraph evidence) → planner context
- **과거 Hook A의 진화 형태** but agent 명령 X → agent 힌트 O

**Novelty vs 5 papers**:
- CBA는 keyword search (3-tier cascade). Intent-to-query는 더 구조화
- KG-QA 전통을 웹 action planning에 적용
- **initial direction + lessons learned 결합**

**Reviewer-proof 방어**:
1. "SPARQL full spec 아닌가?" → Domain-restricted minimal query language. RDF/OWL full spec 불필요
2. "CBA와 차이?" → CBA tip은 natural language, structured query는 구조적 필터 (AND/OR/path). 복잡한 constraint-based retrieval 가능
3. "과거 실패 반복?" → 과거 Hook A가 "KG가 agent 명령" 모델이었다면, 이것은 "agent가 query invoke" 모델. lessons §7.2 반영

**Feasibility**: ⭐⭐ 중간. Query language spec + parser 설계 필요. 3-page scope 가능성 있음
**Risk**: Query translation 실패 빈도 (과거 Hook A 실패 원인과 동일 위험)

---

## 5. 종합 비교 + 권고 조합

### 5.1 매트릭스

| Direction | Novelty | Feasibility | Cost | 3-page 적합 | 기존 자산 재사용 |
|---|---|---|---|---|---|
| A. Cross-state connectivity | 높음 | ⭐⭐⭐ | 낮음 | ✅ | Frozen KG LeadsToEdge |
| B. State invariants | 중간 | ⭐⭐ | 중간 | ✅ | KG 구조 확장 필요 |
| C. Failure-based update | 중간 | ⭐⭐ | 중간 | ✅ | 신규 infra |
| D. Graph-compressed context | 높음 | ⭐⭐⭐ | 낮음 | ✅ | KG query.py |
| E. Offline bootstrap | 높음 | ⭐ | 높음 | ❌ | WALT 재현 |
| F. Intent-to-query | 중간 | ⭐⭐ | 중간 | ✅ | Hook A 재설계 |

### 5.2 **권고 조합**: **A + D (combined)**

**이유**:
1. 두 direction 모두 **feasibility 최고** + **기존 Frozen KG 재사용 가능**
2. A (connectivity) = **graph structure 의미**, D (compressed context) = **graph content 활용**
3. 두 개 합치면 "site의 구조를 graph로 표현 (A) + task에 맞게 추출하여 context 압축 (D)" = 자연스러운 single method
4. 5개 논문 어디도 이 조합 안 함
5. Reviewer-proof: 각각의 contribution 분리 측정 가능 (A ablation / D ablation / A+D)
6. `lessons_learned §7.3-10` ("첫 시도는 passive retrieval부터")과 부합

### 5.3 제안 논문 narrative

> **"Structural Site Knowledge as Compressed Context for Web Agents"**
>
> 웹 에이전트가 long-horizon task에서 매번 site 구조를 재발견하는 부담을 줄이기 위해, 우리는 site-specific KG에서 **task-relevant subgraph**를 추출하여 agent의 context로 주입한다. KG는 **state 간 connectivity** (LeadsToEdge)를 명시적으로 표현하며, 추출된 subgraph는 현재 page의 canonical 상태 + 관련 adjacent 상태 + 가능한 transition을 compact하게 전달한다.
>
> 우리는 WebArena-Verified GitLab에서 평가하여 다음을 측정한다:
> - (1) KG 없이 prompt에 전체 graph 정보 주입 (Direction D ablation)
> - (2) KG 있고 subgraph 추출 (Direction A+D)
> - (3) Baseline (no KG)
>
> 주된 결과 지표: **paired McNemar** 대비 baseline + per-task-type breakdown

### 5.4 `lessons_learned §7` 원칙 체크

권고 조합이 교훈을 위반 안 하는지:
- §7.1 Silent fallback 금지 — ✅ KG 로드 실패 시 fail-loud
- §7.2 Hook이 command 아닌 suggestion — ✅ subgraph는 context, 명령 아님
- §7.2 validator 다축 검증 — 해당 없음 (validator 없음)
- §7.3 Passive retrieval부터 — ✅ D가 정확히 passive context injection
- §7.3 Framing 잠정적 언어 — ✅ "structured LTM for action planning" 수준
- §7.4 RealizesEdges 채움 정책 — ⚠ 구현 시 Realizes 활용 여부 검토

---

## 6. 대안 권고 (A+D 실패 시)

A+D smoke에서 ablation 효과 없으면:

**Plan B**: Direction C (Failure trajectory) 단독
- Introduction 초안의 "continual adaptation + failed-task replay" 주제와 가장 정합
- 독특한 narrative ("failure is also information")
- Pre-failure vs post-failure 2-round 측정

**Plan C**: Direction F (Intent-to-query) 단독
- 과거 접근의 진화 버전. lessons_learned 활용
- 다만 초기 시도 (Hook A) 실패 원인 재발 위험 있음 — 명시적 회피 설계 필수

---

## 7. 3-page scope 내 execution plan 초안 (권고 A+D 기준)

### 7.1 Phase 구조
1. **P0 — 재설계** (1 week): KG subgraph extraction algorithm + graph context formatter + injection point
2. **P1 — Smoke** (1 week): 6-task × 3 variants (baseline / D-only / A+D) × N=2
3. **P2 — Measurement** (1 week): 30-task × 3 variants × N=3 (McNemar paired)
4. **P3 — Paper draft** (1-2 weeks): 3-page 논문

### 7.2 예상 smoke green 조건
- A+D NET > baseline NET in ≥4/6 tasks
- A+D AR ≈ NET (이전 R3-α에서의 false positive 재현 안 함)

### 7.3 예상 measurement outcome 시나리오
- **Green**: A+D ablation positive → direct paper
- **Yellow**: A+D ≈ baseline but D only positive → "subgraph content enough" framing
- **Red**: A+D < baseline → Plan C (intent-to-query)로 pivot

---

## 8. 다음 단계 확인 필요

1. **Direction A+D 권고에 동의하시나요?** 다른 direction 조합 원하시면 재논의
2. **3-page scope 유지?** 아니면 longer venue 고려?
3. **Benchmark 확정**: WebArena-Verified GitLab 유지 vs 원조 WebArena / Online-Mind2Web 전환?
4. **모델**: GPT-4o-mini 유지 vs 업그레이드 (ColorBrowserAgent급은 불가하지만 GPT-4o는 가능)?

답변 후 Direction A+D 구체 설계 (KG subgraph extraction algorithm spec + injection format + evaluation protocol)로 들어갈 수 있습니다.
