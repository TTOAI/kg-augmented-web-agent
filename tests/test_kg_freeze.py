"""kg.seed.run_freeze 단위 테스트.

git_rev은 subprocess 호출이 환경에 의존하므로 None인 경우만 검증.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from kg_augmented_webagent.kg.seed.run_freeze import freeze
from kg_augmented_webagent.kg.store import SiteKGStore


FIXTURE_KG_DIR = Path(__file__).parent / "fixtures" / "kg_test_site"


def _copy_gitlab_to(tmp: Path) -> Path:
    """실 GitLab manual seed를 tmp/sites/gitlab/로 복사 (테스트가 변경 안전)."""
    site_root = tmp / "sites"
    target = site_root / "gitlab"
    shutil.copytree(FIXTURE_KG_DIR, target)
    # 기존 frozen_kg/ 디렉토리가 있을 경우 제거 (테스트 격리)
    fz = target / "frozen_kg"
    if fz.exists():
        shutil.rmtree(fz)
    return site_root


class FreezeTests(unittest.TestCase):
    def test_creates_snapshot_and_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site_root = _copy_gitlab_to(Path(tmp))
            snapshot, meta = freeze(
                site="gitlab",
                site_config_dir=site_root,
                crawl_dir=None,
                derivation_dir=None,
                note="unit test",
                timestamp="2026-04-16T00-00-00Z",
            )
            self.assertTrue(snapshot.exists())
            self.assertTrue(meta.exists())
            meta_data = json.loads(meta.read_text(encoding="utf-8"))
            self.assertEqual(meta_data["timestamp"], "2026-04-16T00-00-00Z")
            self.assertEqual(meta_data["note"], "unit test")
            self.assertIn("source_mix", meta_data)

    def test_snapshot_round_trip_preserves_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site_root = _copy_gitlab_to(Path(tmp))
            snapshot, _ = freeze(
                site="gitlab",
                site_config_dir=site_root,
                crawl_dir=None,
                derivation_dir=None,
                note="rt",
                timestamp="2026-04-16T00-01-00Z",
            )
            kg = SiteKGStore.load(snapshot).kg
            self.assertIsNotNone(kg.build_timestamp)
            self.assertEqual(kg.source_mix.get("manual", 0) > 0, True)

    def test_duplicate_timestamp_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site_root = _copy_gitlab_to(Path(tmp))
            ts = "2026-04-16T00-02-00Z"
            freeze(
                site="gitlab", site_config_dir=site_root,
                crawl_dir=None, derivation_dir=None, timestamp=ts,
            )
            with self.assertRaises(FileExistsError):
                freeze(
                    site="gitlab", site_config_dir=site_root,
                    crawl_dir=None, derivation_dir=None, timestamp=ts,
                )

    def test_index_md_appended(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site_root = _copy_gitlab_to(Path(tmp))
            freeze(
                site="gitlab", site_config_dir=site_root,
                crawl_dir=None, derivation_dir=None,
                timestamp="2026-04-16T00-03-00Z", note="first",
            )
            freeze(
                site="gitlab", site_config_dir=site_root,
                crawl_dir=None, derivation_dir=None,
                timestamp="2026-04-16T00-04-00Z", note="second",
            )
            idx = (site_root / "gitlab" / "frozen_kg" / "INDEX.md").read_text(encoding="utf-8")
            self.assertIn("first", idx)
            self.assertIn("second", idx)
            self.assertIn("2026-04-16T00-03-00Z", idx)
            self.assertIn("2026-04-16T00-04-00Z", idx)


if __name__ == "__main__":
    unittest.main()
