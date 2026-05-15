"""Per-trial signal extractor for the characterization study.

Inputs (per trial dir):
    <trial_dir>/agent_response.json       # task_type, status, retrieved_data
    <trial_dir>/webarena_verified.log     # agent + KG + LLM events
    <trial_dir>/eval_result.json          # post-measurement evaluator output (optional)
    <trial_dir>/network.har               # raw network capture (untouched)

Output: <trial_dir>/signals.json with the 5 signals defined in
docs/evaluation/metrics.md:
    1. evaluator_outcomes
    2. step_count
    3. mechanism_invocation
    4. trajectory_actions  (raw — divergence is computed by compare script)
    5. token_latency
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from site_adaptive_webagent.benchmarks.webarena_verified.types import TASK_LOG_FILENAME


# Log line patterns
_RE_KG_SESSION = re.compile(r"\[KG\] session loaded:\s*(.*)$")
_RE_KG_INFER = re.compile(
    r"\[KG\] inferred target=(\S+)\s+agreement=(\d+)/(\d+)\s+rejected=\[(.*?)\]"
)
_RE_KG_DISABLED = re.compile(r"\[KG\] target inferrer disabled")
_RE_KG_PATH = re.compile(r"\[KG\] (find_path|generate_hint|.*path).*")
_RE_LLM_STEP_ACTION = re.compile(
    r"\[LLM\] step=(\d+)\s+action=(\S+)\s+thought=(.*)$"
)
_RE_LLM_TOKENS = re.compile(
    r"\[LLM\] tokens in=(\d+)\s+out=(\d+)\s+cache_create=(\d+)\s+cache_read=(\d+)"
)
_RE_OUTCOME_DONE = re.compile(
    r"\[LLM\] (?:all goals complete|task completed|"
    r"(?:RETRIEVE )?final answer(?: stage failed)?|"
    r"final report_failure) in ([\d.]+)s \((\d+) steps?\)"
)
_RE_OUTCOME_TIMEOUT = re.compile(r"TIMEOUT|wall.?clock.*timeout|Killed", re.IGNORECASE)
_RE_TOOL_CALL = re.compile(r"\[LLM\] (\w+)\s+(.*)$")  # generic per-tool log


@dataclass
class StepAction:
    step: int
    action: str
    thought_excerpt: str = ""
    detail: str = ""  # raw arg line that follows the step= line


@dataclass
class TrialSignals:
    trial_dir: str
    task_id: Optional[int] = None
    variant: Optional[str] = None  # 'v0' / 'v1' / 'v1_tc' inferred from path
    # 1. evaluator outcomes
    agent_status: Optional[str] = None  # SUCCESS / FAILURE / etc from agent_response.json
    agent_evaluator: Optional[str] = None  # PASS/FAIL from eval_result.json (None if unscored)
    network_evaluator: Optional[str] = None  # PASS/FAIL/NA
    # 2. step count
    step_count: Optional[int] = None  # int or None if timeout
    timed_out: bool = False
    wall_clock_s: Optional[float] = None
    # 3. mechanism invocation
    kg_session_loaded: bool = False
    kg_inferrer_disabled: bool = False
    kg_inferred_target: Optional[str] = None
    kg_inferrer_agreement: Optional[str] = None  # "K/K" string
    kg_inferrer_rejected: list[str] = field(default_factory=list)
    # 4. trajectory actions (raw step list — divergence in compare script)
    trajectory: list[StepAction] = field(default_factory=list)
    # 5. token / latency
    llm_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_create_tokens: int = 0
    total_cache_read_tokens: int = 0


def _infer_variant_from_path(trial_dir: Path) -> Optional[str]:
    """Walk up the parent chain looking for v0 / v1 / v1_tc segments."""
    for part in trial_dir.parts[::-1]:
        if part in ("v0", "v1", "v1_tc"):
            return part
    return None


def _infer_task_id(trial_dir: Path) -> Optional[int]:
    """task_id is one of the parents (named numerically)."""
    for part in trial_dir.parts[::-1]:
        if part.isdigit():
            return int(part)
    return None


def parse_log(log_path: Path, sig: TrialSignals) -> None:
    """Parse log file and populate mechanism / trajectory / token / outcome fields."""
    if not log_path.exists():
        return
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    last_step_action: Optional[StepAction] = None
    for line in lines:
        if _RE_KG_SESSION.search(line):
            sig.kg_session_loaded = True
            continue
        if _RE_KG_DISABLED.search(line):
            sig.kg_inferrer_disabled = True
            continue
        m = _RE_KG_INFER.search(line)
        if m:
            sig.kg_inferred_target = m.group(1)
            sig.kg_inferrer_agreement = f"{m.group(2)}/{m.group(3)}"
            rejected_raw = m.group(4).strip()
            if rejected_raw:
                sig.kg_inferrer_rejected = [
                    r.strip().strip("'\"") for r in rejected_raw.split(",")
                    if r.strip()
                ]
            continue
        m = _RE_LLM_TOKENS.search(line)
        if m:
            sig.llm_calls += 1
            sig.total_input_tokens += int(m.group(1))
            sig.total_output_tokens += int(m.group(2))
            sig.total_cache_create_tokens += int(m.group(3))
            sig.total_cache_read_tokens += int(m.group(4))
            continue
        m = _RE_LLM_STEP_ACTION.search(line)
        if m:
            step = int(m.group(1))
            action = m.group(2)
            thought = m.group(3).strip().strip("'\"")
            if len(thought) > 200:
                thought = thought[:200] + "..."
            last_step_action = StepAction(
                step=step, action=action, thought_excerpt=thought,
            )
            sig.trajectory.append(last_step_action)
            continue
        m = _RE_OUTCOME_DONE.search(line)
        if m:
            sig.wall_clock_s = float(m.group(1))
            sig.step_count = int(m.group(2))
            continue
    # Heuristic: if no completion line and log has timeout marker, mark timed_out.
    if sig.step_count is None and _RE_OUTCOME_TIMEOUT.search(text):
        sig.timed_out = True


def parse_agent_response(trial_dir: Path, sig: TrialSignals) -> None:
    p = trial_dir / "agent_response.json"
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    sig.agent_status = data.get("status")


def parse_eval_result(trial_dir: Path, sig: TrialSignals) -> None:
    """Parse the post-measurement evaluator output (optional).

    Format depends on `webarena-verified eval-tasks` — handle a few shapes:
      {"score": 1.0, ...}  → PASS if score == 1.0
      {"agent_response": {...}, "network_event": {...}}
    Update field shapes here when the actual evaluator schema is locked.
    """
    p = trial_dir / "eval_result.json"
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    # Best-effort extraction; refine when concrete schema is known.
    score = data.get("score")
    if score is not None:
        sig.agent_evaluator = "PASS" if float(score) >= 1.0 else "FAIL"
    agent = data.get("agent_response_evaluator") or data.get("agent_response")
    if isinstance(agent, dict):
        ag_score = agent.get("score")
        if ag_score is not None:
            sig.agent_evaluator = "PASS" if float(ag_score) >= 1.0 else "FAIL"
    net = data.get("network_event_evaluator") or data.get("network_event")
    if isinstance(net, dict):
        net_score = net.get("score")
        if net_score is None:
            sig.network_evaluator = "NA"
        else:
            sig.network_evaluator = "PASS" if float(net_score) >= 1.0 else "FAIL"


def extract_signals(trial_dir: Path) -> TrialSignals:
    sig = TrialSignals(trial_dir=str(trial_dir))
    sig.task_id = _infer_task_id(trial_dir)
    sig.variant = _infer_variant_from_path(trial_dir)
    parse_log(trial_dir / TASK_LOG_FILENAME, sig)
    parse_agent_response(trial_dir, sig)
    parse_eval_result(trial_dir, sig)
    return sig


def write_signals(sig: TrialSignals, out_path: Path) -> None:
    payload = asdict(sig)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("trial_dirs", nargs="+", type=Path)
    ap.add_argument("--stdout", action="store_true",
                    help="Print to stdout instead of writing signals.json")
    args = ap.parse_args(argv)
    for d in args.trial_dirs:
        if not d.is_dir():
            print(f"[skip] {d}: not a directory", file=sys.stderr)
            continue
        sig = extract_signals(d)
        if args.stdout:
            print(json.dumps(asdict(sig), indent=2, ensure_ascii=False))
        else:
            write_signals(sig, d / "signals.json")
            print(f"[ok] {d}/signals.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
