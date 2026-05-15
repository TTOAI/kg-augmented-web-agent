"""Render PathResult + inference context as advisory hint text.

Design: exact/stay paths use deterministic rule-based templates (0 LLM cost,
consistent wording). Fallback strategies (family_sibling, scope_entry,
hub_fallback) use an LLM to produce a 2-4 line natural explanation because
the "why" deserves contextual wording. LLM results are cached by
(strategy, current, actual_target, inferred_target).
"""
from __future__ import annotations

import logging
import os as _os
import re
from collections import Counter
from typing import Optional

from site_adaptive_webagent.runtime.llm import LLMClient

from .path_finder import PathResult, PathStep

logger = logging.getLogger("agent_runtime")

_HINT_HEADER = "[KG navigation hint — advisory]"


def _weakened_mode() -> bool:
    """Whether KG is in map+signpost (weakened) mode.

    When true, hints suppress URL-parameter recipes and present filter/search
    structure as in-page interaction targets only (click toggle → pick option).
    This avoids agent over-commitment to exact filter URLs that return empty
    results, and preserves KG's role as a knowledge provider rather than an
    auto-pilot URL constructor.

    Implies-by-inclusion: `minimal` mode also suppresses URL-parameter recipes.
    """
    mode = _os.getenv("KG_MODE", "auto").lower()
    return mode in ("weakened", "minimal")


def _minimal_mode() -> bool:
    """Whether KG is in minimal (shortcut + page-surface only) mode.

    When true, in addition to `weakened` suppression, hints also hide:
      - the conceptual navigation-hint framing header
      - current / target / path class names
      - `→ class_name` suffixes on action listings

    The agent receives only: the next-hop action label (or target URL path as
    a shortcut) and the list of buttons / filters visible on the landed page.
    This avoids agent over-analysis caused by exposing structural class
    expectations (e.g., treating a form as a specific typed entity whose
    labels must match).
    """
    return _os.getenv("KG_MODE", "auto").lower() == "minimal"

# Regex for normalizing multi-instance action labels.
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
    original variants so the agent can match against literal page text.
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


# Parametric filter params: value가 entity/label/user/milestone 같은 task-dependent
# 변수면 `<param>` placeholder를 함께 표시해 agent가 task 값으로 치환할 수 있도록 한다.
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

    In default (auto) mode this exposes `path?query` URL recipes so the agent
    can `goto(...)` a filtered state directly. In weakened (map+signpost) mode
    this section is suppressed entirely — the agent should reach the class via
    the base URL and invoke filters through in-page controls, not by
    constructing parameterized URLs.
    """
    if _weakened_mode():
        return ""
    if not filter_templates:
        return ""
    shown = list(filter_templates)[:limit]
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
            href_tail = ""
            if href:
                # path + query만 추출 (protocol/host 제거).
                from urllib.parse import urlparse

                parsed = urlparse(href)
                href_tail = parsed.path
                if parsed.query:
                    href_tail += f"?{parsed.query}"
            # In minimal mode, hide class-name suffixes (→ target_class) to
            # avoid priming the agent with structural expectations. The URL
            # tail alone serves as the shortcut target.
            tgt_part = (
                ""
                if _minimal_mode()
                else (f" → {target}" if target else "")
            )
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

    # Filter controls (enumerated dropdown/menu options) — give the agent the
    # concrete values it can plug into a filter param, so it can either click
    # the toggle and pick the value directly, or jump to `goto(?param=value)`.
    filter_section = _render_filter_controls(actions.get("filter_controls") or [])
    if filter_section:
        if lines:
            lines.append("")
        lines.append(filter_section)

    # Filtered-search categories (3-level expansion: category → operator → value).
    # KG only needs to tell the agent the categories exist + URL params; actual
    # filter values are task-supplied.
    fc_section = _render_filter_categories(actions.get("filter_categories") or [])
    if fc_section:
        if lines:
            lines.append("")
        lines.append(fc_section)

    # Modal structures — dialog-opening triggers + their inner input fields.
    # Values (usernames, emails) are task-supplied; KG only names the structure.
    modal_section = _render_modal_structures(actions.get("modal_structures") or [])
    if modal_section:
        if lines:
            lines.append("")
        lines.append(modal_section)

    # MUTATE form shortcut: off by default — agent의 form URL 해석이 불안정한
    # 환경에서 noise가 됨. 명시적으로 KG_FORM_SHORTCUT=1로 enable.
    if _os.getenv("KG_FORM_SHORTCUT", "0") == "1":
        form_section = _render_form_shortcuts(actions.get("forms") or [])
        if form_section:
            if lines:
                lines.append("")
            lines.append(form_section)

    return "\n".join(lines)


def _render_modal_structures(modals: list[dict], *,
                              max_modals: int = 4,
                              max_inputs: int = 8) -> str:
    """Render dialog-opening interactions and their inner field structure.

    KG records the structural surface only — button that opens it, the
    searchbox/combobox/textbox inside, their aria-label / placeholder, option
    lists for selects. The actual values (usernames, emails, custom text) the
    agent supplies from task context.
    """
    if not modals:
        return ""
    lines: list[str] = [
        "Dialog interactions on this page (click the trigger button to open "
        "the dialog, then fill the listed fields with task-supplied values):"
    ]
    for m in (modals or [])[:max_modals]:
        trigger = (m.get("trigger_label") or "").strip()
        if not trigger:
            continue
        inputs = m.get("inputs") or []
        submits = m.get("submit_labels") or []
        form_action = (m.get("form_action") or "").strip()
        form_method = (m.get("form_method") or "").strip()
        lines.append(f"  - trigger: [{trigger}]")
        for inp in inputs[:max_inputs]:
            role = (inp.get("role") or "").strip()
            label = (inp.get("label") or "").strip()
            placeholder = (inp.get("placeholder") or "").strip()
            has_popup = (inp.get("has_popup") or "").strip()
            autocomplete = (inp.get("autocomplete") or "").strip()
            options = inp.get("options") or []
            desc_parts = [f"role={role}"]
            if label:
                desc_parts.append(f"label={label!r}")
            if placeholder:
                desc_parts.append(f"placeholder={placeholder!r}")
            if has_popup:
                desc_parts.append(f"has_popup={has_popup}")
            if autocomplete:
                desc_parts.append(f"autocomplete={autocomplete}")
            if options:
                opt_head = options[:6]
                extra = f" +{len(options)-6}" if len(options) > 6 else ""
                desc_parts.append(f"options={opt_head}{extra}")
            lines.append(f"      • {', '.join(desc_parts)}")
        if submits:
            lines.append(f"      submit buttons: {submits[:3]}")
        if form_action:
            lines.append(
                f"      form: {form_method or 'POST'} {form_action}"
            )
    return "\n".join(lines) if len(lines) > 1 else ""


def _render_filter_categories(categories: list[dict], *,
                              max_categories: int = 12) -> str:
    """Render recursive filter-search categories as a hint section.

    Exposes TWO equivalent routes to apply a filter so the agent can choose
    whichever matches its current state:
      (A) URL-direct (single `goto` step): append `?param=value` to the
          current URL using the KG-known `param` for this category.
      (B) UI sequence (4 clicks): search/filter input → category menuitem
          → operator menuitem → value (click if listed, type if autocomplete).

    Per-category fields: name, URL param (if configured), operator list, and
    a sample of observed values (existence proof, not full inventory — the
    agent supplies the task-specific value from task context).
    """
    if not categories:
        return ""
    weakened = _weakened_mode()
    if weakened:
        lines: list[str] = [
            "Filter categories on this page — interact with the filter input "
            "on the page: select the desired category, then an operator, then "
            "the value (exact click count varies; some categories have inline "
            "yes/no, others route through a value picker).",
            "Categories (KG-observed — category names and operators are "
            "literal strings the page exposes):",
        ]
    else:
        lines: list[str] = [
            "Filter categories on this page. Two equivalent routes to apply a filter:",
            "  (A) URL-direct: `goto` with `?param=value` appended to current URL.",
            "  (B) UI sequence: interact with the filter input on the page — "
            "select the desired category, then an operator, then the value. "
            "Exact click count varies (some categories have inline yes/no; others "
            "route through a value picker).",
            "Categories (KG-observed — category names and operators below are "
            "literal strings the page exposes):",
        ]
    for c in (categories or [])[:max_categories]:
        name = (c.get("name") or "").strip()
        if not name:
            continue
        param = (c.get("param") or "").strip()
        ops = c.get("operators") or []
        has_vals = bool(c.get("has_values"))
        examples = c.get("example_values") or []
        op_summary = ""
        if ops:
            op_clean = [o.split("\n")[0].strip() for o in ops if o]
            op_summary = f" operators=[{', '.join(op_clean[:3])}]"
        # Suppress URL param name in weakened mode — it encourages URL recipe
        # construction and is not needed for in-page interaction.
        param_str = "" if weakened else (f" param=`{param}`" if param else "")
        vals_flag = " (values exist — supply from task)" if has_vals else ""
        lines.append(f"  - {name}:{param_str}{op_summary}{vals_flag}")
        # Design principle: KG는 방향(카테고리·연산자)까지만, 구체값은 agent가 페이지
        # 상호작용으로 직접 찾는다. weakened/minimal에서는 example_values 노출 금지.
        if examples and not weakened:
            lines.append(
                f"      example values seen: "
                f"{', '.join(str(v) for v in examples[:3])}"
            )
    return "\n".join(lines) if len(lines) > 1 else ""


def _render_filter_controls(controls: list[dict], *,
                            max_controls: int = 8,
                            max_options: int = 15) -> str:
    """Render enumerated filter-control entries as an advisory hint section.

    controls: list of {label, param, options:[{name,value,href}], instance_freq}.
    Caps shown controls by instance_freq and options by freq (as-ordered).
    """
    if not controls:
        return ""
    weakened = _weakened_mode()
    top = sorted(controls, key=lambda c: -int(c.get("instance_freq") or 0))[:max_controls]
    if weakened:
        header = (
            "In-page filter controls on this page — click the toggle button "
            "and pick from the options shown:"
        )
    else:
        header = (
            "In-page filter controls on this class (values KG observed; combine "
            "freely with `goto(?param=value)` or click the toggle and pick):"
        )
    lines: list[str] = [header]
    for ctl in top:
        label = (ctl.get("label") or "").strip()
        if not label:
            continue
        param = (ctl.get("param") or "").strip()
        opts = ctl.get("options") or []
        shown = []
        for opt in opts[:max_options]:
            name = (opt.get("name") or opt.get("value") or "").strip()
            if not name:
                continue
            shown.append(name)
        overflow = max(0, len(opts) - len(shown))
        head = f"  - [{label}]"
        # Suppress URL param in weakened mode (keeps focus on in-page action).
        if param and not weakened:
            head += f" → param `{param}`"
        # Design principle: weakened/minimal에서 option 값 리스트는 구체값에 해당해
        # 노출 금지. agent가 토글 클릭 후 페이지에서 직접 옵션을 본다. 단 옵션 *개수*는
        # 방향 정보로 유지 (선택지 규모 = 직접 클릭이 적정한지의 판단 근거).
        if shown:
            if weakened:
                head += f" ({len(shown)}+{overflow} options — click toggle to view)" if overflow else f" ({len(shown)} options — click toggle to view)"
            else:
                overflow_tag = f" …+{overflow}" if overflow else ""
                head += f", options: {shown}{overflow_tag}"
        lines.append(head)
    return "\n".join(lines) if len(lines) > 1 else ""


def _render_form_shortcuts(forms: list[dict], limit: int = 5) -> str:
    """Render form metadata as an advisory MUTATE shortcut section.

      Agent가 form 상호작용을 여러 step으로 수행하는 대신 미리 정의된 form
    endpoint + required params를 보고 한 번에 fill+submit 할 수 있도록 힌트.
    각 form은 action URL + method + submit label + required fields + (select 시)
    options 를 짧게 나열. token budget 관리를 위해 상위 `limit`개 form, form당
    top-N fields만 노출.

    Design principle: weakened/minimal mode에서는 default 값·placeholder·option 값
    리스트 등 *구체값*을 억제하고 form 구조(action, method, field name/type/required)
    만 노출. 구체값은 agent가 페이지 상호작용으로 직접 확인한다.
    """
    if not forms:
        return ""
    weakened = _weakened_mode()
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
            default_part = ""
            placeholder_part = ""
            opt_part = ""
            if not weakened:
                default = fd.get("default_value")
                if default not in (None, ""):
                    default_str = str(default)
                    if len(default_str) > 40:
                        default_str = default_str[:37] + "..."
                    default_part = f" default={default_str!r}"
                placeholder = fd.get("placeholder") or ""
                if placeholder:
                    placeholder_part = f" placeholder={placeholder!r}"
                # Select options (short list)
                options = fd.get("options") or []
                if options:
                    opt_vals = [f"{o.get('value','')}={o.get('label','')}" for o in options[:5]]
                    opt_part = f" options=[{', '.join(opt_vals)}]"
            else:
                # weakened: 옵션 *개수*만 방향으로 노출 (선택지 규모는 구조 정보).
                options = fd.get("options") or []
                if options:
                    opt_part = f" ({len(options)} options)"
            lines.append(
                f"      {name}{req_mark} [{typ}]{sens}{default_part}{placeholder_part}{opt_part}"
            )
        if len(shown_fields) > 12:
            lines.append(f"      ... (+{len(shown_fields) - 12} more fields)")
    return "\n".join(lines)


def _fmt_path_steps(path: list[PathStep]) -> list[str]:
    out: list[str] = []
    minimal = _minimal_mode()
    for i, step in enumerate(path, start=1):
        if minimal:
            out.append(f"  {i}. Click {_fmt_action_labels(step.actions)}")
        else:
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
    minimal = _minimal_mode()
    if minimal:
        # Minimal: no class/target framing, shortcut steps + page surface only.
        lines: list[str] = ["[Page shortcut — advisory]"]
        if path_result.path:
            lines.append("Suggested next steps:")
            lines.extend(_fmt_path_steps(path_result.path))
        else:
            lines.append("(already at the right page — proceed with the task action)")
    else:
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
    if not minimal:
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
    if _minimal_mode():
        lines: list[str] = [
            "[Page shortcut — advisory]",
            "No direct shortcut is recorded for this action.",
            "Best option: explore the current page — look for visible links or "
            "buttons related to the task intent.",
        ]
    else:
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

    def _join(base: str) -> str:
        # cascade fallback 경로에서도 filter_section(cross-class URL recipe
        # shortcut) 유지 — fallback은 cross-class shortcut이 가장 가치 있는 경로.
        parts = [base]
        if actions_section:
            parts.append(actions_section)
        if filter_section:
            parts.append(filter_section)
        return "\n".join(parts)

    # In minimal mode, always use a terse template (never LLM-generated text)
    # to guarantee class names are not leaked into the hint.
    if _minimal_mode():
        base = "[Page shortcut — advisory]"
        bind_line = _fmt_bindings(bindings)
        if bind_line:
            base = f"{base}\n{bind_line}"
        return _join(base)
    if llm is None:
        # No LLM: degrade to a terse template so integration still proceeds.
        base = (
            f"{_HINT_HEADER}\n"
            f"Current: {current}; inferred target: {path_result.inferred_target}\n"
            f"Strategy: {strategy}; routed to {path_result.actual_target}\n"
            f"{path_result.note}"
        )
        return _join(base)
    key = _cache_key(path_result, current)
    if cache is not None and key in cache:
        return _join(cache[key])
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
    return _join(hint)
