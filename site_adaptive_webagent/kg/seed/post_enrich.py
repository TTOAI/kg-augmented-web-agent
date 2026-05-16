"""Post-derivation enrichment — LLM 재호출 없이 schema gap을 자동 채움.

crawl + LLM derivation 결과를 받아, schema가 요구하지만 derivation이 비워둔
필드를 name·regex 기반 heuristic으로 보강한다.

보강 항목:
- binding_map: auto_fill_binding_map
- path_params type: auto_fill_path_params
- identity_query_params: auto_fill_query_params / backfill_query_params_from_form_actions
- InfoType.optional_bindings: backfill_optional_bindings
- InfoType category: assign_infotype_category
- unused form action prune + action description 보강

원칙:
- LLM 재호출 없음 (비용·결정성 유지)
- 사이트·task 특정 어휘 하드코딩 금지 (memory feedback_no_task_site_bias)
- In-place mutation으로 SiteKG enrich
- 모든 enrichment가 trust="inferred" 수준 — reviewer에게 derivation의 연장선으로 설명
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict

from ..types import IdentityParam, InfoType, SiteKG, StatePattern

logger = logging.getLogger("kg.enrich")

# URL template에서 {slot} 추출
_SLOT_RE = re.compile(r"\{([^}]+)\}")


def auto_fill_binding_map(kg: SiteKG) -> int:
    """InfoType.required/optional bindings를 realize edge가 가리키는 StatePattern의
    path slot·query param 이름에 자동 매핑한다.

    매칭 규칙 (우선순위):
    1. Exact name match (e.g., "project_path" ↔ "project_path")
    2. Bare ↔ multi_string suffix ("label_name" ↔ "label_name[]")
    3. Snake ↔ kebab/camel variants

    이미 binding_map이 채워진 edge는 건들지 않음.

    Return: 수정된 edge 수
    """
    modified = 0
    for it in kg.infotypes.values():
        all_bindings = list(it.required_bindings) + list(it.optional_bindings)
        if not all_bindings:
            continue
        for edge in it.realizes:
            if edge.binding_map:
                continue  # 이미 채워져 있음
            target = kg.state_patterns.get(edge.state_pattern_id)
            if target is None:
                continue
            target_slots = set(target.path_params.keys())
            target_slots.update(p.name for p in target.identity_query_params)
            auto_map: dict[str, str] = {}
            for b in all_bindings:
                match = _match_binding_to_slot(b, target_slots)
                if match:
                    auto_map[b] = match
            if auto_map:
                edge.binding_map = auto_map
                modified += 1
    logger.info("[enrich] binding_map auto-filled: %d edges", modified)
    return modified


def _match_binding_to_slot(binding: str, slots: set[str]) -> str | None:
    if binding in slots:
        return binding
    # bare → [] suffix
    if f"{binding}[]" in slots:
        return f"{binding}[]"
    # [] suffix → bare
    if binding.endswith("[]") and binding[:-2] in slots:
        return binding[:-2]
    return None


def auto_fill_path_params(kg: SiteKG) -> int:
    """StatePattern의 url_template에서 {slot}을 추출해 path_params를 채움.

    Slot type 추론 규칙:
    - "*_path" ending → `path_segments` (여러 segment, 예: "group/subgroup/leaf")
    - 그 외 → `segment` (단일 URL segment)

    이미 해당 slot에 type이 지정돼 있으면 overwrite하지 않음.

    Return: 수정된 StatePattern 수
    """
    modified = 0
    for sp in kg.state_patterns.values():
        slots = _SLOT_RE.findall(sp.url_template)
        if not slots:
            continue
        changed = False
        for slot in slots:
            existing = sp.path_params.get(slot) or {}
            if "type" in existing:
                continue
            inferred_type = "path_segments" if slot.endswith("_path") else "segment"
            existing["type"] = inferred_type
            sp.path_params[slot] = existing
            changed = True
        if changed:
            modified += 1
    logger.info("[enrich] path_params auto-filled: %d state_patterns", modified)
    return modified


_ENUM_HINTS = {"state", "scope", "sort", "order", "direction", "status", "visibility"}


def auto_fill_query_params(kg: SiteKG) -> int:
    """InfoType.optional_bindings를 대응 StatePattern의 identity_query_params에 추가.

    규칙:
    - InfoType.optional_bindings의 각 이름 b가 대응 StatePattern의 path slot이 아니면
      query param 후보로 간주한다.
    - 이미 같은 name의 query param이 있으면 skip.
    - type 추론:
      * 이름이 `[]` 로 끝나면 `multi_string`
      * 이름이 _ENUM_HINTS 세트에 포함되거나 그 이름으로 끝나면 `enum` (values는 비워둠 — 후속 manual·LLM 보강)
      * `*_id` / `*_ids` → `int` 또는 `multi_string`
      * 그 외 → `string`

    Return: 수정된 (InfoType, StatePattern) pair 수
    """
    modified = 0
    for it in kg.infotypes.values():
        if not it.optional_bindings:
            continue
        for edge in it.realizes:
            target = kg.state_patterns.get(edge.state_pattern_id)
            if target is None:
                continue
            existing_names = {p.name for p in target.identity_query_params}
            path_slots = set(target.path_params.keys())
            added = False
            for b in it.optional_bindings:
                slot_form = _match_binding_to_slot(b, existing_names | path_slots)
                if slot_form is not None:
                    continue  # 이미 path/query에 있음
                qname = b if not b.endswith("[]") else b
                if qname in existing_names:
                    continue
                target.identity_query_params.append(
                    IdentityParam(
                        name=qname,
                        type=_infer_param_type(qname),
                        required=False,
                    )
                )
                if qname not in target.canonical_emit_order:
                    target.canonical_emit_order.append(qname)
                existing_names.add(qname)
                added = True
            if added:
                modified += 1
    logger.info("[enrich] identity_query_params auto-filled: %d (infotype, state) pairs", modified)
    return modified


def _infer_param_type(name: str) -> str:
    low = name.lower()
    if low.endswith("[]"):
        return "multi_string"
    if low in _ENUM_HINTS or any(low.endswith("_" + h) for h in _ENUM_HINTS):
        return "enum"
    if low.endswith("_ids"):
        return "multi_string"
    if low.endswith("_id"):
        return "int"
    return "string"


def assign_infotype_category(kg: SiteKG, min_cluster_size: int = 2) -> int:
    """InfoType 이름의 prefix로 category 자동 부여.

    규칙:
    - 같은 prefix(underscore로 분리된 첫 조각)를 공유하는 InfoType이 `min_cluster_size`
      이상이면 그 prefix를 explicit category로 할당.
    - 그 외는 "misc".

    이미 category가 설정된 InfoType은 건들지 않음.

    Return: 수정된 InfoType 수
    """
    by_prefix: dict[str, list[str]] = defaultdict(list)
    for name in kg.infotypes:
        prefix = name.split("_", 1)[0]
        by_prefix[prefix].append(name)
    categories = {
        prefix: prefix
        for prefix, names in by_prefix.items()
        if len(names) >= min_cluster_size
    }
    modified = 0
    for it in kg.infotypes.values():
        if it.category is not None:
            continue
        prefix = it.name.split("_", 1)[0]
        it.category = categories.get(prefix, "misc")
        modified += 1
    logger.info("[enrich] categories auto-assigned: %d InfoTypes (explicit categories=%d)",
                modified, len(categories))
    return modified


_FORM_ACTION_RE = re.compile(r"^crawl:form:(?P<slug>[^:]+):(?P<input>.+)$")


_FORM_SKIP_INPUTS = {
    "submit", "commit", "ok", "cancel", "_token", "authenticity_token", "utf8",
    "button", "reset", "close", "done",
}


def backfill_query_params_from_form_actions(kg: SiteKG) -> int:
    """`crawl:form:*` action이 연결된 LeadsToEdge에서 input name을 edge의
    to_state_pattern_id에 query param으로 추가.

    crawl_to_kg가 form input마다 edge를 기록하며, target state는 form.action_url에
    기반한 lookup (실패 시 self-loop fallback). edge의 to_state는 "form submit이
    실제로 도착하는 페이지"이므로 query param이 의미적으로 옳은 곳에 박힌다.

    추가로, crawl literal StatePattern에 확보된 input을 그 group에 속한 llm semantic
    StatePattern에도 전파한다 (semantic_template suffix 공유).

    Return: 수정된 StatePattern 수
    """
    # 1. form action이 연결된 edge에서 (target_state_id, input_name) 수집
    state_to_inputs: dict[str, set[str]] = defaultdict(set)
    for le in kg.leads_to_edges:
        m = _FORM_ACTION_RE.match(le.action_name)
        if not m:
            continue
        input_name = m.group("input").strip()
        if not input_name or input_name.lower() in _FORM_SKIP_INPUTS:
            continue
        state_to_inputs[le.to_state_pattern_id].add(input_name)

    if not state_to_inputs:
        logger.info("[enrich] form→query backfill: no form edges found")
        return 0

    # 2. 직접 매핑: form edge의 from state에 query param 추가
    modified = 0
    for state_id, input_names in state_to_inputs.items():
        sp = kg.state_patterns.get(state_id)
        if sp is None:
            continue
        if _add_inputs_as_query_params(sp, input_names):
            modified += 1

    # 3. literal tail segment 기반 suffix 매칭으로 전파.
    # slot(`{...}`)을 가진 template에서 뒤쪽 연속 literal segment를 suffix로 추출하고,
    # 다른 template (literal 포함)의 url_template이 그 suffix로 endsWith하면
    # 같은 resource type으로 보고 query param을 전파한다. 사이트별 separator
    # (`/-/`, `/u/` 등)에 의존하지 않는 일반화 규칙.
    suffix_to_sps: dict[str, list[StatePattern]] = {}
    for sp in kg.state_patterns.values():
        suffix = _extract_literal_suffix(sp.url_template)
        if suffix:
            suffix_to_sps.setdefault(suffix, []).append(sp)

    # 각 seed state(form 관찰)에서 나온 inputs을 endsWith 매칭되는 target sp에 전파
    for state_id, inputs in state_to_inputs.items():
        seed = kg.state_patterns.get(state_id)
        if seed is None:
            continue
        for suffix, targets in suffix_to_sps.items():
            if not seed.url_template.endswith(suffix):
                continue
            for target in targets:
                if target.id == seed.id:
                    continue
                existing = {p.name for p in target.identity_query_params}
                new_inputs = inputs - existing
                if new_inputs and _add_inputs_as_query_params(target, new_inputs):
                    modified += 1

    logger.info(
        "[enrich] form→query backfill: %d StatePatterns enriched "
        "(%d distinct form states)",
        modified, len(state_to_inputs),
    )
    return modified


def _extract_literal_suffix(url_template: str) -> str:
    """url_template의 뒤쪽 연속 literal segment를 slash-prefixed suffix로 반환.

    뒤에서부터 segment를 훑어 slot(`{...}`)을 만나기 전까지 literal만 취합.
    suffix가 비거나 1개 segment뿐이면 too-generic으로 간주해 빈 문자열 반환 →
    "모든 path에 match"되어 잘못 전파하는 것을 방지.
    """
    segments = [s for s in url_template.strip("/").split("/") if s]
    literal_tail: list[str] = []
    for seg in reversed(segments):
        if seg.startswith("{") and seg.endswith("}"):
            break
        literal_tail.append(seg)
    if len(literal_tail) < 2:
        return ""
    return "/" + "/".join(reversed(literal_tail))


def _add_inputs_as_query_params(sp: StatePattern, input_names) -> bool:
    existing = {p.name for p in sp.identity_query_params}
    added = False
    for name in input_names:
        if name in existing:
            continue
        sp.identity_query_params.append(
            IdentityParam(name=name, type=_infer_param_type(name), required=False)
        )
        if name not in sp.canonical_emit_order:
            sp.canonical_emit_order.append(name)
        existing.add(name)
        added = True
    return added


def backfill_optional_bindings(kg: SiteKG) -> int:
    """각 InfoType의 realize target StatePattern이 가진 query params 이름을
    해당 InfoType의 optional_bindings에 backfill한다 (중복·required 제외).

    근원적으로 "InfoType이 어떤 binding을 받을 수 있는가"는 "realize하는 StatePattern의
    식별 query param"과 동일해야 함. 현재 LLM derivation은 InfoType.optional_bindings를
    대부분 빈 list로 냄 → StatePattern에서 역투영.
    """
    modified = 0
    for it in kg.infotypes.values():
        before = set(it.optional_bindings)
        required = set(it.required_bindings)
        new_opt = list(it.optional_bindings)
        for edge in it.realizes:
            target = kg.state_patterns.get(edge.state_pattern_id)
            if target is None:
                continue
            for p in target.identity_query_params:
                bare = p.name[:-2] if p.name.endswith("[]") else p.name
                if bare in required or bare in before:
                    continue
                if bare in new_opt:
                    continue
                new_opt.append(bare)
        if set(new_opt) != before:
            it.optional_bindings = new_opt
            modified += 1
    logger.info(
        "[enrich] InfoType.optional_bindings backfilled: %d InfoTypes",
        modified,
    )
    return modified


def prune_unused_form_actions(kg: SiteKG) -> int:
    """LeadsToEdge에 한 번도 참조되지 않는 `crawl:form:*` action을 catalog에서 제거.

    crawl_to_kg에서 form input 별로 action을 만들었지만 LeadsToEdge는 거의 없음
    (crawler는 form submit 후 target state를 확정할 수 없음). 이 dead weight를
    제거해 catalog와 edge 사용의 괴리를 해소.

    Return: 제거된 action 수
    """
    used_names = {le.action_name for le in kg.leads_to_edges}
    removed = 0
    for name in list(kg.actions.keys()):
        if name.startswith("crawl:form:") and name not in used_names:
            del kg.actions[name]
            removed += 1
    logger.info("[enrich] unused form actions pruned: %d", removed)
    return removed


def auto_fill_action_descriptions(kg: SiteKG) -> int:
    """빈 description인 Action에 name 기반 자동 설명 추가.

    - `crawl:nav` → "Generic navigation transition observed by crawler."
    - semantic action (crawl: prefix 없음) 중 빈 것 → "Semantic action; inferred from
      LLM derivation over crawler observations."
    - `crawl:form:<slug>:<input>` → "Form input '<input>' observed on page
      '/<slug-as-path>'; submit transitions to a derived page state."
    """
    modified = 0
    for act in kg.actions.values():
        if (act.description or "").strip():
            continue
        name = act.name
        if name == "crawl:nav":
            act.description = "Generic navigation transition observed by crawler."
        elif name.startswith("crawl:form:"):
            m = _FORM_ACTION_RE.match(name)
            slug = m.group("slug") if m else "?"
            input_name = m.group("input") if m else "?"
            path_guess = slug.replace("_", "/")
            act.description = (
                f"Form input {input_name!r} observed on page '/{path_guess}'; "
                "form submit transitions to a derived page state."
            )
        else:
            act.description = (
                "Semantic action derived from LLM-level interpretation of crawler "
                "observations; trust=inferred."
            )
        modified += 1
    logger.info("[enrich] action descriptions auto-filled: %d", modified)
    return modified


def enrich(kg: SiteKG) -> dict[str, int]:
    """모든 enrichment helper를 순서대로 적용.

    주의: 의존 순서 — path_params 먼저 (slot 식별), 그 다음 form→query 역투영,
    그 다음 optional_bindings backfill, 마지막 binding_map. 이 순서로 가야
    뒤에서 앞 단계의 산출을 활용.
    """
    summary = {
        "path_params": auto_fill_path_params(kg),
        "form_backfill": backfill_query_params_from_form_actions(kg),
        "query_params": auto_fill_query_params(kg),
        "optional_backfill": backfill_optional_bindings(kg),
        "binding_map": auto_fill_binding_map(kg),
        "category": assign_infotype_category(kg),
        "prune_form_actions": prune_unused_form_actions(kg),
        "action_descriptions": auto_fill_action_descriptions(kg),
    }
    logger.info("[enrich] summary: %s", summary)
    return summary
