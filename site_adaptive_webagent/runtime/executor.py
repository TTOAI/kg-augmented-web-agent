from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .enums import ApprovalEventStatus, RecoveryResult, StepRecordStatus, TaskRunStatus, ValidationResult
from .recovery import execute_recovery
from .store import ExecutionStore
from .types import ApprovalEvent, FailurePattern, StepRecord, ValidatorRule
from .validator import validate


def execute_fast_path(
    *,
    task_run_id: str,
    validator_rules: list[ValidatorRule],
    failure_patterns: list[FailurePattern],
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool]:
    """fast path stub 실행.

    validator → FAIL 시 recovery 1회 → 재검증 순으로 진행한다.
    Returns: (final_status, validator_used, recovery_used)
    """
    step = StepRecord(
        step_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        step_index=0,
        step_type="fast_path",
        status=StepRecordStatus.RUNNING,
        pre_state_summary="fast_path 시작",
        post_state_summary="",
    )

    result = validate(validator_rules)
    validator_used = True
    recovery_used = False

    if result == ValidationResult.PASS:
        step = _update_step(step, StepRecordStatus.SUCCEEDED, "validator pass")
        execution_store.save_step_record(step)
        return TaskRunStatus.VALIDATED, validator_used, recovery_used

    # validator FAIL → recovery 1회 시도
    recovery_result = execute_recovery(
        task_run_id=task_run_id,
        failure_patterns=failure_patterns,
        execution_store=execution_store,
    )
    recovery_used = True

    if recovery_result != RecoveryResult.SUCCESS:
        step = _update_step(step, StepRecordStatus.FAILED, "recovery 실패")
        execution_store.save_step_record(step)
        return TaskRunStatus.HANDOFF, validator_used, recovery_used

    # recovery 성공 후 재검증 (1회 한정)
    revalidation_result = validate(validator_rules)
    if revalidation_result == ValidationResult.PASS:
        step = _update_step(step, StepRecordStatus.SUCCEEDED, "재검증 pass")
        execution_store.save_step_record(step)
        return TaskRunStatus.VALIDATED, validator_used, recovery_used

    step = _update_step(step, StepRecordStatus.FAILED, "재검증 실패 → handoff")
    execution_store.save_step_record(step)
    return TaskRunStatus.HANDOFF, validator_used, recovery_used


def execute_partial_prior(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool]:
    """partial prior path stub 실행. prior가 부분적이므로 FAILED 반환."""
    step = StepRecord(
        step_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        step_index=0,
        step_type="partial_prior",
        status=StepRecordStatus.FAILED,
        pre_state_summary="partial_prior 시작",
        post_state_summary="prior 불충분으로 실행 실패",
    )
    execution_store.save_step_record(step)
    return TaskRunStatus.FAILED, False, False


def execute_fallback(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool]:
    """fallback path stub 실행. site 미온보딩이므로 HANDOFF 반환."""
    step = StepRecord(
        step_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        step_index=0,
        step_type="fallback",
        status=StepRecordStatus.SKIPPED,
        pre_state_summary="fallback 시작",
        post_state_summary="site 미온보딩으로 handoff",
    )
    execution_store.save_step_record(step)
    return TaskRunStatus.HANDOFF, False, False


def execute_approval_first(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool]:
    """approval-first path stub 실행. ApprovalEvent(REQUESTED)를 기록하고 APPROVAL_WAIT 반환."""
    event = ApprovalEvent(
        approval_event_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        action_key="policy_required_action",
        approval_status=ApprovalEventStatus.REQUESTED,
        reason="policy rule이 사전 승인을 요구합니다",
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    execution_store.save_approval_event(event)
    return TaskRunStatus.APPROVAL_WAIT, False, False


def _update_step(step: StepRecord, status: StepRecordStatus, summary: str) -> StepRecord:
    return StepRecord(
        step_record_id=step.step_record_id,
        task_run_id=step.task_run_id,
        step_index=step.step_index,
        step_type=step.step_type,
        status=status,
        pre_state_summary=step.pre_state_summary,
        post_state_summary=summary,
    )
