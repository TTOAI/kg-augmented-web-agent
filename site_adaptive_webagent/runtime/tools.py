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

# Generic optional memo field — accumulated into task_notes and reviewed before done
_MEMO_FIELD = {
    "type": "string",
    "description": (
        "Optional: a one-phrase note of what you observed or concluded in this step. "
        "Use it when the task requires gathering multiple pieces of information across "
        "pages — notes are accumulated and reviewed before done."
    ),
}


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
                "memo": _MEMO_FIELD,
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
                "memo": _MEMO_FIELD,
            },
            "required": ["target", "value"],
        },
    }


def _search_tool() -> dict:
    return {
        "name": "search",
        "description": (
            "Use the page's search or filter input. "
            "Clicks the input first to reveal dropdown options, "
            "then selects a matching option or types the query, "
            "then submits with Enter. Handles AJAX loading automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search or filter for",
                },
                "memo": _MEMO_FIELD,
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
            "properties": {
                "memo": _MEMO_FIELD,
            },
        },
    }


def _goto_tool() -> dict:
    return {
        "name": "goto",
        "description": (
            "Directly navigate to a URL. Prefer over clicking when you have a "
            "specific URL target — e.g. a filter template from KG hints "
            "(`/{ns}/{proj}/-/issues?state=opened&label_name[]=bug`) or a known "
            "page path. Relative paths are resolved against the current origin."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "Target URL or path. Accepts absolute (https://...) or "
                        "site-relative (/{ns}/{proj}/-/issues?...) form. "
                        "Placeholders like {namespace} must already be filled in."
                    ),
                },
                "memo": _MEMO_FIELD,
            },
            "required": ["url"],
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
                "memo": _MEMO_FIELD,
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
                    "description": "The fact to save",
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
                    "description": "Evidence why this objective is complete (e.g. 'URL changed to the target page' or 'the expected content is visible')",
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


def _declare_error_tool() -> dict:
    """WebArena-Verified status enum에 맞춘 task-level error 선언 tool.

    LLM이 충분한 근거로 "이 task는 에러 상태가 정답"이라 판단할 때 사용.
    예: 검색 대상이 존재하지 않음 → NOT_FOUND_ERROR.
    sub-goal 수준 실패가 아니라 task-level outcome으로 즉시 종료된다.
    """
    return {
        "name": "declare_error",
        "description": (
            "Declare that this task has a definitive non-success outcome. "
            "Use when you have sufficient evidence that the target entity does not exist, "
            "the action is not permitted by the platform, the user lacks permission, "
            "the required input is invalid, or an unexpected failure occurred. "
            "A correct error declaration is a valid task outcome for some tasks — "
            "do NOT keep searching indefinitely when evidence points to a clear error state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [
                        "NOT_FOUND_ERROR",
                        "ACTION_NOT_ALLOWED_ERROR",
                        "PERMISSION_DENIED_ERROR",
                        "DATA_VALIDATION_ERROR",
                        "UNKNOWN_ERROR",
                    ],
                    "description": (
                        "NOT_FOUND_ERROR: target entity or resource does not exist. "
                        "ACTION_NOT_ALLOWED_ERROR: platform does not support the requested action in this state. "
                        "PERMISSION_DENIED_ERROR: current user lacks required permission. "
                        "DATA_VALIDATION_ERROR: required input is missing or invalid. "
                        "UNKNOWN_ERROR: unexpected failure that doesn't fit other categories."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "Concise explanation of the evidence for this error (< 200 chars).",
                },
            },
            "required": ["status", "reason"],
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
                                "enum": ["navigation", "action"],
                                "description": "navigation=reach target page/URL, action=change state or read/extract",
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

    중간 goal: browser + cognition + done + declare_error
    마지막 goal (RETRIEVE): + extract + declare_error
    마지막 goal (NAVIGATE/MUTATE): + declare_error

    declare_error는 모든 sub-goal에서 사용 가능 — task-level error가 정답인 경우
    중간 sub-goal에서도 즉시 선언해 소모적 탐색을 방지한다.
    """
    tools = [
        _click_tool(), _fill_tool(), _search_tool(), _goback_tool(),
        _goto_tool(),
        _observe_tool(), _remember_tool(), _recall_tool(), _done_tool(),
        _declare_error_tool(),
    ]
    if is_last_goal and task_type == "RETRIEVE":
        tools.append(_extract_tool())
    return tools


# ---------------------------------------------------------------------------
# Message format helpers
# ---------------------------------------------------------------------------

def format_assistant_tool_use(response: LLMToolResponse) -> dict:
    """LLMToolResponse를 대화 히스토리용 assistant 메시지로 포맷한다.

    LLM이 한 턴에 여러 tool_use를 반환하더라도(시스템 프롬프트는 단일 호출을 요구하지만
    모델이 가끔 어기는 경우) 첫 번째만 포함한다. Anthropic API는 각 tool_use id마다 매칭
    되는 tool_result를 요구하므로, 1개 tool_use + 1개 tool_result로 엄격히 1:1을 유지해
    orphaned tool_use로 인한 후속 API 실패를 차단한다.
    """
    content: list[dict[str, Any]] = []
    if response.thought:
        content.append({"type": "text", "text": response.thought})
    if response.tool_calls:
        tc = response.tool_calls[0]
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
