# Lab Report 004 — Task 45·357: 동명 링크 Disambiguation 및 파싱 안정성

**날짜**: 2026-04-07  
**목적**: Task 45의 동명 링크 문제 해결, Task 357 드롭다운 패턴 재확인, LLM 응답 파싱 실패 방어.

---

## 003 대비 변경 사항 요약

### 프롬프트 개선

| 개선 | 내용 |
|---|---|
| Click URL 힌트 | click 액션에 `url` 필드 안내 추가 → 동명 링크 구분 시 pathname 지정 가능 |
| Reasoning 간결화 | "Keep reasoning to 1-2 sentences" 추가 → 응답 토큰 초과 방지 |

### 실행 레이어 개선

| 개선 | 내용 |
|---|---|
| URL 힌트 매칭 | click 실행 시 `url` 필드가 있고 매칭 요소가 2개 이상이면 href로 필터링 |
| 파싱 실패 재시도 | `parse_llm_action()` 실패 시 LLM에 1회 재요청 |

---

## Task 357: 드롭다운 패턴 재확인

### 실험 조건

| 항목 | 값 |
|---|---|
| Task ID | 357 |
| Intent | "Go to the merge requests requiring my review" |
| Site | GitLab (`http://localhost:8023`) |
| Task Type | NAVIGATE |

### 실행 트레이스

```
step=1  click 'Merge requests' → page content changed (드롭다운 열림)
step=2  click 'Review requests for you 5' → navigated to /dashboard/merge_requests?reviewer_username=byteblaze
step=3  done → SUCCESS
```

**Eval: PASS** — Task 156과 동일한 드롭다운 패턴. visibility 필터 + DOM 변경 감지가 안정적으로 동작.

---

## Task 45: 동명 링크 문제

### 실험 조건

| 항목 | 값 |
|---|---|
| Task ID | 45 |
| Intent | "Open the issues page for the current project filtered to the most recent open issues" |
| Site | GitLab (`http://localhost:8023`) |
| Start URL | `http://localhost:8023/a11yproject/a11yproject.com` |
| Task Type | NAVIGATE |

### 문제 분석

links에 "Issues"가 두 개 존재:
- `Issues → /dashboard/issues` (글로벌 nav)
- `Issues → /a11yproject/a11yproject.com/-/issues` (프로젝트 sidebar)

`get_by_role("link", name="Issues")`가 DOM 순서상 글로벌 nav를 먼저 매칭 → 잘못된 페이지로 이동.

### 수정 전 실행 결과 (6회)

| 실행 | 결과 | step 1 | 회복 방법 | 스텝 수 |
|---|---|---|---|---|
| 45_bkp_5 | FAIL | Issues → 글로벌 대시보드 | goto 시도했으나 스텝 소진 | 5 |
| 45_bkp_4 | PASS | Issues → 글로벌 대시보드 | goto 회복 | 5 |
| 45_bkp_3 | FAIL | Issues → 글로벌 대시보드 | goto → fill/click 필터 시도 실패 | 5 |
| 45_bkp_2 | FAIL | Issues → 글로벌 대시보드 | 개별 issue 열고 루프 | 5 |
| 45_bkp_1 | PASS | Issues → 글로벌 대시보드 | goto 회복 | 4 |
| 45 | PASS | Issues → 글로벌 대시보드 | goto 회복 | 3 |

**성공률: 3/6 (50%)** — 6회 모두 step 1 실패, 성공은 전부 goto 회복 의존.

### 수정 후 실행 트레이스

```
step=1  click 'Issues'  url_hint='/a11yproject/a11yproject.com/-/issues'
step=1  result=click 'Issues': navigated to /a11yproject/a11yproject.com/-/issues  ← URL 힌트로 프로젝트 Issues 직접 매칭
step=2  done → SUCCESS
```

**Eval: PASS** — step 1에서 프로젝트 Issues로 바로 이동. 2스텝 완료.

### 수정 효과

| 지표 | 수정 전 | 수정 후 |
|---|---|---|
| step 1 정확도 | 0/6 (0%) | 1/1 (100%) |
| 성공률 | 3/6 (50%) | 1/1 (100%) |
| 평균 스텝 수 (성공 시) | 4.0 | **2** |
| 회복 방법 | goto 추측 | 불필요 |

---

## LLM 응답 파싱 실패 분석

### 발생 상황

Task 156 regression 확인 중 1회 발생:

```
step=1  action=not_found  reasoning='LLM 응답 파싱 실패: {"reasoning":"The dashboard shows a visible link to the Merge requests page in the top navigation. T'
```

LLM 응답이 `max_tokens=1024` 한도에서 잘려 JSON이 불완전하게 끝남 → `json.loads()` 실패 → `not_found` 폴백 → 즉시 FAIL.

### 수정

1. **예방**: 프롬프트에 "Keep reasoning to 1-2 sentences" 추가 → 응답 길이 제어
2. **방어**: 파싱 실패 시 LLM에 "Your response was truncated. Reply with valid JSON only." 재요청 1회

---

## Regression 확인

| Task | 결과 |
|---|---|
| 44 | SUCCESS |
| 156 | SUCCESS (1회 파싱 실패 → 재실행 시 정상) |
| 357 | SUCCESS |
| 45 | SUCCESS |

---

## 변경 파일 요약

| 파일 | 변경 |
|---|---|
| `runtime/llm.py` | click URL 힌트 안내, reasoning 간결화 지침 |
| `runtime/executor.py` | click URL 힌트 매칭 로직, 파싱 실패 재시도 |
| `tests/fixtures.py` | `FakeRoleLocator.nth()`, `FakeRoleLocatorSingle.get_attribute()` 추가 |

---

## 누적 성과 (001 → 004)

| Task | 001 baseline | 004 현재 | 비고 |
|---|---|---|---|
| 44 | 30% (3/10) | **100%** | 관측 + 실행 개선 |
| 156 | - | **SUCCESS** | visibility 필터 + DOM 변경 감지 |
| 357 | - | **SUCCESS** | 156과 동일 드롭다운 패턴 |
| 45 | - | **SUCCESS (50%→100%)** | URL 힌트 disambiguation |
| 258 | - | **FAIL (prior 필요)** | visibility_level=20 사이트 지식 필요 |

---

## 잔존 문제 및 다음 액션

1. **Task 258**: prior 필요 문제로 분류 완료. prior store 구현 후 재실험.
2. **URL 힌트 안정성**: task 45에서 1회만 확인. 추가 반복 실험 필요.
3. **다음 task 실험**: 339, 102, 259, 132 등 진행.
