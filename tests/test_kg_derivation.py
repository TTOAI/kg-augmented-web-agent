"""kg.seed.llm_derivation + derivation_to_kg offline 테스트.

LLM 호출은 FakeLLMClient mock으로 대체 (실호출 없음).
"""
from __future__ import annotations

import json
import unittest

from site_adaptive_webagent.kg import (
    Action,
    SiteKG,
    StatePattern,
)
from site_adaptive_webagent.kg.seed.crawl_to_kg import crawl_results_to_sitekg
from site_adaptive_webagent.kg.seed.derivation_to_kg import derivation_to_sitekg
from site_adaptive_webagent.kg.seed.llm_derivation import (
    DerivationResult,
    build_derivation_system_prompt,
    build_derive_kg_tool,
    derive_infotypes_and_actions,
)
from site_adaptive_webagent.kg.seed.playwright_crawler import (
    CrawlResult,
    FormElementMeta,
)
from site_adaptive_webagent.kg.store import SiteKGStore
from site_adaptive_webagent.kg.types import SiteConfig

from .fixtures import FakeLLMClient


def _sample_crawl_kg() -> tuple[list[CrawlResult], SiteKG]:
    """작은 crawl 산출물 (StatePattern 2 + form Action 1)."""
    cfg = SiteConfig(site="example")
    results = [
        CrawlResult(
            url="http://x/dashboard",
            normalized_url_template="/dashboard",
            query_params_seen=["state"],
        ),
        CrawlResult(
            url="http://x/foo/-/issues",
            normalized_url_template="/{slot_0}/-/issues",
            query_params_seen=["state", "label_name[]"],
            parent_url="http://x/dashboard",
            form_elements=[
                FormElementMeta(name="title", type="text", action_url="/foo/-/issues/new"),
            ],
        ),
    ]
    crawl_kg = crawl_results_to_sitekg(results, cfg, site="example")
    return results, crawl_kg


def _make_valid_response(crawl_kg: SiteKG) -> str:
    """LLM이 valid한 derive_kg 호출을 한 척하는 JSON 응답.

    state_pattern_groups: 각 crawl StatePattern을 자기 자신이 유일한 member인
    그룹으로 간단히 묶음 (테스트 편의).
    """
    pattern_ids = list(crawl_kg.state_patterns.keys())
    form_action_name = next(
        (n for n in crawl_kg.actions if n.startswith("crawl:form:")),
        "crawl:form:_:title",
    )
    groups = []
    for sp_id in pattern_ids:
        sp = crawl_kg.state_patterns[sp_id]
        groups.append({
            "semantic_template": sp.url_template,
            "path_params": dict(sp.path_params),
            "member_ids": [sp_id],
            "reasoning": "unit test group",
        })
    return json.dumps({
        "action": "derive_kg",
        "state_pattern_groups": groups,
        "infotypes": [
            {
                "name": "site_dashboard",
                "description": "Top-level dashboard",
                "required_bindings": [],
                "optional_bindings": ["state"],
                "intent_examples": ["Open my dashboard"],
                "realizes": [
                    {
                        "state_pattern_id": pattern_ids[0],
                        "condition": "default",
                        "binding_map": {},
                    },
                ],
            },
            {
                "name": "project_issues_list",
                "description": "Per-project issues list",
                "required_bindings": ["project_path"],
                "optional_bindings": ["state", "label_name"],
                "intent_examples": [],
                "realizes": [
                    {
                        "state_pattern_id": pattern_ids[1],
                        "condition": "has_filter",
                        "binding_map": {"project_path": "slot_0"},
                    },
                ],
            },
        ],
        "action_renames": [
            {
                "original_name": form_action_name,
                "semantic_name": "create_issue",
                "description": "Submit new issue form",
            },
        ],
    })


# ---------------------------------------------------------------------------
# build_derive_kg_tool / build_derivation_system_prompt
# ---------------------------------------------------------------------------

class BuildDeriveKgToolTests(unittest.TestCase):
    def test_tool_has_required_fields(self) -> None:
        tool = build_derive_kg_tool()
        self.assertEqual(tool["name"], "derive_kg")
        schema = tool["input_schema"]
        self.assertIn("infotypes", schema["properties"])
        self.assertIn("action_renames", schema["properties"])
        self.assertIn("state_pattern_groups", schema["properties"])
        self.assertEqual(
            set(schema["required"]),
            {"state_pattern_groups", "infotypes", "action_renames"},
        )


class BuildSystemPromptTests(unittest.TestCase):
    def test_prompt_lists_observed_state_patterns(self) -> None:
        results, kg = _sample_crawl_kg()
        prompt = build_derivation_system_prompt(kg, results)
        for sp_id in kg.state_patterns:
            self.assertIn(sp_id, prompt)

    def test_prompt_lists_observed_actions(self) -> None:
        results, kg = _sample_crawl_kg()
        prompt = build_derivation_system_prompt(kg, results)
        for act_name in kg.actions:
            self.assertIn(act_name, prompt)


# ---------------------------------------------------------------------------
# derive_infotypes_and_actions
# ---------------------------------------------------------------------------

class DeriveInfoTypesAndActionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.results, self.crawl_kg = _sample_crawl_kg()

    def test_valid_response_parsed_into_infotypes(self) -> None:
        llm = FakeLLMClient(_make_valid_response(self.crawl_kg))
        result = derive_infotypes_and_actions(self.results, self.crawl_kg, llm)
        names = {it.name for it in result.infotypes}
        self.assertEqual(names, {"site_dashboard", "project_issues_list"})
        for it in result.infotypes:
            self.assertEqual(it.source, "llm")
            self.assertEqual(it.trust_label, "inferred")

    def test_valid_response_parses_action_rename_map(self) -> None:
        llm = FakeLLMClient(_make_valid_response(self.crawl_kg))
        result = derive_infotypes_and_actions(self.results, self.crawl_kg, llm)
        self.assertEqual(len(result.action_name_map), 1)
        semantic = next(iter(result.action_name_map.values()))
        self.assertEqual(semantic, "create_issue")
        self.assertIn("create_issue", result.actions)
        self.assertEqual(result.actions["create_issue"].source, "llm")

    def test_no_tool_call_returns_empty(self) -> None:
        # FakeLLMClient는 'action' 필드를 tool_name으로 사용한다. 다른 이름이면 매칭 안 됨.
        llm = FakeLLMClient(json.dumps({"action": "something_else"}))
        result = derive_infotypes_and_actions(self.results, self.crawl_kg, llm)
        self.assertEqual(result.infotypes, [])
        self.assertEqual(result.action_name_map, {})

    def test_llm_exception_returns_empty(self) -> None:
        class RaisingClient:
            def complete_with_tools(self, *, system, messages, tools):
                raise RuntimeError("network down")
        result = derive_infotypes_and_actions(self.results, self.crawl_kg, RaisingClient())
        self.assertEqual(result.infotypes, [])
        # prompt는 보존돼야 (재현성)
        self.assertGreater(len(result.prompt), 0)

    def test_empty_crawl_kg_skips_llm(self) -> None:
        empty_kg = SiteKG(site="example")
        llm = FakeLLMClient("{}")
        result = derive_infotypes_and_actions([], empty_kg, llm)
        self.assertEqual(result.infotypes, [])
        # LLM 호출 안 함
        self.assertEqual(len(llm.calls), 0)

    def test_realizes_with_unknown_state_pattern_kept_in_raw_but_filtered_at_kg_step(self) -> None:
        """derive 단계에선 그대로 두고, derivation_to_sitekg가 filter."""
        bad = json.dumps({
            "action": "derive_kg",
            "infotypes": [
                {
                    "name": "x",
                    "description": "y",
                    "realizes": [{"state_pattern_id": "nonexistent_id"}],
                },
            ],
            "action_renames": [],
        })
        llm = FakeLLMClient(bad)
        result = derive_infotypes_and_actions(self.results, self.crawl_kg, llm)
        # derive 단계에선 RealizesEdge 객체 자체는 만들어둠
        self.assertEqual(len(result.infotypes), 1)
        self.assertEqual(result.infotypes[0].realizes[0].state_pattern_id, "nonexistent_id")


# ---------------------------------------------------------------------------
# derivation_to_sitekg
# ---------------------------------------------------------------------------

class DerivationToSiteKGTests(unittest.TestCase):
    def setUp(self) -> None:
        self.results, self.crawl_kg = _sample_crawl_kg()
        self.llm = FakeLLMClient(_make_valid_response(self.crawl_kg))
        self.derivation = derive_infotypes_and_actions(
            self.results, self.crawl_kg, self.llm,
        )

    def test_creates_llm_sitekg_with_infotypes(self) -> None:
        derived = derivation_to_sitekg(self.derivation, self.crawl_kg)
        self.assertEqual(len(derived.infotypes), 2)
        for it in derived.infotypes.values():
            self.assertEqual(it.source, "llm")

    def test_renames_action_in_actions_dict(self) -> None:
        derived = derivation_to_sitekg(self.derivation, self.crawl_kg)
        self.assertIn("create_issue", derived.actions)
        # crawl:form:* 원본 이름은 derived KG에 없음 (rename됨)
        for n in derived.actions:
            self.assertFalse(n.startswith("crawl:form:"), n)

    def test_unknown_state_pattern_realizes_filtered(self) -> None:
        bad = DerivationResult(
            infotypes=self.derivation.infotypes
            + [
                __import__(
                    "site_adaptive_webagent.kg.types", fromlist=["InfoType"],
                ).InfoType(
                    name="orphan",
                    realizes=[
                        __import__(
                            "site_adaptive_webagent.kg.types", fromlist=["RealizesEdge"],
                        ).RealizesEdge(
                            infotype="orphan",
                            state_pattern_id="missing_id_xyz",
                            trust="inferred",
                            source="llm",
                        ),
                    ],
                    source="llm",
                    trust_label="inferred",
                ),
            ],
            action_name_map=self.derivation.action_name_map,
            actions=self.derivation.actions,
        )
        derived = derivation_to_sitekg(bad, self.crawl_kg)
        # orphan InfoType은 살아 있되 realizes는 비어있음 (filter됨)
        self.assertIn("orphan", derived.infotypes)
        self.assertEqual(derived.infotypes["orphan"].realizes, [])

    def test_unknown_action_in_rename_map_is_skipped(self) -> None:
        broken = DerivationResult(
            infotypes=[],
            action_name_map={"crawl:form:nonexistent": "do_x"},
            actions={"do_x": Action(name="do_x", source="llm")},
        )
        derived = derivation_to_sitekg(broken, self.crawl_kg)
        self.assertNotIn("do_x", derived.actions)


# ---------------------------------------------------------------------------
# Merge: manual + crawl + llm
# ---------------------------------------------------------------------------

class MergeManualCrawlLlmTests(unittest.TestCase):
    def test_three_layer_merge_yields_all_sources_in_mix(self) -> None:
        manual = SiteKG(site="example")
        manual.state_patterns["manual_p"] = StatePattern(
            id="manual_p", url_template="/m", source="manual",
        )
        results, crawl_kg = _sample_crawl_kg()
        llm = FakeLLMClient(_make_valid_response(crawl_kg))
        derivation = derive_infotypes_and_actions(results, crawl_kg, llm)
        derived = derivation_to_sitekg(derivation, crawl_kg)

        store = SiteKGStore(manual)
        store.merge(crawl_kg)
        store.merge(derived)
        mix = store.kg.source_mix
        self.assertGreater(mix["manual"], 0)
        self.assertGreater(mix["crawl"], 0)
        self.assertGreater(mix["llm"], 0)


class StatePatternGroupingTests(unittest.TestCase):
    """M4-B 확장: LLM grouping → llm StatePattern 승격 + realizes/leads_to id resolve."""

    def _make_crawl_kg_with_n_patterns(self, n: int) -> SiteKG:
        kg = SiteKG(site="x")
        from site_adaptive_webagent.kg import StatePattern as SP
        for i in range(n):
            sp_id = f"crawl:proj{i}_issues"
            kg.state_patterns[sp_id] = SP(
                id=sp_id,
                url_template=f"/proj{i}/-/issues",
                source="crawl",
            )
        return kg

    def test_single_group_merges_members_into_one_state_pattern(self) -> None:
        crawl_kg = self._make_crawl_kg_with_n_patterns(3)
        response = json.dumps({
            "action": "derive_kg",
            "state_pattern_groups": [
                {
                    "semantic_template": "/{project_path}/-/issues",
                    "path_params": {"project_path": {"type": "path_segments"}},
                    "member_ids": list(crawl_kg.state_patterns.keys()),
                    "reasoning": "all share same /-/issues tail",
                },
            ],
            "infotypes": [],
            "action_renames": [],
        })
        result = derive_infotypes_and_actions([], crawl_kg, FakeLLMClient(response))
        self.assertEqual(len(result.state_pattern_groups), 1)
        self.assertEqual(len(result.state_pattern_groups[0].member_ids), 3)
        derived = derivation_to_sitekg(result, crawl_kg)
        self.assertEqual(len(derived.state_patterns), 1)
        sp = next(iter(derived.state_patterns.values()))
        self.assertTrue(sp.id.startswith("llm:"))
        self.assertEqual(sp.url_template, "/{project_path}/-/issues")
        self.assertEqual(sp.source, "llm")
        self.assertEqual(sp.url_template_trust, "inferred")

    def test_group_member_ids_with_unknown_crawl_id_filtered(self) -> None:
        crawl_kg = self._make_crawl_kg_with_n_patterns(2)
        response = json.dumps({
            "action": "derive_kg",
            "state_pattern_groups": [
                {
                    "semantic_template": "/{x}/-/issues",
                    "member_ids": list(crawl_kg.state_patterns.keys()) + ["crawl:nonexistent"],
                },
            ],
            "infotypes": [],
            "action_renames": [],
        })
        result = derive_infotypes_and_actions([], crawl_kg, FakeLLMClient(response))
        # nonexistent는 filter됨
        self.assertEqual(len(result.state_pattern_groups[0].member_ids), 2)

    def test_infotype_realizes_crawl_member_resolves_to_group_id(self) -> None:
        crawl_kg = self._make_crawl_kg_with_n_patterns(2)
        crawl_ids = list(crawl_kg.state_patterns.keys())
        response = json.dumps({
            "action": "derive_kg",
            "state_pattern_groups": [
                {
                    "semantic_template": "/{project_path}/-/issues",
                    "member_ids": crawl_ids,
                },
            ],
            "infotypes": [
                {
                    "name": "project_issues_list",
                    "description": "",
                    "realizes": [{"state_pattern_id": crawl_ids[0]}],
                },
            ],
            "action_renames": [],
        })
        result = derive_infotypes_and_actions([], crawl_kg, FakeLLMClient(response))
        derived = derivation_to_sitekg(result, crawl_kg)
        it = derived.infotypes["project_issues_list"]
        self.assertEqual(len(it.realizes), 1)
        # crawl id가 아닌 llm: group id로 교체돼야
        self.assertTrue(it.realizes[0].state_pattern_id.startswith("llm:"))
        self.assertIn(it.realizes[0].state_pattern_id, derived.state_patterns)

    def test_group_reasoning_preserved_in_derivation_result(self) -> None:
        crawl_kg = self._make_crawl_kg_with_n_patterns(1)
        response = json.dumps({
            "action": "derive_kg",
            "state_pattern_groups": [
                {
                    "semantic_template": "/{x}/-/issues",
                    "member_ids": list(crawl_kg.state_patterns.keys()),
                    "reasoning": "audit trail text",
                },
            ],
            "infotypes": [],
            "action_renames": [],
        })
        result = derive_infotypes_and_actions([], crawl_kg, FakeLLMClient(response))
        self.assertEqual(result.state_pattern_groups[0].reasoning, "audit trail text")

    def test_no_groups_yields_empty_derived_state_patterns(self) -> None:
        """LLM이 grouping을 거부하면 derived SiteKG에 StatePattern 없음 (realizes도 skip)."""
        crawl_kg = self._make_crawl_kg_with_n_patterns(2)
        response = json.dumps({
            "action": "derive_kg",
            "state_pattern_groups": [],
            "infotypes": [
                {
                    "name": "x",
                    "description": "",
                    "realizes": [{"state_pattern_id": list(crawl_kg.state_patterns.keys())[0]}],
                },
            ],
            "action_renames": [],
        })
        result = derive_infotypes_and_actions([], crawl_kg, FakeLLMClient(response))
        derived = derivation_to_sitekg(result, crawl_kg)
        self.assertEqual(len(derived.state_patterns), 0)
        self.assertIn("x", derived.infotypes)
        # realizes는 resolve 실패해 skip됨
        self.assertEqual(derived.infotypes["x"].realizes, [])

    def test_compression_scale_thousand_to_one(self) -> None:
        """1,000 crawl StatePattern이 단일 group으로 묶이는 시나리오 smoke."""
        crawl_kg = self._make_crawl_kg_with_n_patterns(1000)
        response = json.dumps({
            "action": "derive_kg",
            "state_pattern_groups": [
                {
                    "semantic_template": "/{project_path}/-/issues",
                    "member_ids": list(crawl_kg.state_patterns.keys()),
                },
            ],
            "infotypes": [],
            "action_renames": [],
        })
        result = derive_infotypes_and_actions([], crawl_kg, FakeLLMClient(response))
        derived = derivation_to_sitekg(result, crawl_kg)
        self.assertEqual(len(derived.state_patterns), 1)


if __name__ == "__main__":
    unittest.main()
