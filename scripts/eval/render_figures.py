"""Render result table + step box plot from cells.json.

Inputs: <root>/cells.json (produced by aggregate_cells.py)
Outputs:
    <root>/step_table.md            — per-task step statistics table
    <root>/figures/step_box.png     — per-trial step box plot
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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


def render_step_table(cells: dict, out_path: Path) -> None:
    """Render per-task step statistics table.

    For each (condition, task_id, variant), reports mean / std (population,
    ddof=0) / median / range over cells[*]["step"]["raw"]. None entries
    (non-success/non-timeout trials) are excluded; n_finite vs n_trials is
    reported so reviewers can audit how many trials were valid.
    """
    import statistics

    variant_label = {"v0": "baseline", "v1": "KG"}
    lines: list[str] = ["# Per-task step statistics\n"]
    lines.append("| 조건 | task | 비교군 | 평균 | 표준편차 | 중앙값 | 범위 | n |")
    lines.append("|------|-----:|--------|-----:|---------:|-------:|------|--:|")
    for cond, task_id in CONDITION_TO_TASK.items():
        for variant in VARIANTS:
            cell = cells.get(f"{task_id}__{variant}") or {}
            step = cell.get("step") or {}
            raw = step.get("raw") or []
            valid = [v for v in raw if v is not None]
            label = variant_label.get(variant, variant)
            if not valid:
                n_timeout = step.get("n_timeout") or 0
                status = cell.get("agent_status_majority") or "no_data"
                if n_timeout >= len(raw) and len(raw) > 0:
                    suffix = "timeout"
                elif status == "UNKNOWN_ERROR":
                    suffix = "error"
                elif status == "mixed":
                    suffix = "mixed"
                else:
                    suffix = "no data"
                lines.append(
                    f"| {cond} | {task_id} | {label} | "
                    f"— ({suffix}) | — | — | — | 0/{len(raw)} |"
                )
                continue
            mean = sum(valid) / len(valid)
            std = (sum((v - mean) ** 2 for v in valid) / len(valid)) ** 0.5
            median = statistics.median(valid)
            lo, hi = min(valid), max(valid)
            lines.append(
                f"| {cond} | {task_id} | {label} | "
                f"{mean:.2f} | {std:.2f} | {median:g} | {lo}–{hi} | "
                f"{len(valid)}/{len(raw)} |"
            )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
    render_step_box_plot(cells, out_dir / "figures" / "step_box.png")
    render_step_table(cells, out_dir / "step_table.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
