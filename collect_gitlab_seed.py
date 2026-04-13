"""GitLab seed 재수집 — URL unchanged effect 표현 검증.

수집 전 fresh storage_state 발급 (byteblaze ui_login).
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

import yaml
from playwright.async_api import async_playwright

from site_adaptive_webagent.benchmarks.webarena_verified.adapter import gitlab_ui_login
from site_adaptive_webagent.runtime.sitekg.seed_collector import collect_site_kg


AUTH_PATH = Path("seeds/.gitlab_auth_state.json")


async def issue_fresh_auth() -> None:
    """byteblaze로 GitLab 로그인 후 storage_state 저장."""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        await gitlab_ui_login(
            context, "http://localhost:8023", "byteblaze", "hello1234"
        )
        await context.storage_state(path=str(AUTH_PATH))
        await browser.close()
    print(f"[auth] saved fresh storage state to {AUTH_PATH}")


async def main() -> None:
    await issue_fresh_auth()

    sitekg = await collect_site_kg(
        base_url="http://localhost:8023",
        site_id="gitlab",
        auth_storage_state=str(AUTH_PATH),
        extra_start_urls=[
            "http://localhost:8023/dashboard/projects",
            "http://localhost:8023/dashboard/issues",
            "http://localhost:8023/dashboard/merge_requests",
            "http://localhost:8023/dashboard/todos",
            "http://localhost:8023/explore",
            "http://localhost:8023/explore/projects/topics",
            "http://localhost:8023/byteblaze",
            "http://localhost:8023/a11yproject/a11yproject.com",
            "http://localhost:8023/a11yproject/a11yproject.com/-/issues",
            "http://localhost:8023/a11yproject/a11yproject.com/-/merge_requests",
            "http://localhost:8023/byteblaze/a11y-syntax-highlighting",
            "http://localhost:8023/byteblaze/a11y-syntax-highlighting/-/issues",
            "http://localhost:8023/primer/design",
            "http://localhost:8023/primer/design/-/commits/main",
            "http://localhost:8023/-/profile",
        ],
        max_pages=50,
        max_widgets_per_page=15,
    )

    data = {
        "site_id": sitekg.site_id,
        "base_url": sitekg.base_url,
        "page_nodes": [asdict(p) for p in sitekg.page_nodes],
        "widget_nodes": [asdict(w) for w in sitekg.widget_nodes],
        "navigation_edges": [asdict(e) for e in sitekg.navigation_edges],
        "interaction_edges": [asdict(e) for e in sitekg.interaction_edges],
    }
    Path("seeds/gitlab.auto.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    )
    print(
        f"Saved: {len(sitekg.page_nodes)} pages, "
        f"{len(sitekg.widget_nodes)} widgets, "
        f"{len(sitekg.navigation_edges)} nav edges, "
        f"{len(sitekg.interaction_edges)} interaction edges"
    )


if __name__ == "__main__":
    asyncio.run(main())
