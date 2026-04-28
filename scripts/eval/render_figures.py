"""Render paper §4 condition synthesis table + step bar chart from cells.json.

Inputs: <root>/cells.json (produced by aggregate_cells.py)
Outputs:
    <root>/condition_synthesis.md  — paper §4 source table
    <root>/figures/step_counts.png — grouped bar chart over 8 tasks × 3 variants

Outcome label per condition (automated triage; manual narrative still required):
    H*    confirmed if V1 step median < V0; partial if equal; refuted if >.
    L*    confirmed_limitation if V1 timeout count > V0 (or both fail);
           needs_review otherwise.
    Null* confirmed_parity if V0 step == V1 step; needs_review otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


VARIANTS = ("v0", "v1")
DEFAULT_TASK_CARDS_DIR = Path("docs/evaluation/task_cards")


def discover_condition_to_task(task_cards_dir: Path = DEFAULT_TASK_CARDS_DIR) -> dict[str, int]:
    mapping: dict[str, int] = {}
    if not task_cards_dir.is_dir():
        return mapping
    for p in sorted(task_cards_dir.glob("*.md")):
        stem = p.stem
        parts = stem.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            mapping[parts[0]] = int(parts[1])
    return mapping


CONDITION_TO_TASK = discover_condition_to_task()


def _step_median(cell: Optional[dict]) -> Optional[float]:
    if not cell:
        return None
    return cell.get("step", {}).get("median")


def _step_n_timeout(cell: Optional[dict]) -> int:
    if not cell:
        return 0
    return cell.get("step", {}).get("n_timeout") or 0


def _kg_fired(cell: Optional[dict]) -> str:
    if not cell:
        return "—"
    if cell.get("kg_inferrer_disabled"):
        return "(disabled)"
    target = cell.get("kg_inferred_target_first")
    return target or "—"


def _outcome_label(condition: str, v0: dict | None, v1: dict | None) -> str:
    if not v0 or not v1:
        return "no_data"
    s0 = _step_median(v0)
    s1 = _step_median(v1)
    t0 = _step_n_timeout(v0)
    t1 = _step_n_timeout(v1)
    if condition.startswith("H"):
        if s0 is None or s1 is None:
            return "needs_review"
        if s1 < s0:
            return "confirmed"
        if s1 == s0:
            return "partial"
        return "refuted"
    if condition.startswith("L"):
        # Limitation confirmed when V1 hits the predicted failure mode (timeout
        # or parity-with-baseline-failure) more than V0.
        if t1 > t0:
            return "confirmed_limitation"
        if t0 == t1 and s0 == s1:
            return "parity_review"
        return "needs_review"
    if condition.startswith("Null"):
        if s0 == s1:
            return "confirmed_parity"
        return "needs_review"
    return "unknown_condition"


def render_condition_synthesis_md(cells: dict) -> str:
    lines: list[str] = ["# Condition synthesis (paper §4)\n"]
    lines.append(
        "| Cond | Task | V0 step | V1 step | V1−tc step | "
        "V0 timeout | V1 timeout | KG fired (V1) | Auto outcome |"
    )
    lines.append(
        "|------|-----:|--------:|--------:|----------:|"
        "----------:|----------:|---------------|--------------|"
    )
    for cond, task_id in CONDITION_TO_TASK.items():
        v0 = cells.get(f"{task_id}__v0")
        v1 = cells.get(f"{task_id}__v1")
        v1tc = cells.get(f"{task_id}__v1_tc")
        outcome = _outcome_label(cond, v0, v1)
        s0 = _step_median(v0); s1 = _step_median(v1); s1tc = _step_median(v1tc)
        lines.append(
            f"| {cond} | {task_id} | "
            f"{s0 if s0 is not None else '—'} | "
            f"{s1 if s1 is not None else '—'} | "
            f"{s1tc if s1tc is not None else '—'} | "
            f"{_step_n_timeout(v0)} | {_step_n_timeout(v1)} | "
            f"{_kg_fired(v1)} | **{outcome}** |"
        )
    lines.append("")
    lines.append("Outcome labels are automated triage. Manual narrative for")
    lines.append("each condition (especially `needs_review` rows) is added")
    lines.append("during paper §4 writing.")
    return "\n".join(lines) + "\n"


def render_step_bar_chart(cells: dict, out_path: Path) -> None:
    """Save a grouped bar chart of step counts (8 tasks × 3 variants)."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("[warn] matplotlib not installed; skipping bar chart", file=sys.stderr)
        return
    conditions = list(CONDITION_TO_TASK.keys())
    task_ids = [CONDITION_TO_TASK[c] for c in conditions]
    labels = [f"{c}\n#{tid}" for c, tid in zip(conditions, task_ids)]
    n = len(conditions)
    width = 0.27
    xs = list(range(n))
    series: dict[str, list[float]] = {v: [] for v in VARIANTS}
    timeouts: dict[str, list[bool]] = {v: [] for v in VARIANTS}
    for tid in task_ids:
        for variant in VARIANTS:
            cell = cells.get(f"{tid}__{variant}")
            step = _step_median(cell)
            n_to = _step_n_timeout(cell)
            # Visualize timeout as a tall sentinel bar (max + 5) with hatch.
            if n_to and step is None:
                series[variant].append(0)
                timeouts[variant].append(True)
            else:
                series[variant].append(step if step is not None else 0)
                timeouts[variant].append(False)
    # Determine max for sentinel scaling
    flat = [s for v in series.values() for s in v if s]
    sentinel = (max(flat) if flat else 10) + 5
    for variant in VARIANTS:
        for i, t in enumerate(timeouts[variant]):
            if t:
                series[variant][i] = sentinel

    fig, ax = plt.subplots(figsize=(11, 5))
    colors = {"v0": "#777777", "v1": "#1f77b4", "v1_tc": "#9467bd"}
    for j, variant in enumerate(VARIANTS):
        offset = (j - 1) * width
        bars = ax.bar(
            [x + offset for x in xs], series[variant],
            width=width, label=variant, color=colors.get(variant),
            edgecolor="black", linewidth=0.5,
        )
        # Hatch timed-out bars
        for bar, is_to in zip(bars, timeouts[variant]):
            if is_to:
                bar.set_hatch("///")
                bar.set_alpha(0.6)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("step count (median over trials)")
    ax.set_title("Step counts by condition × variant (hatched = timeout)")
    ax.legend(loc="upper left")
    ax.axhline(sentinel - 0.1, linestyle=":", color="red", linewidth=0.5)
    ax.text(n - 0.5, sentinel + 0.3, "timeout sentinel",
            color="red", fontsize=8, ha="right")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[ok] {out_path}")


def render_step_box_plot(cells: dict, out_path: Path) -> None:
    """Per-trial box+scatter plot: V0 (gray) vs V1 (blue) side-by-side per task.

    With only 3 trials per cell a true box is degenerate; we overlay raw trial
    points so the reader sees the full distribution. Timeouts are shown as a
    red 'x' marker at a sentinel height.
    """
    try:
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except ImportError:
        print("[warn] matplotlib not installed; skipping box plot", file=sys.stderr)
        return
    conditions = list(CONDITION_TO_TASK.keys())
    task_ids = [CONDITION_TO_TASK[c] for c in conditions]
    labels = [f"{c}\n#{tid}" for c, tid in zip(conditions, task_ids)]
    width = 0.32

    # Determine y-axis range from non-timeout values across all cells.
    all_vals: list[float] = []
    for cond in conditions:
        tid = CONDITION_TO_TASK[cond]
        for variant in VARIANTS:
            cell = cells.get(f"{tid}__{variant}") or {}
            raw = (cell.get("step") or {}).get("raw") or []
            all_vals.extend([v for v in raw if v is not None])
    y_max = (max(all_vals) if all_vals else 30) + 5
    timeout_y = y_max - 2

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for i, tid in enumerate(task_ids):
        for j, variant in enumerate(VARIANTS):
            offset = (j - (len(VARIANTS) - 1) / 2) * width
            x = i + offset
            cell = cells.get(f"{tid}__{variant}") or {}
            raw = (cell.get("step") or {}).get("raw") or []
            valid = [v for v in raw if v is not None]
            if not valid:
                ax.scatter([x], [timeout_y], marker="x", s=80, color="red", zorder=4)
                ax.text(x, timeout_y + 0.6, "timeout", ha="center", fontsize=7, color="red")
                continue
            color = "#888" if variant == "v0" else "#1f77b4"
            ax.boxplot(
                valid, positions=[x], widths=width * 0.85,
                patch_artist=True, whis=(0, 100), showfliers=False,
                medianprops={"color": "black"},
                boxprops={"facecolor": color, "alpha": 0.55, "edgecolor": "black"},
                whiskerprops={"color": "black"},
                capprops={"color": "black"},
            )
            jitter = [x + ((k - (len(valid) - 1) / 2) * 0.05) for k in range(len(valid))]
            ax.scatter(jitter, valid, color="black", s=22, zorder=3, alpha=0.85)

    ax.set_xticks(range(len(conditions)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Step count (per trial)")
    ax.set_title("Per-task step distribution: Baseline vs KG (3 trials each, raw points overlaid)")
    legend_elements = [
        Patch(facecolor="#888", alpha=0.55, edgecolor="black", label="Baseline (no KG)"),
        Patch(facecolor="#1f77b4", alpha=0.55, edgecolor="black", label="KG (minimal mode)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left")
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_ylim(0, y_max + 1)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[ok] {out_path}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path,
                    help="Measurement root (must contain cells.json)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    cells_path = args.root / "cells.json"
    if not cells_path.exists():
        print(f"[err] {cells_path} not found — run aggregate_cells.py first", file=sys.stderr)
        return 1
    cells = json.loads(cells_path.read_text(encoding="utf-8"))
    out_dir = args.out or args.root
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "condition_synthesis.md").write_text(
        render_condition_synthesis_md(cells), encoding="utf-8"
    )
    print(f"[ok] {out_dir}/condition_synthesis.md")
    render_step_bar_chart(cells, out_dir / "figures" / "step_counts.png")
    render_step_box_plot(cells, out_dir / "figures" / "step_box.png")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
