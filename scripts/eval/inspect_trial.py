"""한 trial(시행)의 intent·ground truth·agent 답변·평가기 판정을 한 화면에 출력.

수동 검증용 헬퍼. 평가기가 진짜 맞는지, 의미적으로는 성공했지만 형식 차이로
fail로 나오는지 등을 사용자가 직접 검토할 때 사용한다.

Usage:
    .venv/bin/python scripts/eval/inspect_trial.py <trial_dir> [<trial_dir>...]

예:
    .venv/bin/python scripts/eval/inspect_trial.py \\
        output/characterization_m1_repro/v0/102/trial_1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

import webarena_verified

DATASET_PATH = (
    Path(webarena_verified.__file__).parent / "assets" / "dataset" / "webarena-verified.json"
)

_RE_STEP_URL = re.compile(r"step=\d+\s+url=(\S+)")
_RE_STEP_ACTION = re.compile(r"step=(\d+)\s+action=(\S+)\s+thought='([^']{0,80})")
_RE_COMPLETED = re.compile(r"(?:task completed|all goals complete) in [\d.]+s \((\d+) steps?\)")
_RE_SUBGOAL_FAIL = re.compile(r"goal (\d+/\d+) failed after all retries")
_RE_TIMEOUT = re.compile(r"\bTIMEOUT\b")
# repo 패턴: owner/repo (둘 다 식별자 character만)
_RE_REPO_PATH = re.compile(r"\b([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)\b")
_RE_EXP_REPO = re.compile(r"__GITLAB__/([a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+)")


def load_dataset() -> dict[int, dict]:
    with open(DATASET_PATH) as f:
        tasks = json.load(f)
    return {t["task_id"]: t for t in tasks}


def parse_trial_path(trial_dir: Path) -> tuple[Optional[int], Optional[str], Optional[int]]:
    """경로 .../v0/102/trial_1 → (102, 'v0', 1)"""
    task_id, variant, trial_n = None, None, None
    for p in trial_dir.parts:
        if p in ("v0", "v1", "v1_tc"):
            variant = p
        elif p.startswith("trial_"):
            try:
                trial_n = int(p.split("_")[1])
            except (ValueError, IndexError):
                pass
        elif p.isdigit() and 1 <= int(p) <= 10000:
            task_id = int(p)
    return task_id, variant, trial_n


def fmt_expected(eval_entries: list[dict]) -> list[str]:
    """task definition의 eval[] 항목을 사람이 읽기 좋게 요약."""
    lines = []
    for e in eval_entries:
        name = e.get("evaluator", "?")
        exp = e.get("expected", {})
        if name == "AgentResponseEvaluator":
            parts = []
            for k in ("task_type", "status", "retrieved_data"):
                if k in exp:
                    parts.append(f"{k}={exp[k]!r}")
            lines.append(f"AgentResponseEvaluator: {', '.join(parts)}")
        elif name == "NetworkEventEvaluator":
            url = exp.get("url", "")
            method = exp.get("http_method", "GET")
            ref = (exp.get("headers") or {}).get("referer")
            label = f"{method} {url}"
            if ref:
                label += f"  referer={ref}"
            lines.append(f"NetworkEventEvaluator: {label}")
        else:
            lines.append(f"{name}: {json.dumps(exp, ensure_ascii=False)[:140]}")
    return lines


def read_log_tail(log_path: Path) -> dict:
    """log에서 last URL, completion 종류, 마지막 action 3개를 추출."""
    info = {"last_url": None, "completion": "(none)", "last_actions": []}
    if not log_path.exists():
        info["completion"] = "(log missing)"
        return info
    text = log_path.read_text(encoding="utf-8", errors="replace")

    urls = _RE_STEP_URL.findall(text)
    if urls:
        info["last_url"] = urls[-1]

    if _RE_COMPLETED.search(text):
        m = _RE_COMPLETED.search(text)
        info["completion"] = f"task completed ({m.group(1)} steps)"
    elif _RE_SUBGOAL_FAIL.search(text):
        m = _RE_SUBGOAL_FAIL.search(text)
        info["completion"] = f"sub-goal {m.group(1)} failed after retries"
    elif _RE_TIMEOUT.search(text):
        info["completion"] = "TIMEOUT (wrapper killed)"

    actions = _RE_STEP_ACTION.findall(text)
    info["last_actions"] = list(actions[-3:])
    return info


def fmt_evaluator_verdict(eval_result: dict) -> list[str]:
    """eval_result.json을 요약. 실패한 evaluator는 첫 fail msg를 함께."""
    lines = []
    overall = eval_result.get("status", "?")
    score = eval_result.get("score", 0.0)
    lines.append(f"Overall: {overall.upper()} (score {score})")
    for er in eval_result.get("evaluators_results", []) or []:
        name = er.get("evaluator_name", "?")
        status = er.get("status", "?")
        sc = er.get("score", 0)
        fail_msg = ""
        if status == "failure":
            for a in er.get("assertions") or []:
                msgs = a.get("assertion_msgs") or []
                if msgs:
                    fail_msg = f" — {msgs[0][:140]}"
                    break
            if not fail_msg and er.get("error_msg"):
                fail_msg = f" — {er['error_msg'][:140]}"
        lines.append(f"  {name}: {status} (score {sc}){fail_msg}")
    return lines


def heuristic_flags(
    task_def: dict, agent_resp: dict, eval_result: Optional[dict]
) -> list[str]:
    """자동 발견 가능한 의심점. 판정은 사람이 한다."""
    flags = []
    if not eval_result or eval_result.get("status") != "failure":
        return flags

    # H1: intent에 언급된 repo와 expected URL의 repo가 다른 경우 (broken-eval-task 후보)
    intent = task_def.get("intent", "")
    for ev in task_def.get("eval", []) or []:
        if ev.get("evaluator") != "NetworkEventEvaluator":
            continue
        exp_url = (ev.get("expected") or {}).get("url", "")
        m = _RE_EXP_REPO.search(exp_url)
        if not m:
            continue
        exp_repo = m.group(1)
        intent_repos = [r for r in _RE_REPO_PATH.findall(intent) if "/" in r]
        if intent_repos and exp_repo not in intent_repos:
            flags.append(
                f"intent의 repo({intent_repos[0]})와 expected URL의 repo({exp_repo})가 다름 — broken-eval-task 후보"
            )
        break

    # H2: agent self-status가 SUCCESS인데 평가기는 FAIL
    if agent_resp.get("status") == "SUCCESS":
        flags.append("agent self-status=SUCCESS인데 평가기 FAIL — 형식 차이/dataset 오류 후보")

    return flags


def inspect(trial_dir: Path, dataset: dict[int, dict]) -> None:
    print(f"== Trial: {trial_dir} ==")
    task_id, variant, trial_n = parse_trial_path(trial_dir)
    print(f"Task {task_id} | variant={variant} | trial={trial_n}")
    print()

    task_def = dataset.get(task_id) if task_id is not None else None

    print("[1] INTENT")
    if task_def:
        print(f"  {task_def.get('intent', '(no intent field)')}")
    else:
        print("  (task definition not found)")
    print()

    print("[2] GROUND TRUTH (expected)")
    if task_def:
        for line in fmt_expected(task_def.get("eval", []) or []):
            print(f"  - {line}")
    else:
        print("  (no task def)")
    print()

    print("[3] AGENT ANSWER (agent_response.json)")
    agent_resp: dict = {}
    ar_path = trial_dir / "agent_response.json"
    if ar_path.exists():
        agent_resp = json.loads(ar_path.read_text())
        print(f"  task_type:     {agent_resp.get('task_type')}")
        print(f"  status:        {agent_resp.get('status')}")
        print(f"  retrieved:     {agent_resp.get('retrieved_data')}")
        if agent_resp.get("error_details"):
            print(f"  error_details: {agent_resp['error_details']}")
    else:
        print("  (missing — likely timeout)")
    print()

    print("[4] AGENT TRAJECTORY (log tail)")
    log_info = read_log_tail(trial_dir / "webarena_verified.log")
    print(f"  last url:   {log_info['last_url']}")
    print(f"  completion: {log_info['completion']}")
    if log_info["last_actions"]:
        print(f"  last actions:")
        for s, a, t in log_info["last_actions"]:
            print(f"    step={s} action={a} thought='{t}...'")
    print()

    print("[5] EVALUATOR VERDICT (eval_result.json)")
    eval_result: Optional[dict] = None
    er_path = trial_dir / "eval_result.json"
    if er_path.exists():
        eval_result = json.loads(er_path.read_text())
        for line in fmt_evaluator_verdict(eval_result):
            print(line)
    else:
        print("  (missing — eval not run for this trial)")
    print()

    print("[6] HEURISTIC FLAGS")
    flags = heuristic_flags(task_def or {}, agent_resp, eval_result)
    if flags:
        for f in flags:
            print(f"  ⚠ {f}")
    else:
        print("  (none)")
    print()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="한 trial의 intent/expected/agent/evaluator를 한 화면에 출력."
    )
    ap.add_argument(
        "trial_dirs",
        nargs="+",
        type=Path,
        help="trial 디렉터리 (예: output/.../v0/102/trial_1). 여러 개 가능.",
    )
    args = ap.parse_args(argv)

    dataset = load_dataset()
    for i, trial_dir in enumerate(args.trial_dirs):
        if not trial_dir.exists():
            print(f"!! {trial_dir} not found", file=sys.stderr)
            continue
        if i > 0:
            print("=" * 70)
        inspect(trial_dir, dataset)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
