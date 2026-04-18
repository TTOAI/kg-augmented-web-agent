"""Nano vs mini baseline 비교 분석.

Phase 2-C smoke에서 gpt-5.4-nano로 실행된 baseline 데이터와, Phase C (2026-04-17)
본 측정에서 gpt-5.4-mini로 실행된 baseline 데이터 (kg_context=None 경로)를 동일 task
subset으로 비교하여 모델 크기에 따른 성능 차이를 산출한다.

주의: Phase C kg_full 데이터는 SITEKG_ENABLED=1 누락으로 실질 baseline 경로였으므로
mini-baseline 소스로 활용 가능. 하지만 설명 복잡도를 피하기 위해 공식 baseline
(`output/phase_c_180/baseline/N1~N3`)만 사용. 공통 task_id에서 majority vote binary로
paired 비교.

사용:
  python scripts/compare_models.py \\
      --nano-baseline-dir output/smoke_nano_expanded/baseline \\
      --mini-baseline-dir output/phase_c_180/baseline \\
      --output docs/paper/appendix_nano_vs_mini.md
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path


def _load_raw_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _per_task_majority(rows: list[dict], task_id: int) -> int | None:
    """task_id 기준 eval_status='success' majority (runs 수 < 필요 시 None)."""
    task_rows = [r for r in rows if int(r["task_id"]) == task_id]
    if not task_rows:
        return None
    succ = sum(1 for r in task_rows if r.get("eval_status", "").strip().lower() == "success")
    total = len(task_rows)
    return 1 if succ > total / 2 else 0


def _per_task_mean(rows: list[dict], task_id: int, field: str) -> float | None:
    """task_id의 해당 field 평균."""
    vals = []
    for r in rows if rows else []:
        if int(r["task_id"]) != task_id:
            continue
        v = r.get(field, "")
        if v == "" or v is None:
            continue
        try:
            vals.append(float(v))
        except ValueError:
            continue
    return sum(vals) / len(vals) if vals else None


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (center - margin) / denom), min(1.0, (center + margin) / denom))


def render_comparison(nano_dir: Path, mini_dir: Path, output: Path) -> None:
    nano_rows = _load_raw_csv(nano_dir / "analysis" / "raw.csv")
    mini_rows = _load_raw_csv(mini_dir / "analysis" / "raw.csv")
    if not nano_rows:
        print(f"[warn] nano raw.csv 없음: {nano_dir}/analysis/raw.csv — analyze_baseline.py 먼저 실행 필요", file=sys.stderr)
    if not mini_rows:
        print(f"[warn] mini raw.csv 없음: {mini_dir}/analysis/raw.csv", file=sys.stderr)

    # Common task_ids
    nano_tasks = {int(r["task_id"]) for r in nano_rows}
    mini_tasks = {int(r["task_id"]) for r in mini_rows}
    common = sorted(nano_tasks & mini_tasks)
    if not common:
        print("[error] nano와 mini에 공통 task 없음 — 비교 불가", file=sys.stderr)
        return

    per_task: list[dict] = []
    for tid in common:
        n_bin = _per_task_majority(nano_rows, tid)
        m_bin = _per_task_majority(mini_rows, tid)
        n_steps = _per_task_mean(nano_rows, tid, "step_count")
        m_steps = _per_task_mean(mini_rows, tid, "step_count")
        n_time = _per_task_mean(nano_rows, tid, "wall_time_sec")
        m_time = _per_task_mean(mini_rows, tid, "wall_time_sec")
        n_llm = _per_task_mean(nano_rows, tid, "llm_calls")
        m_llm = _per_task_mean(mini_rows, tid, "llm_calls")
        task_type = ""
        for r in nano_rows + mini_rows:
            if int(r["task_id"]) == tid:
                task_type = r.get("task_type", "")
                break
        per_task.append({
            "task_id": tid, "task_type": task_type,
            "nano_bin": n_bin, "mini_bin": m_bin,
            "nano_steps": n_steps, "mini_steps": m_steps,
            "nano_time": n_time, "mini_time": m_time,
            "nano_llm": n_llm, "mini_llm": m_llm,
        })

    # Aggregate
    n_succ = sum(1 for r in per_task if r["nano_bin"] == 1)
    m_succ = sum(1 for r in per_task if r["mini_bin"] == 1)
    n_tot = sum(1 for r in per_task if r["nano_bin"] is not None)
    m_tot = sum(1 for r in per_task if r["mini_bin"] is not None)
    n_lo, n_hi = _wilson_ci(n_succ, n_tot)
    m_lo, m_hi = _wilson_ci(m_succ, m_tot)

    # Per-type
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in per_task:
        by_type[r["task_type"]].append(r)

    lines = [
        "# Appendix — Model Size Comparison (gpt-5.4-nano vs gpt-5.4-mini baseline)",
        "",
        "## Method",
        "",
        "Phase 2-C smoke에서 gpt-5.4-nano로 수행한 baseline과 Phase C (2026-04-17) 본 측정의",
        "gpt-5.4-mini baseline (동일 task_types.txt sample)을 공통 task_id subset으로 비교.",
        "각 task는 majority vote binary success로 이진화 (per-task), step/wall-time/llm_calls는",
        "task 내 run 평균. Model size robustness future work (`docs/07 §11`)의 preliminary signal.",
        "",
        f"- Common tasks: {len(common)}",
        f"- Nano data: `{nano_dir}`",
        f"- Mini data: `{mini_dir}`",
        "",
        "## Overall Success Rate",
        "",
        "| Model | Success | Wilson 95% CI |",
        "|---|---|---|",
        f"| **gpt-5.4-nano** | {n_succ}/{n_tot} ({100*n_succ/max(1, n_tot):.1f}%) | "
        f"[{100*n_lo:.1f}%, {100*n_hi:.1f}%] |",
        f"| **gpt-5.4-mini** | {m_succ}/{m_tot} ({100*m_succ/max(1, m_tot):.1f}%) | "
        f"[{100*m_lo:.1f}%, {100*m_hi:.1f}%] |",
        "",
        "## Per-type Success Rate",
        "",
        "| task_type | Nano | Mini |",
        "|---|---|---|",
    ]
    for t in ("NAVIGATE", "RETRIEVE", "MUTATE"):
        rs = by_type.get(t, [])
        ns = sum(1 for r in rs if r["nano_bin"] == 1)
        ms = sum(1 for r in rs if r["mini_bin"] == 1)
        n_n = sum(1 for r in rs if r["nano_bin"] is not None)
        n_m = sum(1 for r in rs if r["mini_bin"] is not None)
        lines.append(
            f"| {t} | {ns}/{n_n} ({100*ns/max(1, n_n):.1f}%) | "
            f"{ms}/{n_m} ({100*ms/max(1, n_m):.1f}%) |"
        )
    lines += ["", "## Per-task Detail", "",
              "| task_id | type | Nano bin | Mini bin | Nano steps | Mini steps | Nano time | Mini time | Nano llm | Mini llm |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    def _fmt(v: float | None, spec: str = ".1f") -> str:
        if v is None:
            return "—"
        return format(v, spec)
    for r in per_task:
        lines.append(
            f"| {r['task_id']} | {r['task_type']} | "
            f"{r['nano_bin'] if r['nano_bin'] is not None else '—'} | "
            f"{r['mini_bin'] if r['mini_bin'] is not None else '—'} | "
            f"{_fmt(r['nano_steps'])} | {_fmt(r['mini_steps'])} | "
            f"{_fmt(r['nano_time'])} | {_fmt(r['mini_time'])} | "
            f"{_fmt(r['nano_llm'], '.0f')} | {_fmt(r['mini_llm'], '.0f')} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("Nano와 mini의 비교는 **model size robustness의 preliminary evidence**로 본 3-page")
    lines.append("논문의 Limitation/Future Work 섹션에 인용된다. 본 실험은 mini 단일 모델로 진행됐고")
    lines.append("(`docs/07 §7`), nano 비교는 동일 pipeline 하에서의 smoke 수준 관찰로 limited.")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"[ok] wrote {output}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--nano-baseline-dir", type=Path,
                        default=Path("output/smoke_nano_expanded/baseline"))
    parser.add_argument("--mini-baseline-dir", type=Path,
                        default=Path("output/phase_c_180/baseline"))
    parser.add_argument("--output", type=Path,
                        default=Path("docs/paper/appendix_nano_vs_mini.md"))
    args = parser.parse_args(argv)
    render_comparison(args.nano_baseline_dir, args.mini_baseline_dir, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
