"""Render PathResult + inference context as advisory hint text.

Design: exact/stay paths use deterministic rule-based templates (0 LLM cost,
consistent wording). Fallback strategies (family_sibling, scope_entry,
hub_fallback) use an LLM to produce a 2-4 line natural explanation because
the "why" deserves contextual wording. LLM results are cached by
(strategy, current, actual_target, inferred_target).

See docs/validation/solution2_design_decisions.md §8.
"""
from __future__ import annotations

import logging
import os as _os
import re
from collections import Counter
from typing import Optional

from site_adaptive_webagent.runtime.llm import LLMClient

from .path_finder import PathResult, PathStep

logger = logging.getLogger("webarena_verified")

_HINT_HEADER = "[KG navigation hint — advisory]"

# Regex for normalizing multi-instance action labels. See solution2_design §7.
# Strips trailing counts (" 5"), user mentions (" @alice"), issue refs ("#42"),
# and runs of whitespace. Preserves the semantic prefix.
_NORMALIZE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\s+#\d+\b"),         # issue / MR reference
    re.compile(r"\s+@\w+"),            # user mention
    re.compile(r"\s+\d+$"),            # trailing count
)


def _normalize_label(label: str) -> str:
    s = label.strip()
    for pat in _NORMALIZE_PATTERNS:
        s = pat.sub("", s)
    return re.sub(r"\s+", " ", s).strip()

_FALLBACK_LLM_SYSTEM = (
    "You write a concise navigation hint for a web agent. The hint is "
    "advisory — the agent can ignore it if the page clearly contradicts. "
    "Write 2-4 short lines explaining what the agent should do, based on "
    "the given strategy and path. No markdown, no code fences."
)


def _fmt_action_labels(actions: list[str]) -> str:
    """Render the edge's action labels.

    Normalizes instance-variable suffixes (counts, user mentions, issue refs),
    picks the most frequent canonical form as primary, and surfaces up to two
    original variants so the agent can match against literal page text. See
    solution2_design §7 for the normalize → canonical → variance-hint flow.
    """
    if not actions:
        return "(unknown action)"
    # Canonical selection: most frequent normalized form wins; ties preserve
    # first-seen order.
    normalized = [_normalize_label(a) for a in actions]
    norm_counts: Counter[str] = Counter(n for n in normalized if n)
    if norm_counts:
        canonical, _ = norm_counts.most_common(1)[0]
    else:
        canonical = actions[0]
    # Surface raw variants (≤ 2) that differ from canonical, for UI matching.
    variants: list[str] = []
    for raw in actions:
        if raw == canonical or raw in variants:
            continue
        variants.append(raw)
        if len(variants) >= 2:
            break
    if not variants:
        return f'"{canonical}"'
    alts = ", ".join(f'"{v}"' for v in variants)
    return f'"{canonical}" (variants on page may include: {alts})'


def _fmt_bindings(bindings: dict[str, str]) -> str:
    if not bindings:
        return ""
    pairs = ", ".join(f"{k}={v}" for k, v in bindings.items())
    return f"Bindings extracted from task: {pairs}"


# Phase 3.J F3: parametric filter params. Value가 entity/label/user/milestone 같은
# task-dependent 변수면 `<param>` placeholder를 함께 표시해 agent가 task 값으로 치환할 수
# 있음을 명시한다. param name → placeholder name 매핑 (site-agnostic naming 기반).
_PARAMETRIC_PARAM_PLACEHOLDERS: dict[str, str] = {
    "label_name[]": "<label>",
    "label_name": "<label>",
    "assignee_username": "<username>",
    "author_username": "<username>",
    "milestone_title": "<milestone>",
    "iteration_title": "<iteration>",
    "search": "<query>",
}


def _annotate_parametric_query(query_example: str) -> str:
    """Given `k1=v1&k2=v2`, return `k1=v1&k2=v2  (substitute <placeholder> for parametric params)`.

    Returns query_example unchanged if no parametric params detected.
    """
    if not query_example or "=" not in query_example:
        return query_example
    found: list[str] = []
    for kv in query_example.split("&"):
        if "=" not in kv:
            continue
        key = kv.split("=", 1)[0]
        if key in _PARAMETRIC_PARAM_PLACEHOLDERS:
            placeholder = _PARAMETRIC_PARAM_PLACEHOLDERS[key]
            found.append(f"{key}={placeholder}")
    if not found:
        return query_example
    return f"{query_example}  (parametric: substitute from task → {', '.join(found)})"


def _render_filter_templates(
    filter_templates: "list | tuple", limit: int = 8
) -> str:
    """Render a class's observed filter URL templates.

    Phase 3.F β: Agent가 UI filter widget을 탐색하지 않고 KG가 제공하는 filter
    URL로 `goto(...)`해 state에 도달할 수 있게 한다. Filter param 조합을 URL에
    직접 구성 → UI dropdown 탐색 우회.

    Phase 3.J F3: param name이 known-parametric (`label_name[]`, `assignee_username`,
    `milestone_title` 등)이면 `<placeholder>` 안내를 같이 표시해 agent가 task에서
    추출한 구체값으로 치환하도록 유도. 예: 관측된 값이 `checklist`여도 task가 "bug"
    요구하면 agent는 `label_name[]=bug`로 치환해 goto.
    """
    if not filter_templates:
        return ""
    shown = list(filter_templates)[:limit]
    # Phase 3.H Tier 2: preamble (header/body/emphasis)은 site prompts.yaml에서 로드
    from site_adaptive_webagent.runtime.prompts import default_prompt_library

    lines: list[str] = list(default_prompt_library().render_filter_template_preamble())
    for ft in shown:
        label = getattr(ft, "label", "") or "(no label)"
        path = getattr(ft, "path_template", "")
        q = getattr(ft, "query_example", "")
        q_annotated = _annotate_parametric_query(q)
        url = f"{path}?{q_annotated}" if path and q_annotated else (path or q_annotated)
        lines.append(f"  - [{label}] {url}")
    return "\n".join(lines)


def _render_class_actions(
    actions: Optional[dict],
    *,
    exclude_labels: Optional[set[str]] = None,
    limit_nav: int = 10,
    limit_int: int = 5,
) -> str:
    """Render a class's action catalog entry as an advisory hint section.

    actions: stage_b catalog entry, shape
        {"navigation_actions": [{"label", "target_class", "sample_href",
                                 "instance_freq", "self_edge", ...}, ...],
         "internal_actions": [{"label", "tag", "instance_freq", ...}, ...]}
    exclude_labels: label set already surfaced in the path steps; skipped here
        to avoid duplication.
    limit_nav/limit_int: top-N by instance_freq.
    """
    if not actions:
        return ""
    exclude = {label for label in (exclude_labels or set()) if label}
    lines: list[str] = []

    nav = actions.get("navigation_actions") or []
    nav_sorted = sorted(
        (a for a in nav if a.get("label") and a["label"] not in exclude),
        key=lambda a: -int(a.get("instance_freq", 0)),
    )[:limit_nav]
    if nav_sorted:
        lines.append("Available navigation on this page (from KG):")
        for a in nav_sorted:
            label = a["label"]
            target = a.get("target_class")
            href = a.get("sample_href")
            # Extract just the path + query for readability.
            href_tail = ""
            if href:
                # Strip protocol/host for brevity.
                from urllib.parse import urlparse

                parsed = urlparse(href)
                href_tail = parsed.path
                if parsed.query:
                    href_tail += f"?{parsed.query}"
            tgt_part = f" → {target}" if target else ""
            href_part = f" [{href_tail}]" if href_tail else ""
            lines.append(f"  - [{label}]{tgt_part}{href_part}")

    internal = actions.get("internal_actions") or []
    internal_sorted = sorted(
        (a for a in internal if a.get("label") and a["label"] not in exclude),
        key=lambda a: -int(a.get("instance_freq", 0)),
    )[:limit_int]
    if internal_sorted:
        lines.append("In-page controls (buttons/dropdowns on this page):")
        for a in internal_sorted:
            label = a["label"]
            tag = a.get("tag") or ""
            role = a.get("role") or ""
            meta_parts = [p for p in (tag, role) if p]
            meta = f" ({', '.join(meta_parts)})" if meta_parts else ""
            lines.append(f"  - [{label}]{meta}")

    # Phase 3.K: MUTATE form shortcut section (disabled by default).
    # 데이터는 action_catalog에 수집되어 있으나 agent hint에는 rendering 안 함.
    # pilot_form 결과 (-4pp overall) 에서 agent가 form URL을 misinterpret하여 오히려
    # 성능 하락 → agent visibility 제거. 데이터는 `actions.get("forms")`로 여전히
    # 접근 가능 (별도 ablation 실험용).
    if _os.getenv("KG_FORM_SHORTCUT", "0") == "1":
        form_section = _render_form_shortcuts(actions.get("forms") or [])
        if form_section:
            if lines:
                lines.append("")
            lines.append(form_section)

    return "\n".join(lines)


def _render_form_shortcuts(forms: list[dict], limit: int = 5) -> str:
    """Render form metadata as an advisory MUTATE shortcut section.

    Phase 3.K: Agent가 form 상호작용을 여러 step으로 수행하는 대신 미리 정의된 form
    endpoint + required params를 보고 한 번에 fill+submit 할 수 있도록 힌트.
    각 form은 action URL + method + submit label + required fields + (select 시)
    options 를 짧게 나열. token budget 관리를 위해 상위 `limit`개 form, form당
    top-N fields만 노출.
    """
    if not forms:
        return ""
    top = sorted(forms, key=lambda f: -int(f.get("instance_freq", 0)))[:limit]
    lines: list[str] = ["Forms on this page (MUTATE shortcut — use `goto(action) + fill + submit`):"]
    for f in top:
        action = f.get("action_url") or "<current_url>"
        method = f.get("method") or "POST"
        submit = f.get("submit_label") or ""
        header = f"  - {method} {action}"
        if submit:
            header += f"  (submit: {submit!r})"
        lines.append(header)
        fields = f.get("fields") or []
        # Filter out trivial fields (hidden without name of interest already excluded earlier)
        # Separate required first, then optional.
        req = [fd for fd in fields if fd.get("required")]
        opt = [fd for fd in fields if not fd.get("required")]
        shown_fields = req + opt
        for fd in shown_fields[:12]:
            name = fd.get("name") or "?"
            typ = fd.get("type") or ""
            req_mark = " *" if fd.get("required") else ""
            sens = " (sensitive)" if fd.get("sensitive") else ""
            default = fd.get("default_value")
            default_part = ""
            if default not in (None, ""):
                default_str = str(default)
                if len(default_str) > 40:
                    default_str = default_str[:37] + "..."
                default_part = f" default={default_str!r}"
            placeholder = fd.get("placeholder") or ""
            placeholder_part = f" placeholder={placeholder!r}" if placeholder else ""
            # Select options (short list)
            options = fd.get("options") or []
            opt_part = ""
            if options:
                opt_vals = [f"{o.get('value','')}={o.get('label','')}" for o in options[:5]]
                opt_part = f" options=[{', '.join(opt_vals)}]"
            lines.append(
                f"      {name}{req_mark} [{typ}]{sens}{default_part}{placeholder_part}{opt_part}"
            )
        if len(shown_fields) > 12:
            lines.append(f"      ... (+{len(shown_fields) - 12} more fields)")
    return "\n".join(lines)


def _fmt_path_steps(path: list[PathStep]) -> list[str]:
    out: list[str] = []
    for i, step in enumerate(path, start=1):
        out.append(
            f"  {i}. Click {_fmt_action_labels(step.actions)} → {step.target}"
        )
    return out


def _path_step_labels(path: Optional[list[PathStep]]) -> set[str]:
    labels: set[str] = set()
    for step in path or []:
        for a in step.actions or []:
            if a:
                labels.add(a)
    return labels


def _template_exact(
    path_result: PathResult,
    current: str,
    bindings: dict[str, str],
    *,
    current_class_actions: Optional[dict] = None,
) -> str:
    assert path_result.path is not None
    lines = [
        _HINT_HEADER,
        f"Current page class: {current}",
        f"Inferred target: {path_result.inferred_target}",
        f"Suggested path ({path_result.hops} hop{'s' if path_result.hops != 1 else ''}):",
    ]
    if path_result.path:
        lines.extend(_fmt_path_steps(path_result.path))
    else:
        lines.append("  (already at target class — proceed with task action)")
    bind_line = _fmt_bindings(bindings)
    if bind_line:
        lines.append(bind_line)
    actions_section = _render_class_actions(
        current_class_actions,
        exclude_labels=_path_step_labels(path_result.path),
    )
    if actions_section:
        lines.append(actions_section)
    lines.append(
        "(Structural suggestion — verify against the observed page.)"
    )
    return "\n".join(lines)


def _template_stay(
    path_result: PathResult,
    current: str,
    bindings: dict[str, str],
    *,
    current_class_actions: Optional[dict] = None,
) -> str:
    lines = [
        _HINT_HEADER,
        f"Current page class: {current}",
        f"Inferred target: {path_result.inferred_target}",
        "No direct path to the target is recorded in the site structure.",
        "Best option: explore the current page — look for visible links or "
        "buttons that relate to the target and follow them.",
    ]
    bind_line = _fmt_bindings(bindings)
    if bind_line:
        lines.append(bind_line)
    actions_section = _render_class_actions(current_class_actions)
    if actions_section:
        lines.append(actions_section)
    return "\n".join(lines)


def _llm_fallback_user_prompt(
    path_result: PathResult, current: str, task: str, bindings: dict[str, str]
) -> str:
    path_summary: list[str]
    if path_result.path:
        path_summary = [
            f"  {i}. {s.source} -[{(s.actions or ['?'])[0]}]-> {s.target}"
            for i, s in enumerate(path_result.path, start=1)
        ]
    else:
        path_summary = ["  (no path steps)"]
    bind_line = _fmt_bindings(bindings) or "(no bindings)"
    return (
        f"Task: {task}\n"
        f"Current page class: {current}\n"
        f"Original target class: {path_result.inferred_target}\n"
        f"Strategy: {path_result.strategy}\n"
        f"Cascade routed to: {path_result.actual_target}\n"
        f"Path:\n" + "\n".join(path_summary) + "\n"
        f"{bind_line}\n"
        f"Explain in 2-4 short lines what the agent should do."
    )


def _cache_key(path_result: PathResult, current: str) -> tuple:
    path_shape = tuple(
        (s.source, s.target) for s in (path_result.path or [])
    )
    return (
        path_result.strategy,
        current,
        path_result.inferred_target,
        path_result.actual_target,
        path_shape,
    )


def generate_hint(
    path_result: PathResult,
    *,
    current: str,
    task: str,
    bindings: Optional[dict[str, str]] = None,
    llm: Optional[LLMClient] = None,
    cache: Optional[dict[tuple, str]] = None,
    current_class_actions: Optional[dict] = None,
    filter_templates: Optional["list | tuple"] = None,
) -> Optional[str]:
    """Return an advisory hint string, or None if no hint applies.

    - exact / stay_and_explore: rule-based template (no LLM).
    - family_sibling / scope_entry / hub_fallback: LLM + cache.
    - failed: None (graceful — agent runs baseline).

    current_class_actions: optional action catalog entry for the current
    class; when provided, a "Available navigation / In-page controls" section
    is appended so the agent can see filter/sort links and same-page buttons.
    """
    bindings = bindings or {}
    strategy = path_result.strategy
    if strategy == "failed":
        return None

    filter_section = _render_filter_templates(filter_templates or [])

    if strategy == "exact":
        hint = _template_exact(
            path_result,
            current,
            bindings,
            current_class_actions=current_class_actions,
        )
        return f"{hint}\n{filter_section}" if filter_section else hint
    if strategy == "stay_and_explore":
        hint = _template_stay(
            path_result,
            current,
            bindings,
            current_class_actions=current_class_actions,
        )
        return f"{hint}\n{filter_section}" if filter_section else hint
    # Fallback strategies: LLM.
    actions_section = _render_class_actions(
        current_class_actions,
        exclude_labels=_path_step_labels(path_result.path),
    )
    if llm is None:
        # No LLM: degrade to a terse template so integration still proceeds.
        base = (
            f"{_HINT_HEADER}\n"
            f"Current: {current}; inferred target: {path_result.inferred_target}\n"
            f"Strategy: {strategy}; routed to {path_result.actual_target}\n"
            f"{path_result.note}"
        )
        return f"{base}\n{actions_section}" if actions_section else base
    key = _cache_key(path_result, current)
    if cache is not None and key in cache:
        cached = cache[key]
        return f"{cached}\n{actions_section}" if actions_section else cached
    user_prompt = _llm_fallback_user_prompt(path_result, current, task, bindings)
    try:
        raw = llm.complete(
            system=_FALLBACK_LLM_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except Exception as exc:
        logger.warning("[KG] hint_generator LLM call failed: %s", exc)
        raw = path_result.note
    hint = f"{_HINT_HEADER}\n{raw.strip()}"
    if cache is not None:
        cache[key] = hint
    return f"{hint}\n{actions_section}" if actions_section else hint
