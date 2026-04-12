from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .types import AgentRunResult
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
    """웹 에이전트 정책을 실행한다.

    SITEKG_SEED_PATH 환경변수가 설정되면 SiteKG 적용 (조건 D).
    미설정이면 baseline (조건 A).
    """
    del context, task_id, task_output_dir, sites, start_urls

    if not pages:
        return AgentRunResult.unknown_error("No pages opened for this task")

    llm = make_llm_client()
    plan = analyze_intent(intent, llm=llm)
    primary_page = pages[0]
    observation = await observe_page(primary_page)

    if llm is None:
        return AgentRunResult.unknown_error("LLM client unavailable — set ANTHROPIC_API_KEY or OPENAI_API_KEY")

    # SiteKG 로드 (조건 A vs D 분기)
    sitekg = None
    kg_seed_path = os.getenv("SITEKG_SEED_PATH", "")
    if kg_seed_path and Path(kg_seed_path).exists():
        try:
            from site_adaptive_webagent.runtime.sitekg import load_seed
            sitekg = load_seed(kg_seed_path)
            logger.info("SiteKG loaded: %s (%d pages, %d widgets)",
                        kg_seed_path, len(sitekg.page_nodes), len(sitekg.widget_nodes))
        except Exception as e:
            logger.warning("Failed to load SiteKG from %s: %s", kg_seed_path, e)

    outcome = await execute_with_llm(
        task=intent,
        task_type=plan.task_type,
        page=primary_page,
        observation=observation,
        llm=llm,
        sitekg=sitekg,
    )

    return AgentRunResult(
        task_type=outcome.task_type,
        status=outcome.status,
        retrieved_data=outcome.retrieved_data,
        error_details=outcome.error_details,
    )
