"""Site-specific Knowledge Graph 모듈 — 수집·저장·URL 정규화만 제공.

현재 범위:
- types: SiteKG dataclass 정의 (StatePattern, InfoType, Action, RealizesEdge, LeadsToEdge, Trust)
- store: SiteKG JSON 직렬화 (SiteKGStore)
- urlnorm: URL 정규화 primitive (normalize_url / match_pattern / emit_url)
- seed/: collector 파이프라인 (crawler + LLM derivation + freeze)

활용(agent-side 통합) 로직은 제거됨 — `docs/lessons_learned_kg_v2.md` 참조.
"""
from .types import (
    Action,
    IdentityParam,
    InfoType,
    LeadsToEdge,
    RealizesEdge,
    SiteConfig,
    SiteKG,
    Source,
    StatePattern,
    TrustLevel,
    default_trust_for_source,
)
from .urlnorm import emit_url, match_pattern, normalize_url

__all__ = [
    # Trust / source primitives
    "TrustLevel",
    "Source",
    "default_trust_for_source",
    # Schema types
    "SiteConfig",
    "IdentityParam",
    "StatePattern",
    "InfoType",
    "Action",
    "RealizesEdge",
    "LeadsToEdge",
    "SiteKG",
    # URL primitives
    "normalize_url",
    "match_pattern",
    "emit_url",
]
