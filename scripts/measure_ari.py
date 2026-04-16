"""M4-B LLM grouping ARI stability 측정 — reviewer 재현성 검증용.

N개 derivation run(derivation_response.json)을 읽어 grouping 안정성을
Adjusted Rand Index로 계산한다. temperature=0인데 실제로 얼마나 안정적인지.

사용:
  python scripts/measure_ari.py \
      output/derivation/20260416_131636 \
      output/derivation/20260416_131636_run2 \
      output/derivation/20260416_131636_run3

산출:
  각 run 쌍의 ARI + 평균 + 결과 markdown 요약
"""
from __future__ import annotations

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path


def load_member_to_group(run_dir: Path) -> dict[str, str]:
    """derivation_response.json → {crawl_member_id: group_index_str}."""
    resp_path = run_dir / "derivation_response.json"
    if not resp_path.exists():
        raise FileNotFoundError(f"missing {resp_path}")
    raw = json.loads(resp_path.read_text(encoding="utf-8"))
    groups = raw.get("state_pattern_groups") or []
    member_to_group: dict[str, str] = {}
    for idx, g in enumerate(groups):
        gid = str(idx)  # run 내부 group index
        for m in g.get("member_ids") or []:
            member_to_group[m] = gid
    return member_to_group


def adjusted_rand_index(labels_a: list[str], labels_b: list[str]) -> float:
    """ARI의 자체 구현 (sklearn.metrics.adjusted_rand_score와 동등, sklearn 비의존)."""
    from collections import Counter
    from math import comb

    assert len(labels_a) == len(labels_b)
    n = len(labels_a)
    if n < 2:
        return 1.0
    cont = Counter(zip(labels_a, labels_b))
    a_cnt = Counter(labels_a)
    b_cnt = Counter(labels_b)
    sum_ij = sum(comb(v, 2) for v in cont.values())
    sum_a = sum(comb(v, 2) for v in a_cnt.values())
    sum_b = sum(comb(v, 2) for v in b_cnt.values())
    total = comb(n, 2)
    expected = (sum_a * sum_b) / total if total else 0.0
    max_idx = (sum_a + sum_b) / 2
    if max_idx - expected == 0:
        return 1.0
    return (sum_ij - expected) / (max_idx - expected)


def pair_ari(a: dict[str, str], b: dict[str, str]) -> tuple[float, int]:
    """두 run의 공통 member id에 대해 ARI 계산. 공통 없으면 (nan, 0)."""
    common = sorted(set(a) & set(b))
    if not common:
        return (float("nan"), 0)
    labels_a = [a[k] for k in common]
    labels_b = [b[k] for k in common]
    return (adjusted_rand_index(labels_a, labels_b), len(common))


def group_count_stability(runs: list[dict[str, str]]) -> list[int]:
    """각 run의 group 개수 list."""
    return [len(set(r.values())) for r in runs]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs="+", type=Path,
                        help="derivation output 디렉토리들 (2개 이상)")
    parser.add_argument("--output-md", type=Path, default=None,
                        help="markdown 요약 저장")
    args = parser.parse_args(argv)

    if len(args.run_dirs) < 2:
        print("at least 2 run dirs needed", file=sys.stderr)
        return 2

    runs = [load_member_to_group(d) for d in args.run_dirs]
    names = [d.name for d in args.run_dirs]

    group_counts = group_count_stability(runs)
    ari_results: list[tuple[str, str, float, int]] = []
    for (i, a), (j, b) in combinations(enumerate(runs), 2):
        ari, n = pair_ari(a, b)
        ari_results.append((names[i], names[j], ari, n))

    # 요약
    aris = [r[2] for r in ari_results if not (r[2] != r[2])]  # NaN 제거
    mean_ari = sum(aris) / len(aris) if aris else float("nan")

    print("=" * 60)
    print("M4-B LLM grouping ARI stability")
    print("=" * 60)
    print(f"runs: {len(runs)}")
    for name, gc in zip(names, group_counts):
        print(f"  {name}: {gc} groups, {len(runs[names.index(name)])} members assigned")
    print()
    print("Pairwise ARI (1.0 = identical clustering):")
    for a_name, b_name, ari, n in ari_results:
        print(f"  {a_name} vs {b_name}: ARI={ari:.4f} (common members={n})")
    print()
    print(f"Mean ARI: {mean_ari:.4f}")
    print(f"Group count stability: min={min(group_counts)} max={max(group_counts)}")

    if args.output_md:
        lines = [
            "# M4-B LLM Grouping ARI Stability",
            "",
            f"- Runs: {len(runs)} (derivation_response.json)",
            f"- Mean Adjusted Rand Index: **{mean_ari:.4f}**",
            f"- Group count range: [{min(group_counts)}, {max(group_counts)}]",
            "",
            "## Per-run group counts",
            "",
            "| run | group count | members assigned |",
            "|---|---|---|",
        ]
        for name, r in zip(names, runs):
            lines.append(f"| `{name}` | {len(set(r.values()))} | {len(r)} |")
        lines += ["", "## Pairwise ARI", "", "| run A | run B | ARI | common members |", "|---|---|---|---|"]
        for a_name, b_name, ari, n in ari_results:
            lines.append(f"| `{a_name}` | `{b_name}` | {ari:.4f} | {n} |")
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nwrote {args.output_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
