from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .browser import execute_plan, observe_page
from .enums import ApprovalEventStatus, RecoveryResult, StepRecordStatus, TaskRunStatus, ValidationResult
from .recovery import execute_recovery
from .store import ExecutionStore
from .types import ApprovalEvent, BrowserSession, ExecutionOutcome, FailurePattern, StepRecord, ValidatorRule
from .validator import validate

_TASK_TO_RUN_STATUS: dict[str, TaskRunStatus] = {
    "SUCCESS": TaskRunStatus.VALIDATED,
    "ACTION_NOT_ALLOWED_ERROR": TaskRunStatus.HANDOFF,
    "PERMISSION_DENIED_ERROR": TaskRunStatus.HANDOFF,
    "NOT_FOUND_ERROR": TaskRunStatus.FAILED,
    "DATA_VALIDATION_ERROR": TaskRunStatus.FAILED,
    "UNKNOWN_ERROR": TaskRunStatus.FAILED,
}


async def execute_fast_path(
    *,
    task_run_id: str,
    validator_rules: list[ValidatorRule],
    failure_patterns: list[FailurePattern],
    execution_store: ExecutionStore,
    browser_session: BrowserSession | None = None,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """fast path 실행.

    browser_session이 있으면 실제 브라우저 실행 결과를 TaskRunStatus로 매핑한다.
    없으면 결정론적 stub(validator → recovery → 재검증)을 실행한다.

    Returns: (final_status, validator_used, recovery_used, execution_outcome)
    """
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="fast_path",
            browser_session=browser_session,
            execution_store=execution_store,
        )

    # --- stub 동작 ---
    step = _make_step(task_run_id, "fast_path")

    result = validate(validator_rules)
    validator_used = True
    recovery_used = False

    if result == ValidationResult.PASS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.SUCCEEDED, "validator pass"))
        return TaskRunStatus.VALIDATED, validator_used, recovery_used, None

    recovery_result = await execute_recovery(
        task_run_id=task_run_id,
        failure_patterns=failure_patterns,
        execution_store=execution_store,
    )
    recovery_used = True

    if recovery_result != RecoveryResult.SUCCESS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.FAILED, "recovery 실패"))
        return TaskRunStatus.HANDOFF, validator_used, recovery_used, None

    revalidation_result = validate(validator_rules)
    if revalidation_result == ValidationResult.PASS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.SUCCEEDED, "재검증 pass"))
        return TaskRunStatus.VALIDATED, validator_used, recovery_used, None

    execution_store.save_step_record(_finish_step(step, StepRecordStatus.FAILED, "재검증 실패 → handoff"))
    return TaskRunStatus.HANDOFF, validator_used, recovery_used, None


async def execute_partial_prior(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
    browser_session: BrowserSession | None = None,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """partial prior path 실행.

    browser_session이 있으면 실제 브라우저 실행을 수행한다. (prior 안내 없는 best-effort)
    없으면 FAILED stub을 반환한다.
    """
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="partial_prior",
            browser_session=browser_session,
            execution_store=execution_store,
        )

    step = _make_step(task_run_id, "partial_prior")
    execution_store.save_step_record(
        _finish_step(step, StepRecordStatus.FAILED, "prior 불충분으로 실행 실패")
    )
    return TaskRunStatus.FAILED, False, False, None


async def execute_fallback(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
    browser_session: BrowserSession | None = None,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """fallback path 실행.

    browser_session이 있으면 prior 없이 범용 브라우저 실행을 수행한다.
    없으면 HANDOFF stub을 반환한다.
    """
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="fallback",
            browser_session=browser_session,
            execution_store=execution_store,
        )

    step = _make_step(task_run_id, "fallback")
    execution_store.save_step_record(
        _finish_step(step, StepRecordStatus.SKIPPED, "site 미온보딩으로 handoff")
    )
    return TaskRunStatus.HANDOFF, False, False, None


async def execute_approval_first(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
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
    return TaskRunStatus.APPROVAL_WAIT, False, False, None


# --- 내부 헬퍼 ---

async def _run_with_browser(
    *,
    task_run_id: str,
    step_type: str,
    browser_session: BrowserSession,
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome]:
    """브라우저를 실행하고 ExecutionOutcome을 TaskRunStatus로 매핑한다."""
    primary_page = browser_session.pages[0]
    observation = await observe_page(primary_page)

    if browser_session.plan.action == "unsupported":
        outcome = ExecutionOutcome(
            task_type=browser_session.plan.task_type,
            status="UNKNOWN_ERROR",
            error_details=f"지원하지 않는 intent입니다",
        )
    else:
        outcome = await execute_plan(
            plan=browser_session.plan,
            sites=browser_session.sites,
            start_urls=browser_session.start_urls,
            page=primary_page,
            observation=observation,
        )

    task_status = _TASK_TO_RUN_STATUS.get(outcome.status, TaskRunStatus.FAILED)
    step_status = StepRecordStatus.SUCCEEDED if task_status == TaskRunStatus.VALIDATED else StepRecordStatus.FAILED

    step = _make_step(task_run_id, step_type)
    execution_store.save_step_record(_finish_step(step, step_status, outcome.status))
    return task_status, False, False, outcome


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
