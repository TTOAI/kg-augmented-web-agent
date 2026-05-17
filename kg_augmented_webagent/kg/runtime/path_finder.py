"""BFS path finder with 6-stage cascade + progress check.

Given current_class and target_class, return a structured PathResult describing
how the agent can move from current to (or near) target. Uses the class-level
edge graph produced by Stage C.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Optional

#  아래 두 상수는 **GitLab-flavored fallback**으로 남아 있다
# (production 사용은 cascade.yaml에서 로드된 CascadeConfig 필드를 사용).
# 모듈 단독 import (예: extract_family(class_path) 직접 호출) 시 이 값이 쓰임.
#
# Order matters (longest first) so that `_new_form` is stripped before `_form`.
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

VARIANT_SEGMENTS: frozenset[str] = frozenset(
    {"yours", "starred", "all", "trending", "pending", "done"}
)

# Trust ordering for tie-break: higher trust searched first.
_TRUST_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3, "unknown": 3}


@dataclass(frozen=True)
class CascadeConfig:
    """Site-configurable cascade parameters.

    config/sites/<site>/cascade.yaml에서 로드되어 `build_kg_session()`을
    거쳐 KGSession.cascade_config로 주입된다.

    - scope_entries: {scope: entry_class} cascade stage 3 target
    - hub: cascade stage 4 fallback
    - variant_segments: class name variant suffix 집합 (extract_family에서 참조).
      비어 있으면 path_finder 모듈 상수 VARIANT_SEGMENTS로 fallback.
    - family_type_suffixes: class name 타입 suffix tuple (extract_family에서 참조).
      비어 있으면 module 상수 FAMILY_TYPE_SUFFIXES로 fallback.
    """

    scope_entries: dict[str, str]
    hub: str
    variant_segments: frozenset[str] = frozenset()
    family_type_suffixes: tuple[str, ...] = ()


# path_finder.find_path() 의 fallback default. cascade stages 모두 skip → stay_and_explore.
_EMPTY_CASCADE_CONFIG = CascadeConfig(
    scope_entries={}, hub="", variant_segments=frozenset(), family_type_suffixes=(),
)


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


def extract_family(
    class_path: str, config: Optional[CascadeConfig] = None
) -> str:
    """Return family key. Classes in same family share this key.

    variant_segments / family_type_suffixes를 CascadeConfig에서 우선 로드.
    Config가 없거나 해당 필드가 비어 있으면 모듈-수준 fallback 사용
    (GitLab-flavored default).

    Examples:
      scope/thing_list            -> scope/thing
      scope/thing_new_form        -> scope/thing
      scope/other_*               -> scope/other
      scope/thing_list/<variant>  -> scope/thing_list
    """
    variants = (
        config.variant_segments
        if config and config.variant_segments
        else VARIANT_SEGMENTS
    )
    suffixes = (
        config.family_type_suffixes
        if config and config.family_type_suffixes
        else FAMILY_TYPE_SUFFIXES
    )

    parts = class_path.split("/")
    if not parts:
        return class_path
    scope = parts[0]
    # Drop trailing variant segment if present and there is a base before it.
    if len(parts) >= 3 and parts[-1] in variants:
        base = "/".join(parts[1:-1])
    else:
        base = "/".join(parts[1:])
    for suf in suffixes:
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


def _find_family_siblings(
    target: str, all_classes: set[str], config: Optional[CascadeConfig] = None
) -> list[str]:
    family = extract_family(target, config=config)
    return sorted(
        c for c in all_classes
        if c != target and extract_family(c, config=config) == family
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
    for sibling in _find_family_siblings(target, all_classes, config=config):
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
                f"{sibling!r} in family {extract_family(target, config=config)!r}; "
                f"agent may find target via in-page links not captured in KG."
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
