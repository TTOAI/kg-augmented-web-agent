from __future__ import annotations

from dataclasses import dataclass, field

from .enums import (
    ApprovalEventStatus,
    ApprovalState,
    PriorConfidence,
    RecoveryResult,
    SiteOnboardingStatus,
    StepRecordStatus,
    TaskRunStatus,
    ValidationResult,
)


@dataclass(slots=True)
class RunRequest:
    """사용자 요청의 runtime 정규화 입력."""

    request_text: str
    task_family: str
    user_constraints: list[str] = field(default_factory=list)
    risk_tolerance: str = "medium"


@dataclass(slots=True)
class RunContext:
    """런타임 분기에 필요한 현재 상태."""

    site_id: str
    page_type_id: str
    task_family: str
    state_summary: str
    approval_state: ApprovalState = ApprovalState.NOT_REQUIRED


@dataclass(slots=True)
class SiteProfile:
    """사이트 수준 prior."""

    site_id: str
    site_key: str
    domain: str
    login_type: str
    onboarding_status: SiteOnboardingStatus
    default_execution_mode: str
    prior_confidence: PriorConfidence


@dataclass(slots=True)
class PageType:
    """페이지 유형 prior."""

    page_type_id: str
    site_id: str
    page_key: str
    url_patterns: list[str] = field(default_factory=list)
    structural_signals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ActionSchema:
    """반복 액션 정의."""

    action_schema_id: str
    site_id: str
    action_key: str
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    preferred_locator_strategy: str = ""


@dataclass(slots=True)
class WorkflowHint:
    """task family별 workflow 힌트."""

    workflow_hint_id: str
    site_id: str
    task_family: str
    typical_step_order: list[str] = field(default_factory=list)
    branch_points: list[str] = field(default_factory=list)
    expected_terminal_states: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ValidatorRule:
    """성공 판정 규칙."""

    validator_rule_id: str
    site_id: str
    task_family: str
    rule_type: str
    pass_criteria: str


@dataclass(slots=True)
class PolicyRule:
    """실행 허용/승인 정책."""

    policy_rule_id: str
    site_id: str
    action_key: str
    policy_type: str
    policy_decision: str


@dataclass(slots=True)
class FailurePattern:
    """실패 및 recovery 힌트."""

    failure_pattern_id: str
    site_id: str
    failure_type: str
    detection_signal: str
    recommended_recovery: str


@dataclass(slots=True)
class PriorBundle:
    """선택된 site prior 묶음."""

    site_profile: SiteProfile
    page_types: list[PageType] = field(default_factory=list)
    action_schemas: list[ActionSchema] = field(default_factory=list)
    workflow_hints: list[WorkflowHint] = field(default_factory=list)
    validator_rules: list[ValidatorRule] = field(default_factory=list)
    policy_rules: list[PolicyRule] = field(default_factory=list)
    failure_patterns: list[FailurePattern] = field(default_factory=list)


@dataclass(slots=True)
class TaskRun:
    """한 번의 실행 전체를 대표하는 기록."""

    task_run_id: str
    request_text: str
    site_id: str
    task_family: str
    run_mode: str
    status: TaskRunStatus
    started_at: str
    ended_at: str
    prior_used: bool
    validator_used: bool
    recovery_used: bool


@dataclass(slots=True)
class StepRecord:
    """개별 단계 실행 기록."""

    step_record_id: str
    task_run_id: str
    step_index: int
    step_type: str
    status: StepRecordStatus
    pre_state_summary: str
    post_state_summary: str


@dataclass(slots=True)
class ValidationRecord:
    """validator 실행 결과."""

    validation_record_id: str
    task_run_id: str
    validator_rule_id: str
    result: ValidationResult
    validated_at: str


@dataclass(slots=True)
class RecoveryRecord:
    """recovery 실행 결과."""

    recovery_record_id: str
    task_run_id: str
    failure_pattern_id: str
    recovery_action: str
    recovery_result: RecoveryResult
    recorded_at: str


@dataclass(slots=True)
class ApprovalEvent:
    """승인 요청/결과 기록."""

    approval_event_id: str
    task_run_id: str
    action_key: str
    approval_status: ApprovalEventStatus
    reason: str
    recorded_at: str
