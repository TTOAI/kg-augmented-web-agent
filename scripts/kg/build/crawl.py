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

from scripts.kg.utils.classify import load_classifier
from site_adaptive_webagent.kg.seed.manual_config import load_site_config
from site_adaptive_webagent.kg.site_extras import load_site_crawl
from site_adaptive_webagent.kg.urlnorm import normalize_url

import os

#  crawl 상수를 config/sites/<site>/crawl.yaml에서 로드.
# 기존 하드코드 값(BASE_URL, SEEDS, FORBIDDEN_PATTERNS)은 gitlab crawl.yaml에 이관.
_SITE_NAME = os.getenv("SITE_NAME", "gitlab")
_SITE_CRAWL = load_site_crawl(_SITE_NAME)

BASE_URL = _SITE_CRAWL.base_url
STORAGE_STATE = Path("output/validation/.storage_state.json")
SITE_CONFIG_PATH = Path("config/sites") / _SITE_NAME / "site_config.yaml"
RULES_PATH = Path("output/validation/rules/class_rules.json")
OUT_DIR = Path("output/validation/stage_a_f")

SEEDS: list[str] = list(_SITE_CRAWL.seeds)
if not SEEDS:
    # Config가 로드되지 않은 경우 — "/" 하나로 시작해 BFS가 기본 root에서 확장
    # 되도록. site-specific seed 목록은 반드시 crawl.yaml에서 공급.
    SEEDS = ["/"]

# CDIP Step 2'+ 지원: env var로 seed 오버라이드. 이전 step BFS tree의 leaves를
# 넘겨 frontier expansion을 수행할 수 있게 한다.
_SEEDS_OVERRIDE = os.getenv("CRAWL_SEEDS_JSON", "").strip()
if _SEEDS_OVERRIDE:
    try:
        _override = json.loads(_SEEDS_OVERRIDE)
        if isinstance(_override, list) and _override:
            SEEDS = [str(s) for s in _override]
            print(f"[stage_a_f_crawl] seeds overridden via CRAWL_SEEDS_JSON: {len(SEEDS)} entries")
    except Exception as exc:
        print(f"[stage_a_f_crawl] invalid CRAWL_SEEDS_JSON, ignoring: {exc}")

# Skip-existing mode: 이전 step에서 이미 방문한 URL 목록을 skip 처리하고 accumulate.
_SKIP_EXISTING_PATH = os.getenv("CRAWL_SKIP_EXISTING", "").strip()
_APPEND_MODE = bool(os.getenv("CRAWL_APPEND_OUT", "").strip())

MAX_DEPTH = 5
MAX_URLS = 1500
MAX_TIME_SEC = 30 * 60
DELAY_MS = 150
KNOWN_CAP = 5
# Per-page link cap (mainly for depth 0 to avoid seed queue explosion)
DEPTH0_LINK_CAP = 50

FORBIDDEN_PATTERNS: list[str] = list(_SITE_CRAWL.forbidden_patterns)
if not FORBIDDEN_PATTERNS:
    # Config 없을 때 minimal generic fallback — 세션 종료 / HTTP method override만
    FORBIDDEN_PATTERNS = [
        "/sign_out", "/logout", "?_method=delete", "?method=delete",
    ]

# site-agnostic allowed hosts (config 기반). 기본은 base_url의 host를 urlparse로
# 추출해 단일 host만 허용.
def _derive_allowed_hosts() -> tuple[str, ...]:
    if _SITE_CRAWL.allowed_hosts:
        return tuple(_SITE_CRAWL.allowed_hosts)
    try:
        host = urlparse(BASE_URL).netloc
        return (host,) if host else ()
    except Exception:
        return ()


_ALLOWED_HOSTS: tuple[str, ...] = _derive_allowed_hosts()


def is_same_host(url: str) -> bool:
    try:
        p = urlparse(url)
        # 빈 netloc은 상대경로 — 항상 허용. 명시 allowed_hosts에만 포함.
        return p.netloc in ("", *_ALLOWED_HOSTS)
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

    # CDIP accumulate mode: skip URLs already visited in previous steps.
    prior_visited_norm: set[str] = set()
    prior_records: list[dict] = []
    if _SKIP_EXISTING_PATH:
        try:
            prior_records = json.loads(Path(_SKIP_EXISTING_PATH).read_text())
            for r in prior_records:
                u = r.get("url") or r.get("final_url")
                if u:
                    prior_visited_norm.add(normalize_for_dedup(u, site_config))
            print(f"[stage_a_f_crawl] skip-existing loaded: {len(prior_visited_norm)} prior URLs")
        except Exception as exc:
            print(f"[stage_a_f_crawl] skip-existing load failed: {exc}")

    # Seeds: prefix with BASE_URL if relative, else use as-is (Step 2' may pass full URLs).
    for seed in SEEDS:
        if seed.startswith("http://") or seed.startswith("https://"):
            queue.append((seed, 0, "seed"))
        else:
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
            if norm in prior_visited_norm:
                continue  # CDIP accumulate: skip URLs from prior steps
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
    if _APPEND_MODE and prior_records:
        # Merge prior + new. Dedup by url.
        existing_urls = {r.get("url") for r in prior_records}
        merged = list(prior_records) + [r for r in records if r.get("url") not in existing_urls]
        records = merged
        print(f"[stage_a_f_crawl] append mode: merged {len(prior_records)} prior + {len(merged)-len(prior_records)} new = {len(merged)} total")
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
