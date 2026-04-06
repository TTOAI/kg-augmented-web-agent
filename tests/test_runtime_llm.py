"""LLM 연결 테스트: prompt builder + FakeLLMClient 기반 executor 경로."""
from __future__ import annotations

import json
import sqlite3
import unittest

from site_adaptive_webagent.runtime.enums import PriorConfidence, SiteOnboardingStatus, TaskRunStatus
from site_adaptive_webagent.runtime.intent import analyze_intent
from site_adaptive_webagent.runtime.llm import build_action_request, build_system_prompt, classify_task_type, parse_llm_action
from site_adaptive_webagent.runtime.orchestrator import RuntimeOrchestrator
from site_adaptive_webagent.runtime.schema import bootstrap_runtime_schema
from site_adaptive_webagent.runtime.store import ExecutionStore, PriorStore
from site_adaptive_webagent.runtime.types import (
    BrowserSession,
    PageObservation,
    PriorBundle,
    RunContext,
    RunRequest,
)

from .fixtures import (
    FakeLLMClient,
    make_action_schema,
    make_fake_page,
    make_page_type,
    make_site_profile,
    make_validator_rule,
    make_failure_pattern,
    make_policy_rule,
)


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------

class BuildSystemPromptTests(unittest.TestCase):
    def test_no_prior_bundle_contains_action_schema(self) -> None:
        prompt = build_system_prompt(None)
        self.assertIn("extract", prompt)
        self.assertIn("click", prompt)
        self.assertIn("not_found", prompt)
        self.assertIn("done", prompt)

    def test_system_prompt_contains_strategy_hint(self) -> None:
        prompt = build_system_prompt(None)
        self.assertIn("prefer", prompt.lower())
        self.assertIn("goto", prompt)

    def test_prior_bundle_includes_site_info(self) -> None:
        profile = make_site_profile(site_id="gitlab")
        bundle = PriorBundle(site_profile=profile)
        prompt = build_system_prompt(bundle)
        self.assertIn("gitlab", prompt)
        self.assertIn("Site Knowledge", prompt)

    def test_prior_bundle_includes_page_types(self) -> None:
        profile = make_site_profile()
        page_type = make_page_type()
        bundle = PriorBundle(site_profile=profile, page_types=[page_type])
        prompt = build_system_prompt(bundle)
        self.assertIn("dashboard", prompt)
        self.assertIn("Known Pages", prompt)

    def test_prior_bundle_includes_action_schemas(self) -> None:
        profile = make_site_profile()
        schema = make_action_schema()
        bundle = PriorBundle(site_profile=profile, action_schemas=[schema])
        prompt = build_system_prompt(bundle)
        self.assertIn("click_dashboard", prompt)
        self.assertIn("Available Actions", prompt)


class BuildActionRequestTests(unittest.TestCase):
    def test_contains_task_and_url(self) -> None:
        obs = PageObservation(
            url="https://example.com/dashboard",
            title="Dashboard",
            headings=["My Project"],
            text_lines=[],
            links=[],
            buttons=[],
        )
        msg = build_action_request(task="Find the todo count", observation=obs)
        self.assertIn("Find the todo count", msg)
        self.assertIn("https://example.com/dashboard", msg)
        self.assertIn("Dashboard", msg)

    def test_includes_headings_and_links(self) -> None:
        obs = PageObservation(
            url="https://example.com",
            title="Home",
            headings=["Welcome"],
            text_lines=[],
            links=["Settings", "Profile"],
            buttons=["Submit"],
        )
        msg = build_action_request(task="go to settings", observation=obs)
        self.assertIn("Welcome", msg)
        self.assertIn("Settings", msg)


class ParseLlmActionTests(unittest.TestCase):
    def test_valid_json_returns_dict(self) -> None:
        response = '{"action": "extract", "value": "42", "label": "count"}'
        result = parse_llm_action(response)
        self.assertEqual(result["action"], "extract")
        self.assertEqual(result["value"], "42")

    def test_markdown_fenced_json_is_stripped(self) -> None:
        response = '```json\n{"action": "click", "target": "Dashboard"}\n```'
        result = parse_llm_action(response)
        self.assertEqual(result["action"], "click")
        self.assertEqual(result["target"], "Dashboard")

    def test_invalid_json_returns_not_found(self) -> None:
        result = parse_llm_action("this is not json")
        self.assertEqual(result["action"], "not_found")
        self.assertIn("reasoning", result)

    def test_empty_response_returns_not_found(self) -> None:
        result = parse_llm_action("   ")
        self.assertEqual(result["action"], "not_found")


# ---------------------------------------------------------------------------
# Executor + LLM integration tests
# ---------------------------------------------------------------------------

def _make_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    bootstrap_runtime_schema(conn)
    return conn


def _seed_site(conn: sqlite3.Connection, *, site_id: str = "gitlab") -> None:
    profile = make_site_profile(site_id=site_id)
    conn.execute(
        "INSERT INTO site_profiles VALUES (?, ?, ?, ?, ?, ?)",
        (profile.site_id, profile.display_name, profile.base_url, profile.auth_type,
         profile.onboarding_status, profile.prior_confidence),
    )
    schema = make_action_schema(site_id=site_id)
    conn.execute(
        "INSERT INTO action_schemas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (schema.action_schema_id, schema.site_id, schema.action_key,
         schema.display_name, schema.description, schema.source_page_key,
         schema.target_page_key,
         json.dumps(schema.preconditions), json.dumps(schema.postconditions),
         schema.locator_strategy, schema.locator_value),
    )
    rule = make_validator_rule(site_id=site_id, rule_type="always_pass")
    conn.execute(
        "INSERT INTO validator_rules VALUES (?, ?, ?, ?, ?)",
        (rule.validator_rule_id, rule.site_id, rule.task_family, rule.rule_type, rule.pass_criteria),
    )
    policy = make_policy_rule(site_id=site_id)
    conn.execute(
        "INSERT INTO policy_rules VALUES (?, ?, ?, ?, ?)",
        (policy.policy_rule_id, policy.site_id, policy.action_key,
         policy.policy_type, policy.reason),
    )
    conn.commit()


class LLMExecutorTests(unittest.IsolatedAsyncioTestCase):
    """FakeLLMClient를 사용한 LLM 실행 경로 테스트."""

    # plan 응답 — 모든 LLM executor 테스트에서 첫 호출은 build_plan()
    PLAN_RESPONSE = '{"sub_goals": ["Complete the task"]}'

    async def test_llm_extract_returns_success(self) -> None:
        """LLM이 extract를 반환하면 SUCCESS + retrieved_data."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "extract", "value": "42", "label": "Todo Count"}'])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(
            url="https://example.com/dashboard",
            title_text="Dashboard",
            headings=["Todo Count: 42"],
        )
        plan = analyze_intent("Find the todo count")
        result = await orchestrator.run(
            RunRequest(request_text="Find the todo count", task_family="retrieve"),
            RunContext(site_id="gitlab", page_type_id="dashboard",
                       task_family="retrieve", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["https://example.com"], plan=plan,
            ),
        )

        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)
        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "SUCCESS")
        self.assertIn("42", result.execution_outcome.retrieved_data[0])

    async def test_llm_not_found_returns_failed(self) -> None:
        """LLM이 not_found를 반환하면 FAILED."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "not_found", "reasoning": "데이터가 없습니다"}'])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(url="https://example.com", title_text="Home")
        plan = analyze_intent("Find the nonexistent metric")
        result = await orchestrator.run(
            RunRequest(request_text="Find the nonexistent metric", task_family="retrieve"),
            RunContext(site_id="gitlab", page_type_id="dashboard",
                       task_family="retrieve", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["https://example.com"], plan=plan,
            ),
        )

        self.assertEqual(result.final_status, TaskRunStatus.FAILED)
        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "NOT_FOUND_ERROR")

    async def test_llm_click_then_extract(self) -> None:
        """LLM이 click 후 extract를 반환하면 plan + 2회 호출되고 SUCCESS."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([
            self.PLAN_RESPONSE,
            '{"action": "click", "target": "Dashboard"}',
            '{"action": "extract", "value": "7", "label": "Open Issues"}',
        ])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(
            url="https://example.com",
            title_text="Home",
            links=["Dashboard"],
        )
        plan = analyze_intent("Find the open issue count")
        result = await orchestrator.run(
            RunRequest(request_text="Find the open issue count", task_family="retrieve"),
            RunContext(site_id="gitlab", page_type_id="home",
                       task_family="retrieve", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["https://example.com"], plan=plan,
            ),
        )

        self.assertEqual(len(llm.calls), 3)  # plan + 2 action calls
        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)
        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "SUCCESS")

    async def test_llm_called_with_system_prompt_containing_prior(self) -> None:
        """LLM 호출 시 system prompt에 prior 정보가 포함된다."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "extract", "value": "done", "label": "result"}'])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(url="https://example.com", title_text="Home")
        plan = analyze_intent("Find the todo count")
        await orchestrator.run(
            RunRequest(request_text="Find the todo count", task_family="retrieve"),
            RunContext(site_id="gitlab", page_type_id="home",
                       task_family="retrieve", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["https://example.com"], plan=plan,
            ),
        )

        self.assertEqual(len(llm.calls), 2)  # plan + 1 action call
        # calls[1] is the action call (calls[0] is plan)
        system_prompt = llm.calls[1]["system"]
        self.assertIn("gitlab", system_prompt)
        user_message = llm.calls[1]["messages"][0]["content"]
        self.assertIn("Find the todo count", user_message)

    async def test_llm_fill_then_extract(self) -> None:
        """LLM이 fill 후 extract를 반환하면 plan + 2회 호출되고 SUCCESS."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([
            self.PLAN_RESPONSE,
            '{"action": "fill", "target": "Username", "value": "admin", "submit": false}',
            '{"action": "extract", "value": "Welcome, admin", "label": "greeting"}',
        ])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(
            url="https://example.com/login",
            title_text="Login",
            inputs=["Username"],
        )
        plan = analyze_intent("Find the greeting message")
        result = await orchestrator.run(
            RunRequest(request_text="Find the greeting message", task_family="retrieve"),
            RunContext(site_id="gitlab", page_type_id="login",
                       task_family="retrieve", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["https://example.com"], plan=plan,
            ),
        )

        self.assertEqual(len(llm.calls), 3)  # plan + 2 action calls
        # 세 번째 호출(두 번째 액션)에 대화 히스토리가 포함되어야 한다
        self.assertEqual(len(llm.calls[2]["messages"]), 3)  # user, assistant, user
        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)

    async def test_conversation_history_accumulates(self) -> None:
        """매 스텝 이전 (user, assistant) 쌍이 누적된다."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([
            self.PLAN_RESPONSE,
            '{"action": "click", "target": "Issues"}',
            '{"action": "click", "target": "Open"}',
            '{"action": "extract", "value": "42", "label": "open count"}',
        ])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(
            url="https://example.com",
            title_text="Home",
            links=["Issues", "Open"],
        )
        plan = analyze_intent("Find the open issue count")
        await orchestrator.run(
            RunRequest(request_text="Find the open issue count", task_family="retrieve"),
            RunContext(site_id="gitlab", page_type_id="home",
                       task_family="retrieve", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["https://example.com"], plan=plan,
            ),
        )

        # calls[0] = plan, calls[1..3] = action steps
        # 1번째 액션 호출: [user]
        self.assertEqual(len(llm.calls[1]["messages"]), 1)
        # 2번째 액션 호출: [user, assistant, user]
        self.assertEqual(len(llm.calls[2]["messages"]), 3)
        # 3번째 액션 호출: [user, assistant, user, assistant, user]
        self.assertEqual(len(llm.calls[3]["messages"]), 5)

    async def test_llm_permission_denied_returns_correct_status(self) -> None:
        """LLM이 permission_denied를 반환하면 PERMISSION_DENIED_ERROR."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "permission_denied", "reasoning": "No admin role"}'])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(url="http://localhost:8023/admin", title_text="Admin")
        plan = analyze_intent("Open admin settings")
        result = await orchestrator.run(
            RunRequest(request_text="Open admin settings", task_family="navigate"),
            RunContext(site_id="gitlab", page_type_id="unresolved",
                       task_family="navigate", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["http://localhost:8023"], plan=plan,
            ),
        )

        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "PERMISSION_DENIED_ERROR")

    async def test_llm_action_not_allowed_returns_correct_status(self) -> None:
        """LLM이 action_not_allowed를 반환하면 ACTION_NOT_ALLOWED_ERROR."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "action_not_allowed", "reasoning": "Billing disabled"}'])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(url="http://localhost:8023/", title_text="GitLab")
        plan = analyze_intent("Navigate to billing page")
        result = await orchestrator.run(
            RunRequest(request_text="Navigate to billing page", task_family="navigate"),
            RunContext(site_id="gitlab", page_type_id="unresolved",
                       task_family="navigate", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["http://localhost:8023"], plan=plan,
            ),
        )

        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "ACTION_NOT_ALLOWED_ERROR")

    async def test_llm_done_returns_navigate_success(self) -> None:
        """LLM이 done을 반환하면 NAVIGATE SUCCESS."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "done"}'])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(
            url="http://localhost:8023/dashboard/todos",
            title_text="Todos",
        )
        plan = analyze_intent("Open my todos page")
        result = await orchestrator.run(
            RunRequest(request_text="Open my todos page", task_family="navigate"),
            RunContext(site_id="gitlab", page_type_id="unresolved",
                       task_family="navigate", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["http://localhost:8023"], plan=plan,
            ),
        )

        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)
        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "SUCCESS")

    async def test_llm_done_returns_mutate_success(self) -> None:
        """LLM이 done을 반환하면 MUTATE SUCCESS."""
        conn = _make_connection()
        _seed_site(conn)

        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "done"}'])
        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

        page = make_fake_page(url="http://localhost:8023/", title_text="GitLab")
        plan = analyze_intent("Click submit button")
        result = await orchestrator.run(
            RunRequest(request_text="Click submit button", task_family="mutate"),
            RunContext(site_id="gitlab", page_type_id="unresolved",
                       task_family="mutate", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["http://localhost:8023"], plan=plan,
            ),
        )

        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)
        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "SUCCESS")

    async def test_llm_none_falls_back_to_rule_based(self) -> None:
        """llm=None이면 기존 규칙 기반 경로를 사용한다."""
        conn = _make_connection()
        _seed_site(conn)

        orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=None)

        page = make_fake_page(
            url="https://example.com/dashboard",
            title_text="Dashboard",
            headings=["Todo Count: 5"],
        )
        plan = analyze_intent("Find the todo count")
        result = await orchestrator.run(
            RunRequest(request_text="Find the todo count", task_family="retrieve"),
            RunContext(site_id="gitlab", page_type_id="dashboard",
                       task_family="retrieve", state_summary=""),
            browser_session=BrowserSession(
                pages=[page], sites=["gitlab"],
                start_urls=["https://example.com"], plan=plan,
            ),
        )

        self.assertEqual(result.final_status, TaskRunStatus.VALIDATED)
        assert result.execution_outcome is not None
        self.assertEqual(result.execution_outcome.status, "SUCCESS")


# ---------------------------------------------------------------------------
# classify_task_type tests
# ---------------------------------------------------------------------------

class ClassifyTaskTypeTests(unittest.TestCase):
    def test_navigate_intent(self) -> None:
        llm = FakeLLMClient('{"task_type": "NAVIGATE"}')
        result = classify_task_type("Go to my todos page", llm)
        self.assertEqual(result, "NAVIGATE")

    def test_retrieve_intent(self) -> None:
        llm = FakeLLMClient('{"task_type": "RETRIEVE"}')
        result = classify_task_type("How many commits did kilian make?", llm)
        self.assertEqual(result, "RETRIEVE")

    def test_mutate_intent(self) -> None:
        llm = FakeLLMClient('{"task_type": "MUTATE"}')
        result = classify_task_type("Post a comment saying lgtm", llm)
        self.assertEqual(result, "MUTATE")

    def test_fallback_on_parse_failure(self) -> None:
        llm = FakeLLMClient("not valid json at all")
        result = classify_task_type("Something", llm)
        self.assertEqual(result, "NAVIGATE")

    def test_fallback_on_unknown_value(self) -> None:
        llm = FakeLLMClient('{"task_type": "UNKNOWN"}')
        result = classify_task_type("Something weird", llm)
        self.assertEqual(result, "NAVIGATE")

    def test_intent_passed_to_llm(self) -> None:
        llm = FakeLLMClient('{"task_type": "RETRIEVE"}')
        classify_task_type("Get the RSS feed token", llm)
        self.assertIn("Get the RSS feed token", llm.calls[0]["messages"][0]["content"])

    def test_analyze_intent_uses_llm_when_provided(self) -> None:
        """analyze_intent에 llm을 주면 키워드 분류를 무시하고 LLM 결과를 사용한다."""
        from site_adaptive_webagent.runtime.intent import analyze_intent
        # "Go to" → 키워드로는 NAVIGATE지만 LLM은 MUTATE 반환
        llm = FakeLLMClient('{"task_type": "MUTATE"}')
        plan = analyze_intent("Go to the settings", llm=llm)
        self.assertEqual(plan.task_type, "MUTATE")

    def test_analyze_intent_keyword_fallback_without_llm(self) -> None:
        """llm 없으면 기존 키워드 분류를 사용한다."""
        from site_adaptive_webagent.runtime.intent import analyze_intent
        plan = analyze_intent("Go to my todos page")
        self.assertEqual(plan.task_type, "NAVIGATE")


if __name__ == "__main__":
    unittest.main()
