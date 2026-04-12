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



class SubGoal:
    """sub-goal과 유형 정보."""
    __slots__ = ("goal", "goal_type")

    def __init__(self, goal: str, goal_type: str = "cognition"):
        self.goal = goal
        self.goal_type = goal_type  # "navigation", "action", "cognition"

    def __repr__(self) -> str:
        return f"{self.goal} [{self.goal_type}]"


def build_plan(*, task: str, task_type: str, observation: Any, llm: LLMClient, kg_context: str = "") -> list[SubGoal]:
    """태스크를 2~5개 sub-goal로 분해한다. LLM 1회 호출."""
    system = (
        "You are a web task planner. Break down a web automation task into 2-5 sub-goals.\n"
        "Each sub-goal should be a concrete, verifiable objective — not a specific UI action.\n"
        "Good: 'Apply the status filter'  Bad: 'Click the dropdown'\n"
        "Consider the current page state when planning.\n"
        "For each sub-goal, classify its type:\n"
        '  "navigation" — move to a different page (open, navigate, go to)\n'
        '  "action" — change page state (filter, apply, sort, submit, post)\n'
        '  "cognition" — analyze or read information (determine, identify, find, check)\n'
        "\n"
        "IMPORTANT: For NAVIGATE tasks, the LAST sub-goal MUST be type 'navigation'.\n"
        "The final goal should be to arrive at the target page with the correct URL.\n"
        "Example: if the task is 'go to filtered items', the last goal should be\n"
        "'Navigate to the filtered page' (navigation), not 'Apply filter' (action).\n"
        "This ensures the page URL reflects the final state.\n"
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
    if kg_context:
        lines.append(f"\nSite knowledge:\n{kg_context}")

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

def build_tool_use_system_prompt() -> str:
    """Tool Use 모드용 system prompt. 규칙 대신 전략을 전달한다."""
    lines = [
        "You are a web automation agent controlling a browser via tools.",
        "Think step-by-step (your text is your reasoning), then call exactly one tool per turn.",
        "",
        "## Strategy",
        "1. Act on what you SEE, not what you KNOW. Click to explore — never guess.",
        "2. Click before typing. Reveal dropdown options first, then decide.",
        "3. After selecting options, submit to commit. Check URL parameters to confirm.",
        "4. Never repeat a failed action. Use goback to return to a known page and try a different path.",
        "6. Use the remember tool to save important facts (IDs, counts, names).",
        "7. Before extract or done, use recall to verify completeness.",
    ]
    return "\n".join(lines)


def build_observation_message(
    *,
    task: str,
    observation: Any,
    last_action_feedback: str = "",
    sub_goals: list[SubGoal] | None = None,
    current_goal_index: int = 0,
    start_url: str = "",
    kg_widgets: list[Any] | None = None,
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

    if kg_widgets:
        kg_lines = []
        for w in kg_widgets:
            line = f"● {w.widget_key} [{w.locator_strategy}: {w.locator_value}]"
            if w.side_effects:
                line += f" → {', '.join(w.side_effects)}"
            if w.visibility_condition:
                line += f" [visible if: {w.visibility_condition}]"
            kg_lines.append(line)
        sections.append("## KG Registered Widgets\n" + "\n".join(kg_lines))

    return "\n\n".join(sections)
