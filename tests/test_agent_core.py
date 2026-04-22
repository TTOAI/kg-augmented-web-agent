from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from site_adaptive_webagent.runtime.intent import analyze_intent
from site_adaptive_webagent.agent.core import run_agent

from .fixtures import make_fake_page

_NO_LLM = {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": ""}


class AnalyzeIntentTests(unittest.TestCase):
    def test_default_navigate_without_llm(self) -> None:
        """LLM이 없으면 task_type은 NAVIGATE 기본값."""
        plan = analyze_intent("Find the issue count on the project page")
        self.assertEqual(plan.task_type, "NAVIGATE")

    def test_url_in_intent_does_not_force_navigate(self) -> None:
        """intent에 URL이 있어도 LLM 분류 결과를 따르고 NAVIGATE로 강제하지 않는다.
        (이전 버전의 URL-shortcut이 'set homepage URL to https://...' 같은 MUTATE task를
        NAVIGATE로 오분류하던 실험 결함을 방지.)"""
        from .fixtures import FakeLLMClient
        llm = FakeLLMClient('{"task_type": "MUTATE"}')
        plan = analyze_intent(
            "Set my homepage URL to https://byteblaze.github.io",
            llm=llm,
        )
        self.assertEqual(plan.task_type, "MUTATE")
        # URL은 여전히 참조용으로 추출됨 (단, 분류에 영향 안 줌)
        self.assertEqual(plan.explicit_url, "https://byteblaze.github.io")

    def test_url_extraction_still_exposed(self) -> None:
        """extract_explicit_url은 URL 추출 유틸로 유지된다 (분류 결정에는 안 씀)."""
        from site_adaptive_webagent.runtime.intent import extract_explicit_url
        self.assertEqual(
            extract_explicit_url("Visit https://example.com."),
            "https://example.com",
        )
        self.assertIsNone(extract_explicit_url("No URL here."))


class RunAgentTests(unittest.IsolatedAsyncioTestCase):
    @patch.dict(os.environ, _NO_LLM)
    async def test_returns_stuck_verdict_without_llm(self) -> None:
        """LLM client가 없으면 verdict=stuck으로 반환 (benchmark classifier가
        UNKNOWN_ERROR로 매핑)."""
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

        self.assertEqual(result.verdict, "stuck")
        self.assertIn("LLM", result.reason or "")

    async def test_returns_stuck_verdict_when_no_pages(self) -> None:
        result = await run_agent(
            intent="Find the todo count",
            sites=["gitlab"],
            start_urls=[],
            task_id=1,
            context=None,
            pages=[],
            task_output_dir=None,
        )

        self.assertEqual(result.verdict, "stuck")
        self.assertIn("No pages", result.reason or "")


if __name__ == "__main__":
    unittest.main()
