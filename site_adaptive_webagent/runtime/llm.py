"""LLM provider-agnostic interface and implementations.

사용법:
    llm = make_llm_client()   # .env의 LLM_PROVIDER로 구현체 선택
    if llm is not None:
        response = llm.complete(system="...", messages=[{"role": "user", "content": "..."}])
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Protocol, runtime_checkable

from .tools import LLMToolResponse, ToolCall
from .types import PriorBundle


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMClient(Protocol):
    """LLM provider-agnostic 인터페이스."""

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        """단일 완성 요청. 응답 텍스트를 반환한다."""
        ...

    def complete_with_tools(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict],
    ) -> "LLMToolResponse":
        """Tool Use 완성. Thought + tool call을 반환한다."""
        ...


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

class AnthropicLLMClient:
    """Claude API를 사용하는 LLMClient 구현."""

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        import anthropic  # lazy import — 패키지 미설치 시 런타임 오류만 발생
        self._client = anthropic.Anthropic()
        self._model = model

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        return response.content[0].text

    def complete_with_tools(
        self, *, system: str, messages: list[dict], tools: list[dict],
    ) -> LLMToolResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
            tools=tools,
        )
        thought = None
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                thought = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=block.input))
        return LLMToolResponse(thought=thought, tool_calls=tool_calls, raw_content=list(response.content))


class OpenAILLMClient:
    """OpenAI API를 사용하는 LLMClient 구현."""

    def __init__(self, model: str = "gpt-4o") -> None:
        import openai  # lazy import
        self._client = openai.OpenAI()
        self._model = model

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        all_messages = [{"role": "system", "content": system}, *messages]
        response = self._client.chat.completions.create(
            model=self._model,
            messages=all_messages,  # type: ignore[arg-type]
            max_completion_tokens=1024,
        )
        return response.choices[0].message.content or ""

    def complete_with_tools(
        self, *, system: str, messages: list[dict], tools: list[dict],
    ) -> LLMToolResponse:
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]
        # Anthropic content-block 메시지를 OpenAI 형식으로 변환
        oai_messages = [{"role": "system", "content": system}]
        for msg in messages:
            oai_messages.extend(_to_openai_messages(msg))
        response = self._client.chat.completions.create(
            model=self._model,
            messages=oai_messages,  # type: ignore[arg-type]
            tools=oai_tools,  # type: ignore[arg-type]
            max_completion_tokens=1024,
            parallel_tool_calls=False,  # 1턴 1 tool call 강제
        )
        choice = response.choices[0]
        thought = choice.message.content
        tool_calls: list[ToolCall] = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))
        return LLMToolResponse(thought=thought, tool_calls=tool_calls, raw_content=[choice.message])


def _to_openai_messages(msg: dict) -> list[dict]:
    """Anthropic content-block 메시지를 OpenAI 형식 메시지 리스트로 변환한다."""
    role = msg.get("role", "user")
    content = msg.get("content")

    # 단순 텍스트 메시지
    if isinstance(content, str):
        return [{"role": role, "content": content}]

    # content block 리스트
    if not isinstance(content, list):
        return [{"role": role, "content": str(content)}]

    # assistant 메시지: text + tool_use → OpenAI assistant + tool_calls
    if role == "assistant":
        text_parts = []
        tool_calls_oai = []
        for block in content:
            if block.get("type") == "text":
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                tool_calls_oai.append({
                    "id": block["id"],
                    "type": "function",
                    "function": {
                        "name": block["name"],
                        "arguments": json.dumps(block["input"]),
                    },
                })
        result: dict = {"role": "assistant", "content": "\n".join(text_parts) or None}
        if tool_calls_oai:
            result["tool_calls"] = tool_calls_oai
        return [result]

    # user 메시지: tool_result + text 블록 → OpenAI tool messages + user message
    results = []
    text_parts = []
    for block in content:
        if block.get("type") == "tool_result":
            results.append({
                "role": "tool",
                "tool_call_id": block["tool_use_id"],
                "content": block.get("content", ""),
            })
        elif block.get("type") == "text":
            text_parts.append(block["text"])
        else:
            text_parts.append(str(block))
    if text_parts:
        results.append({"role": "user", "content": "\n".join(text_parts)})
    return results if results else [{"role": "user", "content": ""}]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def make_llm_client() -> LLMClient | None:
    """LLM_PROVIDER 환경변수로 구현체를 선택한다.

    API 키가 없으면 None을 반환한다 (rule-based 폴백으로 동작).
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return OpenAILLMClient(model=model)
    # anthropic (기본값)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    return AnthropicLLMClient(model=model)


# ---------------------------------------------------------------------------
# Prompt builders
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


def build_system_prompt(prior_bundle: PriorBundle | None) -> str:
    """PriorBundle을 LLM system prompt로 직렬화한다."""
    lines = [
        "You are a web automation agent. Respond in English with a single JSON action.",
        "",
        "## Rules",
        "1. Act on what you SEE, not what you KNOW. Click to explore — never guess syntax or URLs.",
        "2. Click before typing. Reveal options first, then decide.",
        "3. After selecting filters/options, click Search/Submit to commit. Check URL parameters to confirm.",
        "4. Never repeat a failed action. Try a different approach.",
        "5. When you find important facts, write 'NOTE: ...' in your reasoning (e.g. 'NOTE: Project ID is 183'). These are saved and shown in every step.",
        "6. Before extract or done, cross-check your answer against your collected notes. If notes show multiple items, include ALL of them.",
        "",
        "## Actions",
        '{"reasoning": "...", "action": "...", "target": "...", "value": "...", "url": "...", "element_type": "button|link", "label": "...", "submit": true/false}',
        '  click, fill, goback, search, observe, extract, done, not_found, permission_denied, action_not_allowed, unknown_error',
        '  click: set "target" to the name only (NOT the path). Use "url" or "element_type" to disambiguate.',
        '  fill: set "target", "value". "submit": true to press Enter.',
        '  observe: set "target" (keyword) to filter truncated lists.',
        '  note: save information for later. Set "value" (fact to remember). Use when collecting data across pages.',
        '  extract: set "value" (complete answer), "label".',
    ]

    if prior_bundle is not None:
        profile = prior_bundle.site_profile
        lines += [
            "",
            "## Site Knowledge",
            f"Site: {profile.display_name}  Base URL: {profile.base_url}  Auth: {profile.auth_type}",
        ]

        if prior_bundle.page_types:
            lines += ["", "### Known Pages"]
            for pt in prior_bundle.page_types:
                desc = f" — {pt.description}" if pt.description else ""
                lines.append(f"  [{pt.page_key}] {pt.display_name}{desc}")
                if pt.url_patterns:
                    lines.append(f"    URLs: {', '.join(pt.url_patterns)}")

        if prior_bundle.action_schemas:
            lines += ["", "### Available Actions (use these to navigate the site)"]
            for action in prior_bundle.action_schemas:
                desc = f" — {action.description}" if action.description else ""
                src = action.source_page_key or "any"
                tgt = f" → {action.target_page_key}" if action.target_page_key else ""
                lines.append(f"  [{action.action_key}] {action.display_name}{desc} (from: {src}{tgt})")
                if action.locator_value:
                    lines.append(f"    Locator ({action.locator_strategy}): {action.locator_value}")

    return "\n".join(lines)


class SubGoal:
    """sub-goal과 유형 정보."""
    __slots__ = ("goal", "goal_type")

    def __init__(self, goal: str, goal_type: str = "cognition"):
        self.goal = goal
        self.goal_type = goal_type  # "navigation", "action", "cognition"

    def __repr__(self) -> str:
        return f"{self.goal} [{self.goal_type}]"


def build_plan(*, task: str, task_type: str, observation: Any, llm: LLMClient) -> list[SubGoal]:
    """태스크를 2~5개 sub-goal로 분해한다. LLM 1회 호출."""
    system = (
        "You are a web task planner. Break down a web automation task into 2-5 sub-goals.\n"
        "Each sub-goal should be a concrete, verifiable objective — not a specific UI action.\n"
        "Good: 'Apply the bug label filter'  Bad: 'Click the Label dropdown'\n"
        "Consider the current page state when planning.\n"
        "For each sub-goal, classify its type:\n"
        '  "navigation" — move to a different page (open, navigate, go to)\n'
        '  "action" — change page state (filter, apply, sort, submit, post)\n'
        '  "cognition" — analyze or read information (determine, identify, find, check)\n'
        "\n"
        "IMPORTANT: For NAVIGATE tasks, the LAST sub-goal MUST be type 'navigation'.\n"
        "The final goal should be to arrive at the target page with the correct URL.\n"
        "Example: if the task is 'go to bug issues', the last goal should be\n"
        "'Navigate to the filtered bug issues page' (navigation), not 'Apply bug filter' (action).\n"
        "This ensures the page URL reflects the final state.\n"
        "Do NOT create sub-goals to apply filters or sorts that are likely already the page defaults.\n"
        "Only filter/sort when the task explicitly requires a non-default state (e.g. 'bug label', 'help wanted').\n"
        "\n"
        'Respond ONLY with JSON: {"sub_goals": [{"goal": "...", "type": "navigation|action|cognition"}, ...]}\n'
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
                result.append(SubGoal(str(g.get("goal", "")), str(g.get("type", "cognition"))))
            else:
                result.append(SubGoal(str(g)))
        return result if result else [SubGoal(task)]
    return [SubGoal(task)]


def build_action_request(
    *,
    task: str,
    observation: Any,
    last_action_result: str = "",
    sub_goals: list[SubGoal] | None = None,
    current_goal_index: int = 0,
    notes: list[str] | None = None,
) -> str:
    """태스크 지시와 현재 페이지 상태를 user 메시지로 직렬화한다."""
    lines = [f"Task: {task}", ""]
    if notes:
        lines += [f"Collected notes: {notes}", ""]

    if sub_goals and current_goal_index < len(sub_goals):
        current_goal = sub_goals[current_goal_index].goal
        is_last = current_goal_index == len(sub_goals) - 1
        lines += [
            f"Current objective ({current_goal_index + 1}/{len(sub_goals)}): {current_goal}",
            "When this objective is achieved, declare done. Do not work beyond this objective.",
        ]
        if not is_last:
            lines.append("Use only action commands (click, fill, goto, search, done). Do not use extract or failure actions.")
        lines.append("")

    if last_action_result:
        lines += [f"Last action result: {last_action_result}", ""]
    from urllib.parse import urlparse, parse_qs
    parsed_url = urlparse(observation.url)
    params = parse_qs(parsed_url.query)
    params_str = ", ".join(f"{k}={v[0]}" for k, v in params.items()) if params else "(none)"
    lines += [
        f"Current URL: {observation.url}",
        f"URL parameters: {params_str}",
        f"Page title: {observation.title}",
    ]
    if observation.headings:
        lines.append(f"Headings: {observation.headings}")
    if observation.text_lines:
        lines.append(f"Visible text (first 10): {observation.text_lines[:10]}")
    if observation.links:
        total = len(observation.links)
        shown = min(30, total)
        label = f"Links ({shown} of {total} — use 'observe' to see more)" if total > shown else "Links"
        lines.append(f"{label}: {observation.links[:30]}")
    if observation.dropdown_options:
        lines.append(f"Dropdown options (click to select): {observation.dropdown_options[:20]}")
    if observation.buttons:
        total = len(observation.buttons)
        shown = min(10, total)
        label = f"Buttons ({shown} of {total})" if total > shown else "Buttons"
        lines.append(f"{label}: {observation.buttons[:10]}")
    if observation.inputs:
        lines.append(f"Input fields: {observation.inputs[:10]}")
    lines += ["", "What single action should be taken? Respond with JSON only."]
    return "\n".join(lines)


def parse_llm_action(response_text: str) -> dict[str, Any]:
    """LLM 응답 텍스트에서 JSON action을 파싱한다.

    ```json ... ``` 마크다운 펜스를 자동으로 제거한다.
    파싱 실패 시 {"action": "not_found"} 폴백을 반환한다.
    """
    text = response_text.strip()
    # 마크다운 코드 펜스 제거
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"action": "not_found", "reasoning": f"LLM 응답 파싱 실패: {text[:100]}"}


# ---------------------------------------------------------------------------
# Tool Use prompt builders
# ---------------------------------------------------------------------------

def build_tool_use_system_prompt(prior_bundle: PriorBundle | None) -> str:
    """Tool Use 모드용 system prompt. 규칙 대신 전략을 전달한다."""
    lines = [
        "You are a web automation agent controlling a browser via tools.",
        "Think step-by-step (your text is your reasoning), then call exactly one tool per turn.",
        "",
        "## Strategy",
        "1. Act on what you SEE, not what you KNOW. Click to explore — never guess.",
        "2. Click before typing. To apply filters, click the filter/search input to reveal dropdown categories (e.g. Label, Assignee), then click through options. Do NOT type filter queries directly.",
        "3. After selecting filters/options, click Search/Submit to commit. Check URL parameters to confirm.",
        "4. Check if the page already shows the desired state before applying filters. Don't re-apply defaults.",
        "5. Never repeat a failed action. Use goback to return to a known page and try a different path.",
        "6. Use the remember tool to save important facts (IDs, counts, names).",
        "7. Before extract or done, use recall to verify completeness.",
    ]

    if prior_bundle is not None:
        profile = prior_bundle.site_profile
        lines += [
            "",
            "## Site Knowledge",
            f"Site: {profile.display_name}  Base URL: {profile.base_url}  Auth: {profile.auth_type}",
        ]

        if prior_bundle.page_types:
            lines += ["", "### Known Pages"]
            for pt in prior_bundle.page_types:
                desc = f" — {pt.description}" if pt.description else ""
                lines.append(f"  [{pt.page_key}] {pt.display_name}{desc}")
                if pt.url_patterns:
                    lines.append(f"    URLs: {', '.join(pt.url_patterns)}")

        if prior_bundle.action_schemas:
            lines += ["", "### Available Actions (use these to navigate the site)"]
            for action in prior_bundle.action_schemas:
                desc = f" — {action.description}" if action.description else ""
                src = action.source_page_key or "any"
                tgt = f" → {action.target_page_key}" if action.target_page_key else ""
                lines.append(f"  [{action.action_key}] {action.display_name}{desc} (from: {src}{tgt})")
                if action.locator_value:
                    lines.append(f"    Locator ({action.locator_strategy}): {action.locator_value}")

    return "\n".join(lines)


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
            sections.append("Use only action tools (click, fill, search, goback, done). Do not use extract or failure tools.")

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
