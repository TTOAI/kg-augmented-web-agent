"""Failure mode taxonomy 라벨링 보조 + Cohen's κ 계산 — `06 §3-2`.

기능:
- 실패 task 수집 → labeling template (CSV) 생성 (저자 1·2 또는 self-rerate용)
- 채워진 라벨 CSV 두 개 비교 → Cohen's κ + per-category breakdown

Taxonomy: P (Plan) / R (Route) / G (Grounding) / A (Verifier artifact) / O (Other)
- 각 task에 primary (●) + secondary (△, optional) 라벨

사용:
  # Step 1: template 생성 (실패 task 수집)
  python scripts/failure_mode.py template \\
      --variant baseline=output/baseline_n3 \\
      --variant kg_full=output/kg_full_n3 \\
      --output output/analysis/failure_template.csv

  # Step 2 (수동): 저자가 template을 두 번 라벨링 (rate1.csv, rate2.csv)
  # primary, secondary 컬럼에 P/R/G/A/O 입력

  # Step 3: Cohen's κ 계산
  python scripts/failure_mode.py kappa \\
      --rate1 output/analysis/failure_rate1.csv \\
      --rate2 output/analysis/failure_rate2.csv \\
      --output output/analysis/failure_kappa.md

reviewer-proof: κ < 0.6이면 taxonomy 재정의. ≥ 0.6이면 substantial agreement.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


_TAXONOMY = ("P", "R", "G", "A", "O")


def _is_failed_run(eval_status: str) -> bool:
    return str(eval_status).strip().lower() != "success"


def collect_failures(variant_dir: Path) -> list[dict]:
    """변형의 실패 task를 (task_id, run, agent_status, eval_status, log_excerpt)로 수집."""
    import json
    runs = ("N1", "N2", "N3")
    out: list[dict] = []
    for run in runs:
        run_dir = variant_dir / run
        if not run_dir.exists():
            continue
        for task_dir in sorted(run_dir.iterdir()):
            if not task_dir.is_dir() or not task_dir.name.isdigit():
                continue
            task_id = int(task_dir.name)
            ev_path = task_dir / "eval_result.json"
            ev = {}
            if ev_path.exists():
                try:
                    ev = json.loads(ev_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            eval_status = ev.get("status", "")
            if not _is_failed_run(eval_status):
                continue

            agent_resp = {}
            ar_path = task_dir / "agent_response.json"
            if ar_path.exists():
                try:
                    agent_resp = json.loads(ar_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            log_excerpt = ""
            log_path = task_dir / "webarena_verified.log"
            if log_path.exists():
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                # 마지막 5줄 (failure 직전 컨텍스트)
                log_excerpt = " | ".join(lines[-5:])[:300]

            out.append({
                "task_id": task_id,
                "run": run,
                "agent_status": agent_resp.get("status", ""),
                "eval_status": eval_status,
                "log_excerpt": log_excerpt,
            })
    return out


def write_template(variants: dict[str, Path], output_path: Path) -> int:
    """Variant별 실패 task를 모아 라벨링 template 작성."""
    rows: list[dict] = []
    for name, vdir in variants.items():
        for fail in collect_failures(vdir):
            rows.append({
                "variant": name,
                **fail,
                "primary": "",   # 라벨러가 채움 (P/R/G/A/O)
                "secondary": "", # optional
                "note": "",
            })
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["variant", "task_id", "run", "agent_status", "eval_status",
              "log_excerpt", "primary", "secondary", "note"]
    with output_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def cohens_kappa(rater1: list[str], rater2: list[str]) -> float:
    """Cohen's κ for nominal labels.

    κ = (Po - Pe) / (1 - Pe)
    Po: observed agreement
    Pe: expected agreement by chance
    """
    assert len(rater1) == len(rater2), "raters must have same length"
    n = len(rater1)
    if n == 0:
        return float("nan")
    categories = sorted(set(rater1) | set(rater2))
    if len(categories) <= 1:
        return 1.0  # all same label

    po = sum(1 for a, b in zip(rater1, rater2) if a == b) / n
    cnt1 = Counter(rater1)
    cnt2 = Counter(rater2)
    pe = sum((cnt1[c] / n) * (cnt2[c] / n) for c in categories)
    if pe == 1.0:
        return 1.0  # 모든 라벨이 같은 카테고리 → 우연 일치 100%
    return (po - pe) / (1 - pe)


def kappa_interpretation(k: float) -> str:
    """Landis & Koch (1977) interpretation."""
    if k != k:  # NaN
        return "n/a"
    if k < 0:
        return "poor (no agreement)"
    if k < 0.20:
        return "slight"
    if k < 0.40:
        return "fair"
    if k < 0.60:
        return "moderate"
    if k < 0.80:
        return "substantial"
    return "almost perfect"


def load_labeled(path: Path) -> dict[tuple[str, int, str], dict]:
    """라벨된 CSV → {(variant, task_id, run): {primary, secondary}}."""
    out: dict[tuple[str, int, str], dict] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["variant"], int(row["task_id"]), row["run"])
            out[key] = {
                "primary": (row.get("primary") or "").strip().upper(),
                "secondary": (row.get("secondary") or "").strip().upper(),
            }
    return out


def render_kappa_report(rate1: dict, rate2: dict) -> str:
    common = sorted(set(rate1.keys()) & set(rate2.keys()))
    n = len(common)
    if n == 0:
        return "# Failure Mode Cohen's κ\n\nNo common labeled rows.\n"

    pri1 = [rate1[k]["primary"] for k in common]
    pri2 = [rate2[k]["primary"] for k in common]
    sec1 = [rate1[k]["secondary"] for k in common]
    sec2 = [rate2[k]["secondary"] for k in common]

    k_pri = cohens_kappa(pri1, pri2)
    k_sec = cohens_kappa(sec1, sec2)

    # Per-category disagreement (primary)
    confusion: dict[tuple[str, str], int] = defaultdict(int)
    for a, b in zip(pri1, pri2):
        confusion[(a, b)] += 1

    cats = sorted(set(pri1) | set(pri2))
    lines = [
        "# Failure Mode Inter-rater Agreement",
        "",
        "Generated by `scripts/failure_mode.py kappa`. Reviewer-proof context: `06 §3-2`.",
        "",
        f"- Common labeled rows: {n}",
        f"- **Cohen's κ (primary)**: {k_pri:.3f} ({kappa_interpretation(k_pri)})",
        f"- **Cohen's κ (secondary)**: {k_sec:.3f} ({kappa_interpretation(k_sec)})",
        "",
        "### Threshold (06 §3-2)",
        "- κ ≥ 0.6 (substantial): protocol confirmed",
        "- κ < 0.6: taxonomy 재정의 고려",
        "",
        "## Confusion matrix (primary)",
        "",
        "| rate1 \\ rate2 | " + " | ".join(cats) + " |",
        "|---|" + "|".join(["---"] * len(cats)) + "|",
    ]
    for a in cats:
        row = [f"**{a}**"] + [str(confusion.get((a, b), 0)) for b in cats]
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## Disagreement examples", ""]
    disagree = [(k, rate1[k], rate2[k]) for k in common if rate1[k]["primary"] != rate2[k]["primary"]]
    lines.append(f"- Total disagreements (primary): {len(disagree)}")
    for k, r1, r2 in disagree[:15]:
        v, t, run = k
        lines.append(f"  - `{v}`/{t}/{run}: rate1=`{r1['primary']}`, rate2=`{r2['primary']}`")
    if len(disagree) > 15:
        lines.append(f"  - ... and {len(disagree) - 15} more")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tpl = sub.add_parser("template", help="실패 task → 라벨링 template CSV")
    p_tpl.add_argument(
        "--variant", action="append", required=True,
        help="name=path/to/variant_n3_dir",
    )
    p_tpl.add_argument(
        "--output", type=Path, default=Path("output/analysis/failure_template.csv"),
    )

    p_k = sub.add_parser("kappa", help="라벨된 CSV 두 개 비교 → Cohen's κ")
    p_k.add_argument("--rate1", type=Path, required=True)
    p_k.add_argument("--rate2", type=Path, required=True)
    p_k.add_argument("--output", type=Path, default=Path("output/analysis/failure_kappa.md"))

    args = parser.parse_args(argv)

    if args.cmd == "template":
        variants: dict[str, Path] = {}
        for spec in args.variant:
            if "=" not in spec:
                print(f"[error] --variant must be NAME=PATH: {spec}", file=sys.stderr)
                return 2
            name, path_str = spec.split("=", 1)
            variants[name.strip()] = Path(path_str)
        n = write_template(variants, args.output)
        print(f"[ok] wrote {args.output} ({n} failed runs)")
        return 0

    if args.cmd == "kappa":
        if not args.rate1.exists() or not args.rate2.exists():
            print(f"[error] missing rate file", file=sys.stderr)
            return 2
        rate1 = load_labeled(args.rate1)
        rate2 = load_labeled(args.rate2)
        report = render_kappa_report(rate1, rate2)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"[ok] wrote {args.output}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
