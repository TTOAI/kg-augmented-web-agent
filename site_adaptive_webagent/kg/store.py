"""In-memory KG 저장소 + JSON round-trip.

M2 범위: CRUD + lookup + JSON serialize/deserialize.
M2b 이후에서 trust 업데이트, 수동 패치 API 등이 추가될 수 있음.

의미론:
- SiteKG dataclass가 저장 구조. Store는 얇은 wrapper로 조회·검증 편의 제공.
- JSON 직렬화 포맷은 config/sites/<site>/kg_seed.json과 호환.
"""
from __future__ import annotations

import json
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any

from .types import (
    Action,
    IdentityParam,
    InfoType,
    LeadsToEdge,
    RealizesEdge,
    SiteKG,
    Source,
    StatePattern,
)

# Source-based merge 우선순위. 높을수록 우선.
_SOURCE_PRIORITY: dict[str, int] = {"crawl": 3, "manual": 2, "llm": 1}


class SiteKGStore:
    """SiteKG wrapper. lookup 편의 + 간단한 validation."""

    def __init__(self, kg: SiteKG) -> None:
        self.kg = kg

    # ------ 조회 ------

    def get_state_pattern(self, pattern_id: str) -> StatePattern | None:
        return self.kg.state_patterns.get(pattern_id)

    def get_infotype(self, name: str) -> InfoType | None:
        return self.kg.infotypes.get(name)

    def get_action(self, name: str) -> Action | None:
        return self.kg.actions.get(name)

    def realizes_edges_for(self, infotype_name: str) -> list[RealizesEdge]:
        """infotype_name에서 시작하는 realizes 엣지들."""
        return [e for e in self.kg.realizes_edges if e.infotype == infotype_name]

    def leads_to_edges_from(self, state_pattern_id: str) -> list[LeadsToEdge]:
        return [e for e in self.kg.leads_to_edges if e.from_state_pattern_id == state_pattern_id]

    # ------ 수정 ------

    def add_state_pattern(self, pattern: StatePattern) -> None:
        if pattern.id in self.kg.state_patterns:
            raise ValueError(f"state_pattern id 중복: {pattern.id!r}")
        self.kg.state_patterns[pattern.id] = pattern

    def add_infotype(self, infotype: InfoType) -> None:
        if infotype.name in self.kg.infotypes:
            raise ValueError(f"infotype name 중복: {infotype.name!r}")
        self.kg.infotypes[infotype.name] = infotype
        # realizes flat list 동기화
        for e in infotype.realizes:
            self.kg.realizes_edges.append(e)

    def add_action(self, action: Action) -> None:
        if action.name in self.kg.actions:
            raise ValueError(f"action name 중복: {action.name!r}")
        self.kg.actions[action.name] = action

    def add_leads_to_edge(self, edge: LeadsToEdge) -> None:
        self.kg.leads_to_edges.append(edge)

    # ------ Merge ------

    def merge(self, other: SiteKG) -> None:
        """다른 SiteKG를 현재 KG에 in-place 병합.

        Source 우선순위 (crawl > manual > llm)를 따라 동일 key에서 높은 source가
        기존 값을 덮어쓴다. 같은 우선순위면 기존 값 유지 (첫 기록 우선).

        - state_patterns: id 기준
        - infotypes: name 기준 (realizes는 source 우선순위 재평가 후 InfoType 단위 교체)
        - actions: name 기준
        - realizes_edges / leads_to_edges: flat list이므로 중복 제거 (from/to/action/infotype/state_pattern_id + condition 기준)
        """
        for sp in other.state_patterns.values():
            existing = self.kg.state_patterns.get(sp.id)
            if existing is None or _source_rank(sp.source) > _source_rank(existing.source):
                self.kg.state_patterns[sp.id] = sp

        for act in other.actions.values():
            existing_act = self.kg.actions.get(act.name)
            if existing_act is None or _source_rank(act.source) > _source_rank(existing_act.source):
                self.kg.actions[act.name] = act

        for it in other.infotypes.values():
            existing_it = self.kg.infotypes.get(it.name)
            if existing_it is None or _source_rank(it.source) > _source_rank(existing_it.source):
                self.kg.infotypes[it.name] = it

        # Flat edge lists: merge by key, keep higher-source on conflict
        self.kg.realizes_edges = _merge_edges(
            self.kg.realizes_edges,
            other.realizes_edges,
            key=lambda e: (e.infotype, e.state_pattern_id, e.condition),
            source_of=lambda e: e.source,
        )
        self.kg.leads_to_edges = _merge_edges(
            self.kg.leads_to_edges,
            other.leads_to_edges,
            key=lambda e: (e.from_state_pattern_id, e.action_name, e.to_state_pattern_id),
            source_of=lambda e: e.source,
        )

        # source_mix 재계산
        from .seed.seed_loader import compute_source_mix

        self.kg.source_mix = compute_source_mix(self.kg)

    # ------ Validation ------

    def validate(self) -> list[str]:
        """참조 무결성 체크. 문제 목록 반환 (빈 리스트면 OK).

        검사 항목:
        - realizes_edges의 infotype / state_pattern_id 존재 여부
        - leads_to_edges의 from/to state_pattern_id 존재 여부
        - leads_to_edges의 action_name 존재 여부
        - InfoType.realizes의 state_pattern_id 존재 여부
        """
        issues: list[str] = []
        for e in self.kg.realizes_edges:
            if e.infotype not in self.kg.infotypes:
                issues.append(f"realizes: unknown infotype={e.infotype!r}")
            if e.state_pattern_id not in self.kg.state_patterns:
                issues.append(f"realizes: unknown state_pattern={e.state_pattern_id!r}")
        for e in self.kg.leads_to_edges:
            if e.from_state_pattern_id not in self.kg.state_patterns:
                issues.append(f"leads_to: unknown from={e.from_state_pattern_id!r}")
            if e.to_state_pattern_id and e.to_state_pattern_id not in self.kg.state_patterns:
                issues.append(f"leads_to: unknown to={e.to_state_pattern_id!r}")
            if e.action_name and e.action_name not in self.kg.actions:
                issues.append(f"leads_to: unknown action={e.action_name!r}")
        for it in self.kg.infotypes.values():
            for r in it.realizes:
                if r.state_pattern_id not in self.kg.state_patterns:
                    issues.append(
                        f"InfoType {it.name!r}.realizes: unknown state_pattern={r.state_pattern_id!r}"
                    )
        return issues

    # ------ Serialization ------

    def to_json(self) -> dict[str, Any]:
        """SiteKG를 JSON-호환 dict로 직렬화.

        kg_seed.json 포맷과 최대한 근접하게. 단, flat realizes_edges는
        InfoType.realizes로부터 유도되므로 중복 저장 대신 각 InfoType 안에만 직렬화.
        """
        return {
            "site": self.kg.site,
            "build_timestamp": self.kg.build_timestamp,
            "builder_version": self.kg.builder_version,
            "source_mix": dict(self.kg.source_mix),
            "state_patterns": [_dc_to_dict(p) for p in self.kg.state_patterns.values()],
            "infotypes": [_dc_to_dict(it) for it in self.kg.infotypes.values()],
            "actions": [_dc_to_dict(a) for a in self.kg.actions.values()],
            "leads_to_edges": [_dc_to_dict(e) for e in self.kg.leads_to_edges],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SiteKGStore":
        kg = SiteKG(
            site=data.get("site", ""),
            build_timestamp=data.get("build_timestamp"),
            builder_version=data.get("builder_version"),
            source_mix=dict(data.get("source_mix") or {}),
        )
        for p in data.get("state_patterns", []):
            sp = _state_pattern_from_dict(p)
            kg.state_patterns[sp.id] = sp
        for it in data.get("infotypes", []):
            info = _infotype_from_dict(it)
            kg.infotypes[info.name] = info
            kg.realizes_edges.extend(info.realizes)
        for a in data.get("actions", []):
            act = _action_from_dict(a)
            kg.actions[act.name] = act
        for e in data.get("leads_to_edges", []):
            kg.leads_to_edges.append(_leads_to_from_dict(e))
        return cls(kg)

    @classmethod
    def load(cls, path: str | Path) -> "SiteKGStore":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_json(data)


# ---------------------------------------------------------------------------
# Helpers: dataclass ↔ dict (slots=True 호환)
# ---------------------------------------------------------------------------

def _dc_to_dict(obj: Any) -> Any:
    """slots=True dataclass를 포함해 nested dict 변환."""
    if is_dataclass(obj):
        return {f.name: _dc_to_dict(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, list):
        return [_dc_to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dc_to_dict(v) for k, v in obj.items()}
    return obj


def _identity_param_from_dict(d: dict[str, Any]) -> IdentityParam:
    return IdentityParam(
        name=d["name"],
        type=d.get("type", "string"),
        values=d.get("values"),
        default=d.get("default"),
        default_trust=d.get("default_trust", "declared"),
        required=d.get("required", False),
    )


def _state_pattern_from_dict(d: dict[str, Any]) -> StatePattern:
    params = [_identity_param_from_dict(p) for p in d.get("identity_query_params", [])]
    return StatePattern(
        id=d["id"],
        url_template=d["url_template"],
        path_params=dict(d.get("path_params", {})),
        identity_query_params=params,
        canonical_emit_order=list(d.get("canonical_emit_order", [])),
        url_template_trust=d.get("url_template_trust", "declared"),
        source=_coerce_source(d.get("source", "manual")),
    )


def _realizes_edge_from_dict(d: dict[str, Any]) -> RealizesEdge:
    return RealizesEdge(
        infotype=d["infotype"],
        state_pattern_id=d["state_pattern_id"],
        condition=d.get("condition", "default"),
        binding_map=dict(d.get("binding_map", {})),
        trust=d.get("trust", "declared"),
        source=_coerce_source(d.get("source", "manual")),
    )


def _infotype_from_dict(d: dict[str, Any]) -> InfoType:
    realizes = []
    for r in d.get("realizes", []):
        # InfoType.realizes 안에는 infotype 필드가 없을 수 있음 — InfoType.name으로 채움
        r_copy = {**r, "infotype": r.get("infotype", d["name"])}
        realizes.append(_realizes_edge_from_dict(r_copy))
    return InfoType(
        name=d["name"],
        description=d.get("description", ""),
        required_bindings=list(d.get("required_bindings", [])),
        optional_bindings=list(d.get("optional_bindings", [])),
        realizes=realizes,
        intent_examples=list(d.get("intent_examples", [])),
        trust_label=d.get("trust_label", "declared"),
        source=_coerce_source(d.get("source", "manual")),
    )


def _action_from_dict(d: dict[str, Any]) -> Action:
    return Action(
        name=d["name"],
        params=list(d.get("params", [])),
        description=d.get("description", ""),
        source=_coerce_source(d.get("source", "manual")),
    )


def _leads_to_from_dict(d: dict[str, Any]) -> LeadsToEdge:
    return LeadsToEdge(
        from_state_pattern_id=d["from_state_pattern_id"],
        from_bindings=list(d.get("from_bindings", [])),
        action_name=d.get("action_name", ""),
        to_state_pattern_id=d.get("to_state_pattern_id", ""),
        to_bindings=list(d.get("to_bindings", [])),
        trust=d.get("trust", "declared"),
        source=_coerce_source(d.get("source", "manual")),
    )


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def _source_rank(source: str) -> int:
    return _SOURCE_PRIORITY.get(source, 0)


def _coerce_source(value: Any) -> Source:
    s = str(value) if value is not None else "manual"
    if s not in ("crawl", "llm", "manual"):
        return "manual"
    return s  # type: ignore[return-value]


def _merge_edges(base, incoming, key, source_of):
    """edge list를 key-based로 병합. 동일 key에서 source_of가 높으면 incoming이 우선."""
    indexed: dict[Any, Any] = {}
    for e in base:
        indexed[key(e)] = e
    for e in incoming:
        k = key(e)
        existing = indexed.get(k)
        if existing is None or _source_rank(source_of(e)) > _source_rank(source_of(existing)):
            indexed[k] = e
    return list(indexed.values())
