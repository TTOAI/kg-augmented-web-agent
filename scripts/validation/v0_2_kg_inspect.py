"""V0.2 — Frozen KG structure inventory.

Purpose: 현 Frozen KG (2026-04-16T16-46-55Z.json)의 구성요소와 분포 정량화.
Output: docs/validation/V0_2_kg_inventory.md
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

FROZEN_KG = Path("config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json")
OUTPUT_MD = Path("docs/validation/V0_2_kg_inventory.md")


def main():
    print(f"Loading {FROZEN_KG}...")
    data = json.loads(FROZEN_KG.read_text(encoding="utf-8"))

    # Top-level keys
    keys = list(data.keys())

    # State patterns (list)
    sps_list = data.get("state_patterns", [])
    sps = {sp["id"]: sp for sp in sps_list}
    sp_ids = list(sps.keys())
    sp_sources = Counter(sp.get("source", "?") for sp in sps_list)
    sp_trusts = Counter(sp.get("url_template_trust", "?") for sp in sps_list)
    sp_path_params_counts = Counter(len(sp.get("path_params", {})) for sp in sps_list)
    sp_query_params_counts = Counter(len(sp.get("identity_query_params") or []) for sp in sps_list)

    # InfoTypes (list)
    infos_list = data.get("infotypes", [])
    infos = {info["name"]: info for info in infos_list}
    info_names = list(infos.keys())
    info_sources = Counter(info.get("source", "?") for info in infos_list)
    info_trusts = Counter(info.get("trust_label", "?") for info in infos_list)
    info_realize_counts = Counter(len(info.get("realizes", [])) for info in infos_list)
    info_req_binding_counts = Counter(len(info.get("required_bindings", [])) for info in infos_list)
    info_categories = Counter(info.get("category") or "None" for info in infos_list)

    # Actions (list)
    actions_list = data.get("actions", [])
    actions = {a["name"]: a for a in actions_list}
    action_ids = list(actions.keys())
    action_sources = Counter(a.get("source", "?") for a in actions_list)
    # Categorize action id prefix
    action_prefixes = Counter()
    for aid in action_ids:
        if ":" in aid:
            prefix = aid.split(":", 2)[0] + ":" + (aid.split(":", 2)[1] if aid.count(":") >= 2 else "")
            prefix = ":".join(aid.split(":")[:2])
            action_prefixes[prefix] += 1
        else:
            action_prefixes["(no prefix)"] += 1

    # LeadsToEdges
    edges = data.get("leads_to_edges", [])
    edge_trusts = Counter(e.get("trust", "?") for e in edges)
    edge_sources = Counter(e.get("source", "?") for e in edges)
    # Unique source-target pairs
    edge_actions = Counter()
    for e in edges:
        aname = e.get("action_name", "")
        if aname.startswith("crawl:link:"):
            edge_actions["crawl:link"] += 1
        elif aname.startswith("crawl:form:"):
            edge_actions["crawl:form"] += 1
        else:
            edge_actions[aname.split(":")[0] if ":" in aname else aname] += 1

    # RealizesEdges (flat list + via InfoType.realizes)
    flat_realizes = data.get("realizes_edges", [])
    info_realize_total = sum(len(info.get("realizes", [])) for info in infos.values())

    # Source mix
    source_mix = data.get("source_mix", {})

    # Build report
    lines = []
    lines.append("# V0.2 — Frozen KG Structure Inventory\n")
    lines.append("**Date**: 2026-04-19")
    lines.append("**Status**: Complete")
    lines.append("")
    lines.append("## Question")
    lines.append("현 Frozen KG의 StatePattern / Action / LeadsToEdge / InfoType / RealizesEdge 분포와 품질은?")
    lines.append("")
    lines.append("## KG metadata")
    lines.append(f"- Path: `{FROZEN_KG}`")
    lines.append(f"- File size: {FROZEN_KG.stat().st_size / 1024 / 1024:.1f} MB")
    lines.append(f"- build_timestamp: `{data.get('build_timestamp')}`")
    lines.append(f"- git_rev: `{data.get('git_rev')}`")
    lines.append(f"- builder_version: `{data.get('builder_version')}`")
    lines.append(f"- site: `{data.get('site')}`")
    lines.append(f"- Top-level keys: {keys}")
    lines.append("")
    lines.append("## Source Mix (from KG metadata)")
    for k, v in source_mix.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    # StatePatterns
    lines.append("## StatePatterns")
    lines.append(f"- **Total**: {len(sp_ids)}")
    lines.append("")
    lines.append("### Source distribution")
    for k, v in sp_sources.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Trust distribution")
    for k, v in sp_trusts.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### path_params count distribution")
    for k in sorted(sp_path_params_counts.keys()):
        lines.append(f"- {k} params: {sp_path_params_counts[k]} patterns")
    lines.append("")
    lines.append("### identity_query_params count distribution")
    for k in sorted(sp_query_params_counts.keys()):
        lines.append(f"- {k} query params: {sp_query_params_counts[k]} patterns")
    lines.append("")
    lines.append("### Sample StatePatterns (first 10 by id)")
    sample_sps = sorted(sps.items())[:10]
    lines.append("")
    lines.append("| id | url_pattern | path_params | query_params | source | trust |")
    lines.append("|---|---|---|---|---|---|")
    for sp_id, sp in sample_sps:
        url_pat = sp.get("url_template") or sp.get("url_pattern") or sp.get("path_pattern") or "?"
        pp = ",".join((sp.get("path_params") or {}).keys())
        qps = sp.get("identity_query_params") or []
        qp = ",".join(q.get("name", "?") if isinstance(q, dict) else str(q) for q in qps)
        lines.append(
            f"| `{sp_id[:40]}` | `{url_pat[:40]}` | {pp[:30]} | {qp[:20]} | "
            f"{sp.get('source','?')} | {sp.get('url_template_trust','?')} |"
        )
    lines.append("")

    # InfoTypes
    lines.append("## InfoTypes")
    lines.append(f"- **Total**: {len(info_names)}")
    lines.append("")
    lines.append("### Source distribution")
    for k, v in info_sources.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Trust label distribution")
    for k, v in info_trusts.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Category distribution")
    for k, v in info_categories.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### realizes count distribution (# of StatePatterns each InfoType maps to)")
    for k in sorted(info_realize_counts.keys()):
        lines.append(f"- {k} realizes: {info_realize_counts[k]} infotypes")
    lines.append("")
    lines.append("### Complete InfoType list")
    lines.append("")
    lines.append("| name | description | required_bindings | realizes | category |")
    lines.append("|---|---|---|---|---|")
    for name in sorted(info_names):
        info = infos[name]
        desc = (info.get("description") or "").replace("\n", " ")[:80]
        req = ",".join(info.get("required_bindings", []))
        realize_n = len(info.get("realizes", []))
        cat = info.get("category") or "None"
        lines.append(f"| `{name}` | {desc} | {req[:30]} | {realize_n} | {cat} |")
    lines.append("")

    # Actions
    lines.append("## Actions")
    lines.append(f"- **Total**: {len(action_ids)}")
    lines.append("")
    lines.append("### Source distribution")
    for k, v in action_sources.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Prefix distribution (action id)")
    for k, v in action_prefixes.most_common(20):
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("### Sample Actions (first 10)")
    sample_actions = sorted(actions.items())[:10]
    lines.append("")
    lines.append("| id | description | source |")
    lines.append("|---|---|---|")
    for aid, a in sample_actions:
        desc = (a.get("description") or "").replace("\n", " ")[:60]
        lines.append(f"| `{aid[:60]}` | {desc} | {a.get('source','?')} |")
    lines.append("")

    # LeadsToEdges
    lines.append("## LeadsToEdges")
    lines.append(f"- **Total**: {len(edges)}")
    lines.append("")
    lines.append("### Trust distribution")
    for k, v in edge_trusts.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Source distribution")
    for k, v in edge_sources.most_common():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("### Action type distribution in edges")
    for k, v in edge_actions.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("")

    # RealizesEdges — critical issue
    lines.append("## RealizesEdges (CRITICAL)")
    lines.append(f"- Flat `realizes_edges` list: {len(flat_realizes)}")
    lines.append(f"- Total `InfoType.realizes` entries: {info_realize_total}")
    lines.append("")
    if len(flat_realizes) == 0 and info_realize_total > 0:
        lines.append("→ `realizes_edges` top-level list는 **empty**지만 InfoType 내부 `realizes` field에는 총 "
                     f"{info_realize_total}개 매핑이 존재 (InfoType → StatePattern).")
        lines.append("→ `lessons_learned_kg_v2.md §6.2` 기록 확인: realizes_edges=0이라는 표현은 flat list 기준. ")
        lines.append("   실제로는 InfoType catalog 안에 매핑 embedded.")
    elif len(flat_realizes) == 0:
        lines.append("→ **BOTH flat list AND InfoType.realizes both empty**. Class-instance 매핑 부재.")

    lines.append("")
    lines.append("### InfoType.realizes 분포")
    for k in sorted(info_realize_counts.keys()):
        lines.append(f"- {k} realizes: {info_realize_counts[k]} infotypes")
    lines.append("")

    # Implications
    lines.append("## Implications for Original Plan")
    lines.append("")
    lines.append("### 재사용 가능")
    lines.append("- **37 InfoType**: class catalog seed 후보로 재사용 가능")
    lines.append(f"- **{len(edges)} LeadsToEdges**: 기존 transition graph (crawl 기반)")
    lines.append(f"- **{len(actions)} Actions**: widget catalog (crawl 기반)")
    lines.append(f"- **{len(sp_ids)} StatePatterns**: instance-level URL 정보")
    lines.append("")
    lines.append("### 재구축 필요")
    lines.append("- StatePattern이 **URL-level (instance-like)** — class abstraction 없음")
    lines.append("- Class-level layer는 InfoType 위에 새로 구축해야")
    lines.append("- AXTree 기반 widget 정보는 없음 (Action은 crawler의 form/link URL only)")
    lines.append("")
    lines.append("### Class 재구축 시 reuse 전략")
    if info_realize_total > 0:
        lines.append("- InfoType.realizes 매핑이 존재 → class↔instance 초기 매핑으로 활용")
        lines.append("- 추가로 AXTree 기반 검증 필요 (same class의 instance들이 AXTree structure도 유사한지)")
    else:
        lines.append("- InfoType↔StatePattern 매핑이 비어 있음 → Browser Agent가 처음부터 구축해야")
    lines.append("")

    # Next step
    lines.append("## Next step")
    lines.append("- **V1** — 15-20 GitLab 페이지 수동 annotation → class identification rule 도출")
    lines.append("- V1 수행 시 본 inventory의 **37 InfoType**을 candidate class seed로 사용")
    lines.append("- V1 결과와 KG's current class layer (InfoType) 비교 → 얼마나 align되는지 측정")
    lines.append("")

    # Write
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report: {OUTPUT_MD} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
