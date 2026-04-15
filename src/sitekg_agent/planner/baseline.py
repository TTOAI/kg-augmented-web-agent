"""Baseline planner — V2.5에서 이식한 LLM 기반 sub-goal 분해 + Tool Use 시스템 프롬프트.

KG를 사용하지 않고 task와 현재 observation만으로 계획을 세운다.
"""
from __future__ import annotations

from typing import Any

from ..config import LLMClient, parse_llm_action
from ..types import SubGoal


# ---------------------------------------------------------------------------
# Intent 분류 (task_type)
# ---------------------------------------------------------------------------


def classify_task_type(intent: str, llm: LLMClient) -> str:
    """LLM을 사용해 intent를 RETRIEVE / NAVIGATE / MUTATE 중 하나로 분류한다.

    파싱 실패 또는 알 수 없는 값이면 NAVIGATE를 반환한다.
    """
    system = (
        "Classify the user intent as exactly one of: RETRIEVE, NAVIGATE, MUTATE.\n"
        "RETRIEVE: extract or read data from a page (find, get, how many, what is).\n"
        "NAVIGATE: go to a specific page (open, go to, navigate, visit).\n"
        "MUTATE: submit, post, fill, click to change state (post, create, edit, submit).\n"
        'Respond ONLY with JSON: {"task_type": "RETRIEVE"|"NAVIGATE"|"MUTATE"}'
    )
    messages = [{"role": "user", "content": f"Intent: {intent}"}]
    response = llm.complete(system=system, messages=messages)
    parsed = parse_llm_action(response)
    task_type = str(parsed.get("task_type", "NAVIGATE")).upper()
    return task_type if task_type in ("RETRIEVE", "NAVIGATE", "MUTATE") else "NAVIGATE"


# ---------------------------------------------------------------------------
# Sub-goal 분해
# ---------------------------------------------------------------------------


def build_plan(*, task: str, task_type: str, observation: Any, llm: LLMClient) -> list[SubGoal]:
    """태스크를 2~5개 sub-goal로 분해한다. LLM 1회 호출."""
    system = (
        "You are a web task planner. Break down a web automation task into 2-5 sub-goals.\n"
        "Each sub-goal should be a concrete, verifiable objective — not a specific UI action.\n"
        "Good: 'Apply the status filter'  Bad: 'Click the dropdown'\n"
        "Consider the current page state when planning.\n"
        "For each sub-goal, classify its type (only two types):\n"
        '  "navigation" — reach a target page or URL state (open, navigate, go to, arrive at)\n'
        '  "action" — change page state or read/extract info (filter, apply, sort, submit, post, extract, read)\n'
        "\n"
        "IMPORTANT: For NAVIGATE tasks, the LAST sub-goal MUST be type 'navigation'.\n"
        "The final goal should be to arrive at the target page with the correct URL.\n"
        "Example: if the task is 'go to filtered items', the last goal should be\n"
        "'Navigate to the filtered page' (navigation), not 'Apply filter' (action).\n"
        "This ensures the page URL reflects the final state.\n"
        "\n"
        'Respond ONLY with JSON: {"sub_goals": [{"goal": "...", "type": "navigation|action"}, ...]}\n'
        "Keep each sub-goal to one short sentence."
    )
    lines = [
        f"Task: {task}",
        f"Task type: {task_type}",
        f"Current URL: {observation.url}",
        f"Page title: {observation.title}",
    ]
    if observation.links:
        lines.append(f"Links (first 15): {observation.links[:15]}")
    if observation.buttons:
        lines.append(f"Buttons: {observation.buttons[:10]}")
    if observation.inputs:
        lines.append(f"Input fields: {observation.inputs[:10]}")

    messages = [{"role": "user", "content": "\n".join(lines)}]
    response = llm.complete(system=system, messages=messages)
    parsed = parse_llm_action(response)
    sub_goals = parsed.get("sub_goals", [])
    if isinstance(sub_goals, list) and sub_goals:
        result = []
        for g in sub_goals:
            if isinstance(g, dict):
                result.append(SubGoal(str(g.get("goal", "")), str(g.get("type", "action"))))
            else:
                result.append(SubGoal(str(g)))
        return result if result else [SubGoal(task)]
    return [SubGoal(task)]


# ---------------------------------------------------------------------------
# Tool Use 시스템 프롬프트
# ---------------------------------------------------------------------------


def build_tool_use_system_prompt() -> str:
    """Tool Use 루프에서 사용할 기본 system prompt."""
    lines = [
        "You are a web automation agent using Tool Use.",
        "You will see the current page state and must call one tool per turn.",
        "",
        "Workflow:",
        "1. Read the current objective and page state.",
        "2. Decide the best single action to take (click, fill, search, goback, observe, remember, recall).",
        "3. Call that tool with precise arguments.",
        "4. When the objective is achieved, call the done tool.",
        "5. When the FULL task requires reporting data, call extract (only on the LAST sub-goal).",
        "6. If the task is impossible, call one of the failure tools (not_found, permission_denied, etc.).",
        "7. Before extract or done, use recall to verify completeness.",
    ]
    return "\n".join(lines)
