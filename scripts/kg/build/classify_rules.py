"""Stage A.e — URL → class rule 추출.

Input:
  - output/validation/V1_pages/all_annotated.json (57 annotation)
  - config/sites/gitlab/site_config.yaml (URL normalization rules)
  - config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json (reference templates)

Output:
  - output/validation/rules/class_rules.json
  - docs/validation/stage_a_rules_report.md

Approach:
1. 각 user_class를 독립 rule로 취급 (base_class 병합 안 함)
2. Class instance URL들로부터 path template + path_params 도출
3. 같은 template 공유하는 rule들을 query-variant group으로 사후 병합 (todo_list/pending vs /done)
4. Specificity로 정렬 (literal segment 많을수록 앞)
5. 57 annotation에 역적용해 100% self-validation
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from kg_augmented_webagent.kg.seed.manual_config import load_site_config
from kg_augmented_webagent.kg.site_extras import load_site_crawl, load_site_entities
from kg_augmented_webagent.kg.site_plugin import load_site_plugin
from kg_augmented_webagent.kg.types import IdentityParam, StatePattern
from kg_augmented_webagent.kg.urlnorm import match_pattern

import os

ANNOT_PATH = Path("output/validation/V1_pages/all_annotated.json")
FROZEN_KG_PATH = Path("config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json")
SITE_CONFIG_PATH = Path("config/sites/gitlab/site_config.yaml")
RULES_OUT = Path("output/validation/rules/class_rules.json")
REPORT_OUT = Path("docs/validation/stage_a_rules_report.md")

# site-specific 상수는 config/sites/<site>/*.yaml에서 로드. Site 선택은
# `SITE_NAME` env (default "gitlab") — 대응하는 entities.yaml + crawl.yaml을 읽음.
_SITE_NAME = os.getenv("SITE_NAME", "gitlab")
_SITE_ENTITIES = load_site_entities(_SITE_NAME)
_SITE_CRAWL = load_site_crawl(_SITE_NAME)

BASE_URL = _SITE_CRAWL.base_url

# entity 집합은 entities.yaml에서 로드. 다른 site 적용 시 entities.yaml만 교체.
KNOWN_NAMESPACES: set[str] = set(_SITE_ENTITIES.namespaces)
KNOWN_USERNAMES: set[str] = set(_SITE_ENTITIES.usernames)
ACTION_KEYWORDS: set[str] = set(_SITE_ENTITIES.action_keywords)

# URL template 도출의 site-specific 부분은 `SitePlugin.derive_path_template()`에
# 위임. SITE_NAME에 대응하는 plugin이 로드되며, 없으면 DefaultSitePlugin
# (numeric/SHA만 일반화) fallback.
_SITE_PLUGIN = load_site_plugin(_SITE_NAME)


def normalize_path(url: str) -> str:
    p = urlparse(url)
    return p.path or "/"


def parse_query(url: str) -> dict[str, list[str]]:
    p = urlparse(url)
    return parse_qs(p.query, keep_blank_values=True)


def derive_templates(paths: list[str]) -> list[tuple[str, dict[str, dict]]]:
    """Derive one or more templates from instance paths.

    If paths have 3+ distinct depths → collapse to single {path*} template
      (catch-all for deep hierarchical paths like /help/*).
    Else if paths have 2 different lengths (e.g., /dashboard vs /dashboard/projects)
      → multiple templates (one per length) to match all exactly.
    Else single template.
    """
    from collections import defaultdict
    unique = list(dict.fromkeys(paths))
    if len(unique) == 1:
        return [_derive_from_single(unique[0])]
    by_length: dict[int, list[str]] = defaultdict(list)
    for p in unique:
        seg_count = len([s for s in p.strip("/").split("/") if s])
        by_length[seg_count].append(p)

    # 3+ distinct depths → treat as path_segments catch-all
    if len(by_length) >= 3:
        return [_derive_from_multi(unique)]

    results: list[tuple[str, dict]] = []
    for length, group in by_length.items():
        if len(group) == 1:
            results.append(_derive_from_single(group[0]))
        else:
            results.append(_derive_from_multi(group))
    return results


def _derive_from_single(path: str) -> tuple[str, dict[str, dict]]:
    """Single instance → template + path_params derivation (site-pluggable).

     CDIP protocol 의 site-specific URL scheme 로직을
    `SitePlugin.derive_path_template()` 에 위임한다. 본 함수는 path를
    segment list로 쪼개고 plugin에 넘겨주는 adapter만 담당 — protocol
    skeleton (single URL → template)은 site-agnostic.

    Plugin 선택은 `SITE_NAME` env (default "gitlab") → `load_site_plugin()`.
    Plugin 미존재 시 `DefaultSitePlugin` (numeric/SHA 일반화만) fallback.

    Returns: (template_path, path_params dict)
    """
    segments = path.strip("/").split("/")
    return _SITE_PLUGIN.derive_path_template(segments, entities=_SITE_ENTITIES)


def _derive_from_multi(paths: list[str]) -> tuple[str, dict[str, dict]]:
    """Multiple instances — segments that differ become path params."""
    segmentss = [p.strip("/").split("/") for p in paths]
    max_len = max(len(s) for s in segmentss)
    min_len = min(len(s) for s in segmentss)

    if min_len != max_len:
        # Different lengths — use common prefix only (fallback: trailing path*)
        common_prefix: list[str] = []
        for i in range(min_len):
            vals = {segs[i] for segs in segmentss}
            if len(vals) == 1:
                common_prefix.append(next(iter(vals)))
            else:
                break
        # If prefix is empty and paths are varying root-level, skip (avoid "//{path}" bug)
        if not common_prefix:
            # Fallback: use only leading segment of first path as literal. Not ideal but safe.
            # Actually better: use {path*} only, template "/{path}"
            return "/{path}", {"path": {"type": "path_segments"}}
        template = "/" + "/".join(common_prefix) + "/{path}"
        return template, {"path": {"type": "path_segments"}}

    # Same length: segments that vary become path params
    template_segs: list[str] = []
    params: dict[str, dict] = {}
    used_names: set[str] = set()
    for i in range(max_len):
        vals = {segs[i] for segs in segmentss}
        if len(vals) == 1:
            only_val = next(iter(vals))
            # Generalize known-namespace literal → {namespace} param
            # (all instances happen to share same namespace; rule should still generalize to other namespaces)
            if only_val in KNOWN_NAMESPACES and "namespace" not in used_names:
                template_segs.append("{namespace}")
                params["namespace"] = {"type": "segment"}
                used_names.add("namespace")
            elif only_val in KNOWN_USERNAMES and "username" not in used_names and i == 0:
                template_segs.append("{username}")
                params["username"] = {"type": "segment"}
                used_names.add("username")
            # If previous was {namespace}, current segment is {project} regardless of value
            elif "namespace" in used_names and "project" not in used_names and i == 1:
                template_segs.append("{project}")
                params["project"] = {"type": "segment"}
                used_names.add("project")
            else:
                template_segs.append(only_val)
        else:
            name = _infer_slot_name(vals, used_names, prev_literal=template_segs[-1] if template_segs else None)
            used_names.add(name)
            template_segs.append("{" + name + "}")
            params[name] = {"type": "segment"}
    return "/" + "/".join(template_segs), params


def _infer_slot_name(values: set[str], used: set[str], prev_literal: str | None) -> str:
    all_numeric = all(re.fullmatch(r"\d+", v) for v in values)
    all_sha = all(re.fullmatch(r"[0-9a-f]{8,40}", v) for v in values)
    if all_numeric and "id" not in used:
        return "id"
    if all_sha and "sha" not in used:
        return "sha"
    if prev_literal in ("tree", "commits", "blob") and "branch" not in used:
        return "branch"
    if values & KNOWN_NAMESPACES and "namespace" not in used:
        return "namespace"
    if prev_literal in (None, "") and "namespace" not in used:
        return "namespace"
    if "project" not in used:
        return "project"
    return f"slot_{len(used)}"


def compute_specificity(template: str, path_params: dict) -> int:
    segs = [s for s in template.strip("/").split("/") if s]
    literal_count = sum(1 for s in segs if not s.startswith("{"))
    has_path_segments = any(p.get("type") == "path_segments" for p in path_params.values())
    return literal_count * 10 + len(segs) - (5 if has_path_segments else 0)


def lookup_frozen_template(template: str, frozen_kg: dict) -> str | None:
    for sp in frozen_kg.get("state_patterns", []):
        if sp.get("url_template") == template:
            return sp.get("id")
    return None


def merge_query_variants(rules: list[dict], annotations_by_class: dict) -> list[dict]:
    """Find rules sharing same url_template → merge as query-variants of a base rule."""
    # Group by (template, path_params)
    from collections import defaultdict
    template_groups: dict[str, list[dict]] = defaultdict(list)
    for r in rules:
        key = r["url_template"]  # same template → merge candidate
        template_groups[key].append(r)

    merged: list[dict] = []
    for key, group in template_groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue
        # Multiple rules share same template — check if they're variants of same base
        # Variant = the leaf-most component (scope/.../leaf/variant)
        class_parts = [r["class"].split("/") for r in group]
        # Expect all to share same prefix up to last component
        prefix_len = min(len(p) for p in class_parts) - 1
        shared_prefix = class_parts[0][:prefix_len]
        same_base = all(p[:prefix_len] == shared_prefix for p in class_parts)
        if not same_base or prefix_len == 0:
            # Different bases sharing template — keep separate, warn
            for r in group:
                r["_warning"] = f"template shared with: {[g['class'] for g in group if g is not r]}"
                merged.append(r)
            continue
        # They're query-variants of base = "/".join(shared_prefix)
        base_class = "/".join(shared_prefix)
        # Detect variant query key from instances
        variants_info = {}
        for r in group:
            variant_leaf = r["class"].split("/")[-1]
            variants_info[variant_leaf] = annotations_by_class[r["class"]]
        vq = detect_variant_query(variants_info)
        if vq is None:
            # No query key distinguishes them — keep separate
            for r in group:
                r["_warning"] = f"same template as: {[g['class'] for g in group if g is not r]}, no query differentiator"
                merged.append(r)
            continue
        # Merge into single base rule with variant_queries
        base_rule = {
            "class": base_class,
            "url_template": group[0]["url_template"],
            "path_params": group[0]["path_params"],
            "variant_queries": vq,
            "specificity": group[0]["specificity"],
            "frozen_kg_template_id": group[0].get("frozen_kg_template_id"),
            "source_instances": sum([g["source_instances"] for g in group], []),
            "is_variant_base": True,
            "variant_leaves": [g["class"].split("/")[-1] for g in group],
        }
        merged.append(base_rule)
    return merged


def detect_variant_query(variants_records: dict[str, list[dict]]) -> dict | None:
    """Detect a query key that distinguishes variants.

    Returns {"key": "state", "mapping": {"done": "done", None: "pending"}}
    """
    variant_queries = {v: [parse_query(r["url"]) for r in recs]
                       for v, recs in variants_records.items()}
    all_keys = set()
    for qlist in variant_queries.values():
        for q in qlist:
            all_keys.update(q.keys())

    for key in all_keys:
        mapping: dict = {}
        consistent = True
        for variant, qlist in variant_queries.items():
            values = set()
            for q in qlist:
                vs = q.get(key, [])
                values.add(vs[0] if vs else None)
            if len(values) != 1:
                consistent = False
                break
            val = next(iter(values))
            # Use sentinel string for None to avoid JSON key serialization ambiguity
            mapping[str(val) if val is not None else "__absent__"] = variant
        if consistent and len(mapping) == len(variants_records):
            return {"key": key, "mapping": mapping}
    return None


def build_state_pattern(rule: dict) -> StatePattern:
    idparams = []
    if rule.get("variant_queries"):
        vq = rule["variant_queries"]
        idparams.append(IdentityParam(name=vq["key"], type="string", required=False, default=None))
    return StatePattern(
        id=f"rule:{rule['class']}",
        url_template=rule["url_template"],
        path_params=rule["path_params"],
        identity_query_params=idparams,
    )


def classify_url(url: str, rules: list[dict], site_config) -> str | None:
    for rule in rules:
        pattern = build_state_pattern(rule)
        ok, bindings = match_pattern(url, pattern, site_config)
        if not ok:
            continue
        base_class = rule["class"]
        vq = rule.get("variant_queries")
        if vq:
            key = vq["key"]
            val = bindings.get(key)
            val_key = str(val) if val is not None else "__absent__"
            variant = vq["mapping"].get(val_key) or vq["mapping"].get("__absent__")
            if variant:
                return f"{base_class}/{variant}"
        return base_class
    return None


def main():
    annotations = json.loads(ANNOT_PATH.read_text(encoding="utf-8"))
    frozen_kg = json.loads(FROZEN_KG_PATH.read_text(encoding="utf-8"))
    site_config = load_site_config(SITE_CONFIG_PATH)

    print(f"Loaded {len(annotations)} annotations, Frozen KG: {len(frozen_kg.get('state_patterns', []))} SPs")

    # Group by FULL user_class (no base merging at this step)
    from collections import defaultdict
    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in annotations:
        by_class[r["user_class"]].append(r)

    print(f"Unique user_class: {len(by_class)}")

    # Derive template(s) per class — may produce multiple rules per class
    rules: list[dict] = []
    for cls, records in by_class.items():
        paths = [normalize_path(r["url"]) for r in records]
        templates = derive_templates(paths)
        for template, params in templates:
            spec = compute_specificity(template, params)
            frozen_id = lookup_frozen_template(template, frozen_kg)
            rules.append({
                "class": cls,
                "url_template": template,
                "path_params": params,
                "variant_queries": None,
                "specificity": spec,
                "frozen_kg_template_id": frozen_id,
                "source_instances": [r["name"] for r in records],
                "is_variant_base": False,
            })

    # Post-hoc query-variant merging (rules with same template → merge)
    rules = merge_query_variants(rules, by_class)
    print(f"After query-variant merging: {len(rules)} rules")

    # Sort by specificity (desc)
    rules.sort(key=lambda r: -r["specificity"])

    # Self-validation
    mismatches = []
    for r in annotations:
        predicted = classify_url(r["url"], rules, site_config)
        expected = r["user_class"]
        if predicted != expected:
            mismatches.append({
                "name": r["name"],
                "url": r["url"],
                "expected": expected,
                "predicted": predicted,
            })

    total = len(annotations)
    ok = total - len(mismatches)
    print(f"Self-validation: {ok}/{total} match, {len(mismatches)} mismatch")
    if mismatches:
        print("\nMismatches:")
        for m in mismatches[:15]:
            print(f"  {m['name']}: expected={m['expected']!r} predicted={m['predicted']!r}")
            print(f"    url={m['url']}")

    # Save
    RULES_OUT.parent.mkdir(parents=True, exist_ok=True)
    RULES_OUT.write_text(json.dumps({
        "protocol_version": "0.6",
        "date": "2026-04-21",
        "total_rules": len(rules),
        "self_validation": {"total": total, "match": ok, "mismatch": len(mismatches)},
        "rules": rules,
        "mismatches": mismatches,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRules saved: {RULES_OUT}")

    write_report(rules, mismatches, total, ok)


def write_report(rules, mismatches, total, ok):
    lines = []
    lines.append("# Stage A.e — URL → class rule 추출 결과")
    lines.append("")
    lines.append("**Date**: 2026-04-21")
    lines.append(f"**Total rules**: {len(rules)}")
    lines.append(f"**Self-validation**: {ok}/{total} = {ok/total*100:.1f}%")
    reused = sum(1 for r in rules if r.get("frozen_kg_template_id"))
    lines.append(f"**Frozen KG template 재사용**: {reused}/{len(rules)} rules")
    lines.append("")
    lines.append("## Approach")
    lines.append("")
    lines.append("- 각 user_class를 독립 rule로 취급")
    lines.append("- Instance URL들로부터 template 도출 (varying segment → path param)")
    lines.append("- 같은 template 공유하는 rule들 → query-variant group으로 post-hoc 병합")
    lines.append("- Specificity 정렬 (literal ×10 + 총 segment − path_segments penalty)")
    lines.append("")
    lines.append("## Self-validation")
    lines.append("")
    if mismatches:
        lines.append(f"⚠️ **{len(mismatches)} mismatches**:")
        lines.append("")
        lines.append("| name | expected | predicted |")
        lines.append("|---|---|---|")
        for m in mismatches:
            lines.append(f"| `{m['name']}` | `{m['expected']}` | `{m['predicted']}` |")
    else:
        lines.append("✅ **전부 self-consistent** — 모든 annotation이 rule로 정확히 재분류됨.")
    lines.append("")
    lines.append("## Rules (specificity desc)")
    lines.append("")
    lines.append("| # | class | url_template | path_params | variant_queries | spec | frozen | instances |")
    lines.append("|---|---|---|---|---|---:|---|---:|")
    for i, r in enumerate(rules, 1):
        vq_txt = "—"
        if r["variant_queries"]:
            vq = r["variant_queries"]
            vq_txt = f"key=`{vq['key']}`, {vq['mapping']}"
        pp = ",".join(r["path_params"].keys()) or "—"
        frozen = "✓" if r.get("frozen_kg_template_id") else "—"
        n_inst = len(r["source_instances"])
        warn = f" ⚠️{r.get('_warning','')}" if r.get('_warning') else ''
        lines.append(f"| {i} | **`{r['class']}`**{warn} | `{r['url_template']}` | {pp} | {vq_txt} | {r['specificity']} | {frozen} | {n_inst} |")
    lines.append("")
    lines.append("## 다음 단계")
    lines.append("")
    lines.append("- **Stage A.f**: Rule을 Frozen KG 3,040 StatePattern에 적용")
    lines.append("- **Stage A.f.post**: Coverage, compression ratio, unmatched SP 분석")

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report:      {REPORT_OUT}")


if __name__ == "__main__":
    main()
