"""Build per-class 1-line descriptions for target_class inference prompt.

Combines class_rules (URL templates) with V1_pages annotations (user_reason)
to produce a compact `{class: {url_template, description, filter_templates}}`
mapping consumed by `site_adaptive_webagent/kg_solution/class_descriptions.py`.

filter_templates: Phase 3.F β에서 추가. Stage B self-edges의 URL 쿼리 파라미터
패턴을 per-class로 추출해, agent가 Label/status filter 같은 visible UI 상호작용
없이도 `goto(url)` 한 step으로 filter state에 도달하게 한다. 예: state=opened,
state=merged, sort=created_asc 등 observed pattern 열거.

Input:
  output/validation/rules/class_rules.json
  output/validation/V1_pages/all_annotated.json
  output/validation/stage_b/action_catalog.json  (Phase 3.F β)

Output:
  output/validation/kg_solution/class_descriptions.json
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

RULES = Path("output/validation/rules/class_rules.json")
ANNOTATIONS = Path("output/validation/V1_pages/all_annotated.json")
ACTION_CATALOG = Path("output/validation/stage_b/action_catalog.json")
OUT = Path("output/validation/kg_solution/class_descriptions.json")

MAX_DESC_CHARS = 140
FILTER_TEMPLATE_LIMIT = 10  # per class, top-N by instance_freq


def _extract_filter_templates(
    class_name: str, action_entry: dict, url_template: str | None
) -> list[dict]:
    """Extract generalized filter URL templates from a class's self-edge actions.

    Returns list of `{label, query_signature, query_example}` entries. Only
    self-edges with non-empty query string are included (pure path-only self
    edges don't add filter info). Query signature = sorted(param_names) joined
    by '&', used for dedup.
    """
    if not action_entry:
        return []
    seen_sigs: set[tuple] = set()
    out: list[dict] = []
    for a in action_entry.get("navigation_actions", []):
        if not a.get("self_edge"):
            continue
        href = a.get("sample_href") or ""
        if not href:
            continue
        try:
            parsed = urlparse(href)
        except Exception:
            continue
        if not parsed.query:
            continue
        params = parse_qsl(parsed.query, keep_blank_values=True)
        if not params:
            continue
        sig = tuple(sorted(k for k, _ in params))
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        # Generalize path using url_template if available. Fallback: use the
        # observed path with "{namespace}/{project}" guess if looks like that.
        path_tpl = url_template or parsed.path
        query_example = "&".join(f"{k}={v}" for k, v in params)
        label = str(a.get("label") or "").strip()
        out.append({
            "label": label,
            "query_signature": ", ".join(sig),
            "query_example": query_example,
            "path_template": path_tpl,
            "instance_freq": int(a.get("instance_freq") or 0),
        })
    out.sort(key=lambda x: -x["instance_freq"])
    return out[:FILTER_TEMPLATE_LIMIT]


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

    # Phase 3.F β: action_catalog에서 per-class filter URL 템플릿 도출
    try:
        action_catalog = json.loads(ACTION_CATALOG.read_text(encoding="utf-8")).get("catalog", {})
    except Exception:
        action_catalog = {}

    all_classes = set(rules.keys()) | set(reasons_by_class.keys()) | set(action_catalog.keys())

    entries: dict[str, dict] = {}
    for cls in sorted(all_classes):
        rule = rules.get(cls)
        url_template = rule["url_template"] if rule else None
        description = _shortest_annotation(reasons_by_class.get(cls, []))
        filter_templates = _extract_filter_templates(
            cls, action_catalog.get(cls, {}), url_template
        )
        entries[cls] = {
            "url_template": url_template,
            "description": description,
            "filter_templates": filter_templates,
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "total_classes": len(entries),
                "classes_with_description": sum(1 for e in entries.values() if e["description"]),
                "classes_with_url": sum(1 for e in entries.values() if e["url_template"]),
                "classes_with_filter_templates": sum(
                    1 for e in entries.values() if e.get("filter_templates")
                ),
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
    print(f"  with filter_templates: {sum(1 for e in entries.values() if e.get('filter_templates'))}")


if __name__ == "__main__":
    main()
