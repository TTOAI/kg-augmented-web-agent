"""SiteKG types contract tests."""
from __future__ import annotations

import unittest
from dataclasses import fields

from site_adaptive_webagent.runtime.sitekg.types import (
    InteractionEdge,
    NavigationEdge,
    PageNode,
    SiteKG,
    WidgetNode,
)


class PageNodeTests(unittest.TestCase):
    def test_fields(self) -> None:
        self.assertEqual(
            {f.name for f in fields(PageNode)},
            {"page_node_id", "site_id", "page_key", "url_patterns", "structural_signals"},
        )

    def test_no_description_field(self) -> None:
        """minimum viable KG: description은 DOM에서 직접 가져오므로 KG에 박지 않는다."""
        field_names = {f.name for f in fields(PageNode)}
        self.assertNotIn("description", field_names)
        self.assertNotIn("display_name", field_names)


class WidgetNodeTests(unittest.TestCase):
    def test_fields(self) -> None:
        self.assertEqual(
            {f.name for f in fields(WidgetNode)},
            {
                "widget_node_id", "site_id", "page_key", "widget_key",
                "locator_strategy", "locator_value",
                "visibility_condition", "side_effects",
            },
        )

    def test_no_description_or_tags(self) -> None:
        """minimum viable KG: description/display_name/task_relevance_tags 폐기."""
        field_names = {f.name for f in fields(WidgetNode)}
        for forbidden in ("description", "display_name", "task_relevance_tags", "widget_type", "category"):
            self.assertNotIn(forbidden, field_names)


class NavigationEdgeTests(unittest.TestCase):
    def test_fields(self) -> None:
        self.assertEqual(
            {f.name for f in fields(NavigationEdge)},
            {"edge_id", "site_id", "source_page_key", "target_page_key", "trigger_widget_key"},
        )

    def test_no_description(self) -> None:
        field_names = {f.name for f in fields(NavigationEdge)}
        self.assertNotIn("description", field_names)


class InteractionEdgeTests(unittest.TestCase):
    def test_fields(self) -> None:
        self.assertEqual(
            {f.name for f in fields(InteractionEdge)},
            {"edge_id", "site_id", "page_key", "source_widget_key", "target_widget_key", "relation_type"},
        )

    def test_no_description(self) -> None:
        field_names = {f.name for f in fields(InteractionEdge)}
        self.assertNotIn("description", field_names)


class SiteKGTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sitekg = SiteKG(
            site_id="test",
            base_url="https://test.example.com",
            page_nodes=[
                PageNode(page_node_id="p1", site_id="test", page_key="dashboard"),
                PageNode(page_node_id="p2", site_id="test", page_key="issues"),
            ],
            widget_nodes=[
                WidgetNode(widget_node_id="w1", site_id="test", page_key="dashboard", widget_key="search"),
                WidgetNode(widget_node_id="w2", site_id="test", page_key="issues", widget_key="filter"),
                WidgetNode(widget_node_id="w3", site_id="test", page_key="issues", widget_key="sort"),
            ],
        )

    def test_get_page_node(self) -> None:
        self.assertEqual(self.sitekg.get_page_node("dashboard").page_node_id, "p1")
        self.assertIsNone(self.sitekg.get_page_node("nonexistent"))

    def test_get_widgets_for_page(self) -> None:
        widgets = self.sitekg.get_widgets_for_page("issues")
        self.assertEqual(len(widgets), 2)
        self.assertEqual({w.widget_key for w in widgets}, {"filter", "sort"})

    def test_page_keys(self) -> None:
        self.assertEqual(self.sitekg.page_keys(), {"dashboard", "issues"})

    def test_widget_keys_all(self) -> None:
        self.assertEqual(self.sitekg.widget_keys(), {"search", "filter", "sort"})

    def test_widget_keys_for_page(self) -> None:
        self.assertEqual(self.sitekg.widget_keys("dashboard"), {"search"})


if __name__ == "__main__":
    unittest.main()
