"""Playwright auto-crawl — 3단계 hybrid 구축의 단계 1 (M4-A).

docs/kg_design/07 §14의 `source=crawl` / `trust=verified` layer를 생산한다.

입력:
- base_url: 사이트 루트 URL (예: "http://localhost:8023")
- seed_urls: crawl 시작점 URL 목록 (사이트 공식 기능 표면 기준; 실험 task 미참조)
- max_depth: link-following 최대 깊이
- storage_state_file: 로그인 상태 Playwright storage_state JSON (선택)

산출물:
- list[CrawlResult] — 관찰된 URL, path/query param, form schema, outgoing link.
  `crawl_to_kg.crawl_results_to_sitekg`가 이를 SiteKG의 `source="crawl"` 노드·엣지로 승격.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class FormElementMeta:
    """관찰된 form input 하나에 대한 메타.

    Action 후보 (특히 MUTATE) 추론·LLM derivation 입력으로 사용.
    """

    name: str
    type: str = "text"  # input type 또는 'select', 'textarea'
    options: list[str] | None = None  # select일 때만
    required: bool = False
    action_url: str | None = None  # form action attribute
    method: str = "get"  # form method


@dataclass(slots=True)
class CrawlResult:
    """Crawler가 관찰한 단일 URL에 대한 요약.

    `crawl_to_kg`가 이 구조를 StatePattern / LeadsToEdge / Action으로 승격.
    """

    url: str
    normalized_url_template: str
    path_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    query_params_seen: list[str] = field(default_factory=list)
    outgoing_links: list[str] = field(default_factory=list)
    form_elements: list[FormElementMeta] = field(default_factory=list)
    dom_signature: str | None = None
    http_status: int = 200
    parent_url: str | None = None  # BFS 부모 — leads_to 후보 추론용


def crawl_site(
    base_url: str,
    seed_urls: list[str],
    max_depth: int = 2,
    storage_state_file: str | Path | None = None,
) -> list[CrawlResult]:
    """사이트를 BFS crawl하여 관찰된 URL·param·form·링크를 수집.

    실제 Playwright integration은 동일 모듈의 `_crawl_site_async`에서 수행되며,
    이 함수는 sync 진입점으로 asyncio 이벤트 루프를 띄운다.
    """
    import asyncio

    return asyncio.run(
        _crawl_site_async(
            base_url=base_url,
            seed_urls=seed_urls,
            max_depth=max_depth,
            storage_state_file=storage_state_file,
        )
    )


async def _crawl_site_async(
    base_url: str,
    seed_urls: list[str],
    max_depth: int,
    storage_state_file: str | Path | None,
) -> list[CrawlResult]:
    """Playwright 기반 BFS crawl."""
    import logging
    from collections import deque
    from urllib.parse import urlparse

    from playwright.async_api import async_playwright

    from ..types import SiteConfig
    from ..urlnorm import normalize_url

    logger = logging.getLogger("kg.crawler")

    cfg = SiteConfig(site="", base_url=base_url)
    base_host = urlparse(base_url).netloc
    storage_path = Path(storage_state_file) if storage_state_file else None

    results: list[CrawlResult] = []
    template_to_result: dict[str, CrawlResult] = {}
    visited_urls: set[str] = set()
    # 같은 (template, query_keys) 조합은 한 번만 큐에 추가 — query NAME 발견이 목적이므로
    # 같은 key set의 다른 value는 중복. visit 수 폭발 방지.
    planned_signatures: set[tuple[str, tuple[str, ...]]] = set()
    queue: deque[tuple[str, int, str | None]] = deque()
    for url in seed_urls:
        queue.append((url, 0, None))

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        ctx_kwargs: dict[str, Any] = {"viewport": None, "no_viewport": True}
        if storage_path and storage_path.exists():
            ctx_kwargs["storage_state"] = str(storage_path)
        context = await browser.new_context(**ctx_kwargs)

        try:
            while queue:
                url, depth, parent = queue.popleft()
                if url in visited_urls:
                    continue
                visited_urls.add(url)
                if len(visited_urls) % 100 == 0:
                    logger.info(
                        "[progress] visited=%d queued=%d results=%d",
                        len(visited_urls), len(queue), len(results),
                    )

                page = await context.new_page()
                try:
                    response = await page.goto(url, wait_until="load", timeout=10000)
                    status = response.status if response else 0
                    final_url = page.url
                except Exception as e:
                    logger.warning("crawl failed for %s: %s", url, e)
                    await page.close()
                    continue

                # Session expiry detection
                if status == 403 or "/users/sign_in" in final_url:
                    logger.warning(
                        "session expired or forbidden at %s (status=%s, final=%s)",
                        url, status, final_url,
                    )
                    await page.close()
                    continue

                # URL 정규화 + path slot 추출은 후처리 단계 (crawl_to_kg)에서.
                # 여기선 normalized path만 보유 (path만, query는 별도).
                parsed = urlparse(final_url)
                normalized = normalize_url(parsed.path or "/", cfg)
                template = normalized.path
                query_names = sorted({k for k, _ in normalized.query_pairs})

                # DOM 수집
                outgoing = await _extract_links(page, base_url, base_host)
                forms = await _extract_forms(page)
                signature = await _dom_signature(page)

                # 동일 template은 한 번만 결과로 채택하되, query_params_seen은
                # 후속 방문에서 발견된 key를 union해 누적한다. 사이트의 같은 page에
                # 대해 여러 filter URL을 visit한 경우 모두 catalog에 반영하기 위함.
                existing = template_to_result.get(template)
                if existing is None:
                    cr = CrawlResult(
                        url=final_url,
                        normalized_url_template=template,
                        path_params={},
                        query_params_seen=list(query_names),
                        outgoing_links=outgoing,
                        form_elements=forms,
                        dom_signature=signature,
                        http_status=status,
                        parent_url=parent,
                    )
                    template_to_result[template] = cr
                    results.append(cr)
                else:
                    for q in query_names:
                        if q not in existing.query_params_seen:
                            existing.query_params_seen.append(q)

                await page.close()

                if depth < max_depth:
                    for link in outgoing:
                        if link in visited_urls:
                            continue
                        link_parsed = urlparse(link)
                        link_norm = normalize_url(link_parsed.path or "/", cfg)
                        link_template = link_norm.path
                        link_keys = tuple(sorted({k for k, _ in link_norm.query_pairs}))
                        sig = (link_template, link_keys)
                        if sig in planned_signatures:
                            continue
                        planned_signatures.add(sig)
                        queue.append((link, depth + 1, final_url))
        finally:
            await context.close()
            await browser.close()

    return results


_DOWNLOAD_EXTENSIONS = frozenset({
    # 압축 archive
    "zip", "tar", "gz", "bz2", "xz", "7z", "rar",
    # diff/patch
    "diff", "patch",
    # binary asset
    "exe", "dmg", "iso", "deb", "rpm", "pkg", "apk",
    # media (페이지가 아니라 raw asset)
    "png", "jpg", "jpeg", "gif", "svg", "ico", "webp",
    "mp3", "mp4", "mov", "avi", "wav", "ogg",
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    # source/config dump
    "ics", "git",
})


async def _extract_links(page: Any, base_url: str, base_host: str) -> list[str]:
    """페이지의 <a href> 중 같은 호스트인 절대 URL만 추출, 중복 제거.

    다운로드로 끝나는 binary/asset 확장자는 제외 — Playwright `page.goto`가
    download trigger를 만나면 timeout이 길어져 crawl이 비효율적이 된다.
    이 결정은 사이트 무관 — 일반적인 web download 확장자 집합.
    """
    from urllib.parse import urljoin, urlparse

    hrefs: list[str] = await page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    out: list[str] = []
    seen: set[str] = set()
    for href in hrefs:
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.netloc != base_host:
            continue
        # download extension filter
        last = parsed.path.rsplit("/", 1)[-1]
        if "." in last:
            ext = last.rsplit(".", 1)[-1].lower()
            if ext in _DOWNLOAD_EXTENSIONS:
                continue
        # fragment 제거
        cleaned = absolute.split("#", 1)[0]
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


async def _extract_forms(page: Any) -> list[FormElementMeta]:
    """페이지의 form input/select를 FormElementMeta로 추출."""
    raw = await page.evaluate(
        """() => {
          const out = [];
          for (const form of document.querySelectorAll('form')) {
            const action = form.getAttribute('action');
            const method = (form.getAttribute('method') || 'get').toLowerCase();
            for (const el of form.querySelectorAll('input,select,textarea')) {
              const name = el.getAttribute('name');
              if (!name) continue;
              const tag = el.tagName.toLowerCase();
              const type = tag === 'select' ? 'select'
                         : tag === 'textarea' ? 'textarea'
                         : (el.getAttribute('type') || 'text');
              const required = el.hasAttribute('required');
              let options = null;
              if (tag === 'select') {
                options = Array.from(el.querySelectorAll('option'))
                               .map(o => o.value).filter(Boolean);
              }
              out.push({name, type, required, options, action, method});
            }
          }
          return out;
        }"""
    )
    return [
        FormElementMeta(
            name=item["name"],
            type=item["type"],
            options=item["options"],
            required=bool(item["required"]),
            action_url=item.get("action"),
            method=item.get("method", "get"),
        )
        for item in raw
    ]


async def _dom_signature(page: Any) -> str:
    """페이지의 가벼운 DOM 시그니처 — h1 + 주요 nav landmark 텍스트의 해시."""
    import hashlib

    raw = await page.evaluate(
        """() => {
          const parts = [];
          for (const h of document.querySelectorAll('h1, [role=main] h2')) {
            parts.push((h.textContent || '').trim().slice(0, 80));
          }
          for (const n of document.querySelectorAll('nav a, [role=navigation] a')) {
            parts.push((n.textContent || '').trim().slice(0, 40));
          }
          return parts.join('|');
        }"""
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
