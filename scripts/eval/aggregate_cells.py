"""Aggregate per-trial signals into per-cell outcomes (task × variant).

Inputs: a measurement root directory with structure
    <root>/v0/<task_id>/trial_<n>/signals.json
    <root>/v1/<task_id>/trial_<n>/signals.json
    <root>/v1_tc/<task_id>/trial_<n>/signals.json

For each (task, variant) cell, aggregate per metrics.md:
  - agent_evaluator + network_evaluator outcomes (majority of 3 trials)
  - step_count: median + [min, max]
  - mechanism_fired: any-trial fired
  - token + wall-clock: median

Output: <root>/cells.json + <root>/cells_summary.md
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Optional


VARIANTS = ("v0", "v1")
DEFAULT_TASK_CARDS_DIR = Path("docs/evaluation/task_cards")


def discover_condition_to_task(task_cards_dir: Path = DEFAULT_TASK_CARDS_DIR) -> dict[str, int]:
    """Discover condition → task_id mapping from task_cards/<COND>_<task_id>.md filenames.

    Only the *root* of task_cards/ counts as the active round set; cards in
    `task_cards/candidates/` are future-round candidates and are not aggregated.
    """
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


def _majority(values: list[Optional[str]]) -> Optional[str]:
    """Majority of 3 trials: PASS / FAIL / mixed / unscored."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return None
    counts: dict[str, int] = {}
    for v in non_null:
        counts[v] = counts.get(v, 0) + 1
    sorted_counts = sorted(counts.items(), key=lambda kv: -kv[1])
    top, top_count = sorted_counts[0]
    if top_count >= max(2, (len(non_null) + 1) // 2):
        return top
    return "mixed"


def _median_or_none(values: list[Optional[float]]) -> Optional[float]:
    nn = [v for v in values if v is not None]
    if not nn:
        return None
    return statistics.median(nn)


def _step_summary(steps: list[Optional[int]], timed_outs: list[bool]) -> dict:
    """Step count: median + range. Timeouts are marked separately."""
    finite = [s for s in steps if s is not None]
    n_timeout = sum(1 for t in timed_outs if t)
    out: dict = {
        "median": statistics.median(finite) if finite else None,
        "min": min(finite) if finite else None,
        "max": max(finite) if finite else None,
        "n_finite": len(finite),
        "n_timeout": n_timeout,
        "raw": steps,
    }
    return out


def aggregate_cell(trial_signals: list[dict]) -> dict:
    if not trial_signals:
        return {}
    agent_outs = [t.get("agent_evaluator") for t in trial_signals]
    network_outs = [t.get("network_evaluator") for t in trial_signals]
    statuses = [t.get("agent_status") for t in trial_signals]
    steps = [t.get("step_count") for t in trial_signals]
    timed = [bool(t.get("timed_out")) for t in trial_signals]
    wall = [t.get("wall_clock_s") for t in trial_signals]
    inferred_targets = [t.get("kg_inferred_target") for t in trial_signals]
    inferrer_disabled = any(t.get("kg_inferrer_disabled") for t in trial_signals)
    kg_loaded = any(t.get("kg_session_loaded") for t in trial_signals)
    inputs = [t.get("total_input_tokens", 0) for t in trial_signals]
    outputs = [t.get("total_output_tokens", 0) for t in trial_signals]
    cache_creates = [t.get("total_cache_create_tokens", 0) for t in trial_signals]
    cache_reads = [t.get("total_cache_read_tokens", 0) for t in trial_signals]
    return {
        "n_trials": len(trial_signals),
        "agent_evaluator": _majority(agent_outs),
        "network_evaluator": _majority(network_outs),
        "agent_status_majority": _majority(statuses),
        "step": _step_summary(steps, timed),
        "wall_clock_s_median": _median_or_none(wall),
        "kg_session_loaded": kg_loaded,
        "kg_inferrer_disabled": inferrer_disabled,
        "kg_inferred_target_first": next(
            (t for t in inferred_targets if t), None
        ),
        "kg_inferred_targets_all": inferred_targets,
        "tokens_median": {
            "input": statistics.median(inputs) if inputs else 0,
            "output": statistics.median(outputs) if outputs else 0,
            "cache_create": statistics.median(cache_creates) if cache_creates else 0,
            "cache_read": statistics.median(cache_reads) if cache_reads else 0,
        },
    }


def load_signals(trial_dir: Path) -> Optional[dict]:
    p = trial_dir / "signals.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def gather_cells(root: Path) -> dict[tuple[int, str], dict]:
    """Walk root/<variant>/<task_id>/trial_*/signals.json and aggregate cells."""
    cells: dict[tuple[int, str], list[dict]] = {}
    for variant in VARIANTS:
        vdir = root / variant
        if not vdir.is_dir():
            continue
        for task_dir in sorted(vdir.iterdir()):
            if not task_dir.is_dir() or not task_dir.name.isdigit():
                continue
            task_id = int(task_dir.name)
            trial_dirs = [d for d in sorted(task_dir.iterdir())
                          if d.is_dir() and d.name.startswith("trial_")]
            # Single-shot directories (no trial_N subdir) are also valid input
            # — treat the task_dir itself as the trial.
            if not trial_dirs and (task_dir / "signals.json").exists():
                trial_dirs = [task_dir]
            for td in trial_dirs:
                sig = load_signals(td)
                if sig is None:
                    continue
                cells.setdefault((task_id, variant), []).append(sig)
    aggregated = {
        f"{task_id}__{variant}": aggregate_cell(trials)
        for (task_id, variant), trials in cells.items()
    }
    return aggregated


def render_summary_md(cells: dict[str, dict]) -> str:
    """Render a Markdown table grouped by condition."""
    lines: list[str] = ["# Cell-level outcomes (post-measurement)\n"]
    lines.append(
        "| Cond | Task | Variant | n | step (med [min, max]) | n_timeout | "
        "agent eval | net eval | KG inferred | wall(s) |"
    )
    lines.append(
        "|------|-----:|---------|--:|----------------------|----------:|"
        "------------|----------|-------------|--------:|"
    )
    for cond, task_id in CONDITION_TO_TASK.items():
        for variant in VARIANTS:
            key = f"{task_id}__{variant}"
            cell = cells.get(key)
            if cell is None:
                lines.append(f"| {cond} | {task_id} | {variant} | 0 | — | — | — | — | — | — |")
                continue
            step = cell["step"]
            step_str = (
                f"{step['median']} [{step['min']}, {step['max']}]"
                if step["median"] is not None else "—"
            )
            wall = cell["wall_clock_s_median"]
            wall_str = f"{wall:.1f}" if wall is not None else "—"
            kg_target = cell.get("kg_inferred_target_first")
            if cell.get("kg_inferrer_disabled"):
                kg_target_str = "(disabled)"
            elif kg_target:
                kg_target_str = kg_target
            else:
                kg_target_str = "—"
            lines.append(
                f"| {cond} | {task_id} | {variant} | {cell['n_trials']} | "
                f"{step_str} | {step['n_timeout']} | "
                f"{cell['agent_evaluator'] or '—'} | "
                f"{cell['network_evaluator'] or '—'} | "
                f"{kg_target_str} | {wall_str} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path,
                    help="Measurement root (e.g., output/characterization or output/smoke_claude)")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output directory for cells.json + cells_summary.md (default: <root>)")
    args = ap.parse_args(argv)
    out_dir = args.out or args.root
    cells = gather_cells(args.root)
    if not cells:
        print(f"[warn] no cells gathered from {args.root}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cells.json").write_text(
        json.dumps(cells, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "cells_summary.md").write_text(
        render_summary_md(cells), encoding="utf-8"
    )
    print(f"[ok] {out_dir}/cells.json")
    print(f"[ok] {out_dir}/cells_summary.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
