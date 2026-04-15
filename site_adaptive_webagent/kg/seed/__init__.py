"""KG seed 로더.

3 파일 로드:
- site_config.yaml → SiteConfig (URL 정규화 규칙)
- infotypes.yaml → list[InfoType]
- kg_seed.json → SiteKG (StatePatterns + realizes + leads_to + actions)
"""
from .crawl_to_kg import crawl_results_to_sitekg, extract_url_template
from .derivation_to_kg import derivation_to_sitekg
from .infotype_catalog import load_infotypes
from .llm_derivation import DerivationResult, derive_infotypes_and_actions
from .manual_config import load_site_config
from .playwright_crawler import CrawlResult, FormElementMeta, crawl_site
from .review_diff import (
    DiffEntry,
    diff_actions,
    diff_leads_to_edges,
    diff_realizes_edges,
    diff_state_patterns,
    render_markdown,
)
from .run_freeze import freeze
from .seed_loader import (
    BUILDER_VERSION,
    compute_source_mix,
    load_kg_seed,
    load_site_kg_from_dir,
)

__all__ = [
    "load_site_config",
    "load_infotypes",
    "load_kg_seed",
    "load_site_kg_from_dir",
    "compute_source_mix",
    "BUILDER_VERSION",
    # M4-A crawler
    "crawl_site",
    "CrawlResult",
    "FormElementMeta",
    "crawl_results_to_sitekg",
    "extract_url_template",
    # M4-B LLM derivation
    "derive_infotypes_and_actions",
    "DerivationResult",
    "derivation_to_sitekg",
    # M4-C review + freeze
    "DiffEntry",
    "diff_state_patterns",
    "diff_actions",
    "diff_realizes_edges",
    "diff_leads_to_edges",
    "render_markdown",
    "freeze",
]
