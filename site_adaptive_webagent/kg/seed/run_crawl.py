"""M4-A CLI: site config 기준 base_url을 읽어 crawl 수행 후 SiteKG 산출.

실행 예 (GitLab Docker가 떠 있고 storage_state가 준비된 상태):
  python -m site_adaptive_webagent.kg.seed.run_crawl \\
      --site gitlab \\
      --config config/webarena_verified.json \\
      --storage-state output/<task>/.storage_state.json \\
      --max-depth 2 \\
      --output output/crawl/$(date +%Y%m%d_%H%M%S)/

산출:
  <output>/crawl_results.json   — list[CrawlResult] (직렬화)
  <output>/crawled_kg.json      — SiteKGStore.to_json (source=crawl 노드·엣지)
  <output>/crawl.log            — crawl 진행 로그
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from ..store import SiteKGStore
from ..types import SiteConfig
from .crawl_to_kg import crawl_results_to_sitekg
from .manual_config import load_site_config
from .playwright_crawler import crawl_site


# 사이트 공식 기능 표면 기준 default seed URL (사이트별로 분기).
# **금지 사항**: 실험 task ID·실험 task 분포에 맞춘 URL을 추가하지 말 것
# (docs/kg_design/07 §14 hindsight bias 차단 + memory feedback_no_task_site_bias).
_DEFAULT_SEEDS: dict[str, list[str]] = {
    "gitlab": [
        "/",
        "/dashboard",
        "/dashboard/projects",
        "/dashboard/issues",
        "/dashboard/merge_requests",
        "/explore/projects",
        "/explore/groups",
        "/-/profile",
    ],
}


def _read_base_url(config_path: Path, site: str) -> str:
    """webarena_verified config에서 site의 base_url 추출."""
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    envs = raw.get("environments", {})
    key = f"__{site.upper()}__"
    if key not in envs:
        raise ValueError(f"site {site!r} not in config environments")
    urls = envs[key].get("urls") or []
    if not urls:
        raise ValueError(
            f"site {site!r} has no URLs in config (run `webarena-verified env start --site {site}` first)"
        )
    idx = envs[key].get("active_url_idx") or 0
    return urls[idx]


def _setup_logging(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("kg.crawler")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stream)
    return logger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M4-A: Playwright crawler for KG construction")
    parser.add_argument("--site", required=True, help="site key (e.g., gitlab)")
    parser.add_argument("--config", required=True, type=Path, help="webarena_verified.json path")
    parser.add_argument("--site-config-dir", type=Path,
                        default=Path("config/sites"),
                        help="parent dir of <site>/site_config.yaml")
    parser.add_argument("--storage-state", type=Path, default=None,
                        help="Playwright storage_state JSON (logged-in session)")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--output", required=True, type=Path,
                        help="output directory for crawl_results.json + crawled_kg.json")
    parser.add_argument("--seed-url", action="append", default=None,
                        help="override default seed URL (relative path, repeatable)")
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    logger = _setup_logging(args.output / "crawl.log")

    base_url = _read_base_url(args.config, args.site)
    logger.info("base_url=%s", base_url)

    site_cfg_path = args.site_config_dir / args.site / "site_config.yaml"
    if site_cfg_path.exists():
        site_config: SiteConfig = load_site_config(site_cfg_path)
    else:
        logger.warning("no site_config.yaml at %s — using minimal SiteConfig", site_cfg_path)
        site_config = SiteConfig(site=args.site, base_url=base_url)

    relative_seeds = args.seed_url or _DEFAULT_SEEDS.get(args.site)
    if not relative_seeds:
        raise ValueError(
            f"no default seeds for site {args.site!r}; pass --seed-url explicitly"
        )
    seed_urls = [base_url.rstrip("/") + s if s.startswith("/") else s for s in relative_seeds]
    logger.info("seed_urls=%s", seed_urls)
    logger.info("max_depth=%d", args.max_depth)

    results = crawl_site(
        base_url=base_url,
        seed_urls=seed_urls,
        max_depth=args.max_depth,
        storage_state_file=args.storage_state,
    )
    logger.info("crawl finished: %d CrawlResult(s)", len(results))

    # 산출 1: CrawlResult 직렬화
    raw_results = [asdict(r) for r in results]
    (args.output / "crawl_results.json").write_text(
        json.dumps(raw_results, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    # 산출 2: SiteKG 변환 + 직렬화
    kg = crawl_results_to_sitekg(results, site_config, site=args.site)
    SiteKGStore(kg).save(args.output / "crawled_kg.json")
    logger.info(
        "wrote crawled_kg.json: %d state_patterns, %d actions, %d leads_to_edges",
        len(kg.state_patterns), len(kg.actions), len(kg.leads_to_edges),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
