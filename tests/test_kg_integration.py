"""agent.kg_integration 단위 테스트 — Hook A + KGContext loader."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from site_adaptive_webagent.agent.kg_integration import (
    build_plan_to_info_system_prompt,
    build_plan_to_info_tool,
    classify_intent_via_kg,
    load_kg_context,
)
from site_adaptive_webagent.kg import KGLookup
from site_adaptive_webagent.kg.seed import load_site_kg_from_dir

from .fixtures import FakeLLMClient

GITLAB_CONFIG_DIR = Path(__file__).parent.parent / "config" / "sites" / "gitlab"


class PlanToInfoToolTests(unittest.TestCase):
    def setUp(self) -> None:
        _, self.kg = load_site_kg_from_dir(GITLAB_CONFIG_DIR)

    def test_tool_has_required_fields(self) -> None:
        tool = build_plan_to_info_tool(self.kg)
        self.assertEqual(tool["name"], "plan_to_info")
        schema = tool["input_schema"]
        self.assertIn("target_infotype", schema["properties"])
        self.assertIn("bindings", schema["properties"])
        self.assertEqual(
            set(schema["required"]),
            {"target_infotype", "bindings"},
        )

    def test_target_infotype_enum_matches_kg(self) -> None:
        tool = build_plan_to_info_tool(self.kg)
        enum = tool["input_schema"]["properties"]["target_infotype"]["enum"]
        self.assertEqual(set(enum), set(self.kg.infotypes.keys()))

    def test_system_prompt_lists_all_infotypes(self) -> None:
        prompt = build_plan_to_info_system_prompt(self.kg)
        for name in self.kg.infotypes:
            self.assertIn(name, prompt)


class ClassifyIntentTests(unittest.TestCase):
    def setUp(self) -> None:
        _, self.kg = load_site_kg_from_dir(GITLAB_CONFIG_DIR)

    def test_valid_classification_returns_lookup(self) -> None:
        """LLM이 plan_to_info tool을 올바르게 호출하면 KGLookup 반환."""
        # FakeLLMClient: 하나의 tool call (action=plan_to_info) 스타일로 응답
        payload = {
            "action": "plan_to_info",
            "target_infotype": "issues_list",
            "bindings": {
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name": ["bug"],
            },
        }
        llm = FakeLLMClient(json.dumps(payload))
        lookup = classify_intent_via_kg(
            "Go to bug issues in the current project", self.kg, llm,
        )
        self.assertIsNotNone(lookup)
        assert lookup is not None
        self.assertEqual(lookup.infotype, "issues_list")
        self.assertEqual(lookup.bindings.get("project_path"), "a11yproject/a11yproject.com")
        self.assertEqual(lookup.bindings.get("label_name"), ["bug"])

    def test_unknown_infotype_returns_none(self) -> None:
        payload = {
            "action": "plan_to_info",
            "target_infotype": "no_such_type",
            "bindings": {},
        }
        llm = FakeLLMClient(json.dumps(payload))
        self.assertIsNone(
            classify_intent_via_kg("whatever", self.kg, llm)
        )

    def test_llm_no_tool_call_returns_none(self) -> None:
        """FakeLLMClient가 'declare_error'를 쓰면 tool name이 plan_to_info가 아님 → None."""
        payload = {"action": "declare_error", "status": "UNKNOWN_ERROR", "reason": "x"}
        llm = FakeLLMClient(json.dumps(payload))
        self.assertIsNone(
            classify_intent_via_kg("whatever", self.kg, llm)
        )


class LoadKGContextTests(unittest.TestCase):
    def test_load_gitlab_returns_context(self) -> None:
        ctx = load_kg_context("gitlab", config_root=GITLAB_CONFIG_DIR.parent)
        self.assertIsNotNone(ctx)
        assert ctx is not None
        self.assertEqual(ctx.site_config.site, "gitlab")
        self.assertGreater(len(ctx.kg.infotypes), 0)

    def test_missing_site_returns_none(self) -> None:
        ctx = load_kg_context("nonexistent_site", config_root=GITLAB_CONFIG_DIR.parent)
        self.assertIsNone(ctx)


if __name__ == "__main__":
    unittest.main()
