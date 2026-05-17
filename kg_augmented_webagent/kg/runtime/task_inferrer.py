"""Infer the target page class for a sub-goal using an LLM.

Uses K-sample self-consistency to filter low-agreement inferences: if the K
samples do not reach a 2/K majority on a single class, the sub-goal is
considered ambiguous and no hint is produced (returns `target_class=None`).
The LLM is constrained to a closed set of known classes; any response outside
the set is rejected as invalid.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from kg_augmented_webagent.runtime.llm import LLMClient

from .class_descriptions import ClassCatalog

logger = logging.getLogger("agent_runtime")

SYSTEM_PROMPT = (
    "You are a web navigation planner. You are given a task and the current "
    "sub-goal toward that task. Map the sub-goal to the single most "
    "appropriate page class from the provided closed set of known classes. "
    "You MUST pick one class from the list or return null if no class fits. "
    "Extract any entity bindings (project namespace, project name, etc.) "
    "that the sub-goal or task mentions. Respond with JSON only, no "
    "commentary, no markdown code fences.\n\n"
    "Class selection rules:\n"
    "1. Prefer user-scoped classes (scope=user or scope=user_profile) when "
    "the task uses first-person pronouns ('my', 'I', 'me') or refers to the "
    "current account's resources across the site. Do NOT pick an "
    "entity-scoped class unless the task explicitly names that entity.\n"
    "2. Prefer entity-scoped classes only when the task binds to a specific "
    "entity (project, forum, group, namespace, repo, etc.) named or clearly "
    "implied in the task.\n"
    "3. Prefer scope=admin classes only when the task requires administrative "
    "privileges or site-wide configuration.\n"
    "4. Read each class's `triggers` and `not_for` fields — these are the "
    "primary disambiguation signal, more reliable than URL or name alone.\n"
    "5. If two classes have similar `role`, the one whose `triggers` match "
    "the task phrasing wins."
)

USER_TEMPLATE = """Task: {task}

Current sub-goal: {sub_goal}

Available classes (closed set, one per line):
{catalog}

Respond with JSON only in this exact shape:
{{"target_class": "<one of the listed classes, or null>",
  "bindings": {{"<slot>": "<value>", ...}},
  "reasoning": "<one sentence>"}}
"""


@dataclass
class InferSample:
    target_class: Optional[str]
    bindings: dict[str, str]
    reasoning: str
    raw: str


@dataclass
class InferResult:
    target_class: Optional[str]
    bindings: dict[str, str]
    samples: list[InferSample] = field(default_factory=list)
    agreement: int = 0
    rejected_out_of_set: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def has_hint(self) -> bool:
        return self.target_class is not None


def _extract_json(text: str) -> Optional[dict]:
    text = text.strip()
    # Strip common code fences.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text.strip(), flags=re.MULTILINE)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _parse_sample(raw: str, catalog: ClassCatalog) -> tuple[InferSample, Optional[str]]:
    """Return (sample, rejected_class_name_if_any)."""
    payload = _extract_json(raw)
    if payload is None:
        return (
            InferSample(target_class=None, bindings={}, reasoning="", raw=raw),
            None,
        )
    target = payload.get("target_class")
    if target == "" or target == "null":
        target = None
    rejected: Optional[str] = None
    if target is not None and target not in catalog:
        rejected = target
        target = None
    bindings_raw = payload.get("bindings") or {}
    if not isinstance(bindings_raw, dict):
        bindings_raw = {}
    bindings = {
        str(k): str(v)
        for k, v in bindings_raw.items()
        if v not in (None, "", [], {})
    }
    reasoning = str(payload.get("reasoning") or "")[:300]
    return (
        InferSample(
            target_class=target,
            bindings=bindings,
            reasoning=reasoning,
            raw=raw,
        ),
        rejected,
    )


def _consensus(
    samples: list[InferSample], k: Optional[int] = None
) -> tuple[Optional[str], int]:
    """Return (winning_class, vote_count).

    Requires strict-majority votes: `floor(K/2) + 1`.
      K=2 → 2 (both agree)
      K=3 → 2
      K=4 → 3
      K=5 → 3
    """
    total = k if k is not None else len(samples)
    threshold = (total // 2) + 1
    classes = [s.target_class for s in samples if s.target_class]
    if not classes:
        return None, 0
    winner, count = Counter(classes).most_common(1)[0]
    if count < threshold:
        return None, count
    return winner, count


def _merge_bindings(samples: list[InferSample], winner: str) -> dict[str, str]:
    merged: dict[str, str] = {}
    for s in samples:
        if s.target_class != winner:
            continue
        for k, v in s.bindings.items():
            merged.setdefault(k, v)
    return merged


def infer_target(
    *,
    sub_goal: str,
    task: str,
    catalog: ClassCatalog,
    llm: LLMClient,
    k: int = 3,
) -> InferResult:
    """Map sub-goal to a target class via K-sample self-consistency.

    Returns InferResult with `target_class=None` if (a) the LLM cannot
    produce a valid class in K tries, (b) no majority of at least 2/K
    agrees on a single class, or (c) all samples pick classes outside the
    closed set.
    """
    catalog_formatted = catalog.format_for_prompt(include_url=True)
    user_msg = USER_TEMPLATE.format(
        task=task.strip(),
        sub_goal=sub_goal.strip(),
        catalog=catalog_formatted,
    )
    samples: list[InferSample] = []
    rejected: list[str] = []
    for _ in range(k):
        try:
            raw = llm.complete(
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
        except Exception as exc:
            logger.warning("[KG] infer_target LLM call failed: %s", exc)
            samples.append(
                InferSample(target_class=None, bindings={}, reasoning="", raw="")
            )
            continue
        sample, reject = _parse_sample(raw, catalog)
        samples.append(sample)
        if reject:
            rejected.append(reject)
    winner, count = _consensus(samples, k=k)
    if winner is None:
        return InferResult(
            target_class=None,
            bindings={},
            samples=samples,
            agreement=count,
            rejected_out_of_set=rejected,
            note=(
                f"No consensus among {k} samples (threshold "
                f"{(k // 2) + 1}, got {count})"
                if count > 0
                else "No valid in-set class inferred"
            ),
        )
    return InferResult(
        target_class=winner,
        bindings=_merge_bindings(samples, winner),
        samples=samples,
        agreement=count,
        rejected_out_of_set=rejected,
    )
