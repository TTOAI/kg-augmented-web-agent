"""Baseline N=3 결과 분석 — sanity + broken eval 후보 + McNemar 입력 변환.

Plan: `docs/kg_design/06_evaluation_protocol.md` + `.claude/plans/joyful-moseying-diffie.md`.

입력:
  output/baseline_n3/
    N1/<task_id>/{agent_response.json, eval_result.json, webarena_verified.log}
    N2/...
    N3/...
    task_types.txt  (task_id<TAB>task_type)

산출:
  output/baseline_n3/analysis/raw.csv
    (task_id, run, task_type, agent_status, agent_error, eval_status, eval_score,
     step_count, wall_time_sec)
  output/baseline_n3/analysis/paired.csv
    (task_id, task_type, N1_success, N2_success, N3_success,
     majority_success, all3_success, any_success)
  output/baseline_n3/analysis/summary.md
    전체 성공률 + Wilson 95% CI + task_type별 + sanity + broken 후보
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

_RUN_NAMES = ("N1", "N2", "N3")
_STEPS_RE = re.compile(r"all goals complete in ([\d.]+)s \((\d+) steps\)")
# "insufficient_quota" 같은 agent 외부 원인도 env error로 집계
_ENV_ERROR_TOKENS = ("insufficient_quota", "RateLimitError", "ConnectionError")


def _read_task_types(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "\t" not in line:
            continue
        task_id_str, task_type = line.split("\t", 1)
        out[int(task_id_str)] = task_type.strip()
    return out


def _parse_log_metrics(log_path: Path) -> tuple[int | None, float | None, bool]:
    """step_count, wall_time_sec, env_error_flag."""
    if not log_path.exists():
        return (None, None, False)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    match = _STEPS_RE.search(text)
    step_count = int(match.group(2)) if match else None
    wall_time = float(match.group(1)) if match else None
    env_error = any(tok in text for tok in _ENV_ERROR_TOKENS)
    return (step_count, wall_time, env_error)


def _load_agent_response(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_eval_result(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
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


def collect(baseline_dir: Path) -> tuple[list[dict], dict[int, str]]:
    """각 run × task × 산출물 파싱 → rows."""
    task_types = _read_task_types(baseline_dir / "task_types.txt")
    rows: list[dict] = []
    for run in _RUN_NAMES:
        run_dir = baseline_dir / run
        if not run_dir.exists():
            continue
        for task_dir in sorted(run_dir.iterdir()):
            if not task_dir.is_dir() or not task_dir.name.isdigit():
                continue
            task_id = int(task_dir.name)
            resp = _load_agent_response(task_dir / "agent_response.json")
            ev = _load_eval_result(task_dir / "eval_result.json")
            steps, wall, env_err = _parse_log_metrics(task_dir / "webarena_verified.log")
            rows.append({
                "task_id": task_id,
                "run": run,
                "task_type": task_types.get(task_id, resp.get("task_type", "")),
                "agent_status": resp.get("status", ""),
                "agent_error": (resp.get("error_details") or "").replace("\n", " ")[:240],
                "eval_status": ev.get("status", ""),
                "eval_score": ev.get("score", ""),
                "step_count": steps if steps is not None else "",
                "wall_time_sec": wall if wall is not None else "",
                "env_error_in_log": env_err,
            })
    return rows, task_types


def write_raw_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "task_id", "run", "task_type", "agent_status", "agent_error",
        "eval_status", "eval_score", "step_count", "wall_time_sec", "env_error_in_log",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_paired_csv(rows: list[dict], task_types: dict[int, str], path: Path) -> None:
    """eval_status == 'SUCCESS' (대소문자 무관) 기준으로 pair 만들기."""
    def is_success(row: dict) -> bool:
        return str(row.get("eval_status", "")).strip().lower() == "success"

    by_task: dict[int, dict[str, bool]] = defaultdict(dict)
    for row in rows:
        by_task[row["task_id"]][row["run"]] = is_success(row)

    fields = [
        "task_id", "task_type",
        "N1_success", "N2_success", "N3_success",
        "majority_success", "all3_success", "any_success",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for task_id in sorted(by_task):
            r = by_task[task_id]
            vals = [int(r.get(run, False)) for run in _RUN_NAMES]
            w.writerow({
                "task_id": task_id,
                "task_type": task_types.get(task_id, ""),
                "N1_success": vals[0],
                "N2_success": vals[1],
                "N3_success": vals[2],
                "majority_success": int(sum(vals) >= 2),
                "all3_success": int(sum(vals) == 3),
                "any_success": int(sum(vals) >= 1),
            })


def _is_success(row: dict) -> bool:
    return str(row.get("eval_status", "")).strip().lower() == "success"


def build_summary(rows: list[dict], task_types: dict[int, str]) -> str:
    n = len(rows)
    successes = sum(1 for r in rows if _is_success(r))
    agent_success = sum(1 for r in rows if str(r["agent_status"]).lower() == "success")
    timeout_or_crash = sum(1 for r in rows if str(r["agent_status"]).lower() != "success")
    env_errors = sum(1 for r in rows if r["env_error_in_log"])
    eval_statuses = Counter(str(r["eval_status"]).strip().lower() for r in rows)

    # per task_type
    per_tt: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    for r in rows:
        tt = r["task_type"] or "?"
        k, total = per_tt[tt]
        per_tt[tt] = (k + (1 if _is_success(r) else 0), total + 1)

    # per-task 안정성 (3 runs 통계)
    by_task: dict[int, list[bool]] = defaultdict(list)
    for r in rows:
        by_task[r["task_id"]].append(_is_success(r))
    n_tasks = len(by_task)
    all3 = sum(1 for v in by_task.values() if len(v) == 3 and all(v))
    none3 = sum(1 for v in by_task.values() if len(v) == 3 and not any(v))
    mixed = sum(1 for v in by_task.values() if len(v) == 3 and 0 < sum(v) < 3)
    incomplete = sum(1 for v in by_task.values() if len(v) != 3)

    # broken 후보: agent SUCCESS인데 eval !=success
    broken_candidates: list[dict] = [
        r for r in rows
        if str(r["agent_status"]).lower() == "success" and not _is_success(r)
    ]

    # CI
    lo, hi = _wilson_ci(successes, n) if n else (0.0, 0.0)

    lines: list[str] = []
    lines.append("# Baseline N=3 분석 요약")
    lines.append("")
    lines.append(f"- Total runs: **{n}** (expected {3 * len(task_types)})")
    lines.append(f"- Unique tasks: **{n_tasks}**")
    lines.append(f"- Agent status=SUCCESS: **{agent_success}** / {n} "
                 f"({100 * agent_success / n:.1f}%)" if n else "- Agent status=SUCCESS: 0")
    lines.append(f"- Eval status=success: **{successes}** / {n} "
                 f"({100 * successes / n:.1f}%, Wilson 95% CI [{100*lo:.1f}%, {100*hi:.1f}%])"
                 if n else "- Eval status=success: 0")
    lines.append(f"- Agent non-success: {timeout_or_crash}")
    lines.append(f"- Runs with env error token in log: **{env_errors}**")
    lines.append("")
    lines.append("## Eval status 분포")
    lines.append("")
    lines.append("| status | count |")
    lines.append("|---|---|")
    for status, cnt in eval_statuses.most_common():
        lines.append(f"| `{status or '(blank)'}` | {cnt} |")
    lines.append("")
    lines.append("## task_type 별 eval success")
    lines.append("")
    lines.append("| task_type | success | total | rate |")
    lines.append("|---|---|---|---|")
    for tt, (k, total) in sorted(per_tt.items()):
        rate = 100 * k / total if total else 0
        lines.append(f"| {tt} | {k} | {total} | {rate:.1f}% |")
    lines.append("")
    lines.append("## Per-task N=3 안정성")
    lines.append("")
    lines.append(f"- All 3 success: **{all3}** / {n_tasks}")
    lines.append(f"- All 3 fail: **{none3}** / {n_tasks}")
    lines.append(f"- Mixed (1 or 2 success): **{mixed}** / {n_tasks}")
    if incomplete:
        lines.append(f"- Incomplete runs (missing): **{incomplete}**")
    lines.append("")
    lines.append("## Broken evaluator 후보")
    lines.append("")
    lines.append(f"Agent 내부 판정은 SUCCESS이나 evaluator는 success 아님. 수동 확인 필요 → "
                 f"`docs/kg_design/eval_exclusions.md`에 기록.")
    lines.append("")
    lines.append(f"- 후보 runs: **{len(broken_candidates)}**")
    if broken_candidates:
        lines.append("")
        lines.append("| task_id | run | task_type | eval_status | agent_error |")
        lines.append("|---|---|---|---|---|")
        # 중복 task_id 한 번만 보이게 정렬
        shown_keys: set[tuple[int, str]] = set()
        for r in broken_candidates:
            key = (r["task_id"], r["run"])
            if key in shown_keys:
                continue
            shown_keys.add(key)
            err = (r.get("agent_error") or "").replace("|", "\\|")[:60]
            lines.append(f"| {r['task_id']} | {r['run']} | {r['task_type']} | "
                         f"`{r['eval_status']}` | {err} |")
    lines.append("")
    lines.append("## Environment error 후보 (재측정 고려)")
    lines.append("")
    env_err_rows = [r for r in rows if r["env_error_in_log"]]
    if env_err_rows:
        lines.append("| task_id | run | agent_status | eval_status |")
        lines.append("|---|---|---|---|")
        for r in env_err_rows:
            lines.append(f"| {r['task_id']} | {r['run']} | `{r['agent_status']}` | "
                         f"`{r['eval_status']}` |")
    else:
        lines.append("(none detected)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("_Generated by `scripts/analyze_baseline.py`. "
                 "Reviewer-proof context: docs/kg_design/06 §2-2, §6._")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-dir", type=Path,
                        default=Path("output/baseline_n3"))
    parser.add_argument("--output-dir", type=Path,
                        default=Path("output/baseline_n3/analysis"))
    args = parser.parse_args(argv)

    if not args.baseline_dir.exists():
        print(f"[error] {args.baseline_dir} not found", file=sys.stderr)
        return 2

    rows, task_types = collect(args.baseline_dir)
    write_raw_csv(rows, args.output_dir / "raw.csv")
    write_paired_csv(rows, task_types, args.output_dir / "paired.csv")
    (args.output_dir / "summary.md").write_text(
        build_summary(rows, task_types), encoding="utf-8",
    )
    print(f"[ok] wrote {args.output_dir}/raw.csv")
    print(f"[ok] wrote {args.output_dir}/paired.csv")
    print(f"[ok] wrote {args.output_dir}/summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
