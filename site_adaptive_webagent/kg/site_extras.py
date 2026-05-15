"""Site-specific config extensions beyond SiteConfig.

SiteConfig (kg/types.py) covers URL normalization rules (decorative params,
identity tokens, path aliases). This module adds per-site *entity lists* and
*crawl configuration*, loaded from YAML the same way as `load_site_config`
(site directory 경로 받기 + YAML 로드).

File layout (per site):
  config/sites/<site>/
    ├── site_config.yaml      (URL normalization)
    ├── entities.yaml         (namespaces, usernames, action_keywords, sample_values)
    └── crawl.yaml            (base_url, forbidden_patterns, seeds, etc.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SITE = "gitlab"


def _site_dir(site: str = DEFAULT_SITE) -> Path:
    return Path("config/sites") / site


@dataclass(frozen=True)
class SiteEntities:
    """Per-site entity lists used by Stage A template generalization."""

    namespaces: frozenset[str]
    usernames: frozenset[str]
    action_keywords: frozenset[str]
    sample_values: dict[str, str]

    @classmethod
    def empty(cls) -> "SiteEntities":
        return cls(
            namespaces=frozenset(),
            usernames=frozenset(),
            action_keywords=frozenset(),
            sample_values={},
        )


@dataclass(frozen=True)
class SiteCascadeEntries:
    """Per-site cascade routing entries (used by path_finder fallback stages).

    - scope_entries / hub: cascade fallback stage targets
    - variant_segments / family_type_suffixes: class name 파싱 상수
      (GitLab naming 관례 기반의 site-specific 값).
    """

    scope_entries: dict[str, str]
    hub: str
    variant_segments: frozenset[str] = frozenset()
    family_type_suffixes: tuple[str, ...] = ()

    @classmethod
    def empty(cls) -> "SiteCascadeEntries":
        return cls(
            scope_entries={},
            hub="",
            variant_segments=frozenset(),
            family_type_suffixes=(),
        )


@dataclass(frozen=True)
class SiteCrawlConfig:
    """Per-site crawl configuration."""

    base_url: str
    allowed_hosts: tuple[str, ...]
    seeds: tuple[str, ...]
    forbidden_patterns: tuple[str, ...]
    site_global_routes: frozenset[str]

    @classmethod
    def empty(cls) -> "SiteCrawlConfig":
        return cls(
            base_url="",
            allowed_hosts=(),
            seeds=(),
            forbidden_patterns=(),
            site_global_routes=frozenset(),
        )


def load_site_entities(site: str = DEFAULT_SITE) -> SiteEntities:
    """Load `<site_dir>/entities.yaml`. Returns empty instance if file missing."""
    path = _site_dir(site) / "entities.yaml"
    if not path.exists():
        return SiteEntities.empty()
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    samples = raw.get("sample_values", {}) or {}
    return SiteEntities(
        namespaces=frozenset(raw.get("namespaces", []) or []),
        usernames=frozenset(raw.get("usernames", []) or []),
        action_keywords=frozenset(raw.get("action_keywords", []) or []),
        sample_values={str(k): str(v) for k, v in samples.items()},
    )


def load_site_cascade(site: str = DEFAULT_SITE) -> SiteCascadeEntries:
    """Load `<site_dir>/cascade.yaml`. Returns empty instance if file missing."""
    path = _site_dir(site) / "cascade.yaml"
    if not path.exists():
        return SiteCascadeEntries.empty()
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    scope_entries = raw.get("scope_entries") or {}
    return SiteCascadeEntries(
        scope_entries={str(k): str(v) for k, v in scope_entries.items()},
        hub=str(raw.get("hub", "")),
        variant_segments=frozenset(raw.get("variant_segments", []) or []),
        family_type_suffixes=tuple(raw.get("family_type_suffixes", []) or []),
    )


def load_site_crawl(site: str = DEFAULT_SITE) -> SiteCrawlConfig:
    """Load `<site_dir>/crawl.yaml`. Returns empty instance if file missing."""
    path = _site_dir(site) / "crawl.yaml"
    if not path.exists():
        return SiteCrawlConfig.empty()
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SiteCrawlConfig(
        base_url=str(raw.get("base_url", "")),
        allowed_hosts=tuple(raw.get("allowed_hosts", []) or []),
        seeds=tuple(raw.get("seeds", []) or []),
        forbidden_patterns=tuple(raw.get("forbidden_patterns", []) or []),
        site_global_routes=frozenset(raw.get("site_global_routes", []) or []),
    )
