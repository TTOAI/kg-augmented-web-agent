"""Plan rewrite — Hook B의 핵심 로직.

LLM이 생성한 sub_goal 목록을 KG가 알고 있는 canonical URL로 재작성.

정책 (2026-04-18 Option B: verified + inferred 수용):
- `verified` / `inferred` edge·pattern은 rewrite 진행
- `declared` trust는 기록상 존재하나 본 연구 frozen KG에는 manual=0 → 현재 no-op
- emit_target_url이 URL을 반환하면 leading navigation sub-goals를 single navigate_to로 축약
- 첫 번째 action sub-goal 이후는 그대로 보존 (MUTATE의 form submit, RETRIEVE의 extract 유지)
- 모든 sub-goal이 navigation이면 전체를 단일 navigate_to로 치환
- emit_target_url이 None (InfoType 없음·bindings 부족)이면 no-op
- emit_target_url이 `{slot}` unfilled (LLM derivation incomplete binding)이면 no-op
  — malformed URL navigation 방지 (Option B 활성 후 inferred edge에서 발생 가능)
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from .query import _select_realizes_edge, emit_target_url
from .store import SiteKGStore
from .types import KGContext, KGLookup

_UNFILLED_SLOT_RE = re.compile(r"\{[^}]+\}")

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

    # Trust 정책 (Option B, 2026-04-18): verified / declared / inferred 전부 허용.
    # 이전 정책 (inferred skip)은 Hook B 사실상 비활성 유발 → 본 연구 frozen KG가
    # LLM derivation inferred edge 상당수 보유하므로 Hook B 효과 측정 불가.
    # Trust 기반 skip을 제거해 모든 trust level 수용. Incomplete URL (unfilled slots)은
    # 아래 별도 guard로 처리.
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
    # Trust 로깅 (분석용, skip 조건 아님)
    logger.info(
        "[KG] rewrite considering: edge.trust=%s, url_template_trust=%s",
        edge.trust, pattern.url_template_trust,
    )

    target_url = emit_target_url(
        ctx.kg, ctx.site_config, lookup.infotype, lookup.bindings, ctx.runtime_context,
    )
    if target_url is None:
        return None
    # Malformed URL guard: inferred edge에서 path slot unfilled 케이스 방지.
    # (예: "/{namespace}/{project}/-/{section}" 에서 section binding 누락 → literal 남음)
    if _UNFILLED_SLOT_RE.search(target_url):
        logger.info(
            "[KG] rewrite skipped: incomplete_url (unfilled slots in %s)", target_url,
        )
        return None

    navigate = SubGoal(f"Navigate directly to {target_url}", "navigation")

    # 첫 번째 비-navigation sub-goal 위치 찾기
    for idx, sg in enumerate(sub_goals):
        if sg.goal_type != "navigation":
            # 이 sub-goal부터 trailing 유지, leading navigation을 single navigate_to로 대체
            return [navigate] + list(sub_goals[idx:])

    # 모든 sub-goal이 navigation: 전체를 단일 navigate_to로 치환
    return [navigate]
