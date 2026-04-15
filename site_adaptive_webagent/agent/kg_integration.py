"""Agent ↔ KG 통합 bridge — 4 Hook 구현.

Hook 책임:
- A (plan_to_info): LLM에게 intent를 (InfoType, bindings)로 분류시킴
- B (rewrite): LLM plan을 canonical URL 기반으로 재작성 (`kg.rewrite.rewrite_plan`)
- C (validator): sub-goal 경계에서 target 도달 여부 판정 (`kg.validator.target_reached`)
- D (trust update): 성공/실패 피드백으로 trust 업데이트. M3에선 no-op logging.

Hook B, C는 `kg.rewrite`, `kg.validator`의 얇은 wrapper.
Hook A만 새 LLM 호출 로직이 필요해 여기 구현.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from site_adaptive_webagent.kg import (
    KGContext,
    KGLookup,
    SiteKG,
)

if TYPE_CHECKING:
    from site_adaptive_webagent.runtime.llm import LLMClient

logger = logging.getLogger("webarena_verified")


# ---------------------------------------------------------------------------
# Hook A: plan_to_info tool schema + LLM call
# ---------------------------------------------------------------------------

def build_plan_to_info_tool(kg: SiteKG) -> dict[str, Any]:
    """KG의 InfoType 카탈로그를 기반으로 plan_to_info tool schema 생성.

    - target_infotype: enum (KG에 등록된 InfoType 이름)
    - bindings: free-form object (InfoType별 required/optional에 맞춰 LLM이 채움)
    """
    infotype_names = list(kg.infotypes.keys())
    # enum 설명에 각 InfoType의 description + required/optional 요약 포함
    enum_description_parts: list[str] = []
    for name in infotype_names:
        it = kg.infotypes[name]
        req = ", ".join(it.required_bindings) if it.required_bindings else "(none)"
        opt = ", ".join(it.optional_bindings) if it.optional_bindings else "(none)"
        desc = it.description.strip() if it.description else ""
        enum_description_parts.append(
            f"'{name}': {desc} required=[{req}] optional=[{opt}]"
        )
    enum_description = "Pick one: " + " | ".join(enum_description_parts)

    return {
        "name": "plan_to_info",
        "description": (
            "Classify the user intent into a known InfoType and extract the bindings "
            "needed to identify the target state. Only call this when an InfoType clearly "
            "applies to the intent; otherwise do not call any tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_infotype": {
                    "type": "string",
                    "enum": infotype_names,
                    "description": enum_description,
                },
                "bindings": {
                    "type": "object",
                    "description": (
                        "Key-value pairs matching the chosen InfoType's required and optional fields. "
                        "Use strings for single values and arrays for multi-value fields (e.g., label_name)."
                    ),
                    "additionalProperties": True,
                },
            },
            "required": ["target_infotype", "bindings"],
        },
    }


def build_plan_to_info_system_prompt(kg: SiteKG) -> str:
    """Hook A용 system prompt."""
    lines = [
        "You classify a user intent into one of the known InfoTypes and extract binding values.",
        "",
        "## InfoTypes",
    ]
    for name, it in kg.infotypes.items():
        desc = it.description.strip() if it.description else ""
        req = ", ".join(it.required_bindings) if it.required_bindings else "(none)"
        opt = ", ".join(it.optional_bindings) if it.optional_bindings else "(none)"
        lines.append(f"- **{name}**: {desc}")
        lines.append(f"  required: {req}")
        lines.append(f"  optional: {opt}")
        if it.intent_examples:
            ex = "; ".join(it.intent_examples[:3])
            lines.append(f"  examples: {ex}")
    lines += [
        "",
        "## Rule",
        "- Call plan_to_info with the best matching InfoType name and the bindings you can infer from the intent.",
        "- For multi-value fields (name ending in multi_string type, e.g. label_name), provide an array even for a single value.",
        "- If no InfoType fits the intent well, DO NOT call any tool. The system will fall back to the baseline plan.",
    ]
    return "\n".join(lines)


def classify_intent_via_kg(
    intent: str,
    kg: SiteKG,
    llm: "LLMClient",
) -> KGLookup | None:
    """Hook A: intent → (InfoType, bindings) LLM 분류.

    성공 시 KGLookup 반환. LLM이 tool을 호출하지 않거나 알 수 없는 InfoType을
    반환하면 None (KG 개입 포기, baseline 유지).
    """
    if not kg.infotypes:
        return None
    system = build_plan_to_info_system_prompt(kg)
    tool = build_plan_to_info_tool(kg)
    messages = [{"role": "user", "content": f"Intent: {intent}"}]
    try:
        response = llm.complete_with_tools(system=system, messages=messages, tools=[tool])
    except Exception:
        logger.exception("[KG] plan_to_info LLM call raised")
        return None
    if not response.tool_calls:
        logger.info("[KG] plan_to_info: LLM declined classification (no tool call)")
        return None
    tc = response.tool_calls[0]
    if tc.name != "plan_to_info":
        logger.info("[KG] plan_to_info: unexpected tool %r", tc.name)
        return None
    args = tc.arguments if isinstance(tc.arguments, dict) else {}
    infotype = str(args.get("target_infotype", "")).strip()
    bindings = args.get("bindings") if isinstance(args.get("bindings"), dict) else {}
    if infotype not in kg.infotypes:
        logger.info("[KG] plan_to_info: unknown infotype %r", infotype)
        return None
    return KGLookup(infotype=infotype, bindings=dict(bindings))


# ---------------------------------------------------------------------------
# KGContext 빌더
# ---------------------------------------------------------------------------

def load_kg_context(
    site: str,
    config_root: str | Path = "config/sites",
    runtime_context: dict[str, Any] | None = None,
) -> KGContext | None:
    """`config/sites/<site>/` 에서 SiteConfig + SiteKG를 로드해 KGContext 구성.

    해당 디렉토리가 없거나 로드 실패 시 None.
    """
    from site_adaptive_webagent.kg.seed import load_site_kg_from_dir

    dir_path = Path(config_root) / site
    if not dir_path.exists():
        logger.info("[KG] no config dir at %s — KG disabled", dir_path)
        return None
    try:
        site_config, kg = load_site_kg_from_dir(dir_path)
    except Exception:
        logger.exception("[KG] failed to load site dir %s — KG disabled", dir_path)
        return None
    return KGContext(
        kg=kg,
        site_config=site_config,
        runtime_context=runtime_context or {},
    )
