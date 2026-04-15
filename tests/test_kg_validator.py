"""kg.validator 단위 테스트 — Hook C의 target_reached 검증."""
from __future__ import annotations

import unittest
from pathlib import Path

from site_adaptive_webagent.kg import KGContext, KGLookup, target_reached
from site_adaptive_webagent.kg.seed import load_site_kg_from_dir

GITLAB_CONFIG_DIR = Path(__file__).parent.parent / "config" / "sites" / "gitlab"


def _ctx() -> KGContext:
    cfg, kg = load_site_kg_from_dir(GITLAB_CONFIG_DIR)
    return KGContext(kg=kg, site_config=cfg)


class TargetReachedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = _ctx()

    def test_match_target_url(self) -> None:
        """현재 URL이 정확히 target이면 True."""
        lookup = KGLookup(
            infotype="issues_list",
            bindings={
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name": ["bug"],
            },
        )
        self.assertTrue(target_reached(
            "/a11yproject/a11yproject.com/-/issues?state=opened&label_name[]=bug",
            lookup, self.ctx,
        ))

    def test_wrong_project_not_reached(self) -> None:
        lookup = KGLookup(
            infotype="issues_list",
            bindings={"project_path": "a11yproject/a11yproject.com", "label_name": ["bug"]},
        )
        self.assertFalse(target_reached(
            "/other/project/-/issues?state=opened&label_name[]=bug",
            lookup, self.ctx,
        ))

    def test_missing_filter_not_reached(self) -> None:
        """target이 bug filter 요구, 현재 URL엔 label_name 없음 → False."""
        lookup = KGLookup(
            infotype="issues_list",
            bindings={
                "project_path": "p",
                "state": "opened",
                "label_name": ["bug"],
            },
        )
        self.assertFalse(target_reached(
            "/p/-/issues?state=opened",
            lookup, self.ctx,
        ))

    def test_decorative_param_ignored(self) -> None:
        """URL에 page=2 같은 decorative param 있어도 target 판정에 영향 없음."""
        lookup = KGLookup(
            infotype="issues_list",
            bindings={
                "project_path": "p",
                "state": "opened",
                "label_name": ["bug"],
            },
        )
        self.assertTrue(target_reached(
            "/p/-/issues?state=opened&label_name[]=bug&page=2",
            lookup, self.ctx,
        ))

    def test_unknown_infotype_returns_false(self) -> None:
        lookup = KGLookup(infotype="no_such_type", bindings={})
        self.assertFalse(target_reached("/any", lookup, self.ctx))

    def test_commits_contributors_reached(self) -> None:
        """project_commits_contributors target URL과 현재 URL이 일치하면 True."""
        lookup = KGLookup(
            infotype="project_commits_contributors",
            bindings={"project_path": "primer/design"},
        )
        self.assertTrue(target_reached(
            "/primer/design/-/graphs/main", lookup, self.ctx,
        ))


if __name__ == "__main__":
    unittest.main()
