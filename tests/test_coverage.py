"""scripts/coverage.py 단위 테스트."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.coverage import collect_variant_coverage, load_frozen_metadata


def _make_log(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class CollectVariantCoverageTests(unittest.TestCase):
    def test_no_logs_returns_empty(self) -> None:
        with TemporaryDirectory() as td:
            data = collect_variant_coverage(Path(td))
            self.assertEqual(data["total_tasks"], 0)

    def test_classified_task_counted(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            log = (
                "[INFO] starting agent\n"
                "[KG] Hook A (full): infotype=project_issue_list bindings={'project_path': 'foo'}\n"
                "[INFO] step=1\n"
            )
            _make_log(log, base / "N1" / "44" / "webarena_verified.log")
            data = collect_variant_coverage(base)
            self.assertEqual(data["total_tasks"], 1)
            self.assertEqual(data["classified_tasks"], 1)
            self.assertEqual(data["coverage_pct"], 100.0)

    def test_declined_task_separate_count(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            log = "[KG] Hook A (full): classification declined — baseline path\n"
            _make_log(log, base / "N1" / "44" / "webarena_verified.log")
            data = collect_variant_coverage(base)
            self.assertEqual(data["classified_tasks"], 0)
            self.assertEqual(data["declined_tasks"], 1)

    def test_info_ignored_distinct(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            log = "[KG] Hook A (info_ignored): LLM call performed, result discarded\n"
            _make_log(log, base / "N1" / "44" / "webarena_verified.log")
            data = collect_variant_coverage(base)
            # info_ignored도 hook_a_called로 카운트
            self.assertEqual(data["total_tasks"], 1)
            byt = data["by_task"][44]
            self.assertEqual(byt["hook_a_info_ignored"], 1)

    def test_top_infotypes_aggregated(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            for tid, infotype in [(1, "alpha"), (2, "beta"), (3, "alpha")]:
                _make_log(
                    f"[KG] Hook A (full): infotype={infotype} bindings={{}}\n",
                    base / "N1" / str(tid) / "webarena_verified.log",
                )
            data = collect_variant_coverage(base)
            top = dict(data["top_infotypes"])
            self.assertEqual(top["alpha"], 2)
            self.assertEqual(top["beta"], 1)


class LoadFrozenMetadataTests(unittest.TestCase):
    def test_missing_path_returns_error(self) -> None:
        meta = load_frozen_metadata(Path("/nonexistent/frozen.json"))
        self.assertIn("error", meta)

    def test_extracts_source_mix_and_metadata(self) -> None:
        with TemporaryDirectory() as td:
            kg_path = Path(td) / "frozen.json"
            kg_path.write_text(json.dumps({
                "build_timestamp": "2026-04-16T16:46:55Z",
                "git_rev": "abc1234",
                "builder_version": "v1",
                "source_mix": {"crawl": 100, "llm": 50, "manual": 0},
                "state_patterns": {"a": {}, "b": {}},
                "infotypes": {"x": {}},
                "actions": {"act1": {}, "act2": {}},
                "realizes_edges": [],
                "leads_to_edges": [{}, {}, {}],
            }))
            meta_path = kg_path.with_suffix(".meta.json")
            meta_path.write_text(json.dumps({"note": "test note"}))

            meta = load_frozen_metadata(kg_path)
            self.assertEqual(meta["build_timestamp"], "2026-04-16T16:46:55Z")
            self.assertEqual(meta["source_mix"]["crawl"], 100)
            self.assertEqual(meta["n_state_patterns"], 2)
            self.assertEqual(meta["n_actions"], 2)
            self.assertEqual(meta["meta_note"], "test note")


if __name__ == "__main__":
    unittest.main()
