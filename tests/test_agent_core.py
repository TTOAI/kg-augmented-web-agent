from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from site_adaptive_webagent.runtime.intent import analyze_intent
from site_adaptive_webagent.agent.core import run_agent

from .fixtures import make_fake_page

_NO_LLM = {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}


class AnalyzeIntentTests(unittest.TestCase):
    def test_classifies_navigate_intent_with_url(self) -> None:
        plan = analyze_intent("Open https://example.com/issues")
        self.assertEqual(plan.task_type, "NAVIGATE")
        self.assertEqual(plan.action, "goto_url")
        self.assertEqual(plan.explicit_url, "https://example.com/issues")

    def test_default_navigate_without_llm(self) -> None:
        plan = analyze_intent("Find the issue count on the project page")
        self.assertEqual(plan.task_type, "NAVIGATE")


class RunAgentTests(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, _NO_LLM)
    async def test_returns_unknown_error_without_llm(self) -> None:
        """LLM client가 없으면 unknown_error를 반환한다 (baseline은 LLM 필수)."""
        page = make_fake_page(
            url="https://example.com/todos",
            title_text="Todos",
            headings=["Todo Count: 5"],
        )

        result = await run_agent(
            intent="Find the todo count",
            sites=["gitlab"],
            start_urls=["https://example.com/todos"],
            task_id=1,
            context=None,
            pages=[page],
            task_output_dir=None,
        )

        self.assertEqual(result.status, "UNKNOWN_ERROR")
        self.assertIn("LLM", result.error_details or "")

    async def test_returns_unknown_error_when_no_pages(self) -> None:
        result = await run_agent(
            intent="Find the todo count",
            sites=["gitlab"],
            start_urls=[],
            task_id=1,
            context=None,
            pages=[],
            task_output_dir=None,
        )

        self.assertEqual(result.status, "UNKNOWN_ERROR")
        self.assertIn("No pages", result.error_details or "")


if __name__ == "__main__":
    unittest.main()
