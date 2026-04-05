# Implementation Bootstrap

## 1. Purpose

이 문서는 다음 세션이나 다른 세션에서 구현을 바로 재개하기 위한 부트스트랩 문서다.
상세 설계를 다시 쓰는 문서가 아니라, 이미 고정된 결정을 구현 순서로 압축해 전달하는 용도다.

먼저 읽어야 할 기준 문서:

- `docs/01_mvp_foundation.md`
- `docs/02_runtime_architecture.md`
- `docs/03_runtime_data_contracts.md`

## 2. Fixed Decisions

구현 고정 결정:

- `Python` 오케스트레이터
- `direct Playwright` 브라우저 제어
- `Claude` 판단 레이어 (구조적 site prior를 컨텍스트로 주입)
- `SQLite` 저장소
- `core runtime`과 `WebArena-Verified adapter` 분리
- `benchmark-aware but benchmark-decoupled`

바꾸지 말아야 할 규칙:

- `RunRequest`, `RunContext`, `PriorBundle` 중심 구조 유지
- `fast_path`, `partial_prior`, `fallback`, `approval_first` 경로 유지
- `approval_wait` 상태 유지
- recovery 성공 후 validator 재실행
- `Execution Memory`와 `Site Prior Store` 분리
- benchmark 전용 필드를 core 타입과 core DB에 넣지 않기
- prior는 구조적 지식(page_types + action_schemas)만 포함하며 절차적 레시피(WorkflowHint)는 넣지 않기

## 3. Implementation Order

구현 순서:

1. Python 프로젝트 골격과 의존성 정의 ✅
2. SQLite 스키마와 핵심 타입 정의 ✅
3. prior store / memory store 구현 ✅
4. direct Playwright browser wrapper 구현 ✅
5. router / executor / validator / recovery 구현 ✅
6. local runner로 acceptance 시나리오 3개 통과 ✅
7. LLM 연결 — page_types + action_schemas를 컨텍스트로 Claude 추론 주입
8. Recording Session — 사용자 시연 이벤트 수집 → page_types / action_schemas 자동 추출
9. `WebArena-Verified` adapter 연결 + baseline 측정
10. Prior 자동 강화 — 에이전트 성공 실행 결과로 action_schemas / page_types 업데이트
11. 적응 루프 — 실패 분석 → prior 보강 → 재실행

## 4. Benchmark Integration Rule

`WebArena-Verified`는 core runtime 설계 기준이 아니라 연동 대상이다.
먼저 benchmark의 최소 agent interface만 확인하고, 이후 adapter에서 아래 변환만 담당한다.

- benchmark input -> `RunRequest`
- benchmark observation -> `RunContext`
- core action/result/log -> benchmark output format

adapter가 바꾸면 안 되는 것:

- router 판단 규칙
- prior selection 규칙
- validator / recovery semantics

## 5. Current Non-Goals

현재 구현 범위에 넣지 않는 것:

- MCP
- 자동 prior 승격 (MVP 이후)
- full vision
- WorkflowHint 또는 절차적 레시피 기반 실행 안내
- benchmark 전용 필드의 core 침투
- benchmark harness 자체를 core runtime보다 먼저 구현하는 일

## 6. Next Session Prompt

다음 세션 시작 시 아래 프롬프트를 그대로 붙여 넣으면 된다.

```text
이 repo는 runtime 파이프라인 뼈대가 구현되어 있습니다.
먼저 다음 문서를 읽고 그 기준으로 다음 단계를 진행하세요.

- docs/01_mvp_foundation.md
- docs/02_runtime_architecture.md
- docs/03_runtime_data_contracts.md
- docs/04_implementation_bootstrap.md

고정 결정:
- Python 오케스트레이터
- direct Playwright
- Claude 판단 레이어 (site prior를 컨텍스트로 주입)
- SQLite 저장
- core runtime과 WebArena-Verified adapter 분리
- benchmark-aware but benchmark-decoupled

바꾸지 말아야 할 규칙:
- RunRequest / RunContext / PriorBundle 중심 구조
- fast_path / partial_prior / fallback / approval_first
- approval_wait 상태 유지
- recovery 성공 후 validator 재실행
- Execution Memory와 Site Prior Store 분리
- prior = 구조적 지식(page_types + action_schemas), WorkflowHint 없음
- benchmark 전용 필드는 core에 넣지 않기

다음 구현 단계: LLM 연결 (7번)
- page_types + action_schemas를 Claude 컨텍스트로 직렬화
- executor에서 Claude API 호출로 브라우저 액션 계획 수립
- 결과를 ExecutionOutcome으로 변환

구현을 진행하면서 문서와 충돌하는 결정은 하지 말고, 필요하면 문서 기준으로 최소한만 보완하세요.
```
