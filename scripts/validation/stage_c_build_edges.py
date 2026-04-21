"""Stage C — Class-level navigation edge graph 구축.

Input: output/validation/stage_b/action_catalog.json
Output:
  output/validation/stage_c/edge_graph.json
  docs/validation/stage_c_edge_graph_report.md

Edge model:
  source_class --[action_label, action_tag]--> target_class
  metadata: instance_freq (class의 몇 instance에서 관찰), trust (frequency 기반)

Aggregation:
  Per-class catalog의 nav_actions 각각이 하나의 edge 후보.
  (source, target) pair 중복 제거 — action_label 목록으로 병합.
  Self-edges 별도 표시 (filter/sort/within-class).

Graph stats:
  - Total unique edges
  - Out-degree / in-degree 분포
  - Isolated classes (out-degree 0)
  - Unreachable classes (in-degree 0)
  - Strongly connected components (for graph structure)
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

CATALOG = Path("output/validation/stage_b/action_catalog.json")
OUT = Path("output/validation/stage_c/edge_graph.json")
REPORT = Path("docs/validation/stage_c_edge_graph_report.md")


def compute_trust(instance_freq: int, sample_count: int) -> str:
    """High if observed in all instances. Medium if majority. Low if single."""
    if sample_count <= 0:
        return "unknown"
    ratio = instance_freq / sample_count
    if ratio >= 0.99:
        return "high"  # observed in all instances
    if ratio >= 0.5:
        return "medium"
    return "low"


def main():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog = data["catalog"]

    # Edges: (source, target) → metadata
    edges: dict[tuple[str, str], dict] = {}
    self_edges: dict[tuple[str, str], dict] = {}
    no_target_actions: list[dict] = []

    all_classes: set[str] = set(catalog.keys())

    for source, cls_data in catalog.items():
        sample_count = cls_data.get("instance_count", 1)
        for a in cls_data.get("navigation_actions", []):
            target = a.get("target_class")
            if target is None:
                no_target_actions.append({"source": source, **a})
                continue
            all_classes.add(target)
            key = (source, target)
            bucket = self_edges if source == target else edges
            if key not in bucket:
                bucket[key] = {
                    "source": source,
                    "target": target,
                    "actions": [],
                    "trust": None,
                    "self": source == target,
                }
            bucket[key]["actions"].append({
                "label": a["label"],
                "tag": a.get("tag"),
                "role": a.get("role"),
                "instance_freq": a["instance_freq"],
                "sample_href": a.get("sample_href"),
            })

    # Compute trust per edge (max of action freq / sample_count)
    def finalize_edges(e_dict: dict) -> list[dict]:
        out = []
        for (src, tgt), meta in e_dict.items():
            sample = catalog.get(src, {}).get("instance_count", 1)
            max_freq = max(a["instance_freq"] for a in meta["actions"])
            meta["trust"] = compute_trust(max_freq, sample)
            meta["max_instance_freq"] = max_freq
            meta["action_count"] = len(meta["actions"])
            out.append(meta)
        return out

    edge_list = finalize_edges(edges)
    self_edge_list = finalize_edges(self_edges)

    # Per-class stats
    out_degree = defaultdict(int)
    in_degree = defaultdict(int)
    for e in edge_list:
        out_degree[e["source"]] += 1
        in_degree[e["target"]] += 1

    isolated_source = [c for c in all_classes if out_degree[c] == 0 and c in catalog]
    unreachable = [c for c in all_classes if in_degree[c] == 0]

    # Adjacency list for Solution 2 BFS
    adjacency: dict[str, list[dict]] = defaultdict(list)
    reverse_adj: dict[str, list[dict]] = defaultdict(list)
    for e in edge_list:
        adjacency[e["source"]].append({
            "target": e["target"],
            "actions": [a["label"] for a in e["actions"]],
            "trust": e["trust"],
        })
        reverse_adj[e["target"]].append({
            "source": e["source"],
            "actions": [a["label"] for a in e["actions"]],
            "trust": e["trust"],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "summary": {
            "total_classes": len(all_classes),
            "classes_in_catalog": len(catalog),
            "unique_edges": len(edge_list),
            "self_edges": len(self_edge_list),
            "no_target_actions": len(no_target_actions),
            "isolated_source_classes": len(isolated_source),
            "unreachable_classes": len(unreachable),
        },
        "edges": edge_list,
        "self_edges": self_edge_list,
        "no_target_actions": no_target_actions,
        "adjacency": dict(adjacency),
        "reverse_adjacency": dict(reverse_adj),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {OUT}")

    # Report
    lines = [
        "# Stage C — Navigation edge graph report",
        "",
        "**Date**: 2026-04-21",
        "",
        "## Summary",
        "",
        f"- Total classes in graph: {len(all_classes)}",
        f"- Classes in catalog (source-side): {len(catalog)}",
        f"- **Unique edges** (source → target, distinct): **{len(edge_list)}**",
        f"- Self-edges (within-class): {len(self_edge_list)}",
        f"- Actions with unresolved target: {len(no_target_actions)}",
        f"- Isolated source classes (out-degree 0): {len(isolated_source)}",
        f"- Unreachable classes (in-degree 0): {len(unreachable)}",
        "",
        "## Trust distribution",
        "",
    ]
    trust_dist = defaultdict(int)
    for e in edge_list:
        trust_dist[e["trust"]] += 1
    lines.append("| trust | count |")
    lines.append("|---|---:|")
    for t in ("high", "medium", "low", "unknown"):
        lines.append(f"| `{t}` | {trust_dist[t]} |")
    lines.append("")
    lines.append("## Top out-degree classes (hubs)")
    lines.append("")
    lines.append("| class | out-degree | in-degree |")
    lines.append("|---|---:|---:|")
    sorted_out = sorted(all_classes, key=lambda c: -out_degree[c])
    for c in sorted_out[:15]:
        lines.append(f"| `{c}` | {out_degree[c]} | {in_degree[c]} |")
    lines.append("")
    lines.append("## Top in-degree classes (destinations)")
    lines.append("")
    lines.append("| class | in-degree | out-degree |")
    lines.append("|---|---:|---:|")
    sorted_in = sorted(all_classes, key=lambda c: -in_degree[c])
    for c in sorted_in[:15]:
        lines.append(f"| `{c}` | {in_degree[c]} | {out_degree[c]} |")
    lines.append("")
    lines.append("## Isolated source (no out-edges)")
    lines.append("")
    if isolated_source:
        for c in isolated_source[:20]:
            lines.append(f"- `{c}` (instance count: {catalog[c].get('instance_count', '?')})")
    else:
        lines.append("None ✓")
    lines.append("")
    lines.append("## Unreachable classes (no in-edges)")
    lines.append("")
    if unreachable:
        for c in unreachable[:20]:
            lines.append(f"- `{c}` (out-degree: {out_degree.get(c, 0)})")
    else:
        lines.append("None ✓")
    lines.append("")
    lines.append("## Example edges — project/issue_list outgoing")
    lines.append("")
    lines.append("| target | trust | actions |")
    lines.append("|---|---|---|")
    for e in sorted(edge_list, key=lambda x: -x["max_instance_freq"]):
        if e["source"] == "project/issue_list":
            labels = [a["label"][:30] for a in e["actions"][:3]]
            lines.append(f"| `{e['target']}` | `{e['trust']}` | {', '.join(labels)} |")
    lines.append("")
    lines.append("## Next (Solution 2)")
    lines.append("")
    lines.append("- Adjacency list / reverse adjacency 이미 저장됨 (`edge_graph.json`)")
    lines.append("- BFS from (current_class) to (target_class) 가능")
    lines.append("- Trust-weighted path ranking 가능")
    lines.append("- Path → agent hint (URL sequence) 변환은 Solution 2의 별도 단계")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {REPORT}")

    print()
    print("=== Stats ===")
    print(f"Total edges: {len(edge_list)}")
    print(f"Self-edges: {len(self_edge_list)}")
    print(f"Isolated source: {len(isolated_source)}")
    print(f"Unreachable: {len(unreachable)}")
    print(f"Trust: {dict(trust_dist)}")


if __name__ == "__main__":
    main()
