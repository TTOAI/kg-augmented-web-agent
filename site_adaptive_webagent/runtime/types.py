from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

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

# --- 에이전트 실행 결과 타입 ---

IntentAction = Literal["goto_url", "inspect_page", "click_target", "search_target", "unsupported"]
TaskType = Literal["RETRIEVE", "MUTATE", "NAVIGATE"]
TaskStatus = Literal[
    "SUCCESS",
    "ACTION_NOT_ALLOWED_ERROR",
    "PERMISSION_DENIED_ERROR",
    "NOT_FOUND_ERROR",
    "DATA_VALIDATION_ERROR",
    "UNKNOWN_ERROR",
]


@dataclass(slots=True)
class IntentPlan:
    """task intent를 얕게 분류한 결과."""

    task_type: TaskType
    action: IntentAction
    target_phrase: str | None
    target_terms: list[str]
    explicit_url: str | None = None


@dataclass(slots=True)
class PageObservation:
    """현재 페이지에서 관찰한 핵심 상태 스냅샷."""

    url: str
    title: str
    headings: list[str]
    text_lines: list[str]
    links: list[str]
    buttons: list[str]
    inputs: list[str] = field(default_factory=list)  # placeholder / label 기반 입력 필드


@dataclass(slots=True)
class ExecutionOutcome:
    """브라우저 실행의 중간 결과."""

    task_type: TaskType
    status: TaskStatus
    retrieved_data: list[str] | None = None
    error_details: str | None = None


@dataclass(slots=True)
class BrowserSession:
    """브라우저 실행에 필요한 Playwright 컨텍스트."""

    pages: list[Any]
    sites: list[str]
    start_urls: list[str]
    plan: IntentPlan


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
    display_name: str
    base_url: str
    auth_type: str
    onboarding_status: SiteOnboardingStatus
    prior_confidence: PriorConfidence


@dataclass(slots=True)
class PageType:
    """페이지 유형 prior — 사이트 그래프의 노드."""

    page_type_id: str
    site_id: str
    page_key: str
    display_name: str = ""
    description: str = ""
    url_patterns: list[str] = field(default_factory=list)
    structural_signals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ActionSchema:
    """반복 액션 정의 — 사이트 그래프의 엣지."""

    action_schema_id: str
    site_id: str
    action_key: str
    display_name: str = ""
    description: str = ""
    source_page_key: str = ""
    target_page_key: str | None = None
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    locator_strategy: str = ""
    locator_value: str = ""


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
    reason: str = ""


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
