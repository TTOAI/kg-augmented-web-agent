"""Stage A.f final convergence crawl — new seeds, measure unmatched with final rules.

Different from iter 1 crawl:
- New seeds (different entry points)
- Smaller budget (500 URLs) — final verification, not exhaustive
- Lower known-cap (2) — prioritize diversity
- Apply current 136 rules

If unmatched = 0 (or near-zero), Stage A.f is converged.
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
    BASE_URL, STORAGE_STATE, FORBIDDEN_PATTERNS, LINK_EXTRACT_JS,
    is_same_host, is_forbidden, normalize_for_dedup,
)
from site_adaptive_webagent.kg.seed.manual_config import load_site_config

SITE_CONFIG_PATH = Path("config/sites/gitlab/site_config.yaml")
RULES_PATH = Path("output/validation/rules/class_rules.json")
OUT_DIR = Path("output/validation/stage_a_f_final")

# New seeds (different from iter 1)
NEW_SEEDS = [
    "/byteblaze/a11y-webring.club",                # different project
    "/byteblaze/empathy-prompts",                  # different project
    "/a11yproject/a11yproject.com",                # different namespace
    "/byteblaze/empathy-prompts/-/merge_requests/19",  # MR detail entry
    "/-/profile/account",                          # account sub-tree
    "/-/snippets",                                 # global snippets
    "/byteblaze/a11y-syntax-highlighting/-/pipelines",  # CI/CD deep start
    "/users/byteblaze",                            # user page (redirects)
]

MAX_DEPTH = 4
MAX_URLS = 500
MAX_TIME_SEC = 15 * 60
DELAY_MS = 150
KNOWN_CAP = 2
DEPTH0_LINK_CAP = 40


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    site_config = load_site_config(SITE_CONFIG_PATH)
    classify = load_classifier(RULES_PATH, SITE_CONFIG_PATH)

    visited: dict[str, dict] = {}
    class_counter: Counter = Counter()
    queue: deque = deque()
    start = time.time()

    for seed in NEW_SEEDS:
        queue.append((BASE_URL + seed, 0, "seed"))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        page.set_default_timeout(15000)

        enqueued_seen: set[str] = set()

        while queue and len(visited) < MAX_URLS:
            elapsed = time.time() - start
            if elapsed > MAX_TIME_SEC:
                print(f"Timeout {MAX_TIME_SEC}s reached")
                break
            url, depth, parent = queue.popleft()
            norm = normalize_for_dedup(url, site_config)
            if norm in visited:
                continue
            if depth > MAX_DEPTH:
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

            # Re-classify final_url (after redirect) for accurate outcome
            final_class = classify(final) if status == 200 else None

            visited[norm] = {
                "url": url, "final_url": final, "http_status": status,
                "title": (title or "")[:120], "depth": depth,
                "linked_from": parent,
                "predicted_class": predicted, "final_class": final_class,
            }
            class_counter[final_class] += 1

            if status == 200 and depth < MAX_DEPTH:
                try:
                    links = await page.evaluate(LINK_EXTRACT_JS)
                except Exception:
                    links = []
                seen_page: set[str] = set()
                added = 0
                cap = DEPTH0_LINK_CAP if depth == 0 else 500
                for link in links:
                    if not is_same_host(link) or is_forbidden(link):
                        continue
                    if link in seen_page:
                        continue
                    seen_page.add(link)
                    link_norm = normalize_for_dedup(link, site_config)
                    if link_norm in visited or link_norm in enqueued_seen:
                        continue
                    enqueued_seen.add(link_norm)
                    queue.append((link, depth + 1, url))
                    added += 1
                    if added >= cap:
                        break

            if len(visited) % 25 == 0:
                known = sum(v for k, v in class_counter.items() if k is not None)
                unm = class_counter.get(None, 0)
                print(f"[{len(visited):4d}/{MAX_URLS}] depth={depth} elapsed={elapsed:4.0f}s "
                      f"queue={len(queue):4d} known={known:3d} unmatched={unm:3d}")

        await browser.close()

    records = list(visited.values())
    (OUT_DIR / "crawled_urls.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    # Analysis
    ok = [r for r in records if r.get("http_status") == 200]
    matched = [r for r in ok if r.get("final_class")]
    unmatched = [r for r in ok if not r.get("final_class")]
    coverage = len(matched) / len(ok) * 100 if ok else 0

    print()
    print(f"=== Convergence check result ===")
    print(f"Total records: {len(records)}")
    print(f"HTTP 200: {len(ok)}")
    print(f"Matched: {len(matched)} ({coverage:.1f}%)")
    print(f"Unmatched: {len(unmatched)}")
    print()
    if unmatched:
        print("Unmatched URL samples (first 20):")
        for r in unmatched[:20]:
            u = (r.get("final_url") or r["url"]).replace(BASE_URL, "")
            print(f"  depth={r['depth']}  {u}")
    else:
        print("✅ ALL matched — Stage A.f CONVERGED")

    # Cross-check with iter1 seeds' rules — any previously unseen class appear?
    previous_classes = set()
    try:
        iter2 = json.loads(Path("output/validation/stage_a_f/classified.json").read_text())
        previous_classes = {r["final_class"] for r in iter2 if r.get("final_class")}
    except Exception:
        pass
    new_classes_encountered = {r["final_class"] for r in matched} - previous_classes
    print()
    print(f"Classes observed in this crawl: {len({r['final_class'] for r in matched})}")
    print(f"Classes seen in iter 1-3: {len(previous_classes)}")
    if new_classes_encountered:
        print(f"⚠️ NEW classes found only in final check: {new_classes_encountered}")
    else:
        print("✅ No new classes in final check — class taxonomy stable")


if __name__ == "__main__":
    asyncio.run(main())
