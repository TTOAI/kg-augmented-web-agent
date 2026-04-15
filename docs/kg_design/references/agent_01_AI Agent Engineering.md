## 1) 먼저 결론부터

**AI Agent Engineering**은 2026년 현재 학계에서 완전히 고정된 단일 표준 정의가 있는 용어라기보다, **LLM 기반 에이전트(agentic systems)를 실제로 설계·구현·평가·배포·운영하는 공학적 실천**을 가리키는 신생 개념에 가깝습니다. 실제로 Anthropic은 “agent”라는 말 자체가 여러 방식으로 쓰인다고 설명하고, 최근 연구들은 에이전트를 단순 모델이 아니라 **도구, 메모리, 계획, 평가, 가드레일**까지 포함한 **시스템 수준(system-level)** 대상으로 다룹니다. ([Anthropic][1])

이 자료들을 종합하면, **AI Agent Engineering**은 다음처럼 정의하는 것이 가장 무리가 없습니다.
**“기초 모델(주로 LLM)을 중심에 두고, 도구 사용, 상태/메모리 관리, 계획과 실행, 검증과 평가, 안전 제약과 인간 개입을 결합하여, 목표지향적 다단계 작업을 안정적으로 수행하는 에이전트 시스템을 만드는 공학 분야”**입니다. 이 정의는 단순 프롬프트 작성이 아니라, **확률적 모델을 신뢰 가능한 소프트웨어 시스템으로 바꾸는 일**에 초점을 둡니다. ([arXiv][2])

## 2) 왜 갑자기 중요해졌나

이 분야가 본격화된 직접적 배경은 LLM이 “대답하는 모델”을 넘어 “행동하는 시스템”으로 확장되었기 때문입니다. ReAct는 **추론(reasoning)과 행동(acting)** 을 번갈아 수행하게 만들었고, Toolformer는 모델이 **언제 어떤 API를 어떤 인자로 호출할지** 스스로 결정하는 방향을 보여줬으며, Reflexion은 실행 결과를 언어적 피드백으로 축적해 **에피소드 메모리 기반 개선**이 가능함을 보였습니다. 이후 여러 서베이들은 이런 흐름을 묶어 LLM 에이전트를 하나의 독립 연구 축으로 정리했습니다. ([arXiv][3])

즉, 예전의 “좋은 프롬프트를 만들기”가 중심이었다면, 지금의 Agent Engineering은 **모델이 환경을 관찰하고, 계획을 세우고, 도구를 호출하고, 실패를 복구하고, 결과를 검증하는 전체 루프를 설계하는 것**이 핵심입니다. 그래서 이 분야는 자연어처리만이 아니라 소프트웨어 공학, HCI, 분산 시스템, 보안, 평가 방법론까지 함께 요구합니다. ([arXiv][4])

## 3) AI Agent Engineering의 핵심 구성요소

가장 바닥의 기본 단위는 **augmented LLM**입니다. Anthropic은 agentic system의 기본 블록을 **LLM + retrieval + tools + memory**로 설명합니다. 즉, 모델 자체보다 중요한 것은 모델 주변에 어떤 **외부 능력(capability)** 을 붙여 주느냐입니다. ([Anthropic][1])

그 위에는 **오케스트레이션과 계획 계층**이 있습니다. Anthropic은 **workflow**를 “미리 정한 코드 경로로 LLM과 도구를 조합한 시스템”, **agent**를 “LLM이 스스로 프로세스와 도구 사용을 동적으로 결정하는 시스템”으로 구분합니다. 이 구분은 매우 중요합니다. 왜냐하면 모든 복잡한 LLM 앱이 곧바로 agent는 아니고, 어디까지를 고정 흐름으로 둘지, 어디부터 모델 자율성에 맡길지가 엔지니어링의 핵심 결정이기 때문입니다. ([Anthropic][1])

또 하나의 핵심은 **도구 인터페이스 설계**입니다. SWE-agent는 에이전트 성능이 모델 자체만이 아니라 **ACI(Agent-Computer Interface)** 설계에 크게 좌우된다는 점을 보여줬습니다. 파일을 어떻게 보여줄지, 검색·편집·실행 명령을 어떤 단위로 노출할지, 실패 피드백을 어떻게 돌려줄지가 성능을 바꾼다는 뜻입니다. 그래서 Agent Engineering은 “좋은 모델 선택”만이 아니라 “좋은 작업 인터페이스 설계”까지 포함합니다. ([arXiv][5])

여기에 **메모리와 상태 관리**가 더해집니다. Reflexion은 언어적 피드백을 **episodic memory buffer**에 저장해 다음 시도 의사결정에 반영했고, 최근 서베이들은 이런 메모리·협업·진화 메커니즘을 LLM agent 연구의 핵심 축으로 정리합니다. 즉, agent는 매 호출이 독립인 챗봇이 아니라, **이전 실행 흔적을 활용하는 상태ful 시스템**으로 설계되는 경우가 많습니다. ([arXiv][6])

마지막으로 실전에서는 **검증, 가드레일, 인간 개입**이 필수입니다. Evaluation-Driven Development and Operations 연구는 에이전트 평가를 배포 전 일회성 테스트가 아니라 **라이프사이클 전체를 지배하는 연속 기능**으로 넣어야 한다고 주장합니다. AgentSpec은 에이전트의 자율성이 보안·법규·위험 행동 문제를 낳기 때문에, 런타임 제약을 명시적으로 걸어 **실행 중 안전 경계**를 강제해야 한다고 보여줍니다. ([arXiv][4])

## 4) 이것이 왜 단순한 Prompt Engineering이 아닌가

Prompt Engineering은 주로 **한 번의 입력-출력 품질**을 높이는 기술입니다. 반면 AI Agent Engineering은 **여러 단계의 관찰-판단-행동-검증 루프**를 다루며, 실패 복구, 툴 호출 정책, 승인 흐름, 로그/추적, 메트릭, 실시간 제약까지 포함합니다. 그래서 좋은 agent는 “말을 잘하는 모델”이 아니라, **불완전한 모델을 둘러싼 시스템을 잘 만든 결과물**이라고 보는 편이 맞습니다. ([arXiv][4])

이 점 때문에 최근 연구는 평가도 모델 점수만 보지 않습니다. 2025년 agent evaluation survey는 평가 대상을 **행동, 능력, 신뢰성, 안전성**으로 나누고, 평가 방식도 **벤치마크, 상호작용 모드, 메트릭, 툴링**까지 포함해 체계화해야 한다고 정리합니다. 즉, agent engineering의 품질은 “정답률” 하나로 끝나지 않습니다. ([arXiv][7])

## 5) 실무에서는 어떻게 구현되는가

흥미롭게도 실제 배포 현장에서는 “복잡한 자율 시스템”보다 **단순하고 통제 가능한 구조**가 더 많이 쓰입니다. Anthropic도 가장 성공적인 사례들이 복잡한 프레임워크보다 **simple, composable patterns**를 썼다고 말하며, 가능한 한 단순한 해법에서 시작하라고 권합니다. ([Anthropic][1])

실제 생산 환경 연구인 MAP(Measuring Agents in Production)도 비슷한 결론을 냈습니다. 조사된 배포형 에이전트 중 **68%는 인간 개입 전 10단계 이하만 자율 실행**했고, **70%는 가중치 튜닝보다 오프더셸프 모델 + 프롬프팅**에 의존했으며, **74%는 주된 평가 수단으로 인간 평가**를 사용했습니다. 또한 사례 연구의 **85%가 외부 프레임워크보다 직접 API를 호출하는 커스텀 구현**을 택했습니다. 핵심 이유는 성능 극대화보다 **신뢰성, 단순성, 제어 가능성**이 더 중요했기 때문입니다. ([arXiv][2])

이건 매우 중요한 포인트입니다. 많은 사람들이 agent engineering을 “더 자율적인 AI 만들기”로만 이해하지만, 실제로는 **자율성을 어디까지 제한할지 설계하는 일**이 더 중요합니다. 다시 말해 좋은 agent engineering은 autonomy를 무작정 늘리는 것이 아니라, **업무 위험도에 맞게 자율성과 통제를 정교하게 배합하는 것**입니다. ([arXiv][2])

## 6) 대표 벤치마크와 현재 수준

이 분야를 이해하려면 벤치마크도 같이 봐야 합니다. GAIA는 일반 AI assistant에게 필요한 **추론, 멀티모달 처리, 웹 탐색, 도구 사용**을 요구하는 문제군을 제시했고, Mind2Web은 **137개 웹사이트, 31개 도메인**의 실제 웹 환경 데이터를 통해 범용 웹 에이전트 평가를 가능하게 했습니다. WebArena는 재현 가능한 웹 환경에서 **길고 복잡한 웹 작업**을 평가하도록 설계되었습니다. ([arXiv][8])

하지만 현재 성능은 아직 사람과 거리가 큽니다. WebArena에서 당시 최고 GPT-4 기반 에이전트는 **14.41%**, 인간은 **78.24%**를 기록했고, OSWorld에서는 최고 모델이 **12.24%**, 인간은 **72.36% 이상**을 달성했습니다. 또 Online-Mind2Web은 기존 결과가 실제 웹 환경을 과대평가했을 수 있다고 지적했고, WebArena Verified는 기존 WebArena의 평가기가 성능을 잘못 측정할 수 있어 **평가 파이프라인 자체를 수정**해야 한다고 보여줬습니다. 이는 Agent Engineering에서 **모델 개선만큼 평가 설계 자체가 중요하다**는 뜻입니다. ([arXiv][9])

## 7) 최종적으로 어떻게 이해하면 좋은가

정리하면, **AI Agent Engineering은 “LLM을 에이전트로 쓰는 법”이 아니라, “LLM을 포함한 확률적 시스템을 실제 업무를 수행하는 신뢰 가능한 소프트웨어로 만드는 법”**입니다. 그 핵심은
모델 선택보다 **도구 설계**,
긴 프롬프트보다 **상태·메모리 관리**,
한 번의 데모보다 **지속적 평가와 관측성**,
완전 자율보다 **통제 가능한 자율성**,
출력 필터링보다 **행동 제약과 검증**에 있습니다. ([arXiv][4])

한 문장으로 압축하면 이렇습니다.
**AI Agent Engineering = “생성 모델을 중심에 둔 다단계 행동 시스템을, 평가 가능하고 안전하며 운영 가능한 형태로 공학화하는 일.”** ([arXiv][4])

[1]: https://www.anthropic.com/research/building-effective-agents "Building Effective AI Agents \\ Anthropic"
[2]: https://arxiv.org/html/2512.04123v2 "Measuring Agents in Production"
[3]: https://arxiv.org/abs/2210.03629 "[2210.03629] ReAct: Synergizing Reasoning and Acting in Language Models"
[4]: https://arxiv.org/abs/2411.13768 "[2411.13768] Evaluation-Driven Development and Operations of LLM Agents: A Process Model and Reference Architecture"
[5]: https://arxiv.org/abs/2405.15793 "[2405.15793] SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering"
[6]: https://arxiv.org/abs/2303.11366 "[2303.11366] Reflexion: Language Agents with Verbal Reinforcement Learning"
[7]: https://arxiv.org/abs/2507.21504 "[2507.21504] Evaluation and Benchmarking of LLM Agents: A Survey"
[8]: https://arxiv.org/abs/2311.12983 "[2311.12983] GAIA: a benchmark for General AI Assistants"
[9]: https://arxiv.org/abs/2307.13854 "[2307.13854] WebArena: A Realistic Web Environment for Building Autonomous Agents"
