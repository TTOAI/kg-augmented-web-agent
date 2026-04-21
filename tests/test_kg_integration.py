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
    DEFAULT_GITLAB_CONFIG,
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
        cascade_config=DEFAULT_GITLAB_CONFIG,
        cascade_enabled=cascade_enabled,
        replan_per_step=replan_per_step,
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

    def test_hint_included_when_provided(self):
        from site_adaptive_webagent.runtime.llm import build_observation_message

        class _Obs:
            url = "http://x"
            title = "t"
            headings = []
            text_lines = []
            links = []
            buttons = []
            inputs = []
            dropdown_options = []
            forms = []
            context_snippets = []

        msg = build_observation_message(
            task="task",
            observation=_Obs(),
            kg_hint="[KG hint]\nSome advice",
        )
        self.assertIn("[KG hint]", msg)
        self.assertIn("Some advice", msg)

    def test_hint_omitted_when_none(self):
        from site_adaptive_webagent.runtime.llm import build_observation_message

        class _Obs:
            url = "http://x"
            title = "t"
            headings = []
            text_lines = []
            links = []
            buttons = []
            inputs = []
            dropdown_options = []
            forms = []
            context_snippets = []

        msg = build_observation_message(
            task="task", observation=_Obs(), kg_hint=None
        )
        self.assertNotIn("[KG", msg)


class SubGoalKGContextTests(unittest.TestCase):
    def test_default_empty(self):
        ctx = SubGoalKGContext(target_class=None)
        self.assertEqual(ctx.bindings, {})
        self.assertIsNone(ctx.cached_initial_path)
        self.assertEqual(ctx.rejected_out_of_set, [])


if __name__ == "__main__":
    unittest.main()
