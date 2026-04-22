from __future__ import annotations

from dataclasses import fields
import unittest

from site_adaptive_webagent.runtime.types import (
    BrowserSession,
    ExecutionOutcome,
    IntentPlan,
    PageObservation,
)


class RuntimeContractTests(unittest.TestCase):
    def test_intent_plan_has_documented_fields(self) -> None:
        self.assertEqual(
            {field.name for field in fields(IntentPlan)},
            {"task_type", "action", "target_phrase", "target_terms", "explicit_url"},
        )

    def test_page_observation_has_documented_fields(self) -> None:
        self.assertEqual(
            {field.name for field in fields(PageObservation)},
            {
                "url",
                "title",
                "headings",
                "text_lines",
                "links",
                "buttons",
                "inputs",
                "dropdown_options",
                "latent_nav",
            },
        )

    def test_execution_outcome_has_documented_fields(self) -> None:
        self.assertEqual(
            {field.name for field in fields(ExecutionOutcome)},
            {"task_type", "verdict", "answer", "answer_label", "reason"},
        )

    def test_browser_session_has_documented_fields(self) -> None:
        self.assertEqual(
            {field.name for field in fields(BrowserSession)},
            {"pages", "sites", "start_urls", "plan"},
        )


if __name__ == "__main__":
    unittest.main()
