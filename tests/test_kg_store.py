"""kg.store 단위 테스트 — CRUD + validation + JSON round-trip."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from site_adaptive_webagent.kg import (
    Action,
    IdentityParam,
    InfoType,
    LeadsToEdge,
    RealizesEdge,
    SiteKG,
    StatePattern,
)
from site_adaptive_webagent.kg.seed import compute_source_mix
from site_adaptive_webagent.kg.store import SiteKGStore


def _make_minimal_kg() -> SiteKG:
    """최소 KG fixture: project_page + issues_list + issues_filtered."""
    kg = SiteKG(site="gitlab")
    kg.state_patterns["project_issues_list"] = StatePattern(
        id="project_issues_list",
        url_template="/{project_path}/-/issues",
        path_params={"project_path": {"type": "path_segments"}},
    )
    kg.state_patterns["project_issues_filtered"] = StatePattern(
        id="project_issues_filtered",
        url_template="/{project_path}/-/issues",
        path_params={"project_path": {"type": "path_segments"}},
        identity_query_params=[
            IdentityParam(name="state", type="enum", values=["opened", "closed", "all"], default="opened"),
            IdentityParam(name="label_name[]", type="multi_string", default=[]),
        ],
        canonical_emit_order=["state", "label_name[]"],
    )
    kg.actions["navigate_to"] = Action(name="navigate_to", params=[{"name": "url", "type": "string"}])
    kg.actions["apply_label_filter"] = Action(
        name="apply_label_filter", params=[{"name": "label", "type": "string"}]
    )
    it = InfoType(
        name="issues_list",
        description="Project-scoped issues list.",
        required_bindings=["project_path"],
        optional_bindings=["state", "label_name", "assignee_username"],
        realizes=[
            RealizesEdge(
                infotype="issues_list",
                state_pattern_id="project_issues_list",
                condition="default",
                binding_map={"project_path": "project_path"},
            ),
            RealizesEdge(
                infotype="issues_list",
                state_pattern_id="project_issues_filtered",
                condition="has_filter",
                binding_map={
                    "project_path": "project_path",
                    "state": "state",
                    "label_name": "label_name[]",
                },
            ),
        ],
        intent_examples=["List open issues", "Bug issues in project X"],
    )
    kg.infotypes["issues_list"] = it
    kg.realizes_edges.extend(it.realizes)
    kg.leads_to_edges.append(
        LeadsToEdge(
            from_state_pattern_id="project_issues_list",
            action_name="apply_label_filter",
            to_state_pattern_id="project_issues_filtered",
        )
    )
    return kg


class SiteKGStoreLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SiteKGStore(_make_minimal_kg())

    def test_get_state_pattern(self) -> None:
        sp = self.store.get_state_pattern("project_issues_filtered")
        self.assertIsNotNone(sp)
        assert sp is not None
        self.assertEqual(sp.id, "project_issues_filtered")

    def test_get_missing_state_pattern_returns_none(self) -> None:
        self.assertIsNone(self.store.get_state_pattern("nonexistent"))

    def test_get_infotype(self) -> None:
        it = self.store.get_infotype("issues_list")
        self.assertIsNotNone(it)
        assert it is not None
        self.assertEqual(it.name, "issues_list")
        self.assertEqual(len(it.realizes), 2)

    def test_realizes_edges_for_infotype(self) -> None:
        edges = self.store.realizes_edges_for("issues_list")
        self.assertEqual(len(edges), 2)
        conditions = {e.condition for e in edges}
        self.assertEqual(conditions, {"default", "has_filter"})

    def test_leads_to_edges_from_state(self) -> None:
        edges = self.store.leads_to_edges_from("project_issues_list")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].action_name, "apply_label_filter")


class SiteKGStoreMutationTests(unittest.TestCase):
    def test_add_state_pattern_ok(self) -> None:
        store = SiteKGStore(SiteKG(site="gitlab"))
        store.add_state_pattern(StatePattern(id="p1", url_template="/p1"))
        self.assertIsNotNone(store.get_state_pattern("p1"))

    def test_add_duplicate_state_pattern_raises(self) -> None:
        store = SiteKGStore(SiteKG(site="gitlab"))
        store.add_state_pattern(StatePattern(id="p1", url_template="/p1"))
        with self.assertRaises(ValueError):
            store.add_state_pattern(StatePattern(id="p1", url_template="/other"))

    def test_add_infotype_syncs_realizes_flat_list(self) -> None:
        store = SiteKGStore(SiteKG(site="gitlab"))
        store.add_state_pattern(StatePattern(id="p1", url_template="/p1"))
        it = InfoType(
            name="foo",
            realizes=[RealizesEdge(infotype="foo", state_pattern_id="p1", condition="default")],
        )
        store.add_infotype(it)
        self.assertEqual(len(store.kg.realizes_edges), 1)
        self.assertEqual(store.kg.realizes_edges[0].infotype, "foo")


class SiteKGStoreValidationTests(unittest.TestCase):
    def test_valid_kg_has_no_issues(self) -> None:
        store = SiteKGStore(_make_minimal_kg())
        self.assertEqual(store.validate(), [])

    def test_dangling_realizes_detected(self) -> None:
        kg = _make_minimal_kg()
        kg.realizes_edges.append(
            RealizesEdge(infotype="issues_list", state_pattern_id="missing_pattern", condition="default")
        )
        store = SiteKGStore(kg)
        issues = store.validate()
        self.assertTrue(any("missing_pattern" in i for i in issues))

    def test_dangling_leads_to_detected(self) -> None:
        kg = _make_minimal_kg()
        kg.leads_to_edges.append(
            LeadsToEdge(
                from_state_pattern_id="unknown_from",
                action_name="navigate_to",
                to_state_pattern_id="project_issues_list",
            )
        )
        store = SiteKGStore(kg)
        issues = store.validate()
        self.assertTrue(any("unknown_from" in i for i in issues))

    def test_unknown_action_in_edge_detected(self) -> None:
        kg = _make_minimal_kg()
        kg.leads_to_edges.append(
            LeadsToEdge(
                from_state_pattern_id="project_issues_list",
                action_name="nonexistent_action",
                to_state_pattern_id="project_issues_filtered",
            )
        )
        store = SiteKGStore(kg)
        issues = store.validate()
        self.assertTrue(any("nonexistent_action" in i for i in issues))


class SiteKGStoreJSONRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_state_patterns(self) -> None:
        original = SiteKGStore(_make_minimal_kg())
        data = original.to_json()
        restored = SiteKGStore.from_json(data)
        self.assertEqual(
            set(restored.kg.state_patterns.keys()),
            set(original.kg.state_patterns.keys()),
        )

    def test_round_trip_preserves_infotypes(self) -> None:
        original = SiteKGStore(_make_minimal_kg())
        data = original.to_json()
        restored = SiteKGStore.from_json(data)
        orig_it = original.get_infotype("issues_list")
        rest_it = restored.get_infotype("issues_list")
        assert orig_it is not None and rest_it is not None
        self.assertEqual(rest_it.name, orig_it.name)
        self.assertEqual(len(rest_it.realizes), len(orig_it.realizes))

    def test_round_trip_preserves_leads_to_edges(self) -> None:
        original = SiteKGStore(_make_minimal_kg())
        data = original.to_json()
        restored = SiteKGStore.from_json(data)
        self.assertEqual(len(restored.kg.leads_to_edges), len(original.kg.leads_to_edges))
        self.assertEqual(
            restored.kg.leads_to_edges[0].action_name,
            original.kg.leads_to_edges[0].action_name,
        )

    def test_save_and_load_file(self) -> None:
        original = SiteKGStore(_make_minimal_kg())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kg.json"
            original.save(path)
            # File contains expected keys
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["site"], "gitlab")
            self.assertIn("state_patterns", raw)
            self.assertIn("infotypes", raw)
            # Round-trip
            restored = SiteKGStore.load(path)
            self.assertEqual(restored.kg.site, "gitlab")
            self.assertIn("issues_list", restored.kg.infotypes)

    def test_restored_store_passes_validation(self) -> None:
        original = SiteKGStore(_make_minimal_kg())
        data = original.to_json()
        restored = SiteKGStore.from_json(data)
        self.assertEqual(restored.validate(), [])


class SiteKGStoreMergeTests(unittest.TestCase):
    """source 우선순위 기반 merge 정책 (crawl > manual > llm)."""

    def test_merge_crawl_overwrites_manual_on_same_id(self) -> None:
        base = SiteKG(site="gitlab")
        base.state_patterns["p1"] = StatePattern(id="p1", url_template="/old", source="manual")
        other = SiteKG(site="gitlab")
        other.state_patterns["p1"] = StatePattern(id="p1", url_template="/new", source="crawl")
        store = SiteKGStore(base)
        store.merge(other)
        self.assertEqual(store.kg.state_patterns["p1"].url_template, "/new")
        self.assertEqual(store.kg.state_patterns["p1"].source, "crawl")

    def test_merge_llm_does_not_overwrite_manual(self) -> None:
        base = SiteKG(site="gitlab")
        base.state_patterns["p1"] = StatePattern(id="p1", url_template="/manual", source="manual")
        other = SiteKG(site="gitlab")
        other.state_patterns["p1"] = StatePattern(id="p1", url_template="/llm", source="llm")
        store = SiteKGStore(base)
        store.merge(other)
        self.assertEqual(store.kg.state_patterns["p1"].url_template, "/manual")
        self.assertEqual(store.kg.state_patterns["p1"].source, "manual")

    def test_merge_adds_new_ids(self) -> None:
        base = SiteKG(site="gitlab")
        base.state_patterns["p1"] = StatePattern(id="p1", url_template="/one", source="manual")
        other = SiteKG(site="gitlab")
        other.state_patterns["p2"] = StatePattern(id="p2", url_template="/two", source="crawl")
        store = SiteKGStore(base)
        store.merge(other)
        self.assertIn("p1", store.kg.state_patterns)
        self.assertIn("p2", store.kg.state_patterns)

    def test_merge_updates_source_mix(self) -> None:
        base = SiteKG(site="gitlab")
        base.state_patterns["p1"] = StatePattern(id="p1", url_template="/a", source="manual")
        other = SiteKG(site="gitlab")
        other.state_patterns["p2"] = StatePattern(id="p2", url_template="/b", source="crawl")
        store = SiteKGStore(base)
        store.merge(other)
        self.assertEqual(store.kg.source_mix["manual"], 1)
        self.assertEqual(store.kg.source_mix["crawl"], 1)


class ComputeSourceMixTests(unittest.TestCase):
    def test_mix_counts_all_node_and_edge_sources(self) -> None:
        kg = _make_minimal_kg()  # 모두 default "manual"
        mix = compute_source_mix(kg)
        self.assertGreater(mix["manual"], 0)
        self.assertEqual(mix["crawl"], 0)
        self.assertEqual(mix["llm"], 0)

    def test_mix_reflects_mixed_sources(self) -> None:
        kg = SiteKG(site="gitlab")
        kg.state_patterns["a"] = StatePattern(id="a", url_template="/a", source="crawl")
        kg.state_patterns["b"] = StatePattern(id="b", url_template="/b", source="llm")
        kg.state_patterns["c"] = StatePattern(id="c", url_template="/c", source="manual")
        mix = compute_source_mix(kg)
        self.assertEqual(mix, {"crawl": 1, "llm": 1, "manual": 1})


class SiteKGStoreBuildMetadataTests(unittest.TestCase):
    def test_to_json_preserves_build_metadata(self) -> None:
        kg = _make_minimal_kg()
        kg.build_timestamp = "2026-04-16T00:00:00+00:00"
        kg.builder_version = "0.1.0-hybrid"
        kg.source_mix = {"crawl": 0, "llm": 0, "manual": 10}
        data = SiteKGStore(kg).to_json()
        self.assertEqual(data["build_timestamp"], "2026-04-16T00:00:00+00:00")
        self.assertEqual(data["builder_version"], "0.1.0-hybrid")
        self.assertEqual(data["source_mix"], {"crawl": 0, "llm": 0, "manual": 10})

    def test_from_json_restores_build_metadata(self) -> None:
        kg = _make_minimal_kg()
        kg.build_timestamp = "2026-04-16T00:00:00+00:00"
        kg.builder_version = "0.1.0-hybrid"
        kg.source_mix = {"crawl": 2, "llm": 1, "manual": 5}
        data = SiteKGStore(kg).to_json()
        restored = SiteKGStore.from_json(data).kg
        self.assertEqual(restored.build_timestamp, "2026-04-16T00:00:00+00:00")
        self.assertEqual(restored.builder_version, "0.1.0-hybrid")
        self.assertEqual(restored.source_mix, {"crawl": 2, "llm": 1, "manual": 5})


if __name__ == "__main__":
    unittest.main()
