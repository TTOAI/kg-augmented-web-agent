"""Tests for benchmark-side outcome classifier.

Phase 3.I: classifier가 agent의 **neutral verdict** (AgentRunResult)를 받아
WebArena-Verified status enum (WebArenaRunResult)으로 매핑한다.

Hard-rule 경로:
- verdict=done_no_answer → SUCCESS
- verdict=stuck → UNKNOWN_ERROR
- verdict=done_with_answer + non-RETRIEVE → SUCCESS (answer 무시)

LLM 경로 (done_with_answer + RETRIEVE / abandoned):
- placeholder ('none', 'no match') → NOT_FOUND_ERROR
- valid answer → SUCCESS + retrieved_data
- abandoned → NOT_FOUND_ERROR / ACTION_NOT_ALLOWED_ERROR / ... 매핑
"""
from __future__ import annotations

import unittest

from site_adaptive_webagent.agent.types import AgentRunResult
from site_adaptive_webagent.benchmarks.webarena_verified.outcome_classifier import (
    classify_outcome,
)

from .fixtures import FakeLLMClient


def _done_with_answer(
    answer: str, *, task_type: str = "RETRIEVE", answer_label: str | None = None,
) -> AgentRunResult:
    return AgentRunResult(
        task_type=task_type,  # type: ignore[arg-type]
        verdict="done_with_answer",
        answer=answer,
        answer_label=answer_label,
    )


def _abandoned(reason: str, *, task_type: str = "RETRIEVE") -> AgentRunResult:
    return AgentRunResult(
        task_type=task_type,  # type: ignore[arg-type]
        verdict="abandoned",
        reason=reason,
    )


def _stuck(reason: str, *, task_type: str = "RETRIEVE") -> AgentRunResult:
    return AgentRunResult(
        task_type=task_type,  # type: ignore[arg-type]
        verdict="stuck",
        reason=reason,
    )


def _done_no_answer(task_type: str = "NAVIGATE") -> AgentRunResult:
    return AgentRunResult(
        task_type=task_type,  # type: ignore[arg-type]
        verdict="done_no_answer",
    )


class HardRuleMappingTests(unittest.TestCase):
    """LLM 호출 없이 hard-rule만으로 결정되는 경로."""

    def test_done_no_answer_maps_to_success(self) -> None:
        """NAVIGATE/MUTATE: done_no_answer → SUCCESS (retrieved_data=null)."""
        for tt in ("NAVIGATE", "MUTATE"):
            with self.subTest(task_type=tt):
                result = classify_outcome(
                    task="t", agent_result=_done_no_answer(tt), llm=None,
                )
                self.assertEqual(result.status, "SUCCESS")
                self.assertIsNone(result.retrieved_data)
                self.assertEqual(result.task_type, tt)

    def test_stuck_maps_to_unknown_error(self) -> None:
        """verdict=stuck → UNKNOWN_ERROR (scaffold 실패)."""
        result = classify_outcome(
            task="t", agent_result=_stuck("budget exceeded"), llm=None,
        )
        self.assertEqual(result.status, "UNKNOWN_ERROR")
        assert result.error_details is not None
        self.assertIn("budget", result.error_details)

    def test_done_with_answer_non_retrieve_maps_to_success(self) -> None:
        """NAVIGATE/MUTATE에서 done_with_answer가 들어와도 SUCCESS (LLM 호출 없음)."""
        result = classify_outcome(
            task="navigate somewhere",
            agent_result=_done_with_answer("irrelevant", task_type="NAVIGATE"),
            llm=None,
        )
        self.assertEqual(result.status, "SUCCESS")
        self.assertIsNone(result.retrieved_data)

    def test_done_with_answer_retrieve_no_llm_preserves_as_success(self) -> None:
        """LLM 미제공 시 RETRIEVE done_with_answer → SUCCESS + answer 보존."""
        result = classify_outcome(
            task="count todos",
            agent_result=_done_with_answer("42", answer_label="count"),
            llm=None,
        )
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.retrieved_data, ["42"])

    def test_done_with_answer_retrieve_comma_split(self) -> None:
        """쉼표 구분 multi-value는 list로 분해."""
        result = classify_outcome(
            task="ids",
            agent_result=_done_with_answer("1, 2, 3"),
            llm=None,
        )
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.retrieved_data, ["1", "2", "3"])

    def test_empty_answer_maps_to_unknown_error(self) -> None:
        """done_with_answer + empty answer → UNKNOWN_ERROR (이전 단계 re-prompt 빠져나옴)."""
        result = classify_outcome(
            task="t", agent_result=_done_with_answer(""), llm=None,
        )
        self.assertEqual(result.status, "UNKNOWN_ERROR")

    def test_abandoned_no_llm_maps_to_unknown_error(self) -> None:
        """LLM 미제공 시 abandoned → UNKNOWN_ERROR + reason을 error_details로."""
        result = classify_outcome(
            task="t", agent_result=_abandoned("cannot proceed"), llm=None,
        )
        self.assertEqual(result.status, "UNKNOWN_ERROR")
        assert result.error_details is not None
        self.assertIn("cannot proceed", result.error_details)


class LLMBackedMappingTests(unittest.TestCase):
    """LLM 호출 경로 (RETRIEVE done_with_answer + abandoned)."""

    def test_retrieve_placeholder_answer_becomes_not_found(self) -> None:
        """'none' 같은 placeholder answer → NOT_FOUND_ERROR."""
        llm_reply = (
            '{"status": "NOT_FOUND_ERROR", "retrieved_data": null, '
            '"error_details": "no match", "reason": "placeholder"}'
        )
        result = classify_outcome(
            task="Get the project ID with > 100 stars",
            agent_result=_done_with_answer("none"),
            llm=FakeLLMClient(llm_reply),
        )
        self.assertEqual(result.status, "NOT_FOUND_ERROR")
        self.assertIsNone(result.retrieved_data)

    def test_retrieve_valid_answer_preserved(self) -> None:
        """valid concrete answer → SUCCESS + retrieved_data."""
        llm_reply = (
            '{"status": "SUCCESS", "retrieved_data": ["42"], '
            '"error_details": null, "reason": "42 is a concrete count"}'
        )
        result = classify_outcome(
            task="How many commits?",
            agent_result=_done_with_answer("42"),
            llm=FakeLLMClient(llm_reply),
        )
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.retrieved_data, ["42"])

    def test_retrieve_invalid_json_falls_back_to_success(self) -> None:
        """LLM 응답 파싱 실패 시 SUCCESS + answer 보존 (agent 원본 신뢰)."""
        result = classify_outcome(
            task="t",
            agent_result=_done_with_answer("real_answer"),
            llm=FakeLLMClient("not json at all"),
        )
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.retrieved_data, ["real_answer"])

    def test_retrieve_invalid_status_falls_back_to_success(self) -> None:
        """Classifier가 enum 외 status 반환 시 SUCCESS + answer 보존."""
        llm_reply = '{"status": "BOGUS", "retrieved_data": null, "reason": "oops"}'
        result = classify_outcome(
            task="t",
            agent_result=_done_with_answer("x"),
            llm=FakeLLMClient(llm_reply),
        )
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.retrieved_data, ["x"])

    def test_retrieve_llm_exception_falls_back_to_success(self) -> None:
        class _ExplodingLLM:
            def complete(self, *, system: str, messages: list) -> str:
                raise RuntimeError("network failure")

        result = classify_outcome(
            task="t",
            agent_result=_done_with_answer("answer"),
            llm=_ExplodingLLM(),  # type: ignore[arg-type]
        )
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.retrieved_data, ["answer"])

    def test_abandoned_maps_to_not_found(self) -> None:
        """abandoned reason이 명확한 경우 NOT_FOUND_ERROR."""
        llm_reply = (
            '{"status": "NOT_FOUND_ERROR", '
            '"error_details": "entity absent", "reason": "target not on site"}'
        )
        result = classify_outcome(
            task="find X",
            agent_result=_abandoned("no such user on this instance"),
            llm=FakeLLMClient(llm_reply),
        )
        self.assertEqual(result.status, "NOT_FOUND_ERROR")

    def test_abandoned_maps_to_permission_denied(self) -> None:
        llm_reply = (
            '{"status": "PERMISSION_DENIED_ERROR", '
            '"error_details": "admin only", "reason": "acl"}'
        )
        result = classify_outcome(
            task="delete user",
            agent_result=_abandoned("user lacks admin permission"),
            llm=FakeLLMClient(llm_reply),
        )
        self.assertEqual(result.status, "PERMISSION_DENIED_ERROR")

    def test_abandoned_invalid_json_falls_back_to_unknown_error(self) -> None:
        result = classify_outcome(
            task="t",
            agent_result=_abandoned("some reason"),
            llm=FakeLLMClient("not json"),
        )
        self.assertEqual(result.status, "UNKNOWN_ERROR")
        assert result.error_details is not None
        self.assertIn("some reason", result.error_details)

    def test_markdown_fenced_response_parsed(self) -> None:
        llm_reply = (
            "```json\n"
            '{"status": "NOT_FOUND_ERROR", "retrieved_data": null, '
            '"error_details": "no match", "reason": "placeholder"}\n'
            "```"
        )
        result = classify_outcome(
            task="t",
            agent_result=_done_with_answer("no matching X"),
            llm=FakeLLMClient(llm_reply),
        )
        self.assertEqual(result.status, "NOT_FOUND_ERROR")


if __name__ == "__main__":
    unittest.main()
