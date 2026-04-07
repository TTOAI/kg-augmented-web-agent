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
        "You are a web automation agent. Complete tasks on websites by interacting with the browser.",
        "Analyze the current page state and decide the best single action to take.",
        "Always respond in English only.",
        "",
        "Respond ONLY with a JSON object using this schema:",
        '{"reasoning": "...", "action": "extract|click|goto|search|fill|done|not_found|permission_denied|action_not_allowed|data_validation_error|unknown_error",',
        ' "value": "...", "label": "...", "target": "...", "url": "..."}',
        "Keep reasoning to 1-2 sentences. Be concise.",
        "",
        "Action descriptions:",
        '  "extract"   — the requested data is already visible; set "value" to the exact answer only (a number, name, or URL — no extra words), and "label" (what it represents).',
        '               Before extracting, verify your value matches what the task asks for (e.g. ID → numeric ID, not a name).',
        '  "click"     — click a link or button; set "target" to the visible name only (NOT the URL).',
        '               Example: target="Issues", NOT target="Issues → /path".',
        '               If multiple links share the same name, set "url" to the pathname (e.g. "/project/-/issues").',
        '  "fill"      — type into an input field; set "target" (placeholder/label of the field), "value" (text to type)',
        '                optionally set "submit": true to press Enter after filling',
        '  "goto"      — navigate to a URL directly; set "url"',
        '  "search"    — type in a search box and submit; set "target" (the query)',
        '  "done"      — NAVIGATE or MUTATE task is complete; the target page or action is confirmed.',
        '               Before declaring done, review the current page state (URL, title, links, buttons,',
        '               filters) and verify it matches the task goal exactly. If there is any mismatch,',
        '               take further action instead of declaring done.',
        "  Failure actions (choose the most specific one):",
        '  "not_found"            — the target element, page, or data does not exist',
        '  "permission_denied"    — the user lacks the required role or permission',
        '  "action_not_allowed"   — the action is explicitly disabled or restricted for this context',
        '  "data_validation_error"— the retrieved data does not match the expected format or constraints',
        '  "unknown_error"        — an unexpected error occurred that does not fit other categories',
        "",
        "Strategy: prefer 'click' if a matching link or button is visible on the page.",
        "Use 'goto' only if no clickable target is found and you are confident of the URL.",
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


def build_plan(*, task: str, observation: Any, llm: LLMClient) -> list[str]:
    """태스크를 2~5개 sub-goal로 분해한다. LLM 1회 호출."""
    system = (
        "You are a web task planner. Break down a web automation task into 2-5 sub-goals.\n"
        "Each sub-goal should be a concrete, verifiable objective — not a specific UI action.\n"
        "Good: 'Apply the bug label filter'  Bad: 'Click the Label dropdown'\n"
        "Consider the current page state when planning.\n"
        "When filters are needed, include a sub-goal to submit/apply the filter after selecting values.\n"
        "If the task asks for a specific field (ID, URL, email, etc.), include a sub-goal to navigate to the page where that field is actually visible.\n"
        'Respond ONLY with JSON: {"sub_goals": ["...", "..."]}\n'
        "Keep each sub-goal to one short sentence."
    )
    lines = [
        f"Task: {task}",
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
        return [str(g) for g in sub_goals]
    return [task]  # 파싱 실패 시 task 전체를 단일 goal로 폴백


def build_action_request(
    *,
    task: str,
    observation: Any,
    last_action_result: str = "",
    sub_goals: list[str] | None = None,
    current_goal_index: int = 0,
) -> str:
    """태스크 지시와 현재 페이지 상태를 user 메시지로 직렬화한다."""
    lines = [f"Task: {task}", ""]

    if sub_goals:
        lines.append("Plan:")
        for i, goal in enumerate(sub_goals):
            if i < current_goal_index:
                marker = "done"
            elif i == current_goal_index:
                marker = "current"
            else:
                marker = " "
            lines.append(f"  [{marker}] {i + 1}. {goal}")
        lines += [
            "",
            "Focus on the [current] sub-goal. Set \"goal_complete\": true when it is achieved.",
            "Only use \"done\" action when ALL sub-goals are complete.",
            "Only use \"extract\" to return the FINAL answer to the task — never for intermediate progress.",
            "",
        ]

    if last_action_result:
        lines += [f"Last action result: {last_action_result}", ""]
    lines += [
        f"Current URL: {observation.url}",
        f"Page title: {observation.title}",
    ]
    if observation.headings:
        lines.append(f"Headings: {observation.headings}")
    if observation.text_lines:
        lines.append(f"Visible text (first 10): {observation.text_lines[:10]}")
    if observation.links:
        lines.append(f"Links (first 20): {observation.links[:20]}")
    if observation.dropdown_options:
        lines.append(f"Dropdown options (click to select): {observation.dropdown_options[:20]}")
    if observation.buttons:
        lines.append(f"Buttons: {observation.buttons[:10]}")
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
