"""Deterministic NAV/RET/MUT classifier for measurement-2 task universe.

Implements the **leading verb/phrase** rule pinned in
docs/evaluation/measurement_2_lock.md §5.1 verbatim: the intent's *leading*
verb/phrase determines the type (NOT mere presence anywhere — that would let
the noun "merge requests" trip the MUT verb "merge"). Priority on a leading
match: MUT > RET > NAV > type_review. No LLM — fully reproducible; the script
is the audit trail for the committed `type` field.

Usage:
    python scripts/eval/classify_task_type_rule.py docs/evaluation/task_universe.gitlab.json
writes `type` (+ `type_review` flag for unmatched) in place and prints a summary.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MUT = ["set", "create", "add", "invite", "post", "delete", "update",
       "remove", "assign", "merge", "close", "fork", "star"]
RET = ["what", "which", "who", "how many", "list the", "find the value",
       "get the", "tell me"]
NAV = ["open", "go to", "navigate", "show", "display", "access"]


def _leads_with(t: str, terms: list[str]) -> bool:
    """True if normalized intent `t` *begins* with any term (word/phrase)."""
    for term in terms:
        if " " in term:
            if t == term or t.startswith(term + " "):
                return True
        elif re.match(rf"{re.escape(term)}\b", t):
            return True
    return False


def classify(intent: str) -> tuple[str, bool]:
    """Return (type, needs_review). needs_review True when no leading rule matched."""
    t = intent.lower().lstrip(" \"'[(")
    if _leads_with(t, MUT):
        return "MUT", False
    if _leads_with(t, RET):
        return "RET", False
    if _leads_with(t, NAV):
        return "NAV", False
    return "type_review", True


def main(argv: list[str]) -> int:
    path = Path(argv[0])
    tasks = json.loads(path.read_text(encoding="utf-8"))
    counts = {"MUT": 0, "RET": 0, "NAV": 0, "type_review": 0}
    review: list[tuple[int, str]] = []
    for task in tasks:
        ttype, needs = classify(task["intent"])
        task["type"] = ttype
        if needs:
            task["type_review"] = True
            review.append((task["task_id"], task["intent"]))
        counts[ttype] += 1
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"[ok] {path} — {len(tasks)} tasks")
    print("분포:", counts)
    if review:
        print(f"\ntype_review ({len(review)}개) — 수동 확정 필요:")
        for tid, intent in review:
            print(f"  #{tid}: {intent}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
