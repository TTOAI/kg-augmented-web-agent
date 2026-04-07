from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

logger = logging.getLogger("webarena_verified")

from .browser import execute_plan, observe_page, try_click_target, try_fill_target, try_search
from .enums import ApprovalEventStatus, RecoveryResult, StepRecordStatus, TaskRunStatus, ValidationResult
from .llm import LLMClient, build_action_request, build_plan, build_system_prompt, parse_llm_action
from .recovery import execute_recovery
from .store import ExecutionStore
from .types import ApprovalEvent, BrowserSession, ExecutionOutcome, FailurePattern, PageObservation, PriorBundle, StepRecord, ValidatorRule
from .validator import validate

_FAILURE_ACTION_TO_STATUS: dict[str, str] = {
    "not_found": "NOT_FOUND_ERROR",
    "permission_denied": "PERMISSION_DENIED_ERROR",
    "action_not_allowed": "ACTION_NOT_ALLOWED_ERROR",
    "data_validation_error": "DATA_VALIDATION_ERROR",
    "unknown_error": "UNKNOWN_ERROR",
}

_TASK_TO_RUN_STATUS: dict[str, TaskRunStatus] = {
    "SUCCESS": TaskRunStatus.VALIDATED,
    "ACTION_NOT_ALLOWED_ERROR": TaskRunStatus.HANDOFF,
    "PERMISSION_DENIED_ERROR": TaskRunStatus.HANDOFF,
    "NOT_FOUND_ERROR": TaskRunStatus.FAILED,
    "DATA_VALIDATION_ERROR": TaskRunStatus.FAILED,
    "UNKNOWN_ERROR": TaskRunStatus.FAILED,
}


# ---------------------------------------------------------------------------
# Path executors (public API)
# ---------------------------------------------------------------------------

async def execute_fast_path(
    *,
    task_run_id: str,
    validator_rules: list[ValidatorRule],
    failure_patterns: list[FailurePattern],
    execution_store: ExecutionStore,
    browser_session: BrowserSession | None = None,
    task: str = "",
    llm: LLMClient | None = None,
    prior_bundle: PriorBundle | None = None,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """fast path 실행."""
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id, step_type="fast_path",
            browser_session=browser_session, execution_store=execution_store,
            task=task, llm=llm, prior_bundle=prior_bundle,
        )

    step = _make_step(task_run_id, "fast_path")
    result = validate(validator_rules)
    validator_used = True
    recovery_used = False

    if result == ValidationResult.PASS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.SUCCEEDED, "validator pass"))
        return TaskRunStatus.VALIDATED, validator_used, recovery_used, None

    recovery_result = await execute_recovery(
        task_run_id=task_run_id, failure_patterns=failure_patterns, execution_store=execution_store,
    )
    recovery_used = True

    if recovery_result != RecoveryResult.SUCCESS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.FAILED, "recovery 실패"))
        return TaskRunStatus.HANDOFF, validator_used, recovery_used, None

    revalidation_result = validate(validator_rules)
    if revalidation_result == ValidationResult.PASS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.SUCCEEDED, "재검증 pass"))
        return TaskRunStatus.VALIDATED, validator_used, recovery_used, None

    execution_store.save_step_record(_finish_step(step, StepRecordStatus.FAILED, "재검증 실패 → handoff"))
    return TaskRunStatus.HANDOFF, validator_used, recovery_used, None


async def execute_partial_prior(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
    browser_session: BrowserSession | None = None,
    task: str = "",
    llm: LLMClient | None = None,
    prior_bundle: PriorBundle | None = None,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """partial prior path 실행."""
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id, step_type="partial_prior",
            browser_session=browser_session, execution_store=execution_store,
            task=task, llm=llm, prior_bundle=prior_bundle,
        )

    step = _make_step(task_run_id, "partial_prior")
    execution_store.save_step_record(_finish_step(step, StepRecordStatus.FAILED, "prior 불충분으로 실행 실패"))
    return TaskRunStatus.FAILED, False, False, None


async def execute_fallback(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
    browser_session: BrowserSession | None = None,
    task: str = "",
    llm: LLMClient | None = None,
    prior_bundle: PriorBundle | None = None,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """fallback path 실행."""
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id, step_type="fallback",
            browser_session=browser_session, execution_store=execution_store,
            task=task, llm=llm, prior_bundle=prior_bundle,
        )

    step = _make_step(task_run_id, "fallback")
    execution_store.save_step_record(_finish_step(step, StepRecordStatus.SKIPPED, "site 미온보딩으로 handoff"))
    return TaskRunStatus.HANDOFF, False, False, None


async def execute_approval_first(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """approval-first path stub 실행."""
    event = ApprovalEvent(
        approval_event_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        action_key="policy_required_action",
        approval_status=ApprovalEventStatus.REQUESTED,
        reason="policy rule이 사전 승인을 요구합니다",
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )
    execution_store.save_approval_event(event)
    return TaskRunStatus.APPROVAL_WAIT, False, False, None


# ---------------------------------------------------------------------------
# Browser execution
# ---------------------------------------------------------------------------

async def _run_with_browser(
    *,
    task_run_id: str,
    step_type: str,
    browser_session: BrowserSession,
    execution_store: ExecutionStore,
    task: str = "",
    llm: LLMClient | None = None,
    prior_bundle: PriorBundle | None = None,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome]:
    """브라우저를 실행하고 ExecutionOutcome을 TaskRunStatus로 매핑한다."""
    primary_page = browser_session.pages[0]
    observation = await observe_page(primary_page)

    if browser_session.plan.action == "unsupported":
        outcome = ExecutionOutcome(
            task_type=browser_session.plan.task_type,
            status="UNKNOWN_ERROR",
            error_details="Unsupported intent",
        )
    elif llm is not None:
        outcome = await _execute_with_llm(
            task=task or browser_session.plan.target_phrase or "complete the task",
            task_type=browser_session.plan.task_type,
            page=primary_page, observation=observation,
            llm=llm, prior_bundle=prior_bundle,
        )
    else:
        outcome = await execute_plan(
            plan=browser_session.plan, sites=browser_session.sites,
            start_urls=browser_session.start_urls,
            page=primary_page, observation=observation,
        )

    task_status = _TASK_TO_RUN_STATUS.get(outcome.status, TaskRunStatus.FAILED)
    step_status = StepRecordStatus.SUCCEEDED if task_status == TaskRunStatus.VALIDATED else StepRecordStatus.FAILED
    step = _make_step(task_run_id, step_type)
    execution_store.save_step_record(_finish_step(step, step_status, outcome.status))
    return task_status, False, False, outcome


# ---------------------------------------------------------------------------
# LLM execution loop
# ---------------------------------------------------------------------------

async def _execute_with_llm(
    *,
    task: str,
    task_type: str,
    page: Any,
    observation: PageObservation,
    llm: LLMClient,
    prior_bundle: PriorBundle | None,
    max_steps: int = 15,
) -> ExecutionOutcome:
    """LLM 기반 액션 루프. 대화 히스토리를 누적하며 태스크를 완수한다."""
    system = build_system_prompt(prior_bundle)
    current_obs = observation
    messages: list[dict[str, str]] = []
    last_action_result = ""

    sub_goals = build_plan(task=task, observation=current_obs, llm=llm)
    current_goal_index = 0
    logger.info("[LLM] task=%r  task_type=%s", task, task_type)
    logger.info("[LLM] plan=%s", sub_goals)

    for step in range(max_steps):
        _log_step_observation(step, current_obs, sub_goals, current_goal_index)

        user_msg = build_action_request(
            task=task, observation=current_obs, last_action_result=last_action_result,
            sub_goals=sub_goals, current_goal_index=current_goal_index,
        )
        messages.append({"role": "user", "content": user_msg})
        last_action_result = ""

        action, messages = _get_llm_action(llm, system, messages)
        action_type = action.get("action", "not_found")
        goal_complete_requested = bool(action.get("goal_complete"))
        logger.info("[LLM] step=%d  action=%s  reasoning=%r", step + 1, action_type, action.get("reasoning", "")[:200])

        # --- Terminal actions ---
        if action_type == "done":
            result = await _handle_done(
                sub_goals=sub_goals,
                current_goal_index=current_goal_index, task_type=task_type,
            )
            if result is not None:
                return result
            # done rejected → advance goal or continue
            current_goal_index += 1
            last_action_result = (
                f"Sub-goal completed. Now working on: {sub_goals[current_goal_index]}"
                if current_goal_index < len(sub_goals)
                else "Task not yet complete. Continue working."
            )
            current_obs = await observe_page(page)
            continue

        if action_type == "extract":
            return _handle_extract(action, task_type)

        if action_type in _FAILURE_ACTION_TO_STATUS:
            return _handle_failure(action, action_type, task_type)

        # --- Browser actions ---
        prev_state = _capture_page_state(current_obs)
        action_result = await _execute_browser_action(
            action_type=action_type, action=action, page=page,
            current_obs=current_obs,
        )

        if action_result.should_continue:
            current_obs = action_result.observation or current_obs
            last_action_result = action_result.feedback
            logger.info("[LLM] step=%d  result=%s", step + 1, last_action_result)
            continue

        current_obs = await observe_page(page)
        last_action_result = _summarize_action_result(
            action_type, action, action_result.succeeded, current_obs, prev_state,
        )
        logger.info("[LLM] step=%d  result=%s", step + 1, last_action_result)

        if goal_complete_requested and action_result.succeeded and current_goal_index < len(sub_goals):
            logger.info("[LLM] step=%d  goal %d complete: %r", step + 1, current_goal_index + 1, sub_goals[current_goal_index])
            current_goal_index += 1

    return ExecutionOutcome(
        task_type=task_type, status="NOT_FOUND_ERROR",
        error_details=f"Task not completed after {max_steps} attempts",
    )


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

class _ActionResult:
    """Browser 액션 실행 결과."""
    __slots__ = ("succeeded", "should_continue", "feedback", "observation")

    def __init__(
        self,
        succeeded: bool = False,
        should_continue: bool = False,
        feedback: str = "",
        observation: PageObservation | None = None,
    ):
        self.succeeded = succeeded
        self.should_continue = should_continue
        self.feedback = feedback
        self.observation = observation


async def _handle_done(
    *,
    sub_goals: list[str],
    current_goal_index: int,
    task_type: str,
) -> ExecutionOutcome | None:
    """done 처리. SUCCESS를 반환하거나, 아직 미완이면 None을 반환한다."""
    if current_goal_index < len(sub_goals) - 1:
        logger.info("[LLM] done ignored — advancing to goal %d/%d: %r",
                     current_goal_index + 2, len(sub_goals), sub_goals[current_goal_index + 1])
        return None

    logger.info("[LLM] done → SUCCESS (all goals complete)")
    return ExecutionOutcome(task_type=task_type, status="SUCCESS")


def _handle_extract(action: dict[str, Any], task_type: str) -> ExecutionOutcome:
    """extract 처리."""
    value = action.get("value", "")
    label = action.get("label", "")
    if value:
        retrieved = [v.strip() for v in value.split(",") if v.strip()] if "," in value else [value]
        logger.info("[LLM] extract → SUCCESS  label=%r value=%r", label, value[:100])
        return ExecutionOutcome(task_type=task_type, status="SUCCESS", retrieved_data=retrieved)
    logger.info("[LLM] extract → NOT_FOUND_ERROR (missing value)")
    return ExecutionOutcome(task_type=task_type, status="NOT_FOUND_ERROR", error_details="LLM extract action missing value")


def _handle_failure(action: dict[str, Any], action_type: str, task_type: str) -> ExecutionOutcome:
    """failure action 처리."""
    status = _FAILURE_ACTION_TO_STATUS[action_type]
    logger.info("[LLM] %s → %s", action_type, status)
    return ExecutionOutcome(
        task_type=task_type, status=status,
        error_details=action.get("reasoning", f"LLM returned {action_type}"),
    )


async def _execute_browser_action(
    *,
    action_type: str,
    action: dict[str, Any],
    page: Any,
    current_obs: PageObservation,
) -> _ActionResult:
    """click/fill/goto/search 액션 실행. _ActionResult를 반환한다."""
    if action_type == "click":
        return await _execute_click(action, page, current_obs)
    if action_type == "fill":
        return await _execute_fill(action, page)
    if action_type == "goto":
        return await _execute_goto(action, page)
    if action_type == "search":
        return await _execute_search(action, page)
    return _ActionResult()


async def _execute_click(action: dict[str, Any], page: Any, obs: PageObservation) -> _ActionResult:
    """click 액션: 관측 링크 → get_by_role → try_click_target 순으로 시도."""
    target = action.get("target", "")
    url_hint = action.get("url", "")
    logger.info("[LLM] click  target=%r  url_hint=%r", target, url_hint)
    if not target:
        return _ActionResult()

    # 1. 관측 links에서 매칭
    target_lower = target.lower()
    matching_links = [l for l in obs.links if target_lower in l.split(" → ")[0].lower()]

    if len(matching_links) > 1 and not url_hint:
        return _ActionResult(
            should_continue=True,
            feedback=(
                f"Multiple links match '{target}': {matching_links}. "
                "Set 'url' to the pathname of the intended target and retry click."
            ),
        )

    if matching_links:
        click_href = None
        if url_hint:
            click_href = next((l.split(" → ")[1] for l in matching_links if " → " in l and url_hint in l), None)
        elif len(matching_links) == 1 and " → " in matching_links[0]:
            click_href = matching_links[0].split(" → ")[1]
        if click_href:
            try:
                loc = page.locator(f"a[href='{click_href}']:visible")
                if await loc.count() > 0:
                    await loc.first.click()
                    logger.info("[LLM] click via observation link: %r", click_href)
                    return _ActionResult(succeeded=True)
            except Exception as exc:
                logger.debug("observation link click failed: %s", exc)

    # 2. get_by_role fallback
    for role in ("link", "button", "textbox", "option", "menuitem", "tab"):
        try:
            locator = page.get_by_role(role, name=target)
            count = await locator.count()
            if count < 1:
                continue
            if url_hint and count > 1:
                for i in range(count):
                    href = await locator.nth(i).get_attribute("href") or ""
                    if url_hint in href:
                        await locator.nth(i).click()
                        return _ActionResult(succeeded=True)
            await locator.first.click()
            return _ActionResult(succeeded=True)
        except Exception as exc:
            logger.debug("get_by_role(%s) failed: %s", role, exc)

    # 3. try_click_target fallback
    if await try_click_target(page, [target]):
        return _ActionResult(succeeded=True)

    return _ActionResult(succeeded=False)


async def _execute_fill(action: dict[str, Any], page: Any) -> _ActionResult:
    """fill 액션: 입력 필드를 찾아 값을 채운다."""
    target = action.get("target", "")
    value = action.get("value", "")
    submit = bool(action.get("submit", False))
    logger.info("[LLM] fill  target=%r  value=%r  submit=%s", target, value, submit)

    succeeded = False
    if target and value:
        succeeded = await try_fill_target(page, target, value, submit=submit)
    return _ActionResult(succeeded=succeeded)


async def _execute_goto(action: dict[str, Any], page: Any) -> _ActionResult:
    """goto 액션."""
    url = action.get("url", "")
    logger.info("[LLM] goto  url=%r", url)
    if url:
        try:
            await page.goto(url)
            return _ActionResult(succeeded=True)
        except Exception:
            pass
    return _ActionResult(succeeded=False)


async def _execute_search(action: dict[str, Any], page: Any) -> _ActionResult:
    """search 액션."""
    query = action.get("target", "")
    logger.info("[LLM] search  query=%r", query)
    if query:
        succeeded = await try_search(page, query)
        return _ActionResult(succeeded=succeeded)
    return _ActionResult(succeeded=False)


# ---------------------------------------------------------------------------
# Result summarization
# ---------------------------------------------------------------------------

class _PageState:
    """관측 상태 스냅샷 (변경 감지용)."""
    __slots__ = ("url", "links", "buttons", "dropdown")

    def __init__(self, obs: PageObservation):
        self.url = obs.url
        self.links = set(obs.links)
        self.buttons = set(obs.buttons)
        self.dropdown = set(obs.dropdown_options)


def _capture_page_state(obs: PageObservation) -> _PageState:
    return _PageState(obs)


def _summarize_action_result(
    action_type: str,
    action: dict[str, Any],
    succeeded: bool,
    current_obs: PageObservation,
    prev: _PageState,
) -> str:
    """액션 실행 결과를 LLM 피드백 문자열로 요약한다."""
    if action_type == "click":
        target = action.get("target", "")
        if not succeeded:
            extras = []
            extra_links = current_obs.links[20:40]
            extra_buttons = current_obs.buttons[10:20]
            if extra_links:
                extras.append(f"More links: {extra_links}")
            if extra_buttons:
                extras.append(f"More buttons: {extra_buttons}")
            extra_msg = " " + " ".join(extras) if extras else ""
            return f"click '{target}': element not found.{extra_msg}"
        if current_obs.url != prev.url:
            return f"click '{target}': navigated to {current_obs.url}"
        if set(current_obs.links) != prev.links or set(current_obs.buttons) != prev.buttons or set(current_obs.dropdown_options) != prev.dropdown:
            return f"click '{target}': page content changed"
        return f"click '{target}': no visible change"

    if action_type == "fill":
        target = action.get("target", "")
        if not succeeded:
            return f"fill '{target}': field not found"
        if current_obs.url != prev.url:
            return f"fill '{target}': navigated to {current_obs.url}"
        return f"fill '{target}': submitted"

    if action_type == "goto":
        url = action.get("url", "")
        if not succeeded:
            return f"goto '{url}': navigation failed"
        return f"goto: navigated to {current_obs.url}"

    if action_type == "search":
        query = action.get("target", "")
        if not succeeded:
            return f"search '{query}': search field not found"
        if current_obs.url != prev.url:
            return f"search '{query}': navigated to {current_obs.url}"
        return f"search '{query}': URL unchanged"

    return ""


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _get_llm_action(
    llm: LLMClient, system: str, messages: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """LLM 호출 + 파싱. 실패 시 1회 재시도."""
    response = llm.complete(system=system, messages=messages)
    messages.append({"role": "assistant", "content": response})

    action = parse_llm_action(response)
    reasoning = action.get("reasoning", "")

    if "파싱 실패" in reasoning:
        logger.info("[LLM] parse failed, retrying")
        messages.append({"role": "user", "content": "Your response was truncated or malformed. Reply with valid JSON only."})
        response = llm.complete(system=system, messages=messages)
        messages.append({"role": "assistant", "content": response})
        action = parse_llm_action(response)

    return action, messages


def _log_step_observation(
    step: int, obs: PageObservation, sub_goals: list[str], goal_index: int,
) -> None:
    """스텝별 관측 로깅."""
    logger.info("[LLM] step=%d  url=%s", step + 1, obs.url)
    logger.info("[LLM] step=%d  links=%s", step + 1, obs.links[:20])
    logger.info("[LLM] step=%d  buttons=%s", step + 1, obs.buttons[:10])
    if obs.dropdown_options:
        logger.info("[LLM] step=%d  dropdown=%s", step + 1, obs.dropdown_options[:15])
    goal_desc = sub_goals[goal_index] if goal_index < len(sub_goals) else "ALL DONE"
    logger.info("[LLM] step=%d  goal=%d/%d %r", step + 1, goal_index + 1, len(sub_goals), goal_desc)


# ---------------------------------------------------------------------------
# Step record helpers
# ---------------------------------------------------------------------------

def _make_step(task_run_id: str, step_type: str) -> StepRecord:
    return StepRecord(
        step_record_id=str(uuid.uuid4()),
        task_run_id=task_run_id,
        step_index=0,
        step_type=step_type,
        status=StepRecordStatus.RUNNING,
        pre_state_summary=f"{step_type} 시작",
        post_state_summary="",
    )


def _finish_step(step: StepRecord, status: StepRecordStatus, summary: str) -> StepRecord:
    return StepRecord(
        step_record_id=step.step_record_id,
        task_run_id=step.task_run_id,
        step_index=step.step_index,
        step_type=step.step_type,
        status=status,
        pre_state_summary=step.pre_state_summary,
        post_state_summary=summary,
    )
