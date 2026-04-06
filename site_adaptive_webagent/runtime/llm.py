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
        '{"reasoning": "...", "action": "extract|click|goto|search|not_found",',
        ' "value": "...", "label": "...", "target": "...", "url": "..."}',
        "",
        "Action descriptions:",
        '  "extract"   — the requested data is already visible; set "value" (the data) and "label" (what it represents)',
        '  "click"     — click a link or button; set "target" (visible text to match)',
        '  "fill"      — type into an input field; set "target" (placeholder/label of the field), "value" (text to type)',
        '                optionally set "submit": true to press Enter after filling',
        '  "goto"      — navigate to a URL directly; set "url"',
        '  "search"    — type in a search box and submit; set "target" (the query)',
        '  "not_found" — the task cannot be completed from the current page state',
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


def build_action_request(*, task: str, observation: Any) -> str:
    """태스크 지시와 현재 페이지 상태를 user 메시지로 직렬화한다."""
    lines = [
        f"Task: {task}",
        "",
        f"Current URL: {observation.url}",
        f"Page title: {observation.title}",
    ]
    if observation.headings:
        lines.append(f"Headings: {observation.headings}")
    if observation.text_lines:
        lines.append(f"Visible text (first 10): {observation.text_lines[:10]}")
    if observation.links:
        lines.append(f"Links (first 20): {observation.links[:20]}")
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
