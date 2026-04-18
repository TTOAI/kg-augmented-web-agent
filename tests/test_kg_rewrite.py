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

    def test_missing_required_binding_skipped_by_incomplete_url_guard(self) -> None:
        """Option B (2026-04-18): required binding 부족으로 unfilled slot이 남는 URL은
        rewrite skip (malformed URL navigation 방지).

        이전 동작: `{project_path}` literal 남긴 URL로 rewrite 진행 (agent가 404로 이동 가능).
        현재 동작: _UNFILLED_SLOT_RE guard가 감지 → None 반환 → baseline plan 유지.
        """
        sub_goals = [SubGoal("x", "navigation")]
        lookup = KGLookup(infotype="issues_list", bindings={})
        result = rewrite_plan(sub_goals, lookup, self.ctx)
        self.assertIsNone(result)

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
    """Option B (2026-04-18): trust 기반 skip 제거. verified / declared / inferred 전부 허용.
    이전 정책 (inferred skip)은 Hook B 사실상 비활성 유발 → LLM derivation inferred edge를
    활용하기 위해 trust 필터 제거. Malformed URL은 별도 guard로 처리.
    """

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

    def test_inferred_url_template_allows_rewrite(self) -> None:
        """Option B: inferred url_template_trust도 rewrite 진행."""
        ctx = self._ctx_with_trust(url_trust="inferred", edge_trust="declared")
        sub_goals = [SubGoal("nav", "navigation")]
        lookup = KGLookup(infotype="issues_list", bindings={"project_path": "a/b"})
        result = rewrite_plan(sub_goals, lookup, ctx)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("/a/b/-/issues", result[0].goal)

    def test_inferred_realizes_edge_allows_rewrite(self) -> None:
        """Option B: inferred edge.trust도 rewrite 진행."""
        ctx = self._ctx_with_trust(url_trust="declared", edge_trust="inferred")
        sub_goals = [SubGoal("nav", "navigation")]
        lookup = KGLookup(infotype="issues_list", bindings={"project_path": "a/b"})
        result = rewrite_plan(sub_goals, lookup, ctx)
        self.assertIsNotNone(result)

    def test_verified_inferred_hybrid_allows_rewrite(self) -> None:
        """verified url + inferred edge 혼합도 rewrite 진행."""
        ctx = self._ctx_with_trust(url_trust="verified", edge_trust="inferred")
        sub_goals = [SubGoal("nav", "navigation")]
        lookup = KGLookup(infotype="issues_list", bindings={"project_path": "a/b"})
        result = rewrite_plan(sub_goals, lookup, ctx)
        self.assertIsNotNone(result)

    def test_declared_trust_allows_rewrite(self) -> None:
        """declared도 여전히 허용 (본 연구 frozen KG에는 없지만 schema 상 유효)."""
        ctx = self._ctx_with_trust(url_trust="declared", edge_trust="declared")
        sub_goals = [SubGoal("nav", "navigation")]
        lookup = KGLookup(infotype="issues_list", bindings={"project_path": "a/b"})
        result = rewrite_plan(sub_goals, lookup, ctx)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result), 1)
        self.assertIn("/a/b/-/issues", result[0].goal)


class IncompleteUrlGuardTests(unittest.TestCase):
    """Option B: emit_target_url이 unfilled slot을 남기면 rewrite skip (malformed URL 방지)."""

    def test_unfilled_path_slot_skips_rewrite(self) -> None:
        """path slot이 binding 없이 literal로 남으면 rewrite 진행 안 함."""
        kg = SiteKG(site="gitlab")
        kg.state_patterns["p1"] = StatePattern(
            id="p1",
            url_template="/{namespace}/{project}/-/{section}",
            path_params={
                "namespace": {"type": "segment"},
                "project": {"type": "segment"},
                "section": {"type": "segment"},
            },
            url_template_trust="inferred",
        )
        it = InfoType(
            name="t1",
            required_bindings=["namespace", "project"],
            realizes=[RealizesEdge(
                infotype="t1", state_pattern_id="p1", condition="default", trust="inferred",
            )],
        )
        kg.infotypes["t1"] = it
        kg.realizes_edges.extend(it.realizes)
        ctx = KGContext(kg=kg, site_config=SiteConfig(site="gitlab"))
        lookup = KGLookup(infotype="t1", bindings={"namespace": "a", "project": "b"})
        # section binding 누락 → URL에 {section} 남음 → rewrite skip
        self.assertIsNone(rewrite_plan([SubGoal("x", "navigation")], lookup, ctx))


if __name__ == "__main__":
    unittest.main()
