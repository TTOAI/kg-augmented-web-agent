**최근 웹 에이전트 논문들은 공통적으로 `perception → planning & reasoning → execution` 골격을 유지하지만, 실제 제안 아키텍처는 하나로 수렴하지 않았습니다.** 대신 대표 논문들을 보면, 어떤 논문은 **멀티모달 단일 에이전트**, 어떤 논문은 **계층형/멀티에이전트**, 어떤 논문은 **트리서치·월드모델 기반 계획기**, 또 어떤 논문은 **메모리·가이드라인·평가기 결합형**을 채택합니다. WebAgents 서베이도 아키텍처를 perception, planning & reasoning, execution으로 정리하면서, planning 안에 task planning, action reasoning, memory utilization이 포함된다고 설명합니다. ([arXiv][1])

또 하나 중요한 점은, 최근 논문들이 “좋은 웹 에이전트”를 만드는 방식이 꽤 갈린다는 것입니다. AgentOccam 논문이 정리한 비교표를 보면, SteP, AutoGuide, AWM, WebPilot, Agent-E 등은 각각 **task-specific strategies, in-context examples, additional modules, offline data, online search**를 서로 다르게 채택하고 있고, 반대로 AgentOccam은 그런 보조 모듈 없이 **observation/action space 자체를 정렬하는 단순 구조**를 밀고 있습니다. 즉 최근 연구는 “정답 아키텍처 1개”보다는, **어디를 강화할 것인가**에 따라 서로 다른 구조를 채택하는 국면입니다. ([arXiv][2])

아래에 대표 논문들이 **구체적으로 무엇을 채택했는지** 구조 중심으로 정리해드릴게요.

## 1) 모듈형 파이프라인: 계획기 + HTML 요약기 + 실행기

가장 전형적인 모듈형 구조는 **A Real-World WebAgent with Planning, Long Context Understanding, and Program Synthesis**입니다. 이 논문은 WebAgent가 **(1) 자연어 지시를 하위 sub-instructions로 분해하고, (2) 긴 HTML을 과업 관련 snippet으로 요약하고, (3) 그 결과를 실행 가능한 Python 코드로 바꿔 웹에서 행동**한다고 설명합니다. 구조적으로는 **계획 모듈 + 긴 HTML 이해 모듈 + 프로그램 합성 기반 실행 모듈**을 결합한 형태이고, HTML-T5와 Flan-U-PaLM이라는 **서로 다른 모델을 조합한 modular recipe**를 택했습니다. 즉 이 계열은 “하나의 거대한 agent loop”보다 **역할이 분리된 파이프라인형 웹 에이전트**에 가깝습니다.

## 2) 멀티모달 end-to-end 단일 에이전트

**WebVoyager**는 최근 웹 에이전트 논문들 중에서 가장 대표적인 **멀티모달 단일 에이전트** 계열입니다. 이 논문은 에이전트가 **스크린샷과 상호작용 가능한 요소의 텍스트를 함께 보고**, 다음에 할 행동을 생각한 뒤 클릭·타이핑·스크롤 등을 **끝까지 end-to-end로 수행**한다고 설명합니다. 또한 Set-of-Mark prompting을 써서 **스크린샷 위에 인터랙티브 요소의 박스를 표시**해 의사결정과 grounding을 돕습니다. GUI agent survey에서도 WebVoyager는 **single-agent**이며, **screenshots with numerical labels on interactive elements**를 쓰는 구조로 요약됩니다. 즉 이 계열은 HTML 파싱 중심이 아니라 **렌더링된 페이지를 직접 보고 행동하는 시각 중심 단일 루프형 구조**입니다. ([arXiv][3])

## 3) “행동 생성”과 “grounding”을 분리한 구조

**SeeAct**는 멀티모달이지만 WebVoyager와는 조금 다릅니다. 이 논문은 웹 에이전트의 핵심 능력을 **(i) action generation**과 **(ii) element grounding**으로 명시적으로 나눕니다. 즉 먼저 모델이 “지금 무엇을 해야 하는가”라는 **텍스트 계획/행동 설명**을 만들고, 그다음 현재 화면에서 **그 행동이 적용될 HTML element를 특정**합니다. 논문은 GPT-4V가 **행동 계획 자체는 강하지만 grounding은 여전히 큰 병목**이라고 보고합니다. 그래서 SeeAct 계열은 구조적으로 **멀티모달 단일 에이전트**이면서도, 내부 기능을 **계획 생성과 UI grounding의 2단계로 분리**해 다루는 것이 특징입니다. ([arXiv][4])

## 4) 동적 계층 제어: stack-based / planner–executor 구조

**SteP**는 웹 에이전트를 **동적으로 조합되는 정책 스택**으로 봅니다. SteP는 상태를 “policy stack”으로 정의하고, 매 시점마다 스택 최상단 정책이 **직접 행동하거나, 하위 정책을 호출해 push하거나, 종료하면서 pop**하는 구조를 취합니다. 즉 고정된 계층이 아니라 **동적으로 정책 호출 체인을 구성하는 hierarchical control architecture**입니다. ([arXiv][5])

비슷한 방향이지만 더 명시적인 멀티에이전트 구조를 택한 것이 **Agent-E**입니다. Agent-E는 **hierarchical architecture**, **flexible DOM distillation**, **change observation**을 핵심 개선점으로 내세우고, GUI agent survey에서는 이를 **planner agent + browser navigation agent로 구성된 hierarchical multi-agent architecture**라고 요약합니다. 즉 최근 웹 에이전트 논문들 중 일부는 단일 정책 대신, **상위 planner와 하위 browser executor를 분리하는 계층형 구조**를 채택하고 있습니다. ([arXiv][6])

## 5) 관찰/행동 공간 자체를 손보는 구조

**AutoWebGLM**은 “좋은 웹 에이전트는 planner를 더 복잡하게 만들기보다, 웹을 모델이 읽기 좋게 바꾸는 것이 중요하다”는 방향을 취합니다. 이 논문은 **HTML simplification + OCR**로 관찰을 정리하고, HTML과 스크린샷을 받아 **간결한 simplified HTML representation**을 만든 뒤 행동 예측을 수행합니다. 관찰 공간에는 **task description, simplified HTML, current location, past operation records**를 넣고, 학습도 먼저 **웹을 읽고 조작하는 능력**을 익힌 다음, 그 위에서 **plan & reason**을 배우는 2단계 curriculum을 둡니다. 즉 구조적으로는 **single-agent + observation preprocessor + training-based capability shaping** 계열입니다. ([arXiv][7])

**AgentOccam**은 이 방향을 더 밀어붙입니다. 이 논문은 많은 prior work가 compound policy나 보조 모듈에 의존한다고 비판하면서, 자신들은 **action space alignment**와 **observation space alignment**만으로 성능을 끌어올린다고 주장합니다. 구체적으로는 불필요한 action을 줄이고, **note / stop / branch / prune** 같은 **workflow management 및 planning actions**를 추가하며, observation 쪽에서는 페이지를 더 읽기 쉬운 형태로 압축하고 **planning tree를 이용해 memory를 더 간결하게 유지**합니다. 즉 AgentOccam은 “복잡한 멀티모듈 시스템”보다 **LLM 친화적 interface 설계**를 핵심 아키텍처로 채택한 사례입니다. ([arXiv][2])

## 6) inference-time search를 붙이는 구조

최근 2024년 이후의 큰 흐름 중 하나는 **agent 본체 위에 search layer를 얹는 것**입니다. **Tree Search for Language Model Agents**는 base LM agent는 그대로 두고, 그 위에 **best-first tree search**를 얹어 실제 interactive web environment 안에서 **여러 action branch를 탐색**하게 합니다. 이 논문은 자신의 방법이 대부분의 기존 base agent와 **complementary**하다고 말하고, 실제로 value function을 써서 현재 상태의 기대 보상을 추정하며, LM agent가 다음 branch 후보 action을 제안하는 구조를 채택합니다. 즉 이것은 **reactive agent + inference-time planner/search wrapper** 구조입니다. ([arXiv][8])

## 7) 글로벌 계획 + 로컬 탐색을 분리한 멀티에이전트 구조

**WebPilot**은 search 계열 중에서도 더 복합적인 구조를 택합니다. 이 논문은 **multi-agent system with a dual optimization strategy**라고 직접 설명하며, 먼저 **Global Optimization** 단계에서 과업을 하위 subtask로 분해하고 관찰과 이전 시도를 바탕으로 plan을 계속 고칩니다. 그다음 **Local Optimization** 단계에서 각 subtask를 **tailored MCTS**로 해결합니다. 즉 WebPilot은 구조적으로 **고수준 planner + 저수준 MCTS executor**를 결합한 계층형 멀티에이전트 구조라고 볼 수 있습니다. ([arXiv][9])

## 8) 월드모델을 넣는 model-based planning 구조

**WebDreamer**는 최근 논문들 중에서 가장 뚜렷하게 새로운 planning 구조를 제안합니다. 이 논문은 reactive approach 대신, 행동 전에 LLM으로 **“이 버튼을 누르면 무슨 일이 일어날까?”**를 자연어로 시뮬레이션하게 하고, 그 결과 trajectory를 scoring해서 최적 행동을 고르는 **model-based planning**을 채택합니다. 논문 표현대로는, WebDreamer는 LLM을 **simulation function + scoring function**으로 사용해 candidate action마다 **imagined outcome**을 만든 뒤 가장 좋은 action을 실행합니다. 즉 이 계열은 tree search처럼 실제 웹에서 분기 탐색을 많이 하는 대신, **머릿속 시뮬레이션으로 계획을 세운 뒤 한 번만 실제 행동**하는 구조입니다. ([arXiv][10])

## 9) 메모리/경험 재사용 구조

최근 논문들 중 일부는 웹 에이전트를 “매번 새로 푸는 시스템”이 아니라 **경험을 축적하는 시스템**으로 봅니다. **AutoGuide**는 offline trajectories에서 **context-aware guidelines**를 뽑아내는 구조를 택합니다. 구체적으로는 **context identification module**과 **guideline extraction module**이 contrastive trajectories에서 “어떤 상황에서 어떤 행동 규칙이 유효한가”를 자연어 guideline으로 추출하고, 테스트 시 현재 상태와 맞는 guideline만 prompt에 넣습니다. 즉 구조적으로는 **base agent + retrieval-style policy guidance memory**입니다. ([arXiv][11])

**AWM (Agent Workflow Memory)**은 더 직접적으로 **workflow memory**를 만듭니다. 이 논문은 agent trajectories에서 **재사용 가능한 common routine**을 workflow로 추출하고, 이를 agent memory에 저장해 다음 과업을 안내합니다. 각 workflow는 하나의 goal과 공통 실행 루틴을 표현하고, 더 단순한 workflow를 바탕으로 더 복잡한 workflow를 쌓아가는 **continual memory architecture**를 지향합니다. 즉 AWM 계열은 웹 에이전트 구조에 **long-term procedural memory layer**를 명시적으로 추가한 경우입니다. ([arXiv][12])

## 10) evaluator를 루프 안에 넣는 구조

**Autonomous Evaluation and Refinement of Digital Agents**는 planning 자체보다 **evaluation loop**를 중심으로 구조를 짭니다. 이 논문은 **model-based evaluator**가 agent trajectory를 평가하고, 그것을 **Reflexion의 reward/evaluator**로 쓰거나 **filtered behavior cloning**에 활용해 성능을 개선한다고 설명합니다. 부록에서는 Reflexion 구조를 **Actor + Evaluator + Self-Reflection module**로 명시하고, evaluator가 실패라고 판단하면 self-reflection이 메모리에 들어가 다음 시도를 개선한다고 설명합니다. 즉 이 계열은 웹 에이전트 본체 위에 **외부 평가기와 자기반성 루프를 얹는 evaluator-in-the-loop architecture**입니다. ([arXiv][13])

## 11) 브라우저만이 아니라 API까지 쓰는 hybrid 구조

최근에는 “웹 에이전트는 꼭 브라우저만 써야 하나?”를 묻는 흐름도 있습니다. **Beyond Browsing: API-Based Web Agents**는 **Browsing Agent**, **API-Based Agent**, **Hybrid Agent**를 비교하고, Hybrid Agent가 **API calling과 web browsing을 interleave**하도록 설계합니다. 논문은 API-Based Agent가 essentially **CodeAct architecture**를 사용한다고 말하고, Hybrid Agent는 상황에 따라 **API와 브라우징 사이를 전환**해 둘을 함께 씁니다. 즉 최근 일부 연구는 웹 에이전트 구조를 **GUI 조작기**로만 보지 않고, **browser + API tool router**로 확장하고 있습니다. ([arXiv][14])

## 종합하면, 최근 논문들이 실제로 채택한 구조는 이렇게 정리됩니다

정말 압축해서 말하면 최근 웹 에이전트 논문들은 다음 여섯 갈래로 갈립니다.

첫째, **모듈형 파이프라인**입니다. 계획, 긴 HTML 이해, 실행을 분리합니다. WebAgent가 대표적입니다.

둘째, **멀티모달 단일 에이전트**입니다. 스크린샷과 UI 텍스트를 함께 보고 end-to-end로 행동합니다. WebVoyager와 SeeAct가 대표적입니다. ([arXiv][3])

셋째, **계층형/멀티에이전트 제어**입니다. planner와 executor를 분리하거나, 정책을 동적으로 중첩합니다. SteP, Agent-E, WebPilot이 여기에 들어갑니다. ([arXiv][5])

넷째, **search/model-based planning**입니다. reactive next-action 대신 트리 탐색이나 월드모델 시뮬레이션으로 여러 경로를 비교합니다. Tree Search for LM Agents와 WebDreamer가 대표적입니다. ([arXiv][8])

다섯째, **memory/guideline/evaluator augmentation**입니다. 경험에서 규칙을 뽑아 쓰거나, workflow memory를 쌓거나, evaluator를 루프 안에 넣어 실패를 교정합니다. AutoGuide, AWM, Autonomous Evaluation and Refinement가 이 계열입니다. ([arXiv][11])

여섯째, **hybrid tool-use 구조**입니다. 브라우저 조작만 하지 않고 API까지 함께 씁니다. Beyond Browsing이 대표적입니다. ([arXiv][14])

즉, 최근 웹 에이전트 논문들이 채택한 구조를 한 문장으로 정리하면 이렇습니다.

**공통 골격은 여전히 perception → planning/reasoning → execution이지만, 실제 최신 논문들은 여기에 멀티모달 관찰, 계층 제어, 검색/시뮬레이션 기반 계획, 경험 메모리, 외부 평가기, API 도구 사용을 각각 다른 방식으로 얹는 방향으로 분화되고 있다**고 보는 것이 가장 정확합니다. ([arXiv][1])

[1]: https://arxiv.org/html/2503.23350v4 "A Survey of WebAgents: Towards Next-Generation AI Agents for Web Automation with Large Foundation Models"
[2]: https://arxiv.org/html/2410.13825v2 "AgentOccam: A Simple Yet Strong Baseline for LLM-Based Web Agents"
[3]: https://arxiv.org/html/2401.13919v3 "WebVoyager : Building an End-to-End Web Agent with Large Multimodal Models"
[4]: https://arxiv.org/html/2401.01614v1 "GPT-4V(ision) is a Generalist Web Agent, if Grounded"
[5]: https://arxiv.org/html/2310.03720v4 "Untitled Document"
[6]: https://arxiv.org/abs/2407.13032?utm_source=chatgpt.com "Agent-E: From Autonomous Web Navigation to Foundational Design Principles in Agentic Systems"
[7]: https://arxiv.org/html/2404.03648v1 "AutoWebGLM: Bootstrap And Reinforce A Large Language Model-based Web Navigating Agent"
[8]: https://arxiv.org/html/2407.01476v4 "Tree Search for Language Model Agents"
[9]: https://arxiv.org/html/2408.15978v1 "WebPilot: A Versatile and Autonomous Multi-Agent System for Web Task Execution with Strategic Exploration"
[10]: https://arxiv.org/html/2411.06559v1 "Is Your LLM Secretly a World Model of the Internet? Model-Based Planning for Web Agents"
[11]: https://arxiv.org/html/2403.08978v2 "AutoGuide: Automated Generation and Selection of Context-Aware Guidelines for Large Language Model Agents"
[12]: https://arxiv.org/html/2409.07429v1 "Agent Workflow Memory"
[13]: https://arxiv.org/html/2404.06474v1 "Autonomous Evaluation and Refinement of Digital Agents"
[14]: https://arxiv.org/html/2410.16464v3 "Beyond Browsing: API-Based Web Agents"
