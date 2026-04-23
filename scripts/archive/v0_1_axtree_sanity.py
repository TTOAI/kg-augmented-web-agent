"""V0.1 — AXTree collection pipeline sanity check.

Purpose: Playwright로 GitLab 5 페이지의 AXTree를 2회 수집하여 일관성 측정.
Success criterion: 2회 수집 간 AXTree 98%+ 일치 (동적 timestamp 등 허용).

Output:
  output/validation/V0_1_axtree_samples/run1/<page>.json
  output/validation/V0_1_axtree_samples/run2/<page>.json
  output/validation/V0_1_axtree_samples/diff_report.md
"""
from __future__ import annotations

import asyncio
import difflib
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

# Test pages (주요 GitLab section)
TEST_PAGES = [
    ("dashboard", "/dashboard"),
    ("dashboard_projects", "/dashboard/projects"),
    ("dashboard_issues", "/dashboard/issues"),
    ("explore_projects", "/explore/projects"),
    ("user_profile", "/byteblaze"),
]

BASE_URL = "http://localhost:8023"
OUTPUT_DIR = Path("output/validation/V0_1_axtree_samples")
STORAGE_STATE = Path("output/validation/.storage_state.json")


_STRUCTURE_EXTRACT_JS = r"""
() => {
    // Walk DOM and build role+label tree similar to AXTree
    const INTERACTIVE = new Set([
        'a', 'button', 'input', 'select', 'textarea', 'form',
        'nav', 'main', 'header', 'footer', 'aside', 'section', 'article',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'table', 'tr', 'td', 'th',
    ]);
    function roleOf(el) {
        const ariaRole = el.getAttribute('role');
        if (ariaRole) return ariaRole;
        const tag = el.tagName.toLowerCase();
        return tag;
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
    const root = document.body;
    return walk(root, 0);
}
"""


async def collect_axtree(page, url: str) -> dict:
    """Load page and extract DOM-based structure tree (AXTree proxy)."""
    await page.goto(url, wait_until="networkidle", timeout=30000)
    # Small wait for dynamic content stabilize
    await page.wait_for_timeout(1500)
    snapshot = await page.evaluate(_STRUCTURE_EXTRACT_JS)
    return {
        "url": page.url,
        "title": await page.title(),
        "axtree": snapshot,
    }


async def collect_run(run_label: str, output_dir: Path):
    """Run 1 collection: visit all test pages and save AXTree."""
    output_dir.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context_kwargs = {}
        if STORAGE_STATE.exists():
            context_kwargs["storage_state"] = str(STORAGE_STATE)
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        for name, path in TEST_PAGES:
            url = BASE_URL + path
            print(f"[{run_label}] Visiting {url}...", flush=True)
            try:
                data = await collect_axtree(page, url)
                out_path = output_dir / f"{name}.json"
                out_path.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                print(f"  → saved {out_path} ({out_path.stat().st_size} bytes)")
            except Exception as e:
                print(f"  ERROR: {e}")
                out_path = output_dir / f"{name}.error.txt"
                out_path.write_text(str(e), encoding="utf-8")
        await browser.close()


def normalize_axtree_for_compare(tree: dict) -> str:
    """Strip volatile fields (timestamps, counters) for diff."""
    def _walk(node, lines, depth=0):
        if not isinstance(node, dict):
            return
        role = node.get("role", "")
        name = node.get("name", "")
        # Skip nodes that change every load
        if any(kw in name.lower() for kw in ["ago", "sec", "min", "hour", "day"]):
            name = "<time>"
        # Skip counters (numbers that may change)
        # Keep structure only
        lines.append("  " * depth + f"{role}: {name}")
        for child in node.get("children", []):
            _walk(child, lines, depth + 1)
    lines = []
    _walk(tree.get("axtree") or tree, lines)
    return "\n".join(lines)


def compute_similarity(text_a: str, text_b: str) -> float:
    """Line-level similarity via difflib."""
    return difflib.SequenceMatcher(None, text_a, text_b).ratio()


def compare_runs(run1_dir: Path, run2_dir: Path) -> dict:
    """Compare run1 and run2 per page."""
    report = {}
    for name, _ in TEST_PAGES:
        f1 = run1_dir / f"{name}.json"
        f2 = run2_dir / f"{name}.json"
        if not (f1.exists() and f2.exists()):
            report[name] = {"status": "missing", "f1_exists": f1.exists(), "f2_exists": f2.exists()}
            continue
        try:
            d1 = json.loads(f1.read_text(encoding="utf-8"))
            d2 = json.loads(f2.read_text(encoding="utf-8"))
        except Exception as e:
            report[name] = {"status": "parse_error", "error": str(e)}
            continue
        norm1 = normalize_axtree_for_compare(d1)
        norm2 = normalize_axtree_for_compare(d2)
        sim = compute_similarity(norm1, norm2)
        line_count_1 = norm1.count("\n") + 1
        line_count_2 = norm2.count("\n") + 1
        report[name] = {
            "status": "ok",
            "similarity": round(sim, 4),
            "lines_run1": line_count_1,
            "lines_run2": line_count_2,
            "url_run1": d1.get("url"),
            "url_run2": d2.get("url"),
        }
    return report


def write_report(report: dict, output_path: Path):
    lines = ["# V0.1 — AXTree Collection Sanity", ""]
    lines.append("## Summary")
    lines.append("")
    sims = [v["similarity"] for v in report.values() if v.get("status") == "ok"]
    if sims:
        avg_sim = sum(sims) / len(sims)
        lines.append(f"- Pages tested: {len(TEST_PAGES)}")
        lines.append(f"- Successful comparisons: {len(sims)}")
        lines.append(f"- Average similarity: **{avg_sim:.4f}** ({avg_sim*100:.2f}%)")
        lines.append(f"- Min similarity: {min(sims):.4f}")
        lines.append(f"- Max similarity: {max(sims):.4f}")
        lines.append("")
        threshold = 0.98
        passed = sum(1 for s in sims if s >= threshold)
        lines.append(f"## Pass/Fail @ threshold {threshold}")
        lines.append(f"- **{passed}/{len(sims)} pages** reached {threshold} similarity")
        lines.append("")
    lines.append("## Per-page detail")
    lines.append("")
    lines.append("| Page | Status | Similarity | Lines (run1 / run2) | URL match |")
    lines.append("|---|---|---|---|---|")
    for name, r in report.items():
        if r.get("status") == "ok":
            url_match = "✓" if r["url_run1"] == r["url_run2"] else "✗"
            lines.append(
                f"| {name} | ok | {r['similarity']:.4f} | "
                f"{r['lines_run1']} / {r['lines_run2']} | {url_match} |"
            )
        else:
            lines.append(f"| {name} | {r.get('status')} | — | — | — |")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {output_path}")


async def main():
    run1_dir = OUTPUT_DIR / "run1"
    run2_dir = OUTPUT_DIR / "run2"
    print("=" * 60)
    print("V0.1 — AXTree Collection Sanity")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Storage state: {STORAGE_STATE} (exists: {STORAGE_STATE.exists()})")
    print(f"Output: {OUTPUT_DIR}")
    print()
    await collect_run("run1", run1_dir)
    print()
    await collect_run("run2", run2_dir)
    print()
    print("=" * 60)
    print("Comparing run1 vs run2...")
    report = compare_runs(run1_dir, run2_dir)
    write_report(report, OUTPUT_DIR / "diff_report.md")


if __name__ == "__main__":
    asyncio.run(main())
