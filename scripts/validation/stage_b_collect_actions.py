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
                    else:
                        actions = []
                except Exception as e:
                    actions = [{"error": str(e)[:100]}]
                cls_actions.append({
                    "url": url,
                    "actions": actions,
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
