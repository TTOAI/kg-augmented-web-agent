# WALT — 분석 노트

**출처**: Prabhu, Dai, Fernandez, Gu et al., "WALT: Web Agents that Learn Tools", **Preprint** (arXiv:2510.01524v1, **2025-10**)
**소속**: Salesforce AI Research
**분량**: 17 pages
**라이선스**: CC-BY-4.0

---

## 1. 핵심 아이디어

**웹사이트가 이미 설계한 functionality를 reverse-engineering하여 agent가 invoke 가능한 deterministic tool로 노출**.

- 기존 agent: `click → type → click → hover → click → sort` (8+ step UI 조작)
- WALT: `search(query='blue kayak', category='Boats', sort_by='price')` (1 step tool call)

### 핵심 주장

> 사람은 "search for kayaks, filter by price, identify first blue one" 처럼 **기능 수준으로 생각**. UI 클릭 순서가 아니라 "무엇을 원하는지"에 집중. WALT는 agent에게 같은 추상화 제공.

---

## 2. 기존 skill-discovery 대비 차별점

**WALT가 명시적으로 비판하는 선행 연구**:

1. **SkillWeaver** (Zheng et al. 2025): 성공 trajectory에서 Python 함수 생성 (trajectory mining)
2. **AWM** (Wang et al. 2024): 성공 trajectory에서 자연어 workflow 유도
3. **ASI** (Wang et al. 2025): 성공 trajectory에서 program 유도

**WALT 비판 요점**:

- 위 3개는 **이미 있는 behavior를 codify**할 뿐, 기능 확장 못 함
- 구현이 **brittle UI action sequence** → UI 변경 시 깨짐
- 성공 trajectory에만 의존 → agent가 찾지 못한 기능은 skill로 안 됨

**WALT 접근**:

- Agent trajectory가 아니라 **website 자체가 제공하는 functionality** 직접 탐색
- systematic exploration (특정 task 성공과 무관)
- URL parameter promotion → 가능하면 UI sequence를 URL 조작으로 대체
- stress-test + iterative optimization

---

## 3. 메커니즘 (3-phase demonstrate-generate-validate)

### Stage 1: Tool Discovery

- Browser agent가 site의 key section (content/discovery/communication) 탐색
- Dropdown hover, menu click 등 interactive element 발견
- **Candidate tool list** 생성 (명확한 user intent + coverage 최대화 + 중복 최소화)

### Stage 2: Tool Construction

**Two-agent system**:

- `B_browser` (browser agent): 후보 tool 실행 → trace `X` 생성
- `B_tool` (tool construction agent): trace 분석 → action script 생성

**Action script 4-type**:

1. **Navigation** — URL route / query param 변경
2. **Extraction** — DOM 내용 추출
3. **UI interaction** — element hash로 정확한 타겟팅
4. **Agentic** — 동적 element(lazy-loaded 등)용 LLM 호출

**2nd pass 최적화**: **URL parameter promotion** — 다단계 UI를 `?query=X&category=Y`같은 URL로 압축

### Stage 3: Validation

- `(tool, InputSchema, I_test)` 등록 후 `B_browser`가 pre-vetted 테스트 입력으로 end-to-end 실행
- 실패 → structured feedback → selector/schema/script refine
- **Fixed attempt budget** 안에서 pass한 tool만 노출
- 런타임 fallback: 실패 시 fresh agent를 spawn (agentic fallback)

### 목적 함수

```
minimize  FailRate(u, I_test) + StepCount(u) + AgenticRatio(u)
```

→ 정확도 + 효율 + 결정성을 동시 최적화

---

## 4. 성능 수치

### 4.1 WebArena (812 tasks, GPT-5 planner + GPT-5-mini executor)

| Method               | GitLab   | Map      | Shopping | CMS      | Reddit | Multi    | Avg      |
| -------------------- | -------- | -------- | -------- | -------- | ------ | -------- | -------- |
| GPT-4+CoT (original) | —        | —        | —        | —        | —      | —        | 14.4     |
| SkillWeaver (2025)   | 22.2     | 33.9     | 27.2     | 25.8     | 50.0   | —        | 29.8     |
| AWM (2024)           | 28.9     | 39.4     | 34.8     | 39.0     | 51.9   | 18.8     | 35.5     |
| ASI (2025)           | 32.2     | 43.1     | 40.1     | 44.0     | 54.7   | 20.8     | 40.4     |
| Hybrid Agent (2024)  | 44.4     | 45.9     | 25.7     | 41.2     | 51.9   | 16.7     | 38.9     |
| **WALT**             | **57.0** | **58.7** | **41.2** | **56.2** | 48.5   | **20.8** | **50.1** |
| Human                | —        | —        | —        | —        | —      | —        | 78.2     |

→ WebArena **새 SOTA 50.1%** (non-training 방법 중)
→ GitLab **57.0%** — 이 프로젝트 scope와 직접 관련

### 4.2 VisualWebArena (910 tasks)

| Method                | Classifieds | Shopping | Reddit   | Avg      |
| --------------------- | ----------- | -------- | -------- | -------- |
| GPT-4V+SoM            | 9.8         | 17.1     | 19.3     | 16.4     |
| Computer-Use (Claude) | 36.7        | 21.9     | 27.5     | 27.0     |
| AWorld (2025)         | —           | —        | —        | 36.5     |
| SGV (2025)            | 52.0        | 57.0     | 33.0     | 50.2     |
| **WALT**              | **64.1**    | 53.4     | **39.0** | **52.9** |
| Human                 | 91.7        | 88.4     | 87.1     | 88.7     |

### 4.3 Ablation (VWA Classifieds, tools vs no tools)

| LLM        | tools?                           | Steps      | SR           |
| ---------- | -------------------------------- | ---------- | ------------ |
| gpt-4.1    | none                             | 7.6        | 34.9         |
| gpt-4.1    | discovered                       | 6.6 (−13%) | 36.4 (+4.3%) |
| gpt-5-mini | none                             | 8.9        | 57.5         |
| gpt-5-mini | discovered                       | 6.5 (−27%) | 61.5 (+7.0%) |
| gpt-5-mini | **human demo**                   | 7.4        | **66.0**     |
| gpt-5-mini | discovered + multimodal + verify | 7.0        | **64.1**     |

→ **자동 발견 tool이 human-curated(66.0%) 거의 따라잡음 (64.1%)**
→ Tool 있으면 모든 backbone에서 step 수 감소 + SR 증가
→ 강한 LLM일수록 tool의 이득 더 큼 (better reasoning → better tool selection)

### 4.4 Discovered tool stats (VWA Classifieds)

- 50+ tools per site
- `search listings`: 262회 invoke, 거의 완벽한 SR
- Successful trajectory 평균 tool call: 2-5개

---

## 5. Survey taxonomy (00_survey_notes.md) 위치

| 축                 | WALT 분류                                  |
| ------------------ | ------------------------------------------ |
| Perception         | MM (multimodal DOM parsing + SoM)          |
| Task Planning      | Explicit (tool composition)                |
| Action Reasoning   | Reactive (RR) — tool call 단위             |
| Memory Utilization | **LTM (tool library)** — site별 persistent |
| Execution          | **Tools (TL)** — primary paradigm          |
| Grounding          | Both (DG + IG 혼합)                        |

**Survey Table 1에 누락** — 2025-10 발표, survey cutoff 이후.
**Survey §3.3 Execution의 Tools-based 흐름 정점**.

---

## 6. 공통 질문 (00 §6) 적용

### 6.1 Memory 축 위치

**LTM — Tool Library 형태**.

### 6.2 LTM 표현 방식

**Invocable deterministic tools** (action script + input schema + test cases). 자연어 prompt(AWM/SteP)나 graph(과거 SKG)가 아닌 **executable abstraction**.

### 6.3 Execution 방식

**Tool-based primary** + UI primitive fallback + agentic fallback 3계층.

### 6.4 이 프로젝트 "graph-structured LTM" 대비 비교

| 축                     | WALT                                                     | 과거 SKG v2                              |
| ---------------------- | -------------------------------------------------------- | ---------------------------------------- |
| LTM 단위               | **Tool (callable function)**                             | State/InfoType (graph node)              |
| URL shortcut           | **핵심 기능** (URL param promotion 자동)                 | Hook B로 구현 시도, 실패                 |
| 구축 방식              | **Iterative demonstrate-generate-validate**              | One-shot crawl + LLM derivation + freeze |
| Validation             | **Stress-test + feedback loop + retry budget**           | Post-enrich heuristic (LLM 재호출 없음)  |
| Selector 안정성        | **Element hash + alternate selectors + DOM change 대비** | 없음 (URL만)                             |
| 동적 fallback          | **Agentic fallback (fresh agent spawn)**                 | 없음                                     |
| Agent 주도권           | **Agent가 tool invoke** (자율)                           | Hook B가 URL 강제 (command)              |
| 성능 (WebArena GitLab) | **57.0%**                                                | 내 baseline 20-30%                       |

---

## 7. 이 프로젝트에 미치는 strongest implication

### 7.1 WALT가 "KG URL shortcut" 아이디어를 **완전히 subsume**

과거 Hook B의 핵심 아이디어:

> InfoType → StatePattern → URL 템플릿으로 agent를 바로 이동시켜 step 절약

WALT의 "URL parameter promotion":

> 다단계 UI sequence를 **검증된 URL 조작**으로 자동 압축, 동적 fallback 포함

→ WALT가 **훨씬 성숙**: 자동 발견 + 검증 + fallback + selector 안정성. 이 연구의 KG URL shortcut은 WALT의 약한 prototype.

### 7.2 Framing 위기 — "structural site knowledge" 주장 무너짐

Survey가 "LTM 카테고리"로 이 연구의 SKG를 격하시킨 데 이어, **WALT가 site-functionality를 이미 체계적으로 추출**. "KG가 site 지식을 구조화"라는 주장의 novelty가 거의 소멸.

### 7.3 남은 이 프로젝트의 생존 가능 방향

**생존 불가능한 방향** (WALT에 완전 subsume):

- ❌ "KG가 site-specific functionality를 제공한다" — WALT가 더 잘 함
- ❌ "URL pattern으로 navigation 가속" — WALT URL promotion이 우수
- ❌ "Site의 구조적 지식을 agent에 제공" — WALT tool discovery가 더 실용적

**생존 가능한 방향** (WALT가 다루지 않는 영역):

- ✅ **Cross-tool connectivity (graph)** — WALT는 tool 독립적. "tool A 다음에 어떤 tool?"이라는 관계 지식은 미다룸
- ✅ **State invariants / conditional availability** — WALT tool은 항상 사용 가능하다 가정. "이 action은 로그인 후에만 가능"같은 조건부 지식 없음
- ✅ **Low-cost variant** — WALT는 GPT-5 기반으로 자동화 비용 높음. KG는 crawl + cheap LLM으로 저비용. **"1/10 비용으로 유사 성능"** framing 가능

### 7.4 재설계 옵션 재평가

| 옵션                          | WALT 충돌 여부 | 평가                                             |
| ----------------------------- | -------------- | ------------------------------------------------ |
| SteP-style policy library     | 부분 충돌      | WALT tool이 상위 개념. SteP 정도 접근은 marginal |
| Graph-guided policy selection | 충돌 적음      | Tool 간 전이 관계를 graph로 → 가능성 있음        |
| Low-cost KG + weak LLM        | 충돌 없음      | Novelty는 약하지만 실용성 방어                   |
| KG as site audit tool         | 충돌 없음      | WALT가 할 수 없는 "무엇이 비어있나" 점검         |

### 7.5 Benchmark bar 재조정

- WALT WebArena GitLab **57.0%**
- 현실적 max (GPT-4o-mini + baseline executor + KG): ~30-35%
- **절대 성능 경쟁 포기** 권고. relative gain (baseline + α) 또는 **cost-efficiency** framing으로 전환

### 7.6 `lessons_learned_kg_v2.md` 업데이트 필요

- §7.4 (데이터 원칙) 14번 "manual seed 실질 채움"에 대한 WALT 대조 추가:
  - "WALT가 보여준 바: manual seed 없이도 iterative demonstrate-generate-validate로 비슷한 품질 도달 가능 (66% human vs 64.1% auto)"
- §7.2 (아키텍처) 7번 "Hook A context-aware"에 WALT의 agentic fallback 패턴 참고로 추가

---

## 8. Reviewer-proof 관점

**예상 공격**:

> "WALT가 이미 site functionality를 reverse-engineering하여 tool로 노출합니다. 귀하의 KG는 WALT의 덜 성숙한 버전 아닌가요?"

**방어 3축**:

1. **Cost**: WALT는 GPT-5 기반 + iterative validation으로 site당 구축 비용 높음. KG는 훨씬 저렴
2. **Orthogonal info**: KG는 tool 간 전이 관계(graph structure)를 제공. WALT tool 호출을 "어떤 순서로" 할지 guide 가능
3. **Audit**: KG는 WALT 같은 tool 라이브러리의 커버리지 평가 도구로 사용 가능

→ 방어 2·3축이 성립하려면 **재설계가 그 방향으로 수렴**해야 함. 단순 "URL shortcut을 재구현"하면 방어 실패.

---

## 9. 불확실한 부분 / 추가 확인 필요

- WALT의 **site당 tool discovery 비용** (얼마나 오래, $ 얼마) — 논문 본문에 명시 없음
- **Tool 간 composition의 한계**: 5개 call로 task 해결, 10+ step task는?
- **Visual-only tool** (이미지 기반 filter) 지원 여부
- **사용자 task scope 밖** functionality를 발견하면 어떻게 되나 (over-discovery)

---

## 10. 한줄 정리

> WALT = **2025-10 WebArena non-training SOTA (50.1%)**. Iterative demonstrate-generate-validate로 50+ deterministic tool 자동 발견. 이 프로젝트의 "KG URL shortcut" 아이디어를 **근본적으로 subsume**. 재설계가 WALT와 정면 충돌 회피하려면 **tool 간 connectivity graph**, **state invariants**, 또는 **low-cost framing** 방향으로 전환 필수. 절대 성능 경쟁은 포기하고 **직교적 기여**로 포지셔닝해야 함.
