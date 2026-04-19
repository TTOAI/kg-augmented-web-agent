"""DerivationResult → SiteKG (source=llm) 변환 (LLM derivation 후처리).

LLM derivation 결과를 source=llm/trust=inferred SiteKG로 만들어 manual seed +
crawl SiteKG와 별개로 보관한다. 호출자가 SiteKGStore.merge로 합치며,
merge 시 우선순위(crawl > manual > llm)에 따라 inferred 항목은 기존 declared·
verified를 덮지 못한다.

확장 (2026-04-16): state_pattern_groups를 수용. 각 group을 하나의 LLM StatePattern
(id = `llm:<hash>`)으로 승격하고, InfoType.realizes와 LeadsToEdge의 crawl id를
속한 group id로 자동 resolve해 1,000+ literal template을 의미 단위 수십 개로 압축.
"""
from __future__ import annotations

import hashlib
import logging
import re

from ..types import Action, IdentityParam, LeadsToEdge, SiteKG, StatePattern
from .llm_derivation import DerivationResult, StatePatternGroup
from .post_enrich import enrich as _post_enrich

logger = logging.getLogger("kg.derivation")

_LLM_PREFIX = "llm:"


def derivation_to_sitekg(
    derivation: DerivationResult,
    crawl_kg: SiteKG,
) -> SiteKG:
    """LLM 산출(Grouping + InfoType + Action rename) + crawl_kg → source=llm SiteKG.

    동작:
    1. state_pattern_groups를 single llm StatePattern으로 승격 (id = `llm:<slug>__<hash>`)
    2. crawl id → 속한 group의 llm id map 구성
    3. InfoType.realizes의 state_pattern_id를 group id로 resolve (crawl id·group 멤버 아닌 id는 skip)
    4. Action rename은 기존 로직 그대로
    5. crawl_kg.leads_to_edges는 renamed action만 source=llm로 복사 + 양 끝점을 group id로 resolve
    """
    derived = SiteKG(site=crawl_kg.site)

    # 1. Group → StatePattern 승격 + member → group id map
    group_by_member: dict[str, str] = {}
    for group in derivation.state_pattern_groups:
        group_id = _make_group_id(group.semantic_template)
        # member들의 query params union + LLM이 추정한 expected_query_params 병합
        union_param_types: dict[str, str] = {}
        for member_id in group.member_ids:
            member = crawl_kg.state_patterns.get(member_id)
            if member is None:
                continue
            for p in member.identity_query_params:
                union_param_types.setdefault(p.name, p.type or "string")
            group_by_member[member_id] = group_id
        # LLM expected_query_params는 crawler가 못 본 것을 보강 (사이트 어휘를 코드에
        # 박지 않기 위해 LLM이 page kind에서 도메인 추정으로 제공)
        for eqp in group.expected_query_params:
            name = eqp.get("name")
            if not name or name in union_param_types:
                continue
            t = eqp.get("type") or "string"
            union_param_types[name] = t
        identity_params = [
            IdentityParam(name=n, type=t) for n, t in union_param_types.items()
        ]
        derived.state_patterns[group_id] = StatePattern(
            id=group_id,
            url_template=group.semantic_template,
            path_params=dict(group.path_params),
            identity_query_params=identity_params,
            canonical_emit_order=list(union_param_types.keys()),
            url_template_trust="inferred",
            source="llm",
        )

    # 2. InfoType + realizes: crawl id를 group id로 resolve
    for it in derivation.infotypes:
        resolved_realizes = []
        for edge in it.realizes:
            target_id: str | None = None
            if edge.state_pattern_id in group_by_member:
                target_id = group_by_member[edge.state_pattern_id]
            elif edge.state_pattern_id in derived.state_patterns:
                target_id = edge.state_pattern_id  # LLM이 직접 llm group id를 썼을 때
            if target_id is None:
                logger.warning(
                    "[derivation→kg] InfoType %r realizes unresolved id %r — skipping",
                    it.name, edge.state_pattern_id,
                )
                continue
            edge.state_pattern_id = target_id
            resolved_realizes.append(edge)
        it.realizes = resolved_realizes
        derived.infotypes[it.name] = it
        derived.realizes_edges.extend(resolved_realizes)

    # 3. Action rename
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

    # 4. Post-enrichment: schema 결함(0-entries) 자동 보강
    _post_enrich(derived)

    # 5. LeadsToEdge 복사: action rename + 양 끝점을 group id로 resolve
    for le in crawl_kg.leads_to_edges:
        if le.action_name not in derivation.action_name_map:
            continue
        new_name = derivation.action_name_map[le.action_name]
        from_id = group_by_member.get(le.from_state_pattern_id, le.from_state_pattern_id)
        to_id = group_by_member.get(le.to_state_pattern_id, le.to_state_pattern_id)
        # Self-loop은 form submit 같은 in-place 전이를 표현. semantic rename된
        # form action만 보존 (crawl:nav self-loop는 의미 없음 — 어차피 제외됨).
        if from_id == to_id and not le.action_name.startswith("crawl:form:"):
            continue
        # 양쪽 모두 derived에 존재하는 경우만 기록
        if from_id not in derived.state_patterns or to_id not in derived.state_patterns:
            continue
        derived.leads_to_edges.append(
            LeadsToEdge(
                from_state_pattern_id=from_id,
                from_bindings=list(le.from_bindings),
                action_name=new_name,
                to_state_pattern_id=to_id,
                to_bindings=list(le.to_bindings),
                trust="inferred",
                source="llm",
            )
        )

    return derived


def _make_group_id(semantic_template: str) -> str:
    """semantic_template → 안정적 llm StatePattern id."""
    digest = hashlib.sha1(semantic_template.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", semantic_template).strip("_")[:40] or "root"
    return f"{_LLM_PREFIX}{slug}__{digest}"
