# AVENIR-WEB — 분석 노트

**출처**: Li, Hao, Liu, Wang, "Avenir-Web: Human-Experience-Imitating Multimodal Web Agents with Mixture of Grounding Experts", **Preprint** (arXiv:2602.02468v1, **2026-02**)
**소속**: UCL + Princeton + Edinburgh
**분량**: 19 pages
**Code**: https://github.com/Princeton-AI2-Lab/Avenir-Web

---

## 1. 핵심 아이디어

**Online-Mind2Web**(live web 300 tasks) 벤치마크에서 **open-source 새 SOTA 53.7%** 달성. 3가지 병목을 동시에 공격:

1. **Element grounding** → Mixture of Grounding Experts (MoGE)
2. **Site-specific procedural knowledge 부재** → Experience-Imitation Planning (EIP)
3. **Long-term task tracking 불안정** → Task-Tracking Checklist + Adaptive Memory

### 이 연구에 중요한 비교 맥락

- **WebArena가 아닌 Online-Mind2Web 사용** — 이전에 이 연구의 WebArena-Verified 공신력 우려와 공명하는 흐름
- Open-source agent가 Proprietary SOTA (Yutori Navigator 64.7%, OpenAI Operator 58.3%)와 경쟁 근접
- **Claude Computer Use 3.7 (47.3%)을 53.7%로 추월**

---

## 2. 메커니즘 (3 컴포넌트)

### 2.1 Experience-Imitation Planning (EIP)

**핵심 설계**:
- 과거 crawl 기반 KG가 아니라 **LLM의 online search**로 live 문서 retrieval
- Claude 4.5 Sonnet + online search로 **forums, help centers, user guides** 조회
- Site instruction + target URL → 2-4개 imperative directive로 요약
- Task 시작 시 1회 실행 (initialization phase)

**예시 (petfinder.com)**:
```
1. Click "Find a cat" to start cat adoption search.
2. Enter "94587" in location and set distance to 10 miles.
3. Apply filters by selecting Young and Adult options.
4. Change sort order to Oldest Addition using dropdown.
```

**중요 특성**:
- Plan은 **abstract action description** (precise selector 없음) — 다양한 UI 레이아웃에 robust
- "careers link in footer"같은 **site-specific convention**을 외부 문서에서 미리 파악

### 2.2 Mixture of Grounding Experts (MoGE)

**Visual-first grounding**:
- QWEN3-VL, Gemini 3 Pro로 viewport를 unified visual canvas로 처리
- iframe, canvas, shadow DOM을 DOM 파싱 없이 해결
- Coordinate-based interaction (point-based action)

**Hierarchical fallback (3-tier)**:
- Point-based (정규화 좌표) → Structural element targeting → Global LLM search
- Dropdown: script-level manipulation → semantic search → LLM reasoning
- Text entry: coordinate input → selector fallback → global field search

### 2.3 Task-Tracking Checklist + Adaptive Memory

**Checklist**:
- EIP 결과를 atomic sub-goal로 변환
- 각 sub-goal은 상태를 가짐: `SUCCESS` / `PENDING` / `FAILED`
- 매 action 후 lightweight model이 checklist 업데이트
- Action agent가 checklist를 source of truth로 사용

**Adaptive Memory (chunked recursive summarization)**:
- Sliding window W=5로 raw buffer를 distill → persistent memory state `M_k`
- `M_k = G_φ(M_{k-1}, B_k, E_k)` (E_k = failure reflection buffer)
- Failure는 즉시 요약되어 **Failure Reflection**으로 보존 (summarization에서 잃지 않도록)
- Outcome detection: action 전후 page state 비교 (text, element, focus, URL, scroll, modal)

---

## 3. 성능 수치

### 3.1 Online-Mind2Web (300 tasks × 136 websites)

| Agent | Main Model | Open? | Easy | Med | Hard | Overall |
|---|---|---|---|---|---|---|
| **Proprietary** | | | | | | |
| Navigator | n1-preview | ✗ | 84.0 | 62.2 | 48.7 | **64.7** |
| OpenAI Operator | Computer-Using | ✗ | 73.5 | 59.4 | 39.2 | 58.3 |
| Google Gemini 2.5 CU | Gemini 2.5 CU | ✗ | 77.1 | 55.2 | 45.9 | 57.3 |
| ACT-1 (2025-08) | o3 + Claude-sonnet-4 | ✗ | 71.1 | 52.4 | 32.4 | 52.7 |
| Claude CU 3.7 | Claude-3.7 | ✗ | 75.9 | 41.3 | 27.0 | 47.3 |
| **Open-Source** | | | | | | |
| SeeAct | gpt-4o | ✓ | 51.8 | 28.0 | 9.5 | 30.0 |
| Agent-E | gpt-4o | ✓ | 51.8 | 23.1 | 6.8 | 27.0 |
| Browser Use | gpt-4o | ✓ | 44.6 | 23.1 | 10.8 | 26.0 |
| **AVENIR-WEB (Gemini 3 Pro)** | Gemini 3 Pro | ✓ | 74.1 | 54.6 | 30.3 | **53.7** |
| AVENIR-WEB (Qwen-3-VL-8B) | Qwen-3-VL-8B | ✓ | 42.0 | 23.8 | 11.8 | 25.7 |

→ Open-source SOTA **53.7%** (prior best: SeeAct 30%)
→ Claude Computer Use 3.7 추월. OpenAI Operator와 근접
→ **lightweight 8B open-source model도 25.7%로 이전 SOTA 근사**

### 3.2 Ablation (50-task subset)

| 설정 | SR |
|---|---|
| Full AVENIR-WEB | 48.0% |
| w/o EIP | 36.0% (−12pt) |
| w/o MoGE | 40.0% (−8pt) |
| w/o Checklist | 44.0% (−4pt) |
| w/o Adaptive Memory (W=∞) | Hallucination 증가 |

→ **EIP가 가장 큰 기여 (−12pt)** — procedural knowledge 주입이 성능 핵심

---

## 4. Survey taxonomy 위치

| 축 | AVENIR-WEB |
|---|---|
| Perception | **MM** (visual-first via MoGE + DOM fallback) |
| Task Planning | **Explicit** (EIP + Checklist) |
| Action Reasoning | **SR** (EIP roadmap + failure reflection) |
| Memory Utilization | **LTM (online knowledge retrieval) + STM (adaptive memory)** |
| Execution | WB (plus coord-based visual) |
| Grounding | **Both DG + IG** (hierarchical) |

**Survey Table 1에 누락** — 2026-02 발표로 cutoff 이후.

---

## 5. 공통 질문 적용

### 5.1 Memory 축 위치
**LTM (EIP online retrieval) + STM (Adaptive Memory summarization)**. 두 layer 명시 혼합.

### 5.2 LTM 표현 방식
**자연어 imperative directive** (2-4개). online search로 live 획득.
- 기존 CBA (52 frozen tip), WALT (50+ frozen tool), SteP (14 frozen policy)와 달리 **pre-built knowledge base 없음**.
- 대신 **task 시작 시 live search**.

### 5.3 Execution 방식
Web Browsing 기반이나 **visual coord-based** (DOM-centric 아닌 MoGE 접근).

### 5.4 이 프로젝트 "graph-structured LTM" 대비 비교

| 축 | AVENIR-WEB | 과거 SKG v2 |
|---|---|---|
| Knowledge 획득 | **Task 시작 시 online search** | **사전 crawl + LLM derivation** (frozen) |
| Knowledge 형태 | 자연어 2-4개 directive | Graph (StatePattern/InfoType/LeadsToEdge) |
| Knowledge 출처 | **Human-authored online docs** | Site crawl 결과 |
| 지식 성격 | **Procedural (how-to)** | Structural (URL patterns) |
| Long-horizon 대응 | Adaptive Memory + Checklist | 없음 |
| Grounding | Visual-first (MoGE) | Text-only (DOM id) |
| Benchmark | Online-Mind2Web 53.7% | WebArena baseline 20-30% |

---

## 6. 이 프로젝트에 미치는 implication

### 6.1 "Online retrieval vs Offline KG" 새 축

- WALT, CBA, 과거 SKG는 전부 **사전 구축 frozen knowledge base**
- AVENIR-WEB은 **task-time online search**로 fresh knowledge 획득
- **Online retrieval의 장점**: 최신 정보, 사전 구축 비용 없음
- **Offline KG의 장점**: reproducibility, no network dep, 측정 실험에 적합

→ 재설계 포지셔닝: 이 프로젝트의 frozen KG vs AVENIR-WEB의 online retrieval 비교 ablation 가능. "offline-only setting에서 유사 성능"으로 차별화.

### 6.2 Procedural vs Structural knowledge 재확인

CBA에서 발견한 "operational logic" 구분이 AVENIR-WEB에서 강화됨:
- CBA tips = operational logic (52 rules)
- AVENIR-WEB EIP directives = **procedural knowledge** (how-to steps from docs)
- 과거 SKG = **structural knowledge** (URL patterns, graph connectivity)

→ **3-axis knowledge taxonomy**:
1. Procedural (how-to) — AVENIR-WEB, AWM
2. Operational (logic/rules) — CBA
3. Structural (topology) — 과거 SKG, WALT (URL promotion 부분)

**재설계 제안**: Structural knowledge는 유일한 graph-friendly category. Procedural/operational은 다른 연구가 잘 함. 이 프로젝트는 structural에 집중해야 함.

### 6.3 Visual grounding의 중요성 (MoGE ablation)

**−8pt 없으면 성능 손실**. 이 프로젝트의 text-only baseline은:
- iframe, canvas, shadow DOM에서 grounding 실패
- WebArena-Verified GitLab은 iframe 많지 않아 이슈 적으나, 일반화 시 치명적
- 논문 limitation에 "text-only grounding" 명시 필수

### 6.4 Checklist 개념

AVENIR-WEB의 Task-Tracking Checklist는:
- 2-4개 atomic sub-goal + SUCCESS/PENDING/FAILED status
- action 후 lightweight model로 업데이트
- Source of truth 역할

→ 이 연구의 `build_plan()` → `sub_goals[]` 구조와 유사하나 **status tracking이 부재**. 재설계 시 status-aware sub-goal 도입 가치. `_verify_done` over-permissive 문제(lessons_learned §6.3)도 checklist status 기반으로 해결 가능.

### 6.5 Benchmark 재고

- AVENIR-WEB은 **Online-Mind2Web**에서 53.7%
- WebArena에선 이 논문이 다루지 않음
- Xue et al. "Illusion of Progress" (memory `feedback_research_evaluation_strategy`)가 Online-Mind2Web 제안자
- Field가 live benchmark로 이동하는 흐름 확실

**함의**: WebArena-Verified GitLab subset scope를 **신생 benchmark라 공신력 낮음** 방어 불가능에 근접. 원조 WebArena 또는 Online-Mind2Web 도입 검토 재강화.

### 6.6 Open-source SOTA 접근 가능성

- Gemini 3 Pro로 53.7%, Qwen-3-VL-8B로 25.7%
- 이 연구는 GPT-4o-mini로 baseline ~30% 수준
- **모델 업그레이드만으로 20-30%p 개선 가능성** (memory `feedback_measurement_once` 고려 필요)
- Reviewer 공격 예상: "왜 Qwen-3-VL-8B 같은 open 모델 사용 안 했는가?"

### 6.7 생존 가능 방향 재평가 (4개 논문 누적)

| 방향 | WALT | CBA | AVENIR-WEB | 종합 |
|---|---|---|---|---|
| Structural knowledge (graph) | 충돌 낮음 | 충돌 낮음 | 충돌 없음 (procedural 전담) | ✅ 확정 |
| State invariants | 낮음 | 낮음 | 낮음 | ✅ |
| Low-cost framing | 없음 | 중간 | 약함 | ⚠ |
| Offline vs Online retrieval | 없음 | 비교군 | **새 축** | ✅ 강화 |
| Checklist 도입 | — | — | 권장 | ✅ 부가 |
| Visual grounding 언급 | — | — | 필수 | ⚠ limitation |

---

## 7. `lessons_learned_kg_v2.md` 추가 교훈

### §7.2 (아키텍처) 추가
- **Status-aware sub-goal tracking 필수** — AVENIR-WEB Checklist + `_verify_done` over-permissiveness 해결 단서
- **Visual grounding 없으면 일반화 상실** — text-only는 특정 벤치에만 통함

### §7.4 (데이터 원칙) 추가
- Knowledge taxonomy 3-axis: **Procedural / Operational / Structural**
- Graph representation은 Structural에만 자연스러움

### §7.3 (방법론) 추가
- **Online retrieval vs Offline KG**는 명시적 ablation 대상으로 고려 — 2-variant 이상 비교 시 offline-KG의 가치 empirical 검증

---

## 8. 불확실한 부분 / 추가 확인 필요

- EIP의 **online search 실패** 시 fallback behavior
- **Freshness**: live search 결과가 outdated이면 성능 어떻게 변하나
- **Multilingual site** 대응 (비영어 문서 retrieval)
- Task-Tracking Checklist의 업데이트 정확도 (false status 전환 빈도)

---

## 9. 한줄 정리

> AVENIR-WEB = **2026-02 Online-Mind2Web open-source SOTA (53.7%)**. **EIP (LLM online search 기반 procedural knowledge) + MoGE (visual-first grounding) + Checklist + Adaptive Memory** 4-component. 과거 SKG와 직접 경쟁하지 않음 — knowledge 형태가 **procedural** (how-to directive)로 이 프로젝트의 **structural** (URL patterns)과 다른 category. 재설계에 주는 교훈: **(1) online vs offline retrieval 축 명시**, **(2) Checklist status tracking 도입**, **(3) knowledge taxonomy 3분할 (procedural / operational / structural)**. 이 프로젝트는 structural에 집중하여 차별화 가능.
