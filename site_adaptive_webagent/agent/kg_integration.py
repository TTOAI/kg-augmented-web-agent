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

    (Phase 2C C1 rollback 2026-04-18: path_slot hint가 prompt에 포함될 때 Hook A가
    rich-but-wrong bindings를 생성해 agent를 잘못된 URL로 유도하는 사례 관찰됨.
    따라서 path_slot 정보 embed는 제외하고 InfoType 기본 정보만 유지. C2 runtime
    context auto-fill은 독립적으로 유지됨 — agent URL에서 path_slots 자동 추출하여
    emit_target_url이 bindings 부족 시 fallback으로 사용.)
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
# R3-α: KG context block builder (Hook A의 결과를 agent system prompt에 주입)
# ---------------------------------------------------------------------------

def format_kg_context_for_prompt(
    kg_context: KGContext,
    kg_lookup: KGLookup,
    *,
    max_patterns: int = 3,
    max_adjacent: int = 5,
) -> str:
    """Hook A 결과(InfoType + bindings)를 agent system prompt에 주입할
    passive context block으로 포맷.

    R3-α 원칙: command가 아닌 informational. agent가 URL 이동·클릭 등을 직접 선택.
    - 관련 URL 패턴 (realize edges)
    - 필요한 bindings 힌트
    - 인접 InfoType 후보 (1-hop LeadsToEdge)

    max_patterns/max_adjacent로 prompt 길이 제한. 빈 InfoType이면 empty string.
    """
    kg = kg_context.kg
    infotype_name = kg_lookup.infotype
    it = kg.infotypes.get(infotype_name)
    if it is None:
        return ""

    lines: list[str] = ["## Site knowledge (from SiteKG, informational)"]
    desc = it.description.strip() if it.description else ""
    if desc:
        lines.append(f"The requested information likely corresponds to **{infotype_name}**: {desc}")
    else:
        lines.append(f"The requested information likely corresponds to **{infotype_name}**.")

    # 관련 URL 패턴
    patterns_shown = 0
    if it.realizes:
        lines.append("")
        lines.append("Relevant URL patterns you may navigate to:")
        for realize in it.realizes[:max_patterns]:
            sp = kg.state_patterns.get(realize.state_pattern_id)
            if sp is None:
                continue
            url_repr = getattr(sp, "url_pattern", None) or getattr(sp, "path_pattern", None) or realize.state_pattern_id
            lines.append(f"- `{url_repr}`")
            patterns_shown += 1

    # 필요한 bindings 힌트
    if it.required_bindings:
        req = ", ".join(it.required_bindings)
        lines.append("")
        lines.append(f"Context fields the URL pattern expects: {req}")

    # 이미 Hook A가 채운 bindings (runtime 상태 힌트)
    if kg_lookup.bindings:
        nonempty = {k: v for k, v in kg_lookup.bindings.items() if v not in (None, "", [])}
        if nonempty:
            pretty = ", ".join(f"{k}={v}" for k, v in nonempty.items())
            lines.append(f"Inferred context from intent: {pretty}")

    # 인접 InfoType 후보 (1-hop LeadsToEdge로부터)
    adjacent: list[str] = []
    if it.realizes:
        state_pattern_ids = {r.state_pattern_id for r in it.realizes}
        for edge in kg.leads_to_edges:
            if edge.from_state_pattern_id in state_pattern_ids:
                to_sp = edge.to_state_pattern_id
                # to_sp를 realize하는 다른 InfoType 찾기
                for other_name, other_it in kg.infotypes.items():
                    if other_name == infotype_name:
                        continue
                    if any(r.state_pattern_id == to_sp for r in other_it.realizes):
                        if other_name not in adjacent:
                            adjacent.append(other_name)
                if len(adjacent) >= max_adjacent:
                    break
    if adjacent:
        lines.append("")
        lines.append(f"Adjacent pages reachable from this area: {', '.join(adjacent[:max_adjacent])}")

    lines.append("")
    lines.append("Use this as hints. You decide how to navigate — this knowledge does not override your own observations.")

    if patterns_shown == 0 and not it.required_bindings and not adjacent:
        return ""
    return "\n".join(lines)


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

    환경변수 `SITEKG_FROZEN`이 set이면 해당 path의 frozen snapshot(SiteKGStore.load
    호환 JSON)만 로드하고, SiteConfig는 같은 site config 디렉토리에서 fallback 로드.
    이는 baseline 측정 시 catalog freeze 보장(M4-C, docs/kg_design/07 §14)을 위함.
    """
    import json
    import os

    import yaml

    from site_adaptive_webagent.kg.seed import load_site_kg_from_dir
    from site_adaptive_webagent.kg.seed.manual_config import load_site_config
    from site_adaptive_webagent.kg.store import SiteKGStore

    # Expected structural errors (silent fallback OK — 재현성 영향 없음).
    # 그 외 예외는 re-raise (fail-loud) — 측정 도중 silent 오염 방지.
    _EXPECTED_LOAD_ERRORS = (FileNotFoundError, json.JSONDecodeError, yaml.YAMLError,
                             KeyError, PermissionError, IsADirectoryError)

    dir_path = Path(config_root) / site

    frozen_env = os.getenv("SITEKG_FROZEN", "").strip()
    if frozen_env:
        frozen_path = Path(frozen_env)
        if not frozen_path.exists():
            logger.error("[KG] SITEKG_FROZEN=%s does not exist — KG disabled", frozen_path)
            return None
        try:
            kg = SiteKGStore.load(frozen_path).kg
        except _EXPECTED_LOAD_ERRORS as e:
            logger.error("[KG] frozen snapshot %s structural error: %s — KG disabled",
                         frozen_path, e)
            return None
        site_config_path = dir_path / "site_config.yaml"
        if not site_config_path.exists():
            logger.error(
                "[KG] frozen snapshot loaded but site_config.yaml missing at %s — KG disabled",
                site_config_path,
            )
            return None
        try:
            site_config = load_site_config(site_config_path)
        except _EXPECTED_LOAD_ERRORS as e:
            logger.error("[KG] site_config %s structural error: %s — KG disabled",
                         site_config_path, e)
            return None
        logger.info("[KG] loaded frozen snapshot %s (git_rev=%s)", frozen_path, kg.git_rev)
        return KGContext(
            kg=kg,
            site_config=site_config,
            runtime_context=runtime_context or {},
        )

    if not dir_path.exists():
        logger.info("[KG] no config dir at %s — KG disabled", dir_path)
        return None
    try:
        site_config, kg = load_site_kg_from_dir(dir_path)
    except _EXPECTED_LOAD_ERRORS as e:
        logger.error("[KG] site dir %s structural error: %s — KG disabled",
                     dir_path, e)
        return None
    return KGContext(
        kg=kg,
        site_config=site_config,
        runtime_context=runtime_context or {},
    )
