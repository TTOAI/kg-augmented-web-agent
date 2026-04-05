# Site-Adaptive Execution Agent Runtime Data Contracts

## 1. Purpose

이 문서는 MVP 런타임이 실제로 읽고 쓰는 최소 데이터 계약을 정의한다.
핵심 목표는 저장소 경계와 필수 필드를 고정하는 것이다.
필드가 런타임의 직접 입력, 분기, 검증, 기록에 쓰이지 않으면 넣지 않는다.
이 문서는 상위 목표나 실행 경로 설명을 맡지 않는다.

## 2. Store Boundaries

MVP는 두 저장소만 핵심으로 사용한다.

### 2.1 Site Prior Store

온보딩 결과를 저장한다.
정적이거나 반정적인 사이트 구조 정보를 담는다.
prior는 레시피(절차)가 아니라 사이트에 대한 구조적 이해다.

### 2.2 Execution Memory

실행 중 생성되는 기록을 저장한다.
한 번의 런타임에서 실제로 무엇이 일어났는지 재구성 가능해야 한다.

규칙:

- prior와 runtime trace를 같은 객체에 섞지 않는다.
- 실험용 추가 메타데이터보다 실행 분기와 감사 가능성이 우선이다.

## 3. Public Runtime Contracts

런타임이 다루는 공개 계약은 아래와 같다.

- `RunRequest`
- `RunContext`
- `PriorBundle`
- `TaskRun`
- `StepRecord`
- `ValidationRecord`
- `RecoveryRecord`
- `ApprovalEvent`

### 3.1 RunRequest

목적:
사용자 요청을 실행 가능한 입력으로 정규화한다.

필수 필드:

- `request_text`
- `task_family`
- `user_constraints`
- `risk_tolerance`

### 3.2 RunContext

목적:
현재 런타임 분기에 필요한 상태를 제공한다.

필수 필드:

- `site_id`
- `page_type_id`
- `task_family`
- `state_summary`
- `approval_state`

규칙:
`TaskRun` 생성 전 `RunContext`가 준비되어야 한다.
`approval_state`는 `not_required`, `requested`, `approved`, `rejected` 중 하나를 가져야 한다.
`page_type_id`를 확정하지 못하면 null 대신 `unresolved`를 사용한다.

### 3.3 PriorBundle

목적:
선택된 site prior를 한 번에 주입하기 위한 묶음이다.

필수 필드:

- `site_profile`
- `page_types`
- `action_schemas`
- `validator_rules`
- `policy_rules`
- `failure_patterns`

## 4. Site Prior Store Entities

### 4.1 SiteProfile

목적:
사이트 수준 기본 설정과 온보딩 상태를 표현한다.

필수 필드:

- `site_id`
- `site_key`
- `domain`
- `login_type`
- `onboarding_status`
- `default_execution_mode`
- `prior_confidence`

메모:
router는 `prior_confidence`와 `ActionSchema` 존재 여부를 함께 보고 fast path를 선택한다.

### 4.2 PageType

목적:
현재 페이지가 어떤 종류인지와 분류 신호를 표현한다.

필수 필드:

- `page_type_id`
- `site_id`
- `page_key`
- `url_patterns`
- `structural_signals`

메모:
구조 prior는 `SiteProfile`, `PageType` 중심으로 유지한다.
`url_patterns`를 우선 사용하고 `structural_signals`로 보조 판단한다.
단일하게 고르지 못하면 `page_type_id=unresolved`로 기록한다.

### 4.3 ActionSchema

목적:
사이트에서 반복적으로 사용하는 핵심 액션과 그 전후 상태를 정의한다.

필수 필드:

- `action_schema_id`
- `site_id`
- `action_key`
- `preconditions`
- `postconditions`
- `preferred_locator_strategy`

메모:
`preconditions`와 `postconditions`는 사이트 그래프의 엣지 정보다.
LLM은 이 그래프를 탐색해 태스크 수행 경로를 자율 추론한다.
절차적 workflow 힌트는 별도 엔터티로 두지 않으며, ActionSchema만으로 경로 추론이 가능해야 한다.

### 4.4 ValidatorRule

목적:
무엇을 성공으로 볼지 정의한다.

필수 필드:

- `validator_rule_id`
- `site_id`
- `task_family`
- `rule_type`
- `pass_criteria`

메모:
기본 조회 기준은 `site_id + task_family`이며, 각 조합에 최소 1개 기본 규칙이 있어야 한다.

### 4.5 PolicyRule

목적:
허용, 차단, 승인 요구 조건을 정의한다.

필수 필드:

- `policy_rule_id`
- `site_id`
- `action_key`
- `policy_type`
- `policy_decision`

메모:
기본 조회 기준은 `site_id + action_key`다.

### 4.6 FailurePattern

목적:
자주 발생하는 실패 유형과 기본 recovery 힌트를 저장한다.

필수 필드:

- `failure_pattern_id`
- `site_id`
- `failure_type`
- `detection_signal`
- `recommended_recovery`

메모:
`FailurePattern`은 recovery 보조 prior이며 fast path 진입의 필수 조건은 아니다.

## 5. Execution Memory Entities

### 5.1 TaskRun

목적:
한 번의 요청 실행 전체를 대표한다.

필수 필드:

- `task_run_id`
- `request_text`
- `site_id`
- `task_family`
- `run_mode`
- `status`
- `started_at`
- `ended_at`
- `prior_used`
- `validator_used`
- `recovery_used`

### 5.2 StepRecord

목적:
개별 액션 또는 단계의 실행 기록을 남긴다.

필수 필드:

- `step_record_id`
- `task_run_id`
- `step_index`
- `step_type`
- `status`
- `pre_state_summary`
- `post_state_summary`

### 5.3 ValidationRecord

목적:
validator 실행 결과를 기록한다.

필수 필드:

- `validation_record_id`
- `task_run_id`
- `validator_rule_id`
- `result`
- `validated_at`

### 5.4 RecoveryRecord

목적:
실패 대응 시도와 결과를 기록한다.

필수 필드:

- `recovery_record_id`
- `task_run_id`
- `failure_pattern_id`
- `recovery_action`
- `recovery_result`
- `recorded_at`

### 5.5 ApprovalEvent

목적:
승인 요청, 승인 완료, 거절을 기록한다.

필수 필드:

- `approval_event_id`
- `task_run_id`
- `action_key`
- `approval_status`
- `reason`
- `recorded_at`

## 6. Runtime Enums

### 6.1 TaskRun.status

- `pending`
- `running`
- `approval_wait`
- `validated`
- `failed`
- `handoff`
- `cancelled`

### 6.2 StepRecord.status

- `pending`
- `running`
- `succeeded`
- `failed`
- `skipped`

### 6.3 ValidationRecord.result

- `pass`
- `fail`
- `partial`

### 6.4 RecoveryRecord.recovery_result

- `success`
- `failed`
- `handoff`
- `approval_wait`

### 6.5 SiteProfile.onboarding_status

- `draft`
- `active`
- `stale`
- `disabled`

### 6.6 ApprovalEvent.approval_status

- `requested`
- `approved`
- `rejected`

## 7. Contract Rules

- `PriorBundle`은 `SiteProfile`, 관련 `PageType`, `ActionSchema`, `ValidatorRule`, `PolicyRule`, `FailurePattern`의 묶음이다.
- `RunContext`는 현재 `site_id`, `page_type_id`, `task_family`, state summary, approval state를 포함해야 한다.
- `TaskRun` 하나에 여러 `StepRecord`, `ValidationRecord`, `RecoveryRecord`, `ApprovalEvent`가 연결된다.
- `ValidationRecord`, `RecoveryRecord`, `ApprovalEvent`는 모두 독립 실행 단위가 아니라 `task_run_id`에 종속된다.
- approval 대기 중에는 `TaskRun.status=approval_wait`와 `ApprovalEvent.approval_status=requested`를 함께 기록한다.
- 승인 후 실행이 재개되면 `TaskRun.status=running`으로 복귀한다.
- validator와 policy는 분리한다.
  성공 판정 기준은 `ValidatorRule`, 실행 허용/차단 기준은 `PolicyRule`이 맡는다.
- recovery 성공은 곧바로 성공을 의미하지 않으며, validator 재실행 후 `pass`일 때만 성공으로 처리한다.
- 실험 확장 필드는 MVP 핵심 계약에 넣지 않는다.

## 8. Excluded from MVP Contracts

다음 항목은 데이터 계약에서 제외한다.

- `WorkflowHint` 및 절차적 workflow 엔터티
- 독립 `StatePrior` 엔터티
- 독립 `StructuralPrior` 테이블 집합
- benchmark, comparison arm, model track 전용 필드
- stale/drift 장기 관리 정책 세부 필드
- Knowledge Assets 관련 저장 구조
- ontology 설명용 메타 필드
- `Execution Memory -> Site Prior Store` 자동 승격 파이프라인
