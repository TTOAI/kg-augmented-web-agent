"""Phase C 180 runs 측정 실행을 주기적으로 monitoring.

background로 main.log를 follow하며:
1. 주기적 상태 요약을 `status.md`에 기록
2. 문제 패턴 감지 시 stderr + `alerts.log`에 경고
3. 터미널 bell (BEL, \\a)로 critical alert

감지 패턴:
- quota/rate limit error (insufficient_quota, RateLimitError)
- docker container conflict
- task hang (N분간 log 업데이트 없음)
- LLM call budget exceeded
- 연속 task 실패 (≥3)
- timeout 임박 (task가 overall TIMEOUT의 80% 초과)

사용:
  nohup python3 scripts/monitor_phase_c.py \\
      --run-root output/phase_c_180 \\
      --total-runs 180 \\
      --check-interval 30 \\
      > output/phase_c_180/monitor_console.log 2>&1 &
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path


# 감지 패턴
_TASK_START_RE = re.compile(
    r"===== N=(\d+) TASK (\d+) \(([A-Z]+)\) \[(\w+)\] start (\d+:\d+:\d+)"
)
_TASK_DONE_RE = re.compile(
    r"===== N=(\d+) TASK (\d+) done (\d+:\d+:\d+) rc=(\d+)"
)
# 실제 persistent env 문제만 감지 — transient network (now retried in llm.py) 제외.
# "ConnectionError" literal은 너무 광범위해 log 문자열 false positive 유발 (Phase C 사건).
# insufficient_quota / RateLimitError: 측정 차단 신호
# openai.APIConnectionError: retry 후에도 해결 안 된 연속 실패 — 실제 env issue 의심
_ENV_ERROR_TOKENS = (
    "insufficient_quota",
    "RateLimitError: Error code: 429",
    "quota exceeded",
    "openai.APIConnectionError: Connection error",
)
_DOCKER_CONFLICT = "container name ../webarena_verified_gitlab../ is already in use"
_BUDGET_EXCEEDED = "exceeded task LLM call budget"
_AGENT_ERROR_RE = re.compile(r"에이전트 실행 실패:|agent_status.*UNKNOWN_ERROR")


def parse_status_line(line: str) -> dict | None:
    """한 줄에서 task 경계 이벤트 추출."""
    m = _TASK_START_RE.search(line)
    if m:
        return {
            "event": "start",
            "N": int(m.group(1)), "task_id": int(m.group(2)),
            "task_type": m.group(3), "variant": m.group(4),
            "time": m.group(5),
        }
    m = _TASK_DONE_RE.search(line)
    if m:
        return {
            "event": "done",
            "N": int(m.group(1)), "task_id": int(m.group(2)),
            "time": m.group(3), "rc": int(m.group(4)),
        }
    return None


def render_status(state: dict, total_runs: int, elapsed_s: float) -> str:
    completed = state["completed_count"]
    current = state["current_task"]
    alerts = state["recent_alerts"]
    errors = state["error_counts"]

    pct = 100 * completed / total_runs if total_runs else 0
    eta_str = "n/a"
    if completed > 0 and completed < total_runs:
        avg_per_run = elapsed_s / completed
        remaining = (total_runs - completed) * avg_per_run
        eta = datetime.now() + timedelta(seconds=remaining)
        eta_str = eta.strftime("%H:%M:%S") + f" (in {remaining / 60:.0f} min)"

    lines = [
        f"# Phase C Monitor — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- Completed: **{completed}/{total_runs}** ({pct:.1f}%)",
        f"- Elapsed: {elapsed_s / 60:.1f} min",
        f"- ETA: {eta_str}",
        "",
    ]
    if current:
        last_update = state["last_log_update"]
        stale = time.time() - last_update if last_update else 0
        lines.append(f"## Current task")
        lines.append(f"- N={current['N']} variant={current['variant']} "
                     f"task={current['task_id']} ({current['task_type']})")
        lines.append(f"- Started: {current['time']}  stale: {stale:.0f}s ago")
        lines.append("")

    lines.append("## Error counts")
    for k, v in errors.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    if alerts:
        lines.append("## Recent alerts (last 10)")
        for a in alerts:
            lines.append(f"- {a}")
        lines.append("")

    return "\n".join(lines)


def emit_alert(msg: str, alerts_log: Path, state: dict) -> None:
    """stderr + alerts.log + terminal bell."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    state["recent_alerts"].append(line)
    print(f"\a⚠️  {line}", file=sys.stderr, flush=True)
    with alerts_log.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True,
                        help="예: output/phase_c_180")
    parser.add_argument("--total-runs", type=int, default=180)
    parser.add_argument("--check-interval", type=int, default=30,
                        help="상태 체크 주기 (초, default 30)")
    parser.add_argument("--hang-threshold", type=int, default=300,
                        help="main.log 업데이트 없이 N초 경과 시 hang 경고")
    parser.add_argument("--timeout-warn-s", type=int, default=600,
                        help="current task가 N초 이상 실행 시 timeout 임박 경고")
    parser.add_argument("--log-file", type=str, default="main.log",
                        help="run-root 내 watch할 로그 파일명 (default main.log, recovery는 recovery.log)")
    parser.add_argument("--status-file", type=str, default="status.md",
                        help="상태 기록 파일 (default status.md)")
    parser.add_argument("--alerts-file", type=str, default="alerts.log",
                        help="알림 로그 파일 (default alerts.log)")
    args = parser.parse_args(argv)

    run_root = args.run_root
    main_log = run_root / args.log_file
    status_path = run_root / args.status_file
    alerts_log = run_root / args.alerts_file

    print(f"[monitor] watching {main_log}")
    print(f"[monitor] status → {status_path}")
    print(f"[monitor] alerts → {alerts_log}")

    # main.log 생성 기다림 (최대 60초)
    for _ in range(60):
        if main_log.exists():
            break
        time.sleep(1)
    if not main_log.exists():
        print(f"[monitor] ERROR: {main_log} not found after 60s", file=sys.stderr)
        return 2

    state = {
        "completed_count": 0,
        "current_task": None,
        "current_start_time": None,
        "last_log_update": time.time(),
        "last_log_size": 0,
        "recent_alerts": deque(maxlen=10),
        "error_counts": {
            "env_error": 0,
            "docker_conflict": 0,
            "budget_exceeded": 0,
            "agent_error": 0,
            "consecutive_failures": 0,
            "max_consecutive_failures": 0,
            "timeouts": 0,
        },
        "consecutive_fail_streak": 0,
    }

    t_start = time.time()
    last_status_write = 0.0
    seen_alerts: set[str] = set()  # dedupe 같은 pattern에서 연속 trigger

    with main_log.open("r", encoding="utf-8", errors="replace") as f:
        while True:
            line = f.readline()
            if not line:
                # EOF; check hang + write status + sleep
                now = time.time()
                size = main_log.stat().st_size
                if size > state["last_log_size"]:
                    state["last_log_update"] = now
                    state["last_log_size"] = size

                stale = now - state["last_log_update"]
                if state["current_task"] and stale > args.hang_threshold:
                    key = f"hang:{state['current_task']['task_id']}:{int(stale//60)}m"
                    if key not in seen_alerts:
                        seen_alerts.add(key)
                        emit_alert(
                            f"HANG? task={state['current_task']['task_id']} "
                            f"stale={stale:.0f}s (>{args.hang_threshold}s)",
                            alerts_log, state,
                        )
                if state["current_task"] and state["current_start_time"]:
                    task_elapsed = now - state["current_start_time"]
                    if task_elapsed > args.timeout_warn_s:
                        key = f"timeout_warn:{state['current_task']['task_id']}"
                        if key not in seen_alerts:
                            seen_alerts.add(key)
                            emit_alert(
                                f"TIMEOUT-IMMINENT task={state['current_task']['task_id']} "
                                f"elapsed={task_elapsed:.0f}s",
                                alerts_log, state,
                            )

                # periodic status dump
                if now - last_status_write >= args.check_interval:
                    status_path.write_text(
                        render_status(state, args.total_runs, now - t_start),
                        encoding="utf-8",
                    )
                    last_status_write = now

                # main process 끝났는지 체크 (main.log에 "done ====="이 있는지)
                # 너무 aggressive하지 않게, completed == total_runs면 종료
                if state["completed_count"] >= args.total_runs:
                    print(f"[monitor] reached {args.total_runs} runs — exiting")
                    status_path.write_text(
                        render_status(state, args.total_runs, now - t_start),
                        encoding="utf-8",
                    )
                    return 0

                time.sleep(2)
                continue

            # pattern match
            stripped = line.rstrip("\n")

            # 1. Task 경계
            ev = parse_status_line(stripped)
            if ev:
                if ev["event"] == "start":
                    state["current_task"] = ev
                    state["current_start_time"] = time.time()
                    seen_alerts.clear()  # task별 alert 리셋
                elif ev["event"] == "done":
                    state["completed_count"] += 1
                    state["current_task"] = None
                    state["current_start_time"] = None
                    if ev["rc"] != 0:
                        state["consecutive_fail_streak"] += 1
                        state["error_counts"]["consecutive_failures"] = state["consecutive_fail_streak"]
                        state["error_counts"]["max_consecutive_failures"] = max(
                            state["error_counts"]["max_consecutive_failures"],
                            state["consecutive_fail_streak"],
                        )
                        if state["consecutive_fail_streak"] >= 3:
                            emit_alert(
                                f"CONSECUTIVE-FAIL-STREAK: {state['consecutive_fail_streak']} tasks failed in a row",
                                alerts_log, state,
                            )
                    else:
                        state["consecutive_fail_streak"] = 0
                        state["error_counts"]["consecutive_failures"] = 0
                continue

            # 2. Error patterns
            for tok in _ENV_ERROR_TOKENS:
                if tok in stripped:
                    state["error_counts"]["env_error"] += 1
                    key = f"env_error:{tok}:{state['error_counts']['env_error']}"
                    if key not in seen_alerts:
                        seen_alerts.add(key)
                        emit_alert(
                            f"ENV-ERROR [{tok}]: {stripped[:150]}",
                            alerts_log, state,
                        )
                    break

            if _DOCKER_CONFLICT in stripped:
                state["error_counts"]["docker_conflict"] += 1
                emit_alert(f"DOCKER-CONFLICT: {stripped[:150]}", alerts_log, state)

            if _BUDGET_EXCEEDED in stripped:
                state["error_counts"]["budget_exceeded"] += 1
                tid = state["current_task"]["task_id"] if state["current_task"] else "?"
                emit_alert(
                    f"LLM-BUDGET-EXCEEDED task={tid}: {stripped[:100]}",
                    alerts_log, state,
                )

            if _AGENT_ERROR_RE.search(stripped):
                state["error_counts"]["agent_error"] += 1


if __name__ == "__main__":
    raise SystemExit(main())
