"""Integration tests for kg_solution.integration."""
from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from site_adaptive_webagent.kg_solution.class_descriptions import (
    ClassCatalog,
    ClassDescription,
)
from site_adaptive_webagent.kg_solution.integration import (
    KGSession,
    SubGoalKGContext,
)
from site_adaptive_webagent.kg_solution.path_finder import (
    CascadeConfig,
    PathResult,
    PathStep,
)


@dataclass
class _FakeLLM:
    responses: list[str] = field(default_factory=list)
    calls: int = 0

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        if not self.responses:
            return "{}"
        r = self.responses[self.calls % len(self.responses)]
        self.calls += 1
        return r


def _make_session(
    *,
    classifier: Callable[[str], Optional[str]] = lambda u: None,
    adjacency: Optional[dict] = None,
    all_classes: Optional[set[str]] = None,
    responses: Optional[list[str]] = None,
    cascade_enabled: bool = True,
    replan_per_step: bool = True,
    action_catalog: Optional[dict] = None,
    expose_actions: bool = True,
) -> KGSession:
    adjacency = adjacency or {}
    all_classes = all_classes or set(adjacency.keys())
    llm = _FakeLLM(responses=responses or [])
    catalog = ClassCatalog(entries={
        "A": ClassDescription(class_name="A", url_template=None, description=""),
        "B": ClassDescription(class_name="B", url_template=None, description=""),
    })
    return KGSession(
        classifier=classifier,
        adjacency=adjacency,
        all_classes=all_classes,
        catalog=catalog,
        inferrer_llm=llm,
        hint_llm=llm,
        cascade_config=CascadeConfig(scope_entries={}, hub=""),
        cascade_enabled=cascade_enabled,
        replan_per_step=replan_per_step,
        action_catalog=action_catalog or {},
        expose_actions=expose_actions,
    )


class KGSessionMethodsTests(unittest.TestCase):
    def test_classify_url_swallows_exception(self):
        def boom(_: str) -> str:
            raise RuntimeError("bad url")
        session = _make_session(classifier=boom)
        self.assertIsNone(session.classify_url("http://x"))

    def test_classify_url_passthrough(self):
        session = _make_session(classifier=lambda u: "A" if u.endswith("/a") else None)
        self.assertEqual(session.classify_url("http://x/a"), "A")
        self.assertIsNone(session.classify_url("http://x/z"))

    def test_infer_target_success(self):
        responses = ['{"target_class": "A", "bindings": {}}'] * 3
        session = _make_session(responses=responses)
        ctx = session.infer_target_for_sub_goal("navigate to A", "task")
        self.assertEqual(ctx.target_class, "A")
        self.assertEqual(ctx.agreement, 3)

    def test_infer_target_no_consensus(self):
        responses = [
            '{"target_class": "A"}',
            '{"target_class": "B"}',
            '{"target_class": null}',
        ]
        session = _make_session(responses=responses)
        ctx = session.infer_target_for_sub_goal("x", "y")
        self.assertIsNone(ctx.target_class)

    def test_find_path_exact(self):
        adj = {"X": [{"target": "A", "actions": ["click"], "trust": "high"}]}
        session = _make_session(adjacency=adj, all_classes={"X", "A"})
        result = session.find_path("X", "A")
        self.assertEqual(result.strategy, "exact")

    def test_find_path_v1b_cascade_disabled(self):
        # target A unreachable from X; sibling A2 reachable.
        adj = {"X": [{"target": "A2", "actions": ["click"], "trust": "high"}]}
        session = _make_session(
            adjacency=adj,
            all_classes={"X", "A", "A2"},
            cascade_enabled=False,
        )
        result = session.find_path("X", "A")
        self.assertEqual(result.strategy, "stay_and_explore")

    def test_find_path_v1_cascade_enabled_returns_sibling(self):
        adj = {"X": [{"target": "scope/item_list", "actions": ["c"], "trust": "high"}]}
        session = _make_session(
            adjacency=adj,
            all_classes={"X", "scope/item_list", "scope/item_detail"},
            cascade_enabled=True,
        )
        result = session.find_path("X", "scope/item_detail")
        self.assertEqual(result.strategy, "family_sibling")

    def test_generate_hint_exact_no_llm_needed(self):
        session = _make_session()
        path = PathResult(
            strategy="exact",
            actual_target="A",
            inferred_target="A",
            path=[
                PathStep(
                    source="X", target="A",
                    actions=["Go"], trust="high",
                )
            ],
            hops=1,
        )
        hint = session.generate_hint(
            path, current="X", task="t", bindings={}
        )
        assert hint is not None
        self.assertIn("KG navigation hint", hint)

    def test_generate_hint_swallows_exception(self):
        # Hint LLM raises; session returns None instead of propagating.
        class _BoomLLM:
            def complete(self, **kw):
                raise RuntimeError("boom")

        session = _make_session()
        session.hint_llm = _BoomLLM()
        path = PathResult(
            strategy="family_sibling",
            actual_target="A",
            inferred_target="A_target",
            path=[
                PathStep(
                    source="X", target="A",
                    actions=["go"], trust="high",
                )
            ],
            hops=1,
        )
        # The hint_generator handles the exception internally and falls back
        # to a terse template — verify session forwards that without crashing.
        hint = session.generate_hint(
            path, current="X", task="t", bindings={}
        )
        self.assertIsNotNone(hint)  # falls back to terse template with note


class BuildObservationMessageHintInjectionTests(unittest.TestCase):
    """Verify that build_observation_message surfaces the kg_hint section."""

    def _obs(self, inputs=None):
        class _Obs:
            url = "http://x"
            title = "t"
            headings = []
            text_lines = []
            links = []
            buttons = []
            dropdown_options = []
            forms = []
            context_snippets = []
        o = _Obs()
        o.inputs = inputs or []
        return o

    def test_hint_included_when_provided(self):
        from site_adaptive_webagent.runtime.llm import build_observation_message
        msg = build_observation_message(
            task="task",
            observation=self._obs(),
            kg_hint="[KG hint]\nSome advice",
        )
        self.assertIn("[KG hint]", msg)
        self.assertIn("Some advice", msg)

    def test_hint_omitted_when_none(self):
        from site_adaptive_webagent.runtime.llm import build_observation_message
        msg = build_observation_message(
            task="task", observation=self._obs(), kg_hint=None
        )
        self.assertNotIn("[KG", msg)

    def test_mutate_checklist_injected_when_form_present(self):
        from site_adaptive_webagent.runtime.llm import build_observation_message
        msg = build_observation_message(
            task="Create new project",
            observation=self._obs(inputs=["project-name"]),
            task_type="MUTATE",
        )
        self.assertIn("Form submission checklist", msg)
        self.assertIn("empty", msg.lower())

    def test_mutate_checklist_skipped_when_no_form(self):
        from site_adaptive_webagent.runtime.llm import build_observation_message
        msg = build_observation_message(
            task="Create new project",
            observation=self._obs(inputs=[]),
            task_type="MUTATE",
        )
        self.assertNotIn("Form submission checklist", msg)

    def test_checklist_not_injected_for_navigate(self):
        from site_adaptive_webagent.runtime.llm import build_observation_message
        msg = build_observation_message(
            task="Navigate to page",
            observation=self._obs(inputs=["search"]),
            task_type="NAVIGATE",
        )
        self.assertNotIn("Form submission checklist", msg)


class SubGoalKGContextTests(unittest.TestCase):
    def test_default_empty(self):
        ctx = SubGoalKGContext(target_class=None)
        self.assertEqual(ctx.bindings, {})
        self.assertIsNone(ctx.cached_initial_path)
        self.assertEqual(ctx.rejected_out_of_set, [])


class GetClassActionsTests(unittest.TestCase):
    def test_returns_entry_when_present(self):
        session = _make_session(
            action_catalog={
                "A": {
                    "instance_count": 3,
                    "navigation_actions": [{"label": "X", "instance_freq": 1}],
                    "internal_actions": [],
                }
            }
        )
        entry = session.get_class_actions("A")
        assert entry is not None
        self.assertEqual(entry["instance_count"], 3)

    def test_returns_none_when_missing(self):
        session = _make_session(action_catalog={})
        self.assertIsNone(session.get_class_actions("A"))

    def test_returns_none_for_empty_class_name(self):
        session = _make_session(
            action_catalog={"A": {"navigation_actions": []}}
        )
        self.assertIsNone(session.get_class_actions(""))


class GenerateHintForwardsActionsTests(unittest.TestCase):
    def test_generate_hint_includes_action_section(self):
        from site_adaptive_webagent.kg_solution.path_finder import (
            PathResult,
            PathStep,
        )

        session = _make_session()
        result = PathResult(
            strategy="exact",
            actual_target="A",
            inferred_target="A",
            path=[
                PathStep(
                    source="X", target="A", actions=["Go"], trust="high"
                )
            ],
            hops=1,
        )
        actions = {
            "navigation_actions": [
                {"label": "Personal", "target_class": "A",
                 "sample_href": "/dashboard?personal=true",
                 "tag": "a", "role": None, "instance_freq": 3,
                 "self_edge": True}
            ],
            "internal_actions": [],
        }
        hint = session.generate_hint(
            result,
            current="X",
            task="t",
            bindings={},
            current_class_actions=actions,
        )
        assert hint is not None
        self.assertIn("Personal", hint)


if __name__ == "__main__":
    unittest.main()
