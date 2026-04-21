"""Build per-class 1-line descriptions for target_class inference prompt.

Combines class_rules (URL templates) with V1_pages annotations (user_reason)
to produce a compact `{class: {url_template, description}}` mapping consumed
by `site_adaptive_webagent/kg_solution/class_descriptions.py`.

Input:
  output/validation/rules/class_rules.json
  output/validation/V1_pages/all_annotated.json

Output:
  output/validation/kg_solution/class_descriptions.json
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

RULES = Path("output/validation/rules/class_rules.json")
ANNOTATIONS = Path("output/validation/V1_pages/all_annotated.json")
OUT = Path("output/validation/kg_solution/class_descriptions.json")

MAX_DESC_CHARS = 140


def _shortest_annotation(reasons: list[str]) -> str:
    reasons = [r.strip() for r in reasons if r and r.strip()]
    if not reasons:
        return ""
    reasons.sort(key=len)
    desc = reasons[0]
    if len(desc) > MAX_DESC_CHARS:
        desc = desc[:MAX_DESC_CHARS].rstrip() + "..."
    return desc


def main() -> None:
    rules_data = json.loads(RULES.read_text(encoding="utf-8"))
    rules = {r["class"]: r for r in rules_data["rules"]}

    annotations = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    reasons_by_class: dict[str, list[str]] = defaultdict(list)
    for a in annotations:
        cls = a.get("user_class")
        if not cls:
            continue
        reason = a.get("user_reason") or ""
        if reason:
            reasons_by_class[cls].append(reason)

    all_classes = set(rules.keys()) | set(reasons_by_class.keys())

    entries: dict[str, dict] = {}
    for cls in sorted(all_classes):
        rule = rules.get(cls)
        url_template = rule["url_template"] if rule else None
        description = _shortest_annotation(reasons_by_class.get(cls, []))
        entries[cls] = {
            "url_template": url_template,
            "description": description,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "total_classes": len(entries),
                "classes_with_description": sum(1 for e in entries.values() if e["description"]),
                "classes_with_url": sum(1 for e in entries.values() if e["url_template"]),
                "entries": entries,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Saved: {OUT}")
    print(f"  total_classes: {len(entries)}")
    print(f"  with description: {sum(1 for e in entries.values() if e['description'])}")
    print(f"  with url_template: {sum(1 for e in entries.values() if e['url_template'])}")


if __name__ == "__main__":
    main()
