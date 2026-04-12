"""seed_loader tests — YAML 로딩 + 참조 무결성."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from site_adaptive_webagent.runtime.sitekg.seed_loader import SeedValidationError, load


VALID_SEED = """\
site_id: test_site
base_url: https://test.example.com

page_nodes:
  - page_key: dashboard
    url_patterns: ["/", "/dashboard"]
  - page_key: issues
    url_patterns: ["/-/issues"]

widget_nodes:
  - widget_key: search
    page_key: dashboard
    locator_strategy: css
    locator_value: 'input[type="search"]'
  - widget_key: label_filter
    page_key: issues
    locator_strategy: css
    locator_value: 'input[placeholder*="Label"]'
    side_effects:
      - "URL gains ?label_name[]=<value>"

navigation_edges:
  - source_page_key: dashboard
    target_page_key: issues
    trigger_widget_key: issues_link

interaction_edges:
  - page_key: issues
    source_widget_key: label_filter
    target_widget_key: label_filter
    relation_type: self_submit
"""


class LoadValidSeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        self.tmpfile.write(VALID_SEED)
        self.tmpfile.close()
        self.sitekg = load(self.tmpfile.name)

    def tearDown(self) -> None:
        Path(self.tmpfile.name).unlink(missing_ok=True)

    def test_site_id(self) -> None:
        self.assertEqual(self.sitekg.site_id, "test_site")

    def test_page_nodes_count(self) -> None:
        self.assertEqual(len(self.sitekg.page_nodes), 2)

    def test_widget_nodes_count(self) -> None:
        self.assertEqual(len(self.sitekg.widget_nodes), 2)

    def test_widget_has_no_description(self) -> None:
        for w in self.sitekg.widget_nodes:
            self.assertFalse(hasattr(w, "description"))

    def test_navigation_edges(self) -> None:
        self.assertEqual(len(self.sitekg.navigation_edges), 1)
        self.assertEqual(self.sitekg.navigation_edges[0].source_page_key, "dashboard")

    def test_side_effects_loaded(self) -> None:
        lf = next(w for w in self.sitekg.widget_nodes if w.widget_key == "label_filter")
        self.assertEqual(len(lf.side_effects), 1)
        self.assertIn("label_name", lf.side_effects[0])

    def test_auto_generates_ids(self) -> None:
        for pn in self.sitekg.page_nodes:
            self.assertTrue(len(pn.page_node_id) > 0)


class ValidationErrorTests(unittest.TestCase):
    def _load_yaml(self, content: str):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.close()
            try:
                return load(f.name)
            finally:
                Path(f.name).unlink(missing_ok=True)

    def test_widget_references_nonexistent_page(self) -> None:
        bad = """\
site_id: test
page_nodes:
  - page_key: dashboard
widget_nodes:
  - widget_key: w1
    page_key: nonexistent
"""
        with self.assertRaises(SeedValidationError) as ctx:
            self._load_yaml(bad)
        self.assertIn("nonexistent", str(ctx.exception))

    def test_nav_edge_references_nonexistent_page(self) -> None:
        bad = """\
site_id: test
page_nodes:
  - page_key: dashboard
navigation_edges:
  - source_page_key: dashboard
    target_page_key: nonexistent
"""
        with self.assertRaises(SeedValidationError) as ctx:
            self._load_yaml(bad)
        self.assertIn("nonexistent", str(ctx.exception))

    def test_interaction_edge_references_nonexistent_widget(self) -> None:
        bad = """\
site_id: test
page_nodes:
  - page_key: dashboard
widget_nodes:
  - widget_key: w1
    page_key: dashboard
interaction_edges:
  - page_key: dashboard
    source_widget_key: w1
    target_widget_key: nonexistent
"""
        with self.assertRaises(SeedValidationError) as ctx:
            self._load_yaml(bad)
        self.assertIn("nonexistent", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
