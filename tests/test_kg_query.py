"""kg.query 단위 테스트 — primitive별 시나리오 검증."""
from __future__ import annotations

import unittest
from pathlib import Path

from site_adaptive_webagent.kg import (
    Action,
    IdentityParam,
    InfoType,
    LeadsToEdge,
    RealizesEdge,
    SiteConfig,
    SiteKG,
    StatePattern,
    emit_target_url,
    simulate_final_state,
    state_matches,
)
from site_adaptive_webagent.kg.seed import load_site_kg_from_dir

FIXTURE_KG_DIR = Path(__file__).parent / "fixtures" / "kg_test_site"


def _make_kg() -> tuple[SiteConfig, SiteKG]:
    """실 config 파일에서 KG + SiteConfig 로드."""
    return load_site_kg_from_dir(FIXTURE_KG_DIR)


# ---------------------------------------------------------------------------
# 1. emit_target_url
# ---------------------------------------------------------------------------

class EmitTargetURLTests(unittest.TestCase):
    """InfoType + bindings → canonical URL."""

    def setUp(self) -> None:
        self.config, self.kg = _make_kg()

    def test_issues_list_with_filter(self) -> None:
        """intent: "Go to bug issues for project X" → has_filter realizes로 URL 합성."""
        url = emit_target_url(
            self.kg,
            self.config,
            "issues_list",
            {
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name": ["bug"],
            },
        )
        self.assertIsNotNone(url)
        assert url is not None
        self.assertIn("/a11yproject/a11yproject.com/-/issues", url)
        self.assertIn("state=opened", url)
        self.assertIn("label_name[]=bug", url)

    def test_help_wanted_label_filter(self) -> None:
        """label에 공백·다단어가 들어가도 URL-encode 되어 emit."""
        url = emit_target_url(
            self.kg,
            self.config,
            "issues_list",
            {
                "project_path": "a11yproject/a11yproject.com",
                "label_name": ["help wanted"],
            },
        )
        self.assertIsNotNone(url)
        assert url is not None
        self.assertIn("label_name[]=help%20wanted", url)

    def test_issues_list_no_filter_uses_default_realize(self) -> None:
        """optional_bindings 없으면 default realize → project_issues_list (no filter)."""
        url = emit_target_url(
            self.kg,
            self.config,
            "issues_list",
            {"project_path": "some/project"},
        )
        self.assertIsNotNone(url)
        assert url is not None
        self.assertIn("/some/project/-/issues", url)
        # query string이 없거나 default만 있어야 함
        self.assertFalse(url.endswith("?"))

    def test_unknown_infotype_returns_none(self) -> None:
        url = emit_target_url(
            self.kg, self.config, "nonexistent_infotype", {},
        )
        self.assertIsNone(url)

    def test_commits_contributors_routing(self) -> None:
        """project_commits_contributors → /-/graphs/<branch>, branch default='main' 적용."""
        url = emit_target_url(
            self.kg,
            self.config,
            "project_commits_contributors",
            {"project_path": "primer/design"},
        )
        self.assertIsNotNone(url)
        assert url is not None
        self.assertIn("/primer/design/-/graphs/main", url)


# ---------------------------------------------------------------------------
# 2. state_matches
# ---------------------------------------------------------------------------

class StateMatchesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config, self.kg = _make_kg()

    def test_exact_match_target_state(self) -> None:
        """현재 URL이 정확히 target 상태이면 True."""
        current = "/a11yproject/a11yproject.com/-/issues?state=opened&label_name[]=bug"
        self.assertTrue(state_matches(
            self.kg, self.config, current, "issues_list",
            {
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name": ["bug"],
            },
        ))

    def test_wrong_project_does_not_match(self) -> None:
        current = "/other/project/-/issues?state=opened&label_name[]=bug"
        self.assertFalse(state_matches(
            self.kg, self.config, current, "issues_list",
            {
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name": ["bug"],
            },
        ))

    def test_decorative_param_does_not_break_match(self) -> None:
        """URL에 page=2가 있어도 state_matches는 True."""
        current = "/a11yproject/a11yproject.com/-/issues?state=opened&label_name[]=bug&page=2"
        self.assertTrue(state_matches(
            self.kg, self.config, current, "issues_list",
            {
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name": ["bug"],
            },
        ))

    def test_missing_filter_label_does_not_match(self) -> None:
        """target이 bug 필터를 요구하는데 URL엔 label_name 없으면 False."""
        current = "/a11yproject/a11yproject.com/-/issues?state=opened"
        self.assertFalse(state_matches(
            self.kg, self.config, current, "issues_list",
            {
                "project_path": "a11yproject/a11yproject.com",
                "state": "opened",
                "label_name": ["bug"],
            },
        ))

    def test_unknown_infotype_returns_false(self) -> None:
        self.assertFalse(state_matches(
            self.kg, self.config, "/x", "no_such_type", {},
        ))


# ---------------------------------------------------------------------------
# 3. simulate_final_state (기본 구현)
# ---------------------------------------------------------------------------

class SimulateFinalStateTests(unittest.TestCase):
    """leads_to 엣지 순차 적용 시뮬레이션."""

    def _small_kg(self) -> SiteKG:
        """project_page -> goto_issues_tab -> project_issues_list 단일 체인."""
        kg = SiteKG(site="gitlab")
        kg.state_patterns["project_page"] = StatePattern(
            id="project_page",
            url_template="/{project_path}",
            path_params={"project_path": {"type": "path_segments"}},
        )
        kg.state_patterns["project_issues_list"] = StatePattern(
            id="project_issues_list",
            url_template="/{project_path}/-/issues",
            path_params={"project_path": {"type": "path_segments"}},
        )
        kg.state_patterns["project_issues_filtered"] = StatePattern(
            id="project_issues_filtered",
            url_template="/{project_path}/-/issues",
        )
        kg.actions["goto_issues_tab"] = Action(name="goto_issues_tab")
        kg.actions["apply_label_filter"] = Action(name="apply_label_filter")
        kg.leads_to_edges.extend([
            LeadsToEdge(
                from_state_pattern_id="project_page",
                action_name="goto_issues_tab",
                to_state_pattern_id="project_issues_list",
            ),
            LeadsToEdge(
                from_state_pattern_id="project_issues_list",
                action_name="apply_label_filter",
                to_state_pattern_id="project_issues_filtered",
            ),
        ])
        return kg

    def test_single_action_transition(self) -> None:
        kg = self._small_kg()
        final = simulate_final_state(kg, "project_page", ["goto_issues_tab"])
        self.assertIsNotNone(final)
        assert final is not None
        self.assertEqual(final.id, "project_issues_list")

    def test_two_action_chain(self) -> None:
        kg = self._small_kg()
        final = simulate_final_state(
            kg, "project_page", ["goto_issues_tab", "apply_label_filter"],
        )
        self.assertIsNotNone(final)
        assert final is not None
        self.assertEqual(final.id, "project_issues_filtered")

    def test_unknown_action_returns_none(self) -> None:
        kg = self._small_kg()
        self.assertIsNone(simulate_final_state(kg, "project_page", ["nonexistent"]))

    def test_empty_sequence_returns_initial(self) -> None:
        kg = self._small_kg()
        final = simulate_final_state(kg, "project_page", [])
        self.assertIsNotNone(final)
        assert final is not None
        self.assertEqual(final.id, "project_page")


class TrustAwareEdgeSelectionTests(unittest.TestCase):
    """동일 InfoType에 여러 realizes 엣지 존재 시 trust 우선순위 (verified > declared > inferred)."""

    def _two_pattern_kg(self) -> tuple[SiteConfig, SiteKG]:
        kg = SiteKG(site="gitlab")
        kg.state_patterns["p_verified"] = StatePattern(
            id="p_verified",
            url_template="/{project_path}/-/issues",
            path_params={"project_path": {"type": "path_segments"}},
            url_template_trust="verified",
        )
        kg.state_patterns["p_inferred"] = StatePattern(
            id="p_inferred",
            url_template="/{project_path}/old_issues",
            path_params={"project_path": {"type": "path_segments"}},
            url_template_trust="inferred",
        )
        it = InfoType(
            name="x_issues",
            required_bindings=["project_path"],
            realizes=[
                # 순서상 inferred가 앞, 하지만 trust로 verified가 선택돼야 함
                RealizesEdge(
                    infotype="x_issues",
                    state_pattern_id="p_inferred",
                    condition="default",
                    trust="inferred",
                ),
                RealizesEdge(
                    infotype="x_issues",
                    state_pattern_id="p_verified",
                    condition="default",
                    trust="verified",
                ),
            ],
        )
        kg.infotypes["x_issues"] = it
        kg.realizes_edges.extend(it.realizes)
        return SiteConfig(site="gitlab"), kg

    def test_verified_edge_wins_over_inferred(self) -> None:
        cfg, kg = self._two_pattern_kg()
        url = emit_target_url(kg, cfg, "x_issues", {"project_path": "a/b"})
        self.assertIsNotNone(url)
        assert url is not None
        self.assertIn("/-/issues", url)
        self.assertNotIn("old_issues", url)


if __name__ == "__main__":
    unittest.main()
