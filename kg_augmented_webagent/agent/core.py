from __future__ import annotations

import logging
from typing import Any

from dotenv import load_dotenv

from .types import AgentRunResult
from kg_augmented_webagent.kg.runtime.integration import build_kg_session
from kg_augmented_webagent.runtime.browser import observe_page
from kg_augmented_webagent.runtime.executor import execute_with_llm
from kg_augmented_webagent.runtime.intent import analyze_intent
from kg_augmented_webagent.runtime.llm import make_llm_client

load_dotenv()

logger = logging.getLogger("agent_runtime")

__all__ = ["run_agent", "analyze_intent"]


async def run_agent(
    *,
    intent: str,
    sites: list[str],
    start_urls: list[str],
    task_id: int,
    context: Any,
    pages: list[Any],
    task_output_dir: Path,
) -> AgentRunResult:
    """웹 에이전트 런타임의 메인 엔트리포인트. 주어진 task를 실행하고 결과를 반환한다."""
    del context, task_id, task_output_dir, sites, start_urls

    if not pages:
        return AgentRunResult.stuck("No pages opened for this task")

    llm = make_llm_client()
    plan = analyze_intent(intent, llm=llm)
    primary_page = pages[0]
    observation = await observe_page(primary_page)

    if llm is None:
        return AgentRunResult.stuck("LLM client unavailable — set ANTHROPIC_API_KEY or OPENAI_API_KEY")

    import os
    try:
        max_steps = int(os.getenv("MAX_STEPS_PER_TASK", "50"))
    except ValueError:
        max_steps = 50

    # KG session 로드 (실패 시 None → baseline 동작)
    # env `KG_ENABLED=0`으로 완전 비활성화 가능
    # `SITE_NAME`은 cross-site 실행 시 필수
    kg_session = None
    if os.getenv("KG_ENABLED", "1") != "0":
        kg_session = build_kg_session(
            site_name=os.getenv("SITE_NAME", "gitlab"),
            cascade_enabled=(os.getenv("KG_CASCADE", "1") != "0"),
            replan_per_step=(os.getenv("KG_REPLAN", "1") != "0"),
            expose_actions=(os.getenv("KG_EXPOSE_ACTIONS", "1") != "0"),
        )

    outcome = await execute_with_llm(
        task=intent,
        task_type=plan.task_type,
        page=primary_page,
        observation=observation,
        llm=llm,
        max_steps=max_steps,
        kg_session=kg_session,
    )

    return AgentRunResult(
        task_type=outcome.task_type,
        verdict=outcome.verdict,
        answer=outcome.answer,
        answer_label=outcome.answer_label,
        reason=outcome.reason,
    )
