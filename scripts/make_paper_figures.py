"""Generate result bar charts for the paper.

논문 Figure 3 등 결과 시각화. 측정 종료 후 run_analysis.sh의 연장으로 호출 가능하나
필수는 아님 (Table 1만으로도 논문 충분).

산출:
  docs/paper/figures/results_per_type.png — Baseline vs Full KG per-type SR + Wilson CI
  docs/paper/figures/results_compute.png  — token/step/time per-type bar

사용:
  .venv/bin/python3 scripts/make_paper_figures.py \\
      --baseline-analysis output/phase_c_180/baseline/analysis \\
      --kg-analysis output/phase_c_180/kg_full/analysis \\
      --output-dir docs/paper/figures

의존성: matplotlib (선택). 미설치 시 경고 후 skip.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from paired_stats import (  # noqa: E402
    compare_binary, compare_continuous, load_paired_csv, load_raw_csv, wilson_ci,
)


def _check_matplotlib():
    try:
        import matplotlib  # noqa: F401
        import matplotlib.pyplot as plt  # noqa: F401
        return True
    except ImportError:
        print("[warn] matplotlib 미설치 — `pip install matplotlib` 후 재시도", file=sys.stderr)
        return False


def plot_per_type_sr(
    baseline_dir: Path,
    kg_dir: Path,
    output: Path,
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    paired_b = load_paired_csv(baseline_dir / "paired.csv")
    paired_k = load_paired_csv(kg_dir / "paired.csv")

    types = ("NAVIGATE", "RETRIEVE", "MUTATE", None)  # None = Overall
    labels = ("NAVIGATE", "RETRIEVE", "MUTATE", "Overall")

    base_rate, base_err_lo, base_err_hi = [], [], []
    kg_rate, kg_err_lo, kg_err_hi = [], [], []
    ns = []
    for tt in types:
        b = compare_binary(paired_b, paired_k, task_type_filter=tt)
        n = b["n_common"]
        ns.append(n)
        if n == 0:
            base_rate.append(0); kg_rate.append(0)
            base_err_lo.append(0); base_err_hi.append(0)
            kg_err_lo.append(0); kg_err_hi.append(0)
            continue
        b_lo, b_hi = wilson_ci(b["a_success"], n)
        k_lo, k_hi = wilson_ci(b["b_success"], n)
        base_rate.append(100 * b["a_rate"])
        kg_rate.append(100 * b["b_rate"])
        base_err_lo.append(100 * b["a_rate"] - 100 * b_lo)
        base_err_hi.append(100 * b_hi - 100 * b["a_rate"])
        kg_err_lo.append(100 * b["b_rate"] - 100 * k_lo)
        kg_err_hi.append(100 * k_hi - 100 * b["b_rate"])

    x = np.arange(len(labels))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - w/2, base_rate, w, yerr=[base_err_lo, base_err_hi],
           label="Baseline", color="#6b93b8", capsize=4)
    ax.bar(x + w/2, kg_rate, w, yerr=[kg_err_lo, kg_err_hi],
           label="Full KG", color="#d08030", capsize=4)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{lab}\n(N={n})" for lab, n in zip(labels, ns)])
    ax.set_ylabel("Task success rate (%)  [Wilson 95% CI]")
    ax.set_title("Per-type success rate — Baseline vs Full KG")
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(f"[ok] wrote {output}")


def plot_compute(
    baseline_dir: Path,
    kg_dir: Path,
    output: Path,
) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    raw_b = load_raw_csv(baseline_dir / "raw.csv")
    raw_k = load_raw_csv(kg_dir / "raw.csv")

    metrics = [("step_count", "Steps"),
               ("wall_time_sec", "Wall-time (s)"),
               ("llm_calls", "LLM calls")]
    types = ("NAVIGATE", "RETRIEVE", "MUTATE")

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, (metric, label) in zip(axes, metrics):
        base_vals, kg_vals = [], []
        for tt in types:
            r = compare_continuous(raw_b, raw_k, metric, task_type_filter=tt)
            base_vals.append(r["a_mean"] if r["n_paired"] > 0 else 0)
            kg_vals.append(r["b_mean"] if r["n_paired"] > 0 else 0)
        x = np.arange(len(types))
        w = 0.35
        ax.bar(x - w/2, base_vals, w, label="Baseline", color="#6b93b8")
        ax.bar(x + w/2, kg_vals, w, label="Full KG", color="#d08030")
        ax.set_xticks(x)
        ax.set_xticklabels(types)
        ax.set_title(label)
        ax.set_ylabel(f"Mean {label.lower()}")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(f"[ok] wrote {output}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-analysis", type=Path, required=True)
    parser.add_argument("--kg-analysis", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/paper/figures"))
    args = parser.parse_args(argv)

    if not _check_matplotlib():
        return 1

    plot_per_type_sr(
        args.baseline_analysis, args.kg_analysis,
        args.output_dir / "results_per_type.png",
    )
    plot_compute(
        args.baseline_analysis, args.kg_analysis,
        args.output_dir / "results_compute.png",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
