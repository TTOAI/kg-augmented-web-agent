from __future__ import annotations

from enum import StrEnum


class KBConfidence(StrEnum):
    """라우터가 사용하는 KB confidence 분류."""

    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


class ApprovalState(StrEnum):
    """RunContext에서 사용하는 승인 상태."""

    NOT_REQUIRED = "not_required"
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"


class RouteKind(StrEnum):
    """문서 기준 runtime path."""

    FAST_PATH = "fast_path"
    PARTIAL_KB = "partial_kb"
    FALLBACK = "fallback"
    APPROVAL_FIRST = "approval_first"


class TaskRunStatus(StrEnum):
    """TaskRun.status 허용값."""

    PENDING = "pending"
    RUNNING = "running"
    APPROVAL_WAIT = "approval_wait"
    VALIDATED = "validated"
    FAILED = "failed"
    HANDOFF = "handoff"
    CANCELLED = "cancelled"


class StepRecordStatus(StrEnum):
    """StepRecord.status 허용값."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ValidationResult(StrEnum):
    """ValidationRecord.result 허용값."""

    PASS = "pass"
    FAIL = "fail"
    PARTIAL = "partial"


class RecoveryResult(StrEnum):
    """RecoveryRecord.recovery_result 허용값."""

    SUCCESS = "success"
    FAILED = "failed"
    HANDOFF = "handoff"
    APPROVAL_WAIT = "approval_wait"


class SiteOnboardingStatus(StrEnum):
    """SiteProfile.onboarding_status 허용값."""

    DRAFT = "draft"
    ACTIVE = "active"
    STALE = "stale"
    DISABLED = "disabled"


class ApprovalEventStatus(StrEnum):
    """ApprovalEvent.approval_status 허용값."""

    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
