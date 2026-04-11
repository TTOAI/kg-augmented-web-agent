# 연구계획서: Hierarchical Site Knowledge Graph 기반 LLM 웹 에이전트

**작성일**: 2026-04-11 (v2 — 전면 재설계)
**프로젝트 코드명**: site-adaptive-webagent
**문서 유형**: 연구 계획서 (Research Proposal)
**상태**: 초안

---

## 0. 변경 이력

본 문서는 2026-04-10 v1 (page-level KG 안)을 폐기하고 전면 재작성한 v2다. 변경 동기는 §1.3 한계 분석에 통합되어 있다. 핵심 차이:

- v1: 사이트를 *page graph*로 표현 (PageType 노드 + ActionSchema 엣지)
- **v2: 사이트를 *hierarchical graph*로 표현** — page graph + 각 페이지 내부의 widget graph

---

## 1. 배경 및 동기

### 1.1 LLM 웹 에이전트의 본질적 병목

LLM 기반 웹 에이전트(WebGPT, ReAct, AutoWebGLM, SeeAct, WebVoyager, Agent-E, Browser-use, OpenAI Operator, Claude Computer Use 등)는 자연어 task를 받아 브라우저를 조작한다. WebArena 류 벤치마크의 성공률은 한동안 낮았으나(GPT-4o baseline 약 24%, Contextual Experience Replay 36.7%) 2024년 후반부터 *보고 성능*이 가파르게 향상되었다. 그러나 **이 향상이 진짜 진보였는가**에 대한 의문이 동시에 제기되었다.

**"An Illusion of Progress?"** (Xue et al., COLM 2025, arXiv:2504.01382)는 이 의문을 정면으로 다룬 paper다. 저자들은 어려운 평가 환경 *Online-Mind2Web*(300 task × 136 websites, 라이브 web)을 새로 구축하고 기존 SOTA를 재측정한 결과, **대다수 후속 agent가 SeeAct(early 2024) 수준을 능가하지 못함**을 발견했다 — 기존 보고치가 최대 59% 부풀려졌다는 결론. 같은 환경에서 측정된 baseline pool은 다음과 같다 (§3.1·§7.3에서 자세히 다룸):

| Agent | Online-Mind2Web 성공률 | 비고 |
|---|---|---|
| Browser-use (Auto-Research) | 97% | learning + multimodal |
| GPT-5.4 | 92.8% | screenshot only, OpenAI 측정 |
| OpenAI Operator | 61% (사람), 71.8% (WebJudge) | multimodal computer use |
| Claude Computer Use 3.7 | top performer 그룹 | multimodal computer use |
| **SeeAct (early 2024)** | (기준점) | DOM-based, *대다수 후속 agent의 천장* |
| 대다수 후속 agent | 28~30% (사람), 34~40% (WebJudge) | "Illusion" 핵심 발견 |
| Baseline search | 22% | floor |

이 결과가 시사하는 바: **최근 향상의 상당 부분이 새 학습 데이터나 더 큰 모델이 아니라 "DOM/관측 정보를 LLM에 어떻게 더 효과적으로 줄 것인가"에 대한 알고리즘 개선에서 나왔지만, 그 효과가 *어려운 환경*에서는 무너진다**는 사실. Agent-E(WebVoyager 73.2%) 같은 기존 SOTA들은 모두 (i) 학습 기반(AutoWebGLM, MindAct, OmniParser) 또는 site-agnostic 일반 압축(Agent-E)이고, (ii) **사이트별 구조 지식을 명시적으로 활용하지 않는다**.

본 연구는 이 두 한계를 가설로 진술한다:

> **현대 웹 에이전트가 다음 단계 향상을 위해 다뤄야 할 핵심 문제 중 하나는, 페이지 *내부*에서 task-relevant 인터랙션 요소를 식별하는 능력이다. 그리고 이 능력은 학습 기반 일반화나 site-agnostic 일반 압축만으로는 한계가 있고, *사이트별 구조 지식을 명시적으로 표현·활용*함으로써 보완될 수 있다.**

본 연구는 이를 **intra-page widget salience problem**이라 부르고, 해법으로 **declarative site-specific KG + universal widget taxonomy**를 제시한다 (§3.4.5, §3.5 참고). 이 해법의 *상대적 효과*는 §5의 조건 비교로 경험적으로 검증한다.

### 1.2 본 프로젝트의 선행 실험 (lab 001~006) — historical context

| Lab | 기여 |
|---|---|
| 001-002 | 단순 선형 에이전트 baseline |
| 003-004 | sub-goal/checkpoint, 관측·검증·실행 레이어 개선 |
| 005 | Tool Use API 전환 (v3 baseline) |
| 006 | **Page-level prior 주입 실험 — 효과 미미 (50% → 47.6%)** |
| post-006 (2026-04-12) | **lab 005 baseline 복원 + memo 강화** — lab 006의 KB layer를 모두 폐기하고 lab 005 시점 코드로 환원, action tool에 optional `memo` field와 `_verify_done`의 `task_notes` 검토를 추가하여 multi-step RETRIEVE에서 LLM working memory를 외부 보강 |

lab 006은 GitLab 9 PageType + 5 ActionSchema(모두 page-level)를 시스템 프롬프트에 텍스트로 주입했으나 성공률 향상이 없었다. v1 문서는 이 결과를 "주입 방식이 비효율적이라 효과가 보이지 않았다"로 해석하고 selective retrieval / path finding / dynamic construction 같은 *page-level KG 기법*을 처방했다. 본 문서(v2)는 이 진단이 표면적이었다고 본다 (§1.3).

본 연구는 lab 006의 50% 결과를 직접 비교 대상으로 사용하지 않는다. v3 baseline 코드 자체가 본 연구에서 재구현되었고(2026-04-12 lab 005 시점으로 복원 + memo 강화), 새 baseline 측정부터 다시 시작한다. memo 강화는 lab 005 §"Skill Library 시도 및 철회"가 *예약*한 cognitive aid 영역의 가벼운 구현이며 system prompt는 task-agnostic 유지.

### 1.3 한계의 본질 — 다섯 가지 통찰

lab 006의 부정적 결과를 다시 분석하면, 사람의 손으로 가능한 거의 모든 page-level prior를 주입했음에도 성공률이 변하지 않았다. 이는 page-level KG가 *틀린 문제*를 풀고 있었음을 시사한다. 다음 다섯 가지 관찰이 본 연구의 출발점이다.

**(1) DOM은 1차원, LLM 관측은 lossy**

사람은 페이지를 시각적으로 한 번에 스캔해 "이 영역은 헤더, 저 영역은 검색 필터, 가운데는 결과 리스트"를 즉시 파악한다. 에이전트는 그렇지 않다. DOM은 본질적으로 1차원 트리고, LLM에 주입할 수 있는 토큰 예산은 제한적이라 매 step마다 페이지의 *일부 요소만* 본다. 다음 행동에 필요한 요소가 그 일부에 포함되지 않으면, 에이전트는 그 요소가 *존재하지 않는다*고 가정한다.

**(2) 진짜 문제는 navigation이 아니라 widget selection이다**

페이지 *간* 이동(navigation)은 전체 인터랙션의 작은 부분에 불과하다. 현대 웹사이트에서 압도적 다수의 클릭은 *같은 페이지 안의 JS 인터랙션*이다 — 검색창 활성화, 드롭다운 열기, 정렬 토글, 필터 칩 추가, 모달 호출 등. page graph는 이런 intra-page 인터랙션을 *전혀* 표현하지 못한다.

**(3) 페이지 내 정보 폭증과 selective subset 문제**

이상적으로는 페이지 내 모든 요소를 LLM에 보여주면 된다. 그러나 현대 웹 페이지에는 수십~수백 개의 인터랙션 요소가 있고, 모두 보여줄 토큰 예산이 없다. 따라서 진짜 질문은 "*어떻게 페이지 내 요소들 중 task에 필요한 부분만 골라 보여줄 것인가*"가 된다. 이는 page graph로는 답할 수 없는 질문이다.

**(4) 같은 task, 다른 사이트, 완전히 다른 UI**

"필터 검색"이라는 같은 추상 task가 사이트마다 전혀 다른 UI 패턴으로 풀린다.
- **GitLab**: 검색창을 클릭 → AJAX로 드롭다운 활성화 → "Label" 선택 → 옵션 선택 → 검색 실행
- **Baekjoon**: 검색창 옆 옵션 버튼 클릭 → 정렬/상태/알고리즘 옵션 패널 노출 → 옵션 선택

이런 사이트별 위젯 패턴 차이는 page graph가 표현할 수 없는 정보다. 그런데 이 정보야말로 *site-adaptive*의 진짜 의미다.

**(5) 구체적 실패 시나리오 — 시간순 정렬 토글**

목록을 시간순으로 정렬하는 task를 가정하자. 에이전트가 페이지 내에서 찾아야 할 가장 중요한 요소는 정렬 토글 버튼이다. 그러나 이 버튼이 페이지 내 50개 넘는 요소들 중 *제공되지 못하면*, 에이전트는 (a) "이 페이지에서 정렬이 불가능"이라고 잘못 결론짓거나 (b) "이미 정렬되어 있다"고 가정하고 done을 외친다. 이게 lab 006이 50%에서 멈춘 진짜 이유다 — page-level prior는 "이 사이트엔 issues 페이지가 있다"만 알려주고, "issues 페이지의 정렬 토글이 어디 있는지"는 알려주지 못한다.

### 1.4 본 연구의 진단

위 다섯 가지를 종합하면 본 연구의 진단은 다음과 같다:

> page-level KG는 web agent의 navigation 측면을 부분적으로 다루지만, *intra-page widget salience* 문제를 효과적으로 다루지 못한다. 이를 보완하려면 KG가 페이지 *내부*까지 표현해야 하고, LLM에 주입되는 정보의 상당 부분이 page-level이 아니라 widget-level이어야 한다.

#### 1.4.1 연구 동기 — KG 부분 그래프 노출이라는 관점

본 연구는 다음 관점을 *동기*로 삼는다 (검증 가능한 가설은 §2의 H1'~H3에서 제시):

> **본 연구의 selective retrieval은 단순한 DOM 압축이 아니라, 사이트의 구조화된 KG 중 task-relevant한 부분 그래프를 노출하는 것이다.**

이 관점이 단순 DOM 압축과 다른 *operational* 차이를 만들려면 다음 두 가지가 prompt 구조에 명시적으로 들어가야 한다 (§4.2.1에서 구체화):

1. **labeled 추론 단서** — WidgetNode/InteractionEdge의 description, task_relevance_tags, side_effects, 그리고 그래프 구조 정보(어느 위젯이 어느 다른 위젯을 활성화하는가)가 함께 주입된다. 평면 element 리스트와 달리 *그래프 구조 위 추론*이 가능해진다.
2. **(optional) 미관측 메타 카운트** — 노출되지 않은 widget의 카테고리·개수를 prompt에 명시한다. "이 페이지에 KG에 등록된 widget이 12개 있고 그 중 5개를 보여줍니다. 나머지는 sort/modal 카테고리에 있습니다." 같은 형태. 이 메타 카운트의 효과는 §5의 조건 비교에서 별도로 측정한다 (조건 D vs D').

이 두 차원이 *없으면* 본 연구의 selective retrieval은 Mind2Web/Agent-E의 element ranking과 operational하게 구분되지 않는다. 즉 본 관점은 자동으로 따라오는 효과가 아니라, **prompt 구조와 알고리즘에 명시적으로 인코딩되어야 의미가 있다**.

이 관점이 알고리즘 차원에서 어떻게 반영되는지는 §4.2.1, 측정 방법은 §5.1·§5.4 참고.

#### 1.4.2 Cold-start와 시딩 비용 — 본 연구의 두 번째 축

§1.4.1의 관점은 *KG가 이미 있다*는 전제를 깔고 있다. 그러나 실제 운영 환경에서는 두 가지 부수 문제가 따라온다:

1. **Cold-start 문제** — 새 사이트에서 시작할 때 KG가 비어 있으면 Phase 1 widget retrieval이 작동할 수 있는 *대상 자체*가 없다. Phase 3 dynamic construction은 task가 *도달한* 페이지/위젯만 발견하므로 cold-start를 해결하지 못한다 (도달성에 묶임).
2. **시딩 비용** — 수동으로 declarative YAML 시드를 작성하면 minimal viable seed 기준 GitLab에서 약 6~10시간 (§4.1.7 fallback reference). 학습 기반 접근(수 일~수 주)보다 차수 작지만 *여전히 무겁다*. 본 연구의 design constraint("KG 구축이 쉬워야 한다")와 직관이 어긋난다.

본 연구는 두 문제를 동시에 해결하는 **핵심 메커니즘**으로 **§4.4 LLM-driven Offline KG Bootstrapping**을 도입한다 (마일스톤 M0.5). 이는 *본 연구 가치 명제의 핵심*이지 add-on이 아니다. Phase 3 dynamic construction과 별개로:
- *task 실행 전에* 사이트를 자동 graph traversal로 순회
- DOM에서 인터랙션 요소를 추출하고 LLM이 자연어 description + 자유 string 태그 생성 (분류 아님, §4.1.6 minimum viable 원칙)
- widget을 직접 click/hover하여 side_effects 관측 → InteractionEdge 자동 생성
- 결과를 declarative YAML로 dump → 사람은 confidence mid 항목만 검증

**시간 framing — 두 시나리오를 항상 분리**:

| 시나리오 | 사람 시간 | LLM/도구 비용 | 위치 |
|---|---|---|---|
| **★ 목표 (M0.5 작동 시)** | **사람 검증 ~30분~1시간** | bootstrapping wall-clock + LLM API (사이트당 100~200 호출, gpt-4o-mini 기준) | 본 연구의 *진짜 가치 명제* |
| Fallback (M0.5 미작동 시) | 사람이 처음부터 작성 ~6~10시간 | 0 | M0.5 검증 실패 시의 후퇴선 |
| 학습 기반 비교 (외부 baseline) | — | 수 일~수 주 (데이터 수집 + fine-tuning) | Mind2Web, AutoWebGLM, OmniParser 등 |

본 연구가 입증하려는 차수 절감은 *학습 기반(수 일~수 주) → 목표(30분~1시간)* 의 약 **2~3 차수**다. Fallback(6~10시간)은 1~2 차수 절감이지만 design constraint와 여전히 어긋난다 — *목표*가 진짜 가치 명제이고, 6~10시간은 정직성을 위해 보존하는 후퇴선일 뿐.

§1.4.1의 framing이 *이미 채워진 KG를 어떻게 잘 노출할 것인가*라면, §1.4.2는 *그 KG를 어떻게 거의 무료로 채울 것인가*를 다룬다. 두 축이 합쳐져야 본 연구의 가치 명제 — *학습 없이, 사람 비용을 사람 검증 수준으로 수렴, 새 사이트에 자동 적응* — 가 완성된다.

검증 가설은 §2의 H4, 알고리즘은 §4.4, 측정은 §5.4 ablation 8에서 다룬다. **중요**: M0.5가 작동하지 않으면 본 연구의 가치 명제가 "학습 대비 fallback 6~10시간" 수준으로 약해지며, 이는 §8에 명시된 *핵심 위험*이다.

### 1.5 본 연구가 답하려는 질문

1. 사이트의 페이지 내부 구조까지 표현하는 KG는 어떻게 정의해야 하는가?
2. 그런 KG로 매 step마다 LLM에 *task-relevant widget*만 selective하게 노출하면, page-level KG 대비 task 성공률이 얼마나 향상되는가?
3. 사이트마다 다른 widget 패턴을 어떻게 site-agnostic taxonomy로 추상화할 것인가?
4. 사람의 수동 시딩 없이 에이전트가 *task 수행 중* widget을 자율 발견·등록할 수 있는가?
5. **WebArena-Verified로 격리 검증된 효과가 Online-Mind2Web 같은 *다른* 평가 환경에서도 일관 작동하는가?** (cross-benchmark 일반화 — "Illusion of Progress?" 흐름과의 정합성)

---

## 2. 연구 가설

### H0 (중심 가설)

> **Hierarchical Site Knowledge Graph** (page graph + intra-page widget graph)를 LLM 웹 에이전트에 통합하여 (a) 현재 페이지의 task-relevant widget을 selective하게 노출하고, (b) site-specific widget interaction 패턴을 inference time에 주입하며, (c) widget 차원의 dynamic construction으로 새 사이트에 자동 적응하면, page-level KG augmentation 대비 task 성공률이 통계적으로 유의미하게 향상되며, 새 사이트로의 zero-shot 일반화가 가능해진다.

### H1' (핵심 가설 — 본 연구의 중심 주장)

> Page-level selective retrieval(조건 C)에 widget-level selective retrieval(조건 D)을 더하면, GitLab 14 task의 평균 성공률이 통계적으로 유의미하게 향상된다 (paired t-test, p < 0.05).

**선택적 sub-claim**: D - C 의 효과 크기가 C - B 의 효과 크기보다 크다 (즉 widget-level이 page-level보다 더 큰 추가 기여를 한다). 이 sub-claim은 *기대*이지 강제 검증 항목은 아니다 — H1' 본 가설은 D > C 만으로 채택된다.

**검증 방법**: 조건 B/C/D 측정 후 paired t-test. (§5)

### H2 (재정의)

> Path finding 기법은 두 종류의 path 모두에 적용된다: (a) page-level navigation path (BFS over G_page), (b) intra-page widget interaction sequence (InteractionEdge graph 위에서 LLM이 위상 reasoning). (b)가 사이트 다양성을 흡수하는 핵심 메커니즘이다.

### H3 (재정의)

> Dynamic construction은 (a) 새 PageNode 발견뿐 아니라 (b) 각 PageNode 내의 새 WidgetNode와 InteractionEdge까지 자동 추가해야 새 사이트로의 zero-shot 적응이 의미 있게 가능해진다. 본 연구의 *최종 목표*는 사람의 수동 시딩 없이도 GitLab 수준의 task 성공률에 도달하는 것이다.

### H4 (Offline KG Bootstrapping — M0.5 신설로 추가된 가설)

> **LLM-driven offline KG bootstrapping**(graph traversal + LLM description generator + interaction 시뮬레이션, §4.4)으로 자동 생성한 시드만으로 본 연구 알고리즘(조건 D)을 실행했을 때, 사람이 작성한 시드 대비 task 성공률 차이가 *일정 천장* 이내(예: 절대 차이 ≤ 15%p)에 머문다.

**검증 방법** (사용자 결정에 따라 *task 성공률 우선*):
- **Primary**: 조건 D를 두 번 측정 — `D_manual` (사람 시드) vs `D_auto` (자동 시드 only). paired t-test로 차이 검정. 본 가설은 `D_auto`가 `D_manual`의 일정 천장 이내에 머물면 채택.
- **Secondary** (보조 metric, §5.2): 자동 시드의 widget recall / precision / false positive rate를 사람 시드와 직접 비교. 자동 시드의 *품질*을 직접 측정하는 진단용.

**중요한 sub-claim**:
- 자동 시드가 사람 시드를 *능가*한다고 주장하지 않는다. *비교 가능한 천장 이내*면 충분 — 그 의미는 "사람 비용을 거의 0으로 줄이면서도 본 연구 알고리즘이 작동한다"는 운영 가치.
- 천장 초과 시(예: `D_auto`가 `D_manual`보다 30%p 낮음) H4는 기각되고, automated bootstrapping은 *스캐폴딩 도구*로만 자리매김 (사람이 자동 시드 위에서 수정).

### H5 (Cross-benchmark 일반화 — M6 신설로 추가된 가설)

> Hierarchical SiteKG + Phase 1/2/3 + M0.5 offline bootstrapping의 효과가 **WebArena-Verified GitLab 14 task** (내부 ablation 환경)와 **Online-Mind2Web sub-set** (cross-benchmark 일반화 환경) 두 환경에서 *방향성 일관*하게 관찰된다. 즉 본 연구의 hierarchical KG 효과가 WebArena GitLab에 *과적합*되지 않고 다른 평가 환경에서도 *같은 방향*으로 작동한다.

**채택 기준 (사용자 결정에 따라 *방향성 일관성만*)**:
- WebArena-Verified에서 H1' 채택 (D > C, paired t-test p < 0.05) → Online-Mind2Web에서도 D > C 방향이면 H5 채택
- **효과 크기(effect size) 동등 요구 안 함**. Online-Mind2Web의 효과 크기가 WebArena의 일부만 보존되어도 *방향성*만 같으면 채택. 두 환경의 task 분포가 다르므로 효과 크기 차이는 정상.

**중요한 sub-claim** (선택):
- *효과 크기 보존 비율*은 sub-claim으로 별도 보고 (예: WebArena 효과의 60% 이상 보존). 이는 본 가설의 *강한 형태*이지만 채택 조건 아님.

**의미**:
- H5가 채택되면: 본 연구의 효과가 단일 벤치마크 overfit이 아님. *cross-benchmark 일반화* 입증.
- H5가 기각되면: 본 연구 효과가 GitLab/WebArena 특화임을 솔직 보고. contribution을 *해당 환경 한정*으로 한정.

**Online-Mind2Web에서의 외부 baseline 비교 (자동 부수 효과)**:
H5 검증 과정에서 본 연구는 Online-Mind2Web의 leaderboard baseline (Browser-use 97%, GPT-5.4 92.8%, Operator 61%, Claude Computer Use 3.7, SeeAct ~early 2024 수준, 대다수 후속 agent 28~30%)과 *동일 환경*에서 자동 비교된다. 본 연구의 정직한 천장 목표는 *SeeAct 수준 도달 + 대다수 후속 agent 능가*이지 multimodal flagship 능가가 아님 (§7.1·§7.3 참고).

---

## 3. 관련 연구

### 3.1 LLM 웹 에이전트
- **WebGPT** (OpenAI 2021): 검색 + 브라우징을 LLM 도구로 노출. 사이트 구조 모델 없음.
- **ReAct** (Yao et al. 2022): Reasoning + Acting 인터리브 패턴. 본 프로젝트 v3 baseline의 토대.
- **WebArena / WebArena-Verified** (Zhou et al. 2023, ServiceNow 2024): 본 연구의 *내부 ablation 검증 환경*.
- **Mind2Web / MindAct** (Deng et al. NeurIPS 2023): 137개 웹사이트, 2000+ open-ended task. 학습 기반 element ranking. 자세한 분해는 §3.4.2.
- **Contextual Experience Replay** (Liu et al. ACL 2025): GPT-4o를 36.7%로 향상. 자연어 trajectory 누적.
- **AutoWebGLM** (Lai et al. KDD 2024): ChatGLM3-6B SFT/RL + HTML simplification. 자세한 분해는 §3.4.1.
- **SeeAct** (Zheng et al. ICML 2024): GPT-4V 시각 perception + DOM grounding. Mind2Web oracle grounding 50%. **본 연구가 Online-Mind2Web에서 직접 비교 대상으로 삼는 baseline** — *학습 0 + DOM 기반*이라는 본 연구와 가장 유사한 흐름. 자세한 분해는 §3.4.4.
- **WebVoyager** (He et al. 2024): screenshot + 텍스트 통합 LMM 에이전트. Set-of-Mark.
- **Agent-E** (Emergence AI, arXiv 2407.13032, 2024): hierarchical 에이전트 + flexible DOM distillation + change observation. WebVoyager 73.2%. *다른 벤치마크* SOTA이므로 본 연구와 직접 비교 대상은 아니지만, change observation은 본 연구 Phase 3의 직접 영감원. 자세한 분해는 §3.4.3.
- **★ Online-Mind2Web** (Xue et al., COLM 2025, arXiv:2504.01382, *"An Illusion of Progress?"*): **본 연구의 cross-benchmark 일반화 검증 환경**. 300 task × 136 websites. 기존 web agent의 보고 성능이 표면적 측정에 의존했음을 입증한 critical paper — *대다수 후속 agent가 SeeAct(early 2024) 수준을 능가하지 못함*을 발견. 본 연구는 이 paper의 진단을 공유하고 *intra-page widget salience*로 더 구체화한다.
- **★ Browser-use** (Browser-use Inc, 2025): production web agent. **Online-Mind2Web 97%** (Auto-Research 기법). 학습 + 외부 검색 결합. 본 연구 능가 대상 아님 — multimodal flagship 등급.
- **★ OpenAI Operator** (OpenAI, 2025): multimodal computer use agent. Online-Mind2Web 61% (사람 평가) / 71.8% (WebJudge). 본 연구의 *실용적 천장* reference.
- **★ Claude Computer Use 3.7** (Anthropic, 2025): multimodal computer use. Online-Mind2Web top performer 그룹. Operator와 동급.
- **★ GPT-5.4** (OpenAI, 2026-03): WebArena-Verified 67.3% (DOM + screenshot 통합), Online-Mind2Web 92.8% (screenshot only). multimodal flagship + 거대 학습 모델. 본 연구 능가 대상 아님 — *학습 0 + visual 0의 천장* 측정의 reference로만 인용.

### 3.2 Knowledge Graph + LLM (GraphRAG 류)
- **GraphRAG 서베이** (Peng et al. 2024)
- **SubgraphRAG** (Li et al. ICLR 2025)
- **GRAG** (Hu et al. NAACL 2025)
- **AGENTiGraph** (Zhao et al. CIKM 2025)
- **KG-Agent** (2024)
- **DynaSearcher** (2025)

이들은 모두 *external knowledge base*를 graph로 표현하는 데 집중한다. 본 연구는 "*사이트 자체가 graph*"이고 동시에 "*페이지 내부도 sub-graph*"라는 점에서 다르다.

### 3.3 Web Application as Knowledge Graph
- **Chandrasekharuni 2024 (arXiv 2410.17258)** "Representing Web Applications As Knowledge Graphs": 웹 앱을 state graph로. 주로 자동 테스트 케이스 생성.
- **Go-Browse** (Gandhi & Neubig, 2025, arXiv 2506.03533): 그래프 기반 exploration으로 학습 데이터 수집. exploration phase에서 KG 구축. 본 연구는 *task execution 중* 사용한다는 점에서 다르다.

### 3.4 Intra-page DOM understanding (본 연구가 가장 인접한 흐름)

본 연구의 widget layer가 다루는 *intra-page widget salience* 문제는 여러 흐름에서 부분적으로 연구되어 왔다. 이를 5개 sub-section으로 분해 정리한다.

#### 3.4.1 학습 기반 representation pretraining

DOM/HTML을 학습으로 표현하는 흐름.

- **WebFormer** (Wang et al. WWW 2022): 각 DOM 노드에 HTML token을 부여하고 graph attention으로 이웃 토큰의 representation을 embedding. 웹 레이아웃 구조를 attention weight 계산에 활용. structure information extraction 목적.
- **DOM-LM** (Deng et al. arXiv 2201.10608): "Learning Generalizable Representations for HTML Documents". HTML을 generic embedding으로 사전학습.
- **Pix2Struct** (Lee et al. ICML 2023): masked screenshot → simplified HTML 파싱을 pretraining objective로. variable-resolution input. UI/문서/일러스트 등 4개 도메인 6/9 task SOTA.
- **AutoWebGLM** (Lai et al. KDD 2024): "사람의 브라우징 패턴에서 영감 받은 HTML simplification algorithm" + operability flag + OCR 보조 + curriculum learning + RL + rejection sampling. ChatGLM3-6B SFT 기반. 학습 기반 SOTA 중 하나.

**본 연구와의 관계**: 모두 *학습 기반*. 본 연구는 같은 정보(어느 요소가 중요한지)를 *학습 없이 declarative KG*로 표현한다. 학습 비용 / 사이트 추가 비용 / cross-site 일반화 메커니즘에서 차이가 난다.

#### 3.4.2 학습 기반 element ranking + selection

페이지 내 candidate 요소를 ranking하는 흐름. 본 연구의 Phase 1 widget retrieval과 가장 직접적으로 비교되는 영역.

- **Mind2Web / MindAct** (Deng et al. NeurIPS 2023): **2-stage 모델**
  - Stage 1: fine-tuned DeBERTa classifier가 페이지 요소를 task relevance로 ranking. top-K candidate + ancestors만 남겨 DOM tree pruning.
  - Stage 2: top-K를 multiple-choice로 LLM에 제시 ("None of the above" = option A 항상 포함). LLM이 선택 → 행동 예측.

**본 연구와의 관계**: MindAct의 2-stage filter+select 패턴은 본 연구의 widget retrieval과 *정확히 같은 추상*이다. 차이는 **(a) Stage 1이 학습된 DeBERTa ranker가 아니라 *task_relevance_tags 기반 zero-shot ranking* (사람이 미리 KG에 박은 widget의 의미 태그와 task intent의 자연어 키워드를 직접 매칭)이고, (b) Stage 2의 candidate가 raw DOM 요소가 아니라 미리 정의된 WidgetNode**라는 것. 본 연구는 MindAct의 패턴을 *학습 없이* 재현하되 *task semantic은 KG에 박지 않는* 원칙(§4.1.6)을 유지한다 — 사람은 widget의 *의미 태그*만 박고, *어느 task에 어느 widget이 필요한지의 매핑*은 LLM이 자체 추론.

#### 3.4.3 Inference-time DOM compression / distillation (가장 직결)

학습 없이 runtime에 DOM을 압축하는 흐름. 본 연구와 직접 경쟁하는 영역.

- **Agent-E** (arXiv 2407.13032, 2024): **hierarchical 에이전트 (planner + browser navigation agent)** + **flexible DOM distillation** (task에 따라 3가지 DOM representation 중 선택) + **change observation** (행동 전후 DOM 차분을 LLM에 피드백). WebVoyager **73.2% SOTA**, 이전 multi-modal 에이전트 대비 +16%, text-only 대비 +20%.
- **Beyond Pixels: DOM Downsampling for LLM-Based Web Agents** (arXiv 2508.04412, 2025): downsampling = signal processing 개념을 DOM에 적용. 노드 syntax를 *semantic entity*로 보고 consolidation. site-agnostic 일반 압축.
- **Reduce LLM Agent Costs by 90% with Structure-Preserving HTML Compression** (HN, 2025): 산업계 제품. XPath/CSS selector 정확성을 유지하면서 토큰 비용 1/10. 산업계 신호.
- **LLMLingua** (Microsoft EMNLP 2023, ACL 2024): 일반 prompt/KV-cache 압축. 도메인 무관. 본 연구와 직교.

**본 연구와의 관계**: 가장 직접적인 경쟁 영역.
- **Agent-E의 change observation**은 본 연구의 Phase 3 dynamic construction의 직접 영감이다 — "행동 전후 관측 차분으로 새 widget/edge 발견". 본 연구의 차별화는 *change를 random discovery가 아니라 minimum viable KG의 4가지 정보(description / locator / visibility / side_effects)로 정리·등록한다*는 점, 그리고 *site-specific KG에 영구 commit하여 다음 task가 재사용한다*는 점.
- **Agent-E의 distillation은 site-agnostic policy**이고, 본 연구의 retrieval은 **site-specific declarative KG**다. 본 연구가 입증해야 할 핵심 주장: site-specific KG가 generic distillation보다 *cross-site 일반화*에서 우월하다.

#### 3.4.4 Visual / hybrid (DOM + screenshot)

순수 또는 hybrid 시각 기반 흐름.

- **SeeAct** (Zheng et al. ICML 2024): GPT-4V 기반 multi-modal 에이전트. visual perception + DOM grounding 결합. **결정적 발견**: "Set-of-Mark 같은 시각 단독 grounding은 web agent에서 부분 효과뿐. **HTML 구조와 visual을 결합한 grounding이 가장 효과적**" (GPT-4V is a Generalist Web Agent, if Grounded, arXiv 2401.01614). Mind2Web 라이브 사이트 oracle grounding 50%.
- **WebVoyager** (He et al. 2024): LMM + Set-of-Mark으로 인터랙션 요소 위에 numeric marker overlay. visual+DOM hybrid의 대표.
- **Set-of-Mark Prompting** (Yang et al. arXiv 2310.11441): SAM/SEEM으로 segmentation → 마크 overlay. 일반 vision task에서 SOTA지만 web agent에서는 부분 효과.
- **OmniParser** (Microsoft arXiv 2408.00203, 2024 / V2 2025-02): **순수 vision 기반** GUI agent. interactable icon detector + caption model + OCR. 67k 스크린샷 데이터셋으로 학습. WindowsAgentArena SOTA.

**본 연구와의 관계**: 본 연구는 *순수 텍스트 KG*를 채택한다. SeeAct의 결론("HTML과 visual 결합이 최선")이 본 연구에 도전을 제기한다 — 본 연구는 *학습 없이도 declarative widget KG만으로 충분한 grounding이 가능함*을 입증해야 한다. 만약 H1' 검증 후에도 visual 결합 없이는 한계가 있다면, future work로 *KG + screenshot Set-of-Mark 통합*을 제안.

#### 3.4.5 Offline KG bootstrapping / 사이트 자동 탐색 (M0.5와 직접 인접)

본 연구의 §4.4 LLM-driven offline bootstrapping과 가장 직접적으로 비교되는 흐름.

- **Go-Browse** (Gandhi & Neubig, 2025, arXiv 2506.03533) — graph traversal 기반 사이트 exploration. NavExplorer + FeasibilityChecker로 페이지를 자동 순회하며 trajectory 수집. 노드 = URL, 엣지 = trajectory. *학습 데이터 수집*이 목적이고, 수집한 trajectory로 sub-10B 모델을 SFT한다. WebArena에서 7B 모델 21.7% 도달.
- **OmniParser** (Microsoft 2024, V2 2025-02) — vision detector + caption model로 페이지의 인터랙션 요소를 자동 분류. 67k 스크린샷 라벨링 데이터로 학습. WindowsAgentArena SOTA.
- **Web Apps as Knowledge Graphs** (Chandrasekharuni 2024, arXiv 2410.17258) — 웹 앱을 state graph로 자동 표현. 자동 테스트 케이스 생성 목적. 본 연구의 PageNode/NavigationEdge 데이터 모델과 직접 일치.
- **Mind2Web의 trajectory 수집** (Deng 2023) — 사람이 137개 사이트에서 2000+ task의 trajectory를 수동 수집. 본 연구의 자동 시딩과는 정반대 극.

**본 연구의 차별화 (§4.4)**:
- vs Go-Browse: Go-Browse는 *page-level + trajectory*만, 본 연구는 *page-level + intra-page widget*까지 다루며 *DOM이 표현 못 하는 4가지 정보*만 박는다 (§4.1.6 minimum viable 원칙). Go-Browse는 *학습 데이터 수집*이 목적이고 수집 후 SFT 필요, 본 연구는 *inference-time KG 자체*가 산출물이고 학습 불필요.
- vs OmniParser: OmniParser는 *vision detector + 67k 라벨링 학습 필요*, 본 연구는 *학습 없이 LLM zero-shot 분류 + universal taxonomy*. 새 사이트 적용 시 OmniParser는 detector 재학습 또는 일반화 한계, 본 연구는 LLM 호출만.
- vs Web Apps as KG: Chandrasekharuni의 자동 테스트 케이스 생성 vs 본 연구의 *LLM 에이전트의 inference-time retrieval에 직접 사용*. 또한 widget-level 분류는 본 연구가 도입.
- vs Mind2Web 수집: 사람 수동 vs LLM 자동.

이 4개 비교는 §3.5의 전체 매트릭스와 §7.3 차별화 표에 통합된다.

#### 3.4.6 본 연구의 위치 (intra-page 흐름 안에서)

| 차원 | 학습 기반 representation (3.4.1) | 학습 기반 ranking (3.4.2) | Inference-time compression (3.4.3) | Visual/hybrid (3.4.4) | **본 연구** |
|---|---|---|---|---|---|
| 대표 | Pix2Struct, WebFormer, AutoWebGLM | Mind2Web/MindAct | Agent-E, Beyond Pixels | SeeAct, OmniParser | **Hierarchical SiteKG** |
| 학습 필요 | ◎ | ◎ | × | △ (vision detector) | **×** |
| Site-specific 구조 명시 | × | × | × | × | **◎** (PageNode + WidgetNode + Interaction/NavigationEdge) |
| Intra-page widget 다룸 | ○ (압축) | ◎ (ranking) | ○ (distillation) | ◎ (vision) | **◎** (KG retrieval) |
| 사이트 추가 비용 | 학습 데이터 수집 + 재학습 (수 일~수 주) | 학습 데이터 + 재학습 (수 일~수 주) | 0 (일반 압축) | vision detector 재학습 (수십 시간 + 67k 라벨링) | **★ M0.5 작동 시 (목표): 사람 검증 ~30분~1시간 + LLM API 비용** / fallback (M0.5 미작동 시): 수동 작성 ~6~10시간 — M0.5에서 직접 측정 |
| Cross-site 일반화 | 학습 일반화 | 학습 일반화 | distillation policy | LMM 일반화 | **description의 의미적 유사성 (LLM embedding 매칭)** |
| Inference-time 자동 구축 | × | × | △ (Agent-E change obs) | × | **◎** (Phase 3) |

본 연구의 차별화 한 줄: **intra-page widget representation을 학습 없이, site-specific declarative KG + universal taxonomy로 다룬다**. 이 조합은 기존 흐름에서 명시적으로 시도된 적이 드물며, 학습 비용 / 사이트 추가 비용 / cross-site 일반화 메커니즘 차원에서 기존 접근과 구분된다.

### 3.5 본 연구의 위치 (전체 흐름 종합)

| 차원 | 기존 LLM 웹 에이전트 (텍스트 기반) | 기존 KG-RAG | 학습 기반 representation/ranking (3.4.1, 3.4.2) | Inference-time DOM compression (3.4.3) | Visual/hybrid (3.4.4) | **본 연구** |
|---|---|---|---|---|---|---|
| 도메인 | 웹 자동화 | QA, 챗봇 | 웹 자동화 | 웹 자동화 | 웹 자동화 | **웹 자동화** |
| 지식 표현 | 텍스트 (대화 기록) | external KG | 학습된 representation | 일반 압축 정책 | 학습된 vision representation | **사이트 hierarchical KG** |
| Intra-page 다룸 | × (관측만) | × | ◎ (학습) | ○ (압축) | ◎ (vision) | **◎ (declarative KG)** |
| Site-specific 구조 명시 | × | × | × | × | × | **◎ (PageNode + WidgetNode + Interaction/NavigationEdge — *task semantic 박지 않음*)** |
| 적응 방식 | — | 정적 | 학습 (RL/SFT) | 정적 정책 | 학습/LMM | **inference time KG 갱신** |
| 새 사이트 일반화 | — | 정적 KG 재구축 | 학습 재실행 필요 | 일반 정책 적용 | LMM 일반화 또는 detector 재학습 | **자동 KG 구축 (Phase 3)** |

본 연구의 차별화: **intra-page widget representation을 학습 없이 declarative KG로 다루면서, *사이트 구조*만 KG에 박고 *task 풀이는 LLM의 자체 추론*에 위임하는 접근**. site-specific 차원(WidgetNode 정의 + InteractionEdge)과 site-agnostic 차원(Universal WidgetType taxonomy)을 결합하되, *task semantic은 KG에 박지 않는다*는 명시적 분리(§4.1.6). 이 조합과 분리 원칙 자체가 기존 흐름과 구분되며, 상대적 효과는 §5의 조건 비교로 경험적으로 검증한다.

---

## 4. 방법론

### 4.1 Hierarchical Site Knowledge Graph 정의

#### 4.1.1 형식 정의

```
SiteKG = (G_page, {G_widget(p) | p ∈ V_page})

Layer 1: Page-level graph
   G_page = (V_page, E_page)
   V_page = PageNode 집합
   E_page = NavigationEdge 집합 (V_page × V_page, source ≠ target)

Layer 2: Per-page widget graph (각 PageNode p마다)
   G_widget(p) = (V_widget(p), E_widget(p))
   V_widget(p) = WidgetNode 집합 (p에 속하는 인터랙션 요소)
   E_widget(p) = InteractionEdge 집합 (위젯 간 활성/의존 관계)

Cross-layer:
   각 NavigationEdge는 trigger_widget_key ∈ V_widget(source) 를 가질 수 있음
   (또는 None — direct goto)

★ KG에 *없는* 것 (§4.1.6 minimum viable 원칙):
   - widget_type / category / WidgetType taxonomy (DOM의 tag/role/class에서 직접 추출)
   - element raw metadata (DOM에서 runtime에 직접 추출, KG에 박지 않음)
   - task → widget mapping (LLM의 영역)
   - task family 분류 (알고리즘 input 아님; §5.2의 사후 분석 카테고리로만 사용)
   - task 풀이 sequence (LLM의 영역)

★ KG가 박는 것 (DOM이 원리적으로 표현 못 하는 4가지, §4.1.6):
   1. Connectivity (NavigationEdge + InteractionEdge)
   2. Conditional state (visibility_condition)
   3. Causal effects (side_effects, trigger_widget_key)
   4. Stable references (locator_strategy/value)
```

#### 4.1.2 PageNode (옛 PageType 확장) + Matching 알고리즘

```
PageNode {
  page_node_id: str
  site_id: str
  page_key: str                        # 사람이 읽는 식별자 ("issues_list")
  display_name: str
  description: str                     # LLM 주입용 의미 설명
  url_patterns: list[str]              # ★ Express.js placeholder 형식 (아래 명시)
  structural_signals: list[str]        # 페이지 식별 보조 신호 (tiebreak fallback)
  widget_nodes: list[WidgetNode]       # 이 페이지의 위젯들
  widget_edges: list[InteractionEdge]  # 위젯 간 관계
}
```

PageNode는 더 이상 *flat한 페이지 유형 식별자*가 아니라, **그 자체로 sub-graph를 가지는 컨테이너 노드**다.

##### URL pattern 형식 (Express.js placeholder)

```yaml
url_patterns:
  - "/dashboard"                      # 정확 매칭
  - "/projects/:ns/:project"          # placeholder (임의 식별자, wildcard 역할)
  - "/users/:user/projects"
  - "/:catchall"                      # catch-all (모든 path)
  - "/explore?visibility_level=20"    # query parameter 명시 시 매칭에 포함
```

**규칙**:
- `:name` placeholder는 *임의 path segment*를 매칭 (regex `[^/]+`)
- placeholder 이름은 가독성용 — 매칭에 영향 없음
- **Query parameter**: 기본 *무시*. 명시 시 (`?key=value`) 매칭에 포함
- **URL fragment** (`#section`): 기본 *무시*
- **Trailing slash**: 정규화 (`/issues` ≡ `/issues/`)
- **SPA hash routing** (`/dashboard#issues`): 본 연구 범위 외 — future work (§11)

##### Matching 알고리즘 (deterministic priority)

PageNode 매칭은 매 step의 retrieval 시작점이라 *deterministic*해야 한다 (LLM 위임 없음, 임의 가중치 없음). 알고리즘:

```python
def match_page_node(current_url, current_dom, sitekg) -> PageNode | "UNRESOLVED":
    """
    Priority (deterministic):
    1. URL pattern 매칭 (Express.js placeholder)
    2. 후보 1개 → 채택
    3. 여러 후보 → specificity (placeholder 적은 것) 우선
    4. 같은 specificity → structural_signals tiebreak
    5. 매칭 0개 → UNRESOLVED
    """
    # Normalize: query/fragment 제거 + trailing slash 정규화
    url_path = normalize_url(current_url)

    # Stage 1: URL pattern matching
    candidates = []
    for pn in sitekg.page_nodes:
        for pattern in pn.url_patterns:
            if pattern_matches(pattern, url_path):
                candidates.append((pn, pattern))
                break

    if len(candidates) == 0:
        return "UNRESOLVED"
    if len(candidates) == 1:
        return candidates[0][0]

    # Stage 2: specificity sort (placeholder 적은 것 우선)
    candidates.sort(key=lambda c: pattern_specificity(c[1]), reverse=True)
    top_specificity = pattern_specificity(candidates[0][1])
    top_candidates = [c[0] for c in candidates if pattern_specificity(c[1]) == top_specificity]

    if len(top_candidates) == 1:
        return top_candidates[0]

    # Stage 3: structural_signals tiebreak (deterministic — 첫 후보가 default)
    return tiebreak_by_signals(top_candidates, current_dom)


def pattern_matches(pattern: str, url_path: str) -> bool:
    """Express.js placeholder를 regex로 변환 후 매칭."""
    # ":name" → "[^/]+"
    regex_str = re.sub(r":\w+", r"[^/]+", re.escape(pattern).replace(r"\:", ":"))
    return re.fullmatch(regex_str, url_path) is not None


def pattern_specificity(pattern: str) -> int:
    """placeholder가 적을수록 specific. 100 - (placeholder 수 × 20)."""
    return 100 - pattern.count(":") * 20


def normalize_url(url: str) -> str:
    """query/fragment 제거 + trailing slash 정규화."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return path


def tiebreak_by_signals(candidates: list[PageNode], current_dom) -> PageNode:
    """structural_signals 매칭 점수가 가장 높은 후보. 모두 0이면 첫 후보 (deterministic)."""
    scored = [(pn, count_matching_signals(pn.structural_signals, current_dom)) for pn in candidates]
    return max(scored, key=lambda x: x[1])[0]
```

**Specificity 예시**:
- `/issues` → 100 (placeholder 0)
- `/projects/:ns/:project` → 60 (placeholder 2)
- `/:catchall` → 80 (placeholder 1)

GitLab의 `/projects/foo`가 `/projects/:ns/:project`와 `/:catchall` 두 후보에 매칭되면 → 전자(60 < 80?)... 잠깐, *placeholder 적은 것*이 specific이므로 `/:catchall`(1)이 `/projects/:ns/:project`(2)보다 더 specific으로 계산. **이는 의도와 반대**.

→ 정정: specificity 함수는 *경로 길이*도 고려해야 함. 더 정확한 정의:

```python
def pattern_specificity(pattern: str) -> int:
    """더 긴 path + 더 적은 placeholder가 specific."""
    segments = [s for s in pattern.split("/") if s]
    placeholder_count = sum(1 for s in segments if s.startswith(":"))
    literal_count = len(segments) - placeholder_count
    return literal_count * 100 - placeholder_count * 10
```

- `/issues` → 1 literal × 100 = 100
- `/projects/:ns/:project` → 1 × 100 - 2 × 10 = 80
- `/:catchall` → 0 - 1 × 10 = -10

이 정의로 `/projects/:ns/:project` (80)이 `/:catchall` (-10)보다 specific하게 평가됨. 의도와 일치.

##### Unresolved 결정 기준

- URL pattern 매칭 0개 → `UNRESOLVED`
- structural_signals만 매칭되는 케이스는 *고려 안 함* (URL 우선 원칙)
- M0.5 / Phase 3 dynamic construction이 `UNRESOLVED` 결과를 받아 새 PageNode 후보 생성

##### 단위 테스트 (M0 필수)

`runtime/sitekg/page_matcher.py` (또는 `store.py`의 메서드)에 다음 케이스 ~20개 단위 테스트:
- 정확 매칭 (`/dashboard`)
- placeholder 매칭 (`/projects/foo/bar` → `/projects/:ns/:project`)
- catch-all과의 specificity (`/projects/foo` → `/projects/:ns` 우선, not `/:catchall`)
- query parameter 무시 (`/issues?state=open` → `/issues`)
- query parameter 명시 매칭 (`/explore?visibility_level=20`)
- trailing slash 정규화 (`/issues/` ≡ `/issues`)
- structural_signals tiebreak (URL 같지만 DOM 다른 경우)
- UNRESOLVED 반환 (매칭 0개)
- 잘못된 매칭 회피 (다른 사이트 도메인)

#### 4.1.3 WidgetNode (신규 — 본 연구의 핵심 도입)

```
WidgetNode {
  widget_node_id: str
  site_id: str
  page_key: str
  widget_key: str                      # 사람이 읽는 식별자 ("search_box")
  display_name: str                    # (★ DOM의 aria-label/text에서 자동 보강 가능)
  description: str                     # ★ 핵심 — LLM 주입용 자연어 의미 ("검색창 — 클릭 시 필터 드롭다운 노출")
  task_relevance_tags: list[str]       # 자유 string 태그 ("filter", "sort", ...). enum 아님
  locator_strategy: str                # ★ KG가 박음 — "role" | "testid" | "aria" | "text" | "css"
  locator_value: str                   # ★ KG가 박음 — 안정 selector
  visibility_condition: str | None     # ★ KG가 박음 — 동적 조건
  side_effects: list[str]              # ★ KG가 박음 — 행동 결과
}
```

**★ widget_type 필드 *없음*** (§4.1.5 폐기, §4.1.6 minimum viable 원칙). type/category/raw metadata는 *runtime에 DOM에서 직접 추출*. KG는 *DOM이 표현 못 하는 4가지*만 박는다 (description은 사람의 의미 보강 + LLM 매칭 토대, locator/visibility/side_effects는 안정성/조건/인과).

WidgetNode는 "사람이 보면 즉시 식별 가능한 페이지 내 인터랙션 요소" 1건을 표현한다. *task semantics*가 아니라 *위치/의존/조건/식별*의 4가지 관점에서 정의된다.

#### 4.1.4 NavigationEdge / InteractionEdge (옛 ActionSchema 분화)

```
NavigationEdge {  # 페이지 간 전이만
  navigation_edge_id: str
  site_id: str
  action_key: str                      # "click_dashboard"
  source_page_key: str
  target_page_key: str
  trigger_widget_key: str | None       # 어느 위젯이 trigger하는가
  description: str
  preconditions: list[str]
  postconditions: list[str]
}

InteractionEdge {  # 같은 페이지 내 위젯 간 관계
  interaction_edge_id: str
  site_id: str
  page_key: str
  source_widget_key: str
  target_widget_key: str
  interaction_type: str                # "activates" | "fills" | "depends_on" | "toggles"
  description: str
}
```

옛 `ActionSchema`는 page-changing click과 intra-page interaction을 한 클래스에 섞었다. 이 둘은 본질적으로 다른 정보다:
- NavigationEdge: G_page의 엣지. BFS path finding의 대상.
- InteractionEdge: G_widget의 엣지. widget interaction sequencing의 대상.

#### 4.1.5 *(폐기 — 2026-04-11)* Universal WidgetType taxonomy

**상태**: 본 연구에서 **완전 폐기**.

**폐기 이유** (§4.1.6 minimum viable KG 원칙에 의해):
- 본 연구는 KG에 박을 정보를 *DOM이 원리적으로 표현 못 하는 4가지*로 좁혔다 — connectivity / conditional state / causal effects / stable references (§4.1.6).
- WidgetType / category / element type 같은 *분류 정보*는 DOM이 이미 표현한다 (HTML tag, ARIA role, class names, aria attributes 등). KG가 *복사해서 박을* 가치가 없다.
- type 분류는 *runtime에 DOM에서 직접 추출*하거나, *cross-site 의미 매칭*은 LLM의 description 기반 reasoning으로 처리.
- 사용자의 일관된 통찰: *"카테고리 라벨이 굳이 있어야 해? `<a>` 태그의 class라던가, HTML/DOM에서부터 카테고리를 가져오면 안 되려나?"*

**대체** (§4.1.6 4가지 정보 + §4.1.3 단순화된 WidgetNode):
- WidgetNode에 `widget_type` 필드 *없음*
- `infer_widget_type()` 함수 *없음*
- 35개 enum *없음*
- LLM 분류기 *없음* (M0.5는 *description generator*로 재정의)
- type/category는 *runtime에 DOM의 tag/role/class에서 직접 추출*
- cross-site 일반화는 *description의 의미적 유사성*으로 LLM이 자동 매칭

**향후 본 문서의 어디에서도 WidgetType을 새로 정의하지 말 것**. KG가 박을 가치가 있는 정보의 기준은 §4.1.6 4가지 정보 원칙으로 통합되었다.

#### 4.1.6 KG의 표현 범위 — *Minimum viable KG: DOM이 원리적으로 표현 못 하는 4가지만*

본 연구의 KG는 다음 *minimum viable* 원칙을 엄격히 따른다:

> **KG는 DOM이 원리적으로 표현 못 하는 4가지 정보만 박는다 — 그 외 모든 것 (type, category, raw metadata, text)은 DOM에서 직접 추출하거나 LLM이 추론한다.**

##### KG가 박는 4가지 정보 (DOM에서 *원리적으로* 못 가져오는 것)

1. **Connectivity** (연결 관계) — 시간/공간을 가로지르는 정보
   - PageNode 간 NavigationEdge: 어느 페이지에서 어느 페이지로 갈 수 있는가
   - WidgetNode 간 InteractionEdge: 어느 widget이 어느 widget을 활성화/의존하는가
   - **DOM은 *현재 한 페이지의 한 시점*만 본다. 연결은 *행동 결과*로만 알 수 있다.**

2. **Conditional state** (동적 조건)
   - WidgetNode.visibility_condition: "이 widget은 X 조건에서만 보임"
   - **DOM은 *현재 보이는 것*만 본다. 조건부 widget(modal, AJAX dropdown)은 여러 상태를 시도해본 후에야 추론 가능.**

3. **Causal effects** (행동의 인과 결과)
   - WidgetNode.side_effects: "이 click이 다른 widget을 활성화/페이지 전이를 일으킴"
   - NavigationEdge.trigger_widget_key: "이 widget click이 페이지 전이를 trigger"
   - **DOM은 행동을 미리 예측 못 한다. 인과는 *시도해본 후*에만 알 수 있다.**

4. **Stable references** (안정 식별자)
   - WidgetNode.locator_strategy / locator_value: 동적 DOM에서 *안정적인 selector* 선택
   - **DOM은 *어느 selector가 안정*인지 모른다 (동적 class vs role/aria). 사람의 *판단* 또는 LLM의 추론.**

##### KG가 박지 *않는* 것 (DOM에 이미 있거나 LLM이 추론)

| 정보 | 어디서 처리되는가 |
|---|---|
| type / category | DOM에서 직접 (tag, ARIA role, class names) |
| element text / aria-label / placeholder | DOM에서 직접 |
| element 부모/자식 구조 | DOM에서 직접 |
| task → widget mapping | LLM의 영역 (task semantic 추론) |
| task family 분류 | LLM의 영역 (자연어 키워드 매칭) |
| task 풀이 sequence | LLM의 영역 (KG 위 reasoning) |
| widget 간 의미 매칭 (cross-site) | LLM의 영역 (description embedding similarity) |

##### 본 연구의 설계 원칙 — Minimum viable seed

KG에 박을 정보는 *4가지 정보 원칙*을 통과해야 한다. 새 정보를 추가할 때 항상 자문:
1. *DOM에서 직접 가져올 수 있는가?* → Yes면 KG에 박지 말 것
2. *LLM이 자연어로 추론할 수 있는가?* → Yes면 KG에 박지 말 것
3. *행동의 결과로만 알 수 있는가?* → Yes면 KG에 박을 것 (또는 Phase 3가 자동 학습)
4. *사람의 경험 (안정 selector, visibility 조건)으로만 알 수 있는가?* → Yes면 KG에 박을 것

이 원칙으로 본 연구는 시드 작성 비용을 *minimum viable*로 환원한다. 사람은 *DOM이 모르는 것*만 박고, *DOM이 아는 것*은 runtime에 DOM에서 직접 추출, *task 풀이*는 LLM의 자체 reasoning에 위임한다. 이게 *진짜 site-adaptive*이고 본 연구의 학술적 기여 #1 (§7.1)의 핵심이다.

##### 결과: LLM의 일과 KG의 일의 명확한 분리

- **KG의 일**: 4가지 정보 박음 (connectivity / conditional state / causal effects / stable references)
- **DOM의 일**: 매 step의 현재 element 정보 제공 (tag/role/class/text/aria)
- **LLM의 일**: KG (4가지) + DOM (현재 상태)을 동시에 보고 *task 풀이* 자체 추론 — 어느 widget을 어느 순서로 클릭할지, 어느 페이지로 갈지, 언제 멈출지

이 3-way 분리가 본 연구의 design 핵심.

#### 4.1.7 Declarative seed format (YAML)

KG 시딩이 *쉽고 범용적*이어야 한다는 design constraint를 만족하기 위해, 시드는 코드(Python dict)가 아니라 declarative YAML로 작성한다.

```yaml
site:
  id: gitlab
  display_name: GitLab
  base_url: https://gitlab.example.com

pages:
  - page_key: issues_list
    display_name: Issues
    url_patterns: ["/-/issues"]
    description: |
      Open issues by default, newest first.
    widgets:
      - widget_key: search_box
        description: "검색창. 클릭하면 AJAX로 필터 드롭다운(Label/Assignee/Author)이 노출됨"
        locator: { strategy: role, value: searchbox }
        task_relevance: [filter, search]                    # ← 자유 string (enum 아님)
        side_effects: [activates_filter_dropdown]
      - widget_key: label_dropdown
        description: "Label 필터. search_box 클릭 후에만 보임"
        locator: { strategy: text, value: Label }
        visibility_condition: visible_after_search_box_click
      - widget_key: state_tabs
        description: "Open / Closed / All 탭"
        locator: { strategy: role, value: tablist }
        task_relevance: [filter, view_switch]
      - widget_key: sort_dropdown
        description: "정렬 기준 드롭다운 (Created date / Updated date / Priority)"
        locator: { strategy: text, value: "Sort by" }
        task_relevance: [sort, ordering]
    widget_edges:
      - source: search_box
        target: label_dropdown
        type: activates

navigation:
  - source: project_overview
    target: contributors
    trigger: project_overview.contributors_link
    description: "Click Contributors in the sidebar"
```

**시드에 *없는 것* (의도적, §4.1.6 minimum viable 원칙)**:
- `type:` / `widget_type:` 필드 — *없음*. type/category는 runtime에 DOM의 tag/role/class에서 직접 추출
- `task_widgets:` 같은 task→widget 명시 매핑 — *없음*. task의 풀이는 LLM이 KG 위에서 자체 추론
- task family 분류 — *없음*. 사람은 사이트 구조 (4가지 정보)만 박고, task semantic은 LLM의 영역
- element raw metadata (text, aria-label, class) — *없음*. runtime에 DOM에서 직접 읽음

**시드에 *있는 것* (의도적, §4.1.6의 4가지 정보)**:
- `description` — 사람 보강 (또는 LLM 자동 생성). LLM의 의미 매칭의 토대
- `locator: { strategy, value }` — 안정 selector (stable references)
- `task_relevance` — 자유 string 태그, LLM ranking 보조
- `visibility_condition` — 동적 조건 (conditional state)
- `side_effects` — 행동 인과 (causal effects)
- `widget_edges:` (Interaction) + `navigation:` — 연결 관계 (connectivity)

이 형식의 **목표 시간** (M0.5 §4.4 offline bootstrapping 작동 시): 사람이 *처음부터* 작성하는 게 아니라 **M0.5가 자동 생성한 시드의 confidence mid 항목을 검증**만 하는 수준 — **사람 작업 시간 약 30분~1시간**. 이게 본 연구의 *진짜 목표 시간*이고 가치 명제의 핵심. v1의 Python 하드코딩 시드는 폐기.

**Fallback reference 추정** (M0.5 미작동 시, 목표 아님): 본 연구의 GitLab YAML 시드(9 PageNode + 페이지당 ~6 widget + 페이지당 ~3~5 InteractionEdge + ~10 NavigationEdge)를 사람이 *처음부터 작성*하는 데는, widget당 4~6분 (selector 검증 + side_effect 관찰 포함) 기준으로 *minimal viable seed*가 약 **5~9시간** 단위로 추정된다 (TaskWidgetMap 폐기로 약간 감소). 이 추정은 산업계 Page Object pattern (페이지당 1~2시간) 및 Mind2Web task 트레이스 수집 (task당 30분+) 비교에서 도출된다. M0.5 검증이 실패할 경우의 후퇴선이다 — 본 연구의 *목표*가 아니라 *fallback baseline*.

**차수 비교**:
- *학습 기반 접근* (Mind2Web/AutoWebGLM/OmniParser 데이터 수집 + fine-tuning, 수 일~수 주)
- → **M0.5 목표** (사람 검증 30분~1시간 + LLM API 비용): **2~3 차수 절감**
- → M0.5 fallback (사람 수동 6~10시간): 1~2 차수 절감

본 연구는 *절대 시간*이 아니라 *학습 기반 대비 차수 절감*을 가치 명제로 삼되, **목표 시나리오가 fallback이 아니라 M0.5 작동 시**임을 명확히 한다. 정확한 wall-clock은 M0.5 + M4에서 직접 측정.

### 4.2 세 가지 KG 기법 통합 (모두 widget-aware)

#### 4.2.1 Phase 1: Two-Level Selective Retrieval — 본 연구의 핵심 #1

**문제**: 매 LLM 호출마다 페이지 내 50+개 요소 중 *어느 일부만* LLM에 보여줄 수 있다. 이 일부를 어떻게 고르느냐가 task 성공률을 결정한다.

**Phase 1의 두 가지 design choice (§1.4.1과 짝)**:

본 연구의 selective retrieval이 단순 element ranking과 *operational하게* 다르려면, 알고리즘이 다음 두 가지를 prompt에 명시적으로 인코딩해야 한다:

1. **Label-rich graph context (필수)**: 단순 widget 리스트가 아니라 *그래프 위의 라벨이 함께 들어간 KG 부분 그래프*를 직렬화한다. 각 WidgetNode의 description / task_relevance_tags / side_effects, 그리고 InteractionEdge로 표현된 *위젯 간 의존 관계*를 prompt에 포함한다. 평면 element 리스트와 달리 그래프 구조 위 추론이 가능해진다 (예: "검색창을 클릭해야 label_dropdown이 보임"이라는 InteractionEdge가 함께 주입됨).

2. **Unobserved meta-count (선택, ablation으로 측정)**: 노출된 widget 외에 KG에 등록된 widget 카테고리·개수를 prompt에 명시한다. 예: *"이 페이지에 KG에 등록된 widget이 12개 있고 그 중 5개를 보여줍니다. 나머지는 sort/modal/settings 카테고리에 있습니다."* 이 메타 카운트의 *실제 효과*는 §5.4 ablation 4 (D vs D')에서 측정한다 — 본 연구의 검증되지 않은 기대이지 강제 가정이 아니다.

이 두 차원이 *모두 없으면* Phase 1은 Mind2Web/Agent-E의 element ranking과 operational하게 동일해지고, 본 연구의 차별화는 시딩 방식(declarative vs 학습)에 머문다.

**해결**: KG에서 두 레벨로 selective retrieval:

```
input: current_url, task_intent, page_observation, sitekg
output: LLMContext {
  page_layer: 1-hop 이웃 PageNode description (현재 페이지에서 갈 수 있는 곳)
  widget_layer: 현재 PageNode의 task-relevant WidgetNode top-K
  widget_to_dom: 각 WidgetNode → DOM selector + 주변 컨텍스트
}
```

**Widget retrieval 알고리즘**:

```
def extract_relevant_widgets(current_url, task_intent, page_observation, sitekg, K=8):
    # ★ §4.1.2 deterministic matching 알고리즘 사용
    page_node = match_page_node(current_url, page_observation.dom, sitekg)
    if page_node == "UNRESOLVED":
        return []  # Phase 3 dynamic construction이 새 PageNode 생성
    candidate_widgets = page_node.widget_nodes

    # 1. task_relevance_tags 기반 zero-shot ranking
    #    (★ task family 추론 / TaskWidgetMap lookup 단계 *없음*. §4.1.6 원칙)
    relevant_tags = extract_keywords_from_intent(task_intent)  # 자연어 → 키워드 set
    scored = []
    for w in candidate_widgets:
        score = len(set(w.task_relevance_tags) & relevant_tags)
        score += semantic_similarity(w.description, task_intent)
        scored.append((w, score))

    # 2. visibility_condition 필터링 (현재 page state에 보이는 것만)
    visible = [w for w, s in scored if check_visible(w, page_observation)]

    # 3. top-K
    return sorted(visible, key=score, reverse=True)[:K]
```

**핵심**: 알고리즘은 *task family 분류*나 *task→widget 명시 매핑*에 의존하지 않는다. 자연어 task intent의 키워드와 widget의 task_relevance_tags를 직접 매칭하고, semantic similarity로 보조 ranking. **task의 풀이 sequence를 결정하는 건 LLM이지 retrieval 알고리즘이 아니다** — retrieval은 *재료를 골라서 LLM에 보여주는 것까지*가 일이고, 클릭 순서·재시도 등 *행동 결정*은 LLM이 KG 위에서 자체 추론.

**LLM에 주입되는 정보** (예: GitLab issues_list에서 "filter by label" task):
```
[Page context]
You are on: issues_list (Issues page)
Possible navigation: → merge_requests, → project_overview

[Task-relevant widgets on this page]
1. search_box (search_filter_combo): 검색창. 클릭하면 필터 드롭다운이 활성화됨.
   selector: role=searchbox
   activates: label_dropdown, assignee_dropdown
2. label_dropdown (dropdown): Label 필터. search_box 클릭 후에만 보임.
   selector: text="Label"
   visibility: visible_after_search_box_click
3. state_tabs (tab_strip): Open / Closed 탭.
   selector: role=tablist
4. sort_dropdown (sort_dropdown): 정렬 기준 (Created date / Updated date / ...)
   selector: text="Sort by"
```

전체 DOM 덤프(50+ 요소)가 아니라 *task-relevant 위젯 3~8개* + 그들의 selector + InteractionEdge 정보가 LLM에 주입된다. **클릭 순서는 LLM이 자체 추론**: 위 정보로부터 LLM은 "search_box를 먼저 클릭해야 label_dropdown이 보임"을 *그래프 구조에서 읽어내고*, 그 위에서 행동 sequence를 자체 결정한다. 이게 본 연구의 핵심 메커니즘 — KG는 *재료*, LLM은 *추론자*.

#### 4.2.2 Phase 2: Two-Level Traversal Planning

**Page-level path finding** (BFS, v1과 동일):
```
find_navigation_path(start_page, target_page, sitekg) → list[NavigationEdge]
```
NAVIGATE task에서 LLM이 중간 페이지를 누락하는 문제 해결.

**Widget-level interaction reasoning** (신규):
```
build_widget_context(page_node, retrieved_widgets, sitekg) → LLMContext
```
**알고리즘이 sequence를 *결정*하지 않는다** (§4.1.6 원칙). retrieval이 골라준 widget set + 그들 사이의 InteractionEdge (`activates`, `depends_on`, `fills`, `toggles`)를 함께 LLM에 노출하면, **LLM이 InteractionEdge graph 위에서 자체 위상 reasoning을 수행**한다 — 예를 들어 `search_box --activates--> label_dropdown` 엣지를 보고 LLM이 *"search_box를 먼저 클릭해야 label_dropdown이 나타난다"*는 순서를 자체 추론. 알고리즘은 *재료를 잘 골라 보여주는 것까지*가 일이고, *순서 결정*은 LLM의 reasoning 영역.

Page-level navigation path는 sub-goal sequence로 변환되어 planner에 제공:
```
[Navigate: home → project_overview]
[Navigate: project_overview → issues_list]
[Interact: 현재 페이지의 retrieved widget을 LLM이 자체 reasoning으로 사용]
[Extract: result list]
```

즉 *navigation path*는 알고리즘이 BFS로 계산해 LLM에게 sub-goal로 주지만, *intra-page widget interaction sequence*는 LLM이 KG 위에서 자체 reasoning한다.

#### 4.2.3 Phase 3: Two-Level Dynamic Construction — 본 연구의 핵심 #2

**영감원**: Agent-E (§3.4.3)의 *change observation* 메커니즘 — 행동 전후 DOM 차분을 LLM에 피드백 — 이 본 phase의 직접 영감이다. 본 연구의 차별화는 다음 두 가지:
1. change를 *random discovery*가 아니라 **§4.1.6의 4가지 정보 (locator / visibility / side_effects + LLM 자동 생성 description)**로 정리·등록한다.
2. discovery 결과를 *transient feedback*이 아니라 **site-specific KG에 영구 commit**하여 다음 task가 재사용한다.

**Page-level dynamic**:
- 새 PageNode 발견: `match_page_node(current_url, dom, sitekg) == "UNRESOLVED"`일 때 (§4.1.2 알고리즘) 새 노드 후보 생성. URL 정규화·specificity 정렬·signals tiebreak 모두 deterministic한 결과로 unresolved 판정.
- 새 NavigationEdge 발견: 페이지 전이가 발생했는데 KG에 없으면 새 엣지 생성

**Widget-level dynamic (★ 본 연구의 최종 목표)** — **§4.1.6 minimum viable 원칙 따름**: type 분류 없음, description 자동 생성:

```
def discover_widgets_from_observation(page_obs, current_page_node, sitekg):
    """매 step의 페이지 관측에서 새 WidgetNode 후보를 추출한다.
    type 분류 단계 없음 — DOM raw metadata는 element가 직접 들고 있고,
    KG에는 4가지 정보 (locator + description + visibility + side_effects)만 박는다.
    """
    candidates = []
    for element in page_obs.interactive_elements:
        if not matches_existing_widget(element, current_page_node):
            candidate = WidgetNode(
                widget_key=derive_widget_key(element),
                # ★ widget_type 없음 (DOM의 tag/role/class에서 직접)
                locator_strategy=element.best_selector_strategy,  # 안정 selector 선택
                locator_value=element.best_selector,
                description=llm_generate_description(element),    # ★ LLM이 자연어 의미 생성
                task_relevance_tags=llm_infer_tags(element),      # ★ LLM이 자유 string 태그 생성
                # visibility_condition / side_effects는 후속 관측으로 채움
            )
            candidates.append(candidate)
    return candidates

def llm_generate_description(element) -> str:
    """LLM(gpt-4o-mini)에게 element의 raw metadata를 주고 자연어 description 생성 요청.
    35-way 분류가 *아님*. 자유 자연어 의미 추출.
    예: "Search box that opens a filter dropdown when clicked" """
    prompt = f"Element: tag={element.tag}, role={element.role}, "
             f"text={element.text}, aria_label={element.aria_label}, "
             f"class={element.class_names}. Generate a concise description."
    return llm_call(prompt)
```

★ **`infer_widget_type()` 함수 *없음*** (§4.1.5 폐기). type 분류는 본 연구가 하지 않는다 — DOM의 tag/role/class에 이미 있는 정보다.

**에이전트가 클릭한 위젯의 결과 관찰 → InteractionEdge 자동 생성**:
```
def update_kg_from_action(clicked_widget, pre_obs, post_obs, sitekg):
    new_visible = post_obs.elements - pre_obs.elements
    if new_visible:
        # 클릭이 다른 위젯을 활성화함 → activates 엣지
        for nw in new_visible:
            sitekg.add_interaction_edge(
                source=clicked_widget,
                target=nw,
                type="activates"
            )
```

**Confidence threshold + persistent commit**:
- task 1회 실행에서 발견된 후보는 in-memory KG에만 등록
- 같은 후보가 여러 task에서 N회 이상 관측되면 persistent KG에 commit
- (선택) 운영자 confirm 단계

이 메커니즘이 작동하면 **사람이 새 사이트를 한 번도 시딩하지 않고도** 에이전트가 task를 수행하면서 KG가 자라난다. 그러나 Phase 3은 task가 *도달한* 영역만 발견하므로 **cold-start 문제**가 남는다 — 빈 KG에서 첫 task가 작동하기 어렵다. 이를 보완하는 게 §4.4 offline bootstrapping이다.

### 4.4 LLM-driven Offline KG Bootstrapping (M0.5 신설)

**문제**: §1.4.2에서 정의한 두 문제 — (a) cold-start (빈 KG에서 첫 task 작동 어려움), (b) 수동 시딩 비용 (사이트당 ~6~10시간) — 를 해결해야 본 연구의 가치 명제 *"학습 없이, 사람 비용을 점근적으로 줄이며 새 사이트에 적응"* 이 완성된다.

**해결**: task 실행 *전*에 사이트를 자동 graph traversal로 순회하여 hierarchical SiteKG를 declarative YAML로 자동 생성. 사람은 검증/정제만 (또는 confidence 기반 자동 commit).

**Phase 3 dynamic construction과의 차이**:
- Phase 3 = task 실행 *중*, task가 도달한 영역만 발견 (도달성 묶임)
- §4.4 offline bootstrapping = task 실행 *전*, 사이트를 체계적으로 커버 (depth/coverage 한계 내)

두 메커니즘은 **상호 보완적**이다 — offline bootstrapping이 *cold-start*를 해결하고 *baseline KG*를 만들며, Phase 3가 *운영 중 점진 증식*한다.

#### 4.4.1 Graph traversal 알고리즘

```
def bootstrap_sitekg(start_url, depth_limit=3, max_widgets_per_page=15):
    sitekg = SiteKG.empty()
    visited_pages = set()
    queue = [(start_url, depth=0)]

    while queue and within_budget():
        url, depth = queue.popleft()
        if url in visited_pages or depth > depth_limit:
            continue
        visited_pages.add(url)

        # 1. 페이지 진입 + page_observation 수집
        page_obs = open_page_with_playwright(url)

        # 2. 이미 알려진 PageNode인지 확인 (§4.1.2 deterministic matching). UNRESOLVED면 새 노드 생성
        matched = match_page_node(url, page_obs.dom, sitekg)
        if matched == "UNRESOLVED":
            page_node = create_new_page_node(url, page_obs, sitekg)  # url_pattern은 derive_url_pattern으로 추론
        else:
            page_node = matched

        # 3. DOM에서 인터랙션 요소 후보 추출 (§4.4.2)
        candidates = extract_widget_candidates(page_obs)

        # 4. LLM zero-shot 분류 (§4.4.3)
        described = llm_generate_descriptions(candidates)  # ★ 분류 아님 — description + 자유 string 태그 생성 (§4.4.3)

        # 5. confidence threshold 통과한 widget만 후보로 등록
        for w in classified:
            if w.confidence >= HIGH_CONF_THRESHOLD:
                page_node.add_widget(w, status='auto_committed')
            elif w.confidence >= MID_CONF_THRESHOLD:
                page_node.add_widget(w, status='needs_review')
            # low confidence는 폐기

        # 6. interaction 시뮬레이션 (§4.4.4) — top-K widget 직접 click/hover
        for w in top_k(page_node.widgets, k=max_widgets_per_page):
            pre_obs = page_observation(page)
            try_click_or_hover(w)
            post_obs = page_observation(page)

            # 6a. side_effects 관찰 → InteractionEdge
            new_visible = post_obs.elements - pre_obs.elements
            for nv in new_visible:
                interaction_edge = InteractionEdge(source=w, target=nv, type='activates')
                page_node.add_interaction_edge(interaction_edge)

            # 6b. 페이지 전이가 일어났으면 NavigationEdge + 새 페이지 enqueue
            if post_obs.url != pre_obs.url:
                # ★ §4.1.2 deterministic matching → UNRESOLVED면 새 노드
                matched = match_page_node(post_obs.url, post_obs.dom, sitekg)
                target_node = matched if matched != "UNRESOLVED" else create_new_page_node(post_obs.url, post_obs, sitekg)
                nav_edge = NavigationEdge(source=page_node, target=target_node, trigger=w)
                sitekg.add_navigation_edge(nav_edge)
                queue.append((post_obs.url, depth + 1))
                navigate_back(page)  # 원래 페이지로 복귀

    return sitekg.dump_yaml()
```

**Termination conditions**: depth_limit / page coverage ceiling / LLM API budget ceiling / wall-clock timeout.

#### 4.4.2 DOM → WidgetNode 후보 추출 규칙

LLM 호출을 줄이기 위해 LLM 분류 *전*에 휴리스틱 필터로 후보를 줄인다:

1. **ARIA role 우선**: `role=button`, `role=link`, `role=searchbox`, `role=tablist`, `role=combobox`, `role=switch`, `role=menu` 등 universal taxonomy 매핑되는 role 모두
2. **HTML tag fallback**: `<button>`, `<input>`, `<select>`, `<a>`, `<textarea>`, `<form>` 등
3. **Visible 필터**: 화면에 visible (display: none, visibility: hidden 제외)
4. **Disabled 제외**: disabled 상태 요소 제외
5. **중복 제거**: 같은 selector·같은 visible text 가지는 요소는 하나로 묶음
6. **Container 제거**: 다른 widget을 *포함*하는 container는 별도 처리 (form, panel, modal은 보존하되 self-contained)

이 단계 후 페이지당 후보가 보통 50~150개 → LLM 분류 단계에서 task-relevance ranking + universal type 부여로 task-relevant 5~15개 widget으로 압축.

#### 4.4.3 LLM description generator (★ §4.1.5 폐기 후 재정의)

**역할**: §4.1.5 (Universal WidgetType taxonomy)가 폐기되면서, M0.5의 LLM은 *분류기*가 아니라 ***description generator***로 재정의되었다. 35-way 분류가 아니라 **자유 자연어 의미 추출 + 자유 string 태그 생성**이 핵심 task.

**선택된 LLM**: gpt-4o-mini (M0.5 default).
- 이유: 비용 최소, 속도 빠름. *분류*가 아니라 *description 생성*이라 분류 정확도 측정 부담이 적음. 정확도가 부족하면 gpt-4o로 격상.

**LLM 호출 형식** (구조화 출력):
```
System: 너는 web UI element를 보고 자연어 description과 task relevance tags를
        생성하는 도구다. element의 raw metadata (tag/role/text/aria/class)를 받아
        다음을 출력하라:
        - description: 사람이 읽을 수 있는 자연어 의미 1~2문장
        - task_relevance_tags: 자유 string 태그 (filter/sort/search/submit 등)
        - confidence: 0~1
        ★ widget type을 *분류*하지 말 것. type/category는 DOM의 tag/role/class에
          이미 있으니 KG에 박을 가치가 없다 (§4.1.6 minimum viable 원칙).

Element:
  tag: <button>
  role: button
  text: "Sort by"
  aria-label: "Sort options"
  parent_context: "Issues page header"

Output (JSON):
{
  "description": "정렬 기준 드롭다운 — Created date / Updated date / Priority 등을 선택",
  "task_relevance_tags": ["sort", "ordering"],
  "confidence": 0.92
}
```

**Batching**: 페이지의 후보들을 한 번에 LLM에 보내 JSON 배열로 받는다 (호출 횟수 ↓). gpt-4o-mini context는 충분.

**Confidence**:
- LLM이 self-report한 0~1 score를 1차 근거로
- 보조 휴리스틱: ARIA role/aria-label이 명확하면 +0.1, raw metadata 부족하면 -0.2, visible text가 명확하면 +0.05

**중요한 차이 (이전 분류기 대비)**:
- 이전: 35개 type 중 *정확한 하나*를 선택해야 함 → 분류 오류 가능성, hallucination, "어느 type에도 안 맞음" 케이스
- 이후: *자유 자연어 description* 생성 → LLM의 본래 강점 (생성)에 부합. 분류의 모호성 제거. cross-site 매칭은 *runtime에 description embedding similarity*로 LLM이 자체 처리.

#### 4.4.4 Interaction simulation + side_effect 관측

§4.4.1의 step 6에서 *분류된 widget을 직접 click/hover*하여:

1. **Click 실행 전 page observation snapshot** (DOM 요소 set, URL)
2. **Click 실행** (Playwright로 실제 클릭)
3. **N초 wait** (AJAX/animation 완료 대기, 보통 0.5~2초)
4. **Click 실행 후 page observation snapshot**
5. **차분 계산**:
   - URL 변함 → page 전이 → NavigationEdge 생성
   - 새 element visible → side_effect → InteractionEdge `activates`
   - 기존 element disabled/hidden → InteractionEdge `toggles`
6. **Click 영향 되돌리기**:
   - 페이지 전이는 navigate back
   - 모달/드롭다운 활성화는 ESC 또는 outside click
   - 비가역 액션 (form submit 등)은 *시뮬레이션하지 않음* (read-only mode 유지)

**Read-only safeguard**: bootstrapping은 *읽기 전용* 인터랙션만 수행. submit / delete / create 같은 mutate widget은 type 분류만 하고 click 시뮬레이션은 건너뜀 (`task_relevance_tags`에 `mutate` 포함되면 skip).

#### 4.4.5 Confidence threshold + commit 정책

**사용자 결정에 따라 confidence별 분류 (3-tier)**:

| Confidence | 처리 |
|---|---|
| **High** (≥ 0.85) | `runtime/sitekg/seeds/{site_id}.auto.yaml`에 *자동 commit*. status: `auto_committed` |
| **Mid** (0.5 ~ 0.85) | `auto.yaml`에 등록하되 status: `needs_review`. 사람 검증 단계에서 확인 |
| **Low** (< 0.5) | 폐기 (commit 안 함). 로그에는 남김 |

**검증 단계**:
- M0.5의 GitLab 자동 시드 결과를 사람이 *sample 검증* (예: 무작위 20% widget을 사람 시드와 대조)
- High confidence 항목의 false positive rate 측정 → 측정 결과로 threshold 재조정
- 검증 결과는 §5.4 ablation 8에서 자동 시드 only 조건 D 측정의 신뢰 근거

**Failure mode** (정직하게 명시):
- LLM hallucination: 존재하지 않는 selector 생성 → Playwright 검증 단계에서 매칭 0개로 감지 → 폐기
- 잘못된 type 분류: confidence high인데 type 잘못 → ablation 측정에서 task 성공률 떨어짐으로 감지 → threshold 상향
- visibility_condition 누락: dynamic으로만 보이는 widget을 statically 분류 → §4.4.4 interaction simulation에서 차분으로 발견 → 시드에 condition 추가

### 4.5 통합 아키텍처

```
   ┌────────────────────────────────────────────────────────┐
   │   §4.4 Offline KG Bootstrapping (M0.5, task 실행 전)    │
   │   Playwright crawler + LLM zero-shot widget classify   │
   │   + interaction simulator → seeds/{site}.auto.yaml     │
   └─────────────────────────┬──────────────────────────────┘
                             │ (자동 시드 또는 사람 시드)
                             ▼
                    ┌──────────────────────────────────┐
                    │   Hierarchical SiteKG             │
                    │                                   │
                    │   G_page = (V_page, E_page)       │
                    │     PageNodes ← NavigationEdges   │
                    │                                   │
                    │   {G_widget(p) for each p}        │
                    │     WidgetNodes ← InteractionEdges│
                    │                                   │
                    │   ★ Minimum viable KG (§4.1.6)    │
                    │   KG가 박는 4가지 정보:            │
                    │   1. connectivity (Nav/InteractionEdge)│
                    │   2. conditional state (visibility)│
                    │   3. causal effects (side_effects) │
                    │   4. stable references (locator)   │
                    │                                   │
                    │   ★ KG에 *없는* 것:                │
                    │   - widget_type / category         │
                    │   - element raw metadata           │
                    │   - task→widget mapping            │
                    │   (모두 DOM 또는 LLM의 영역)        │
                    └──────────┬───────────────────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ▼                  ▼                  ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │  Phase 1     │   │   Phase 2    │   │   Phase 3    │
   │  Two-Level   │   │   Two-Level  │   │   Two-Level  │
   │  Selective   │   │   Traversal  │   │   Dynamic    │
   │  Retrieval   │   │   (page+seq) │   │   Construction│
   │              │   │              │   │              │
   │  page subgr. │   │  BFS path    │   │  page node + │
   │  + widget    │   │  + widget    │   │  widget node │
   │  top-K       │   │  sequence    │   │  auto-discov.│
   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
          │                  │                  │
          ▼                  ▼                  ▼
   ┌─────────────────────────────────────────────────────┐
   │           LLM Web Agent (v3 + KG)                    │
   │  Sub-goal loop                                       │
   │   ├─ planning (page path + widget sequence)         │
   │   ├─ step loop                                       │
   │   │   ├─ observation                                 │
   │   │   ├─ retrieve widget top-K (Phase 1)            │
   │   │   ├─ build prompt with selected widgets        │
   │   │   ├─ LLM tool call (click target widget)       │
   │   │   ├─ execute action                              │
   │   │   ├─ observe post-state                         │
   │   │   └─ update KG: discover new widgets (Phase 3) │
   │   └─ checkpoint + retry + replan                    │
   └─────────────────────────────────────────────────────┘
```

**두 시딩 경로**:
- **자동**: §4.4 offline bootstrapping → `seeds/{site}.auto.yaml`
- **수동**: 사람이 직접 작성 → `seeds/{site}.yaml`
- 본 연구는 두 경로를 모두 지원하고, ablation 8에서 두 시드의 task 성공률 차이를 직접 비교한다 (H4 검증).
```

---

## 5. 실험 설계

### 5.1 독립 변수 — 6 조건

| 조건 | Page graph | Widget graph | Selective retrieval | Path finding | Dynamic |
|---|---|---|---|---|---|
| **A. Baseline v3** | — | — | — | — | — |
| **B. Page-Full** | full inject | — | — | — | — |
| **C. Page-Selective** | selective | — | ✓ (page) | — | — |
| **D. Page+Widget Selective** ★ | selective | selective | ✓ (page + widget) | — | — |
| **E. + Path** | selective | selective | ✓ | ✓ (page + widget seq) | — |
| **F. + Dynamic** | selective | selective | ✓ | ✓ | ✓ (page + widget) |

**조건 A의 정확한 정의** — "v3 코어"는 lab 005 보고서 §"현재 아키텍처 요약"이 backing하는 코드(Tool Use API + sub-goal/checkpoint/retry/replan/verification + 클릭 매칭 6단계 + DOM 안정화 + NAVIGATE final URL check + graduated retry) **+ 2026-04-12 memo 강화**(action tool의 optional `memo` field + `_verify_done`의 `task_notes` 검토)를 포함한다. memo 강화는 lab 005 §"Skill Library 시도 및 철회"가 예약한 cognitive aid 영역의 가벼운 구현이며 system prompt는 task-agnostic 유지(특정 task 형태에 fit한 hint 없음). 6 조건 모두 *동일한* v3 코어를 공유하고 KG 컴포넌트만 다르다.

**핵심 비교**:
- **B vs C**: page-level selective retrieval의 효과 (v1 가설)
- **C vs D**: ★ widget-level retrieval의 효과 (H1' 핵심)
- **D vs E**: widget interaction sequencing의 효과 (H2)
- **E vs F**: dynamic construction의 효과 (H3)

H1' 검증: `(D - C) > (C - B)` 를 보이면 H1' 채택.

### 5.2 종속 변수

**주요**:
- task 평균 성공률 (3회 반복 평균)

**보조**:
- 평균 step 수 / LLM 호출 수 / 토큰 수 / wall-clock time
- sub-goal 단위 성공률
- **task family별 성공률 — *사후 분석 카테고리*** (RETRIEVE / NAVIGATE / MUTATE / FILTER / SORT). ★ 중요: task family는 *알고리즘 input*이 아니다 (§4.1.6 원칙). 사람이 측정 후 14 task를 의미적으로 묶어 *결과를 보고하는 라벨*로만 사용 — 예: "본 연구는 filter task에 강하고 mutate task에 약함". 알고리즘은 task family 분류를 *알지 못하고*, LLM도 task intent의 자연어만 받음. task family는 *결과 해석*에만 등장.
- **Widget recall**: 정답 위젯이 LLM에 노출됐는가
- **Widget precision**: 노출된 위젯 중 실제 사용된 비율
- **사람 시딩 비용 (wall-clock)**: 새 사이트를 사람이 YAML로 시딩하는 데 걸린 시간. 측정 절차: 저자(또는 시뮬레이션 사용자)가 selector 검증·side_effect 관찰을 포함해 직접 작성한 시간을 reference로 보고. 사전 목표 숫자 없음, 측정 결과 자체가 결과. 비교는 *절대 시간*이 아니라 학습 기반 접근(Mind2Web/AutoWebGLM/OmniParser)의 데이터 수집 + fine-tuning 시간과의 *차수 비교*
- **자동 시딩 비용 (M0.5 §4.4)**: bootstrapping pipeline의 wall-clock + LLM API 호출 횟수 + token 비용. 사이트당 100~200 LLM 호출 추정 (gpt-4o-mini default).
- **자동 시드 widget recall**: 사람 시드의 widget을 ground truth로 두고 자동 시드가 그 중 몇 %를 포함하는가
- **자동 시드 widget precision**: 자동 시드의 widget 중 사람 시드에도 있거나 사람이 사후 검증으로 valid 판정한 비율
- **자동 시드 false positive rate**: 존재하지 않는 selector / 잘못된 type 분류 / 환각 widget의 비율
- **자동 시드 task 성공률** (H4 primary metric): 자동 시드만 사용한 조건 D 측정. 사람 시드 사용한 조건 D와 paired t-test 비교

**Online-Mind2Web 측정 항목 (M6 신설, H5 검증용)**:
- **Online-Mind2Web sub-set task 성공률**: 본 연구가 측정한 sub-set (30~50 task)의 평균 성공률
- **WebJudge 자동 평가 점수**: WebJudge(o4-mini)로 본 연구 결과 평가. 사람 evaluation과 86% agreement.
- **Hugging Face leaderboard rank**: 본 연구 결과를 공식 leaderboard에 등록 시 순위 + 외부 baseline과 직접 비교
- **Cross-benchmark 효과 일관성** (H5 primary): WebArena-Verified의 D vs C 효과 방향성과 Online-Mind2Web의 동일 비교 방향성을 비교. *방향성 일관*하면 H5 채택.
- **Cross-benchmark 효과 크기 보존 비율** (H5 secondary, sub-claim): WebArena의 effect size 대비 Online-Mind2Web의 effect size 비율. 보존 비율 60%+를 강한 형태의 sub-claim으로 보고. 강한 형태 미달 시 본 가설에는 영향 없음 (방향성만 보면 됨).

### 5.3 평가 환경

- **LLM**: OpenAI gpt-4o (`LLM_PROVIDER=openai`). 보조: Claude Opus 4.6. M0.5 bootstrapping은 gpt-4o-mini.
- **에이전트 코어**: 본 프로젝트 v3 재구현 (Tool Use API + sub-goal/checkpoint/retry/replan + 새 KG 통합)
- **반복**: 각 조건 × 각 task = 3회. 비결정성 흡수.
- **통계 검증**: paired t-test, p < 0.05

#### 두 벤치마크의 역할 분리 (★ 핵심 설계)

본 연구는 두 벤치마크를 *역할 분리*해 사용한다:

| | **WebArena-Verified GitLab 14 task** | **Online-Mind2Web sub-set** (M6 신설) |
|---|---|---|
| 역할 | **내부 ablation 검증 환경** | **cross-benchmark 일반화 검증 환경** |
| 검증 가설 | H1' / H2 / H3 / H4 + 9 ablation | **H5 — cross-benchmark 일관성** |
| 측정 task 수 | 14 task × 3회 (= 42 측정점) | sub-set 30~50 task × 3회 (M6.2에서 결정) |
| 비교 baseline | 본 프로젝트 v3 (조건 A) — 내부 | **Hugging Face leaderboard 외부 baseline 풍부** (Browser-use, GPT-5.4, Operator, Claude 3.7, SeeAct, 대다수 후속 agent) |
| 측정 metric | task 성공률 + widget recall/precision + 시딩 비용 | task 성공률 + WebJudge (사람 86% agreement) + leaderboard rank |
| Cross-site 평가 (H3) | Reddit/Shopping_admin 일부 task로 검증 | (해당 없음 — Online-Mind2Web 자체가 136 사이트) |
| 용도 | 효과 입증 (effect size + paired t-test) | 일반화 입증 (방향성 일관성) |

**왜 분리하는가**:
1. WebArena-Verified는 *작고 reproducibility 검증된 환경*이라 정밀 ablation에 적합하지만 외부 baseline pool이 빈약 (벤치마크가 새로움)
2. Online-Mind2Web은 *외부 baseline이 풍부하고 어려운 환경*이지만 내부 ablation을 모두 측정하기엔 비용 큼
3. 두 환경의 *역할 분리*가 본 연구의 외부 baseline 부재 약점(이전 plan의 A1)을 *완전히* 해결 — 외부 비교는 Online-Mind2Web에 위임

**Online-Mind2Web의 외부 baseline pool**:

| Tier | Baseline | 본 연구 비교 위치 |
|---|---|---|
| 능가 불가능 | Browser-use 97%, GPT-5.4 92.8% | multimodal flagship — 비교 대상 아님 |
| 실용적 천장 | Operator 61%, Claude Computer Use 3.7 | 본 연구의 *학습 0 + DOM only* upper bound reference |
| **★ 직접 비교 대상** | SeeAct (early 2024) | 비슷한 *학습 없는 DOM-based*. 본 연구가 능가 또는 동급이면 의미 있는 contribution |
| **★ 현실적 비교군** | 대다수 후속 agent 28~30% (사람), 34~40% (WebJudge) | 본 연구가 30~40%대면 *학습 0의 강력한 evidence* |
| Floor | 단순 search 22% | 본 연구가 이보다 낮으면 의미 없음 |

**본 연구의 정직한 천장 목표** (Online-Mind2Web에서):
- SeeAct (~2024 DOM 기반) 수준 도달 또는 동급
- 대다수 후속 agent (28~30%대) 명확한 능가
- Operator (61%) / multimodal SOTA 능가는 1차 목표 *아님* — *학습/visual/시딩 비용 trade-off* 비교

### 5.4 Ablation 실험

| Ablation | 조작 | 검증 대상 |
|---|---|---|
| 1. Phase 1 widget만 | C는 그대로, D에서 page selective 끄기 | widget retrieval 단독 효과 |
| ~~2. TaskWidgetMap 효과~~ | **폐기 (2026-04-11)**. TaskWidgetMap이 §4.1.6 원칙에 따라 본 연구에서 *완전 제거*됨. 본 연구는 task→widget 명시 매핑을 KG에 박지 않으므로 측정할 수 없음. *task semantic은 LLM 영역*. | — |
| ~~3. Universal taxonomy 효과~~ | **폐기 (2026-04-11)** — §4.1.5 Universal WidgetType taxonomy가 §4.1.6 minimum viable 원칙으로 *완전 폐기*. taxonomy 자체가 없으므로 측정 대상 없음 | — |
| 4. **Unobserved meta-count 효과 (D vs D')** | D' = D + prompt에 미관측 widget 카테고리·개수 명시 | §1.4.1·§4.2.1 design choice 2의 효과. 본 연구의 *KG 부분 그래프 노출* framing이 단순 element ranking과 operational하게 차이를 만드는지 직접 측정 |
| 5. Label-rich graph context 효과 | D에서 InteractionEdge 정보 빼기 (위젯 라벨만 제공) | §4.2.1 design choice 1의 효과. 그래프 구조 정보가 평면 라벨 대비 추가 기여하는지 |
| 6. Phase 3 only (no seed) | 빈 KG에서 Phase 3만 작동 | 자동 구축(task-driven)의 zero-shot 성능 |
| 7. Cross-site dynamic | GitLab에서 학습된 widget 추론 규칙을 Reddit에 zero-shot 적용 | universal taxonomy의 cross-site 일반화 |
| **8. Automated vs Manual seeding (★ H4 핵심)** | 동일 task 14개에 대해 조건 D를 두 번 측정: `D_manual` (사람 시드) vs `D_auto` (§4.4 offline bootstrapping 자동 시드 only). paired t-test | **H4 검증 — Task 성공률 우선**. 추가로 widget recall/precision으로 자동 시드 품질 진단. `D_auto`가 `D_manual`의 일정 천장 이내(예: 절대 차이 ≤ 15%p)면 H4 채택 → 사람 비용을 사실상 0으로 줄여도 본 연구 알고리즘 작동 |
| 9. Bootstrapping + Phase 3 stacking | 자동 시드 + 운영 중 Phase 3 dynamic construction 결합 | 두 메커니즘의 시너지 측정 (cold-start 해결 + 운영 중 증식) |
| **10. ★ Cross-benchmark 일관성 (H5 핵심, M6 신설)** | WebArena-Verified의 H1' (D > C) 결과와 동일 비교를 Online-Mind2Web sub-set (30~50 task)에서 재측정. 채택 기준 = *방향성 일관성만* (effect size 동등 요구 안 함). 추가로 Online-Mind2Web에서 외부 baseline (Browser-use, GPT-5.4, Operator, Claude 3.7, SeeAct, 대다수 후속 agent)과 직접 비교. | **H5 검증** + 외부 baseline 비교 + cross-benchmark 일반화 입증. 본 연구가 WebArena GitLab에 *과적합되지 않음* 입증. 기각 시 contribution을 *해당 환경 한정*으로 한정하고 솔직 보고 |
| ~~11. Core taxonomy only vs Core+Extended~~ | **폐기 (2026-04-11)** — §4.1.5 Universal WidgetType taxonomy 자체가 §4.1.6 minimum viable 원칙으로 폐기됨. Core/Extended 분리 측정이 불가능 (taxonomy 자체가 없음) | — |
| **11 (재정의). ★ Description-only retrieval 효과 측정** | WidgetNode가 *description + locator + visibility + side_effects*만 가진 minimum spec과 *description + raw DOM metadata 추가* 두 가지를 비교 측정. LLM의 cross-site 의미 매칭 정확도 평가 | **A3/B1 약점이 §4.1.6 원칙으로 자동 해결된 후의 경험적 검증** — minimum viable KG가 *진짜* cross-site 일반화에 충분한지 측정. 부족하면 description의 *어떤 부분*을 보강해야 하는지 진단 |

### 5.5 실패 분석

task별 실패 원인 분류:
- 사이트 지식 부재 (KG에 widget 또는 InteractionEdge 누락 → 시딩/bootstrapping으로 해결 가능)
- LLM 판단 오류 (KG 위에서 잘못된 reasoning, KG 자체는 충분)
- Widget retrieval 누락 (Phase 1 ranking 실패 — 정답 widget을 top-K에 넣지 못함)
- Dynamic construction 잘못된 추론 (Phase 3 noise, 자동 분류 오류)
- 벤치마크 데이터 문제

---

## 6. 구현 계획

### 6.1 모듈 구조 (`runtime/sitekg/` 재설계)

```
site_adaptive_webagent/runtime/
├── sitekg/                          # 신규 패키지 (v1의 `sitekg`도 폐기 후 재구축)
│   ├── __init__.py
│   ├── types.py                     # 신규 — PageNode, WidgetNode, NavigationEdge,
│   │                                 #         InteractionEdge, SiteKG, SiteKGContext
│   # ★ widget_types.py — *폐기 (2026-04-11, §4.1.5 폐기, §4.1.6 minimum viable 원칙)*
│   ├── store.py                     # 신규 — SiteKGStore + 새 SQL 스키마
│   ├── seed_loader.py               # 신규 — YAML/JSON → SiteKG 객체
│   ├── page_matcher.py              # ★ 신규 (M0) — match_page_node() deterministic 알고리즘 (§4.1.2)
│   ├── retrieval.py                 # 신규 — Phase 1 (page + widget retrieval)
│   ├── traversal.py                 # 신규 — Phase 2 (BFS + widget sequencing)
│   ├── dynamic.py                   # 신규 — Phase 3 (page + widget auto-discovery)
│   # ★ widget_inference.py — *폐기 (2026-04-11, §4.1.5 폐기)*. type 분류 자체가 사라짐
│   ├── bootstrapping/               # ★ 신규 (M0.5) — Offline KG bootstrapping
│   │   ├── __init__.py
│   │   ├── crawler.py               # Playwright 기반 graph traversal
│   │   ├── widget_extractor.py      # DOM → WidgetNode 후보 추출
│   │   ├── description_generator.py # ★ LLM이 element 자연어 description 생성 (gpt-4o-mini, §4.4.3) — *분류기 아님*
│   │   ├── interaction_simulator.py # widget click/hover → side_effect 관측
│   │   ├── confidence.py            # 3-tier confidence 정책 (high/mid/low)
│   │   └── pipeline.py              # end-to-end pipeline + CLI entry
│   └── seeds/
│       ├── gitlab.yaml              # 신규 — 사람 작성 declarative (M0)
│       ├── gitlab.auto.yaml         # ★ 신규 (M0.5) — 자동 생성 시드
│       ├── reddit.yaml              # 신규 — cross-site 평가용 사람 시드 (M4)
│       ├── reddit.auto.yaml         # ★ 신규 (M0.5/M4) — 자동 생성 시드
│       └── om2w/                    # ★ 신규 (M6) — Online-Mind2Web 사이트별 자동 시드
│           └── *.auto.yaml          # M6.3에서 M0.5 자동 bootstrapping으로 생성

└── benchmarks/                      # ★ 신규 패키지 (M6) — 다중 벤치마크 adapter
    ├── __init__.py
    ├── webarena_verified/           # 기존 benchmarks/webarena_verified/와 통합
    │   └── adapter.py
    └── online_mind2web/             # ★ 신규 (M6)
        ├── __init__.py
        ├── adapter.py               # task input/output 변환
        ├── evaluator.py             # WebJudge (o4-mini) 호출 + 결과 파싱
        └── leaderboard.py           # Hugging Face leaderboard 등록 + 비교 표 생성
├── executor.py                       # 수정 — step loop 재구성
├── llm.py                            # 수정 — build_tool_use_system_prompt(widget_list)
├── orchestrator.py                   # 수정 — SiteKGContext 전달
└── (폐기) types.py 내 PageType, ActionSchema, KBBundle
└── (폐기) store.py 내 KBStore
└── (폐기) seeds/gitlab.py
```

### 6.2 마일스톤 (M0~M5 재정의)

| 마일스톤 | 작업 | 산출물 |
|---|---|---|
| **M0: KG 모델 + seed schema** | runtime/sitekg/types.py (★ widget_type 필드 없음), seed_loader.py, store.py 신규. GitLab 사람 시드(`gitlab.yaml`) 작성. v1 KB 코드 폐기. v3 baseline 재구현. 기존 테스트 갱신. (★ widget_types.py / widget_inference.py *폐기 — §4.1.5 minimum viable 원칙*) | 새 모델 단위 테스트 + GitLab 사람 시드 + v3 baseline 동작 |
| **★ M0.5: Offline KG Bootstrapping (신규)** | `runtime/sitekg/bootstrapping/` 패키지 — crawler / widget_extractor / llm_classifier(gpt-4o-mini default) / interaction_simulator / confidence(3-tier) / pipeline + CLI. GitLab 자동 시드 `gitlab.auto.yaml` 생성. 자동 시드 vs 사람 시드 widget recall/precision 직접 비교. 사람 sample 검증으로 false positive rate 측정. | bootstrapping 도구 + GitLab 자동 시드 + 자동/사람 시드 품질 비교 표 + LLM API 비용·wall-clock reference |
| **M1: Phase 1 (Two-Level Selective Retrieval)** | retrieval.py + llm.py / executor.py 수정. 조건 A vs B vs C vs D 측정. | H1' 검증 결과 |
| **M2: Phase 2 (Two-Level Traversal)** | traversal.py + planning 통합. 조건 D vs E. | H2 검증 결과 |
| **M3: Phase 3 (Dynamic Construction)** | dynamic.py + store write API. 조건 E vs F + 자동 구축 시뮬레이션. (★ widget_inference.py 폐기 — §4.1.5 폐기) | H3 검증 결과 |
| **M4: Cross-site (Reddit)** | reddit.yaml 시딩 + Reddit task에서 조건 F 측정 + 빈 KG zero-shot 측정 | cross-site 결과 + 시딩 비용 측정 |
| **M5: Ablation + 통계 + lab report 007** | 9개 ablation 분석, paired t-test, lab report + 논문 초안 | 최종 결과 문서 |
| **★ M6: Cross-benchmark generalization (Online-Mind2Web 통합, H5 검증)** | M6.1 `runtime/benchmarks/online_mind2web/` adapter (3~5일) → M6.2 sub-set 30~50 task 선정 (0.5일) → M6.3 사이트별 자동 시드 (M0.5 도구 재사용, 사이트당 1~2시간) → M6.4 측정 (조건 D + 조건 F × 3회, 1~2주) → M6.5 Hugging Face leaderboard 등록 + 외부 baseline 비교 표 (2~3일) → M6.6 H5 cross-benchmark 일관성 분석 (방향성 우선, 효과 크기 보존은 sub-claim, 2~3일) | M6 lab report + H5 검증 결과 + 외부 baseline 비교 표 + leaderboard rank. **총 추정 2~3주** |

총 timeline: 산정 보류 (M0의 v3 재구현 범위가 결정되면 산정 가능).

### 6.3 코드 변경 사양 — 폐기 / 신규 / 수정

**폐기**:
- `runtime/types.py`의 `PageType`, `ActionSchema`, `KBBundle`, `kb_used`, `kb_confidence` 등
- `runtime/store.py`의 `KBStore`
- `runtime/seeds/gitlab.py` (Python 하드코딩 시드)
- `runtime/enums.py`의 `KBConfidence`, `RouteKind.PARTIAL_KB`

**신규** (`runtime/sitekg/` 패키지):

| 파일 | 내용 |
|---|---|
| `types.py` | PageNode, WidgetNode, NavigationEdge, InteractionEdge, SiteKG, SiteKGContext (★ WidgetType enum *없음* — §4.1.5 폐기, §4.1.6 minimum viable 원칙. ★ TaskWidgetMapEntry 없음) |
| ~~`widget_types.py`~~ | **폐기 (2026-04-11)** — §4.1.5 Universal WidgetType taxonomy 폐기로 enum 자체가 사라짐 |
| `store.py` | SiteKGStore + 새 SQL 스키마 (page_nodes, widget_nodes, navigation_edges, interaction_edges 테이블. ★ task_widget_map 테이블 없음) |
| `seed_loader.py` | YAML → SiteKG 객체. 스키마 validation. |
| `page_matcher.py` | ★ 신규 (M0) — `match_page_node()` deterministic 알고리즘 (§4.1.2). URL pattern matching (Express.js placeholder) + specificity sort + structural_signals tiebreak. ~20 단위 테스트 케이스 |
| `retrieval.py` | extract_page_subgraph, extract_relevant_widgets |
| `traversal.py` | find_navigation_path (BFS), find_widget_sequence |
| `dynamic.py` | discover_widgets_from_observation, update_kg_from_action |
| ~~`widget_inference.py`~~ | **폐기 (2026-04-11)** — §4.1.5 폐기. type 분류 자체가 사라짐. M0.5 LLM은 *description generator* (`description_generator.py`) |
| `bootstrapping/__init__.py` | ★ M0.5 신규 — Offline KG bootstrapping 패키지 |
| `bootstrapping/crawler.py` | ★ Playwright 기반 graph traversal (visited 추적, depth limit, budget ceiling) |
| `bootstrapping/widget_extractor.py` | ★ DOM에서 인터랙션 요소 후보 추출 (ARIA role + tag fallback + visible/disabled 필터) |
| `bootstrapping/description_generator.py` | ★ LLM (gpt-4o-mini) element → 자연어 description + 자유 string 태그 생성. *분류기 아님* (§4.1.5 폐기, §4.1.6 minimum viable 원칙). structured JSON 출력. batching 지원 |
| `bootstrapping/interaction_simulator.py` | ★ widget click/hover → page observation 차분 → InteractionEdge / NavigationEdge 자동 생성. read-only safeguard |
| `bootstrapping/confidence.py` | ★ 3-tier confidence 정책 (high → 자동 commit, mid → 사람 confirm, low → 폐기) |
| `bootstrapping/pipeline.py` | ★ end-to-end pipeline + CLI entry (`bootstrap-sitekg`) |
| `seeds/gitlab.yaml` | GitLab의 9 PageNode + 각 PageNode의 widgets + InteractionEdges + NavigationEdges (M0, 사람 작성. ★ task_widgets 섹션 없음) |
| `seeds/gitlab.auto.yaml` | ★ GitLab 자동 생성 시드 (M0.5) |
| `seeds/reddit.yaml` | Reddit의 핵심 PageNode + widgets (M4, 사람 작성) |
| `seeds/reddit.auto.yaml` | ★ Reddit 자동 생성 시드 (M4) |
| `seeds/om2w/*.auto.yaml` | ★ M6 신규 — Online-Mind2Web sub-set의 사이트별 자동 시드 |
| `benchmarks/__init__.py` | ★ M6 신규 — 다중 벤치마크 adapter 패키지 |
| `benchmarks/online_mind2web/adapter.py` | ★ M6 신규 — Online-Mind2Web task input/output 변환, agent 통합 |
| `benchmarks/online_mind2web/evaluator.py` | ★ M6 신규 — WebJudge (o4-mini) 호출 + 결과 파싱 |
| `benchmarks/online_mind2web/leaderboard.py` | ★ M6 신규 — Hugging Face leaderboard 등록 + 비교 표 자동 생성 |

**수정**:

| 파일 | 변경 |
|---|---|
| `runtime/llm.py` | `build_tool_use_system_prompt(page_subgraph, widget_list)` 신호 변경 |
| `runtime/executor.py` | step loop에 retrieval/dynamic 통합. 매 step 마다 widget top-K 선별 후 LLM 호출 |
| `runtime/orchestrator.py` | KBBundle → SiteKGContext 전달로 변경 |
| `agent/core.py` | KBStore → SiteKGStore 진입점 갱신 |
| `tests/` | 새 모듈 단위 테스트 + 통합 테스트 + 기존 테스트 마이그레이션 |
| `docs/architecture/v4_hierarchical_sitekg.md` | 신규 아키텍처 문서 |
| `docs/lab_reports/007_hierarchical_sitekg.md` | 신규 실험 결과 |

---

## 7. 예상 기여

### 7.1 학술적 기여

본 연구는 다음 5가지 *측정 가능한* 기여를 목표로 한다. 각 기여는 §5의 실험 설계로 직접 검증되거나 정량화된다.

1. **★ Minimum viable declarative seed — KG가 박을 가치가 있는 정보의 design principle** (§4.1.6) — 본 연구는 *KG가 박을 정보*에 대한 새 design principle을 제시한다. KG는 DOM이 *원리적으로* 표현 못 하는 4가지 정보만 박는다: (a) **connectivity** (PageNode 간 NavigationEdge + WidgetNode 간 InteractionEdge), (b) **conditional state** (visibility_condition), (c) **causal effects** (side_effects, trigger_widget_key), (d) **stable references** (locator strategy/value). 기존 KG 기반 web agent 연구가 *type / category / element ranking / task→widget mapping*을 KG에 박았던 것과 달리, 본 연구는 *DOM에 이미 있는 정보는 DOM에 위임*하고 *task semantic은 LLM에 위임*한다 — KG가 박는 것은 *DOM도 LLM도 모르는* 4가지뿐. 이 *minimum spec*이 GitLab + Online-Mind2Web 두 환경에서 작동함을 입증한다 (§5.4 ablation 7, 11). **이전 v2의 Universal WidgetType taxonomy(~35개)는 본 원칙에 의해 폐기됨** (§4.1.5) — type/category는 DOM의 tag/role/class에 이미 있고, KG에 복사해 박을 가치가 없다.
2. **Two-Level KG retrieval 알고리즘** (§4.2.1) — page-level과 widget-level을 동시에 selective retrieval하는 알고리즘 + label-rich graph context와 (선택적) unobserved meta-count의 두 design choice. 검증: 조건 D > 조건 C (H1') + ablation 4, 5로 각 design choice의 단독 효과 측정.
3. **Inference-time widget auto-discovery** (§4.2.3) — universal taxonomy를 활용해 학습 없이 task 실행 중 widget을 자동 발견·등록하는 메커니즘. Agent-E의 change observation을 직접 영감으로 하되 (a) universal taxonomy 분류, (b) persistent KG commit으로 차별화. 검증: 조건 F + ablation 6 (빈 KG zero-shot 시나리오).
4. **Intra-page selective retrieval의 추가 효과 정량화** (H1') — page-level KG augmentation 위에 widget-level retrieval을 더했을 때의 추가 성공률 향상을 paired t-test로 정량화. lab 006의 부정적 결과를 *page-level만으로는 충분하지 않다*는 측정 결과로 보완.
5. **Reproducible benchmark + 시딩 비용 측정** — 6개 조건 × 14 task × 3회 반복 + cross-site 평가 + 새 사이트 시딩 시간 직접 측정 (사람 + 자동 두 시나리오). 학습 없는 site adaptation의 *비용 측정*은 기존 학습 기반 SOTA(Agent-E, AutoWebGLM, OmniParser)와 본 연구를 비교할 때 핵심 차원이 된다.
6. **★ LLM-driven Offline KG Bootstrapping — 본 연구 가치 명제의 핵심 메커니즘** (§4.4, M0.5) — 학습 없이 *graph traversal + universal WidgetType taxonomy 기반 LLM zero-shot 분류 + interaction 시뮬레이션*만으로 새 사이트의 hierarchical KG를 자동 생성하는 파이프라인. **이는 add-on이 아니라 본 연구의 전체 가치 명제가 의존하는 핵심 메커니즘**이다 — M0.5가 작동하면 사람 시간이 ~30분~1시간 검증으로 수렴하여 "학습 기반 대비 2~3 차수 절감"이 달성되고, 작동하지 않으면 본 연구는 fallback(수동 6~10시간)으로 후퇴하여 "1~2 차수 절감"으로 약해진다 (§8 핵심 위험 참고). 동시에 cold-start 문제를 해결한다 (task 실행 전에 baseline KG 제공, Phase 3 dynamic construction이 task 중 증식). 검증: H4 (조건 D를 자동 시드 vs 사람 시드로 두 번 측정해 paired t-test), 보조로 widget recall/precision/false positive rate. Go-Browse(학습 데이터 수집 → SFT 필요)·OmniParser(67k 라벨링 학습 필요)와 정직한 4축 비교 (§7.3).
7. **★ Cross-benchmark generalization (M6 신설)** — 본 연구의 hierarchical KG 효과가 WebArena-Verified(내부 ablation 환경)와 Online-Mind2Web(cross-benchmark 환경) 두 환경에서 *방향성 일관*하게 작동함을 입증. 단일 벤치마크 overfit이 아님. **본 연구는 *"An Illusion of Progress?"* (Xue et al., COLM 2025)의 진단 — 기존 web agent 보고 성능이 표면적 측정에 의존했다 — 을 공유하고, 그 진단을 *intra-page widget salience*로 더 구체화한다.** 어려운 평가 환경(Online-Mind2Web)에서 *학습 0 + visual 0 + 작은 declarative 시드*만으로 SeeAct(early 2024 DOM-based) 수준 천장에 도달하고 대다수 후속 agent (28~30%대)를 능가하는지 측정. 검증: H5 (방향성 일관성, ablation 10) + Hugging Face leaderboard 직접 등록 + 외부 baseline (Browser-use, GPT-5.4, Operator, Claude Computer Use 3.7, SeeAct, 단순 search) 동일 환경 비교.

**§1.4.1의 framing(KG 부분 그래프 노출 관점)에 대해**: 본 연구는 이를 *연구 동기*로 명시하지만, 그 자체를 학술적 기여로 주장하지는 않는다. operational한 차이는 §4.2.1의 두 design choice (label-rich graph context, unobserved meta-count)로 환원되며, 그 *효과의 크기*는 ablation 4, 5에서 측정된다. 이 측정 결과가 양수이면 framing이 정당화되고, 그렇지 않으면 framing은 *수사*로 남는다.

### 7.2 실용적 기여

1. **WebArena-Verified GitLab 성공률 향상** — 새 v3 baseline 측정 후 목표 65%+
2. **Declarative seed format + M0.5 자동 bootstrapping** — 학습 데이터 수집 + fine-tuning(Mind2Web/AutoWebGLM 류, 수 일~수 주)이나 vision detector 학습(OmniParser, 수십 시간 + 67k 라벨링) 대비 **2~3 차수** 절감이 가치 명제.
   - **목표 시나리오 (M0.5 작동 시)**: `bootstrap-sitekg` CLI가 자동 생성한 시드의 confidence mid 항목만 사람이 검증. **사람 작업 시간 ~30분~1시간** + LLM API 비용 (사이트당 100~200 호출, gpt-4o-mini 기준).
   - **Fallback 시나리오 (M0.5 미작동 시)**: 사람이 YAML 시드를 처음부터 작성. ~6~10시간. 여전히 학습 기반 대비 1~2 차수 작지만 본 연구 design constraint와 어긋남.
   - 정확한 시간은 M0.5 + M4에서 직접 측정.
3. **Zero-shot site adaptation 검증** — 사람 시딩 없이도 일정 성공률 도달 가능성 검증 (H3 + H4)
4. **★ 사이트 온보딩 자동화 도구** (§4.4 M0.5) — `bootstrap-sitekg` CLI. 새 사이트 URL을 입력하면 LLM-driven offline bootstrapping으로 declarative YAML 시드를 자동 생성. 사람은 confidence mid 항목만 검증. *사이트 추가 비용을 사람 시간 0~소량 + LLM API 비용*으로 환원
5. **오픈 소스 구현체** — `site-adaptive-webagent` 저장소

### 7.3 기존 연구와의 차별화

| 비교 대상 | 차이 |
|---|---|
| **★ Browser-use (Online-Mind2Web 97%)** | learning + multimodal + Auto-Research. *능가 대상 아님*. 본 연구는 *학습 0 + DOM only* trade-off로 비교 |
| **★ GPT-5.4 (Online-Mind2Web 92.8%, WebArena-Verified 67.3%)** | OpenAI multimodal flagship + 거대 학습. 본 연구는 *학습 0 + visual 0의 정직한 천장* 측정. 절대 성능 능가 아닌 trade-off 비교 |
| **★ OpenAI Operator (Online-Mind2Web 61% / 71.8%)** | multimodal + computer use. 본 연구의 *실용적 천장* reference. Operator도 학습 + multimodal이라 본 연구의 *학습 0* 차별화가 명확 |
| **★ Claude Computer Use 3.7 (Online-Mind2Web top 그룹)** | Operator와 동급. 동일하게 학습 + multimodal computer use |
| **★ SeeAct (Online-Mind2Web ~early 2024 DOM-based 천장)** | 본 연구의 *직접 비교 대상*. 비슷한 *학습 없는 DOM-based* 접근. 본 연구가 능가 또는 동급이면 *site-specific declarative KG의 의미 있는 contribution*. 차이: SeeAct는 GPT-4V 시각 보강 + ad-hoc DOM grounding, 본 연구는 hierarchical KG + universal taxonomy |
| **★ "An Illusion of Progress?" 후속 agent들 (Online-Mind2Web 28~30%)** | 학습 기반 후속 agent도 30%대에 머무름. 본 연구가 30~40%대면 *학습 0의 강력한 evidence* |
| **Agent-E** (Emergence AI 2024, WebVoyager 73.2% SOTA) | 다른 벤치마크. 본 연구 직접 비교 대상이 아님. flexible DOM distillation은 site-agnostic 일반 정책 vs 본 연구의 site-specific declarative KG. change observation은 본 연구 Phase 3의 직접 영감이지만, 본 연구는 universal taxonomy로 분류·persistent KG에 commit한다는 점에서 다름 |
| **Mind2Web / MindAct** (Deng 2023) | 학습된 DeBERTa ranker (2-stage filter+select) vs 본 연구의 KG-based retrieval (학습 없음). 사이트 추가 시 학습 데이터 수집·fine-tuning(수 일~수 주) 필요 vs 본 연구는 (목표) M0.5 자동 bootstrapping + 사람 검증 30분~1시간 / (fallback) 수동 시딩 6~10시간, M0.5/M4에서 직접 측정 |
| **AutoWebGLM** (Lai 2024) | ChatGLM3-6B SFT/RL + HTML simplification 학습 vs 본 연구의 inference-time + declarative KG |
| **Beyond Pixels: DOM Downsampling** (2025) | site-agnostic signal-processing 식 압축 vs 본 연구의 site-specific KG retrieval. 도메인 지식 명시 여부 |
| **OmniParser** (Microsoft 2024) | 순수 vision (학습된 detector + caption) vs 본 연구의 순수 텍스트 KG. screenshot 의존성 vs DOM/A11y tree 의존성 |
| **SeeAct / WebVoyager / Set-of-Mark** | visual + DOM hybrid grounding (LMM) vs 본 연구의 KG-only grounding. 본 연구가 입증할 것: visual 없이도 declarative widget KG로 충분한 grounding 가능 |
| **WebFormer / DOM-LM / Pix2Struct** | DOM/screenshot representation pretraining vs 본 연구의 inference-time declarative |
| **Contextual Experience Replay** (Liu 2025) | 자연어 trajectory 누적 vs 본 연구의 구조적 hierarchical KG |
| **GraphRAG** (Peng 2024 et al.) | external KG (QA 도메인) vs 본 연구의 사이트 내부까지 표현 |
| **Go-Browse** (Gandhi & Neubig 2025) | graph traversal 기반 사이트 탐색은 본 연구 §4.4 offline bootstrapping과 가장 인접. 차이: Go-Browse는 *trajectory 수집 → SFT 학습 필요* + page-level만, 본 연구는 *KG 산출물 자체가 inference-time에 직접 사용* + widget-level 분류 + 학습 불필요 |
| **Web Apps as KG** (Chandrasekharuni 2024) | 자동 테스트 케이스 생성 vs 본 연구의 LLM 에이전트 통합 + intra-page |
| **A11y Tree Self-Healing** (arXiv 2603.20358) | 산업계 test automation의 10-tier locator hierarchy. 본 연구의 WidgetNode locator strategy fallback 설계의 직접 참고 |
| **v1 page-level SKG** (본 프로젝트, 폐기) | page graph만 vs 본 연구의 hierarchical (page + widget) |

---

## 8. 위험 요소 및 완화 방안

| 위험 | 가능성 | 영향 | 완화 |
|---|---|---|---|
| **H1' 검증 실패 (D > C가 통계 유의하지 않음)** | 중 | 큼 | 7개 ablation + task family별 (filter/sort/retrieve/navigate/mutate) 분리 분석. 최소한 widget-heavy task family(filter/sort)에서 효과 검출되는지 확인. 검증 실패 시 부정 결과로 솔직히 보고 — lab 006의 page-level 결과와 같은 학술적 가치가 있음 |
| **Ablation 4 (unobserved meta-count) 효과 없음** | 중 | 중 | 본 연구의 framing(§1.4.1)이 단순 수사임을 인정. label-rich graph context (ablation 5)의 단독 효과만으로도 본 연구의 핵심 algorithmic 기여(§7.1.2)는 유지 가능 |
| **Ablation 5 (label-rich graph context) 효과 없음** | 중 | 큼 | 본 연구가 Mind2Web/Agent-E의 element ranking과 operational하게 동일해진다는 의미. 이 경우 본 연구의 차별화는 *시딩 비용*과 *cross-site adaptation 메커니즘* 두 차원으로 좁혀진다. 부정 결과로 솔직 보고 |
| ~~Agent-E baseline 대비 절대 성능 밀림~~ → **해결됨 (M6 신설로)** | — | — | M6 Online-Mind2Web 통합으로 본 연구는 *동일 환경 외부 baseline pool* 확보 (Browser-use, GPT-5.4, Operator, Claude 3.7, SeeAct, 후속 agent). Agent-E는 *positioning reference*로만 인용. 본 연구의 비교 위치는 SeeAct 천장 + 30%대 후속 agent 능가가 정직한 목표 |
| **★ M6 H5 미검출 (Online-Mind2Web에서 D > C 방향성 부재)** | 중 | 큼 | cross-benchmark 일반화 실패 = 본 연구 효과가 WebArena GitLab 특화. 완화: (a) 솔직 보고 — contribution을 "WebArena GitLab 환경 한정 효과"로 명시 한정. (b) 두 벤치마크의 task 분포 차이 분석으로 *어느 task family*에서 일관성이 무너지는지 진단. (c) Online-Mind2Web 특정 task 유형에 본 연구가 강함/약함을 sub-claim으로 분리 보고 |
| **★ M6 SeeAct 천장 미도달 (Online-Mind2Web에서 본 연구가 SeeAct early 2024 수준 미달)** | 중 | 큼 | 본 연구의 정직한 직접 비교 대상이 SeeAct. 미도달이면 *학습 0 + DOM only* 접근의 천장이 SeeAct보다 낮음을 인정해야 함. 완화: (a) 본 연구가 SeeAct와 다른 task 유형(filter/sort 같은 widget-heavy)에서 우위인지 분리 분석. (b) Operator/Claude 3.7 같은 multimodal과의 trade-off framing으로 contribution 보존 |
| **★ "Illusion of Progress?" 흐름 인용이 본 연구를 *과도하게 야심차게* 보이게 만들 위험** | 중 | 중 | 본 연구는 *후속 작업*이지 *대체 작업*이 아님을 §1.1·§7.1에 일관 명시. "정면 대응", "흐름을 잇는다" 같은 표현 사용 시 신중. 본 연구가 Illusion 흐름의 *모든* 결론을 능가한다고 주장하지 않음 |
| **★ Online-Mind2Web 사이트 다양성에 비한 시드 부담** | 높 | 중 | Online-Mind2Web은 136개 사이트. sub-set으로 30~50 task만 측정해도 사이트 ~20+개. 사이트당 시드가 부담. 완화: M0.5 자동 bootstrapping을 *cross-benchmark 검증 자체*로 활용 — 자동 시드 작동 확인이 H5 검증의 부수 효과 |
| **SeeAct/WebVoyager 결론(visual+DOM hybrid 최선) 정당화 위협** | 중 | 중 | 본 연구는 *순수 텍스트 KG 단독*의 천장을 측정하는 것이 1차 목표. visual 결합 없이 도달 가능한 한계를 정량화하면 본 연구의 의의가 명확해짐. future work로 *KG + Set-of-Mark* hybrid 제안 |
| ~~WidgetType taxonomy의 GitLab bias~~ → **§4.1.5 폐기로 위험 자체 사라짐 (2026-04-11)** | — | — | taxonomy 자체가 없음. cross-site 일반화는 *description의 의미적 유사성*으로 LLM이 처리. 새 위험은 위 *Description-based cross-site 매칭의 LLM 의존성*으로 대체 |
| Phase 3 dynamic construction 노이즈 | 높 | 중 | confidence threshold + commit 단계 분리. 처음엔 운영자 confirm |
| LLM 비결정성으로 통계 유의성 미달 | 중 | 높 | 반복 회수 3→5 증가, 효과 크기 + p-value 동시 보고 |
| **시딩 비용이 학습 기반 대비 차수 절감을 보이지 못함** | 중 | 큼 | 본 연구의 가치 명제 핵심 위협. 완화: (a) M4에서 직접 wall-clock 측정 후 학습 기반 접근(Mind2Web 데이터 수집 + fine-tuning, OmniParser 67k 라벨링)과 비교 표 작성. (b) 절대 시간이 *minimal viable seed* 기준 약 6~10시간 (§4.1.7 reference)이라 가정해도 fine-tuning(수 일~수 주)보다 1~2 차수 작음 — 차수 비교는 거의 확실. (c) 만약 본 비교에서도 절감이 미미하면 본 연구의 가치는 *시딩 비용*이 아니라 *Phase 3 자동 구축*과 *학습 데이터 부재 환경에서의 적용 가능성*으로 좁혀짐 |
| ~~Cold-start 문제 (빈 KG에서 첫 task 작동 어려움)~~ → **§4.4 offline bootstrapping(M0.5)으로 해결** | — | — | 이전 plan에 미해결로 남아 있던 위험. M0.5 신설로 해결 — task 실행 *전*에 사이트 자동 순회로 baseline KG를 생성. ablation 9 (bootstrapping + Phase 3 stacking)로 시너지 측정 |
| ~~A2: TaskWidgetMap이 oracle이라는 의문~~ → **§4.1.6 원칙으로 근본 해결 (2026-04-11)** | — | — | TaskWidgetMap 자체를 본 연구에서 *완전 폐기*. KG는 사이트 *구조*만 표현하고 task→widget mapping은 KG에 박지 않음. task의 풀이는 LLM이 KG 위에서 자체 추론. oracle 의문이 *성립할 대상 자체*가 사라짐. H1' 검증의 정직성 회복, H4 검증의 공정성 회복 (자동/사람 시드 모두 동일하게 task semantic 없음) |
| ~~A3: Universal taxonomy ~35개 도출 근거 부재~~ → **§4.1.5 통째 폐기로 근본 해결 (2026-04-11)** | — | — | §4.1.6 minimum viable 원칙 도입으로 taxonomy 자체가 폐기됨. 도출 근거 약점이 *성립할 대상 자체*가 사라짐. type/category는 runtime에 DOM의 tag/role/class에서 직접 추출 |
| ~~B1: infer_widget_type() 휴리스틱 spec 부족~~ → **§4.1.5 통째 폐기로 근본 해결 (2026-04-11)** | — | — | type 분류 자체가 본 연구에서 사라졌으므로 휴리스틱 spec이 필요 없음. M0.5 LLM은 *분류기*가 아니라 *description generator* (§4.4.3) |
| ~~B2: PageNode matching 알고리즘 부재~~ → **§4.1.2 deterministic spec으로 해결 (2026-04-11)** | — | — | URL pattern (Express.js placeholder) + specificity sort + structural_signals tiebreak. URL pattern 매칭 0개면 UNRESOLVED. ~20 단위 테스트 케이스 (M0). LLM 위임 없음, 임의 가중치 없음 |
| **★ B2 잔존 위험: SPA hash routing 미지원** | 낮 | 중 | `/dashboard#issues` 같은 hash-based SPA routing은 본 연구의 URL pattern matching이 처리 못 함 (fragment 무시). WebArena-Verified GitLab은 hash routing 거의 사용 안 하므로 영향 작지만, Online-Mind2Web의 일부 modern SPA 사이트(SPA framework 기반)에서 한계 가능. 완화: future work로 hash routing pattern 추가 (§11) |
| **★ B1 후속 위험: Description-based cross-site 매칭의 LLM 의존성** | 중 | 중 | type 명시 없이 LLM이 description의 의미적 유사성으로 cross-site 매칭. 학습된 LLM에 *전적으로 의존*. 사이트마다 description 표현이 다르면 매칭 실패 가능. 완화: (a) ablation 11(재정의)로 description-only 매칭 효과 측정. (b) LLM 모델별 robustness 검증 (gpt-4o vs Claude). (c) 매칭 실패 시 raw DOM metadata (tag/role/class)를 LLM에 함께 전달해 보강 |
| **★ Minimum viable KG가 너무 가벼울 위험** | 중 | 중 | KG가 *DOM이 못 표현하는 4가지*만 박으면, *그 4가지의 description 품질*이 모든 효과를 결정. description이 약하면 KG 전체가 약해짐. 완화: (a) M0.5 description generator의 정확도 sample 검증, (b) ablation 11(재정의)로 description-only vs description+raw metadata 효과 분리, (c) 사람 시드의 description은 minimum 2~3 문장 이상 가이드라인 명시 |
| **★★ M0.5 미작동으로 본 연구 가치 명제 약화 — 핵심 위험** | 중 | **매우 큼** | 본 연구의 *목표 시나리오*는 "M0.5 작동 + 사람 검증 30분~1시간". M0.5가 H4 검증에서 실패(자동 시드의 task 성공률이 사람 시드 대비 천장 15%p 이상 하락)하면 본 연구의 가치 명제가 *fallback*("수동 6~10시간, 학습 대비 1~2 차수 절감")으로 약화. 이는 design constraint와 어긋나는 수준. 완화: (a) confidence 3-tier로 high/mid/low 분리해 자동 commit 범위를 control, (b) M0.5에서 자동/사람 시드의 widget recall/precision을 M1 이전에 먼저 측정해 조기 경고, (c) 실패 시 offline bootstrapping을 *스캐폴딩 도구*로 격하 (사람이 자동 시드 위에서 수정) — 그래도 수동 0에서 시작보다는 빠름. (d) 최악 시나리오(fallback 고정)는 §7.2에 명시되어 있고 정직하게 보고 |
| **★ M0.5 LLM 분류 hallucination** (자동 시드의 false positive) | 높 | 큼 | gpt-4o-mini가 잘못된 type 분류 또는 존재하지 않는 selector를 생성할 수 있음. 완화: (a) Playwright 검증 단계에서 selector 매칭 0개 항목 폐기, (b) 3-tier confidence 정책 (high만 자동 commit, mid는 사람 confirm), (c) M0.5 검증 단계에서 사람 sample 검증으로 false positive rate 직접 측정, (d) 측정 결과로 confidence threshold 재조정 |
| **★ M0.5 자동 시드의 brittleness** | 중 | 중 | LLM 분류가 site/page 특성에 따라 정확도 변동 가능. 완화: ablation 8에서 자동 시드의 task 성공률을 사람 시드와 *직접 비교*. 차이가 크면 자동 시드를 *스캐폴딩 도구*로 강등 (사람이 자동 시드 위에서 수정) |
| **★ M0.5 LLM API 비용 증가** | 중 | 중 | bootstrapping에 사이트당 100~200 LLM 호출 추정 (gpt-4o-mini 기준). 완화: (a) gpt-4o-mini default로 비용 최소화, (b) batching으로 호출 횟수 ↓, (c) 사이트당 비용 ceiling 명시 (M0.5에서 결정), (d) cross-site 평가도 사이트당 1회만 |
| **★ 자동 시드 false positive가 ablation 결과 오염** | 중 | 큼 | H1' 검증(조건 D)에 자동 시드를 사용하면 잘못 분류된 widget이 결과를 오염시킬 수 있음. 완화: H1'/H2/H3 검증의 1차 측정은 *사람 시드*로 수행. 자동 시드는 ablation 8 (H4)에서만 별도 측정. 두 결과를 분리 보고 |
| seed YAML 자동 생성 도구 부재 | 해결 | — | M0.5 신설로 해결 (`runtime/sitekg/bootstrapping/`) |
| v3 baseline 재구현 범위 폭증 | 높 | 큼 | M0를 두 sub-마일스톤으로 (M0a: KG 모델, M0b: v3 통합) |

---

## 9. 검증 체크리스트

- [ ] M0: 새 KG 모델 단위 테스트 (PageNode/WidgetNode/Two-layer 그래프 연산)
- [ ] M0: YAML seed_loader round-trip 테스트
- [ ] **★ M0: `match_page_node()` 단위 테스트 ~20 케이스 (§4.1.2 B2 해결)** — 정확 매칭 / placeholder / specificity 정렬 / catch-all과의 우선순위 / query parameter 무시 / query parameter 명시 매칭 / trailing slash 정규화 / structural_signals tiebreak / UNRESOLVED 반환 / 잘못된 도메인 회피
- [ ] M0: GitLab 사람 시드 작성 (9 PageNode + ~5~10 widgets per page + InteractionEdges + NavigationEdges. ★ task_widgets 섹션 없음 — §4.1.6 원칙)
- [ ] M0: v3 baseline 재구현 + 기존 테스트 통과
- [ ] M0: 새 baseline 측정 (조건 A)
- [ ] **★ M0.5: `runtime/sitekg/bootstrapping/` 패키지 구현 (crawler + extractor + classifier + simulator + confidence + pipeline + CLI)**
- [ ] **★ M0.5: GitLab 자동 시드 `gitlab.auto.yaml` 생성 (gpt-4o-mini)**
- [ ] **★ M0.5: 자동 시드 vs 사람 시드 widget recall/precision/false positive 측정 + 비교 표**
- [ ] **★ M0.5: bootstrapping wall-clock + LLM API 호출 횟수/토큰 비용 reference 측정**
- [ ] **★ M0.5: confidence 3-tier 정책 검증 — high false positive rate 측정 → threshold 재조정**
- [ ] M1: widget retrieval 단위 테스트
- [ ] M1: 조건 B/C/D 측정 → H1' 검증 (`D - C > C - B`)
- [ ] M2: BFS path finding + widget sequencing 단위 테스트
- [ ] M2: 조건 E 측정 → H2 검증
- [ ] M3: dynamic construction 단위 테스트
- [ ] M3: 조건 F 측정 → H3 검증
- [ ] M3: 빈 KG에서 Phase 3만으로 GitLab task 측정 (zero-shot 자동 구축)
- [ ] M4: Reddit YAML 시드 + 시딩 wall-clock 직접 측정 (사전 목표 숫자 없음, 측정 결과 자체가 결과). 학습 기반 접근(Mind2Web 데이터 수집 + fine-tuning, OmniParser 67k 라벨링)과의 *차수 비교 표* 작성
- [ ] M4: Reddit cross-site 측정 + 빈 KG에서 Reddit zero-shot 측정
- [ ] M5: 9개 ablation 결과 (특히 ablation 4, 5 — framing operational 검증; ablation 8 — H4 자동 vs 사람 시드 검증; ablation 9 — bootstrapping + Phase 3 시너지)
- [ ] M5: paired t-test + 효과 크기 표
- [ ] M5: 각 학술적 기여(§7.1.1~6)에 대해 *해당 ablation 결과*를 명시 매핑한 표
- [ ] M5: lab report 007 + 논문 초안 (M6 결과 이전 1차)
- [ ] **★ M6.1: `runtime/benchmarks/online_mind2web/` adapter 작성 (3~5일)**
- [ ] **★ M6.2: Online-Mind2Web sub-set 30~50 task 선정 (난이도/사이트 다양성 균형)**
- [ ] **★ M6.3: Online-Mind2Web 사이트별 자동 시드 (M0.5 도구 재사용, 사이트당 1~2시간)**
- [ ] **★ M6.4: 측정 (조건 D + 조건 F × 3회 반복) — 1~2주**
- [ ] **★ M6.5: Hugging Face leaderboard 등록 + 외부 baseline 비교 표 작성 (Browser-use, GPT-5.4, Operator, Claude 3.7, SeeAct, 후속 agent)**
- [ ] **★ M6.6: H5 cross-benchmark 일관성 분석 — WebArena vs Online-Mind2Web 효과 방향성 비교 (방향성 우선, 효과 크기 보존은 sub-claim)**
- [ ] **★ M6: lab report 007 보강 + 논문 초안 cross-benchmark 섹션 추가**

---

## 10. 참고 문헌

### 10.1 핵심 참고
- **Chandrasekharuni Y.** (2024). *Representing Web Applications As Knowledge Graphs*. arXiv:2410.17258.
- **Liu Y. et al.** (2025). *Contextual Experience Replay for Self-Improvement of Language Agents*. ACL 2025.
- **Lai H. et al.** (2024). *AutoWebGLM: Bootstrap And Reinforce A Large Language Model-based Web Navigating Agent*. KDD 2024. arXiv:2404.03648.
- **Zhou S. et al.** (2023). *WebArena: A Realistic Web Environment for Building Autonomous Agents*. arXiv:2307.13854.
- **Gandhi A., Neubig G.** (2025). *Go-Browse: Training Web Agents with Structured Exploration*. arXiv:2506.03533.

### 10.2 KG-RAG 관련
- **Peng C. et al.** (2024). *Graph Retrieval-Augmented Generation: A Survey*. arXiv:2408.08921.
- **Li M. et al.** (2025). *SubgraphRAG*. ICLR 2025.
- **Hu Y. et al.** (2025). *GRAG*. NAACL 2025 Findings.
- **Zhao L. et al.** (2025). *AGENTiGraph: Multi-Agent KG Framework for LLM Chatbots*. CIKM 2025.

### 10.3 Intra-page DOM understanding (본 연구의 핵심 비교군)

#### 10.3.1 학습 기반 representation pretraining (§3.4.1)
- **Lee K. et al.** (2023). *Pix2Struct: Screenshot Parsing as Pretraining for Visual Language Understanding*. ICML 2023. arXiv:2210.03347.
- **Wang C. et al.** (2022). *WebFormer: The Web-page Transformer for Structure Information Extraction*. WWW 2022. arXiv:2202.00217.
- **Deng X. et al.** (2022). *DOM-LM: Learning Generalizable Representations for HTML Documents*. arXiv:2201.10608.

#### 10.3.2 학습 기반 element ranking (§3.4.2)
- **Deng X. et al.** (2023). *Mind2Web: Towards a Generalist Agent for the Web*. NeurIPS 2023 Spotlight. arXiv:2306.06070.
- **Xue Y. et al.** (2025). *An Illusion of Progress? Assessing the Current State of Web Agents*. COLM 2025. arXiv:2504.01382. — **본 연구의 cross-benchmark 일반화 검증 환경(Online-Mind2Web) 출처. 본 연구가 진단을 공유하고 *intra-page widget salience*로 더 구체화한다.**
- **OSU-NLP-Group**. *Online-Mind2Web Benchmark*. https://github.com/OSU-NLP-Group/Online-Mind2Web. *Hugging Face leaderboard*: https://huggingface.co/spaces/osunlp/Online_Mind2Web_Leaderboard. *HAL Princeton leaderboard*: https://hal.cs.princeton.edu/online_mind2web.

#### 10.3.3 Inference-time DOM compression / distillation (§3.4.3) — 본 연구의 직접 경쟁/영감
- **Abuelsaad T. et al.** (2024). *Agent-E: From Autonomous Web Navigation to Foundational Design Principles in Agentic Systems*. arXiv:2407.13032. — **WebVoyager 73.2% SOTA. 본 연구 Phase 3 change observation의 직접 영감.**
- **Beyond Pixels: Exploring DOM Downsampling for LLM-Based Web Agents** (2025). arXiv:2508.04412.
- **Jiang H. et al.** (2023). *LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models*. EMNLP 2023.

#### 10.3.4 Visual / hybrid grounding (§3.4.4)
- **Zheng B. et al.** (2024). *GPT-4V(ision) is a Generalist Web Agent, if Grounded* (SeeAct). ICML 2024. arXiv:2401.01614.
- **He H. et al.** (2024). *WebVoyager: Building an End-to-End Web Agent with Large Multimodal Models*. arXiv:2401.13919.
- **Yang J. et al.** (2023). *Set-of-Mark Prompting Unleashes Extraordinary Visual Grounding in GPT-4V*. arXiv:2310.11441.
- **Lu Y. et al.** (2024). *OmniParser for Pure Vision Based GUI Agent*. Microsoft Research. arXiv:2408.00203. (V2: 2025-02)

#### 10.3.5 A11y tree 기반 산업계 자동화
- **Beyond LLM-based test automation: A Zero-Cost Self-Healing Approach Using DOM Accessibility Tree Extraction** (2026). arXiv:2603.20358. — 10-tier locator hierarchy. 본 연구 WidgetNode locator strategy fallback의 직접 참고.
- **Playwright MCP** (Microsoft, 2025) — A11y snapshot 기반 LLM 자동화 도구.

#### 10.3.6 *(폐기 — 2026-04-11)* Universal WidgetType taxonomy 출처

**상태**: §4.1.5 Universal WidgetType taxonomy가 §4.1.6 minimum viable 원칙으로 폐기됨에 따라, 본 sub-section의 인용 (WAI-ARIA / WAI APG / Material Design / Apple HIG / Bootstrap-Tailwind UI)은 *본 연구의 근거가 아님*. 본 연구는 type/category를 KG에 박지 않고 *runtime에 DOM의 ARIA role / tag에서 직접 추출*한다.

WAI-ARIA spec과 산업계 design system은 *DOM 자체가 표현하는 카테고리 정보*의 출처일 뿐, 본 연구가 *KG에 박는 정보*의 출처는 아님. 이전 v2 작업의 역사적 reference로만 보존.

### 10.4 LLM Agent 일반
- **Yao S. et al.** (2022). *ReAct: Synergizing Reasoning and Acting in Language Models*. ICLR 2023. arXiv:2210.03629.

### 10.5 본 프로젝트 사전 작업
- `docs/lab_reports/001~005`
- `docs/lab_reports/006_prior_injection_experiment.md` — 본 연구의 직접 동기 (page-level prior 부족 입증)

---

## 11. 다음 단계

### 11.1 본 연구 마일스톤 순서

1. 본 문서 검토 후 02_terminology.md 동시 갱신 확인
2. M0 시작: 새 KG 모델 dataclass (★ widget_type 필드 없음, §4.1.6 minimum viable 원칙) + YAML seed loader
3. v3 baseline 재구현 (M0 sub-task)
4. GitLab 사람 시드 작성 → 새 baseline 측정
5. **★ M0.5 시작: `runtime/sitekg/bootstrapping/` 패키지 구현 + GitLab 자동 시드 생성 + 사람 시드와 품질 비교**
6. 각 phase 완료 시 lab report 갱신
7. M5에서 1차 lab report 007 + 논문 초안 작성
8. **★ M6 시작: Online-Mind2Web adapter 구현 + sub-set 측정 + leaderboard 등록 + H5 검증**
9. M6 완료 후 lab report 007 + 논문 초안에 cross-benchmark 섹션 추가

### 11.2 Future work (본 연구 범위 외)

본 연구가 의도적으로 분리한 future work 항목들. lab report 008+ 또는 후속 연구로 다룰 가치 있음:

1. **Minimum viable KG의 한계 검증 — Description-based 매칭이 약한 경우** — 본 연구는 §4.1.5 (Universal WidgetType taxonomy)를 *통째 폐기*하고 LLM의 description 의미 매칭에 cross-site 일반화를 위임한다. 이게 약한 경우 (특정 사이트에서 description 표현 다양성 때문에 매칭 실패)를 측정하고, *최소한의 type 힌트*를 보강하는 hybrid 접근을 future work로 검토 가능. 단 본 연구의 minimum viable 원칙을 깨지 않는 형태여야 함.
2. **KG + Set-of-Mark visual hybrid** — 본 연구는 *순수 텍스트 KG*만 다룸. 만약 H1' 검증 후에도 visual 결합 없이는 한계가 있다면, future work로 *KG + screenshot Set-of-Mark*를 결합하는 hybrid 접근을 제안 (§3.4.4).
3. **Cross-benchmark 확장** — 본 연구는 WebArena-Verified + Online-Mind2Web 두 환경. WebVoyager는 visual 의존이라 제외했지만, *DOM only* 평가가 가능한 다른 벤치마크가 등장하면 추가 검증.
4. **Mind2Web (원본 static dataset)** — action prediction 평가 mismatch로 본 연구 범위 외. 단 trajectory ranking 평가로 본 연구의 *widget retrieval 정확도*만 분리 측정 가능할 수 있음.
5. **Multi-LLM robustness** — 본 연구는 gpt-4o (1차) + Claude Opus 4.6 (보조). Llama / Mistral 등 더 다양한 모델에서 H1'~H5의 robustness 측정.
6. **★ SPA hash routing 지원** (§4.1.2 / §8 B2 잔존 위험) — 본 연구의 URL pattern matching은 fragment(`#section`)를 무시한다. modern SPA의 hash-based routing(`/dashboard#issues`, `/#/projects/123`) 처리는 future work. 해결 시 url_patterns 형식에 hash 지원 추가 (예: `/dashboard#:section`).
