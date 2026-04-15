"""kg.seed.playwright_crawler + crawl_to_kg offline 단위 테스트.

실제 Playwright 호출은 RUN_LIVE_CRAWL 환경변수 있을 때만 (CI 기본 비활성).
"""
from __future__ import annotations

import os
import unittest

from site_adaptive_webagent.kg import (
    SiteConfig,
    SiteKG,
    StatePattern,
)
from site_adaptive_webagent.kg.seed import (
    CrawlResult,
    FormElementMeta,
    crawl_results_to_sitekg,
    crawl_site,
    extract_url_template,
)
from site_adaptive_webagent.kg.store import SiteKGStore


def _gitlab_like_config() -> SiteConfig:
    return SiteConfig(
        site="gitlab",
        base_url="http://localhost:8023",
        url_decode=True,
        trailing_slash_ignore=True,
        strip_fragment=True,
    )


# ---------------------------------------------------------------------------
# extract_url_template
# ---------------------------------------------------------------------------

class ExtractUrlTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = _gitlab_like_config()

    def test_single_url_returns_path_no_slot(self) -> None:
        t, params = extract_url_template(["/dashboard"], self.cfg)
        self.assertEqual(t, "/dashboard")
        self.assertEqual(params, {})

    def test_two_urls_with_one_varying_segment_extracts_slot(self) -> None:
        t, params = extract_url_template(
            ["/foo/-/issues", "/baz/-/issues"], self.cfg,
        )
        self.assertEqual(t, "/{slot_0}/-/issues")
        self.assertIn("slot_0", params)
        self.assertEqual(params["slot_0"]["type"], "segment")

    def test_two_urls_with_multiple_varying_segments(self) -> None:
        t, params = extract_url_template(
            ["/a/b/-/issues", "/c/d/-/issues"], self.cfg,
        )
        self.assertEqual(t, "/{slot_0}/{slot_1}/-/issues")
        self.assertEqual(set(params), {"slot_0", "slot_1"})

    def test_identical_paths_yield_no_slots(self) -> None:
        t, params = extract_url_template(
            ["/dashboard", "/dashboard"], self.cfg,
        )
        self.assertEqual(t, "/dashboard")
        self.assertEqual(params, {})

    def test_different_path_lengths_falls_back_to_shortest(self) -> None:
        t, params = extract_url_template(
            ["/a/b", "/x/y/z"], self.cfg,
        )
        # 길이 다르면 일반화 어려움 → 짧은 path 그대로
        self.assertIn(t, ("/a/b", "/x/y/z"))
        self.assertEqual(params, {})

    def test_empty_input_returns_empty(self) -> None:
        t, params = extract_url_template([], self.cfg)
        self.assertEqual(t, "")
        self.assertEqual(params, {})


# ---------------------------------------------------------------------------
# crawl_results_to_sitekg
# ---------------------------------------------------------------------------

class CrawlResultsToSiteKGTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = _gitlab_like_config()

    def test_single_crawl_result_creates_one_state_pattern(self) -> None:
        results = [
            CrawlResult(
                url="http://x/dashboard",
                normalized_url_template="/dashboard",
            ),
        ]
        kg = crawl_results_to_sitekg(results, self.cfg, site="gitlab")
        self.assertEqual(len(kg.state_patterns), 1)
        sp = next(iter(kg.state_patterns.values()))
        self.assertEqual(sp.url_template, "/dashboard")
        self.assertEqual(sp.source, "crawl")
        self.assertEqual(sp.url_template_trust, "verified")
        self.assertTrue(sp.id.startswith("crawl:"))

    def test_state_pattern_id_uses_crawl_prefix(self) -> None:
        """manual seed와 충돌 회피를 위한 id 규약."""
        results = [CrawlResult(url="http://x/a", normalized_url_template="/a")]
        kg = crawl_results_to_sitekg(results, self.cfg)
        for sp_id in kg.state_patterns:
            self.assertTrue(sp_id.startswith("crawl:"), sp_id)

    def test_multiple_results_same_template_collapse(self) -> None:
        results = [
            CrawlResult(url="http://x/foo/-/issues", normalized_url_template="/{slot_0}/-/issues"),
            CrawlResult(url="http://x/bar/-/issues", normalized_url_template="/{slot_0}/-/issues"),
        ]
        kg = crawl_results_to_sitekg(results, self.cfg)
        self.assertEqual(len(kg.state_patterns), 1)

    def test_query_params_become_identity_params(self) -> None:
        results = [
            CrawlResult(
                url="http://x/dashboard",
                normalized_url_template="/dashboard",
                query_params_seen=["state", "label_name[]"],
            ),
        ]
        kg = crawl_results_to_sitekg(results, self.cfg)
        sp = next(iter(kg.state_patterns.values()))
        names = {p.name for p in sp.identity_query_params}
        self.assertEqual(names, {"state", "label_name[]"})
        for p in sp.identity_query_params:
            self.assertEqual(p.type, "string")  # crawler는 type 추론 안 함

    def test_parent_to_child_creates_leads_to_edge(self) -> None:
        results = [
            CrawlResult(url="http://x/a", normalized_url_template="/a"),
            CrawlResult(
                url="http://x/b",
                normalized_url_template="/b",
                parent_url="http://x/a",
            ),
        ]
        kg = crawl_results_to_sitekg(results, self.cfg)
        self.assertEqual(len(kg.leads_to_edges), 1)
        edge = kg.leads_to_edges[0]
        self.assertEqual(edge.action_name, "crawl:nav")
        self.assertEqual(edge.source, "crawl")
        self.assertEqual(edge.trust, "verified")

    def test_self_transition_skipped(self) -> None:
        """같은 template 내 link은 leads_to로 만들지 않음."""
        results = [
            CrawlResult(url="http://x/a", normalized_url_template="/a"),
            CrawlResult(url="http://x/a?p=1", normalized_url_template="/a", parent_url="http://x/a"),
        ]
        kg = crawl_results_to_sitekg(results, self.cfg)
        self.assertEqual(len(kg.leads_to_edges), 0)

    def test_form_elements_become_actions(self) -> None:
        results = [
            CrawlResult(
                url="http://x/new",
                normalized_url_template="/new",
                form_elements=[
                    FormElementMeta(name="title", type="text", action_url="/new"),
                ],
            ),
        ]
        kg = crawl_results_to_sitekg(results, self.cfg)
        # 단일 nav action은 없어야 함 (parent_url 없음)
        self.assertEqual(len(kg.leads_to_edges), 0)
        # form action 1개
        form_actions = [n for n in kg.actions if n.startswith("crawl:form:")]
        self.assertEqual(len(form_actions), 1)
        self.assertEqual(kg.actions[form_actions[0]].source, "crawl")

    def test_failed_status_skipped(self) -> None:
        results = [
            CrawlResult(url="http://x/a", normalized_url_template="/a", http_status=404),
        ]
        kg = crawl_results_to_sitekg(results, self.cfg)
        self.assertEqual(len(kg.state_patterns), 0)

    def test_empty_input_returns_empty_kg(self) -> None:
        kg = crawl_results_to_sitekg([], self.cfg, site="gitlab")
        self.assertEqual(kg.site, "gitlab")
        self.assertEqual(len(kg.state_patterns), 0)


# ---------------------------------------------------------------------------
# Merge with manual seed (source priority)
# ---------------------------------------------------------------------------

class CrawlMergeWithManualTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = _gitlab_like_config()

    def test_crawl_state_pattern_merges_alongside_manual(self) -> None:
        """crawl과 manual은 다른 id 규약을 쓰므로 둘 다 보존돼야 함."""
        manual = SiteKG(site="gitlab")
        manual.state_patterns["project_issues_list"] = StatePattern(
            id="project_issues_list",
            url_template="/{project_path}/-/issues",
            source="manual",
        )
        crawl_kg = crawl_results_to_sitekg(
            [CrawlResult(url="http://x/foo/-/issues", normalized_url_template="/{slot_0}/-/issues")],
            self.cfg,
        )
        store = SiteKGStore(manual)
        store.merge(crawl_kg)
        self.assertIn("project_issues_list", store.kg.state_patterns)
        crawl_ids = [k for k in store.kg.state_patterns if k.startswith("crawl:")]
        self.assertEqual(len(crawl_ids), 1)
        self.assertGreater(store.kg.source_mix["manual"], 0)
        self.assertGreater(store.kg.source_mix["crawl"], 0)


# ---------------------------------------------------------------------------
# Live crawl (manual only — needs GitLab Docker up)
# ---------------------------------------------------------------------------

@unittest.skipUnless(
    os.environ.get("RUN_LIVE_CRAWL"),
    "Live crawl requires RUN_LIVE_CRAWL=1 + running GitLab Docker.",
)
class LiveCrawlSmokeTests(unittest.TestCase):
    def test_smoke_crawl_returns_results(self) -> None:
        results = crawl_site(
            base_url="http://localhost:8023",
            seed_urls=["http://localhost:8023/"],
            max_depth=0,
        )
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main()
