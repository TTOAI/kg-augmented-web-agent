# 06. Evaluation Protocol

## 이 문서의 목적

쟁점 #4 ablation 결과를 publication-quality로 분석하기 위한 측정·기록·분석 프로토콜을 확정한다. 본 실험이 시작되기 전에 protocol을 fix함으로써 post-hoc 해석 편향을 방지한다(pre-registration에 가까운 원칙).

---

## 1. 원칙

- **Fixed before experiment**: 본 실험 ablation 측정 시작 전 이 문서의 protocol은 동결. 해석 시점에 바꾸지 않는다.
- **모든 실행 로그 보존**: raw agent response + network HAR + webarena_verified.log 전부 task 단위 보관. 재집계 가능.
- **Limitation을 결과와 동등하게 기록**: 약점을 별도 섹션에 명시 (Phase 2 샘플 편향, N 크기 등).
- **선택적 리포팅 금지**: 모든 variant의 모든 task에 대한 결과를 보고. cherry-picking 차단.

---

## 2. Primary outcome

**Task success rate per variant**

- 정의: `eval_result.json`의 `status == "success"` 비율.
- 분모: 실행 task 수 (error/timeout 포함).
- 분자: evaluator `status = success` 수.
- 단위: task 단위. step/sub-goal 단위 아님.

### 2-1. Error 처리

- **timeout error** (600s 초과): 실패로 계산. 별도로 timeout 비율 보고.
- **env error** (gitlab container down 등): 재실행 후 그 결과 사용. 재실행 불가면 제외하고 이유 명시.
- **agent crash** (Python exception): 실패로 계산.

### 2-2. Broken eval task

메모리 원칙(`broken eval task 처리 원칙`)에 따라 **evaluator의 strict match 결함으로 정상 행동이 fail나는 task는 공식 점수 배제, 내부 성공으로 기록**.

- broken eval 판정 기준: 수동 검증에서 "agent가 의미적으로 목표 달성, 단 evaluator의 URL/문자열 match 규칙이 지나치게 엄격해서 fail"인 경우.
- 판정자: 저자 + 자체 log 확인. 판정 근거를 `docs/kg_design/eval_exclusions.md`에 공개 기록.
- 공식 보고: broken 제외 success rate와 broken 포함 success rate **둘 다** 보고.

---

## 3. Secondary outcomes

### 3-1. Compute cost

- **Token usage**: 누적 input + output + tool input 토큰. OpenAI/Anthropic API response의 usage 필드에서 추출.
- **Step count**: agent loop step 수 (webarena_verified.log의 `step=<N>` 최댓값).
- **Wall-clock time**: task 시작~종료 (log timestamp).
- **LLM call count**: complete_with_tools 호출 횟수.

### 3-2. Failure mode 분포

`04_baseline_failure_analysis.md`의 taxonomy를 사용해 실패 task를 라벨링:

- **P** (Plan-structural)
- **R** (Route-knowledge)
- **G** (Grounding/extraction)
- **A** (Verifier/evaluator artifact)
- **O** (Other — 지정 불가)

각 task는 primary (●) + secondary (△) 라벨을 받음 (한 task가 여러 카테고리에 해당 가능).

**라벨링 절차**:
1. 저자 1이 모든 실패 task를 log 보고 1차 라벨링.
2. 저자 2가 독립적으로 재라벨링 (또는 본 연구가 단일 저자면 48시간 간격으로 자체 재라벨링).
3. 불일치 case는 합의 또는 제3자 판정.
4. **Inter-rater agreement (Cohen's κ) 보고** — κ < 0.6이면 taxonomy 재정의 고려.
5. 본 연구가 단일 저자일 경우 intra-rater agreement로 대체.

### 3-3. Task-type subset 분석

agent가 runtime에 결정한 task_type(`NAVIGATE` / `RETRIEVE` / `MUTATE`) 기준으로 subset 분리 보고.

- 쟁점 #2의 "navigate_to collapse" 비판 대응에 NAVIGATE subset 따로 보고 필수.
- MUTATE subset에서 KG의 multi-step rewrite 유지 비율 보고.

### 3-4. Rewrite intervention 통계 (KG variants만)

- rewrite 적용 비율: plan이 실제로 rewrite된 task 비율.
- collapse 비율: rewrite 결과가 single `navigate_to`로 축약된 비율 (NAVIGATE subset에서).
- Hook C (early termination) 발동 비율.
- Trust 레벨별 rewrite 적용 빈도 (verified / declared / inferred).

### 3-5. KG-addressable coverage (catalog objectivity 지표)

- **정의**: 50 task 중 Hook A가 `plan_to_info` tool을 성공적으로 호출해 InfoType·bindings로 분류된 비율.
- **목적**: catalog가 실험 task에 맞춰 사후 조정되지 않았음을 드러내는 objectivity 지표 (`02 §3-4`, `07 §14` 참조). 커버리지 < 100%가 오히려 정상 — catalog가 실험 task 분포가 아니라 사이트 전반을 기준으로 작성됐다는 증거.
- **보고 형식**: §7 Table 1에 coverage 행을 추가 (전체 + task_type subset별).
- **Source-mix 동반 보고**: `SiteKG.source_mix` (crawl / llm / manual 분포)를 함께 제시해 catalog 구축 파이프라인이 3단계 hybrid로 수행됐음을 보인다.

---

## 4. Statistical design

### 4-1. Replication

- **N=3 per (variant, task)** 최소. 가능하면 N=5.
- 예산 제약 시 N=3 유지하고 task 수 줄이는 쪽 우선.
- 동일 (variant, task) N회 실행 결과의 aggregation: **majority vote** 기본. success 비율도 부록 보고.

### 4-2. Confidence intervals

- Success rate: Wilson score interval (binary 성공률에 적합, 양극단 값 안정).
- Variance 표시: 모든 rate에 95% CI 표기.

### 4-3. Significance testing

- **Variant 간 비교**: paired analysis (같은 task의 variant별 결과를 pair). McNemar's test for paired binary outcomes.
- **Multiple comparisons**: Bonferroni correction (ablation variant 수로 나눔).
- 유의수준: α = 0.05.

### 4-4. Primary 가설 (3-page scope, 단일 H1)

**H1**: Full KG variant의 success rate > Baseline variant의 success rate (paired McNemar test, α=0.05).

비교 구성:
- Variants: 2개 (Baseline, Full KG). 자세한 scope 근거는 `07_scope_and_justifications.md §5`.
- Paired 단위: (task, N회 반복 중 majority vote 결과).
- Test: McNemar's test for paired binary outcomes. Multiple comparison correction 불필요 (가설 1개).

### 4-5. 의도적으로 평가하지 않는 가설 (future work로 분리)

3-page 분량 제약으로 다음 세분 가설은 본 논문에서 검정하지 않고 `07 §11`의 Out-of-scope 표에 future work로 선언한다:

- "KG가 retrieval 아닌 planning substrate" → KG-retrieval ablation 필요
- "단순 compute 증가 아님" → compute-matched ablation 필요. 대신 §3-1 token/step 수치 함께 보고로 사전 차단
- "모델 크기 invariance" → mini+full 양쪽 측정 필요
- "Continual adaptation 효과" → 3-round replay 필요

---

## 5. Continual replay evaluation (future work로 이관)

**본 3-page 논문에서는 실험하지 않는다.** Trust evolution 메커니즘은 architecture 수준에 설계되어 있으나 (`05_implementation_architecture.md §3 Continual 셋업`), 실험적 검증은 **longitudinal evaluation as future work**로 `07 §11`에 선언된다.

단일 round 측정만 수행하며 trust 값은 seed 상태를 유지한 채 변동 없이 사용한다 (Hook D는 로깅 목적으로만 호출).

근거는 `07_scope_and_justifications.md §1` (의도적 제외).

---

## 6. Evaluator quirks handling

WebArena-Verified evaluator의 알려진 문제점들:

### 6-1. NetworkEventEvaluator strict URL match

- Pilot에서 agent는 SUCCESS 선언하지만 evaluator는 URL 세부 불일치로 fail (4/6).
- 본 연구에서 **agent 내부 성공 vs evaluator 판정 둘 다 기록**. "evaluator-restrictive" 차이 드러내기.

### 6-2. AgentResponseEvaluator string match

- RETRIEVE task에서 extracted value가 정답과 exact match 안 되면 fail.
- 원인 분석: (a) 틀림 (b) 정답이나 formatting 다름 (c) evaluator 정답 자체 오류.
- 정답 formatting 차이(예: "183" vs "183,184")의 경우 수동 검증 후 broken eval로 분류 가능.

### 6-3. MUTATE backend state 평가

- 일부 MUTATE task는 DB 쿼리로 평가. agent가 UI에서 성공해도 backend 효과가 없으면 fail.
- 이게 정확한 평가 방식 — 수용. 단 "UI 성공 vs DB 성공"의 괴리는 pipeline 문제로 별도 보고.

---

## 7. Reporting standards (3-page scope)

### 7-1. 본문 표 — 필수 1개

- **Table 1** (필수): 전체 task × 2 variant success rate + token·step·wall-time 평균. Raw · Adjusted(broken eval 제외) 양쪽. Wilson 95% CI 포함. 하단에 **KG-addressable coverage** (§3-5) + **KG source_mix** (crawl/llm/manual 비율)를 표기.

### 7-2. 본문 표 — 공간 여유 시 추가

- Table 2: Task-type subset × variant success rate (RETRIEVE / NAVIGATE / MUTATE).
- Table 3: Failure mode 분포 × variant (P/R/G/A 카테고리, 04_baseline_failure_analysis 분류 체계 재사용).

### 7-3. 그림 — 최대 1개

- Fig 1 (선택): 전체 success rate + 95% CI bar chart. 공간 있을 때만.
- continual · heatmap 등 여러 variant/round 그림은 3-page scope 밖이라 제외.

### 7-3. 부록

- variant별 task별 N 회 실행 결과 full table.
- failure classification 이유 (task별 summary).
- broken eval 판정 근거.
- Phase 2 샘플링 full procedure.
- Inter-rater agreement 세부.

### 7-4. Code + data release

- 실행 스크립트 + config 공개.
- 원 log는 sensitive data 제외하고 공개.
- 재현 지침 (seed, 모델 버전, Docker 이미지 해시).

---

## 8. Limitation 공개 (reporting 필수 항목)

본 논문 Limitation 섹션에 **다음 5개를 명시적으로 열거** (근거: `07_scope_and_justifications.md §11`):

1. **단일 사이트 (GitLab)**: Cross-domain 일반화는 future work.
2. **Fine-grained ablation 미수행**: rewrite / validate / trust policy 개별 기여 분석은 future work.
3. **Compute-matched ablation 미수행**: 대신 token·step·wall-time 수치로 compute confound 사전 차단, 공식 ablation은 future work.
4. **단일 모델 family**: 모델 크기에 따른 KG 효과 robustness는 future work.
5. **Single-shot evaluation**: Continual trust evolution은 architecture에 설계돼 있으나 longitudinal empirical 검증은 future work.
6. **KG 구축 방법론 자체가 연구 artifact**: 본 연구의 3단계 hybrid 구축 파이프라인(Playwright crawl + LLM derivation + 수동 검증)은 GitLab에 적용된 첫 사례로, 다른 사이트에 scale했을 때의 인력·시간 비용, crawler 커버리지, LLM derivation의 재현성은 본 논문에서 측정하지 않는다 (`07 §14` 참조).

Reviewer가 이 중 한 항목을 지적해도 "우리가 먼저 future work로 선언함"으로 답변 가능. `07 §11`의 "review 공격면 통제" 설계.

---

## 9. 결정된 타임라인

**주의**: 개발 초기의 비공식 baseline(Phase 1/2 pilot)은 다수 버그가 발견돼 폐기됐다. 그 pilot 결과는 `04_baseline_failure_analysis.md`에 개발 로그로만 남아 있고 **paper에 인용되지 않는다**.

전체 실험 규모는 `07_scope_and_justifications.md §12`: **~370 runs, ~$11 (mini), ~19시간**.

```
[baseline 첫 공식 측정]
  1. 새 baseline (29건 버그 수정 반영, LLM_TEMPERATURE=0)을 gitlab 50 task × N=3 실행
     → 150 runs. token 사용량·실행 시간·실패 분포 측정
  2. 측정 결과로 token/run 비용 확정 → full 모델 전환 여지 검토
  3. 새 baseline failure classification (본 protocol §3-2 적용) → paper Method 근거

[KG 구현]
  4. M1~M6 (05 참고). 구현 중 14 task smoke로 회귀 검증 (~60 runs)

[본 실험]
  5. Full KG variant × N=3 × 50 task = 150 runs 측정
  6. H1: McNemar's test (Baseline vs Full KG)
  7. Failure classification (단일 저자 intra-rater agreement)

[논문 작성]
  8. Introduction / Related Work / Method / Experiment / Limitation / References
  9. Limitation 섹션에 §8의 5개 항목 명시
  10. 부록: 재현 지침 (seed, task_id 목록, 모델 버전, Docker 이미지 해시)
```
