from __future__ import annotations

import logging
from typing import Any

from dotenv import load_dotenv

from .types import AgentRunResult
from site_adaptive_webagent.kg_solution.integration import build_kg_session
from site_adaptive_webagent.runtime.browser import observe_page
from site_adaptive_webagent.runtime.executor import execute_with_llm
from site_adaptive_webagent.runtime.intent import analyze_intent
from site_adaptive_webagent.runtime.llm import make_llm_client

load_dotenv()  # .env 파일에서 LLM_PROVIDER / API 키를 로드한다

logger = logging.getLogger("webarena_verified")

# analyze_intent를 이 모듈에서도 참조 가능하도록 re-export
__all__ = ["run_agent", "analyze_intent"]


async def run_agent(  # noqa: PLR0913
    *,
    intent: str,
    sites: list[str],
    start_urls: list[str],
    task_id: int,
    context: Any,
    pages: list[Any],
    task_output_dir: Path,
) -> AgentRunResult:
    """웹 에이전트 정책을 실행한다."""
    del context, task_id, task_output_dir, sites, start_urls

    if not pages:
        return AgentRunResult.unknown_error("No pages opened for this task")

    llm = make_llm_client()
    plan = analyze_intent(intent, llm=llm)
    primary_page = pages[0]
    observation = await observe_page(primary_page)

    if llm is None:
        return AgentRunResult.unknown_error("LLM client unavailable — set ANTHROPIC_API_KEY or OPENAI_API_KEY")

    import os
    try:
        max_steps = int(os.getenv("MAX_STEPS_PER_TASK", "50"))
    except ValueError:
        max_steps = 50

    # KG session 로드 (실패 시 None → baseline 동작).
    # env `KG_ENABLED=0`으로 완전 비활성화 가능 (ablation baseline 재측정용).
    kg_session = None
    if os.getenv("KG_ENABLED", "1") != "0":
        kg_session = build_kg_session(
            cascade_enabled=(os.getenv("KG_CASCADE", "1") != "0"),
            replan_per_step=(os.getenv("KG_REPLAN", "1") != "0"),
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
        status=outcome.status,
        retrieved_data=outcome.retrieved_data,
        error_details=outcome.error_details,
    )
