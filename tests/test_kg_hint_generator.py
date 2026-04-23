"""Tests for kg_solution.hint_generator."""
from __future__ import annotations

import unittest
from dataclasses import dataclass

from site_adaptive_webagent.kg.runtime.hint_generator import (
    _fmt_action_labels,
    _normalize_label,
    generate_hint,
)
from site_adaptive_webagent.kg.runtime.path_finder import PathResult, PathStep


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


class RenderClassActionsTests(unittest.TestCase):
    def _catalog(self):
        return {
            "navigation_actions": [
                {"label": "Personal", "target_class": "dashboard/project_list/yours",
                 "sample_href": "http://x/dashboard?personal=true&sort=created_desc",
                 "tag": "a", "role": None, "instance_freq": 3, "self_edge": True},
                {"label": "Starred 3", "target_class": "dashboard/project_list/starred",
                 "sample_href": "http://x/dashboard/projects/starred",
                 "tag": "a", "role": None, "instance_freq": 3, "self_edge": False},
                {"label": "New project", "target_class": "global/new_project_form",
                 "sample_href": "http://x/projects/new",
                 "tag": "a", "role": None, "instance_freq": 2, "self_edge": False},
            ],
            "internal_actions": [
                {"label": "Last created", "tag": "button", "role": None,
                 "type": None, "instance_freq": 2},
                {"label": "Updated date", "tag": "button", "role": None,
                 "type": None, "instance_freq": 1},
            ],
        }

    def test_empty_input_returns_empty(self):
        from site_adaptive_webagent.kg.runtime.hint_generator import (
            _render_class_actions,
        )
        self.assertEqual(_render_class_actions(None), "")
        self.assertEqual(_render_class_actions({}), "")

    def test_renders_nav_and_internal(self):
        from site_adaptive_webagent.kg.runtime.hint_generator import (
            _render_class_actions,
        )
        out = _render_class_actions(self._catalog())
        self.assertIn("Personal", out)
        self.assertIn("dashboard/project_list/yours", out)
        self.assertIn("personal=true", out)  # query is preserved
        self.assertIn("Last created", out)
        self.assertIn("button", out)

    def test_excludes_labels_already_in_path(self):
        from site_adaptive_webagent.kg.runtime.hint_generator import (
            _render_class_actions,
        )
        out = _render_class_actions(
            self._catalog(),
            exclude_labels={"Personal"},
        )
        self.assertNotIn("Personal", out)
        self.assertIn("Starred", out)  # other labels still rendered

    def test_limits_respected(self):
        from site_adaptive_webagent.kg.runtime.hint_generator import (
            _render_class_actions,
        )
        out = _render_class_actions(
            self._catalog(), limit_nav=1, limit_int=1
        )
        # Only top-freq nav and internal included
        self.assertIn("Personal", out)
        self.assertNotIn("New project", out)
        self.assertIn("Last created", out)
        self.assertNotIn("Updated date", out)


class ActionsInjectedIntoHintTests(unittest.TestCase):
    def _catalog(self):
        return {
            "navigation_actions": [
                {"label": "Personal", "target_class": "dashboard/project_list/yours",
                 "sample_href": "http://x/dashboard?personal=true",
                 "tag": "a", "role": None, "instance_freq": 3, "self_edge": True},
            ],
            "internal_actions": [
                {"label": "Last created", "tag": "button", "role": None,
                 "type": None, "instance_freq": 2},
            ],
        }

    def test_exact_template_includes_actions(self):
        hint = generate_hint(
            _exact_result(),
            current="dashboard/project_list/yours",
            task="find my personal projects",
            bindings={},
            current_class_actions=self._catalog(),
        )
        assert hint is not None
        self.assertIn("Personal", hint)
        self.assertIn("Last created", hint)

    def test_stay_template_includes_actions(self):
        from site_adaptive_webagent.kg.runtime.path_finder import PathResult
        result = PathResult(
            strategy="stay_and_explore",
            actual_target="A",
            inferred_target="B",
            path=None,
            note="n",
        )
        hint = generate_hint(
            result,
            current="A",
            task="t",
            bindings={},
            current_class_actions=self._catalog(),
        )
        assert hint is not None
        self.assertIn("Personal", hint)

    def test_no_actions_dict_no_section(self):
        hint = generate_hint(
            _exact_result(),
            current="dashboard/project_list/yours",
            task="t",
            bindings={},
            current_class_actions=None,
        )
        assert hint is not None
        self.assertNotIn("Available navigation on this page", hint)
        self.assertNotIn("In-page controls", hint)

    def test_path_labels_excluded_from_actions(self):
        # exact path includes "Click 'a11yproject'"; if a11yproject is also
        # a nav action label, it should not appear in actions section.
        catalog = {
            "navigation_actions": [
                {"label": "a11yproject", "target_class": "project/main",
                 "sample_href": "http://x/a11yproject", "tag": "a",
                 "role": None, "instance_freq": 3, "self_edge": False},
                {"label": "Starred", "target_class": "X",
                 "sample_href": "http://x/s", "tag": "a",
                 "role": None, "instance_freq": 2, "self_edge": False},
            ],
            "internal_actions": [],
        }
        hint = generate_hint(
            _exact_result(),
            current="dashboard/project_list/yours",
            task="t",
            bindings={},
            current_class_actions=catalog,
        )
        assert hint is not None
        # "a11yproject" is in path steps; should not be re-surfaced in action section
        nav_section_idx = hint.find("Available navigation on this page")
        if nav_section_idx >= 0:
            nav_section = hint[nav_section_idx:]
            self.assertNotIn("- [a11yproject]", nav_section)
            self.assertIn("Starred", nav_section)


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
