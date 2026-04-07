# Lab Report 008 — Baseline 안정성 재측정 (Prior 도입 전)

**날짜**: 2026-04-07  
**목적**: 003~007에서 누적된 baseline 개선 후 전체 13개 task의 안정성 재측정. Prior 도입 전 baseline의 현재 수준 확정.

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
| 45 | NAVIGATE | Open issues for current project | FAIL | FAIL | FAIL | regression (0/3) |
| 339 | NAVIGATE | Open bug issues for current project | PASS | FAIL | PASS | 불안정 (2/3) |
| 132 | RETRIEVE | Commits by kilian on March 5, 2023 | PASS | PASS | PASS | 안정 (3/3) |
| 205 | RETRIEVE | Commits by kilian on March 5, 2023 (current) | PASS | PASS | PASS | 안정 (3/3) |
| 293 | RETRIEVE | SSH clone URL for Super_Awesome_Robot | FAIL | FAIL | FAIL | regression (0/3) |
| 169 | RETRIEVE | Project ID of most starred personal project | FAIL | FAIL | FAIL | regression (0/3) |
| 390 | MUTATE | Post "lgtm" on semantic HTML MR | FAIL | FAIL | FAIL | regression (0/3) |
| 258 | NAVIGATE | Open public projects listing | FAIL | FAIL | FAIL | 기대 (prior 필요) |
| 102 | NAVIGATE | Open help wanted issues | FAIL | FAIL | FAIL | 기대 (벤치마크 오류) |
| 308 | RETRIEVE | Username with most commits | FAIL | FAIL | FAIL | 기대 (prior/벤치마크) |

### 요약

| 분류 | Task 수 | Tasks |
|---|---|---|
| 안정 성공 (3/3) | 5 | 44, 156, 357, 132, 205 |
| 불안정 (2/3) | 1 | 339 |
| Regression (이전 성공 → 0/3) | 4 | 45, 293, 169, 390 |
| 기대 실패 (prior/벤치마크) | 3 | 258, 102, 308 |

**안정 성공률: 5/13 (38.5%)**  
**1회 이상 성공: 6/13 (46.2%)**

---

## Regression 분석 (다음 액션)

이전에 1회 이상 성공했던 task 중 4개가 3/3 실패로 regression:

| Task | 이전 성공 시점 | 가능한 원인 |
|---|---|---|
| 45 | 004에서 URL 힌트로 해결 | 이후 프롬프트/실행 레이어 변경으로 regression |
| 293 | 007에서 readonly 관측 + CSS fallback으로 해결 | 검색 경로 비결정성 + 이후 변경 영향 |
| 169 | 이번 세션에서 Planning + extract 검증으로 해결 | 비결정성 또는 최근 커밋 영향 |
| 390 | 이번 재측정 직전 1회 성공 | 비결정성 높음 |

원인 후보:
1. **프롬프트 누적 변경**: 여러 차례 프롬프트를 수정하면서 이전에 작동하던 LLM 행동 패턴이 깨졌을 가능성
2. **실행 레이어 변경 영향**: CSS fallback, fill 리다이렉트 등 후속 수정이 이전 성공 경로에 영향
3. **LLM 비결정성**: 같은 코드라도 LLM 응답이 달라져서 실패하는 경우

---

## 누적 개선 사항 (003 → 008)

### 관측 레이어
- aria-label + pathname 조합 링크 추출
- Visibility 필터 (숨겨진 드롭다운 항목 제거)
- 드롭다운 옵션 별도 분리 (`dropdown_options`)
- readonly input value 수집
- 클릭 실패 시 확장 관측 (추가 links/buttons 피드백)
- 검색 필드 `:visible` 체크 + selector 우선순위 조정

### 실행 레이어
- URL 힌트 기반 동명 링크 disambiguation
- 드롭다운 CSS locator 클릭 (get_by_role 대신)
- CSS locator fallback (get_by_role 전체 실패 시)
- 필터 검색 버튼 자동 제출 (done 시)
- SPA reload (HAR GET 요청 보장)
- 클릭 후 1초 대기 (비동기 렌더링)
- LLM 응답 파싱 실패 재시도
- NAVIGATE not_found → 다음 goal 전환 또는 SUCCESS

### Planning 레이어 (신규)
- build_plan()으로 task → 2~5개 sub-goal 분해
- 매 스텝 sub-goal 컨텍스트 제공
- premature done 방지 (남은 goal 있으면 전환)
- goal_complete 액션 성공 시만 인정
- extract misuse 방어

### 프롬프트
- click target에 URL이 아닌 이름만 사용
- extract에 "exact answer only" + 형식 검증
- reasoning 간결화
- done 검증 지침
- Plan에 특정 필드(ID, URL) 방문 유도

---

## 다음 액션

1. **Regression 원인 파악**: 45, 293, 169, 390의 실패 로그 분석 → 수정
2. **339 안정화**: 2/3 → 3/3으로 안정화
3. **Prior 도입**: 안정화 후 258을 첫 대상으로 Prior 효과 측정
