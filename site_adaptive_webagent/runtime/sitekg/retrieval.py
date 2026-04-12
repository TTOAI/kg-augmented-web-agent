"""Graph distance 기반 KG context 생성.

현재 URL에서 N hop 이내의 노드 정보를 LLM에 주입할 텍스트로 포맷한다.
description 없이 *locator + side_effects + visibility_condition + graph structure*만.
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
    reachable = _bfs_reachable(current_page_key, sitekg, max_hops)

    sections: list[str] = []
    sections.append(f"\n## KG Context (current: {current_page_key}, {max_hops} hop)")

    # 현재 page의 widgets (0 hop)
    current_widgets = sitekg.get_widgets_for_page(current_page_key)
    if current_widgets:
        widget_lines = [_format_widget(w) for w in current_widgets]
        sections.append("Widgets on this page:\n" + "\n".join(widget_lines))

    # Reachable pages (1+ hop)
    reachable_lines: list[str] = []
    for page_key, distance in sorted(reachable.items(), key=lambda x: x[1]):
        if page_key == current_page_key:
            continue
        page_node = sitekg.get_page_node(page_key)
        if not page_node:
            continue
        widgets = sitekg.get_widgets_for_page(page_key)
        widget_count = len(widgets)
        url_hint = page_node.url_patterns[0] if page_node.url_patterns else ""

        line = f"  → {page_key} ({widget_count} widgets"
        if url_hint:
            line += f", url: {url_hint}"
        line += f", {distance} hop)"

        # reachable page의 side_effects 있는 widget만 요약
        notable = [w for w in widgets if w.side_effects]
        if notable:
            for w in notable[:3]:
                line += f"\n      ● {w.widget_key} → {', '.join(w.side_effects)}"

        reachable_lines.append(line)

    if reachable_lines:
        sections.append("Reachable pages:\n" + "\n".join(reachable_lines))

    return "\n".join(sections)


def _format_widget(widget: WidgetNode) -> str:
    """WidgetNode를 LLM 가독 형태로 포맷."""
    line = f"  ● {widget.widget_key} [{widget.locator_strategy}: {widget.locator_value}]"
    if widget.side_effects:
        line += f"\n      side_effects: {widget.side_effects}"
    if widget.visibility_condition:
        line += f"\n      visible if: {widget.visibility_condition}"
    return line


def _bfs_reachable(
    start_page_key: str, sitekg: SiteKG, max_hops: int,
) -> dict[str, int]:
    """start_page_key에서 N hop 이내의 reachable page_key → distance."""
    distances: dict[str, int] = {start_page_key: 0}
    queue: deque[tuple[str, int]] = deque([(start_page_key, 0)])

    while queue:
        page_key, dist = queue.popleft()
        if dist >= max_hops:
            continue
        for edge in sitekg.navigation_edges:
            if edge.source_page_key == page_key:
                target = edge.target_page_key
                if target not in distances:
                    distances[target] = dist + 1
                    queue.append((target, dist + 1))
            # bidirectional: target → source도 1 hop
            if edge.target_page_key == page_key:
                source = edge.source_page_key
                if source not in distances:
                    distances[source] = dist + 1
                    queue.append((source, dist + 1))

    return distances
