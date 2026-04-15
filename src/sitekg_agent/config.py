"""LLM provider-agnostic 인터페이스와 구현.

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

from .runtime.tools import LLMToolResponse, ToolCall


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMClient(Protocol):
    """LLM provider-agnostic 인터페이스."""

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str: ...

    def complete_with_tools(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict],
    ) -> "LLMToolResponse": ...


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


class AnthropicLLMClient:
    """Claude API를 사용하는 LLMClient 구현."""

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        import anthropic

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
        import openai

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
        oai_messages = [{"role": "system", "content": system}]
        for msg in messages:
            oai_messages.extend(_to_openai_messages(msg))
        response = self._client.chat.completions.create(
            model=self._model,
            messages=oai_messages,  # type: ignore[arg-type]
            tools=oai_tools,  # type: ignore[arg-type]
            max_completion_tokens=1024,
        )
        choice = response.choices[0]
        thought = choice.message.content
        tool_calls: list[ToolCall] = []
        for tc in (choice.message.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}
            assistant_block = {
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": args,
            }
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))
            _ = assistant_block
        raw_content: list[Any] = []
        if thought:
            raw_content.append({"type": "text", "text": thought})
        for tc in tool_calls:
            raw_content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
        return LLMToolResponse(thought=thought, tool_calls=tool_calls, raw_content=raw_content)


def _to_openai_messages(msg: dict) -> list[dict]:
    """Anthropic content-block 메시지를 OpenAI 형식 메시지 리스트로 변환한다."""
    role = msg.get("role", "user")
    content = msg.get("content")

    if isinstance(content, str):
        return [{"role": role, "content": content}]

    if not isinstance(content, list):
        return [{"role": role, "content": str(content)}]

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

    API 키가 없으면 None을 반환한다.
    """
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            return None
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        return OpenAILLMClient(model=model)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    return AnthropicLLMClient(model=model)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def parse_llm_action(response_text: str) -> dict[str, Any]:
    """LLM 응답 텍스트에서 JSON action을 파싱한다.

    ```json ... ``` 마크다운 펜스를 자동으로 제거한다.
    파싱 실패 시 {"action": "not_found"} 폴백을 반환한다.
    """
    text = response_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"action": "not_found", "reasoning": f"LLM 응답 파싱 실패: {text[:100]}"}
