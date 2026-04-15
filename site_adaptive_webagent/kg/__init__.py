"""Site-specific Knowledge Graph 모듈.

07_scope_and_justifications.md와 02_open_questions.md 쟁점 #3의 스키마 결정을
구현한다.

M1 (완료): URL 정규화 3 primitive (normalize_url / match_pattern / emit_url)
M2 (이 범위): KG container + store + seed loaders + emit_target_url / state_matches
M2b (future): full BFS route_to, rewrite, validator
M3 (future): agent integration (Hook A/B/C/D)
"""
from .query import emit_target_url, simulate_final_state, state_matches
from .rewrite import rewrite_plan
from .types import (
    Action,
    IdentityParam,
    InfoType,
    KGContext,
    KGLookup,
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
from .validator import target_reached

__all__ = [
    # Trust / source primitives
    "TrustLevel",
    "Source",
    "default_trust_for_source",
    # M1 types (urlnorm 의존분)
    "SiteConfig",
    "IdentityParam",
    "StatePattern",
    # M2 types (KG container)
    "InfoType",
    "Action",
    "RealizesEdge",
    "LeadsToEdge",
    "SiteKG",
    # M2b types (runtime container)
    "KGLookup",
    "KGContext",
    # M1 primitives
    "normalize_url",
    "match_pattern",
    "emit_url",
    # M2 primitives
    "emit_target_url",
    "state_matches",
    "simulate_final_state",
    # M2b primitives
    "rewrite_plan",
    "target_reached",
]
