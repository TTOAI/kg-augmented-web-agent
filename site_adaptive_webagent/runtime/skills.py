"""Skill Library — 복합 multi-step tool.

LLM이 단일 tool call로 호출하면, 내부적으로 LLM 1회 호출 + 부수 효과(task_notes 등)를
수행하고 결과를 반환한다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .llm import LLMClient, parse_llm_action
from .types import ExecutionOutcome, PageObservation


@dataclass(slots=True)
class SkillResult:
    """Skill 실행 결과."""
    feedback: str
    outcome: ExecutionOutcome | None = None
    notes_added: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# scan_and_remember
# ---------------------------------------------------------------------------

def scan_and_remember(
    *,
    task: str,
    task_hint: str,
    current_obs: PageObservation,
    task_notes: list[str],
    llm: LLMClient,
) -> SkillResult:
    """현재 페이지에서 task 관련 사실을 모두 찾아 task_notes에 저장한다."""
    system = (
        "You are a data extraction assistant. "
        "Given a web task and the current page content, identify ALL task-relevant facts. "
        "Return ONLY a JSON array of short fact strings. "
        'Example: ["Project ID is 183", "empathy-prompts has 6 stars"]'
    )
    hint_str = f"\nFocus on: {task_hint}" if task_hint else ""
    user_msg = (
        f"Task: {task}{hint_str}\n\n"
        f"URL: {current_obs.url}\n"
        f"Title: {current_obs.title}\n"
        f"Headings: {current_obs.headings[:10]}\n"
        f"Visible text: {current_obs.text_lines[:15]}\n"
        f"Links: {current_obs.links[:20]}\n"
        f"Buttons: {current_obs.buttons[:10]}\n"
    )

    try:
        response = llm.complete(system=system, messages=[{"role": "user", "content": user_msg}])
        facts = _parse_json_array(response)
    except Exception:
        facts = []

    if not facts:
        return SkillResult(feedback="scan_and_remember: no task-relevant facts found on this page.")

    added: list[str] = []
    existing = set(task_notes)
    for fact in facts:
        fact_str = str(fact).strip()
        if fact_str and fact_str not in existing:
            task_notes.append(fact_str)
            existing.add(fact_str)
            added.append(fact_str)

    if not added:
        return SkillResult(feedback=f"scan_and_remember: all {len(facts)} facts already saved.")

    summary = "; ".join(added[:5])
    if len(added) > 5:
        summary += f" ... and {len(added) - 5} more"
    return SkillResult(
        feedback=f"Scanned and saved {len(added)} facts: {summary}",
        notes_added=added,
    )


# ---------------------------------------------------------------------------
# verified_extract
# ---------------------------------------------------------------------------

def verified_extract(
    *,
    task: str,
    task_type: str,
    preliminary_answer: str,
    current_obs: PageObservation,
    task_notes: list[str],
    llm: LLMClient,
) -> SkillResult:
    """저장된 facts와 현재 페이지를 대조하여 검증된 답을 추출한다."""
    notes_str = "\n".join(f"- {n}" for n in task_notes) if task_notes else "(no saved facts)"

    system = (
        "You are a verification assistant. "
        "Cross-check the preliminary answer against ALL saved facts and the current page. "
        "If any saved facts are missing from the answer, ADD them. "
        'Return ONLY JSON: {"value": "complete answer", "label": "what it is"}\n'
        "For multiple values, separate with commas in the value field."
    )
    user_msg = (
        f"Task: {task}\n"
        f"Preliminary answer: {preliminary_answer or '(none)'}\n\n"
        f"Saved facts:\n{notes_str}\n\n"
        f"Current page URL: {current_obs.url}\n"
        f"Page title: {current_obs.title}\n"
        f"Visible text: {current_obs.text_lines[:10]}\n"
        f"Links: {current_obs.links[:10]}\n\n"
        "Cross-check: Does the preliminary answer include ALL relevant facts? "
        "Extract the COMPLETE verified answer."
    )

    try:
        response = llm.complete(system=system, messages=[{"role": "user", "content": user_msg}])
        parsed = parse_llm_action(response)
        value = parsed.get("value", "")
    except Exception:
        value = ""

    # fallback: 파싱 실패 시 preliminary_answer 사용
    if not value and preliminary_answer:
        value = preliminary_answer

    if not value:
        return SkillResult(
            feedback="verified_extract: could not extract an answer.",
            outcome=ExecutionOutcome(task_type=task_type, status="NOT_FOUND_ERROR",
                                     error_details="Verified extract failed — no value"),
        )

    # 쉼표 구분 값 분리
    retrieved = [v.strip() for v in value.split(",") if v.strip()] if "," in value else [value]
    label = parsed.get("label", "") if 'parsed' in dir() else ""

    return SkillResult(
        feedback=f"Verified extract: {value}",
        outcome=ExecutionOutcome(task_type=task_type, status="SUCCESS", retrieved_data=retrieved),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_array(text: str) -> list[str]:
    """텍스트에서 JSON 배열을 파싱한다. 마크다운 펜스를 자동 제거."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [str(item) for item in result]
    except json.JSONDecodeError:
        pass
    return []
