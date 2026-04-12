"""YAML seed → SiteKG 변환기.

load() 후 자동으로 implicit edge를 추출한다:
1. side_effects "navigates to X" → NavigationEdge + trigger_widget_key
2. visibility_condition "after X click" → InteractionEdge (activates)
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

import yaml

from .types import InteractionEdge, NavigationEdge, PageNode, SiteKG, WidgetNode


class SeedValidationError(Exception):
    """시드 검증 실패."""


def load(path: str | Path) -> SiteKG:
    """YAML 시드 파일을 SiteKG 객체로 변환한다.

    검증:
    - WidgetNode.page_key가 PageNode에 존재
    - NavigationEdge.source/target_page_key가 PageNode에 존재
    - InteractionEdge.source/target_widget_key가 같은 page의 WidgetNode에 존재
    """
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise SeedValidationError("seed YAML must be a mapping")

    site_id = raw.get("site_id", "unknown")
    base_url = raw.get("base_url", "")

    page_nodes = [_parse_page_node(p, site_id) for p in raw.get("page_nodes", [])]
    widget_nodes = [_parse_widget_node(w, site_id) for w in raw.get("widget_nodes", [])]
    navigation_edges = [_parse_nav_edge(e, site_id) for e in raw.get("navigation_edges", [])]
    interaction_edges = [_parse_interaction_edge(e, site_id) for e in raw.get("interaction_edges", [])]

    sitekg = SiteKG(
        site_id=site_id,
        base_url=base_url,
        page_nodes=page_nodes,
        widget_nodes=widget_nodes,
        navigation_edges=navigation_edges,
        interaction_edges=interaction_edges,
    )

    _validate_references(sitekg)
    _extract_implicit_edges(sitekg)
    return sitekg


def _parse_page_node(data: dict[str, Any], site_id: str) -> PageNode:
    return PageNode(
        page_node_id=data.get("page_node_id", str(uuid.uuid4())),
        site_id=site_id,
        page_key=data["page_key"],
        url_patterns=data.get("url_patterns", []),
        structural_signals=data.get("structural_signals", []),
    )


def _parse_widget_node(data: dict[str, Any], site_id: str) -> WidgetNode:
    return WidgetNode(
        widget_node_id=data.get("widget_node_id", str(uuid.uuid4())),
        site_id=site_id,
        page_key=data["page_key"],
        widget_key=data["widget_key"],
        locator_strategy=data.get("locator_strategy", ""),
        locator_value=data.get("locator_value", ""),
        visibility_condition=data.get("visibility_condition"),
        side_effects=data.get("side_effects", []),
    )


def _parse_nav_edge(data: dict[str, Any], site_id: str) -> NavigationEdge:
    return NavigationEdge(
        edge_id=data.get("edge_id", str(uuid.uuid4())),
        site_id=site_id,
        source_page_key=data["source_page_key"],
        target_page_key=data["target_page_key"],
        trigger_widget_key=data.get("trigger_widget_key"),
    )


def _parse_interaction_edge(data: dict[str, Any], site_id: str) -> InteractionEdge:
    return InteractionEdge(
        edge_id=data.get("edge_id", str(uuid.uuid4())),
        site_id=site_id,
        page_key=data["page_key"],
        source_widget_key=data["source_widget_key"],
        target_widget_key=data["target_widget_key"],
        relation_type=data.get("relation_type", ""),
    )


def _validate_references(sitekg: SiteKG) -> None:
    """참조 무결성 검증."""
    page_keys = sitekg.page_keys()
    all_widget_keys = sitekg.widget_keys()

    for w in sitekg.widget_nodes:
        if w.page_key not in page_keys:
            raise SeedValidationError(
                f"WidgetNode '{w.widget_key}' references page_key '{w.page_key}' "
                f"which does not exist. Available: {page_keys}"
            )

    for e in sitekg.navigation_edges:
        if e.source_page_key not in page_keys:
            raise SeedValidationError(
                f"NavigationEdge references source_page_key '{e.source_page_key}' "
                f"which does not exist. Available: {page_keys}"
            )
        if e.target_page_key not in page_keys:
            raise SeedValidationError(
                f"NavigationEdge references target_page_key '{e.target_page_key}' "
                f"which does not exist. Available: {page_keys}"
            )

    for e in sitekg.interaction_edges:
        page_widgets = sitekg.widget_keys(e.page_key)
        if e.source_widget_key not in page_widgets:
            raise SeedValidationError(
                f"InteractionEdge references source_widget_key '{e.source_widget_key}' "
                f"not found in page '{e.page_key}'. Available: {page_widgets}"
            )
        if e.target_widget_key not in page_widgets:
            raise SeedValidationError(
                f"InteractionEdge references target_widget_key '{e.target_widget_key}' "
                f"not found in page '{e.page_key}'. Available: {page_widgets}"
            )


def _extract_implicit_edges(sitekg: SiteKG) -> None:
    """side_effects와 visibility_condition에서 implicit edge를 추출한다.

    1. "navigates to X" → NavigationEdge + trigger_widget_key
    2. "after X click" → InteractionEdge (activates)
    """
    existing_nav = {
        (e.source_page_key, e.target_page_key, e.trigger_widget_key)
        for e in sitekg.navigation_edges
    }
    widget_key_set = {w.widget_key for w in sitekg.widget_nodes}

    # 1. side_effects "navigates to X" → NavigationEdge
    for w in sitekg.widget_nodes:
        for se in w.side_effects:
            m = re.search(r"navigates to (/[^\s]+)", se)
            if not m:
                continue
            target_path = m.group(1).split("?")[0].rstrip("/") or "/"
            target_page = _find_page_by_path(sitekg, target_path)
            if target_page and target_page.page_key != w.page_key:
                key = (w.page_key, target_page.page_key, w.widget_key)
                if key not in existing_nav:
                    existing_nav.add(key)
                    sitekg.navigation_edges.append(NavigationEdge(
                        edge_id=str(uuid.uuid4()),
                        site_id=sitekg.site_id,
                        source_page_key=w.page_key,
                        target_page_key=target_page.page_key,
                        trigger_widget_key=w.widget_key,
                    ))

    # 2. visibility_condition "after X click" → InteractionEdge
    existing_interact = {
        (e.source_widget_key, e.target_widget_key)
        for e in sitekg.interaction_edges
    }
    for w in sitekg.widget_nodes:
        vc = w.visibility_condition or ""
        m = re.search(r"after (.+?) click", vc)
        if not m:
            continue
        source_key = m.group(1)
        if source_key in widget_key_set:
            key = (source_key, w.widget_key)
            if key not in existing_interact:
                existing_interact.add(key)
                sitekg.interaction_edges.append(InteractionEdge(
                    edge_id=str(uuid.uuid4()),
                    site_id=sitekg.site_id,
                    page_key=w.page_key,
                    source_widget_key=source_key,
                    target_widget_key=w.widget_key,
                    relation_type="activates",
                ))


def _find_page_by_path(sitekg: SiteKG, target_path: str) -> PageNode | None:
    """URL path로 PageNode를 찾는다."""
    for p in sitekg.page_nodes:
        for pat in p.url_patterns:
            pat_clean = pat.split("?")[0].rstrip("/") or "/"
            if pat_clean == target_path:
                return p
    return None
