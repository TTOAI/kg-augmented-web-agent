# SteP — 분석 노트

**출처**: Sodhi, Branavan, Artzi, McDonald, "SteP: Stacked LLM Policies for Web Actions", **COLM 2024** (arXiv:2310.03720v4, 2024-08)
**소속**: ASAPP Research + Cornell
**분량**: 33 pages (본문 + 부록)
**Code**: https://asappresearch.github.io/webagents-step

---

## 1. 핵심 아이디어

**Policy 라이브러리를 stack으로 관리하는 MDP**. 모든 policy는 실행 중 **다른 policy를 동적으로 호출** 가능 (자기 자신 포함). 상태 = stack of active policies.

- 기존 hierarchical planning: 2-3 level 정적 계층에 제한
- SteP: 임의 policy가 임의 policy를 invoke → 재귀/유연성 확보

### 예시 (Figure 1)
Task: "Find all commits by `<user>` across all repositories"
- `search_list(repos)` → iterates repos → 각 repo에서 `search_list(commits)` 재귀 호출
- Policy stack: `[search_list(repos), search_list(commits)]` → pop 후 return

---

## 2. 메커니즘

### 2.1 Policy Stack Model
- **State**: MDP state augmented with stack Σ = ⟨π₀|π₁|...|πᵢ⟩
- **Action** (top-of-stack policy πᵢ의 선택지):
  1. **Issue action**: 환경에 action 전달 (click/type/...) → 관측 반환
  2. **Invoke policy**: 새 policy를 stack에 push
  3. **Terminate**: 현재 policy를 pop + return value를 이전 policy 기록에 추가

### 2.2 Policy 정의
- **Templated prompt**: 일반 instruction + action space 정의 + policy-specific 예시
- Policy = **functionally equivalent intent cluster** (예: "search over orders / list products" = 1 policy)
- WebArena용 policy 14개 수동 설계 (Appendix A.2)
  - `find_page`, `search_list`, `fill_form`, `web_agent`, `cms_agent` 등
- **Policy는 자연어 prompt 단위**이지, 코드/API/그래프 아님

### 2.3 실행 모델
- 매 step에서 stack top policy가 ReAct(Yao et al. 2022b) style로 action 생성
- in-context 예시 2-3개
- Model: `gpt-4-turbo` (WebArena), `text-davinci-003` (MiniWob++)

---

## 3. 성능 수치

### 3.1 WebArena 804 tasks (GPT-4-turbo)

| Method | 전체 | Shopping | CMS | Reddit | GitLab | Maps |
|---|---|---|---|---|---|---|
| Zhou et al. 2023 (SOTA) | 14.9% | 14% | 11% | 6% | 15% | 16% |
| Akter et al. 2023 | 15.3% | 20% | 10% | 11% | 14% | 15% |
| Flat-4k (baseline) | 20% | 28% | 17% | 17% | 20% | 20% |
| Flat-8k (baseline) | 23% | 30% | 18% | 30% | 23% | 20% |
| **SteP** | **33.5%** | **37%** | **24%** | **59%** | **32%** | **30%** |

→ SOTA 대비 **+18.6%p**, Flat-8k 대비 **+10%p**
→ 토큰 사용량 **2.3배 적음**

### 3.2 MiniWoB++ (45 tasks, 50 seeds)
- **96%** 성공 (demo trajectory 10개만 사용)
- Comparable to Synapse (98%, 100 trajectories), WebGUM (90%, 347K trajectories)

### 3.3 AirlineCRM (자체 제작 long-horizon)
- 20+ step task에서 일관된 성능

---

## 4. 핵심 분석 요점

### 4.1 왜 단일 policy가 아닌 stack이 유리한가

실험적 발견:
- Flat-4k → Flat-8k (context 2배): 20% → 23% 미미
- 긴 context에서 **attention dilution** → 관련 정보 찾기 실패
- Policy 분해 + stack 호출로 **각 policy가 자기 sub-problem만 봄** → 정확도 ↑ + 비용 ↓

### 4.2 Intent coverage 효과

Shopping에서 policy가 48 intent 중 **50+%를 포괄**하면 SOTA 대비 gain 큼. Reddit (59%) 최고, Maps (30%) 낮음 — policy 커버리지가 작은 카테고리에서 gain 작음.

### 4.3 Zero-shot vs Few-shot

in-context 예시 2-3개가 **ambiguity resolution**에 결정적 (Figure 6):
- Task: "click link 7"에서 "7"이 현재 페이지 index인가, 전체 목록 index인가?
- Few-shot 예시만 있으면 agent가 "페이지 넘기며 count"하는 correct behavior 학습

---

## 5. Survey taxonomy (00_survey_notes.md) 위치

| 축 | SteP 분류 |
|---|---|
| Perception | TT (HTML 기반) |
| Task Planning | **Explicit (policy 자체가 sub-task 분해)** |
| Action Reasoning | **Strategic (SR) — policy composition이 exploration** |
| Memory Utilization | **LTM (policy library가 external knowledge)** |
| Execution | WB (clicking/typing) |
| Grounding | Inferential (HTML id 기반) |

**Survey Table 1에 누락** — 2023-10 v1임에도 포함되지 않음. Aug 2024 v4가 최신이라 등재 시점 놓친 듯. Field에서 중요 method 인식.

---

## 6. 공통 질문 (00 §6) 적용

### 6.1 Memory 축 위치
**LTM (Long-term Memory)**.

### 6.2 LTM 표현 방식
**자연어 prompt 템플릿** (policy = templated prompt). code/graph/API 아님.

### 6.3 Execution 방식
**Web Browsing only**. tool-based execution 아님.

### 6.4 이 프로젝트 "graph-structured LTM" 대비 비교

| 축 | SteP | 과거 SKG v2 |
|---|---|---|
| LTM granularity | **Task/intent level** (search_list, fill_form, ...) | **State level** (URL pattern, InfoType) |
| LTM 표현 | 자연어 prompt | Graph (StatePattern/InfoType/LeadsToEdge) |
| Agent 통제 방식 | **Agent가 policy를 invoke** (자율) | **Hook B가 URL을 강제** (command) |
| 구축 방식 | **수동** 14 policy | Playwright crawl + LLM derivation (자동) |
| Intent coverage | 170 intent 중 50+% 수동 모집 | 37 InfoType 자동 |
| 새 task에 대한 일반화 | Policy recursion으로 자연 composition | Hook A LLM 분류가 오분류 시 실패 |

**중요 관찰**: SteP의 핵심은 **"agent가 policy를 호출"**이지, **"policy가 agent를 명령"**하지 않음.
이것이 이 연구의 Hook B 실패의 반대 방향:
- Hook B: KG → agent에게 URL 명령 → agent 궤도 이탈
- SteP: Agent → policy library 호출 → 자율

`lessons_learned_kg_v2.md` §6.1 (3-coupled defect)의 첫 항목("Hook B = command")이 SteP 관점에서 뚜렷한 설계 오류.

---

## 7. 재설계에 주는 시사점

### 7.1 LTM granularity 재검토

이 연구의 SKG는 **state-level (URL pattern)**에 집중. 하지만 SteP은 **task/intent-level**이 WebArena에서 훨씬 강함을 보임.
→ "StatePattern 그래프"가 아니라 "**policy/skill 라이브러리**" 형태로 KG 재설계 고려 가치.

### 7.2 Agent 주도 vs KG 주도

Hook B style "KG가 agent에게 명령" 패러다임은 잘못됨. SteP처럼 **agent가 KG를 tool처럼 호출**해야 함.
→ 재설계 옵션: KG를 invoke 가능한 policy library로 변환. 각 InfoType을 "이 정보를 얻는 policy"로 매핑.

### 7.3 Hand-crafted vs Automatic

SteP은 **14 policy 수동 설계**로도 33% SUCCESS 달성. 이 프로젝트는 **자동 구축**을 강점으로 삼았지만:
- SteP의 수동 policy가 더 적은 노력으로 더 높은 성능 (이 연구의 baseline ~30% vs SteP 33%)
- 자동 구축의 이점은 **scale**이지 quality 아님
- → 논문 포지셔닝: "**자동 구축 + 유사 성능**" 또는 "**낮은 비용 + 약간 낮은 성능**"

### 7.4 정량 비교 target

SteP 33% WebArena는 **2024년 기준 strong baseline**. 재설계 성공 기준:
- Minimum: baseline(20-30%) + α > SteP (33%) 는 달성 어려움
- Realistic: baseline + KG로 5-10%p lift (20→30% 수준)
- Stretch: SteP 수치 근접/초과하면 강한 contribution

### 7.5 Reviewer-proof 강화

SteP이 있으면 "hand-crafted policy library vs automated KG"라는 **직접 비교 ablation** 필요. 이 연구의 KG가 SteP보다 못하면 "자동화의 이점"을 empirical로 방어해야 함 (예: 새 사이트 추가 비용, scalability 실험).

---

## 8. 재설계 후보 방향 (SteP에서 얻은 힌트)

| 방향 | 설명 | 위험 |
|---|---|---|
| **A. SKG → Policy Library 전환** | InfoType마다 "이걸 얻는 policy"를 자연어 prompt로 매핑 | SteP의 열화 버전 위험 |
| **B. Graph-guided policy selection** | SteP의 policy library 유지, KG는 "어느 policy 호출할까"만 돕는 index | 역할 축소로 contribution 약함 |
| **C. Structured knowledge for policy grounding** | Policy 내부에서 graph의 URL pattern + bindings로 grounding | 기존 SteP policy 수정 필요 |

---

## 9. 불확실한 부분 / 추가 확인 필요

- SteP의 14 policy 설계 **시간/노력 비용** 미보고 (수동 작업량)
- **Out-of-distribution intent**에 대한 behavior (policy 라이브러리 밖 task)
- **Observation/action space 의존성** (HTML id 기반 → SoM / accessibility tree와 비교 필요)
- AgentOccam (45.7% WebArena) 등 **SteP 이후 SOTA 대비 상대 위치** — SteP은 2023-10 방법, 2024-Q4 methods가 더 높음

---

## 10. 한줄 정리

> SteP = **"WebArena의 첫 강한 LLM agent"**. Natural language policy library + dynamic stack composition으로 33% 달성. 이 프로젝트와 가장 큰 차이는 **agent가 KG를 호출**(SteP) vs **KG가 agent를 명령**(과거 SKG v2). **LTM granularity를 state-level에서 task/intent-level로 전환**하는 것이 재설계의 가장 유력한 방향.
