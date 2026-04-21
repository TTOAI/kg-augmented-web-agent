# LCoW — 분석 노트

**출처**: Lee, Lee, Kim, Tack, Shin, Teh, Lee, "Learning to Contextualize Web Pages for Enhanced Decision Making by LLM Agents", **ICLR 2025** (arXiv:2503.10689v2, v1: 2025-03, v2: 2025-12)
**소속**: KAIST AI + University of Oxford
**분량**: 35 pages
**Code**: https://lcowiclr2025.github.io
**Survey 등재**: **Table 1에 LCoW (03/2025)** — TT/RR/STM/IG

---

## 1. 핵심 아이디어

**Web page understanding과 decision making을 decouple**. 별도의 **contextualization module** (소형 LM)을 훈련시켜 복잡한 web page observation을 agent가 이해하기 쉬운 형태로 압축.

- 기존 agent: raw HTML/AXTree를 agent가 직접 처리 → 긴 context로 성능 저하
- LCoW: separate LM `f_θ`가 observation을 압축 → agent는 압축된 context로 decision 집중

### 핵심 가설
> LLM agent는 decision-making 능력은 강하지만, **긴 non-contextualized observation (HTML/AXTree)**에서 성능이 크게 떨어진다. Observation understanding을 별도 layer로 분리하면 agent는 decision에 집중 가능.

---

## 2. 메커니즘

### 2.1 Contextualization Module

- 별도의 LM `f_θ` (GPT-4o 등 closed 또는 Llama open 모델 가능)
- 입력: `[TASK]`, `a_<t` (action history), `o_t` (raw observation)
- 출력: `o^co_t` — 자연어 contextualized observation

**출력 형태 예시** (WebArena에서):
```
The AXTree observation shows a list of forums on a website called Postmill. 
Each forum is presented as an article with its name, number of subscribers, 
and number of submissions. The forums are sorted by the number of submissions 
in descending order.
...
Additionally, for context, we can include the first forum in the list:
[141] article ''
    [143] heading 'AskReddit — AskReddit'
...
This extraction shows the first forum in the list, which is "AskReddit" 
with 10,041 submissions. It confirms that we are currently on the first 
page of forums and need to navigate to the next page.
```

→ Raw AXTree 수백 줄을 **의미 중심 자연어** + 관련 UI 요소만 선별

### 2.2 Iterative Training (3-step loop)

**Step 1 (Trajectory collection)**:
- 현재 module `f_θ(i)`로 agent rollout
- 성공한 trajectory만 수집

**Step 2 (Sampling optimal contextualization)**:
- 각 observation `o_t`에 대해 다수 candidate `o^co_t ~ f_θ(i)` 샘플링
- Reward: **multiple LLM agent들이 ground-truth action `a_t`를 예측 가능한가**
- 최대 reward를 받은 candidate 선택
- 모든 candidate가 0 reward면 ground-truth action을 추가 context로 제공 후 재샘플링

**Step 3 (Model update)**:
- 선택된 optimal contextualized observation으로 `f_θ` SFT

→ 3 iteration 정도로 수렴

---

## 3. 성능 수치

### 3.1 WebShop (500 eval tasks)

| Agent | Raw | Self-ctx | LCoW iter1 | LCoW iter2 | **LCoW iter3** |
|---|---|---|---|---|---|
| GPT-4o | 34.8% | 26.2% | 27.8% | 46.0% | **50.6%** |
| Gemini-1.5-flash | 43.6% | 46.4% | 46.4% | 58.2% | **62.8%** |
| Claude-3.5-Sonnet | 26.6% | 12.4% | 39.4% | 58.8% | **59.8%** |
| Llama-3.1-70B (unseen) | 34.2% | 40.2% | 39.2% | 55.0% | **59.6%** |

→ Gemini-1.5-flash **62.8%** SOTA on WebShop (prior best AgentQ 50.5%, human expert 59.6%)
→ **인간 전문가 초과**

### 3.2 WorkArena (165 eval tasks)

| Agent | Raw | Self-ctx | LCoW iter1 |
|---|---|---|---|
| GPT-4o | 38.2% | 43.0% | **44.2%** (+6) |
| Gemini-1.5-flash | 11.5% | 12.7% | **41.2%** (+30!) |
| Claude-3.5-Sonnet | 44.8% | 50.3% | **55.8%** (+11) |
| Llama-3.1-70B (unseen) | 26.1% | 29.1% | **40.0%** (+14) |
| **Llama-3.1-8B (unseen)** | 1.2% | 7.3% | **37.0%** (+36) |

→ **Small 모델 (Llama-8B)에서 가장 큰 ablation gain (+36pt)**
→ unseen agent로도 generalize (훈련 시 사용 안 한 모델도 개선)

### 3.3 WebArena (추가 분석만, main experiment 아님)
- 논문 본문에서는 상세 table 없음 (appendix 확인 필요)

---

## 4. Survey taxonomy 위치

| 축 | LCoW | 비고 |
|---|---|---|
| Perception | **TT** (AXTree) | Survey 등재 정보 |
| Task Planning | ✗ (Implicit) | sub-task 분해 없음 |
| Action Reasoning | **RR** (Reactive) | 단순 next-action prediction |
| Memory Utilization | **STM** | persistent knowledge base 없음 |
| Execution | WB | |
| Grounding | **IG** (Inferential) | |

**주목**: LCoW은 Memory (LTM) 축이 아닌 **Perception (TT)** 축에 가치를 추가하는 연구. 다른 4개 논문(SteP/WALT/CBA/AVENIR)과 **완전히 다른 레이어**에 작동.

---

## 5. 공통 질문 적용

### 5.1 Memory 축 위치
**STM only**. Persistent knowledge base 없음. 대신 **trained parameters에 implicit knowledge** 내재 (SFT로 학습).

### 5.2 LTM 표현 방식
LTM 없음. **Parametric memory** (훈련된 `f_θ` 모델 가중치).

### 5.3 Execution 방식
Web Browsing only. Tool 사용 안 함.

### 5.4 이 프로젝트 "graph-structured LTM" 대비 비교

| 축 | LCoW | 과거 SKG v2 |
|---|---|---|
| 문제 layer | **Perception (observation preprocessing)** | Memory (site knowledge base) |
| 솔루션 | **Trained LM (SFT)** | Frozen Graph |
| Training 필요 | **Yes** (successful trajectory 500개) | No (training-free) |
| Site 독립성 | **Site-independent** (모든 사이트에 동일 module) | **Site-specific** (사이트마다 다른 KG) |
| Orthogonality | **과거 SKG와 완전 orthogonal** — 결합 가능 | — |
| WebShop SR | 62.8% (Gemini-1.5-flash) | N/A |

---

## 6. 이 프로젝트에 미치는 implication

### 6.1 LCoW는 이 프로젝트와 **Orthogonal** — 경쟁 아님

- 다른 4개 논문과 달리 LCoW는 **Perception layer**에 작동
- Site knowledge는 다루지 않음
- **그래서 과거 SKG 같은 "Memory/LTM" 접근과 자연스럽게 결합 가능**

### 6.2 새 재설계 축: Perception Preprocessing 추가

LCoW의 성공은 다음을 시사:
- Raw AXTree는 agent에게 **비효율적 observation 포맷**
- 소형 LM으로 **task-aware 압축**하면 decision 품질 ↑
- Gemini-1.5-flash가 raw 43.6% → LCoW 62.8% (+19pt)는 거의 모델 업그레이드급

**이 연구의 baseline agent는 raw observation 사용** → LCoW 유사 접근 도입 시 상당한 개선 여지:
- GPT-4o-mini → small contextualization LM 조합도 가능
- Training cost: 500 trajectory 수집 + 3 iteration SFT

### 6.3 Training-based 방법이 제공하는 insight

4개 training-free 논문과 달리 LCoW는 training을 요구. 이게 의미하는 바:
- **재설계가 꼭 training-free일 필요 없음**
- Training-free 제약 때문에 놓친 optimization 공간 존재
- 다만 재현성/비용 trade-off 고민 필요

### 6.4 Small model 이득 특히 큼 (Llama-8B +36pt)

이 연구는 **GPT-4o-mini 같은 저비용 모델** 사용. LCoW 관점에서:
- Small 모델이 LCoW 이득을 가장 크게 받음
- WebArena-Verified 같은 복잡 AXTree 환경에서 LCoW가 GPT-4o-mini baseline을 크게 올릴 가능성

### 6.5 Knowledge Taxonomy 4-axis로 확장

이전 3-axis에 LCoW를 반영하면:

| 종류 | 예시 | 과거 SKG와 관계 |
|---|---|---|
| **Perception preprocessing** | LCoW contextualization | Orthogonal — 결합 가능 |
| **Procedural (how-to)** | AVENIR-WEB EIP, AWM | Orthogonal |
| **Operational (logic/rules)** | CBA tips 52 | Partial overlap |
| **Structural (topology)** | 과거 SKG, WALT URL promotion | 과거 SKG 영역 |

### 6.6 생존 가능 방향 재평가 (5개 논문 누적)

| 방향 | SteP | WALT | CBA | AVENIR | LCoW | 종합 |
|---|---|---|---|---|---|---|
| Structural knowledge (graph) | 충돌 낮음 | 충돌 낮음 | 충돌 낮음 | 충돌 없음 | 충돌 없음 | ✅ |
| State invariants | 낮음 | 낮음 | 낮음 | 낮음 | 없음 | ✅ |
| Low-cost framing | 없음 | 없음 | 중간 | 약함 | 중간 | ⚠ |
| Offline retrieval | 없음 | 비교 | 비교 | 새 축 | 없음 | ✅ |
| + LCoW 유사 preprocessing 도입 | — | — | — | — | — | 🆕 고려 |

**새 가능성**: **KG (structural) + LCoW preprocessing (perception) 결합**이 자연스러운 보완. 둘 다 서로를 subsume 안 함.

### 6.7 Benchmark 주목

LCoW는 **WorkArena**에 초점. WorkArena는 WebArena와 다른 enterprise task 중심 benchmark. 이 연구가 WebArena-Verified GitLab scope라면 직접 비교 데이터 얻기 어렵지만, WebArena 부분 측정 존재.

---

## 7. `lessons_learned_kg_v2.md` 추가 교훈

### §7.2 (아키텍처) 추가
- **Observation preprocessing이 상당한 gain 원천** — raw HTML/AXTree는 LLM에 비효율. Agent 이전 layer에서 task-aware 압축 고려
- Structural knowledge(KG)와 perception preprocessing(LCoW-like)은 **orthogonal**. 둘 다 도입 가능

### §7.3 (방법론) 추가
- **Training-free 제약은 self-imposed** — 재현성 확보 후 small-LM SFT 기반 component 추가 가능
- Small model (GPT-4o-mini 같은) 사용 시 LCoW 유사 preprocessing 이득 가장 큼

### §7.4 (데이터 원칙) 추가
- Knowledge taxonomy에 **Perception preprocessing** 층 추가 (4번째 축)

---

## 8. 불확실한 부분 / 추가 확인 필요

- WebArena 세부 수치 (main result 아니고 additional analysis 중)
- Contextualization module 크기 (small LM? 8B? large?)
- **Online site에서 generalization** — WorkArena/WebShop은 simulated
- Failure mode: contextualization 오류 시 agent 유도 어떻게
- **과거 SKG 같은 site knowledge와 결합했을 때 성능** (본 논문에선 미실험)

---

## 9. 한줄 정리

> LCoW = **ICLR 2025 published, WebShop SOTA 62.8% (human expert 초과)**. Observation preprocessing을 **별도 trained LM으로 decouple**. 다른 4개 논문과 달리 **Perception layer**에 작동 → 과거 SKG 같은 Memory layer 접근과 **orthogonal 결합 가능**. Small model(Llama-8B +36pt)에서 특히 큰 이득. 재설계 시 **(1) KG(structural) + LCoW(perception) 결합 가능성**, **(2) training-based 접근 허용 시 저비용 모델의 큰 성능 여지** 두 가지 새 축 추가. 경쟁 관계 아닌 **complementary 관계**.
