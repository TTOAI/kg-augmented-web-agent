"""Stage B.1 — Collect per-class actions.

For each class, pick 1-3 sample URLs from the accumulated pool (step 1 + step 2').
Re-visit each sample, extract actionable elements (a[href], button, role=button).
Save raw action list per class.

Stage B.2/3 aggregate + normalize afterwards.

Input:
  output/validation/stage_a_f/classified.json (step 1, 1457)
  output/validation/stage_a_f/step/step_2_new.json (step 2', 238)
  output/validation/rules/class_rules.json

Output:
  output/validation/stage_b/raw_actions_per_class.json
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path

from playwright.async_api import async_playwright

from scripts.validation.stage_a_classify import load_classifier
from scripts.validation.stage_a_f_crawl import BASE_URL, STORAGE_STATE

POOL_PATHS = [
    Path("output/validation/stage_a_f/classified.json"),
    Path("output/validation/stage_a_f/step/step_2_new.json"),
]
OUT = Path("output/validation/stage_b/raw_actions_per_class.json")

SAMPLES_PER_CLASS = 3  # up to N sample URLs per class
DELAY_MS = 120

ACTION_EXTRACT_JS = r"""
() => {
    const els = Array.from(document.querySelectorAll(
        'a[href], button, [role="button"], [role="tab"], [role="link"], input[type="submit"]'
    ));
    const out = [];
    for (const e of els) {
        if (e.offsetParent === null) continue;
        const label = (e.innerText || e.getAttribute('aria-label') || e.getAttribute('title') || '').trim().replace(/\s+/g, ' ');
        if (!label || label.length > 120) continue;
        const tag = e.tagName.toLowerCase();
        const href = e.getAttribute('href') || null;
        const role = e.getAttribute('role') || null;
        const type = e.getAttribute('type') || null;
        out.push({label, tag, href, role, type});
    }
    return out;
}
"""

# Phase 3.K: MUTATE form shortcut — DOM의 <form> 요소 + 그 아래 input/select/textarea
# 메타데이터를 수집해 agent에게 "POST/PUT endpoint + required params" 힌트로 제공.
# 각 form의 action / method / field list를 JSON으로 덤프.
#
# 수집 범위:
#   - action (form submission URL, 절대 경로로 변환)
#   - method (POST/GET/PATCH/DELETE 등; 'dialog' 등 특수값은 무시)
#   - fields: name/type/required/default/placeholder/checked/options(select)
#
# 보안/운영 고려:
#   - authenticity_token / _method hidden 은 agent에게는 "런타임 추출" 대상이라 힌트에서 제외
#   - password / session / OTP 필드는 민감하므로 placeholder만 노출 (value 제외)
FORM_EXTRACT_JS = r"""
() => {
    const SENSITIVE_NAMES = new Set([
        'password', 'current_password', 'new_password', 'password_confirmation',
        'otp', 'one_time_password', 'code',
    ]);
    const EXCLUDED_NAMES = new Set([
        'authenticity_token', 'utf8', '_method',
    ]);
    function normalizeUrl(action) {
        if (!action) return location.pathname + location.search;
        try {
            const u = new URL(action, location.href);
            if (u.origin === location.origin) return u.pathname + u.search;
            return action;
        } catch (_) { return action; }
    }
    const forms = document.querySelectorAll('form');
    const out = [];
    for (const f of forms) {
        const rawMethod = (f.getAttribute('method') || 'GET').toUpperCase();
        const actionUrl = normalizeUrl(f.getAttribute('action') || f.action || '');
        // HTTP method override via hidden <input name="_method">
        const mOverride = f.querySelector('input[name="_method"]');
        const method = mOverride ? (mOverride.value || rawMethod).toUpperCase() : rawMethod;
        if (method === 'DIALOG') continue;
        // Collect fields
        const fields = [];
        const inputs = f.querySelectorAll('input, select, textarea');
        for (const el of inputs) {
            const name = el.getAttribute('name') || '';
            if (!name || EXCLUDED_NAMES.has(name)) continue;
            const tag = el.tagName.toLowerCase();
            const type = (el.getAttribute('type') || tag).toLowerCase();
            const required = el.required || el.hasAttribute('required');
            const placeholder = el.getAttribute('placeholder') || '';
            const isSensitive = SENSITIVE_NAMES.has(name) || type === 'password';
            const fieldEntry = {
                name, tag, type,
                required,
                placeholder: placeholder.slice(0, 80),
            };
            // default value (except sensitive)
            if (!isSensitive) {
                if (tag === 'select') {
                    const selected = el.querySelector('option[selected]') || el.querySelector('option');
                    fieldEntry.default_value = selected ? (selected.value || selected.textContent.trim()).slice(0, 80) : '';
                    // Collect option values (up to 10)
                    const opts = Array.from(el.querySelectorAll('option')).slice(0, 10).map(o => ({
                        value: (o.value || '').slice(0, 60),
                        label: (o.textContent || '').trim().slice(0, 60),
                    }));
                    fieldEntry.options = opts;
                } else if (type === 'radio') {
                    fieldEntry.default_value = el.value || '';
                    fieldEntry.checked = !!el.checked;
                } else if (type === 'checkbox') {
                    fieldEntry.default_value = el.value || '1';
                    fieldEntry.checked = !!el.checked;
                } else if (type === 'hidden') {
                    fieldEntry.default_value = (el.value || '').slice(0, 80);
                } else {
                    fieldEntry.default_value = (el.value || '').slice(0, 80);
                }
            } else {
                fieldEntry.sensitive = true;
            }
            fields.push(fieldEntry);
        }
        // Submit button label (if any) — helps agent identify form purpose
        let submitLabel = '';
        const btn = f.querySelector('button[type="submit"], input[type="submit"]');
        if (btn) {
            submitLabel = (btn.innerText || btn.getAttribute('value') || btn.getAttribute('aria-label') || '').trim().slice(0, 60);
        }
        out.push({action: actionUrl, method, submit_label: submitLabel, fields});
    }
    return out;
}
"""

# Phase 3.J F1: role=tab 요소의 href가 '#' 또는 null일 때 Playwright 클릭으로 URL
# 변화를 관측해 실제 쿼리 파라미터 포함 URL을 캡처한다. ARIA 계약상 role="tab"은
# 읽기 전용 view switch이므로 side effect 없음 (state 변경 없는 filter URL 요청).
# Click 후 `goto(original)`로 복원.
TAB_CAPTURE_LIMIT = 10  # per URL, avoid runaway when page has many stale tabs


async def _capture_tab_click_urls(
    page, original_url: str, existing_hrefs: set[str]
) -> list[dict]:
    """Click each role=tab with href='#' or no href, record URL change as action.

    Returns list of captured action dicts matching ACTION_EXTRACT_JS shape.
    Errors or navigations away from the list page (different path) are discarded.
    """
    captured: list[dict] = []
    try:
        tab_locators = page.locator('[role="tab"]')
        count = await tab_locators.count()
    except Exception:
        return captured
    count = min(count, TAB_CAPTURE_LIMIT)
    for idx in range(count):
        try:
            el = tab_locators.nth(idx)
            if not await el.is_visible():
                continue
            href_attr = (await el.get_attribute("href")) or ""
            # Only click tabs whose static href is unresolvable (# / empty)
            if href_attr and href_attr != "#":
                continue
            label = ((await el.inner_text()) or "").strip().replace("\n", " ")
            if not label or len(label) > 120:
                continue
            try:
                await el.click(timeout=3000)
            except Exception:
                continue
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            new_url = page.url
            if not new_url or new_url == original_url:
                continue
            if new_url in existing_hrefs:
                continue
            existing_hrefs.add(new_url)
            captured.append({
                "label": label,
                "tag": "a",
                "href": new_url,
                "role": "tab",
                "type": None,
            })
        except Exception:
            continue
        finally:
            # Revert to original URL so subsequent tab clicks start from same state.
            try:
                if page.url != original_url:
                    await page.goto(original_url, wait_until="domcontentloaded", timeout=10000)
            except Exception:
                break  # if revert fails, abandon remaining tabs on this URL
    return captured


def load_pool() -> list[dict]:
    pool = []
    for p in POOL_PATHS:
        if p.exists():
            pool.extend(json.loads(p.read_text(encoding="utf-8")))
    return pool


def pick_sample_urls(pool: list[dict]) -> dict[str, list[str]]:
    """Per class, collect up to SAMPLES_PER_CLASS URLs."""
    by_class: dict[str, list[str]] = defaultdict(list)
    for r in pool:
        cls = r.get("final_class")
        if not cls:
            continue
        url = r.get("final_url") or r.get("url")
        if not url:
            continue
        if len(by_class[cls]) < SAMPLES_PER_CLASS:
            # Dedup same-URL
            if url not in by_class[cls]:
                by_class[cls].append(url)
    return dict(by_class)


async def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pool = load_pool()
    print(f"Pool size: {len(pool)} records")
    class_samples = pick_sample_urls(pool)
    print(f"Classes: {len(class_samples)}")
    total_urls = sum(len(v) for v in class_samples.values())
    print(f"Total URLs to visit: {total_urls}")

    results: dict[str, dict] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        page.set_default_timeout(15000)

        i = 0
        for cls, urls in sorted(class_samples.items()):
            cls_actions: list[dict] = []
            for url in urls:
                i += 1
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(DELAY_MS)
                    if resp and resp.status == 200:
                        actions = await page.evaluate(ACTION_EXTRACT_JS)
                        # Phase 3.J F1: additionally click role=tab with href=# to
                        # capture the query-param URL that the tab navigates to.
                        existing_hrefs = {
                            a.get("href") for a in actions if a.get("href")
                        }
                        extra = await _capture_tab_click_urls(
                            page, original_url=url, existing_hrefs=existing_hrefs,
                        )
                        actions.extend(extra)
                        # Phase 3.K: extract form metadata for MUTATE shortcut hints.
                        try:
                            forms = await page.evaluate(FORM_EXTRACT_JS)
                        except Exception:
                            forms = []
                    else:
                        actions = []
                        forms = []
                except Exception as e:
                    actions = [{"error": str(e)[:100]}]
                    forms = []
                cls_actions.append({
                    "url": url,
                    "actions": actions,
                    "forms": forms,
                })
                if i % 50 == 0:
                    print(f"  [{i}/{total_urls}] visited, current class={cls}")
            results[cls] = {
                "sample_count": len(urls),
                "instances": cls_actions,
            }
        await browser.close()

    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {OUT}")
    # Summary
    total_actions = sum(
        sum(len(inst["actions"]) for inst in cls_data["instances"])
        for cls_data in results.values()
    )
    print(f"Total raw actions collected: {total_actions}")
    print(f"Classes processed: {len(results)}")


if __name__ == "__main__":
    asyncio.run(main())
