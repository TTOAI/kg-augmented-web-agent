"""Runtime state validator — Hook C의 핵심 로직.

sub-goal 경계에서 agent의 현재 URL이 target InfoType state와 일치하는지 판정.
일치하면 early-termination (SUCCESS 조기 선언) 가능.

M2b 구현은 `query.state_matches`의 얇은 wrapper로 시작.
"""
from __future__ import annotations

from .query import state_matches
from .types import KGContext, KGLookup


def target_reached(
    current_url: str,
    lookup: KGLookup,
    ctx: KGContext,
) -> bool:
    """현재 URL이 target InfoType+bindings 상태에 도달했는가.

    True면 agent가 task를 완료했다고 판단 가능 → early-termination.
    False면 계속 진행.

    Args:
        current_url: agent의 현재 페이지 URL (normalize 이전 상태. state_matches 내부에서 정규화).
        lookup: (InfoType, bindings).
        ctx: KG + site_config + runtime_context.
    """
    return state_matches(
        ctx.kg,
        ctx.site_config,
        current_url,
        lookup.infotype,
        lookup.bindings,
        ctx.runtime_context,
    )
