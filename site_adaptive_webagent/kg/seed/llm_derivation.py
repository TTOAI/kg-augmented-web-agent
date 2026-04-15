"""LLM-assisted InfoType derivation — 3단계 hybrid 구축의 단계 2.

docs/kg_design/07 §14의 `source=llm` / `trust=inferred` layer를 생산한다.
crawl 산출물로부터 InfoType 후보·description·realizes 매핑을 LLM이 도출.
실제 구현은 M4 (docs/kg_design/05 §6 Milestones)에서 수행.

입력:
- crawl_results: list[CrawlResult] — 단계 1 산출물
- llm: LLMClient — tool use 지원 클라이언트

산출물:
- list[InfoType] — LLM이 추출한 후보. 각 노드·엣지에 `source="llm"`, `trust="inferred"`.
  수동 검증 단계(3)에서 승격·보정·제거됨.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..types import InfoType

if TYPE_CHECKING:
    from site_adaptive_webagent.runtime.llm import LLMClient

    from .playwright_crawler import CrawlResult


def derive_infotypes(
    crawl_results: list["CrawlResult"],
    llm: "LLMClient",
) -> list[InfoType]:
    """crawl 산출물을 LLM에 주고 InfoType 후보·realizes 매핑을 추출.

    구현 예정: M4 단계 (docs/kg_design/05 §6).
    """
    raise NotImplementedError("Scheduled for M4 — see docs/kg_design/05 §6 Milestones")
