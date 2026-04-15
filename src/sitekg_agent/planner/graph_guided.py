"""KG 기반 planner — 스켈레톤.

추후 KG retrieval을 plan 생성에 반영하는 로직을 이 파일에 구현한다.
"""
from __future__ import annotations

from typing import Any

from ..types import SubGoal


def build_plan_with_kg(
    *,
    task: str,
    task_type: str,
    observation: Any,
    llm: Any,
    kg: Any,
) -> list[SubGoal]:
    """KG를 참고하는 sub-goal 분해. 현재는 미구현."""
    raise NotImplementedError(
        "graph-guided planner는 재설계 후속 단계에서 구현된다."
    )
