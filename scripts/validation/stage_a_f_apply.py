"""Stage A.f apply — crawl 결과에 rule 적용 + 분석.

Output:
  output/validation/stage_a_f/classified.json
  docs/validation/stage_a_f_fresh_crawl_report.md
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from scripts.validation.stage_a_classify import load_classifier

CRAWL_PATH = Path("output/validation/stage_a_f/crawled_urls.json")
CLASSIFIED_OUT = Path("output/validation/stage_a_f/classified.json")
REPORT_OUT = Path("docs/validation/stage_a_f_fresh_crawl_report.md")


def extract_namespace(url: str) -> str | None:
    """First path segment as namespace (heuristic for instance variance)."""
    try:
        p = urlparse(url)
        parts = [s for s in p.path.strip("/").split("/") if s]
        if parts and parts[0] not in ("-", "dashboard", "explore", "users", "help",
                                       "search", "snippets", "projects", "groups", "admin"):
            return parts[0]
        return None
    except Exception:
        return None


def main():
    records = json.loads(CRAWL_PATH.read_text(encoding="utf-8"))
    classify = load_classifier()

    ok = [r for r in records if r.get("http_status") == 200]
    bad = [r for r in records if r.get("http_status") != 200]

    classified = []
    for r in ok:
        url = r.get("final_url") or r["url"]
        cls = classify(url)
        classified.append({**r, "final_class": cls})

    matched = [r for r in classified if r["final_class"]]
    unmatched = [r for r in classified if not r["final_class"]]

    total_200 = len(ok)
    coverage = len(matched) / total_200 * 100 if total_200 else 0

    class_counter = Counter(r["final_class"] for r in matched)
    scope_counter = Counter(r["final_class"].split("/")[0] for r in matched)

    namespace_per_class: dict[str, set] = defaultdict(set)
    for r in matched:
        ns = extract_namespace(r.get("final_url") or r["url"])
        if ns:
            namespace_per_class[r["final_class"]].add(ns)

    # Pre-visit vs post-visit classify agreement
    pre_match = sum(1 for r in classified
                    if r.get("predicted_class") == r.get("final_class"))

    CLASSIFIED_OUT.write_text(
        json.dumps(classified, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {CLASSIFIED_OUT}")

    # Report
    lines = []
    lines.append("# Stage A.f — Fresh BFS crawl rule validation")
    lines.append("")
    lines.append("**Date**: 2026-04-21")
    lines.append(f"**Total crawled**: {len(records)}")
    lines.append(f"**HTTP 200**: {total_200}")
    lines.append(f"**Non-200**: {len(bad)}")
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- Matched: **{len(matched)}/{total_200} = {coverage:.1f}%**")
    lines.append(f"- Unmatched: {len(unmatched)}")
    lines.append(f"- Pre-visit classify vs final classify 일치: {pre_match}/{len(classified)}")
    lines.append("")
    lines.append("## Scope 분포")
    lines.append("")
    lines.append("| scope | count |")
    lines.append("|---|---:|")
    for s, n in scope_counter.most_common():
        lines.append(f"| `{s}` | {n} |")
    lines.append("")
    lines.append("## Per-class 분포")
    lines.append("")
    lines.append("| class | instance 수 | unique namespace 수 |")
    lines.append("|---|---:|---:|")
    for c, n in class_counter.most_common():
        ns = len(namespace_per_class.get(c, set()))
        lines.append(f"| `{c}` | {n} | {ns} |")
    lines.append("")
    lines.append("## Instance variance 검증")
    lines.append("")
    multi_ns = {c: ns for c, ns in namespace_per_class.items() if len(ns) >= 2}
    if multi_ns:
        lines.append(f"**Multi-namespace class** ({len(multi_ns)}개) — rule이 여러 project에서 일반화됨:")
        for c, ns in sorted(multi_ns.items(), key=lambda x: -len(x[1])):
            lines.append(f"- `{c}`: {len(ns)} namespaces → {sorted(ns)[:6]}")
    else:
        lines.append("Multi-namespace class 없음 (crawl이 단일 project에 집중되었을 가능성).")
    lines.append("")
    lines.append("## Unmatched URL (rule gap)")
    lines.append("")
    lines.append(f"총 {len(unmatched)}개. 샘플 (최대 40개):")
    lines.append("")
    lines.append("| depth | final_url | title | linked_from |")
    lines.append("|---|---|---|---|")
    for r in unmatched[:40]:
        u = (r.get("final_url") or r["url"]).replace("http://localhost:8023", "")
        t = (r.get("title") or "")[:40]
        lf = (r.get("linked_from") or "").replace("http://localhost:8023", "")[:50]
        lines.append(f"| {r['depth']} | `{u}` | {t} | `{lf}` |")
    lines.append("")
    lines.append("## Non-200 샘플")
    lines.append("")
    lines.append("| http_status | url |")
    lines.append("|---|---|")
    for r in bad[:15]:
        u = (r.get("url") or "").replace("http://localhost:8023", "")
        lines.append(f"| {r.get('http_status')} | `{u}` |")
    lines.append("")
    lines.append("## Gate 검증")
    lines.append("")
    gate_coverage = "✅" if coverage >= 80 else "❌"
    gate_unmatched = "✅" if unmatched else "—"
    gate_multi = "✅" if multi_ns else "❌"
    lines.append(f"- Coverage ≥ 80%: {gate_coverage} ({coverage:.1f}%)")
    lines.append(f"- Unmatched 수집: {gate_unmatched} ({len(unmatched)} URL)")
    lines.append(f"- Multi-namespace class: {gate_multi} ({len(multi_ns)}개)")
    lines.append("")

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {REPORT_OUT}")


if __name__ == "__main__":
    main()
