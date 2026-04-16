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
# executor.py의 다양한 종료 경로에서 뿌리는 "in Xs (Y steps)" 포맷을 모두 capture.
# 예: "task completed in 64.6s (22 steps)", "final extract in 72.0s (23 steps)",
#     "final declare_error → NOT_FOUND_ERROR in 95.3s (27 steps)" 등.
_STEPS_RE = re.compile(r"in ([\d.]+)s \((\d+) steps\)")
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


def _parse_log_metrics(log_path: Path) -> tuple[int | None, float | None, bool, int]:
    """step_count, wall_time_sec, env_error_flag, llm_call_count."""
    if not log_path.exists():
        return (None, None, False, 0)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    match = _STEPS_RE.search(text)
    step_count = int(match.group(2)) if match else None
    wall_time = float(match.group(1)) if match else None
    env_error = any(tok in text for tok in _ENV_ERROR_TOKENS)
    # LLM call count: "[LLM] step=" 라인 수 (중복 가능성 있으나 근사)
    llm_calls = len(re.findall(r"\[LLM\] step=", text))
    return (step_count, wall_time, env_error, llm_calls)


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
            steps, wall, env_err, llm_calls = _parse_log_metrics(
                task_dir / "webarena_verified.log",
            )
            # 어떤 evaluator가 실패했는지 (broken 후보 세분)
            failed_evaluators: list[str] = []
            for er in ev.get("evaluators_results") or []:
                if str(er.get("status", "")).lower() != "success":
                    name = str(er.get("evaluator_name", "unknown"))
                    failed_evaluators.append(name)
            rows.append({
                "task_id": task_id,
                "run": run,
                "task_type": task_types.get(task_id, resp.get("task_type", "")),
                "agent_status": resp.get("status", ""),
                "agent_error": (resp.get("error_details") or "").replace("\n", " ")[:240],
                "eval_status": ev.get("status", ""),
                "eval_score": ev.get("score", ""),
                "failed_evaluators": "|".join(failed_evaluators),
                "step_count": steps if steps is not None else "",
                "wall_time_sec": wall if wall is not None else "",
                "llm_calls": llm_calls,
                "env_error_in_log": env_err,
            })
    return rows, task_types


def write_raw_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "task_id", "run", "task_type", "agent_status", "agent_error",
        "eval_status", "eval_score", "failed_evaluators",
        "step_count", "wall_time_sec", "llm_calls", "env_error_in_log",
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


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    mid = len(s) // 2
    if len(s) % 2 == 1:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2


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

    # broken 후보: agent SUCCESS인데 eval != success
    broken_candidates: list[dict] = [
        r for r in rows
        if str(r["agent_status"]).lower() == "success" and not _is_success(r)
    ]
    # 세분화: 어떤 evaluator가 실패했나
    broken_by_category: Counter[str] = Counter()
    for r in broken_candidates:
        fe = str(r.get("failed_evaluators") or "")
        if not fe:
            broken_by_category["(unknown)"] += 1
        elif "NetworkEventEvaluator" in fe and "AgentResponseEvaluator" in fe:
            broken_by_category["Both network+response"] += 1
        elif "NetworkEventEvaluator" in fe:
            broken_by_category["NetworkEventEvaluator only"] += 1
        elif "AgentResponseEvaluator" in fe:
            broken_by_category["AgentResponseEvaluator only"] += 1
        else:
            broken_by_category[fe] += 1

    # McNemar discordant pair preview (majority vote → per-task pair)
    # 지금은 single variant(baseline)만 있으므로 per-task 안정성만 보여줌.
    # N=3 run 일관성: 3/3 성공/실패 외 mixed를 "per-task variance"로 리포트.

    # 성능 통계 (step·wall·llm_calls) — 성공 run만 포함해 outlier 완화
    steps_vals = [int(r["step_count"]) for r in rows if str(r.get("step_count", "")).isdigit()]
    wall_vals = [float(r["wall_time_sec"]) for r in rows if str(r.get("wall_time_sec") or "").replace(".", "", 1).isdigit()]
    llm_vals = [int(r["llm_calls"]) for r in rows if str(r.get("llm_calls", "")).isdigit() and int(r["llm_calls"]) > 0]

    # CI
    lo, hi = _wilson_ci(successes, n) if n else (0.0, 0.0)

    lines: list[str] = []
    lines.append("# Baseline N=3 분석 요약")
    lines.append("")
    lines.append("## 주요 수치 (primary)")
    lines.append("")
    if n:
        lines.append(f"- **Eval success rate**: {successes} / {n} = **{100 * successes / n:.1f}%** "
                     f"(Wilson 95% CI [{100*lo:.1f}%, {100*hi:.1f}%])")
        lines.append(f"- Agent status=SUCCESS: {agent_success} / {n} ({100 * agent_success / n:.1f}%)")
        lines.append(f"- Total runs: {n} (expected {3 * len(task_types)}) · Unique tasks: {n_tasks}")
    else:
        lines.append("- (empty)")
    lines.append("")
    lines.append("### Sanity")
    lines.append("")
    env_pct = (100 * env_errors / n) if n else 0
    lines.append(f"- Agent non-success: **{timeout_or_crash}**")
    lines.append(f"- Env error token in log: **{env_errors}** ({env_pct:.0f}%)")
    lines.append("")
    # Performance metrics (step/wall/llm_calls)
    lines.append("### Performance metrics")
    lines.append("")
    if steps_vals:
        lines.append(f"- Steps (n={len(steps_vals)}): median={_median(steps_vals):.0f}, "
                     f"mean={_mean(steps_vals):.1f}, min={min(steps_vals)}, max={max(steps_vals)}")
    if wall_vals:
        lines.append(f"- Wall-time sec (n={len(wall_vals)}): median={_median(wall_vals):.1f}, "
                     f"mean={_mean(wall_vals):.1f}")
    if llm_vals:
        lines.append(f"- LLM call count (n={len(llm_vals)}): median={_median(llm_vals):.0f}, "
                     f"mean={_mean(llm_vals):.1f}")
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
    lines.append("Agent 내부 판정은 SUCCESS이나 evaluator는 success 아님. 수동 확인 필요 → "
                 "`docs/kg_design/eval_exclusions.md`에 기록.")
    lines.append("")
    lines.append(f"- 전체 후보: **{len(broken_candidates)}** runs")
    if broken_by_category:
        lines.append("")
        lines.append("| 카테고리 | count |")
        lines.append("|---|---|")
        for cat, cnt in broken_by_category.most_common():
            lines.append(f"| {cat} | {cnt} |")
    if broken_candidates:
        lines.append("")
        lines.append("<details><summary>후보 task 상세 (클릭)</summary>")
        lines.append("")
        lines.append("| task_id | run | task_type | failed_evaluators |")
        lines.append("|---|---|---|---|")
        for r in broken_candidates:
            fe = (r.get("failed_evaluators") or "").replace("|", "/")[:60]
            lines.append(f"| {r['task_id']} | {r['run']} | {r['task_type']} | {fe} |")
        lines.append("")
        lines.append("</details>")
    lines.append("")
    lines.append("## Environment error 후보 (재측정 필요)")
    lines.append("")
    env_err_rows = [r for r in rows if r["env_error_in_log"]]
    lines.append(f"- {len(env_err_rows)} runs 에서 env error token 감지 (insufficient_quota 등)")
    if env_err_rows:
        lines.append("")
        lines.append("<details><summary>env error 목록 (클릭)</summary>")
        lines.append("")
        lines.append("| task_id | run | agent_status | eval_status |")
        lines.append("|---|---|---|---|")
        for r in env_err_rows:
            lines.append(f"| {r['task_id']} | {r['run']} | `{r['agent_status']}` | "
                         f"`{r['eval_status']}` |")
        lines.append("")
        lines.append("</details>")
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
