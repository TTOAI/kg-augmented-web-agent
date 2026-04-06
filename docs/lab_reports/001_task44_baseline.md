# Lab Report 001 — Task 44 Baseline (Prior 없는 LLM 일반 추론)

**날짜**: 2026-04-06  
**목적**: prior DB 없이 LLM 일반 추론만으로 GitLab task 44를 얼마나 안정적으로 완수할 수 있는지 기준선 측정

---

## 실험 조건

| 항목      | 값                                   |
| --------- | ------------------------------------ |
| Task ID   | 44                                   |
| Intent    | "Open my todos page"                 |
| Site      | GitLab (`http://localhost:8023`)     |
| Start URL | `http://localhost:8023`              |
| Task Type | NAVIGATE                             |
| LLM       | Anthropic Claude (claude-sonnet-4-6) |
| Prior DB  | 비어있음 (FALLBACK 경로)             |
| Max Steps | 5                                    |
| 반복 횟수 | 10                                   |

---

## 결과 요약

| 지표       | 값      |
| ---------- | ------- |
| 성공       | 3 / 10  |
| 실패       | 7 / 10  |
| **성공률** | **30%** |

---

## 실행별 상세 결과

| 실행 디렉토리 | 결과         | 비고                                     |
| ------------- | ------------ | ---------------------------------------- |
| 44_bkp_1      | ✅ SUCCESS   | `goto /dashboard/todos` → `extract` URL  |
| 44_bkp_2      | ✅ SUCCESS   | `goto /dashboard/todos` → `extract` URL  |
| 44_bkp_3      | ❌ NOT_FOUND | max_steps(5) 소진                        |
| 44_bkp_4      | ❌ NOT_FOUND | max_steps(5) 소진                        |
| 44_bkp_5      | ❌ NOT_FOUND | LLM 첫 스텝에서 즉시 포기                |
| 44_bkp_6      | ❌ NOT_FOUND | todos 페이지 도달했으나 실패 처리 (버그) |
| 44_bkp_7      | ❌ NOT_FOUND | max_steps(5) 소진                        |
| 44_bkp_8      | ❌ NOT_FOUND | todos 페이지 도달했으나 실패 처리 (버그) |
| 44_bkp_9      | ✅ SUCCESS   | `goto /dashboard/todos` → `extract` URL  |
| 44 (최신)     | ❌ NOT_FOUND | LLM 첫 스텝에서 즉시 포기                |

---

## 실패 유형 분류

### 유형 A: max_steps 소진 (3건 — bkp_3, bkp_4, bkp_7)

LLM이 GitLab 상단 nav의 todos 아이콘을 `click`으로 찾으려 했으나 실제 클릭에 실패해 5번 시도 후 포기.

**원인**: `observe_page()`는 `extract_texts()`의 aria-label 폴백 덕분에 "Todos"를 수집했고 LLM도 이를 인지해 `click` 액션을 선택했을 것으로 보인다. 그러나 `try_click_target()`이 `inner_text()`만 사용하기 때문에 aria-label만 있는 icon-only 링크는 텍스트가 빈 문자열로 반환되어 매칭에 실패한다. 관찰(observe)과 실행(click) 간의 불일치가 원인.

### 유형 B: 첫 스텝 즉시 포기 (2건 — bkp_5, 44)

LLM이 첫 관찰에서 todos 링크가 보이지 않는다고 판단하고 바로 `not_found` 반환.

> bkp_5: _"no explicit 'todos' link is visible ... task cannot be completed from the current state"_
> 44: _"visible navigation includes links for assigned items and review requests, but no explicit 'todos' link"_

**원인**: 유형 A와 달리 LLM이 observation에서 "Todos"를 인식하지 못한 케이스. `extract_texts()`가 수집한 aria-label 값이 LLM 프롬프트의 links 목록에 포함됐음에도 LLM이 이를 todos 링크로 연결하지 못했거나, 해당 실행 시점에 GitLab nav 렌더링이 달랐을 가능성이 있다.

### 유형 C: 목표 도달 후 실패 처리 (2건 — bkp_6, bkp_8)

LLM이 `/dashboard/todos`에 도달했음을 인지했음에도 NOT_FOUND_ERROR를 반환.

> bkp_6: _"The todos page is already open and visible, so the task is complete; no further action is needed."_
> bkp_8: _"The todos page is already open at the current URL, so no further navigation is needed."_

**원인**: `_execute_with_llm()`의 액션 스페이스에 NAVIGATE 완료를 알리는 수단이 없음. `extract`는 RETRIEVE 전용으로 인식되고, `not_found`만 남아 어쩔 수 없이 실패 처리됨.

---

## 성공 메커니즘 분석

성공한 3번(bkp_1, bkp_2, bkp_9)은 모두 같은 패턴:

1. LLM이 GitLab URL 패턴(`/dashboard/todos`)을 학습 데이터에서 알고 있어 `goto` 액션으로 직접 이동
2. 이동 후 `extract` 액션으로 현재 URL을 반환 → RETRIEVE SUCCESS 처리

즉, 성공은 **nav 아이콘 클릭이 아닌 URL 직접 추측**으로 이뤄졌다.
관찰 범위 문제를 우회한 것이지 해결한 것이 아님.

---

## 발견된 버그 및 구조적 문제

### Bug 1: NAVIGATE 완료 신호 부재 (유형 C)

`_execute_with_llm()`의 액션 스페이스: `extract | click | goto | search | fill | not_found`

NAVIGATE 태스크에서 LLM이 목표 페이지에 도달했을 때 성공을 선언할 방법이 없음.
→ **수정 방향**: `done` 액션 추가, task_type=NAVIGATE일 때 → SUCCESS 처리

### Bug 2: LLM 전략 비결정성

동일 task를 반복 실행할 때 LLM이 매번 다른 전략을 선택함:

- 운 좋으면: `goto` URL 직접 이동 → 성공
- 운 나쁘면: `click` 탐색 → 실패

prior가 없으면 이 비결정성을 제어할 방법이 없음.

### Click-Observe 불일치

`observe_page()`는 aria-label 폴백으로 icon-only 링크를 수집하지만, `try_click_target()`은 여전히 `inner_text()`만 사용해 매칭한다. LLM이 링크를 인지하고 `click` 액션을 반환해도 실제 클릭이 실패하는 구조적 불일치가 있다.
→ **미수정**: `try_click_target()`에도 aria-label/title 폴백 적용 필요.

---

## 다음 액션

1. **`done` 액션 추가** — 유형 C(2건) 즉시 해결 가능
2. **aria-label 수집 추가 후 재실험** — 유형 A, B 개선 여부 확인 (이미 코드 반영됨)
3. **다른 task로 범위 확장** — task 44 이외의 다양한 유형(RETRIEVE, MUTATE) 측정
