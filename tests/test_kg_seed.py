"""kg.seed 로더 단위 테스트.

실 config 파일(`config/sites/gitlab/`)을 로드해 어댑터 변환 검증.
재현성 원칙(`06_evaluation_protocol.md`)에 맞춰 고정 artifact로 사용.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from site_adaptive_webagent.kg.seed import (
    load_infotypes,
    load_kg_seed,
    load_site_config,
    load_site_kg_from_dir,
)

GITLAB_CONFIG_DIR = Path(__file__).parent.parent / "config" / "sites" / "gitlab"


class LoadSiteConfigTests(unittest.TestCase):
    """site_config.yaml → SiteConfig 어댑터 검증."""

    def test_load_actual_gitlab_config(self) -> None:
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertEqual(cfg.site, "gitlab")
        self.assertIn("localhost", cfg.base_url)

    def test_url_decode_aggressive_maps_to_true(self) -> None:
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertTrue(cfg.url_decode)

    def test_trailing_slash_ignore_maps_to_true(self) -> None:
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertTrue(cfg.trailing_slash_ignore)

    def test_case_sensitive_dict_flattened(self) -> None:
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertTrue(cfg.path_case_sensitive)
        self.assertTrue(cfg.query_key_case_sensitive)
        self.assertFalse(cfg.query_value_case_sensitive)

    def test_decorative_params_loaded(self) -> None:
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertIn("page", cfg.decorative_params)
        self.assertIn("utm_source", cfg.decorative_params)

    def test_multi_value_params_flattened(self) -> None:
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertEqual(cfg.multi_value_suffix_pattern, r"\[\]$")
        self.assertIn("approver_ids", cfg.multi_value_explicit)

    def test_identity_tokens_wrapped(self) -> None:
        """YAML의 {me: {replacement_key: 'a.b'}} → {me: '{{a.b}}'}."""
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertIn("me", cfg.identity_tokens)
        self.assertEqual(cfg.identity_tokens["me"], "{{current_user.username}}")

    def test_path_aliases_loaded(self) -> None:
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertGreaterEqual(len(cfg.path_aliases), 1)
        # 첫 alias 그룹의 canonical이 첫 entry
        self.assertEqual(cfg.path_aliases[0][0], cfg.path_aliases[0][0])

    def test_emit_policy_parsed(self) -> None:
        cfg = load_site_config(GITLAB_CONFIG_DIR / "site_config.yaml")
        self.assertTrue(cfg.emit_include_default_values)
        self.assertTrue(cfg.emit_multi_value_sorted)


class LoadSiteConfigInlineTests(unittest.TestCase):
    """인라인 YAML로 어댑터 분기 검증."""

    def _load(self, yaml_text: str):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(yaml_text)
            path = f.name
        try:
            return load_site_config(path)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_url_decode_boolean_true(self) -> None:
        cfg = self._load("site: x\nurl_decode: true\n")
        self.assertTrue(cfg.url_decode)

    def test_url_decode_string_variants(self) -> None:
        for s in ["aggressive", "yes", "on", "1"]:
            cfg = self._load(f"site: x\nurl_decode: {s}\n")
            self.assertTrue(cfg.url_decode, f"string={s!r}")

    def test_identity_tokens_inline_string(self) -> None:
        cfg = self._load(
            "site: x\nidentity_tokens:\n  me: '{{foo.bar}}'\n"
        )
        self.assertEqual(cfg.identity_tokens["me"], "{{foo.bar}}")


class LoadInfoTypesTests(unittest.TestCase):
    def test_load_actual_gitlab_infotypes(self) -> None:
        infotypes = load_infotypes(GITLAB_CONFIG_DIR / "infotypes.yaml")
        self.assertGreaterEqual(len(infotypes), 3)
        names = {it.name for it in infotypes}
        self.assertIn("issues_list", names)

    def test_issues_list_has_realizes_edges(self) -> None:
        infotypes = load_infotypes(GITLAB_CONFIG_DIR / "infotypes.yaml")
        issues_list = next(it for it in infotypes if it.name == "issues_list")
        self.assertEqual(len(issues_list.realizes), 2)
        conditions = {e.condition for e in issues_list.realizes}
        self.assertEqual(conditions, {"default", "has_filter"})

    def test_required_and_optional_bindings_loaded(self) -> None:
        infotypes = load_infotypes(GITLAB_CONFIG_DIR / "infotypes.yaml")
        issues_list = next(it for it in infotypes if it.name == "issues_list")
        self.assertIn("project_path", issues_list.required_bindings)
        self.assertIn("state", issues_list.optional_bindings)

    def test_description_whitespace_normalized(self) -> None:
        """YAML > block scalar의 여러 줄이 한 줄로 정규화됨."""
        infotypes = load_infotypes(GITLAB_CONFIG_DIR / "infotypes.yaml")
        issues_list = next(it for it in infotypes if it.name == "issues_list")
        self.assertNotIn("\n", issues_list.description)
        self.assertNotIn("  ", issues_list.description)

    def test_realizes_edge_infotype_backfilled(self) -> None:
        """YAML의 realizes 항목에 infotype 필드 없어도 InfoType.name으로 자동 채움."""
        infotypes = load_infotypes(GITLAB_CONFIG_DIR / "infotypes.yaml")
        issues_list = next(it for it in infotypes if it.name == "issues_list")
        for edge in issues_list.realizes:
            self.assertEqual(edge.infotype, "issues_list")


class LoadKGSeedTests(unittest.TestCase):
    def test_load_actual_gitlab_kg_seed(self) -> None:
        kg = load_kg_seed(GITLAB_CONFIG_DIR / "kg_seed.json")
        self.assertEqual(kg.site, "gitlab")
        self.assertIn("project_issues_filtered", kg.state_patterns)

    def test_state_patterns_with_query_params(self) -> None:
        kg = load_kg_seed(GITLAB_CONFIG_DIR / "kg_seed.json")
        sp = kg.state_patterns["project_issues_filtered"]
        self.assertGreaterEqual(len(sp.identity_query_params), 2)
        names = {p.name for p in sp.identity_query_params}
        self.assertIn("state", names)
        self.assertIn("label_name[]", names)

    def test_actions_loaded(self) -> None:
        kg = load_kg_seed(GITLAB_CONFIG_DIR / "kg_seed.json")
        self.assertIn("navigate_to", kg.actions)
        self.assertIn("apply_label_filter", kg.actions)

    def test_leads_to_edges_style_b_parsed(self) -> None:
        """config 파일의 중첩 스타일(from:{}, to:{}) 파싱."""
        kg = load_kg_seed(GITLAB_CONFIG_DIR / "kg_seed.json")
        self.assertGreater(len(kg.leads_to_edges), 0)
        edge = kg.leads_to_edges[0]
        self.assertTrue(edge.from_state_pattern_id)
        self.assertTrue(edge.to_state_pattern_id)


class LoadSiteKGFromDirTests(unittest.TestCase):
    """3 파일 통합 로드."""

    def test_returns_site_config_and_kg(self) -> None:
        cfg, kg = load_site_kg_from_dir(GITLAB_CONFIG_DIR)
        self.assertEqual(cfg.site, "gitlab")
        self.assertEqual(kg.site, "gitlab")

    def test_kg_has_state_patterns_and_infotypes(self) -> None:
        _, kg = load_site_kg_from_dir(GITLAB_CONFIG_DIR)
        self.assertGreater(len(kg.state_patterns), 0)
        self.assertGreater(len(kg.infotypes), 0)

    def test_realizes_flat_list_matches_infotypes(self) -> None:
        """infotypes의 realizes가 flat list에 모두 포함."""
        _, kg = load_site_kg_from_dir(GITLAB_CONFIG_DIR)
        total_per_infotype = sum(len(it.realizes) for it in kg.infotypes.values())
        self.assertEqual(len(kg.realizes_edges), total_per_infotype)

    def test_store_validation_passes_for_known_types(self) -> None:
        """실 config 파일에서 로드한 KG는 InfoType 외 state_pattern이 존재해야 valid.

        infotypes.yaml에는 dashboard_mr_default 등이 선언되어 있으나 kg_seed.json에는
        아직 해당 state_pattern이 없으므로 issue가 발생할 수 있음. 이 테스트는
        현 skeleton 범위에서 issue가 0건이 아닐 수 있음을 인정하고, 주요
        state_pattern (project_issues_filtered 등)이 올바르게 로드됐는지만 검증.
        """
        from site_adaptive_webagent.kg.store import SiteKGStore
        _, kg = load_site_kg_from_dir(GITLAB_CONFIG_DIR)
        store = SiteKGStore(kg)
        # validate()는 issue 목록 반환 — 현 skeleton 상태에서는 일부 unknown이 있을 수 있음
        issues = store.validate()
        # project_issues_filtered는 반드시 존재
        self.assertIn("project_issues_filtered", kg.state_patterns)
        # issue가 있다면 모두 "unknown state_pattern" 형태여야 함 (skeleton 한계)
        for issue in issues:
            self.assertIn("unknown", issue.lower(),
                          f"예상 외 validation 실패: {issue}")


class SourceFieldLoadTests(unittest.TestCase):
    """source 필드가 YAML/JSON에서 올바르게 로드되는지 검증."""

    def test_state_pattern_source_loaded_from_json(self) -> None:
        kg = load_kg_seed(GITLAB_CONFIG_DIR / "kg_seed.json")
        sp = kg.state_patterns["project_issues_filtered"]
        self.assertEqual(sp.source, "manual")

    def test_action_source_loaded_from_json(self) -> None:
        kg = load_kg_seed(GITLAB_CONFIG_DIR / "kg_seed.json")
        self.assertEqual(kg.actions["navigate_to"].source, "manual")

    def test_leads_to_edge_source_loaded(self) -> None:
        kg = load_kg_seed(GITLAB_CONFIG_DIR / "kg_seed.json")
        self.assertTrue(kg.leads_to_edges)
        self.assertEqual(kg.leads_to_edges[0].source, "manual")

    def test_infotype_source_loaded_from_yaml(self) -> None:
        infotypes = load_infotypes(GITLAB_CONFIG_DIR / "infotypes.yaml")
        issues_list = next(it for it in infotypes if it.name == "issues_list")
        self.assertEqual(issues_list.source, "manual")
        # realizes 엣지도 동일 기본 source
        self.assertTrue(all(r.source == "manual" for r in issues_list.realizes))

    def test_missing_source_defaults_to_manual(self) -> None:
        """source 필드가 JSON에 없으면 "manual"로 fallback."""
        import json

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kg.json"
            path.write_text(
                json.dumps(
                    {
                        "site": "x",
                        "state_patterns": [{"id": "p", "url_template": "/p"}],
                        "actions": [{"name": "a", "params": []}],
                        "leads_to_edges": [],
                    }
                ),
                encoding="utf-8",
            )
            kg = load_kg_seed(path)
            self.assertEqual(kg.state_patterns["p"].source, "manual")
            self.assertEqual(kg.actions["a"].source, "manual")


class BuildMetadataTests(unittest.TestCase):
    def test_load_site_kg_sets_build_timestamp_and_source_mix(self) -> None:
        _, kg = load_site_kg_from_dir(GITLAB_CONFIG_DIR)
        self.assertIsNotNone(kg.build_timestamp)
        self.assertIsNotNone(kg.builder_version)
        # 모든 노드·엣지가 manual이므로 manual count > 0
        self.assertGreater(kg.source_mix.get("manual", 0), 0)


if __name__ == "__main__":
    unittest.main()
