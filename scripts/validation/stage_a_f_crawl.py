"""Stage A.f — BFS spider crawl + pre-visit per-known-class cap.

Seeds → BFS → (pre-visit URL classify → known-class cap skip) → fetch → extract links.

Output:
  output/validation/stage_a_f/crawled_urls.json
  output/validation/stage_a_f/class_counter.json
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import Counter, deque
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from scripts.validation.stage_a_classify import load_classifier
from site_adaptive_webagent.kg.seed.manual_config import load_site_config
from site_adaptive_webagent.kg.urlnorm import normalize_url

BASE_URL = "http://localhost:8023"
STORAGE_STATE = Path("output/validation/.storage_state.json")
SITE_CONFIG_PATH = Path("config/sites/gitlab/site_config.yaml")
RULES_PATH = Path("output/validation/rules/class_rules.json")
OUT_DIR = Path("output/validation/stage_a_f")

SEEDS = [
    "/dashboard",
    "/explore/projects",
    "/byteblaze",
    "/byteblaze/a11y-syntax-highlighting",
    "/-/profile",
    "/help",
]

MAX_DEPTH = 5
MAX_URLS = 1500
MAX_TIME_SEC = 30 * 60
DELAY_MS = 150
KNOWN_CAP = 5
# Per-page link cap (mainly for depth 0 to avoid seed queue explosion)
DEPTH0_LINK_CAP = 50

FORBIDDEN_PATTERNS = [
    "/sign_out",
    "/logout",
    "?_method=delete",
    "?method=delete",
    "/destroy",
    "/admin",
    # Mutation-risk endpoints
    "/toggle_",
    "/resolve",
    "/reopen",
]


def is_same_host(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.netloc in ("", "localhost:8023", "127.0.0.1:8023")
    except Exception:
        return False


def is_forbidden(url: str) -> bool:
    return any(pat in url for pat in FORBIDDEN_PATTERNS)


def normalize_for_dedup(url: str, site_config) -> str:
    try:
        norm = normalize_url(url, site_config)
        qs = "&".join(f"{k}={v}" for k, v in sorted(norm.query_pairs))
        return norm.path + (f"?{qs}" if qs else "")
    except Exception:
        return url


LINK_EXTRACT_JS = r"""
() => {
    const anchors = Array.from(document.querySelectorAll('a[href]'));
    return anchors.map(a => a.href).filter(h => /^https?:\/\//.test(h));
}
"""


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    site_config = load_site_config(SITE_CONFIG_PATH)
    classify = load_classifier(RULES_PATH, SITE_CONFIG_PATH)

    visited: dict[str, dict] = {}
    class_counter: Counter = Counter()
    queue: deque = deque()
    start = time.time()

    for seed in SEEDS:
        queue.append((BASE_URL + seed, 0, "seed"))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {}
        if STORAGE_STATE.exists():
            ctx_kwargs["storage_state"] = str(STORAGE_STATE)
        ctx = await browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        page.set_default_timeout(15000)

        # Auth sanity
        try:
            resp = await page.goto(BASE_URL + "/dashboard", wait_until="domcontentloaded", timeout=15000)
            if resp and resp.status != 200:
                print(f"WARNING: /dashboard returned {resp.status} — auth may be expired. Continuing anyway.")
        except Exception as e:
            print(f"WARNING: auth sanity check failed: {e}")

        enqueued_seen: set[str] = set()  # prevent duplicate queue entries early

        while queue and len(visited) < MAX_URLS:
            elapsed = time.time() - start
            if elapsed > MAX_TIME_SEC:
                print(f"\nTimeout {MAX_TIME_SEC}s reached")
                break

            url, depth, parent = queue.popleft()
            norm = normalize_for_dedup(url, site_config)
            if norm in visited:
                continue
            if depth > MAX_DEPTH:
                continue

            # Pre-visit URL-only classification for cap
            try:
                predicted = classify(url)
            except Exception:
                predicted = None
            if predicted is not None and class_counter[predicted] >= KNOWN_CAP:
                continue  # known class cap reached, skip

            # Fetch
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

            visited[norm] = {
                "url": url, "final_url": final, "http_status": status,
                "title": (title or "")[:120], "depth": depth,
                "linked_from": parent, "predicted_class": predicted,
            }
            class_counter[predicted] += 1

            # Extract links
            if status == 200 and depth < MAX_DEPTH:
                try:
                    links = await page.evaluate(LINK_EXTRACT_JS)
                except Exception:
                    links = []
                seen_page: set[str] = set()
                added = 0
                cap = DEPTH0_LINK_CAP if depth == 0 else 1000
                for link in links:
                    if not is_same_host(link) or is_forbidden(link):
                        continue
                    if link in seen_page:
                        continue
                    seen_page.add(link)
                    # Early dedup to avoid queue blowup
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
    (OUT_DIR / "class_counter.json").write_text(
        json.dumps({(k if k is not None else "__unmatched__"): v
                    for k, v in class_counter.items()}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print()
    print(f"Total records: {len(records)}")
    top = class_counter.most_common(15)
    print(f"Top classes ({len(class_counter)} distinct keys):")
    for k, v in top:
        print(f"  {k!r}: {v}")
    print(f"\nSaved: {OUT_DIR / 'crawled_urls.json'}")
    print(f"       {OUT_DIR / 'class_counter.json'}")


if __name__ == "__main__":
    asyncio.run(main())
