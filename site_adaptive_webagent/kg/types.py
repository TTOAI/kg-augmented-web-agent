"""KG 스키마 dataclass.

02_open_questions.md 쟁점 #3의 minimum viable schema 결정을 Python 타입으로 옮김.

M1: urlnorm 의존분 (SiteConfig / IdentityParam / StatePattern)
M2: 완전한 KG container (InfoType / Action / RealizesEdge / LeadsToEdge / SiteKG)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TrustLevel = Literal["verified", "declared", "inferred"]
Source = Literal["crawl", "llm", "manual"]
ParamType = Literal["enum", "string", "multi_string", "int"]
RealizesCondition = Literal["default", "has_filter"]

# Source → TrustLevel 기본 매핑 (docs/kg_design/02 §3-7)
_SOURCE_TO_TRUST: dict[Source, TrustLevel] = {
    "crawl": "verified",
    "manual": "declared",
    "llm": "inferred",
}


def default_trust_for_source(source: Source) -> TrustLevel:
    return _SOURCE_TO_TRUST[source]


@dataclass(slots=True)
class IdentityParam:
    """StatePattern의 identity query param 하나.

    URL param 중 state 식별에 관여하는 항목만 이 목록에 포함된다 (decorative는 별도 제외).
    """

    name: str  # e.g., "state", "label_name[]", "assignee_username"
    type: ParamType = "string"
    values: list[str] | None = None  # type=enum일 때만
    default: Any = None  # 값 미지정 시 암묵 값 (e.g., GitLab의 state default="opened")
    default_trust: TrustLevel = "declared"
    required: bool = False


@dataclass(slots=True)
class StatePattern:
    """사이트 상태의 formal 표현 (URL-based).

    url_template: path slot을 포함 (예: "/{project_path}/-/issues")
    path_params: slot 이름 → 메타 (e.g., {"project_path": {"type": "path_segments"}})
    """

    id: str
    url_template: str
    path_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    identity_query_params: list[IdentityParam] = field(default_factory=list)
    canonical_emit_order: list[str] = field(default_factory=list)
    url_template_trust: TrustLevel = "declared"
    source: Source = "manual"


@dataclass(slots=True)
class SiteConfig:
    """사이트 공통 URL 정규화 규칙.

    config/sites/<site>/site_config.yaml의 필드를 1:1로 매핑.
    """

    site: str
    base_url: str = ""

    # --- 1. URL decoding / 공통 string 처리 ---
    url_decode: bool = True  # aggressive=True 상수 매핑
    trailing_slash_ignore: bool = True
    strip_fragment: bool = True

    # case sensitivity
    path_case_sensitive: bool = True
    query_key_case_sensitive: bool = True
    query_value_case_sensitive: bool = False

    # --- 2. Decorative params (denylist, 비교에서 제거) ---
    decorative_params: list[str] = field(default_factory=list)

    # --- 3. Multi-value array params ---
    multi_value_suffix_pattern: str | None = r"\[\]$"  # e.g., "label_name[]"
    multi_value_explicit: list[str] = field(default_factory=list)

    # --- 4. Identity tokens (런타임 치환) ---
    # value는 runtime_context의 키 경로를 "{{path}}" 포맷으로 가리킴
    identity_tokens: dict[str, str] = field(default_factory=dict)

    # --- 5. Path aliases (canonical, alias1, alias2, ...) ---
    path_aliases: list[list[str]] = field(default_factory=list)

    # --- 6. Emit 정책 ---
    emit_include_default_values: bool = True
    emit_multi_value_sorted: bool = True


# ---------------------------------------------------------------------------
# M2: KG container types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class RealizesEdge:
    """InfoType → StatePattern 매핑. 1:N 허용 (condition으로 구분).

    binding_map: InfoType의 binding 이름을 StatePattern의 binding 이름으로 매핑.
    (예: InfoType의 'label_name' → StatePattern의 'label_name[]')
    """

    infotype: str  # InfoType.name (flat list용 key)
    state_pattern_id: str
    condition: RealizesCondition = "default"
    binding_map: dict[str, str] = field(default_factory=dict)
    trust: TrustLevel = "declared"
    source: Source = "manual"


@dataclass(slots=True)
class InfoType:
    """자연어 intent의 추상 카테고리.

    granularity β: 도메인 명사구 수준 (issues_list, merge_requests_list 등).
    """

    name: str
    description: str = ""
    required_bindings: list[str] = field(default_factory=list)
    optional_bindings: list[str] = field(default_factory=list)
    realizes: list[RealizesEdge] = field(default_factory=list)
    intent_examples: list[str] = field(default_factory=list)
    trust_label: TrustLevel = "declared"
    source: Source = "manual"
    # post-enrichment: prefix 기반 자동 category ("project" / "repository" / "pipeline" / "misc" 등)
    category: str | None = None


@dataclass(slots=True)
class Action:
    """상태 전이를 일으키는 연산 template.

    fine granularity 원칙: 한 action당 파라미터 하나.
    params schema는 간단한 list[dict] 형태 (추후 확장 가능).
    """

    name: str
    params: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""
    source: Source = "manual"


@dataclass(slots=True)
class LeadsToEdge:
    """StatePattern --Action--> StatePattern 전이.

    from_bindings / to_bindings는 해당 state에서 유지·전달되는 binding 이름 목록.
    to_bindings의 "label_name[]<-label" 표기는 action의 label 파라미터를
    target state의 label_name[] 슬롯에 매핑함을 의미 (선택적 해석).
    """

    from_state_pattern_id: str
    from_bindings: list[str] = field(default_factory=list)
    action_name: str = ""
    to_state_pattern_id: str = ""
    to_bindings: list[str] = field(default_factory=list)
    trust: TrustLevel = "declared"
    source: Source = "manual"


@dataclass(slots=True)
class SiteKG:
    """단일 사이트의 전체 KG container.

    id 기반 lookup을 위해 state_patterns / infotypes / actions는 dict로 보유.
    realizes_edges는 InfoType.realizes와 동일 데이터를 flat list로 보유 (조회 편의).
    """

    site: str
    state_patterns: dict[str, StatePattern] = field(default_factory=dict)
    infotypes: dict[str, InfoType] = field(default_factory=dict)
    actions: dict[str, Action] = field(default_factory=dict)
    realizes_edges: list[RealizesEdge] = field(default_factory=list)
    leads_to_edges: list[LeadsToEdge] = field(default_factory=list)
    # Build metadata (07 §14 — KG 구축 방법론)
    build_timestamp: str | None = None
    source_mix: dict[str, int] = field(default_factory=dict)
    builder_version: str | None = None
    git_rev: str | None = None  # freeze 시점 git HEAD (재현성)


# ---------------------------------------------------------------------------
# M2b: Runtime 호출용 container
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class KGLookup:
    """LLM tool use(`plan_to_info`) 결과를 묶은 container.

    agent가 intent를 LLM에게 classify시켜 받은 (InfoType, bindings)가 여기 들어간다.
    rewrite / validator 호출의 공통 입력.
    """

    infotype: str
    bindings: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class KGContext:
    """KG 호출의 정적 컨텍스트.

    runtime_context: identity token 치환용 dict (예: {"current_user": {"username": "byteblaze"}}).
    task 별 agent 실행 전에 한 번 구성 → rewrite/validator가 공유.
    """

    kg: SiteKG
    site_config: SiteConfig
    runtime_context: dict[str, Any] = field(default_factory=dict)
