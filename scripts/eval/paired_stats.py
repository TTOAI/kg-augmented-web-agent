"""Paired statistical tests for variant comparison (binary success + continuous cost).

지원하는 테스트:
- **McNemar's exact test** (paired binary, primary outcome 비교)
- **Wilcoxon signed-rank test** (paired continuous, token/step/time 비교)
- **Wilson 95% CI** (binary success rate)
- **Bonferroni correction** (multiple comparisons)

입력: 2~3 variant 디렉토리. 각 디렉토리는 `analyze_baseline.py`가 만든 paired.csv 형식.
출력: 페어와이즈 비교표 + sub-test별 p-value + 결정 narrative.

사용:
  # 2 variants
  python scripts/paired_stats.py \\
      --variant baseline=output/<base>/analysis \\
      --variant treatment=output/<treat>/analysis \\
      --output output/analysis/paired_stats.md

  # 3 variants (07 §5 ablation)
  python scripts/paired_stats.py \\
      --variant baseline=output/baseline_n3/analysis \\
      --variant info_ignored=output/kg_info_ignored_n3/analysis \\
      --variant full_kg=output/kg_full_n3/analysis \\
      --bonferroni 3 \\
      --output output/analysis/paired_stats.md

self-contained: scipy 의존성 없음 (chi2/binomial/normal 직접 구현). reviewer가 즉시 재현 가능.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path


# ---------------------------------------------------------------------------
# Statistical primitives (self-contained)
# ---------------------------------------------------------------------------

def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% CI for binary success rate."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return (max(0.0, lo), min(1.0, hi))


def _binomial_pmf(k: int, n: int, p: float) -> float:
    """P(X = k) for X ~ Binomial(n, p). Numerically stable via lgamma."""
    if k < 0 or k > n:
        return 0.0
    log_coef = (
        math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    )
    if p == 0:
        return 1.0 if k == 0 else 0.0
    if p == 1:
        return 1.0 if k == n else 0.0
    return math.exp(log_coef + k * math.log(p) + (n - k) * math.log(1 - p))


def mcnemar_exact(b: int, c: int) -> float:
    """McNemar's exact two-tailed p-value.

    b: variant_A=success & variant_B=fail
    c: variant_A=fail & variant_B=success
    Both are "discordant" pairs. Under H0 (no difference), b ~ Binomial(b+c, 0.5).
    Two-tailed p = 2 * min(P(X ≤ min(b,c)), 0.5).
    """
    n = b + c
    if n == 0:
        return 1.0  # No discordant pairs → no evidence of difference
    k = min(b, c)
    # Sum of tail: P(X ≤ k)
    tail = sum(_binomial_pmf(i, n, 0.5) for i in range(k + 1))
    p = 2.0 * tail
    return min(1.0, p)


def mcnemar_chi2_corrected(b: int, c: int) -> tuple[float, float]:
    """McNemar's χ² (continuity corrected) + asymptotic p-value.

    χ² = (|b - c| - 1)² / (b + c). Use when b + c ≥ 25 (asymptotic regime).
    For smaller samples, prefer mcnemar_exact.
    """
    n = b + c
    if n == 0:
        return (0.0, 1.0)
    chi2 = (abs(b - c) - 1) ** 2 / n if n > 0 else 0.0
    # Survival of chi2 with df=1: P(X² > chi2) = erfc(sqrt(chi2/2))
    p = math.erfc(math.sqrt(chi2 / 2)) if chi2 > 0 else 1.0
    return (chi2, p)


def _normal_cdf(x: float) -> float:
    """Standard normal CDF via erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def wilcoxon_signed_rank(diffs: list[float]) -> tuple[float, float]:
    """Wilcoxon signed-rank test (two-sided) — normal approximation.

    diffs: paired differences (variant_A - variant_B). 0은 제외.
    Returns (W+, p-value).

    50 task 표본에 대해 normal approx 적합 (n ≥ 20). small-n exact는 미구현.
    """
    nonzero = [d for d in diffs if d != 0]
    n = len(nonzero)
    if n == 0:
        return (0.0, 1.0)

    # Rank by absolute value, handle ties with average rank
    indexed = sorted(enumerate(nonzero), key=lambda x: abs(x[1]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and abs(indexed[j + 1][1]) == abs(indexed[i][1]):
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            orig_idx = indexed[k][0]
            ranks[orig_idx] = avg
        i = j + 1

    # Sum of positive ranks
    w_plus = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    # Expected and variance under H0
    mean_w = n * (n + 1) / 4.0
    var_w = n * (n + 1) * (2 * n + 1) / 24.0
    if var_w == 0:
        return (w_plus, 1.0)
    z = (w_plus - mean_w) / math.sqrt(var_w)
    # Two-tailed p
    p = 2.0 * (1.0 - _normal_cdf(abs(z)))
    return (w_plus, min(1.0, p))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_paired_csv(path: Path) -> dict[int, dict]:
    """analyze_baseline.py의 paired.csv → {task_id: {majority_success, ...}}."""
    out: dict[int, dict] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task_id = int(row["task_id"])
            out[task_id] = {
                "task_type": row.get("task_type", ""),
                "majority_success": int(row.get("majority_success", "0")),
                "all3_success": int(row.get("all3_success", "0")),
                "any_success": int(row.get("any_success", "0")),
            }
    return out


def load_raw_csv(path: Path) -> dict[int, list[dict]]:
    """raw.csv → {task_id: [run rows]} (token/step/time 평균 계산용)."""
    out: dict[int, list[dict]] = defaultdict(list)
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            task_id = int(row["task_id"])
            out[task_id].append(row)
    return out


def task_mean_metric(task_rows: list[dict], metric_field: str) -> float | None:
    """N runs의 metric 평균 (값 없으면 None)."""
    vals: list[float] = []
    for row in task_rows:
        v = row.get(metric_field, "")
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    return sum(vals) / len(vals) if vals else None


# ---------------------------------------------------------------------------
# Pairwise comparison
# ---------------------------------------------------------------------------

def compare_binary(
    paired_a: dict[int, dict], paired_b: dict[int, dict],
    success_field: str = "majority_success",
    task_type_filter: str | None = None,
) -> dict:
    """McNemar + 성공률 비교 for two variants.

    task_type_filter가 주어지면 해당 task_type task만 사용 (per-type subset 분석).
    """
    common = sorted(set(paired_a) & set(paired_b))
    if task_type_filter is not None:
        common = [
            t for t in common
            if paired_a[t].get("task_type") == task_type_filter
            and paired_b[t].get("task_type") == task_type_filter
        ]
    a_succ = sum(paired_a[t][success_field] for t in common)
    b_succ = sum(paired_b[t][success_field] for t in common)
    n = len(common)

    # 2x2 contingency
    a_yes_b_yes = sum(1 for t in common if paired_a[t][success_field] and paired_b[t][success_field])
    a_yes_b_no = sum(1 for t in common if paired_a[t][success_field] and not paired_b[t][success_field])
    a_no_b_yes = sum(1 for t in common if not paired_a[t][success_field] and paired_b[t][success_field])
    a_no_b_no = sum(1 for t in common if not paired_a[t][success_field] and not paired_b[t][success_field])

    # Discordant pairs
    b = a_yes_b_no  # A success, B fail
    c = a_no_b_yes  # A fail, B success

    p_exact = mcnemar_exact(b, c)
    chi2, p_chi2 = mcnemar_chi2_corrected(b, c)
    a_lo, a_hi = wilson_ci(a_succ, n)
    b_lo, b_hi = wilson_ci(b_succ, n)

    return {
        "n_common": n,
        "a_success": a_succ,
        "b_success": b_succ,
        "a_rate": a_succ / n if n else 0.0,
        "b_rate": b_succ / n if n else 0.0,
        "a_ci": (a_lo, a_hi),
        "b_ci": (b_lo, b_hi),
        "contingency": {
            "a_yes_b_yes": a_yes_b_yes,
            "a_yes_b_no": a_yes_b_no,  # b
            "a_no_b_yes": a_no_b_yes,  # c
            "a_no_b_no": a_no_b_no,
        },
        "discordant": {"b": b, "c": c},
        "mcnemar_chi2": chi2,
        "mcnemar_p_chi2": p_chi2,
        "mcnemar_p_exact": p_exact,
    }


def compare_continuous(
    raw_a: dict[int, list[dict]], raw_b: dict[int, list[dict]],
    metric_field: str,
    task_type_filter: str | None = None,
) -> dict:
    """Wilcoxon signed-rank for two variants on continuous metric.

    task_type_filter가 주어지면 해당 task_type task만 사용 (per-type subset 분석).
    task_type은 raw_a/raw_b의 각 row에서 "task_type" 칼럼 확인 (analyze_baseline.py 출력).
    """
    common = sorted(set(raw_a) & set(raw_b))
    if task_type_filter is not None:
        common = [
            t for t in common
            if any(row.get("task_type") == task_type_filter for row in raw_a[t])
            and any(row.get("task_type") == task_type_filter for row in raw_b[t])
        ]
    diffs: list[float] = []
    a_means: list[float] = []
    b_means: list[float] = []
    for t in common:
        ma = task_mean_metric(raw_a[t], metric_field)
        mb = task_mean_metric(raw_b[t], metric_field)
        if ma is None or mb is None:
            continue
        a_means.append(ma)
        b_means.append(mb)
        diffs.append(ma - mb)
    w_plus, p = wilcoxon_signed_rank(diffs)
    return {
        "n_paired": len(diffs),
        "a_mean": sum(a_means) / len(a_means) if a_means else 0.0,
        "b_mean": sum(b_means) / len(b_means) if b_means else 0.0,
        "median_diff": sorted(diffs)[len(diffs) // 2] if diffs else 0.0,
        "w_plus": w_plus,
        "p_value": p,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def render_report(
    variants: dict[str, tuple[Path, Path]],  # name -> (paired.csv, raw.csv)
    bonferroni_factor: int,
) -> str:
    """Multiple variants pairwise table + dual H1 sub-tests."""
    lines = [
        "# Paired Statistical Tests",
        "",
        "Generated by `scripts/paired_stats.py`.",
        "",
        f"- Variants: {len(variants)} ({', '.join(variants.keys())})",
        f"- Bonferroni factor: {bonferroni_factor} → effective α = {0.05 / bonferroni_factor:.4f}",
        "",
    ]

    # Load all variants
    loaded: dict[str, tuple[dict, dict]] = {}
    for name, (paired_path, raw_path) in variants.items():
        if not paired_path.exists():
            lines.append(f"⚠️ Missing paired.csv for `{name}`: {paired_path}")
            continue
        loaded[name] = (
            load_paired_csv(paired_path),
            load_raw_csv(raw_path) if raw_path.exists() else {},
        )
    if len(loaded) < 2:
        lines.append("Insufficient variants — need ≥ 2 with paired.csv.")
        return "\n".join(lines)

    # Per-variant overall summary
    lines += ["## Per-variant summary", "", "| variant | n | success | rate (Wilson 95% CI) |",
              "|---|---|---|---|"]
    for name, (paired, _) in loaded.items():
        n = len(paired)
        k = sum(p["majority_success"] for p in paired.values())
        lo, hi = wilson_ci(k, n)
        lines.append(f"| `{name}` | {n} | {k} | {100*k/n:.1f}% [{100*lo:.1f}%, {100*hi:.1f}%] |")
    lines.append("")

    # Pairwise comparisons
    pairs = list(combinations(loaded.keys(), 2))
    lines += ["## H1a (정확도) — McNemar's test", ""]
    for a_name, b_name in pairs:
        paired_a, _ = loaded[a_name]
        paired_b, _ = loaded[b_name]
        result = compare_binary(paired_a, paired_b)
        cont = result["contingency"]
        sig_exact = "✅" if result["mcnemar_p_exact"] < 0.05 / bonferroni_factor else "—"
        lines += [
            f"### `{a_name}` vs `{b_name}`",
            "",
            f"- Common tasks: {result['n_common']}",
            f"- `{a_name}` success: {result['a_success']} ({100*result['a_rate']:.1f}%)",
            f"- `{b_name}` success: {result['b_success']} ({100*result['b_rate']:.1f}%)",
            "",
            "| | B success | B fail |",
            "|---|---|---|",
            f"| **A success** | {cont['a_yes_b_yes']} | {cont['a_yes_b_no']} (= b) |",
            f"| **A fail** | {cont['a_no_b_yes']} (= c) | {cont['a_no_b_no']} |",
            "",
            f"- Discordant: b = {result['discordant']['b']}, c = {result['discordant']['c']}",
            f"- McNemar χ² (cc): {result['mcnemar_chi2']:.4f}, p (asymptotic) = {result['mcnemar_p_chi2']:.4f}",
            f"- **McNemar exact two-tailed p = {result['mcnemar_p_exact']:.4f}** {sig_exact}",
            "",
        ]

    # H1b — continuous metrics
    lines += ["## H1b (효율) — Wilcoxon signed-rank", ""]
    for metric, label in [
        ("step_count", "Step count"),
        ("wall_time_sec", "Wall-clock time (s)"),
        ("llm_calls", "LLM call count"),
    ]:
        lines += [f"### {label}", "",
                  "| comparison | n | A mean | B mean | median diff | W+ | p-value | sig |",
                  "|---|---|---|---|---|---|---|---|"]
        for a_name, b_name in pairs:
            _, raw_a = loaded[a_name]
            _, raw_b = loaded[b_name]
            if not raw_a or not raw_b:
                continue
            r = compare_continuous(raw_a, raw_b, metric)
            sig = "✅" if r["p_value"] < 0.05 / bonferroni_factor else "—"
            lines.append(
                f"| `{a_name}` vs `{b_name}` | {r['n_paired']} | "
                f"{r['a_mean']:.2f} | {r['b_mean']:.2f} | "
                f"{r['median_diff']:+.2f} | {r['w_plus']:.1f} | "
                f"{r['p_value']:.4f} | {sig} |"
            )
        lines.append("")

    # Per-type subset analysis (H1_per_type — docs/06 §4-4)
    lines += [
        "## H1_per_type — per task_type 분할 분석",
        "",
        "연구 질문: **KG가 task type에 따라 어떤 heterogeneous effect**를 주는가?",
        "Per-type Bonferroni α = 0.05/3 = 0.0167.",
        "",
    ]
    per_type_alpha = 0.05 / 3
    task_types = ("NAVIGATE", "RETRIEVE", "MUTATE")
    for tt in task_types:
        lines.append(f"### {tt}")
        lines.append("")
        # Per-type McNemar (정확도)
        lines.append("**H1a (정확도) per-type McNemar**")
        lines.append("")
        lines.append("| comparison | n | A rate | B rate | b (A+B−) | c (A−B+) | p exact | sig (α={:.4f}) |".format(per_type_alpha))
        lines.append("|---|---|---|---|---|---|---|---|")
        for a_name, b_name in pairs:
            paired_a, _ = loaded[a_name]
            paired_b, _ = loaded[b_name]
            r = compare_binary(paired_a, paired_b, task_type_filter=tt)
            if r["n_common"] == 0:
                lines.append(f"| `{a_name}` vs `{b_name}` | 0 | — | — | — | — | — | — |")
                continue
            sig = "✅" if r["mcnemar_p_exact"] < per_type_alpha else "—"
            lines.append(
                f"| `{a_name}` vs `{b_name}` | {r['n_common']} | "
                f"{100*r['a_rate']:.1f}% | {100*r['b_rate']:.1f}% | "
                f"{r['discordant']['b']} | {r['discordant']['c']} | "
                f"{r['mcnemar_p_exact']:.4f} | {sig} |"
            )
        lines.append("")

        # Per-type Wilcoxon (효율)
        lines.append("**H1b (효율) per-type Wilcoxon**")
        lines.append("")
        lines.append("| metric | comparison | n | A mean | B mean | median diff | p | sig |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for metric, label in [
            ("step_count", "step"),
            ("wall_time_sec", "wall"),
            ("llm_calls", "llm_calls"),
        ]:
            for a_name, b_name in pairs:
                _, raw_a = loaded[a_name]
                _, raw_b = loaded[b_name]
                if not raw_a or not raw_b:
                    continue
                r = compare_continuous(raw_a, raw_b, metric, task_type_filter=tt)
                if r["n_paired"] == 0:
                    continue
                sig = "✅" if r["p_value"] < per_type_alpha else "—"
                lines.append(
                    f"| {label} | `{a_name}` vs `{b_name}` | {r['n_paired']} | "
                    f"{r['a_mean']:.2f} | {r['b_mean']:.2f} | "
                    f"{r['median_diff']:+.2f} | {r['p_value']:.4f} | {sig} |"
                )
        lines.append("")

    lines += [
        "## Decision narrative",
        "",
        "각 sub-test 결과를 two-tailed로 해석 (부호 가정 없음). ",
        "per-type heterogeneous pattern이 관측되면 task type별 효과 방향 차이를 별도 정리.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paired statistical tests for variant comparison")
    parser.add_argument(
        "--variant", action="append", required=True,
        help="name=path/to/analysis_dir (analyze_baseline.py 산출물 디렉토리). 2~N개 지정.",
    )
    parser.add_argument(
        "--bonferroni", type=int, default=None,
        help="Bonferroni correction factor (default: 자동 계산 = pairwise×sub-tests). "
             "자동 계산 결과를 override하려면 정수 지정.",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output/analysis/paired_stats.md"),
        help="Markdown 결과 저장 경로 (default: output/analysis/paired_stats.md).",
    )
    args = parser.parse_args(argv)

    variants: dict[str, tuple[Path, Path]] = {}
    for spec in args.variant:
        if "=" not in spec:
            print(f"[error] --variant must be NAME=PATH: {spec}", file=sys.stderr)
            return 2
        name, path_str = spec.split("=", 1)
        analysis_dir = Path(path_str)
        variants[name.strip()] = (
            analysis_dir / "paired.csv",
            analysis_dir / "raw.csv",
        )

    n = len(variants)
    if n < 2:
        print("[error] need ≥ 2 variants for paired comparison", file=sys.stderr)
        return 2

    # Auto Bonferroni: pairwise comparisons × dual H1 sub-tests (H1a + H1b 3개 metrics = 4)
    pairwise = n * (n - 1) // 2
    auto_bonf = pairwise * 4
    bonf = args.bonferroni or auto_bonf

    report = render_report(variants, bonf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"[ok] wrote {args.output}")
    print(f"     variants={n}, pairwise={pairwise}, bonferroni={bonf} (effective α={0.05/bonf:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
