## 1) Web Agent의 가장 정확한 정의

현재 연구 문헌에는 **모든 논문이 공유하는 단일한 한 줄 정의**가 딱 정해져 있지는 않습니다. 다만 최근 서베이와 대표 논문들을 종합하면, **Web Agent는 사용자의 자연어 지시를 받아 웹 환경을 관찰하고, 필요한 행동을 계획하며, 실제 브라우저 상에서 클릭·입력·스크롤·탐색 같은 상호작용을 반복 수행해 목표를 완수하는 자율적 에이전트**로 이해하는 것이 가장 정확합니다. 이때 핵심은 단순히 웹페이지를 “읽는” 것이 아니라, **웹을 동적인 실행 환경으로 다루며 행동까지 수행한다는 점**입니다. ([arXiv][1])

조금 더 엄밀하게 말하면, Web Agent는 웹페이지의 **상태(state)** 를 관찰하고, 사용자 목표에 맞는 **행동 시퀀스(action sequence)** 를 결정한 뒤, 그 행동이 적용될 **정확한 UI 요소를 찾아(grounding)** 실행하고, 결과를 다시 관찰하면서 다음 행동을 이어가는 **폐쇄 루프(closed-loop) 시스템**입니다. 최근 WebAgents 서베이는 이 구조를 크게 **Perception → Planning & Reasoning → Execution**으로 정리하고, 그 안에 **memory 활용**까지 포함해 설명합니다. ([arXiv][1])

## 2) 왜 “웹 검색”이나 “챗봇”과 다르게 봐야 하나

Web Agent는 일반적인 검색형 LLM이나 웹 검색 도구와 다릅니다. 예를 들어 WebGPT는 텍스트 기반 웹 브라우징 환경에서 검색과 탐색을 통해 답변을 만드는 방식이었는데, 이는 **웹을 탐색해 근거를 수집하는 에이전트적 행동**의 초기 형태였습니다. 하지만 최근 Web Agent 연구는 여기서 더 나아가, 답변 생성만이 아니라 **실제 사이트에서 업무를 끝내는 것**까지 포함합니다. 즉, “정보를 찾아 알려주는 것”에서 “웹에서 일을 대신 처리하는 것”으로 범위가 확장된 것입니다. ([arXiv][2])

그래서 Web Agent는 보통 다음 둘과 구별됩니다. 첫째, **검색형 시스템**은 보통 정보를 회수하고 요약하는 데 초점이 있습니다. 둘째, **전통적 브라우저 자동화나 RPA**는 규칙 기반 스크립트가 미리 정의된 절차를 따르는 경우가 많습니다. 반면 Web Agent는 **자연어 목표를 해석하고, 보지 못한 페이지에서도 어느 정도 일반화하여, 상황에 따라 다음 행동을 추론**하려는 시스템입니다. Mind2Web은 이를 “어떤 웹사이트에서도 언어 지시를 따라 복잡한 작업을 수행하는 generalist agent” 문제로 제시했고, WorkArena는 이를 브라우저를 통한 실제 지식노동 과업으로 확장해 다룹니다. ([arXiv][3])

## 3) Web Agent의 핵심 구성요소

WebAgents 서베이 기준으로 보면 구조는 비교적 분명합니다. 먼저 **Perception** 단계에서 현재 웹 환경을 읽습니다. 그다음 **Planning & Reasoning** 단계에서 사용자 목표와 현재 상태를 바탕으로 다음 행동을 정합니다. 마지막으로 **Execution** 단계에서 그 행동이 적용될 요소를 찾고 실제 상호작용을 수행합니다. ([arXiv][1])

이 구조를 조금 더 풀면 다음과 같습니다.

- **지각(Perception)**: HTML, DOM, accessibility tree, 스크린샷 같은 입력에서 현재 페이지 상태를 읽음. 최근 문헌은 이를 **text-based / screenshot-based / multimodal**로 나눕니다. ([arXiv][1])
- **계획·추론(Planning & Reasoning)**: 큰 목표를 하위 단계로 나누거나, 현재 한 스텝에서 어떤 행동을 할지 추론함. 서베이는 이를 **명시적 계획 vs 암묵적 계획**, **reactive reasoning vs strategic reasoning**으로 구분합니다. ([arXiv][1])
- **메모리(Memory)**: 이전 행동과 상태를 기억하는 **short-term memory**, 과거 실행 궤적이나 외부 지식을 활용하는 **long-term memory**가 중요하다고 정리됩니다. ([arXiv][1])
- **실행(Execution)**: 행동할 요소를 찾는 **grounding**과, 클릭·입력·선택·스크롤 등을 실제로 수행하는 **interacting**으로 나뉩니다. 상호작용 방식은 사람처럼 브라우저 동작을 쓰는 방식과, 더 추상화된 도구 호출 방식으로 나눌 수 있습니다. ([arXiv][1])

## 4) Web Agent는 무엇을 입력으로 보고, 어떻게 행동하나

초기 또는 텍스트 중심 Web Agent는 주로 **HTML, DOM, accessibility tree 같은 구조화된 텍스트 표현**을 입력으로 사용했습니다. Mind2Web도 실제 웹사이트를 다루면서, 너무 큰 HTML을 바로 모델에 넣기 어렵기 때문에 관련 요소를 걸러내는 방식이 중요하다고 설명합니다. 이는 Web Agent가 단순 자연어 에이전트가 아니라 **웹 구조를 압축해서 읽어야 하는 환경형 에이전트**라는 뜻입니다. ([arXiv][3])

반면 최근에는 스크린샷을 직접 보고 행동하는 **시각·멀티모달 Web Agent** 비중이 크게 늘었습니다. WebVoyager는 기존 에이전트가 단일 입력 모달리티와 단순한 시뮬레이터 평가에 머물렀다고 지적하면서, **실제 웹사이트와 멀티모달 입력**을 통한 end-to-end 에이전트를 제안했습니다. WebAgents 서베이도 이 흐름을 text-only에서 screenshot-based, multimodal로 발전하는 축으로 정리합니다. ([arXiv][4])

행동 측면에서는 클릭, 입력, 선택, 스크롤, 탭 전환, 페이지 이동 같은 **저수준 브라우저 행동**이 기본이고, 일부 시스템은 이를 더 추상화한 **고수준 명령 또는 외부 도구 호출**과 결합합니다. 즉 Web Agent는 “무엇을 할지”뿐 아니라 “어디에 할지”와 “어떻게 실행할지”까지 동시에 해결해야 합니다. ([arXiv][1])

## 5) Web Agent가 수행하는 과업의 범위

문헌을 보면 Web Agent의 과업은 크게 네 부류로 볼 수 있습니다. 첫째는 **정보 탐색과 질의응답**입니다. WebGPT가 여기에 가깝습니다. 둘째는 **일반 웹 내비게이션과 다단계 작업 수행**으로, Mind2Web과 WebArena가 대표적입니다. 셋째는 **실제 소비자 웹사이트에서의 end-to-end 과업**으로, WebVoyager가 이를 강조합니다. 넷째는 **엔터프라이즈/지식노동 업무**로, WorkArena가 ServiceNow 기반의 업무형 브라우저 과제를 통해 이 축을 분명히 보여줍니다. ([arXiv][2])

또 다른 중요한 축은 **대화형 웹 내비게이션**입니다. WebLINX는 사용자의 지시가 한 번에 끝나는 것이 아니라 **여러 턴의 대화 속에서 웹 브라우저를 조작하는 문제**를 제안합니다. 즉 Web Agent는 단발성 명령 실행기라기보다, 사용자의 목표가 уточ정되고 수정되는 과정을 함께 처리하는 인터랙티브 시스템으로도 연구되고 있습니다. ([arXiv][5])

## 6) 연구 흐름으로 보면 어떻게 발전해왔나

큰 흐름만 잡으면 이렇습니다. 2021년의 WebGPT는 웹을 검색·탐색하며 답변의 근거를 모으는 형태로, **웹 브라우징을 LLM 능력에 붙인 초기 계열**로 볼 수 있습니다. 이후 Mind2Web은 실제 웹사이트 기반 데이터셋을 내놓으면서 **generalist web agent** 문제를 본격화했습니다. 이어 WebArena는 복잡하고 장기적인 실제형 과제를 위한 **현실적이면서 재현 가능한 환경**을 만들었고, WorkArena는 이를 **엔터프라이즈 업무 자동화** 방향으로 밀어붙였습니다. WebVoyager는 라이브 웹사이트와 멀티모달 입력을 통해 **현실 웹 end-to-end 수행**을 더 강하게 밀었습니다. BrowserGym은 이후 여러 벤치마크를 공통 observation/action space로 묶어 비교 가능성을 높이려는 시도입니다. ([arXiv][2])

이 흐름을 한 문장으로 요약하면, Web Agent 연구는 **검색 보조 → 일반 웹 내비게이션 → 현실적 장기 과업 → 멀티모달·실웹 실행 → 표준화된 평가와 안전성 검증** 방향으로 진화해 왔다고 볼 수 있습니다. ([arXiv][2])

## 7) 왜 이렇게 어려운 문제인가

가장 큰 이유는 웹이 **부분관찰(partially observable), 동적(dynamic), 장기적(long-horizon)** 환경이기 때문입니다. Mind2Web은 현대 웹사이트가 사용자 행동에 따라 다른 내용을 생성·렌더링하므로, 에이전트는 웹을 **사전 지식이 완전하지 않은 환경**으로 다뤄야 한다고 설명합니다. 즉, 정적인 문서를 읽는 NLP 문제가 아니라 **계속 변하는 인터페이스와 상호작용하는 sequential decision-making 문제**입니다. ([arXiv][3])

또 하나 중요한 점은, 최근 분석에 따르면 Web Agent 실패의 주된 원인이 단순한 클릭 위치 인식보다 **planning**에 더 가까울 수 있다는 것입니다. “From Grounding to Planning” 논문은 웹 에이전트를 planning과 grounding으로 분해해 평가한 뒤, **주된 병목이 grounding보다 planning에 있다**고 보고합니다. 즉 요소를 못 찾는 문제도 있지만, 더 근본적으로는 **지금 무엇을 해야 하는지, 어떤 순서로 해야 하는지**를 결정하는 능력이 어렵다는 뜻입니다. ([arXiv][6])

평가도 쉽지 않습니다. BrowserGym 논문은 기존 벤치마크들이 파편화되어 있고 평가 방식이 일관되지 않아 **신뢰성 있는 비교가 어렵다**고 지적합니다. 또 LLM-based agent evaluation 서베이는 전반적으로 평가가 더 현실적이고 어려운 쪽으로 이동하고 있지만, 여전히 **비용 효율성, 안전성, 강건성, 세분화된 평가**가 부족하다고 봅니다. 그래서 어떤 모델이 “Web Agent를 잘한다”는 말은 **어느 벤치마크, 어떤 관찰 방식, 어떤 평가 프로토콜에서인지**를 함께 봐야 합니다. ([arXiv][7])

## 8) 안전성과 신뢰성은 왜 별도 문제인가

Web Agent는 읽기만 하는 모델이 아니라 **실제로 행동하는 모델**이기 때문에, 정확도만으로는 충분하지 않습니다. ST-WebAgentBench는 기존 벤치마크가 대체로 “과업을 끝냈는가”만 보고, **안전하게 끝냈는가, 정책을 지켰는가, 기업 환경에서 신뢰할 수 있는가**를 잘 보지 않는다고 지적합니다. 즉, 사용자의 계정을 잘못 삭제하거나 엉뚱한 기록을 수정해도 겉보기 completion만 맞으면 위험할 수 있습니다. ([arXiv][8])

보안 측면에서도 웹 에이전트는 새로운 공격면을 가집니다. WASP는 **간접 prompt injection**이 웹 에이전트를 합법적 사용자 의도와 다른 방향으로 유도할 수 있다고 보고하며, 최신 추론 모델과 완화 기법이 있어도 여전히 취약함을 보여줍니다. 즉 Web Agent는 성능 문제만이 아니라 **권한 관리, 민감 행동 승인, 정책 준수, 프롬프트 인젝션 방어**가 함께 설계되어야 하는 시스템입니다. ([arXiv][9])

## 9) 성능은 어느 정도까지 왔나

대표 벤치마크들을 보면 진전은 분명하지만 아직 완성 단계는 아닙니다. WebArena에서는 당시 최고 GPT-4 기반 에이전트가 **14.41%** 성공률로, 사람의 **78.24%**보다 크게 낮았습니다. WorkArena도 현재 에이전트들이 가능성을 보이지만 **완전 자동화까지는 큰 격차**가 있다고 봤고, BrowserGym 역시 다중 벤치마크 비교 결과 **강인하고 효율적인 웹 에이전트 구축이 여전히 어렵다**고 정리합니다. 한편 WebVoyager는 자사 벤치마크에서 **59.1%**를 보고했지만, 이 숫자는 벤치마크와 평가 프로토콜이 다르므로 WebArena 점수와 **직접 비교하면 안 됩니다**. ([arXiv][10])

그래서 오늘 기준으로 가장 정확한 평가는 이렇습니다. **Web Agent는 이미 흥미로운 데모 수준을 넘어 독립된 연구 분야와 시스템 아키텍처 영역이 되었지만, 일반화·장기 계획·신뢰성·보안 측면에서는 아직 연구 과제가 매우 많이 남아 있다**고 보는 것이 맞습니다. ([arXiv][1])

## 10) 한 문장 정의로 마무리

논문식으로 가장 깔끔하게 정리하면:

**Web Agent는 사용자의 자연어 목표를 바탕으로 웹 환경을 지각하고, 필요한 행동을 계획·추론하며, 브라우저 상의 요소를 찾아 실제 상호작용을 반복 수행하여 과업을 자율적으로 완료하는 AI 에이전트이다.** 이 정의에는 지각, 계획, 메모리, grounding, 실행, 검증 가능성까지 포함되어야 최근 연구 흐름과 가장 잘 맞습니다. ([arXiv][1])

[1]: https://arxiv.org/pdf/2503.23350 "A Survey of WebAgents: Towards Next-Generation AI Agents for Web Automation with Large Foundation Models"
[2]: https://arxiv.org/abs/2112.09332 "[2112.09332] WebGPT: Browser-assisted question-answering with human feedback"
[3]: https://arxiv.org/html/2306.06070v3 "Mind2Web: Towards a Generalist Agent for the Web"
[4]: https://arxiv.org/abs/2401.13919 "[2401.13919] WebVoyager: Building an End-to-End Web Agent with Large Multimodal Models"
[5]: https://arxiv.org/abs/2402.05930 "[2402.05930] WebLINX: Real-World Website Navigation with Multi-Turn Dialogue"
[6]: https://arxiv.org/html/2409.01927v1 "From Grounding to Planning: Benchmarking Bottlenecks in Web Agents"
[7]: https://arxiv.org/abs/2412.05467 "[2412.05467] The BrowserGym Ecosystem for Web Agent Research"
[8]: https://arxiv.org/abs/2410.06703 "[2410.06703] ST-WebAgentBench: A Benchmark for Evaluating Safety and Trustworthiness in Web Agents"
[9]: https://arxiv.org/abs/2504.18575?utm_source=chatgpt.com "WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks"
[10]: https://arxiv.org/abs/2307.13854 "[2307.13854] WebArena: A Realistic Web Environment for Building Autonomous Agents"
