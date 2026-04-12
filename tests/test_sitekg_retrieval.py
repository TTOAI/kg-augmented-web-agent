"""retrieval tests — graph distance 기반 KG context 생성."""
from __future__ import annotations

import unittest

from site_adaptive_webagent.runtime.sitekg.retrieval import build_kg_context, _bfs_flat
from site_adaptive_webagent.runtime.sitekg.types import (
    NavigationEdge, PageNode, SiteKG, WidgetNode,
)


def _make_sitekg() -> SiteKG:
    return SiteKG(
        site_id="test",
        base_url="http://localhost",
        page_nodes=[
            PageNode(page_node_id="p1", site_id="test", page_key="dashboard",
                     url_patterns=["/", "/dashboard"]),
            PageNode(page_node_id="p2", site_id="test", page_key="issues",
                     url_patterns=["/-/issues"]),
            PageNode(page_node_id="p3", site_id="test", page_key="explore",
                     url_patterns=["/explore"]),
        ],
        widget_nodes=[
            WidgetNode(widget_node_id="w1", site_id="test", page_key="dashboard",
                       widget_key="search", locator_strategy="css", locator_value="#search"),
            WidgetNode(widget_node_id="w2", site_id="test", page_key="issues",
                       widget_key="label_filter", locator_strategy="css",
                       locator_value="input[placeholder*='Label']",
                       side_effects=["URL gains ?label_name[]=<value>"]),
            WidgetNode(widget_node_id="w3", site_id="test", page_key="explore",
                       widget_key="visibility_dropdown", locator_strategy="css",
                       locator_value="[data-testid='base-dropdown-toggle']",
                       side_effects=["opens dropdown"]),
        ],
        navigation_edges=[
            NavigationEdge(edge_id="e1", site_id="test",
                           source_page_key="dashboard", target_page_key="issues"),
            NavigationEdge(edge_id="e2", site_id="test",
                           source_page_key="dashboard", target_page_key="explore"),
        ],
    )


class BuildKgContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sitekg = _make_sitekg()

    def test_returns_string_for_matched_page(self) -> None:
        result = build_kg_context("http://localhost/dashboard", self.sitekg)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_unresolved_returns_empty(self) -> None:
        result = build_kg_context("http://localhost/unknown/path", self.sitekg)
        self.assertEqual(result, "")

    def test_includes_current_page_widgets(self) -> None:
        result = build_kg_context("http://localhost/dashboard", self.sitekg)
        self.assertIn("search", result)
        self.assertIn("#search", result)

    def test_includes_reachable_pages(self) -> None:
        result = build_kg_context("http://localhost/dashboard", self.sitekg)
        self.assertIn("issues", result)
        self.assertIn("explore", result)

    def test_includes_side_effects(self) -> None:
        result = build_kg_context("http://localhost/-/issues", self.sitekg)
        self.assertIn("label_name", result)

    def test_max_hops_limits_depth(self) -> None:
        # dashboard → issues (1 hop), dashboard → explore (1 hop)
        # From issues with max_hops=1: dashboard is reachable (bidirectional), explore is not
        result_1hop = build_kg_context("http://localhost/-/issues", self.sitekg, max_hops=1)
        self.assertIn("dashboard", result_1hop)
        # explore는 issues에서 2 hop (issues → dashboard → explore)
        # max_hops=1이면 explore 안 보임
        # 단, dashboard에서 explore로의 edge가 있으니 dashboard (1 hop)에서 explore (2 hop)
        result_0hop = build_kg_context("http://localhost/-/issues", self.sitekg, max_hops=0)
        self.assertNotIn("dashboard", result_0hop)
        self.assertNotIn("explore", result_0hop)


class BfsFlatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sitekg = _make_sitekg()

    def test_includes_start(self) -> None:
        result = _bfs_flat("dashboard", self.sitekg, max_hops=2)
        self.assertEqual(result["dashboard"], 0)

    def test_page_to_widget_1_hop(self) -> None:
        """page → widget (contains) = 1 hop."""
        result = _bfs_flat("dashboard", self.sitekg, max_hops=1)
        self.assertIn("search", result)  # dashboard의 widget
        self.assertEqual(result["search"], 1)

    def test_page_to_page_via_nav(self) -> None:
        result = _bfs_flat("dashboard", self.sitekg, max_hops=1)
        self.assertIn("issues", result)
        self.assertEqual(result["issues"], 1)

    def test_hop_limit(self) -> None:
        result = _bfs_flat("issues", self.sitekg, max_hops=0)
        self.assertEqual(len(result), 1)  # only issues itself

    def test_bidirectional(self) -> None:
        result = _bfs_flat("issues", self.sitekg, max_hops=1)
        self.assertIn("dashboard", result)

    def test_widget_to_page_contains(self) -> None:
        """widget → page (contains) = 1 hop."""
        result = _bfs_flat("search", self.sitekg, max_hops=1)
        self.assertIn("dashboard", result)
        self.assertEqual(result["dashboard"], 1)


if __name__ == "__main__":
    unittest.main()
