**논문에서 가장 정통적인 Web Agent 아키텍처 표기는 보통 `perception → planning & reasoning → execution`입니다.** 최근 WebAgents 서베이도 이 3단계를 기본 골격으로 놓고, 그 안에서 memory 활용, grounding, interaction, tool use, trustworthiness를 세부 축으로 분석합니다. 그래서 사용하신 **planning / memory / tools / guardrails / evaluator** 프레임은, 엄밀히 말하면 논문들이 동일한 용어로 통일해 쓰는 “공식 5분할”이라기보다는, **연구 문헌의 핵심 요소를 에이전트 엔지니어링 관점으로 재구성한 실무형 표준도**에 가깝습니다. ([ar5iv][1])

## 1) Web Agent 표준 아키텍처를 5개 블록으로 재구성하면

```text
사용자 목표
   │
   ▼
┌──────────────────────────────┐
│ 1. Planning                  │
│ - 목표 해석                  │
│ - 하위 과업 분해             │
│ - 다음 행동 선택             │
│ - 필요 시 재계획             │
└──────────────┬───────────────┘
               │
     ┌─────────┴─────────┐
     │                   │
     ▼                   ▼
┌──────────────┐   ┌──────────────┐
│ 2. Memory    │   │ 3. Tools     │
│ - 단기 이력  │   │ - 브라우저    │
│ - 장기 경험  │   │ - DOM/AXTree  │
│ - 과거 궤적  │   │ - 스크린샷    │
│ - 워크플로우 │   │ - API/검색    │
└──────┬───────┘   └──────┬───────┘
       │                  │
       └──────┬───────────┘
              ▼
      웹 환경 관찰 / 행동 실행
              │
              ▼
┌──────────────────────────────┐
│ 4. Guardrails                │
│ - 위험행동 차단              │
│ - 정책/권한 확인             │
│ - 사용자 확인 요구           │
│ - prompt injection 방어      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 5. Evaluator                 │
│ - 성공/실패 판정             │
│ - 정책 준수 검사             │
│ - 결과 검증                  │
│ - 실패 원인 기록             │
└──────────────┬───────────────┘
               │
               └─────► Planning / Memory로 피드백
```

이 도식은 연구 문헌의 기본 루프를 엔지니어링 관점으로 옮긴 것입니다. 원래 논문식으로는 **환경을 지각(perception)** 하고, 그 관찰을 바탕으로 **계획·추론(planning & reasoning)** 을 거쳐, 마지막에 **실행(execution)** 합니다. 여기서 당신이 말한 5개 블록으로 바꾸면, **planning은 계획·추론**, **memory는 과거 행동·외부 지식 활용**, **tools는 perception+execution의 인터페이스**, **guardrails는 trustworthiness/safety 계층**, **evaluator는 성공 판정과 검증 계층**으로 대응됩니다. ([ar5iv][1])

## 2) 블록별로 보면 이렇게 이해하면 가장 정확합니다

### 1. Planning

Planning은 Web Agent의 “두뇌”입니다. 사용자 목표를 해석하고, 현재 페이지 상태를 바탕으로 다음 행동을 정합니다. 문헌에서는 이를 보통 **action reasoning** 또는 **task planning**으로 다루며, 최근 서베이는 이를 **reactive reasoning**과 **strategic reasoning**으로 나눕니다. Reactive reasoning은 현재 관찰을 보고 바로 다음 행동을 고르는 방식이고, strategic reasoning은 추가 탐색, 시뮬레이션, 외부 정보 참조 등을 통해 더 신중하게 다음 행동을 정하는 방식입니다. ReAct는 reasoning과 acting을 교차시키는 대표 패러다임이고, 최근 연구는 웹 에이전트의 병목이 grounding보다 planning에 더 크다고 보고합니다. 또 model-based planning 계열은 실제 행동 전에 결과를 시뮬레이션해 더 나은 행동을 고르려 합니다. ([ar5iv][1])

실무적으로는 Planning 블록 안에 보통 이런 하위 기능이 들어갑니다.
목표 해석, 하위 과업 분해, 다음 액션 선택, 예외 처리, 실패 시 재계획입니다.
즉, Web Agent의 핵심 성능 차이는 대체로 “버튼을 볼 수 있느냐”보다 “지금 무엇을 해야 하느냐를 제대로 아느냐”에서 갈리는 경우가 많습니다. ([arXiv][2])

### 2. Memory

Memory는 Planning이 매 스텝마다 “처음 보는 것처럼” 행동하지 않게 만드는 계층입니다. 서베이는 memory를 **short-term memory**와 **long-term memory**로 나눕니다. Short-term memory는 현재 과업 동안의 이전 행동, 이전 페이지 상태, 최근 실패/성공 이력 같은 것들입니다. Long-term memory는 과거 유사 작업의 궤적, 외부 검색으로 얻은 지식, 반복적으로 재사용 가능한 워크플로우 같은 것입니다. ([ar5iv][1])

특히 웹 에이전트에서는 long-horizon task가 많기 때문에 장기 기억이 중요합니다. AWM(Agent Workflow Memory)은 과거 실행에서 **재사용 가능한 workflow**를 유도해 이후 작업을 안내하도록 만들었고, Mind2Web과 WebArena에서 상대적 성공률을 각각 24.6%, 51.1% 개선했다고 보고합니다. 그래서 현대적인 Web Agent 아키텍처에서 memory는 단순 로그 저장이 아니라, **재사용 가능한 실행 경험의 구조화**에 가깝습니다. ([arXiv][3])

### 3. Tools

Tools는 에이전트가 웹과 접촉하는 손과 눈입니다. 엄밀히 말하면 논문식 “perception”과 “execution”을 실제 시스템으로 구현하는 인터페이스가 바로 tools입니다. 서베이는 상호작용 방식을 크게 **web browsing-based**와 **tool-based**로 나눕니다. 전자는 클릭, 스크롤, 타이핑, 선택 같은 브라우저 상호작용을 직접 수행하는 방식이고, 후자는 API나 검색 도구, 스크레이퍼 등을 사용해 GUI를 우회하거나 보조하는 방식입니다. ([ar5iv][1])

따라서 실무형 표준 아키텍처에서 Tools 블록은 보통 다음을 포함합니다.
브라우저 제어기, DOM/HTML 또는 accessibility tree reader, screenshot/VLM 입력, API caller, 검색 도구, 파서/스크레이퍼입니다.
연구 문헌에서는 이 관찰 입력을 **text-based**, **screenshot-based**, **multimodal**로도 구분합니다. 즉 Tools는 단순 외부 유틸이 아니라, Web Agent의 관찰 공간과 행동 공간을 정의하는 핵심 블록입니다. ([ar5iv][1])

### 4. Guardrails

Guardrails는 “할 수 있는 행동”과 “해도 되는 행동”을 구분하는 계층입니다. 이 부분은 전통적인 Web Agent 논문에서 핵심 3단계 중 하나로 독립 표기되지는 않았지만, 최근 문헌에서는 **trustworthiness**가 별도 연구 축으로 올라와 있습니다. ST-WebAgentBench는 단순 과업 성공만 보면 실제 배치에 필요한 안전성을 놓친다고 지적하며, 정책을 지키면서 완료한 경우만 인정하는 **Completion Under Policy (CuP)** 와 정책 위반 정도를 보는 **Risk Ratio**를 제안합니다. 평가 결과, 오픈 SOTA 에이전트들의 평균 CuP가 명목 completion rate의 3분의 2보다 낮았다는 점은, guardrails가 “있으면 좋은 옵션”이 아니라 배치 조건이라는 뜻입니다. ([arXiv][4])

또 보안 측면에서는 WASP가 웹 에이전트가 **간접 prompt injection**에 취약하다는 점을 보여줍니다. 현실적인 시나리오에서 단순한 human-written injection만으로도 에이전트가 공격 방향으로 유도될 수 있었습니다. 따라서 Guardrails 블록에는 보통 **권한 제한, 고위험 행동 승인, 정책 검사, 민감 정보 처리 제한, injection 방어, 되돌릴 수 없는 행동 차단**이 포함됩니다. ST-WebAgentBench가 말하는 대표 안전 차원에는 user consent, boundary, strict execution, hierarchy, robustness, error handling이 포함됩니다. ([arXiv][5])

### 5. Evaluator

Evaluator는 “행동을 했는가”가 아니라 **제대로 했는가**를 판정하는 계층입니다. 이 블록은 두 층으로 나눠 이해하는 게 가장 좋습니다.

첫째는 **런타임 evaluator**입니다.
한 스텝 또는 한 과업이 끝났을 때 목표 달성 여부, 출력 형식, 값의 유효성, 정책 위반 여부를 검사하고, 실패하면 재시도·복구·재계획으로 넘깁니다. 이 구조는 논문에서 항상 동일한 이름으로 불리지는 않지만, 현대 Web Agent 엔지니어링에서는 사실상 필수입니다. 이는 WebArena Verified가 보여주듯이, 느슨한 문자열 매칭이나 모호한 성공 기준은 성능을 과대평가하기 쉽기 때문입니다.

둘째는 **벤치마크 evaluator**입니다.
BrowserGym은 관찰 공간과 행동 공간을 표준화해 벤치마크 비교를 쉽게 만들었고, WebArena Verified는 더 나아가 **deterministic evaluation**, **backend state verification**, **structured JSON schema**, **LLM-as-judge 제거**를 통해 평가 신뢰성을 높였습니다. 즉 Evaluator는 단순 채점기가 아니라, Web Agent 연구와 배치 모두에서 **신뢰 가능한 성공 판정 장치**입니다. ([arXiv][6])

## 3) 이 5개 블록을 한 번에 읽는 법

가장 실전적으로 압축하면 이렇습니다.

**Planning**이 무엇을 할지 정하고,
**Memory**가 과거 맥락과 경험을 공급하고,
**Tools**가 웹을 보고 조작하며,
**Guardrails**가 하면 안 되는 행동을 막고,
**Evaluator**가 결과를 검증해 다시 Planning으로 되돌립니다.

즉 Web Agent의 표준 구조는 사실상 **“계획하는 루프 + 기억 + 실행 인터페이스 + 안전 장치 + 검증 피드백”**라고 보면 됩니다. 이 해석은 서베이의 canonical pipeline과 최근 planning, memory, safety, evaluation 문헌을 가장 잘 연결하는 방식입니다. ([ar5iv][1])

## 4) 한 줄로 정리하면

**Web Agent의 현대적 표준 아키텍처는, 웹 환경을 관찰하는 tool layer 위에서 planning이 행동을 결정하고, memory가 맥락과 경험을 공급하며, guardrails가 위험을 제어하고, evaluator가 결과를 검증해 다시 planning loop로 피드백하는 폐쇄 루프 구조**입니다. ([ar5iv][1])

[1]: https://ar5iv.org/html/2503.23350v4 "[2503.23350] A Survey of WebAgents: Towards Next-Generation AI Agents for Web Automation with Large Foundation Models"
[2]: https://arxiv.org/abs/2409.01927 "[2409.01927] From Grounding to Planning: Benchmarking Bottlenecks in Web Agents"
[3]: https://arxiv.org/abs/2409.07429 "[2409.07429] Agent Workflow Memory"
[4]: https://arxiv.org/abs/2503.23350 "[2503.23350] A Survey of WebAgents: Towards Next-Generation AI Agents for Web Automation with Large Foundation Models"
[5]: https://arxiv.org/abs/2504.18575 "[2504.18575] WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks"
[6]: https://arxiv.org/abs/2412.05467 "[2412.05467] The BrowserGym Ecosystem for Web Agent Research"
