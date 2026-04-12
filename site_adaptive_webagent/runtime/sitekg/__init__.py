"""SiteKG — site-adaptive Knowledge Graph for web agents.

Design Principles:
1. End-to-End connectivity — DOM에서 알 수 없는 사이트/위젯 간 연결 관계를 제공
2. Graph distance — 현재 위치에서 N hop 이내의 노드를 deterministic하게 선택
3. Flat graph — PageNode과 WidgetNode는 동등한 노드 (상하 관계 아님)

Graph 해석:
- WidgetNode.page_key = implicit contains edge (1 hop)
- NavigationEdge = page 간 edge (1 hop)
- InteractionEdge = widget 간 edge (1 hop)
- 노드 간 거리 = shortest path의 hop 수

KG에 박는 것 (DOM에 원리적으로 없는 4가지):
- Connectivity, Conditional state, Causal effects, Stable references

KG에 박지 않는 것 (DOM에서 직접 가져오거나 LLM이 추론):
- description, display_name, task_relevance_tags, widget_type, category
"""

from .page_matcher import match_page_node
from .retrieval import build_kg_context
from .seed_loader import SeedValidationError, load as load_seed
from .types import (
    InteractionEdge,
    NavigationEdge,
    PageNode,
    SiteKG,
    WidgetNode,
)

__all__ = [
    "InteractionEdge",
    "NavigationEdge",
    "PageNode",
    "SeedValidationError",
    "SiteKG",
    "WidgetNode",
    "build_kg_context",
    "load_seed",
    "match_page_node",
]
