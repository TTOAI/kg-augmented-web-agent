# Lab Report 005 — Planning 레이어 도입 및 필터 UI 상호작용

**날짜**: 2026-04-07  
**목적**: premature done 방지를 위한 Planning 레이어 구현, 필터 UI 클릭 기반 상호작용 시도, 전체 task 배치 실험.

---

## 004 대비 변경 사항 요약

### Planning 레이어 (신규)

| 개선 | 내용 |
|---|---|
| `build_plan()` | 실행 전 LLM 1회 호출로 task를 2~5개 sub-goal로 분해 |
| sub-goal 컨텍스트 | 매 스텝 `build_action_request()`에 plan 상태 ([done]/[current]/[ ]) 포함 |
| `goal_complete` | LLM 응답에 선택적 필드, 액션 성공 시에만 sub-goal 전환 |
| premature done 방지 | done 액션 + 남은 sub-goal → done 무시하고 다음 goal로 전환 |

### 관측 레이어 개선

| 개선 | 내용 |
|---|---|
| 드롭다운 항목 수집 | `extract_ax_links()` selector에 `.dropdown-item`, `[role="option"]`, `[role="menuitem"]` 추가 |

### 프롬프트 개선

| 개선 | 내용 |
|---|---|
| click target 명확화 | "set target to the visible name only (NOT the URL)" 명시 |
| 필터 UI 가이드 | "never use fill on filter inputs — click first to explore options" |
| reasoning 간결화 | "Keep reasoning to 1-2 sentences" |
| max_steps | 5 → 15로 증가 |

---

## 전체 task 배치 실험 결과 (Planning 도입 전)

### 이전 성공 task (004 기준)

| Task | Intent | Type | 결과 |
|---|---|---|---|
| 44 | Open my todos page | NAVIGATE | **PASS** |
| 156 | Go to merge requests assigned to me | NAVIGATE | **PASS** |
| 357 | Go to merge requests requiring my review | NAVIGATE | **PASS** |
| 45 | Open issues page for current project | NAVIGATE | **PASS** |

### 신규 8개 task (각 3회 실행, 모두 FAIL)

| Task | Intent | Type | 실패 유형 |
|---|---|---|---|
| 102 | Open issues with "help wanted" label | NAVIGATE | 필터 URL params 미반영 (fill) |
| 339 | Open bug issues for current project | NAVIGATE | 필터 URL params 미반영 (fill) |
| 259 | Get RSS feed token | RETRIEVE | 토큰 값 추출 실패 (reveal 필요) |
| 132 | Commits by kilian on March 5, 2023 | RETRIEVE | 값 형식 불일치 |
| 205 | Commits by kilian on March 5, 2023 | RETRIEVE | 값 형식 불일치 |
| 293 | SSH clone URL for Super_Awesome_Robot | RETRIEVE | 프로젝트 검색 실패 → 스텝 소진 |
| 308 | Username with most commits | RETRIEVE | display name vs username 혼동 |
| 169 | Project ID of most starred project | RETRIEVE | 프로젝트 이름 vs ID 혼동 |
| 390 | Post "lgtm" on semantic HTML MR | MUTATE | MR 클릭 실패 → 스텝 소진 |

### 실패 유형 분류

| 유형 | Tasks | 설명 |
|---|---|---|
| 필터 URL 미반영 | 102, 339 | fill로 텍스트 입력 → query params 안 붙음 |
| 값 추출 정밀도 | 132, 205, 308, 169 | 페이지 도달 OK, 추출 값이 기대와 불일치 |
| 숨겨진 UI 접근 | 259 | reveal 버튼 클릭 필요 |
| 탐색/상호작용 실패 | 293, 390 | 검색/클릭 실패로 스텝 소진 |

---

## Planning 레이어 동작 확인 (Task 339)

### Plan 생성 결과

```
plan=['Open the project's issues list.',
      'Filter the issues to show only open issues.',
      'Filter the issues to show only bug reports.',
      'Confirm the list contains only open bug issues for this project.']
```

### 실행 트레이스

```
step=1  goal=1/4  click 'Issues' → navigated to /-/issues  ← goal 1 complete ✓
step=2  goal=2/4  done → ignored, advancing to goal 3  ← premature done 방지 ✓
step=3  goal=3/4  fill 'search or filter...' value='label:bug' → submitted
step=4  goal=3/4  fill 반복...
step=5  goal=4/4  fill 반복...
step=6  goal=4/4  extract → 실패
```

### Planning 효과

| 지표 | Planning 없을 때 | Planning 있을 때 |
|---|---|---|
| Issues 페이지 도달 | step 1에서 성공 | step 1에서 성공 |
| premature done | step 2에서 바로 done | **done 무시 → 다음 goal로 전환** |
| 필터 시도 | 안 함 (바로 done) | **fill로 시도 (3회)** |
| 최종 결과 | FAIL (premature done) | FAIL (fill이 URL params 미반영) |

**Planning은 premature done 문제를 해결했으나, fill vs click 문제가 남아있음.**

---

## 잔존 문제: fill vs click 필터

LLM이 프롬프트의 "never use fill on filter inputs" 지침을 무시하고 fill을 선호함.

### 원인 분석

1. LLM은 `search or filter results...` 입력 필드를 보면 텍스트 입력이 자연스러움
2. 드롭다운 옵션(Label, Author 등)은 **검색창을 click한 후에만** 관측에 나타남
3. LLM이 click 대신 fill을 선택하므로 드롭다운을 볼 기회가 없음 (catch-22)

### 관측 확인

검색창 클릭 후 `.dropdown-item` 요소가 관측에 보이는 것은 확인됨:
```
Assignee → /.../-/issues
Author → /.../-/issues
Label → /.../-/issues
Milestone → /.../-/issues
Type → /.../-/issues
```

### 다음 시도 방향

- 실행 레이어에서 fill 대신 click을 강제하는 로직
- 또는 fill 실행 시 먼저 click으로 드롭다운을 열고, 드롭다운이 열리면 fill을 취소

---

## 변경 파일 요약

| 파일 | 변경 |
|---|---|
| `runtime/llm.py` | `build_plan()` 추가, `build_action_request()`에 sub_goals/current_goal_index 인자, click target 명확화, 필터 UI 가이드, reasoning 간결화 |
| `runtime/executor.py` | plan 생성 호출, sub-goal 추적, goal_complete 처리 (액션 성공 시만), done + 남은 goals → 전환, max_steps 15, 파싱 실패 재시도, import build_plan |
| `runtime/browser.py` | `extract_ax_links()` selector에 `.dropdown-item`, `[role="option"]`, `[role="menuitem"]` 추가 |
| `tests/fixtures.py` | `FakeRoleLocator.nth()`, `FakeRoleLocatorSingle.get_attribute()` |
| `tests/test_runtime_llm.py` | 모든 LLM executor 테스트에 plan 응답 추가 |

---

## 누적 성과 (001 → 005)

| Task | 001 | 004 | 005 | 비고 |
|---|---|---|---|---|
| 44 | 30% | 100% | 100% | |
| 156 | - | SUCCESS | SUCCESS | |
| 357 | - | SUCCESS | SUCCESS | |
| 45 | - | 50%→100% | 100% | URL 힌트 |
| 258 | - | FAIL | FAIL | prior 필요 |
| 339 | - | FAIL | FAIL (개선) | Planning으로 premature done 해결, fill 문제 잔존 |
| 102 | - | FAIL | FAIL | 339와 동일 유형 |
