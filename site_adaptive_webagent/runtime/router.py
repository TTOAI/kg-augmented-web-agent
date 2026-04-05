from __future__ import annotations

from dataclasses import dataclass

from .enums import PriorConfidence, RouteKind, SiteOnboardingStatus


@dataclass(slots=True)
class RouteInput:
    """라우팅에 필요한 최소 입력."""

    site_onboarding_status: SiteOnboardingStatus
    prior_confidence: PriorConfidence
    approval_required: bool
    action_schema_available: bool
    page_type_id: str = "unresolved"


@dataclass(slots=True)
class RouteDecision:
    """라우팅 결과와 짧은 근거."""

    route: RouteKind
    reason: str


class StrategyRouter:
    """문서의 결정표를 그대로 구현한 router."""

    def route(self, route_input: RouteInput) -> RouteDecision:
        if route_input.approval_required:
            return RouteDecision(
                route=RouteKind.APPROVAL_FIRST,
                reason="policy rule이 사전 승인을 요구합니다",
            )

        if route_input.site_onboarding_status is not SiteOnboardingStatus.ACTIVE:
            return RouteDecision(
                route=RouteKind.FALLBACK,
                reason="site가 active onboarding 상태가 아닙니다",
            )

        if route_input.page_type_id == "unresolved":
            return RouteDecision(
                route=RouteKind.FALLBACK,
                reason="page_type_id가 unresolved 입니다",
            )

        if (
            route_input.prior_confidence is PriorConfidence.SUFFICIENT
            and route_input.action_schema_available
        ):
            return RouteDecision(
                route=RouteKind.FAST_PATH,
                reason="fast path 조건이 모두 충족되었습니다",
            )

        return RouteDecision(
            route=RouteKind.PARTIAL_PRIOR,
            reason="온보딩 사이트이지만 prior 또는 action schema가 충분하지 않습니다",
        )
