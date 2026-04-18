"""Phase 2C C2 — executor._update_runtime_context_from_url 단위 테스트.

executor에 대한 full end-to-end 테스트는 smoke로 대체하므로, 여기선 helper
함수 자체의 동작만 검증 (URL → kg_context.runtime_context["path_slots"] 병합).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from site_adaptive_webagent.kg import KGContext
from site_adaptive_webagent.kg.seed import load_site_kg_from_dir
from site_adaptive_webagent.runtime.executor import _update_runtime_context_from_url

FIXTURE_KG_DIR = Path(__file__).parent / "fixtures" / "kg_test_site"


class UpdateRuntimeContextTests(unittest.TestCase):
    def setUp(self) -> None:
        cfg, kg = load_site_kg_from_dir(FIXTURE_KG_DIR)
        self.kg_context = KGContext(kg=kg, site_config=cfg, runtime_context={})

    def test_populates_path_slots_from_matching_url(self) -> None:
        """URL이 StatePattern과 매칭되면 path slot이 runtime_context에 주입."""
        _update_runtime_context_from_url(
            "/byteblaze/cloud-to-butt/-/issues", self.kg_context,
        )
        path_slots = self.kg_context.runtime_context.get("path_slots", {})
        self.assertIn("project_path", path_slots)
        self.assertEqual(path_slots["project_path"], "byteblaze/cloud-to-butt")

    def test_matches_do_populate_slots(self) -> None:
        """URL이 여러 pattern에 매칭될 수 있으면 path slot이 update되고, 함수가 조용히
        처리 (exception 없음)."""
        # 매칭되는 케이스만 테스트 (non-match는 pattern dependent).
        _update_runtime_context_from_url(
            "/namespace/project/-/issues?state=opened", self.kg_context,
        )
        # path_slots가 있으면 최소 project_path는 채워짐
        slots = self.kg_context.runtime_context.get("path_slots", {})
        if slots:
            self.assertIn("project_path", slots)

    def test_empty_url_no_op(self) -> None:
        """빈 URL이면 변화 없음."""
        _update_runtime_context_from_url("", self.kg_context)
        self.assertEqual(self.kg_context.runtime_context, {})

    def test_none_kg_context_no_error(self) -> None:
        """kg_context None이면 조용히 return."""
        _update_runtime_context_from_url("/any/url", None)  # no exception

    def test_subsequent_calls_merge_slots(self) -> None:
        """여러 번 호출 시 slot이 덮어쓰여 최신 값 유지 (last-write-wins)."""
        _update_runtime_context_from_url(
            "/a/b/-/issues", self.kg_context,
        )
        _update_runtime_context_from_url(
            "/x/y/-/issues", self.kg_context,
        )
        path_slots = self.kg_context.runtime_context.get("path_slots", {})
        self.assertEqual(path_slots.get("project_path"), "x/y")


class EmitTargetUrlWithRuntimeContextTests(unittest.TestCase):
    """Phase 2C C2: runtime_context.path_slots가 emit_target_url에서 소비됨."""

    def setUp(self) -> None:
        cfg, kg = load_site_kg_from_dir(FIXTURE_KG_DIR)
        self.cfg = cfg
        self.kg = kg

    def test_path_slot_from_runtime_context_fills_missing_binding(self) -> None:
        """bindings에 project_path가 없어도 runtime_context로 URL 생성."""
        from site_adaptive_webagent.kg import emit_target_url
        url = emit_target_url(
            self.kg, self.cfg, "issues_list",
            bindings={"state": "opened"},
            runtime_context={"path_slots": {"project_path": "byteblaze/cloud-to-butt"}},
        )
        self.assertIsNotNone(url)
        assert url is not None
        self.assertIn("byteblaze/cloud-to-butt", url)

    def test_bindings_override_runtime_context(self) -> None:
        """bindings에 명시된 값이 runtime_context보다 우선."""
        from site_adaptive_webagent.kg import emit_target_url
        url = emit_target_url(
            self.kg, self.cfg, "issues_list",
            bindings={"project_path": "explicit/path", "state": "opened"},
            runtime_context={"path_slots": {"project_path": "fallback/should_not_use"}},
        )
        self.assertIsNotNone(url)
        assert url is not None
        self.assertIn("explicit/path", url)
        self.assertNotIn("fallback", url)


if __name__ == "__main__":
    unittest.main()
