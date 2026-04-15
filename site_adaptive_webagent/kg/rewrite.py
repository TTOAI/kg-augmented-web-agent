"""Plan rewrite — Hook B의 핵심 로직.

LLM이 생성한 sub_goal 목록을 KG가 알고 있는 canonical URL로 재작성.

정책 (M2b, 단순화):
- emit_target_url이 URL을 반환하면 leading navigation sub-goals를 single navigate_to로 축약
- 첫 번째 action sub-goal 이후는 그대로 보존 (MUTATE의 form submit, RETRIEVE의 extract 유지)
- 모든 sub-goal이 navigation이면 전체를 단일 navigate_to로 치환
- emit_target_url이 None (InfoType 없음·bindings 부족)이면 no-op (원 plan 유지)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .query import _select_realizes_edge, emit_target_url
from .store import SiteKGStore
from .types import KGContext, KGLookup

if TYPE_CHECKING:
    from site_adaptive_webagent.runtime.llm import SubGoal

logger = logging.getLogger("webarena_verified")


def rewrite_plan(
    sub_goals: list["SubGoal"],
    lookup: KGLookup,
    ctx: KGContext,
) -> list["SubGoal"] | None:
    """LLM plan을 KG 정보로 재작성. 실패 시 None.

    Args:
        sub_goals: LLM이 낸 원 plan.
        lookup: (InfoType, bindings).
        ctx: KG + site_config + runtime_context.

    Returns:
        새 sub_goal 목록 (축약됨), 또는 None if KG가 URL을 내지 못하거나 sub_goals가 비어있음.

    Trust 정책 (02 §3-7):
    - target StatePattern의 url_template_trust == "inferred" 이거나
      선택된 realizes 엣지의 trust == "inferred" 이면 rewrite 보류 (원 plan 유지).
    """
    # Lazy import — 순환 방지 (kg는 runtime에 의존하지만 runtime은 kg를 의존하지 않음)
    from site_adaptive_webagent.runtime.llm import SubGoal

    if not sub_goals:
        return None

    # Trust 정책: inferred 엣지·패턴은 rewrite 보류
    store = SiteKGStore(ctx.kg)
    infotype = store.get_infotype(lookup.infotype)
    if infotype is None:
        return None
    edge = _select_realizes_edge(infotype, lookup.bindings)
    if edge is None:
        return None
    pattern = store.get_state_pattern(edge.state_pattern_id)
    if pattern is None:
        return None
    if edge.trust == "inferred" or pattern.url_template_trust == "inferred":
        logger.info(
            "[KG] rewrite skipped: trust=inferred (edge.trust=%s, url_template_trust=%s)",
            edge.trust, pattern.url_template_trust,
        )
        return None

    target_url = emit_target_url(
        ctx.kg, ctx.site_config, lookup.infotype, lookup.bindings, ctx.runtime_context,
    )
    if target_url is None:
        return None

    navigate = SubGoal(f"Navigate directly to {target_url}", "navigation")

    # 첫 번째 비-navigation sub-goal 위치 찾기
    for idx, sg in enumerate(sub_goals):
        if sg.goal_type != "navigation":
            # 이 sub-goal부터 trailing 유지, leading navigation을 single navigate_to로 대체
            return [navigate] + list(sub_goals[idx:])

    # 모든 sub-goal이 navigation: 전체를 단일 navigate_to로 치환
    return [navigate]
