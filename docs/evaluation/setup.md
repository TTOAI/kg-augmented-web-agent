# Evaluation setup

GitLab 사이트에서 KG 힌트 효과 측정 setup. per (task × 에이전트) 3 trial.

> **용어 매핑**: 본 문서의 **baseline 에이전트** ↔ 코드 변종 `v0` (`KG_ENABLED=0`). **KG 에이전트** ↔ 코드 변종 `v1` (`KG_ENABLED=1`, `KG_MODE=minimal`). 산출물 경로는 코드 식별자(`v0`/`v1`)를 그대로 사용한다.

## KG 힌트 설계 원칙

KG는 **구조적 방향**(어느 페이지·어느 경로·어느 필터 카테고리·어느 컨트롤이 존재하는가)까지만 노출하고, **구체값**(필터에 넣을 라벨 값·URL 쿼리 파라미터 값·자유 텍스트 콘텐츠)은 에이전트가 페이지 상호작용으로 직접 찾는다. KG 힌트 모드(`KG_MODE=minimal`)는 이 원칙의 구현체다 — URL 파라미터 레시피·페이지 클래스 식별자·클래스 화살표 주석을 모두 suppress하고 path 단축과 가시 컨트롤만 남긴다.

이 분리가 KG 에이전트의 step 단축이 *KG의 구조 정보 우월*에서 오는지 *KG가 정답을 흘려서*인지 분리한다.

## Benchmark + agent

- 벤치마크: WebArena-Verified GitLab 자가 호스팅 인스턴스.
- 에이전트 LLM: OpenAI `gpt-5.4-mini`, OpenAI SDK.
- 단일 모델. cross-model 일반화는 향후 과제.

## 비교 변종

| 에이전트 | 환경변수 | 목적 |
|---|---|---|
| **baseline** | `KG_ENABLED=0` | KG 미사용. |
| **KG** | `KG_ENABLED=1` `KG_MODE=minimal` | 타겟 클래스 추론기 + 경로 탐색기 + KG 힌트. |

상세는 [`variants.md`](variants.md).

## Trials

- per (task × 에이전트) **3 trial**
- 이진 outcome은 majority, step 수는 median + range로 보고

## Metrics

상세는 [`metrics.md`](metrics.md). 핵심 신호: per-trial 평가기 결과, step 수, mechanism invocation log, baseline/KG trajectory divergence step.

## Environment handling

- MUTATE task: trial 사이·task 사이 모두 `webarena-verified env stop` + `env start`로 컨테이너 상태 초기화.
- NAVIGATE / RETRIEVE task: 연속 실행, task 경계에서 auth만 갱신.
- per-trial wall-clock timeout: 20분 (`run_with_timeout.py 1200`).

## Budget

에이전트 런타임 한도 (양쪽 동일 적용):

- `MAX_RETRIES_PER_GOAL=8`
- `MAX_REPLANS_PER_TASK=3`
- `LLM_CALL_LIMIT_PER_TASK=450`
- `MAX_STEPS_PER_TASK=60`

## Excluded considerations

- **cross-site**: Reddit/Postmill 적용 코드는 빌드되어 있으나 본 측정 범위 외.
- **cross-model**: 단일 모델 측정. 비교는 future work.
- **통계 검정**: 미수행.

## 산출물

- `output/characterization/{v0,v1}/<task_id>/trial_<n>/` per-task per-trial. (`v0`=baseline, `v1`=KG)
- KG snapshot: `output/validation/`.
