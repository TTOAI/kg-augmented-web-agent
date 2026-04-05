from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .enums import RecoveryResult
from .store import ExecutionStore
from .types import FailurePattern, RecoveryRecord


async def execute_recovery(
    *,
    task_run_id: str,
    failure_patterns: list[FailurePattern],
    execution_store: ExecutionStore,
) -> RecoveryResult:
    """FailurePattern 기반 recovery stub을 실행하고 RecoveryRecord를 기록한다.

    이번 구현은 failure_patterns가 있으면 첫 번째 패턴을 기반으로 recovery를 시도한다.
    실제 브라우저 조작 없이 기록만 남기고 SUCCESS를 반환한다.
    failure_patterns가 비어 있으면 FAILED를 반환한다.
    """
    if not failure_patterns:
        return RecoveryResult.FAILED

    pattern = failure_patterns[0]
    record = RecoveryRecord(
        recovery_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        failure_pattern_id=pattern.failure_pattern_id,
        recovery_action=pattern.recommended_recovery,
        recovery_result=RecoveryResult.SUCCESS,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    execution_store.save_recovery_record(record)
    return RecoveryResult.SUCCESS
