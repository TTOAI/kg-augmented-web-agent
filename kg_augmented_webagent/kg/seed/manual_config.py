"""site_config.yaml → SiteConfig 어댑터.

YAML 필드 구조와 SiteConfig dataclass 필드명이 다르므로 매핑 수행:
- url_decode: "aggressive" → True
- trailing_slash: "ignore" → True
- fragment_handling: "strip" → True
- case_sensitive: {path, query_key, query_value} → 3 bool 필드
- multi_value_params: {suffix_pattern, explicit} → 2 필드
- identity_tokens: {me: {replacement_key: "a.b"}} → {me: "{{a.b}}"}
- emit_policy: {include_default_values, multi_value_order} → 2 필드
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..types import SiteConfig


def load_site_config(path: str | Path) -> SiteConfig:
    """YAML 파일을 SiteConfig로 로드."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return _adapt_yaml_to_site_config(raw)


def _adapt_yaml_to_site_config(raw: dict[str, Any]) -> SiteConfig:
    case = raw.get("case_sensitive", {}) or {}
    multi = raw.get("multi_value_params", {}) or {}
    emit = raw.get("emit_policy", {}) or {}

    return SiteConfig(
        site=raw.get("site", ""),
        base_url=raw.get("base_url", ""),
        url_decode=_interpret_url_decode(raw.get("url_decode", True)),
        trailing_slash_ignore=_interpret_trailing_slash(raw.get("trailing_slash", "ignore")),
        strip_fragment=_interpret_fragment(raw.get("fragment_handling", "strip")),
        path_case_sensitive=bool(case.get("path", True)),
        query_key_case_sensitive=bool(case.get("query_key", True)),
        query_value_case_sensitive=bool(case.get("query_value", False)),
        decorative_params=list(raw.get("decorative_params", [])),
        multi_value_suffix_pattern=multi.get("suffix_pattern"),
        multi_value_explicit=list(multi.get("explicit", [])),
        identity_tokens=_adapt_identity_tokens(raw.get("identity_tokens", {}) or {}),
        path_aliases=[list(group) for group in raw.get("path_aliases", []) or []],
        emit_include_default_values=bool(emit.get("include_default_values", True)),
        emit_multi_value_sorted=(emit.get("multi_value_order", "alphabetical") == "alphabetical"),
    )


def _interpret_url_decode(value: Any) -> bool:
    """'aggressive' 문자열 또는 bool을 True/False로 해석."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("aggressive", "true", "on", "yes", "1")
    return True


def _interpret_trailing_slash(value: Any) -> bool:
    """'ignore'|'strip' → True, 'keep'|'strict' → False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("ignore", "strip", "true", "on", "yes", "1")
    return True


def _interpret_fragment(value: Any) -> bool:
    """'strip'|'ignore' → True, 'keep' → False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("strip", "ignore", "true", "on", "yes", "1")
    return True


def _adapt_identity_tokens(raw: dict[str, Any]) -> dict[str, str]:
    """YAML의 {token: {replacement_key: "a.b"}} → {token: "{{a.b}}"}.

    이미 string 형태 "{{...}}"이면 그대로 사용.
    """
    result: dict[str, str] = {}
    for token, value in raw.items():
        if isinstance(value, str):
            result[token] = value if "{{" in value else "{{" + value + "}}"
        elif isinstance(value, dict):
            key = value.get("replacement_key")
            if key:
                result[token] = "{{" + str(key) + "}}"
    return result
