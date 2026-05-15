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

_TOOL_GROUPS = "derive_state_pattern_groups"
_TOOL_INFOTYPES = "derive_infotypes"
_TOOL_ACTIONS = "derive_action_renames"

# reasoning_effort은 Responses API 경로에서만 적용된다 (chat.completions에선 function
# tools와 동시 사용 불가). LLMClient가 gpt-5* / o-series 모델을 감지하면 자동으로
# Responses API로 분기한다. "low"는 단순 cluster·mapping 작업에 충분하고 latency를
# 크게 단축한다.
_REASONING_EFFORT: str | None = "low"


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
    """Action listing은 input-name aggregated 형식 (`crawl:form:*` 4000+ 폭주 대응)."""
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
