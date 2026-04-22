"""WebArena-Verified-specific outcome types.

Benchmark의 status enum / retrieved_data 포맷은 이 벤치마크 고유 contract이므로
**benchmark 레이어에** 정의한다. Agent runtime은 중립적인 `AgentVerdict`만
배출하고, `outcome_classifier`가 이를 이곳 타입으로 매핑한다.

- `WebArenaStatus`: WebArena-Verified의 status 값 enum.
- `WebArenaRunResult`: agent_response.json의 4-field contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from site_adaptive_webagent.runtime.types import TaskType

WebArenaStatus = Literal[
    "SUCCESS",
    "ACTION_NOT_ALLOWED_ERROR",
    "PERMISSION_DENIED_ERROR",
    "NOT_FOUND_ERROR",
    "DATA_VALIDATION_ERROR",
    "UNKNOWN_ERROR",
]

RetrievedItem = str | int | float | bool | dict[str, Any] | None


@dataclass(slots=True)
class WebArenaRunResult:
    """agent_response.json의 benchmark-ready 형식.

    - task_type: WebArena-Verified의 task type 분류 (RETRIEVE/MUTATE/NAVIGATE).
    - status: benchmark status enum (위 `WebArenaStatus`).
    - retrieved_data: RETRIEVE의 경우 정답 값 리스트, 그 외는 None.
    - error_details: 실패 시 사유, 성공 시 None.
    """

    task_type: TaskType
    status: WebArenaStatus
    retrieved_data: list[RetrievedItem] | None = None
    error_details: str | None = None

    @classmethod
    def unknown_error(cls, message: str) -> "WebArenaRunResult":
        return cls(
            task_type="NAVIGATE",
            status="UNKNOWN_ERROR",
            retrieved_data=None,
            error_details=message,
        )
