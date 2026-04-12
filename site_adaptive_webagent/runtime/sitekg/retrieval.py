"""Flat graph BFS 기반 KG context 생성.

모든 노드 (PageNode + WidgetNode)를 동등하게 취급하고,
undirected graph로 BFS를 수행하여 N hop 이내의 노드를 선택한다.

Edge 종류 (모두 1 hop, undirected):
- page ↔ widget: implicit contains (page_key)
- page ↔ page: NavigationEdge
- widget → page: NavigationEdge.trigger_widget_key
- widget ↔ widget: InteractionEdge
"""
from __future__ import annotations

from collections import deque

from .page_matcher import match_page_node
from .types import SiteKG, WidgetNode


def build_kg_context(current_url: str, sitekg: SiteKG, *, max_hops: int = 2) -> str:
    """현재 URL에서 N hop 이내의 노드 정보를 KG context 문자열로 포맷."""
    page_result = match_page_node(current_url, sitekg)
    if isinstance(page_result, str):  # "UNRESOLVED"
        return ""

    current_page_key = page_result.page_key

    # flat graph BFS — page + widget 모두 노드로
    reachable = _bfs_flat(current_page_key, sitekg, max_hops)

    sections: list[str] = []
    sections.append(f"\n## KG Context (current: {current_page_key}, {max_hops} hop)")

    # 현재 page의 widgets (0-1 hop)
    current_widgets = [
        w for w in sitekg.get_widgets_for_page(current_page_key)
        if w.widget_key in reachable
    ]
    if current_widgets:
        widget_lines = [_format_widget(w) for w in current_widgets]
        sections.append("Widgets on this page:\n" + "\n".join(widget_lines))

    # Reachable pages (1+ hop, current 제외)
    reachable_pages: list[str] = []
    for pk in sorted(reachable):
        if pk == current_page_key:
            continue
        if pk not in sitekg.page_keys():
            continue
        dist = reachable[pk]
        page_node = sitekg.get_page_node(pk)
        if not page_node:
            continue
        widgets = [w for w in sitekg.get_widgets_for_page(pk) if w.widget_key in reachable]
        url_hint = page_node.url_patterns[0] if page_node.url_patterns else ""

        line = f"  → {pk} ({len(widgets)} widgets, {dist} hop"
        if url_hint:
            line += f", url: {url_hint}"
        line += ")"

        # side_effects 있는 widget만 요약
        notable = [w for w in widgets if w.side_effects]
        for w in notable[:3]:
            line += f"\n      ● {w.widget_key} → {', '.join(w.side_effects)}"

        reachable_pages.append(line)

    if reachable_pages:
        sections.append("Reachable pages:\n" + "\n".join(reachable_pages))

    return "\n".join(sections)


def _format_widget(widget: WidgetNode) -> str:
    """WidgetNode를 LLM 가독 형태로 포맷."""
    line = f"  ● {widget.widget_key} [{widget.locator_strategy}: {widget.locator_value}]"
    if widget.side_effects:
        line += f"\n      side_effects: {widget.side_effects}"
    if widget.visibility_condition:
        line += f"\n      visible if: {widget.visibility_condition}"
    return line


def _bfs_flat(
    start_node: str, sitekg: SiteKG, max_hops: int,
) -> dict[str, int]:
    """Flat graph BFS — page와 widget을 동등한 노드로 취급.

    Returns: node_key → distance 매핑 (page_key 또는 widget_key).
    """
    distances: dict[str, int] = {start_node: 0}
    queue: deque[tuple[str, int]] = deque([(start_node, 0)])

    # 빠른 lookup을 위한 인덱스
    page_key_set = sitekg.page_keys()
    widget_by_key: dict[str, WidgetNode] = {w.widget_key: w for w in sitekg.widget_nodes}
    widgets_by_page: dict[str, list[str]] = {}
    for w in sitekg.widget_nodes:
        widgets_by_page.setdefault(w.page_key, []).append(w.widget_key)

    # NavigationEdge 인덱스 (양방향)
    nav_from_page: dict[str, list[str]] = {}  # page_key → [target_page_key, ...]
    nav_trigger: dict[str, list[str]] = {}  # widget_key → [target_page_key, ...]
    for e in sitekg.navigation_edges:
        nav_from_page.setdefault(e.source_page_key, []).append(e.target_page_key)
        nav_from_page.setdefault(e.target_page_key, []).append(e.source_page_key)
        if e.trigger_widget_key:
            nav_trigger.setdefault(e.trigger_widget_key, []).append(e.target_page_key)
            nav_trigger.setdefault(e.trigger_widget_key, []).append(e.source_page_key)

    # InteractionEdge 인덱스 (양방향)
    interact: dict[str, list[str]] = {}
    for e in sitekg.interaction_edges:
        interact.setdefault(e.source_widget_key, []).append(e.target_widget_key)
        interact.setdefault(e.target_widget_key, []).append(e.source_widget_key)

    while queue:
        node, dist = queue.popleft()
        if dist >= max_hops:
            continue

        neighbors: set[str] = set()

        if node in page_key_set:
            # page → widget (contains)
            for wk in widgets_by_page.get(node, []):
                neighbors.add(wk)
            # page → page (NavigationEdge, undirected)
            for pk in nav_from_page.get(node, []):
                neighbors.add(pk)

        if node in widget_by_key:
            w = widget_by_key[node]
            # widget → page (contains)
            neighbors.add(w.page_key)
            # widget → page (trigger)
            for pk in nav_trigger.get(node, []):
                neighbors.add(pk)
            # widget → widget (InteractionEdge, undirected)
            for wk in interact.get(node, []):
                neighbors.add(wk)

        for neighbor in neighbors:
            if neighbor not in distances:
                distances[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    return distances
