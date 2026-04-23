"""V1.a — Collect AXTree dumps for 23 representative GitLab pages.

Output:
  output/validation/V1_pages/pages/<page>.json
  output/validation/V1_pages/page_manifest.json
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

from site_adaptive_webagent.kg.site_extras import load_site_crawl

_SITE = os.getenv("SITE_NAME", "gitlab")
BASE_URL = load_site_crawl(_SITE).base_url
if not BASE_URL:
    raise ValueError(
        f"crawl.base_url not configured for site={_SITE!r}. "
        f"Set it in config/sites/{_SITE}/crawl.yaml."
    )
STORAGE_STATE = Path("output/validation/.storage_state.json")
OUTPUT_DIR = Path("output/validation/V1_pages")
PAGES_DIR = OUTPUT_DIR / "pages"

# ~57 representative pages captured from a single site; the page list below
# is the site-specific observation table used by this one-shot script.
PAGES = [
    # ── Original 23 sample ──
    ("dashboard_home", "/dashboard"),
    ("dashboard_projects", "/dashboard/projects"),
    ("dashboard_issues", "/dashboard/issues"),
    ("dashboard_merge_requests", "/dashboard/merge_requests"),
    ("dashboard_todos", "/dashboard/todos"),
    ("dashboard_todos_done", "/dashboard/todos?state=done"),
    ("dashboard_groups", "/dashboard/groups"),
    ("dashboard_projects_starred", "/dashboard/projects/starred"),
    ("explore_projects", "/explore/projects"),
    ("explore_projects_topics", "/explore/projects/topics"),
    ("help_page", "/help"),
    ("user_profile", "/byteblaze"),
    ("new_project_form", "/projects/new"),
    ("project_main", "/byteblaze/a11y-syntax-highlighting"),
    ("project_issues", "/byteblaze/a11y-syntax-highlighting/-/issues"),
    ("project_merge_requests", "/byteblaze/a11y-syntax-highlighting/-/merge_requests"),
    ("project_commits", "/byteblaze/a11y-syntax-highlighting/-/commits/main"),
    ("project_tree", "/byteblaze/a11y-syntax-highlighting/-/tree/main"),
    ("project_members", "/byteblaze/a11y-syntax-highlighting/-/project_members"),
    ("project_labels", "/byteblaze/a11y-syntax-highlighting/-/labels"),
    ("project_milestones", "/byteblaze/a11y-syntax-highlighting/-/milestones"),
    ("project_activity", "/byteblaze/a11y-syntax-highlighting/activity"),
    ("project_forks", "/byteblaze/a11y-syntax-highlighting/-/forks"),

    # ── Stage A.1 expansion (+34) ──
    # A. Project detail (5)
    ("project_issue_detail", "/byteblaze/a11y-syntax-highlighting/-/issues/1"),
    ("project_blob_detail", "/byteblaze/a11y-syntax-highlighting/-/blob/main/README.md"),
    ("project_commit_detail", "/byteblaze/a11y-syntax-highlighting/-/commit/62820763d9b5f3b25720596f542aaf89d917fb17"),
    ("project_tag_detail", "/byteblaze/empathy-prompts/-/tags/v0.1.0"),
    ("project_mr_detail", "/byteblaze/empathy-prompts/-/merge_requests/19"),
    # B. Project form (4, settings_general 중복 방지)
    ("project_issue_new_form", "/byteblaze/a11y-syntax-highlighting/-/issues/new"),
    ("project_mr_new_form", "/byteblaze/a11y-syntax-highlighting/-/merge_requests/new"),
    ("project_branch_new_form", "/byteblaze/a11y-syntax-highlighting/-/branches/new"),
    ("project_tag_new_form", "/byteblaze/a11y-syntax-highlighting/-/tags/new"),
    # C. Project settings (5)
    ("project_settings_general", "/byteblaze/a11y-syntax-highlighting/edit"),
    ("project_settings_repository", "/byteblaze/a11y-syntax-highlighting/-/settings/repository"),
    ("project_settings_ci_cd", "/byteblaze/a11y-syntax-highlighting/-/settings/ci_cd"),
    ("project_settings_integrations", "/byteblaze/a11y-syntax-highlighting/-/settings/integrations"),
    ("project_settings_access_tokens", "/byteblaze/a11y-syntax-highlighting/-/settings/access_tokens"),
    # D. Project CI/CD & infra (4)
    ("project_pipelines", "/byteblaze/a11y-syntax-highlighting/-/pipelines"),
    ("project_pipeline_schedules", "/byteblaze/a11y-syntax-highlighting/-/pipeline_schedules"),
    ("project_environments", "/byteblaze/a11y-syntax-highlighting/-/environments"),
    ("project_jobs", "/byteblaze/a11y-syntax-highlighting/-/jobs"),
    # E. Project 기타 (5)
    ("project_branches", "/byteblaze/a11y-syntax-highlighting/-/branches"),
    ("project_tags", "/byteblaze/a11y-syntax-highlighting/-/tags"),
    ("project_boards", "/byteblaze/a11y-syntax-highlighting/-/boards"),
    ("project_wiki", "/byteblaze/a11y-syntax-highlighting/-/wikis"),
    ("project_snippets", "/byteblaze/a11y-syntax-highlighting/-/snippets"),
    # F. Instance variance (5)
    ("webring_main", "/byteblaze/a11y-webring.club"),
    ("webring_issues", "/byteblaze/a11y-webring.club/-/issues"),
    ("empathy_main", "/byteblaze/empathy-prompts"),
    ("empathy_merge_requests", "/byteblaze/empathy-prompts/-/merge_requests"),
    ("a11yproject_issues", "/a11yproject/a11yproject.com/-/issues"),
    # G. Account scope (3)
    ("account_edit", "/-/profile"),
    ("account_preferences", "/-/profile/preferences"),
    ("account_notifications", "/-/profile/notifications"),
    # H. User scope (1)
    ("user_activity", "/users/byteblaze/activity"),
    # I. Global (2)
    ("search_page", "/search"),
    ("global_snippets", "/snippets"),
]


_STRUCTURE_EXTRACT_JS = r"""
() => {
    const INTERACTIVE = new Set([
        'a', 'button', 'input', 'select', 'textarea', 'form',
        'nav', 'main', 'header', 'footer', 'aside', 'section', 'article',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'table', 'tr', 'td', 'th',
    ]);
    function roleOf(el) {
        const ariaRole = el.getAttribute('role');
        if (ariaRole) return ariaRole;
        return el.tagName.toLowerCase();
    }
    function labelOf(el) {
        const aria = (el.getAttribute('aria-label') || '').trim();
        if (aria) return aria;
        const alt = (el.getAttribute('alt') || '').trim();
        if (alt) return alt;
        const title = (el.getAttribute('title') || '').trim();
        if (title) return title;
        const txt = (el.innerText || el.textContent || '').trim();
        if (txt.length > 0 && txt.length < 100) return txt;
        const href = el.getAttribute('href');
        if (href) return `[href: ${href}]`;
        return '';
    }
    function walk(el, depth) {
        if (!el || depth > 20) return null;
        const tag = el.tagName ? el.tagName.toLowerCase() : '';
        if (!INTERACTIVE.has(tag) && depth > 0 && el.children.length === 0) return null;
        const node = { role: roleOf(el), label: labelOf(el).slice(0, 100), children: [] };
        for (const child of el.children) {
            const sub = walk(child, depth + 1);
            if (sub) node.children.push(sub);
        }
        if (!INTERACTIVE.has(tag) && node.children.length === 0 && !node.label) return null;
        return node;
    }
    return walk(document.body, 0);
}
"""


async def collect_page(page, name: str, path: str, output_dir: Path) -> dict:
    url = BASE_URL + path
    try:
        resp = await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1500)
        axtree = await page.evaluate(_STRUCTURE_EXTRACT_JS)
        final_url = page.url
        title = await page.title()
        http_status = resp.status if resp else None
        data = {
            "name": name,
            "requested_url": url,
            "final_url": final_url,
            "title": title,
            "http_status": http_status,
            "axtree": axtree,
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{name}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {
            "name": name, "requested_url": url,
            "final_url": final_url, "title": title, "http_status": http_status,
            "status": "ok" if final_url.startswith(url.split("?")[0]) or url == final_url else "redirect",
        }
    except Exception as e:
        return {"name": name, "requested_url": url, "status": "error", "error": str(e)}


async def main():
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()
        for name, path in PAGES:
            print(f"{name}: {path}", flush=True)
            result = await collect_page(page, name, path, PAGES_DIR)
            print(f"  → status={result['status']}, final_url={result.get('final_url', 'N/A')}")
            manifest.append(result)
        await browser.close()
    (OUTPUT_DIR / "page_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print()
    print(f"Collected {sum(1 for r in manifest if r['status'] == 'ok')}/{len(manifest)} OK, "
          f"{sum(1 for r in manifest if r['status'] == 'redirect')} redirects, "
          f"{sum(1 for r in manifest if r['status'] == 'error')} errors")
    print(f"Manifest: {OUTPUT_DIR / 'page_manifest.json'}")


if __name__ == "__main__":
    asyncio.run(main())
