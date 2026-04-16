from __future__ import annotations

import logging
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
    kg_context: Any = None,   # Optional[KGContext]; None이면 baseline 동작
) -> AgentRunResult:
    """웹 에이전트 정책을 실행한다.

    kg_context가 주어지면 KG-guided 동작:
      - Hook A: intent → (InfoType, bindings) LLM 분류
      - Hook B: plan rewrite (execute_with_llm 내부)
      - Hook C: runtime target_reached early-termination (executor 내부)
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

    import os
    # KG_VARIANT: "off" | "info_ignored" | "full" (default depends on kg_context)
    # - off: baseline — Hook A/B/C 모두 미실행 (kg_context 무시)
    # - info_ignored: Hook A LLM call 수행, 결과 사용 안 함 (compute-matched control)
    # - full: Hook A/B/C 모두 활성화 (KG hooks 정상 동작)
    kg_variant = os.getenv("KG_VARIANT", "full" if kg_context is not None else "off").lower()
    if kg_variant not in {"off", "info_ignored", "full"}:
        logger.warning("[KG] unknown KG_VARIANT=%r → fallback to baseline (off)", kg_variant)
        kg_variant = "off"

    # Hook A: KG-based intent classification (info_ignored와 full에서 호출)
    kg_lookup = None
    if kg_context is not None and kg_variant in {"info_ignored", "full"}:
        try:
            from .kg_integration import classify_intent_via_kg
            classified = classify_intent_via_kg(intent, kg_context.kg, llm)
            if kg_variant == "full":
                kg_lookup = classified
                if kg_lookup is not None:
                    logger.info("[KG] Hook A (full): infotype=%s bindings=%s",
                                kg_lookup.infotype, kg_lookup.bindings)
                else:
                    logger.info("[KG] Hook A (full): classification declined — baseline path")
            else:
                # info_ignored: LLM call 수행하지만 결과 discard (compute-matched control)
                logger.info("[KG] Hook A (info_ignored): LLM call performed, result discarded "
                            "(infotype=%s)", classified.infotype if classified else "None")
                kg_lookup = None
        except Exception:
            logger.exception("[KG] Hook A raised — baseline path")

    try:
        max_steps = int(os.getenv("MAX_STEPS_PER_TASK", "50"))
    except ValueError:
        max_steps = 50

    # info_ignored는 Hook B/C도 비활성화 (kg_context를 None으로 넘김)
    effective_kg_context = kg_context if kg_variant == "full" else None

    outcome = await execute_with_llm(
        task=intent,
        task_type=plan.task_type,
        page=primary_page,
        observation=observation,
        llm=llm,
        kg_context=effective_kg_context,
        kg_lookup=kg_lookup,
        max_steps=max_steps,
    )

    return AgentRunResult(
        task_type=outcome.task_type,
        status=outcome.status,
        retrieved_data=outcome.retrieved_data,
        error_details=outcome.error_details,
    )
