# Site-Adaptive Execution Agent Runtime Architecture

## 1. Purpose

이 문서는 MVP 런타임이 어떤 레이어와 흐름으로 동작하는지 정의한다.
설명 대상은 구현 직전의 엔지니어다.
이 문서는 확장 논의보다 현재 런타임이 어떤 입력을 받아 어떤 책임 분리로 동작해야 하는지에 집중한다.
이 문서는 상세 데이터 shape나 저장 필드 정의를 맡지 않는다.

## 2. Architecture Overview

MVP 런타임은 네 개의 레이어로 나눈다.

1. `Foundation Execution`
2. `Site Prior Layer`
3. `Orchestration`
4. `Validation and Recovery`

레이어 역할:

- `Foundation Execution`: 브라우저와 도구를 이용해 실제 액션을 수행한다.
- `Site Prior Layer`: 온보딩된 사이트의 구조적 지식(page_types, action_schemas)과 validator, policy, failure prior를 제공한다.
- `Orchestration`: 현재 사이트와 prior 상태를 해석하고 실행 전략을 선택한다.
- `Validation and Recovery`: 결과를 검증하고 실패 시 재시도, 승인, handoff를 결정한다.

## 3. Core Components

### 3.1 Request Interpreter

- 사용자 요청을 `task_family`와 실행 제약으로 정규화한다.
- 출력은 `RunRequest`다.

### 3.2 Site Resolver

- 현재 사이트와 페이지를 식별한다.
- `site_id`, `page_type_id` 후보를 결정한다.

### 3.3 Prior Selector

- `site_id`에 맞는 prior 묶음을 선택한다.
- 출력은 `PriorBundle`이다.

### 3.4 State Tracker

- 현재 단계, 진행 상태, approval 상태, validator 상태를 추적한다.
- ActionSchema 기반 사이트 그래프와 실행 기록을 조합해 현재 위치를 파악한다.

### 3.5 Strategy Router

- fast path, partial-prior path, fallback path, approval-first path 중 하나를 고른다.

결정표:

| site onboarded | action schema available | prior confidence | approval required | selected path |
| --- | --- | --- | --- | --- |
| yes | yes | sufficient | no | `fast path` |
| yes | yes | insufficient | no | `partial-prior path` |
| yes | no | any | no | `partial-prior path` |
| no | any | any | no | `fallback path` |
| any | any | any | yes | `approval-first path` |

메모:
- `approval required`가 `yes`이면 다른 조건보다 우선한다.
- `prior confidence`의 정량식은 이 문서에서 정의하지 않고, router가 `sufficient / insufficient`로만 판단한다.
- fast path는 실행 가능한 `ActionSchema`와 sufficient prior confidence가 모두 있을 때만 진입한다.
- `page_type_id`를 단일하게 고르지 못하면 `page_type_id=unresolved`로 기록하고 즉시 `fallback path`로 전환한다.
- `ActionSchema`가 없으면 site가 `active`여도 `partial-prior path`로 강등한다.

### 3.6 Action Executor

- 구조적 실행 수단을 우선 사용한다.
- 우선순위는 다음과 같다.
  `API/tool -> DOM/accessibility snapshot -> code-assisted browser action -> screenshot-based diagnosis`

### 3.7 Validator Engine

- 실행 결과를 `ValidatorRule`로 검사한다.
- 출력은 `pass`, `fail`, `partial` 중 하나다.

### 3.8 Recovery Manager

- validator 실패, selector mismatch, session 문제, approval 요구 상황에 대응한다.
- 재시도, 우회, approval wait, handoff를 결정한다.

### 3.9 Evidence Logger

- 실행 중 생성된 상태, 검증 결과, recovery 결과를 `Execution Memory`에 저장한다.

## 4. Main Runtime Flow

기본 실행 흐름:

1. 사용자 요청 수신
2. 현재 사이트와 페이지 판별
3. `task_family` 판별
4. `seen-site / known action schema` 여부 판단
5. 관련 prior 선택
6. pre-action approval check
7. LLM이 site prior(page_types + action_schemas)를 참고해 실행 계획 수립
8. 브라우저 액션 수행
9. post-action validation 실행
10. validation 실패 시 recovery 시도
11. recovery 성공 시 validator 재실행
12. 재검증 실패 시 handoff 전환
13. 실행 기록 저장
14. 성공 시 evidence와 함께 결과 반환

## 5. Runtime Paths

### 5.1 Seen-Site Fast Path

아래 조건에서 사용한다.

- 사이트가 온보딩되어 있다.
- 실행 가능한 `ActionSchema`가 존재한다.
- prior confidence가 충분하다.
- 고위험 승인 행동이 없다.

이 경로에서는 site prior를 LLM에 주입해 재탐색 비용을 줄이고 실행 정확도를 높인다.

### 5.2 Partial-Prior Path

아래 조건에서 사용한다.

- 사이트는 온보딩되어 있다.
- `ActionSchema`가 없거나 prior confidence가 낮다.

이 경로에서는 generic execution을 기본으로 하되, page type prior와 policy prior만 부분적으로 사용한다.

### 5.3 General Fallback Path

아래 조건에서 사용한다.

- 사이트가 온보딩되지 않았다.
- 현재 prior를 신뢰하기 어렵다.

이 경로는 안전장치다.
MVP의 핵심 가치나 평가 중심은 아니다.

### 5.4 Approval-First Path

아래 조건에서 사용한다.

- risky action이 포함된다.
- 제출, 전송, 상태 변경 직전이다.
- policy rule이 사전 승인을 요구한다.

이 경우 실제 실행보다 approval event 생성이 우선이며, 런타임은 pre-action hold 상태로 대기한다.

## 6. Onboarding Output Contract

온보딩은 별도 지식 수집 시스템이 아니라 런타임용 prior 생성 절차다.

### 6.1 Recording Session

사용자가 브라우저에서 직접 사이트를 탐색하는 동안, 시스템은 다음을 자동 수집한다.

- 방문한 URL 패턴 → `page_types.url_patterns`
- 각 페이지의 DOM 구조 신호 → `page_types.structural_signals`
- 사용한 인터랙션(클릭, 검색, 폼 입력)의 locator → `action_schemas.preferred_locator_strategy`
- 액션의 전후 상태 변화 → `action_schemas.preconditions / postconditions`

수집 원칙: raw DOM/위치 기반 selector를 의미 단위(role, aria-label, text)로 추상화해 저장한다.
목적은 동작 재현이 아니라 **사이트의 구조적 이해**를 prior로 남기는 것이다.

### 6.2 운영자 확정 항목

Recording Session 결과를 검토하고 아래를 확정한다.

- 핵심 page type
- 주요 action schema
- validator rule
- policy rule
- failure pattern 초안

### 6.3 온보딩 산출물

- `SiteProfile`
- `PageType`
- `ActionSchema`
- `ValidatorRule`
- `PolicyRule`
- `FailurePattern`

`draft -> active` 전환 최소 조건:

- `SiteProfile` 1개
- `PageType` 1개 이상
- `ActionSchema` 1개 이상
- `ValidatorRule` 1개 이상
- 기본 `PolicyRule` 1개 이상

위 조건을 만족하지 못하면 `onboarding_status`는 `draft`를 유지한다.
`FailurePattern`은 유용한 보강 prior지만 `active`의 필수 조건은 아니다.

후속 확장에서는 에이전트의 성공 실행 결과를 검토·정제해 `Site Prior Store`를 보강하는 자동 강화 루프를 추가할 수 있다.
하지만 MVP 런타임에는 이 온라인 업데이트 경로를 포함하지 않는다.

## 7. MVP Boundaries

MVP에서 제외한다.

- 거대한 ontology 계층 문서화
- change detection 전용 서브시스템
- Knowledge Assets 계층
- model track 분기 구조
- benchmark 재현용 아키텍처
- full vision 기반 기본 실행기
- 절차적 레시피(workflow hints) 기반 실행 안내

다음 문서: `03_runtime_data_contracts.md`
