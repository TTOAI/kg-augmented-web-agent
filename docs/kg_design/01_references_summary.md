# 01. 배경 문헌 요약 및 Introduction 초안 대비표

## 이 문서의 목적

`docs/kg_design/references/`의 9편(KG 3 + Agent 3 + Web 3)과 Introduction 초안을 한 번에 훑어볼 수 있게 정리한다. 각 문헌에 대해 (a) 본 연구 논문에서 인용할 핵심 주장, (b) 본 연구 설계를 뒷받침하는 지점, (c) 조심하거나 반대 근거가 될 수 있는 지점을 적는다. 마지막 §4는 Introduction 초안의 주장별로 어느 문헌이 뒷받침하고 어느 지점이 아직 공백인지 표로 정리한다.

인용 키는 파일명 기준 `kg_01 / kg_02 / kg_03 / agent_01 / agent_02 / agent_03 / web_01 / web_02 / web_03`로 쓴다.

---

## 1. Knowledge Graph

### kg_01 — KG의 정의와 경계

**핵심 주장**
- KG의 단일 합의 정의는 없다. Hogan 등은 "실세계 지식을 축적·전달하기 위해 의도된 데이터 그래프"로 폭넓게 정의한다.
- KG는 단순 그래프 저장이 아니라 schema, identity, context, (선택적) reasoning을 포함한다.
- KG = RDF도, KG = graph DB도, KG = ontology도 아니다. RDF는 표현 방식, graph DB는 저장 기술, ontology는 개념 구조.
- KG는 CWA가 아니라 OWA를 따르는 경우가 많다(없는 사실이 곧 거짓은 아님).

**본 연구에 쓸 수 있는 지점**
- "site-specific KG"를 정의할 때 단순한 그래프가 아니라 schema + identity + context가 있는 지식 체계로 위치시킬 근거.
- RDF/SPARQL에 매이지 않아도 됨을 명시(property graph도 KG). 본 연구는 가벼운 property graph류로 갈 수 있음.

**조심할 지점**
- 넓은 정의를 취하면 "우리 것도 KG"라고 말하기 쉬워지지만, identity resolution과 schema 구분이 없으면 비판받기 쉽다. 본 연구의 KG가 최소 어떤 요소를 만족하는지 명시 필요.

---

### kg_02 — RDF/OWL/SPARQL 관점 내부 구조 + LLM 시대 KG의 의의

**핵심 주장**
- KG 내부는 4층으로 읽을 수 있다: RDF(사실 저장), RDFS(기본 스키마), OWL(온톨로지/의미/추론), SPARQL(질의).
- LLM 시대 KG가 다시 중요해진 이유 5가지: **업데이트 가능성, hallucination 완화, 관계 중심 질의, 컨텍스트 압축, 통제/검사 가능성**.
- 효과는 그래프 품질, entity linking 정확도, 검색 단위(노드/트리플/패스/서브그래프), KG→LLM 입력 변환 방식에 크게 좌우됨.
- 결론은 "LLM vs KG"가 아니라 "LLM + KG 하이브리드".

**본 연구에 쓸 수 있는 지점**
- 본 연구가 주장할 "KG = planning substrate"의 정당성을 5가지 이유 중 **관계 중심 질의, 컨텍스트 압축, 통제 가능성**과 연결할 수 있다.
- "KG에 추가 학습/정보 주입이 있으면 같은 사이트에서 반복 과제가 나아질 수 있다"는 주장을 "업데이트 가능성"으로 뒷받침 가능.

**조심할 지점**
- "효과는 그래프 품질에 크게 좌우됨"은 양날의 검. 이전 m0-sitekg의 net negative 결과는 "그래프 품질이 낮거나 retrieval 단위가 부적절했다"로 해석할 수 있어야 한다.
- KG→LLM 형식 변환 자체가 과제라는 지적은 본 연구에서 반드시 다뤄야 한다. 그냥 트리플을 붙이면 verbosity가 늘어나 오히려 손해.

---

### kg_03 — RAG / GraphRAG / KG-QA 비교

**핵심 주장**
- 세 방식은 "질문을 받았을 때 어떤 외부 지식을 어떻게 꺼내 어느 수준의 구조로 활용하는가"의 차이.
- RAG: 텍스트 청크 단위. 관계 중심 질문에 약함.
- GraphRAG: 노드·엣지·패스·서브그래프 단위. relational retrieval에 강하지만 그래프 구축 비용과 retrieval 설계 난도가 높음.
- KG-QA: 질문을 SPARQL 등 실행 가능한 형식으로 바꿔 KG 위에서 정확히 계산. 정확성/추적성/구조적 일관성은 강함. 스키마 불일치, entity/schema/text-to-SPARQL 오류에 취약.
- 실무는 셋이 경쟁이 아니라 계층적 결합인 경우가 많음.

**본 연구에 쓸 수 있는 지점**
- Introduction 초안의 "executable intent-to-query" 주장은 사실상 **KG-QA 구조를 web agent planning으로 이식하는 시도**라고 재프레이밍할 수 있다. 이것이 본 연구의 위치 선정에 핵심.
- GraphRAG의 "엔터티·관계를 명시적으로 표현해 multi-hop을 살린다"는 주장은 web agent에서 navigation 관계 추론에 직접 전이됨.

**조심할 지점**
- KG-QA의 대표적 실패 모드(entity linking 오류, schema linking 오류, text-to-SPARQL 오류)는 본 연구에 그대로 재현될 위험. 이 실패 모드 각각을 어떻게 평가·완화할지 설계에 반영해야 한다.
- RAG vs GraphRAG vs KG-QA 비교가 대체로 **QA 과제**를 전제함. "action 과제에서도 같은 구분이 유효한가?"는 본 연구가 메워야 할 공백이기도 하다.

---

## 2. AI Agent Engineering

### agent_01 — Agent Engineering의 정의와 범위

**핵심 주장**
- Agent Engineering은 "생성 모델을 중심에 둔 다단계 행동 시스템을 평가 가능하고 안전하며 운영 가능한 형태로 공학화하는 일".
- 핵심 구성요소: augmented LLM, orchestration/planning, tool interface(ACI), memory/state, evaluation/guardrails.
- 실무에서는 복잡한 자율보다 **단순·통제 가능한 구조**가 더 많이 성공(MAP: 68% 에이전트가 인간 개입 전 10 스텝 이하).
- Prompt Engineering과 다르다. 루프·복구·평가가 핵심.

**본 연구에 쓸 수 있는 지점**
- "KG를 추가해도 전체 시스템은 단순·통제 가능해야 한다"는 설계 가드레일로 사용. 복잡성이 늘면 실무적 설득력이 떨어짐.
- 본 연구가 제안할 구조가 **tool/observation/context 중 어느 축을 건드리는가**를 명확히 서술할 때 참조.

**조심할 지점**
- "많은 자율성 < 통제된 자율성"이라는 문헌 경향. KG를 planning substrate로 쓴다는 주장이 **자율성 확대로 읽히면 안 된다**. 오히려 "planner가 의존하는 외부 구조를 명시해 통제·검증을 쉽게 한다"는 관점이 낫다.

---

### agent_02 — Agent의 표준 참조 아키텍처

**핵심 주장**
- de facto 참조 아키텍처: **Planner + Memory + Tools + Guardrails + Evaluator** 폐루프.
- Planner는 생각만 하는 블록이 아니라 관측과 evaluator 피드백을 받아 계획을 수정하는 controller.
- Memory는 working / episodic / long-term으로 나뉘고, "많이 저장"보다 **무엇을 언제 저장·읽을지**가 중요.
- Evaluator는 Planner와 대등한 핵심 블록.

**본 연구에 쓸 수 있는 지점**
- 본 연구의 "site-specific KG"는 표준 아키텍처의 **Memory(특히 long-term / domain knowledge)** 블록에 해당한다고 위치시킬 수 있다. "Planner가 참조하는 외부 구조적 지식."
- "무엇을 언제 저장·읽을지"를 정하는 설계 문제가 곧 본 연구의 핵심 설계 문제가 된다.

**조심할 지점**
- Introduction 초안은 KG를 "planning substrate"로 명명하는데, 이 명명이 표준 분류와 긴장을 만든다. Memory의 하위 유형인가, 아니면 planner 자체의 일부인가? 명확한 정의 필요.

---

### agent_03 — single/multi × workflow/full agent 2×2 분류

**핵심 주장**
- 두 축: **제어 방식**(workflow ↔ full agent)과 **주체 수**(single ↔ multi).
- 멀티 LLM 호출 = 멀티 에이전트 아님. 여러 단계 = full agent 아님.
- 실전은 보통 single workflow → multi-component workflow → single full agent → multi-agent 순으로 복잡도를 올려야 안정적.
- 멀티 에이전트가 항상 더 좋지 않다. 토큰 15배, coordination overhead.

**본 연구에 쓸 수 있는 지점**
- 본 연구의 baseline은 **single full agent** 자리에 위치한다고 정확히 기술. "KG 도입"이 자동으로 multi-agent를 의미하지 않음을 강조.
- 평가 지표에 compute 비용(토큰, 스텝 수)을 함께 두어야 "KG 효과가 compute 증가와 구분된다"를 입증 가능.

**조심할 지점**
- KG를 별도 "검색 에이전트"로 외장하면 multi-agent 쪽으로 끌려가 설계가 과도해짐. 본 연구는 **단일 에이전트 안의 tool/memory 계층**으로 KG를 제한하는 편이 문헌 흐름과 정합적.

---

## 3. Web Agent

### web_01 — Web Agent 정의·발전·현재 위치

**핵심 주장**
- Web Agent = 자연어 목표 → 웹 관찰 → 행동 계획·추론 → 브라우저 grounding·실행의 폐루프.
- 웹은 partially observable, dynamic, long-horizon.
- "From Grounding to Planning"은 **주된 병목이 grounding보다 planning**이라 보고.
- 성능 수준: WebArena에서 GPT-4 에이전트 14.41% vs 사람 78.24%. 여전히 큰 격차.
- 안전/신뢰성은 별도 축. ST-WebAgentBench, WASP.

**본 연구에 쓸 수 있는 지점**
- "planning이 주 병목"은 본 연구의 문제 정의를 지탱하는 핵심 근거. Introduction에서 이미 인용됨.
- Web 환경이 relational·dynamic·partially observable이라는 특성은 "site-specific KG"의 필요성을 설득하는 축.

**조심할 지점**
- "planning이 병목"이라는 결론은 특정 벤치마크·모델에서의 분석. 본 연구의 설정(WebArena-Verified text-centric + 현세대 LLM)에서도 같은 병목이 유효한지 자체 실험으로 확인 필요.
- ST-WebAgentBench 축(안전·정책 준수)은 본 연구 scope에서 빠질 가능성 큼. 빠뜨리는 이유 명시 필요.

---

### web_02 — Web Agent 표준 아키텍처(5 블록)

**핵심 주장**
- 논문 정통 표기는 perception → planning & reasoning → execution.
- 5 블록 재구성: **Planning + Memory + Tools + Guardrails + Evaluator**.
- Memory 예: AWM(Agent Workflow Memory)이 재사용 가능한 workflow를 쌓아 Mind2Web·WebArena에서 상대 성공률 24.6%, 51.1% 개선 보고.
- Evaluator는 런타임 evaluator와 벤치마크 evaluator 두 층. WebArena Verified는 deterministic/backend-state/JSON schema로 평가 신뢰성을 올림.

**본 연구에 쓸 수 있는 지점**
- AWM이 강력한 직접 비교군. "site-specific KG가 AWM 대비 어느 부분에서 이득인가?"가 본 연구의 정체성 질문이 됨.
- Evaluator 축은 이미 WebArena Verified를 쓰고 있으므로 본 연구의 측정 신뢰성이 높다는 근거로 사용 가능.

**조심할 지점**
- AWM이 이미 24~51% 상대 개선을 보고했다면, 본 연구의 "KG 도입"이 AWM 대비 뚜렷한 우위를 보이지 못하면 독립 기여로 주장하기 어렵다.
- Guardrails 축을 빼고 싶다면 scope 제한 근거 필요.

---

### web_03 — Web Agent 최신 아키텍처 6 갈래

**핵심 주장**
- 단일 정답 아키텍처는 없다. 6갈래로 분화.
  1. 모듈형 파이프라인(WebAgent)
  2. 멀티모달 end-to-end 단일 에이전트(WebVoyager, SeeAct)
  3. 계층 제어/멀티에이전트(SteP, Agent-E, WebPilot)
  4. search/model-based planning(Tree Search, WebDreamer)
  5. memory/guideline/evaluator augmentation(AutoGuide, AWM, Reflexion 계열)
  6. hybrid tool-use(Beyond Browsing)
- AgentOccam은 오히려 observation/action space 정렬만으로 성능을 내고, "복잡한 보조 모듈"에 대한 비판적 baseline.

**본 연구에 쓸 수 있는 지점**
- 본 연구는 **5번(memory/guideline augmentation) + 1번(모듈형 파이프라인)** 사이에 위치한다고 기술 가능.
- AgentOccam 관점을 진지하게 받아들여, "관측/행동 공간 정렬만으로 되는가 vs KG가 추가로 필요한가"를 ablation으로 설계해야 한다.

**조심할 지점**
- "KG를 넣어서 좋았다"만으로는 부족. AgentOccam처럼 **단순 해법이 KG 해법을 이긴다면 논문이 무너진다**. compute-matched 및 memory-only baseline이 반드시 필요.
- WebDreamer의 model-based planning이 planning-as-simulation의 대안이라는 점. KG-guided planning과 어느 지점이 다른지 대비 서술 필요.

---

## 4. Introduction 초안 주장별 대비표

Introduction 초안은 확정안이 아니라 아이디어 스케치. 각 주장에 대해 (a) 문헌 근거, (b) 본 연구에서 따로 입증해야 할 공백을 구분한다.

> **⚠️ Scope 축소 반영**: 본 연구는 국내 3-page 논문(`07_scope_and_justifications.md` 참조) scope로 축소됨에 따라 아래 주장 중 일부(특히 5, 7, 8)는 본 논문에서 검증 대상이 아니라 **future work**로 유예된다. 각 주장 항목의 **[scope]** 표시로 구분:
> - **[IN]**: 본 3-page 논문에서 다룸
> - **[FW]**: future work로 이관 (본 논문 주장·실험 안 함)
> - **[CONTEXT]**: 논문 Introduction의 배경 서술용만 인용

### 주장 1. "Web agent 병목은 grounding보다 planning에 있다" **[CONTEXT]**
- **근거**: web_01, Introduction 주석 [5](From Grounding to Planning).
- **용도**: 본 논문 Introduction 배경 서술로 인용. 본 연구가 자체 측정으로 입증하지는 않음.

### 주장 2. "KG는 외부 명시 지식 장치로 LLM과 보완 관계" **[CONTEXT]**
- **근거**: kg_02(5가지 이유), agent_01(augmented LLM), agent_02(long-term memory).
- **용도**: 본 논문 Introduction에 "왜 KG를 web agent에 붙이는가"의 motivation.

### 주장 3. "기존 web agent 연구는 KG를 action planning에 쓴 사례가 거의 없다" **[IN — narrow]**
- **근거**: web_03의 6 갈래에 KG 기반 planning이 독립 축으로 등장하지 않음.
- **본 논문 사용**: Related Work 섹션에 간략 언급 (3-page scope). 철저한 survey mapping은 future work.

### 주장 4. "natural language intent → executable graph query" **[IN — KG 내부 메커니즘]**
- **근거**: kg_03의 KG-QA 전통.
- **본 논문 사용**: Method 섹션에 JSON tool-use 기반 query 설명. 결정 근거는 `02 쟁점 #1` 참조.

### 주장 5. "KG를 retrieval backend가 아닌 planning substrate로" **[FW]**
- **근거**: 이 구분이 문헌에서 명확히 정식화되어 있지 않음.
- **유예 이유**: "planning substrate" 주장은 **KG-retrieval ablation**이 뒷받침해야 설득력 가짐. 3-page scope에서 해당 ablation 수행 불가. 본 논문 주장을 "site-specific KG 도입"으로 narrow (`07 §1`). Future work.

### 주장 6. "site 구조·행동 제약·네비게이션 관계·검증 규칙을 모두 KG에 담자" **[IN — KG 스키마]**
- **근거**: web_02(5 블록의 memory/tools), web_01(웹의 relational 특성).
- **본 논문 사용**: Method 섹션의 KG 스키마 설명. StatePattern / InfoType / Action / Trust 기반(`02 쟁점 #3`).

### 주장 7. "incremental KG update로 continual site adaptation" **[FW]**
- **근거**: kg_02(업데이트 가능성), web_02(AWM의 continual memory).
- **유예 이유**: longitudinal empirical 검증 (3-round replay)은 3-page scope 밖. Architecture에만 trust evolution을 포함하고 실험은 future work. `07 §11`의 Limitation에 명시.

### 주장 8. "baseline + 여러 ablation variants로 효과 분리" **[FW 대부분]**
- **근거**: agent_03(compute-matched의 필요성), web_03(AgentOccam식 단순 baseline).
- **본 논문 사용**: Baseline vs Full KG 2-variant 비교만. 세분 ablation(compute-matched / URL-emission-only / KG-retrieval / scaling)은 **전부 future work**로 분리(`02 쟁점 #4`, `07 §1`). 대신 본 실험 Method에 token/step 수치를 함께 보고해 compute confound 사전 차단.

---

## 5. 이 요약이 다음 작업에 주는 입력

- **Paper Introduction 배경 서술 (CONTEXT)**: 주장 1, 2 — web agent planning 병목 + KG의 LLM 보완 역할.
- **Paper Related Work (IN)**: 주장 3 — 기존 web agent × KG 교차 연구 공백.
- **Paper Method (IN)**: 주장 4, 6 — Intent → query 구조, site-specific KG 스키마.
- **Paper Limitation / Future Work (FW)**: 주장 5, 7, 8 — planning substrate 구분, continual adaptation, fine-grained ablation.

- **02_open_questions.md 쟁점들은 설계 결정의 내부 근거** — 본 논문 본문에는 대부분 명시적으로 들어가지 않음. 단 Method 섹션에서 "왜 이런 tool schema인가"를 간단히 설명할 때 참조.
- 주장 3("기존 연구 부재")의 공백은 별도 related-work 매핑 작업으로 뺀다(`03_related_work_mapping.md`).
- 주장 1(병목)은 본 연구 실험의 선결 확인 항목으로 분리(`04_baseline_failure_analysis.md`).

이 세 후속 문서의 초안을 여기서 바로 이어갈 필요는 없다. 먼저 02의 4 쟁점에 대한 답을 쌓아야 나머지 문서의 방향이 정해진다.
