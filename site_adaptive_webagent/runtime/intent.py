from __future__ import annotations

import re

from .types import IntentAction, IntentPlan, PageObservation, TaskType

STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "for",
    "from",
    "go",
    "how",
    "i",
    "in",
    "is",
    "me",
    "my",
    "of",
    "on",
    "open",
    "page",
    "show",
    "the",
    "to",
    "what",
}
RETRIEVE_KEYWORDS = ("find", "what is", "show", "get", "extract", "how many", "count", "list")
NAVIGATE_KEYWORDS = ("open", "go to", "navigate", "visit")
MUTATE_KEYWORDS = ("search", "click", "submit", "create", "update", "edit", "fill")

SEARCH_INPUT_SELECTORS = (
    "input[type='search']",
    "input[placeholder*='search' i]",
    "input[name*='search' i]",
    "input[aria-label*='search' i]",
)
HEADING_SELECTORS = ("h1", "h2", "[role='heading']")
TEXT_BLOCK_SELECTORS = ("main", "article", "body")
LINK_SELECTORS = ("a",)
BUTTON_SELECTORS = ("button", "[role='button']")


def analyze_intent(intent: str) -> IntentPlan:
    """자연어 intent를 얕고 결정적인 실행 계획으로 바꾼다."""
    normalized_intent = normalize_text(intent)
    explicit_url = extract_explicit_url(intent)
    target_phrase = extract_target_phrase(intent)
    target_terms = extract_target_terms(target_phrase or intent)

    if explicit_url:
        return IntentPlan(
            task_type="NAVIGATE",
            action="goto_url",
            target_phrase=target_phrase,
            target_terms=target_terms,
            explicit_url=explicit_url,
        )

    if contains_keyword(normalized_intent, RETRIEVE_KEYWORDS):
        return IntentPlan(
            task_type="RETRIEVE",
            action="inspect_page",
            target_phrase=target_phrase,
            target_terms=target_terms,
        )

    if contains_keyword(normalized_intent, NAVIGATE_KEYWORDS):
        return IntentPlan(
            task_type="NAVIGATE",
            action="click_target",
            target_phrase=target_phrase,
            target_terms=target_terms,
        )

    if contains_keyword(normalized_intent, MUTATE_KEYWORDS):
        action: IntentAction = "search_target" if "search" in normalized_intent else "click_target"
        return IntentPlan(
            task_type="MUTATE",
            action=action,
            target_phrase=target_phrase,
            target_terms=target_terms,
        )

    return IntentPlan(
        task_type="NAVIGATE",
        action="unsupported",
        target_phrase=target_phrase,
        target_terms=target_terms,
    )


def navigation_goal_satisfied(observation: PageObservation, plan: IntentPlan) -> bool:
    """현재 페이지가 이동 목표와 일치해 보이는지 확인한다."""
    if plan.explicit_url and plan.explicit_url in observation.url:
        return True
    if not plan.target_terms:
        return False
    haystacks = [observation.url, observation.title, *observation.headings]
    return any(all(term in normalize_text(text) for term in plan.target_terms) for text in haystacks)


def select_best_match(observation: PageObservation, target_terms: list[str]) -> str | None:
    """추출에 가장 적합한 보이는 텍스트를 고른다."""
    candidates = [
        *observation.headings,
        *observation.text_lines,
        *observation.links,
        *observation.buttons,
    ]
    if not target_terms:
        return select_fallback_value(observation)

    normalized_candidates = [normalize_text(candidate) for candidate in candidates if candidate.strip()]
    for raw_candidate, normalized_candidate in zip(candidates, normalized_candidates, strict=False):
        if all(term in normalized_candidate for term in target_terms):
            return raw_candidate.strip()

    for raw_candidate, normalized_candidate in zip(candidates, normalized_candidates, strict=False):
        if any(term in normalized_candidate for term in target_terms):
            return raw_candidate.strip()
    return None


def select_fallback_value(observation: PageObservation) -> str | None:
    """명시적인 target term이 없을 때 페이지 기반 기본값을 반환한다."""
    for collection in (observation.headings, [observation.title], observation.text_lines):
        for text in collection:
            cleaned = text.strip()
            if cleaned:
                return cleaned
    return None


def extract_explicit_url(intent: str) -> str | None:
    """intent 안에 들어 있는 첫 HTTP(S) URL을 반환한다."""
    match = re.search(r"https?://\S+", intent)
    if match:
        return match.group(0).rstrip(".,)")
    return None


def extract_target_phrase(intent: str) -> str | None:
    """페이지나 값을 가리키는 구절을 휴리스틱하게 추출한다."""
    patterns = (
        r"(?:open|go to|navigate to|visit)\s+(?P<target>.+)",
        r"(?:find|show|get|extract|search for|search)\s+(?P<target>.+)",
        r"(?:what is|how many)\s+(?P<target>.+)",
        r"(?:click|update|create|edit)\s+(?P<target>.+)",
    )
    for pattern in patterns:
        match = re.search(pattern, intent, re.IGNORECASE)
        if match:
            target = strip_trailing_noise(match.group("target"))
            return target or None
    return strip_trailing_noise(intent) or None


def extract_target_terms(text: str) -> list[str]:
    """target 구절을 소수의 매칭용 term으로 축약한다."""
    normalized = normalize_text(text)
    words = [word for word in normalized.split() if len(word) > 1 and word not in STOPWORDS]
    if not words:
        return []
    return words[:4]


def contains_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    """정규화된 텍스트 안에 키워드가 포함되는지 확인한다."""
    return any(keyword in text for keyword in keywords)


def strip_trailing_noise(text: str) -> str:
    """문장 부호와 흔한 후행 지시어를 제거한다."""
    stripped = text.strip().strip("?.!,")
    for suffix in (" page", " site", " website"):
        if stripped.lower().endswith(suffix):
            stripped = stripped[: -len(suffix)]
    return stripped.strip()


def collapse_whitespace(text: str) -> str:
    """보이는 토큰은 유지하면서 공백을 정규화한다."""
    return " ".join(text.split())


def normalize_text(text: str) -> str:
    """매칭을 위해 텍스트를 정규화한다."""
    return collapse_whitespace(text).lower()
