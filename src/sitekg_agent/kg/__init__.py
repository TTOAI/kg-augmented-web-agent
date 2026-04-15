"""Knowledge Graph package — 재설계 진행 중.

현재는 ontology 스키마와 빈 스켈레톤만 제공한다.
"""

from .ontology import (
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
    "SiteKG",
    "WidgetNode",
]
