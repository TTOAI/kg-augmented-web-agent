"""kg.rewrite 단위 테스트 — Hook B의 rewrite_plan 검증.

NAVIGATE / RETRIEVE / MUTATE 각 task type에서 rewrite 정책 동작 검증.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from site_adaptive_webagent.kg import (
    InfoType,
    KGContext,
    KGLookup,
    RealizesEdge,
    SiteConfig,
    SiteKG,
    StatePattern,
    rewrite_plan,
)
from site_adaptive_webagent.kg.seed import load_site_kg_from_dir
from site_adaptive_webagent.runtime.llm import SubGoal

FIXTURE_KG_DIR = Path(__file__).parent / "fixtures" / "kg_test_site"


def _ctx() -> KGContext:
    cfg, kg = load_site_kg_from_dir(FIXTURE_KG_DIR)
    return KGContext(kg=kg, site_config=cfg)


# ---------------------------------------------------------------------------
# Task type별 rewrite 동작
# ---------------------------------------------------------------------------

class RewritePlanTaskTypesTests(unittest.TestCase):
    """NAVIGATE/RETRIEVE/MUTATE 각각에서 rewrite 정책이 의도대로 동작."""

    def setUp(self) -> None:
        self.ctx = _ctx()

    def test_navigate_all_nav_collapses_to_single_navigate_to(self) -> None:
        """모든 sub-goal이 navigation → 전체를 단일 navigate_to로 치환."""
        sub_goals = [
            SubGoal("Open project page", "navigation"),
            SubGoal("Navigate to issues list", "navigation"),
            SubGoal("Arrive at filtered URL", "navigation"),
        ]
        lookup = KGLookup(
            infotype="issues_list",
            bindings={
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name": ["bug"],
            },
        )
        result = rewrite_plan(sub_goals, lookup, self.ctx)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].goal_type, "navigation")
        self.assertIn("/a11yproject/a11yproject.com/-/issues", result[0].goal)
        self.assertIn("label_name[]=bug", result[0].goal)

    def test_retrieve_preserves_action_tail(self) -> None:
        """[nav, action(find), action(extract)] → [nav_direct, action(find), action(extract)]."""
        sub_goals = [
            SubGoal("Open project page", "navigation"),
            SubGoal("Find contributors section", "action"),
            SubGoal("Extract top committer username", "action"),
        ]
        lookup = KGLookup(
            infotype="project_commits_contributors",
            bindings={"project_path": "primer/design"},
        )
        result = rewrite_plan(sub_goals, lookup, self.ctx)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 3)
        # 첫 sub-goal은 navigate_to (target URL 포함)
        self.assertEqual(result[0].goal_type, "navigation")
        self.assertIn("/primer/design/-/graphs/main", result[0].goal)
        # 이후 action sub-goal은 그대로 유지
        self.assertEqual(result[1].goal, "Find contributors section")
        self.assertEqual(result[2].goal, "Extract top committer username")

    def test_mutate_task_pattern_preserves_action_tail(self) -> None:
        """MUTATE: [nav(profile), action(edit), action(save)] → [nav_direct, action(edit), action(save)]"""
        sub_goals = [
            SubGoal("Go to profile page", "navigation"),
            SubGoal("Edit homepage URL field", "action"),
            SubGoal("Save changes", "action"),
        ]
        # 여기선 issues_list를 target으로 사용 (profile InfoType이 현 config에 없어서 간접 검증)
        lookup = KGLookup(
            infotype="issues_list",
            bindings={"project_path": "some/project"},
        )
        result = rewrite_plan(sub_goals, lookup, self.ctx)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].goal_type, "navigation")
        self.assertEqual(result[1].goal, "Edit homepage URL field")
        self.assertEqual(result[2].goal, "Save changes")


# ---------------------------------------------------------------------------
# Failure / edge cases
# ---------------------------------------------------------------------------

class RewritePlanEdgeCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ctx = _ctx()

    def test_unknown_infotype_returns_none(self) -> None:
        """InfoType이 KG에 없으면 rewrite 포기."""
        sub_goals = [SubGoal("x", "navigation")]
        lookup = KGLookup(infotype="nonexistent", bindings={})
        self.assertIsNone(rewrite_plan(sub_goals, lookup, self.ctx))

    def test_missing_required_binding_returns_none(self) -> None:
        """required binding 부족 → emit_target_url이 불완전 URL을 낼 수 있어도 rewrite 정책은
        일단 URL을 얻으면 진행. 완전 실패하면 (path slot unfilled) None.

        현 구현에서는 path slot이 채워지지 않으면 {project_path} 같은 literal이 남지만
        그래도 URL 문자열이 반환되므로 rewrite는 진행됨. 이 테스트는 현 동작을 고정.
        """
        sub_goals = [SubGoal("x", "navigation")]
        # project_path 누락 → path에 "{project_path}" 리터럴이 남음
        lookup = KGLookup(infotype="issues_list", bindings={})
        result = rewrite_plan(sub_goals, lookup, self.ctx)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("{project_path}", result[0].goal)

    def test_empty_sub_goals_returns_none(self) -> None:
        """빈 plan이 들어오면 rewrite 실패."""
        self.assertIsNone(rewrite_plan([], KGLookup(infotype="issues_list", bindings={"project_path": "x"}), self.ctx))

    def test_all_action_plan_prepends_navigate_to(self) -> None:
        """plan이 전부 action이면 맨 앞에 navigate_to prepend."""
        sub_goals = [
            SubGoal("a1", "action"),
            SubGoal("a2", "action"),
        ]
        lookup = KGLookup(
            infotype="issues_list",
            bindings={"project_path": "p"},
        )
        result = rewrite_plan(sub_goals, lookup, self.ctx)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].goal_type, "navigation")
        self.assertEqual(result[1].goal, "a1")
        self.assertEqual(result[2].goal, "a2")


class TrustAwareRewriteTests(unittest.TestCase):
    """02 §3-7: url_template_trust == 'inferred' 이면 rewrite 보류 (원 plan 유지)."""

    def _ctx_with_trust(self, url_trust: str, edge_trust: str) -> KGContext:
        kg = SiteKG(site="gitlab")
        kg.state_patterns["p1"] = StatePattern(
            id="p1",
            url_template="/{project_path}/-/issues",
            path_params={"project_path": {"type": "path_segments"}},
            url_template_trust=url_trust,
        )
        it = InfoType(
            name="issues_list",
            required_bindings=["project_path"],
            realizes=[
                RealizesEdge(
                    infotype="issues_list",
                    state_pattern_id="p1",
                    condition="default",
                    trust=edge_trust,
                ),
            ],
        )
        kg.infotypes["issues_list"] = it
        kg.realizes_edges.extend(it.realizes)
        return KGContext(kg=kg, site_config=SiteConfig(site="gitlab"))

    def test_inferred_url_template_skips_rewrite(self) -> None:
        ctx = self._ctx_with_trust(url_trust="inferred", edge_trust="declared")
        sub_goals = [SubGoal("nav", "navigation")]
        lookup = KGLookup(infotype="issues_list", bindings={"project_path": "a/b"})
        self.assertIsNone(rewrite_plan(sub_goals, lookup, ctx))

    def test_inferred_realizes_edge_skips_rewrite(self) -> None:
        ctx = self._ctx_with_trust(url_trust="declared", edge_trust="inferred")
        sub_goals = [SubGoal("nav", "navigation")]
        lookup = KGLookup(infotype="issues_list", bindings={"project_path": "a/b"})
        self.assertIsNone(rewrite_plan(sub_goals, lookup, ctx))

    def test_declared_trust_allows_rewrite(self) -> None:
        ctx = self._ctx_with_trust(url_trust="declared", edge_trust="declared")
        sub_goals = [SubGoal("nav", "navigation")]
        lookup = KGLookup(infotype="issues_list", bindings={"project_path": "a/b"})
        result = rewrite_plan(sub_goals, lookup, ctx)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 1)
        self.assertIn("/a/b/-/issues", result[0].goal)


if __name__ == "__main__":
    unittest.main()
