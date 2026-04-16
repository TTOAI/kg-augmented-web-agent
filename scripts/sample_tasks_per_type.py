"""WebArena-Verified GitLab 180 task 모집단에서 task_type별 N개를 random sampling.

정당화 (docs/kg_design/07 §3):
- 연구 질문이 "KG의 task type별 heterogeneous effect" → per-type equal sampling
- seed=42 고정으로 재현성 보장
- task_type 분류는 `run_baseline_n3.sh` 라인 37~45의 정규식 재사용 (사이트 공통 heuristic)

사용:
  python scripts/sample_tasks_per_type.py \\
      --input output/tasks.gitlab.json \\
      --per-type 10 \\
      --seed 42 \\
      --output output/tasks.30.json

출력:
  - output/tasks.30.json: 30 task (type별 10) JSON array
  - output/tasks.30.task_types.txt: `task_id<TAB>task_type` (runner 스크립트 호환)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

# run_baseline_n3.sh 라인 37-45의 정규식 그대로 (사이트 무관)
_MUTATE_RX = re.compile(
    r'\b(create|add|post|submit|delete|remove|rename|change|merge|assign|upload|invite'
    r'|fork|close|reopen|star|unstar|follow|unfollow|comment|approve|disapprove|set'
    r'|make|send|publish|archive|update|modify|edit)\b',
    re.IGNORECASE,
)
_RETRIEVE_RX = re.compile(
    r'\b(get |find |how many|what is|what are|who |tell me|count|number of|latest'
    r'|most recent|highest|which |where |how much)\b',
    re.IGNORECASE,
)


def classify_task_type(intent: str) -> str:
    """intent 정규식 기반 분류 — heuristic. Agent runtime 분류와 다를 수 있음 (후처리에서 재집계)."""
    if _MUTATE_RX.search(intent):
        return "MUTATE"
    if _RETRIEVE_RX.search(intent):
        return "RETRIEVE"
    return "NAVIGATE"


def sample_per_type(
    tasks: list[dict], per_type: int, seed: int,
) -> tuple[list[dict], dict[int, str]]:
    """task_type 각각에서 per_type개를 seed 기반 random sampling.

    Returns: (sampled tasks list, task_id → task_type dict)
    """
    by_type: dict[str, list[dict]] = {"NAVIGATE": [], "RETRIEVE": [], "MUTATE": []}
    type_map: dict[int, str] = {}
    for t in tasks:
        tt = classify_task_type(t["intent"])
        by_type[tt].append(t)
        type_map[int(t["task_id"])] = tt

    rng = random.Random(seed)
    sampled: list[dict] = []
    for tt in ("NAVIGATE", "RETRIEVE", "MUTATE"):
        pool = by_type[tt]
        if len(pool) < per_type:
            print(f"[warning] {tt} pool has only {len(pool)} tasks (< {per_type})",
                  file=sys.stderr)
            sampled.extend(pool)
        else:
            sampled.extend(rng.sample(pool, per_type))

    # task_id 순으로 정렬 (runner 스크립트 호환)
    sampled.sort(key=lambda t: int(t["task_id"]))
    return sampled, type_map


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output/tasks.gitlab.json"),
                        help="입력 모집단 task JSON")
    parser.add_argument("--per-type", type=int, default=10,
                        help="task_type 당 샘플 개수 (default: 10)")
    parser.add_argument("--seed", type=int, default=42,
                        help="random seed (default: 42)")
    parser.add_argument("--output", type=Path, default=Path("output/tasks.30.json"),
                        help="출력 sampled task JSON")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"[error] {args.input} not found", file=sys.stderr)
        return 2

    tasks = json.loads(args.input.read_text(encoding="utf-8"))
    sampled, type_map = sample_per_type(tasks, args.per_type, args.seed)

    # 출력 1: sampled task JSON
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(sampled, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # 출력 2: task_types.txt (runner 호환)
    types_path = args.output.with_suffix(".task_types.txt")
    lines = [f"{t['task_id']}\t{type_map[int(t['task_id'])]}" for t in sampled]
    types_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 검증 출력
    print(f"[ok] wrote {args.output} ({len(sampled)} tasks)")
    print(f"[ok] wrote {types_path}")
    dist: dict[str, int] = {}
    for t in sampled:
        tt = type_map[int(t["task_id"])]
        dist[tt] = dist.get(tt, 0) + 1
    print(f"[info] distribution: {dist}")
    print(f"[info] task_ids: {sorted(int(t['task_id']) for t in sampled)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
