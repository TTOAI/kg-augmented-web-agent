"""KG query primitives.

M2 범위:
- emit_target_url(kg, cfg, infotype_name, bindings, runtime_context=None) → str | None
- state_matches(kg, cfg, current_url, infotype_name, bindings, runtime_context=None) → bool
- simulate_final_state_url(kg, initial_state_id, action_sequence, bindings) → StatePattern | None

M2b에서 추가 예정:
- route_to (full BFS)
"""
from __future__ import annotations

from typing import Any

from .store import SiteKGStore
from .types import RealizesEdge, SiteConfig, SiteKG, StatePattern
from .urlnorm import emit_url, match_pattern


# ---------------------------------------------------------------------------
# 1. emit_target_url — InfoType + bindings → canonical URL
# ---------------------------------------------------------------------------

def emit_target_url(
    kg: SiteKG,
    site_config: SiteConfig,
    infotype_name: str,
    bindings: dict[str, Any],
    runtime_context: dict[str, Any] | None = None,
) -> str | None:
    """InfoType + bindings로부터 canonical URL을 합성.

    흐름:
      1. InfoType 조회 → realizes 엣지 목록
      2. bindings·optional_bindings로 condition 판정 (has_filter vs default)
      3. 적절한 realizes 엣지 선택 (has_filter 우선)
      4. binding_map을 적용해 StatePattern bindings 생성
      5. urlnorm.emit_url 호출 → URL 문자열

    실패 (InfoType 없음 / realizes 없음 / StatePattern 없음) 시 None.
    """
    store = SiteKGStore(kg)
    infotype = store.get_infotype(infotype_name)
    if infotype is None:
        return None

    edge = _select_realizes_edge(infotype, bindings)
    if edge is None:
        return None

    pattern = store.get_state_pattern(edge.state_pattern_id)
    if pattern is None:
        return None

    # binding_map 적용: infotype binding → state_pattern binding
    state_bindings = _apply_binding_map_to_pattern(bindings, edge.binding_map, pattern)
    # Phase 2C C2: runtime_context의 path_slots로 빈 slot 보완 (bindings 우선).
    # agent가 현재 페이지 URL에서 자동 추출한 path slot이 있으면 emit_url 호출 전 inject.
    if runtime_context:
        path_slots_ctx = runtime_context.get("path_slots") or {}
        for slot_name, slot_val in path_slots_ctx.items():
            if slot_name in pattern.path_params and slot_name not in state_bindings:
                state_bindings[slot_name] = slot_val
    return emit_url(pattern, state_bindings, site_config)


_TRUST_PRIORITY = {"verified": 3, "declared": 2, "inferred": 1}


def _trust_rank(trust: str) -> int:
    return _TRUST_PRIORITY.get(trust, 0)


def _select_realizes_edge(infotype, bindings: dict[str, Any]) -> RealizesEdge | None:
    """condition + trust에 따라 적절한 realizes 엣지 선택.

    규칙:
    - optional_bindings 중 하나라도 비어있지 않으면 has_filter 우선
    - 같은 condition 안에서는 trust 우선순위 (verified > declared > inferred)
    - has_filter 엣지가 없으면 default로 폴백
    """
    if not infotype.realizes:
        return None

    has_filter = _has_any_filter(bindings, infotype.optional_bindings)

    def _best_by_trust(edges: list[RealizesEdge]) -> RealizesEdge | None:
        if not edges:
            return None
        return max(edges, key=lambda e: _trust_rank(e.trust))

    if has_filter:
        filtered = [e for e in infotype.realizes if e.condition == "has_filter"]
        picked = _best_by_trust(filtered)
        if picked is not None:
            return picked
        # has_filter 엣지가 없으면 default로 폴백
    defaults = [e for e in infotype.realizes if e.condition == "default"]
    picked = _best_by_trust(defaults)
    if picked is not None:
        return picked
    # default도 없으면 전체 중 trust 최고
    return _best_by_trust(list(infotype.realizes))


def _has_any_filter(bindings: dict[str, Any], optional_names: list[str]) -> bool:
    """optional_bindings 중 실제로 값이 있는(비 None·비 empty) 것이 하나라도 있는가."""
    for name in optional_names:
        value = bindings.get(name)
        if value is None:
            continue
        if isinstance(value, (list, tuple, str)) and len(value) == 0:
            continue
        return True
    return False


def _apply_binding_map_to_pattern(
    source_bindings: dict[str, Any],
    binding_map: dict[str, str],
    pattern: StatePattern,
) -> dict[str, Any]:
    """source(InfoType binding) → target(StatePattern binding) 매핑.

    binding_map이 명시돼 있으면 source_name → target_name 형태로 적용.
    비어있으면 pattern의 path_params·identity_query_params 이름과 매칭:
    - target name이 source에 있으면 그대로 사용
    - target name이 `[]` 접미사를 갖고 source에 bare 이름(`foo`)이 있으면 자동 연결
      (예: pattern이 `label_name[]`을 요구하고 source는 `label_name=[...]`)

    이 자동 매핑은 infotypes.yaml에 binding_map을 명시하지 않아도 편의 동작하도록 한다.
    """
    if binding_map:
        result: dict[str, Any] = {}
        for src_name, dst_name in binding_map.items():
            if src_name in source_bindings:
                result[dst_name] = source_bindings[src_name]
        return result

    # Implicit matching
    result = {}
    target_names: set[str] = set()
    for path_slot in pattern.path_params:
        target_names.add(path_slot)
    for p in pattern.identity_query_params:
        target_names.add(p.name)

    for target_name in target_names:
        if target_name in source_bindings:
            result[target_name] = source_bindings[target_name]
        elif target_name.endswith("[]"):
            bare = target_name[:-2]
            if bare in source_bindings:
                result[target_name] = source_bindings[bare]
    return result


# ---------------------------------------------------------------------------
# 2. state_matches — current URL이 target InfoType 상태인지 판정
# ---------------------------------------------------------------------------

def state_matches(
    kg: SiteKG,
    site_config: SiteConfig,
    current_url: str,
    infotype_name: str,
    bindings: dict[str, Any],
    runtime_context: dict[str, Any] | None = None,
) -> bool:
    """현재 URL이 target InfoType+bindings 상태에 해당하는가.

    구현: emit_target_url로 기대 URL 계산 → match_pattern으로 current_url 비교.

    둘 다 같은 StatePattern을 target으로 삼으므로 match_pattern의 bindings가
    target bindings와 같으면 True.
    """
    store = SiteKGStore(kg)
    infotype = store.get_infotype(infotype_name)
    if infotype is None:
        return False

    edge = _select_realizes_edge(infotype, bindings)
    if edge is None:
        return False

    pattern = store.get_state_pattern(edge.state_pattern_id)
    if pattern is None:
        return False

    expected_state_bindings = _apply_binding_map_to_pattern(bindings, edge.binding_map, pattern)

    ok, actual_bindings = match_pattern(current_url, pattern, site_config, runtime_context)
    if not ok:
        return False

    # identity_query_params 기준으로 값 일치 확인 (path params도 포함)
    for key, expected_value in expected_state_bindings.items():
        actual_value = actual_bindings.get(key)
        if not _value_equal(actual_value, expected_value, site_config):
            return False
    return True


def _value_equal(actual: Any, expected: Any, site_config: SiteConfig) -> bool:
    """identity param 값 비교. multi_string은 정렬 후 비교, 단일 값은 case-insensitive 가능."""
    if isinstance(expected, list) or isinstance(actual, list):
        a = sorted([str(x) for x in (actual or [])])
        e = sorted([str(x) for x in (expected or [])])
        if not site_config.query_value_case_sensitive:
            a = [s.lower() for s in a]
            e = [s.lower() for s in e]
        return a == e
    if actual is None and expected is None:
        return True
    if actual is None or expected is None:
        return False
    a_s = str(actual)
    e_s = str(expected)
    if not site_config.query_value_case_sensitive:
        return a_s.lower() == e_s.lower()
    return a_s == e_s


# ---------------------------------------------------------------------------
# 3. simulate_final_state_url — action sequence 시뮬레이션 (기본 구현)
# ---------------------------------------------------------------------------

def simulate_final_state(
    kg: SiteKG,
    initial_state_id: str,
    action_sequence: list[str],
) -> StatePattern | None:
    """leads_to 엣지를 순차 적용해 최종 StatePattern을 반환.

    기본 구현: 각 action에 대해 `from_state_pattern_id == current` and `action_name == action`인
    첫 엣지를 선택해 다음 state로 전이. multi-hop 분기는 미지원 (M2b에서 개선).
    """
    store = SiteKGStore(kg)
    current = store.get_state_pattern(initial_state_id)
    if current is None:
        return None
    for action in action_sequence:
        edges = [
            e for e in store.leads_to_edges_from(current.id)
            if e.action_name == action
        ]
        if not edges:
            return None
        next_pattern = store.get_state_pattern(edges[0].to_state_pattern_id)
        if next_pattern is None:
            return None
        current = next_pattern
    return current
