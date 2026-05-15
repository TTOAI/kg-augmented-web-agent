from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from site_adaptive_webagent.runtime.types import AgentVerdict, TaskType

RetrievedItem = str | int | float | bool | dict[str, Any] | None


@dataclass(slots=True)
class AgentRunResult:
    """Benchmark-agnostic agent verdict 결과.

    runtime의 neutral verdict만 보유한다. Benchmark-specific status/retrieved_data
    매핑은 benchmark adapter의 `outcome_classifier`가 수행한다.

    구조:
    - task_type: task 분류.
    - verdict: agent의 task-level 결론 (done_with_answer / done_no_answer /
      abandoned / stuck).
    - answer: done_with_answer 시 agent가 제출한 구체적 정답.
    - answer_label: done_with_answer 시 answer가 어떤 종류인지 (예: 'project_id').
    - reason: abandoned / stuck / done_*의 설명.
    """

    task_type: TaskType
    verdict: AgentVerdict
    answer: str | None = None
    answer_label: str | None = None
    reason: str | None = None

    @classmethod
    def stuck(cls, message: str, task_type: TaskType = "NAVIGATE") -> "AgentRunResult":
        """scaffold 레벨 실패 생성 헬퍼 (로드 실패·예외 등)."""
        return cls(
            task_type=task_type,
            verdict="stuck",
            reason=message,
        )
