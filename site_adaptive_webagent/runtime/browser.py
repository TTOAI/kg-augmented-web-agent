from __future__ import annotations

import asyncio
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

# 입력 필드 관찰용 selector
_INPUT_SELECTORS = (
    "input[type='text']",
    "input[type='email']",
    "input[type='search']",
    "input[type='password']",
    "input[type='number']",
    "input:not([type])",
    "textarea",
)
_SELECT_SELECTORS = ("select",)


async def observe_page(page: Any) -> PageObservation:
    """현재 보이는 페이지 상태를 간결하게 수집한다."""
    url = normalize_text(getattr(page, "url", ""))
    title, headings, text_lines, ax_links, dropdown_options, buttons, inputs, readonly_values = await asyncio.gather(
        safe_title(page),
        extract_texts(page, HEADING_SELECTORS),
        extract_texts(page, TEXT_BLOCK_SELECTORS),
        extract_ax_links(page),
        extract_dropdown_options(page),
        extract_texts(page, BUTTON_SELECTORS, visible_only=True),
        extract_input_labels(page),
        extract_readonly_values(page),
    )
    # AX tree가 빈 결과면 CSS selector 폴백
    links = ax_links if ax_links else await extract_texts(page, LINK_SELECTORS)
    # readonly input의 value를 text_lines에 병합
    all_text = text_lines + readonly_values
    return PageObservation(
        url=url,
        title=normalize_text(title),
        headings=headings,
        text_lines=all_text,
        links=links,
        buttons=buttons,
        inputs=inputs,
        dropdown_options=dropdown_options,
    )


_LINK_EXTRACT_JS = """(selector) => {
    const seen = new Set();
    return Array.from(document.querySelectorAll(selector))
      .filter(el => el.offsetWidth > 0 || el.offsetHeight > 0)
      .slice(0, 60)
      .map(el => {
        const aria = (el.getAttribute('aria-label') || '').trim();
        const text = (el.innerText || '').replace(/\\s+/g, ' ').trim();
        const title = (el.getAttribute('title') || '').trim();
        const imgAlt = (el.querySelector('img[alt]')?.getAttribute('alt') || '').trim();
        const name = aria || text || title || imgAlt;
        const path = el.pathname || '';
        if (!name) return '';
        const entry = path ? name + ' \\u2192 ' + path : name;
        if (seen.has(entry)) return '';
        seen.add(entry);
        return entry;
      })
      .filter(Boolean);
}"""


async def extract_ax_links(page: Any) -> list[str]:
    """page.evaluate()로 일반 링크의 aria-label + pathname을 추출한다.

    드롭다운 항목은 extract_dropdown_options()에서 별도 수집한다.
    """
    try:
        results: list[str] = await page.evaluate(_LINK_EXTRACT_JS, "a[href]")
        return results[:50]
    except Exception:
        return []


async def extract_dropdown_options(page: Any) -> list[str]:
    """열린 드롭다운/메뉴의 보이는 항목을 수집한다."""
    try:
        results: list[str] = await page.evaluate(
            _LINK_EXTRACT_JS,
            '.dropdown-item, [role="option"], [role="menuitem"], [role="tab"]',
        )
        return results[:30]
    except Exception:
        return []


async def extract_input_labels(page: Any) -> list[str]:
    """입력 필드의 placeholder / aria-label / name 속성을 수집한다."""
    labels: list[str] = []
    seen: set[str] = set()
    for selector in (*_INPUT_SELECTORS, *_SELECT_SELECTORS):
        locator = page.locator(selector)
        try:
            results: list[str] = await locator.evaluate_all(
                "els => els.slice(0, 20).map(el =>"
                " el.getAttribute('placeholder') || el.getAttribute('aria-label') || el.getAttribute('name') || ''"
                ").filter(Boolean)"
            )
        except Exception:
            continue
        for t in results:
            cleaned = normalize_text(t)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                labels.append(cleaned)
    return labels


async def extract_readonly_values(page: Any) -> list[str]:
    """보이는 readonly input의 value를 수집한다 (예: clone URL)."""
    try:
        results: list[str] = await page.evaluate(
            """() => {
                return Array.from(document.querySelectorAll('input[readonly]'))
                    .filter(el => el.offsetWidth > 0 || el.offsetHeight > 0)
                    .map(el => {
                        const label = el.getAttribute('aria-label') || el.getAttribute('name') || '';
                        const value = el.value || '';
                        if (!value) return '';
                        return label ? label + ': ' + value : value;
                    })
                    .filter(Boolean)
            }"""
        )
        return results[:10]
    except Exception:
        return []


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
        error_details=f"Value not found: {plan.target_phrase or 'intent'}",
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

    return ExecutionOutcome(
        task_type="NAVIGATE",
        status="NOT_FOUND_ERROR",
        error_details=f"Could not navigate to target: {plan.target_phrase or 'intent'}",
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
            error_details=f"Target element not found: {plan.target_phrase or 'intent'}",
        )

    refreshed = await observe_page(page)
    if refreshed.url != observation.url or refreshed.title != observation.title:
        return ExecutionOutcome(task_type="MUTATE", status="SUCCESS")
    if select_best_match(refreshed, plan.target_terms):
        return ExecutionOutcome(task_type="MUTATE", status="SUCCESS")

    return ExecutionOutcome(
        task_type="MUTATE",
        status="UNKNOWN_ERROR",
        error_details="No visible state change after action",
    )


async def try_click_target(page: Any, target_terms: list[str]) -> bool:
    """target term과 맞는 첫 링크 또는 버튼을 클릭한다."""
    if not target_terms:
        return False

    _target_terms_norm = [normalize_text(t) for t in target_terms]

    for selector in (*LINK_SELECTORS, *BUTTON_SELECTORS):
        locator = page.locator(selector)
        try:
            count = await locator.count()
        except Exception:
            continue
        for index in range(count):
            item = locator.nth(index)
            try:
                raw = await item.inner_text()
            except Exception:
                raw = ""
            text = normalize_text(raw)
            if not text:
                # icon-only 요소 — aria-label / title 속성으로 대체
                for attr in ("aria-label", "title"):
                    try:
                        value = await item.get_attribute(attr)
                        if value:
                            text = normalize_text(value)
                            break
                    except Exception:
                        continue
            if text and any(term in text for term in _target_terms_norm):
                try:
                    await item.click()
                    return True
                except Exception:
                    continue
    return False



async def try_fill_target(page: Any, target: str, value: str, *, submit: bool = False) -> bool:
    """target(placeholder/aria-label/name)과 일치하는 입력 필드를 찾아 value를 채운다."""
    target_norm = normalize_text(target)
    for selector in (*_INPUT_SELECTORS, *_SELECT_SELECTORS):
        locator = page.locator(selector)
        try:
            count = await locator.count()
        except Exception:
            continue
        for i in range(min(count, 20)):
            item = locator.nth(i)
            label = ""
            for attr in ("placeholder", "aria-label", "name"):
                try:
                    val = await item.get_attribute(attr)
                    if val:
                        label = normalize_text(val)
                        break
                except Exception:
                    continue
            if label and target_norm in label:
                try:
                    await item.fill(value, timeout=5000)
                    if submit:
                        await item.press("Enter", timeout=5000)
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
        locator = page.locator(f"{selector}:visible")
        try:
            count = await locator.count()
        except Exception:
            continue
        if count < 1:
            continue
        item = locator.nth(0)
        try:
            await item.fill(cleaned_phrase, timeout=5000)
            await item.press("Enter", timeout=5000)
            return True
        except Exception:
            continue
    return False


async def extract_texts(page: Any, selectors: tuple[str, ...], *, visible_only: bool = False) -> list[str]:
    """실행 전체를 깨뜨리지 않고 selector 목록에서 텍스트를 읽는다.

    evaluate_all()로 selector당 단일 JS 호출로 모든 요소를 처리한다.
    inner_text가 비어있는 요소(예: 아이콘 전용 링크)는 aria-label → title 순으로 대체한다.
    visible_only=True이면 보이는 요소만 수집 (숨겨진 버튼 제외용).
    """
    from .intent import collapse_whitespace

    vis_filter = ".filter(el => el.offsetWidth > 0 || el.offsetHeight > 0)" if visible_only else ""
    texts: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        locator = page.locator(selector)
        try:
            results: list[str] = await locator.evaluate_all(
                "els => els"
                f"  {vis_filter}"
                "  .slice(0, 50).map(el => {"
                "  const t = (el.innerText || '').trim();"
                "  const name = t || el.getAttribute('aria-label') || el.getAttribute('title') || '';"
                "  if (!name) return '';"
                "  const cls = (el.className || '').trim();"
                "  const hints = ['dropdown', 'toggle', 'menu', 'sort', 'filter', 'select', 'tab', 'modal', 'search']"
                "    .filter(k => cls.includes(k));"
                "  return hints.length ? name + ' [' + hints.join(', ') + ']' : name;"
                "}).filter(Boolean)"
            )
        except Exception:
            continue
        for raw in results:
            cleaned = collapse_whitespace(raw)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                texts.append(cleaned)
    return texts


async def safe_title(page: Any) -> str:
    """페이지 title을 반환하고, 얻을 수 없으면 빈 문자열을 반환한다."""
    try:
        return await page.title()
    except Exception:
        return ""
