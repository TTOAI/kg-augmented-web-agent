from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# --- 에이전트 실행 결과 타입 ---

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
    inputs: list[str] = field(default_factory=list)  # placeholder / label 기반 입력 필드
    dropdown_options: list[str] = field(default_factory=list)  # 열린 드롭다운/메뉴 항목


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
