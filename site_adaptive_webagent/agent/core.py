from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from .types import AgentRunResult
from site_adaptive_webagent.runtime.intent import analyze_intent
from site_adaptive_webagent.runtime.llm import make_llm_client

load_dotenv()  # .env 파일에서 LLM_PROVIDER / API 키를 로드한다
from site_adaptive_webagent.runtime.orchestrator import RuntimeOrchestrator
from site_adaptive_webagent.runtime.schema import bootstrap_runtime_schema
from site_adaptive_webagent.runtime.store import ExecutionStore, KBStore
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

    primary_site = sites[0] if sites else "unknown"

    # 알려진 사이트면 KB 시딩
    if primary_site == "gitlab" and start_urls:
        from site_adaptive_webagent.runtime.seeds.gitlab import seed_gitlab_kb
        parsed = urlparse(start_urls[0])
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        seed_gitlab_kb(conn, base_url=base_url)

    llm = make_llm_client()
    plan = analyze_intent(intent, llm=llm)
    orchestrator = RuntimeOrchestrator(KBStore(conn), ExecutionStore(conn), llm=llm)

    task_family = plan.task_type.lower()
    page_type_id = _resolve_page_type(conn, primary_site, start_urls[0]) if start_urls else "unresolved"

    runtime_result = await orchestrator.run(
        RunRequest(request_text=intent, task_family=task_family),
        RunContext(
            site_id=primary_site,
            page_type_id=page_type_id,
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


def _resolve_page_type(conn: sqlite3.Connection, site_id: str, url: str) -> str:
    """URL을 page_types의 url_patterns와 매칭하여 page_key를 반환한다."""
    path = urlparse(url).path.rstrip("/")
    cur = conn.execute(
        "SELECT page_key, url_patterns FROM page_types WHERE site_id = ?", (site_id,)
    )
    for page_key, patterns_json in cur:
        patterns = json.loads(patterns_json)
        for pattern in patterns:
            # 단순 suffix 매칭: URL path가 pattern으로 끝나면 매칭
            pattern_clean = pattern.rstrip("/")
            if "{" in pattern_clean:
                continue  # 템플릿 패턴은 skip (/{namespace}/{project} 등)
            if path == pattern_clean or path.endswith(pattern_clean):
                return page_key
    return "unresolved"
