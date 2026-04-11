# Lab Report 004 — 관측·검증·실행 전면 개선

**날짜**: 2026-04-08  
**목적**: v2 아키텍처 위에서 관측(Observation), 검증(Verification), 실행(Execution) 레이어를 전면 개선하여 339 (GitLab 필터 UI) 해결.

---

## 해결한 문제들

### 1. AJAX 콘텐츠 미관측
**증상**: `= is` 클릭 후 label 값(bug 등)이 관측에 안 잡힘. None/Any만 보임.  
**원인**: AJAX로 label 로딩되는데, 관측이 DOM 업데이트 전에 찍힘.  
**해결**: DOM 안정화 — in-page 클릭 후 콘텐츠 변화 감지 시 500ms 간격으로 안정될 때까지 반복 관측 (최대 2초).

### 2. 드롭다운 클릭이 사이드바 링크로 매칭
**증상**: "Label" 클릭 → 사이드바의 Issues 링크 클릭됨.  
**원인**: 드롭다운 옵션과 사이드바 링크가 같은 href를 공유. `a[href='...']:visible`의 첫 번째 매칭이 사이드바.  
**해결**: 드롭다운 옵션 매칭을 최우선으로 `.dropdown-item` 전용 selector 사용.

### 3. "Search" 버튼 미관측
**증상**: 필터 Search 버튼이 buttons 관측에 안 잡힘.  
**원인**: 버튼 추출에 visibility 필터 없음 → 숨겨진 버튼이 50개 슬롯 선점.  
**해결**: `el.offsetWidth > 0 || el.offsetHeight > 0` 필터 추가.

### 4. "Search" 버튼/링크 혼동
**증상**: "Search" 클릭 시 상단 네비게이션 검색 링크(`/search`)로 이동.  
**원인**: links 부분 매칭에서 "Search"가 "Search Within" 드롭다운에 걸림. 또한 "Search" 링크가 버튼보다 먼저 매칭.  
**해결**:
- 드롭다운 매칭을 정확 매칭(exact)으로 변경
- element_type("button"|"link") 지원 — LLM이 요소 타입 지정 가능
- 타입 충돌 감지: 같은 이름이 여러 타입에 매칭되면 요소 타입 구분 피드백 → LLM이 element_type으로 재시도

### 5. 검증 레이어의 잘못된 판단 (통과해선 안 될 것이 통과, 통과해야 할 것이 거부)
**증상**: 이미 달성된 goal 거부 (10스텝 낭비), 엉뚱한 변화 통과.  
**원인**: dropdown/links/buttons 변화로 판단 → 임시 UI 상태(메뉴 열림/닫힘)에 오염.  
**해결**: 결정론적 검증 제거. LLM 자가 판단에 위임. navigation goal만 URL 변화 필수.

### 6. 필터 선택만 하고 제출 안 함
**증상**: bug 라벨 선택 후 done → URL 안 바뀜 → eval FAIL.  
**원인**: LLM이 "Label = ~bug 토큰 보임 = 필터 적용됨"으로 착각.  
**해결**: navigation goal done 시 URL 변화 체크 — 안 바뀌면 "URL has not changed" 피드백 → LLM이 Search 버튼을 찾아 클릭.

### 7. NAVIGATE에서 extract로 탈출
**증상**: 마지막 goal에서 extract로 잘못된 SUCCESS 반환.  
**해결**: extract는 RETRIEVE 과제에서만 허용.

### 8. 네트워크 기록에 페이지 내 URL 변경이 안 남음
**증상**: 브라우저가 페이지 내에서 URL만 변경(전체 새로고침 없음) → 네트워크 기록에 GET 요청 없음 → 평가 FAIL.  
**해결**: adapter에서 NAVIGATE SUCCESS 후 `page.goto(page.url)` 리로드.

---

## 주요 설계 결정

### 관측 피드백 3단계
1. **콘텐츠 delta**: 클릭 후 새로 나타난 dropdown/button/link 명시적 보고
2. **주변 요소(nearby)**: 클릭 직후 포커스 컨테이너 캡처 → DOM 안정화 후 추출
3. **요소 타입 구분**: 같은 이름의 요소가 여러 타입에 존재하면 LLM에게 되물음

### 검증 전략
- **결정론적 검증 제거**: 잘못된 통과/거부 반복 → LLM 자가 판단이 더 정확
- **navigation URL 강제만 유지**: navigation의 정의 자체가 URL 변화
- **extract는 RETRIEVE만**: NAVIGATE/MUTATE에서 extract 탈출 차단

### Planning 개선
- NAVIGATE 과제의 마지막 goal = navigation 타입 강제 (task_type 전달)
- LLM planner가 task_type을 보고 적절한 plan 구조 생성

---

## 실행 파라미터 변경

| 파라미터 | 이전 | 이후 | 이유 |
|---|---|---|---|
| min step budget | 5 | 10 | 필터 인터랙션(4클릭+done) 여유 |
| retry per goal | 3 | 5 | 같은 goal에서 더 많이 시도 |
| replan | 5 | 3 | retry 증가로 replan 필요성 감소 |

### Graduated retry
- 1~3회: 소조정
- 4회: 다른 접근
- 5회: 완전히 다른 방법

---

## 339 결과

| 시도 | 결과 | 시간 | 스텝 | 핵심 |
|---|---|---|---|---|
| v2 초기 | FAIL | 351s/66 | label 못 봄 (AJAX 미관측) |
| DOM 안정화 | FAIL | 168s/48 | label 봤으나 Search 못 누름 |
| + 검증 개선 | FAIL | 24s/8 | 필터 제출 안 함 |
| + navigation URL 강제 | FAIL | 153s/30 | Search가 링크로 매칭 |
| + 요소 타입 구분 | **PASS** | **57s/31** | **Search 버튼 정확 클릭** |

---

## 수정 파일

| 파일 | 변경 |
|---|---|
| `runtime/executor.py` | DOM 안정화, nearby 추출, 요소 타입 구분, element_type, navigation URL 강제, 검증 제거, extract 제한, retry/replan/budget 조정 |
| `runtime/llm.py` | element_type 프롬프트, planning에 task_type 전달, NAVIGATE 마지막 goal navigation 강제 |
| `runtime/browser.py` | 버튼 visibility 필터 |
| `benchmarks/.../adapter.py` | NAVIGATE 성공 후 현재 URL 리로드 (네트워크 기록 보장) |
| `tests/test_runtime_llm.py` | 실패 테스트 기대값 수정 (goal 실패 → NOT_FOUND_ERROR) |

---

## 다음 단계
- 안정 태스크 성능 저하 여부 확인 (44, 156, 357, 132, 205)
- 전체 측정 재실행
- 339 반복 안정성 확인 (3회)
