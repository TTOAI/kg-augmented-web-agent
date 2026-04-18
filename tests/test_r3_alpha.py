"""R3-α: SITEKG_MODE=alpha + Hook A 결과 system prompt 주입 검증.

Phase 2C β smoke에서 Hook C URL-only false positive로 AR=100% vs NET≤40% gap을
관찰. R3-α는 Hook B/C 완전 제거 + Hook A 결과를 passive context로 system prompt에
주입하는 실험. 이 테스트는 mode gating + context 포맷 정확성을 단위 수준에서 검증.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from site_adaptive_webagent.agent.kg_integration import (
    format_kg_context_for_prompt,
)
from site_adaptive_webagent.kg import KGContext, KGLookup
from site_adaptive_webagent.kg.seed import load_site_kg_from_dir
from site_adaptive_webagent.runtime.executor import _sitekg_mode

FIXTURE_KG_DIR = Path(__file__).parent / "fixtures" / "kg_test_site"


class SitekgModeTests(unittest.TestCase):
    def test_default_is_full(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SITEKG_MODE", None)
            self.assertEqual(_sitekg_mode(), "full")

    def test_alpha_mode(self) -> None:
        with patch.dict(os.environ, {"SITEKG_MODE": "alpha"}):
            self.assertEqual(_sitekg_mode(), "alpha")

    def test_disabled_mode(self) -> None:
        with patch.dict(os.environ, {"SITEKG_MODE": "disabled"}):
            self.assertEqual(_sitekg_mode(), "disabled")

    def test_case_insensitive(self) -> None:
        with patch.dict(os.environ, {"SITEKG_MODE": "ALPHA"}):
            self.assertEqual(_sitekg_mode(), "alpha")

    def test_whitespace_stripped(self) -> None:
        with patch.dict(os.environ, {"SITEKG_MODE": "  alpha  "}):
            self.assertEqual(_sitekg_mode(), "alpha")


class FormatKgContextForPromptTests(unittest.TestCase):
    def setUp(self) -> None:
        site_config, kg = load_site_kg_from_dir(FIXTURE_KG_DIR)
        self.kg_context = KGContext(kg=kg, site_config=site_config)

    def _first_infotype_with_realizes(self) -> str:
        for name, it in self.kg_context.kg.infotypes.items():
            if it.realizes:
                return name
        self.skipTest("fixture has no InfoType with realizes — cannot run")
        return ""  # unreachable but satisfies type checker

    def test_returns_block_with_infotype_name(self) -> None:
        infotype_name = self._first_infotype_with_realizes()
        lookup = KGLookup(infotype=infotype_name, bindings={})
        block = format_kg_context_for_prompt(self.kg_context, lookup)
        self.assertIn(infotype_name, block)
        self.assertIn("Site knowledge", block)

    def test_block_is_informational_not_command(self) -> None:
        """R3-α 원칙: command가 아닌 informational. 강제 지시 동사 없어야 함."""
        infotype_name = self._first_infotype_with_realizes()
        lookup = KGLookup(infotype=infotype_name, bindings={})
        block = format_kg_context_for_prompt(self.kg_context, lookup)
        # 강제성 키워드 부재 확인 (KG가 agent에게 명령하지 않음)
        lowered = block.lower()
        self.assertNotIn("you must", lowered)
        self.assertNotIn("you shall", lowered)
        self.assertIn("hints", lowered)  # informational 키워드

    def test_includes_required_bindings_when_present(self) -> None:
        for name, it in self.kg_context.kg.infotypes.items():
            if it.required_bindings and it.realizes:
                lookup = KGLookup(infotype=name, bindings={})
                block = format_kg_context_for_prompt(self.kg_context, lookup)
                for b in it.required_bindings:
                    self.assertIn(b, block)
                return
        self.skipTest("no InfoType with required_bindings + realizes in fixture")

    def test_includes_inferred_bindings_when_nonempty(self) -> None:
        infotype_name = self._first_infotype_with_realizes()
        lookup = KGLookup(
            infotype=infotype_name,
            bindings={"project_path": "myrepo", "empty_val": ""},
        )
        block = format_kg_context_for_prompt(self.kg_context, lookup)
        self.assertIn("project_path=myrepo", block)
        # 빈 값은 포함 안 함
        self.assertNotIn("empty_val=", block)

    def test_unknown_infotype_returns_empty(self) -> None:
        lookup = KGLookup(infotype="nonexistent_infotype_xyz", bindings={})
        block = format_kg_context_for_prompt(self.kg_context, lookup)
        self.assertEqual(block, "")

    def test_respects_max_patterns(self) -> None:
        """max_patterns=1이면 URL pattern 라인 최대 1개."""
        infotype_name = self._first_infotype_with_realizes()
        lookup = KGLookup(infotype=infotype_name, bindings={})
        block = format_kg_context_for_prompt(
            self.kg_context, lookup, max_patterns=1, max_adjacent=0,
        )
        # 각 pattern은 "- `url`" 형식의 라인
        pattern_lines = [l for l in block.splitlines() if l.startswith("- `")]
        self.assertLessEqual(len(pattern_lines), 1)


class SitekgModeIntegrationTests(unittest.TestCase):
    """alpha mode에서 Hook B(rewrite) 호출이 skip되는지 얇게 검증.

    full 동작 복원 체크(_sitekg_mode 반환값)로 간접 검증. 직접적인 rewrite_plan
    호출 skip은 test_kg_integration.py의 기존 dry-run 테스트로 이미 커버됨.
    """

    def test_mode_alpha_gates_hook_b_c(self) -> None:
        with patch.dict(os.environ, {"SITEKG_MODE": "alpha"}):
            self.assertEqual(_sitekg_mode(), "alpha")
            # executor 로직: mode != "full"이면 rewrite/target_reached 호출 skip
            self.assertNotEqual(_sitekg_mode(), "full")

    def test_mode_full_preserves_hook_b_c(self) -> None:
        with patch.dict(os.environ, {"SITEKG_MODE": "full"}):
            self.assertEqual(_sitekg_mode(), "full")


if __name__ == "__main__":
    unittest.main()
