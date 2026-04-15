"""M4-B CLI: M4-A crawl 산출물에 LLM derivation을 적용해 derived_kg.json 생성.

실행 예 (.env 또는 환경변수에 OPENAI_API_KEY + 아래 설정):
  export LLM_PROVIDER=openai
  export OPENAI_MODEL=gpt-5.4-full
  export LLM_TEMPERATURE=0
  python -m site_adaptive_webagent.kg.seed.run_derivation \\
      --crawl-dir output/crawl/<ts>/ \\
      --site gitlab \\
      --output output/derivation/<ts>/

산출:
  <output>/derivation_prompt.txt    — system prompt (재현성)
  <output>/derivation_response.json — raw LLM tool_call arguments
  <output>/derived_kg.json          — SiteKG (source=llm, trust=inferred)
  <output>/action_name_map.json     — {crawl_name: semantic_name}
  <output>/derivation.log           — 진행 로그
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from site_adaptive_webagent.runtime.llm import make_llm_client

from ..store import SiteKGStore
from .derivation_to_kg import derivation_to_sitekg
from .llm_derivation import derive_infotypes_and_actions
from .playwright_crawler import CrawlResult, FormElementMeta


def _setup_logging(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("kg.derivation")
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(sh)
    return logger


def _load_crawl_results(path: Path) -> list[CrawlResult]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: list[CrawlResult] = []
    for r in raw:
        forms = [
            FormElementMeta(**f) for f in (r.get("form_elements") or [])
        ]
        out.append(
            CrawlResult(
                url=r["url"],
                normalized_url_template=r["normalized_url_template"],
                path_params=dict(r.get("path_params") or {}),
                query_params_seen=list(r.get("query_params_seen") or []),
                outgoing_links=list(r.get("outgoing_links") or []),
                form_elements=forms,
                dom_signature=r.get("dom_signature"),
                http_status=int(r.get("http_status", 200)),
                parent_url=r.get("parent_url"),
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M4-B: LLM-assisted KG derivation")
    parser.add_argument("--crawl-dir", required=True, type=Path,
                        help="M4-A 산출 디렉토리 (crawl_results.json + crawled_kg.json 포함)")
    parser.add_argument("--site", required=True, help="site key (e.g., gitlab)")
    parser.add_argument("--output", required=True, type=Path,
                        help="derivation 산출 디렉토리")
    args = parser.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)
    logger = _setup_logging(args.output / "derivation.log")

    crawl_results_path = args.crawl_dir / "crawl_results.json"
    crawled_kg_path = args.crawl_dir / "crawled_kg.json"
    if not crawl_results_path.exists() or not crawled_kg_path.exists():
        logger.error("missing crawl artifacts in %s", args.crawl_dir)
        return 2

    crawl_results = _load_crawl_results(crawl_results_path)
    crawl_kg = SiteKGStore.load(crawled_kg_path).kg
    logger.info(
        "loaded crawl: %d results, %d state_patterns, %d actions",
        len(crawl_results), len(crawl_kg.state_patterns), len(crawl_kg.actions),
    )

    llm = make_llm_client()
    if llm is None:
        logger.error(
            "LLM client unavailable — set OPENAI_API_KEY (and LLM_PROVIDER=openai) in env"
        )
        return 3

    derivation = derive_infotypes_and_actions(crawl_results, crawl_kg, llm)
    logger.info(
        "derivation: %d infotypes, %d action renames",
        len(derivation.infotypes), len(derivation.action_name_map),
    )

    # 산출 4파일
    (args.output / "derivation_prompt.txt").write_text(derivation.prompt, encoding="utf-8")
    (args.output / "derivation_response.json").write_text(
        derivation.raw_response or "{}", encoding="utf-8",
    )
    (args.output / "action_name_map.json").write_text(
        json.dumps(derivation.action_name_map, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    derived = derivation_to_sitekg(derivation, crawl_kg)
    SiteKGStore(derived).save(args.output / "derived_kg.json")
    logger.info(
        "wrote derived_kg.json: %d infotypes, %d actions, %d realizes_edges, %d leads_to_edges",
        len(derived.infotypes), len(derived.actions),
        len(derived.realizes_edges), len(derived.leads_to_edges),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
