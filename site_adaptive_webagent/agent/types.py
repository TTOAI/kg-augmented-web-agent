from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

TaskType = Literal["RETRIEVE", "MUTATE", "NAVIGATE"]
TaskStatus = Literal[
    "SUCCESS",
    "ACTION_NOT_ALLOWED_ERROR",
    "PERMISSION_DENIED_ERROR",
    "NOT_FOUND_ERROR",
    "DATA_VALIDATION_ERROR",
    "UNKNOWN_ERROR",
]
RetrievedItem = str | int | float | bool | dict[str, Any] | None


@dataclass(slots=True)
class AgentRunResult:
    """에이전트 정책이 반환하는 정규화된 결과."""

    task_type: TaskType
    status: TaskStatus
    retrieved_data: list[RetrievedItem] | None = None
    error_details: str | None = None

    @classmethod
    def not_implemented(
        cls,
        message: str = "site_adaptive_webagent/agent/core.py is not implemented yet",
    ) -> "AgentRunResult":
        """미구현 에이전트를 위한 안전한 기본 결과를 반환한다."""
        return cls(
            task_type="NAVIGATE",
            status="UNKNOWN_ERROR",
            retrieved_data=None,
            error_details=message,
        )

    @classmethod
    def unknown_error(cls, message: str) -> "AgentRunResult":
        """벤치마크와 호환되는 예기치 않은 실패 결과를 반환한다."""
        return cls(
            task_type="NAVIGATE",
            status="UNKNOWN_ERROR",
            retrieved_data=None,
            error_details=message,
        )
