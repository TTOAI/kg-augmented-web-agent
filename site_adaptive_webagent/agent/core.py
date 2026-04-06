from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .types import AgentRunResult
from site_adaptive_webagent.runtime.intent import analyze_intent
from site_adaptive_webagent.runtime.llm import make_llm_client

load_dotenv()  # .env 파일에서 LLM_PROVIDER / API 키를 로드한다
from site_adaptive_webagent.runtime.orchestrator import RuntimeOrchestrator
from site_adaptive_webagent.runtime.schema import bootstrap_runtime_schema
from site_adaptive_webagent.runtime.store import ExecutionStore, PriorStore
from site_adaptive_webagent.runtime.types import BrowserSession, RunContext, RunRequest

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
    """RuntimeOrchestrator를 통해 baseline 웹 에이전트 정책을 실행한다."""
    del context, task_id, task_output_dir

    if not pages:
        return AgentRunResult.unknown_error("No pages opened for this task")

    conn = sqlite3.connect(":memory:")
    bootstrap_runtime_schema(conn)
    llm = make_llm_client()
    plan = analyze_intent(intent, llm=llm)
    orchestrator = RuntimeOrchestrator(PriorStore(conn), ExecutionStore(conn), llm=llm)

    primary_site = sites[0] if sites else "unknown"
    task_family = plan.task_type.lower()

    runtime_result = await orchestrator.run(
        RunRequest(request_text=intent, task_family=task_family),
        RunContext(
            site_id=primary_site,
            page_type_id="unresolved",
            task_family=task_family,
            state_summary=intent,
        ),
        browser_session=BrowserSession(
            pages=pages,
            sites=sites,
            start_urls=start_urls,
            plan=plan,
        ),
    )

    if runtime_result.execution_outcome is not None:
        o = runtime_result.execution_outcome
        return AgentRunResult(
            task_type=o.task_type,
            status=o.status,
            retrieved_data=o.retrieved_data,
            error_details=o.error_details,
        )

    return AgentRunResult.unknown_error(runtime_result.error_details or "No execution result")
