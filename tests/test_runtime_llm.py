"""LLM 연결 테스트: prompt builder + FakeLLMClient 기반 executor 경로."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from kg_augmented_webagent.runtime.executor import execute_with_llm
from kg_augmented_webagent.runtime.intent import analyze_intent
from kg_augmented_webagent.runtime.llm import classify_task_type, parse_llm_action
from kg_augmented_webagent.runtime.types import PageObservation

from .fixtures import FakeLLMClient, make_fake_page


class ParseLlmActionTests(unittest.TestCase):
    def test_valid_json_returns_dict(self) -> None:
        response = '{"action": "report_success", "answer": "42", "answer_label": "count"}'
        result = parse_llm_action(response)
        self.assertEqual(result["action"], "report_success")
        self.assertEqual(result["answer"], "42")

    def test_markdown_fenced_json_is_stripped(self) -> None:
        response = '```json\n{"action": "click", "target": "Dashboard"}\n```'
        result = parse_llm_action(response)
        self.assertEqual(result["action"], "click")
        self.assertEqual(result["target"], "Dashboard")

    def test_invalid_json_returns_parse_error(self) -> None:
        result = parse_llm_action("this is not json")
        self.assertEqual(result["action"], "parse_error")
        self.assertIn("reasoning", result)

    def test_empty_response_returns_parse_error(self) -> None:
        result = parse_llm_action("   ")
        self.assertEqual(result["action"], "parse_error")


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

    async def test_llm_report_success_returns_done_with_answer(self) -> None:
        """LLM이 report_success(answer=...)를 반환하면 verdict=done_with_answer."""
        llm = FakeLLMClient([
            self.PLAN_RESPONSE,
            '{"action": "report_success", "reason": "count visible", "answer": "42", "answer_label": "Todo Count"}',
        ])
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

        self.assertEqual(outcome.verdict, "done_with_answer")
        self.assertEqual(outcome.answer, "42")

    async def test_llm_report_failure_returns_abandoned(self) -> None:
        """LLM이 report_failure를 호출하면 verdict=abandoned (benchmark-specific
        status 분류는 outcome_classifier의 몫)."""
        failure_response = (
            '{"action": "report_failure", "reason": "Target entity does not exist on this site."}'
        )
        llm = FakeLLMClient([self.PLAN_RESPONSE, failure_response])
        page = make_fake_page(url="https://example.com", title_text="Home")

        outcome = await execute_with_llm(
            task="Find the nonexistent metric",
            task_type="RETRIEVE",
            page=page,
            observation=_empty_observation(),
            llm=llm,
        )

        self.assertEqual(outcome.verdict, "abandoned")
        assert outcome.reason is not None
        self.assertIn("does not exist", outcome.reason)

    async def test_stuck_loop_exits_as_stuck_verdict(self) -> None:
        """LLM이 report_failure도 report_success도 안 부르고 의미 없는 액션을 반복하면,
        retry+replan이 모두 소진된 뒤 verdict=stuck으로 종료된다. (이전 baseline은 이
        경로에 NOT_FOUND_ERROR status를 잘못 쓰던 의미론 오분류를 수정 — 이제는 verdict
        단에서 stuck으로 중립 표현, benchmark classifier가 UNKNOWN_ERROR로 매핑.)"""
        junk_response = '{"action": "unknown_tool", "reasoning": "stuck"}'
        llm = FakeLLMClient(
            [self.PLAN_RESPONSE]
            + [junk_response] * 30
            + [self.PLAN_RESPONSE]
            + [junk_response] * 30
        )
        page = make_fake_page(url="https://example.com", title_text="Home")

        outcome = await execute_with_llm(
            task="Do something the agent cannot perform",
            task_type="RETRIEVE",
            page=page,
            observation=_empty_observation(),
            llm=llm,
        )

        self.assertEqual(outcome.verdict, "stuck")

    async def test_llm_called_with_system_prompt(self) -> None:
        """LLM 호출 시 system prompt에 strategy가 포함된다 (KB 없음)."""
        llm = FakeLLMClient([
            self.PLAN_RESPONSE,
            '{"action": "report_success", "reason": "confirmed", "answer": "done", "answer_label": "result"}',
        ])
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

    async def test_unknown_tool_gets_explicit_feedback_and_exhausts_budget(self) -> None:
        """LLM이 존재하지 않는 tool을 호출하면 명시적 "Unknown tool" 피드백을 받고,
        반복되면 step budget 소진 → sub_goal_failed → retry/replan 소진 → verdict=stuck."""
        # sub-goal 수는 1개로 짧은 plan을 쓴다.
        plan = '{"sub_goals": [{"goal": "g", "type": "action"}]}'
        junk = '{"action": "scroll", "reasoning": "bad tool"}'
        llm = FakeLLMClient([plan] + [junk] * 40)
        page = make_fake_page(url="https://example.com", title_text="Home")

        outcome = await execute_with_llm(
            task="t", task_type="RETRIEVE",
            page=page, observation=_empty_observation(), llm=llm,
        )
        self.assertEqual(outcome.verdict, "stuck")

    async def test_final_retrieve_accepts_report_failure(self) -> None:
        """RETRIEVE의 최종 answer 단계에서 LLM이 report_failure를 호출하면 verdict=
        abandoned로 즉시 종료된다 (이전 'strong signal first-attempt accept' 분기 제거
        — status 분류는 benchmark outcome_classifier의 몫)."""
        plan = '{"sub_goals": [{"goal": "look", "type": "action"}]}'
        # 중간 sub-goal은 report_success (non-RETRIEVE-final)로 통과
        mid_success = '{"action": "report_success", "reason": "searched"}'
        # 최종 answer stage에서 report_failure 호출
        final_failure = (
            '{"action": "report_failure", "reason": "target truly does not exist"}'
        )
        llm = FakeLLMClient([plan, mid_success, final_failure])
        page = make_fake_page(url="https://example.com", title_text="Home")

        outcome = await execute_with_llm(
            task="find nonexistent", task_type="RETRIEVE",
            page=page, observation=_empty_observation(), llm=llm,
        )
        self.assertEqual(outcome.verdict, "abandoned")
        assert outcome.reason is not None
        self.assertIn("does not exist", outcome.reason)

    async def test_navigate_unchanged_url_returns_stuck(self) -> None:
        """NAVIGATE task가 모든 sub-goal을 통과했더라도 URL이 시작과 같으면
        done_no_answer가 아니라 verdict=stuck으로 종료된다."""
        # goal_type="action"으로 설정해 navigation hard rule 우회, verify_done approve,
        # 그 다음 execute_with_llm의 NAVIGATE-URL-unchanged guard가 발동.
        plan = '{"sub_goals": [{"goal": "act", "type": "action"}]}'
        success_response = '{"action": "report_success", "reason": "arrived"}'
        verify_ok = '{"achieved": true}'
        llm = FakeLLMClient([plan, success_response, verify_ok])
        page = make_fake_page(url="https://example.com/start", title_text="Start")

        outcome = await execute_with_llm(
            task="navigate somewhere", task_type="NAVIGATE",
            page=page, observation=_empty_observation(url="https://example.com/start"),
            llm=llm,
        )
        # URL이 변하지 않았으므로 NAVIGATE URL-unchanged guard 발동 → stuck.
        self.assertEqual(outcome.verdict, "stuck")


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


class BuildPlanNormalizationTests(unittest.TestCase):
    """build_plan이 sub-goal type을 정규화하는지 검증 — hard rule이 'navigation' 정확 매칭에 의존하므로
    스키마 외 값은 'action'으로 강등되어야 한다."""

    def _make_llm(self, response: str):
        return FakeLLMClient(response)

    def _obs(self):
        return PageObservation(
            url="https://example.com", title="Home",
            headings=[], text_lines=[], links=[], buttons=[], inputs=[],
        )

    def test_navigation_type_preserved(self) -> None:
        from kg_augmented_webagent.runtime.llm import build_plan
        llm = self._make_llm(
            '{"sub_goals": [{"goal": "Go to project", "type": "navigation"}]}'
        )
        plan = build_plan(task="go", task_type="NAVIGATE", observation=self._obs(), llm=llm)
        self.assertEqual(plan[0].goal_type, "navigation")

    def test_action_type_preserved(self) -> None:
        from kg_augmented_webagent.runtime.llm import build_plan
        llm = self._make_llm(
            '{"sub_goals": [{"goal": "Apply filter", "type": "action"}]}'
        )
        plan = build_plan(task="apply", task_type="NAVIGATE", observation=self._obs(), llm=llm)
        self.assertEqual(plan[0].goal_type, "action")

    def test_unknown_type_normalized_to_action(self) -> None:
        """legacy 'cognition' 또는 오타 type은 'action'으로 강등된다 (hard rule 우회 방지)."""
        from kg_augmented_webagent.runtime.llm import build_plan
        for bad_type in ("cognition", "Navigate", "navigate_to", ""):
            llm = self._make_llm(
                f'{{"sub_goals": [{{"goal": "x", "type": "{bad_type}"}}]}}'
            )
            plan = build_plan(task="t", task_type="NAVIGATE", observation=self._obs(), llm=llm)
            self.assertEqual(plan[0].goal_type, "action",
                             f"bad_type={bad_type!r} should normalize to 'action'")

    def test_empty_goal_string_filtered(self) -> None:
        from kg_augmented_webagent.runtime.llm import build_plan
        llm = self._make_llm(
            '{"sub_goals": [{"goal": "", "type": "action"}, {"goal": "real goal", "type": "action"}]}'
        )
        plan = build_plan(task="t", task_type="NAVIGATE", observation=self._obs(), llm=llm)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].goal, "real goal")


class ToolDefinitionTests(unittest.TestCase):
    """tools_for_goal()이 sub-goal 위치에 따라 올바른 tool 목록을 반환하는지 검증.

    Hierarchical tool design (2026-04-21 refactor):
    - report_success: terminal SUCCESS (sub-goal or task). RETRIEVE final goal에서는
      answer 필수, 그 외에는 reason만 필수.
    - report_failure: terminal FAILURE with status enum. 모든 context에서 사용 가능.
    """

    def test_intermediate_goal_includes_both_terminals(self) -> None:
        from kg_augmented_webagent.runtime.tools import tools_for_goal
        tools = tools_for_goal(is_last_goal=False, task_type="RETRIEVE")
        names = {t["name"] for t in tools}
        self.assertIn("click", names)
        self.assertIn("remember", names)
        self.assertIn("recall", names)
        self.assertIn("report_success", names)
        # report_failure는 중간 sub-goal에서도 사용 가능 (task-level error 선언 허용)
        self.assertIn("report_failure", names)

    def test_last_retrieve_requires_answer_in_report_success(self) -> None:
        """RETRIEVE 최종 sub-goal의 report_success schema는 answer 필수."""
        from kg_augmented_webagent.runtime.tools import tools_for_goal
        tools = tools_for_goal(is_last_goal=True, task_type="RETRIEVE")
        names_to_tool = {t["name"]: t for t in tools}
        self.assertIn("report_success", names_to_tool)
        self.assertIn("report_failure", names_to_tool)
        rs = names_to_tool["report_success"]
        self.assertIn("answer", rs["input_schema"]["properties"])
        self.assertIn("answer", rs["input_schema"]["required"])

    def test_non_retrieve_final_report_success_no_answer(self) -> None:
        """NAVIGATE/MUTATE 최종 sub-goal의 report_success는 answer 없음."""
        from kg_augmented_webagent.runtime.tools import tools_for_goal
        for task_type in ("NAVIGATE", "MUTATE"):
            with self.subTest(task_type=task_type):
                tools = tools_for_goal(is_last_goal=True, task_type=task_type)
                names_to_tool = {t["name"]: t for t in tools}
                self.assertIn("report_success", names_to_tool)
                self.assertIn("report_failure", names_to_tool)
                rs = names_to_tool["report_success"]
                self.assertNotIn("answer", rs["input_schema"]["properties"])

    def test_report_failure_schema(self) -> None:
        """status enum 없이 reason만 required. benchmark-agnostic."""
        from kg_augmented_webagent.runtime.tools import _report_failure_tool
        tool = _report_failure_tool()
        self.assertEqual(tool["name"], "report_failure")
        props = tool["input_schema"]["properties"]
        self.assertIn("reason", props)
        self.assertNotIn("status", props)
        self.assertEqual(set(tool["input_schema"]["required"]), {"reason"})

    def test_scaffold_includes_goto_tool(self) -> None:
        """baseline은 goto tool을 포함한다 — KG filter URL 템플릿
        hint를 agent가 직접 실행(`goto(url)`)할 경로가 필요."""
        from kg_augmented_webagent.runtime.tools import tools_for_goal
        for is_last in (False, True):
            for task_type in ("RETRIEVE", "NAVIGATE", "MUTATE"):
                tools = tools_for_goal(is_last_goal=is_last, task_type=task_type)
                names = {t["name"] for t in tools}
                self.assertIn("goto", names)

    def test_action_tools_have_optional_memo_field(self) -> None:
        """5 action tools (click/fill/search/goback/observe)에 memo field가 있다."""
        from kg_augmented_webagent.runtime.tools import (
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
        """remember / recall / report_success / report_failure는 자체 메커니즘이 있어 memo가 없다."""
        from kg_augmented_webagent.runtime.tools import (
            _recall_tool, _remember_tool, _report_failure_tool, _report_success_tool,
        )
        tool_specs: list[dict] = [
            _remember_tool(), _recall_tool(),
            _report_success_tool(is_last_goal=False, task_type="NAVIGATE"),
            _report_success_tool(is_last_goal=True, task_type="RETRIEVE"),
            _report_failure_tool(),
        ]
        for tool in tool_specs:
            with self.subTest(tool=tool["name"]):
                props = tool["input_schema"]["properties"]
                self.assertNotIn("memo", props)


class VerifyDoneTests(unittest.IsolatedAsyncioTestCase):
    """_verify_done이 task_notes를 활용해 done을 거부할 수 있는지 검증."""

    def test_verify_done_accepts_when_no_notes(self) -> None:
        from kg_augmented_webagent.runtime.executor import _verify_done
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

    def test_verify_done_standard_react_no_llm_call(self) -> None:
        """표준 ReAct 전환 (2026-04-17): _verify_done은 LLM 재호출 없이 agent의 done 선언을
        그대로 수용. hard rule 위반이 없으면 True. LLM call은 0회."""
        from kg_augmented_webagent.runtime.executor import _verify_done
        llm = FakeLLMClient('{"achieved": true}')
        obs = PageObservation(
            url="https://example.com/projects/empathy-prompts",
            title="empathy-prompts", headings=[], text_lines=[], links=[], buttons=[],
        )
        result = _verify_done(
            goal="Determine project IDs of top-starred projects",
            reason="found ID 183",
            current_obs=obs,
            llm=llm,
            task_notes=["empathy-prompts ID = 183"],
        )
        self.assertTrue(result)
        # 표준 ReAct: LLM 호출 0회 (agent의 done을 그대로 수용)
        self.assertEqual(len(llm.calls), 0)

    def test_verify_done_hard_rule_final_navigation_requires_url_change(self) -> None:
        """Hard rule: 마지막 navigation sub-goal인데 URL 변경 없으면 reject."""
        from kg_augmented_webagent.runtime.executor import _verify_done
        obs = PageObservation(
            url="https://example.com/start",
            title="Start", headings=[], text_lines=[], links=[], buttons=[],
        )
        result = _verify_done(
            goal="Navigate to target",
            reason="done",
            current_obs=obs,
            llm=FakeLLMClient("unused"),
            sub_goal_type="navigation",
            sub_goal_start_url="https://example.com/start",
            is_last_goal=True,
        )
        self.assertIsInstance(result, str)
        assert isinstance(result, str)
        self.assertIn("URL change", result)


class ReadTemperatureEnvTests(unittest.TestCase):
    """LLM_TEMPERATURE 환경변수 파싱 — 실험 재현성 제어."""

    def test_unset_returns_none(self) -> None:
        import os
        from kg_augmented_webagent.runtime.llm import _read_temperature_env
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLM_TEMPERATURE", None)
            self.assertIsNone(_read_temperature_env())

    def test_empty_string_returns_none(self) -> None:
        import os
        from kg_augmented_webagent.runtime.llm import _read_temperature_env
        with patch.dict(os.environ, {"LLM_TEMPERATURE": "  "}):
            self.assertIsNone(_read_temperature_env())

    def test_valid_number_parsed(self) -> None:
        import os
        from kg_augmented_webagent.runtime.llm import _read_temperature_env
        with patch.dict(os.environ, {"LLM_TEMPERATURE": "0"}):
            self.assertEqual(_read_temperature_env(), 0.0)
        with patch.dict(os.environ, {"LLM_TEMPERATURE": "0.7"}):
            self.assertEqual(_read_temperature_env(), 0.7)

    def test_invalid_string_returns_none(self) -> None:
        import os
        from kg_augmented_webagent.runtime.llm import _read_temperature_env
        with patch.dict(os.environ, {"LLM_TEMPERATURE": "hot"}):
            self.assertIsNone(_read_temperature_env())


class TaskNotesAccumulationTests(unittest.TestCase):
    """_append_task_note: 중복 제거 + 상한 유지."""

    def test_dedup(self) -> None:
        from kg_augmented_webagent.runtime.executor import _append_task_note
        notes: list[str] = []
        _append_task_note(notes, "fact A")
        _append_task_note(notes, "fact A")  # 중복
        _append_task_note(notes, "fact B")
        self.assertEqual(notes, ["fact A", "fact B"])

    def test_strip_whitespace(self) -> None:
        from kg_augmented_webagent.runtime.executor import _append_task_note
        notes: list[str] = []
        _append_task_note(notes, "  fact  ")
        self.assertEqual(notes, ["fact"])

    def test_empty_skipped(self) -> None:
        from kg_augmented_webagent.runtime.executor import _append_task_note
        notes: list[str] = []
        _append_task_note(notes, "")
        _append_task_note(notes, "   ")
        self.assertEqual(notes, [])

    def test_none_notes_no_crash(self) -> None:
        from kg_augmented_webagent.runtime.executor import _append_task_note
        _append_task_note(None, "anything")  # no-op, no crash

    def test_cap_keeps_latest(self) -> None:
        """상한 초과 시 가장 오래된 항목부터 drop."""
        from kg_augmented_webagent.runtime.executor import _TASK_NOTES_MAX, _append_task_note
        notes: list[str] = []
        for i in range(_TASK_NOTES_MAX + 5):
            _append_task_note(notes, f"fact {i}")
        self.assertEqual(len(notes), _TASK_NOTES_MAX)
        self.assertEqual(notes[-1], f"fact {_TASK_NOTES_MAX + 4}")
        self.assertEqual(notes[0], "fact 5")


class FormatAssistantToolUseTests(unittest.TestCase):
    """format_assistant_tool_use 방어: 여러 tool_calls 시 첫 번째만 포함해 pair 무결성 유지."""

    def test_single_tool_use_preserved(self) -> None:
        from kg_augmented_webagent.runtime.tools import LLMToolResponse, ToolCall, format_assistant_tool_use
        r = LLMToolResponse(
            thought="reasoning",
            tool_calls=[ToolCall(id="a", name="click", arguments={"target": "x"})],
        )
        msg = format_assistant_tool_use(r)
        tool_uses = [b for b in msg["content"] if isinstance(b, dict) and b.get("type") == "tool_use"]
        self.assertEqual(len(tool_uses), 1)
        self.assertEqual(tool_uses[0]["id"], "a")

    def test_multiple_tool_uses_reduced_to_first(self) -> None:
        """LLM이 한 턴에 여러 tool_use를 반환해도 첫 번째만 메시지에 포함된다.
        (orphaned tool_use → tool_result 매칭 실패로 Anthropic API가 에러를 내는 위험 차단.)"""
        from kg_augmented_webagent.runtime.tools import LLMToolResponse, ToolCall, format_assistant_tool_use
        r = LLMToolResponse(
            thought="reasoning",
            tool_calls=[
                ToolCall(id="a", name="click", arguments={"target": "x"}),
                ToolCall(id="b", name="fill", arguments={"target": "y", "value": "z"}),
                ToolCall(id="c", name="report_success", arguments={"reason": "r"}),
            ],
        )
        msg = format_assistant_tool_use(r)
        tool_uses = [b for b in msg["content"] if isinstance(b, dict) and b.get("type") == "tool_use"]
        self.assertEqual(len(tool_uses), 1)
        self.assertEqual(tool_uses[0]["id"], "a")
        self.assertEqual(tool_uses[0]["name"], "click")

    def test_no_tool_calls_produces_text_only(self) -> None:
        from kg_augmented_webagent.runtime.tools import LLMToolResponse, format_assistant_tool_use
        r = LLMToolResponse(thought="just thinking", tool_calls=[])
        msg = format_assistant_tool_use(r)
        tool_uses = [b for b in msg["content"] if isinstance(b, dict) and b.get("type") == "tool_use"]
        self.assertEqual(len(tool_uses), 0)


class ToolUseMessageTests(unittest.TestCase):
    """Tool Use 메시지 포맷 헬퍼 테스트."""

    def test_format_assistant_tool_use(self) -> None:
        from kg_augmented_webagent.runtime.tools import LLMToolResponse, ToolCall, format_assistant_tool_use
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
        from kg_augmented_webagent.runtime.tools import format_tool_result
        msg = format_tool_result("tc_1", "click 'Issues': navigated to /issues")
        self.assertEqual(msg["role"], "user")
        self.assertEqual(msg["content"][0]["type"], "tool_result")
        self.assertEqual(msg["content"][0]["tool_use_id"], "tc_1")

    def test_format_assistant_without_thought(self) -> None:
        from kg_augmented_webagent.runtime.tools import LLMToolResponse, ToolCall, format_assistant_tool_use
        response = LLMToolResponse(
            thought=None,
            tool_calls=[ToolCall(id="tc_2", name="report_success", arguments={})],
        )
        msg = format_assistant_tool_use(response)
        self.assertEqual(len(msg["content"]), 1)
        self.assertEqual(msg["content"][0]["type"], "tool_use")


class FakeLLMClientToolUseTests(unittest.TestCase):
    """FakeLLMClient.complete_with_tools() 테스트."""

    def test_parses_action_as_tool_name(self) -> None:
        from kg_augmented_webagent.runtime.tools import LLMToolResponse
        llm = FakeLLMClient('{"action": "click", "target": "Issues", "url": "/issues"}')
        response = llm.complete_with_tools(system="test", messages=[], tools=[])
        self.assertIsInstance(response, LLMToolResponse)
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].name, "click")
        self.assertEqual(response.tool_calls[0].arguments, {"target": "Issues", "url": "/issues"})

    def test_terminal_action_has_empty_arguments(self) -> None:
        llm = FakeLLMClient('{"action": "report_success"}')
        response = llm.complete_with_tools(system="test", messages=[], tools=[])
        self.assertEqual(response.tool_calls[0].name, "report_success")
        self.assertEqual(response.tool_calls[0].arguments, {})

    def test_preserves_reasoning_as_thought(self) -> None:
        llm = FakeLLMClient('{"action": "click", "target": "X", "reasoning": "I see X on the page"}')
        response = llm.complete_with_tools(system="test", messages=[], tools=[])
        self.assertEqual(response.thought, "I see X on the page")

    def test_records_tools_in_calls(self) -> None:
        llm = FakeLLMClient('{"action": "report_success"}')
        fake_tools = [{"name": "report_success"}]
        llm.complete_with_tools(system="sys", messages=[{"role": "user", "content": "hi"}], tools=fake_tools)
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(llm.calls[0]["tools"], fake_tools)


class ToolUseSystemPromptTests(unittest.TestCase):
    """build_tool_use_system_prompt() 테스트."""

    def test_contains_strategy_not_actions(self) -> None:
        from kg_augmented_webagent.runtime.llm import build_tool_use_system_prompt
        prompt = build_tool_use_system_prompt()
        self.assertIn("## Strategy", prompt)
        self.assertNotIn("## Actions", prompt)
        self.assertIn("remember", prompt)

    def test_does_not_inject_kb(self) -> None:
        """lab 005 baseline은 system prompt에 Site Knowledge 섹션을 박지 않는다."""
        from kg_augmented_webagent.runtime.llm import build_tool_use_system_prompt
        prompt = build_tool_use_system_prompt()
        self.assertNotIn("## Site Knowledge", prompt)
        self.assertNotIn("Page:", prompt)
        self.assertNotIn("Action:", prompt)


class ObservationMessageTests(unittest.TestCase):
    """build_observation_message() 테스트."""

    def test_contains_structured_sections(self) -> None:
        from kg_augmented_webagent.runtime.llm import SubGoal, build_observation_message
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
        from kg_augmented_webagent.runtime.llm import build_observation_message
        obs = PageObservation(
            url="https://example.com", title="Home",
            headings=[], text_lines=[], links=[], buttons=[],
        )
        msg = build_observation_message(task="Test", observation=obs)
        self.assertNotIn("## Last Action Result", msg)


if __name__ == "__main__":
    unittest.main()
