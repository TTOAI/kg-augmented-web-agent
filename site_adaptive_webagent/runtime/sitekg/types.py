"""SiteKG 데이터 모델 — minimum viable KG 4-노드 구조.

KG는 DOM이 원리적으로 표현 못 하는 4가지 정보만 박는다:
1. Connectivity — NavigationEdge + InteractionEdge + implicit contains (page_key)
2. Conditional state — WidgetNode.visibility_condition
3. Causal effects — WidgetNode.side_effects, NavigationEdge.trigger_widget_key
4. Stable references — WidgetNode.locator_strategy / locator_value

DOM에서 직접 가져올 수 있는 정보 (description, display_name, text, aria-label,
task_relevance_tags)는 *박지 않는다* — runtime에 DOM에서 추출하거나 LLM이 추론.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PageNode:
    """사이트 그래프의 노드 — 한 페이지를 표현한다."""

    page_node_id: str
    site_id: str
    page_key: str
    url_patterns: list[str] = field(default_factory=list)
    structural_signals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WidgetNode:
    """페이지 내 인터랙션 요소 — DOM에 없는 4가지 정보만."""

    widget_node_id: str
    site_id: str
    page_key: str
    widget_key: str
    locator_strategy: str = ""
    locator_value: str = ""
    visibility_condition: str | None = None
    side_effects: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NavigationEdge:
    """페이지 간 전이 — connectivity + causal effects."""

    edge_id: str
    site_id: str
    source_page_key: str
    target_page_key: str
    trigger_widget_key: str | None = None


@dataclass(slots=True)
class InteractionEdge:
    """같은 페이지 내 위젯 간 의존/활성 관계."""

    edge_id: str
    site_id: str
    page_key: str
    source_widget_key: str
    target_widget_key: str
    relation_type: str = ""


@dataclass(slots=True)
class SiteKG:
    """한 사이트의 전체 KG — flat graph 모델.

    PageNode과 WidgetNode는 동등한 노드 (상하 관계 아님).
    WidgetNode.page_key = implicit contains edge (1 hop).
    노드 간 거리 = shortest path의 hop 수.
    """

    site_id: str
    base_url: str
    page_nodes: list[PageNode] = field(default_factory=list)
    widget_nodes: list[WidgetNode] = field(default_factory=list)
    navigation_edges: list[NavigationEdge] = field(default_factory=list)
    interaction_edges: list[InteractionEdge] = field(default_factory=list)

    def get_page_node(self, page_key: str) -> PageNode | None:
        """page_key로 PageNode를 찾는다."""
        return next((p for p in self.page_nodes if p.page_key == page_key), None)

    def get_widgets_for_page(self, page_key: str) -> list[WidgetNode]:
        """특정 페이지의 WidgetNode 목록을 반환한다."""
        return [w for w in self.widget_nodes if w.page_key == page_key]

    def page_keys(self) -> set[str]:
        """모든 page_key의 집합."""
        return {p.page_key for p in self.page_nodes}

    def widget_keys(self, page_key: str | None = None) -> set[str]:
        """widget_key의 집합. page_key가 주어지면 해당 페이지만."""
        if page_key is not None:
            return {w.widget_key for w in self.widget_nodes if w.page_key == page_key}
        return {w.widget_key for w in self.widget_nodes}
