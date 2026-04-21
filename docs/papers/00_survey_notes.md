# A Survey of WebAgents — 분석 노트

**출처**: Ning et al., "A Survey of WebAgents: Towards Next-Generation AI Agents for Web Automation with Large Foundation Models", arXiv:2503.23350v4 (2025-08)
**분량**: 17 pages
**저자**: HK PolyU / CityU HK / MSU / UIC
**읽은 목적**: 5개 논문(SteP / WALT / ColorBrowserAgent / AVENIR-WEB / LCoW) 분석에 앞서 field 전체 구도 파악 + 이 프로젝트 위치 결정

---

## 1. Survey의 3축 구조

| 축 | 내용 |
|---|---|
| **§3 Architectures** | Perception → Planning & Reasoning → Execution |
| **§4 Training** | Data (pre-processing / augmentation) + Strategies (training-free / GUI comprehension / fine-tuning / post-training) |
| **§5 Trustworthiness** | Safety/Robustness, Privacy, Generalizability |
| **§6 Future** | Fairness/Explainability, Benchmarks, etc. |

---

## 2. 핵심 분류 체계 (§3)

### 2.1 세부 축

| 축 | 카테고리 |
|---|---|
| Perception | Text (TT) / Screenshot (SS) / Multi-modal (MM) |
| Task Planning | Explicit (sub-task 분해) / Implicit |
| Action Reasoning | Reactive (RR, 즉흥) / Strategic (SR, 탐색·시뮬레이션) |
| Memory Utilization | Short-term Memory (STM) / Long-term Memory (LTM) |
| Execution Interacting | Web Browsing (WB, 클릭·입력) / Tools (TL, API call) |
| Grounding | Direct Grounding (DG, 좌표 직접) / Inferential Grounding (IG, 요소 추론) |

### 2.2 Memory Utilization (가장 관련 깊음)

- **STM**: 현재 task의 previous actions (redundant 방지)
- **LTM**: 외부 지속 정보 — 과거 task trajectory, 온라인 검색 지식 등
- LTM 사용 주요 기법:
  - **Trajectory-as-Exemplar** (Synapse) — raw trajectory를 prompt에 주입
  - **Narrative Memory** (Agent S) — 성공·실패 요약을 retrieval
  - **Workflow Memory** (AWM) — 재사용 가능 workflow 유도 후 prompt inject
  - **Online Web Search** (Agent S, OS-Copilot) — 외부 검색 knowledge

**Survey taxonomy에는 "Structured KG" 카테고리 없음**. site-level 지식은 전부 LTM 하위로 분류되며, **주된 표현 형태는 자연어 trajectory / narrative / workflow**.

---

## 3. Table 1 매핑 — 이 프로젝트 관련 WebAgent

| 모델 | 날짜 | 분류 | 비고 |
|---|---|---|---|
| **AWM** | 09/2024 | TT / SR / **LTM** | 가장 가까운 이웃, workflow memory |
| **LCoW** | 03/2025 | TT / RR / STM / IG | 분석 대상 #5 |
| **AgentOccam** | 10/2024 | TT / Explicit / RR / STM | 강한 baseline 후보 |
| **Agent-E** | 07/2024 | TT / Explicit / RR / STM | DOM-only baseline 계열 |
| **Agent S** | 10/2024 | MM / Explicit / SR / **LTM** | Narrative + Online Search |
| **Synapse** | 06/2023 | TT / SR / **LTM** | Trajectory-as-Exemplar |
| **UFO** | 02/2024 | SS / Explicit / RR / **LTM** | |
| **WebAgent** (Gur et al.) | 07/2023 | TT / Explicit / RR / STM | |
| SteP | ? | **Table에 없음** | 분석 대상 #1 — 2023 발표 예상, 누락 |
| WALT | ? | **Table에 없음** | 분석 대상 #2 — survey 이후 발표 |
| ColorBrowserAgent | ? | **Table에 없음** | 분석 대상 #3 |
| AVENIR-WEB | ? | **Table에 없음** | 분석 대상 #4 |

---

## 4. 이 프로젝트 위치 매핑

### 4.1 과거 SKG v2 (삭제된 설계)

- Perception: TT
- Task Planning: Explicit (build_plan → sub-goals)
- Action Reasoning: Strategic + LTM 개입 (Hook B rewrite, Hook C validator)
- Memory Utilization: **LTM (structured graph)** — survey taxonomy에서 **marginal** 하위 카테고리
- Execution: WB

→ 분류상 "**graph-structured LTM**". AWM 워크플로 계열 변종이지만, survey가 인정하는 기존 카테고리에 없음. Reviewer가 "왜 natural language workflow(AWM) 대신 graph인가?" 질문할 것.

### 4.2 현재 baseline-only (KG 활용 로직 제거 후)

- TT / Explicit / Reactive / STM / WB / IG
- AgentOccam · Agent-E · Agent-E 계열과 같은 타입
- 즉 Training-free 범주

### 4.3 향후 재설계 방향별 taxonomy 위치

| 재설계 방향 | Survey taxonomy 위치 |
|---|---|
| KG content를 passive context로 주입 | LTM (graph-structured) + Reactive |
| KG로 tool schema 생성 | Tools-based Execution (WALT 유사) |
| KG 전면 폐기 + workflow memory | LTM (natural language) — AWM 복제 |

---

## 5. Survey가 재설계에 주는 시사점 (가장 중요)

### 5.1 Framing 관점 (`lessons_learned §7.3-9` 와 직접 연결)

Survey는 **"Long-term Memory"를 통합 카테고리로 사용**. 과거 제가 썼던 "structural operator / planning substrate" 같은 강한 구분은 **survey 내에서 지지되지 않음**.

→ **재설계 시 "KG는 structured LTM"으로 중립 포지셔닝**. Novelty는 "graph structure" 선택의 empirical trade-off 비교로 확보.

### 5.2 Passive Retrieval이 Field 관행

- **Synapse** (Trajectory-as-Exemplar): LTM을 prompt context로 주입
- **Agent S** (Narrative Memory): 성공·실패 summary retrieval
- **AWM**: workflow를 prompt inject

→ 전부 passive context injection. 과거 R3-α가 이 패턴을 뒤늦게 따라갔으나 여전히 Hook A (LLM 분류) 잔여로 오염. `lessons_learned §7.3-10` ("첫 시도는 passive retrieval부터")이 field 관행과 부합.

### 5.3 Grounding blind spot

Survey가 Direct (DG) / Inferential (IG) Grounding을 별도 축으로 다룸. 이 연구의 baseline은 TT 기반이라 grounding 축에서 약함.

→ **KG 도입해도 grounding 문제는 해결 안 됨**. 논문 scope에 "multi-modal 미포함" 한계 명시 필수.

### 5.4 Tools-based Execution이 떠오르는 패러다임 (§3.3)

- API-calling agent, Infogent, WALT 같은 **tool-based execution**이 최근 흐름
- 이 프로젝트의 "KG로 URL shortcut" 아이디어는 tools-based의 **약한 버전** (URL을 tool처럼 쓴다)
- **WALT 분석 시 정면 비교 예상** — "KG가 WALT의 덜 개발된 버전이 아닌가"라는 비판 방어 필요

### 5.5 Training-free vs Training-based 경쟁

- Survey는 training-free가 **prompt engineering 한계에 도달**하고 있다고 암시 (§4.2)
- Post-training 계열 (WebRL, WebAgent-R1, ScribeAgent) 이 떠오름
- 이 연구의 방향(no-training + KG)은 training-free 안에 머물지만, 성능 경쟁자가 training 쪽에 있음

### 5.6 Benchmark 공백 (§6.2)

- Survey가 "기존 benchmark가 real-world 복잡성 과소표현"이라고 지적
- 이 프로젝트의 **WebArena-Verified가 신생 benchmark라 공신력 낮다**는 이전 우려와 공명
- 원조 WebArena 또는 Online-Mind2Web 같은 more established benchmark 고려 필요

---

## 6. 5개 논문 분석 시 공통 질문 template

각 논문을 읽을 때 다음 4개 질문으로 정렬:

1. **Memory 축 위치**: 어떤 카테고리 (STM / LTM / 없음) ?
2. **LTM이면 표현 방식**: natural language / graph / tool schema / API / 코드 ?
3. **Execution 방식**: Web Browsing / Tools / 혼합 ?
4. **이 프로젝트 "graph-structured LTM" 방향 대비 비교 우위**: 무엇이 novel 한가, 이 연구의 아이디어를 이미 subsume 하는가 ?

---

## 7. 다음 단계

- 5개 논문을 순서대로 분석 (SteP → WALT → ColorBrowserAgent → AVENIR-WEB → LCoW)
- 각 논문 분석 후 `docs/papers/<n>_<name>_notes.md` 신규 파일 생성
- 모든 분석 완료 후 종합 비교표 + 재설계 방향 제안서 (`docs/related_work_synthesis.md`) 작성

## 8. 유의사항

- Survey가 Aug 2025 cut-off. WALT, ColorBrowserAgent, AVENIR-WEB은 누락 가능성 — 각 논문 publication date 확인 필요
- Survey는 **방법론 taxonomy 중심**이고 benchmark 수치(WebArena success rate 등)는 직접 제공 안 함 → 각 논문에서 공통 benchmark 수치 확보해야 fair comparison 가능
