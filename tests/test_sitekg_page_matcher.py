"""page_matcher tests — 5단계 deterministic matching."""
from __future__ import annotations

import unittest

from site_adaptive_webagent.runtime.sitekg.page_matcher import match_page_node
from site_adaptive_webagent.runtime.sitekg.types import PageNode, SiteKG


def _make_sitekg(*page_defs: tuple[str, list[str]]) -> SiteKG:
    """(page_key, url_patterns) 튜플로 SiteKG를 만든다."""
    return SiteKG(
        site_id="test",
        base_url="http://localhost:8023",
        page_nodes=[
            PageNode(page_node_id=f"p_{pk}", site_id="test", page_key=pk, url_patterns=patterns)
            for pk, patterns in page_defs
        ],
    )


class LiteralMatchTests(unittest.TestCase):
    def test_exact_match(self) -> None:
        sitekg = _make_sitekg(("dashboard", ["/", "/dashboard"]))
        result = match_page_node("http://localhost:8023/dashboard", sitekg)
        self.assertEqual(result.page_key, "dashboard")

    def test_root_match(self) -> None:
        sitekg = _make_sitekg(("dashboard", ["/", "/dashboard"]))
        result = match_page_node("http://localhost:8023/", sitekg)
        self.assertEqual(result.page_key, "dashboard")

    def test_trailing_slash_ignored(self) -> None:
        sitekg = _make_sitekg(("issues", ["/-/issues"]))
        result = match_page_node("http://localhost:8023/-/issues/", sitekg)
        self.assertEqual(result.page_key, "issues")


class PlaceholderMatchTests(unittest.TestCase):
    def test_single_placeholder(self) -> None:
        sitekg = _make_sitekg(("user_projects", ["/users/{user}/projects"]))
        result = match_page_node("http://localhost:8023/users/byteblaze/projects", sitekg)
        self.assertEqual(result.page_key, "user_projects")

    def test_multiple_placeholders(self) -> None:
        sitekg = _make_sitekg(("project_overview", ["/{ns}/{project}"]))
        result = match_page_node("http://localhost:8023/byteblaze/empathy-prompts", sitekg)
        self.assertEqual(result.page_key, "project_overview")

    def test_mixed_literal_and_placeholder(self) -> None:
        sitekg = _make_sitekg(("issues", ["/{ns}/{project}/-/issues"]))
        result = match_page_node("http://localhost:8023/a11y/a11y.com/-/issues", sitekg)
        self.assertEqual(result.page_key, "issues")


class SpecificityTiebreakTests(unittest.TestCase):
    def test_literal_beats_placeholder(self) -> None:
        sitekg = _make_sitekg(
            ("project_overview", ["/{ns}/{project}"]),
            ("issues", ["/{ns}/{project}/-/issues"]),
        )
        result = match_page_node("http://localhost:8023/a11y/a11y.com/-/issues", sitekg)
        self.assertEqual(result.page_key, "issues")

    def test_more_literals_wins(self) -> None:
        sitekg = _make_sitekg(
            ("commits", ["/{ns}/{project}/-/commits/{branch}"]),
            ("project_overview", ["/{ns}/{project}"]),
        )
        result = match_page_node("http://localhost:8023/ns/proj/-/commits/main", sitekg)
        self.assertEqual(result.page_key, "commits")


class QueryParamMatchTests(unittest.TestCase):
    def test_query_param_match(self) -> None:
        sitekg = _make_sitekg(
            ("explore", ["/explore"]),
            ("explore_public", ["/explore?visibility_level=20"]),
        )
        result = match_page_node("http://localhost:8023/explore?visibility_level=20", sitekg)
        self.assertEqual(result.page_key, "explore_public")

    def test_query_param_missing_falls_back(self) -> None:
        sitekg = _make_sitekg(
            ("explore", ["/explore"]),
            ("explore_public", ["/explore?visibility_level=20"]),
        )
        result = match_page_node("http://localhost:8023/explore", sitekg)
        self.assertEqual(result.page_key, "explore")


class UnresolvedTests(unittest.TestCase):
    def test_no_match_returns_unresolved(self) -> None:
        sitekg = _make_sitekg(("dashboard", ["/dashboard"]))
        result = match_page_node("http://localhost:8023/unknown/path", sitekg)
        self.assertEqual(result, "UNRESOLVED")

    def test_segment_count_mismatch(self) -> None:
        sitekg = _make_sitekg(("issues", ["/{ns}/{project}/-/issues"]))
        result = match_page_node("http://localhost:8023/just-one-segment", sitekg)
        self.assertEqual(result, "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
