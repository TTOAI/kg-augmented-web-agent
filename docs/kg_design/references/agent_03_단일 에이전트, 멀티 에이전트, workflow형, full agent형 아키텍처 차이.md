첫째 축은 **제어 방식**이다.
왼쪽은 **workflow형**이고, 오른쪽은 **full agent형**이다. Anthropic은 workflow를 **“LLM과 도구가 미리 정해진 코드 경로(predefined code paths)로 오케스트레이션되는 시스템”**, agent를 **“LLM이 자신의 프로세스와 도구 사용을 동적으로 지시하는 시스템”**으로 구분한다. 또 “agent는 사실상 **환경 피드백을 받으며 도구를 루프 안에서 사용하는 LLM**”이라고 설명한다. 여기서 말하는 **full agent형**은 공식 표준 용어라기보다, 이런 **높은 자율성의 agent loop**를 가리키는 실무적 표현으로 이해하면 된다. ([Anthropic][1])

둘째 축은 **주체 수**다.
위쪽은 **단일 에이전트(single-agent)**, 아래쪽은 **멀티 에이전트(multi-agent)** 다. 최근 survey와 보안 아키텍처 논문들은 단일 에이전트를 보통 **하나의 LLM이 planner와 actor 역할을 함께 수행하는 구조**, 더 복잡한 구조를 **planner/actor 분리**, 그리고 거기서 더 나아가 **여러 specialized agents가 협업하는 구조**로 설명한다. 즉, **single vs multi**는 “몇 개의 자율 주체가 있느냐”의 문제이고, **workflow vs full agent**는 “그 주체들이 얼마나 미리 짜인 흐름을 따르느냐 vs 스스로 루프를 돌며 결정하느냐”의 문제다. ([arXiv][2])

이를 2x2로 그리면 이렇게 된다.

```text
                      제어 방식
                workflow형  <------->  full agent형

주체 수
single-agent     ① 단일 워크플로우       ③ 단일 자율 에이전트

multi-agent      ② 멀티 컴포넌트/        ④ 멀티 에이전트 시스템
                    멀티 스텝 워크플로우
```

핵심은 **이 네 칸이 서로 다른 것**이라는 점이다. 특히 **멀티 LLM 호출**이 있다고 해서 자동으로 **멀티 에이전트**가 되는 것은 아니고, **여러 단계가 있다**고 해서 자동으로 **full agent**가 되는 것도 아니다. Anthropic의 taxonomy에서 **prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer**는 모두 workflow로 분류되고, 그 다음에 별도로 agents를 설명한다는 점이 이 구분을 잘 보여준다. ([Anthropic][1])

## ① 단일 에이전트 + workflow형

이 구조는 가장 단순하다. 하나의 주 실행 흐름을 코드가 잡고, LLM은 그 흐름 안에서 특정 단계만 수행한다. 예를 들어 **입력 분류 → 알맞은 프롬프트 선택 → 초안 생성 → 검증 → 출력** 같은 식이다. Anthropic이 말한 **prompt chaining, routing, parallelization, evaluator-optimizer**가 여기에 들어간다. 이런 구조는 **태스크를 고정된 하위 단계로 잘 나눌 수 있을 때**, 그리고 **디버깅·비용·예측 가능성**이 중요할 때 적합하다. ([Anthropic][1])

이 구조의 장점은 분명하다. 흐름이 고정돼 있어서 **관측성(observability)** 이 좋고, 실패 지점이 명확하며, 비용과 지연시간을 상대적으로 잘 통제할 수 있다. 반면 약점은 **경로 밖 예외 처리**에 약하다는 점이다. 필요한 단계 수가 실행 중 바뀌거나, 도중 발견된 정보에 따라 계획을 크게 바꿔야 하는 문제에는 한계가 있다. Anthropic도 workflow는 **fixed subtasks**나 **distinct categories**가 있을 때 잘 맞는다고 설명한다. ([Anthropic][1])

## ② 멀티 에이전트가 아니라 “멀티 컴포넌트 workflow”인 경우

이 부분이 가장 많이 헷갈린다. 예를 들어 **orchestrator-workers**처럼 여러 LLM 호출이 있고 역할도 나뉘어 있지만, 전체 제어 골격이 여전히 코드에 의해 정해져 있다면 이것은 엄밀히는 **workflow형**으로 보는 편이 맞다. Anthropic도 **orchestrator-workers**를 agent가 아니라 workflow 패턴 아래에 둔다. 즉, **여러 모델/여러 역할**이 있다고 해서 곧바로 “멀티 에이전트 시스템”이라고 부르기보다, **각 노드가 독립적 자율 루프를 가지는지**를 봐야 한다. ([Anthropic][1])

이 형태는 **역할 분업**은 필요하지만, **최종 통제권은 코드나 중앙 오케스트레이터가 강하게 쥐고 있어야 할 때** 유용하다. 예를 들어 한 노드는 분류, 다른 노드는 생성, 또 다른 노드는 안전성 검사만 담당하게 할 수 있다. Anthropic의 글에서도 병렬화와 evaluator-optimizer는 각각 **서로 다른 관점의 독립 처리**와 **생성-평가 루프**에 특히 유용하다고 설명된다. 그래서 실무에서는 이것을 “멀티 에이전트”라고 부르기보다 **multi-stage workflow** 또는 **multi-component workflow**라고 부르는 쪽이 더 정확한 경우가 많다. ([Anthropic][1])

## ③ 단일 에이전트 + full agent형

이제 여기서부터가 보통 사람들이 떠올리는 “에이전트”다. 하나의 주 에이전트가 **도구를 루프 안에서 사용**하면서, 환경 피드백을 보고 다음 행동을 정하고, 필요하면 재계획한다. Anthropic은 agent를 **오픈엔드 문제**, 즉 **필요한 단계 수를 미리 예측하기 어렵고 고정 경로를 하드코딩할 수 없는 문제**에 쓰라고 말한다. 또 실행 중에는 tool result나 code execution 같은 **ground truth**를 계속 받아야 하며, 반복 횟수 제한이나 checkpoint 같은 제어 장치가 중요하다고 설명한다. ([Anthropic][1])

이 구조의 장점은 **유연성**이다. 새로운 정보가 나오면 계획을 바꾸고, 예상치 못한 실패도 어느 정도 복구할 수 있다. 대신 비용은 커지고, 평가와 디버깅이 어려워진다. 그래서 Anthropic의 2026 eval 글은 agent는 **many turns, tool calls, state changes** 때문에 일반적인 단발성 모델보다 훨씬 평가하기 어렵다고 강조한다. 즉, full agent형은 planner만 있으면 되는 게 아니라 **memory, tool design, guardrails, evaluator**가 함께 붙어야 한다. ([Anthropic][3])

## ④ 멀티 에이전트 + full agent형

이건 가장 강력하지만 가장 비싼 구조다. 여러 자율 에이전트가 각자 루프를 돌며 협업한다. Anthropic의 Research 시스템이 대표적 예인데, **lead agent가 연구 계획을 세우고**, 그다음 **parallel subagents**를 만들어 각기 다른 관점에서 정보를 탐색하게 한다. Anthropic은 이런 구조가 **탐색 공간이 넓고, 미리 경로를 짤 수 없고, 병렬 조사 가치가 큰 연구형 작업**에 특히 잘 맞는다고 설명한다. ([Anthropic][4])

하지만 단점도 아주 크다. Anthropic은 실제 운영 데이터에서 **agents가 일반 chat보다 약 4배**, **multi-agent systems는 chat보다 약 15배** 토큰을 썼다고 적고, coordination·evaluation·reliability 문제가 새로 생긴다고 말한다. 또 리드 에이전트가 서브에이전트들을 동기적으로 기다리면 병목이 생기고, 서브에이전트끼리 직접 조정하지 못하는 문제도 있었다고 공개했다. 즉 멀티 에이전트는 **항상 상위호환이 아니라**, 병렬 탐색·역할 전문화·컨텍스트 분산의 이득이 coordination overhead를 이길 때만 정당화된다. ([Anthropic][4])

## 그래서 “workflow형 vs full agent형”의 본질적 차이는 무엇인가

가장 본질적인 차이는 **누가 실행 경로를 정하느냐**다. workflow형에서는 **개발자가 실행 그래프를 미리 설계**하고 LLM은 그 노드들 중 일부를 채운다. full agent형에서는 **LLM이 실행 중 계획과 도구 사용을 동적으로 선택**한다. Anthropic의 정의를 그대로 옮기면, workflow는 **predefined code paths**, agent는 **dynamic self-direction**이다. ([Anthropic][1])

그래서 workflow형은 보통 **예측 가능성, 검증 가능성, 비용 통제**에서 유리하고, full agent형은 **개방형 문제 해결, 장기 상호작용, 환경 적응성**에서 유리하다. 다만 Anthropic도 “가능한 한 단순하게 시작하라”고 권하고, 실전 배포에서는 복잡한 자율 시스템보다 **simple, composable patterns**가 자주 성공한다고 말한다. 즉, 특별한 이유가 없다면 **workflow에서 시작해 agent로 올라가는 방식**이 일반적으로 더 안전하다. ([Anthropic][1])

## 그러면 “단일 vs 멀티”의 본질적 차이는 무엇인가

단일 vs 멀티의 차이는 **자율 주체 수와 상호작용 구조**다. 단일 에이전트에서는 planner와 actor가 한 LLM 안에 합쳐질 수 있고, 더 복잡해도 결국 하나의 중심 주체가 전 과정을 담당한다. 반면 멀티 에이전트에서는 **planner, generator, evaluator**처럼 역할을 분리하거나, **lead agent + subagents**처럼 병렬 탐색 구조를 만든다. Anthropic의 long-running coding harness도 실제로 **planner, generator, evaluator의 3-agent architecture**를 썼다고 설명한다. ([arXiv][2])

하지만 최신 연구들은 멀티 에이전트가 항상 더 낫다고 보지 않는다. 2025년 비교 연구는 **기본 모델 능력이 좋아질수록 MAS의 장점이 줄어든다**고 보고했고, 2026년 Stanford 연구는 **멀티홉 추론에서 thinking-token budget을 맞추면 single-agent가 MAS를 match하거나 outperform**했다고 보고했다. 이 결과를 모든 실제 업무에 그대로 일반화하면 안 되지만, 적어도 **멀티 에이전트의 이점은 종종 추가 계산량과 분업 비용에 의해 설명될 수 있다**는 점은 분명하다. ([arXiv][5])

## 실무적으로 어떻게 선택하면 되나

가장 실용적인 선택 기준은 이렇다.

**입력 유형이 비교적 안정적이고, 하위 단계가 미리 보이며, 실패 비용이 높다**면
→ **단일 workflow형**부터 시작하는 게 맞다. ([Anthropic][1])

**하위 역할을 분리하면 성능이 좋아지지만, 여전히 전체 흐름은 통제하고 싶다**면
→ **멀티 컴포넌트 workflow형**이 맞다. evaluator-optimizer, routing, orchestrator-workers가 여기에 가깝다. ([Anthropic][1])

**문제가 개방형이고, 필요한 단계 수를 미리 못 정하며, 실행 중 탐색·재계획이 중요하다**면
→ **단일 full agent형**으로 올라간다. ([Anthropic][1])

**탐색 공간이 너무 넓고, 병렬 조사나 역할 전문화가 실제로 큰 성능 이득을 주며, 비용을 감당할 가치가 있다**면
→ 그때 **멀티 에이전트 full agent형**을 쓴다. Anthropic의 Research 시스템이 바로 이 경우다. ([Anthropic][4])

한 줄로 압축하면 이렇다.

**workflow형과 full agent형의 차이는 “누가 실행 경로를 정하느냐”이고, single과 multi의 차이는 “몇 개의 자율 주체가 협업하느냐”다.**
그래서 올바른 순서는 보통 **single workflow → multi-component workflow → single full agent → multi-agent full system** 순으로 복잡도를 올리는 것이다. 최근 문헌과 실전 사례를 같이 보면, 이 점진적 확장이 가장 안정적이다. ([Anthropic][1])

[1]: https://www.anthropic.com/research/building-effective-agents "Building Effective AI Agents \\ Anthropic"
[2]: https://arxiv.org/html/2603.11088v1 "The Attack and Defense Landscape of Agentic AI: A Comprehensive Survey"
[3]: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents "Demystifying evals for AI agents \\ Anthropic"
[4]: https://www.anthropic.com/engineering/built-multi-agent-research-system "How we built our multi-agent research system \\ Anthropic"
[5]: https://arxiv.org/abs/2505.18286 "[2505.18286] Single-agent or Multi-agent Systems? Why Not Both?"
