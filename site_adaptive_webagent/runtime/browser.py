from __future__ import annotations

from typing import Any

from .intent import (
    BUTTON_SELECTORS,
    HEADING_SELECTORS,
    LINK_SELECTORS,
    SEARCH_INPUT_SELECTORS,
    TEXT_BLOCK_SELECTORS,
    navigation_goal_satisfied,
    normalize_text,
    select_best_match,
    select_fallback_value,
)
from .types import ExecutionOutcome, IntentPlan, PageObservation


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
            from .intent import collapse_whitespace
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
