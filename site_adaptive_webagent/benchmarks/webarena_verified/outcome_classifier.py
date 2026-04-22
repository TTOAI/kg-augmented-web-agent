"""Benchmark-side outcome classifier: agent verdict → WebArena-Verified status.

Phase 3.I 구조:
  Agent runtime이 benchmark-agnostic `AgentVerdict` + raw payload (answer / reason)를
  배출하고, 여기서 WebArena-Verified의 status enum + retrieved_data로 **매핑**한다.
  이 모듈이 agent_response.json의 status/retrieved_data를 결정하는 **유일한** source
  of truth.

매핑 전략 (hard-rule → LLM fallback):

1. verdict=done_with_answer:
   - RETRIEVE: LLM 호출 — answer가 valid한 값인지 (IDs/counts/etc.) vs "none" / "no
     match" 같은 not-found placeholder인지 판단. placeholder면 NOT_FOUND_ERROR로 전환.
     valid이면 SUCCESS + retrieved_data=[answer].
   - NAVIGATE/MUTATE: 대부분 answer 없이 done_no_answer 경로. 만약 answer가 실려 있으면
     무시하고 SUCCESS.
2. verdict=done_no_answer:
   - 바로 SUCCESS (retrieved_data=null). Network-level 검증은 benchmark evaluator 쪽.
3. verdict=abandoned:
   - LLM 호출 — reason의 의미론을 분석해 NOT_FOUND_ERROR / ACTION_NOT_ALLOWED_ERROR /
     PERMISSION_DENIED_ERROR / DATA_VALIDATION_ERROR / UNKNOWN_ERROR 중 선택.
4. verdict=stuck:
   - 바로 UNKNOWN_ERROR (scaffold 자체 실패는 semantic 분류 의미 없음).
5. LLM이 없거나 실패 시:
   - done_with_answer → SUCCESS + retrieved_data=[answer]
   - abandoned → UNKNOWN_ERROR + error_details=reason
   - 나머지는 hard-rule로 충분.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from site_adaptive_webagent.agent.types import AgentRunResult
from site_adaptive_webagent.runtime.llm import LLMClient

from .types import WebArenaRunResult, WebArenaStatus

logger = logging.getLogger("webarena_verified")

_VALID_STATUSES: frozenset[str] = frozenset({
    "SUCCESS",
    "NOT_FOUND_ERROR",
    "ACTION_NOT_ALLOWED_ERROR",
    "PERMISSION_DENIED_ERROR",
    "DATA_VALIDATION_ERROR",
    "UNKNOWN_ERROR",
})

_ERROR_STATUSES: frozenset[str] = _VALID_STATUSES - {"SUCCESS"}


def _split_comma(value: str) -> list[str]:
    """쉼표로 분리된 멀티-값을 list[str]로 변환. 단일 값이면 [value]."""
    if "," in value:
        return [v.strip() for v in value.split(",") if v.strip()]
    return [value]


def _parse_json_response(raw: str) -> Optional[dict]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _classify_retrieve_answer_with_llm(
    *, task: str, answer: str, answer_label: Optional[str], llm: LLMClient,
) -> tuple[WebArenaStatus, list[str] | None, Optional[str]]:
    """done_with_answer + RETRIEVE의 semantic 분류.

    LLM이 answer를 보고 valid인지 placeholder(no-match)인지 판단.
    Fallback: LLM 실패/파싱 실패 시 SUCCESS (agent의 draft 신뢰).
    """
    prompt = (
        "You are the WebArena-Verified outcome classifier.\n"
        "A RETRIEVE task agent has submitted a draft answer. Decide whether this\n"
        "is a valid concrete answer or a placeholder for 'not found'.\n"
        "\n"
        f"Task intent: {task}\n"
        f"Draft answer: {answer!r}\n"
        f"Answer label: {answer_label!r}\n"
        "\n"
        "Rules:\n"
        "- If answer is a concrete value matching what the task asks for (ID, count,\n"
        "  name, email, URL, etc.), emit SUCCESS and keep the answer.\n"
        "- If answer is a placeholder indicating 'not found' ('none', 'no match',\n"
        "  'no matching X', 'not found', '-', 'n/a', empty), emit NOT_FOUND_ERROR\n"
        "  with retrieved_data=null. This is the primary correction.\n"
        "- If unsure, default to SUCCESS (preserve the agent's draft).\n"
        "\n"
        "Respond with a single JSON object: "
        '{"status": "SUCCESS" | "NOT_FOUND_ERROR", '
        '"retrieved_data": [...] | null, '
        '"error_details": string | null, '
        '"reason": string}'
    )
    try:
        raw = llm.complete(
            system="You are a precise JSON-only classifier. Output valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        logger.warning("[classify_outcome] LLM call (retrieve-answer) failed: %s", exc)
        return "SUCCESS", _split_comma(answer), None
    parsed = _parse_json_response(raw)
    if parsed is None:
        logger.warning("[classify_outcome] non-JSON response (retrieve-answer): %r", raw[:200])
        return "SUCCESS", _split_comma(answer), None
    status_raw = str(parsed.get("status", "")).strip()
    if status_raw not in ("SUCCESS", "NOT_FOUND_ERROR"):
        logger.warning("[classify_outcome] invalid retrieve-answer status=%r", status_raw)
        return "SUCCESS", _split_comma(answer), None
    status: WebArenaStatus = status_raw  # type: ignore[assignment]
    retrieved = parsed.get("retrieved_data")
    if retrieved is not None and not isinstance(retrieved, list):
        retrieved = [retrieved] if isinstance(retrieved, (str, int, float, bool)) else None
    if status == "SUCCESS" and not retrieved:
        retrieved = _split_comma(answer)
    error_details = parsed.get("error_details")
    if error_details is not None:
        error_details = str(error_details)[:200]
    return status, retrieved, error_details


def _classify_abandoned_with_llm(
    *, task: str, reason: str, llm: LLMClient,
) -> tuple[WebArenaStatus, Optional[str]]:
    """abandoned verdict의 reason을 WebArena error status로 분류.

    Fallback: LLM 실패/파싱 실패 시 UNKNOWN_ERROR.
    """
    prompt = (
        "You are the WebArena-Verified outcome classifier.\n"
        "The agent declared the task infeasible. Classify the failure mode into\n"
        "one of WebArena-Verified's error statuses.\n"
        "\n"
        f"Task intent: {task}\n"
        f"Agent's reason: {reason!r}\n"
        "\n"
        "Statuses:\n"
        "- NOT_FOUND_ERROR: target entity/resource does not exist.\n"
        "- ACTION_NOT_ALLOWED_ERROR: the platform explicitly blocks the requested action in this state.\n"
        "- PERMISSION_DENIED_ERROR: current user lacks permission.\n"
        "- DATA_VALIDATION_ERROR: required input is missing or invalid.\n"
        "- UNKNOWN_ERROR: unexpected failure not fitting the other categories.\n"
        "\n"
        "Respond with a single JSON object: "
        '{"status": one of the above, "error_details": short string, "reason": string}'
    )
    try:
        raw = llm.complete(
            system="You are a precise JSON-only classifier. Output valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        logger.warning("[classify_outcome] LLM call (abandoned) failed: %s", exc)
        return "UNKNOWN_ERROR", reason[:200] if reason else None
    parsed = _parse_json_response(raw)
    if parsed is None:
        logger.warning("[classify_outcome] non-JSON response (abandoned): %r", raw[:200])
        return "UNKNOWN_ERROR", reason[:200] if reason else None
    status_raw = str(parsed.get("status", "")).strip()
    if status_raw not in _ERROR_STATUSES:
        logger.warning("[classify_outcome] invalid abandoned status=%r", status_raw)
        return "UNKNOWN_ERROR", reason[:200] if reason else None
    status: WebArenaStatus = status_raw  # type: ignore[assignment]
    error_details = parsed.get("error_details")
    if error_details is not None:
        error_details = str(error_details)[:200]
    elif reason:
        error_details = reason[:200]
    return status, error_details


def classify_outcome(
    *,
    task: str,
    agent_result: AgentRunResult,
    llm: Optional[LLMClient] = None,
) -> WebArenaRunResult:
    """Agent의 neutral verdict를 WebArena-Verified `WebArenaRunResult`로 매핑한다.

    LLM=None일 때도 hard-rule로 완결된 결과를 내도록 설계되어 있어, offline/test
    환경에서 안전하게 동작한다.
    """
    task_type = agent_result.task_type
    verdict = agent_result.verdict

    if verdict == "done_no_answer":
        return WebArenaRunResult(
            task_type=task_type, status="SUCCESS",
            retrieved_data=None, error_details=None,
        )

    if verdict == "stuck":
        return WebArenaRunResult(
            task_type=task_type, status="UNKNOWN_ERROR",
            retrieved_data=None,
            error_details=(agent_result.reason or "agent stuck")[:200],
        )

    if verdict == "done_with_answer":
        answer = (agent_result.answer or "").strip()
        if not answer:
            return WebArenaRunResult(
                task_type=task_type, status="UNKNOWN_ERROR",
                retrieved_data=None,
                error_details="done_with_answer but answer is empty",
            )
        # NAVIGATE/MUTATE에서 예외적으로 answer를 제출한 경우도 SUCCESS (retrieved_data는 무시).
        if task_type != "RETRIEVE":
            return WebArenaRunResult(
                task_type=task_type, status="SUCCESS",
                retrieved_data=None, error_details=None,
            )
        if llm is None:
            return WebArenaRunResult(
                task_type=task_type, status="SUCCESS",
                retrieved_data=_split_comma(answer), error_details=None,
            )
        status, retrieved, err = _classify_retrieve_answer_with_llm(
            task=task, answer=answer, answer_label=agent_result.answer_label, llm=llm,
        )
        return WebArenaRunResult(
            task_type=task_type, status=status,
            retrieved_data=retrieved, error_details=err,
        )

    if verdict == "abandoned":
        reason = agent_result.reason or ""
        if llm is None:
            return WebArenaRunResult(
                task_type=task_type, status="UNKNOWN_ERROR",
                retrieved_data=None,
                error_details=reason[:200] if reason else "task abandoned",
            )
        status, err = _classify_abandoned_with_llm(task=task, reason=reason, llm=llm)
        return WebArenaRunResult(
            task_type=task_type, status=status,
            retrieved_data=None, error_details=err,
        )

    # sub_goal_failed 등 예상 외 verdict — 방어적으로 UNKNOWN_ERROR.
    logger.warning("[classify_outcome] unexpected verdict=%r — UNKNOWN_ERROR", verdict)
    return WebArenaRunResult(
        task_type=task_type, status="UNKNOWN_ERROR",
        retrieved_data=None,
        error_details=f"unexpected agent verdict: {verdict}",
    )
