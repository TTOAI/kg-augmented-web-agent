# Agent Execution Architecture v2

## 배경

### 현재 구조의 문제

현재 에이전트는 **선형 실행 구조**로, 최대 15스텝을 순차적으로 소진한다.

```
step 1 → step 2 → step 3 → ... → step 15 (소진)
```

이 구조의 핵심 문제:

1. **되돌아갈 수 없다**: 잘못된 페이지에 들어가면 복구가 LLM의 자발적 goto에 의존한다.
2. **실패를 반복한다**: 같은 관측 → 같은 LLM 판단 → 같은 실패가 반복되며 스텝을 낭비한다.
3. **검증이 마지막에만 있다**: 중간 스텝에서 잘못된 경로인 걸 인식하지 못한다.
4. **한 곳에서 모든 스텝을 소진한다**: sub-goal이 3개여도 goal 1에서 15스텝을 다 쓸 수 있다.
5. **executor가 판단을 대신한다**: fill→click 리다이렉트, 동명 링크 후보 제시, done 검증 등 executor가 LLM의 결정을 덮어쓰는 특수 로직이 많다.

### 설계 원칙

1. **빠르게 실행하고, 빠르게 검증하고, 빠르게 되돌린다.** 정답 경로를 처음부터 완벽히 찾는 것보다, 오답 경로를 빠르게 인식하고 복귀하는 것이 효율적이다.
2. **LLM의 판단을 zero-trust하되, 첫 판단의 방향은 신뢰한다.** Planning과 intent 분석이 잘 되어 있다면 첫 시도의 접근(방향)은 대체로 맞다. 실패는 보통 실행(방법) 수준이므로, 재시도 시 같은 접근에서 미세 조정을 우선한다.
3. **Executor는 범용 도구이다.** Executor는 LLM의 판단을 충실히 수행하고 결과를 정확히 보고한다. 판단을 대신하거나 덮어쓰지 않는다. LLM이 다양한 판단을 할 수 있도록 실행 능력을 넓게 열어둔다.

---

## 아키텍처

### 레이어 구조

```
Task Intent
    ↓
Planning Layer: sub-goal 분해
    ↓
Sub-goal별 실행 (retry with checkpoint):
    ↓
    Observation: 페이지 상태 수집
        ↓
    LLM: 다음 액션 판단
        ↓
    Executor: 판단을 충실히 실행
        ↓
    Feedback: 실행 결과 보고
        ↓
    Verification: sub-goal 달성 확인
        ↓
    성공 → checkpoint 갱신 + 다음 sub-goal
    실패 → checkpoint 복원 + graduated retry
```

### 각 레이어의 책임

| 레이어 | 책임 | 하지 않는 것 |
|---|---|---|
| **Planning** | task를 sub-goal로 분해 | 실행 방법 결정 |
| **Observation** | 페이지 상태를 풍부하고 정확하게 수집 | 상태 해석 |
| **LLM** | 관측 + 피드백을 보고 다음 액션 판단 | 직접 실행 |
| **Executor** | LLM의 판단을 충실히 실행 + 결과 보고 | 판단 대신하기, 액션 변경 |
| **Verification** | sub-goal 달성 여부 독립 판단 | 실행에 개입 |
| **Retry** | 실패 시 checkpoint 복원 + 피드백 주입 | 다음 시도의 방향 강제 |

### Executor의 역할 재정의

Executor는 **"할 수 있는 것"을 최대한 넓히되, "해야 하는 것"을 판단하지 않는다.**

- LLM이 fill을 보내면 fill을 한다. 드롭다운이 열리든 안 열리든 결과를 보고한다.
- LLM이 click을 보내면 click을 한다. 여러 요소가 매칭되면 첫 번째를 클릭하고 결과를 보고한다.
- LLM이 done을 보내면 done을 접수한다. Verification 레이어가 독립적으로 검증한다.

Executor가 판단을 대신하던 로직(fill→click 리다이렉트, 동명 링크 후보 제시 등)은 제거하거나, LLM에게 풍부한 피드백으로 대체한다.

---

## Sub-goal별 실행 + Checkpoint + Retry

### 전체 흐름

```python
async def execute_task(task, page, llm):
    plan = build_plan(task, observe_page(page), llm)
    checkpoint = Checkpoint(url=page.url, goal_index=0)

    for i, sub_goal in enumerate(plan):
        failures = []

        for attempt in range(MAX_RETRIES_PER_GOAL):
            result = try_sub_goal(
                sub_goal, page, llm,
                step_budget=remaining_steps // remaining_goals,
                previous_failures=failures,
            )

            if result.succeeded:
                checkpoint = Checkpoint(url=page.url, goal_index=i+1)
                break

            await page.goto(checkpoint.url)
            failures.append(result)

    return final_result
```

### Checkpoint

- sub-goal **성공 후에만** 갱신
- 실패 시 이전 성공 지점으로 복원 (`page.goto(checkpoint.url)`)
- 저장하는 것: URL, goal index

### 스텝 예산

- 총 스텝을 남은 sub-goal 수로 나누어 배분
- 한 sub-goal이 전체 스텝을 소진하지 않도록 방지

---

## Graduated Retry (단계적 재시도)

### 원칙

첫 시도의 **접근(방향)을 신뢰**한다. 실패 시 접근 자체를 바꾸는 것이 아니라, **실행 방법을 미세 조정**하며 정답을 찾아간다.

### 재시도 레벨

| 레벨 | 전략 | 피드백 예시 |
|---|---|---|
| **1. 실행 미세 조정** | 같은 접근, 클릭/입력 방법만 변경 | "접근은 합리적이었습니다. 'Label' 클릭이 다른 요소에 맞았습니다. 같은 접근을 유지하되 더 구체적으로 지정해보세요." |
| **2. 경로 변경** | 같은 목표, 다른 진입점 | "같은 접근이 두 번 실패했습니다. 같은 목표를 다른 방법으로 시도해보세요." |
| **3. 접근 전환** | 완전히 다른 방법 | "이 접근이 반복적으로 실패하고 있습니다. 다른 방법을 시도해보세요." |

### 피드백 설계

실패 이력은 **서술적**이어야 한다. 접근을 회피하라는 지시가 아니라, 무슨 일이 있었는지를 기술한다.

```
레벨 1 피드백:
"Your approach of [접근 설명] is likely correct.
The specific issue was: [구체적 실패 원인].
Try the same approach with a small adjustment."

레벨 2 피드백:
"The same approach failed [N] times: [실패 이력 요약].
Try a different way to achieve '[sub-goal]'."

레벨 3 피드백:
"This approach has been tried [N] times without success.
Consider a completely different method for '[sub-goal]'."
```

### 실패 분류

| 유형 | 예시 | 재시도 레벨 |
|---|---|---|
| **실행 실패** | 클릭이 잘못된 요소에 맞음, 타이밍 문제 | 레벨 1 |
| **경로 실패** | 올바른 UI 요소를 못 찾음, 페이지 구조가 예상과 다름 | 레벨 2 |
| **접근 실패** | 해당 기능이 이 페이지에 없음 | 레벨 3 |

---

## Sub-goal 내부 실행

```python
async def try_sub_goal(sub_goal, page, llm, step_budget, previous_failures):
    messages = []

    # 이전 실패 이력을 컨텍스트로 주입
    if previous_failures:
        retry_level = len(previous_failures)
        feedback = build_retry_feedback(previous_failures, retry_level)
        # messages에 포함

    for step in range(step_budget):
        obs = observe_page(page)
        action = llm.decide(obs, messages, sub_goal)
        result = executor.execute(action, page)
        feedback = build_feedback(result)

        if action == "done":
            verified = verify(sub_goal, obs)
            if verified:
                return SubGoalResult(succeeded=True)
            else:
                return SubGoalResult(
                    succeeded=False,
                    description="done declared but verification failed",
                )

    return SubGoalResult(
        succeeded=False,
        description=f"Step budget ({step_budget}) exhausted",
    )
```

---

## 기존 구조와의 비교

| | 현재 (v1) | 새 설계 (v2) |
|---|---|---|
| **실행 단위** | 전체 task (15스텝) | sub-goal별 (예산 분배) |
| **실패 시** | 다음 스텝에서 같은 상황 반복 | checkpoint 복원 + graduated retry |
| **대화 컨텍스트** | 누적 (실패도 포함) | sub-goal마다 초기화 (실패 이력만 포함) |
| **검증** | done 시점에서만 | sub-goal 완료마다 |
| **LLM 비결정성** | 단점 (같은 실수 반복) | 장점 (재시도 시 다른 판단) |
| **Executor 역할** | 판단 대행 (fill→click 등) | 충실한 실행 + 결과 보고 |
| **재시도 전략** | 없음 | 단계적 (미세 조정 → 경로 변경 → 접근 전환) |

---

## 구현 우선순위

1. **Executor 단순화**: 판단 대행 로직 제거, 범용 실행 레이어로 재구성
2. **Sub-goal별 실행 루프**: checkpoint + retry + 스텝 예산 분배
3. **Graduated retry 피드백**: 실패 분류 + 레벨별 피드백 생성
4. **Verification 레이어**: sub-goal별 독립 검증
5. **Observation 강화**: LLM이 더 정확한 판단을 내릴 수 있도록 풍부한 페이지 정보 제공
