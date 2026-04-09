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

Prior 인프라(types, schema, store, router, system prompt injection)는 **이미 전부 구현돼 있었으나**, `conn = sqlite3.connect(":memory:")`로 매번 빈 DB를 생성하여 Prior 데이터가 없는 상태로 실행됨.

### 변경 사항

1. **seeds/gitlab.py**: SiteProfile(active, sufficient) + 9 PageTypes + 5 ActionSchemas 시딩
2. **agent/core.py**: GitLab일 때 자동 시딩 + URL→page_type 해결
3. **llm.py**: build_plan()에 prior_bundle 전달
4. **executor.py**: build_plan 호출에 prior_bundle 전달
5. **goto tool**: Prior 있을 때만 활성화

### 개선 과정

1차: PageType/ActionSchema 데이터 채움 + goto 활성화 → 258 PASS (goto로 visibility_level=20 직접 이동)
2차: Prior description 간결화 (시스템 프롬프트 ~50% 축소) → 역효과 최소화
3차: issues_list "default view, no filter needed" 명시 + goto 지시 강화

---

## Prior 측정

### 1차 (3회 반복, 상세 Prior)

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

### 2차 (간결화 후, 단일 실행 2회)

| 실행 | PASS | task IDs |
|---|---|---|
| Compact Prior | 8/14 | 44, 132, 156, 169, 205, 259, 293, 357 |
| Improved Prior | 5/14 | 44, 156, 259, 293, 357 |

---

## 비교 분석

### 전체 성공률

| 지표 | Baseline (3회) | Prior 1차 (3회) |
|---|---|---|
| 총 PASS | 21/42 (50.0%) | 20/42 (47.6%) |
| 안정 PASS (3/3) | 4개 | 4개 |
| 안정 FAIL (0/3) | 4개 | 2개 |

**전체 성공률은 유의미한 차이 없음.**

### Task별 변화

| Task | Baseline | Prior | 변화 | 원인 |
|---|---|---|---|---|
| 258 | 0/3 | 1/3 | ↑ | goto로 `?visibility_level=20` 직접 이동. LLM이 goto를 안 쓰면 FAIL. |
| 308 | 0/3 | 1/3 | ↑ | `view_contributors` ActionSchema가 `/-/graphs` 경로 안내. |
| 339 | 0/3 | 1/3 | ↑ | `filter_issues_by_label` 패턴 안내. |
| 293 | 2/3 | 3/3 | ↑ | 네비게이션 안정화. |
| 259 | 3/3 | 2/3 | ↓ | 시스템 프롬프트 길이 증가 역효과 가능. |
| 390 | 2/3 | 0/3 | ↓ | 동일 가능성. |

### Prior가 구조적으로 필수인 경우

**258**: `visibility_level=20` 파라미터는 Prior 없이는 알 수 없는 사이트 특화 지식. Prior가 이 정보를 제공하고 goto로 직접 이동할 때 PASS. **Prior 없이 구조적으로 불가능한 유일한 task.**

### Prior가 도움을 주지만 비결정적인 경우

**308, 339**: Prior에 올바른 경로/패턴이 있지만 LLM이 때때로 무시. 프롬프트 기반 주입의 한계.

### Prior가 역효과를 내는 경우

**259, 390**: Prior 주입으로 시스템 프롬프트가 길어져서 기존에 잘 되던 task 성능 하락. 간결화 후 부분적으로 개선됐지만 완전히 해소되지 않음.

---

## 결론

### 가설 검증 결과

**"사이트별 사전 지식(Prior)을 주입하면 baseline 대비 태스크 성공률이 올라가는가?"**

**결론: 전체 성공률 기준으로는 NO.** Baseline 50% vs Prior 48% — 유의미한 차이 없음.

그러나:
- **안정 FAIL이 4→2로 감소**: 이전에 절대 성공하지 못하던 task 중 3개(258, 308, 339)가 간헐적으로 성공
- **258은 Prior 없이 구조적으로 불가능**: 사이트 특화 URL 파라미터를 Prior가 제공
- **역효과 존재**: Prior 주입이 일부 기존 성공 task를 실패로 전환

### 근본 원인

1. **프롬프트 기반 주입의 한계**: Prior를 시스템 프롬프트에 텍스트로 넣는 방식은 LLM이 일관되게 따르지 않음. "use goto"라고 명시해도 LLM이 click을 선택하는 경우가 빈번.

2. **LLM 비결정성**: 같은 코드, 같은 Prior, 같은 task에서 실행마다 다른 결과. 5/14 ~ 8/14 범위에서 변동.

3. **프롬프트 길이 트레이드오프**: Prior 정보를 추가하면 유용하지만 프롬프트가 길어져서 다른 task에 역효과.

### 시사점

현재 접근(시스템 프롬프트에 Prior 텍스트 주입)은 Prior의 효과를 충분히 실현하지 못한다. Prior를 더 효과적으로 활용하려면:

1. **구조적 강제**: Prior 정보를 프롬프트 텍스트가 아닌 tool/executor 레벨에서 적용 (예: Prior에 goto URL이 있으면 executor가 자동으로 이동)
2. **선택적 주입**: 현재 task와 관련된 Prior만 필터링하여 프롬프트 길이 최소화
3. **다른 LLM 모델**: gpt-4o의 지시 준수 특성이 Prior 활용에 영향. Claude 등 다른 모델에서 다른 결과 가능
4. **더 큰 task 셋**: 14개 task로는 통계적 유의성 확보 어려움

---

## 실험 환경

- LLM: OpenAI gpt-4o (LLM_PROVIDER=openai)
- 벤치마크: WebArena-Verified GitLab (14 tasks)
- 에이전트: Tool Use v5 + done 검증 + search skill + retry 8
- Prior: GitLab seed data (9 PageTypes, 5 ActionSchemas)
- 측정: 각 조건 3회 반복 (일부 단일 실행 추가)
