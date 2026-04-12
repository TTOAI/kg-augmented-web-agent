"""seed_collector tests — helper 함수 + dump/load round-trip."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from site_adaptive_webagent.runtime.sitekg.seed_collector import (
    _diff_query_params,
    _looks_dynamic,
    _normalize_path,
    _path_to_page_key,
    _slugify,
    dump_yaml,
)
from site_adaptive_webagent.runtime.sitekg.seed_loader import load
from site_adaptive_webagent.runtime.sitekg.types import (
    NavigationEdge,
    PageNode,
    SiteKG,
    WidgetNode,
)


class NormalizePathTests(unittest.TestCase):
    def test_strips_trailing_slash(self) -> None:
        self.assertEqual(_normalize_path("http://localhost/issues/"), "/issues")

    def test_preserves_query(self) -> None:
        self.assertEqual(
            _normalize_path("http://localhost/explore?visibility_level=20"),
            "/explore?visibility_level=20",
        )

    def test_root(self) -> None:
        self.assertEqual(_normalize_path("http://localhost/"), "/")


class PathToPageKeyTests(unittest.TestCase):
    def test_simple(self) -> None:
        self.assertEqual(_path_to_page_key("/dashboard"), "dashboard")

    def test_nested(self) -> None:
        self.assertEqual(_path_to_page_key("/ns/project/-/issues"), "ns_project___issues")

    def test_root(self) -> None:
        self.assertEqual(_path_to_page_key("/"), "root")

    def test_query_stripped(self) -> None:
        self.assertEqual(_path_to_page_key("/explore?vis=20"), "explore")


class LooksDynamicTests(unittest.TestCase):
    def test_short_id_ok(self) -> None:
        self.assertFalse(_looks_dynamic("search-input"))

    def test_long_hash_dynamic(self) -> None:
        self.assertTrue(_looks_dynamic("ember123456789abcdef01234"))

    def test_mostly_digits_dynamic(self) -> None:
        self.assertTrue(_looks_dynamic("id_12345678"))


class SlugifyTests(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(_slugify("Clone with SSH"), "clone_with_ssh")

    def test_special_chars(self) -> None:
        self.assertEqual(_slugify("Sort direction: Ascending"), "sort_direction_ascending")

    def test_truncation(self) -> None:
        result = _slugify("a" * 100)
        self.assertLessEqual(len(result), 40)


class DiffQueryParamsTests(unittest.TestCase):
    def test_new_param(self) -> None:
        result = _diff_query_params(
            "http://localhost/issues",
            "http://localhost/issues?sort=desc",
        )
        self.assertEqual(result, "sort=desc")

    def test_no_diff(self) -> None:
        result = _diff_query_params(
            "http://localhost/issues?sort=desc",
            "http://localhost/issues?sort=desc",
        )
        self.assertEqual(result, "")

    def test_no_query_before(self) -> None:
        result = _diff_query_params(
            "http://localhost/explore",
            "http://localhost/explore?visibility_level=20",
        )
        self.assertIn("visibility_level=20", result)


class DumpYamlRoundTripTests(unittest.TestCase):
    def test_dump_and_reload(self) -> None:
        sitekg = SiteKG(
            site_id="test",
            base_url="http://localhost",
            page_nodes=[
                PageNode(page_node_id="p1", site_id="test", page_key="dashboard",
                         url_patterns=["/", "/dashboard"]),
                PageNode(page_node_id="p2", site_id="test", page_key="issues",
                         url_patterns=["/-/issues"]),
            ],
            widget_nodes=[
                WidgetNode(widget_node_id="w1", site_id="test", page_key="dashboard",
                           widget_key="search", locator_strategy="css",
                           locator_value="input[type='search']"),
                WidgetNode(widget_node_id="w2", site_id="test", page_key="issues",
                           widget_key="label_filter", locator_strategy="css",
                           locator_value="input[placeholder*='Label']",
                           side_effects=["URL gains ?label_name[]=<value>"]),
            ],
            navigation_edges=[
                NavigationEdge(edge_id="e1", site_id="test",
                               source_page_key="dashboard", target_page_key="issues"),
            ],
        )

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            dump_yaml(sitekg, f.name)
            reloaded = load(f.name)
            Path(f.name).unlink()

        self.assertEqual(reloaded.site_id, "test")
        self.assertEqual(len(reloaded.page_nodes), 2)
        self.assertEqual(len(reloaded.widget_nodes), 2)
        self.assertEqual(len(reloaded.navigation_edges), 1)

        lf = next(w for w in reloaded.widget_nodes if w.widget_key == "label_filter")
        self.assertEqual(len(lf.side_effects), 1)
        self.assertIn("label_name", lf.side_effects[0])


if __name__ == "__main__":
    unittest.main()
