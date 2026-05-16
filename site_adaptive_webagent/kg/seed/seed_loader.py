"""kg_seed.json → SiteKG 로더 + 3 파일 통합 로더.

kg_seed.json의 포맷은 `config/sites/gitlab/kg_seed.json` 참조.
InfoType은 infotypes.yaml에서 별도 로드하므로 여기서는 StatePatterns/Actions/
realizes_edges/leads_to_edges만 읽는다.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..types import (
    Action,
    IdentityParam,
    InfoType,
    LeadsToEdge,
    RealizesEdge,
    SiteConfig,
    SiteKG,
    Source,
    StatePattern,
)
from .infotype_catalog import load_infotypes
from .manual_config import load_site_config

BUILDER_VERSION = "0.1.0-hybrid"


def load_kg_seed(path: str | Path) -> SiteKG:
    """kg_seed.json 단독 로드. infotypes는 빈 상태로 반환.

    통합 로드는 `load_site_kg_from_dir` 사용.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    kg = SiteKG(site=raw.get("site", ""))

    for sp_dict in raw.get("state_patterns", []) or []:
        sp = _adapt_state_pattern(sp_dict)
        kg.state_patterns[sp.id] = sp

    for act_dict in raw.get("actions", []) or []:
        act = Action(
            name=act_dict["name"],
            params=list(act_dict.get("params", []) or []),
            description=act_dict.get("description", ""),
            source=_coerce_source(act_dict.get("source", "manual")),
        )
        kg.actions[act.name] = act

    for r_dict in raw.get("realizes_edges", []) or []:
        kg.realizes_edges.append(
            RealizesEdge(
                infotype=r_dict["infotype"],
                state_pattern_id=r_dict["state_pattern"],
                condition=r_dict.get("condition", "default"),
                binding_map=dict(r_dict.get("binding_map", {}) or {}),
                trust=r_dict.get("trust", "declared"),
                source=_coerce_source(r_dict.get("source", "manual")),
            )
        )

    for l_dict in raw.get("leads_to_edges", []) or []:
        kg.leads_to_edges.append(_adapt_leads_to_edge(l_dict))

    return kg


def load_site_kg_from_dir(
    dir_path: str | Path,
) -> tuple[SiteConfig, SiteKG]:
    """config/sites/<site>/ 디렉토리에서 site_config.yaml + infotypes.yaml + kg_seed.json을
    모두 로드하여 (SiteConfig, SiteKG)를 반환.

    infotypes.yaml의 InfoType들은 kg_seed.json의 StatePattern/Action과 합쳐져 단일 SiteKG 구성.
    kg_seed.json에서 로드된 realizes_edges와 infotypes.yaml의 InfoType.realizes는
    중복일 수 있으나, InfoType 단위로 관리하고 flat list는 infotypes에서 파생한다.
    """
    dir_p = Path(dir_path)
    site_config = load_site_config(dir_p / "site_config.yaml")
    kg = load_kg_seed(dir_p / "kg_seed.json")
    infotypes = load_infotypes(dir_p / "infotypes.yaml")

    # InfoType 병합. 기존 flat realizes_edges는 덮어씀 (InfoType이 source of truth).
    kg.realizes_edges = []
    for it in infotypes:
        kg.infotypes[it.name] = it
        kg.realizes_edges.extend(it.realizes)

    # Build metadata
    kg.build_timestamp = datetime.now(tz=timezone.utc).isoformat()
    kg.builder_version = BUILDER_VERSION
    kg.source_mix = compute_source_mix(kg)

    return site_config, kg


def compute_source_mix(kg: SiteKG) -> dict[str, int]:
    """모든 노드·엣지의 source 필드를 집계하여 {'crawl': n, 'llm': n, 'manual': n} 반환."""
    counter: Counter[str] = Counter()
    for sp in kg.state_patterns.values():
        counter[sp.source] += 1
    for it in kg.infotypes.values():
        counter[it.source] += 1
    for act in kg.actions.values():
        counter[act.source] += 1
    for re_ in kg.realizes_edges:
        counter[re_.source] += 1
    for le in kg.leads_to_edges:
        counter[le.source] += 1
    return {"crawl": counter["crawl"], "llm": counter["llm"], "manual": counter["manual"]}


def _coerce_source(value: Any) -> Source:
    s = str(value) if value is not None else "manual"
    if s not in ("crawl", "llm", "manual"):
        return "manual"
    return s  # type: ignore[return-value]


def _adapt_state_pattern(d: dict[str, Any]) -> StatePattern:
    params = [_adapt_identity_param(p) for p in d.get("identity_query_params", []) or []]
    return StatePattern(
        id=d["id"],
        url_template=d["url_template"],
        path_params=dict(d.get("path_params", {}) or {}),
        identity_query_params=params,
        canonical_emit_order=list(d.get("canonical_emit_order", []) or []),
        url_template_trust=d.get("url_template_trust", "declared"),
        source=_coerce_source(d.get("source", "manual")),
    )


def _adapt_identity_param(d: dict[str, Any]) -> IdentityParam:
    return IdentityParam(
        name=d["name"],
        type=d.get("type", "string"),
        values=d.get("values"),
        default=d.get("default"),
        default_trust=d.get("default_trust", "declared"),
        required=bool(d.get("required", False)),
    )


def _adapt_leads_to_edge(d: dict[str, Any]) -> LeadsToEdge:
    """kg_seed.json의 leads_to 포맷은 아래 두 가지를 모두 허용:

    Style A (평탄):
        {"from_state_pattern_id": "...", "action_name": "...", "to_state_pattern_id": "...", ...}

    Style B (중첩, config 파일의 기본 스타일):
        {"from": {"state_pattern": "...", "bindings": [...]},
         "action": "...",
         "to":   {"state_pattern": "...", "bindings": [...]}, ...}

    내부 LeadsToEdge는 평탄 구조로 통일.
    """
    if "from_state_pattern_id" in d:
        # Style A
        return LeadsToEdge(
            from_state_pattern_id=d["from_state_pattern_id"],
            from_bindings=list(d.get("from_bindings", []) or []),
            action_name=d.get("action_name", ""),
            to_state_pattern_id=d.get("to_state_pattern_id", ""),
            to_bindings=list(d.get("to_bindings", []) or []),
            trust=d.get("trust", "declared"),
            source=_coerce_source(d.get("source", "manual")),
        )
    # Style B
    src = d.get("from", {}) or {}
    dst = d.get("to", {}) or {}
    return LeadsToEdge(
        from_state_pattern_id=src.get("state_pattern", ""),
        from_bindings=list(src.get("bindings", []) or []),
        action_name=d.get("action", ""),
        to_state_pattern_id=dst.get("state_pattern", ""),
        to_bindings=list(dst.get("bindings", []) or []),
        trust=d.get("trust", "declared"),
        source=_coerce_source(d.get("source", "manual")),
    )
