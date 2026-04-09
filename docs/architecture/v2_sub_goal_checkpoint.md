# Architecture v2 — Sub-goal + Checkpoint

**기간**: v2 도입 ~ v5 Tool Use 전환 전  
**상태**: 폐기 (v3로 대체). 실행 구조(sub-goal, checkpoint, retry, replan)는 v3에서 계승.

---

## 개요

태스크를 2~5개 sub-goal로 분해하고, 각 goal별 checkpoint 저장 + graduated retry + replan으로 복구하는 구조. v1의 선형 실행 한계를 해결.

```
태스크 → Planning (2~5 sub-goals) → Sub-goal 루프:
    Step 루프 (budget 내): 관측 → LLM 판단 (JSON) → Executor 실행 → 피드백
    성공 → checkpoint 저장 → 다음 goal
    실패 → checkpoint 복원 → retry (graduated)
    retry 소진 → replan (점진적 롤백)
```

## 핵심 구조

### Sub-goal 분해
- LLM이 태스크를 2~5개 sub-goal로 분해 (Planning 1회 호출)
- 각 goal에 navigation/action/cognition 타입 부여
- NAVIGATE 태스크의 마지막 goal = navigation 타입 강제

### Checkpoint 스택
- goal 성공 시 `checkpoint_stack.append(page.url)`
- 실패 시 `page.goto(checkpoint_stack[-1])`로 복원
- 2차+ replan: 이전 checkpoint로 점진적 롤백

### Graduated Retry
- goal당 최대 5회
- 실패 이력 전달: "이전 시도에서 이렇게 했는데 실패. 다른 접근을 해라"

### Replan
- 최대 3회
- 실패한 goal 이후의 plan을 LLM이 재생성

### LLM 인터페이스 (프롬프트 기반)
- System prompt에 Rules + Actions JSON 형식 설명
- LLM 응답: `{"action": "click", "target": "...", "reasoning": "..."}`
- Executor가 `parse_llm_action()`으로 텍스트 파싱

### 점진적 개선 (v2 → v3 → v4)

| 항목 | v2 | v3 | v4 |
|---|---|---|---|
| 검증 | 결정론적 (URL/DOM 변화) | LLM 자가 판단 | done 자유 통과 + NAVIGATE URL 체크만 |
| 관측 | 기본 요소 수집 | DOM 안정화 + delta 추적 + visibility 필터 | delta + URL params (nearby 제거) |
| 클릭 매칭 | 기본 | dropdown 우선 + element_type | + target " → /path" 자동 파싱 |
| 진행 감지 | 없음 | 6스텝 강제 종료 + 반복 감지 | 제거 (budget이 자연 제한) |
| messages | 6개 | 6개 | 10개 |

## 한계 (v3 전환 이유)

1. **JSON 파싱 취약** — 마크다운 펜스 누락, 불완전 JSON 등
2. **프롬프트 규칙 소프트 제약** — "goto 금지" 등을 LLM이 어길 수 있음
3. **정보 수집 수동적** — NOTE: 텍스트 매칭이 불안정
4. **규칙 비대화** — Actions 설명 + Rules가 컨텍스트를 차지

## 참고

- `docs/archive/05_agent_execution_architecture_v2.md` — v2 원본
- `docs/archive/06_agent_execution_architecture_v3.md` — v3 원본
- `docs/archive/07_agent_execution_architecture_v4.md` — v4 원본
- `docs/lab_reports/003_overfit_cleanup_and_v2_design.md` — v2 설계 과정
- `docs/lab_reports/004_observation_verification_execution_overhaul.md` — v3 관측/검증 개선
