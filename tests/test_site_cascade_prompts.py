"""Tests for cascade.yaml + prompts.yaml externalization.

cascade.yaml / prompts.yaml에 저장된 값(DEFAULT_GITLAB_CONFIG,
_MUTATE_FORM_CHECKLIST 대응분)이 기준 하드코드 값과 동등함을 확인한다.
"""
from __future__ import annotations

import unittest

from kg_augmented_webagent.kg.site_extras import (
    SiteCascadeEntries,
    load_site_cascade,
)
from kg_augmented_webagent.runtime.prompts import (
    load_prompt_library,
)


class GitLabCascadeRoundtripTests(unittest.TestCase):
    """cascade.yaml이 이관 전 DEFAULT_GITLAB_CONFIG와 동등."""

    def setUp(self) -> None:
        self.cascade = load_site_cascade("gitlab")

    def test_scope_entries_matches_pre_migration(self) -> None:
        expected = {
            "project": "project/main",
            "dashboard": "dashboard/project_list/yours",
            "account": "account/account",
            "global": "global/root_redirect",
            "user": "user/profile",
            "explore": "explore/project_list/all",
            "ide": "ide/edit_view",
        }
        self.assertEqual(self.cascade.scope_entries, expected)

    def test_hub_matches_pre_migration(self) -> None:
        self.assertEqual(self.cascade.hub, "dashboard/project_list/yours")

    def test_missing_site_returns_empty(self) -> None:
        empty = load_site_cascade("_nonexistent_site_")
        self.assertEqual(empty, SiteCascadeEntries.empty())


class GitLabPromptsRoundtripTests(unittest.TestCase):
    """prompts.yaml 렌더 결과가 이관 전 하드코드 checklist와 의미적으로 동등
    (주요 anchor phrase 모두 포함)."""

    def setUp(self) -> None:
        self.library = load_prompt_library("gitlab")

    def test_mutate_checklist_contains_key_anchors(self) -> None:
        rendered = self.library.render_mutate_checklist()
        # 이관 전 _MUTATE_FORM_CHECKLIST의 핵심 phrase 모두 존재해야 함
        expected_anchors = [
            "Form submission checklist (MUTATE)",
            "Before clicking Create / Submit / Save",
            '"empty"',
            "Initialize repository with a README",
            '"private"',
            "visibility",
            '"as guest"',
            "role select",
            '"change"',
            "LOCATE it",
            '"create"',
            "Create form",
            "After submit, verify the target state",
        ]
        for anchor in expected_anchors:
            self.assertIn(anchor, rendered, f"anchor missing: {anchor}")

    def test_mutate_checklist_structure_sections(self) -> None:
        """Rendered checklist has `## header`, bullet lines, `### Verb routing`, closing."""
        rendered = self.library.render_mutate_checklist()
        self.assertIn("## Form submission checklist", rendered)
        self.assertIn("### Verb routing", rendered)
        # 불릿 포맷
        self.assertIn("  - ", rendered)

    def test_filter_template_preamble_contains_anchors(self) -> None:
        lines = self.library.render_filter_template_preamble()
        body = "\n".join(lines)
        anchors = [
            "Filter/sort URL templates",
            "query-param patterns",
            "sibling list endpoints",
            "Prefer `goto(url)`",
            "extraneous `search=",
        ]
        for a in anchors:
            self.assertIn(a, body, f"anchor missing: {a}")

    def test_goto_tool_description_loaded(self) -> None:
        desc, url_desc = self.library.goto_tool_description()
        self.assertIn("Directly navigate to a URL", desc)
        self.assertIn("placeholder", url_desc.lower())

    def test_missing_site_returns_empty(self) -> None:
        empty = load_prompt_library("_nonexistent_site_")
        self.assertEqual(empty.render_mutate_checklist(), "")
        self.assertEqual(empty.render_filter_template_preamble(), [])
        self.assertEqual(empty.goto_tool_description(), ("", ""))


class BuildKgSessionLoadsCascadeFromConfig(unittest.TestCase):
    """build_kg_session이 cascade.yaml을 읽어 KGSession.cascade_config를 채우는지
    (동작은 integration test — unit level에선 cascade config 로드 자체만 확인)."""

    def test_load_site_cascade_is_callable(self) -> None:
        # smoke: import + call without errors
        cfg = load_site_cascade("gitlab")
        self.assertTrue(cfg.scope_entries)
        self.assertEqual(cfg.hub, "dashboard/project_list/yours")


class GotoToolUsesLibrary(unittest.TestCase):
    """_goto_tool이 library에서 description 로드하는지 확인."""

    def test_goto_description_is_non_empty(self) -> None:
        from kg_augmented_webagent.runtime.tools import _goto_tool
        tool = _goto_tool()
        self.assertEqual(tool["name"], "goto")
        self.assertTrue(tool["description"])
        url_prop = tool["input_schema"]["properties"]["url"]
        self.assertTrue(url_prop["description"])


if __name__ == "__main__":
    unittest.main()
