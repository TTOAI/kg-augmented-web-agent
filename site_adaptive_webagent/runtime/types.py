from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# --- 에이전트 실행 결과 타입 ---

IntentAction = Literal["goto_url", "inspect_page", "click_target", "search_target", "unsupported"]
TaskType = Literal["RETRIEVE", "MUTATE", "NAVIGATE"]

# Benchmark-agnostic agent verdict. Phase 3.I refactor: runtime은 benchmark의
# status enum (NOT_FOUND_ERROR 등)을 말하지 않고, 이 중립 verdict만 배출한다.
# Benchmark adapter가 verdict → benchmark-specific status로 매핑한다.
#
# - done_with_answer: agent가 구체적 정답(answer)을 냄 (RETRIEVE 최종 단계)
# - done_no_answer:   sub-goal/task가 답 없이 완료됨 (NAVIGATE/MUTATE 성공)
# - abandoned:        agent가 명시적으로 "불가능/해당 없음" 판단 (report_failure)
# - stuck:            scaffold 자체 실패 (step budget / replan 소진, tool-call 누락 등)
# - sub_goal_failed:  **내부 전용**. sub-goal 단위 실패를 outer retry loop에 알리는
#                     control signal. execute_with_llm 종료 시점에는 발생하지 않아야
#                     하며 (retry/replan/stuck 중 하나로 resolve됨), benchmark
#                     classifier로 전달되지 않는다.
AgentVerdict = Literal[
    "done_with_answer",
    "done_no_answer",
    "abandoned",
    "stuck",
    "sub_goal_failed",
]


@dataclass(slots=True)
class IntentPlan:
    """task intent를 얕게 분류한 결과."""

    task_type: TaskType
    action: IntentAction
    target_phrase: str | None
    target_terms: list[str]
    explicit_url: str | None = None


@dataclass(slots=True)
class PageObservation:
    """현재 페이지에서 관찰한 핵심 상태 스냅샷."""

    url: str
    title: str
    headings: list[str]
    text_lines: list[str]
    links: list[str]
    buttons: list[str]
    inputs: list[str] = field(default_factory=list)  # placeholder / label 기반 입력 필드
    dropdown_options: list[str] = field(default_factory=list)  # 열린 드롭다운/메뉴 항목
    # Phase 3.F α: DOM에 rendered되어 있지만 collapsed/aria-hidden 상태라 visible
    # extraction에선 누락되는 navigation/option 항목. "[collapsed] label → path"
    # 형태로 사전 노출해 agent의 구조적 한계(sub-menu/filter dropdown 미발견)를 해소.
    latent_nav: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionOutcome:
    """Runtime이 반환하는 benchmark-agnostic agent verdict.

    Phase 3.I 이전: status가 WebArena status enum이었고 retrieved_data/error_details도
    benchmark-specific 필드였음. 이제는 중립 verdict + raw payload만 포함하고, benchmark
    adapter의 outcome_classifier가 이를 `WebArenaRunResult`로 매핑한다.
    """

    task_type: TaskType
    verdict: AgentVerdict
    answer: str | None = None  # done_with_answer 시 agent가 제출한 구체적 값
    reason: str | None = None  # abandoned / stuck / done_with_answer 의 설명

    # Agent's draft notes field — optional agent_label (RETRIEVE의 answer가 어떤 종류인지).
    answer_label: str | None = None


@dataclass(slots=True)
class BrowserSession:
    """브라우저 실행에 필요한 Playwright 컨텍스트."""

    pages: list[Any]
    sites: list[str]
    start_urls: list[str]
    plan: IntentPlan
