"""Tests for kg_solution.path_finder."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from site_adaptive_webagent.kg.site_extras import load_site_cascade
from site_adaptive_webagent.kg.runtime.path_finder import (
    CascadeConfig,
    PathResult,
    extract_family,
    find_path,
)

# Phase 3.H Tier 2: DEFAULT_GITLAB_CONFIG 제거 — cascade.yaml에서 로드해 test에서 사용
_gitlab_cascade = load_site_cascade("gitlab")
GITLAB_CASCADE = CascadeConfig(
    scope_entries=dict(_gitlab_cascade.scope_entries),
    hub=_gitlab_cascade.hub,
)


class ExtractFamilyTests(unittest.TestCase):
    def test_issue_family(self):
        self.assertEqual(extract_family("project/issue_list"), "project/issue")
        self.assertEqual(extract_family("project/issue_detail"), "project/issue")
        self.assertEqual(extract_family("project/issue_new_form"), "project/issue")
        self.assertEqual(extract_family("project/issue_board"), "project/issue")
        self.assertEqual(extract_family("project/issue_feed"), "project/issue")

    def test_merge_request_family(self):
        self.assertEqual(
            extract_family("project/merge_request_list"), "project/merge_request"
        )
        self.assertEqual(
            extract_family("project/merge_request_new_form"),
            "project/merge_request",
        )
        self.assertEqual(
            extract_family("project/merge_request_edit_form"),
            "project/merge_request",
        )
        self.assertEqual(
            extract_family("project/merge_request_pipelines"),
            "project/merge_request",
        )

    def test_variant_strip(self):
        self.assertEqual(
            extract_family("dashboard/project_list/yours"),
            "dashboard/project",
        )
        self.assertEqual(
            extract_family("dashboard/project_list/starred"),
            "dashboard/project",
        )
        self.assertEqual(
            extract_family("dashboard/todo_list/pending"),
            "dashboard/todo",
        )
        self.assertEqual(
            extract_family("explore/project_list/all"),
            "explore/project",
        )

    def test_no_suffix(self):
        # class without a known suffix keeps base as-is
        self.assertEqual(extract_family("project/main"), "project/main")
        self.assertEqual(extract_family("user/profile"), "user/profile")


def _make_adj(edges: list[tuple[str, str, str]]) -> dict:
    """Build adjacency dict from (src, tgt, trust) triples."""
    adj: dict = {}
    for src, tgt, trust in edges:
        adj.setdefault(src, []).append(
            {"target": tgt, "actions": [f"to_{tgt}"], "trust": trust}
        )
    return adj


class FindPathExactStrategyTests(unittest.TestCase):
    def test_same_source_and_target(self):
        adj = _make_adj([("A", "B", "high")])
        result = find_path(adj, "A", "A", all_classes={"A", "B"})
        self.assertEqual(result.strategy, "exact")
        self.assertEqual(result.hops, 0)
        self.assertEqual(result.path, [])

    def test_direct_edge(self):
        adj = _make_adj([("A", "B", "high")])
        result = find_path(adj, "A", "B", all_classes={"A", "B"})
        self.assertEqual(result.strategy, "exact")
        self.assertEqual(result.hops, 1)
        assert result.path is not None
        self.assertEqual(result.path[0].source, "A")
        self.assertEqual(result.path[0].target, "B")

    def test_multi_hop(self):
        adj = _make_adj([
            ("A", "B", "high"),
            ("B", "C", "high"),
            ("C", "D", "high"),
        ])
        result = find_path(adj, "A", "D", all_classes={"A", "B", "C", "D"})
        self.assertEqual(result.strategy, "exact")
        self.assertEqual(result.hops, 3)

    def test_trust_tiebreak(self):
        # Two equal-length paths A→B→D and A→C→D; B has high trust, C has low.
        adj = _make_adj([
            ("A", "B", "high"),
            ("A", "C", "low"),
            ("B", "D", "high"),
            ("C", "D", "high"),
        ])
        result = find_path(adj, "A", "D", all_classes={"A", "B", "C", "D"})
        self.assertEqual(result.strategy, "exact")
        assert result.path is not None
        self.assertEqual(result.path[0].target, "B")  # high-trust preferred


class FindPathCascadeTests(unittest.TestCase):
    def test_family_sibling_when_target_unreachable(self):
        # Target project/issue_detail has no in-edges (unreachable), but
        # sibling project/issue_list IS reachable from A.
        adj = _make_adj([
            ("A", "project/issue_list", "high"),
        ])
        all_cls = {"A", "project/issue_list", "project/issue_detail"}
        result = find_path(
            adj, "A", "project/issue_detail", all_classes=all_cls
        )
        self.assertEqual(result.strategy, "family_sibling")
        self.assertEqual(result.actual_target, "project/issue_list")
        self.assertTrue(result.progress_checked)

    def test_scope_entry_when_family_fails(self):
        # Target unreachable and no family sibling available, but scope entry
        # project/main is reachable.
        config = CascadeConfig(
            scope_entries={"project": "project/main"}, hub="dashboard/hub"
        )
        adj = _make_adj([
            ("A", "project/main", "high"),
        ])
        all_cls = {"A", "project/main", "project/rare_page", "dashboard/hub"}
        result = find_path(
            adj, "A", "project/rare_page", all_classes=all_cls, config=config
        )
        self.assertEqual(result.strategy, "scope_entry")
        self.assertEqual(result.actual_target, "project/main")

    def test_hub_fallback_when_scope_entry_cannot_reach(self):
        # Target unreachable; configured scope entry is unreachable from A;
        # hub IS reachable.
        config = CascadeConfig(
            scope_entries={"project": "project/unreachable_entry"},
            hub="dashboard/hub",
        )
        adj = _make_adj([
            ("A", "dashboard/hub", "high"),
        ])
        all_cls = {"A", "dashboard/hub", "project/target",
                   "project/unreachable_entry"}
        result = find_path(
            adj, "A", "project/target", all_classes=all_cls, config=config
        )
        self.assertEqual(result.strategy, "hub_fallback")
        self.assertEqual(result.actual_target, "dashboard/hub")

    def test_stay_and_explore_when_nothing_helps(self):
        # No edges at all out of current; no cascade candidate is reachable.
        config = CascadeConfig(
            scope_entries={"project": "project/entry"}, hub="dashboard/hub"
        )
        adj = _make_adj([])  # empty graph
        all_cls = {"A", "project/target", "project/entry", "dashboard/hub"}
        result = find_path(
            adj, "A", "project/target", all_classes=all_cls, config=config
        )
        self.assertEqual(result.strategy, "stay_and_explore")
        self.assertEqual(result.actual_target, "A")

    def test_family_preferred_over_scope_when_both_reachable(self):
        # Family sibling and scope entry both reachable; family wins.
        config = CascadeConfig(
            scope_entries={"project": "project/main"}, hub="dashboard/hub"
        )
        adj = _make_adj([
            ("A", "project/issue_list", "high"),  # family sibling of target
            ("A", "project/main", "high"),        # scope entry
            ("A", "dashboard/hub", "high"),       # hub
        ])
        all_cls = {"A", "project/issue_list", "project/issue_detail",
                   "project/main", "dashboard/hub"}
        result = find_path(
            adj, "A", "project/issue_detail",
            all_classes=all_cls, config=config,
        )
        self.assertEqual(result.strategy, "family_sibling")


class FindPathInputValidationTests(unittest.TestCase):
    def test_unknown_current_returns_failed(self):
        adj = _make_adj([("A", "B", "high")])
        result = find_path(adj, "UNKNOWN", "B", all_classes={"A", "B"})
        self.assertEqual(result.strategy, "failed")

    def test_unknown_target_returns_failed(self):
        adj = _make_adj([("A", "B", "high")])
        result = find_path(adj, "A", "UNKNOWN", all_classes={"A", "B"})
        self.assertEqual(result.strategy, "failed")


class FindPathRealGraphTests(unittest.TestCase):
    """Sanity checks against the real Stage C edge graph."""

    @classmethod
    def setUpClass(cls):
        graph_path = (
            Path(__file__).resolve().parents[1]
            / "output" / "validation" / "stage_c" / "edge_graph.json"
        )
        if not graph_path.exists():
            raise unittest.SkipTest("edge_graph.json not present")
        data = json.loads(graph_path.read_text(encoding="utf-8"))
        cls.adj = data["adjacency"]
        cls.all_classes = set(
            list(cls.adj.keys()) + [e["target"] for e in data["edges"]]
        )

    def test_dashboard_to_issue_detail_exact(self):
        result = find_path(
            self.adj,
            "dashboard/project_list/yours",
            "project/issue_detail",
            all_classes=self.all_classes,
        )
        self.assertEqual(result.strategy, "exact")
        self.assertGreater(result.hops, 0)

    def test_account_to_project_main_reachable(self):
        result = find_path(
            self.adj,
            "account/account",
            "project/main",
            all_classes=self.all_classes,
        )
        self.assertEqual(result.strategy, "exact")


if __name__ == "__main__":
    unittest.main()
