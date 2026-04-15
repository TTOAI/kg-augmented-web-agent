"""Agent 실행 진입점 (stub).

WebArena-Verified 어댑터가 기대하는 `run_agent` 함수의 skeleton만 제공한다.
실제 agent 로직은 이후 단계에서 새로 구현한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .types import AgentRunResult

__all__ = ["run_agent"]


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
    """Agent 로직 미구현 스텁.

    어댑터와의 시그니처 계약만 유지하며, 실제 동작은 이후 재설계 단계에서 채운다.
    """
    del intent, sites, start_urls, task_id, context, pages, task_output_dir
    return AgentRunResult.unknown_error("Agent logic not implemented yet")
