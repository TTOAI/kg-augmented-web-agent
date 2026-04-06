# Lab Report 007 — Task 293: 검색 효율화, CSS click fallback, readonly input 관측

**날짜**: 2026-04-07  
**목적**: Task 293 (SSH clone URL 추출) 해결. 검색 필드 visibility 문제, get_by_role 매칭 실패, readonly input 관측 부재 등 복합 문제 분석 및 수정.

---

## 006 대비 변경 사항 요약

### 관측 레이어

| 개선 | 내용 |
|---|---|
| readonly input 수집 | `extract_readonly_values()`로 `input[readonly]`의 value 수집 (Clone URL 등) |
| 확장 관측 | click element not found 시 추가 links/buttons를 피드백에 포함 |

### 실행 레이어

| 개선 | 내용 |
|---|---|
| CSS click fallback | get_by_role 전체 실패 시 CSS locator(`a`, `button`, `[role='tab']` 등)로 innerText partial 매칭 |
| 검색 visibility | `try_search()`에 `:visible` 추가로 숨겨진 검색 필드 매칭 방지 |
| selector 우선순위 | `SEARCH_INPUT_SELECTORS`에서 `placeholder` 기반을 `type` 기반보다 우선 |
| fill 리다이렉트 정밀화 | "search or filter" 구체적 패턴만 대상 (일반 "filter by name" 제외) |

### 기타

| 개선 | 내용 |
|---|---|
| extract label 분리 | `retrieved_data`에서 label 제거, value만 반환 |
| extract misuse 방어 | "extract는 최종 답변에만 사용" 프롬프트 |
| human agent 입력 | task_type/retrieved_data 터미널 입력 지원 |

---

## Task 293 문제 분석

### 실험 조건

| 항목 | 값 |
|---|---|
| Task ID | 293 |
| Intent | "Get the URL to clone Super_Awesome_Robot with SSH. Return the URL only." |
| Site | GitLab (`http://localhost:8023`) |
| Task Type | RETRIEVE |
| 정답 | `git@localhost:convexegg/super_awesome_robot.git` |

### 문제 1: 프로젝트 검색 비효율 (13스텝 소진)

**원인**: `try_search()`가 숨겨진 `input[type='search']` (대시보드 프로젝트 필터)를 먼저 매칭 → fill 실패 → search 액션 반복 실패.

**해결**: `:visible` pseudo-selector 추가 + `SEARCH_INPUT_SELECTORS` 우선순위 조정.

### 문제 2: Clone 드롭다운 접근 불가

**원인**: Clone 버튼이 links/buttons 제한에 잘려서 관측에 안 보임 → LLM이 Clone 클릭 불가.

**해결**: click element not found 시 확장 관측(추가 links/buttons)을 피드백에 포함. CSS click fallback으로 `get_by_role` 실패 시에도 클릭 가능.

### 문제 3: SSH URL이 관측에 없음

**원인**: SSH clone URL이 `input[readonly]`의 value에 있는데, 기존 관측이 input value를 수집하지 않음.

**해결**: `extract_readonly_values()`로 보이는 readonly input의 `aria-label: value` 수집 → text_lines에 포함.

### 문제 4: SSH 경고에 속음

**원인**: "You can't push or pull using SSH until you add an SSH key" 경고를 보고 PERMISSION_DENIED 선언. 실제로는 Clone 드롭다운에 SSH URL이 존재.

**해결**: Clone 클릭 성공 + readonly value 관측으로 SSH URL이 보이면 LLM이 정상 extract.

### 문제 5: "Open 40" 탭 클릭 실패 (339 regression)

**원인**: `role="tab"`의 accessible name이 `"Open"`인데, 관측에서는 `"Open 40"` (배지 숫자 포함). `get_by_role("tab", name="Open 40")` → 매칭 실패.

**해결**: CSS click fallback으로 `[role='tab']:visible`에서 innerText partial 매칭.

### 문제 6: fill 리다이렉트 무한루프 (293 regression)

**원인**: `Filter by name` input의 placeholder에 "filter" 포함 → fill→click 리다이렉트 반복.

**해결**: 리다이렉트 조건을 `"search or filter"`로 구체화. 일반 `"filter by name"`은 통과.

### Human Agent 검증

수동 조작으로 정답 경로 확인:
1. 프로젝트 검색 → Super_Awesome_Robot 페이지 도달
2. Clone 드롭다운 열기 → "Clone with SSH" 섹션에서 URL 확인
3. `git@localhost:convexegg/super_awesome_robot.git` 추출
4. Eval: PASS

---

## 최종 실행 트레이스 (Task 293)

```
step=1   search 'Super_Awesome_Robot' → /?name=... (대시보드 필터, 결과 없음)
step=2   search 반복 → URL unchanged
step=3   goto /super_awesome_robot → 404
step=4   search → /search?search=super_awesome_robot ✓
step=5   click 'Convex Eggtart / Super_Awesome_Robot' → 프로젝트 도달 ✓
step=6   extract 시도 (SSH URL 아직 안 보임)
step=7   click 'Clone' via CSS fallback → page content changed ✓
step=8   extract 'git@localhost:convexegg/super_awesome_robot.git' ✓
```

**Eval: PASS** (1/3 안정성, 검색 경로 비결정성 잔존)

---

## 추가 해결: Task 132, 205

### 문제

extract value에 label이 포함되어 반환. eval은 값만 비교.
- 에이전트: `"Commits by Kilian Valkhof on 05 Mar, 2023: 1 commit"` 
- 정답: `1.0`

### 해결

`executor.py`에서 `retrieved_data`에 value만 포함 (label 제거).

### 결과

- 132: eval PASS ✓
- 205: eval PASS ✓

---

## 변경 파일 요약

| 파일 | 변경 |
|---|---|
| `runtime/browser.py` | `extract_readonly_values()` 신규, `try_search()` `:visible` 추가 |
| `runtime/executor.py` | CSS click fallback, 확장 관측, fill 리다이렉트 정밀화, extract label 분리 |
| `runtime/intent.py` | `SEARCH_INPUT_SELECTORS` 우선순위 조정 |
| `runtime/llm.py` | extract "exact answer only" 프롬프트, extract misuse 방어 |
| `benchmarks/.../adapter.py` | human agent task_type/retrieved_data 입력 |

---

## 누적 성과 (001 → 007)

| Task | Type | 005 | 007 | 비고 |
|---|---|---|---|---|
| 44 | NAVIGATE | PASS | PASS | |
| 156 | NAVIGATE | PASS | PASS | |
| 357 | NAVIGATE | PASS | PASS | |
| 45 | NAVIGATE | PASS | PASS | |
| 339 | NAVIGATE | FAIL | **PASS** | 필터 UI + CSS fallback |
| **132** | RETRIEVE | FAIL | **PASS** | extract label 분리 |
| **205** | RETRIEVE | FAIL | **PASS** | extract label 분리 |
| **293** | RETRIEVE | FAIL | **PASS** | 검색 + Clone + readonly 관측 |
| 258 | NAVIGATE | FAIL | FAIL | prior 필요 |
| 102 | NAVIGATE | FAIL | 미재실험 | 잘못된 프로젝트 선택 |
| 308 | RETRIEVE | FAIL | 미재실험 | display name vs username |
| 169 | RETRIEVE | FAIL | 미재실험 | 다단계 탐색 |
| 390 | MUTATE | FAIL | 미재실험 | 코멘트 POST |

**현재: 8/13 (62%)**
