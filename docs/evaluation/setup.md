# Evaluation setup — characterization study

## Research framing

본 측정은 사전 계산된 사이트별 구조 KG를 LLM 웹 에이전트에 힌트로 주입했을 때 **GitLab 사전 선정 과제 군에서 어떤 메커니즘이 어떤 조건에서 효과·무효·역효과를 보이는지 특성화**(characterization)하는 연구다.

- 모집단 수준의 우열 비교가 아니다.
- 효과 / 한계 / 무영향이 모두 동등하게 publishable한 결과다.
- 통계 검정은 N이 작아 보고하지 않는다.

## KG hint design principle

KG는 **구조적 방향**(어느 페이지·어느 경로·어느 필터 카테고리·어느 컨트롤이 존재하는가)까지만 노출하고, **구체값**(필터에 넣을 라벨 값·URL 쿼리 파라미터 값·자유 텍스트 콘텐츠)은 agent가 페이지 상호작용으로 직접 찾는다. minimal mode는 이 원칙의 구현체다 — URL 파라미터 레시피·페이지 클래스 식별자·클래스 화살표 주석을 모두 suppress하고 path 단축과 가시 컨트롤만 남긴다.

이 분리가 V1의 step 단축이 *KG의 구조 정보 우월*에서 오는지 *KG가 정답을 흘려서*인지 reviewer-proof하게 분리한다.

## Benchmark + agent

- 벤치마크: WebArena-Verified GitLab 자가 호스팅 인스턴스.
- 에이전트 LLM: Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`), Anthropic SDK 0.89.0+, prompt caching 활성화.
- 단일 모델. cross-model 일반화는 향후 연구로 명시.

## Variants — V0 vs V1 (V1−tc 제외)

| Variant | KG | 목적 |
|---|---|---|
| **V0** | `KG_ENABLED=0` | KG 미사용 baseline. |
| **V1** | `KG_ENABLED=1` `KG_MODE=minimal` | 타겟 클래스 추론기 + 경로 탐색기 + minimal hint. |

상세는 [`variants.md`](variants.md). V1−tc는 pilot에서 page-surface info의 자체 효과로 clean control이 아님이 확인되어 본 측정 범위 제외 ([`round_protocol.md`](round_protocol.md) §4 참조).

## 측정 방법론 — iterative round

본 측정은 **task 8개를 사전 lock하지 않는다**. round별로 task를 선정하되 (1) 선정 규칙, (2) stopping rule, (3) 전건 보고 의무를 측정 *전*에 main 브랜치에 commit한다. 상세는 [`round_protocol.md`](round_protocol.md).

각 round의 task는 [`task_cards/<COND>_<task_id>.md`](task_cards/)에 사전 등록된다. 후보 task는 [`task_cards/candidates/`](task_cards/candidates/)에 보관되며 round 시작 시 root로 이동한다.

## Trials

- per (task × variant) cell **3 trial**
- 이진 outcome은 majority, step 수는 median + range로 보고

## Metrics

상세는 [`metrics.md`](metrics.md). 핵심 신호: per-trial 평가기 결과, step 수, mechanism invocation log, V0/V1 trajectory divergence step.

## Environment handling

- MUTATE task: trial 사이·task 사이 모두 `webarena-verified env stop` + `env start`로 컨테이너 상태 초기화.
- NAVIGATE / RETRIEVE task: 연속 실행, task 경계에서 auth만 갱신.
- per-trial wall-clock timeout: 20분 (`run_with_timeout.py 1200`).

## Budget

에이전트 런타임 한도 (모든 variant 동일 적용):

- `MAX_RETRIES_PER_GOAL=8`
- `MAX_REPLANS_PER_TASK=3`
- `LLM_CALL_LIMIT_PER_TASK=450`
- `MAX_STEPS_PER_TASK=60`

## Excluded considerations

- **cross-site**: Reddit/Postmill 적용 코드는 빌드되어 있으나 본 측정 범위 외.
- **cross-model**: Claude Sonnet 4.6 단일 모델. OpenAI 비교는 future work.
- **V1−tc ablation**: pilot 결과 기반 제외. future work.
- **통계 검정**: paired-test power 부족으로 보고 안 함.

## Reproducibility artefacts (post-measurement)

측정 완료 시 다음을 commit:

- `output/characterization/{v0,v1}/<task_id>/trial_<n>/` per-task per-trial.
- `eval_exclusions.md` freeze (broken evaluator task 식별 후 commit).
- KG snapshot (`output/validation/...`) git-tracked.
- 측정 commit SHA를 paper §3에 인용 (round_protocol.md commit SHA 별도 인용).
