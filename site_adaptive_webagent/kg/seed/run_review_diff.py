"""M4-C CLI: manual seed + crawl + derived(llm) 3-source SiteKG diff를 markdown으로.

실행 예:
  python -m site_adaptive_webagent.kg.seed.run_review_diff \\
      --site gitlab \\
      --crawl-dir output/crawl/<ts>/ \\
      --derivation-dir output/derivation/<ts>/ \\
      --output output/review/<ts>.md

산출:
  stdout 또는 --output에 markdown diff 표.
사용 의도: 사람이 이 표를 보면서 config/sites/<site>/{infotypes.yaml, kg_seed.json}을
직접 편집해 승격(verified/declared)·강등·제거 결정을 반영. 자동 적용은 하지 않는다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..store import SiteKGStore
from ..types import SiteKG
from .review_diff import render_markdown
from .seed_loader import load_site_kg_from_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M4-C: 3-source SiteKG diff helper")
    parser.add_argument("--site", required=True, help="site key (e.g., gitlab)")
    parser.add_argument("--site-config-dir", type=Path, default=Path("config/sites"),
                        help="parent dir containing <site>/")
    parser.add_argument("--crawl-dir", type=Path, default=None,
                        help="M4-A 출력 디렉토리 (crawled_kg.json)")
    parser.add_argument("--derivation-dir", type=Path, default=None,
                        help="M4-B 출력 디렉토리 (derived_kg.json)")
    parser.add_argument("--output", type=Path, default=None,
                        help="markdown 출력 파일 (생략 시 stdout)")
    args = parser.parse_args(argv)

    site_dir = args.site_config_dir / args.site
    if not site_dir.exists():
        print(f"[error] site config dir not found: {site_dir}", file=sys.stderr)
        return 2
    _, manual_kg = load_site_kg_from_dir(site_dir)

    crawl_kg = SiteKG(site=args.site)
    if args.crawl_dir:
        crawl_path = args.crawl_dir / "crawled_kg.json"
        if crawl_path.exists():
            crawl_kg = SiteKGStore.load(crawl_path).kg
        else:
            print(f"[warn] no crawled_kg.json at {crawl_path}", file=sys.stderr)

    derived_kg = SiteKG(site=args.site)
    if args.derivation_dir:
        derived_path = args.derivation_dir / "derived_kg.json"
        if derived_path.exists():
            derived_kg = SiteKGStore.load(derived_path).kg
        else:
            print(f"[warn] no derived_kg.json at {derived_path}", file=sys.stderr)

    md = render_markdown(manual_kg, crawl_kg, derived_kg)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(md, encoding="utf-8")
        print(f"[ok] wrote {args.output}", file=sys.stderr)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
