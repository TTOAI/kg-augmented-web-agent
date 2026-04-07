# Lab Report 002 — Baseline 안정성 재측정 (Prior 도입 전)

**날짜**: 2026-04-07  
**목적**: 001에서 누적된 baseline 개선 후 전체 13개 task의 안정성 재측정. Prior 도입 전 baseline의 현재 수준 확정.

---

## 재측정 조건

| 항목 | 값 |
|---|---|
| Site | GitLab (`http://localhost:8023`) |
| Task 수 | 13개 (NAVIGATE 6, RETRIEVE 5, MUTATE 1, 벤치마크 오류 1) |
| 반복 횟수 | 3회/task |
| LLM | GPT-5.4-mini (OpenAI API) |
| max_steps | 15 |

---

## 재측정 결과

| Task | Type | Intent (요약) | Run1 | Run2 | Run3 | 안정성 |
|---|---|---|---|---|---|---|
| 44 | NAVIGATE | Open my todos page | PASS | PASS | PASS | 안정 (3/3) |
| 156 | NAVIGATE | Merge requests assigned to me | PASS | PASS | PASS | 안정 (3/3) |
| 357 | NAVIGATE | Merge requests requiring my review | PASS | PASS | PASS | 안정 (3/3) |
| 45 | NAVIGATE | Open issues for current project | FAIL | FAIL | FAIL | 성능 저하 (0/3) |
| 339 | NAVIGATE | Open bug issues for current project | PASS | FAIL | PASS | 불안정 (2/3) |
| 132 | RETRIEVE | Commits by kilian on March 5, 2023 | PASS | PASS | PASS | 안정 (3/3) |
| 205 | RETRIEVE | Commits by kilian on March 5, 2023 (current) | PASS | PASS | PASS | 안정 (3/3) |
| 293 | RETRIEVE | SSH clone URL for Super_Awesome_Robot | FAIL | FAIL | FAIL | 성능 저하 (0/3) |
| 169 | RETRIEVE | Project ID of most starred personal project | FAIL | FAIL | FAIL | 성능 저하 (0/3) |
| 390 | MUTATE | Post "lgtm" on semantic HTML MR | FAIL | FAIL | FAIL | 성능 저하 (0/3) |
| 258 | NAVIGATE | Open public projects listing | FAIL | FAIL | FAIL | 기대 실패 (사전 지식 필요) |
| 102 | NAVIGATE | Open help wanted issues | FAIL | FAIL | FAIL | 기대 실패 (벤치마크 오류) |
| 308 | RETRIEVE | Username with most commits | FAIL | FAIL | FAIL | 기대 실패 (사전 지식/벤치마크) |

### 요약

| 분류 | Task 수 | Tasks |
|---|---|---|
| 안정 성공 (3/3) | 5 | 44, 156, 357, 132, 205 |
| 불안정 (2/3) | 1 | 339 |
| 성능 저하 (이전 성공 → 0/3) | 4 | 45, 293, 169, 390 |
| 기대 실패 (사전 지식/벤치마크) | 3 | 258, 102, 308 |

**안정 성공률: 5/13 (38.5%)**  
**1회 이상 성공: 6/13 (46.2%)**

---

## 성능 저하 분석

이전에 1회 이상 성공했던 task 중 4개가 3/3 실패:

| Task | 이전 성공 시점 | 가능한 원인 |
|---|---|---|
| 45 | Phase 4에서 URL 힌트로 해결 | 이후 프롬프트/실행 변경으로 이전 성공 경로 깨짐 |
| 293 | Phase 7에서 읽기전용 관측으로 해결 | 검색 경로의 비결정성 + 이후 변경 영향 |
| 169 | Planning + 데이터 추출 검증으로 해결 | LLM 비결정성 또는 최근 변경 영향 |
| 390 | 재측정 직전 1회 성공 | LLM 비결정성 높음 |

원인 후보:
1. **프롬프트 누적 변경**: 여러 차례 수정하면서 이전에 작동하던 LLM 행동 패턴이 깨짐
2. **태스크별 특수 로직 간섭**: 한 태스크를 위한 수정이 다른 태스크의 성공 경로에 영향
3. **LLM 비결정성**: 같은 코드라도 LLM 응답이 달라져서 실패

---

## 누적 개선 사항 (001 baseline 개발 과정)

### 관측 레이어
- 아이콘 링크의 aria-label + 경로 조합 추출
- 보이는 요소만 수집하는 필터 (숨겨진 드롭다운 항목 제거)
- 드롭다운 옵션을 링크와 별도로 분리 수집
- 읽기전용 입력 필드의 값 수집
- 클릭 실패 시 추가 링크/버튼 정보 피드백
- 검색 필드 보임 여부 체크

### 실행 레이어
- URL 경로 힌트로 같은 이름의 링크 구분
- 드롭다운 항목을 전용 CSS 선택자로 클릭
- 역할 기반 클릭 전체 실패 시 CSS 선택자로 대체 시도
- 필터 검색 버튼 자동 제출
- SPA 방식 URL 변경 후 페이지 리로드 (네트워크 기록 보장)
- LLM 응답 파싱 실패 시 1회 재시도

### Planning 레이어 (신규)
- 태스크를 2~5개 단계별 목표(sub-goal)로 분해
- 매 스텝마다 현재 목표 컨텍스트 제공
- 준비 안 된 상태에서 완료 선언하는 것을 방지
- 데이터 추출의 잘못된 사용 방어

### 프롬프트
- 클릭 대상에 URL이 아닌 표시 이름만 사용
- 데이터 추출 시 정확한 값만 반환하도록 안내
- 추론(reasoning) 간결화

---

## 다음 액션

1. **성능 저하 원인 파악**: 45, 293, 169, 390의 실패 로그 분석 → 수정
2. **339 안정화**: 2/3 → 3/3으로 안정화
3. **Prior 도입**: 안정화 후 258을 첫 대상으로 사전 지식(Prior) 효과 측정
