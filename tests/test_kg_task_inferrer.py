"""Tests for kg_solution.task_inferrer."""
from __future__ import annotations

import unittest
from dataclasses import dataclass

from site_adaptive_webagent.kg.runtime.class_descriptions import (
    ClassCatalog,
    ClassDescription,
)
from site_adaptive_webagent.kg.runtime.task_inferrer import (
    _consensus,
    _extract_json,
    _merge_bindings,
    _parse_sample,
    infer_target,
)


def _catalog(*classes: str) -> ClassCatalog:
    return ClassCatalog(
        entries={
            c: ClassDescription(class_name=c, url_template=None, description="")
            for c in classes
        }
    )


@dataclass
class _FakeLLM:
    responses: list[str]

    def __post_init__(self):
        self._idx = 0

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        r = self.responses[self._idx % len(self.responses)]
        self._idx += 1
        return r


class ExtractJsonTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(_extract_json('{"a": 1}'), {"a": 1})

    def test_fenced_markdown(self):
        self.assertEqual(
            _extract_json('```json\n{"a": 1}\n```'), {"a": 1}
        )

    def test_embedded_in_prose(self):
        self.assertEqual(
            _extract_json('Sure, here: {"a": 1} done'), {"a": 1}
        )

    def test_invalid_returns_none(self):
        self.assertIsNone(_extract_json("not json at all"))


class ParseSampleTests(unittest.TestCase):
    def test_valid_in_set(self):
        cat = _catalog("project/issue_list")
        sample, rej = _parse_sample(
            '{"target_class": "project/issue_list", "bindings": {"namespace": "a11y"}, "reasoning": "x"}',
            cat,
        )
        self.assertEqual(sample.target_class, "project/issue_list")
        self.assertEqual(sample.bindings, {"namespace": "a11y"})
        self.assertIsNone(rej)

    def test_out_of_set_rejected(self):
        cat = _catalog("project/issue_list")
        sample, rej = _parse_sample(
            '{"target_class": "nonexistent/class", "bindings": {}}', cat
        )
        self.assertIsNone(sample.target_class)
        self.assertEqual(rej, "nonexistent/class")

    def test_null_target(self):
        cat = _catalog("project/issue_list")
        sample, rej = _parse_sample(
            '{"target_class": null, "bindings": {}}', cat
        )
        self.assertIsNone(sample.target_class)
        self.assertIsNone(rej)

    def test_malformed_json(self):
        cat = _catalog("project/issue_list")
        sample, rej = _parse_sample("garbage", cat)
        self.assertIsNone(sample.target_class)
        self.assertIsNone(rej)

    def test_empty_string_treated_as_none(self):
        cat = _catalog("project/issue_list")
        sample, _ = _parse_sample(
            '{"target_class": "", "bindings": {}}', cat
        )
        self.assertIsNone(sample.target_class)


class ConsensusTests(unittest.TestCase):
    def _mk(self, cls: str | None) -> "_Sample":
        from site_adaptive_webagent.kg.runtime.task_inferrer import InferSample
        return InferSample(target_class=cls, bindings={}, reasoning="", raw="")

    def test_3_same(self):
        samples = [self._mk("A"), self._mk("A"), self._mk("A")]
        winner, count = _consensus(samples, k=3)
        self.assertEqual(winner, "A")
        self.assertEqual(count, 3)

    def test_2_majority(self):
        samples = [self._mk("A"), self._mk("A"), self._mk("B")]
        winner, count = _consensus(samples, k=3)
        self.assertEqual(winner, "A")
        self.assertEqual(count, 2)

    def test_all_different_returns_none(self):
        samples = [self._mk("A"), self._mk("B"), self._mk("C")]
        winner, count = _consensus(samples, k=3)
        self.assertIsNone(winner)
        self.assertEqual(count, 1)

    def test_all_none_returns_none(self):
        samples = [self._mk(None), self._mk(None), self._mk(None)]
        winner, count = _consensus(samples, k=3)
        self.assertIsNone(winner)
        self.assertEqual(count, 0)

    def test_k5_requires_three_votes(self):
        # Threshold = ceil(5/2) = 3
        samples = [
            self._mk("A"), self._mk("A"), self._mk("B"),
            self._mk("B"), self._mk("C"),
        ]
        winner, count = _consensus(samples, k=5)
        self.assertIsNone(winner)  # A and B tied at 2, below threshold 3
        self.assertEqual(count, 2)

    def test_k5_with_three_agreeing_wins(self):
        samples = [
            self._mk("A"), self._mk("A"), self._mk("A"),
            self._mk("B"), self._mk("C"),
        ]
        winner, count = _consensus(samples, k=5)
        self.assertEqual(winner, "A")
        self.assertEqual(count, 3)

    def test_k2_requires_both_agree(self):
        # Strict-majority threshold (2//2)+1 = 2 → K=2 demands unanimity.
        samples = [self._mk("A"), self._mk(None)]
        winner, count = _consensus(samples, k=2)
        self.assertIsNone(winner)  # only 1 vote, need 2
        self.assertEqual(count, 1)

    def test_k2_both_agree(self):
        samples = [self._mk("A"), self._mk("A")]
        winner, count = _consensus(samples, k=2)
        self.assertEqual(winner, "A")
        self.assertEqual(count, 2)


class MergeBindingsTests(unittest.TestCase):
    def test_first_occurrence_wins(self):
        from site_adaptive_webagent.kg.runtime.task_inferrer import InferSample
        samples = [
            InferSample(
                target_class="A", bindings={"ns": "v1"}, reasoning="", raw=""
            ),
            InferSample(
                target_class="A", bindings={"ns": "v2", "p": "x"}, reasoning="", raw=""
            ),
            InferSample(
                target_class="B", bindings={"ns": "v3"}, reasoning="", raw=""
            ),
        ]
        merged = _merge_bindings(samples, "A")
        self.assertEqual(merged, {"ns": "v1", "p": "x"})


class InferTargetTests(unittest.TestCase):
    def test_consensus_happy_path(self):
        cat = _catalog("project/issue_list", "project/issue_new_form")
        responses = [
            '{"target_class": "project/issue_new_form", "bindings": {"namespace": "a11y"}}',
            '{"target_class": "project/issue_new_form", "bindings": {}}',
            '{"target_class": "project/issue_new_form", "bindings": {}}',
        ]
        llm = _FakeLLM(responses=responses)
        result = infer_target(
            sub_goal="navigate to issue creation form",
            task="create an issue in a11yproject",
            catalog=cat,
            llm=llm,
            k=3,
        )
        self.assertTrue(result.has_hint)
        self.assertEqual(result.target_class, "project/issue_new_form")
        self.assertEqual(result.agreement, 3)
        self.assertEqual(result.bindings, {"namespace": "a11y"})

    def test_no_consensus_returns_none(self):
        cat = _catalog("A", "B", "C")
        llm = _FakeLLM(responses=[
            '{"target_class": "A"}',
            '{"target_class": "B"}',
            '{"target_class": "C"}',
        ])
        result = infer_target(
            sub_goal="x", task="y", catalog=cat, llm=llm, k=3
        )
        self.assertFalse(result.has_hint)
        self.assertIn("consensus", result.note.lower())

    def test_out_of_set_rejected(self):
        cat = _catalog("A", "B")
        llm = _FakeLLM(responses=[
            '{"target_class": "UNKNOWN"}',
            '{"target_class": "UNKNOWN"}',
            '{"target_class": "UNKNOWN"}',
        ])
        result = infer_target(
            sub_goal="x", task="y", catalog=cat, llm=llm, k=3
        )
        self.assertFalse(result.has_hint)
        self.assertEqual(len(result.rejected_out_of_set), 3)

    def test_two_of_three_agrees(self):
        cat = _catalog("A", "B")
        llm = _FakeLLM(responses=[
            '{"target_class": "A"}',
            '{"target_class": "A"}',
            '{"target_class": "B"}',
        ])
        result = infer_target(
            sub_goal="x", task="y", catalog=cat, llm=llm, k=3
        )
        self.assertTrue(result.has_hint)
        self.assertEqual(result.target_class, "A")
        self.assertEqual(result.agreement, 2)


if __name__ == "__main__":
    unittest.main()
