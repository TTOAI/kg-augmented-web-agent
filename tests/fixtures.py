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
        display_name=site_id,
        base_url=f"https://{site_id}.example.com",
        auth_type="session",
        onboarding_status=onboarding_status,
        prior_confidence=prior_confidence,
    )


def make_action_schema(*, site_id: str = _SITE_ID) -> ActionSchema:
    return ActionSchema(
        action_schema_id=str(uuid.uuid4()),
        site_id=site_id,
        action_key="click_dashboard",
        display_name="대시보드로 이동",
        description="프로젝트 대시보드 페이지로 이동한다.",
        source_page_key="home",
        target_page_key="dashboard",
        preconditions=["logged_in"],
        postconditions=["dashboard_visible"],
        locator_strategy="role",
        locator_value="",
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
        reason="",
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
        display_name="프로젝트 대시보드",
        description="프로젝트 개요, 지표, 빠른 링크를 보여주는 페이지.",
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


# --- LLM stub ---

class FakeLLMClient:
    """테스트용 고정 응답 LLMClient stub."""

    def __init__(self, responses: list[str] | str) -> None:
        self._responses = [responses] if isinstance(responses, str) else responses
        self._index = 0
        self.calls: list[dict] = []

    def complete(self, *, system: str, messages: list[dict[str, str]]) -> str:
        self.calls.append({"system": system, "messages": list(messages)})  # 스냅샷 저장
        response = self._responses[min(self._index, len(self._responses) - 1)]
        self._index += 1
        return response


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

    async def get_attribute(self, name: str) -> str | None:
        attrs = self.page.element_attributes.get((self.selector, self.index), {})
        return attrs.get(name)


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

    async def evaluate_all(self, _js: str) -> list[Any]:
        """evaluate_all() stub: JS를 실행하지 않고 selector 데이터로 결과를 시뮬레이션한다.

        우선순위: innerText → placeholder → aria-label → title → name
        """
        texts = list(self.page.selector_texts.get(self.selector, []))
        results = []
        for i, text in enumerate(texts[:50]):
            if text:
                results.append(text)
            else:
                attrs = self.page.element_attributes.get((self.selector, i), {})
                fallback = (
                    attrs.get("placeholder")
                    or attrs.get("aria-label")
                    or attrs.get("title")
                    or attrs.get("name")
                    or ""
                )
                if fallback:
                    results.append(fallback)
        return results


class FakeRoleLocator:
    """get_by_role() stub — role+name으로 matching되는 요소를 찾는다."""

    def __init__(self, page: "FakePage", role: str, name: str) -> None:
        self.page = page
        self.role = role
        self.name = name.lower()
        self._matched: list[tuple[str, int]] = self._find_matches()

    def _find_matches(self) -> list[tuple[str, int]]:
        matches = []
        # role에 맞는 selector_texts 순회 (a→link, button→button)
        role_map = {"link": "a", "button": "button"}
        selector = role_map.get(self.role, self.role)
        texts = self.page.selector_texts.get(selector, [])
        for i, text in enumerate(texts):
            attrs = self.page.element_attributes.get((selector, i), {})
            candidates = [
                text.lower(),
                (attrs.get("aria-label") or "").lower(),
                (attrs.get("title") or "").lower(),
            ]
            if any(self.name in c for c in candidates if c):
                matches.append((selector, i))
        return matches

    async def count(self) -> int:
        return len(self._matched)

    @property
    def first(self) -> "FakeRoleLocatorSingle":
        return FakeRoleLocatorSingle(self.page, self._matched[0] if self._matched else None)

    def nth(self, index: int) -> "FakeRoleLocatorSingle":
        if index < len(self._matched):
            return FakeRoleLocatorSingle(self.page, self._matched[index])
        return FakeRoleLocatorSingle(self.page, None)


class FakeRoleLocatorSingle:
    def __init__(self, page: "FakePage", match: tuple[str, int] | None) -> None:
        self.page = page
        self._match = match

    async def click(self) -> None:
        if self._match:
            self.page.apply_click(*self._match)

    async def get_attribute(self, name: str) -> str | None:
        if self._match is None:
            return None
        attrs = self.page.element_attributes.get(self._match, {})
        return attrs.get(name)


class FakePage:
    def __init__(
        self,
        *,
        url: str,
        title_text: str,
        selector_texts: dict[str, list[str]],
        click_updates: dict[tuple[str, int], dict[str, Any]] | None = None,
        element_attributes: dict[tuple[str, int], dict[str, str]] | None = None,
        evaluate_links: list[str] | None = None,
    ) -> None:
        self.url = url
        self._title = title_text
        self.selector_texts = selector_texts
        self.click_updates = click_updates or {}
        self.element_attributes = element_attributes or {}
        self.last_filled: str | None = None
        self.last_pressed: str | None = None
        self._evaluate_links = evaluate_links  # extract_ax_links()용 고정 반환값
        self._evaluate_dropdown: list[str] = []  # extract_dropdown_options()용

    async def evaluate(self, _js: str, _arg: str | None = None) -> Any:
        """evaluate() stub: extract_ax_links/extract_dropdown_options가 사용하는 JS 평가를 시뮬레이션한다."""
        if _arg and "dropdown" in _arg:
            return self._evaluate_dropdown or []
        if self._evaluate_links is not None:
            return self._evaluate_links
        return []

    async def title(self) -> str:
        return self._title

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def get_by_role(self, role: str, *, name: str = "") -> "FakeLocator":
        """get_by_role() stub: role=link/button + name으로 FakeLocator를 반환한다."""
        selector = role  # FakeLocator는 selector_texts의 키로 role을 사용
        return FakeRoleLocator(self, role, name)

    async def goto(self, url: str) -> None:
        self.url = url

    async def wait_for_timeout(self, ms: int) -> None:
        pass

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
    inputs: list[str] | None = None,
) -> FakePage:
    """기본값을 채운 FakePage를 생성한다.

    inputs: placeholder 텍스트 목록. input[type='text'] selector에 매핑된다.
    """
    input_labels = inputs or []
    # input 개수만큼 selector_texts에 빈 문자열 엔트리 생성 (count용)
    input_selector = "input[type='text']"
    element_attrs = {
        (input_selector, i): {"placeholder": label}
        for i, label in enumerate(input_labels)
    }
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
            input_selector: [""] * len(input_labels),
        },
        element_attributes=element_attrs,
    )
