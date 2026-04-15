"""Playwright auto-crawl — 3단계 hybrid 구축의 단계 1.

docs/kg_design/07 §14의 `source=crawl` / `trust=verified` layer를 생산한다.
실제 구현은 M4 (docs/kg_design/05 §6 Milestones)에서 수행.

입력:
- base_url: 사이트 루트 URL (예: "http://localhost:8023")
- seed_urls: crawl 시작점 URL 목록
- max_depth: link-following 최대 깊이
- storage_state_file: 로그인 상태 Playwright storage_state JSON (선택)

산출물:
- list[CrawlResult] — 관찰된 URL, path/query param, leads_to 엣지 후보.
  seed_loader가 이를 SiteKG의 `source="crawl"` 노드·엣지로 주입.

본 plan(현재 브랜치)은 파이프라인을 인프라·스키마 수준에서 정렬하는 범위이며,
crawler 자체의 실제 구현은 별도 plan에서 진행된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CrawlResult:
    """Crawler가 관찰한 단일 URL에 대한 요약.

    seed_loader가 이 구조를 StatePattern / LeadsToEdge로 승격.
    """

    url: str
    normalized_url_template: str
    path_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    query_params_seen: list[str] = field(default_factory=list)
    outgoing_links: list[str] = field(default_factory=list)
    dom_signature: str | None = None


def crawl_site(
    base_url: str,
    seed_urls: list[str],
    max_depth: int = 2,
    storage_state_file: str | Path | None = None,
) -> list[CrawlResult]:
    """사이트를 crawl하여 관찰된 URL·param·링크를 수집.

    구현 예정: M4 단계 (docs/kg_design/05 §6).
    """
    raise NotImplementedError("Scheduled for M4 — see docs/kg_design/05 §6 Milestones")
