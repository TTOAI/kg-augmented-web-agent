"""Runtime state validator — Hook C의 핵심 로직.

sub-goal 경계에서 agent의 현재 URL이 target InfoType state와 일치하는지 판정.
일치하면 early-termination (SUCCESS 조기 선언) 가능.

정책 (2026-04-18 Option B Issue #1 fix):
- NAVIGATE: URL 도달 자체가 task 성공 signal → target_reached 활용.
- RETRIEVE / MUTATE: URL 도달만으로는 부족 (data 추출 또는 form submit 필요).
  false positive SUCCESS 방지 위해 target_reached 억제.
- baseline은 kg_context=None이라 이 함수 호출되지 않음 (executor.py의 Hook C guard).
"""
from __future__ import annotations

from .query import state_matches
from .types import KGContext, KGLookup


def target_reached(
    current_url: str,
    lookup: KGLookup,
    ctx: KGContext,
    task_type: str | None = None,
) -> bool:
    """현재 URL이 target InfoType+bindings 상태에 도달했는가.

    True면 agent가 task를 완료했다고 판단 가능 → early-termination.
    False면 계속 진행.

    Args:
        current_url: agent의 현재 페이지 URL (정규화 전. state_matches 내부에서 정규화).
        lookup: (InfoType, bindings).
        ctx: KG + site_config + runtime_context.
        task_type: agent-classified task type. "NAVIGATE" 가 아니면 early-termination
            억제 — RETRIEVE는 data 추출, MUTATE는 form submit이 필요하므로 URL 도달
            만으로 SUCCESS 선언할 수 없다. None이면 보수적 처리 (suppress).
    """
    if not state_matches(
        ctx.kg,
        ctx.site_config,
        current_url,
        lookup.infotype,
        lookup.bindings,
        ctx.runtime_context,
    ):
        return False
    # URL match 성공. task_type에 따라 early-termination 가부 결정.
    if task_type is None or task_type.upper() != "NAVIGATE":
        return False
    return True
