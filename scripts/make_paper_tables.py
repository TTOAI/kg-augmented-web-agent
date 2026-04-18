"""Table 1 fill-in — paired.csv/raw.csv에서 직접 값 계산해 placeholder 치환.

paired_stats.md를 re-parse하지 않고 `paired_stats.py`의 primitive를 재사용해
값을 다시 계산. 이유: paired_stats.md의 narrative 포맷이 바뀔 수 있지만, 원천
CSV는 `analyze_baseline.py` 계약대로 안정적.

Placeholder 형식:
  {{b_<key>_<metric>}}  — baseline value
  {{k_<key>_<metric>}}  — kg_full value
  {{p_<key>}}           — McNemar p
  {{or_<key>}}          — odds ratio
  {{d_<key>}}           — delta SR (kg - baseline)
  {{tok_<key>}}, {{step_<key>}}, {{time_<key>}}  — compute
  {{cov_*}}, {{f_*}}, {{kappa}} — (optional, coverage/failure)

사용:
  .venv/bin/python3 scripts/make_paper_tables.py \\
      --baseline-analysis output/phase_c_180/baseline/analysis \\
      --kg-analysis output/phase_c_180/kg_full/analysis \\
      --template docs/paper/table1_template.md \\
      --output docs/paper/table1_filled.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from paired_stats import (  # noqa: E402
    compare_binary, compare_continuous, load_paired_csv, load_raw_csv, wilson_ci,
)


_TASK_TYPES = ("NAVIGATE", "RETRIEVE", "MUTATE")


def _sr_str(rate: float, ci_lo: float, ci_hi: float) -> str:
    return f"{100*rate:.1f}% ({100*ci_lo:.1f}, {100*ci_hi:.1f})"


def _compute_str(a: float, b: float, unit: str = "") -> str:
    return f"{a:.0f}{unit} → {b:.0f}{unit}"


def _odds_ratio(cont: dict) -> tuple[float, float, float]:
    """OR + 95% CI from 2x2. Haldane correction if any cell = 0."""
    import math
    a = cont["a_yes_b_yes"]
    b = cont["a_yes_b_no"]
    c = cont["a_no_b_yes"]
    d = cont["a_no_b_no"]
    if min(a, b, c, d) == 0:
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    odds = (a * d) / (b * c) if (b * c) > 0 else float("nan")
    se = math.sqrt(1/a + 1/b + 1/c + 1/d)
    lo = math.exp(math.log(odds) - 1.96 * se)
    hi = math.exp(math.log(odds) + 1.96 * se)
    return odds, lo, hi


def build_tokens(
    baseline_dir: Path,
    kg_dir: Path,
) -> dict[str, str]:
    """Key → replacement string."""
    paired_b = load_paired_csv(baseline_dir / "paired.csv")
    paired_k = load_paired_csv(kg_dir / "paired.csv")
    raw_b = load_raw_csv(baseline_dir / "raw.csv")
    raw_k = load_raw_csv(kg_dir / "raw.csv")

    tokens: dict[str, str] = {}

    # Overall + per-type
    for slot, tt in [("overall", None), ("nav", "NAVIGATE"),
                     ("ret", "RETRIEVE"), ("mut", "MUTATE")]:
        binary = compare_binary(paired_b, paired_k, task_type_filter=tt)
        if binary["n_common"] == 0:
            _fill_empty(tokens, slot)
            continue
        a_rate, b_rate = binary["a_rate"], binary["b_rate"]
        a_k = binary["a_success"]
        b_k = binary["b_success"]
        n = binary["n_common"]
        a_lo, a_hi = wilson_ci(a_k, n)
        b_lo, b_hi = wilson_ci(b_k, n)
        p = binary["mcnemar_p_exact"]
        or_val, or_lo, or_hi = _odds_ratio(binary["contingency"])

        tokens[f"b_{slot}_sr"] = _sr_str(a_rate, a_lo, a_hi)
        tokens[f"k_{slot}_sr"] = _sr_str(b_rate, b_lo, b_hi)
        tokens[f"b_{_slot_aliased(slot)}"] = _sr_str(a_rate, a_lo, a_hi)
        tokens[f"k_{_slot_aliased(slot)}"] = _sr_str(b_rate, b_lo, b_hi)
        tokens[f"d_{slot}"] = f"{100*(b_rate - a_rate):+.1f} pp"
        tokens[f"p_{slot}"] = f"{p:.4f}" + _sig_marker(p, slot)
        tokens[f"or_{slot}"] = f"{or_val:.2f} [{or_lo:.2f}, {or_hi:.2f}]"

        # Compute metrics
        for metric, key in [("step_count", "step"),
                            ("wall_time_sec", "time"),
                            ("llm_calls", "tok")]:
            r = compare_continuous(raw_b, raw_k, metric, task_type_filter=tt)
            if r["n_paired"] == 0:
                tokens[f"{key}_{slot}"] = "n/a"
            else:
                tokens[f"{key}_{slot}"] = _compute_str(r["a_mean"], r["b_mean"])

    return tokens


def _slot_aliased(slot: str) -> str:
    """{{b_overall}}같은 shorthand도 허용."""
    return slot


def _fill_empty(tokens: dict[str, str], slot: str) -> None:
    for key in (f"b_{slot}_sr", f"k_{slot}_sr", f"d_{slot}", f"p_{slot}",
                f"or_{slot}", f"tok_{slot}", f"step_{slot}", f"time_{slot}"):
        tokens[key] = "—"


def _sig_marker(p: float, slot: str) -> str:
    """Significance markers. overall α=0.05, per-type α=0.0167 (Bonferroni 3)."""
    alpha = 0.05 if slot == "overall" else 0.05 / 3
    if p < 0.01:
        return " ***"
    if p < alpha:
        return " **"
    return " ns"


def apply_tokens(template: str, tokens: dict[str, str]) -> str:
    out = template
    for key, val in tokens.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-analysis", type=Path, required=False,
                        help="e.g., output/phase_c_180/baseline/analysis")
    parser.add_argument("--kg-analysis", type=Path, required=False,
                        help="e.g., output/phase_c_180/kg_full/analysis")
    parser.add_argument("--paired-stats", type=Path, required=False,
                        help="(unused — kept for backward compat with run_analysis.sh)")
    parser.add_argument("--baseline-summary", type=Path, required=False)
    parser.add_argument("--kg-summary", type=Path, required=False)
    parser.add_argument("--coverage", type=Path, required=False)
    parser.add_argument("--template", type=Path,
                        default=Path("docs/paper/table1_template.md"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/paper/table1_filled.md"))
    parser.add_argument("--json", type=Path, required=False,
                        help="Optional — also dump token dict as JSON for inspection")
    args = parser.parse_args(argv)

    # run_analysis.sh는 --paired-stats/summary 경로를 넘기므로 여기서 analysis 디렉토리 유추
    baseline_dir = args.baseline_analysis
    kg_dir = args.kg_analysis
    if baseline_dir is None and args.baseline_summary is not None:
        baseline_dir = args.baseline_summary.parent
    if kg_dir is None and args.kg_summary is not None:
        kg_dir = args.kg_summary.parent
    if baseline_dir is None or kg_dir is None:
        print("[error] need --baseline-analysis + --kg-analysis (or --*-summary)", file=sys.stderr)
        return 2

    if not (baseline_dir / "paired.csv").exists():
        print(f"[error] {baseline_dir}/paired.csv not found", file=sys.stderr)
        return 2
    if not (kg_dir / "paired.csv").exists():
        print(f"[error] {kg_dir}/paired.csv not found", file=sys.stderr)
        return 2

    tokens = build_tokens(baseline_dir, kg_dir)
    template_text = args.template.read_text(encoding="utf-8")
    filled = apply_tokens(template_text, tokens)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(filled, encoding="utf-8")
    print(f"[ok] wrote {args.output} ({len(tokens)} tokens substituted)")

    if args.json is not None:
        args.json.write_text(json.dumps(tokens, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[ok] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
