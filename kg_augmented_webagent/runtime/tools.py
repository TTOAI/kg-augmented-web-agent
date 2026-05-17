"""Tool Use 정의와 응답 타입.

LLM Tool Use API를 위한 tool 정의 카탈로그, 응답 래퍼,
메시지 포맷 헬퍼를 제공한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    #  description을 site prompts.yaml에서 로드. Library에 없으면
    # site-agnostic minimal description으로 fallback.
    from .prompts import default_prompt_library

    desc, url_desc = default_prompt_library().goto_tool_description()
    if not desc:
        desc = (
            "Directly navigate to a URL. Prefer over clicking when you already "
            "have a specific URL target. Relative paths are resolved against "
            "the current page's origin."
        )
    if not url_desc:
        url_desc = (
            "Target URL. Accepts absolute or site-relative form. "
            "Placeholders (e.g. {namespace}) must be filled in before calling."
        )
    return {
        "name": "goto",
        "description": desc,
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": url_desc,
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


def _report_success_tool(*, is_last_goal: bool, task_type: str) -> dict:
    """Terminal tool for a successful outcome (sub-goal or task).

    Hierarchical tool design: the agent's first decision is success vs failure.
    All SUCCESS paths (sub-goal transition, NAVIGATE/MUTATE task completion,
    RETRIEVE answer submission) converge here; category-specific fields gate
    on position (is_last_goal) and task_type.
    """
    need_answer = is_last_goal and task_type == "RETRIEVE"
    props: dict[str, Any] = {
        "reason": {
            "type": "string",
            "description": (
                "Evidence why this objective succeeded "
                "(e.g. 'URL changed to the target page', "
                "'the expected content is visible', "
                "'the form was submitted and the confirmation page loaded')."
            ),
        },
    }
    if need_answer:
        props["answer"] = {
            "type": "string",
            "description": (
                "REQUIRED on the final sub-goal of a RETRIEVE task: "
                "the concrete answer value(s) the task asks for (IDs, names, "
                "counts, emails, URLs, etc.). For multiple values, separate "
                "with commas. The value must be the actual data — NOT a "
                "narrative like 'no match found' or 'none'. If the target "
                "genuinely does not exist, call report_failure instead."
            ),
        }
        props["answer_label"] = {
            "type": "string",
            "description": "What 'answer' represents (e.g. 'project_id', 'commit_count').",
        }
    required = ["reason", "answer"] if need_answer else ["reason"]
    description_lines = [
        "Declare that the current objective has been successfully achieved.",
        "",
        "Use this tool when:",
        "  - an intermediate sub-goal is complete (e.g. reached the target page), OR",
        "  - a NAVIGATE/MUTATE task's final sub-goal is complete, OR",
        "  - a RETRIEVE task's final sub-goal is complete AND you have a concrete answer.",
        "",
        "Do NOT use this tool when the target answer/entity does not exist — "
        "that is a FAILURE outcome; use report_failure with a short reason instead.",
    ]
    if need_answer:
        description_lines.append(
            "\nThis is the FINAL sub-goal of a RETRIEVE task — you MUST include the "
            "'answer' field with the concrete value. Recall your saved facts first."
        )
    return {
        "name": "report_success",
        "description": "\n".join(description_lines),
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": required,
        },
    }


def _report_failure_tool() -> dict:
    """Terminal tool for a non-success task outcome.

    Benchmark-specific status enum은 들고 있지 않는다. Agent는 "task를
    완수할 수 없다"는 판단만 보고하고, 그것을 NOT_FOUND_ERROR / PERMISSION_DENIED /
    UNKNOWN_ERROR 등 benchmark-specific status로 분류하는 것은 benchmark adapter의
    `outcome_classifier` 몫. 이 분리로 agent runtime이 특정 벤치마크에 결합되지
    않음 (다른 벤치마크 이식 시 classifier만 추가하면 됨).
    """
    return {
        "name": "report_failure",
        "description": (
            "Declare that the task cannot be completed as stated — the target "
            "entity does not exist, the requested action is not available, the "
            "current user lacks permission, the input is invalid, or some other "
            "definitive obstacle prevents success. "
            "A correct failure declaration is a VALID task outcome — do NOT "
            "keep searching or invent a placeholder answer when evidence points "
            "to a clear impossibility. This tool is always available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": (
                        "Concise explanation of the evidence for this outcome "
                        "(< 200 chars). Describe what you observed that makes "
                        "the task infeasible — the benchmark adapter will use "
                        "this to classify the specific failure mode."
                    ),
                },
            },
            "required": ["reason"],
        },
    }


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

    모든 sub-goal에 공통으로 browser + cognition + report_success + report_failure를
    제공한다. report_success의 schema는 position/task_type에 따라 달라진다:
      - 마지막 sub-goal + RETRIEVE: answer 필수 (concrete 정답값)
      - 그 외: reason만 필수

    report_failure는 모든 sub-goal에서 사용 가능 — task-level error가 정답인 경우
    중간 sub-goal에서도 즉시 선언해 소모적 탐색을 방지한다.
    """
    return [
        _click_tool(), _fill_tool(), _search_tool(), _goback_tool(),
        _goto_tool(),
        _observe_tool(), _remember_tool(), _recall_tool(),
        _report_success_tool(is_last_goal=is_last_goal, task_type=task_type),
        _report_failure_tool(),
    ]


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
