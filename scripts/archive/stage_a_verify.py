"""Stage A verify — 57 페이지 action set 실측 + 위험 카테고리별 비교.

Phase 1: 각 scope base(공유 chrome) 측정
Phase 2: 전 57 페이지 action set 측정
Phase 3: 카테고리별 비교
Phase 4: (사용자 상호작용) 판정
Phase 5: annotation 수정 (별도)

Output:
  output/validation/stage_a_verify/scope_bases.json
  output/validation/stage_a_verify/page_actions.json
  docs/validation/stage_a_verify_report.md
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from itertools import combinations
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8023"
STORAGE_STATE = Path("output/validation/.storage_state.json")
ANNOT_PATH = Path("output/validation/V1_pages/all_annotated.json")
OUT_DIR = Path("output/validation/stage_a_verify")
REPORT_MD = Path("docs/validation/stage_a_verify_report.md")

# Representative pages for each scope base (intersection)
SCOPE_BASE_SOURCES = {
    "project":   ["project_main", "project_tree", "project_commits"],
    "dashboard": ["dashboard_home", "dashboard_issues", "dashboard_merge_requests"],
    "account":   ["account_edit", "account_preferences", "account_notifications"],
    "explore":   ["explore_projects", "explore_projects_topics"],
    "user":      ["user_profile", "user_activity"],
    "global":    ["help_page", "new_project_form", "search_page", "global_snippets"],
}

# Categories for Phase 3 comparison
CATEGORY_DETAIL = [
    "project_issue_detail", "project_blob_detail", "project_commit_detail",
    "project_mr_detail", "project_tag_detail",
]
CATEGORY_FORM = [
    "project_issue_new_form", "project_mr_new_form",
    "project_branch_new_form", "project_tag_new_form",
]
CATEGORY_SETTINGS = [
    "project_settings_general", "project_settings_repository", "project_settings_ci_cd",
    "project_settings_integrations", "project_settings_access_tokens",
]
CATEGORY_CI_INFRA = [
    "project_pipelines", "project_pipeline_schedules",
    "project_environments", "project_jobs",
]
CATEGORY_INSTANCE_VARIANCE = [
    ("webring_main", "project_main"),
    ("webring_issues", "project_issues"),
    ("empathy_main", "project_main"),
    ("empathy_merge_requests", "project_merge_requests"),
    ("a11yproject_issues", "project_issues"),
]
CATEGORY_MISC_LIST = [
    "project_branches", "project_tags", "project_boards", "project_wiki",
    "project_labels", "project_milestones", "project_members",
    "project_activity", "project_forks", "project_snippets",
]


ACTION_JS = """() => {
    const els = Array.from(document.querySelectorAll('a, button, [role="button"], [role="tab"]'));
    const out = new Set();
    for (const e of els) {
        if (e.offsetParent === null) continue;
        const label = (e.innerText || e.getAttribute('aria-label') || '').trim().replace(/\\s+/g, ' ');
        if (label && label.length > 0 && label.length < 80) out.add(label);
    }
    return [...out];
}"""


async def get_action_set(page, url_path: str) -> set[str]:
    try:
        await page.goto(BASE_URL + url_path, wait_until="networkidle", timeout=20000)
    except Exception:
        pass
    await page.wait_for_timeout(500)
    actions = await page.evaluate(ACTION_JS)
    return set(actions)


def jaccard(a: set, b: set) -> float:
    u = a | b
    return len(a & b) / len(u) if u else 1.0


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    annotated = json.loads(ANNOT_PATH.read_text(encoding="utf-8"))
    name_to_url = {r["name"]: r["url"].replace(BASE_URL, "") for r in annotated}
    name_to_class = {r["name"]: r["user_class"] for r in annotated}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(storage_state=str(STORAGE_STATE))
        page = await ctx.new_page()

        # ── Phase 1: scope bases ──
        print("=" * 60)
        print("Phase 1: scope bases")
        print("=" * 60)
        scope_bases: dict[str, set] = {}
        for scope, sources in SCOPE_BASE_SOURCES.items():
            sets = []
            for name in sources:
                if name not in name_to_url:
                    continue
                actions = await get_action_set(page, name_to_url[name])
                sets.append(actions)
            scope_bases[scope] = set.intersection(*sets) if sets else set()
            print(f"  {scope:10s}: {len(scope_bases[scope]):3d} shared actions (from {len(sources)} pages)")

        # ── Phase 2: per-page action set (all 57) ──
        print()
        print("=" * 60)
        print(f"Phase 2: per-page action set ({len(annotated)} pages)")
        print("=" * 60)
        page_actions: dict[str, set] = {}
        for i, rec in enumerate(annotated, 1):
            name = rec["name"]
            page_actions[name] = await get_action_set(page, name_to_url[name])
            if i % 10 == 0 or i == len(annotated):
                print(f"  [{i}/{len(annotated)}] done")

        await browser.close()

    # Save raw
    (OUT_DIR / "scope_bases.json").write_text(
        json.dumps({k: sorted(v) for k, v in scope_bases.items()}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUT_DIR / "page_actions.json").write_text(
        json.dumps({k: sorted(v) for k, v in page_actions.items()}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Page-specific = full - scope_base
    def specific(name: str) -> set:
        scope = name_to_class[name].split("/")[0]
        return page_actions[name] - scope_bases.get(scope, set())

    # ── Phase 3: category comparisons ──
    lines = []
    lines.append("# Stage A verify — Action set 실측 결과")
    lines.append("")
    lines.append("**Date**: 2026-04-21")
    lines.append(f"**Total pages measured**: {len(page_actions)}")
    lines.append("")
    lines.append("Broader selector (`a, button, [role=button], [role=tab]`) 기준 page-specific action "
                 "(scope base chrome 제외) 비교.")
    lines.append("")
    lines.append("## Phase 1 — Scope base (공유 chrome 수)")
    lines.append("")
    lines.append("| Scope | 공유 chrome size | Source 페이지 |")
    lines.append("|---|---:|---|")
    for scope, base in scope_bases.items():
        src = ", ".join(SCOPE_BASE_SOURCES[scope])
        lines.append(f"| `{scope}` | {len(base)} | {src} |")
    lines.append("")

    # 3.1 Detail
    lines.append("## 3.1 Detail widgets (5)")
    lines.append("")
    lines.append("5 detail 페이지의 page-specific action 교집합·차이:")
    lines.append("")
    lines.append("| page | specific size | 상위 action 샘플 |")
    lines.append("|---|---:|---|")
    detail_specifics = {n: specific(n) for n in CATEGORY_DETAIL if n in page_actions}
    for n, s in detail_specifics.items():
        sample = sorted(s)[:6]
        lines.append(f"| `{n}` | {len(s)} | {', '.join(sample)} |")
    lines.append("")
    if detail_specifics:
        common = set.intersection(*detail_specifics.values())
        lines.append(f"**Detail 공통**: {len(common)} action — {sorted(common)[:10]}")
        lines.append("")
        lines.append("**Pairwise Jaccard (유사도)**:")
        lines.append("")
        names = list(detail_specifics.keys())
        lines.append("| pair | jaccard | &#124;intersect&#124; / &#124;union&#124; |")
        lines.append("|---|---:|---|")
        for a, b in combinations(names, 2):
            j = jaccard(detail_specifics[a], detail_specifics[b])
            inter = detail_specifics[a] & detail_specifics[b]
            union = detail_specifics[a] | detail_specifics[b]
            lines.append(f"| `{a}` ↔ `{b}` | {j:.2f} | {len(inter)}/{len(union)} |")
        lines.append("")
        lines.append("**판정 가이드**: Jaccard < 0.5면 확실히 다른 class. > 0.8이면 같은 class 또는 variant 가능성.")
        lines.append("")

    # 3.2 Form
    lines.append("## 3.2 Form widgets (4 new_form)")
    lines.append("")
    form_specifics = {n: specific(n) for n in CATEGORY_FORM if n in page_actions}
    for n, s in form_specifics.items():
        sample = sorted(s)[:6]
        lines.append(f"- `{n}` ({len(s)} specific): {', '.join(sample)}")
    lines.append("")
    if form_specifics:
        common = set.intersection(*form_specifics.values())
        lines.append(f"**Form 공통**: {len(common)} — {sorted(common)[:10]}")
        lines.append("")
        names = list(form_specifics.keys())
        lines.append("| pair | jaccard |")
        lines.append("|---|---:|")
        for a, b in combinations(names, 2):
            j = jaccard(form_specifics[a], form_specifics[b])
            lines.append(f"| `{a}` ↔ `{b}` | {j:.2f} |")
        lines.append("")

    # 3.3 Settings (5 — originally flat, verify)
    lines.append("## 3.3 Settings widgets (5, 현재 flat) — 추가 검증")
    lines.append("")
    settings_specifics = {n: specific(n) for n in CATEGORY_SETTINGS if n in page_actions}
    for n, s in settings_specifics.items():
        sample = sorted(s)[:6]
        lines.append(f"- `{n}` ({len(s)} specific): {', '.join(sample)}")
    lines.append("")
    if settings_specifics:
        names = list(settings_specifics.keys())
        lines.append("| pair | jaccard |")
        lines.append("|---|---:|")
        for a, b in combinations(names, 2):
            j = jaccard(settings_specifics[a], settings_specifics[b])
            lines.append(f"| `{a}` ↔ `{b}` | {j:.2f} |")
        lines.append("")

    # 3.4 CI/Infra
    lines.append("## 3.4 CI/Infra lists (4)")
    lines.append("")
    ci_specifics = {n: specific(n) for n in CATEGORY_CI_INFRA if n in page_actions}
    for n, s in ci_specifics.items():
        sample = sorted(s)[:8]
        lines.append(f"- `{n}` ({len(s)} specific): {', '.join(sample)}")
    lines.append("")
    if ci_specifics:
        names = list(ci_specifics.keys())
        lines.append("| pair | jaccard |")
        lines.append("|---|---:|")
        for a, b in combinations(names, 2):
            j = jaccard(ci_specifics[a], ci_specifics[b])
            lines.append(f"| `{a}` ↔ `{b}` | {j:.2f} |")
        lines.append("")

    # 3.5 Instance variance (critical)
    lines.append("## 3.5 Instance variance (5 pairs) — 가장 중요")
    lines.append("")
    lines.append("Rule 일반화의 전제: 같은 class라 주장한 instance끼리 action set이 같아야 함.")
    lines.append("")
    lines.append("| variance | vs base | jaccard | 공통 | variance only | base only |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for var, base in CATEGORY_INSTANCE_VARIANCE:
        if var not in page_actions or base not in page_actions:
            lines.append(f"| `{var}` | `{base}` | — (missing) | — | — | — |")
            continue
        v, b = specific(var), specific(base)
        j = jaccard(v, b)
        lines.append(f"| `{var}` | `{base}` | {j:.2f} | {len(v & b)} | {len(v - b)} | {len(b - v)} |")
    lines.append("")
    lines.append("**판정 가이드**: Jaccard < 0.7이면 instance variance 주장 약해짐. 차이 content 검토 필요.")
    lines.append("")

    # 3.6 Misc lists
    lines.append("## 3.6 Misc lists (10)")
    lines.append("")
    misc_specifics = {n: specific(n) for n in CATEGORY_MISC_LIST if n in page_actions}
    for n, s in misc_specifics.items():
        sample = sorted(s)[:6]
        lines.append(f"- `{n}` ({len(s)} specific): {', '.join(sample)}")
    lines.append("")

    # Overall: write representative jaccard matrix for misc lists to show spread
    if misc_specifics:
        names = list(misc_specifics.keys())
        lines.append("**Pairwise Jaccard (high-level):**")
        lines.append("")
        lines.append("각 misc list가 서로 얼마나 유사/상이한지 (0.0 — 완전 다름, 1.0 — 동일):")
        lines.append("")
        # Compact text instead of full matrix
        high_sim = []
        low_sim = []
        for a, b in combinations(names, 2):
            j = jaccard(misc_specifics[a], misc_specifics[b])
            if j > 0.8:
                high_sim.append((a, b, j))
            elif j < 0.2:
                low_sim.append((a, b, j))
        lines.append(f"- **유사도 > 0.8 (같은 class 의심)**: {len(high_sim)} pair")
        for a, b, j in high_sim[:10]:
            lines.append(f"  - `{a}` ↔ `{b}`: {j:.2f}")
        lines.append(f"- **유사도 < 0.2 (확실히 다름)**: {len(low_sim)} pair")
        lines.append("")

    # 3.7 Cross-scope widget check (global singletons)
    lines.append("## 3.7 Cross-scope widget 비교")
    lines.append("")
    cross_pairs = [
        ("global_snippets", "project_snippets"),
        ("user_activity", "project_activity"),
    ]
    lines.append("| cross pair | jaccard | 공통 | 설명 |")
    lines.append("|---|---:|---:|---|")
    for a, b in cross_pairs:
        if a not in page_actions or b not in page_actions:
            continue
        sa, sb = specific(a), specific(b)
        j = jaccard(sa, sb)
        lines.append(f"| `{a}` ↔ `{b}` | {j:.2f} | {len(sa & sb)} | 같은 widget이 다른 scope에 있는지 검증 |")
    lines.append("")

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print()
    print(f"Report: {REPORT_MD}")
    print(f"Raw:    {OUT_DIR / 'page_actions.json'}")


if __name__ == "__main__":
    asyncio.run(main())
