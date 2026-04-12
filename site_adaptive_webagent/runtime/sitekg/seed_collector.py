"""Playwright 자동 시드 수집 — LLM 호출 0.

사이트를 자동 순회하여 SiteKG를 생성한다:
1. BFS link 순회 → PageNode + NavigationEdge
2. 페이지별 interactive element → WidgetNode
3. widget 클릭 → side_effects + visibility_condition
4. YAML dump → seeds/{site}.auto.yaml
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs, urljoin

import yaml

from .types import InteractionEdge, NavigationEdge, PageNode, SiteKG, WidgetNode

logger = logging.getLogger("seed_collector")

_INTERACTIVE_SELECTORS = (
    "button:visible",
    "input:visible",
    "select:visible",
    "[role='button']:visible",
    "[role='tab']:visible",
    "[role='menuitem']:visible",
    "[role='option']:visible",
)

_SKIP_PATTERNS = ("/users/sign_in", "/users/sign_out", "/admin", "/-/profile")


async def collect_site_kg(
    base_url: str,
    site_id: str,
    *,
    auth_storage_state: str | None = None,
    max_pages: int = 20,
    max_widgets_per_page: int = 15,
    max_depth: int = 4,
    headed: bool = False,
) -> SiteKG:
    """Playwright로 사이트를 자동 순회하여 SiteKG를 생성한다."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        context_kwargs: dict[str, Any] = {}
        if auth_storage_state:
            context_kwargs["storage_state"] = auth_storage_state
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        try:
            # Step 1: BFS page traversal
            page_nodes, nav_edges, page_urls = await _bfs_pages(
                page, base_url, site_id, max_pages, max_depth,
            )
            logger.info("Collected %d pages, %d navigation edges", len(page_nodes), len(nav_edges))

            # Step 2+3: widget 수집 + 행동 관찰
            all_widgets: list[WidgetNode] = []
            for pn in page_nodes:
                page_url = page_urls.get(pn.page_key, base_url)
                await page.goto(page_url)
                await page.wait_for_timeout(500)
                widgets = await _collect_widgets(page, pn.page_key, site_id, max_widgets_per_page)
                widgets = await _observe_widget_effects(page, widgets, page_url)
                all_widgets.extend(widgets)
                logger.info("Page '%s': %d widgets", pn.page_key, len(widgets))

            return SiteKG(
                site_id=site_id,
                base_url=base_url,
                page_nodes=page_nodes,
                widget_nodes=all_widgets,
                navigation_edges=nav_edges,
                interaction_edges=[],  # M0: interaction edges는 side_effects에서 간접 표현
            )
        finally:
            await context.close()
            await browser.close()


def dump_yaml(sitekg: SiteKG, path: str | Path) -> None:
    """SiteKG를 seed_loader 호환 YAML로 저장한다."""
    data: dict[str, Any] = {
        "site_id": sitekg.site_id,
        "base_url": sitekg.base_url,
        "page_nodes": [
            {
                "page_key": p.page_key,
                "url_patterns": p.url_patterns,
                **({"structural_signals": p.structural_signals} if p.structural_signals else {}),
            }
            for p in sitekg.page_nodes
        ],
        "widget_nodes": [
            {
                k: v for k, v in {
                    "widget_key": w.widget_key,
                    "page_key": w.page_key,
                    "locator_strategy": w.locator_strategy,
                    "locator_value": w.locator_value,
                    "visibility_condition": w.visibility_condition,
                    "side_effects": w.side_effects or None,
                }.items() if v
            }
            for w in sitekg.widget_nodes
        ],
        "navigation_edges": [
            {
                "source_page_key": e.source_page_key,
                "target_page_key": e.target_page_key,
                **({"trigger_widget_key": e.trigger_widget_key} if e.trigger_widget_key else {}),
            }
            for e in sitekg.navigation_edges
        ],
    }
    if sitekg.interaction_edges:
        data["interaction_edges"] = [
            {
                "page_key": e.page_key,
                "source_widget_key": e.source_widget_key,
                "target_widget_key": e.target_widget_key,
                "relation_type": e.relation_type,
            }
            for e in sitekg.interaction_edges
        ]

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
    )
    logger.info("Saved seed to %s", path)


# ---------------------------------------------------------------------------
# BFS page traversal
# ---------------------------------------------------------------------------

async def _bfs_pages(
    page: Any,
    base_url: str,
    site_id: str,
    max_pages: int,
    max_depth: int,
) -> tuple[list[PageNode], list[NavigationEdge], dict[str, str]]:
    """BFS link 순회 → PageNode + NavigationEdge."""
    base_host = urlparse(base_url).netloc
    visited: dict[str, PageNode] = {}  # normalized_path → PageNode
    page_urls: dict[str, str] = {}  # page_key → full URL
    nav_edges: list[NavigationEdge] = []
    queue: list[tuple[str, int, str | None]] = [(base_url, 0, None)]  # (url, depth, source_page_key)

    while queue and len(visited) < max_pages:
        url, depth, source_pk = queue.pop(0)
        if depth > max_depth:
            continue

        norm_path = _normalize_path(url)
        if norm_path in visited:
            # edge만 추가 (이미 방문한 페이지)
            if source_pk and source_pk != visited[norm_path].page_key:
                target_pk = visited[norm_path].page_key
                if not any(e.source_page_key == source_pk and e.target_page_key == target_pk for e in nav_edges):
                    nav_edges.append(NavigationEdge(
                        edge_id=str(uuid.uuid4()), site_id=site_id,
                        source_page_key=source_pk, target_page_key=target_pk,
                    ))
            continue

        if any(skip in norm_path for skip in _SKIP_PATTERNS):
            continue

        try:
            await page.goto(url, timeout=10000)
            await page.wait_for_timeout(500)
        except Exception:
            continue

        actual_path = _normalize_path(page.url)
        page_key = _path_to_page_key(actual_path)
        if actual_path in visited:
            continue

        pn = PageNode(
            page_node_id=str(uuid.uuid4()),
            site_id=site_id,
            page_key=page_key,
            url_patterns=[actual_path],
        )
        visited[actual_path] = pn
        page_urls[page_key] = page.url

        if source_pk:
            nav_edges.append(NavigationEdge(
                edge_id=str(uuid.uuid4()), site_id=site_id,
                source_page_key=source_pk, target_page_key=page_key,
            ))

        # 현재 페이지의 내부 links 수집
        try:
            hrefs: list[str] = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(Boolean)
                    .slice(0, 50)
            }""")
        except Exception:
            hrefs = []

        for href in hrefs:
            parsed = urlparse(href)
            if parsed.netloc and parsed.netloc != base_host:
                continue  # 외부 링크 skip
            full_url = urljoin(base_url, parsed.path)
            queue.append((full_url, depth + 1, page_key))

    return list(visited.values()), nav_edges, page_urls


# ---------------------------------------------------------------------------
# Widget 수집
# ---------------------------------------------------------------------------

async def _collect_widgets(
    page: Any,
    page_key: str,
    site_id: str,
    max_widgets: int,
) -> list[WidgetNode]:
    """페이지에서 interactive element를 수집하여 WidgetNode로 변환."""
    widgets: list[WidgetNode] = []
    seen_locators: set[str] = set()

    for selector in _INTERACTIVE_SELECTORS:
        try:
            elements = await page.locator(selector).all()
        except Exception:
            continue

        for el in elements:
            if len(widgets) >= max_widgets:
                break
            try:
                locator = await _generate_locator(el)
                if not locator or locator in seen_locators:
                    continue
                seen_locators.add(locator)

                widget_key = await _generate_widget_key(el, locator)
                widgets.append(WidgetNode(
                    widget_node_id=str(uuid.uuid4()),
                    site_id=site_id,
                    page_key=page_key,
                    widget_key=widget_key,
                    locator_strategy="css",
                    locator_value=locator,
                ))
            except Exception:
                continue

    return widgets


async def _generate_locator(element: Any) -> str:
    """element에 대해 안정적인 CSS selector를 생성한다."""
    # id (동적으로 보이지 않는 것만)
    el_id = await element.get_attribute("id")
    if el_id and not _looks_dynamic(el_id):
        return f"#{el_id}"

    # data-testid
    testid = await element.get_attribute("data-testid")
    if testid:
        return f"[data-testid='{testid}']"

    # aria-label + tag
    aria = await element.get_attribute("aria-label")
    tag = await element.evaluate("el => el.tagName.toLowerCase()")
    if aria:
        return f"{tag}[aria-label='{_escape_css(aria)}']"

    # placeholder + tag
    placeholder = await element.get_attribute("placeholder")
    if placeholder:
        return f"{tag}[placeholder='{_escape_css(placeholder)}']"

    # name + tag
    name = await element.get_attribute("name")
    if name:
        return f"{tag}[name='{_escape_css(name)}']"

    # role + text (fallback)
    role = await element.get_attribute("role")
    text = (await element.inner_text() or "").strip()[:30]
    if role and text:
        return f"[role='{role}']:has-text('{_escape_css(text)}')"

    return ""


async def _generate_widget_key(element: Any, locator: str) -> str:
    """사람 가독용 widget_key를 생성한다."""
    aria = await element.get_attribute("aria-label")
    if aria:
        return _slugify(aria)
    text = (await element.inner_text() or "").strip()[:30]
    if text:
        return _slugify(text)
    return _slugify(locator)[:40]


# ---------------------------------------------------------------------------
# Widget 행동 관찰
# ---------------------------------------------------------------------------

async def _observe_widget_effects(
    page: Any,
    widgets: list[WidgetNode],
    page_url: str,
) -> list[WidgetNode]:
    """각 widget을 클릭해보고 side_effects를 기록한다."""
    for widget in widgets:
        try:
            before_url = page.url
            locator = page.locator(widget.locator_value).first

            if not await locator.is_visible():
                widget.visibility_condition = "not visible by default"
                continue

            await locator.click(timeout=3000)
            await page.wait_for_timeout(500)

            after_url = page.url
            effects: list[str] = []

            # URL 변화 감지
            if _normalize_path(after_url) != _normalize_path(before_url):
                effects.append(f"navigates to {_normalize_path(after_url)}")
            else:
                param_diff = _diff_query_params(before_url, after_url)
                if param_diff:
                    effects.append(f"URL gains {param_diff}")

            widget.side_effects = effects

            # 원래 상태로 복원
            await page.goto(page_url, timeout=5000)
            await page.wait_for_timeout(300)

        except Exception:
            # 클릭 실패 시 복원만 시도
            try:
                await page.goto(page_url, timeout=5000)
                await page.wait_for_timeout(300)
            except Exception:
                pass

    return widgets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_path(url: str) -> str:
    """URL에서 path만 추출 (trailing slash 제거)."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def _path_to_page_key(path: str) -> str:
    """URL path를 page_key로 변환. 읽기 쉬운 형태."""
    clean = path.split("?")[0].strip("/")
    if not clean:
        return "root"
    return clean.replace("/", "_").replace("-", "_").replace(".", "_")[:60]


def _looks_dynamic(value: str) -> bool:
    """ID가 동적으로 생성된 것처럼 보이는지."""
    if len(value) > 20:
        return True
    digit_ratio = sum(c.isdigit() for c in value) / max(len(value), 1)
    return digit_ratio > 0.5


def _escape_css(value: str) -> str:
    """CSS selector에서 안전하게 사용할 수 있도록 escape."""
    return value.replace("'", "\\'").replace('"', '\\"')


def _slugify(text: str) -> str:
    """텍스트를 snake_case widget_key로 변환."""
    import re
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return slug[:40] or "widget"


def _diff_query_params(before_url: str, after_url: str) -> str:
    """URL 간 query parameter 차이를 문자열로."""
    before_params = parse_qs(urlparse(before_url).query)
    after_params = parse_qs(urlparse(after_url).query)
    new_params = {k: v for k, v in after_params.items() if k not in before_params}
    if new_params:
        return "&".join(f"{k}={v[0]}" for k, v in new_params.items())
    return ""
