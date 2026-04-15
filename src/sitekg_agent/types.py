"""sitekg_agent 공용 타입.

agent/runtime에서 공유하는 데이터 모델을 모두 이 파일에 모은다.
외부 계약(AgentRunResult)과 내부 실행 타입(PageObservation, ExecutionOutcome 등) 양쪽 포함.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# --- 외부 노출 타입 ------------------------------------------------------------

IntentAction = Literal["goto_url", "inspect_page", "click_target", "search_target", "unsupported"]
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


# --- 내부 실행 타입 ------------------------------------------------------------


@dataclass(slots=True)
class IntentPlan:
    """task intent를 얕게 분류한 결과."""

    task_type: TaskType
    action: IntentAction
    target_phrase: str | None
    target_terms: list[str]
    explicit_url: str | None = None


@dataclass(slots=True)
class PageObservation:
    """현재 페이지에서 관찰한 핵심 상태 스냅샷."""

    url: str
    title: str
    headings: list[str]
    text_lines: list[str]
    links: list[str]
    buttons: list[str]
    inputs: list[str] = field(default_factory=list)
    dropdown_options: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionOutcome:
    """브라우저 실행의 중간 결과."""

    task_type: TaskType
    status: TaskStatus
    retrieved_data: list[str] | None = None
    error_details: str | None = None


@dataclass(slots=True)
class BrowserSession:
    """브라우저 실행에 필요한 Playwright 컨텍스트."""

    pages: list[Any]
    sites: list[str]
    start_urls: list[str]
    plan: IntentPlan


class SubGoal:
    """태스크를 쪼갠 하위 목표."""

    __slots__ = ("goal", "goal_type")

    def __init__(self, goal: str, goal_type: str = "action"):
        self.goal = goal
        self.goal_type = goal_type  # "navigation" | "action"

    def __repr__(self) -> str:
        return f"{self.goal} [{self.goal_type}]"
