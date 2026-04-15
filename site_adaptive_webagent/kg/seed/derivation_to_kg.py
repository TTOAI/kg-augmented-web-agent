"""DerivationResult → SiteKG (source=llm) 변환 — M4-B 후처리.

LLM derivation 결과를 source=llm/trust=inferred SiteKG로 만들어 manual seed +
crawl SiteKG와 별개로 보관한다. 호출자가 SiteKGStore.merge로 합치며,
merge 시 우선순위(crawl > manual > llm)에 따라 inferred 항목은 기존 declared·
verified를 덮지 못한다.
"""
from __future__ import annotations

import logging

from ..types import Action, LeadsToEdge, SiteKG
from .llm_derivation import DerivationResult

logger = logging.getLogger("kg.derivation")


def derivation_to_sitekg(
    derivation: DerivationResult,
    crawl_kg: SiteKG,
) -> SiteKG:
    """LLM 산출(InfoType + Action rename) + crawl_kg → source=llm SiteKG.

    동작:
    - InfoType은 그대로 추가 (source="llm" 이미 set됨)
    - InfoType.realizes의 state_pattern_id가 crawl_kg에 없으면 skip + warning
    - action_name_map이 명시한 crawler Action을 의미 이름의 새 Action으로 교체
      → 새 Action은 source="llm" 으로 추가
      → crawl_kg의 LeadsToEdge 중 해당 action_name을 사용하는 엣지를 새 이름으로
        복사하고 source/trust = llm/inferred로 표시
    - state_patterns 자체는 복사하지 않는다 (crawl 권한 영역 — manual seed의
      declared와도 분리)
    """
    derived = SiteKG(site=crawl_kg.site)

    # 1. InfoType 추가 (state_pattern_id 검증)
    valid_pattern_ids = set(crawl_kg.state_patterns.keys())
    for it in derivation.infotypes:
        kept_realizes = []
        for edge in it.realizes:
            if edge.state_pattern_id in valid_pattern_ids:
                kept_realizes.append(edge)
            else:
                logger.warning(
                    "[derivation→kg] InfoType %r realizes unknown state_pattern %r — skipping",
                    it.name, edge.state_pattern_id,
                )
        it.realizes = kept_realizes
        derived.infotypes[it.name] = it
        derived.realizes_edges.extend(kept_realizes)

    # 2. Action rename
    for original_name, semantic_name in derivation.action_name_map.items():
        if original_name not in crawl_kg.actions:
            logger.warning(
                "[derivation→kg] action_name_map references unknown crawl action %r — skipping",
                original_name,
            )
            continue
        derived.actions[semantic_name] = derivation.actions.get(
            semantic_name,
            Action(
                name=semantic_name,
                params=list(crawl_kg.actions[original_name].params),
                description="",
                source="llm",
            ),
        )

    # 3. LeadsToEdge 복사 + action_name 교체
    for le in crawl_kg.leads_to_edges:
        if le.action_name not in derivation.action_name_map:
            continue
        new_name = derivation.action_name_map[le.action_name]
        derived.leads_to_edges.append(
            LeadsToEdge(
                from_state_pattern_id=le.from_state_pattern_id,
                from_bindings=list(le.from_bindings),
                action_name=new_name,
                to_state_pattern_id=le.to_state_pattern_id,
                to_bindings=list(le.to_bindings),
                trust="inferred",
                source="llm",
            )
        )

    return derived
