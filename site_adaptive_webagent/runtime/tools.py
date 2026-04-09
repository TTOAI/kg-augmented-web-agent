"""Tool Use 정의와 응답 타입.

LLM Tool Use API를 위한 tool 정의 카탈로그, 응답 래퍼,
메시지 포맷 헬퍼를 제공한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Response types (provider-agnostic)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ToolCall:
    """LLM이 반환한 단일 tool 호출."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class LLMToolResponse:
    """Provider-agnostic tool use 응답 래퍼."""
    thought: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_content: list[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic format)
# ---------------------------------------------------------------------------

def _click_tool() -> dict:
    return {
        "name": "click",
        "description": (
            "Click a visible element on the page. "
            "Set target to the element's displayed text (not a CSS selector or path)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Visible label text of the element to click",
                },
                "url": {
                    "type": "string",
                    "description": "URL pathname to disambiguate when multiple elements share the same name",
                },
                "element_type": {
                    "type": "string",
                    "enum": ["button", "link"],
                    "description": "Narrow matching to button or link when both exist",
                },
            },
            "required": ["target"],
        },
    }


def _fill_tool() -> dict:
    return {
        "name": "fill",
        "description": (
            "Type text into an input field. "
            "Click to reveal options BEFORE typing when possible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Input field name or label",
                },
                "value": {
                    "type": "string",
                    "description": "Text to type into the field",
                },
                "submit": {
                    "type": "boolean",
                    "description": "Press Enter after typing (default false)",
                },
            },
            "required": ["target", "value"],
        },
    }


def _search_tool() -> dict:
    return {
        "name": "search",
        "description": "Execute a search query using the page's search field.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query text",
                },
            },
            "required": ["query"],
        },
    }


def _goback_tool() -> dict:
    return {
        "name": "goback",
        "description": "Navigate back to the previous page in browser history.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    }


def _observe_tool() -> dict:
    return {
        "name": "observe",
        "description": (
            "Get a filtered view of page elements matching a keyword. "
            "Use when the standard observation truncates long lists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Case-insensitive filter keyword",
                },
            },
            "required": ["keyword"],
        },
    }


def _remember_tool() -> dict:
    return {
        "name": "remember",
        "description": (
            "Save an important fact for later use across sub-goals. "
            "Use when you discover IDs, counts, names, or other data "
            "that you will need in a later step."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {
                    "type": "string",
                    "description": "The fact to save (e.g. 'Project ID is 183')",
                },
            },
            "required": ["fact"],
        },
    }


def _recall_tool() -> dict:
    return {
        "name": "recall",
        "description": (
            "Retrieve all previously saved facts. "
            "Use before extract or done to verify completeness."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    }


def _done_tool() -> dict:
    return {
        "name": "done",
        "description": "Declare the current objective complete. You must provide evidence from the current page state.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Evidence why this objective is complete (e.g. 'URL contains label_name=bug and state=opened')",
                },
            },
            "required": ["reason"],
        },
    }


def _extract_tool() -> dict:
    return {
        "name": "extract",
        "description": (
            "Extract the final answer for a RETRIEVE task. "
            "Recall your saved facts first and cross-check completeness."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string",
                    "description": "The extracted answer. For multiple values, separate with commas.",
                },
                "label": {
                    "type": "string",
                    "description": "What this value represents (e.g. 'project_id')",
                },
            },
            "required": ["value"],
        },
    }


def _not_found_tool() -> dict:
    return {
        "name": "not_found",
        "description": "The requested information or element was not found on the site.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why it was not found"},
            },
            "required": ["reason"],
        },
    }


def _permission_denied_tool() -> dict:
    return {
        "name": "permission_denied",
        "description": "Access to the requested resource is denied.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Details about the permission denial"},
            },
            "required": ["reason"],
        },
    }


def _action_not_allowed_tool() -> dict:
    return {
        "name": "action_not_allowed",
        "description": "The requested action is not permitted on this site.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why the action is not allowed"},
            },
            "required": ["reason"],
        },
    }


def _unknown_error_tool() -> dict:
    return {
        "name": "unknown_error",
        "description": "An unexpected error prevents completing the task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Error description"},
            },
            "required": ["reason"],
        },
    }


# ---------------------------------------------------------------------------
# Tool set composition
# ---------------------------------------------------------------------------

def replan_tool() -> dict:
    """replan용 tool 정의. LLM이 새로운 sub-goal 목록을 반환한다."""
    return {
        "name": "replan",
        "description": (
            "Create a new list of sub-goals to complete the remaining task. "
            "Each sub-goal should be a concrete, verifiable objective."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sub_goals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "goal": {"type": "string", "description": "Short sentence describing the objective"},
                            "type": {
                                "type": "string",
                                "enum": ["navigation", "action", "cognition"],
                                "description": "navigation=move to page, action=change state, cognition=read/analyze",
                            },
                        },
                        "required": ["goal", "type"],
                    },
                    "description": "2-5 sub-goals to complete the remaining task",
                },
            },
            "required": ["sub_goals"],
        },
    }


def tools_for_goal(*, is_last_goal: bool, task_type: str) -> list[dict]:
    """sub-goal 위치와 task_type에 따라 제공할 tool 목록을 구성한다.

    중간 goal: browser + cognition + done
    마지막 goal (RETRIEVE): + extract + failure tools
    마지막 goal (NAVIGATE/MUTATE): + failure tools
    """
    tools = [
        _click_tool(), _fill_tool(), _search_tool(), _goback_tool(),
        _observe_tool(), _remember_tool(), _recall_tool(), _done_tool(),
    ]
    if is_last_goal:
        if task_type == "RETRIEVE":
            tools.append(_extract_tool())
        tools += [
            _not_found_tool(), _permission_denied_tool(),
            _action_not_allowed_tool(), _unknown_error_tool(),
        ]
    return tools


# ---------------------------------------------------------------------------
# Message format helpers
# ---------------------------------------------------------------------------

def format_assistant_tool_use(response: LLMToolResponse) -> dict:
    """LLMToolResponse를 대화 히스토리용 assistant 메시지로 포맷한다."""
    content: list[dict[str, Any]] = []
    if response.thought:
        content.append({"type": "text", "text": response.thought})
    for tc in response.tool_calls:
        content.append({
            "type": "tool_use",
            "id": tc.id,
            "name": tc.name,
            "input": tc.arguments,
        })
    return {"role": "assistant", "content": content}


def format_tool_result(tool_call_id: str, result_text: str) -> dict:
    """tool 실행 결과를 대화 히스토리용 user 메시지로 포맷한다."""
    return {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tool_call_id, "content": result_text}],
    }
