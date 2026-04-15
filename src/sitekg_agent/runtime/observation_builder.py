"""LLM에 보낼 observation 메시지 포맷터."""
from __future__ import annotations

from typing import Any

from ..types import SubGoal


def build_observation_message(
    *,
    task: str,
    observation: Any,
    last_action_feedback: str = "",
    sub_goals: list[SubGoal] | None = None,
    current_goal_index: int = 0,
    start_url: str = "",
) -> str:
    """페이지 상태를 마크다운 섹션으로 구조화한다 (Tool Use용)."""
    from urllib.parse import urlparse, parse_qs

    sections: list[str] = []

    task_section = f"## Task\n{task}"
    if start_url:
        task_section += f"\n**Started from:** {start_url}"
    sections.append(task_section)

    if sub_goals and current_goal_index < len(sub_goals):
        current_goal = sub_goals[current_goal_index].goal
        is_last = current_goal_index == len(sub_goals) - 1
        sections.append(
            f"## Current Objective ({current_goal_index + 1}/{len(sub_goals)})\n{current_goal}\n"
            "When achieved, call the done tool."
        )
        if not is_last:
            sections.append(
                "Use only action tools (click, fill, search, goback, done). "
                "Do not use extract or failure tools."
            )

    if last_action_feedback:
        sections.append(f"## Last Action Result\n{last_action_feedback}")

    parsed_url = urlparse(observation.url)
    params = parse_qs(parsed_url.query)
    params_str = ", ".join(f"{k}={v[0]}" for k, v in params.items()) if params else "(none)"
    page_lines = [
        f"**URL:** {observation.url}",
        f"**URL params:** {params_str}",
        f"**Title:** {observation.title}",
    ]
    if observation.headings:
        page_lines.append(f"**Headings:** {observation.headings}")
    if observation.text_lines:
        page_lines.append(f"**Visible text (first 10):** {observation.text_lines[:10]}")
    sections.append("## Page State\n" + "\n".join(page_lines))

    elements: list[str] = []
    if observation.links:
        total = len(observation.links)
        shown = min(30, total)
        truncated = f" ({shown}/{total} — use observe tool for more)" if total > shown else ""
        elements.append(f"**Links{truncated}:**\n" + "\n".join(f"- {l}" for l in observation.links[:30]))
    if observation.buttons:
        total = len(observation.buttons)
        shown = min(10, total)
        truncated = f" ({shown}/{total})" if total > shown else ""
        elements.append(f"**Buttons{truncated}:**\n" + "\n".join(f"- {b}" for b in observation.buttons[:shown]))
    if observation.dropdown_options:
        elements.append(
            "**Dropdown options (click to select):**\n"
            + "\n".join(f"- {d}" for d in observation.dropdown_options[:20])
        )
    if observation.inputs:
        elements.append("**Input fields:**\n" + "\n".join(f"- {i}" for i in observation.inputs[:10]))
    if elements:
        sections.append("## Interactive Elements\n" + "\n\n".join(elements))

    return "\n\n".join(sections)
