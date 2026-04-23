from __future__ import annotations

import asyncio
from typing import Any

from .intent import (
    BUTTON_SELECTORS,
    HEADING_SELECTORS,
    LINK_SELECTORS,
    SEARCH_INPUT_SELECTORS,
    TEXT_BLOCK_SELECTORS,
    normalize_text,
)
from .types import PageObservation

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
    # URL은 원본 그대로 (.lower() 등 정규화하지 않음) — case-sensitive path·query
    # 보존. _sub_goal_start_url 비교에도 원본 기반이 안전 (Y-code-4 fix).
    url = (getattr(page, "url", "") or "").strip()
    (
        title, headings, text_lines, ax_links, dropdown_options, buttons,
        inputs, readonly_values, toggle_states, latent_nav,
    ) = await asyncio.gather(
        safe_title(page),
        extract_texts(page, HEADING_SELECTORS),
        extract_texts(page, TEXT_BLOCK_SELECTORS),
        extract_ax_links(page),
        extract_dropdown_options(page),
        extract_texts(page, BUTTON_SELECTORS, visible_only=True),
        extract_input_labels(page),
        extract_readonly_values(page),
        extract_toggle_states(page),
        extract_latent_nav(page),
    )
    # AX tree가 빈 결과면 CSS selector 폴백
    links = ax_links if ax_links else await extract_texts(page, LINK_SELECTORS)
    # readonly input의 value를 text_lines에 병합
    all_text = text_lines + readonly_values
    # Checkbox / radio 상태를 inputs에 prepend — agent가 form 제출 전 확인 가능하게.
    # 기본 checkbox/radio selector로는 toggle 상태를 누락해서 qualifier 필드
    # (예: 폼의 "empty" / "private" 선택지)가 form 필드로 매핑 안 되고 default로 submit되는 문제를 방지.
    all_inputs = toggle_states + inputs
    # Latent nav에서 visible link 중복 제거 — observation 표면에 이미 있는 것은 불필요
    visible_link_texts = {l.split(" → ")[0].strip() for l in links if " → " in l}
    latent_nav_dedup = [
        item for item in latent_nav
        if item.split(" → ")[0].replace("[collapsed] ", "").strip()
        not in visible_link_texts
    ]
    return PageObservation(
        url=url,
        title=normalize_text(title),
        headings=headings,
        text_lines=all_text,
        links=links,
        buttons=buttons,
        inputs=all_inputs,
        dropdown_options=dropdown_options,
        latent_nav=latent_nav_dedup,
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


async def extract_latent_nav(page: Any) -> list[str]:
    """DOM에 렌더되어 있지만 collapsed / aria-hidden으로 인해 visible extract에서
    누락되는 navigation 항목을 사전 추출한다 (site-agnostic ARIA 표준 기반).

    타겟:
      1. `aria-expanded='false'` + `aria-controls` 연결된 container 안의
         `<a href>` 링크. Collapsed sub-menu 패턴을 표현하는 표준 ARIA 속성.
      2. `role='menu'` / `role='listbox'`로 렌더된 dropdown의 menu/option 자식
         (현재 closed 상태여도 DOM에 pre-rendered된 경우).

    출력 형식: "[collapsed:<parent>] label → /path" 또는 "[menu:<trigger>] option"
    부수 효과 없음: DOM read만, 실제 expand 안 함.
    """
    try:
        results: list[str] = await page.evaluate(
            """() => {
                const out = [];
                const seen = new Set();
                const push = (item) => {
                    if (!item || seen.has(item)) return;
                    seen.add(item);
                    out.push(item);
                };

                // 1. aria-controls 연결 기반 collapsed container 링크
                const toggles = Array.from(document.querySelectorAll(
                    '[aria-expanded="false"][aria-controls]'
                ));
                for (const t of toggles) {
                    const targetId = t.getAttribute('aria-controls');
                    if (!targetId) continue;
                    const container = document.getElementById(targetId);
                    if (!container) continue;
                    const toggleLabel = (t.innerText || t.getAttribute('aria-label') || '').trim().split('\\n')[0];
                    const anchors = Array.from(container.querySelectorAll('a[href]')).slice(0, 20);
                    for (const a of anchors) {
                        const txt = (a.innerText || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim();
                        if (!txt) continue;
                        const path = a.pathname || '';
                        const entry = path
                            ? `[collapsed:${toggleLabel}] ${txt} \\u2192 ${path}`
                            : `[collapsed:${toggleLabel}] ${txt}`;
                        push(entry);
                    }
                }

                // 2. pre-rendered menu / listbox options (closed dropdown)
                // visibility:hidden / display:none이 아니면서 offsetParent null인 case 포함
                const menus = Array.from(document.querySelectorAll(
                    '[role="menu"], [role="listbox"]'
                ));
                for (const m of menus) {
                    const style = window.getComputedStyle(m);
                    if (style.display === 'none') continue;
                    // 이미 agent에게 visible (extract_dropdown_options로 잡힘)이면 skip
                    if (m.offsetParent !== null && style.visibility !== 'hidden') continue;
                    const items = Array.from(m.querySelectorAll(
                        '[role="menuitem"], [role="option"], [role="menuitemradio"], [role="menuitemcheckbox"], a[href]'
                    )).slice(0, 20);
                    const trigger = m.getAttribute('aria-labelledby');
                    const trigLabel = trigger
                        ? (document.getElementById(trigger)?.innerText || '').trim().split('\\n')[0]
                        : (m.getAttribute('aria-label') || '');
                    for (const it of items) {
                        const txt = (it.innerText || it.getAttribute('aria-label') || '').trim();
                        if (!txt) continue;
                        push(`[menu:${trigLabel}] ${txt}`);
                    }
                }

                return out.slice(0, 40);
            }"""
        )
        return [r for r in results if r]
    except Exception:
        return []


async def extract_toggle_states(page: Any) -> list[str]:
    """Checkbox / radio 상태를 label과 함께 수집한다.

    출력 포맷:
      "[checked] <checkbox label>"
      "<radio_group_name>: <option1> | <option2 selected> ✓ | <option3>"

    이 신호 없이는 agent가 intent의 non-default 수식어 (site별 어휘)를 form 필드와
    매핑 못함 — default submit이 고질적 실패 원인 ( P1.1 진단).
    """
    try:
        results: list[str] = await page.evaluate(
            """() => {
                const out = [];
                const visible = (el) => el.offsetWidth > 0 || el.offsetHeight > 0;
                const labelOf = (el) => {
                    const ls = el.labels && el.labels[0];
                    const txt = ls ? (ls.innerText || '').trim() : '';
                    return txt || el.getAttribute('aria-label') || el.getAttribute('name') || '';
                };
                // Checkboxes
                const cbs = Array.from(document.querySelectorAll('input[type=checkbox]'));
                for (const el of cbs) {
                    if (!visible(el)) continue;
                    const label = labelOf(el);
                    if (!label) continue;
                    const state = el.checked ? 'checked' : 'unchecked';
                    out.push(`[${state}] ${label}`);
                }
                // Radios grouped by name
                const radios = Array.from(document.querySelectorAll('input[type=radio]'));
                const groups = {};
                for (const el of radios) {
                    if (!visible(el)) continue;
                    const name = el.getAttribute('name') || '';
                    if (!name) continue;
                    if (!groups[name]) groups[name] = [];
                    const label = labelOf(el) || el.value || '';
                    groups[name].push(label + (el.checked ? ' \\u2713' : ''));
                }
                for (const [name, opts] of Object.entries(groups)) {
                    out.push(`${name}: ${opts.join(' | ')}`);
                }
                return out.slice(0, 25);
            }"""
        )
        return [r for r in results if r]
    except Exception:
        return []


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


async def try_click_target(page: Any, target_terms: list[str]) -> bool:
    """target term과 맞는 첫 링크 / 버튼 / 폼 label을 클릭한다.

    Checkbox/radio는 `<label>` 클릭으로 토글되므로 label 경로를 함께 지원한다.
    label 경로가 없으면 checkbox/radio가 자체 요소로 잡히지 않아 토글 불가.
    """
    if not target_terms:
        return False

    _target_terms_norm = [normalize_text(t) for t in target_terms]

    for selector in (*LINK_SELECTORS, *BUTTON_SELECTORS, "label"):
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
