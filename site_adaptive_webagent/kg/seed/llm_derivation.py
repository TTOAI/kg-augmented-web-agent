"""LLM-assisted InfoType + Action derivation (collector 2단계).

`source=llm` / `trust=inferred` layer를 생산한다. crawler가 만든 SiteKG와 raw
CrawlResult를 LLM tool call로 넘겨 의미적 InfoType과 의미적 Action 이름
(rename map)을 도출한다.

산출 SiteKG는 `derivation_to_kg.derivation_to_sitekg`에서 구성되며,
manual seed + crawl SiteKG와 별개로 만들어져 호출자가 SiteKGStore.merge로 합친다.
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

# Multi-call decomposition: 단일 호출의 reasoning context overflow를 피해 task별로 분할.
# Cross-consistency는 Call 2/3 prompt에 Call 1의 group_id를 명시하여 보존.
_TOOL_NAME = "derive_kg"  # Backward-compat: 단일 호출 (deprecated path)
_TOOL_GROUPS = "derive_state_pattern_groups"
_TOOL_INFOTYPES = "derive_infotypes"
_TOOL_ACTIONS = "derive_action_renames"

# reasoning_effort은 Responses API 경로에서만 적용된다 (chat.completions에선 function
# tools와 동시 사용 불가). LLMClient가 gpt-5* / o-series 모델을 감지하면 자동으로
# Responses API로 분기한다. "low"는 단순 cluster·mapping 작업에 충분하고 latency를
# 크게 단축한다.
_REASONING_EFFORT: str | None = "low"


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class StatePatternGroup:
    """LLM이 제안한 의미적 StatePattern 그룹.

    semantic_template: 공통 url_template (예: "/{project_path}/-/issues")
    path_params: semantic_template의 slot 메타 (type 등)
    member_ids: 이 그룹에 속하는 crawl StatePattern id 목록
    expected_query_params: page 의미상 받을 수 있는 query param 후보
        (LLM이 page kind에서 도메인 추정 — list page는 filter/sort/pagination 받음 등).
        post-processor가 이를 union해 group의 StatePattern.identity_query_params에 반영.
    reasoning: LLM이 제공한 grouping 근거 (reviewer 감사용)
    """

    semantic_template: str
    path_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    member_ids: list[str] = field(default_factory=list)
    expected_query_params: list[dict[str, Any]] = field(default_factory=list)
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
                            "expected_query_params": {
                                "type": "array",
                                "description": (
                                    "Query parameters this page semantically accepts but the "
                                    "crawler may not have observed. Infer ONLY from the page "
                                    "kind suggested by the URL/path (e.g., a list/index page "
                                    "typically accepts filter/sort/pagination params; a search "
                                    "page accepts a query string). Do NOT invent params with no "
                                    "structural justification. The post-processor unions these "
                                    "with crawler-observed params."
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {
                                            "type": "string",
                                            "enum": ["string", "int", "enum",
                                                     "multi_string", "bool"],
                                        },
                                        "reasoning": {"type": "string"},
                                    },
                                    "required": ["name"],
                                },
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
        "entries below are instances of the same semantic template (different concrete",
        "instances all share one generalized path). Your first job is to cluster them.",
        "",
        "## Output contract (call derive_kg exactly once)",
        "1. `state_pattern_groups`: cluster the crawl StatePatterns by semantic_template.",
        "   - Use descriptive slot names (e.g., `{project_path}`, `{issue_iid}`), NOT `slot_0`.",
        "   - Different meanings MUST stay in different groups even if structures look alike",
        "     (sibling resource sections under a common admin/explore prefix are usually",
        "     distinct groups, not a single one).",
        "   - Every member_id must be one of the crawl ids below.",
        "   - Provide `reasoning` for each group (audit trail for reviewers).",
        "   - **expected_query_params**: infer query params the page semantically accepts.",
        "     For list/index pages, this typically includes filter/sort/pagination keys;",
        "     for search pages, the query/scope keys. Crawler may have missed many of these",
        "     because it never visited the filtered URLs. Only include params justifiable",
        "     from the page's *kind*, not invented.",
        "2. `infotypes`: semantic domain-noun catalog (one item per concept).",
        "   - InfoType.name: snake_case, generic domain term, not brand-specific.",
        "   - **realizes is 1:N**: the same InfoType can be satisfied by multiple distinct",
        "     `state_pattern_id`s. Use this when:",
        "       (a) Different page paths offer the same information differently (e.g.,",
        "           `/explore` default vs `/explore/starred` curated subset).",
        "       (b) The same path has a meaningfully different mode under filter (use",
        "           `condition: \"has_filter\"` and a non-empty `binding_map` to record",
        "           which optional_binding maps to which query/path slot).",
        "     Aim for explicit 1:N coverage where the crawl catalog supports it; do not",
        "     duplicate the same realize edge twice.",
        "   - `binding_map` MUST link each binding name to a slot/query name on the target.",
        "3. `action_renames` (OPTIONAL): map `crawl:nav` / `crawl:form:*` to semantic verbs",
        "   only when obvious. Otherwise omit — post-processor handles the rest.",
        "",
        "## Observed crawl StatePatterns",
    ]
    for sp_id, sp in crawl_kg.state_patterns.items():
        params = ",".join(p.name for p in sp.identity_query_params) or "-"
        lines.append(f"id={sp_id} url={sp.url_template} q=[{params}]")
    if not crawl_kg.state_patterns:
        lines.append("(none observed)")

    # Actions section: 4000+ form actions를 raw listing하면 input token 폭발.
    # `crawl:form:<page_slug>:<input_name>` 구조에서 input_name별로 sample 3개만
    # 보여주고 나머지는 count로 표현. Action rename은 input name 의미로도 충분히
    # 일관되게 매기므로 모든 page binding을 보여줄 필요 없음.
    lines += ["", "## Observed crawl Actions (input-name aggregated)"]
    if not crawl_kg.actions:
        lines.append("(none observed)")
    else:
        from collections import defaultdict as _dd
        by_input: _dd[str, list[str]] = _dd(list)
        non_form: list[tuple[str, Any]] = []
        for act_name, act in crawl_kg.actions.items():
            if act_name.startswith("crawl:form:"):
                parts = act_name.split(":", 3)
                input_name = parts[3] if len(parts) > 3 else "?"
                by_input[input_name].append(act_name)
            else:
                non_form.append((act_name, act))
        for act_name, act in non_form:
            params = ",".join(p.get("name", "?") for p in act.params) or "-"
            lines.append(f"name={act_name} params=[{params}]")
        for input_name, acts in sorted(by_input.items()):
            n = len(acts)
            samples = acts[:3]
            sample_str = ", ".join(samples)
            if n > 3:
                lines.append(
                    f"input={input_name!r} count={n} samples=[{sample_str}, …(+{n-3} more)]"
                )
            else:
                lines.append(f"input={input_name!r} count={n} actions=[{sample_str}]")

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
    """Multi-call decomposition으로 InfoType + Action rename map을 도출.

    분할 정당화: 단일 호출에 grouping/InfoType/action_rename을 모두 시키면 reasoning
    model의 context overflow 위험 + 응답 token 폭발이 발생함. 각 task는 독립적이고
    cross-consistency는 Call 1의 group_id를 Call 2 prompt에 명시해 보존한다.

    실패는 partial DerivationResult 반환 (성공한 단계만 채워짐) + 로깅.
    """
    if not crawl_kg.state_patterns:
        logger.info("[derivation] empty crawl_kg — nothing to derive")
        return DerivationResult()

    # Call 1: state_pattern grouping
    groups, groups_prompt, groups_raw = _derive_state_pattern_groups(crawl_kg, llm)
    logger.info("[derivation] Call 1 groups=%d", len(groups))

    # Call 2: InfoTypes + realize (groups를 input에 명시)
    infotypes, it_prompt, it_raw = _derive_infotypes(crawl_kg, groups, llm)
    logger.info("[derivation] Call 2 infotypes=%d", len(infotypes))

    # Call 3: action renames
    action_name_map, actions, ar_prompt, ar_raw = _derive_action_renames(crawl_kg, llm)
    logger.info("[derivation] Call 3 action_renames=%d", len(action_name_map))

    return DerivationResult(
        infotypes=infotypes,
        action_name_map=action_name_map,
        actions=actions,
        state_pattern_groups=groups,
        raw_response=json.dumps({
            "groups": groups_raw,
            "infotypes": it_raw,
            "action_renames": ar_raw,
        }, ensure_ascii=False),
        prompt="\n\n=== CALL 1 (groups) ===\n" + groups_prompt
               + "\n\n=== CALL 2 (infotypes) ===\n" + it_prompt
               + "\n\n=== CALL 3 (actions) ===\n" + ar_prompt,
    )


def _derive_state_pattern_groups_legacy(
    crawl_results, crawl_kg, llm,
):
    """[deprecated] 단일 호출 방식 — backward-compat용. 새 코드는 derive_infotypes_and_actions 사용."""
    if not crawl_kg.state_patterns:
        return DerivationResult()
    system = build_derivation_system_prompt(crawl_kg, crawl_results)
    tool = build_derive_kg_tool()
    user_message = (
        "Below is the full crawler summary. Derive InfoTypes and propose semantic "
        "Action names by calling `derive_kg` once."
    )
    messages = [{"role": "user", "content": user_message}]

    try:
        response = llm.complete_with_tools(
            system=system, messages=messages, tools=[tool], max_tokens=65536,
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
        # expected_query_params: 각 항목 정규화 (name 필수)
        eqp_raw = g.get("expected_query_params") or []
        eqp: list[dict[str, Any]] = []
        for item in eqp_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            eqp.append({
                "name": name,
                "type": str(item.get("type") or "string"),
                "reasoning": str(item.get("reasoning") or "").strip(),
            })
        state_pattern_groups.append(
            StatePatternGroup(
                semantic_template=str(g["semantic_template"]).strip(),
                path_params=dict(g.get("path_params") or {}),
                member_ids=members,
                expected_query_params=eqp,
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


# ---------------------------------------------------------------------------
# Multi-call decomposition: Call 1 — state pattern grouping
# ---------------------------------------------------------------------------

def _build_groups_tool() -> dict[str, Any]:
    return {
        "name": _TOOL_GROUPS,
        "description": (
            "Cluster crawler-observed StatePatterns into semantic groups. Each group "
            "names one generalized url_template that covers its members. Different page "
            "kinds MUST stay in different groups even if URL structure looks alike."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "groups": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "semantic_template": {
                                "type": "string",
                                "description": (
                                    "Generalized url_template with named slots, e.g. "
                                    "'/{project_path}/-/issues'. Use descriptive slot names."
                                ),
                            },
                            "path_params": {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "object",
                                    "additionalProperties": True,
                                },
                            },
                            "member_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Crawl StatePattern ids assigned to this group. "
                                    "Every crawl id should appear in exactly one group."
                                ),
                            },
                            "expected_query_params": {
                                "type": "array",
                                "description": (
                                    "Query parameters this page kind semantically accepts. "
                                    "Infer ONLY from the page kind (list/index → filter/sort/"
                                    "pagination; search → query/scope). Do not invent."
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "type": {
                                            "type": "string",
                                            "enum": ["string", "int", "enum",
                                                     "multi_string", "bool"],
                                        },
                                    },
                                    "required": ["name"],
                                },
                            },
                            "reasoning": {"type": "string"},
                        },
                        "required": ["semantic_template", "member_ids"],
                    },
                },
            },
            "required": ["groups"],
        },
    }


def _build_groups_prompt(crawl_kg: SiteKG) -> str:
    lines = [
        "You cluster crawler-observed StatePatterns into semantic groups.",
        "",
        "## Output contract (call derive_state_pattern_groups exactly once)",
        "- **Every crawl id below MUST appear in exactly one group's `member_ids`. No id left out.**",
        "- **Produce many groups (typically 30+) — one per distinct page kind.** A web app",
        "  catalog with thousands of URLs always has dozens of semantic page kinds (list",
        "  pages, detail pages, settings, dashboards, admin sections, search, profile, …).",
        "  Do NOT collapse everything into one giant group — that defeats the purpose.",
        "- Each group's `semantic_template` generalizes its members with named slots",
        "  (e.g., `/{project_path}/-/issues`). Use descriptive slot names, NOT `slot_0`.",
        "- Different page kinds (sibling resource sections under a common admin/explore",
        "  prefix) are usually distinct groups, even if URL structures look alike.",
        "- For each group, provide `expected_query_params` — query keys the page semantically",
        "  accepts (filter/sort/pagination for list pages, query/scope for search pages).",
        "  Crawler may have missed some; this fills gaps. Only include params justifiable",
        "  from the page kind, not invented.",
        "",
        "## Observed crawl StatePatterns",
    ]
    for sp_id, sp in crawl_kg.state_patterns.items():
        params = ",".join(p.name for p in sp.identity_query_params) or "-"
        lines.append(f"id={sp_id} url={sp.url_template} q=[{params}]")
    if not crawl_kg.state_patterns:
        lines.append("(none observed)")
    return "\n".join(lines)


def _derive_state_pattern_groups(
    crawl_kg: SiteKG, llm: "LLMClient",
) -> tuple[list[StatePatternGroup], str, dict]:
    """Call 1: 모든 crawl StatePattern을 의미 그룹으로 cluster."""
    system = _build_groups_prompt(crawl_kg)
    tool = _build_groups_tool()
    user = "Cluster the crawler-observed StatePatterns by calling derive_state_pattern_groups once."
    try:
        resp = llm.complete_with_tools(
            system=system, messages=[{"role": "user", "content": user}],
            tools=[tool], max_tokens=65536, reasoning_effort=_REASONING_EFFORT,
        )
    except Exception:
        logger.exception("[derivation Call 1] LLM call raised")
        return ([], system, {})

    if not resp.tool_calls or resp.tool_calls[0].name != _TOOL_GROUPS:
        logger.info("[derivation Call 1] no/unexpected tool call")
        return ([], system, {})

    args = resp.tool_calls[0].arguments if isinstance(resp.tool_calls[0].arguments, dict) else {}
    groups_raw = args.get("groups") or []
    out: list[StatePatternGroup] = []
    for g in groups_raw:
        if not isinstance(g, dict) or not g.get("semantic_template"):
            continue
        members = [m for m in (g.get("member_ids") or []) if m in crawl_kg.state_patterns]
        if not members:
            continue
        eqp_raw = g.get("expected_query_params") or []
        eqp: list[dict[str, Any]] = []
        for item in eqp_raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                eqp.append({"name": name, "type": str(item.get("type") or "string")})
        out.append(StatePatternGroup(
            semantic_template=str(g["semantic_template"]).strip(),
            path_params=dict(g.get("path_params") or {}),
            member_ids=members,
            expected_query_params=eqp,
            reasoning=str(g.get("reasoning") or "").strip(),
        ))
    return (out, system, args)


# ---------------------------------------------------------------------------
# Multi-call decomposition: Call 2 — InfoType naming + realize
# ---------------------------------------------------------------------------

def _build_infotypes_tool() -> dict[str, Any]:
    return {
        "name": _TOOL_INFOTYPES,
        "description": (
            "Define InfoTypes (semantic domain-noun catalog) covering the given "
            "StatePattern groups. Each InfoType.realizes references one or more group_id "
            "with optional condition (default | has_filter) and binding_map."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "infotypes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "required_bindings": {
                                "type": "array", "items": {"type": "string"},
                            },
                            "optional_bindings": {
                                "type": "array", "items": {"type": "string"},
                            },
                            "intent_examples": {
                                "type": "array", "items": {"type": "string"},
                            },
                            "realizes": {
                                "type": "array",
                                "description": (
                                    "Each item references a group by its group_id (G0, G1, …) "
                                    "from the input. Use `condition: 'has_filter'` for filter "
                                    "modes; binding_map maps each binding name to a slot/query "
                                    "param of the target group."
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "group_id": {"type": "string"},
                                        "condition": {
                                            "type": "string",
                                            "enum": ["default", "has_filter"],
                                        },
                                        "binding_map": {
                                            "type": "object",
                                            "additionalProperties": {"type": "string"},
                                        },
                                    },
                                    "required": ["group_id"],
                                },
                            },
                        },
                        "required": ["name", "description", "realizes"],
                    },
                },
            },
            "required": ["infotypes"],
        },
    }


def _build_infotypes_prompt(groups: list[StatePatternGroup]) -> str:
    lines = [
        "You define InfoTypes (semantic domain-nouns) covering the StatePattern groups below.",
        "",
        "## Output contract (call derive_infotypes exactly once)",
        "- One InfoType per concept. snake_case names. NOT brand-specific.",
        "- `realizes` is **1:N**: the same InfoType can be satisfied by multiple groups.",
        "  - (a) Different page paths offering the same info differently (default vs curated subset).",
        "  - (b) Same path with a meaningfully different filter mode (use `condition: 'has_filter'`",
        "    and a non-empty `binding_map` linking each binding to a slot/query param).",
        "  Aim for explicit 1:N coverage where the catalog supports it.",
        "- `binding_map` MUST link each binding to a slot/query param in the target group.",
        "",
        "## Available StatePattern groups",
    ]
    for idx, g in enumerate(groups):
        gid = f"G{idx}"
        slots = sorted(g.path_params.keys())
        eqp = sorted(p.get("name", "") for p in g.expected_query_params)
        lines.append(
            f"group_id={gid} url={g.semantic_template} slots={slots} "
            f"expected_query=[{','.join(eqp) or '-'}] members={len(g.member_ids)}"
        )
    if not groups:
        lines.append("(no groups)")
    return "\n".join(lines)


def _derive_infotypes(
    crawl_kg: SiteKG, groups: list[StatePatternGroup], llm: "LLMClient",
) -> tuple[list[InfoType], str, dict]:
    """Call 2: groups를 input으로 InfoType + realize 도출."""
    if not groups:
        return ([], "(skipped — no groups)", {})

    system = _build_infotypes_prompt(groups)
    tool = _build_infotypes_tool()
    user = (
        "Below are the semantic StatePattern groups. Define the InfoType catalog by "
        "calling derive_infotypes once. Use the `group_id` (G0, G1, …) in realizes."
    )
    try:
        resp = llm.complete_with_tools(
            system=system, messages=[{"role": "user", "content": user}],
            tools=[tool], max_tokens=32768, reasoning_effort=_REASONING_EFFORT,
        )
    except Exception:
        logger.exception("[derivation Call 2] LLM call raised")
        return ([], system, {})

    if not resp.tool_calls or resp.tool_calls[0].name != _TOOL_INFOTYPES:
        logger.info("[derivation Call 2] no/unexpected tool call")
        return ([], system, {})

    args = resp.tool_calls[0].arguments if isinstance(resp.tool_calls[0].arguments, dict) else {}
    its_raw = args.get("infotypes") or []

    # group_id (G0, G1, …) → 첫 sample crawl id (post-processor가 group으로 resolve)
    gid_to_sample: dict[str, str] = {}
    for idx, g in enumerate(groups):
        if g.member_ids:
            gid_to_sample[f"G{idx}"] = g.member_ids[0]

    out: list[InfoType] = []
    for it_raw in its_raw:
        if not isinstance(it_raw, dict) or not it_raw.get("name"):
            continue
        name = str(it_raw["name"]).strip()
        realizes: list[RealizesEdge] = []
        for r in it_raw.get("realizes") or []:
            if not isinstance(r, dict):
                continue
            gid = str(r.get("group_id") or "").strip()
            sample_id = gid_to_sample.get(gid)
            if sample_id is None:
                logger.warning("[derivation Call 2] InfoType %r realizes unknown group %r",
                               name, gid)
                continue
            realizes.append(RealizesEdge(
                infotype=name,
                state_pattern_id=sample_id,  # derivation_to_kg가 group으로 resolve
                condition=r.get("condition", "default"),
                binding_map=dict(r.get("binding_map") or {}),
                trust="inferred",
                source="llm",
            ))
        out.append(InfoType(
            name=name,
            description=str(it_raw.get("description", "")).strip(),
            required_bindings=list(it_raw.get("required_bindings") or []),
            optional_bindings=list(it_raw.get("optional_bindings") or []),
            realizes=realizes,
            intent_examples=list(it_raw.get("intent_examples") or []),
            trust_label="inferred",
            source="llm",
        ))
    return (out, system, args)


# ---------------------------------------------------------------------------
# Multi-call decomposition: Call 3 — action renames
# ---------------------------------------------------------------------------

def _build_action_renames_tool() -> dict[str, Any]:
    return {
        "name": _TOOL_ACTIONS,
        "description": (
            "Rename crawler-observed actions (crawl:nav, crawl:form:*) to semantic "
            "verb-phrase names where the rename is obvious from the input name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "renames": {
                    "type": "array",
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
            "required": ["renames"],
        },
    }


def _build_actions_prompt(crawl_kg: SiteKG) -> str:
    """Action listing은 기존 build_derivation_system_prompt와 동일 (input-name aggregated)."""
    from collections import defaultdict as _dd
    lines = [
        "You rename crawler-observed actions to semantic verb-phrase names.",
        "",
        "## Output contract (call derive_action_renames exactly once)",
        "- **`original_name` MUST be a full action name from the catalog below**, e.g.,",
        "  `crawl:form:search:search` or `crawl:nav`. NOT just an input name.",
        "  When using the input-name aggregated form (e.g., `input='search' samples=[...]`),",
        "  pick one of the listed sample full names as `original_name`.",
        "- Map only when the rename is obvious from the input name and page slug.",
        "- Skip ambiguous or generic ones (omit them — post-processor keeps them as crawl:*).",
        "- `semantic_name` uses verb_phrase (e.g., `set_search_query`, `filter_by_state`).",
        "",
        "## Observed actions (input-name aggregated)",
    ]
    if not crawl_kg.actions:
        lines.append("(none)")
        return "\n".join(lines)
    by_input: _dd[str, list[str]] = _dd(list)
    non_form: list[tuple[str, Any]] = []
    for n, a in crawl_kg.actions.items():
        if n.startswith("crawl:form:"):
            parts = n.split(":", 3)
            input_name = parts[3] if len(parts) > 3 else "?"
            by_input[input_name].append(n)
        else:
            non_form.append((n, a))
    for n, a in non_form:
        params = ",".join(p.get("name", "?") for p in a.params) or "-"
        lines.append(f"name={n} params=[{params}]")
    for input_name, acts in sorted(by_input.items()):
        n_acts = len(acts)
        samples = acts[:3]
        sample_str = ", ".join(samples)
        if n_acts > 3:
            lines.append(
                f"input={input_name!r} count={n_acts} samples=[{sample_str}, …(+{n_acts-3} more)]"
            )
        else:
            lines.append(f"input={input_name!r} count={n_acts} actions=[{sample_str}]")
    return "\n".join(lines)


def _derive_action_renames(
    crawl_kg: SiteKG, llm: "LLMClient",
) -> tuple[dict[str, str], dict[str, Action], str, dict]:
    """Call 3: action_renames + Action 객체 도출."""
    system = _build_actions_prompt(crawl_kg)
    tool = _build_action_renames_tool()
    user = (
        "Below are the crawler-observed actions. Propose semantic renames where obvious "
        "by calling derive_action_renames once. Skip ambiguous ones."
    )
    try:
        resp = llm.complete_with_tools(
            system=system, messages=[{"role": "user", "content": user}],
            tools=[tool], max_tokens=16384, reasoning_effort=_REASONING_EFFORT,
        )
    except Exception:
        logger.exception("[derivation Call 3] LLM call raised")
        return ({}, {}, system, {})

    if not resp.tool_calls or resp.tool_calls[0].name != _TOOL_ACTIONS:
        logger.info("[derivation Call 3] no/unexpected tool call")
        return ({}, {}, system, {})

    args = resp.tool_calls[0].arguments if isinstance(resp.tool_calls[0].arguments, dict) else {}
    renames_raw = args.get("renames") or []
    name_map: dict[str, str] = {}
    actions: dict[str, Action] = {}
    for ar in renames_raw:
        if not isinstance(ar, dict):
            continue
        o = str(ar.get("original_name") or "").strip()
        s = str(ar.get("semantic_name") or "").strip()
        if not o or not s:
            continue
        name_map[o] = s
        existing = crawl_kg.actions.get(o)
        params = list(existing.params) if existing else []
        actions[s] = Action(
            name=s, params=params,
            description=str(ar.get("description") or "").strip(),
            source="llm",
        )
    return (name_map, actions, system, args)
