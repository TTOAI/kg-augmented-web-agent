"""Stage A.f step — Option 1 frontier-BFS based.

Extract leaves from previous step's BFS tree → use as seeds for next step.
Skip already-visited URLs. Apply rule compression after new crawl.

Usage: python -m scripts.archive.stage_a_f_step [--step-num N]

Pool file: output/validation/stage_a_f/classified.json (accumulated)
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import Counter, deque
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from scripts.kg.utils.classify import load_classifier
from scripts.kg.build.crawl import (
    BASE_URL, STORAGE_STATE, LINK_EXTRACT_JS,
    is_same_host, is_forbidden, normalize_for_dedup,
)
from site_adaptive_webagent.kg.seed.manual_config import load_site_config

POOL_PATH = Path("output/validation/stage_a_f/classified.json")
STEP_OUT_DIR = Path("output/validation/stage_a_f/step")
SITE_CONFIG_PATH = Path("config/sites/gitlab/site_config.yaml")
RULES_PATH = Path("output/validation/rules/class_rules.json")

# Step budgets
STEP_MAX_URL = 1500
STEP_MAX_DEPTH = 4  # from frontier
STEP_MAX_TIME_SEC = 20 * 60
DELAY_MS = 150
KNOWN_CAP = 2  # lower than iter 1 (rule already validated)
DEPTH0_LINK_CAP = 40

# Global budgets (for safety; not enforced in single invocation but tracked)
GLOBAL_MAX_URL = 10000
GLOBAL_MAX_CLASS = 250


def extract_frontier(pool: list[dict]) -> list[str]:
    """Extract leaves (max-depth nodes from previous BFS) as seeds."""
    depth_200 = [r for r in pool if r.get("http_status") == 200 and "depth" in r]
    if not depth_200:
        return []
    max_d = max(r["depth"] for r in depth_200)
    leaves = [r for r in depth_200 if r["depth"] == max_d]
    urls = [r.get("final_url") or r.get("url") for r in leaves if r.get("final_url") or r.get("url")]
    # Dedup
    return list(dict.fromkeys(urls))


async def main():
    STEP_OUT_DIR.mkdir(parents=True, exist_ok=True)
    site_config = load_site_config(SITE_CONFIG_PATH)
    classify = load_classifier(RULES_PATH, SITE_CONFIG_PATH)

    # Load existing accumulated pool
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    skip_normalized: set[str] = set()
    for r in pool:
        u = r.get("final_url") or r.get("url")
        if u:
            skip_normalized.add(normalize_for_dedup(u, site_config))
    print(f"Loaded pool: {len(pool)} records, {len(skip_normalized)} normalized URLs")

    # Extract frontier
    frontier = extract_frontier(pool)
    print(f"Frontier: {len(frontier)} leaf URLs (from previous BFS max depth)")
    if not frontier:
        print("ERROR: no frontier URLs to seed from. Step cannot proceed.")
        return

    visited: dict[str, dict] = {}
    class_counter: Counter = Counter()
    queue: deque = deque()
    enqueued_seen: set[str] = set()

    for seed in frontier:
        # Already visited at depth max_d; we want to explore their CHILDREN
        # So we enqueue them at depth 0 but mark visited already, just extract links
        # Simpler: enqueue their links as depth 0
        pass

    # Instead of visiting frontier URLs (already in pool), we fetch their links
    # directly by re-visiting (small cost) then enqueuing NEW children.
    start = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        page.set_default_timeout(15000)

        # Step A: re-visit each frontier URL to extract children links
        # (not saved as new records since already in pool)
        print("\n[Phase A] Re-visiting frontier to extract outbound links...")
        for i, fu in enumerate(frontier[:min(200, len(frontier))], 1):
            try:
                resp = await page.goto(fu, wait_until="domcontentloaded", timeout=15000)
                if resp and resp.status == 200:
                    await page.wait_for_timeout(50)
                    links = await page.evaluate(LINK_EXTRACT_JS)
                else:
                    links = []
            except Exception:
                links = []
            added = 0
            for link in links:
                if not is_same_host(link) or is_forbidden(link):
                    continue
                link_norm = normalize_for_dedup(link, site_config)
                if link_norm in skip_normalized or link_norm in enqueued_seen:
                    continue
                enqueued_seen.add(link_norm)
                queue.append((link, 0, fu))  # depth 0 relative to this step
                added += 1
                if added >= DEPTH0_LINK_CAP:
                    break
            if i % 25 == 0:
                print(f"  [{i}/{len(frontier)}] queue={len(queue)}")
        print(f"[Phase A] Frontier re-visit done. Queue size: {len(queue)}")

        # Step B: BFS from enqueued children
        print("\n[Phase B] BFS from frontier children...")
        while queue and len(visited) < STEP_MAX_URL:
            elapsed = time.time() - start
            if elapsed > STEP_MAX_TIME_SEC:
                print(f"Timeout {STEP_MAX_TIME_SEC}s reached")
                break
            url, depth, parent = queue.popleft()
            norm = normalize_for_dedup(url, site_config)
            if norm in skip_normalized or norm in visited:
                continue
            if depth > STEP_MAX_DEPTH:
                continue

            try:
                predicted = classify(url)
            except Exception:
                predicted = None
            if predicted is not None and class_counter[predicted] >= KNOWN_CAP:
                continue

            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(DELAY_MS)
                status = resp.status if resp else None
                final = page.url
                title = await page.title() if status == 200 else ""
            except Exception as e:
                visited[norm] = {
                    "url": url, "final_url": None, "http_status": "error",
                    "title": None, "depth": depth, "linked_from": parent,
                    "predicted_class": predicted, "error": str(e)[:200],
                }
                continue

            final_class = classify(final) if status == 200 else None
            visited[norm] = {
                "url": url, "final_url": final, "http_status": status,
                "title": (title or "")[:120], "depth": depth,
                "linked_from": parent,
                "predicted_class": predicted, "final_class": final_class,
            }
            class_counter[final_class] += 1

            if status == 200 and depth < STEP_MAX_DEPTH:
                try:
                    links = await page.evaluate(LINK_EXTRACT_JS)
                except Exception:
                    links = []
                for link in links:
                    if not is_same_host(link) or is_forbidden(link):
                        continue
                    link_norm = normalize_for_dedup(link, site_config)
                    if link_norm in skip_normalized or link_norm in enqueued_seen or link_norm in visited:
                        continue
                    enqueued_seen.add(link_norm)
                    queue.append((link, depth + 1, url))

            if len(visited) % 50 == 0:
                known = sum(v for k, v in class_counter.items() if k is not None)
                unm = class_counter.get(None, 0)
                print(f"[{len(visited):4d}/{STEP_MAX_URL}] depth={depth} elapsed={elapsed:4.0f}s "
                      f"queue={len(queue):4d} known={known:3d} unmatched={unm:3d}")

        await browser.close()

    new_records = list(visited.values())
    ok = [r for r in new_records if r.get("http_status") == 200]
    matched = [r for r in ok if r.get("final_class")]
    unmatched = [r for r in ok if not r.get("final_class")]

    print()
    print(f"=== Step result ===")
    print(f"New records: {len(new_records)}")
    print(f"HTTP 200: {len(ok)}")
    print(f"Matched: {len(matched)} ({len(matched)/max(len(ok),1)*100:.1f}%)")
    print(f"Unmatched: {len(unmatched)}")

    # Save step result
    step_num = 2
    while (STEP_OUT_DIR / f"step_{step_num}_new.json").exists():
        step_num += 1
    step_file = STEP_OUT_DIR / f"step_{step_num}_new.json"
    step_file.write_text(json.dumps(new_records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved: {step_file}")

    # Unmatched clusters
    if unmatched:
        from scripts.archive.stage_a_f_cluster import normalize_path_to_pattern
        from collections import defaultdict
        clusters = defaultdict(list)
        for r in unmatched:
            u = r.get("final_url") or r["url"]
            p = urlparse(u)
            clusters[normalize_path_to_pattern(p.path)].append(u)
        print(f"\nUnmatched clusters: {len(clusters)}")
        for pat, urls in sorted(clusters.items(), key=lambda x: -len(x[1]))[:20]:
            print(f"  {len(urls):>3}  {pat}")


if __name__ == "__main__":
    asyncio.run(main())
