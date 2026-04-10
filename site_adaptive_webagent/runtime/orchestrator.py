from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .enums import KBConfidence, RouteKind, SiteOnboardingStatus, TaskRunStatus
from .executor import execute_approval_first, execute_fallback, execute_fast_path, execute_partial_kb
from .llm import LLMClient
from .router import RouteInput, StrategyRouter
from .store import ExecutionStore, KBStore
from .types import BrowserSession, ExecutionOutcome, KBBundle, RunContext, RunRequest, TaskRun


@dataclass(slots=True)
class RuntimeRunResult:
    """RuntimeOrchestrator.run()의 반환 타입."""

    task_run_id: str
    route: RouteKind
    final_status: TaskRunStatus
    validator_used: bool
    recovery_used: bool
    execution_outcome: ExecutionOutcome | None = None
    error_details: str | None = None


class RuntimeOrchestrator:
    """KB 조회 → 라우팅 → 실행 → 기록의 core runtime 흐름을 조율한다."""

    def __init__(
        self,
        kb_store: KBStore,
        execution_store: ExecutionStore,
        llm: LLMClient | None = None,
    ) -> None:
        self._kb_store = kb_store
        self._execution_store = execution_store
        self._router = StrategyRouter()
        self._llm = llm

    async def run(
        self,
        run_request: RunRequest,
        run_context: RunContext,
        *,
        browser_session: BrowserSession | None = None,
    ) -> RuntimeRunResult:
        """KB 조회 → 라우팅 → 실행 → 기록 순으로 처리한다.

        browser_session: 실제 브라우저 실행 컨텍스트. 없으면 결정론적 stub을 사용한다.
        """
        now = datetime.now(timezone.utc).isoformat()
        task_run_id = str(uuid.uuid4())

        kb_bundle = self._kb_store.get_kb_bundle(
            run_context.site_id, run_context.task_family
        )
        route_input = _build_route_input(run_context, kb_bundle)
        route_decision = self._router.route(route_input)
        kb_used = kb_bundle is not None

        task_run = TaskRun(
            task_run_id=task_run_id,
            request_text=run_request.request_text,
            site_id=run_context.site_id,
            task_family=run_context.task_family,
            run_mode=route_decision.route,
            status=TaskRunStatus.RUNNING,
            started_at=now,
            ended_at=now,
            kb_used=kb_used,
            validator_used=False,
            recovery_used=False,
        )
        self._kb_store.ensure_site_profile(run_context.site_id)
        self._execution_store.save_task_run(task_run)

        final_status, validator_used, recovery_used, execution_outcome = await _dispatch(
            route=route_decision.route,
            task_run_id=task_run_id,
            kb_bundle=kb_bundle,
            execution_store=self._execution_store,
            browser_session=browser_session,
            task=run_request.request_text,
            llm=self._llm,
        )

        ended_at = datetime.now(timezone.utc).isoformat()
        self._execution_store.update_task_run_status(task_run_id, final_status, ended_at)

        return RuntimeRunResult(
            task_run_id=task_run_id,
            route=route_decision.route,
            final_status=final_status,
            validator_used=validator_used,
            recovery_used=recovery_used,
            execution_outcome=execution_outcome,
        )


def _build_route_input(run_context: RunContext, kb_bundle: KBBundle | None) -> RouteInput:
    """KBBundle + RunContext를 라우터 입력으로 변환한다."""
    if kb_bundle is None:
        return RouteInput(
            site_onboarding_status=SiteOnboardingStatus.DRAFT,
            kb_confidence=KBConfidence.INSUFFICIENT,
            approval_required=False,
            action_schema_available=False,
            page_type_id=run_context.page_type_id,
        )

    return RouteInput(
        site_onboarding_status=kb_bundle.site_profile.onboarding_status,
        kb_confidence=kb_bundle.site_profile.kb_confidence,
        approval_required=any(
            r.policy_type == "approval_required" for r in kb_bundle.policy_rules
        ),
        action_schema_available=len(kb_bundle.action_schemas) > 0,
        page_type_id=run_context.page_type_id,
    )


async def _dispatch(
    *,
    route: RouteKind,
    task_run_id: str,
    kb_bundle: KBBundle | None,
    execution_store: ExecutionStore,
    browser_session: BrowserSession | None,
    task: str = "",
    llm: LLMClient | None = None,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """route 결과에 따라 적절한 executor로 위임한다."""
    if route == RouteKind.APPROVAL_FIRST:
        return await execute_approval_first(
            task_run_id=task_run_id,
            execution_store=execution_store,
        )

    if route == RouteKind.FALLBACK:
        return await execute_fallback(
            task_run_id=task_run_id,
            execution_store=execution_store,
            browser_session=browser_session,
            task=task,
            llm=llm,
            kb_bundle=kb_bundle,
        )

    if route == RouteKind.PARTIAL_KB:
        return await execute_partial_kb(
            task_run_id=task_run_id,
            execution_store=execution_store,
            browser_session=browser_session,
            task=task,
            llm=llm,
            kb_bundle=kb_bundle,
        )

    # FAST_PATH
    validator_rules = kb_bundle.validator_rules if kb_bundle else []
    failure_patterns = kb_bundle.failure_patterns if kb_bundle else []
    return await execute_fast_path(
        task_run_id=task_run_id,
        validator_rules=validator_rules,
        failure_patterns=failure_patterns,
        execution_store=execution_store,
        browser_session=browser_session,
        task=task,
        llm=llm,
        kb_bundle=kb_bundle,
    )
