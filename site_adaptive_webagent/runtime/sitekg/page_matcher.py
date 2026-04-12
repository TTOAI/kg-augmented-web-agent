"""Deterministic page matching — URL을 PageNode에 매칭한다.

§4.1.2의 5단계 알고리즘:
1. url_patterns에서 Express.js placeholder 매칭으로 candidates 수집
2. 0개면 UNRESOLVED
3. 1개면 그 결과
4. >1개면 specificity (literal segments 우선) 정렬
5. tiebreak — 첫 번째 반환 (M0). structural_signals 활용은 M1+
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .types import PageNode, SiteKG

_UNRESOLVED = "UNRESOLVED"


def match_page_node(current_url: str, sitekg: SiteKG) -> PageNode | str:
    """현재 URL에 대해 page_node를 찾는다.

    Returns: 매칭된 PageNode, 또는 "UNRESOLVED" 문자열.
    """
    url_path = _normalize_url(current_url)
    candidates: list[tuple[PageNode, str]] = []

    for pn in sitekg.page_nodes:
        for pattern in pn.url_patterns:
            if _pattern_matches(pattern, url_path):
                candidates.append((pn, pattern))
                break  # 한 PageNode에서 첫 매칭만

    if len(candidates) == 0:
        return _UNRESOLVED
    if len(candidates) == 1:
        return candidates[0][0]

    # tiebreak by specificity
    candidates.sort(key=lambda c: _pattern_specificity(c[1]), reverse=True)
    return candidates[0][0]


def _normalize_url(url: str) -> str:
    """URL에서 path만 추출하고 trailing slash를 제거한다."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    # query params가 url_pattern에 포함된 경우 처리
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path or "/"


def _pattern_matches(pattern: str, url_path: str) -> bool:
    """Express.js placeholder 패턴으로 URL path를 매칭한다.

    패턴 예: "/{ns}/{project}/-/issues", "/explore?visibility_level=20"
    Placeholder: {name} 또는 :name — 하나의 path segment와 매칭
    """
    # query params가 pattern에 있으면 url_path에도 있어야
    if "?" in pattern:
        pattern_path, pattern_query = pattern.split("?", 1)
        if "?" not in url_path:
            return False
        url_base, url_query = url_path.split("?", 1)
        if not _path_matches(pattern_path, url_base):
            return False
        # query params: pattern의 모든 key=value가 url에 존재해야
        return _query_contains(url_query, pattern_query)

    return _path_matches(pattern, url_path)


def _path_matches(pattern: str, url_path: str) -> bool:
    """path segment 매칭."""
    pattern_clean = pattern.rstrip("/")
    url_clean = url_path.split("?")[0].rstrip("/")

    pattern_segments = [s for s in pattern_clean.split("/") if s]
    url_segments = [s for s in url_clean.split("/") if s]

    if len(pattern_segments) != len(url_segments):
        return False

    for p_seg, u_seg in zip(pattern_segments, url_segments):
        if _is_placeholder(p_seg):
            continue  # placeholder는 모든 값에 매칭
        if p_seg != u_seg:
            return False
    return True


def _query_contains(url_query: str, pattern_query: str) -> bool:
    """url_query가 pattern_query의 모든 key=value 쌍을 포함하는지."""
    pattern_params = dict(p.split("=", 1) for p in pattern_query.split("&") if "=" in p)
    url_params = dict(p.split("=", 1) for p in url_query.split("&") if "=" in p)
    return all(url_params.get(k) == v for k, v in pattern_params.items())


def _is_placeholder(segment: str) -> bool:
    """placeholder segment 판별: {name} 또는 :name."""
    return segment.startswith("{") or segment.startswith(":")


def _pattern_specificity(pattern: str) -> int:
    """패턴의 specificity 점수. literal segment가 많을수록 높음."""
    path_part = pattern.split("?")[0]
    segments = [s for s in path_part.split("/") if s]
    placeholder_count = sum(1 for s in segments if _is_placeholder(s))
    literal_count = len(segments) - placeholder_count
    # query params가 있으면 specificity 보너스
    query_bonus = 50 if "?" in pattern else 0
    return literal_count * 100 - placeholder_count * 10 + query_bonus
