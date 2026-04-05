from __future__ import annotations

import json
import sqlite3
import unittest

from site_adaptive_webagent.runtime.enums import (
    ApprovalEventStatus,
    PriorConfidence,
    RouteKind,
    SiteOnboardingStatus,
    TaskRunStatus,
)
from site_adaptive_webagent.runtime.orchestrator import RuntimeOrchestrator, _build_route_input
from site_adaptive_webagent.runtime.router import RouteInput
from site_adaptive_webagent.runtime.schema import bootstrap_runtime_schema
from site_adaptive_webagent.runtime.store import ExecutionStore, PriorStore
from site_adaptive_webagent.runtime.intent import analyze_intent
from site_adaptive_webagent.runtime.types import BrowserSession, PriorBundle, RunContext, RunRequest

from .fixtures import (
    FakePage,
    make_action_schema,
    make_fake_page,
    make_failure_pattern,
    make_policy_rule,
    make_site_profile,
    make_validator_rule,
    make_workflow_hint,
)


def _make_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    bootstrap_runtime_schema(conn)
    return conn


def _seed_site(
    conn: sqlite3.Connection,
    *,
    site_id: str = "gitlab",
    task_family: str = "dashboard_lookup",
    onboarding_status: SiteOnboardingStatus = SiteOnboardingStatus.ACTIVE,
    prior_confidence: PriorConfidence = PriorConfidence.SUFFICIENT,
    rule_type: str = "always_pass",
    policy_type: str = "allow",
    include_workflow_hint: bool = True,
    include_action_schema: bool = True,
    include_failure_pattern: bool = True,
) -> None:
    """테스트용 site 데이터를 DB에 직접 삽입한다."""
    profile = make_site_profile(
        site_id=site_id,
        onboarding_status=onboarding_status,
        prior_confidence=prior_confidence,
    )
    conn.execute(
        "INSERT INTO site_profiles VALUES (?, ?, ?, ?, ?, ?, ?)",
        (profile.site_id, profile.site_key, profile.domain, profile.login_type,
         profile.onboarding_status, profile.default_execution_mode, profile.prior_confidence),
    )

    if include_workflow_hint:
        hint = make_workflow_hint(site_id=site_id, task_family=task_family)
        conn.execute(
            "INSERT INTO workflow_hints VALUES (?, ?, ?, ?, ?, ?)",
            (hint.workflow_hint_id, hint.site_id, hint.task_family,
             json.dumps(hint.typical_step_order), json.dumps(hint.branch_points),
             json.dumps(hint.expected_terminal_states)),
        )

    if include_action_schema:
        schema = make_action_schema(site_id=site_id)
        conn.execute(
            "INSERT INTO action_schemas VALUES (?, ?, ?, ?, ?, ?)",
            (schema.action_schema_id, schema.site_id, schema.action_key,
             json.dumps(schema.preconditions), json.dumps(schema.postconditions),
             schema.preferred_locator_strategy),
        )

    rule = make_validator_rule(site_id=site_id, task_family=task_family, rule_type=rule_type)
    conn.execute(
        "INSERT INTO validator_rules VALUES (?, ?, ?, ?, ?)",
        (rule.validator_rule_id, rule.site_id, rule.task_family, rule.rule_type, rule.pass_criteria),
    )

    policy = make_policy_rule(site_id=site_id, policy_type=policy_type)
    conn.execute(
        "INSERT INTO policy_rules VALUES (?, ?, ?, ?, ?)",
        (policy.policy_rule_id, policy.site_id, policy.action_key,
         policy.policy_type, policy.policy_decision),
    )

    if include_failure_pattern:
        pattern = make_failure_pattern(site_id=site_id)
        conn.execute(
            "INSERT INTO failure_patterns VALUES (?, ?, ?, ?, ?)",
            (pattern.failure_pattern_id, pattern.site_id, pattern.failure_type,
             pattern.detection_signal, pattern.recommended_recovery),
        )

    conn.commit()


def _make_orchestrator(conn: sqlite3.Connection) -> RuntimeOrchestrator:
    return RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn))


def _make_request(
    task_family: str = "dashboard_lookup",
) -> tuple[RunRequest, RunContext]:
    request = RunRequest(request_text="show dashboard", task_family=task_family)
    context = RunContext(
        site_id="gitlab",
        page_type_id="dashboard",
        task_family=task_family,
        state_summary="dashboard page",
    )
    return request, context


class BuildRouteInputTests(unittest.TestCase):
    """_build_route_input 단위 테스트 (동기)."""

    def test_returns_fallback_input_when_prior_bundle_is_none(self) -> None:
        context = RunContext(
            site_id="unknown",
            page_type_id="unresolved",
            task_family="dashboard_lookup",
            state_summary="unknown",
        )
        route_input = _build_route_input(context, None)

        self.assertEqual(route_input.site_onboarding_status, SiteOnboardingStatus.DRAFT)
        self.assertFalse(route_input.task_family_matches)
        self.assertEqual(route_input.prior_confidence, PriorConfidence.INSUFFICIENT)
        self.assertFalse(route_input.approval_required)

    def test_maps_prior_bundle_fields_correctly(self) -> None:
        profile = make_site_profile(
            onboarding_status=SiteOnboardingStatus.ACTIVE,
            prior_confidence=PriorConfidence.SUFFICIENT,
        )
        hint = make_workflow_hint()
        schema = make_action_schema()
        bundle = PriorBundle(
            site_profile=profile,
            workflow_hints=[hint],
            action_schemas=[schema],
        )
        context = RunContext(
            site_id=profile.site_id,
            page_type_id="dashboard",
            task_family="dashboard_lookup",
            state_summary="",
        )
        route_input = _build_route_input(context, bundle)

        self.assertEqual(route_input.site_onboarding_status, SiteOnboardingStatus.ACTIVE)
        self.assertTrue(route_input.task_family_matches)
        self.assertEqual(route_input.prior_confidence, PriorConfidence.SUFFICIENT)
        self.assertFalse(route_input.approval_required)
        self.assertTrue(route_input.workflow_hint_available)
        self.assertTrue(route_input.action_schema_available)
        self.assertEqual(route_input.page_type_id, "dashboard")

    def test_detects_approval_required_policy(self) -> None:
        profile = make_site_profile()
        policy = make_policy_rule(policy_type="approval_required")
        bundle = PriorBundle(site_profile=profile, policy_rules=[policy])
        context = RunContext(
            site_id=profile.site_id,
            page_type_id="dashboard",
            task_family="dashboard_lookup",
            state_summary="",
        )
        route_input = _build_route_input(context, bundle)

        self.assertTrue(route_input.approval_required)


class AcceptanceTests(unittest.IsolatedAsyncioTestCase):
    """핵심 분기 acceptance 시나리오 (비동기)."""

    async def test_fast_path_success(self) -> None:
        """active site + 모든 prior + always_pass rule → VALIDATED."""
        conn = _make_connection()
        _seed_site(conn, rule_type="always_pass")
        orchestrator = _make_orchestrator(conn)
        request, context = _make_request()

        result = await orchestrator.run(request, context)

        self.assertEqual(result.route, RouteKind.FAST_PATH)
        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)
        self.assertTrue(result.validator_used)
        self.assertFalse(result.recovery_used)

        row = conn.execute(
            "SELECT status FROM task_runs WHERE task_run_id = ?",
            (result.task_run_id,),
        ).fetchone()
        self.assertEqual(row[0], TaskRunStatus.VALIDATED)

    async def test_validator_fail_then_recovery_then_handoff(self) -> None:
        """always_fail + failure_pattern → recovery SUCCESS → 재검증 fail → HANDOFF."""
        conn = _make_connection()
        _seed_site(conn, rule_type="always_fail", include_failure_pattern=True)
        orchestrator = _make_orchestrator(conn)
        request, context = _make_request()

        result = await orchestrator.run(request, context)

        self.assertEqual(result.route, RouteKind.FAST_PATH)
        self.assertTrue(result.recovery_used)
        self.assertEqual(result.final_status, TaskRunStatus.HANDOFF)

        recovery_rows = conn.execute(
            "SELECT recovery_result FROM recovery_records WHERE task_run_id = ?",
            (result.task_run_id,),
        ).fetchall()
        self.assertEqual(len(recovery_rows), 1)

    async def test_validator_fail_no_failure_pattern_gives_handoff(self) -> None:
        """always_fail + failure_patterns 없음 → recovery FAILED → HANDOFF."""
        conn = _make_connection()
        _seed_site(conn, rule_type="always_fail", include_failure_pattern=False)
        orchestrator = _make_orchestrator(conn)
        request, context = _make_request()

        result = await orchestrator.run(request, context)

        self.assertEqual(result.route, RouteKind.FAST_PATH)
        self.assertEqual(result.final_status, TaskRunStatus.HANDOFF)
        self.assertTrue(result.recovery_used)

    async def test_approval_first_records_event_and_returns_approval_wait(self) -> None:
        """approval_required policy → APPROVAL_WAIT + ApprovalEvent(REQUESTED) 기록."""
        conn = _make_connection()
        _seed_site(conn, policy_type="approval_required")
        orchestrator = _make_orchestrator(conn)
        request, context = _make_request()

        result = await orchestrator.run(request, context)

        self.assertEqual(result.route, RouteKind.APPROVAL_FIRST)
        self.assertEqual(result.final_status, TaskRunStatus.APPROVAL_WAIT)
        self.assertFalse(result.validator_used)
        self.assertFalse(result.recovery_used)

        approval_rows = conn.execute(
            "SELECT approval_status FROM approval_events WHERE task_run_id = ?",
            (result.task_run_id,),
        ).fetchall()
        self.assertEqual(len(approval_rows), 1)
        self.assertEqual(approval_rows[0][0], ApprovalEventStatus.REQUESTED)

    async def test_fallback_when_site_is_draft(self) -> None:
        """onboarding_status=DRAFT인 site → FALLBACK → HANDOFF."""
        conn = _make_connection()
        _seed_site(conn, onboarding_status=SiteOnboardingStatus.DRAFT)
        orchestrator = _make_orchestrator(conn)
        request, context = _make_request()

        result = await orchestrator.run(request, context)

        self.assertEqual(result.route, RouteKind.FALLBACK)
        self.assertEqual(result.final_status, TaskRunStatus.HANDOFF)

    async def test_partial_prior_when_workflow_hint_missing(self) -> None:
        """workflow_hint 없는 active site → PARTIAL_PRIOR → FAILED."""
        conn = _make_connection()
        _seed_site(conn, include_workflow_hint=False, include_action_schema=True)
        orchestrator = _make_orchestrator(conn)
        request, context = _make_request()

        result = await orchestrator.run(request, context)

        self.assertEqual(result.route, RouteKind.PARTIAL_PRIOR)
        self.assertEqual(result.final_status, TaskRunStatus.FAILED)

    async def test_browser_session_retrieve_success(self) -> None:
        """browser_session 제공 시 FakePage에서 값 추출 → execution_outcome 반환."""
        conn = _make_connection()
        _seed_site(conn, rule_type="always_pass")
        orchestrator = _make_orchestrator(conn)

        page = make_fake_page(
            url="https://example.com/dashboard",
            title_text="Dashboard",
            headings=["Todo Count: 5"],
        )
        plan = analyze_intent("Find the todo count")
        request = RunRequest(request_text="Find the todo count", task_family="retrieve")
        context = RunContext(
            site_id="gitlab",
            page_type_id="dashboard",
            task_family="retrieve",
            state_summary="",
        )

        result = await orchestrator.run(
            request, context,
            browser_session=BrowserSession(pages=[page], sites=["gitlab"],
                                           start_urls=["https://example.com"], plan=plan),
        )

        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)
        self.assertIsNotNone(result.execution_outcome)
        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "SUCCESS")
        self.assertEqual(result.execution_outcome.retrieved_data, ["Todo Count: 5"])

    async def test_browser_session_not_found_maps_to_failed(self) -> None:
        """browser_session에서 NOT_FOUND_ERROR → FAILED."""
        conn = _make_connection()
        _seed_site(conn, rule_type="always_pass")
        orchestrator = _make_orchestrator(conn)

        page = make_fake_page(
            url="https://example.com/dashboard",
            title_text="Dashboard",
            headings=[],
        )
        plan = analyze_intent("Find the nonexistent widget count")
        request = RunRequest(request_text="Find the nonexistent widget count", task_family="retrieve")
        context = RunContext(
            site_id="gitlab",
            page_type_id="dashboard",
            task_family="retrieve",
            state_summary="",
        )

        result = await orchestrator.run(
            request, context,
            browser_session=BrowserSession(pages=[page], sites=["gitlab"],
                                           start_urls=["https://example.com"], plan=plan),
        )

        self.assertEqual(result.final_status, TaskRunStatus.FAILED)
        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "NOT_FOUND_ERROR")

    async def test_fallback_with_browser_session_runs_browser(self) -> None:
        """DRAFT site + browser_session → FALLBACK 경로에서도 브라우저 실행."""
        conn = _make_connection()
        _seed_site(conn, onboarding_status=SiteOnboardingStatus.DRAFT)
        orchestrator = _make_orchestrator(conn)

        page = make_fake_page(
            url="https://example.com/todos",
            title_text="Todos",
            headings=["Todo Count: 5"],
        )
        plan = analyze_intent("Find the todo count")
        request = RunRequest(request_text="Find the todo count", task_family="retrieve")
        context = RunContext(
            site_id="gitlab",
            page_type_id="unresolved",
            task_family="retrieve",
            state_summary="",
        )

        result = await orchestrator.run(
            request, context,
            browser_session=BrowserSession(pages=[page], sites=["gitlab"],
                                           start_urls=["https://example.com"], plan=plan),
        )

        self.assertEqual(result.route, RouteKind.FALLBACK)
        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)
        self.assertIsNotNone(result.execution_outcome)


if __name__ == "__main__":
    unittest.main()
