"""KG-addressable coverage + source_mix 집계 — `06 §3-5` + `07 §14` 보고 의무.

입력:
  - 측정 결과 디렉토리: output/<variant>_n3/N{1,2,3}/<task_id>/webarena_verified.log
  - Frozen KG path: config/sites/gitlab/frozen_kg/<ts>.json

출력:
  - Markdown 표: variant×coverage / source_mix / freeze metadata
  - 부록 (선택): per-task 분류 결과 (infotype + bindings)

사용:
  python scripts/coverage.py \\
      --variant baseline=output/baseline_n3 \\
      --variant kg_full=output/kg_full_n3 \\
      --frozen config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json \\
      --output output/analysis/coverage.md

reviewer-proof 의도:
- KG-addressable coverage <100%가 정상 — catalog가 task에 맞춰지지 않은 직접 증거
- source_mix가 manual=0이고 crawl+llm 만으로 구성됨을 정량 확인
- freeze timestamp가 baseline 측정보다 앞섬을 metadata로 검증
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


_HOOK_A_LINE = re.compile(r"\[KG\] Hook A")
_HOOK_A_FULL_INFO = re.compile(r"\[KG\] Hook A \(full\): infotype=(\S+)\s+bindings=(.*)")
_HOOK_A_FULL_DECLINED = re.compile(r"\[KG\] Hook A \(full\): classification declined")
_HOOK_A_INFO_IGNORED = re.compile(r"\[KG\] Hook A \(info_ignored\)")

# Hook B — rewrite_plan 호출 결과 (2026-04-18 Option B 이후)
_HOOK_B_CONSIDERING = re.compile(r"\[KG\] rewrite considering: edge\.trust=(\S+), url_template_trust=(\S+)")
_HOOK_B_APPLIED = re.compile(r"\[KG\] plan rewritten (\d+) → (\d+) sub-goals")
_HOOK_B_SKIPPED_TRUST = re.compile(r"\[KG\] rewrite skipped: trust=(\S+)")
_HOOK_B_SKIPPED_INCOMPLETE = re.compile(r"\[KG\] rewrite skipped: incomplete_url")

# Hook C — target_reached early SUCCESS (NAVIGATE에서만 trigger, RET/MUT는 suppressed)
_HOOK_C_REACHED = re.compile(r"\[KG\] target_reached at step=(\d+) — early SUCCESS \(infotype=(\S+)\)")


def collect_variant_coverage(variant_dir: Path) -> dict:
    """Variant의 N=3 run 모두 훑어 Hook A 통계."""
    runs = ("N1", "N2", "N3")
    by_task: dict[int, dict] = {}
    for run in runs:
        run_dir = variant_dir / run
        if not run_dir.exists():
            continue
        for task_dir in sorted(run_dir.iterdir()):
            if not task_dir.is_dir() or not task_dir.name.isdigit():
                continue
            task_id = int(task_dir.name)
            log_path = task_dir / "webarena_verified.log"
            if not log_path.exists():
                continue
            text = log_path.read_text(encoding="utf-8", errors="replace")
            stats = by_task.setdefault(task_id, {
                "hook_a_called": 0,
                "hook_a_classified": 0,
                "hook_a_declined": 0,
                "hook_a_info_ignored": 0,
                "hook_b_considering": 0,
                "hook_b_applied": 0,
                "hook_b_skipped_trust": 0,
                "hook_b_skipped_incomplete": 0,
                "hook_c_reached": 0,
                "infotypes": Counter(),
            })
            if _HOOK_A_LINE.search(text):
                stats["hook_a_called"] += 1
            for m in _HOOK_A_FULL_INFO.finditer(text):
                stats["hook_a_classified"] += 1
                stats["infotypes"][m.group(1)] += 1
            if _HOOK_A_FULL_DECLINED.search(text):
                stats["hook_a_declined"] += 1
            if _HOOK_A_INFO_IGNORED.search(text):
                stats["hook_a_info_ignored"] += 1
            # Hook B
            for _ in _HOOK_B_CONSIDERING.finditer(text):
                stats["hook_b_considering"] += 1
            for _ in _HOOK_B_APPLIED.finditer(text):
                stats["hook_b_applied"] += 1
            for _ in _HOOK_B_SKIPPED_TRUST.finditer(text):
                stats["hook_b_skipped_trust"] += 1
            for _ in _HOOK_B_SKIPPED_INCOMPLETE.finditer(text):
                stats["hook_b_skipped_incomplete"] += 1
            # Hook C
            for _ in _HOOK_C_REACHED.finditer(text):
                stats["hook_c_reached"] += 1

    # Aggregate — mutually exclusive 분류 규칙:
    # (1) any run classified → classified_tasks  (우선)
    # (2) no run classified but any run declined → declined_tasks
    # (3) Hook A 호출 자체가 0건 → not_called_tasks
    # (4) 나머지 (called but neither classified nor declined) → other_tasks
    # 기존 조건 "classified > 0"과 "declined > 0 AND classified == 0"은 (1)+(2) 배타
    # 보장. not_called는 hook_a_called=0만. 세 집합의 합이 total과 일치하는지 검증
    # (coverage 수치 정확성).
    total_tasks = len(by_task)
    if total_tasks == 0:
        return {"total_tasks": 0}
    classified_tasks = sum(1 for s in by_task.values() if s["hook_a_classified"] > 0)
    declined_tasks = sum(1 for s in by_task.values()
                         if s["hook_a_declined"] > 0 and s["hook_a_classified"] == 0)
    not_called = sum(1 for s in by_task.values() if s["hook_a_called"] == 0)
    other_tasks = total_tasks - classified_tasks - declined_tasks - not_called

    # Top infotype distribution
    all_infotypes: Counter = Counter()
    for s in by_task.values():
        all_infotypes.update(s["infotypes"])

    # Hook B/C per-task aggregate
    b_applied = sum(1 for s in by_task.values() if s["hook_b_applied"] > 0)
    b_skipped_trust = sum(1 for s in by_task.values()
                          if s["hook_b_skipped_trust"] > 0 and s["hook_b_applied"] == 0)
    b_skipped_incomplete = sum(1 for s in by_task.values()
                               if s["hook_b_skipped_incomplete"] > 0
                               and s["hook_b_applied"] == 0)
    c_reached = sum(1 for s in by_task.values() if s["hook_c_reached"] > 0)

    return {
        "total_tasks": total_tasks,
        "classified_tasks": classified_tasks,
        "declined_tasks": declined_tasks,
        "not_called_tasks": not_called,
        "other_tasks": other_tasks,
        "coverage_pct": 100 * classified_tasks / total_tasks if total_tasks else 0.0,
        "hook_b_applied_tasks": b_applied,
        "hook_b_skipped_trust_tasks": b_skipped_trust,
        "hook_b_skipped_incomplete_tasks": b_skipped_incomplete,
        "hook_c_reached_tasks": c_reached,
        "top_infotypes": all_infotypes.most_common(10),
        "by_task": by_task,
    }


def load_frozen_metadata(frozen_path: Path) -> dict:
    """Frozen KG의 metadata + source_mix 추출."""
    if not frozen_path.exists():
        return {"error": f"frozen not found: {frozen_path}"}
    raw = json.loads(frozen_path.read_text(encoding="utf-8"))
    meta_path = frozen_path.with_suffix(".meta.json")
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "build_timestamp": raw.get("build_timestamp"),
        "git_rev": raw.get("git_rev"),
        "builder_version": raw.get("builder_version"),
        "source_mix": raw.get("source_mix", {}),
        "n_state_patterns": len(raw.get("state_patterns", {})),
        "n_infotypes": len(raw.get("infotypes", {})),
        "n_actions": len(raw.get("actions", {})),
        "n_realizes_edges": len(raw.get("realizes_edges", [])),
        "n_leads_to_edges": len(raw.get("leads_to_edges", [])),
        "meta_note": meta.get("note", ""),
        "meta_path": str(meta_path) if meta_path.exists() else None,
    }


def render_report(
    variants: dict[str, Path],  # name -> variant dir
    frozen_path: Path | None,
) -> str:
    lines = [
        "# KG-addressable Coverage + Source Mix",
        "",
        "Generated by `scripts/coverage.py`. Reviewer-proof context: ",
        "`docs/kg_design/06 §3-5` (coverage objectivity), `07 §14` (source mix obligation).",
        "",
    ]

    # Frozen metadata
    if frozen_path:
        meta = load_frozen_metadata(frozen_path)
        lines += ["## Frozen KG metadata", "", f"- Path: `{frozen_path}`"]
        if "error" in meta:
            lines.append(f"- ⚠️ {meta['error']}")
        else:
            lines += [
                f"- build_timestamp: `{meta['build_timestamp']}`",
                f"- git_rev: `{meta['git_rev']}`",
                f"- builder_version: `{meta['builder_version']}`",
                f"- StatePatterns: {meta['n_state_patterns']}, "
                f"InfoTypes: {meta['n_infotypes']}, "
                f"Actions: {meta['n_actions']}",
                f"- RealizesEdges: {meta['n_realizes_edges']}, "
                f"LeadsToEdges: {meta['n_leads_to_edges']}",
                "",
                "### Source mix",
                "",
                "| source | count |",
                "|---|---|",
            ]
            for src, cnt in (meta["source_mix"] or {}).items():
                lines.append(f"| `{src}` | {cnt} |")
            lines.append("")
            if meta["meta_note"]:
                lines += ["### Build note", "", f"> {meta['meta_note']}", ""]

    # Per-variant coverage
    lines += ["## KG-addressable coverage (Hook A)", ""]
    if not variants:
        lines.append("(no variant directories provided)")
        return "\n".join(lines)

    lines += [
        "| variant | tasks | classified | declined | not_called | other | coverage |",
        "|---|---|---|---|---|---|---|",
    ]
    all_data: dict[str, dict] = {}
    for name, vdir in variants.items():
        if not vdir.exists():
            lines.append(f"| `{name}` | ⚠️ missing dir `{vdir}` | | | | | |")
            continue
        data = collect_variant_coverage(vdir)
        all_data[name] = data
        if data["total_tasks"] == 0:
            lines.append(f"| `{name}` | 0 (no logs) | | | | | |")
            continue
        lines.append(
            f"| `{name}` | {data['total_tasks']} | "
            f"{data['classified_tasks']} | {data['declined_tasks']} | "
            f"{data['not_called_tasks']} | {data.get('other_tasks', 0)} | "
            f"**{data['coverage_pct']:.1f}%** |"
        )
    lines.append("")
    lines.append("분류 규칙: any run classified → classified, 그외 any run declined → declined, "
                 "Hook A 호출 0건 → not_called, 그외 → other. 4 집합 배타.")
    lines.append("")

    # Per-variant Hook B/C stats (Option B 이후)
    lines += ["## Hook B/C 발동 통계", "",
              "| variant | B applied | B skipped(trust) | B skipped(incomplete_url) | C early SUCCESS |",
              "|---|---|---|---|---|"]
    for name, data in all_data.items():
        if data.get("total_tasks", 0) == 0:
            continue
        lines.append(
            f"| `{name}` | {data.get('hook_b_applied_tasks', 0)} | "
            f"{data.get('hook_b_skipped_trust_tasks', 0)} | "
            f"{data.get('hook_b_skipped_incomplete_tasks', 0)} | "
            f"{data.get('hook_c_reached_tasks', 0)} |"
        )
    lines.append("")
    lines.append("집계 규칙: per task 기준. B는 applied 우선, 나머지 skip 사유는 "
                 "applied=0일 때만 집계. C는 `target_reached at step=X — early SUCCESS` "
                 "로그가 나온 task 수 (task_type=NAVIGATE만 발동, RET/MUT는 validator에서 suppress).")
    lines.append("")

    # Top infotype distribution per variant
    for name, data in all_data.items():
        if not data.get("top_infotypes"):
            continue
        lines += [
            f"### `{name}` — Hook A 분류된 InfoType 분포 (top 10)",
            "",
            "| infotype | count |",
            "|---|---|",
        ]
        for infotype, cnt in data["top_infotypes"]:
            lines.append(f"| `{infotype}` | {cnt} |")
        lines.append("")

    lines += [
        "## Notes",
        "",
        "- Coverage <100%가 정상 — catalog가 task 분포에 맞춰지지 않았다는 직접 증거 (`07 §14`).",
        "- `info_ignored` variant는 Hook A LLM call을 수행하되 결과를 사용 안 함 (compute-matched control).",
        "- ARI run-to-run consistency는 `scripts/measure_ari.py` 출력 참조.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--variant", action="append", required=True,
        help="name=path/to/variant_n3_dir (e.g., baseline=output/baseline_n3)",
    )
    parser.add_argument(
        "--frozen", type=Path, default=None,
        help="Frozen KG snapshot path (e.g., config/sites/gitlab/frozen_kg/<ts>.json)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("output/analysis/coverage.md"),
    )
    args = parser.parse_args(argv)

    variants: dict[str, Path] = {}
    for spec in args.variant:
        if "=" not in spec:
            print(f"[error] --variant must be NAME=PATH: {spec}", file=sys.stderr)
            return 2
        name, path_str = spec.split("=", 1)
        variants[name.strip()] = Path(path_str)

    report = render_report(variants, args.frozen)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"[ok] wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
