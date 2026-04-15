"""Planner 인터페이스 — task와 observation으로부터 sub-goal 목록을 생성한다."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..types import SubGoal


@runtime_checkable
class Planner(Protocol):
    """태스크 분해 계약."""

    def plan(
        self,
        *,
        task: str,
        task_type: str,
        observation: Any,
        llm: Any,
    ) -> list[SubGoal]: ...
