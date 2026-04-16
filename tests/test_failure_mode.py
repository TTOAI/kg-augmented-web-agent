"""scripts/failure_mode.py 단위 테스트."""
from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.failure_mode import (
    cohens_kappa,
    collect_failures,
    kappa_interpretation,
    load_labeled,
    write_template,
)


class CohensKappaTests(unittest.TestCase):
    def test_perfect_agreement(self) -> None:
        k = cohens_kappa(["P", "R", "G"], ["P", "R", "G"])
        self.assertAlmostEqual(k, 1.0)

    def test_chance_only_agreement(self) -> None:
        # 6 labels, 3 P/3 R 각 rater → Pe = 0.5
        # Actual agreements: positions 0,2,3,5 = 4/6 → Po = 0.667
        # κ = (0.667 - 0.5) / (1 - 0.5) = 0.333 (fair agreement)
        k = cohens_kappa(["P", "P", "P", "R", "R", "R"], ["P", "R", "P", "R", "P", "R"])
        self.assertAlmostEqual(k, 0.333, places=2)

    def test_substantial_agreement(self) -> None:
        k = cohens_kappa(["P", "P", "R", "R", "G"], ["P", "P", "R", "G", "G"])
        # 4/5 agree
        self.assertGreater(k, 0.4)

    def test_single_category_returns_one(self) -> None:
        k = cohens_kappa(["P", "P", "P"], ["P", "P", "P"])
        self.assertEqual(k, 1.0)

    def test_empty_returns_nan(self) -> None:
        k = cohens_kappa([], [])
        self.assertTrue(k != k)  # NaN check


class KappaInterpretationTests(unittest.TestCase):
    def test_intervals(self) -> None:
        self.assertEqual(kappa_interpretation(-0.1), "poor (no agreement)")
        self.assertEqual(kappa_interpretation(0.1), "slight")
        self.assertEqual(kappa_interpretation(0.3), "fair")
        self.assertEqual(kappa_interpretation(0.5), "moderate")
        self.assertEqual(kappa_interpretation(0.7), "substantial")
        self.assertEqual(kappa_interpretation(0.9), "almost perfect")


class CollectFailuresTests(unittest.TestCase):
    def test_only_failed_runs_collected(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            # task 1 in N1: success → not collected
            d1 = base / "N1" / "1"
            d1.mkdir(parents=True)
            (d1 / "eval_result.json").write_text(json.dumps({"status": "SUCCESS"}))
            # task 2 in N1: failed → collected
            d2 = base / "N1" / "2"
            d2.mkdir(parents=True)
            (d2 / "eval_result.json").write_text(json.dumps({"status": "FAILED"}))
            (d2 / "agent_response.json").write_text(json.dumps({"status": "SUCCESS"}))
            (d2 / "webarena_verified.log").write_text("line1\nline2\nline3\n")

            failures = collect_failures(base)
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["task_id"], 2)
            self.assertEqual(failures[0]["agent_status"], "SUCCESS")


class WriteTemplateTests(unittest.TestCase):
    def test_template_has_label_columns(self) -> None:
        with TemporaryDirectory() as td:
            base = Path(td)
            vdir = base / "variant_n3"
            d = vdir / "N1" / "44"
            d.mkdir(parents=True)
            (d / "eval_result.json").write_text(json.dumps({"status": "FAILED"}))

            tpl = base / "template.csv"
            n = write_template({"baseline": vdir}, tpl)
            self.assertEqual(n, 1)
            with tpl.open() as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertIn("primary", rows[0])
            self.assertIn("secondary", rows[0])
            self.assertEqual(rows[0]["primary"], "")  # 라벨러가 채워야 함


class LoadLabeledTests(unittest.TestCase):
    def test_normalizes_to_uppercase(self) -> None:
        with TemporaryDirectory() as td:
            p = Path(td) / "rated.csv"
            with p.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["variant", "task_id", "run", "primary", "secondary"])
                w.writerow(["base", 1, "N1", "p", "g"])
            loaded = load_labeled(p)
            self.assertEqual(loaded[("base", 1, "N1")]["primary"], "P")
            self.assertEqual(loaded[("base", 1, "N1")]["secondary"], "G")


if __name__ == "__main__":
    unittest.main()
