from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("webarena_verified")

from .runtime.playwright_runtime import observe_page, try_click_target, try_fill_target, try_search
from .config import LLMClient
from .types import SubGoal
from .runtime.observation_builder import build_observation_message
from .planner.baseline import build_plan, build_tool_use_system_prompt
from .runtime.tools import format_assistant_tool_use, format_tool_result, replan_tool, tools_for_goal
from .evaluator.simple import verify_done
from .types import ExecutionOutcome, PageObservation


_FAILURE_ACTION_TO_STATUS: dict[str, str] = {
    "not_found": "NOT_FOUND_ERROR",
    "permission_denied": "PERMISSION_DENIED_ERROR",
    "action_not_allowed": "ACTION_NOT_ALLOWED_ERROR",
    "data_validation_error": "DATA_VALIDATION_ERROR",
    "unknown_error": "UNKNOWN_ERROR",
}


# ---------------------------------------------------------------------------
# LLM execution loop (entry point)
# ---------------------------------------------------------------------------

_MAX_RETRIES_PER_GOAL = 8


async def execute_with_llm(
    *,
    task: str,
    task_type: str,
    page: Any,
    observation: PageObservation,
    llm: LLMClient,
    max_steps: int = 50,
) -> ExecutionOutcome:
    """Sub-goal별 실행 루프. checkpoint + graduated retry로 태스크를 완수한다."""
    t_start = time.time()
    system = build_tool_use_system_prompt()

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
        step_budget = max(6, (max_steps - steps_used) // remaining_goals)
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
                start_url=checkpoint_stack[0],
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
            from .runtime.tools import _extract_tool
            notes_str = f"\nRemembered facts: {task_notes}" if task_notes else ""
            extract_msg = (
                f"Task: {task}\n"
                f"All preparation steps are complete. Now extract the final answer.{notes_str}\n"
                f"Current URL: {obs.url}\n"
                f"Page title: {obs.title}\n"
                f"Visible text (first 10): {obs.text_lines[:10]}\n"
                f"Links (first 10): {obs.links[:10]}\n"
                "\n"
                "Verification before extracting:\n"
                "1. Identify the exact format the task asks for "
                "(e.g. an ID is a unique identifier, a count is a number of items, "
                "an email contains @, a URL starts with http).\n"
                "2. From the notes and visible info, select ONLY values that match that format. "
                "Do not confuse one field type with another "
                "(e.g. a count vs an ID, a name vs an ID).\n"
                "3. Determine whether the task is singular or plural:\n"
                "   - Singular markers: definite article 'the', no plural 's', single answer expected\n"
                "   - Plural markers: 's', '(s)', 'or', 'all', 'each', 'list', 'IDs', 'names'\n"
                "4. Inclusion policy depends on plurality:\n"
                "   - If SINGULAR and uncertain about a value, exclude it (be conservative)\n"
                "   - If PLURAL and a value of the correct format is mentioned anywhere in your\n"
                "     notes or your prior reasoning, INCLUDE it (be inclusive — better to return\n"
                "     a candidate than to omit it). Re-read the notes carefully for all matches."
            )
            extract_response = llm.complete_with_tools(
                system=system,
                messages=[{"role": "user", "content": extract_msg}],
                tools=[_extract_tool()],
            )
            if extract_response.tool_calls and extract_response.tool_calls[0].name == "extract":
                args = extract_response.tool_calls[0].arguments
                result = _handle_extract({"value": args.get("value", ""), "label": args.get("label", "")}, task_type)
                elapsed = time.time() - t_start
                logger.info("[LLM] final extract in %.1fs (%d steps)", elapsed, steps_used)
                return result
        except Exception:
            pass
        # RETRIEVE인데 extract 실패 → 데이터 없이 SUCCESS 방지
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
                step_budget = max(6, (max_steps - steps_used) // remaining_goals)
                result, used = await _try_sub_goal(
                    task=task, task_type=task_type, sub_goal=sub_goal,
                    sub_goals=sub_goals, goal_index=goal_idx,
                    page=page, llm=llm, system=system,
                    step_budget=step_budget, previous_failures=[],
                    is_last_goal=(goal_idx == len(sub_goals) - 1),
                    task_notes=task_notes,
                    start_url=checkpoint_stack[0],
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
    start_url: str = "",
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
    _sub_goal_start_url = current_obs.url  # 현재 sub-goal 진입 시점 URL (navigation hard check용)
    tools = tools_for_goal(is_last_goal=is_last_goal, task_type=task_type)

    # 이전 실패 이력을 피드백으로 주입 (graduated retry)
    if previous_failures:
        retry_count = len(previous_failures)
        all_failures = " | ".join(previous_failures)
        if retry_count <= 2:
            last_action_feedback = (
                f"Attempt {retry_count} failed. Previous attempts: {all_failures}. "
                "Do NOT repeat these actions. Try a different approach. "
                "Use goback to return to a known page if you're lost."
            )
        elif retry_count <= 5:
            last_action_feedback = (
                f"Attempt {retry_count} failed. Previous attempts: {all_failures}. "
                "Try a COMPLETELY different navigation path. "
                "Use goback aggressively to return to a familiar page, then explore a new route."
            )
        else:
            last_action_feedback = (
                f"This goal has failed {retry_count} times. Previous attempts: {all_failures}. "
                "STOP trying the same area. Go back to the starting page and take an entirely different path."
            )

    for step in range(step_budget):
        _log_step_observation(step, current_obs, sub_goals, goal_index)

        user_msg = build_observation_message(
            task=task, observation=current_obs, last_action_feedback=last_action_feedback,
            sub_goals=sub_goals, current_goal_index=goal_index,
            start_url=start_url,
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

        # --- Auto-accumulate optional memo from any action tool ---
        memo_text = (args.get("memo") or "").strip()
        if memo_text and task_notes is not None:
            task_notes.append(memo_text)
            logger.info("[LLM] step=%d  memo=%r", step + 1, memo_text)

        # --- Terminal actions ---
        if action_name == "done":
            # 마지막 sub-goal done 시 pending network request(예: graphql) 완료 대기
            # → race condition(network event가 evaluator에 response_status=-1로 기록) 방지
            if is_last_goal:
                try:
                    await page.wait_for_load_state("networkidle", timeout=2000)
                    current_obs = await observe_page(page)
                except Exception:
                    pass
            # done 검증: LLM에게 현재 상태와 목표를 대조시킴 (task_notes 함께 검토)
            done_reason = args.get("reason", "")
            verified = verify_done(
                goal=sub_goal.goal, reason=done_reason, current_obs=current_obs,
                llm=llm, task_notes=task_notes,
                sub_goal_type=sub_goal.goal_type,
                sub_goal_start_url=_sub_goal_start_url,
                is_last_goal=is_last_goal,
            )
            if verified is True:
                logger.info("[LLM] sub-goal done (verified) [%s]: %r", sub_goal.goal_type, sub_goal.goal)
                return None, step + 1
            logger.info("[LLM] sub-goal done REJECTED: %s", verified)
            last_action_feedback = f"Done rejected — goal not yet achieved: {verified}. Keep working."
            messages.append(format_tool_result(tool_id, last_action_feedback))
            continue

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

        # --- search skill ---
        if action_name == "search":
            query = args.get("query", "")
            prev_state = _capture_page_state(current_obs)
            feedback = await _execute_search(query=query, page=page)
            current_obs = await observe_page(page)
            if current_obs.url != prev_state.url:
                from urllib.parse import urlparse, parse_qs
                params = parse_qs(urlparse(current_obs.url).query)
                params_str = ", ".join(f"{k}={v[0]}" for k, v in params.items()) if params else "(none)"
                feedback += f" URL: {current_obs.url} | Params: {params_str}"
            logger.info("[LLM] step=%d  search=%r  result=%s", step + 1, query, feedback)
            messages.append(format_tool_result(tool_id, feedback))
            last_action_feedback = feedback
            continue

        # --- Browser actions ---
        action_dict = {
            "target": args.get("target", ""),
            "value": args.get("value", ""),
            "url": args.get("url", ""),
            "element_type": args.get("element_type", ""),
            "submit": args.get("submit", False),
        }

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
                        result.append(SubGoal(str(g.get("goal", "")), str(g.get("type", "action"))))
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
    """click/fill/goback 등 browser 액션 실행. _ActionResult를 반환한다."""
    if action_type == "click":
        return await _execute_click(action, page, current_obs)
    if action_type == "fill":
        return await _execute_fill(action, page)
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


async def _execute_search(*, query: str, page: Any) -> str:
    """search skill: 검색/필터 input 클릭 → AJAX 대기 → 드롭다운 매칭 또는 fill → Enter.

    Returns: 피드백 문자열
    """
    logger.info("[LLM] search  query=%r", query)
    if not query:
        return "search requires a 'query'."

    # 1. 검색/필터 input 찾아서 클릭 (포커스)
    search_selectors = [
        'input[type="search"]:visible',
        'input[placeholder*="search" i]:visible',
        'input[placeholder*="filter" i]:visible',
        'input[role="searchbox"]:visible',
    ]
    input_clicked = False
    for sel in search_selectors:
        try:
            loc = page.locator(sel)
            if await loc.count() > 0:
                await loc.first.click()
                input_clicked = True
                logger.info("[LLM] search: clicked input via %s", sel)
                break
        except Exception:
            continue

    if not input_clicked:
        # fallback: try_search로 대체
        succeeded = await try_search(page, query)
        return f"search '{query}': {'submitted via fallback' if succeeded else 'search field not found'}"

    # 2. DOM 안정화 (AJAX 드롭다운 로딩 대기)
    await page.wait_for_timeout(500)
    obs_after_click = await observe_page(page)

    # 연속 안정 체크
    for _ in range(4):
        await page.wait_for_timeout(500)
        obs_check = await observe_page(page)
        if set(obs_check.dropdown_options) == set(obs_after_click.dropdown_options):
            break
        obs_after_click = obs_check

    # 3. 드롭다운에서 query 매칭 시도
    query_lower = query.lower()
    matched_option = None
    for opt in obs_after_click.dropdown_options:
        opt_name = opt.split(" → ")[0] if " → " in opt else opt
        if query_lower == opt_name.lower():
            matched_option = opt_name
            break

    if matched_option:
        # 드롭다운 항목 클릭
        for dd_sel in ('.dropdown-item', '[role="option"]', '[role="menuitem"]', '[role="tab"]'):
            try:
                loc = page.locator(f'{dd_sel}:visible').filter(has_text=matched_option)
                if await loc.count() > 0:
                    await loc.first.click()
                    logger.info("[LLM] search: clicked dropdown option '%s' via %s", matched_option, dd_sel)

                    # 하위 드롭다운 로딩 대기
                    await page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        return f"search '{query}': selected '{matched_option}' from dropdown."
    else:
        # 드롭다운에 없으면 fill + Enter
        try:
            for sel in search_selectors:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    await loc.first.fill(query)
                    await loc.first.press("Enter")
                    logger.info("[LLM] search: filled '%s' and pressed Enter", query)
                    break
        except Exception as exc:
            logger.debug("search fill failed: %s", exc)
            return f"search '{query}': failed to fill search field."

        return f"search '{query}': typed and submitted."


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
# Agent 실행 진입점 (V2.5 run_agent 이식)
# ---------------------------------------------------------------------------

from pathlib import Path as _Path

from dotenv import load_dotenv as _load_dotenv

from .config import make_llm_client
from .runtime.intent_utils import analyze_intent
from .types import AgentRunResult

_load_dotenv()

__all__ = ["run_agent", "execute_with_llm"]


async def run_agent(
    *,
    intent: str,
    sites: list[str],
    start_urls: list[str],
    task_id: int,
    context: Any,
    pages: list[Any],
    task_output_dir: _Path,
) -> AgentRunResult:
    """웹 에이전트 정책을 실행한다."""
    del context, task_id, task_output_dir, sites, start_urls

    if not pages:
        return AgentRunResult.unknown_error("No pages opened for this task")

    llm = make_llm_client()
    plan = analyze_intent(intent, llm=llm)
    primary_page = pages[0]
    observation = await observe_page(primary_page)

    if llm is None:
        return AgentRunResult.unknown_error(
            "LLM client unavailable — set ANTHROPIC_API_KEY or OPENAI_API_KEY"
        )

    outcome = await execute_with_llm(
        task=intent,
        task_type=plan.task_type,
        page=primary_page,
        observation=observation,
        llm=llm,
    )

    return AgentRunResult(
        task_type=outcome.task_type,
        status=outcome.status,
        retrieved_data=outcome.retrieved_data,
        error_details=outcome.error_details,
    )
