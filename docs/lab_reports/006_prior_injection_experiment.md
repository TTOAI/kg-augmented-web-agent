# Lab Report 006 — Prior 주입 실험

**날짜**: 2026-04-10
**목적**: 가설 검증 — "사이트별 사전 지식(Prior)을 주입하면 baseline 대비 태스크 성공률이 올라가는가?"

---

## Baseline 측정 (Prior 없음)

3회 반복, 14 GitLab task, OpenAI gpt-4o.

| Task | Run 1 | Run 2 | Run 3 | 성공률 |
|---|---|---|---|---|
| 44 | PASS | PASS | PASS | 3/3 |
| 45 | PASS | FAIL | PASS | 2/3 |
| 102 | FAIL | FAIL | FAIL | 0/3 |
| 132 | FAIL | FAIL | PASS | 1/3 |
| 156 | PASS | PASS | PASS | 3/3 |
| 169 | FAIL | PASS | FAIL | 1/3 |
| 205 | FAIL | FAIL | PASS | 1/3 |
| 258 | FAIL | FAIL | FAIL | 0/3 |
| 259 | PASS | PASS | PASS | 3/3 |
| 293 | PASS | PASS | FAIL | 2/3 |
| 308 | FAIL | FAIL | FAIL | 0/3 |
| 339 | FAIL | FAIL | FAIL | 0/3 |
| 357 | PASS | PASS | PASS | 3/3 |
| 390 | PASS | PASS | FAIL | 2/3 |

**총 PASS: 21/42 (50.0%)**
안정 PASS (3/3): 44, 156, 259, 357 — 4개
안정 FAIL (0/3): 102, 258, 308, 339 — 4개

---

## Prior 구현

### 핵심 발견

Prior 인프라(types, schema, store, router, system prompt injection)는 **이미 전부 구현돼 있었으나**, `conn = sqlite3.connect(":memory:")`로 매번 빈 DB를 생성하여 Prior 데이터가 없는 상태로 실행됨. `page_type_id="unresolved"` 고정 → router가 항상 FALLBACK.

**코드 변경은 최소**, 데이터 채우기가 주력.

### 변경 사항

1. **seeds/gitlab.py**: SiteProfile(active, sufficient) + 9 PageTypes + 5 ActionSchemas 시딩
2. **agent/core.py**: GitLab일 때 자동 시딩 + URL→page_type 해결
3. **llm.py**: build_plan()에 prior_bundle 전달 → planning에 사이트 지식 활용
4. **executor.py**: build_plan 호출에 prior_bundle 전달
5. **goto tool**: Prior 있을 때만 활성화 (URL 추측 방지 원칙 유지)

### 주입되는 Prior 정보

System prompt에 `## Site Knowledge` 섹션으로 주입:
- 9개 PageType (dashboard, project_overview, issues_list, merge_requests, commits_list, contributors, explore_projects, user_projects, user_settings)
- 5개 ActionSchema (open_public_projects, filter_issues_by_label, view_contributors, view_commits, list_user_projects)

Planning prompt에도 Known pages + Available actions 주입.

---

## Prior 측정

3회 반복, 동일 14 GitLab task.

| Task | Run 1 | Run 2 | Run 3 | 성공률 |
|---|---|---|---|---|
| 44 | PASS | PASS | PASS | 3/3 |
| 45 | PASS | FAIL | FAIL | 1/3 |
| 102 | FAIL | FAIL | FAIL | 0/3 |
| 132 | PASS | FAIL | FAIL | 1/3 |
| 156 | PASS | PASS | PASS | 3/3 |
| 169 | PASS | FAIL | FAIL | 1/3 |
| 205 | FAIL | FAIL | FAIL | 0/3 |
| 258 | PASS | FAIL | FAIL | 1/3 |
| 259 | FAIL | PASS | PASS | 2/3 |
| 293 | PASS | PASS | PASS | 3/3 |
| 308 | FAIL | FAIL | PASS | 1/3 |
| 339 | FAIL | FAIL | PASS | 1/3 |
| 357 | PASS | PASS | PASS | 3/3 |
| 390 | FAIL | FAIL | FAIL | 0/3 |

**총 PASS: 20/42 (47.6%)**
안정 PASS (3/3): 44, 156, 293, 357 — 4개
안정 FAIL (0/3): 102, 205 — 2개

---

## 비교 분석

### 전체 성공률

| 지표 | Baseline | Prior | 차이 |
|---|---|---|---|
| 총 PASS | 21/42 (50.0%) | 20/42 (47.6%) | -2.4% |
| 안정 PASS (3/3) | 4개 | 4개 | 0 |
| 안정 FAIL (0/3) | 4개 | 2개 | **-2** |

전체 성공률은 거의 동일하지만, **안정 FAIL이 4→2로 감소**.

### Task별 변화

| Task | Baseline | Prior | 변화 | 분석 |
|---|---|---|---|---|
| 258 | 0/3 | **1/3** | ↑ | Prior의 `open_public_projects` ActionSchema. goto로 `/explore?visibility_level=20` 직접 이동. 단, LLM이 goto를 안 쓸 때 FAIL. |
| 308 | 0/3 | **1/3** | ↑ | Prior의 `view_contributors` ActionSchema. `/-/graphs` 경로 안내. |
| 339 | 0/3 | **1/3** | ↑ | Prior의 `filter_issues_by_label` ActionSchema + issues_list PageType description. |
| 293 | 2/3 | **3/3** | ↑ | Prior의 `project_overview` PageType이 네비게이션 안정화. |
| 259 | 3/3 | 2/3 | ↓ | 시스템 프롬프트 길어져서 역효과 가능. |
| 390 | 2/3 | 0/3 | ↓ | 동일 가능성. |

### Prior가 도움을 준 경우

258, 308: Prior에 명시된 **구체적 URL 경로**가 LLM의 네비게이션을 직접적으로 도왔다. 특히 258은 `visibility_level=20`이라는 사이트 특화 파라미터를 Prior 없이는 알 수 없었다.

339: Prior에 명시된 **필터 UI 조작 패턴**("click search input → click Label → select label → click Search")이 LLM의 행동 순서를 안내했다.

### Prior가 역효과를 낸 경우

259, 390: Prior 주입으로 시스템 프롬프트가 ~30줄 증가. 이것이 LLM의 **컨텍스트 부담**을 늘려서 기존에 잘 되던 task의 성능을 떨어뜨렸을 가능성.

### Prior가 효과 없는 경우

102: eval이 기대하는 프로젝트 URL이 task intent와 불일치. Prior로 해결 불가.
205: 커밋 수 추출 — Prior에 `view_commits` 경로가 있지만 LLM이 활용하지 않음.

---

## 결론

1. **Prior는 방향이 맞다**: 안정 FAIL 4개 중 3개(258, 308, 339)가 Prior로 인해 0/3 → 1/3으로 개선. 특히 258은 Prior 없이는 구조적으로 불가능한 task.

2. **효과가 비결정적**: LLM이 Prior를 때때로 무시하고 자기 판단으로 행동. goto를 쓸 때도 있고 안 쓸 때도 있음.

3. **역효과 가능성**: 시스템 프롬프트가 길어져서 일부 task에서 성능 하락. Prior 데이터의 양과 형식 최적화 필요.

4. **전체 성공률은 동일**: Prior가 일부 task를 살리지만 다른 task를 죽여서 총합은 변하지 않음.

---

## 다음 단계

1. **Prior 역효과 최소화**: 시스템 프롬프트 최적화 — 현재 task에 관련된 Prior만 선택적 주입
2. **goto 안정화**: Prior에 URL이 있으면 goto를 더 강하게 유도
3. **Prior 데이터 보강**: 실패 task 분석 후 누락된 패턴 추가
4. **더 많은 task 측정**: 14개 외 추가 task로 범용성 확인
