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
        max_tokens: int = 1024,
    ) -> "LLMToolResponse":
        """Tool Use 완성. Thought + tool call을 반환한다."""
        ...


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

class AnthropicLLMClient:
    """Claude API를 사용하는 LLMClient 구현.

    temperature: None이면 API 호출에 전달하지 않음 (provider default 사용).
    재현성 있는 실험을 위해 env var LLM_TEMPERATURE로 보통 0을 지정한다.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", temperature: float | None = None) -> None:
        import anthropic  # lazy import — 패키지 미설치 시 런타임 오류만 발생
        self._client = anthropic.Anthropic()
        self._model = model
        self._temperature = temperature

    def _extra_kwargs(self) -> dict[str, Any]:
        return {"temperature": self._temperature} if self._temperature is not None else {}

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=messages,
            **self._extra_kwargs(),
        )
        return response.content[0].text

    def complete_with_tools(
        self, *, system: str, messages: list[dict], tools: list[dict],
        max_tokens: int = 1024,
    ) -> LLMToolResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            tools=tools,
            **self._extra_kwargs(),
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
    """OpenAI API를 사용하는 LLMClient 구현.

    temperature: None이면 API 호출에 전달하지 않음 (provider default 사용).
    재현성 있는 실험을 위해 env var LLM_TEMPERATURE로 보통 0을 지정한다.
    """

    def __init__(self, model: str = "gpt-4o", temperature: float | None = None) -> None:
        import openai  # lazy import
        self._client = openai.OpenAI()
        self._model = model
        self._temperature = temperature

    def _extra_kwargs(self) -> dict[str, Any]:
        return {"temperature": self._temperature} if self._temperature is not None else {}

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        all_messages = [{"role": "system", "content": system}, *messages]
        response = self._client.chat.completions.create(
            model=self._model,
            messages=all_messages,  # type: ignore[arg-type]
            max_completion_tokens=1024,
            **self._extra_kwargs(),
        )
        return response.choices[0].message.content or ""

    def complete_with_tools(
        self, *, system: str, messages: list[dict], tools: list[dict],
        max_tokens: int = 1024,
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
            max_completion_tokens=max_tokens,
            parallel_tool_calls=False,  # 1턴 1 tool call 강제
            **self._extra_kwargs(),
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

def _read_temperature_env() -> float | None:
    """env var LLM_TEMPERATURE를 float로 파싱. 없거나 빈 값이면 None (provider default 사용)."""
    raw = os.getenv("LLM_TEMPERATURE", "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def make_llm_client() -> LLMClient | None:
    """LLM_PROVIDER 환경변수로 구현체를 선택한다.

    API 키가 없으면 None을 반환한다 (rule-based 폴백으로 동작).

    환경 변수:
        LLM_PROVIDER: 'anthropic'(기본) 또는 'openai'
        ANTHROPIC_MODEL / OPENAI_MODEL: 모델 이름
        LLM_TEMPERATURE: 숫자 (예 '0')를 넣으면 모든 호출에 temperature 고정.
            비워두면 provider 기본값 (보통 1.0) — **실험 재현성이 필요하면 '0'으로 설정**.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    temperature = _read_temperature_env()
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return OpenAILLMClient(model=model, temperature=temperature)
    # anthropic (기본값)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    return AnthropicLLMClient(model=model, temperature=temperature)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def classify_task_type(intent: str, llm: LLMClient) -> str:
    """LLM을 사용해 intent를 RETRIEVE / NAVIGATE / MUTATE 중 하나로 분류한다.

    파싱 실패 또는 알 수 없는 값이면 NAVIGATE를 반환한다. (LLM_TEMPERATURE=0 권장)

    분류 규칙 (정확도가 실험 성공률 전체에 영향):
      RETRIEVE — 페이지에서 데이터를 읽어 답으로 반환해야 하는 경우.
      NAVIGATE — 특정 페이지/URL에 도달하는 것이 목표. 사이드 이펙트 없음.
      MUTATE — 사용자/저장소/사이트 상태를 변경(생성/수정/삭제/설정).
    """
    system = (
        "Classify the user intent as EXACTLY one of: RETRIEVE, NAVIGATE, MUTATE.\n"
        "\n"
        "RETRIEVE — extract or read data from a page to answer a question.\n"
        "  Verbs: find, get, how many, what is, list, tell me, show (a count/value),\n"
        "  which, who is, count, return.\n"
        "\n"
        "NAVIGATE — reach a specific page or URL state without changing site state.\n"
        "  Verbs: go to, open, navigate to, visit, browse to, show (a page/view).\n"
        "\n"
        "MUTATE — change user/site/repo state (create, update, or delete data).\n"
        "  Verbs: create, add, post, comment, submit, delete, remove, rename,\n"
        "  change, update, set, edit, modify, assign, merge, close, reopen,\n"
        "  fork, star, unstar, follow, unfollow, approve, upvote, downvote, upload.\n"
        "\n"
        "Disambiguation tips:\n"
        "- If the intent has a URL embedded as DATA to be entered (e.g. 'set homepage\n"
        "  URL to https://...'), the intent is MUTATE, not NAVIGATE.\n"
        "- 'Show me my open issues' with no mutation verb → NAVIGATE.\n"
        "- 'Show the count of open issues' → RETRIEVE (a number is requested).\n"
        "- A question word ('how many', 'what is') signals RETRIEVE even if phrasing\n"
        "  superficially resembles navigation.\n"
        "\n"
        'Respond ONLY with JSON: {"task_type": "RETRIEVE" | "NAVIGATE" | "MUTATE"}'
    )
    messages = [{"role": "user", "content": f"Intent: {intent}"}]
    response = llm.complete(system=system, messages=messages)
    parsed = parse_llm_action(response)
    raw = parsed.get("task_type", "")
    task_type = str(raw).upper()
    if task_type in ("RETRIEVE", "NAVIGATE", "MUTATE"):
        return task_type
    # Fallback path (malformed response / missing key) — log so misclassification rate is monitorable.
    import logging
    logging.getLogger("webarena_verified").warning(
        "[classify_task_type] malformed response (raw=%r, parsed_keys=%s) → fallback NAVIGATE",
        raw, list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__,
    )
    return "NAVIGATE"



class SubGoal:
    """sub-goal과 유형 정보."""
    __slots__ = ("goal", "goal_type")

    def __init__(self, goal: str, goal_type: str = "action"):
        self.goal = goal
        self.goal_type = goal_type  # "navigation" | "action"

    def __repr__(self) -> str:
        return f"{self.goal} [{self.goal_type}]"


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
                goal_text = str(g.get("goal", "")).strip()
                goal_type = str(g.get("type", "action"))
                # 스키마 외의 값은 default "action"으로 정규화 — hard rule이 "navigation" 정확 매칭에 의존하므로
                # 오탈자/다른 레이블이 실수로 hard rule을 우회하지 않게 한다.
                if goal_type not in ("navigation", "action"):
                    goal_type = "action"
                if goal_text:
                    result.append(SubGoal(goal_text, goal_type))
            else:
                text = str(g).strip()
                if text:
                    result.append(SubGoal(text))
        return result if result else [SubGoal(task)]
    return [SubGoal(task)]



def parse_llm_action(response_text: str) -> dict[str, Any]:
    """LLM 응답 텍스트에서 JSON action을 파싱한다.

    ```json ... ``` 마크다운 펜스를 자동으로 제거한다.
    파싱 실패 시 {"action": "parse_error", ...} 폴백을 반환한다.
    (참고: 이 함수는 classify_task_type / build_plan의 JSON 파싱 유틸이며, action 키는
    현재 호출자가 무시한다. 'parse_error'는 과거의 'not_found' 관용을 대체하는 중립 레이블이다.)
    """
    text = response_text.strip()
    # 마크다운 코드 펜스 제거
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"action": "parse_error", "reasoning": f"LLM 응답 파싱 실패: {text[:100]}"}


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
        "5. Use the remember tool to save important facts (IDs, counts, names).",
        "6. Before extract or done, use recall to verify completeness.",
        "",
        "## Error-state outcomes",
        "Some tasks have an error state as the correct outcome. Call declare_error ONLY AFTER",
        "you have exhausted reasonable investigation. A premature declare_error will be rejected",
        "and you will be asked to continue.",
        "",
        "Before calling declare_error, verify ALL of the following:",
        "1. You have tried at least 3 meaningfully different strategies — different query terms,",
        "   filter combinations, alternative navigation paths, or scrolling through paginated results.",
        "2. The page does NOT already contain evidence of the answer in visible text, headings, or",
        "   lists. If evidence is visible anywhere, use observe/remember/done instead.",
        "3. Absence of a single UI option (e.g., a missing filter entry) is NOT sufficient grounds —",
        "   the answer may still be present in the page text or in other navigation paths.",
        "",
        "Valid error statuses:",
        "- NOT_FOUND_ERROR: target entity does not exist after thorough search.",
        "- ACTION_NOT_ALLOWED_ERROR: platform explicitly blocks the requested action in this state.",
        "- PERMISSION_DENIED_ERROR: current user lacks permission to perform the action.",
        "- DATA_VALIDATION_ERROR: required input is missing or invalid.",
        "- UNKNOWN_ERROR: unexpected failure that does not match the other categories.",
        "",
        "A correctly declared error is a valid outcome — but 'correctly' means only after",
        "reasonable exhaustion of alternatives.",
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
        # Tool-availability 안내는 두 context(last/non-last) 모두에 제공해 일관성 유지.
        if is_last:
            sections.append(
                "This is the final sub-goal. Available tools: click, fill, search, goback, "
                "observe, remember, recall, done, declare_error (extract is also available if "
                "this is a RETRIEVE task). declare_error is a valid final outcome when evidence "
                "points to a definitive error state."
            )
        else:
            sections.append(
                "Available tools for this sub-goal: click, fill, search, goback, observe, "
                "remember, recall, done, declare_error. Do not call extract on non-final "
                "sub-goals. declare_error is permitted when evidence for a definitive error "
                "state is clear, even on a non-final sub-goal."
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
