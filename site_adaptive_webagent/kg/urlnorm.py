"""URL 정규화·매칭·emit 3 primitive.

핵심 연산:
- normalize_url(url, site_config, runtime_context) → NormalizedURL
- match_pattern(url, pattern, site_config, runtime_context) → (bool, bindings)
- emit_url(pattern, bindings, site_config) → str

NormalizedURL은 내부 구조체. match/emit의 상호 라운드트립 가능해야 한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, quote, unquote, urlparse, urlunparse

from .types import IdentityParam, SiteConfig, StatePattern


# ---------------------------------------------------------------------------
# 내부 구조
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class NormalizedURL:
    """정규화 결과. path + query (identity만) + 제거된 decorative param 집합을 보유."""

    path: str
    query_pairs: list[tuple[str, str]]  # identity param만 (multi-value는 여러 튜플)
    stripped_decorative: list[tuple[str, str]]  # 제거된 decorative param (정보 보존)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_identity_token(value: str, runtime_context: dict | None) -> str:
    """{{path.to.key}} 형식을 runtime_context dict에서 치환.

    예: "{{current_user.username}}" + {"current_user": {"username": "<user>"}}
        → "<user>"
    치환 실패 시 원문 그대로 반환.
    """
    if runtime_context is None:
        return value
    match = re.fullmatch(r"\{\{\s*([^}]+?)\s*\}\}", value.strip())
    if not match:
        return value
    key_path = match.group(1).split(".")
    current: Any = runtime_context
    for key in key_path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return value
    return str(current)


def _apply_identity_tokens_to_path(path: str, site_config: SiteConfig, runtime_context: dict | None) -> str:
    """path 내 /{{token}}/ 형식의 식별 토큰을 치환."""
    if not site_config.identity_tokens or runtime_context is None:
        return path
    for token_name, token_template in site_config.identity_tokens.items():
        resolved = _resolve_identity_token(token_template, runtime_context)
        # /me → /<resolved-user>; /users/me → /users/<resolved-user>
        path = re.sub(rf"(^|/)\s*{re.escape(token_name)}\s*(?=/|$)", rf"\1{resolved}", path)
    return path


def _apply_path_aliases(path: str, site_config: SiteConfig) -> str:
    """path_aliases 목록에서 첫 항목(canonical)을 기준으로 정규화.

    각 alias 그룹은 [canonical, alias1, alias2, ...]. alias 중 하나와 일치하면 canonical로 교체.
    """
    for group in site_config.path_aliases:
        if not group:
            continue
        canonical = group[0]
        for alias in group[1:]:
            # 정확 일치만 교체 (부분 일치는 위험). trailing slash는 ignore 플래그가 처리.
            if path == alias:
                return canonical
    return path


def _is_multi_value_param(name: str, site_config: SiteConfig) -> bool:
    """param 이름이 multi-value array인지 판정."""
    if name in site_config.multi_value_explicit:
        return True
    if site_config.multi_value_suffix_pattern:
        return bool(re.search(site_config.multi_value_suffix_pattern, name))
    return False


def _normalize_query_value(value: str, site_config: SiteConfig) -> str:
    """query_value_case_sensitive 설정을 적용."""
    if not site_config.query_value_case_sensitive:
        return value.lower()
    return value


# ---------------------------------------------------------------------------
# Primitive 1: normalize_url
# ---------------------------------------------------------------------------

def normalize_url(
    url: str,
    site_config: SiteConfig,
    runtime_context: dict | None = None,
    identity_param_names: set[str] | None = None,
) -> NormalizedURL:
    """URL을 canonical NormalizedURL로 변환.

    identity_param_names이 주어지면 그 이름만 identity 취급하고 나머지는 decorative로 제거.
    주어지지 않으면 site_config.decorative_params에 있는 이름만 제거하고 나머지는 identity 취급.
    (match/emit에서 StatePattern의 identity_query_params.name set을 전달해 정확 필터링)
    """
    # 1. URL decode (aggressive)
    if site_config.url_decode:
        url = unquote(url)

    parsed = urlparse(url)

    # 2. Path: trailing slash / fragment / alias / identity token / case
    path = parsed.path
    if site_config.trailing_slash_ignore and path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")
    path = _apply_identity_tokens_to_path(path, site_config, runtime_context)
    path = _apply_path_aliases(path, site_config)
    if not site_config.path_case_sensitive:
        path = path.lower()

    # 3. Query: parse → filter decorative → normalize multi-value → sort
    raw_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    stripped: list[tuple[str, str]] = []
    kept_pairs: list[tuple[str, str]] = []

    for key, value in raw_pairs:
        key_compare = key if site_config.query_key_case_sensitive else key.lower()
        is_decorative = _matches_decorative(key_compare, site_config.decorative_params, site_config)
        # identity_param_names가 주어지면 그 set에 없는 건 decorative 처리
        if identity_param_names is not None and key_compare not in identity_param_names:
            is_decorative = True
        if is_decorative:
            stripped.append((key, value))
            continue
        # identity param value normalize (case)
        kept_pairs.append((key, _normalize_query_value(value, site_config)))

    # 4. Multi-value sort (같은 키 내에서)
    if site_config.emit_multi_value_sorted:
        kept_pairs = _sort_multi_values(kept_pairs, site_config)

    # 5. Canonical ordering: 비교 편의상 key 알파벳순. match/emit이 필요한 순서로 재배치함.
    kept_pairs_sorted = sorted(kept_pairs, key=lambda kv: kv[0])

    return NormalizedURL(
        path=path,
        query_pairs=kept_pairs_sorted,
        stripped_decorative=stripped,
    )


def _matches_decorative(key: str, decorative_list: list[str], site_config: SiteConfig) -> bool:
    """decorative denylist 중 하나와 일치하는지. key는 이미 case normalize 반영된 상태."""
    for pat in decorative_list:
        pat_compare = pat if site_config.query_key_case_sensitive else pat.lower()
        if "*" in pat_compare:
            # 간단 와일드카드 (예: utm_*)
            rx = re.compile("^" + re.escape(pat_compare).replace(r"\*", ".*") + "$")
            if rx.match(key):
                return True
        elif key == pat_compare:
            return True
    return False


def _sort_multi_values(pairs: list[tuple[str, str]], site_config: SiteConfig) -> list[tuple[str, str]]:
    """같은 이름으로 여러 번 등장하는 multi-value param은 value 알파벳순으로 정렬."""
    buckets: dict[str, list[str]] = {}
    order: list[str] = []
    for key, value in pairs:
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(value)
    result: list[tuple[str, str]] = []
    for key in order:
        values = buckets[key]
        if _is_multi_value_param(key, site_config):
            values = sorted(values)
        for v in values:
            result.append((key, v))
    return result


# ---------------------------------------------------------------------------
# Primitive 2: match_pattern
# ---------------------------------------------------------------------------

def match_pattern(
    url: str,
    pattern: StatePattern,
    site_config: SiteConfig,
    runtime_context: dict | None = None,
) -> tuple[bool, dict[str, Any]]:
    """URL이 StatePattern에 매칭되는지 검사. match 시 bindings(path_params + identity_query_params).

    - path: url_template의 {slot}을 실제 값으로 바인딩
    - query: identity_query_params의 값만 매칭 대상. 나머지 param은 decorative 처리
    - default: 값 미지정 시 pattern.identity_query_params[*].default 사용
    """
    identity_names = {p.name for p in pattern.identity_query_params}
    normalized = normalize_url(url, site_config, runtime_context, identity_names)

    # 1. Path template match
    path_match, path_bindings = _match_path_template(normalized.path, pattern)
    if not path_match:
        return False, {}

    # 2. Identity query params 매칭·default 적용
    query_dict: dict[str, list[str]] = {}
    for key, value in normalized.query_pairs:
        query_dict.setdefault(key, []).append(value)

    query_bindings: dict[str, Any] = {}
    for param in pattern.identity_query_params:
        if param.name in query_dict:
            values = query_dict[param.name]
            if param.type == "multi_string":
                query_bindings[param.name] = sorted(values)
            elif param.type == "enum":
                if param.values is not None and not all(v in param.values for v in values):
                    # enum 위반
                    return False, {}
                query_bindings[param.name] = values[0] if values else None
            elif param.type == "int":
                try:
                    query_bindings[param.name] = int(values[0])
                except (ValueError, IndexError):
                    return False, {}
            else:  # string
                query_bindings[param.name] = values[0] if values else None
        else:
            # 값 미지정 → default 사용 (required면 실패)
            if param.required:
                return False, {}
            query_bindings[param.name] = param.default

    bindings = {**path_bindings, **query_bindings}
    return True, bindings


def extract_path_slots_from_url(
    url: str,
    pattern: StatePattern,
    site_config: SiteConfig,
    runtime_context: dict | None = None,
) -> dict[str, Any] | None:
    """URL이 StatePattern과 매칭되면 path_params slot 값만 dict로 반환.

    현재 URL에서 path slot을 추출하는 helper. emit_target_url에서 bindings
    미제공 slot의 fallback 값으로 재사용 가능.

    Returns:
        매칭 성공 시 {"namespace": "<ns>", "project_path": "<proj>", ...}
        매칭 실패 시 None
    """
    ok, bindings = match_pattern(url, pattern, site_config, runtime_context)
    if not ok:
        return None
    path_bindings = {k: v for k, v in bindings.items() if k in pattern.path_params}
    return path_bindings if path_bindings else None


def _match_path_template(path: str, pattern: StatePattern) -> tuple[bool, dict[str, Any]]:
    """url_template의 {slot}을 path의 실제 값으로 추출.

    slot 타입:
      path_segments: 여러 '/' 포함 세그먼트 (기본)
      segment: 단일 세그먼트 ('/' 포함 불가)
    """
    template = pattern.url_template
    # "{name}" 슬롯을 regex group으로 변환
    slot_names: list[str] = []
    regex_parts: list[str] = []
    i = 0
    while i < len(template):
        if template[i] == "{":
            end = template.find("}", i)
            if end == -1:
                return False, {}
            slot_name = template[i + 1 : end]
            slot_names.append(slot_name)
            slot_type = pattern.path_params.get(slot_name, {}).get("type", "path_segments")
            if slot_type == "path_segments":
                regex_parts.append(r"(.+?)")  # greedy but non-greedy? 여러 세그먼트 허용
            else:  # segment
                regex_parts.append(r"([^/]+)")
            i = end + 1
        else:
            regex_parts.append(re.escape(template[i]))
            i += 1
    regex = "^" + "".join(regex_parts) + "$"
    m = re.match(regex, path)
    if not m:
        return False, {}
    bindings = {name: value for name, value in zip(slot_names, m.groups(), strict=False)}
    return True, bindings


# ---------------------------------------------------------------------------
# Primitive 3: emit_url
# ---------------------------------------------------------------------------

def emit_url(
    pattern: StatePattern,
    bindings: dict[str, Any],
    site_config: SiteConfig,
) -> str:
    """StatePattern + bindings → 실제 URL 문자열.

    - path_template의 slot에 bindings 값 삽입
    - identity_query_params를 canonical_emit_order 순서로 직렬화
    - multi-value는 알파벳 정렬
    - emit_include_default_values=True면 default와 같아도 포함 (evaluator 호환 보수적)
    """
    # 1. Path — bindings 우선, 없으면 path_param spec의 default 사용
    path = pattern.url_template
    for slot_name, slot_meta in pattern.path_params.items():
        value: Any = None
        if slot_name in bindings and bindings[slot_name] is not None:
            value = bindings[slot_name]
        elif isinstance(slot_meta, dict) and slot_meta.get("default") is not None:
            value = slot_meta["default"]
        if value is not None:
            path = path.replace("{" + slot_name + "}", str(value))

    # 2. Query params in canonical_emit_order
    param_by_name = {p.name: p for p in pattern.identity_query_params}
    order = pattern.canonical_emit_order or [p.name for p in pattern.identity_query_params]

    query_parts: list[str] = []
    for name in order:
        param = param_by_name.get(name)
        if param is None:
            continue
        value = bindings.get(name, param.default)
        if value is None or value == []:
            continue
        if not site_config.emit_include_default_values and value == param.default:
            continue
        query_parts.extend(_emit_param_pair(name, value, param, site_config))

    query = "&".join(query_parts)
    result = path
    if query:
        result += "?" + query
    return result


def _emit_param_pair(
    name: str,
    value: Any,
    param: IdentityParam,
    site_config: SiteConfig,
) -> list[str]:
    """단일 identity param의 URL-encoded key=value 문자열 목록. multi-value는 여러 항목."""
    if param.type == "multi_string":
        values = list(value) if isinstance(value, (list, tuple)) else [value]
        if site_config.emit_multi_value_sorted:
            values = sorted(str(v) for v in values)
        return [f"{quote(name, safe='[]')}={quote(str(v), safe='')}" for v in values]
    return [f"{quote(name, safe='[]')}={quote(str(value), safe='')}"]
