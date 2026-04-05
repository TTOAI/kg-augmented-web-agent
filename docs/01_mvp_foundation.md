# Site-Adaptive Execution Agent MVP Foundation

## 1. Purpose

이 문서는 프로젝트의 최종 방향을 MVP 런타임 기준으로 고정한다.
목적은 범위를 넓히는 것이 아니라, 무엇을 구현해야 하고 무엇을 구현하지 말아야 하는지 빠르게 판단하게 만드는 것이다.
이 문서는 아키텍처 흐름이나 데이터 shape를 정의하지 않는다.

이 문서가 답하는 질문은 네 가지다.

- 이 시스템은 무엇인가
- 어떤 문제를 풀 것인가
- MVP에서 반드시 포함할 것은 무엇인가
- 구현 완료를 무엇으로 판단할 것인가

## 2. System Identity

이 프로젝트는 `execution-first`, `reliability-oriented`, `site-prior-augmented` 웹 에이전트 시스템이다.

- `execution-first`: 답변 생성보다 실제 웹 작업 수행을 우선한다.
- `reliability-oriented`: 한 번의 시연보다 반복 성공률과 실패 후 복구 가능성을 더 중요하게 본다.
- `site-prior-augmented`: 온보딩된 사이트의 구조적 지식(페이지 유형, 액션 스키마)을 LLM 추론에 주입해 탐색 비용을 줄이고 실행 정확도를 높인다.

prior는 레시피(작업 절차)가 아니라 사이트에 대한 구조적 이해다.
LLM은 이 구조적 지식을 바탕으로 주어진 태스크를 어떻게 수행할지 자율적으로 계획한다.

한 줄 정의:

`Site-Adaptive Execution Agent`는 온보딩된 사이트의 구조적 prior를 LLM 추론에 주입해, 반복 수행되는 장기 웹 과업을 더 안정적으로 실행하는 MVP 런타임이다.

## 3. Problem and Scope

이 프로젝트가 줄이려는 핵심 문제는 다음과 같다.

- 같은 사이트에서도 매번 처음 보는 것처럼 재탐색한다.
- 장기 과업에서 현재 상태와 다음 단계 판단이 흔들린다.
- 잘못된 결과를 늦게 발견하거나 그대로 반환한다.
- 실패 이후 재시도, 우회, 승인 전환이 구조화되어 있지 않다.

MVP 핵심 범위:

- `seen-site long-horizon task`
- site prior(page_types + action_schemas) 기반 LLM planning 보강
- validator 기반 결과 검증
- recovery 기반 실패 대응
- approval gate 기반 위험 행동 통제
- `Site Prior Store`와 `Execution Memory` 분리

MVP 밖의 범위:

- 열린 웹 범용 assistant
- 문서 QA 또는 knowledge platform
- 대규모 ontology 플랫폼
- full vision 또는 computer-use 중심 실행기
- benchmark 재현 자체를 핵심 산출물로 삼는 구조

## 4. MVP User and Task Shape

주 사용자는 정해진 SaaS, 포털, 예약/검색 사이트에서 반복 업무를 수행하는 운영자다.

MVP에서 다루는 task family:

- 검색/비교
- 필터링/정렬
- 폼 입력 초안
- 대시보드 조회/리포트 생성

핵심 경로는 `seen-site + known action schema` fast path다.
`unseen-site`는 안전장치로만 존재하며 MVP 가치의 중심이 아니다.

## 5. Runtime Success Criteria

MVP는 아래 조건을 만족하면 성립한다.

- 온보딩된 사이트에 대해 site prior(page_types + action_schemas)를 읽어 실행 경로를 선택할 수 있다.
- 런타임이 현재 사이트와 prior 신뢰도를 기준으로 fast path와 fallback path를 구분할 수 있다.
- 브라우저 액션 이후 validator를 실행하고 결과를 기록할 수 있다.
- validator 실패 시 recovery 또는 handoff로 전환할 수 있다.
- 승인 대상 행동을 approval gate로 분기할 수 있다.
- 실행 결과를 `Execution Memory`에 구조적으로 저장할 수 있다.

구현 판단 원칙:

- 새로운 개념을 추가하기 전에 위 여섯 조건을 직접 돕는지 확인한다.
- 직접 돕지 않으면 MVP에서는 넣지 않는다.

최소 acceptance 시나리오:

1. `seen-site fast path 성공`
   온보딩된 사이트와 실행 가능한 `ActionSchema`가 존재할 때, site prior를 읽어 fast path를 선택하고 validator `pass`와 함께 결과를 저장해야 한다.
2. `validator fail 후 recovery`
   실행 결과가 validator `fail`이면 recovery를 시도하고, recovery 성공 후 validator를 다시 실행해 `pass`일 때만 결과를 갱신하며, 그렇지 않으면 handoff로 종료해야 한다.
3. `risky action approval-first`
   policy rule이 승인 요구로 판정한 행동은 실제 상태 변경 전에 approval event를 만들고 승인 결과가 나오기 전까지 실행하지 않아야 한다.

## 6. Constraints

- 구조적 실행 수단을 먼저 사용한다.
- prior는 실행, 상태 추적, 검증, 복구에 직접 쓰이는 정보만 담는다.
- prior의 핵심은 `SiteProfile`, `PageType`, `ActionSchema`이며, 절차적 레시피(workflow)는 포함하지 않는다.
- LLM은 구조적 prior를 참고해 태스크 경로를 자율 추론한다.
- 평가와 연구 확장은 런타임이 먼저 작동한 뒤 다시 정의한다.
- benchmark 재현 설계는 제외하지만, 위 acceptance 시나리오를 만족하는 런타임 수용 검증은 포함한다.
- 현재 MVP는 온보딩 기반 적응형 런타임에 집중하며, 실행 기록을 자동으로 prior로 승격하는 학습형 구조는 MVP 이후 확장으로 미룬다.

다음 문서: `02_runtime_architecture.md`
