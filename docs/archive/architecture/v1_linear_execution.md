# Architecture v1 — 선형 실행

**기간**: 프로젝트 초기 ~ v2 도입 전  
**상태**: 폐기 (v2로 대체)

---

## 개요

최대 15스텝의 선형 실행 구조. LLM이 매 스텝마다 관측→판단→실행을 수행하고, 마지막에 한 번 검증.

```
step 1 → step 2 → step 3 → ... → step 15 (소진) → 검증
```

## 핵심 구조

- **실행**: 선형 스텝 루프 (최대 15스텝)
- **LLM 역할**: 매 스텝 관측을 받고 다음 행동 결정
- **검증**: 태스크 완료 후 1회 검증
- **복구**: LLM의 자발적 goto에 의존 (구조적 복구 없음)

## 한계 (v2 전환 이유)

1. **되돌아갈 수 없다** — 잘못된 페이지에 들어가면 복구가 LLM의 자발적 판단에 의존
2. **실패를 반복한다** — 같은 관측 → 같은 판단 → 같은 실패가 반복되며 스텝 낭비
3. **검증이 마지막에만** — 중간 스텝에서 잘못된 경로인 걸 인식하지 못함
4. **스텝 분배 불가** — sub-goal이 3개여도 goal 1에서 15스텝을 다 소진 가능
5. **Executor가 판단을 대행** — fill→click 리다이렉트, 동명 링크 후보 제시 등 특수 로직 다수

## 참고

- `docs/archive/01_mvp_foundation.md` — 프로젝트 정체성 및 MVP 범위
- `docs/archive/02_runtime_architecture.md` — Runtime 컴포넌트 설계
- `docs/archive/03_runtime_data_contracts.md` — 데이터 타입 계약
- `docs/archive/04_implementation_bootstrap.md` — 구현 부트스트랩
