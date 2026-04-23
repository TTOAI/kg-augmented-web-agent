"""scripts/paired_stats.py 단위 테스트.

핵심 검증:
- McNemar exact test가 알려진 입력에 대해 정확한 p-value 산출
- Wilcoxon signed-rank가 비교적 정확한 정규근사 결과
- Wilson CI의 boundary case (k=0, k=n)
- 2-variant pairwise 비교 결과의 contingency 정합성
"""
from __future__ import annotations

import csv
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.eval.paired_stats import (
    compare_binary,
    compare_continuous,
    load_paired_csv,
    load_raw_csv,
    mcnemar_chi2_corrected,
    mcnemar_exact,
    wilcoxon_signed_rank,
    wilson_ci,
)


class WilsonCITests(unittest.TestCase):
    def test_zero_n_returns_zero(self) -> None:
        self.assertEqual(wilson_ci(0, 0), (0.0, 0.0))

    def test_all_success_upper_close_to_one(self) -> None:
        lo, hi = wilson_ci(10, 10)
        self.assertGreater(lo, 0.6)  # k=10/n=10이면 lower bound ~0.72
        self.assertLessEqual(hi, 1.0)

    def test_all_fail_lower_zero(self) -> None:
        lo, hi = wilson_ci(0, 10)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.4)

    def test_50_50_centered_around_half(self) -> None:
        lo, hi = wilson_ci(5, 10)
        self.assertAlmostEqual((lo + hi) / 2, 0.5, places=1)


class McNemarExactTests(unittest.TestCase):
    def test_no_discordant_returns_one(self) -> None:
        self.assertEqual(mcnemar_exact(0, 0), 1.0)

    def test_symmetric_discordant_returns_one(self) -> None:
        # b=c → no evidence of difference → p=1.0
        p = mcnemar_exact(5, 5)
        self.assertAlmostEqual(p, 1.0, places=2)

    def test_extreme_imbalance_low_p(self) -> None:
        # b=10, c=0 → 모든 discordant pair가 한 방향. p < 0.01
        p = mcnemar_exact(10, 0)
        self.assertLess(p, 0.01)

    def test_known_value_b3_c0(self) -> None:
        # b=3, c=0: P(X ≤ 0 | n=3, p=0.5) = 0.125, two-tailed = 0.25
        p = mcnemar_exact(3, 0)
        self.assertAlmostEqual(p, 0.25, places=3)

    def test_known_value_b8_c2(self) -> None:
        # b=8, c=2 → n=10. P(X ≤ 2) = (1+10+45)/1024 = 56/1024 = 0.0547
        # two-tailed = 0.1094
        p = mcnemar_exact(8, 2)
        self.assertAlmostEqual(p, 0.1094, places=3)


class McNemarChi2Tests(unittest.TestCase):
    def test_zero_returns_one(self) -> None:
        chi2, p = mcnemar_chi2_corrected(0, 0)
        self.assertEqual(chi2, 0.0)
        self.assertEqual(p, 1.0)

    def test_continuity_correction_applied(self) -> None:
        # b=5, c=0: χ² = (5-1)² / 5 = 16/5 = 3.2
        chi2, _ = mcnemar_chi2_corrected(5, 0)
        self.assertAlmostEqual(chi2, 3.2, places=2)


class WilcoxonTests(unittest.TestCase):
    def test_all_zero_returns_one(self) -> None:
        w, p = wilcoxon_signed_rank([0, 0, 0])
        self.assertEqual(p, 1.0)

    def test_all_positive_one_sided_extreme(self) -> None:
        # 모든 diff가 양수 → W+ = N(N+1)/2 → 매우 작은 p (two-tailed)
        w, p = wilcoxon_signed_rank([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
        self.assertLess(p, 0.05)

    def test_symmetric_diffs_high_p(self) -> None:
        w, p = wilcoxon_signed_rank([-1.0, 1.0, -2.0, 2.0])
        # ranks are 1.5, 1.5, 3.5, 3.5 — perfectly symmetric → p=1.0
        self.assertAlmostEqual(p, 1.0, places=2)


class CompareBinaryTests(unittest.TestCase):
    def test_perfect_correlation(self) -> None:
        a = {1: {"majority_success": 1}, 2: {"majority_success": 1}, 3: {"majority_success": 0}}
        b = {1: {"majority_success": 1}, 2: {"majority_success": 1}, 3: {"majority_success": 0}}
        result = compare_binary(a, b)
        self.assertEqual(result["discordant"]["b"], 0)
        self.assertEqual(result["discordant"]["c"], 0)
        self.assertEqual(result["mcnemar_p_exact"], 1.0)

    def test_full_disagreement(self) -> None:
        a = {1: {"majority_success": 1}, 2: {"majority_success": 0}, 3: {"majority_success": 1}}
        b = {1: {"majority_success": 0}, 2: {"majority_success": 1}, 3: {"majority_success": 0}}
        result = compare_binary(a, b)
        self.assertEqual(result["discordant"]["b"], 2)  # A succ, B fail
        self.assertEqual(result["discordant"]["c"], 1)  # A fail, B succ

    def test_only_common_tasks_compared(self) -> None:
        a = {1: {"majority_success": 1}, 2: {"majority_success": 1}}
        b = {1: {"majority_success": 0}, 99: {"majority_success": 1}}
        result = compare_binary(a, b)
        self.assertEqual(result["n_common"], 1)


class CompareContinuousTests(unittest.TestCase):
    def test_higher_a_yields_negative_diffs(self) -> None:
        raw_a = {1: [{"step_count": "10"}], 2: [{"step_count": "20"}]}
        raw_b = {1: [{"step_count": "5"}], 2: [{"step_count": "15"}]}
        r = compare_continuous(raw_a, raw_b, "step_count")
        self.assertEqual(r["a_mean"], 15.0)
        self.assertEqual(r["b_mean"], 10.0)
        self.assertEqual(r["n_paired"], 2)

    def test_missing_metric_skipped(self) -> None:
        raw_a = {1: [{"step_count": ""}, {"step_count": "10"}]}
        raw_b = {1: [{"step_count": "5"}, {"step_count": "15"}]}
        r = compare_continuous(raw_a, raw_b, "step_count")
        # task 1 in both; A mean uses only "10", B mean averages 5+15=10
        self.assertEqual(r["a_mean"], 10.0)
        self.assertEqual(r["b_mean"], 10.0)


class CSVRoundTripTests(unittest.TestCase):
    def test_load_paired_csv(self) -> None:
        with TemporaryDirectory() as td:
            p = Path(td) / "paired.csv"
            with p.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["task_id", "task_type", "majority_success",
                            "all3_success", "any_success"])
                w.writerow([1, "RETRIEVE", 1, 1, 1])
                w.writerow([2, "MUTATE", 0, 0, 1])
            loaded = load_paired_csv(p)
            self.assertIn(1, loaded)
            self.assertEqual(loaded[1]["majority_success"], 1)
            self.assertEqual(loaded[2]["task_type"], "MUTATE")

    def test_load_raw_csv_groups_by_task(self) -> None:
        with TemporaryDirectory() as td:
            p = Path(td) / "raw.csv"
            with p.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["task_id", "run", "step_count"])
                w.writerow([1, "N1", "10"])
                w.writerow([1, "N2", "12"])
                w.writerow([2, "N1", "5"])
            loaded = load_raw_csv(p)
            self.assertEqual(len(loaded[1]), 2)
            self.assertEqual(len(loaded[2]), 1)


if __name__ == "__main__":
    unittest.main()
