"""Evaluator 인터페이스 — sub-goal 완료 여부·extract 결과의 검증 계약."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..types import PageObservation


@runtime_checkable
class Evaluator(Protocol):
    """에이전트 선언(done/extract)과 실제 상태를 대조한다."""

    def verify_done(
        self,
        *,
        goal: str,
        reason: str,
        current_obs: PageObservation,
        llm: Any,
        task_notes: list[str] | None = None,
        sub_goal_type: str = "",
        sub_goal_start_url: str = "",
        is_last_goal: bool = False,
    ) -> str | bool: ...
