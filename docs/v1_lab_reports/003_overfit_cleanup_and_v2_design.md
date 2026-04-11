# Lab Report 003 — 과적합 제거, 코드 리팩토링, v2 아키텍처 설계

**날짜**: 2026-04-07~08  
**목적**: 002 안정성 재측정 결과의 성능 저하 분석, 과적합 로직 제거, 코드 구조 개선, 다음 단계 아키텍처 설계.

---

## 002 재측정 결과 (Prior 도입 전 baseline)

| Task | 3회 결과 | 분류 |
|---|---|---|
| 44, 156, 357, 132, 205 | 3/3 PASS | 안정 |
| 339 | 2/3 | 불안정 |
| 45, 293, 169, 390 | 0/3 | 성능 저하 |
| 258, 102, 308 | 0/3 | 기대 실패 (사전 지식/벤치마크) |

안정 성공률: 5/13 (38.5%)

---

## 성능 저하 원인 분석

### 공통 원인
여러 task 해결을 위해 추가한 특수 로직들이 서로 간섭:
- 드롭다운 자동 Enter가 정렬 드롭다운에서 오작동 (45)
- 입력→클릭 자동 전환이 MR 검색을 방해 (390)
- 드롭다운 클릭이 필터/정렬을 구분 못 함 (339, 45)
- 검색 경로 불안정 (293)

### 핵심 인사이트
특정 task를 해결하기 위한 코드가 다른 task를 깨뜨리는 과적합 문제. 하나를 고치면 다른 게 깨지는 구조적 문제.

---

## 수행한 작업

### 1. 과적합 로직 제거

| 제거한 로직 | 원래 목적 | 제거 이유 |
|---|---|---|
| 드롭다운 상태 감지 + 자동 Enter | 339 필터 제출 | 정렬 드롭다운에서 오작동 |
| NAVIGATE에서 not_found를 SUCCESS로 자동 변환 | 빈 결과 페이지 허용 | LLM 판단을 덮어씀 |
| 데이터 추출 오용 방어 | LLM이 완료 액션을 잘못 사용 | 특정 LLM 패턴에 과적합 |
| 클릭 후 1초 대기 | 비동기 렌더링 대기 | 모든 클릭에 불필요한 지연 |
| Plan 특화 프롬프트 (필터/ID/정렬) | 169, 339 | 특정 task에 맞춘 지침 |
| extract 형식 검증 프롬프트 | 169 | 특정 task에 맞춘 지침 |

### 2. 코드 리뷰 (3-agent 병렬)

- **코드 재사용**: CSS fallback을 `try_click_target()` 재사용으로 교체
- **코드 품질**: `text` 변수 NameError 버그 수정, `import re` 모듈 상단 이동, bare except → logger.debug
- **효율성**: N회 CDP 왕복 → 단일 함수 호출로 개선

### 3. 리팩토링: _execute_with_llm() 분리

300줄 모놀리식 함수를 ~70줄 메인 루프 + 독립 핸들러로 분리:

| 함수 | 역할 |
|---|---|
| `_handle_done()` | done 처리 (sub-goal 전환) |
| `_handle_extract()` | extract 처리 |
| `_handle_failure()` | failure action 처리 |
| `_execute_click()` | click 3단계 (관측 → get_by_role → try_click_target) |
| `_execute_fill()` | fill |
| `_execute_goto()` | goto |
| `_execute_search()` | search |
| `_summarize_action_result()` | 결과 피드백 생성 |

### 4. Phase 1: Executor 단순화

판단 대행 로직 제거:
- 입력→클릭 자동 전환 제거
- 완료 선언 시 LLM 검증 호출 제거
- Executor를 순수 실행 + 결과 보고 레이어로 정리

### 5. v2 아키텍처 설계

`docs/specs/05_agent_execution_architecture_v2.md` 작성:

핵심 설계 원칙:
- **빠른 실행 + 빠른 검증 + 빠른 복귀** (zero-trust)
- **LLM 첫 판단의 방향을 신뢰**, 실행만 미세 조정 (graduated retry)
- **Executor는 범용 도구**, 판단을 대신하지 않음

주요 구조:
- Sub-goal별 실행 루프 + checkpoint + retry
- Graduated retry (미세 조정 → 경로 변경 → 접근 전환)
- Replanning (sub-goal 실패 시 동적 재계획)
- Verification 레이어 (독립 검증)

---

## 현재 상태

- 과적합 코드 제거 + 리팩토링 완료
- v2 설계 문서 완성
- Phase 1 (Executor 단순화) 완료
- Phase 2 (Sub-goal별 실행 루프) 구현 예정

---

## 다음 단계

1. **Phase 2 구현**: Sub-goal별 실행 루프 + checkpoint + retry + graduated feedback
2. **Phase 3 구현**: Verification + Replanning
3. **전체 재측정**: v2 구현 후 13개 task 안정성 측정
4. **Prior 도입**: baseline 안정화 후 사이트 특화 지식 주입
