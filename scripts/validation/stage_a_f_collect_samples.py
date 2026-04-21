"""Stage A.f collect samples — cluster representative URL의 AXTree 수집.

Input: output/validation/stage_a_f/iter2_unmatched_clusters.json
Output: output/validation/V1_pages/pages/iter2_<sanitized_name>.json (per-page)
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

from scripts.validation.v1_a_collect_axtrees import (
    PAGES_DIR,
    STORAGE_STATE,
    collect_page,
)

CLUSTERS_PATH = Path("output/validation/stage_a_f/iter2_unmatched_clusters.json")

# Only collect clusters with count >= this threshold
MIN_CLUSTER_COUNT = 3

# Max representatives per cluster
REPS_PER_CLUSTER = 1


def sanitize_name(pattern: str) -> str:
    """Cluster pattern → safe filename."""
    s = pattern.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    s = re.sub(r"[^A-Za-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return f"iter2_{s[:60]}"


async def main():
    data = json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))
    clusters = [c for c in data["clusters"] if c["count"] >= MIN_CLUSTER_COUNT]
    print(f"Clusters with count >= {MIN_CLUSTER_COUNT}: {len(clusters)}")

    # Collect targets
    targets: list[tuple[str, str]] = []
    for c in clusters:
        reps = c["representatives"][:REPS_PER_CLUSTER]
        for i, rep in enumerate(reps):
            url = rep["url"]
            # Strip host to get path for collect_page (which prepends BASE_URL)
            from urllib.parse import urlparse
            p = urlparse(url)
            path = p.path + (f"?{p.query}" if p.query else "")
            name = sanitize_name(c["pattern"])
            if len(reps) > 1:
                name += f"_{i}"
            targets.append((name, path))

    print(f"Target URLs: {len(targets)}")

    # Filter out targets whose file already exists (resume support)
    new_targets = [(n, p) for n, p in targets if not (PAGES_DIR / f"{n}.json").exists()]
    print(f"New (not yet collected): {len(new_targets)}")

    async with async_playwright() as p_ctx:
        browser = await p_ctx.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()
        n_ok = n_err = 0
        for i, (name, path) in enumerate(new_targets, 1):
            result = await collect_page(page, name, path, PAGES_DIR)
            status = result.get("http_status")
            mark = "✓" if status == 200 else "✗"
            if status == 200:
                n_ok += 1
            else:
                n_err += 1
            if i % 10 == 0 or i == len(new_targets):
                print(f"  [{i}/{len(new_targets)}] {mark} {name} http={status}")
        await browser.close()
    print(f"\nCollected: {n_ok} OK, {n_err} errors")


if __name__ == "__main__":
    asyncio.run(main())
