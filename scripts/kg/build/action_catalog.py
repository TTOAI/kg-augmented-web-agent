"""Stage B.2 — Aggregate raw actions into per-class action catalog.

For each class:
  1. Collect all (label, href, tag, role) tuples from samples
  2. Normalize href (full URL → absolute) and classify → target_class
  3. Dedupe by (normalized_label, target_class)
  4. Compute frequency across instances
  5. Separate into:
      - navigation actions (href + target_class known)
      - internal_state actions (href=# or no href)
      - external (other host, skipped)

Output:
  output/validation/stage_b/action_catalog.json
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urljoin, urlparse

from scripts.kg.utils.classify import load_classifier
from scripts.kg.build.crawl import BASE_URL, is_forbidden, is_same_host

IN = Path("output/validation/stage_b/raw_actions_per_class.json")
OUT = Path("output/validation/stage_b/action_catalog.json")
REPORT = Path("docs/validation/stage_b_action_catalog_report.md")


def normalize_label(label: str) -> str:
    """Trim + collapse whitespace + lowercase for dedup."""
    return re.sub(r"\s+", " ", label.strip())[:80]


def resolve_href(href: str | None, base_url: str) -> str | None:
    """Resolve relative → absolute URL. Return None for javascript:/mailto:/fragment."""
    if not href:
        return None
    href = href.strip()
    if href.startswith(("javascript:", "mailto:", "data:")):
        return None
    if href.startswith("#"):
        return None
    try:
        absolute = urljoin(base_url, href)
        if not is_same_host(absolute):
            return None
        return absolute
    except Exception:
        return None


def main():
    raw = json.loads(IN.read_text(encoding="utf-8"))
    classify = load_classifier()
    print(f"Classes in raw: {len(raw)}")

    catalog: dict[str, dict] = {}
    total_nav_actions = 0
    total_dedup_saved = 0

    for cls, data in raw.items():
        instances = data["instances"]
        n_instances = len(instances)

        # Aggregate: (norm_label, target_class) -> stats
        nav_actions: dict[tuple[str, str | None], dict] = {}
        internal_actions: dict[str, dict] = {}  # by norm_label
        raw_count = 0

        for inst in instances:
            base = inst["url"]
            seen_this_instance: set[tuple[str, str]] = set()
            for a in inst.get("actions", []):
                if "error" in a:
                    continue
                raw_count += 1
                label = normalize_label(a.get("label") or "")
                if not label:
                    continue
                href = a.get("href")
                absolute = resolve_href(href, base)

                if absolute and not is_forbidden(absolute):
                    # Navigation action
                    try:
                        target = classify(absolute)
                    except Exception:
                        target = None
                    key = (label, target or "")
                    if key in seen_this_instance:
                        continue
                    seen_this_instance.add(key)

                    if key not in nav_actions:
                        nav_actions[key] = {
                            "label": label,
                            "target_class": target,
                            "sample_href": absolute,
                            "tag": a.get("tag"),
                            "role": a.get("role"),
                            "instance_freq": 0,
                            "self_edge": target == cls,
                        }
                    nav_actions[key]["instance_freq"] += 1
                else:
                    # Internal state action (button, #, or forbidden)
                    if label in seen_this_instance:
                        continue
                    seen_this_instance.add(label)
                    if label not in internal_actions:
                        internal_actions[label] = {
                            "label": label,
                            "tag": a.get("tag"),
                            "role": a.get("role"),
                            "type": a.get("type"),
                            "instance_freq": 0,
                        }
                    internal_actions[label]["instance_freq"] += 1

        # Sort by instance_freq desc
        nav_list = sorted(nav_actions.values(), key=lambda x: -x["instance_freq"])
        int_list = sorted(internal_actions.values(), key=lambda x: -x["instance_freq"])

        total_nav_actions += len(nav_list)
        total_dedup_saved += raw_count - len(nav_list) - len(int_list)

        #   aggregate form metadata per class.
        # Key: (action_url_template, method) — 같은 endpoint + 같은 method는 1개 form.
        # 첫 관측 instance의 fields를 기준으로 저장 (MUTATE form은 보통 동일).
        forms_by_key: dict[tuple[str, str], dict] = {}
        for inst in instances:
            instance_forms = inst.get("forms") or []
            for form in instance_forms:
                if not isinstance(form, dict):
                    continue
                action = form.get("action") or ""
                method = (form.get("method") or "GET").upper()
                # GET forms with search-like semantics → internal, not MUTATE shortcut
                # keep only non-GET (POST/PATCH/PUT/DELETE) for shortcut purposes
                if method == "GET":
                    continue
                key = (action, method)
                if key in forms_by_key:
                    forms_by_key[key]["instance_freq"] += 1
                    continue
                fields = form.get("fields") or []
                forms_by_key[key] = {
                    "action_url": action,
                    "method": method,
                    "submit_label": (form.get("submit_label") or "")[:60],
                    "fields": fields[:30],  # cap
                    "instance_freq": 1,
                }
        form_list = sorted(forms_by_key.values(), key=lambda x: -x["instance_freq"])

        # Aggregate filter_controls (dropdown/menu enumerations) per class.
        # Dedup by label; union options across instances; infer URL param when
        # any observed option href contains a ?param=value.
        filters_by_label: dict[str, dict] = {}
        for inst in instances:
            for fc in inst.get("filter_controls") or []:
                if not isinstance(fc, dict):
                    continue
                label = normalize_label(fc.get("label") or "")
                if not label:
                    continue
                entry = filters_by_label.setdefault(label, {
                    "label": label,
                    "param": fc.get("param") or "",
                    "options": [],
                    "instance_freq": 0,
                })
                entry["instance_freq"] += 1
                seen_values = {o.get("value") or o.get("name") for o in entry["options"]}
                for opt in fc.get("options") or []:
                    name = (opt.get("name") or "").strip()
                    value = opt.get("value") or ""
                    href = opt.get("href") or ""
                    if not name and not value:
                        continue
                    key_val = value or name
                    if key_val in seen_values:
                        continue
                    seen_values.add(key_val)
                    entry["options"].append({
                        "name": name[:80],
                        "value": (value or "")[:80],
                        "href": href[:200] if href else "",
                    })
                # Infer param from href of first option if not yet known.
                if not entry["param"]:
                    for opt in fc.get("options") or []:
                        href = opt.get("href") or ""
                        if "?" in href:
                            qs = href.split("?", 1)[1]
                            first = qs.split("&", 1)[0]
                            if "=" in first:
                                entry["param"] = first.split("=", 1)[0]
                                break
        # cap options per filter
        for entry in filters_by_label.values():
            entry["options"] = entry["options"][:30]
        filter_list = sorted(filters_by_label.values(), key=lambda x: -x["instance_freq"])

        # filter_categories / modal_structures captured at class level
        # (not per-instance) — class is a leaf node, UI generalizes.
        filter_categories = data.get("filter_categories") or []
        modal_structures = data.get("modal_structures") or []

        catalog[cls] = {
            "instance_count": n_instances,
            "raw_action_count": raw_count,
            "navigation_actions": nav_list,
            "internal_actions": int_list,
            "forms": form_list,
            "filter_controls": filter_list,
            "filter_categories": filter_categories,
            "modal_structures": modal_structures,
        }

    # Compute aggregate stats
    classes_with_nav = sum(1 for c in catalog.values() if c["navigation_actions"])
    unresolved_target = sum(
        1
        for c in catalog.values()
        for a in c["navigation_actions"]
        if a["target_class"] is None
    )
    total_edges = sum(len(c["navigation_actions"]) for c in catalog.values())
    self_edges = sum(
        1 for c in catalog.values() for a in c["navigation_actions"] if a["self_edge"]
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "summary": {
            "classes": len(catalog),
            "classes_with_nav_actions": classes_with_nav,
            "total_navigation_actions": total_edges,
            "unresolved_target_class": unresolved_target,
            "self_edges": self_edges,
            "raw_actions": sum(c["raw_action_count"] for c in catalog.values()),
        },
        "catalog": catalog,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {OUT}")

    # Report
    lines = [
        "# Stage B — Action catalog report",
        "",
        "**Date**: 2026-04-21",
        "",
        "## Summary",
        "",
        f"- Classes processed: {len(catalog)}",
        f"- Classes with navigation actions: {classes_with_nav}",
        f"- Total navigation actions (after dedup): {total_edges}",
        f"- Unresolved target class (href 있지만 rule 미매칭): {unresolved_target}",
        f"- Self-edges (action stays in same class): {self_edges}",
        f"- Raw actions total: {sum(c['raw_action_count'] for c in catalog.values())}",
        "",
        "## Class별 action 요약 (top 20 by nav action count)",
        "",
        "| class | instances | nav actions | internal actions | unresolved |",
        "|---|---:|---:|---:|---:|",
    ]
    rows = []
    for cls, c in catalog.items():
        unr = sum(1 for a in c["navigation_actions"] if a["target_class"] is None)
        rows.append((cls, c["instance_count"], len(c["navigation_actions"]), len(c["internal_actions"]), unr))
    rows.sort(key=lambda x: -x[2])
    for cls, ni, nn, nint, unr in rows[:20]:
        lines.append(f"| `{cls}` | {ni} | {nn} | {nint} | {unr} |")
    lines.append("")
    lines.append("## Example — project/issue_list navigation actions")
    lines.append("")
    if "project/issue_list" in catalog:
        actions = catalog["project/issue_list"]["navigation_actions"][:15]
        lines.append("| label | target_class | freq | href |")
        lines.append("|---|---|---:|---|")
        for a in actions:
            lbl = a["label"][:40]
            tgt = a["target_class"] or "—"
            href = a["sample_href"].replace(BASE_URL, "")[:60]
            lines.append(f"| {lbl} | `{tgt}` | {a['instance_freq']} | `{href}` |")
    lines.append("")
    lines.append("## Next step (Stage C)")
    lines.append("")
    lines.append("- Class pair → edge aggregation (예: `project/issue_list` → `project/issue_new_form`)")
    lines.append("- Edge consolidation (majority target class vote)")
    lines.append("- Edge trust (self-validation: 동일 edge가 여러 instance에서 관찰되면 high-trust)")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {REPORT}")
    print()
    print(f"=== Stats ===")
    print(f"Classes with nav actions: {classes_with_nav}/{len(catalog)}")
    print(f"Total nav actions: {total_edges}")
    print(f"Unresolved: {unresolved_target}")
    print(f"Self-edges: {self_edges}")


if __name__ == "__main__":
    main()
