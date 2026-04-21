"""BFS path finder with 6-stage cascade + progress check.

Given current_class and target_class, return a structured PathResult describing
how the agent can move from current to (or near) target. Uses the class-level
edge graph produced by Stage C.

Design decisions: see docs/validation/solution2_design_decisions.md §1, §6.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

# Suffixes used to extract "family" keys. Order matters (longest first) so that
# `_new_form` is stripped before `_form`.
FAMILY_TYPE_SUFFIXES: tuple[str, ...] = (
    "_new_form",
    "_edit_form",
    "_pipelines",
    "_commits",
    "_diff",
    "_feed",
    "_board",
    "_list",
    "_detail",
    "_view",
    "_form",
    "_graph",
    "_search",
)

# Variant segments that appear as third path component (e.g. "yours" in
# "dashboard/project_list/yours").
VARIANT_SEGMENTS: frozenset[str] = frozenset(
    {"yours", "starred", "all", "trending", "pending", "done"}
)

# Trust ordering for tie-break: higher trust searched first.
_TRUST_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3, "unknown": 3}


@dataclass(frozen=True)
class CascadeConfig:
    scope_entries: dict[str, str]
    hub: str


# Phase 3.H Tier 2: 이전 DEFAULT_GITLAB_CONFIG 제거. scope_entries/hub는
# config/sites/<site>/cascade.yaml로 이관되어 `build_kg_session()`에서 로드되고
# KGSession.cascade_config로 주입된다. 이 empty default는 direct `find_path()`
# 호출 시 fail-safe (cascade stages 모두 skip → stay_and_explore) 제공.
_EMPTY_CASCADE_CONFIG = CascadeConfig(scope_entries={}, hub="")


@dataclass
class PathStep:
    source: str
    target: str
    actions: list[str]
    trust: Optional[str]


@dataclass
class PathResult:
    strategy: str
    actual_target: str
    inferred_target: str
    path: Optional[list[PathStep]] = None
    hops: int = 0
    note: str = ""
    progress_checked: bool = False


def extract_family(class_path: str) -> str:
    """Return family key. Classes in same family share this key.

    Examples:
      project/issue_list        -> project/issue
      project/issue_new_form    -> project/issue
      project/merge_request_*   -> project/merge_request
      dashboard/project_list/yours -> dashboard/project_list
    """
    parts = class_path.split("/")
    if not parts:
        return class_path
    scope = parts[0]
    # Drop trailing variant segment if present and there is a base before it.
    if len(parts) >= 3 and parts[-1] in VARIANT_SEGMENTS:
        base = "/".join(parts[1:-1])
    else:
        base = "/".join(parts[1:])
    for suf in FAMILY_TYPE_SUFFIXES:
        if base.endswith(suf):
            base = base[: -len(suf)]
            break
    return f"{scope}/{base}" if base else scope


def _sorted_neighbors(adj: dict, src: str) -> list[dict]:
    """Neighbors ordered by trust (high first)."""
    neighbors = adj.get(src, [])
    return sorted(neighbors, key=lambda e: _TRUST_ORDER.get(e.get("trust"), 3))


def _bfs_to_target(
    adj: dict, start: str, goal: str
) -> Optional[list[PathStep]]:
    """Return shortest path as list of PathStep, or None if unreachable."""
    if start == goal:
        return []
    visited = {start}
    # queue holds (node, predecessor_edge_chain)
    queue: deque[tuple[str, list[PathStep]]] = deque([(start, [])])
    while queue:
        node, chain = queue.popleft()
        for edge in _sorted_neighbors(adj, node):
            tgt = edge["target"]
            if tgt in visited:
                continue
            visited.add(tgt)
            step = PathStep(
                source=node,
                target=tgt,
                actions=list(edge.get("actions", [])),
                trust=edge.get("trust"),
            )
            new_chain = chain + [step]
            if tgt == goal:
                return new_chain
            queue.append((tgt, new_chain))
    return None


def _find_family_siblings(target: str, all_classes: set[str]) -> list[str]:
    family = extract_family(target)
    return sorted(
        c for c in all_classes if c != target and extract_family(c) == family
    )


def find_path(
    adjacency: dict,
    current: str,
    target: str,
    *,
    all_classes: set[str],
    config: CascadeConfig = _EMPTY_CASCADE_CONFIG,
) -> PathResult:
    """Return a PathResult applying the 6-stage cascade.

    Stage order:
      1. exact          — BFS current→target
      2. family_sibling — reachable sibling in target's family
      3. scope_entry    — reachable scope entry for target's scope
      4. hub_fallback   — reachable global hub
      5. stay_and_explore — no cascade candidate reachable (or equal to current)
      6. failed         — input invalid (unknown current or target)

    Progress semantics: if current can reach target via KG, exact BFS finds
    the shortest path and returns. Cascade stages run only when target is in
    a different component from current. In that case, literal graph-distance
    progress (`d_cand < d_cur`) is tautologically false (both are inf).
    Instead, cascade enforces progress *semantically* by stage ordering
    (family → scope → hub): earlier stages are more conceptually related to
    target. Within each stage, the candidate must be reachable from current
    and distinct from current; otherwise the stage is skipped.
    """
    # Stage 6: input validation.
    if current not in all_classes or target not in all_classes:
        return PathResult(
            strategy="failed",
            actual_target=target,
            inferred_target=target,
            note=(
                f"Unknown class in graph: current={current!r} "
                f"known={current in all_classes}, target={target!r} "
                f"known={target in all_classes}"
            ),
        )

    # Stage 1: exact.
    exact_path = _bfs_to_target(adjacency, current, target)
    if exact_path is not None:
        return PathResult(
            strategy="exact",
            actual_target=target,
            inferred_target=target,
            path=exact_path,
            hops=len(exact_path),
        )

    # Stage 2: family sibling — try each reachable sibling.
    for sibling in _find_family_siblings(target, all_classes):
        if sibling == current:
            continue
        sib_path = _bfs_to_target(adjacency, current, sibling)
        if sib_path is None:
            continue
        return PathResult(
            strategy="family_sibling",
            actual_target=sibling,
            inferred_target=target,
            path=sib_path,
            hops=len(sib_path),
            note=(
                f"Exact path to {target!r} unavailable. Routed to sibling "
                f"{sibling!r} in family {extract_family(target)!r}; agent may "
                f"find target via in-page links not captured in KG."
            ),
            progress_checked=True,
        )

    # Stage 3: scope entry.
    scope = target.split("/", 1)[0]
    entry = config.scope_entries.get(scope)
    if entry and entry in all_classes and entry != current:
        entry_path = _bfs_to_target(adjacency, current, entry)
        if entry_path is not None:
            return PathResult(
                strategy="scope_entry",
                actual_target=entry,
                inferred_target=target,
                path=entry_path,
                hops=len(entry_path),
                note=(
                    f"Routed to scope entry {entry!r} (scope {scope!r}); "
                    f"target {target!r} may be reachable from there via "
                    f"in-page exploration."
                ),
                progress_checked=True,
            )

    # Stage 4: hub fallback.
    hub = config.hub
    if hub in all_classes and hub != current:
        hub_path = _bfs_to_target(adjacency, current, hub)
        if hub_path is not None:
            return PathResult(
                strategy="hub_fallback",
                actual_target=hub,
                inferred_target=target,
                path=hub_path,
                hops=len(hub_path),
                note=(
                    f"Routed to global hub {hub!r}; target {target!r} may "
                    f"be approachable from there."
                ),
                progress_checked=True,
            )

    # Stage 5: stay_and_explore — no reachable cascade candidate.
    return PathResult(
        strategy="stay_and_explore",
        actual_target=current,
        inferred_target=target,
        path=None,
        hops=0,
        note=(
            f"No cascade candidate reachable from {current!r} toward target "
            f"{target!r}. Agent should stay and explore locally via visible "
            f"links/buttons."
        ),
        progress_checked=True,
    )
