"""Tests for kg_solution.hint_generator."""
from __future__ import annotations

import unittest
from dataclasses import dataclass

from site_adaptive_webagent.kg_solution.hint_generator import (
    _fmt_action_labels,
    _normalize_label,
    generate_hint,
)
from site_adaptive_webagent.kg_solution.path_finder import PathResult, PathStep


@dataclass
class _FakeLLM:
    responses: list[str]
    calls: int = 0

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        r = self.responses[self.calls % len(self.responses)]
        self.calls += 1
        return r


def _exact_result() -> PathResult:
    return PathResult(
        strategy="exact",
        actual_target="project/issue_new_form",
        inferred_target="project/issue_new_form",
        path=[
            PathStep(
                source="dashboard/project_list/yours",
                target="project/main",
                actions=["a11yproject"],
                trust="high",
            ),
            PathStep(
                source="project/main",
                target="project/issue_list",
                actions=["Issues", "Issues 5"],
                trust="high",
            ),
            PathStep(
                source="project/issue_list",
                target="project/issue_new_form",
                actions=["New issue"],
                trust="high",
            ),
        ],
        hops=3,
    )


class ExactStrategyTests(unittest.TestCase):
    def test_exact_has_path_and_bindings(self):
        hint = generate_hint(
            _exact_result(),
            current="dashboard/project_list/yours",
            task="create an issue",
            bindings={"namespace": "a11y"},
        )
        assert hint is not None
        self.assertIn("KG navigation hint", hint)
        self.assertIn("project/issue_new_form", hint)
        self.assertIn("New issue", hint)
        self.assertIn("namespace=a11y", hint)

    def test_exact_zero_hops(self):
        result = PathResult(
            strategy="exact",
            actual_target="A",
            inferred_target="A",
            path=[],
            hops=0,
        )
        hint = generate_hint(result, current="A", task="stay", bindings={})
        assert hint is not None
        self.assertIn("already at target", hint)


class StayStrategyTests(unittest.TestCase):
    def test_stay_template(self):
        result = PathResult(
            strategy="stay_and_explore",
            actual_target="account/edit",
            inferred_target="project/issue_detail",
            path=None,
            hops=0,
            note="no cascade helped",
        )
        hint = generate_hint(
            result, current="account/edit", task="find issue", bindings={}
        )
        assert hint is not None
        self.assertIn("No direct path", hint)
        self.assertIn("explore", hint.lower())


class FallbackStrategyTests(unittest.TestCase):
    def test_family_sibling_uses_llm(self):
        llm = _FakeLLM(responses=["The agent should click Issues link..."])
        result = PathResult(
            strategy="family_sibling",
            actual_target="project/issue_list",
            inferred_target="project/issue_detail",
            path=[
                PathStep(
                    source="dashboard/project_list/yours",
                    target="project/issue_list",
                    actions=["Issues"],
                    trust="high",
                )
            ],
            hops=1,
            note="routed to sibling",
        )
        hint = generate_hint(
            result,
            current="dashboard/project_list/yours",
            task="open issue #5",
            bindings={},
            llm=llm,
        )
        assert hint is not None
        self.assertIn("click Issues", hint)
        self.assertEqual(llm.calls, 1)

    def test_fallback_cache_hits(self):
        llm = _FakeLLM(responses=["hint body"])
        result = PathResult(
            strategy="scope_entry",
            actual_target="project/main",
            inferred_target="project/rare",
            path=[
                PathStep(
                    source="A", target="project/main",
                    actions=["link"], trust="high",
                )
            ],
            hops=1,
        )
        cache: dict = {}
        h1 = generate_hint(
            result, current="A", task="t", bindings={}, llm=llm, cache=cache
        )
        h2 = generate_hint(
            result, current="A", task="t", bindings={}, llm=llm, cache=cache
        )
        self.assertEqual(h1, h2)
        self.assertEqual(llm.calls, 1)  # second call hit cache

    def test_fallback_no_llm_degrades_to_terse(self):
        result = PathResult(
            strategy="hub_fallback",
            actual_target="dashboard/hub",
            inferred_target="project/rare",
            path=[
                PathStep(
                    source="A", target="dashboard/hub",
                    actions=["go"], trust="high",
                )
            ],
            hops=1,
            note="routed to hub",
        )
        hint = generate_hint(
            result, current="A", task="t", bindings={}, llm=None
        )
        assert hint is not None
        self.assertIn("hub_fallback", hint)
        self.assertIn("routed to hub", hint)


class LabelNormalizationTests(unittest.TestCase):
    def test_strip_trailing_count(self):
        self.assertEqual(_normalize_label("Issues 5"), "Issues")
        self.assertEqual(_normalize_label("Open  3"), "Open")

    def test_strip_user_mention(self):
        self.assertEqual(_normalize_label("Assigned @alice"), "Assigned")

    def test_strip_issue_ref(self):
        self.assertEqual(_normalize_label("Link to #42 thread"), "Link to thread")

    def test_no_change_when_no_pattern(self):
        self.assertEqual(_normalize_label("New issue"), "New issue")

    def test_canonical_picked_from_most_frequent(self):
        # Two variants "Issues 5" and one literal "Issues" → normalized collapse
        # gives "Issues" × 3 → canonical="Issues".
        rendered = _fmt_action_labels(["Issues 5", "Issues 3", "Issues"])
        self.assertTrue(rendered.startswith('"Issues"'))

    def test_variants_surfaced_for_matching(self):
        rendered = _fmt_action_labels(["Issues 5", "Issues", "Issues 3"])
        self.assertIn("Issues 5", rendered)
        self.assertIn("Issues 3", rendered)

    def test_fallback_when_all_normalize_empty(self):
        rendered = _fmt_action_labels(["5", "@alice", "#42"])
        # All become empty after normalization; fallback to actions[0].
        self.assertIn("5", rendered)


class FailedStrategyTests(unittest.TestCase):
    def test_failed_returns_none(self):
        result = PathResult(
            strategy="failed",
            actual_target="X",
            inferred_target="X",
            path=None,
            note="unknown class",
        )
        self.assertIsNone(
            generate_hint(result, current="X", task="t", bindings={})
        )


if __name__ == "__main__":
    unittest.main()
