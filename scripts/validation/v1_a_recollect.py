"""Stage A.1 expansion — 신규 34 페이지 수집."""
from __future__ import annotations

import asyncio
from playwright.async_api import async_playwright

from scripts.validation.v1_a_collect_axtrees import (
    PAGES_DIR,
    STORAGE_STATE,
    collect_page,
)

FIX_PAGES: list[tuple[str, str]] = [
    # A. Project detail (5)
    ("project_issue_detail", "/byteblaze/a11y-syntax-highlighting/-/issues/1"),
    ("project_blob_detail", "/byteblaze/a11y-syntax-highlighting/-/blob/main/README.md"),
    ("project_commit_detail", "/byteblaze/a11y-syntax-highlighting/-/commit/62820763d9b5f3b25720596f542aaf89d917fb17"),
    ("project_tag_detail", "/byteblaze/empathy-prompts/-/tags/v0.1.0"),
    ("project_mr_detail", "/byteblaze/empathy-prompts/-/merge_requests/19"),
    # B. Project form (4)
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


async def main():
    if not FIX_PAGES:
        print("No FIX_PAGES specified.")
        return
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()
        n_ok = n_err = 0
        for name, path in FIX_PAGES:
            result = await collect_page(page, name, path, PAGES_DIR)
            status = result.get('http_status')
            marker = '✓' if status == 200 else '✗'
            print(f"  {marker} {name:35s} http={status} | {path}")
            if status == 200:
                n_ok += 1
            else:
                n_err += 1
        await browser.close()
        print(f"\nCollected: {n_ok} OK, {n_err} errors, total {len(FIX_PAGES)}")


if __name__ == "__main__":
    asyncio.run(main())
