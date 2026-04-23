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
import os
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from site_adaptive_webagent.kg.site_plugin import load_site_plugin

RULES = Path("output/validation/rules/class_rules.json")
ANNOTATIONS = Path("output/validation/V1_pages/all_annotated.json")
ACTION_CATALOG = Path("output/validation/stage_b/action_catalog.json")
OUT = Path("output/validation/kg_solution/class_descriptions.json")

MAX_DESC_CHARS = 140
FILTER_TEMPLATE_LIMIT = 10  # per class, top-N by instance_freq

# Phase 3.K — structured description derivation.
#
# Class names follow `<scope>/<resource>[_<suffix>]` convention. Scope kind
# ("user" | "entity" | "admin" | "site" | ...) and the site's entity_noun
# ("project" for GitLab, "forum" for Reddit, etc.) come from the site plugin
# so this script stays site-agnostic. Override via manual annotation in
# `all_annotated.json:user_reason` still populates `description` for backward
# compat.

_LIST_SUFFIXES = {"list", "board", "feed"}
_DETAIL_SUFFIXES = {"detail", "view", "diff", "graph"}
_FORM_SUFFIXES = {"new_form", "edit_form", "form"}

# Scope kinds that share "my X" trigger phrasing.
_USER_SCOPES = frozenset({"user", "user_profile"})
# Scope kinds that share "X in a named <entity>" phrasing.
_ENTITY_SCOPE_SUFFIX = "_entity"  # e.g. "forum_entity" → entity-scoped Reddit class


def _parse_class_name(class_name: str) -> tuple[str, str, str]:
    """Return (scope_key, resource, suffix).

    Example: `dashboard/issue_list` → ('dashboard', 'issue', 'list')
             `project/merge_request_new_form` → ('project', 'merge_request', 'new_form')
             `site/search` → ('site', 'search', '')
    """
    if "/" in class_name:
        scope_key, tail = class_name.split("/", 1)
    else:
        scope_key, tail = "", class_name
    # Strip leading scope if tail still has further path (e.g., project/project_list/yours)
    # Take up to next '/' as the "resource part".
    if "/" in tail:
        tail = tail.split("/", 1)[0]
    # Identify suffix — check longest suffix match first.
    resource = tail
    suffix = ""
    for cand in sorted(_LIST_SUFFIXES | _DETAIL_SUFFIXES | _FORM_SUFFIXES, key=len, reverse=True):
        token = "_" + cand
        if tail.endswith(token) and len(tail) > len(token):
            resource = tail[: -len(token)]
            suffix = cand
            break
    return scope_key, resource, suffix


def _humanize_resource(resource: str) -> str:
    return resource.replace("_", " ")


def _derive_structured(class_name: str, url_template: str | None,
                       query_params: set[str], *, scope_taxonomy: dict[str, str],
                       entity_noun: str,
                       extra_triggers: dict[tuple[str, str], list[str]]) -> dict:
    """Build structured description fields from class name + URL + observed params.

    Site-agnostic: base triggers use only universal first-person phrasing
    ("my X", "my latest X", "my created X"). Site-specific vocabulary is
    injected via `extra_triggers` (plugin-supplied, loaded from
    `config/sites/<site>/class_taxonomy.yaml`) keyed by
    (scope_kind, suffix_kind). `entity_noun` comes from the same config and
    replaces the binding-noun placeholder in role/trigger phrasing.
    """
    scope_key, resource, suffix = _parse_class_name(class_name)
    scope = scope_taxonomy.get(scope_key, scope_key or "site")
    resource_h = _humanize_resource(resource) if resource else class_name

    triggers: list[str] = []
    not_for: list[str] = []
    role_parts: list[str] = []

    is_user_scoped = scope in _USER_SCOPES
    is_entity_scoped = scope.endswith(_ENTITY_SCOPE_SUFFIX) or scope in {
        "project", "group", "forum", "org", "namespace",
    }
    is_admin = scope == "admin"
    is_site = scope == "site"

    def _suffix_kind(sfx: str) -> str:
        if sfx in _LIST_SUFFIXES:
            return "list"
        if sfx in _DETAIL_SUFFIXES:
            return "detail"
        if sfx in _FORM_SUFFIXES:
            return "form"
        return ""

    def _append_site_extras(scope_kind: str, sfx_kind: str) -> None:
        """Append site-plugin-supplied extra triggers with resource substitution."""
        extras = extra_triggers.get((scope_kind, sfx_kind)) or []
        plural = f"{resource_h}s" if resource_h else ""
        for tpl in extras:
            try:
                triggers.append(tpl.format(resource=plural or resource_h))
            except (KeyError, IndexError):
                triggers.append(tpl)

    if suffix in _LIST_SUFFIXES:
        role_parts.append(f"List of {resource_h}s")
        if is_user_scoped:
            role_parts.append("scoped to the current user")
            # Universal triggers only (site-agnostic).
            triggers += [
                f"my {resource_h}s",
                f"my latest {resource_h}",
                f"my created {resource_h}",
                f"first-person reference to the current account's {resource_h}s",
            ]
            _append_site_extras("user", "list")
            not_for += [f"task naming a specific {entity_noun}'s {resource_h}s"]
        elif is_entity_scoped:
            role_parts.append(f"within one specific {entity_noun}")
            triggers += [
                f"{resource_h}s in a named {entity_noun}",
                f"{entity_noun}'s {resource_h} list",
                f"task binding a specific {entity_noun}",
            ]
            _append_site_extras("entity", "list")
            not_for += [f"user-scoped {resource_h}s without a {entity_noun} context"]
        elif is_admin:
            role_parts.append("admin-only, site-wide scope")
            # Universal admin triggers; site-specific vocabulary joins via plugin extras.
            triggers += [f"admin-only {resource_h} listing", f"site-wide {resource_h}s"]
            _append_site_extras("admin", "list")
            not_for += ["non-administrative task"]
        elif is_site:
            role_parts.append("site-wide public listing")
            triggers += [f"global / public {resource_h} listing"]
        else:
            triggers += [f"{resource_h} listing"]
    elif suffix in _DETAIL_SUFFIXES:
        role_parts.append(f"Single {resource_h} page")
        if is_entity_scoped:
            role_parts.append(f"within a {entity_noun}")
            triggers += [
                f"view a specific {resource_h}",
                f"read the {resource_h}'s content/status",
            ]
    elif suffix in _FORM_SUFFIXES:
        if "new" in suffix:
            role_parts.append(f"Form to create a new {resource_h}")
            triggers += [
                f"create a new {resource_h}",
                f"add a {resource_h}",
                f"new {resource_h}",
            ]
        elif "edit" in suffix:
            role_parts.append(f"Form to edit an existing {resource_h}")
            triggers += [f"edit a {resource_h}", f"modify a {resource_h}"]
        else:
            role_parts.append(f"Form for {resource_h}")
    elif resource in {"home", "index", "main", "root"}:
        role_parts.append(f"{scope_key} landing page")
        triggers += [f"home / landing of {scope_key}"]
    else:
        if is_user_scoped:
            role_parts.append(f"User's {resource_h} page")
            triggers += [f"my {resource_h}", f"the current user's {resource_h}"]
        elif is_entity_scoped:
            role_parts.append(f"{entity_noun}'s {resource_h} page")
        elif is_admin:
            role_parts.append(f"Admin {resource_h} page")
        elif resource:
            role_parts.append(f"{scope_key} {resource_h}")

    role = ", ".join(role_parts)
    typical_params = sorted(query_params)
    return {
        "scope": scope,
        "role": role,
        "triggers": triggers,
        "not_for": not_for,
        "typical_query_params": typical_params,
    }


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
    site_name = os.getenv("SITE_NAME", "gitlab")
    plugin = load_site_plugin(site_name)
    scope_taxonomy = getattr(plugin, "scope_taxonomy", {}) or {}
    entity_noun = getattr(plugin, "entity_noun", "container")
    extra_triggers = getattr(plugin, "extra_triggers", {}) or {}
    print(f"[build_class_descriptions] site={site_name} plugin={plugin.site} "
          f"scope_taxonomy={len(scope_taxonomy)} entity_noun={entity_noun!r} "
          f"extra_triggers_keys={list(extra_triggers.keys())}")

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
        # Collect query param names from filter templates + url_template.
        query_params: set[str] = set()
        for ft in filter_templates:
            sig = ft.get("query_signature") or ""
            for p in sig.split(","):
                p = p.strip()
                if p:
                    query_params.add(p)
        if url_template:
            try:
                qs = urlparse(url_template).query
                for k, _ in parse_qsl(qs, keep_blank_values=True):
                    if k:
                        query_params.add(k)
            except Exception:
                pass
        structured = _derive_structured(
            cls, url_template, query_params,
            scope_taxonomy=scope_taxonomy, entity_noun=entity_noun,
            extra_triggers=extra_triggers,
        )
        filter_controls = action_catalog.get(cls, {}).get("filter_controls") or []
        filter_categories = action_catalog.get(cls, {}).get("filter_categories") or []
        entries[cls] = {
            "url_template": url_template,
            "description": description,
            "filter_templates": filter_templates,
            "filter_controls": filter_controls,
            "filter_categories": filter_categories,
            **structured,
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
                "classes_with_scope": sum(1 for e in entries.values() if e.get("scope")),
                "classes_with_triggers": sum(1 for e in entries.values() if e.get("triggers")),
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
    print(f"  with scope: {sum(1 for e in entries.values() if e.get('scope'))}")
    print(f"  with triggers: {sum(1 for e in entries.values() if e.get('triggers'))}")


if __name__ == "__main__":
    main()
