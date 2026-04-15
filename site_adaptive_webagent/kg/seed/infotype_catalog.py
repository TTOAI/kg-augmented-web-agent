"""infotypes.yaml → list[InfoType] 로더.

YAML 필드를 InfoType dataclass로 매핑. realizes는 RealizesEdge 객체로 변환.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..types import InfoType, RealizesEdge


def load_infotypes(path: str | Path) -> list[InfoType]:
    """YAML 파일에서 InfoType 목록을 로드.

    파일 구조:
        version: 1
        site: gitlab
        infotypes:
          - name: ...
            description: ...
            required_bindings: [...]
            optional_bindings: [...]
            realizes:
              - state_pattern: ...
                condition: default | has_filter
                binding_map: {...}   # 선택
            intent_examples: [...]
            trust_label: declared
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [_adapt_yaml_to_infotype(item) for item in raw.get("infotypes", [])]


def _adapt_yaml_to_infotype(d: dict[str, Any]) -> InfoType:
    name = d["name"]
    default_source = _coerce_source(d.get("source", "manual"))
    realizes = []
    for r in d.get("realizes", []) or []:
        realizes.append(
            RealizesEdge(
                infotype=name,
                state_pattern_id=r.get("state_pattern", ""),
                condition=r.get("condition", "default"),
                binding_map=dict(r.get("binding_map", {}) or {}),
                trust=r.get("trust", d.get("trust_label", "declared")),
                source=_coerce_source(r.get("source", default_source)),
            )
        )
    return InfoType(
        name=name,
        description=_strip(d.get("description", "")),
        required_bindings=list(d.get("required_bindings", []) or []),
        optional_bindings=list(d.get("optional_bindings", []) or []),
        realizes=realizes,
        intent_examples=list(d.get("intent_examples", []) or []),
        trust_label=d.get("trust_label", "declared"),
        source=default_source,
    )


def _coerce_source(value: Any) -> str:
    s = str(value) if value is not None else "manual"
    return s if s in ("crawl", "llm", "manual") else "manual"


def _strip(value: Any) -> str:
    """description은 YAML multi-line block이라 whitespace 정리."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())
