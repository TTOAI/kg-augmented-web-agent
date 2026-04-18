# 03. Related Work Mapping

## 이 문서의 목적

Introduction 초안 주장 3("기존 web agent 연구는 KG를 action planning에 쓴 사례가 거의 없다")을 뒷받침 또는 조정하기 위해, 본 연구가 직접 비교·구별해야 할 접근을 계열별로 매핑한다. 각 접근에 대해 (a) 핵심 주장, (b) 본 연구와의 공통점, (c) 본 연구만 제공하는 차별 지점을 기록한다.

영역을 세 축으로 나눈다:
- §1. Web agent memory / guideline / workflow 계열 — 가장 가까운 이웃
- §2. GraphRAG / KG-QA 계열 — KG 활용은 하지만 action이 아니라 QA 중심
- §3. Web agent planning / search 계열 — planning 축 경쟁자

각 항목 뒤에 "본 연구 대비 포지셔닝 한 줄"을 붙인다.

---

## 1. Memory / Guideline / Workflow 계열 (가장 가까운 이웃)

### AWM — Agent Workflow Memory (Wang et al., 2024)

**핵심**: 과거 trajectory에서 재사용 가능한 workflow를 유도해 memory에 저장. 이후 task에서 관련 workflow를 prompt에 주입. Mind2Web/WebArena에서 상대 성공률 24.6%, 51.1% 개선 보고.

**공통점**:
- 사이트별 실행 경험을 externalized knowledge로 축적
- continual improvement over repeated tasks
- 텍스트 중심 web agent 가정

**차이점**:
- AWM의 단위는 **trajectory-level workflow**(자연어 절차 기술). 본 연구는 **state-transition graph**(관계 구조).
- AWM은 **context injection**(retrieval 계열). 본 연구는 (b) rewrite + (c) validate의 **structural operator**.
- AWM은 workflow를 단순 추가·재사용. 본 연구는 **trust evolution**으로 기존 구조의 신뢰도를 동적 업데이트.
- AWM은 task-level 재사용(유사 task 패턴 매칭)이 강점. 본 연구는 task 간 구조 공유(같은 사이트의 다른 task도 KG를 공유) 강점.

**포지셔닝**: "AWM은 trajectory를 기억하는 retrieval-augmented memory이고, 본 연구는 state-transition을 기억하는 structural planning substrate이다."

---

### AutoGuide (Fu et al., 2024)

**핵심**: Offline trajectory에서 context-aware guidelines를 추출. context identification + guideline extraction 모듈로 "어떤 상황에서 어떤 행동 규칙이 유효한가"를 자연어 guideline으로 만들어 prompt에 넣음.

**공통점**:
- 과거 경험에서 재사용 가능한 지식을 추출
- 자연어 intent와 매칭된 지식만 선택적으로 주입

**차이점**:
- AutoGuide의 knowledge는 **비정형 자연어 규칙**. 본 연구는 **formal StatePattern + Action**.
- AutoGuide는 **prompt injection**(retrieval 계열). 본 연구는 plan 재구조화.
- AutoGuide의 guideline은 품질이 offline trajectory 품질에 종속. 본 연구의 KG는 crawl로 verified fact를 확보 + trust 레벨로 품질 차등.

**포지셔닝**: "AutoGuide는 자연어 guideline의 contextual retrieval. 본 연구는 구조화된 state graph 기반 plan 연산."

---

### Reflexion (Shinn et al., 2023)

**핵심**: 실행 후 언어적 reflection을 episodic memory에 저장, 다음 시도에서 reflection을 context로 투입. Actor + Evaluator + Self-Reflection 3-컴포넌트.

**공통점**:
- 실행 피드백을 외부 지식으로 축적
- evaluator 루프를 포함

**차이점**:
- Reflexion의 memory는 **per-task episodic**(같은 task 재시도용). 본 연구의 KG는 **site-level**(task 간 공유).
- Reflexion은 실패 원인 분석을 언어로. 본 연구는 trust 레벨의 수치적 업데이트.

**포지셔닝**: "Reflexion은 task 내 실패 반성. 본 연구는 사이트 내 지식 진화."

---

## 2. GraphRAG / KG-QA 계열

### GraphRAG (Microsoft / Edge et al., 2024)

**핵심**: 텍스트를 그래프로 인덱싱 → 그래프 기반 retrieval → LLM 생성. Graph-based indexing + graph-guided retrieval + graph-enhanced generation 3 단계.

**공통점**:
- 그래프 구조가 relational retrieval의 base가 됨
- multi-hop 관계 포착

**차이점**:
- GraphRAG는 **QA 출력**이 목적. 본 연구는 **action plan 출력**이 목적.
- GraphRAG는 검색 결과를 context에 삽입. 본 연구는 결과를 plan operator로 사용.
- GraphRAG는 **문서 엔터티 그래프**(텍스트에서 추출). 본 연구는 **사이트 상태 전이 그래프**(사이트 구조에서 관찰).

**포지셔닝**: "GraphRAG는 문서 그래프 기반 질의응답. 본 연구는 사이트 상태 그래프 기반 행동 계획."

---

### KG-QA (semantic parsing / subgraph retrieval 전통)

**핵심**: 자연어 질문을 SPARQL 또는 실행 가능 형식으로 번역해 KG에서 답 계산. 또는 질문 관련 subgraph 추출.

**공통점**:
- "자연어 → 실행 가능 질의 → KG에서 정답 계산" 패러다임 차용

**차이점**:
- KG-QA 출력은 **최종 답**(정보). 본 연구 출력은 **plan 연산자**(행동).
- KG-QA는 text-to-SPARQL 실패 모드(entity/schema linking, 문법 오류)에 취약. 본 연구는 **enum-제약 JSON tool use**로 구조적 차단.
- KG-QA는 static KG 대상. 본 연구는 trust evolution을 가진 dynamic KG.

**포지셔닝**: "KG-QA는 사실을 묻고 답하는 파이프라인. 본 연구는 상태를 묻고 행동을 내는 파이프라인."

---

## 3. Web Agent Planning / Search 계열

### Tree Search for Language Model Agents (Koh et al., 2024)

**핵심**: base LM agent 위에 best-first tree search wrapper를 얹어, 실제 interactive web 환경에서 여러 action branch를 탐색.

**공통점**:
- planner 위에 외부 구조를 추가해 의사결정 보강

**차이점**:
- Tree Search는 **실제 환경에서 분기 탐색**(expensive). 본 연구는 **KG로 분기를 사전 가지치기**.
- Tree Search는 value function으로 상태 평가. 본 연구는 KG의 state_matches로 평가.
- Tree Search는 per-task 탐색. 본 연구의 KG는 사이트 수준 재사용.

**포지셔닝**: "Tree Search는 런타임 탐색으로 planning을 보강. 본 연구는 구조적 지식으로 plan을 축약."

---

### WebDreamer (Gu et al., 2024)

**핵심**: Reactive agent 대신 LLM으로 action 결과를 자연어 시뮬레이션(월드모델) → trajectory를 scoring → 최적 action 실행. Model-based planning.

**공통점**:
- 실행 전 상태 전이 예측
- planner가 향후 상태를 고려

**차이점**:
- WebDreamer는 **LLM을 world model로** 사용. 본 연구는 **명시적 KG를 world model로** 사용.
- WebDreamer의 시뮬레이션은 자연어 hallucination 위험. 본 연구는 verified state_transition 기반.
- WebDreamer는 task별 시뮬레이션 비용. 본 연구는 KG 구축 1회.

**포지셔닝**: "WebDreamer는 LLM 시뮬레이션 기반 planning. 본 연구는 명시적 state graph 기반 planning."

---

### SteP — Stacked Policies (Sodhi et al., 2023)

**핵심**: web agent를 동적 정책 스택으로 정의. 각 시점 스택 최상단 policy가 행동·하위 policy push·pop 결정.

**공통점**:
- web agent에 구조적 계층 도입

**차이점**:
- SteP는 **policy hierarchy**(코드 정의). 본 연구는 **state graph**(관찰 기반).
- SteP는 어느 policy를 호출할지의 제어. 본 연구는 plan 구조 자체의 수정.

**포지셔닝**: "SteP는 정책 스택 제어. 본 연구는 상태 그래프 기반 plan 재구조화."

---

### Agent-E / WebPilot (hierarchical multi-agent)

**핵심**: planner + browser navigator 또는 Global + Local 계층형 멀티 에이전트.

**공통점**:
- planning과 execution의 분리

**차이점**:
- 이들은 **agent 수를 늘려** 전문화. 본 연구는 **단일 agent + KG**.
- 통신 오버헤드 없음. KG는 static knowledge asset.

**포지셔닝**: "계층형 멀티 에이전트는 주체를 나누어 분업. 본 연구는 지식을 외장화."

---

### AgentOccam (Zhu et al., 2024)

**핵심**: compound policy / 보조 모듈 없이 observation/action space alignment만으로 성능 도달. note/stop/branch/prune 같은 planning-action과 간결한 memory tree.

**공통점**:
- "단순함이 낫다"의 방향

**차이점** (중요):
- AgentOccam은 **KG가 필요 없음**을 시사. 본 연구는 **KG가 필요한 task 유형이 있음**을 입증해야 함.
- 본 연구의 실험 설계(쟁점 #4 ablation "URL-emission-only")가 이 입장에 대한 직접적 반박 데이터가 됨.
- AgentOccam과 본 연구의 KG-retrieval(fact injection) ablation이 유사할 수 있음 — 이 구분을 empirical로 보여야 함.

**포지셔닝**: "AgentOccam은 observation/action 정렬으로 충분하다는 주장. 본 연구는 그 한계를 site-specific state-transition 지식이 메울 수 있다는 주장."

---

## 4. 결정 — 본 연구의 차별성 한 줄 (scope 축소 반영)

### 4-1. 본 논문(국내 3-page)용 narrow 버전

> 본 연구는 text-centric web agent에 **site-specific Knowledge Graph**를 결합한 구조를 제안하고, WebArena-Verified GitLab task에서 baseline 대비 task 성공률 개선을 보인다.

scope 근거: `07_scope_and_justifications.md §1`. 탑티어용 세분 기여(planning substrate ≠ retrieval, structural operator vs facts injection 등)는 future work로 분리.

### 4-2. 탑티어용 full 버전 (현재는 보류)

다음 full 주장은 후속 연구에서 ablation으로 입증 예정:

> site-specific state-transition KG가 planning substrate로 기능한다. (i) 출력이 facts가 아니라 plan tree에 적용되는 structural operator이고, (ii) sub-goal 경계에서 실행을 제어하는 state predicate이며, (iii) trust 레벨에 따라 개입 강도가 modulate되는 adaptive 정책이다.

이 full 주장은 KG-retrieval ablation 및 URL-emission-only ablation이 뒷받침하며, 본 논문의 scope 밖이다. 이 관련 연구 맵(§1~§3)은 두 framing 모두를 지원한다.

## 5. 남은 조사 항목 (우선순위 낮음) + Concurrent work hedge

- **Knowledge graph for web tasks 직접 검색**: "site-specific KG" + "web agent" 2025~2026 arxiv.
- **API-based web agents** (Beyond Browsing 계열)와의 관계: API KG도 일종의 structured 지식.
- **WebVoyager 및 멀티모달 계열**: 본 연구의 text-centric scope 정당성 보강.

### Future Work Roadmap (본 연구를 1단계로 한 후속 연구)

본 연구는 **1단계: Site-specific state-transition KG** — URL target 기반. 본 연구에서
관찰된 per-type heterogeneous effect (MUT 제한)는 2단계 연구의 motivation.

**2단계 (후속 논문 scope)**:
- **Action-sequence InfoType schema (C8)** — current state-transition → state + action
  sequence hybrid. AWM (workflow-level memory)와 통합 가능. MUT task에서 "form submit →
  commit" 순차 action hint 제공.
- **Hook-level ablation (H3)** — 4-5 variants (Baseline, A only, A+B, A+B+C, A+B+C+D)로
  각 Hook의 individual contribution 정량화.
- **Trust adaptive thresholding** — current fixed policy (verified+declared+inferred
  accept)를 context-dependent로 확장.

1단계 결과 (특히 per-type heterogeneous MUT-) 가 2단계 연구의 direct evidence 역할.

### Concurrent work disclosure (논문 본문 Related Work 문단 말미 권장)

> "The web agent literature is evolving rapidly with concurrent work in 2025-2026 on
> memory-augmented, hierarchical, and tool-use hybrid agents. We position our contribution
> within the trajectory-memory (AWM [14]) and KG-based retrieval (GraphRAG [8]) lines;
> parallel developments in self-supervised site adaptation and multi-modal grounding are
> complementary directions beyond our 3-page scope."

**목적**: "최근 연구 누락" reviewer 반박에 대한 pre-emptive 방어. 본 3-page scope는
text-centric + single-site로 제한되므로 multi-modal / multi-site concurrent work를 모두
다룰 수 없음을 명시.

본 논문 3-page에 들어갈 Related Work 섹션은 약 0.3 page. 현 §1~§3 12개 접근 중 **논문 Related Work에서 언급할 핵심 3~4개만 선별** 필요:
- **AWM** (trajectory memory): 가장 가까운 비교군, 필수 언급
- **GraphRAG 또는 KG-QA**: KG 계열 대표
- **AutoGuide**: context-aware guideline 대비
- **AgentOccam** (옵션): "단순 해법 vs KG" 대비

나머지는 부록 또는 아예 생략.
