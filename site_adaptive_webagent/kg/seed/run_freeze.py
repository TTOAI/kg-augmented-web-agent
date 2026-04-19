"""Freeze CLI: manual seed (수동 검증 후) + crawl + derived를 단일 immutable snapshot으로 통합.

실행 예 (crawl + derivation 산출물이 있고 수동 seed 편집을 마친 후):
  python -m site_adaptive_webagent.kg.seed.run_freeze \\
      --site gitlab \\
      --crawl-dir output/crawl/<ts>/ \\
      --derivation-dir output/derivation/<ts>/ \\
      --note "<freeze 설명>"

산출:
  config/sites/<site>/frozen_kg/<ISO_ts>.json       — SiteKG 통합 snapshot
  config/sites/<site>/frozen_kg/<ISO_ts>.meta.json  — note + git rev + source_mix
  config/sites/<site>/frozen_kg/INDEX.md            — 한 줄 append (최근 freeze)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..store import SiteKGStore
from ..types import SiteKG
from .seed_loader import compute_source_mix, load_site_kg_from_dir


def _git_rev(repo_dir: Path) -> str | None:
    """현재 git HEAD의 짧은 hash를 반환. 실패 시 None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


def _isoformat_filename_safe() -> str:
    """`2026-04-16T12-34-56Z` 형식 (콜론 회피)."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def freeze(
    site: str,
    site_config_dir: Path,
    crawl_dir: Path | None,
    derivation_dir: Path | None,
    note: str = "",
    timestamp: str | None = None,
    repo_dir: Path | None = None,
) -> tuple[Path, Path]:
    """immutable snapshot을 작성. 동일 timestamp 충돌 시 FileExistsError.

    Returns: (snapshot_path, meta_path)
    """
    site_dir = site_config_dir / site
    if not site_dir.exists():
        raise FileNotFoundError(f"site config dir not found: {site_dir}")

    _, kg = load_site_kg_from_dir(site_dir)
    store = SiteKGStore(kg)

    if crawl_dir:
        crawl_path = crawl_dir / "crawled_kg.json"
        if crawl_path.exists():
            store.merge(SiteKGStore.load(crawl_path).kg)
    if derivation_dir:
        derived_path = derivation_dir / "derived_kg.json"
        if derived_path.exists():
            store.merge(SiteKGStore.load(derived_path).kg)

    ts = timestamp or _isoformat_filename_safe()
    git_rev = _git_rev(repo_dir or Path.cwd())

    # Post-enrichment: merged KG에 0-entries 결함 자동 보강
    from .post_enrich import enrich as _post_enrich
    _post_enrich(store.kg)

    store.kg.build_timestamp = datetime.now(tz=timezone.utc).isoformat()
    store.kg.source_mix = compute_source_mix(store.kg)
    store.kg.git_rev = git_rev

    frozen_dir = site_dir / "frozen_kg"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = frozen_dir / f"{ts}.json"
    meta_path = frozen_dir / f"{ts}.meta.json"

    if snapshot_path.exists() or meta_path.exists():
        raise FileExistsError(
            f"frozen snapshot already exists at {snapshot_path}; "
            "freeze is immutable — use a different timestamp."
        )

    store.save(snapshot_path)
    meta_path.write_text(
        json.dumps(
            {
                "timestamp": ts,
                "git_rev": git_rev,
                "source_mix": dict(store.kg.source_mix),
                "builder_version": store.kg.builder_version,
                "note": note,
                "crawl_dir": str(crawl_dir) if crawl_dir else None,
                "derivation_dir": str(derivation_dir) if derivation_dir else None,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    index_path = frozen_dir / "INDEX.md"
    line = f"- `{ts}` git={git_rev or 'n/a'} mix={dict(store.kg.source_mix)} note={note!r}"
    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8").rstrip()
        index_path.write_text(existing + "\n" + line + "\n", encoding="utf-8")
    else:
        index_path.write_text(
            f"# Frozen KG snapshots — site={site}\n\n{line}\n",
            encoding="utf-8",
        )

    return snapshot_path, meta_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze KG catalog into immutable snapshot")
    parser.add_argument("--site", required=True, help="site key (e.g., gitlab)")
    parser.add_argument("--site-config-dir", type=Path, default=Path("config/sites"))
    parser.add_argument("--crawl-dir", type=Path, default=None,
                        help="crawler 출력 디렉토리 (선택)")
    parser.add_argument("--derivation-dir", type=Path, default=None,
                        help="LLM derivation 출력 디렉토리 (선택)")
    parser.add_argument("--note", default="", help="freeze 사유 한 줄")
    args = parser.parse_args(argv)

    try:
        snapshot, meta = freeze(
            site=args.site,
            site_config_dir=args.site_config_dir,
            crawl_dir=args.crawl_dir,
            derivation_dir=args.derivation_dir,
            note=args.note,
        )
    except FileExistsError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 4
    except FileNotFoundError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2

    print(f"[ok] frozen snapshot: {snapshot}", file=sys.stderr)
    print(f"[ok] metadata: {meta}", file=sys.stderr)
    print(snapshot)  # stdout = snapshot path (스크립트 chaining용)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
