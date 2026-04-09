from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("webarena_verified")

from .browser import execute_plan, observe_page, try_click_target, try_fill_target, try_search
from .enums import ApprovalEventStatus, RecoveryResult, StepRecordStatus, TaskRunStatus, ValidationResult
from .llm import LLMClient, SubGoal, build_observation_message, build_plan, build_tool_use_system_prompt
from .tools import format_assistant_tool_use, format_tool_result, replan_tool, tools_for_goal
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

_MAX_RETRIES_PER_GOAL = 5


async def _execute_with_llm(
    *,
    task: str,
    task_type: str,
    page: Any,
    observation: PageObservation,
    llm: LLMClient,
    prior_bundle: PriorBundle | None,
    max_steps: int = 50,
) -> ExecutionOutcome:
    """Sub-goal별 실행 루프. checkpoint + graduated retry로 태스크를 완수한다."""
    t_start = time.time()
    system = build_tool_use_system_prompt(prior_bundle)

    sub_goals = build_plan(task=task, task_type=task_type, observation=observation, llm=llm)
    logger.info("[LLM] task=%r  task_type=%s", task, task_type)
    logger.info("[LLM] plan=%s", sub_goals)

    checkpoint_stack = [page.url]  # goal별 checkpoint 스택 (index 0 = task 시작 URL)
    task_notes: list[str] = []  # LLM이 수집한 정보 (전체 태스크 동안 유지)
    steps_used = 0
    replans_remaining = 3
    max_replans = replans_remaining

    goal_idx = 0
    while goal_idx < len(sub_goals):
        sub_goal = sub_goals[goal_idx]
        remaining_goals = len(sub_goals) - goal_idx
        step_budget = max(10, (max_steps - steps_used) // remaining_goals)
        failures: list[str] = []
        goal_succeeded = False

        for attempt in range(_MAX_RETRIES_PER_GOAL):
            logger.info("[LLM] goal=%d/%d %r  attempt=%d  budget=%d",
                        goal_idx + 1, len(sub_goals), sub_goal, attempt + 1, step_budget)

            result, used = await _try_sub_goal(
                task=task, task_type=task_type, sub_goal=sub_goal,
                sub_goals=sub_goals, goal_index=goal_idx,
                page=page, llm=llm, system=system,
                step_budget=step_budget, previous_failures=failures,
                is_last_goal=(goal_idx == len(sub_goals) - 1),
                task_notes=task_notes,
            )
            steps_used += used

            # extract/failure → 즉시 반환
            if result is not None and result.status != "SUB_GOAL_FAILED":
                elapsed = time.time() - t_start
                logger.info("[LLM] task completed in %.1fs (%d steps)", elapsed, steps_used)
                return result

            # sub-goal 성공 (done)
            if result is None:
                checkpoint_stack.append(page.url)
                logger.info("[LLM] goal %d/%d complete — checkpoint: %s",
                            goal_idx + 1, len(sub_goals), checkpoint_stack[-1])
                goal_succeeded = True
                break

            # sub-goal 실패 → checkpoint 복원 + retry
            failure_desc = result.error_details or f"attempt {attempt + 1} failed"
            failures.append(failure_desc)
            logger.info("[LLM] goal %d/%d failed (attempt %d): %s — restoring checkpoint",
                        goal_idx + 1, len(sub_goals), attempt + 1, failure_desc)
            try:
                await page.goto(checkpoint_stack[-1])
            except Exception:
                pass

        if not goal_succeeded and replans_remaining > 0:
            replans_remaining -= 1
            replan_count = max_replans - replans_remaining  # 1차, 2차, 3차

            # 2차 이상 replan: 이전 checkpoint로 점진적 롤백 (현재 checkpoint 오염 가능성)
            if replan_count >= 2 and len(checkpoint_stack) > 1:
                checkpoint_stack.pop()
                goal_idx = max(0, len(checkpoint_stack) - 1)
                logger.info("[LLM] deep rollback to checkpoint %d: %s",
                            goal_idx, checkpoint_stack[-1])

            try:
                await page.goto(checkpoint_stack[-1])
            except Exception:
                pass

            current_obs = await observe_page(page)
            logger.info("[LLM] replanning (remaining=%d, depth=%d) after goal %d/%d failed",
                        replans_remaining, replan_count, goal_idx + 1, len(sub_goals))
            new_goals = _replan(
                task=task, task_type=task_type, observation=current_obs, llm=llm,
                completed_goals=sub_goals[:goal_idx],
                failed_goal=sub_goal, failure_history=failures,
            )
            if new_goals:
                logger.info("[LLM] new plan: %s", new_goals)
                sub_goals = sub_goals[:goal_idx] + new_goals
                continue
            else:
                logger.info("[LLM] replan returned empty — failing task")

        if not goal_succeeded:
            # 모든 retry + replan 소진 → 태스크 실패
            elapsed = time.time() - t_start
            logger.info("[LLM] goal %d/%d failed after all retries and replans in %.1fs",
                        goal_idx + 1, len(sub_goals), elapsed)
            return ExecutionOutcome(
                task_type=task_type,
                status="NOT_FOUND_ERROR",
                error_details=f"Sub-goal '{sub_goal.goal}' failed after all retries and replans",
            )

        goal_idx += 1

    # 모든 goal 완료 (또는 소진)
    # RETRIEVE task이면 최종 답 추출
    if task_type == "RETRIEVE":
        obs = await observe_page(page)
        try:
            from .skills import verified_extract as _ve
            skill_result = _ve(
                task=task, task_type=task_type, preliminary_answer="",
                current_obs=obs, task_notes=task_notes, llm=llm,
            )
            if skill_result.outcome is not None:
                elapsed = time.time() - t_start
                logger.info("[LLM] final verified_extract in %.1fs (%d steps)", elapsed, steps_used)
                return skill_result.outcome
        except Exception:
            pass
        elapsed = time.time() - t_start
        logger.info("[LLM] RETRIEVE final extract failed in %.1fs (%d steps)", elapsed, steps_used)
        return ExecutionOutcome(task_type=task_type, status="NOT_FOUND_ERROR",
                                error_details="Final extract failed — no data retrieved")

    # NAVIGATE 최종 체크: URL == 시작 URL이면 replan (navigate인데 안 움직임)
    if task_type == "NAVIGATE" and replans_remaining > 0 and page.url == checkpoint_stack[0]:
        logger.info("[LLM] NAVIGATE final check — URL unchanged from start, replanning")
        replans_remaining -= 1
        obs = await observe_page(page)
        new_goals = _replan(
            task=task, task_type=task_type, observation=obs, llm=llm,
            completed_goals=sub_goals,
            failed_goal=SubGoal("URL unchanged from task start"),
            failure_history=["All goals completed but URL is still the starting URL"],
        )
        if new_goals:
            sub_goals = sub_goals + new_goals
            while goal_idx < len(sub_goals):
                sub_goal = sub_goals[goal_idx]
                remaining_goals = len(sub_goals) - goal_idx
                step_budget = max(10, (max_steps - steps_used) // remaining_goals)
                result, used = await _try_sub_goal(
                    task=task, task_type=task_type, sub_goal=sub_goal,
                    sub_goals=sub_goals, goal_index=goal_idx,
                    page=page, llm=llm, system=system,
                    step_budget=step_budget, previous_failures=[],
                    is_last_goal=(goal_idx == len(sub_goals) - 1),
                    task_notes=task_notes,
                )
                steps_used += used
                if result is not None and result.status != "SUB_GOAL_FAILED":
                    elapsed = time.time() - t_start
                    logger.info("[LLM] task completed in %.1fs (%d steps)", elapsed, steps_used)
                    return result
                if result is None:
                    checkpoint_stack.append(page.url)
                    goal_idx += 1
                    continue
                break

    elapsed = time.time() - t_start
    logger.info("[LLM] all goals complete in %.1fs (%d steps)", elapsed, steps_used)
    return ExecutionOutcome(task_type=task_type, status="SUCCESS")


async def _try_sub_goal(
    *,
    task: str,
    task_type: str,
    sub_goal: SubGoal,
    sub_goals: list[SubGoal],
    goal_index: int,
    page: Any,
    llm: LLMClient,
    system: str,
    step_budget: int,
    previous_failures: list[str],
    is_last_goal: bool = False,
    task_notes: list[str] | None = None,
) -> tuple[ExecutionOutcome | None, int]:
    """단일 sub-goal을 step_budget 안에서 시도한다 (Tool Use 기반).

    Returns:
        (None, steps_used) — sub-goal 완료 (done)
        (ExecutionOutcome, steps_used) — extract/failure/timeout 결과
        status="SUB_GOAL_FAILED"이면 retry 가능한 실패
    """
    messages: list[dict] = []
    last_action_feedback = ""
    current_obs = await observe_page(page)
    _action_history: list[str] = []
    _MAX_MESSAGES = 10
    tools = tools_for_goal(is_last_goal=is_last_goal, task_type=task_type)

    # 이전 실패 이력을 피드백으로 주입 (graduated retry)
    if previous_failures:
        retry_count = len(previous_failures)
        all_failures = " | ".join(previous_failures)
        if retry_count <= 3:
            last_action_feedback = (
                f"Attempt {retry_count} failed. Previous attempts: {all_failures}. "
                "Do NOT repeat these actions. Try a different approach."
            )
        else:
            last_action_feedback = (
                f"This goal has failed {retry_count} times. Previous attempts: {all_failures}. "
                "Try a COMPLETELY different method. Do NOT repeat any previous actions."
            )

    for step in range(step_budget):
        _log_step_observation(step, current_obs, sub_goals, goal_index)

        user_msg = build_observation_message(
            task=task, observation=current_obs, last_action_feedback=last_action_feedback,
            sub_goals=sub_goals, current_goal_index=goal_index,
        )
        messages.append({"role": "user", "content": user_msg})
        if len(messages) > _MAX_MESSAGES:
            messages = _trim_messages(messages, _MAX_MESSAGES)
        last_action_feedback = ""

        action_name, args, thought, tool_id, messages = _get_tool_action(
            llm, system, messages, tools,
        )
        _action_history.append(f"{action_name}({args.get('target', args.get('keyword', args.get('fact', '')[:30]))})")
        logger.info("[LLM] step=%d  action=%s  thought=%r",
                    step + 1, action_name, (thought or "")[:200])

        # --- Terminal actions ---
        if action_name == "done":
            logger.info("[LLM] sub-goal done [%s]: %r", sub_goal.goal_type, sub_goal.goal)
            return None, step + 1

        if action_name == "extract":
            return _handle_extract({"value": args.get("value", ""), "label": args.get("label", "")}, task_type), step + 1

        if action_name in _FAILURE_ACTION_TO_STATUS:
            reason = args.get("reason", action_name)
            logger.info("[LLM] %s → sub-goal failed", action_name)
            return ExecutionOutcome(
                task_type=task_type, status="SUB_GOAL_FAILED",
                error_details=f"{action_name}: {reason[:200]}",
            ), step + 1

        # --- Cognition tools ---
        if action_name == "remember":
            fact = args.get("fact", "")
            if fact and task_notes is not None:
                task_notes.append(fact)
            feedback = f"Remembered: {fact}" if fact else "remember requires a 'fact' to save."
            logger.info("[LLM] step=%d  remember=%r", step + 1, fact)
            messages.append(format_tool_result(tool_id, feedback))
            continue

        if action_name == "recall":
            notes_text = "\n".join(f"- {n}" for n in task_notes) if task_notes else "(no notes saved yet)"
            logger.info("[LLM] step=%d  recall=%d notes", step + 1, len(task_notes or []))
            messages.append(format_tool_result(tool_id, f"Saved notes:\n{notes_text}"))
            continue

        if action_name == "observe":
            keyword = (args.get("keyword") or "").lower()
            filtered: list[str] = []
            if keyword:
                for item in current_obs.links:
                    if keyword in item.lower():
                        filtered.append(f"[link] {item}")
                for item in current_obs.buttons:
                    if keyword in item.lower():
                        filtered.append(f"[button] {item}")
                for item in current_obs.text_lines:
                    if keyword in item.lower():
                        filtered.append(f"[text] {item}")
                for item in current_obs.dropdown_options:
                    if keyword in item.lower():
                        filtered.append(f"[dropdown] {item}")
                feedback = f"Filtered observation for '{keyword}': {filtered}" if filtered else f"No matches found for '{keyword}'"
            else:
                feedback = "observe requires a 'keyword' to filter by."
            logger.info("[LLM] step=%d  observe=%r  results=%d", step + 1, keyword, len(filtered))
            messages.append(format_tool_result(tool_id, feedback))
            continue

        # --- Skill tools ---
        if action_name == "scan_and_remember":
            from .skills import scan_and_remember as _scan_skill
            skill_result = _scan_skill(
                task=task, task_hint=args.get("task_hint", ""),
                current_obs=current_obs,
                task_notes=task_notes if task_notes is not None else [],
                llm=llm,
            )
            logger.info("[LLM] step=%d  scan_and_remember  added=%d", step + 1, len(skill_result.notes_added))
            messages.append(format_tool_result(tool_id, skill_result.feedback))
            continue

        if action_name == "verified_extract":
            from .skills import verified_extract as _ve_skill
            skill_result = _ve_skill(
                task=task, task_type=task_type,
                preliminary_answer=args.get("preliminary_answer", ""),
                current_obs=current_obs,
                task_notes=task_notes if task_notes is not None else [],
                llm=llm,
            )
            if skill_result.outcome is not None:
                logger.info("[LLM] verified_extract → %s  value=%r",
                            skill_result.outcome.status, skill_result.outcome.retrieved_data)
                return skill_result.outcome, step + 1
            messages.append(format_tool_result(tool_id, skill_result.feedback))
            continue

        # --- Browser actions ---
        action_dict = {
            "target": args.get("target", ""),
            "value": args.get("value", ""),
            "url": args.get("url", ""),
            "element_type": args.get("element_type", ""),
            "submit": args.get("submit", False),
            "query": args.get("query", ""),
        }
        # search tool uses 'query' not 'target'
        if action_name == "search" and not action_dict["target"]:
            action_dict["target"] = action_dict["query"]

        prev_state = _capture_page_state(current_obs)
        action_result = await _execute_browser_action(
            action_type=action_name, action=action_dict, page=page,
            current_obs=current_obs,
        )

        if action_result.should_continue:
            current_obs = action_result.observation or current_obs
            feedback = action_result.feedback
            logger.info("[LLM] step=%d  result=%s", step + 1, feedback)
            messages.append(format_tool_result(tool_id, feedback))
            continue

        current_obs = await observe_page(page)
        is_inpage = action_result.succeeded and current_obs.url == prev_state.url
        if is_inpage:
            current_obs = await _wait_for_dom_stable(page, prev_state, current_obs)
        feedback = _summarize_action_result(
            action_name, action_dict, action_result.succeeded, current_obs, prev_state,
        )
        logger.info("[LLM] step=%d  result=%s", step + 1, feedback)
        messages.append(format_tool_result(tool_id, feedback))
        last_action_feedback = feedback

    # step_budget 소진 → done 선언 없이 끝남 = 실패
    return ExecutionOutcome(
        task_type=task_type, status="SUB_GOAL_FAILED",
        error_details=f"Not completed in {step_budget} steps. {_summarize_action_history(_action_history)}",
    ), step_budget


async def _wait_for_dom_stable(
    page: Any, prev_state: Any, current_obs: PageObservation,
) -> PageObservation:
    """in-page 클릭 후 AJAX 콘텐츠 안정화 대기. 연속 안정 2회 확인."""
    try:
        if (set(current_obs.dropdown_options) != prev_state.dropdown
                or set(current_obs.links) != prev_state.links
                or set(current_obs.buttons) != prev_state.buttons):
            consecutive_stable = 0
            cur_dropdown = set(current_obs.dropdown_options)
            cur_links = set(current_obs.links)
            cur_buttons = set(current_obs.buttons)
            for _ in range(6):  # max 3s
                await page.wait_for_timeout(500)
                updated_obs = await observe_page(page)
                upd_dropdown = set(updated_obs.dropdown_options)
                upd_links = set(updated_obs.links)
                upd_buttons = set(updated_obs.buttons)
                if upd_dropdown == cur_dropdown and upd_links == cur_links and upd_buttons == cur_buttons:
                    consecutive_stable += 1
                    if consecutive_stable >= 2:
                        break
                else:
                    consecutive_stable = 0
                    current_obs = updated_obs
                    cur_dropdown, cur_links, cur_buttons = upd_dropdown, upd_links, upd_buttons
    except Exception:
        logger.debug("DOM stabilization interrupted")
    return current_obs


def _trim_messages(messages: list[dict], max_messages: int) -> list[dict]:
    """Tool Use 쌍 무결성을 보장하면서 메시지를 트리밍한다.

    assistant(tool_use)의 tool_call_id가 반드시 대응하는 tool_result를 가지도록
    완전한 교환 단위로만 자른다.
    """
    if len(messages) <= max_messages:
        return messages

    # 뒤에서 max_messages개 자르기
    trimmed = messages[-max_messages:]

    # 잘린 결과에서 assistant(tool_use)의 tool_call_id 수집
    assistant_tool_ids: set[str] = set()
    result_tool_ids: set[str] = set()
    for msg in trimmed:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "tool_use":
                    assistant_tool_ids.add(block.get("id", ""))
                elif block.get("type") == "tool_result":
                    result_tool_ids.add(block.get("tool_use_id", ""))

    # orphaned: tool_result는 있는데 대응하는 assistant가 없거나 그 반대
    orphaned_ids = (assistant_tool_ids - result_tool_ids) | (result_tool_ids - assistant_tool_ids)
    if not orphaned_ids:
        return trimmed

    # orphaned 메시지 제거
    cleaned = []
    for msg in trimmed:
        content = msg.get("content")
        if isinstance(content, list):
            dominated = False
            for block in content:
                if isinstance(block, dict):
                    bid = block.get("id", "") or block.get("tool_use_id", "")
                    if bid in orphaned_ids:
                        dominated = True
                        break
            if dominated:
                continue
        cleaned.append(msg)
    return cleaned


def _summarize_action_history(history: list[str]) -> str:
    """액션 이력을 행동 유형별로 그룹화하여 요약한다."""
    from collections import Counter
    counts = Counter(history)
    parts = [f"{action} x{count}" for action, count in counts.most_common()]
    return f"Actions tried: {' | '.join(parts)}" if parts else ""


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def _replan(
    *,
    task: str,
    task_type: str,
    observation: PageObservation,
    llm: LLMClient,
    completed_goals: list[SubGoal],
    failed_goal: SubGoal,
    failure_history: list[str],
) -> list[SubGoal]:
    """실패한 sub-goal 이후의 plan을 재생성한다 (Tool Use)."""
    navigate_rule = (
        "\nIMPORTANT: For NAVIGATE tasks, the LAST sub-goal MUST be type 'navigation'.\n"
        if task_type == "NAVIGATE" else ""
    )
    system = (
        "You are a web task planner. A sub-goal has failed after multiple retries.\n"
        "Create a new list of sub-goals to complete the remaining task from the current page state.\n"
        f"{navigate_rule}"
        "Keep each sub-goal to one short sentence."
    )
    user_msg = (
        f"Task: {task}\n"
        f"Completed goals: {[g.goal for g in completed_goals]}\n"
        f"Failed goal: {failed_goal.goal}\n"
        f"Failure history: {failure_history}\n"
        f"Current URL: {observation.url}\n"
        f"Page title: {observation.title}\n"
        f"Links (first 15): {observation.links[:15]}\n"
        f"Buttons: {observation.buttons[:10]}\n"
    )
    try:
        response = llm.complete_with_tools(
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            tools=[replan_tool()],
        )
        if response.tool_calls and response.tool_calls[0].name == "replan":
            new_goals = response.tool_calls[0].arguments.get("sub_goals", [])
            if isinstance(new_goals, list) and new_goals:
                result = []
                for g in new_goals:
                    if isinstance(g, dict):
                        result.append(SubGoal(str(g.get("goal", "")), str(g.get("type", "cognition"))))
                    else:
                        result.append(SubGoal(str(g)))
                return result
    except Exception:
        pass
    return []



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
    """click/fill/search/goback 액션 실행. _ActionResult를 반환한다."""
    if action_type == "click":
        return await _execute_click(action, page, current_obs)
    if action_type == "fill":
        return await _execute_fill(action, page)
    if action_type == "search":
        return await _execute_search(action, page)
    if action_type == "goback":
        return await _execute_goback(page)
    return _ActionResult()


async def _execute_click(action: dict[str, Any], page: Any, obs: PageObservation) -> _ActionResult:
    """click 액션: 드롭다운 → element_type → 충돌감지 → links → get_by_role → fallback 순으로 시도."""
    target = action.get("target", "")
    url_hint = action.get("url", "")
    element_type = action.get("element_type", "")
    # target에 " → /path" 포함 시 자동 파싱 (이름 + url_hint 분리)
    if " → " in target:
        parts = target.split(" → ", 1)
        target = parts[0].strip()
        if not url_hint:
            url_hint = parts[1].strip()
    # url_hint가 전체 URL이면 경로만 추출 (href는 경로만 가짐)
    if url_hint.startswith("http"):
        from urllib.parse import urlparse
        url_hint = urlparse(url_hint).path
    logger.info("[LLM] click  target=%r  url_hint=%r  element_type=%r", target, url_hint, element_type)
    if not target:
        return _ActionResult()

    target_lower = target.lower()

    # 0. 드롭다운 정확 매칭 (최우선 — 드롭다운 항목은 role="menuitem"이라 link/button으로 못 잡음)
    matching_dropdown = [d for d in obs.dropdown_options if d.split(" → ")[0].lower() == target_lower]
    if matching_dropdown:
        for dd_sel in ('.dropdown-item', '[role="option"]', '[role="menuitem"]', '[role="tab"]'):
            try:
                loc = page.locator(f'{dd_sel}:visible').filter(has_text=target)
                if await loc.count() > 0:
                    await loc.first.click()
                    logger.info("[LLM] click via dropdown option (%s): %r", dd_sel, target)
                    return _ActionResult(succeeded=True)
            except Exception as exc:
                logger.debug("dropdown click (%s) failed: %s", dd_sel, exc)

    # 1. element_type이 지정되면 해당 타입으로 시도
    if element_type in ("button", "link"):
        try:
            loc = page.get_by_role(element_type, name=target)
            count = await loc.count()
            if count > 1 and url_hint:
                for i in range(count):
                    href = await loc.nth(i).get_attribute("href") or ""
                    if url_hint in href:
                        await loc.nth(i).click()
                        logger.info("[LLM] click via element_type=%s + url_hint: %r", element_type, target)
                        return _ActionResult(succeeded=True)
            if count > 1 and not url_hint:
                hrefs = []
                for i in range(min(count, 5)):
                    href = await loc.nth(i).get_attribute("href") or ""
                    hrefs.append(href)
                return _ActionResult(
                    should_continue=True,
                    feedback=(
                        f"Multiple {element_type}s match '{target}': {hrefs}. "
                        "Set 'url' to the pathname of the intended target."
                    ),
                )
            if count == 1:
                await loc.first.click()
                logger.info("[LLM] click via element_type=%s: %r", element_type, target)
                return _ActionResult(succeeded=True)
        except Exception as exc:
            logger.debug("element_type=%s click failed: %s", element_type, exc)
    # 2. 타입 충돌 감지: element_type 없이 여러 타입에 매칭되면 되묻기
    matching_links = [l for l in obs.links if target_lower in l.split(" → ")[0].lower()]
    matching_buttons = [b for b in obs.buttons if target_lower in b.split(" [")[0].lower()]

    if not element_type:
        type_matches: list[str] = []
        if matching_dropdown:
            type_matches.append(f"dropdown={matching_dropdown[0]}")
        if matching_links:
            type_matches.append(f"link={matching_links[0]}")
        if matching_buttons:
            type_matches.append(f"button={matching_buttons[0]}")
        if len(type_matches) > 1:
            return _ActionResult(
                should_continue=True,
                feedback=(
                    f"'{target}' matches multiple element types: {', '.join(type_matches)}. "
                    "Set \"element_type\" to \"button\" or \"link\" to disambiguate."
                ),
            )

    # 3. 관측 links에서 매칭
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

    # 4. get_by_role fallback
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


async def _execute_search(action: dict[str, Any], page: Any) -> _ActionResult:
    """search 액션."""
    query = action.get("target", "")
    logger.info("[LLM] search  query=%r", query)
    if query:
        succeeded = await try_search(page, query)
        return _ActionResult(succeeded=succeeded)
    return _ActionResult(succeeded=False)


async def _execute_goback(page: Any) -> _ActionResult:
    """goback 액션: 이전 페이지로 돌아간다."""
    logger.info("[LLM] goback")
    try:
        await page.go_back()
        return _ActionResult(succeeded=True)
    except Exception:
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


def _describe_content_delta(prev: _PageState, current_obs: PageObservation) -> str:
    """액션 후 새로 나타난 요소를 요약한다 (주변부 변화)."""
    new_dropdown = [d for d in current_obs.dropdown_options if d not in prev.dropdown]
    new_buttons = [b for b in current_obs.buttons if b not in prev.buttons]
    new_links = [l for l in current_obs.links if l not in prev.links]

    parts: list[str] = []
    if new_dropdown:
        parts.append(f"New options appeared: {new_dropdown[:15]}")
    if new_buttons:
        parts.append(f"New buttons: {new_buttons[:10]}")
    if new_links:
        parts.append(f"New links: {new_links[:10]}")

    return "; ".join(parts) if parts else ""


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
        delta = _describe_content_delta(prev, current_obs)
        if delta:
            return f"click '{target}': {delta}"
        if set(current_obs.links) != prev.links or set(current_obs.buttons) != prev.buttons or set(current_obs.dropdown_options) != prev.dropdown:
            return f"click '{target}': page content changed"
        return f"click '{target}': no visible change"

    if action_type == "fill":
        target = action.get("target", "")
        if not succeeded:
            return f"fill '{target}': field not found"
        if current_obs.url != prev.url:
            return f"fill '{target}': navigated to {current_obs.url}"
        delta = _describe_content_delta(prev, current_obs)
        if delta:
            return f"fill '{target}': submitted. {delta}"
        return f"fill '{target}': submitted (no visible change)"

    if action_type == "search":
        query = action.get("target", "")
        if not succeeded:
            return f"search '{query}': search field not found"
        if current_obs.url != prev.url:
            return f"search '{query}': navigated to {current_obs.url}"
        delta = _describe_content_delta(prev, current_obs)
        if delta:
            return f"search '{query}': {delta}"
        return f"search '{query}': URL unchanged"

    if action_type == "goback":
        if not succeeded:
            return "goback: failed"
        return f"goback: navigated to {current_obs.url}"

    return ""


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _get_tool_action(
    llm: LLMClient, system: str, messages: list[dict], tools: list[dict],
) -> tuple[str, dict[str, Any], str, str, list[dict]]:
    """Tool Use LLM 호출. tool call이 없으면 1회 재시도.

    Returns: (action_name, arguments, thought, tool_call_id, updated_messages)
    """
    response = llm.complete_with_tools(system=system, messages=messages, tools=tools)
    messages.append(format_assistant_tool_use(response))

    if not response.tool_calls:
        logger.info("[LLM] no tool call, nudging")
        messages.append({"role": "user", "content": "You must call exactly one tool. Choose a tool now."})
        response = llm.complete_with_tools(system=system, messages=messages, tools=tools)
        messages.append(format_assistant_tool_use(response))

    if not response.tool_calls:
        return "not_found", {}, "", "none", messages

    tc = response.tool_calls[0]
    return tc.name, tc.arguments, response.thought or "", tc.id, messages


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
