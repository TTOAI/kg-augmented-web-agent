# Lab Report 006 — Task 339: 필터 UI 클릭 기반 상호작용 해결

**날짜**: 2026-04-07  
**목적**: Task 339 ("Go to the list of all opened issues that report bugs")의 필터 UI 상호작용 문제를 해결. 드롭다운 CSS locator 클릭, 검색 제출 자동화, SPA reload 등 복합 문제 분석 및 수정.

---

## 005 대비 변경 사항 요약

### 관측 레이어

| 개선 | 내용 |
|---|---|
| 드롭다운 분리 | `extract_dropdown_options()` 신규. `PageObservation.dropdown_options` 필드 추가 |
| LLM 관측 분리 | `Links`와 `Dropdown options (click to select)` 별도 섹션으로 LLM에 전달 |

### 실행 레이어

| 개선 | 내용 |
|---|---|
| CSS locator 클릭 | 드롭다운 열린 상태에서 `.dropdown-item` CSS locator로 클릭 (get_by_role 대신) |
| fill → click 리다이렉트 | 필터 입력에 fill 시 click으로 전환해서 드롭다운 강제 오픈 |
| 검색 자동 제출 | done 시 `button[aria-label='Search']` 자동 클릭 + URL 변화 대기 |
| SPA reload | done 시 `page.goto(page.url)`로 GET 요청 HAR 기록 보장 |
| 클릭 후 대기 | click 성공 후 1초 대기로 비동기 드롭다운 렌더링 보장 |

### Human Agent 모드

| 개선 | 내용 |
|---|---|
| `--human` 플래그 | `run_webarena_verified.py --human --headed`로 수동 브라우저 조작 후 eval 가능 |

### 코드 정리

| 정리 | 내용 |
|---|---|
| 프롬프트 사족 제거 | 효과 없던 필터 UI 지침 6줄 제거 (실행 레이어가 처리) |
| 불필요한 조건문 | `not action_succeeded` 중복 조건 제거 |

---

## 문제 분석 과정

### 1단계: LLM이 fill로 필터 입력

```
step=2  fill 'search or filter results...' value='label:bug state:opened' → submitted
```

**원인**: LLM이 필터 입력에 텍스트를 직접 타이핑. GitLab 필터 UI는 클릭 기반 드롭다운이라 URL query params가 반영되지 않음.

**해결**: fill → click 리다이렉트. 필터 입력 대상이면 `input[placeholder*='filter']`를 click해서 드롭다운 강제 오픈.

### 2단계: 드롭다운 항목이 관측에서 안 보임

드롭다운이 열려도 `links[:20]` 제한에 sidebar 링크가 대부분 차지 → `bug` 등 드롭다운 항목 누락.

**해결**: `extract_dropdown_options()` 분리. LLM에 `Dropdown options (click to select): [...]` 별도 섹션 제공.

### 3단계: 드롭다운 항목이 비동기 렌더링

`= is` 클릭 직후 observe_page() → label 값(bug 등) 아직 DOM에 없음. 2초 후에 나타남.

**해결**: click 성공 후 1초 대기 (`page.wait_for_timeout(1000)`) 추가.

### 4단계: get_by_role이 잘못된 navigation 발생

`get_by_role("link", name="bug")`로 `<a href="#">` 클릭 → href의 기본 navigation 발생 → `?label_name[]=bug`만 붙고 JS 이벤트 핸들러 미실행.

**해결**: 드롭다운 열린 상태에서는 CSS locator(`.dropdown-item`)로 클릭. JS 이벤트 정상 트리거 → 필터 토큰만 추가, navigation 없음.

### 5단계: 검색 제출 누락

CSS locator로 bug 선택 → 필터 토큰 추가되지만 URL 미변경. 수동 조작 시 **검색 버튼 클릭**이 필터를 제출하고 full URL(`?state=opened&label_name[]=bug`) 생성.

**해결**: done 시 `button[aria-label='Search']` 자동 클릭 + URL 변화 대기(최대 5초).

### 6단계: HAR에 GET 요청 없음

검색 버튼 클릭이 SPA 방식 (URL 변경 + GraphQL만, full page GET 없음) → eval의 NetworkEventEvaluator가 GET 요청 기대.

**해결**: done 시 `page.goto(page.url)` reload로 GET 요청 HAR 기록.

### Human Agent 검증

수동 조작으로 정답 경로 확인:
1. Issues 페이지 → 필터 입력 클릭 → Label → = → bug → 검색 버튼 클릭 → F5 새로고침
2. URL: `?sort=updated_desc&state=opened&label_name%5B%5D=bug&first_page_size=20`
3. Eval: 3/3 PASS

---

## 최종 실행 트레이스 (Task 339)

```
plan=['Open the project issues list.',
      'Apply the bug label filter.',
      'Show only issues with an open status.']

step=1  click 'Issues' url_hint='/.../-/issues' → navigated ✓
step=2  done (goal 1 complete) → advancing to goal 2
step=3  fill 'search or filter...' → [redirected to click] dropdown opened ✓
step=4  click 'Label' via CSS locator → page content changed ✓
step=5  click '= is' → page content changed ✓
step=6  click 'bug' via CSS locator → page content changed ✓ (no navigation!)
step=7  done → auto-submit search button → URL changed to ?state=opened&label_name[]=bug
        → reload → SUCCESS
```

**Eval: 3/3 PASS**

---

## 핵심 발견

| 발견 | 설명 |
|---|---|
| get_by_role vs CSS locator | `<a href="#">` 드롭다운 항목은 get_by_role 클릭 시 잘못된 navigation 발생. CSS locator로 클릭해야 JS 이벤트 정상 처리 |
| 필터 제출 필요 | 드롭다운에서 값 선택만으로는 부족. 검색 버튼 클릭으로 필터를 명시적으로 제출해야 URL params 생성 |
| SPA + HAR | SPA의 URL 변경은 GET 요청을 안 만듦. `page.goto(page.url)` reload로 HAR에 GET 기록 필요 |
| 비동기 렌더링 | 드롭다운 값 목록은 즉시 나타나지 않음. 클릭 후 대기 필요 |

---

## 변경 파일 요약

| 파일 | 변경 |
|---|---|
| `runtime/browser.py` | `extract_dropdown_options()` 신규, `observe_page()`에 dropdown_options 추가 |
| `runtime/executor.py` | CSS locator 클릭, fill→click 리다이렉트, 검색 자동 제출, SPA reload, 클릭 후 대기 |
| `runtime/llm.py` | Dropdown options 별도 섹션, 사족 프롬프트 제거 |
| `runtime/types.py` | `PageObservation.dropdown_options` 필드 |
| `tests/fixtures.py` | FakePage에 `_evaluate_dropdown`, `evaluate()` 인자 지원 |
| `benchmarks/.../runner.py` | `--human` 플래그 |
| `benchmarks/.../adapter.py` | `run_task_human()` 메서드 |

---

## 누적 성과 (001 → 006)

| Task | 001 | 005 | 006 | 비고 |
|---|---|---|---|---|
| 44 | 30% | 100% | 100% | |
| 156 | - | SUCCESS | SUCCESS | visibility 필터 + DOM 변경 감지 |
| 357 | - | SUCCESS | SUCCESS | 드롭다운 패턴 |
| 45 | - | 100% | 100% | URL 힌트 disambiguation |
| 258 | - | FAIL | FAIL | prior 필요 (visibility_level=20) |
| **339** | - | **FAIL** | **SUCCESS** | **필터 UI CSS locator + 검색 제출** |
| 102 | - | FAIL | 미실험 | 339와 동일 유형 (help wanted 필터) |
