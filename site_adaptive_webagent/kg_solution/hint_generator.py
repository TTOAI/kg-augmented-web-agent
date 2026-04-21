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


def _fmt_path_steps(path: list[PathStep]) -> list[str]:
    out: list[str] = []
    for i, step in enumerate(path, start=1):
        out.append(
            f"  {i}. Click {_fmt_action_labels(step.actions)} → {step.target}"
        )
    return out


def _template_exact(
    path_result: PathResult, current: str, bindings: dict[str, str]
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
    lines.append(
        "(Structural suggestion — verify against the observed page.)"
    )
    return "\n".join(lines)


def _template_stay(
    path_result: PathResult, current: str, bindings: dict[str, str]
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
) -> Optional[str]:
    """Return an advisory hint string, or None if no hint applies.

    - exact / stay_and_explore: rule-based template (no LLM).
    - family_sibling / scope_entry / hub_fallback: LLM + cache.
    - failed: None (graceful — agent runs baseline).
    """
    bindings = bindings or {}
    strategy = path_result.strategy
    if strategy == "failed":
        return None
    if strategy == "exact":
        return _template_exact(path_result, current, bindings)
    if strategy == "stay_and_explore":
        return _template_stay(path_result, current, bindings)
    # Fallback strategies: LLM.
    if llm is None:
        # No LLM: degrade to a terse template so integration still proceeds.
        return (
            f"{_HINT_HEADER}\n"
            f"Current: {current}; inferred target: {path_result.inferred_target}\n"
            f"Strategy: {strategy}; routed to {path_result.actual_target}\n"
            f"{path_result.note}"
        )
    key = _cache_key(path_result, current)
    if cache is not None and key in cache:
        return cache[key]
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
    return hint
