"""Skill Library 단위 테스트."""
from __future__ import annotations

import unittest

from site_adaptive_webagent.runtime.skills import scan_and_remember, verified_extract, SkillResult
from site_adaptive_webagent.runtime.types import PageObservation

from .fixtures import FakeLLMClient


def _make_obs(**overrides) -> PageObservation:
    defaults = dict(
        url="https://example.com/projects",
        title="Projects",
        headings=["Projects"],
        text_lines=["empathy-prompts ★6", "millennials-to-snake-people ★6", "dotfiles ★1"],
        links=["empathy-prompts → /byteblaze/empathy-prompts", "millennials → /byteblaze/millennials"],
        buttons=["Sort"],
        inputs=[],
        dropdown_options=[],
    )
    defaults.update(overrides)
    return PageObservation(**defaults)


class ScanAndRememberTests(unittest.TestCase):

    def test_saves_facts(self) -> None:
        llm = FakeLLMClient('["empathy-prompts has 6 stars", "millennials-to-snake-people has 6 stars"]')
        notes: list[str] = []
        result = scan_and_remember(
            task="Find top-starred projects",
            task_hint="star counts",
            current_obs=_make_obs(),
            task_notes=notes,
            llm=llm,
        )
        self.assertEqual(len(result.notes_added), 2)
        self.assertEqual(len(notes), 2)
        self.assertIn("empathy-prompts has 6 stars", notes)
        self.assertIn("millennials-to-snake-people has 6 stars", notes)
        self.assertIn("Scanned and saved 2 facts", result.feedback)
        self.assertIsNone(result.outcome)

    def test_deduplicates(self) -> None:
        llm = FakeLLMClient('["existing fact", "new fact"]')
        notes = ["existing fact"]
        result = scan_and_remember(
            task="test", task_hint="",
            current_obs=_make_obs(),
            task_notes=notes,
            llm=llm,
        )
        self.assertEqual(len(result.notes_added), 1)
        self.assertEqual(result.notes_added[0], "new fact")
        self.assertEqual(len(notes), 2)

    def test_handles_parse_failure(self) -> None:
        llm = FakeLLMClient("not valid json at all")
        notes: list[str] = []
        result = scan_and_remember(
            task="test", task_hint="",
            current_obs=_make_obs(),
            task_notes=notes,
            llm=llm,
        )
        self.assertEqual(len(result.notes_added), 0)
        self.assertEqual(len(notes), 0)
        self.assertIn("no task-relevant facts", result.feedback)

    def test_handles_markdown_fenced_json(self) -> None:
        llm = FakeLLMClient('```json\n["fact one", "fact two"]\n```')
        notes: list[str] = []
        result = scan_and_remember(
            task="test", task_hint="",
            current_obs=_make_obs(),
            task_notes=notes,
            llm=llm,
        )
        self.assertEqual(len(result.notes_added), 2)


class VerifiedExtractTests(unittest.TestCase):

    def test_cross_checks_and_returns_outcome(self) -> None:
        llm = FakeLLMClient('{"value": "183, 187", "label": "project_ids"}')
        notes = ["empathy-prompts ID is 183", "millennials ID is 187"]
        result = verified_extract(
            task="Get project IDs of top-starred projects",
            task_type="RETRIEVE",
            preliminary_answer="183",
            current_obs=_make_obs(),
            task_notes=notes,
            llm=llm,
        )
        self.assertIsNotNone(result.outcome)
        self.assertEqual(result.outcome.status, "SUCCESS")
        self.assertEqual(result.outcome.retrieved_data, ["183", "187"])

    def test_fallback_on_parse_failure(self) -> None:
        llm = FakeLLMClient("invalid json response")
        result = verified_extract(
            task="test", task_type="RETRIEVE",
            preliminary_answer="42",
            current_obs=_make_obs(),
            task_notes=[],
            llm=llm,
        )
        self.assertIsNotNone(result.outcome)
        self.assertEqual(result.outcome.status, "SUCCESS")
        self.assertEqual(result.outcome.retrieved_data, ["42"])

    def test_no_answer_at_all_returns_not_found(self) -> None:
        llm = FakeLLMClient("invalid json")
        result = verified_extract(
            task="test", task_type="RETRIEVE",
            preliminary_answer="",
            current_obs=_make_obs(),
            task_notes=[],
            llm=llm,
        )
        self.assertIsNotNone(result.outcome)
        self.assertEqual(result.outcome.status, "NOT_FOUND_ERROR")

    def test_includes_notes_in_llm_call(self) -> None:
        """LLM 호출에 saved facts가 포함되는지 확인."""
        llm = FakeLLMClient('{"value": "183", "label": "id"}')
        notes = ["Project 183 has 6 stars"]
        verified_extract(
            task="test", task_type="RETRIEVE",
            preliminary_answer="183",
            current_obs=_make_obs(),
            task_notes=notes,
            llm=llm,
        )
        # LLM 호출에 notes가 포함되어야 함
        self.assertEqual(len(llm.calls), 1)
        user_msg = llm.calls[0]["messages"][0]["content"]
        self.assertIn("Project 183 has 6 stars", user_msg)


if __name__ == "__main__":
    unittest.main()
