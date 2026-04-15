**“AI Agent Engineering의 표준 아키텍처”는 2026년 현재 ISO 같은 공식 표준이 있는 것은 아니고**, 최근 논문·서베이·공식 엔지니어링 문서들에서 반복적으로 등장하는 공통 블록을 묶은 **de facto reference architecture(사실상 참조 아키텍처)** 로 이해하는 것이 가장 정확하다. 특히 최근 서베이들은 에이전트를 **foundation model + planning/reasoning + memory + tool use + verification/safety**의 시스템으로 정리하고, Anthropic도 실제 성공 사례를 **simple, composable patterns** 중심으로 설명한다. 또 MAP(Measuring Agents in Production)는 실제 배포형 에이전트들이 대체로 복잡한 완전자율 구조보다 **통제 가능한 단순 구조**를 사용한다고 보고한다. ([arXiv][1])

아래 도식은 그 문헌들을 바탕으로 정리한 **가장 표준적인 AI Agent Engineering 참조 아키텍처**다.

```text
[User / Upstream System]
          |
          v
+---------------------------+
|  Goal / Task Interpreter  |
|  - 요청 해석              |
|  - 성공조건/제약 추출     |
+---------------------------+
          |
          v
+---------------------------+
|   Planner / Controller    |
|  - 계획 수립              |
|  - 다음 행동 선택         |
|  - 재계획(re-plan)        |
+---------------------------+
      |         |         \
      |         |          \
      |         |           \
      v         v            v
+-----------+ +-----------+ +----------------+
|  Memory   | |   Tools   | |  Guardrails    |
| - session | | - search  | | - policy check |
| - episodic| | - code    | | - permission   |
| - longterm| | - APIs    | | - validation   |
+-----------+ +-----------+ +----------------+
      \         |            /
       \        |           /
        \       v          /
         +----------------+
         |  Executor      |
         | - tool call    |
         | - env action   |
         +----------------+
                  |
                  v
         +----------------+
         |  Observation   |
         | - tool result  |
         | - env state    |
         | - traces/logs  |
         +----------------+
                  |
                  v
         +----------------+
         | Evaluator /    |
         | Critic / Judge |
         | - success?     |
         | - grounded?    |
         | - safe?        |
         +----------------+
                  |
        +---------+----------+
        |                    |
      pass                 fail
        |                    |
        v                    v
+----------------+   +----------------------+
| Final Response |   | Recovery / Re-plan   |
| / Commit       |   | / Human Handoff      |
+----------------+   +----------------------+
```

이 구조의 핵심은 **Planner가 중심에서 Memory, Tools, Guardrails, Evaluator를 오케스트레이션**한다는 점이다. ReAct는 추론과 행동을 교차시키는 구조를 보여줬고, Toolformer는 모델이 **언제 도구를 쓸지, 어떤 인자를 넣을지** 결정하는 방향을 제시했으며, Reflexion은 실패 경험을 기억으로 남겨 이후 시도에 반영하는 메모리형 루프를 제안했다. 최근 서베이도 비슷하게 agent core, memory, planner, tool router, critic 같은 블록으로 에이전트 시스템을 정리한다. ([arXiv][2])

---

## 1) Planner: 에이전트의 “두뇌”이자 제어기

Planner는 사용자 목표를 **실행 가능한 하위 단계(subtasks)** 로 쪼개고, 현재 관측 결과를 바탕으로 **다음 행동(next action)** 을 선택한다. 이 블록은 단순 체인형 workflow일 수도 있고, 상황에 따라 계획을 바꾸는 동적 controller일 수도 있다. Anthropic은 이 차이를 **workflow vs. agent**로 구분하면서, agent는 LLM이 스스로 프로세스와 도구 사용을 결정하는 시스템이라고 설명한다. ReAct 역시 reasoning trace가 행동 계획을 유도·수정하고 예외를 처리하는 데 도움을 준다고 보여준다. ([Anthropic][3])

실무적으로 Planner가 하는 일은 보통 네 가지다.
첫째, **goal decomposition**: 큰 목표를 작은 단계로 분해한다.
둘째, **action selection**: 지금 시점에 어떤 도구를 어떤 순서로 쓸지 고른다.
셋째, **state-aware replanning**: 관측 결과가 예상과 다르면 계획을 수정한다.
넷째, **termination decision**: 충분한 근거가 모였는지, 더 진행해야 하는지, 인간에게 넘겨야 하는지 결정한다. 최근 agent systems survey도 planning/control을 reactive policy부터 hierarchical multi-step planner까지 하나의 핵심 축으로 정리한다. ([arXiv][1])

핵심 포인트는 Planner가 “생각만” 하는 블록이 아니라는 점이다. 좋은 Planner는 반드시 **관측 결과와 evaluator 피드백을 받아 계획을 수정하는 폐루프(closed loop)** 로 동작해야 한다. 그래서 Agent Engineering에서 Planner는 단순 프롬프트 한 장이 아니라, **상태 기반 제어기(controller)** 에 가깝다. ([arXiv][2])

---

## 2) Memory: 에이전트가 같은 실수를 반복하지 않게 하는 층

Memory는 대개 세 층으로 나뉜다.

```text
Memory
 ├─ Working / Context Memory
 │   - 현재 턴의 목표, 중간 결과, 최근 관측
 ├─ Episodic Memory
 │   - 이전 실행의 실패/성공 경험, reflection, trace
 └─ Long-term / Knowledge Memory
     - 사용자 선호, 도메인 지식, 사전 온보딩 정보
```

Reflexion은 이 중 **episodic memory**의 중요성을 대표적으로 보여준다. 이 연구는 실행 후 얻은 피드백을 언어적 reflection으로 저장하고, 다음 시도에서 그 반성 내용을 문맥으로 넣어 더 나은 행동을 유도했다. 즉, 메모리는 단순 대화 기록이 아니라 **정책 개선을 위한 실행 경험 저장소**가 될 수 있다. ([arXiv][4])

실무에서는 보통
**working memory**에는 현재 목표, 제약, 중간 산출물, 최근 tool outputs를 두고,
**episodic memory**에는 실패 패턴, 회복 전략, 이전 trajectory 요약을 두며,
**long-term memory**에는 사용자 선호, 자주 쓰는 절차, 사이트/도메인 priors 같은 재사용 가능한 지식을 둔다. 최신 survey도 memory를 agent systems의 독립된 핵심 구성요소로 다루며, context growth와 memory management를 주요 과제로 지적한다. ([arXiv][5])

중요한 점은 **메모리를 많이 넣는다고 항상 좋은 것이 아니라는 것**이다. MAP 연구와 Anthropic의 실무 문서는 둘 다 지나치게 복잡한 구조보다 **필요한 범위의 단순하고 통제 가능한 구성**이 실전에서 더 잘 작동한다고 시사한다. 그래서 좋은 memory 설계는 “많이 저장”보다 **무엇을 언제 저장하고 언제 읽을지**를 분명히 하는 데 있다. ([arXiv][6])

---

## 3) Tools: LLM을 “말하는 모델”에서 “일하는 시스템”으로 바꾸는 층

Tools는 검색, 브라우징, 계산, 코드 실행, 데이터베이스 조회, 외부 API 호출, 파일 조작 같은 **외부 능력**을 제공한다. Toolformer는 모델이 스스로 **언제 API를 호출할지, 어떤 인자를 보낼지, 결과를 어떻게 활용할지** 학습할 수 있음을 보여줬고, Anthropic도 practical agent의 핵심 building block을 **retrieval + tools + memory**로 설명한다. ([arXiv][7])

도구 설계에서 중요한 것은 단순히 “도구가 많다”가 아니다. SWE-agent는 성능 차이가 모델뿐 아니라 **ACI(Agent-Computer Interface)** 에서 크게 난다고 보여줬다. 즉, 파일 시스템·검색·편집·실행 같은 기능을 에이전트에게 **어떤 추상화 수준으로 노출하느냐**가 성능을 좌우한다. 너무 로우레벨이면 계획은 자유롭지만 실행이 불안정해지고, 너무 하이레벨이면 유연성이 떨어진다. ([arXiv][8])

그래서 표준적인 tool layer는 보통 이렇게 나뉜다.

```text
Tools
 ├─ Information tools
 │   - web search, retrieval, DB query
 ├─ Action tools
 │   - browser actions, API POST/PUT, file write
 ├─ Compute tools
 │   - calculator, code execution, SQL, scripts
 └─ Communication tools
     - email, calendar, messaging, ticketing
```

실무에서는 이 도구들을 그대로 Planner에 노출하기보다, **명세화된 schema**로 감싸는 경우가 많다. 즉 각 tool마다 입력 파라미터, 권한 범위, 부작용 정도, 실패 시 반환 형식, 재시도 가능성 같은 메타데이터를 둔다. 이렇게 해야 Planner, Guardrails, Evaluator가 도구 결과를 안정적으로 해석할 수 있다. 이 방향은 Toolformer의 tool-call 구조, SWE-agent의 ACI, 그리고 최근 system survey가 말하는 tool router 관점과 잘 맞는다. ([arXiv][7])

---

## 4) Guardrails: “할 수 있음”과 “해도 됨”을 분리하는 층

Guardrails는 에이전트가 능력이 있어도 **해선 안 되는 행동**을 막는 계층이다. 여기에는 권한 확인, 정책 검사, 민감 작업 승인, 형식 검증, 범위 제한, rate limit, 부작용 큰 action에 대한 human approval 같은 요소가 들어간다. AgentSpec은 이런 제약을 **runtime enforcement**로 명시해, 규칙 기반으로 예방적·교정적 제한을 걸 수 있음을 보여준다. ([arXiv][9])

Guardrails는 보통 세 단계로 작동한다.

```text
Pre-action guardrail
- 이 행동이 허용된 범위인가?
- 이 툴/리소스에 접근 권한이 있는가?

In-action guardrail
- 실행 중 정책 위반 조짐이 있는가?
- 위험 파라미터가 감지되는가?

Post-action guardrail
- 결과가 민감정보를 포함하는가?
- 외부 전송/커밋 전 추가 승인이 필요한가?
```

최근 production 및 research 문헌에서 반복되는 메시지는, 안전성은 모델 내부 alignment만으로 충분하지 않다는 것이다. Anthropic의 multi-agent engineering 글은 명시적 guardrails와 observability를 강조하고, AgentSpec은 런타임 수준 제약이 안전성과 신뢰성에 실용적이라고 주장한다. 즉, guardrail은 “응답 문구 필터”가 아니라 **행동 제어 시스템**이어야 한다. ([Anthropic][10])

실전에서 특히 중요한 것은 **고위험 행동(high-impact action)** 을 분리하는 것이다. 예를 들어 “읽기(read)”와 “쓰기(write)”, “초안 생성(draft)”과 “실제 전송(commit)”은 동일한 tool이라도 다른 권한 정책을 가져야 한다. MAP가 보여주듯 실제 배포형 에이전트는 대체로 제한된 단계 수와 인간 개입을 두며, 이는 guardrail 설계가 현실에서 핵심임을 보여준다. ([arXiv][6])

---

## 5) Evaluator: 결과가 정말 맞는지 확인하는 층

Evaluator는 agent의 결과를 채점하는 블록이다. 이 블록이 없으면 에이전트는 “그럴듯하게 끝냈다”고 말해도 실제로는 틀렸을 수 있다. 최근 서베이와 Anthropic evals 문서는 둘 다 agent 개발에서 eval이 배포 전 테스트가 아니라 **지속적 개발·운영의 중심 기능**이어야 한다고 강조한다. ([arXiv][1])

Evaluator는 보통 네 가지를 본다.

```text
Evaluator / Critic
 ├─ Task success
 │   - 요청한 목표를 달성했는가?
 ├─ Grounding / correctness
 │   - 결과가 도구 출력/환경 상태와 일치하는가?
 ├─ Constraint satisfaction
 │   - 시간, 비용, 정책, 포맷 제약을 지켰는가?
 └─ Confidence / uncertainty
     - 확실한가? 추가 확인이 필요한가?
```

이때 evaluator는 단순 LLM judge일 수도 있지만, 더 신뢰할 수 있는 방식은 **규칙 기반 검증 + 구조화된 체크 + 필요 시 모델 기반 보조 판정**의 조합이다. Anthropic의 eval guidance는 자동화된 eval을 통해 문제를 개발 단계에서 드러내야 한다고 설명하고, 웹 에이전트 분야에서는 WebArena와 Mind2Web 같은 벤치마크가 실제 성공 여부를 평가하는 역할을 한다. 다만 Online-Mind2Web이나 WebArena Verified 계열 논의가 보여주듯, **평가기 자체가 잘못 설계되면 성능을 과대평가할 수 있다**는 점도 중요하다. ([Anthropic][11])

즉, Agent Engineering에서 Evaluator는 “있으면 좋은 부가 기능”이 아니라, Planner와 대등한 핵심 블록이다. Planner가 행동을 만들고, Evaluator가 그 행동이 **정말 맞는지** 판정하며, 실패 시 recovery나 human handoff를 트리거한다. ([arXiv][5])

---

## 6) 다섯 블록이 실제로 연결되는 런타임 루프

실행 흐름은 보통 아래처럼 돈다.

```text
1. Goal intake
   사용자 요청과 성공조건을 구조화

2. Plan
   Planner가 현재 상태 기준 다음 단계 선택

3. Retrieve memory
   관련 과거 경험/선호/중간 상태 불러오기

4. Select tool
   필요한 도구와 인자를 선택

5. Pre-check
   Guardrail이 권한/정책/위험도 검사

6. Execute
   툴 호출 또는 환경 행동 수행

7. Observe
   결과, 로그, 에러, 환경 변화 수집

8. Evaluate
   목표 달성/정확성/정책 만족 여부 판정

9. Update memory
   성공/실패 패턴과 중간 산출물 저장

10. Decide
   종료 / 재계획 / 복구 / 인간에게 이관
```

이 루프는 ReAct의 “reason-act-observe” 패턴을 더 공학적으로 확장한 형태라고 볼 수 있다. 여기에 Reflexion의 memory 업데이트, Toolformer식 도구 결정, AgentSpec식 제약 집행, Anthropic식 eval/observability가 합쳐지면 오늘날의 reference agent loop가 된다. ([arXiv][2])

---

## 7) 가장 실무적인 형태로 다시 압축하면

논문과 실무 문서를 함께 보면, 실제로 많이 쓰이는 “표준형”은 아래 두 버전으로 나뉜다.

### A. 최소 표준형

```text
Planner
  -> Tools
  -> Evaluator
  -> Final response
```

이 구조는 비교적 단순한 QA, search, report generation에 적합하다. Anthropic과 MAP가 공통적으로 보여주듯, 실제 현장에서는 이런 **작고 통제 가능한 구조**가 자주 성공한다. ([Anthropic][3])

### B. 운영형 표준형

```text
Planner
  <-> Memory
  -> Tools
  -> Guardrails
  -> Evaluator
  -> Recovery / Human handoff
```

이 구조는 장기 작업, 외부 시스템 쓰기, 웹 탐색, 코드 수정, 업무 자동화처럼 실패 비용이 높은 작업에 적합하다. 최근 survey들이 정리하는 agent systems의 전형적인 구성도 이 운영형에 가깝다. ([arXiv][1])

---

## 8) 블록별로 “무엇을 넣으면 되는가”

실제로 시스템 설계할 때는 이렇게 생각하면 된다.

**Planner**
무엇을 할지 정한다.
하위 작업 분해, 다음 행동 선택, 재계획, 종료 결정이 들어간다. ([arXiv][2])

**Memory**
무엇을 기억할지 정한다.
현재 상태, 이전 실패/성공 경험, 장기 선호/도메인 지식이 들어간다. ([arXiv][4])

**Tools**
무엇을 할 수 있게 만들지 정한다.
검색, 계산, 브라우징, 코드 실행, 외부 시스템 조작 등이 들어간다. ([arXiv][7])

**Guardrails**
무엇을 하지 못하게 할지 정한다.
권한, 정책, 민감작업 승인, 부작용 제한이 들어간다. ([arXiv][9])

**Evaluator**
무엇을 성공으로 볼지 정한다.
정확성, groundedness, 제약 준수, 비용/시간 만족, 신뢰도 판정이 들어간다. ([Anthropic][11])

---

## 9) 한 문장으로 정리

**AI Agent Engineering의 표준 아키텍처는, Planner가 Memory를 참고해 Tools를 선택하고, Guardrails가 행동을 제약하며, Evaluator가 결과를 판정하고, 실패 시 Recovery/Handoff로 되돌리는 폐루프 시스템**이라고 보면 된다. 이건 ReAct, Toolformer, Reflexion, SWE-agent, AgentSpec, 최근 agent systems survey, 그리고 실제 배포 연구 MAP가 서로 다른 각도에서 공통적으로 뒷받침하는 구조다. ([arXiv][2])

[1]: https://arxiv.org/html/2601.01743v1?utm_source=chatgpt.com "AI Agent Systems: Architectures, Applications, and Evaluation"
[2]: https://arxiv.org/abs/2210.03629?utm_source=chatgpt.com "ReAct: Synergizing Reasoning and Acting in Language Models"
[3]: https://www.anthropic.com/research/building-effective-agents?utm_source=chatgpt.com "Building Effective AI Agents"
[4]: https://arxiv.org/abs/2303.11366?utm_source=chatgpt.com "Reflexion: Language Agents with Verbal Reinforcement ..."
[5]: https://arxiv.org/abs/2601.01743?utm_source=chatgpt.com "AI Agent Systems: Architectures, Applications, and Evaluation"
[6]: https://arxiv.org/abs/2512.04123?utm_source=chatgpt.com "Measuring Agents in Production"
[7]: https://arxiv.org/abs/2302.04761?utm_source=chatgpt.com "Toolformer: Language Models Can Teach Themselves to Use Tools"
[8]: https://arxiv.org/abs/2405.15793?utm_source=chatgpt.com "SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering"
[9]: https://arxiv.org/abs/2503.18666?utm_source=chatgpt.com "AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents"
[10]: https://www.anthropic.com/engineering/built-multi-agent-research-system?utm_source=chatgpt.com "How we built our multi-agent research system"
[11]: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents?utm_source=chatgpt.com "Demystifying evals for AI agents"
