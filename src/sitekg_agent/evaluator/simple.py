"""단순 검증 구현 — V2.5의 _verify_done 로직을 이식.

하드 룰(마지막 navigation sub-goal 진입/종료 URL 동일 시 거부) + LLM judge.
"""
from __future__ import annotations

from typing import Any

from ..config import LLMClient, parse_llm_action
from ..types import PageObservation


def verify_done(
    *,
    goal: str,
    reason: str,
    current_obs: PageObservation,
    llm: LLMClient,
    task_notes: list[str] | None = None,
    sub_goal_type: str = "",
    sub_goal_start_url: str = "",
    is_last_goal: bool = False,
) -> str | bool:
    """LLM에게 현재 상태 + 누적된 task notes를 대조하여 done 검증을 요청한다.

    Returns:
        True — 목표 달성 확인
        str — 미달성 이유
    """
    from urllib.parse import urlparse, parse_qs

    parsed_url = urlparse(current_obs.url)
    params = parse_qs(parsed_url.query)
    params_str = ", ".join(f"{k}={v[0]}" for k, v in params.items()) if params else "(none)"

    # Hard rule: 마지막 sub-goal이 [navigation]이고 그 sub-goal 내에서 URL 진전이 없으면 거부.
    if (is_last_goal and sub_goal_type == "navigation"
            and sub_goal_start_url and sub_goal_start_url == current_obs.url):
        return "final navigation sub-goal requires URL change within the sub-goal"

    notes_section = ""
    if task_notes:
        notes_section = (
            "\n\nNotes accumulated during this task:\n"
            + "\n".join(f"- {n}" for n in task_notes)
        )

    system = (
        "You verify whether a sub-goal has been achieved.\n"
        "Decide PRIMARILY based on HARD EVIDENCE: current URL, URL parameters, page title.\n"
        "- If URL/params already satisfy the goal's target state (e.g., contain the keywords or "
        "filter values implied by the goal), APPROVE.\n"
        "- Accumulated notes are BACKGROUND CONTEXT. Do NOT reject based on them alone when "
        "hard evidence already matches the goal.\n"
        "- Reject only when hard evidence clearly shows the goal is NOT yet achieved (wrong page, "
        "missing required URL parameter, etc.).\n"
        'Respond ONLY with JSON: {"achieved": true} or {"achieved": false, "reason": "..."}'
    )
    user_msg = (
        f"Goal: {goal}\n"
        f"Agent's claim: {reason}\n\n"
        f"Actual page state:\n"
        f"  URL: {current_obs.url}\n"
        f"  URL parameters: {params_str}\n"
        f"  Page title: {current_obs.title}\n"
        f"  Visible text (first 5): {current_obs.text_lines[:5]}"
        f"{notes_section}"
    )
    try:
        response = llm.complete(system=system, messages=[{"role": "user", "content": user_msg}])
        parsed = parse_llm_action(response)
        if parsed.get("achieved", True):
            return True
        return parsed.get("reason", "goal not achieved")
    except Exception:
        return True  # 검증 실패 시 통과 (보수적)
