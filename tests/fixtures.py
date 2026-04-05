"""테스트용 fake 데이터 팩토리 및 Playwright stub."""
from __future__ import annotations

import uuid
from typing import Any

from site_adaptive_webagent.runtime.enums import (
    ApprovalEventStatus,
    PriorConfidence,
    RecoveryResult,
    SiteOnboardingStatus,
    StepRecordStatus,
    TaskRunStatus,
    ValidationResult,
)
from site_adaptive_webagent.runtime.types import (
    ActionSchema,
    ApprovalEvent,
    FailurePattern,
    PageType,
    PolicyRule,
    RecoveryRecord,
    SiteProfile,
    StepRecord,
    TaskRun,
    ValidationRecord,
    ValidatorRule,
    WorkflowHint,
)

_SITE_ID = "gitlab"
_TASK_FAMILY = "dashboard_lookup"


def make_site_profile(
    *,
    site_id: str = _SITE_ID,
    onboarding_status: SiteOnboardingStatus = SiteOnboardingStatus.ACTIVE,
    prior_confidence: PriorConfidence = PriorConfidence.SUFFICIENT,
) -> SiteProfile:
    return SiteProfile(
        site_id=site_id,
        site_key=site_id,
        domain=f"{site_id}.example.com",
        login_type="ui",
        onboarding_status=onboarding_status,
        default_execution_mode="fast_path",
        prior_confidence=prior_confidence,
    )


def make_workflow_hint(
    *,
    site_id: str = _SITE_ID,
    task_family: str = _TASK_FAMILY,
) -> WorkflowHint:
    return WorkflowHint(
        workflow_hint_id=str(uuid.uuid4()),
        site_id=site_id,
        task_family=task_family,
        typical_step_order=["navigate", "inspect"],
        branch_points=["login_required"],
        expected_terminal_states=["validated"],
    )


def make_action_schema(*, site_id: str = _SITE_ID) -> ActionSchema:
    return ActionSchema(
        action_schema_id=str(uuid.uuid4()),
        site_id=site_id,
        action_key="click_dashboard",
        preconditions=["logged_in"],
        postconditions=["dashboard_visible"],
        preferred_locator_strategy="role",
    )


def make_validator_rule(
    *,
    site_id: str = _SITE_ID,
    task_family: str = _TASK_FAMILY,
    rule_type: str = "always_pass",
) -> ValidatorRule:
    return ValidatorRule(
        validator_rule_id=str(uuid.uuid4()),
        site_id=site_id,
        task_family=task_family,
        rule_type=rule_type,
        pass_criteria="",
    )


def make_policy_rule(
    *,
    site_id: str = _SITE_ID,
    policy_type: str = "allow",
) -> PolicyRule:
    return PolicyRule(
        policy_rule_id=str(uuid.uuid4()),
        site_id=site_id,
        action_key="click_dashboard",
        policy_type=policy_type,
        policy_decision="allow",
    )


def make_failure_pattern(*, site_id: str = _SITE_ID) -> FailurePattern:
    return FailurePattern(
        failure_pattern_id=str(uuid.uuid4()),
        site_id=site_id,
        failure_type="element_not_found",
        detection_signal="no_matching_element",
        recommended_recovery="reload_page",
    )


def make_page_type(*, site_id: str = _SITE_ID) -> PageType:
    return PageType(
        page_type_id=str(uuid.uuid4()),
        site_id=site_id,
        page_key="dashboard",
        url_patterns=["/dashboard"],
        structural_signals=["h1.dashboard-title"],
    )


def make_task_run(
    *,
    site_id: str = _SITE_ID,
    task_family: str = _TASK_FAMILY,
    status: TaskRunStatus = TaskRunStatus.RUNNING,
) -> TaskRun:
    return TaskRun(
        task_run_id=str(uuid.uuid4()),
        request_text="test request",
        site_id=site_id,
        task_family=task_family,
        run_mode="fast_path",
        status=status,
        started_at="2025-01-01T00:00:00Z",
        ended_at="2025-01-01T00:00:00Z",
        prior_used=True,
        validator_used=False,
        recovery_used=False,
    )


def make_step_record(
    *,
    task_run_id: str,
    step_type: str = "fast_path",
    status: StepRecordStatus = StepRecordStatus.SUCCEEDED,
) -> StepRecord:
    return StepRecord(
        step_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        step_index=0,
        step_type=step_type,
        status=status,
        pre_state_summary="before",
        post_state_summary="after",
    )


def make_validation_record(
    *,
    task_run_id: str,
    validator_rule_id: str,
    result: ValidationResult = ValidationResult.PASS,
) -> ValidationRecord:
    return ValidationRecord(
        validation_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        validator_rule_id=validator_rule_id,
        result=result,
        validated_at="2025-01-01T00:00:00Z",
    )


def make_recovery_record(
    *,
    task_run_id: str,
    failure_pattern_id: str,
    recovery_result: RecoveryResult = RecoveryResult.SUCCESS,
) -> RecoveryRecord:
    return RecoveryRecord(
        recovery_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        failure_pattern_id=failure_pattern_id,
        recovery_action="reload_page",
        recovery_result=recovery_result,
        recorded_at="2025-01-01T00:00:00Z",
    )


def make_approval_event(
    *,
    task_run_id: str,
    approval_status: ApprovalEventStatus = ApprovalEventStatus.REQUESTED,
) -> ApprovalEvent:
    return ApprovalEvent(
        approval_event_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        action_key="policy_required_action",
        approval_status=approval_status,
        reason="policy rule이 사전 승인을 요구합니다",
        recorded_at="2025-01-01T00:00:00Z",
    )


# --- Playwright stub (테스트용 가짜 페이지) ---

class FakeElementLocator:
    def __init__(self, page: "FakePage", selector: str, index: int) -> None:
        self.page = page
        self.selector = selector
        self.index = index

    async def inner_text(self) -> str:
        return self.page.selector_texts[self.selector][self.index]

    async def click(self) -> None:
        self.page.apply_click(self.selector, self.index)

    async def fill(self, value: str) -> None:
        self.page.last_filled = value

    async def press(self, key: str) -> None:
        self.page.last_pressed = key


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector

    async def all_inner_texts(self) -> list[str]:
        return list(self.page.selector_texts.get(self.selector, []))

    async def count(self) -> int:
        return len(self.page.selector_texts.get(self.selector, []))

    def nth(self, index: int) -> FakeElementLocator:
        return FakeElementLocator(self.page, self.selector, index)


class FakePage:
    def __init__(
        self,
        *,
        url: str,
        title_text: str,
        selector_texts: dict[str, list[str]],
        click_updates: dict[tuple[str, int], dict[str, Any]] | None = None,
    ) -> None:
        self.url = url
        self._title = title_text
        self.selector_texts = selector_texts
        self.click_updates = click_updates or {}
        self.last_filled: str | None = None
        self.last_pressed: str | None = None

    async def title(self) -> str:
        return self._title

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    async def goto(self, url: str) -> None:
        self.url = url

    def apply_click(self, selector: str, index: int) -> None:
        update = self.click_updates.get((selector, index), {})
        if "url" in update:
            self.url = str(update["url"])
        if "title" in update:
            self._title = str(update["title"])
        if "selector_texts" in update:
            self.selector_texts = dict(update["selector_texts"])


def make_fake_page(
    *,
    url: str = "https://example.com",
    title_text: str = "Page",
    headings: list[str] | None = None,
    text_lines: list[str] | None = None,
    links: list[str] | None = None,
    buttons: list[str] | None = None,
) -> FakePage:
    """기본값을 채운 FakePage를 생성한다."""
    return FakePage(
        url=url,
        title_text=title_text,
        selector_texts={
            "h1": headings or [],
            "h2": [],
            "[role='heading']": [],
            "main": text_lines or [],
            "article": [],
            "body": text_lines or [],
            "a": links or [],
            "button": buttons or [],
            "[role='button']": [],
        },
    )
