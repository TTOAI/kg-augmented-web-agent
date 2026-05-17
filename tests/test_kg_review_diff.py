"""kg.seed.review_diff 단위 테스트."""
from __future__ import annotations

import unittest

from kg_augmented_webagent.kg import (
    Action,
    LeadsToEdge,
    RealizesEdge,
    SiteKG,
    StatePattern,
)
from kg_augmented_webagent.kg.seed.review_diff import (
    diff_actions,
    diff_leads_to_edges,
    diff_realizes_edges,
    diff_state_patterns,
    render_markdown,
)


def _kg(site: str, source: str) -> SiteKG:
    return SiteKG(site=site)


class DiffStatePatternsTests(unittest.TestCase):
    def test_only_in_one_source_marked_correctly(self) -> None:
        m = _kg("x", "manual")
        m.state_patterns["m1"] = StatePattern(id="m1", url_template="/m", source="manual")
        c = _kg("x", "crawl")
        c.state_patterns["c1"] = StatePattern(id="c1", url_template="/c", source="crawl")
        l = _kg("x", "llm")
        # llm has no state patterns
        out = diff_state_patterns(m, c, l)
        keys = {e.key: e for e in out}
        self.assertTrue(keys["m1"].in_manual)
        self.assertFalse(keys["m1"].in_crawl)
        self.assertFalse(keys["m1"].in_llm)
        self.assertTrue(keys["c1"].in_crawl)
        self.assertFalse(keys["c1"].in_manual)

    def test_same_id_across_sources(self) -> None:
        m = _kg("x", "manual"); c = _kg("x", "crawl"); l = _kg("x", "llm")
        for kg, src in ((m, "manual"), (c, "crawl"), (l, "llm")):
            kg.state_patterns["shared"] = StatePattern(id="shared", url_template="/s", source=src)
        out = diff_state_patterns(m, c, l)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].in_manual and out[0].in_crawl and out[0].in_llm)


class DiffActionsTests(unittest.TestCase):
    def test_actions_union(self) -> None:
        m = _kg("x", "manual"); c = _kg("x", "crawl"); l = _kg("x", "llm")
        m.actions["a"] = Action(name="a", source="manual", description="manual one")
        c.actions["b"] = Action(name="b", source="crawl")
        l.actions["b"] = Action(name="b", source="llm", description="llm desc")
        out = diff_actions(m, c, l)
        keys = {e.key: e for e in out}
        self.assertEqual(set(keys), {"a", "b"})
        self.assertTrue(keys["b"].in_crawl and keys["b"].in_llm and not keys["b"].in_manual)


class DiffEdgesTests(unittest.TestCase):
    def test_realizes_edge_key_matches_merge(self) -> None:
        m = _kg("x", "manual")
        m.realizes_edges.append(
            RealizesEdge(infotype="i", state_pattern_id="p", condition="default", source="manual"),
        )
        c = _kg("x", "crawl")
        l = _kg("x", "llm")
        l.realizes_edges.append(
            RealizesEdge(infotype="i", state_pattern_id="p", condition="default", source="llm", trust="inferred"),
        )
        out = diff_realizes_edges(m, c, l)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].in_manual and not out[0].in_crawl and out[0].in_llm)

    def test_leads_to_edge_key_matches_merge(self) -> None:
        m = _kg("x", "manual")
        m.leads_to_edges.append(
            LeadsToEdge(from_state_pattern_id="a", action_name="go", to_state_pattern_id="b", source="manual"),
        )
        c = _kg("x", "crawl")
        c.leads_to_edges.append(
            LeadsToEdge(from_state_pattern_id="a", action_name="go", to_state_pattern_id="b", source="crawl", trust="verified"),
        )
        l = _kg("x", "llm")
        out = diff_leads_to_edges(m, c, l)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].in_manual and out[0].in_crawl)


class RenderMarkdownTests(unittest.TestCase):
    def test_render_includes_all_sections(self) -> None:
        m = _kg("x", "manual"); c = _kg("x", "crawl"); l = _kg("x", "llm")
        m.state_patterns["p"] = StatePattern(id="p", url_template="/p", source="manual")
        md = render_markdown(m, c, l)
        for section in ("StatePatterns", "Actions", "RealizesEdges", "LeadsToEdges"):
            self.assertIn(section, md)

    def test_empty_kgs_render_none_markers(self) -> None:
        empty = _kg("x", "manual")
        md = render_markdown(empty, empty, empty)
        self.assertIn("_(none)_", md)


if __name__ == "__main__":
    unittest.main()
