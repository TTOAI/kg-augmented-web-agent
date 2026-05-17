"""Tests for site config extensions (entities.yaml, crawl.yaml).

이 테스트는 YAML에 저장된 값이 기준 상수 값과 정확히 일치하는지
확인한다 (byte-identical 기대).
"""
from __future__ import annotations

import unittest

from kg_augmented_webagent.kg.site_extras import (
    load_site_crawl,
    load_site_entities,
)


class GitLabEntitiesRoundtripTests(unittest.TestCase):
    """entities.yaml이 이관 전 하드코드 값과 정확히 일치."""

    def setUp(self) -> None:
        self.entities = load_site_entities("gitlab")

    def test_namespaces_matches_pre_migration_constant(self) -> None:
        self.assertEqual(
            self.entities.namespaces,
            frozenset({"byteblaze", "a11yproject", "the-a11y-project"}),
        )

    def test_usernames_matches_pre_migration_constant(self) -> None:
        self.assertEqual(self.entities.usernames, frozenset({"byteblaze"}))

    def test_action_keywords_matches_pre_migration_constant(self) -> None:
        self.assertEqual(
            self.entities.action_keywords,
            frozenset({"new", "edit", "create", "delete", "archive", "home"}),
        )

    def test_sample_values_cover_all_expected_slots(self) -> None:
        # classify_template()이 치환하는 모든 placeholder가 포함되어야 함
        required = {
            "namespace", "project", "username", "branch", "id", "sha",
            "tag_name",
        }
        self.assertTrue(
            required.issubset(set(self.entities.sample_values.keys())),
            f"missing sample keys: {required - set(self.entities.sample_values.keys())}",
        )

    def test_sample_values_exact_pre_migration(self) -> None:
        sv = self.entities.sample_values
        self.assertEqual(sv.get("namespace"), "byteblaze")
        self.assertEqual(sv.get("project"), "a11y-syntax-highlighting")
        self.assertEqual(sv.get("username"), "byteblaze")
        self.assertEqual(sv.get("branch"), "main")
        self.assertEqual(sv.get("sha"), "62820763d9b5f3b25720596f542aaf89d917fb17")
        self.assertEqual(sv.get("tag_name"), "v0.1.0")


class GitLabCrawlRoundtripTests(unittest.TestCase):
    """crawl.yaml이 이관 전 하드코드 값과 정확히 일치."""

    def setUp(self) -> None:
        self.crawl = load_site_crawl("gitlab")

    def test_base_url_matches_pre_migration(self) -> None:
        self.assertEqual(self.crawl.base_url, "http://localhost:8023")

    def test_allowed_hosts_contains_baseline_entries(self) -> None:
        # 기존 is_same_host는 "localhost:8023", "127.0.0.1:8023" 수용
        hosts = set(self.crawl.allowed_hosts)
        self.assertIn("localhost:8023", hosts)
        self.assertIn("127.0.0.1:8023", hosts)

    def test_seeds_matches_pre_migration(self) -> None:
        self.assertEqual(
            list(self.crawl.seeds),
            [
                "/dashboard",
                "/explore/projects",
                "/byteblaze",
                "/byteblaze/a11y-syntax-highlighting",
                "/-/profile",
                "/help",
            ],
        )

    def test_forbidden_patterns_matches_pre_migration(self) -> None:
        self.assertEqual(
            list(self.crawl.forbidden_patterns),
            [
                "/sign_out", "/logout", "?_method=delete", "?method=delete",
                "/destroy", "/admin", "/toggle_", "/resolve", "/reopen",
            ],
        )

    def test_site_global_routes_nonempty(self) -> None:
        # extract_namespace() denylist로 사용. dashboard/explore 등 포함해야 함.
        routes = self.crawl.site_global_routes
        self.assertIn("dashboard", routes)
        self.assertIn("explore", routes)
        self.assertIn("admin", routes)


class MissingSiteFallbackTests(unittest.TestCase):
    """존재하지 않는 site에 대해 empty 인스턴스 반환 (graceful fallback)."""

    def test_entities_missing_site_returns_empty(self) -> None:
        e = load_site_entities("_nonexistent_site_")
        self.assertEqual(e.namespaces, frozenset())
        self.assertEqual(e.sample_values, {})

    def test_crawl_missing_site_returns_empty(self) -> None:
        c = load_site_crawl("_nonexistent_site_")
        self.assertEqual(c.base_url, "")
        self.assertEqual(c.seeds, ())


class StageABackcompatTests(unittest.TestCase):
    """Stage A scripts가 config를 로드해 기존 상수와 동일한 값을 노출하는지."""

    def test_stage_a_extract_rules_exposes_loaded_constants(self) -> None:
        from scripts.kg.build import classify_rules as m
        self.assertEqual(
            set(m.KNOWN_NAMESPACES),
            {"byteblaze", "a11yproject", "the-a11y-project"},
        )
        self.assertEqual(set(m.KNOWN_USERNAMES), {"byteblaze"})
        self.assertEqual(
            set(m.ACTION_KEYWORDS),
            {"new", "edit", "create", "delete", "archive", "home"},
        )
        self.assertEqual(m.BASE_URL, "http://localhost:8023")

    def test_stage_a_f_crawl_exposes_loaded_constants(self) -> None:
        from scripts.kg.build import crawl as m
        self.assertEqual(m.BASE_URL, "http://localhost:8023")
        self.assertEqual(
            m.SEEDS,
            [
                "/dashboard", "/explore/projects", "/byteblaze",
                "/byteblaze/a11y-syntax-highlighting", "/-/profile", "/help",
            ],
        )
        self.assertIn("/sign_out", m.FORBIDDEN_PATTERNS)
        self.assertIn("/admin", m.FORBIDDEN_PATTERNS)

    def test_stage_a_f_crawl_is_same_host_still_accepts_baseline(self) -> None:
        from scripts.kg.build.crawl import is_same_host
        self.assertTrue(is_same_host("http://localhost:8023/dashboard"))
        self.assertTrue(is_same_host("http://127.0.0.1:8023/help"))
        self.assertTrue(is_same_host("/relative/path"))
        self.assertFalse(is_same_host("http://example.com/"))

    def test_stage_a_f_crawl_is_forbidden_still_flags_baseline(self) -> None:
        from scripts.kg.build.crawl import is_forbidden
        self.assertTrue(is_forbidden("http://localhost:8023/admin"))
        self.assertTrue(is_forbidden("http://x/y/sign_out"))
        self.assertFalse(is_forbidden("http://localhost:8023/byteblaze/repo"))


if __name__ == "__main__":
    unittest.main()
