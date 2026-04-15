from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

TaskType = Literal["NAVIGATE", "RETRIEVE", "MUTATE"]
TaskStatus = Literal[
    "SUCCESS",
    "UNKNOWN_ERROR",
    "NOT_FOUND_ERROR",
    "PERMISSION_DENIED_ERROR",
    "ACTION_NOT_ALLOWED_ERROR",
    "DATA_VALIDATION_ERROR",
]

RetrievedItem = str | int | float | bool | dict[str, Any] | None


@dataclass(slots=True)
class AgentRunResult:
    """에이전트 정책이 반환하는 정규화된 결과 (벤치마크 출력 계약)."""

    task_type: TaskType
    status: TaskStatus
    retrieved_data: list[RetrievedItem] | None = None
    error_details: str | None = None

    @classmethod
    def unknown_error(cls, message: str) -> "AgentRunResult":
        """벤치마크와 호환되는 예기치 않은 실패 결과를 반환한다."""
        return cls(
            task_type="NAVIGATE",
            status="UNKNOWN_ERROR",
            retrieved_data=None,
            error_details=message,
        )
