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

## 2. Primary outcome (dual — 2026-04-17 update)

본 연구는 **dual primary outcome**을 측정한다 (`07 §1` triple contribution C1/C2 대응):

### 2-A. Task success rate per variant (H1a)

- 정의: `eval_result.json`의 `status == "success"` 비율.
- 분모: 실행 task 수 (error/timeout 포함).
- 분자: evaluator `status = success` 수.
- 단위: task 단위. step/sub-goal 단위 아님.

### 2-B. Compute efficiency per variant (H1b)

- **Token usage**: 누적 input + output + tool input 토큰 합계 (per task 평균).
- **Step count**: agent loop step 수 (per task 평균).
- **Wall-clock time**: task 시작~종료 elapsed seconds (per task 평균).
- 비교: paired (variant 간 같은 task) — 2 variant 간 차이를 Wilcoxon signed-rank test로 검정 가능.
- Budget context: 모든 variant가 `MAX_STEPS_PER_TASK=50` 제약 하 — `agent/core.py` env로 명시.

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

### 4-3. Significance testing (2026-04-17 final — 2-variant)

- **Variant 간 비교**: paired analysis (같은 task의 variant별 결과를 pair).
- 유의수준: α = 0.05 (single pairwise comparison — Bonferroni 불필요).
- Per-type subset 분석 시: 3 types × H1a/H1b 독립 검정 → 필요 시 **per-type Bonferroni
  α=0.05/3 = 0.017** (overall 검정은 0.05 유지).

### 4-4. Primary 가설 (3-page scope, dual H1 + per-type) — 2026-04-17 final

**H1a_overall (정확도)**: Full KG variant의 success rate ≠ Baseline (30 task, paired
McNemar, two-tailed, α=0.05).

**H1b_overall (효율)**: Full KG variant의 compute cost (token / step / wall-time) ≠
Baseline (paired Wilcoxon signed-rank, two-tailed, α=0.05).

**H1_per_type (heterogeneous effect)**: 각 task type (NAVIGATE / RETRIEVE / MUTATE)별로
H1a/H1b를 독립 검정. 각 type 10 pair McNemar/Wilcoxon, Bonferroni α=0.017.

비교 구성:
- **Variants: 2개** (Baseline, Full KG). 자세한 scope 근거는 `07 §5`.
- **Tasks: 30개** (per-type 10). 자세한 sampling 근거는 `07 §3`.
- Paired 단위: (task, N=3 반복의 majority vote).
- **Pairwise tests**: Baseline ↔ Full KG만 (per-type subset에서 각각 재계산).
- **Two-tailed**: KG가 정확도·효율을 *향상*시킬 수도, *손상*시킬 수도 있음을 사전 명시.
  결과 부호 가정 안 함 (any-result-valuable framing의 핵심).

**연구 질문 중심**: "KG가 전체적으로 개선?"보다 "**KG가 어떤 task type에서 improve/degrade하는가?**"
(heterogeneous effect). per-type H1이 core, overall은 summary.

### 4-5. Per-run paired 이진화 규칙 (Pre-registered)

McNemar test 입력을 생성할 때의 이진화 규칙을 **M5 실행 전에 고정**한다. Reviewer가 optional stopping / p-hacking을 의심하지 않도록 사전 선언.

- **Primary**: `(task, variant)` pair 당 **majority vote** (N=3 runs 중 **2회 이상** eval_status=success → 1, 아니면 0). 30 task × 2 variant → 30 pair로 McNemar (overall). Per-type subset에서는 10 pair McNemar.
- **Secondary (appendix)**: per-run paired (N1 쌍·N2 쌍·N3 쌍 = 90 pair). 같은 방향의 유의성 확인용.
- **Broken evaluator 제외 버전**: `eval_exclusions.md`에 등록된 task는 `(task, variant)` pair에서 제외하고 McNemar 재계산. Raw + Adjusted 둘 다 보고.
- **Env error 처리**: agent_status가 `UNKNOWN_ERROR`이고 log에 env error token이 있는 run은 `failure`가 아니라 **재측정 대상**. 재측정 불가 시 해당 task는 Limitation에 명시하고 **fair하게 양 variant에서 동일 규칙 적용**.
- **이진화 규칙 변경 금지**: M5 측정 시작 이후 이 규칙은 수정하지 않는다 (commit hash로 freeze).

근거: `scripts/analyze_baseline.py`의 `write_paired_csv`가 정확히 이 규칙으로 CSV 생성.

### 4-6. 의도적으로 평가하지 않는 가설 (future work로 분리) — 2026-04-17 update

3-page 분량 제약으로 다음 세분 가설은 본 논문에서 검정하지 않고 `07 §11`의 Out-of-scope 표에
future work로 선언한다:

- "KG가 retrieval 아닌 planning substrate" → KG-retrieval ablation 필요
- "Compute-matched ablation (KG-Info-Ignored)" → 본 2-variant 실험에서 제외, token/step 보고로 partial 차단. 공식 분리는 future work.
- "Hook 단위 fine-grained ablation" (rewrite vs validate vs trust 개별 분리) → future work.
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

- **Table 1** (필수): **per-type × 2 variants** (Baseline / Full KG) 매트릭스.
  - Row: task_type (NAVIGATE / RETRIEVE / MUTATE) + Overall (전체 30 task)
  - Column: (variant × {success rate with Wilson 95% CI, token avg, step avg, wall-time avg})
  - Raw · Adjusted (broken eval 제외) 양쪽 지표 표기.
  - 하단 footnote: **KG-addressable coverage** (§3-5) + **KG source_mix** (crawl/llm/manual)
    + **ARI mean (3 derivation runs)**.

### 7-2. 본문 표 — 공간 여유 시 추가

- Table 2: H1a/H1b 검정 결과 (overall + per-type McNemar χ²/p-value, Wilcoxon W/p-value).
- Table 3: Failure mode 분포 × variant (P/R/G/A/O 카테고리, 04_baseline_failure_analysis 분류 체계 재사용).

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

## 8. Limitation 공개 (reporting 필수 항목) — 2026-04-17 update

본 논문 Limitation 섹션에 **다음 6개를 명시적으로 열거** (근거: `07_scope_and_justifications.md §11`):

1. **단일 사이트 (GitLab)**: Cross-domain 일반화는 future work.
2. **Hook 단위 fine-grained ablation 미수행**: 본 3-variant ablation은 KG *정보*의 기여를 분리하나, Hook 개별(rewrite/validate/trust) 분리는 future work.
3. ~~**Compute-matched ablation 미수행**~~ → **본 연구의 KG-Info-Ignored variant가 직접 측정** (해소됨).
4. **단일 모델 family**: 모델 크기에 따른 KG 효과 robustness는 future work.
5. **Single-shot evaluation**: Continual trust evolution은 architecture에 설계돼 있으나 longitudinal empirical 검증은 future work.
6. **KG 구축 방법론 — 2-stage automated + heuristic post-enrich**: GitLab 단일 사이트 case study. 다른 사이트로의 확장성 (per-site setup 비용, crawler coverage, LLM derivation reproducibility)은 future work. Pipeline의 generic web/domain prior(post_enrich heuristics, prompt convention)는 disclose됨 (`07 §14`).
7. **KG coverage의 seed selection 의존성**: 본 연구는 사이트 공식 navigation entry point 8개를 seed로 사용. 다른 seed set으로의 robustness는 future work.

Reviewer가 이 중 한 항목을 지적해도 "우리가 먼저 future work로 선언함"으로 답변 가능. `07 §11`의 "review 공격면 통제" 설계.

---

## 9. 결정된 타임라인 — 2026-04-17 update

**주의**: 개발 초기의 비공식 baseline(Phase 1/2 pilot)은 다수 버그가 발견돼 폐기됐다.
그 pilot 결과는 `04_baseline_failure_analysis.md`에 개발 로그로만 남아 있고 **paper에
인용되지 않는다**.

전체 실험 규모는 `07_scope_and_justifications.md §12`: **~530 runs, ~$16 (mini), ~27시간**.

```
[baseline 첫 공식 측정]
  1. 새 baseline (29건 버그 수정 반영, LLM_TEMPERATURE=0)을 gitlab 50 task × N=3 실행
     → 150 runs. token 사용량·실행 시간·실패 분포 측정

[KG 구현]
  2. M1~M6 (05 참고). 구현 + KG-Info-Ignored variant 분기 추가

[본 실험 — 2 variants (2026-04-17 scope reduction, 07 §5)]
  3. Baseline × N=3 × 30 task = 90 runs (KG off)
  4. Full KG × N=3 × 30 task = 90 runs (Hook A/B/C on, D logging only)
  5. 총 180 runs. 3rd variant KG-Info-Ignored (compute-matched control)는 future work (07 §11).
  6. McNemar/Wilcoxon 검정 (Baseline ↔ Full KG만):
     - H1a: 성공률 paired McNemar, overall α=0.05 + per-type α=0.0167 (Bonferroni 3)
     - H1b: token/step/wall-time paired Wilcoxon
  7. Failure classification (P/R/G/A/O) + Cohen's κ (2-rater)
  8. Hook B/C 발동 통계 (coverage.py 확장, Option B 활성 후)

[논문 작성]
  8. Introduction / Method / Experiment / Discussion / Limitation / References
  9. Limitation 섹션에 §8의 7개 항목 명시
  10. 부록: 재현 지침 (seed, task_id 목록, 모델 버전, Docker hash, ARI score)
```
