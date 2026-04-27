"""LLM provider-agnostic interface and implementations.

사용법:
    llm = make_llm_client()   # .env의 LLM_PROVIDER로 구현체 선택
    if llm is not None:
        response = llm.complete(system="...", messages=[{"role": "user", "content": "..."}])
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from typing import Any, Callable, Protocol, runtime_checkable

from .tools import LLMToolResponse, ToolCall

logger = logging.getLogger("webarena_verified")


def _retry_transient(fn: Callable, *, max_attempts: int = 3, base_delay: float = 1.0,
                     max_delay: float = 10.0):
    """Exponential backoff retry for transient OpenAI errors.

    RateLimitError / APIConnectionError / APITimeoutError만 retry.
    insufficient_quota 류는 persistent이므로 즉시 propagate (측정 중단 트리거).
    """
    import openai
    TRANSIENT = (openai.APIConnectionError, openai.APITimeoutError)
    for attempt in range(max_attempts):
        try:
            return fn()
        except openai.RateLimitError as e:
            # insufficient_quota는 재시도 불가 — 즉시 raise
            if "insufficient_quota" in str(e) or "quota" in str(e).lower():
                raise
            if attempt == max_attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 0.5)
            logger.warning("[LLM] RateLimitError (attempt %d/%d) — retry in %.1fs",
                           attempt + 1, max_attempts, delay)
            time.sleep(delay)
        except TRANSIENT as e:
            if attempt == max_attempts - 1:
                raise
            delay = min(max_delay, base_delay * (2 ** attempt)) + random.uniform(0, 0.5)
            logger.warning("[LLM] %s (attempt %d/%d) — retry in %.1fs",
                           type(e).__name__, attempt + 1, max_attempts, delay)
            time.sleep(delay)


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
        reasoning_effort: str | None = None,
    ) -> "LLMToolResponse":
        """Tool Use 완성. Thought + tool call을 반환한다.

        reasoning_effort: "low" | "medium" | "high" — reasoning model에만 의미가 있다.
        None이면 provider default 사용. 일반 chat model은 무시.
        """
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
        timeout_s = float(os.getenv("LLM_REQUEST_TIMEOUT", "300"))
        self._client = anthropic.Anthropic(timeout=timeout_s, max_retries=3)
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
        reasoning_effort: str | None = None,
    ) -> LLMToolResponse:
        # reasoning_effort는 Anthropic API 미노출 — silently ignore.
        # Prompt caching: system prompt + tools 카탈로그는 task 내내 정적이므로
        # ephemeral cache_control로 표시. 최소 캐시 토큰 미달 시 SDK가 silently no-op.
        system_blocks = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        cached_tools: list[dict] = list(tools)
        if cached_tools:
            cached_tools[-1] = {**cached_tools[-1], "cache_control": {"type": "ephemeral"}}
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_blocks,
            messages=messages,
            tools=cached_tools,
            **self._extra_kwargs(),
        )
        u = getattr(response, "usage", None)
        if u is not None:
            logger.info(
                "[LLM] tokens in=%d out=%d cache_create=%d cache_read=%d",
                u.input_tokens, u.output_tokens,
                getattr(u, "cache_creation_input_tokens", 0) or 0,
                getattr(u, "cache_read_input_tokens", 0) or 0,
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

    모델 분기:
    - **Agent task 실행**: 기본 `gpt-5.4-mini` (.env OPENAI_MODEL). 모델명이 `gpt-5*`로
      시작해 Responses API로 자동 분기. `reasoning_effort`는 넘기지 않으므로 provider
      default 사용.
    - **KG derivation** (`kg/seed/llm_derivation.py`): `gpt-5.4` (full) + `reasoning_effort=
      "low"` 명시. Multi-call decomposition 안정성 확보용. Baseline agent와는 독립 경로.

    Reasoning model (gpt-5*, o-series) 호출 시 reasoning_effort를 사용하려면 Responses API
    를 써야 한다 (chat.completions에선 function tools와 동시 사용 불가). `_use_responses_api`
    가 True면 complete_with_tools가 `client.responses.create`로 분기.

    LLM_REQUEST_TIMEOUT env로 client-side timeout (초) 설정 가능 (기본 300초).
    """

    def __init__(self, model: str = "gpt-4o", temperature: float | None = None) -> None:
        import openai  # lazy import
        timeout_s = float(os.getenv("LLM_REQUEST_TIMEOUT", "300"))
        # OpenAI client에 timeout 적용 — server-side hang 방지
        self._client = openai.OpenAI(timeout=timeout_s)
        self._model = model
        self._temperature = temperature
        # gpt-5* / o-series는 reasoning model → Responses API 우선
        self._use_responses_api = (
            model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3")
        )

    def _extra_kwargs(self) -> dict[str, Any]:
        return {"temperature": self._temperature} if self._temperature is not None else {}

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        all_messages = [{"role": "system", "content": system}, *messages]
        response = _retry_transient(lambda: self._client.chat.completions.create(
            model=self._model,
            messages=all_messages,  # type: ignore[arg-type]
            max_completion_tokens=1024,
            **self._extra_kwargs(),
        ))
        return response.choices[0].message.content or ""

    def complete_with_tools(
        self, *, system: str, messages: list[dict], tools: list[dict],
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> LLMToolResponse:
        # Responses API는 multi-turn tool_calls 포맷이 chat.completions와 달라 agent의
        # ReAct loop (assistant tool_call → tool_result → assistant ...)를 그대로 못 받음.
        # 따라서 `reasoning_effort`가 명시됐을 때만 Responses API 경로 (주로 derivation
        # single-turn tool call). agent task는 reasoning_effort 없이 호출되므로 chat.completions
        # 경로로 분기되어 multi-turn ReAct가 정상 작동.
        if self._use_responses_api and reasoning_effort is not None:
            return self._complete_via_responses_api(
                system=system, messages=messages, tools=tools,
                max_tokens=max_tokens, reasoning_effort=reasoning_effort,
            )
        # 비-reasoning 모델: chat.completions
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
        response = _retry_transient(lambda: self._client.chat.completions.create(
            model=self._model,
            messages=oai_messages,  # type: ignore[arg-type]
            tools=oai_tools,  # type: ignore[arg-type]
            max_completion_tokens=max_tokens,
            parallel_tool_calls=False,
            **self._extra_kwargs(),
        ))
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

    def _complete_via_responses_api(
        self, *, system: str, messages: list[dict], tools: list[dict],
        max_tokens: int, reasoning_effort: str | None,
    ) -> LLMToolResponse:
        """Responses API (reasoning model + function tools 지원)."""
        # Tool spec: Responses API는 type=function + 평면 schema 사용
        resp_tools = [
            {
                "type": "function",
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t["input_schema"],
            }
            for t in tools
        ]
        # input은 chat-style messages list 그대로 받음
        input_messages: list[dict] = []
        for msg in messages:
            input_messages.extend(_to_openai_messages(msg))
        kwargs: dict[str, Any] = {
            "model": self._model,
            "instructions": system,
            "input": input_messages,
            "tools": resp_tools,
            "max_output_tokens": max_tokens,
            "parallel_tool_calls": False,
        }
        if reasoning_effort is not None:
            kwargs["reasoning"] = {"effort": reasoning_effort}
        # 주의: reasoning model (gpt-5*, o-series)는 temperature 파라미터 미지원.
        # determinism은 reasoning model 자체 특성으로 보장된다 (default temp=1, 단
        # 동일 input + reasoning 결정성으로 안정 cluster 결과).
        response = _retry_transient(lambda: self._client.responses.create(**kwargs))

        thought: str | None = None
        tool_calls: list[ToolCall] = []
        for item in getattr(response, "output", []) or []:
            item_type = getattr(item, "type", None)
            if item_type == "message":
                # message.content → list of content blocks
                for block in getattr(item, "content", []) or []:
                    if getattr(block, "type", None) in ("output_text", "text"):
                        thought = (thought or "") + getattr(block, "text", "")
            elif item_type in ("function_call", "tool_call"):
                name = getattr(item, "name", None) or ""
                args_str = getattr(item, "arguments", "") or "{}"
                call_id = getattr(item, "call_id", None) or getattr(item, "id", "")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    args = {}
                tool_calls.append(ToolCall(id=call_id, name=name, arguments=args))
        return LLMToolResponse(thought=thought, tool_calls=tool_calls, raw_content=[response])


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
        # OpenAI chat.completions는 assistant 메시지에서 content=None을 reject하므로
        # (tool_calls가 없을 때), text가 비어 있으면 빈 문자열로 보낸다.
        text_joined = "\n".join(text_parts)
        if tool_calls_oai:
            result: dict = {"role": "assistant", "content": text_joined or None, "tool_calls": tool_calls_oai}
        else:
            result = {"role": "assistant", "content": text_joined}
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
        "6. Before report_success, use recall to verify completeness.",
        "",
        "## Terminal outcomes",
        "Every objective ends with ONE of two terminal tools:",
        "  - report_success — objective achieved. On intermediate sub-goals provide a",
        "    `reason`. On the FINAL sub-goal of a RETRIEVE task, you MUST provide",
        "    `answer` with the concrete value(s) the task asks for (IDs, names,",
        "    counts, etc.). Never pass a narrative like 'no match found' as `answer`.",
        "  - report_failure — task cannot be completed as stated (target does not",
        "    exist, action not allowed, permission denied, input invalid, etc.). This",
        "    is a VALID task outcome when the answer genuinely cannot be produced.",
        "    You only need a concise `reason` — no status codes.",
        "",
        "## When to use report_failure",
        "Some tasks have an infeasible outcome as the correct answer. Use",
        "report_failure when evidence points to a clear obstacle. The scaffold will",
        "require at least 3 prior attempts before accepting a mid-sub-goal",
        "report_failure — giving up too early wastes step budget.",
        "",
        "Before calling report_failure, verify:",
        "1. You have tried at least 3 meaningfully different strategies — different",
        "   query terms, filter combinations, alternative navigation paths, or",
        "   scrolling through paginated results.",
        "2. The page does NOT already contain evidence of the answer. If evidence",
        "   is visible anywhere, use observe/remember/report_success instead.",
        "3. Absence of a single UI option (e.g., a missing filter entry) is NOT",
        "   sufficient grounds — the answer may still be present elsewhere.",
        "",
        "Typical failure reasons include:",
        "- target entity or resource does not exist after thorough search",
        "- the platform explicitly blocks the requested action in this state",
        "- the current user lacks permission to perform the action",
        "- required input is missing or invalid",
        "- an unexpected obstacle prevents completion",
        "Describe which applies in plain language — the benchmark layer classifies.",
    ]
    return "\n".join(lines)


#  _MUTATE_FORM_CHECKLIST는 config/sites/<site>/prompts.yaml로
# 이관되었음 (mutate_checklist key). `build_observation_message`는 module-level
# `default_prompt_library()`를 사용해 현 site의 checklist 렌더.


def build_observation_message(
    *,
    task: str,
    observation: Any,
    last_action_feedback: str = "",
    sub_goals: list[SubGoal] | None = None,
    current_goal_index: int = 0,
    start_url: str = "",
    kg_hint: str | None = None,
    task_type: str = "",
) -> str:
    """페이지 상태를 마크다운 섹션으로 구조화한다 (Tool Use용).

    kg_hint: 선택적 KG 기반 advisory hint. 있으면 task 섹션 뒤, 관측 앞에 주입.
    Agent는 이 hint를 advisory로 취급할 수 있으며, observation과 충돌하면
    observation을 우선한다.

    task_type: "MUTATE" + 현재 page에 form inputs이 있을 때 form-submission
    checklist를 추가 주입. Agent가 intent의 non-primary qualifier
    (empty/private/guest 등)를 form의 non-default 필드와 연결하지 못해
    default 값으로 submit하는 구조적 결함을 방지한다.
    """
    from urllib.parse import urlparse, parse_qs

    sections: list[str] = []

    task_section = f"## Task\n{task}"
    if start_url:
        task_section += f"\n**Started from:** {start_url}"
    sections.append(task_section)

    if kg_hint:
        sections.append(kg_hint)

    if task_type == "MUTATE" and getattr(observation, "inputs", None):
        #  site별 checklist는 prompts.yaml에서 로드
        from .prompts import default_prompt_library

        checklist = default_prompt_library().render_mutate_checklist()
        if checklist:
            sections.append(checklist)
    # NOTE: NAVIGATE filter checklist 추가 시도 ( P3.1) — 역효과 확인.
    # Agent가 "search 회피" 해석을 우선해 label dropdown 탐색 중 deadlock.
    # 근본 해결엔 observation layer 개선 (collapsed dropdown 항목 노출) 또는
    # KG의 filter URL 템플릿 제공이 필요. Prompt-level 단독 guidance로는 regression.

    if sub_goals and current_goal_index < len(sub_goals):
        current_goal = sub_goals[current_goal_index].goal
        is_last = current_goal_index == len(sub_goals) - 1
        sections.append(
            f"## Current Objective ({current_goal_index + 1}/{len(sub_goals)})\n{current_goal}\n"
            "When achieved, call report_success. If the task has a definitive "
            "error outcome, call report_failure."
        )
        # Tool-availability 안내는 두 context(last/non-last) 모두에 제공해 일관성 유지.
        if is_last and task_type == "RETRIEVE":
            sections.append(
                "This is the FINAL sub-goal of a RETRIEVE task. Available tools: "
                "click, fill, search, goback, goto, observe, remember, recall, "
                "report_success, report_failure. "
                "When you call report_success here you MUST include the 'answer' "
                "field with the concrete value(s). If the target genuinely does "
                "not exist, call report_failure with a brief reason — do NOT pass "
                "'no match found' or similar narrative as answer."
            )
        elif is_last:
            sections.append(
                "This is the final sub-goal. Available tools: click, fill, search, "
                "goback, goto, observe, remember, recall, report_success, report_failure. "
                "report_failure is a valid final outcome when evidence points to a "
                "definitive error state."
            )
        else:
            sections.append(
                "Available tools for this sub-goal: click, fill, search, goback, "
                "goto, observe, remember, recall, report_success, report_failure. "
                "report_failure is permitted when evidence for a definitive error "
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
    latent = getattr(observation, "latent_nav", None) or []
    if latent:
        shown = latent[:20]
        elements.append(
            "**Latent navigation (DOM-rendered but currently hidden — "
            "click the parent toggle/menu to reach):**\n"
            + "\n".join(f"- {item}" for item in shown)
        )
    if elements:
        sections.append("## Interactive Elements\n" + "\n\n".join(elements))

    return "\n\n".join(sections)
