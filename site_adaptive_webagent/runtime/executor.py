from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from .enums import ApprovalEventStatus, RecoveryResult, StepRecordStatus, TaskRunStatus, ValidationResult
from .recovery import execute_recovery
from .store import ExecutionStore
from .types import ApprovalEvent, FailurePattern, StepRecord, ValidatorRule
from .validator import validate

# execute_fn 타입 alias: 인자 없이 호출하면 AgentRunResult-like 객체를 반환하는 코루틴
ExecuteFn = Callable[[], Awaitable[Any]]

_AGENT_TO_TASK_STATUS: dict[str, TaskRunStatus] = {
    "SUCCESS": TaskRunStatus.VALIDATED,
    "ACTION_NOT_ALLOWED_ERROR": TaskRunStatus.HANDOFF,
    "PERMISSION_DENIED_ERROR": TaskRunStatus.HANDOFF,
    "NOT_FOUND_ERROR": TaskRunStatus.FAILED,
    "DATA_VALIDATION_ERROR": TaskRunStatus.FAILED,
    "UNKNOWN_ERROR": TaskRunStatus.FAILED,
}


def _map_agent_status(agent_status: str) -> TaskRunStatus:
    return _AGENT_TO_TASK_STATUS.get(agent_status, TaskRunStatus.FAILED)


async def execute_fast_path(
    *,
    task_run_id: str,
    validator_rules: list[ValidatorRule],
    failure_patterns: list[FailurePattern],
    execution_store: ExecutionStore,
    execute_fn: ExecuteFn | None = None,
) -> tuple[TaskRunStatus, bool, bool]:
    """fast path 실행.

    execute_fn이 있으면 실제 브라우저 실행 결과를 TaskRunStatus로 매핑한다.
    없으면 결정론적 stub(validator → recovery → 재검증)을 실행한다.

    Returns: (final_status, validator_used, recovery_used)
    """
    if execute_fn is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="fast_path",
            execute_fn=execute_fn,
            execution_store=execution_store,
        )

    # --- stub 동작 ---
    step = _make_step(task_run_id, "fast_path")

    result = validate(validator_rules)
    validator_used = True
    recovery_used = False

    if result == ValidationResult.PASS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.SUCCEEDED, "validator pass"))
        return TaskRunStatus.VALIDATED, validator_used, recovery_used

    recovery_result = await execute_recovery(
        task_run_id=task_run_id,
        failure_patterns=failure_patterns,
        execution_store=execution_store,
    )
    recovery_used = True

    if recovery_result != RecoveryResult.SUCCESS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.FAILED, "recovery 실패"))
        return TaskRunStatus.HANDOFF, validator_used, recovery_used

    revalidation_result = validate(validator_rules)
    if revalidation_result == ValidationResult.PASS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.SUCCEEDED, "재검증 pass"))
        return TaskRunStatus.VALIDATED, validator_used, recovery_used

    execution_store.save_step_record(_finish_step(step, StepRecordStatus.FAILED, "재검증 실패 → handoff"))
    return TaskRunStatus.HANDOFF, validator_used, recovery_used


async def execute_partial_prior(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
    execute_fn: ExecuteFn | None = None,
) -> tuple[TaskRunStatus, bool, bool]:
    """partial prior path 실행.

    execute_fn이 있으면 실제 브라우저 실행을 수행한다. (prior 안내 없는 best-effort)
    없으면 FAILED stub을 반환한다.
    """
    if execute_fn is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="partial_prior",
            execute_fn=execute_fn,
            execution_store=execution_store,
        )

    step = _make_step(task_run_id, "partial_prior")
    execution_store.save_step_record(
        _finish_step(step, StepRecordStatus.FAILED, "prior 불충분으로 실행 실패")
    )
    return TaskRunStatus.FAILED, False, False


async def execute_fallback(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
    execute_fn: ExecuteFn | None = None,
) -> tuple[TaskRunStatus, bool, bool]:
    """fallback path 실행.

    execute_fn이 있으면 prior 없이 범용 브라우저 실행을 수행한다.
    없으면 HANDOFF stub을 반환한다.
    """
    if execute_fn is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="fallback",
            execute_fn=execute_fn,
            execution_store=execution_store,
        )

    step = _make_step(task_run_id, "fallback")
    execution_store.save_step_record(
        _finish_step(step, StepRecordStatus.SKIPPED, "site 미온보딩으로 handoff")
    )
    return TaskRunStatus.HANDOFF, False, False


async def execute_approval_first(
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


# --- 내부 헬퍼 ---

async def _run_with_browser(
    *,
    task_run_id: str,
    step_type: str,
    execute_fn: ExecuteFn,
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool]:
    """execute_fn을 실행하고 AgentRunResult.status를 TaskRunStatus로 매핑한다."""
    agent_result = await execute_fn()
    agent_status = getattr(agent_result, "status", "UNKNOWN_ERROR")
    task_status = _map_agent_status(agent_status)
    step_status = StepRecordStatus.SUCCEEDED if task_status == TaskRunStatus.VALIDATED else StepRecordStatus.FAILED

    step = _make_step(task_run_id, step_type)
    execution_store.save_step_record(_finish_step(step, step_status, agent_status))
    return task_status, False, False


def _make_step(task_run_id: str, step_type: str) -> StepRecord:
    return StepRecord(
        step_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        step_index=0,
        step_type=step_type,
        status=StepRecordStatus.RUNNING,
        pre_state_summary=f"{step_type} 시작",
        post_state_summary="",
    )


def _finish_step(step: StepRecord, status: StepRecordStatus, summary: str) -> StepRecord:
    return StepRecord(
        step_record_id=step.step_record_id,
        task_run_id=step.task_run_id,
        step_index=step.step_index,
        step_type=step.step_type,
        status=status,
        pre_state_summary=step.pre_state_summary,
        post_state_summary=summary,
    )
