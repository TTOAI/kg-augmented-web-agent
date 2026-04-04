from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Literal

from .types import AgentRunResult, TaskStatus, TaskType

IntentAction = Literal["goto_url", "inspect_page", "click_target", "search_target", "unsupported"]

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


@dataclass(slots=True)
class ExecutionOutcome:
    """benchmark 정규화 전의 중간 실행 결과."""

    task_type: TaskType
    status: TaskStatus
    retrieved_data: list[str] | None = None
    error_details: str | None = None

    def to_agent_result(self) -> AgentRunResult:
        """중간 실행 결과를 benchmark 응답 타입으로 변환한다."""
        return AgentRunResult(
            task_type=self.task_type,
            status=self.status,
            retrieved_data=self.retrieved_data,
            error_details=self.error_details,
        )


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


async def run_agent(  # noqa: PLR0913
    *,
    intent: str,
    sites: list[str],
    start_urls: list[str],
    task_id: int,
    context: Any,
    pages: list[Any],
    task_output_dir: Path,
) -> AgentRunResult:
    """공용 baseline 웹 에이전트 정책을 실행한다."""
    del context, task_id, task_output_dir

    if not pages:
        return AgentRunResult.unknown_error("이 task에서 열린 페이지가 없습니다")

    plan = analyze_intent(intent)
    if plan.action == "unsupported":
        return ExecutionOutcome(
            task_type=plan.task_type,
            status="UNKNOWN_ERROR",
            error_details=f"지원하지 않는 baseline intent 입니다: {intent}",
        ).to_agent_result()

    primary_page = pages[0]
    initial_observation = await observe_page(primary_page)
    outcome = await execute_plan(
        plan=plan,
        sites=sites,
        start_urls=start_urls,
        page=primary_page,
        observation=initial_observation,
    )
    return outcome.to_agent_result()


async def execute_plan(
    *,
    plan: IntentPlan,
    sites: list[str],
    start_urls: list[str],
    page: Any,
    observation: PageObservation,
) -> ExecutionOutcome:
    """작고 결정적인 브라우저 primitive로 얕은 계획을 실행한다."""
    del sites

    if plan.task_type == "RETRIEVE":
        return await execute_retrieve(plan=plan, page=page, observation=observation)
    if plan.task_type == "NAVIGATE":
        return await execute_navigate(plan=plan, page=page, observation=observation, start_urls=start_urls)
    return await execute_mutate(plan=plan, page=page, observation=observation)


async def execute_retrieve(*, plan: IntentPlan, page: Any, observation: PageObservation) -> ExecutionOutcome:
    """현재 페이지 또는 가벼운 이동 뒤에 값을 추출한다."""
    matched_text = select_best_match(observation, plan.target_terms)
    if matched_text:
        return ExecutionOutcome(task_type="RETRIEVE", status="SUCCESS", retrieved_data=[matched_text])

    if plan.target_phrase and await try_search(page, plan.target_phrase):
        refreshed = await observe_page(page)
        matched_text = select_best_match(refreshed, plan.target_terms)
        if matched_text:
            return ExecutionOutcome(task_type="RETRIEVE", status="SUCCESS", retrieved_data=[matched_text])

    if plan.target_terms and await try_click_target(page, plan.target_terms):
        refreshed = await observe_page(page)
        matched_text = select_best_match(refreshed, plan.target_terms)
        if matched_text:
            return ExecutionOutcome(task_type="RETRIEVE", status="SUCCESS", retrieved_data=[matched_text])

    fallback = select_fallback_value(observation)
    if fallback and not plan.target_terms:
        return ExecutionOutcome(task_type="RETRIEVE", status="SUCCESS", retrieved_data=[fallback])

    return ExecutionOutcome(
        task_type="RETRIEVE",
        status="NOT_FOUND_ERROR",
        error_details=f"값을 찾지 못했습니다: {plan.target_phrase or 'intent'}",
    )


async def execute_navigate(
    *,
    plan: IntentPlan,
    page: Any,
    observation: PageObservation,
    start_urls: list[str],
) -> ExecutionOutcome:
    """관련 페이지로 이동하고 목표 페이지 도달 여부를 확인한다."""
    if navigation_goal_satisfied(observation, plan):
        return ExecutionOutcome(task_type="NAVIGATE", status="SUCCESS")

    if plan.explicit_url:
        await page.goto(plan.explicit_url)
        refreshed = await observe_page(page)
        if refreshed.url != observation.url or navigation_goal_satisfied(refreshed, plan):
            return ExecutionOutcome(task_type="NAVIGATE", status="SUCCESS")

    if plan.target_terms and await try_click_target(page, plan.target_terms):
        refreshed = await observe_page(page)
        if refreshed.url != observation.url or navigation_goal_satisfied(refreshed, plan):
            return ExecutionOutcome(task_type="NAVIGATE", status="SUCCESS")

    if plan.target_phrase and await try_search(page, plan.target_phrase):
        refreshed = await observe_page(page)
        if refreshed.url != observation.url or navigation_goal_satisfied(refreshed, plan):
            return ExecutionOutcome(task_type="NAVIGATE", status="SUCCESS")

    if start_urls and normalize_text(observation.url) != normalize_text(start_urls[0]):
        return ExecutionOutcome(task_type="NAVIGATE", status="SUCCESS")

    return ExecutionOutcome(
        task_type="NAVIGATE",
        status="NOT_FOUND_ERROR",
        error_details=f"목표 페이지로 이동하지 못했습니다: {plan.target_phrase or 'intent'}",
    )


async def execute_mutate(*, plan: IntentPlan, page: Any, observation: PageObservation) -> ExecutionOutcome:
    """검색이나 클릭 같은 제한된 변경 작업을 수행한다."""
    acted = False
    if plan.action == "search_target" and plan.target_phrase:
        acted = await try_search(page, plan.target_phrase)
    if not acted and plan.target_terms:
        acted = await try_click_target(page, plan.target_terms)

    if not acted:
        return ExecutionOutcome(
            task_type="MUTATE",
            status="NOT_FOUND_ERROR",
            error_details=f"동작 대상 요소를 찾지 못했습니다: {plan.target_phrase or 'intent'}",
        )

    refreshed = await observe_page(page)
    if refreshed.url != observation.url or refreshed.title != observation.title:
        return ExecutionOutcome(task_type="MUTATE", status="SUCCESS")
    if select_best_match(refreshed, plan.target_terms):
        return ExecutionOutcome(task_type="MUTATE", status="SUCCESS")

    return ExecutionOutcome(
        task_type="MUTATE",
        status="UNKNOWN_ERROR",
        error_details="변경 작업 이후 눈에 띄는 상태 변화가 없었습니다",
    )


async def observe_page(page: Any) -> PageObservation:
    """현재 보이는 페이지 상태를 간결하게 수집한다."""
    return PageObservation(
        url=normalize_text(getattr(page, "url", "")),
        title=normalize_text(await safe_title(page)),
        headings=await extract_texts(page, HEADING_SELECTORS),
        text_lines=await extract_texts(page, TEXT_BLOCK_SELECTORS),
        links=await extract_texts(page, LINK_SELECTORS),
        buttons=await extract_texts(page, BUTTON_SELECTORS),
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


async def try_click_target(page: Any, target_terms: list[str]) -> bool:
    """target term과 맞는 첫 링크 또는 버튼을 클릭한다."""
    if not target_terms:
        return False

    for selector in (*LINK_SELECTORS, *BUTTON_SELECTORS):
        locator = page.locator(selector)
        try:
            count = await locator.count()
        except Exception:
            continue
        for index in range(count):
            item = locator.nth(index)
            try:
                text = normalize_text(await item.inner_text())
            except Exception:
                continue
            if any(term in text for term in target_terms):
                try:
                    await item.click()
                    return True
                except Exception:
                    continue
    return False


async def try_search(page: Any, phrase: str) -> bool:
    """보이는 검색 입력창에 문구를 넣고 제출한다."""
    cleaned_phrase = phrase.strip()
    if not cleaned_phrase:
        return False

    for selector in SEARCH_INPUT_SELECTORS:
        locator = page.locator(selector)
        try:
            count = await locator.count()
        except Exception:
            continue
        if count < 1:
            continue
        item = locator.nth(0)
        try:
            await item.fill(cleaned_phrase)
            await item.press("Enter")
            return True
        except Exception:
            continue
    return False


async def extract_texts(page: Any, selectors: tuple[str, ...]) -> list[str]:
    """실행 전체를 깨뜨리지 않고 selector 목록에서 텍스트를 읽는다."""
    texts: list[str] = []
    for selector in selectors:
        locator = page.locator(selector)
        try:
            selector_texts = await locator.all_inner_texts()
        except Exception:
            continue
        for text in selector_texts:
            cleaned = collapse_whitespace(text)
            if cleaned and cleaned not in texts:
                texts.append(cleaned)
    return texts


async def safe_title(page: Any) -> str:
    """페이지 title을 반환하고, 얻을 수 없으면 빈 문자열을 반환한다."""
    try:
        return await page.title()
    except Exception:
        return ""


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
