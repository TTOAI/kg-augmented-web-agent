from __future__ import annotations

import logging
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
    """fast path 실행.

    browser_session이 있으면 실제 브라우저 실행 결과를 TaskRunStatus로 매핑한다.
    없으면 결정론적 stub(validator → recovery → 재검증)을 실행한다.
    llm이 있으면 LLM 기반 액션 루프를 사용한다.

    Returns: (final_status, validator_used, recovery_used, execution_outcome)
    """
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="fast_path",
            browser_session=browser_session,
            execution_store=execution_store,
            task=task,
            llm=llm,
            prior_bundle=prior_bundle,
        )

    # --- stub 동작 ---
    step = _make_step(task_run_id, "fast_path")

    result = validate(validator_rules)
    validator_used = True
    recovery_used = False

    if result == ValidationResult.PASS:
        execution_store.save_step_record(_finish_step(step, StepRecordStatus.SUCCEEDED, "validator pass"))
        return TaskRunStatus.VALIDATED, validator_used, recovery_used, None

    recovery_result = await execute_recovery(
        task_run_id=task_run_id,
        failure_patterns=failure_patterns,
        execution_store=execution_store,
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
    """partial prior path 실행.

    browser_session이 있으면 실제 브라우저 실행을 수행한다. (prior 안내 없는 best-effort)
    없으면 FAILED stub을 반환한다.
    """
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="partial_prior",
            browser_session=browser_session,
            execution_store=execution_store,
            task=task,
            llm=llm,
            prior_bundle=prior_bundle,
        )

    step = _make_step(task_run_id, "partial_prior")
    execution_store.save_step_record(
        _finish_step(step, StepRecordStatus.FAILED, "prior 불충분으로 실행 실패")
    )
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
    """fallback path 실행.

    browser_session이 있으면 prior 없이 범용 브라우저 실행을 수행한다.
    없으면 HANDOFF stub을 반환한다.
    """
    if browser_session is not None:
        return await _run_with_browser(
            task_run_id=task_run_id,
            step_type="fallback",
            browser_session=browser_session,
            execution_store=execution_store,
            task=task,
            llm=llm,
            prior_bundle=prior_bundle,
        )

    step = _make_step(task_run_id, "fallback")
    execution_store.save_step_record(
        _finish_step(step, StepRecordStatus.SKIPPED, "site 미온보딩으로 handoff")
    )
    return TaskRunStatus.HANDOFF, False, False, None


async def execute_approval_first(
    *,
    task_run_id: str,
    execution_store: ExecutionStore,
) -> tuple[TaskRunStatus, bool, bool, ExecutionOutcome | None]:
    """approval-first path stub 실행. ApprovalEvent(REQUESTED)를 기록하고 APPROVAL_WAIT 반환."""
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


# --- 내부 헬퍼 ---

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
    """브라우저를 실행하고 ExecutionOutcome을 TaskRunStatus로 매핑한다.

    llm이 있으면 LLM 기반 액션 루프를 사용하고, 없으면 규칙 기반 execute_plan을 사용한다.
    """
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
            page=primary_page,
            observation=observation,
            llm=llm,
            prior_bundle=prior_bundle,
        )
    else:
        outcome = await execute_plan(
            plan=browser_session.plan,
            sites=browser_session.sites,
            start_urls=browser_session.start_urls,
            page=primary_page,
            observation=observation,
        )

    task_status = _TASK_TO_RUN_STATUS.get(outcome.status, TaskRunStatus.FAILED)
    step_status = StepRecordStatus.SUCCEEDED if task_status == TaskRunStatus.VALIDATED else StepRecordStatus.FAILED

    step = _make_step(task_run_id, step_type)
    execution_store.save_step_record(_finish_step(step, step_status, outcome.status))
    return task_status, False, False, outcome


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
    """LLM 기반 액션 루프. 최대 max_steps번 LLM에 물어보며 태스크를 완수한다.

    대화 히스토리를 누적해 LLM이 이전 스텝 맥락을 활용할 수 있게 한다.
    """
    system = build_system_prompt(prior_bundle)
    current_obs = observation
    messages: list[dict[str, str]] = []
    last_action_result = ""

    # --- Planning ---
    sub_goals = build_plan(task=task, observation=current_obs, llm=llm)
    current_goal_index = 0
    logger.info("[LLM] task=%r  task_type=%s", task, task_type)
    logger.info("[LLM] plan=%s", sub_goals)

    for step in range(max_steps):
        logger.info("[LLM] step=%d  url=%s", step + 1, current_obs.url)
        logger.info("[LLM] step=%d  links=%s", step + 1, current_obs.links[:20])
        logger.info("[LLM] step=%d  buttons=%s", step + 1, current_obs.buttons[:10])
        logger.info("[LLM] step=%d  goal=%d/%d %r", step + 1, current_goal_index + 1, len(sub_goals), sub_goals[current_goal_index] if current_goal_index < len(sub_goals) else "ALL DONE")

        user_msg = build_action_request(
            task=task,
            observation=current_obs,
            last_action_result=last_action_result,
            sub_goals=sub_goals,
            current_goal_index=current_goal_index,
        )
        messages.append({"role": "user", "content": user_msg})
        last_action_result = ""

        response = llm.complete(system=system, messages=messages)
        messages.append({"role": "assistant", "content": response})

        action = parse_llm_action(response)
        action_type = action.get("action", "not_found")
        reasoning = action.get("reasoning", "")

        # 파싱 실패 시 1회 재시도
        if "파싱 실패" in reasoning:
            logger.info("[LLM] step=%d  parse failed, retrying", step + 1)
            messages.append({"role": "user", "content": "Your response was truncated or malformed. Reply with valid JSON only."})
            response = llm.complete(system=system, messages=messages)
            messages.append({"role": "assistant", "content": response})
            action = parse_llm_action(response)
            action_type = action.get("action", "not_found")
            reasoning = action.get("reasoning", "")
        goal_complete_requested = bool(action.get("goal_complete"))
        logger.info("[LLM] step=%d  action=%s  reasoning=%r", step + 1, action_type, reasoning[:200])

        if action_type == "done":
            if current_goal_index < len(sub_goals) - 1:
                # 아직 남은 sub-goal이 있으면 done을 무시하고 다음 goal로 전환
                current_goal_index += 1
                logger.info("[LLM] done ignored — advancing to goal %d/%d: %r", current_goal_index + 1, len(sub_goals), sub_goals[current_goal_index])
                last_action_result = f"Sub-goal completed. Now working on: {sub_goals[current_goal_index]}"
                current_obs = await observe_page(page)
                continue
            logger.info("[LLM] done → SUCCESS (all goals complete)")
            return ExecutionOutcome(task_type=task_type, status="SUCCESS")

        if action_type == "extract":
            value = action.get("value", "")
            label = action.get("label", "")
            if value:
                display = f"{label}: {value}" if label else value
                logger.info("[LLM] extract → SUCCESS  value=%r", display[:100])
                return ExecutionOutcome(task_type=task_type, status="SUCCESS", retrieved_data=[display])
            logger.info("[LLM] extract → NOT_FOUND_ERROR (missing value)")
            return ExecutionOutcome(
                task_type=task_type,
                status="NOT_FOUND_ERROR",
                error_details="LLM extract action missing value",
            )

        if action_type in _FAILURE_ACTION_TO_STATUS:
            status = _FAILURE_ACTION_TO_STATUS[action_type]
            logger.info("[LLM] %s → %s", action_type, status)
            return ExecutionOutcome(
                task_type=task_type,
                status=status,
                error_details=action.get("reasoning", f"LLM returned {action_type}"),
            )

        # 중간 탐색/입력 액션 실행 — 결과를 다음 스텝에 피드백
        prev_url = current_obs.url
        prev_links = set(current_obs.links)
        prev_buttons = set(current_obs.buttons)
        action_succeeded = False

        if action_type == "click":
            target = action.get("target", "")
            url_hint = action.get("url", "")
            logger.info("[LLM] click  target=%r  url_hint=%r", target, url_hint)
            if target:
                for role in ("link", "button"):
                    try:
                        locator = page.get_by_role(role, name=target)
                        count = await locator.count()
                        if count < 1:
                            continue
                        clicked = False
                        if url_hint and count > 1:
                            for i in range(count):
                                href = await locator.nth(i).get_attribute("href") or ""
                                if url_hint in href:
                                    await locator.nth(i).click()
                                    clicked = True
                                    break
                        if not clicked:
                            await locator.first.click()
                        action_succeeded = True
                        break
                    except Exception:
                        continue
        elif action_type == "fill":
            target = action.get("target", "")
            value = action.get("value", "")
            submit = bool(action.get("submit", False))
            logger.info("[LLM] fill  target=%r  value=%r  submit=%s", target, value, submit)
            if target and value:
                action_succeeded = await try_fill_target(page, target, value, submit=submit)
        elif action_type == "goto":
            url = action.get("url", "")
            logger.info("[LLM] goto  url=%r", url)
            if url:
                try:
                    await page.goto(url)
                    action_succeeded = True
                except Exception:
                    pass
        elif action_type == "search":
            query = action.get("target", "")
            logger.info("[LLM] search  query=%r", query)
            if query:
                action_succeeded = await try_search(page, query)

        current_obs = await observe_page(page)

        # 액션 결과 요약 — 다음 스텝 LLM 메시지에 포함
        if action_type == "click":
            target = action.get("target", "")
            if not action_succeeded:
                last_action_result = f"click '{target}': element not found"
            elif current_obs.url != prev_url:
                last_action_result = f"click '{target}': navigated to {current_obs.url}"
            elif set(current_obs.links) != prev_links or set(current_obs.buttons) != prev_buttons:
                last_action_result = f"click '{target}': page content changed"
            else:
                last_action_result = f"click '{target}': no visible change"
        elif action_type == "fill":
            target = action.get("target", "")
            if not action_succeeded:
                last_action_result = f"fill '{target}': field not found"
            elif current_obs.url != prev_url:
                last_action_result = f"fill '{target}': navigated to {current_obs.url}"
            else:
                last_action_result = f"fill '{target}': submitted"
        elif action_type == "goto":
            url = action.get("url", "")
            if not action_succeeded:
                last_action_result = f"goto '{url}': navigation failed"
            else:
                last_action_result = f"goto: navigated to {current_obs.url}"
        elif action_type == "search":
            query = action.get("target", "")
            if not action_succeeded:
                last_action_result = f"search '{query}': search field not found"
            elif current_obs.url != prev_url:
                last_action_result = f"search '{query}': navigated to {current_obs.url}"
            else:
                last_action_result = f"search '{query}': URL unchanged"

        logger.info("[LLM] step=%d  result=%s", step + 1, last_action_result)

        # goal_complete: 액션이 성공했을 때만 sub-goal 전환
        if goal_complete_requested and action_succeeded and current_goal_index < len(sub_goals):
            logger.info("[LLM] step=%d  goal %d complete: %r", step + 1, current_goal_index + 1, sub_goals[current_goal_index])
            current_goal_index += 1

    return ExecutionOutcome(
        task_type=task_type,
        status="NOT_FOUND_ERROR",
        error_details=f"Task not completed after {max_steps} attempts",
    )


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
