"""LLM 연결 테스트: prompt builder + FakeLLMClient 기반 executor 경로."""
from __future__ import annotations

import unittest

from site_adaptive_webagent.runtime.executor import execute_with_llm
from site_adaptive_webagent.runtime.intent import analyze_intent
from site_adaptive_webagent.runtime.llm import classify_task_type, parse_llm_action
from site_adaptive_webagent.runtime.types import PageObservation

from .fixtures import FakeLLMClient, make_fake_page


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

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

def _empty_observation(url: str = "https://example.com", title: str = "Home") -> PageObservation:
    return PageObservation(
        url=url,
        title=title,
        headings=[],
        text_lines=[],
        links=[],
        buttons=[],
    )


class LLMExecutorTests(unittest.IsolatedAsyncioTestCase):
    """FakeLLMClient를 사용한 LLM 실행 경로 테스트."""

    # plan 응답 — 모든 LLM executor 테스트에서 첫 호출은 build_plan()
    PLAN_RESPONSE = '{"sub_goals": [{"goal": "Complete the task", "type": "cognition"}]}'

    async def test_llm_extract_returns_success(self) -> None:
        """LLM이 extract를 반환하면 SUCCESS + retrieved_data."""
        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "extract", "value": "42", "label": "Todo Count"}'])
        page = make_fake_page(
            url="https://example.com/dashboard",
            title_text="Dashboard",
            headings=["Todo Count: 42"],
        )

        outcome = await execute_with_llm(
            task="Find the todo count",
            task_type="RETRIEVE",
            page=page,
            observation=_empty_observation(url=page.url, title="Dashboard"),
            llm=llm,
        )

        self.assertEqual(outcome.status, "SUCCESS")
        assert outcome.retrieved_data is not None
        self.assertIn("42", outcome.retrieved_data[0])

    async def test_llm_not_found_triggers_failure(self) -> None:
        """LLM이 not_found를 반환하면 sub-goal 실패 → retry+replan 소진 → FAILED."""
        # not_found 응답을 충분히 많이 넣어 retry + replan을 모두 소진시킨다
        not_found_response = '{"action": "not_found", "reasoning": "데이터가 없습니다"}'
        llm = FakeLLMClient(
            [self.PLAN_RESPONSE]
            + [not_found_response] * 30
            + [self.PLAN_RESPONSE]
            + [not_found_response] * 30
        )
        page = make_fake_page(url="https://example.com", title_text="Home")

        outcome = await execute_with_llm(
            task="Find the nonexistent metric",
            task_type="RETRIEVE",
            page=page,
            observation=_empty_observation(),
            llm=llm,
        )

        self.assertEqual(outcome.status, "NOT_FOUND_ERROR")

    async def test_llm_called_with_system_prompt(self) -> None:
        """LLM 호출 시 system prompt에 strategy가 포함된다 (KB 없음)."""
        llm = FakeLLMClient([self.PLAN_RESPONSE, '{"action": "extract", "value": "done", "label": "result"}'])
        page = make_fake_page(url="https://example.com", title_text="Home")

        await execute_with_llm(
            task="Find the todo count",
            task_type="RETRIEVE",
            page=page,
            observation=_empty_observation(),
            llm=llm,
        )

        # calls[0] = plan, calls[1] = action call
        self.assertGreaterEqual(len(llm.calls), 2)
        system_prompt = llm.calls[1]["system"]
        self.assertIn("Strategy", system_prompt)
        # KB layer 폐기 후 Site Knowledge 섹션이 들어가지 않음
        self.assertNotIn("## Site Knowledge", system_prompt)
        user_message = llm.calls[1]["messages"][0]["content"]
        self.assertIn("Find the todo count", user_message)


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
        """analyze_intent에 llm을 주면 LLM 결과로 task_type을 결정한다."""
        llm = FakeLLMClient('{"task_type": "MUTATE"}')
        plan = analyze_intent("Go to the settings", llm=llm)
        self.assertEqual(plan.task_type, "MUTATE")

    def test_analyze_intent_default_navigate_without_llm(self) -> None:
        """llm 없으면 NAVIGATE 기본값을 사용한다."""
        plan = analyze_intent("Go to my todos page")
        self.assertEqual(plan.task_type, "NAVIGATE")


# ---------------------------------------------------------------------------
# Tool Use tests (v5)
# ---------------------------------------------------------------------------

class ToolDefinitionTests(unittest.TestCase):
    """tools_for_goal()이 sub-goal 위치에 따라 올바른 tool 목록을 반환하는지 검증."""

    def test_intermediate_goal_excludes_extract_and_failure(self) -> None:
        from site_adaptive_webagent.runtime.tools import tools_for_goal
        tools = tools_for_goal(is_last_goal=False, task_type="RETRIEVE")
        names = {t["name"] for t in tools}
        self.assertIn("click", names)
        self.assertIn("remember", names)
        self.assertIn("recall", names)
        self.assertIn("done", names)
        self.assertNotIn("extract", names)
        self.assertNotIn("not_found", names)
        self.assertNotIn("permission_denied", names)

    def test_last_goal_retrieve_includes_extract(self) -> None:
        from site_adaptive_webagent.runtime.tools import tools_for_goal
        tools = tools_for_goal(is_last_goal=True, task_type="RETRIEVE")
        names = {t["name"] for t in tools}
        self.assertIn("extract", names)
        self.assertIn("not_found", names)

    def test_last_goal_navigate_excludes_extract(self) -> None:
        from site_adaptive_webagent.runtime.tools import tools_for_goal
        tools = tools_for_goal(is_last_goal=True, task_type="NAVIGATE")
        names = {t["name"] for t in tools}
        self.assertNotIn("extract", names)
        self.assertIn("not_found", names)
        self.assertIn("done", names)

    def test_baseline_excludes_goto_tool(self) -> None:
        """lab 005 baseline은 goto tool을 제공하지 않는다."""
        from site_adaptive_webagent.runtime.tools import tools_for_goal
        for is_last in (False, True):
            for task_type in ("RETRIEVE", "NAVIGATE", "MUTATE"):
                tools = tools_for_goal(is_last_goal=is_last, task_type=task_type)
                names = {t["name"] for t in tools}
                self.assertNotIn("goto", names)

    def test_action_tools_have_optional_memo_field(self) -> None:
        """5 action tools (click/fill/search/goback/observe)에 memo field가 있다."""
        from site_adaptive_webagent.runtime.tools import (
            _click_tool, _fill_tool, _search_tool, _goback_tool, _observe_tool,
        )
        for tool_fn in (_click_tool, _fill_tool, _search_tool, _goback_tool, _observe_tool):
            tool = tool_fn()
            with self.subTest(tool=tool["name"]):
                props = tool["input_schema"]["properties"]
                self.assertIn("memo", props)
                self.assertEqual(props["memo"]["type"], "string")
                # memo는 required가 아니어야 함
                self.assertNotIn("memo", tool["input_schema"].get("required", []))

    def test_cognitive_tools_do_not_have_memo_field(self) -> None:
        """done / remember / recall / extract 등은 자체 메커니즘이 있어 memo가 없다."""
        from site_adaptive_webagent.runtime.tools import (
            _done_tool, _remember_tool, _recall_tool, _extract_tool, _not_found_tool,
        )
        for tool_fn in (_done_tool, _remember_tool, _recall_tool, _extract_tool, _not_found_tool):
            tool = tool_fn()
            with self.subTest(tool=tool["name"]):
                props = tool["input_schema"]["properties"]
                self.assertNotIn("memo", props)


class VerifyDoneTests(unittest.IsolatedAsyncioTestCase):
    """_verify_done이 task_notes를 활용해 done을 거부할 수 있는지 검증."""

    def test_verify_done_accepts_when_no_notes(self) -> None:
        from site_adaptive_webagent.runtime.executor import _verify_done
        llm = FakeLLMClient('{"achieved": true}')
        obs = PageObservation(
            url="https://example.com/done",
            title="Done", headings=[], text_lines=[], links=[], buttons=[],
        )
        result = _verify_done(
            goal="Reach done page",
            reason="URL is /done",
            current_obs=obs,
            llm=llm,
            task_notes=None,
        )
        self.assertTrue(result)

    def test_verify_done_passes_notes_to_llm(self) -> None:
        """task_notes가 LLM 호출의 user_msg에 포함된다."""
        from site_adaptive_webagent.runtime.executor import _verify_done
        llm = FakeLLMClient('{"achieved": true}')
        obs = PageObservation(
            url="https://example.com/projects/empathy-prompts",
            title="empathy-prompts", headings=[], text_lines=[], links=[], buttons=[],
        )
        notes = [
            "empathy-prompts ID = 183",
            "millennials-to-snake-people ID = 187 still needs to be visited",
        ]
        _verify_done(
            goal="Determine project IDs of top-starred projects",
            reason="found ID 183",
            current_obs=obs,
            llm=llm,
            task_notes=notes,
        )
        # LLM이 호출됐고 user_msg에 notes가 포함됨
        self.assertEqual(len(llm.calls), 1)
        user_msg = llm.calls[0]["messages"][0]["content"]
        self.assertIn("Notes accumulated during this task", user_msg)
        self.assertIn("empathy-prompts ID = 183", user_msg)
        self.assertIn("millennials-to-snake-people ID = 187", user_msg)
        # system prompt에 notes 거부 조건 안내가 있음
        system = llm.calls[0]["system"]
        self.assertIn("not yet acted upon", system)

    def test_verify_done_rejects_when_llm_returns_false(self) -> None:
        from site_adaptive_webagent.runtime.executor import _verify_done
        llm = FakeLLMClient('{"achieved": false, "reason": "second item not yet recorded"}')
        obs = PageObservation(
            url="https://example.com",
            title="Page", headings=[], text_lines=[], links=[], buttons=[],
        )
        result = _verify_done(
            goal="Get all IDs",
            reason="got one ID",
            current_obs=obs,
            llm=llm,
            task_notes=["second project ID 187 still pending"],
        )
        self.assertEqual(result, "second item not yet recorded")


class ToolUseMessageTests(unittest.TestCase):
    """Tool Use 메시지 포맷 헬퍼 테스트."""

    def test_format_assistant_tool_use(self) -> None:
        from site_adaptive_webagent.runtime.tools import LLMToolResponse, ToolCall, format_assistant_tool_use
        response = LLMToolResponse(
            thought="I should click Issues",
            tool_calls=[ToolCall(id="tc_1", name="click", arguments={"target": "Issues"})],
        )
        msg = format_assistant_tool_use(response)
        self.assertEqual(msg["role"], "assistant")
        self.assertEqual(len(msg["content"]), 2)
        self.assertEqual(msg["content"][0]["type"], "text")
        self.assertEqual(msg["content"][1]["type"], "tool_use")
        self.assertEqual(msg["content"][1]["name"], "click")

    def test_format_tool_result(self) -> None:
        from site_adaptive_webagent.runtime.tools import format_tool_result
        msg = format_tool_result("tc_1", "click 'Issues': navigated to /issues")
        self.assertEqual(msg["role"], "user")
        self.assertEqual(msg["content"][0]["type"], "tool_result")
        self.assertEqual(msg["content"][0]["tool_use_id"], "tc_1")

    def test_format_assistant_without_thought(self) -> None:
        from site_adaptive_webagent.runtime.tools import LLMToolResponse, ToolCall, format_assistant_tool_use
        response = LLMToolResponse(
            thought=None,
            tool_calls=[ToolCall(id="tc_2", name="done", arguments={})],
        )
        msg = format_assistant_tool_use(response)
        self.assertEqual(len(msg["content"]), 1)
        self.assertEqual(msg["content"][0]["type"], "tool_use")


class FakeLLMClientToolUseTests(unittest.TestCase):
    """FakeLLMClient.complete_with_tools() 테스트."""

    def test_parses_action_as_tool_name(self) -> None:
        from site_adaptive_webagent.runtime.tools import LLMToolResponse
        llm = FakeLLMClient('{"action": "click", "target": "Issues", "url": "/issues"}')
        response = llm.complete_with_tools(system="test", messages=[], tools=[])
        self.assertIsInstance(response, LLMToolResponse)
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].name, "click")
        self.assertEqual(response.tool_calls[0].arguments, {"target": "Issues", "url": "/issues"})

    def test_done_action_has_empty_arguments(self) -> None:
        llm = FakeLLMClient('{"action": "done"}')
        response = llm.complete_with_tools(system="test", messages=[], tools=[])
        self.assertEqual(response.tool_calls[0].name, "done")
        self.assertEqual(response.tool_calls[0].arguments, {})

    def test_preserves_reasoning_as_thought(self) -> None:
        llm = FakeLLMClient('{"action": "click", "target": "X", "reasoning": "I see X on the page"}')
        response = llm.complete_with_tools(system="test", messages=[], tools=[])
        self.assertEqual(response.thought, "I see X on the page")

    def test_records_tools_in_calls(self) -> None:
        llm = FakeLLMClient('{"action": "done"}')
        fake_tools = [{"name": "done"}]
        llm.complete_with_tools(system="sys", messages=[{"role": "user", "content": "hi"}], tools=fake_tools)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(llm.calls[0]["tools"], fake_tools)


class ToolUseSystemPromptTests(unittest.TestCase):
    """build_tool_use_system_prompt() 테스트."""

    def test_contains_strategy_not_actions(self) -> None:
        from site_adaptive_webagent.runtime.llm import build_tool_use_system_prompt
        prompt = build_tool_use_system_prompt()
        self.assertIn("## Strategy", prompt)
        self.assertNotIn("## Actions", prompt)
        self.assertIn("remember", prompt)

    def test_does_not_inject_kb(self) -> None:
        """lab 005 baseline은 system prompt에 Site Knowledge 섹션을 박지 않는다."""
        from site_adaptive_webagent.runtime.llm import build_tool_use_system_prompt
        prompt = build_tool_use_system_prompt()
        self.assertNotIn("## Site Knowledge", prompt)
        self.assertNotIn("Page:", prompt)
        self.assertNotIn("Action:", prompt)


class ObservationMessageTests(unittest.TestCase):
    """build_observation_message() 테스트."""

    def test_contains_structured_sections(self) -> None:
        from site_adaptive_webagent.runtime.llm import SubGoal, build_observation_message
        obs = PageObservation(
            url="https://example.com/issues?label=bug",
            title="Issues", headings=["Issues"], text_lines=["Bug #1"],
            links=["Issues → /issues"], buttons=["Search [button]"],
            inputs=["Search"], dropdown_options=["bug"],
        )
        msg = build_observation_message(
            task="Find bug issues", observation=obs,
            last_action_feedback="click Label: dropdown opened",
            sub_goals=[SubGoal("Apply bug filter"), SubGoal("Navigate")],
            current_goal_index=0,
        )
        self.assertIn("## Task", msg)
        self.assertIn("## Current Objective (1/2)", msg)
        self.assertIn("## Last Action Result", msg)
        self.assertIn("## Page State", msg)
        self.assertIn("label=bug", msg)
        self.assertIn("## Interactive Elements", msg)

    def test_no_action_feedback_omits_section(self) -> None:
        from site_adaptive_webagent.runtime.llm import build_observation_message
        obs = PageObservation(
            url="https://example.com", title="Home",
            headings=[], text_lines=[], links=[], buttons=[],
        )
        msg = build_observation_message(task="Test", observation=obs)
        self.assertNotIn("## Last Action Result", msg)


if __name__ == "__main__":
    unittest.main()
