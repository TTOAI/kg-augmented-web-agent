"""Knowledge Graph 데이터 모델 — 재설계 스켈레톤.

사이트 화면만으로는 알 수 없는 네 가지 정보에 한정한다:
  1. 페이지와 위젯의 연결
  2. 상태에 따른 위젯의 노출 조건
  3. 위젯을 눌렀을 때 일어나는 변화
  4. 위젯을 정확히 지목할 수 있는 내부 식별자
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PageNode:
    page_node_id: str
    site_id: str
    page_key: str
    url_patterns: list[str] = field(default_factory=list)


@dataclass(slots=True)
class WidgetNode:
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
    edge_id: str
    site_id: str
    source_page_key: str
    target_page_key: str
    trigger_widget_key: str | None = None


@dataclass(slots=True)
class InteractionEdge:
    edge_id: str
    site_id: str
    page_key: str
    source_widget_key: str
    target_widget_key: str
    relation_type: str = ""


@dataclass(slots=True)
class SiteKG:
    site_id: str
    base_url: str
    page_nodes: list[PageNode] = field(default_factory=list)
    widget_nodes: list[WidgetNode] = field(default_factory=list)
    navigation_edges: list[NavigationEdge] = field(default_factory=list)
    interaction_edges: list[InteractionEdge] = field(default_factory=list)
