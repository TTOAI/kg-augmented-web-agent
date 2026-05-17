from __future__ import annotations

import re
from typing import Any

from .types import IntentPlan, TaskType

SEARCH_INPUT_SELECTORS = (
    "input[placeholder*='search' i]",
    "input[name*='search' i]",
    "input[aria-label*='search' i]",
    "input[type='search']",
)
HEADING_SELECTORS = ("h1", "h2", "[role='heading']")
TEXT_BLOCK_SELECTORS = ("main", "article", "body")
LINK_SELECTORS = ("a",)
BUTTON_SELECTORS = ("button", "[role='button']")


def analyze_intent(intent: str, llm: Any = None) -> IntentPlan:
    """자연어 intent를 task_type 분류 결과로 바꾼다.

    LLM이 제공되면 LLM으로 task_type을 분류한다. LLM이 없으면 NAVIGATE 기본값을 사용한다.
    target_phrase / target_terms는 LLM 기반 sub-goal planner가 직접 사용하므로 빈 값을 둔다.

    불변식: intent에 http(s) URL이 있어도 NAVIGATE로 강제 분류하지 않는다.
    URL을 **데이터로** 담는 MUTATE 태스크(예: URL을 설정값으로 받는 경우)를
    NAVIGATE로 오분류하면 치명적 실험 결함이 되므로, 모든 intent를 LLM 분류에 맡긴다.
    """
    explicit_url = extract_explicit_url(intent)

    if llm is not None:
        from .llm import classify_task_type  # 지연 임포트로 순환 방지
        task_type: TaskType = classify_task_type(intent, llm)
    else:
        task_type = "NAVIGATE"

    return IntentPlan(
        task_type=task_type,
        action="inspect_page",
        target_phrase=None,
        target_terms=[],
        explicit_url=explicit_url,  # 참고용으로만 보존; 실행 경로에서는 사용되지 않음
    )


def extract_explicit_url(intent: str) -> str | None:
    """intent 안에 들어 있는 첫 HTTP(S) URL을 반환한다."""
    match = re.search(r"https?://\S+", intent)
    if match:
        return match.group(0).rstrip(".,)")
    return None


def collapse_whitespace(text: str) -> str:
    """보이는 토큰은 유지하면서 공백을 정규화한다."""
    return " ".join(text.split())


def normalize_text(text: str) -> str:
    """매칭을 위해 텍스트를 정규화한다."""
    return collapse_whitespace(text).lower()
