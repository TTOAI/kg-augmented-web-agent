# 본 연구 용어집

**작성일**: 2026-04-11 (v2 — Hierarchical SiteKG 재설계 반영)
**대상 연구**: `01_skg_web_agent_proposal.md` (Hierarchical Site Knowledge Graph 기반 LLM 웹 에이전트)
**문서 유형**: 단일 source of truth — 다른 문서/코드는 이 문서를 참조한다.

## 0. 사용 안내

본 문서는 **본 연구에서 쓰이는 용어를 한 곳에 정리**한 reference이다. 같은 개념을 다른 이름으로 부르거나 같은 이름이 다른 의미로 쓰이는 일을 막는 게 목적이다.

- **카테고리 구성** (alphabetical 아님): ① 핵심 KG 용어 → ② 역사적 변천 → ③ KG 엔티티 → ④ 에이전트 실행 단위 → ⑤ 실험 설계 용어 → 부록 (WidgetType 카탈로그 + GitLab 위젯 예시)
- **본문은 한국어, 식별자는 영문**.
- **본 문서의 용어는 v2 (Hierarchical SiteKG) 기준**이다. 현재 코드는 아직 v1 옛 이름(`PageType`, `ActionSchema`, `KBStore`, `KBBundle`)을 쓰고 있지만, 새 문서·논문·후속 코드(M0 이후)는 이 문서의 용어를 따른다. 옛↔새 매핑은 §2.
- 각 항목은 **1줄 정의 + 사용 맥락 + (해당되면) 코드 매핑 + (해당되면) 인접 용어와의 차이** 순서.

---

## 1. 핵심 KG 용어

### 1.1 Hierarchical Site Knowledge Graph (SiteKG / SKG)
**정의**: 한 웹사이트를 두 레이어 그래프로 표현한 directed labeled graph.
```
SiteKG = (G_page, {G_widget(p) for p ∈ V_page}, M_task, W_taxonomy)
```
- Layer 1: page-level graph (페이지 간 navigation)
- Layer 2: per-page widget graph (페이지 내 인터랙션 요소)
- W_taxonomy: universal WidgetType taxonomy
- W_taxonomy: universal WidgetType taxonomy

**사용 맥락**: 본 연구의 핵심 데이터 구조. 매 LLM 호출에서 retrieval/traversal/dynamic update의 대상.
**약어**: SiteKG (코드/문서 일관 표기). SKG도 허용 (논문 제목 등).
**중요한 구별**: v1 SiteKG는 page graph만 다뤘다. v2부터는 hierarchical (page + widget). 본 문서에서 "SiteKG"라 하면 항상 v2 hierarchical을 의미한다.
**저장소**: `runtime/sitekg/store.py` `SiteKGStore` (M0 이후).

### 1.2 Page Layer
**정의**: SiteKG의 첫 번째 레이어. `G_page = (V_page, E_page)`. 페이지 *간* 이동을 표현.
- V_page = PageNode 집합
- E_page = NavigationEdge 집합

**사용 맥락**: BFS path finding(§1.11), navigation 결정의 대상. v1 SiteKG가 다뤘던 전부.

### 1.3 Widget Layer
**정의**: SiteKG의 두 번째 레이어. 각 PageNode `p`마다 `G_widget(p) = (V_widget(p), E_widget(p))`. 페이지 *내부* 인터랙션을 표현.
- V_widget(p) = WidgetNode 집합 (p에 속하는 인터랙션 요소)
- E_widget(p) = InteractionEdge 집합 (위젯 간 활성/의존 관계)

**사용 맥락**: 본 연구가 새로 도입한 레이어. selective widget retrieval, widget interaction sequencing, widget auto-discovery의 대상. **본 연구의 학술적 가치는 대부분 이 레이어에서 나온다.**
**구별**: page layer가 *어디로 갈지*를 다룬다면, widget layer는 *현재 페이지에서 무엇을 클릭할지*를 다룬다. 둘은 직교 차원.

### 1.4 PageNode (V_page의 원소)
**정의**: 사이트 내에서 의미상 구분되는 페이지 유형 1건. 한 사이트의 한 페이지 카테고리에 대응.
**필드**: page_node_id, site_id, page_key, display_name, description, url_patterns, structural_signals, **widget_nodes (★v2 신규)**, **widget_edges (★v2 신규)**.
**사용 맥락**: "dashboard", "issues_list", "project_overview" 같은 page key로 식별.
**중요한 구별**: PageNode는 *구체 URL 1건*이 아니라 *URL 패턴이 묶인 페이지 유형*이다. 또한 v2부터 PageNode는 *그 자체로 sub-graph를 가지는 컨테이너* — widget_nodes, widget_edges를 들고 있다.
**옛 이름**: `PageType` (v1, §2.3 참고).

### 1.5 WidgetNode (V_widget의 원소) — v2 핵심 신규
**정의**: 한 PageNode에 속하는 인터랙션 가능한 페이지 내 요소 1건. KG가 박는 *minimum viable* 정보만 표현 (§4.1.6 원칙).
**필드** (★ minimum viable, 2026-04-11 정정): widget_node_id, site_id, page_key, widget_key, display_name, **description (★ 핵심)**, task_relevance_tags (자유 string), **locator_strategy / locator_value (★ stable references)**, **visibility_condition (★ conditional state)**, **side_effects (★ causal effects)**.
**제거된 필드**: ~~widget_type~~ — DOM의 tag/role/class에서 직접 추출. KG에 박지 않음 (§4.1.5 폐기).
**예 (GitLab issues_list)**: `search_box`, `label_dropdown`, `state_tabs`, `sort_dropdown`, `pagination`.
**사용 맥락**: Phase 1 widget retrieval의 출력 단위. LLM에 노출되는 정보의 가장 중요한 단위.
**중요한 구별**: WidgetNode는 *task semantics*나 *type 분류*가 아니라 *위치/의존/조건/식별*의 4가지 관점에서 정의된다. type/category는 DOM 자체에 이미 있으므로 KG에 박지 않는다.
**옛 이름**: 없음 — v2 신규.

### 1.6 NavigationEdge (E_page의 원소)
**정의**: 한 페이지에서 다른 페이지로 가는 전이 1건. `source_page_key → target_page_key` (source ≠ target).
**필드**: navigation_edge_id, site_id, action_key, source_page_key, target_page_key, **trigger_widget_key (★v2 신규)**, description, preconditions, postconditions.
**예**: `click_dashboard` (`home → dashboard`), `view_contributors` (`project_overview → contributors`).
**사용 맥락**: BFS path finding의 엣지. 어느 위젯이 trigger하는지(`trigger_widget_key`)도 명시.
**옛 이름**: `ActionSchema`의 *page-changing* 부분 (v1, §2.3 참고).

### 1.7 InteractionEdge (E_widget의 원소) — v2 핵심 신규
**정의**: 한 PageNode 내에서 한 위젯이 다른 위젯에 영향을 주는 관계 1건.
**필드**: interaction_edge_id, site_id, page_key, source_widget_key, target_widget_key, interaction_type, description.
**interaction_type 값**:
- `activates` — 클릭하면 다른 위젯이 노출됨 (예: 검색창 → 드롭다운)
- `fills` — 입력 값이 다른 위젯에 자동 채워짐
- `depends_on` — 다른 위젯이 활성화되어야 사용 가능
- `toggles` — 다른 위젯의 on/off를 전환

**사용 맥락**: widget interaction sequencing의 토대. dynamic construction의 자동 추론 대상.
**옛 이름**: 없음 — v2 신규.

### 1.8 *(폐기 — 2026-04-11)* WidgetType (universal taxonomy)

**상태**: 본 연구에서 **완전 폐기** (§4.1.5).

**폐기 이유**: §4.1.6 minimum viable KG 원칙 도입으로 KG에 박을 정보를 *DOM이 원리적으로 표현 못 하는 4가지*(connectivity / conditional state / causal effects / stable references)로 좁혔다. type/category는 DOM의 tag/role/class에 이미 있으므로 KG가 *복사해 박을* 가치가 없다.

**대체**:
- WidgetNode에 `widget_type` 필드 없음 (§1.5 갱신)
- type 분류는 *runtime에 DOM에서 직접*
- cross-site 일반화는 *description의 의미적 유사성*으로 LLM이 자동 매칭
- M0.5의 LLM은 *분류기*가 아니라 *description generator* (`01_proposal.md` §4.4.3)
- 이전 ~35개 표 + WAI-ARIA / Material Design / HIG / Bootstrap 인용 모두 폐기

**향후 작업 시 원칙**: 새 정보를 KG에 박을지 결정할 때 *§4.1.6의 4가지 자기검증 질문*을 적용 — DOM에서 가져올 수 있나? LLM이 추론할 수 있나? 행동 결과로만 알 수 있나? 사람의 경험으로만 알 수 있나? 처음 두 질문에 Yes면 KG에 박지 말 것.

### 1.9 *(폐기 — 2026-04-11)* TaskWidgetMap

**상태**: 본 연구에서 **완전 폐기** (`01_skg_web_agent_proposal.md` §4.1.6 원칙).
**폐기 이유**: 사람이 *task→widget 정답 sequence*를 KG에 박는 것은 *task adaptive*이지 *site adaptive*가 아니며, oracle에 가까움. KG는 사이트의 *구조*만 표현해야 하고, *task의 풀이*는 LLM이 KG 위에서 자체 추론해야 함. 사용자(연구자)가 처음부터 정확히 갖고 있던 KG 개념과 일치.
**대체**: 본 연구의 retrieval은 *task_relevance_tags 기반 zero-shot ranking* (§1.11). LLM은 InteractionEdge graph 위에서 sequence를 자체 reasoning.
**향후 작업 시 원칙**: KG에 task→widget mapping을 박지 말 것. task semantic은 LLM의 영역.

### 1.10 Subgraph
**정의**: SiteKG의 부분 그래프. 본 연구에서는 두 종류:
- **Page subgraph**: V_page의 부분 + 그 사이의 NavigationEdge
- **Widget subgraph**: 한 PageNode의 V_widget(p) 부분 + 그 사이의 InteractionEdge

**사용 맥락**: §1.11 Two-Level Selective Retrieval의 결과물. LLM 시스템 프롬프트에 주입되는 단위.

### 1.11 Two-Level Selective Retrieval — v2 핵심 #1
**정의**: 매 LLM 호출에서 SiteKG 전체가 아니라 *두 레이어 모두에서 task-relevant 부분만* 추출해 prompt에 주입하는 기법.
- Page-level: 현재 PageNode의 1-hop 이웃 PageNode descriptions
- **Widget-level (★ 본 연구의 핵심)**: 현재 PageNode의 task-relevant WidgetNode top-K + 각 위젯의 selector + InteractionEdge 정보. ★ task→widget 명시 매핑 *없음* (§4.1.6 원칙). LLM이 InteractionEdge graph 위에서 sequence 자체 추론.

**연구 동기 (framing — 측정 가능한 가설은 H1')**: 본 연구는 selective retrieval을 단순한 DOM 압축이 아니라 *KG의 부분 그래프 노출*로 framing한다 (`01_proposal.md` §1.4.1 참고). 이 framing이 단순 element ranking과 *operational하게* 다르려면 다음 두 design choice가 prompt 구조에 명시적으로 포함되어야 하며, 각각의 효과는 §5.4 ablation 4·5에서 직접 측정된다:

1. **Label-rich graph context (§4.2.1 design choice 1)** — WidgetNode/InteractionEdge의 description, task_relevance_tags, side_effects, 그리고 위젯 간 의존 관계가 함께 주입된다. 평면 element 리스트와 달리 그래프 구조 위 추론이 가능해진다. *효과 측정*: ablation 5.
2. **Unobserved meta-count (§4.2.1 design choice 2, optional)** — 노출되지 않은 widget의 카테고리·개수를 prompt에 명시한다. *효과 측정*: ablation 4.

이 두 차원이 *모두 효과 없음*으로 측정되면 본 연구의 framing은 수사로 남고, 차별화는 시딩 방식(declarative vs 학습)에 머문다. 효과가 검출되면 framing이 정당화된다. 즉 본 framing은 *철학*이지만 *관련 설계 선택의 효과는 측정 가능*하다.

**사용 맥락**: Phase 1의 알고리즘. v1의 page-only selective retrieval과 결정적으로 다른 점.
**구현 위치 (예정)**: `runtime/sitekg/retrieval.py` (M1).
**중요성**: 본 연구의 핵심 가설 H1'는 "page-level retrieval에 widget-level retrieval을 더하면 task 성공률이 통계적으로 유의미하게 향상된다"이고, 이를 검증하는 게 본 연구의 1차 목표다.

### 1.12 Two-Level Traversal Planning
**정의**: 두 종류의 path/sequence를 동시에 계산:
- Page-level: BFS over G_page → NavigationEdge sequence
- Widget-level: 알고리즘은 *sequence를 결정하지 않음*. retrieval이 골라준 widget set + InteractionEdge를 LLM에 노출하면 LLM이 graph 위에서 위상 reasoning을 자체 수행 (§4.1.6 원칙)

**사용 맥락**: Phase 2의 알고리즘. 결과를 합쳐 sub-goal sequence로 변환.
**구현 위치 (예정)**: `runtime/sitekg/traversal.py` (M2).

### 1.13 Two-Level Dynamic Construction — v2 핵심 #2
**정의**: 에이전트가 task 실행 중 발견한 새 PageNode·NavigationEdge·**WidgetNode·InteractionEdge**를 SiteKG에 자동 추가하는 기법.
- Page layer: 새 PageNode 발견, 새 NavigationEdge 발견
- **Widget layer (★ 본 연구의 최종 목표)**: DOM 관측에서 새 widget 후보 추출 → universal WidgetType으로 분류 → KG 등록. 클릭 결과 관찰로 InteractionEdge 자동 생성.

**사용 맥락**: Phase 3. 본 연구의 *최종 목표*는 사람의 수동 시딩 없이도 에이전트가 새 사이트의 KG를 자율 구축하는 것.
**구현 위치 (예정)**: `runtime/sitekg/dynamic.py` + `widget_inference.py` (M3).

### 1.14 Declarative Seeding
**정의**: KG 시딩을 코드(Python dict)가 아닌 declarative format(YAML/JSON)으로 작성하는 방식.
**사용 맥락**: 본 연구의 design constraint(`feedback_research_kg_buildability.md`)을 만족하기 위함. *학습 기반 접근(Mind2Web 데이터 수집 + fine-tuning, OmniParser 67k 라벨링) 대비 차수 절감*이 가치 명제.
**두 시나리오 (항상 분리 표기)**:
- **목표 (M0.5 작동 시)**: M0.5 자동 bootstrapping이 생성한 `seeds/{site}.auto.yaml`을 사람이 confidence mid 항목만 검증. **사람 시간 ~30분~1시간**. 학습 기반 대비 **2~3 차수 절감**. *본 연구의 진짜 목표*.
- **Fallback (M0.5 미작동 시)**: 사람이 `seeds/{site}.yaml`을 처음부터 작성. ~6~10시간. 1~2 차수 절감. *design constraint와 어긋나는 후퇴선*.
**정확한 wall-clock**: M0.5 + M4에서 직접 측정 (`01_proposal.md` §4.1.7, §5.2 참고).
**예시 형식**: `01_skg_web_agent_proposal.md` §4.1.7 참고.
**옛 방식**: v1의 `runtime/seeds/gitlab.py` (Python 하드코딩) — 폐기 예정.

### 1.15 Inference-time Augmentation
**정의**: 모델 가중치를 학습시키지 않고, 추론 시점의 입력(프롬프트)을 보강해 성능을 끌어올리는 접근.
**사용 맥락**: 본 연구의 입장. RL/SFT(예: AutoWebGLM, Mind2Web, Go-Browse) 없이 KG로만 성능 향상을 시도한다.
**구별**: Mind2Web 등은 같은 *intra-page* 문제를 학습으로 풀지만, 본 연구는 declarative KG로 푼다.

### 1.16 Offline KG Bootstrapping (M0.5 신설)
**정의**: task 실행 *전*에 사이트를 자동 graph traversal로 순회하여 hierarchical SiteKG를 declarative YAML로 자동 생성하는 파이프라인. 학습 없이 LLM zero-shot 분류 + interaction 시뮬레이션으로 작동.
**구성**: Playwright crawler → DOM widget 후보 추출 → LLM zero-shot WidgetType 분류 → widget click/hover로 side_effect 관측 → InteractionEdge/NavigationEdge 자동 생성 → confidence 정책으로 commit.
**사용 맥락**: §1.4.2에서 정의한 두 문제(cold-start + 수동 시딩 비용)를 동시에 해결. M0.5의 산출물.
**구현 위치 (예정)**: `runtime/sitekg/bootstrapping/` (M0.5).
**Phase 3 dynamic construction과의 차이**: Phase 3는 *task 실행 중* + 도달성 묶임, offline bootstrapping은 *task 실행 전* + 사이트 체계적 커버. 두 메커니즘은 상호 보완적.
**검증**: H4 (`D_auto` vs `D_manual` paired t-test, `01_proposal.md` §2 H4 + §5.4 ablation 8).

### 1.17 Widget Auto-Classification (LLM zero-shot)
**정의**: DOM에서 추출한 인터랙션 요소 후보를 LLM에게 universal WidgetType taxonomy 중 하나로 분류하도록 요청하는 것. 학습 없이 zero-shot.
**LLM (default)**: gpt-4o-mini (M0.5 사용자 결정). 비용 + 속도 우선. 분류 정확도는 M0.5 측정 시점에 검증.
**입력**: tag / role / text / aria-label / parent_context
**출력**: widget_type, task_relevance_tags, description, confidence (structured JSON)
**구현 위치 (예정)**: `runtime/sitekg/bootstrapping/llm_classifier.py` (M0.5).

### 1.18 Cross-benchmark Generalization (M6 신설)
**정의**: 본 연구의 hierarchical KG 효과(H1' 등)가 *내부 ablation 검증 환경(WebArena-Verified)*과 *cross-benchmark 검증 환경(Online-Mind2Web)* 두 환경에서 *방향성 일관*하게 작동하는지 검증하는 것.
**검증 가설**: H5 (방향성 일관성만, §5.4c)
**검증 환경**: Online-Mind2Web — 300 task × 136 websites, "An Illusion of Progress?" (Xue et al. COLM 2025) paper의 산물
**외부 baseline**: Browser-use 97%, GPT-5.4 92.8%, Operator 61%, Claude Computer Use 3.7, SeeAct (early 2024 ~기준점), 대다수 후속 agent 28~30%, 단순 search 22%
**본 연구 천장 목표**: SeeAct 수준 + 대다수 후속 agent 능가. multimodal SOTA 능가는 1차 목표 아님 (학습/visual/시딩 비용 trade-off)
**구현 위치 (예정)**: `runtime/benchmarks/online_mind2web/` (M6)
**관련 paper**: *"An Illusion of Progress? Assessing the Current State of Web Agents"* (Xue et al., COLM 2025, arXiv:2504.01382)
**의미**: 본 연구가 WebArena GitLab에 *과적합되지 않음* 입증. 본 연구의 framing은 *Illusion of Progress 흐름과 진단 공유*이지 *대체*가 아님.

### 1.19 Manual vs Automated Seeding
**정의**: 본 연구는 KG 시딩을 두 경로로 지원하지만, **본 연구의 *목표 운영 시나리오*는 Automated + 사람 검증**이다:
- **Automated seeding (★ 본 연구의 목표)** — `runtime/sitekg/bootstrapping/`의 offline pipeline이 `seeds/{site}.auto.yaml`을 자동 생성. **사람은 confidence mid 항목만 검증 (~30분~1시간)**. M0.5에 GitLab, M4에 Reddit. 비용 = wall-clock + LLM API + 사람 검증 시간.
- **Manual seeding (fallback)** — 사람이 `seeds/{site}.yaml`을 처음부터 작성. ~6~10시간/사이트 (fallback reference, `01_proposal.md` §4.1.7). M0.5가 H4 검증에서 실패했을 때의 후퇴선. 본 연구의 design constraint와 어긋나는 수준.

**중요한 framing**: "수 시간 단위 시딩"은 *fallback*이지 *목표*가 아니다. 본 연구 문서에서 시딩 시간을 언급할 때는 항상 *목표 (30분~1시간)*와 *fallback (6~10시간)*을 분리해 표기한다.

**Confidence 정책 (3-tier, 사용자 결정)**:
- **High** (≥ 0.85): 자동 commit, status `auto_committed`. 사람 검증 불필요.
- **Mid** (0.5 ~ 0.85): 사람 confirm 필요, status `needs_review`. *사람 검증 30분~1시간은 이 mid 항목에 투입됨*.
- **Low** (< 0.5): 폐기

**검증**: §5.4 ablation 8에서 `D_manual` vs `D_auto`를 task 성공률로 직접 비교 (H4). 보조 metric: widget recall/precision/false positive rate.
**상호 관계**: 두 시드는 별도 파일로 보존 (`gitlab.yaml` vs `gitlab.auto.yaml`)하고 본 연구는 *두 경로 모두* 지원. H1'/H2/H3 검증의 1차 측정은 사람 시드(또는 사람 검증된 hybrid)로 수행하여 자동 시드 false positive가 결과를 오염시키지 않게 함. H4만 자동 시드 vs 사람 시드 직접 비교.

---

## 2. 역사적 변천

### 2.1 Prior → KB → KG (개념 명칭)
- **Prior** (폐기): lab 005~006 초기 명칭. Bayesian 의미 연상 → 폐기.
- **KB** (이전): "Knowledge Base"의 약어. 코드 식별자(`KBStore`, `KBBundle`, `KBConfidence`)에 잔존.
- **KG** (현재, v2): "Knowledge Graph"의 약어. **Hierarchical** KG임을 항상 의식.

### 2.2 Page-only → Hierarchical (모델 변천)

| | v1 (2026-04-10, 폐기) | **v2 (2026-04-11, 현재)** |
|---|---|---|
| 그래프 모델 | page graph만 | **hierarchical: page + widget** |
| 노드 | PageNode only | PageNode + WidgetNode |
| 엣지 | ActionEdge (page change + intra-page 혼합) | NavigationEdge + InteractionEdge로 분화 |
| 사이트 추상화 | (V, E) | (G_page, {G_widget(p)}, M_task, W_taxonomy) |
| 핵심 가설 | H1: page-level selective retrieval 효과 | **H1': widget-level이 page-level보다 더 큰 기여** |
| 평가 사이트 | GitLab 단일 | GitLab + Reddit cross-site |
| 핵심 기여 | navigation 개선 | **intra-page widget salience + universal taxonomy** |

v2는 v1을 폐기·재작성한 것이지 점진 개선이 아니다.

### 2.3 코드 식별자 변천 (v1 → v2)

본 연구를 위해 M0 단계에서 다음과 같이 일괄 리네이밍 + 신규 도입한다. 본 문서·`01_proposal.md`는 *v2 이름* 기준.

| 옛 (현재 코드) | 새 (M0 이후) | 위치 |
|---|---|---|
| `PageType` | `PageNode` | `runtime/types.py` → `runtime/sitekg/types.py` |
| `ActionSchema` | **두 클래스로 분화**: `NavigationEdge` (page change) + `InteractionEdge` (intra-page) | 〃 |
| `KBStore` | `SiteKGStore` | `runtime/store.py` → `runtime/sitekg/store.py` |
| `KBBundle` | `SiteKGContext` | `runtime/types.py` → `runtime/sitekg/types.py` |
| `KBConfidence` | `KGConfidence` | `runtime/enums.py` |
| `RouteKind.PARTIAL_KB` | `RouteKind.PARTIAL_KG` | `runtime/enums.py` |
| `kb_used` (TaskRun) | `kg_used` | `runtime/types.py` |
| `kb_confidence` (SiteProfile) | `kg_confidence` | `runtime/types.py` |
| `runtime/seeds/gitlab.py` (Python 하드코딩) | `runtime/sitekg/seeds/gitlab.yaml` (declarative) | format 변경 + 패키지 이동 |

**신규 클래스/식별자** (옛 이름 없음):

| 신규 | 위치 | 역할 |
|---|---|---|
| `WidgetNode` | `runtime/sitekg/types.py` | §1.5 |
| `InteractionEdge` | 〃 | §1.7 |
| ~~`WidgetType` (enum)~~ | (폐기, 2026-04-11) | §1.8 폐기 단락 참고 — §4.1.5 minimum viable 원칙으로 통째 제거 |
| ~~`TaskWidgetMapEntry`~~ | (폐기, 2026-04-11) | §1.9 폐기 단락 참고 |
| `SiteKG` (그래프 컨테이너) | 〃 | hierarchical 구조의 root |
| `SiteKGContext` | 〃 | SiteKG + 부속 데이터 (validator/policy/failure) |
| `SiteKGStore` | `runtime/sitekg/store.py` | KG 영속화 + 새 SQL 스키마 |
| **`SiteKGBootstrapper`** | `runtime/sitekg/bootstrapping/pipeline.py` | ★ M0.5 — offline bootstrapping pipeline 진입점 |
| **`PlaywrightCrawler`** | `runtime/sitekg/bootstrapping/crawler.py` | ★ graph traversal 실행 |
| **`WidgetCandidateExtractor`** | `runtime/sitekg/bootstrapping/widget_extractor.py` | ★ DOM → 후보 추출 |
| **`LLMDescriptionGenerator`** | `runtime/sitekg/bootstrapping/description_generator.py` | ★ LLM (gpt-4o-mini) element → 자연어 description + 자유 string 태그 생성. *분류기 아님* (§4.1.5 폐기, §4.4.3) |
| **`InteractionSimulator`** | `runtime/sitekg/bootstrapping/interaction_simulator.py` | ★ click/hover → side_effect 관측 |
| **`ConfidencePolicy`** | `runtime/sitekg/bootstrapping/confidence.py` | ★ 3-tier confidence 정책 |
| **`OnlineMind2WebAdapter`** | `runtime/benchmarks/online_mind2web/adapter.py` | ★ M6 — task 입출력 변환, agent 통합 |
| **`WebJudgeEvaluator`** | `runtime/benchmarks/online_mind2web/evaluator.py` | ★ M6 — WebJudge (o4-mini) 호출 + 결과 파싱 |
| **`OnlineMind2WebLeaderboard`** | `runtime/benchmarks/online_mind2web/leaderboard.py` | ★ M6 — Hugging Face leaderboard 등록 + 비교 표 자동 생성 |

### 2.4 폐기된 명칭

- **Prior**: §2.1.
- **Site Model**: 한 차례 잠깐 등장한 ad-hoc 용어. 폐기.
- **PageType / ActionSchema** (v1 코드명): "Type" 모호성, "schema" JSON-schema 오해, page-change와 intra-page 혼합으로 폐기. PageNode / NavigationEdge / InteractionEdge로 분화.
- **KBBundle**: 불명확한 묶음. SiteKGContext로 이름 변경 + 그래프 부분은 SiteKG로 분리.
- **v1 page-only SiteKG 모델**: 본 문서 v2에서 폐기. hierarchical로 전면 대체.

---

## 3. SiteKG 엔티티 (v2 — 코드 매핑)

본 연구의 SiteKG는 다음 dataclass들로 구성된다 (M0 이후 모두 `runtime/sitekg/types.py`).

```
SiteKG (root container)
├── site_profile: SiteProfile
├── page_nodes: list[PageNode]
│   ├── widget_nodes: list[WidgetNode]      ← V_widget(p)
│   └── widget_edges: list[InteractionEdge] ← E_widget(p)
├── navigation_edges: list[NavigationEdge]  ← E_page
★ task_widget_map *없음* — task semantic은 KG에 박지 않음 (§4.1.6 원칙)

SiteKGContext (task 실행 시 라우터/executor가 받음)
├── sitekg: SiteKG
├── validator_rules: list[ValidatorRule]
├── policy_rules: list[PolicyRule]
└── failure_patterns: list[FailurePattern]
```

### 3.1 SiteProfile
**정의**: 사이트 1건의 메타데이터. site_id, display_name, base_url, auth_type, onboarding_status, kg_confidence.
**역할**: 사이트 자체의 식별/상태. 라우터가 이를 보고 분기 결정.
**위치**: `SiteKG.site_profile`.

### 3.2 PageNode
§1.4 참고. 코드 매핑: `runtime/sitekg/types.py`. v2부터 `widget_nodes`, `widget_edges` 필드를 가진 *컨테이너 노드*.

**URL pattern 형식** (★ B2 해결, 2026-04-11): Express.js placeholder 형식.
- `/dashboard` (정확 매칭), `/projects/:ns/:project` (placeholder), `/:catchall`
- Query parameter: 기본 무시. 명시 시 매칭에 포함 (`/explore?visibility_level=20`)
- Fragment: 기본 무시 (SPA hash routing은 future work)
- Trailing slash: 정규화

**Matching priority** (deterministic, `01_proposal.md` §4.1.2):
1. URL pattern 매칭 → 후보 추출
2. 후보 1개 → 채택
3. 여러 후보 → specificity (placeholder 적은 것) 우선
4. 같은 specificity → structural_signals tiebreak
5. 매칭 0개 → UNRESOLVED → Phase 3 dynamic construction이 새 PageNode 생성

**구현 위치** (M0 이후): `runtime/sitekg/page_matcher.py` `match_page_node()`. ~20 단위 테스트 케이스.

### 3.3 WidgetNode (v2 신규)
§1.5 참고. 코드 매핑: `runtime/sitekg/types.py`.

### 3.4 NavigationEdge (옛 ActionSchema의 page-change 부분)
§1.6 참고. 코드 매핑: `runtime/sitekg/types.py`. `trigger_widget_key`로 어느 위젯이 trigger하는지 명시.

### 3.5 InteractionEdge (v2 신규)
§1.7 참고. 코드 매핑: `runtime/sitekg/types.py`.

### 3.6 *(폐기 — 2026-04-11)* WidgetType
**상태**: §1.8 폐기 단락 참고. WidgetType enum은 §4.1.5 통째 폐기로 본 연구에서 *완전 제거*. `runtime/sitekg/widget_types.py` 파일도 폐기.

### 3.7 *(폐기 — 2026-04-11)* TaskWidgetMapEntry
**상태**: 본 연구에서 폐기. §1.9 폐기 단락 참고. KG에 task→widget mapping을 박지 않는 §4.1.6 원칙에 따라 *데이터 구조 자체가 없음*.

### 3.8 ValidatorRule — *SiteKGContext의 부속 데이터*
**정의**: validator_rule_id, site_id, task_family, rule_type, pass_criteria.
**역할**: task 성공 판정 규칙. SiteKG 그래프의 일부가 *아니다*. SiteKGContext의 부속 데이터. selective retrieval/dynamic construction의 대상이 아님. ★ `task_family` field는 lab 005~006부터 존재하는 단순 라벨링이고 본 연구의 *알고리즘 input*이 아님 — 본 연구의 retrieval은 task family 분류를 모름.

### 3.9 PolicyRule — *SiteKGContext의 부속 데이터*
**정의**: policy_rule_id, site_id, action_key, policy_type, reason.
**역할**: 특정 action_key에 대한 허용/승인 정책.

### 3.10 FailurePattern — *SiteKGContext의 부속 데이터*
**정의**: failure_pattern_id, site_id, failure_type, detection_signal, recommended_recovery.
**역할**: 알려진 실패 패턴 + recovery 힌트.

### 3.11 SiteKG (root container)
**정의**: site_profile + page_nodes (각 PageNode가 widgets + InteractionEdges 포함) + navigation_edges. 한 사이트의 hierarchical KG 전체. ★ task_widget_map *없음* (§4.1.6 원칙).
**역할**: 본 연구의 핵심 데이터 구조. selective retrieval / traversal / dynamic construction의 *대상*. mutable.
**메서드** (M0 이후 예정):
- `add_page_node(node)`, `add_widget_node(page_key, widget)`
- `add_navigation_edge(edge)`, `add_interaction_edge(page_key, edge)`
- `outgoing_navigation_edges(page)`, `widgets_in(page)`
- `find_navigation_path(start, target)` — BFS
- `extract_subgraph(filter)` — selective retrieval

### 3.12 SiteKGContext
**정의**: sitekg(SiteKG) + validator_rules + policy_rules + failure_patterns. task run에서 라우터/executor가 받는 사이트 전체 컨텍스트.
**옛 이름**: `KBBundle`.
**왜 분리하나**: SiteKG는 그래프 연산의 *대상*이고 부속 데이터(validator/policy/failure)는 그래프 연산과 무관하다. 분리하지 않으면 selective retrieval / dynamic construction의 대상이 모호해진다.

---

## 4. 에이전트 실행 단위

본 연구의 에이전트는 **Task → Sub-goal → Step → Action**의 4단 분해.

### 4.1 Task
**정의**: 사용자 자연어 요청 1건. 벤치마크에서 task_id 1개에 대응.
**코드 매핑**: 1 Task = 1 `TaskRun`. `task_run_id`로 식별.

### 4.2 Sub-goal
**정의**: Task를 분할한 중간 목표. Planner가 분해. v2에서는 page navigation sub-goal과 widget interaction sub-goal 두 종류가 모두 등장.
**코드 매핑**: 별도 dataclass 없음. executor 함수 호출 단위로 표현.
**역할**: checkpoint + retry + replan 단위.

### 4.3 Step
**정의**: 1 Sub-goal 수행 중 발생하는 LLM 1회 호출 단위.
**코드 매핑**: 1 Step = 1 `StepRecord`.
**역할**: ReAct loop의 1 turn. "task당 평균 step 수"의 단위.

### 4.4 Action
**정의**: 1 Step 안에서 LLM이 호출한 단일 도구 (Tool Use API의 1 tool_use 블록).
**예**: `click(widget_key="label_dropdown")`, `goto(url=...)`, `extract(selector=...)`, `done(reason=...)`.
**v2 변화**: action의 selector 인자는 점점 *raw DOM selector*에서 *WidgetNode 참조*로 추상화될 수 있음 (M1 이후 결정).

### 4.5 Intent / IntentPlan
**정의**: 사용자 요청 텍스트를 얕게 분류한 결과. task_type, action(IntentAction), target_phrase, target_terms, explicit_url.
**코드 매핑**: `runtime/types.py` `IntentPlan`. `intent.analyze_intent()` 생성.
**역할**: RETRIEVE/NAVIGATE/MUTATE 분류 + Phase 1 widget retrieval의 입력.

### 4.6 Observation / PageObservation
**정의**: 현재 페이지에서 관찰한 핵심 상태 스냅샷. url, title, headings, text_lines, links, buttons, inputs, dropdown_options.
**v2 확장**: Phase 3 widget auto-discovery를 위해 *interactive_elements* 필드 추가 검토.
**역할**: ReAct loop의 "observe" 단계.

### 4.7 Tool Call
**정의**: Tool Use API의 단일 함수 호출. 본 프로젝트는 v5(lab 005)부터 prompt-based JSON parsing 폐기, Tool Use API로 전면 전환.
**페어링 규칙**: 한 tool_use는 반드시 한 tool_result로 응답 (parallel_tool_calls=False).

### 4.8 TaskType
**정의**: `Literal["RETRIEVE", "MUTATE", "NAVIGATE"]`. task의 큰 분류.
**코드 매핑**: `runtime/types.py`.
- RETRIEVE: 페이지에서 정보를 찾아 반환
- NAVIGATE: 특정 페이지로 이동만 하면 성공
- MUTATE: 사이트 상태 변경 (생성/수정/삭제). 실행 후 환경 재시작 필요

**v2에서 추가 검토**: FILTER, SORT 같은 sub-task family가 widget retrieval의 1차 분류 단위로 등장.

### 4.9 TaskStatus (6종)
**정의**: `Literal["SUCCESS", "ACTION_NOT_ALLOWED_ERROR", "PERMISSION_DENIED_ERROR", "NOT_FOUND_ERROR", "DATA_VALIDATION_ERROR", "UNKNOWN_ERROR"]`.
**코드 매핑**: `runtime/types.py`.
**역할**: agent layer가 외부에 반환하는 결과.
**구별**: `runtime/enums.py`의 `TaskRunStatus`와 다르다 (TaskRunStatus는 runtime 내부 상태).

---

## 5. 실험 설계 용어

본 연구는 6개 조건(A~F) × 3개 phase × 14 task × 3회 반복 + cross-site 평가.

### 5.1 가설 H0 (중심 가설)
> Hierarchical SiteKG (page graph + intra-page widget graph)를 LLM 웹 에이전트에 통합하여 (a) selective retrieval, (b) graph traversal, (c) dynamic construction을 적용하면, page-level KG augmentation 대비 task 성공률이 통계적으로 유의미하게 향상되며 새 사이트로의 zero-shot 일반화가 가능해진다.

### 5.2 가설 H1' (핵심 가설 — 본 연구의 중심 주장)
> Selective retrieval은 (a) page graph + (b) WidgetNode 두 레벨에서 동시에 적용되어야 하며, **(b) widget-level이 (a) page-level보다 task 성공률에 더 큰 기여를 한다**.

**검증**: 조건 D - 조건 C 효과 크기 > 조건 C - 조건 B 효과 크기.

### 5.3 가설 H2 (Two-Level Traversal)
> Path finding은 (a) page-level navigation path + (b) intra-page widget interaction sequence 두 종류 모두에 적용된다.

**검증**: 조건 D vs 조건 E.

### 5.4 가설 H3 (Two-Level Dynamic Construction)
> Dynamic construction은 새 PageNode뿐 아니라 새 WidgetNode + InteractionEdge까지 자동 추가해야 새 사이트로의 zero-shot 적응이 가능하다.

**검증**: 조건 E vs 조건 F + 빈 KG에서 Phase 3만 작동하는 zero-shot 시나리오.

### 5.4b 가설 H4 (Offline KG Bootstrapping — M0.5)
> LLM-driven offline KG bootstrapping(§4.4)으로 자동 생성한 시드만으로 본 연구 알고리즘(조건 D)을 실행했을 때, 사람 시드 대비 task 성공률 차이가 일정 천장 이내에 머문다.

**검증** (사용자 결정에 따라 *task 성공률 우선*):
- Primary: `D_manual` vs `D_auto` paired t-test (ablation 8)
- Secondary: 자동 시드의 widget recall / precision / false positive rate (자동 시드 *품질* 직접 측정)

**채택 기준**: 절대 차이 ≤ 15%p (예시 천장. M0.5에서 정확한 천장 결정).
**의미**: 자동 시드가 사람 시드를 *능가*한다고 주장하지 않음. 비교 가능한 천장 이내면 충분 — 그 의미는 "사람 비용 거의 0으로도 본 연구 알고리즘 작동".

### 5.4c 가설 H5 (Cross-benchmark 일관성 — M6 신설)
> Hierarchical SiteKG + Phase 1/2/3 + M0.5 offline bootstrapping의 효과가 **WebArena-Verified**(내부 ablation)와 **Online-Mind2Web**(cross-benchmark 일반화) 두 환경에서 *방향성 일관*하게 관찰된다.

**채택 기준 (사용자 결정 — *방향성 일관성만*)**:
- WebArena에서 D > C이면 Online-Mind2Web에서도 D > C 방향이면 H5 채택
- **효과 크기 동등 요구 안 함** (가장 약한 기준, 가장 정직)
- 효과 크기 보존 비율 (60%+)은 *strong sub-claim*으로 별도 보고

**검증**: ablation 10 (WebArena의 H1' 검증을 Online-Mind2Web sub-set 30~50 task에서 재측정 + 외부 leaderboard baseline 동일 환경 비교)
**의미**: 본 연구가 WebArena GitLab에 *과적합되지 않음* 입증. 기각 시 contribution을 *해당 환경 한정*으로 명시.

### 5.5 두 벤치마크의 역할 분리
| | WebArena-Verified GitLab 14 task | Online-Mind2Web sub-set |
|---|---|---|
| 역할 | 내부 ablation 검증 | cross-benchmark 일반화 검증 |
| 검증 가설 | H1' / H2 / H3 / H4 | H5 |
| 비교 baseline | 본 프로젝트 v3 (조건 A) | Hugging Face leaderboard 외부 baseline 풍부 |
| 측정 metric | task 성공률 + ablation | task 성공률 + WebJudge + leaderboard rank |
| 용도 | 효과 입증 | 일반화 입증 |

상세는 `01_skg_web_agent_proposal.md` §5.3 참고.

### 5.5 조건 A — Baseline v3
**구성**: SiteKG 없음. Tool Use + sub-goal/checkpoint/retry/replan만.
**역할**: 기준점.

### 5.6 조건 B — Page-Full
**구성**: 정적 page-level SiteKG, 매 step에 전체 page graph를 system prompt에 주입.
**역할**: 기존 KG augmentation 방식의 대표. v1의 lab 006 위치에 해당하지만 새로 측정.

### 5.7 조건 C — Page-Selective
**구성**: 정적 page-level SiteKG + page-level selective subgraph retrieval.
**역할**: v1 H1의 검증. page-level selective의 단독 효과.

### 5.8 조건 D — Page+Widget Selective ★ 핵심
**구성**: hierarchical SiteKG + page-level + widget-level selective retrieval. ★ task_relevance_tags 기반 zero-shot ranking (TaskWidgetMap 같은 task→widget 명시 매핑 *없음*, §4.1.6 원칙).
**역할**: H1' 검증의 핵심. 본 연구의 가장 중요한 조건.

### 5.9 조건 E — + Path
**구성**: 조건 D + page-level BFS + widget interaction sequencing (Phase 2).
**역할**: H2 검증.

### 5.10 조건 F — + Dynamic
**구성**: 조건 E + Phase 3 dynamic construction (page + widget).
**역할**: H3 검증. 가장 완전한 hierarchical SKG 에이전트.

### 5.11 Phase 1 / 2 / 3
**Phase 1** = Two-Level Selective Retrieval (§1.11). 조건 D로 측정 (조건 C와 비교).
**Phase 2** = Two-Level Traversal Planning (§1.12). 조건 E로 측정.
**Phase 3** = Two-Level Dynamic Construction (§1.13). 조건 F로 측정.

### 5.12 독립변수 / 종속변수
**독립변수**: 실험 조건 (A~F).
**종속변수**:
- 주요: task 평균 성공률
- 보조: step 수, LLM 호출 수, 토큰 수, wall-clock time, sub-goal 성공률, task family별 성공률, **widget recall**, **widget precision**, **시딩 비용**

### 5.13 Ablation
**정의**: 한 기법을 빼거나 더했을 때의 차이로 그 기법의 단독 기여도를 분리.
**본 연구**: 9개 ablation — Phase 1 widget만, Universal taxonomy 효과, unobserved meta-count 효과 (D vs D'), label-rich graph context 효과, Phase 3 only (no seed), Cross-site dynamic, Automated vs Manual seeding (H4), Bootstrapping + Phase 3 stacking, Cross-benchmark 일관성 (H5). ★ ablation 2 "TaskWidgetMap 효과"는 *§4.1.6 원칙으로 폐기 (2026-04-11)* — 측정 대상 자체가 사라짐.

### 5.14 Baseline (이 프로젝트 맥락)
**정의**: "baseline"이라 하면 *조건 A* (SiteKG 없는 v3 에이전트)를 가리킨다.
**lab 006의 50%**: 본 연구에서 직접 비교 대상으로 쓰지 않는다. v3 baseline 자체가 재구현되므로 새 baseline부터 다시 측정.

### 5.15 Paired t-test
**정의**: 같은 task에 대해 두 조건의 성공률 차이가 우연인지 검증하는 통계 검정.
**본 연구**: 조건 A vs C/D/E/F의 차이를 paired t-test로. 유의수준 p < 0.05.

### 5.16 Widget recall / Widget precision (v2 신규 메트릭)
- **Widget recall**: task가 필요로 하는 정답 위젯이 LLM에 노출됐는가 (Phase 1의 직접적 품질 지표)
- **Widget precision**: LLM에 노출된 위젯 중 실제로 사용된 비율 (노이즈 측정)

### 5.17 Cross-site Generalization
**정의**: GitLab으로 시딩·측정한 후 Reddit(또는 Shopping_admin)에서 재측정. 같은 universal WidgetType taxonomy로 시딩 가능한지 + Phase 3 dynamic construction이 새 사이트에서 작동하는지 검증.
**본 연구**: 5.3 평가 환경의 핵심 축. H3 검증 + universal taxonomy의 가치 증명.

---

## 부록 A: WidgetType 카탈로그 (~30개)

§1.8 참고. 본 부록은 빠른 조회용 요약. 자세한 의미·ARIA role·task relevance는 `01_skg_web_agent_proposal.md` §4.1.5의 표 참조.

| 카테고리 | Type | 한 줄 의미 |
|---|---|---|
| **Input** | `text_input` | 자유 텍스트 입력 |
| | `search_box` | 검색 전용 입력 |
| | `password_input` | 비밀번호 입력 |
| | `textarea` | 다행 텍스트 |
| | `numeric_input` | 숫자 입력 |
| | `date_picker` | 날짜 선택 |
| **Choice** | `dropdown` | 단일 선택 드롭다운 |
| | `radio_group` | 단일 선택 라디오 |
| | `checkbox` | 토글 선택 |
| | `multi_select` | 다중 선택 |
| | `toggle` | on/off 스위치 |
| | `slider` | 범위 선택 |
| **Action** | `button` | 일반 버튼 |
| | `submit_button` | 폼 제출 |
| | `link` | 페이지 전이 링크 |
| | `icon_button` | 아이콘 버튼 (라벨 부재) |
| **Navigation** | `tab_strip` | 탭 그룹 |
| | `breadcrumb` | 계층 nav |
| | `pagination` | 페이지 전환 |
| | `menu` | 드롭다운 메뉴 |
| | `accordion` | 접고 펼치기 |
| **Display** | `list` | 항목 목록 |
| | `table` | 표 데이터 |
| | `card_grid` | 카드 격자 |
| | `chart` | 시각화 |
| | `text_block` | 본문 |
| **Container** | `form` | 폼 |
| | `panel` | 영역 컨테이너 |
| | `modal` | 모달 다이얼로그 |
| | `drawer` | 사이드 패널 |
| | `dialog` | 일반 다이얼로그 |
| **Sort/Filter** ★ | `sort_toggle` | 정렬 방향 토글 |
| | `sort_dropdown` | 정렬 기준 드롭다운 |
| | `filter_panel` | 필터 모음 패널 |
| | `filter_chip` | 적용된 필터 chip |
| | `search_filter_combo` | 검색창 + 필터 결합 (GitLab 패턴) |

총 35개 (Input 6 + Choice 6 + Action 4 + Navigation 5 + Display 5 + Container 5 + Sort/Filter 5).

---

## 부록 B: GitLab `issues_list` PageNode의 위젯 예시

본 연구가 다루는 *intra-page widget* 개념을 구체화하기 위한 예시. M0의 GitLab YAML 시드의 일부.

```
PageNode: issues_list
  url_patterns: ["/-/issues"]
  description: "Open issues by default, newest first"
  widgets:
    1. search_box (search_filter_combo)
       — 검색창. 클릭하면 필터 드롭다운 활성화
       — task_relevance: [filter, search]
       — locator: role=searchbox
       — side_effects: [activates_filter_dropdown]

    2. label_dropdown (dropdown)
       — Label 필터. search_box 클릭 후에만 보임
       — task_relevance: [filter]
       — locator: text="Label"
       — visibility_condition: visible_after_search_box_click

    3. assignee_dropdown (dropdown)
       — Assignee 필터. 동일하게 search_box 활성 후

    4. state_tabs (tab_strip)
       — Open / Closed / All 탭
       — task_relevance: [filter, view_switch]
       — locator: role=tablist

    5. sort_dropdown (sort_dropdown)  ★
       — 정렬 기준. "Created date", "Updated date", "Priority" 등
       — task_relevance: [sort, ordering]
       — locator: text="Sort by"
       — ★ 사용자 §1.3 (5)의 핵심 예시 — 이 위젯이 prompt에 노출되지 않으면
          에이전트는 정렬 불가로 결론짓는다

    6. sort_direction_toggle (sort_toggle)
       — asc/desc 토글
       — task_relevance: [sort]

    7. new_issue_button (button)
       — task_relevance: [create]

    8. pagination (pagination)
       — task_relevance: [scroll, navigation]

  widget_edges:
    - search_box --activates--> label_dropdown
    - search_box --activates--> assignee_dropdown
    - sort_dropdown --depends_on--> sort_direction_toggle  # 정렬 기준 선택 후 방향
```

이 페이지에서 LLM의 raw observation은 50+ 인터랙션 요소를 포함할 수 있다. 본 연구의 widget retrieval은 이 중 *task에 필요한 3~8개*만 LLM에 노출한다 — 예를 들어 "filter by label" task에는 #1, #2, (#5는 제외), "sort by recent activity" task에는 #5, #6 (#1~#4는 제외).

이게 본 연구의 핵심 메커니즘이고, 이게 작동하면 사용자 §1.3 (5)의 정렬 토글 누락 같은 실패가 *구조적으로 사라진다*.

---

## 부록 Cross-reference

| 본 문서 | 참조 위치 |
|---|---|
| §1 핵심 KG 용어 | `01_skg_web_agent_proposal.md` §4.1, §4.2 |
| §2 역사적 변천 | `01_proposal.md` §0 변경 이력, `06_prior_injection_experiment.md` |
| §3 SiteKG 엔티티 | `runtime/sitekg/types.py` (M0 이후), `01_proposal.md` §4.1 |
| §4 에이전트 실행 단위 | `runtime/executor.py`, `runtime/orchestrator.py` |
| §5 실험 설계 | `01_proposal.md` §2, §5 |
| 부록 A WidgetType 카탈로그 | `01_proposal.md` §4.1.5 (full table) |
| 부록 B GitLab 위젯 예시 | `runtime/sitekg/seeds/gitlab.yaml` (M0 이후) |
