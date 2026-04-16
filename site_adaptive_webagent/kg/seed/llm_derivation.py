"""LLM-assisted InfoType + Action derivation — 3단계 hybrid의 단계 2 (M4-B).

docs/kg_design/07 §14의 `source=llm` / `trust=inferred` layer를 생산한다.
M4-A(crawler)가 만든 SiteKG와 raw CrawlResult를 한 번의 LLM tool call로 넘겨
의미적 InfoType과 의미적 Action 이름(rename map)을 도출한다.

산출 SiteKG는 `derivation_to_kg.derivation_to_sitekg`에서 구성되며,
manual seed + crawl SiteKG와 별개로 만들어져 호출자가 SiteKGStore.merge로 합친다.

설계는 `agent/kg_integration.py`의 plan_to_info(Hook A) 패턴을 모방.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..types import Action, InfoType, RealizesEdge, SiteKG
from .playwright_crawler import CrawlResult

if TYPE_CHECKING:
    from site_adaptive_webagent.runtime.llm import LLMClient

logger = logging.getLogger("kg.derivation")

_TOOL_NAME = "derive_kg"


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class StatePatternGroup:
    """LLM이 제안한 의미적 StatePattern 그룹.

    semantic_template: 공통 url_template (예: "/{project_path}/-/issues")
    path_params: semantic_template의 slot 메타 (type 등)
    member_ids: 이 그룹에 속하는 crawl StatePattern id 목록
    reasoning: LLM이 제공한 grouping 근거 (reviewer 감사용)
    """

    semantic_template: str
    path_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    member_ids: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass(slots=True)
class DerivationResult:
    """LLM derivation의 단일 호출 결과.

    infotypes: LLM이 도출한 InfoType 객체들 (source="llm")
    action_name_map: crawler가 만든 Action 이름 → 의미 이름. 빈 매핑이면 rename 없음.
    actions: 의미 이름 기준 Action 객체 (description 포함)
    state_pattern_groups: crawl StatePattern을 의미적 template으로 clustering한 결과.
        후처리에서 각 group을 단일 llm StatePattern으로 merge.
    raw_response: 디버깅·재현성용 raw tool_call arguments JSON
    prompt: derivation에 보낸 system prompt (재현성)
    """

    infotypes: list[InfoType] = field(default_factory=list)
    action_name_map: dict[str, str] = field(default_factory=dict)
    actions: dict[str, Action] = field(default_factory=dict)
    state_pattern_groups: list[StatePatternGroup] = field(default_factory=list)
    raw_response: str = ""
    prompt: str = ""


# ---------------------------------------------------------------------------
# Tool schema + system prompt
# ---------------------------------------------------------------------------

def build_derive_kg_tool() -> dict[str, Any]:
    """LLM에게 grouping + InfoType + Action rename을 한 번에 받기 위한 tool schema."""
    return {
        "name": _TOOL_NAME,
        "description": (
            "Derive the semantic layer of a site-specific Knowledge Graph from crawler "
            "observations: (1) cluster StatePatterns by semantic template, (2) name "
            "InfoTypes that correspond to those clusters, (3) propose semantic names "
            "for crawler placeholder actions. Call exactly once with the complete catalog."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "state_pattern_groups": {
                    "type": "array",
                    "description": (
                        "Cluster the observed crawl StatePatterns into semantic groups. "
                        "Each group names one semantic url_template that generalizes its "
                        "members. Different pages with different meanings MUST be in "
                        "different groups, even if URL structure looks similar."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "semantic_template": {
                                "type": "string",
                                "description": (
                                    "Generalized url_template with named slots, e.g. "
                                    "'/{project_path}/-/issues'. Use descriptive slot "
                                    "names, not slot_0/slot_1."
                                ),
                            },
                            "path_params": {
                                "type": "object",
                                "description": (
                                    "For each slot in semantic_template, describe its "
                                    "type. Example: {'project_path': {'type': 'path_segments'}}."
                                ),
                                "additionalProperties": {
                                    "type": "object",
                                    "additionalProperties": True,
                                },
                            },
                            "member_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Crawl StatePattern ids that belong to this group. "
                                    "Ids must match the 'id=...' prefix in the catalog."
                                ),
                            },
                            "reasoning": {
                                "type": "string",
                                "description": (
                                    "Short justification for why these members share the "
                                    "same semantic template (reviewer audit trail)."
                                ),
                            },
                        },
                        "required": ["semantic_template", "member_ids"],
                    },
                },
                "infotypes": {
                    "type": "array",
                    "description": (
                        "Semantic InfoTypes covering observed StatePatterns. Each item "
                        "describes one domain-noun concept observed across one or more URLs."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "required_bindings": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "optional_bindings": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "intent_examples": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "realizes": {
                                "type": "array",
                                "description": (
                                    "Which StatePatterns this InfoType realizes. Use any "
                                    "crawl id from the observed catalog — the post-processor "
                                    "resolves it to the semantic group containing that id."
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "state_pattern_id": {"type": "string"},
                                        "condition": {
                                            "type": "string",
                                            "enum": ["default", "has_filter"],
                                        },
                                        "binding_map": {
                                            "type": "object",
                                            "additionalProperties": {"type": "string"},
                                        },
                                    },
                                    "required": ["state_pattern_id"],
                                },
                            },
                        },
                        "required": ["name", "description", "realizes"],
                    },
                },
                "action_renames": {
                    "type": "array",
                    "description": (
                        "Rename crawler-observed actions (e.g., 'crawl:form:...') to "
                        "semantic verb-phrase names. Omit entries whose original name "
                        "is already meaningful enough."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "original_name": {"type": "string"},
                            "semantic_name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["original_name", "semantic_name"],
                    },
                },
            },
            "required": ["state_pattern_groups", "infotypes", "action_renames"],
        },
    }


def build_derivation_system_prompt(
    crawl_kg: SiteKG,
    crawl_results: list[CrawlResult],
) -> str:
    """LLM에게 전달할 system prompt — crawl 산출물의 구조적 요약 포함.

    실험 task·평가 task 어휘를 prompt에 박지 않는다 (memory feedback_no_task_site_bias).
    1,000+ StatePattern도 수용할 수 있도록 compact format.
    """
    lines: list[str] = [
        "You derive the semantic layer of a site-specific Knowledge Graph from crawler",
        "observations. The crawler saw one literal url_template per observed URL, so many",
        "entries below are instances of the same semantic template (e.g., different projects",
        "all share '/{project_path}/-/issues'). Your first job is to cluster them.",
        "",
        "## Output contract (call derive_kg exactly once)",
        "1. `state_pattern_groups`: cluster the crawl StatePatterns by semantic_template.",
        "   - Use descriptive slot names (e.g., `{project_path}`, `{issue_iid}`), NOT `slot_0`.",
        "   - Different meanings MUST stay in different groups even if structures look alike",
        "     (e.g., `/admin/users` vs `/admin/groups` are NOT the same group).",
        "   - Every member_id must be one of the crawl ids below.",
        "   - Provide `reasoning` for each group (audit trail for reviewers).",
        "2. `infotypes`: semantic domain-noun catalog (e.g., project issues list, user profile).",
        "   - InfoType.name: snake_case, generic domain term, not brand-specific.",
        "   - realizes[*].state_pattern_id = any crawl id (post-processor resolves to its group).",
        "3. `action_renames` (OPTIONAL): map `crawl:nav` / `crawl:form:*` to semantic verbs",
        "   only when obvious. Otherwise omit — manual review will refine.",
        "",
        "## Observed crawl StatePatterns",
    ]
    for sp_id, sp in crawl_kg.state_patterns.items():
        params = ",".join(p.name for p in sp.identity_query_params) or "-"
        lines.append(f"id={sp_id} url={sp.url_template} q=[{params}]")
    if not crawl_kg.state_patterns:
        lines.append("(none observed)")

    lines += ["", "## Observed crawl Actions"]
    for act_name, act in crawl_kg.actions.items():
        params = ",".join(p.get("name", "?") for p in act.params) or "-"
        lines.append(f"name={act_name} params=[{params}]")
    if not crawl_kg.actions:
        lines.append("(none observed)")

    # 전체 URL 샘플은 prompt 크기 억제를 위해 생략. 필요 시 crawler log 직접 참조.
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def derive_infotypes_and_actions(
    crawl_results: list[CrawlResult],
    crawl_kg: SiteKG,
    llm: "LLMClient",
) -> DerivationResult:
    """단일 LLM tool call로 InfoType + Action rename map을 도출.

    실패(LLM exception, no tool call, schema 위반, unknown InfoType 등)는
    빈 DerivationResult 반환 + 로깅. 호출자가 graceful degrade.
    """
    if not crawl_kg.state_patterns:
        logger.info("[derivation] empty crawl_kg — nothing to derive")
        return DerivationResult()

    system = build_derivation_system_prompt(crawl_kg, crawl_results)
    tool = build_derive_kg_tool()
    user_message = (
        "Below is the full crawler summary. Derive InfoTypes and propose semantic "
        "Action names by calling `derive_kg` once."
    )
    messages = [{"role": "user", "content": user_message}]

    try:
        # derivation은 수백~수천 StatePattern을 grouping하므로 큰 output 필요.
        response = llm.complete_with_tools(
            system=system, messages=messages, tools=[tool], max_tokens=32768,
        )
    except Exception:
        logger.exception("[derivation] LLM call raised")
        return DerivationResult(prompt=system)

    if not response.tool_calls:
        logger.info("[derivation] LLM declined (no tool call)")
        return DerivationResult(prompt=system, raw_response=response.thought or "")

    tc = response.tool_calls[0]
    if tc.name != _TOOL_NAME:
        logger.info("[derivation] unexpected tool name %r", tc.name)
        return DerivationResult(prompt=system)

    args = tc.arguments if isinstance(tc.arguments, dict) else {}
    raw_args_json = json.dumps(args, ensure_ascii=False)

    groups_raw = args.get("state_pattern_groups") or []
    infotypes_raw = args.get("infotypes") or []
    action_renames_raw = args.get("action_renames") or []

    state_pattern_groups: list[StatePatternGroup] = []
    for g in groups_raw:
        if not isinstance(g, dict) or not g.get("semantic_template"):
            continue
        members = list(g.get("member_ids") or [])
        # 알려지지 않은 crawl id는 filter (LLM hallucination 대응)
        members = [m for m in members if m in crawl_kg.state_patterns]
        if not members:
            continue
        state_pattern_groups.append(
            StatePatternGroup(
                semantic_template=str(g["semantic_template"]).strip(),
                path_params=dict(g.get("path_params") or {}),
                member_ids=members,
                reasoning=str(g.get("reasoning", "")).strip(),
            )
        )

    infotypes: list[InfoType] = []
    for it_raw in infotypes_raw:
        if not isinstance(it_raw, dict) or not it_raw.get("name"):
            continue
        name = str(it_raw["name"]).strip()
        realizes_raw = it_raw.get("realizes") or []
        realizes: list[RealizesEdge] = []
        for r in realizes_raw:
            if not isinstance(r, dict) or not r.get("state_pattern_id"):
                continue
            realizes.append(
                RealizesEdge(
                    infotype=name,
                    state_pattern_id=str(r["state_pattern_id"]),
                    condition=r.get("condition", "default"),
                    binding_map=dict(r.get("binding_map") or {}),
                    trust="inferred",
                    source="llm",
                )
            )
        infotypes.append(
            InfoType(
                name=name,
                description=str(it_raw.get("description", "")).strip(),
                required_bindings=list(it_raw.get("required_bindings") or []),
                optional_bindings=list(it_raw.get("optional_bindings") or []),
                realizes=realizes,
                intent_examples=list(it_raw.get("intent_examples") or []),
                trust_label="inferred",
                source="llm",
            )
        )

    action_name_map: dict[str, str] = {}
    actions: dict[str, Action] = {}
    for ar in action_renames_raw:
        if not isinstance(ar, dict):
            continue
        original = ar.get("original_name")
        semantic = ar.get("semantic_name")
        if not original or not semantic:
            continue
        original_s = str(original).strip()
        semantic_s = str(semantic).strip()
        action_name_map[original_s] = semantic_s
        existing_act = crawl_kg.actions.get(original_s)
        params = list(existing_act.params) if existing_act else []
        actions[semantic_s] = Action(
            name=semantic_s,
            params=params,
            description=str(ar.get("description", "")).strip(),
            source="llm",
        )

    return DerivationResult(
        infotypes=infotypes,
        action_name_map=action_name_map,
        actions=actions,
        state_pattern_groups=state_pattern_groups,
        raw_response=raw_args_json,
        prompt=system,
    )
