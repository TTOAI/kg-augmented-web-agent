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

## Variants

상세 정의는 [`variants.md`](variants.md). 세 변종:

- **V0** — KG 미사용 baseline.
- **V1** — KG 최소 힌트 모드 전체 활성.
- **V1−tc** — KG의 page-surface 힌트만 활성, 타겟 클래스 추론기 비활성. L1 능동적 오도의 원인 분리용.

## Task selection

총 8 task를 8개 가설 cell에 1:1 배정한다.

- **3 효과 조건 (H)** — H1: 단일 URL 템플릿 단축 / H2: 다중 hop 경로 압축 / H3: 모호 범위 disambiguation
- **3 한계 조건 (L)** — L1: 미매핑 클래스 능동적 오도 / L2: 비ARIA 모달에서 기여 소멸 / L3: KG 무관한 평가기 strict-match 결함
- **2 null 조건 (Null)** — Null1: 시작 페이지에서 1-step 직접 이동 / Null2: 텍스트 콘텐츠 중심 과제(KG로 단축 불가)

각 task의 가설 카드는 [`task_cards/`](task_cards/)의 `<조건코드>_<task_id>.md`에서 사전 등록. task 선정·가설 수립·falsification 기준은 측정 시작 *이전*에 main 브랜치로 머지된다.

| 조건 | task_id | task type | KG 메커니즘 |
|---|---|---|---|
| H1 | 309 | RET | contributor_graph URL 템플릿 |
| H2 | 102 | NAV | 다중 hop + label_name[] 필터 URL |
| H3 | 156 | NAV | dashboard vs project 범위 disambiguation |
| L1 | 411 | MUT | license edit 페이지 미매핑 |
| L2 | 568 | MUT | invite-members 비ARIA 다이얼로그 |
| L3 | 308 | RET | 답 포맷 strict-match (KG 도달 후에도 평가 실패) |
| Null1 | 44 | NAV | 시작 페이지에서 직접 링크 |
| Null2 | 664 | MUT | 텍스트 콘텐츠 중심 issue 작성 |

## Pre-registration

본 폴더의 task 카드·variant 정의·metric 명세는 측정 시작 commit *이전에* main 브랜치로 머지된다. 측정은 그 이후 commit에서 실행되며 paper §3에 두 SHA가 모두 인용된다.

## Trials

- per (task × variant) cell **3 trial**.
- 총 run: 8 × 3 × 3 = **72**.
- 이진 outcome은 majority, step 수는 median + range로 보고.

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
- **통계 검정**: paired-test power 부족으로 보고 안 함. McNemar/Wilcoxon 등 미사용.

## Reproducibility artefacts (post-measurement)

측정 완료 시 다음을 commit:

- `output/characterization/{v0,v1,v1_tc}/<task_id>/trial_<n>/` per-task per-trial.
- `eval_exclusions.md` freeze (broken evaluator task 식별 후 commit).
- KG snapshot (`output/validation/...`) git-tracked.
- 측정 commit SHA를 paper §3에 인용.
