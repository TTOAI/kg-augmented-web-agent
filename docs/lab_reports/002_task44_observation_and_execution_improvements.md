# Lab Report 002 — Task 44 관측·실행 레이어 개선 및 재실험

**날짜**: 2026-04-06  
**목적**: Lab Report 001에서 발견된 버그 수정 및 관측·실행 레이어 개선 후 task 44 재측정. 개선 전후 성능 비교 및 잔존 문제 파악.

---

## 001 대비 변경 사항 요약

### 버그 수정

| 버그 (001) | 수정 내용 |
|---|---|
| Bug 1: NAVIGATE 완료 신호 부재 | `done` 액션 추가 → `task_type=NAVIGATE/MUTATE` 시 SUCCESS 처리 |
| Click-Observe 불일치 | `try_click_target()`에 aria-label/title 폴백 추가 |
| 실패 코드 단일화 | NOT_FOUND 외 4종 추가 (permission_denied, action_not_allowed, data_validation_error, unknown_error) |

### 관측 레이어 개선

| 개선 | 내용 |
|---|---|
| 성능 | `extract_texts()` → `evaluate_all()` 단일 JS 호출로 교체 (selector당 ~300 왕복 → 1회) |
| 성능 | `observe_page()` → `asyncio.gather()`로 6개 추출 병렬화 |
| 링크 품질 | `extract_ax_links()` 추가: `page.evaluate()`로 `aria-label + pathname` 조합 추출 |
| 링크 형식 변경 | `'13'` → `'To-Do List → /dashboard/todos'` (LLM이 의미와 URL을 동시에 확인 가능) |

### 실행 레이어 개선

| 개선 | 내용 |
|---|---|
| LLM 클릭 | `try_click_target()` 대신 `page.get_by_role(name=target)` 사용 (semantic 매칭, 대소문자 무관) |
| 매칭 정규화 | `try_click_target()`의 target_terms도 `normalize_text()` 적용 |
| 액션 결과 피드백 | 각 액션(click/fill/goto/search) 결과를 다음 스텝 LLM 메시지에 포함 |

### 디버깅 인프라 개선

- 로그 포맷에 `HH:MM:SS` 타임스탬프 추가
- 스텝별 `links[:20]`, `buttons[:10]` 로깅 추가
- 스텝별 액션 결과 로깅 추가

---

## 실험 조건

| 항목 | 값 |
|---|---|
| Task ID | 44 |
| Intent | "Open my todos page" |
| Site | GitLab (`http://localhost:8023`) |
| Task Type | NAVIGATE |
| LLM | Anthropic Claude (claude-sonnet-4-6) |
| Prior DB | 비어있음 (FALLBACK 경로) |
| Max Steps | 5 |

---

## 개선 과정별 실험 결과

### Phase 1: 링크 로깅 추가 후 (AX tree 이전)

links 형식이 여전히 `'13'` (배지 숫자) 상태.

| 실행 | 결과 | 경로 | 스텝 수 |
|---|---|---|---|
| 44_bkp_4 | ✅ SUCCESS | LLM이 `goto /dashboard/todos` 선택 (학습 데이터 추론) | 2 |
| 44 | ✅ SUCCESS | `search` → 실패 → LLM이 스스로 `goto`로 전환 | 5 |

**관찰**: links에 "Todos"가 보이지 않아 LLM이 매번 다른 전략을 선택함 (비결정성 유지).

---

### Phase 2: page.evaluate() 링크 개선 후

links 형식이 `'To-Do List → /dashboard/todos'`로 변경. LLM이 링크를 인식하고 click 시도.

| 실행 | 결과 | 경로 | 스텝 수 |
|---|---|---|---|
| 44 (AX 시도) | ❌ FAILED | `page.accessibility` API 미지원 → CSS fallback → `'Assigned to you 3'` 클릭 5번 반복 | 5 |
| 44 (evaluate 적용) | ❌ FAILED | `'Assigned to you 3'` 클릭 5번 반복 (디버그 로그 확인용 실행) | 5 |
| 44 (피드백 추가 후) | ✅ SUCCESS | click 'To-Do List' element not found → LLM이 피드백 확인 → `goto /dashboard/todos` | 3 |

**관찰**:
- `page.accessibility`가 제거된 Playwright 버전 → `page.evaluate()` JS로 대체
- click element not found 피드백 덕분에 LLM이 스스로 `goto`로 전환해 회복
- 그러나 click 자체는 여전히 실패 (`try_click_target`의 innerText="5" 매칭 실패 + `get_by_role` 미적용 상태)

---

### Phase 3: get_by_role 적용 후 (최종)

LLM executor의 click이 `page.get_by_role(role, name=target)`으로 교체됨.

| 실행 | 결과 | 경로 | 스텝 수 |
|---|---|---|---|
| 44 (최종) | ✅ SUCCESS | `click 'To-Do List'` → `get_by_role` 성공 → 즉시 이동 → `done` | 2 |

---

## 최종 실행 트레이스 (Phase 3)

```
[21:28:13] step=1  url=http://localhost:8023/
[21:28:13] step=1  links=[..., 'To-Do List → /dashboard/todos', ...]
[21:28:15] step=1  action=click  reasoning='The Todos page link is visible in the navigation menu'
[21:28:15] click  target='To-Do List'
[21:28:16] step=1  result=click 'To-Do List': navigated to http://localhost:8023/dashboard/todos
[21:28:16] step=2  url=http://localhost:8023/dashboard/todos
[21:28:16] step=2  action=done  reasoning='The todos page is already open, so the task is complete.'
[21:28:16] done → SUCCESS
```

**총 소요 시간**: ~9초 (로그인 포함 21초, LLM 응답 2회)

---

## 관측 레이어 타이밍 분석

타임스탬프 로그로 병목 위치 확인:

| 단계 | 소요 시간 | 비고 |
|---|---|---|
| observe_page() | < 1초 | evaluate_all + asyncio.gather 적용 후 |
| LLM API 응답 | ~1-2초 | 스텝당 고정 비용 |
| 브라우저 액션 | < 1초 | get_by_role.click() |

→ 현재 병목은 순수하게 LLM API 왕복. `observe_page()` 최적화로 DOM 관련 병목 제거 완료.

---

## Phase 3 반복 실험 결과 (5회)

| 실행 | 결과 | step 1 액션 | 스텝 수 |
|---|---|---|---|
| 44_bkp_1 | ✅ SUCCESS | click 'To-Do List' → navigated | 2 |
| 44_bkp_2 | ✅ SUCCESS | click 'To-Do List' → navigated | 2 |
| 44_bkp_3 | ✅ SUCCESS | click 'To-Do List' → navigated | 2 |
| 44_bkp_4 | ✅ SUCCESS | click 'To-Do List' → navigated | 2 |
| 44 | ✅ SUCCESS | click 'To-Do List' → navigated | 2 |

**성공률: 5/5 (100%)** — LLM이 5회 모두 동일한 전략 선택. 비결정성 제거 확인.

---

## 개선 전후 비교

| 지표 | 001 (개선 전) | 002 Phase 3 (개선 후) |
|---|---|---|
| 성공률 | 30% (3/10) | **100% (5/5)** |
| 평균 스텝 수 | 4-5 (성공 시) | **2** |
| 성공 경로 | URL 직접 추측 (goto) | 링크 클릭 (semantic 매칭) |
| 실패 회복 | 없음 (반복 후 소진) | 피드백 → 전략 전환 |
| LLM 전략 비결정성 | 높음 (goto/search/click 혼재) | **없음 (5회 동일 경로)** |

---

## 구조적 변화 요약

### 001의 실패 원인 → 해결 방식

| 실패 원인 | 해결 |
|---|---|
| "Todos" nav 아이콘이 links에 `'13'`으로만 보임 | `page.evaluate()`로 aria-label+pathname 추출 → `'To-Do List → /dashboard/todos'` |
| LLM이 목표 도달해도 SUCCESS 선언 불가 | `done` 액션 추가 |
| click이 element not found여도 LLM이 모름 | 액션 결과 피드백 → 다음 스텝 메시지에 포함 |
| `get_by_role` 미사용으로 aria-label 클릭 실패 | LLM executor 경로에 `get_by_role` 적용 |

---

## 잔존 문제 및 다음 액션

1. **다른 task 확장**: task 44(NAVIGATE)만 검증됨. RETRIEVE, MUTATE task 실험 필요.
2. **Prior 미적용**: 현재 모든 성과는 prior 없는 LLM 일반 추론 + 관측 품질 개선으로 달성. Prior 추가 시 얼마나 더 안정화되는지 측정 예정.
3. ~~**성공률 측정 미완료**~~: 5/5 확인 완료.
4. ~~**LLM 비결정성**~~: 5회 동일 전략 선택으로 사실상 해소됨.
