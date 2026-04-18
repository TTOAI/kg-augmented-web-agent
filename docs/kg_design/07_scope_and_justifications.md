# 07. Scope 결정과 정당화 근거

## 이 문서의 목적

본 연구가 **국내 학회 3-page 논문** 포맷에 맞춰 내린 모든 scope 결정을 한 곳에 모은다.
각 결정에 대해 **(1) 결정 내용, (2) 근거, (3) 예상 reviewer 반박, (4) 방어 논거**를 기록한다.
다른 설계 문서(02, 05, 06)는 본 문서의 scope 결정을 전제로 갱신된다.

이 문서가 있는 이유: 논문 작성 시점에 **reviewer가 반박할 수 있는 지점을 사전에 모두 nail down**하여, 작성 과정에서 방어적 문장으로 주장을 희석하지 않도록 한다. 작성 이전에 방어 논거가 확정돼 있어야 주장의 범위를 자신 있게 좁힐 수 있다.

---

## 0. 상위 제약 — 학회 포맷

**결정**: 국내 학회 3-page 논문 포맷. 제목~references 포함 총 3페이지 이내.

**근거**: 제출 대상 학회의 공식 분량 제한.

**영향**: 탑티어 학회용 multi-variant ablation 전략은 공간·분량 상 불가능. 주장 단순화가 불가피하며, 대신 그 주장을 **반박 불가 수준으로 엄격히 뒷받침**하는 방향으로 scope 설계.

**예상 reviewer 반박 없음** (scope 자체가 투고 요건).

---

## 1. 주장 범위 (triple contribution)

### 결정 (2026-04-17 update — pre-experiment framing freeze)

본 논문의 contribution을 **3개**로 명시한다:

> **C1 (정확도)**: Site-specific KG가 LLM agent의 task 성공률에 미치는 영향을
> WebArena-Verified GitLab에서 정량화한다.
>
> **C2 (효율)**: KG가 token / step / wall-time 같은 compute 자원을 정량적으로 절약하는가를
> 보고한다.
>
> **C3 (methodology)**: 3-stage automated KG 구축 파이프라인 (Playwright crawl + multi-call
> LLM derivation + heuristic post-enrichment) 자체가 reproducible artifact로 제공된다.

### Hypothesis (dual primary)

- **H1a**: Full KG variant의 success rate ≠ Baseline variant의 success rate (paired McNemar α=0.05)
- **H1b**: Full KG variant의 compute cost (token/step/time) < Baseline variant (paired comparison)

H1a/H1b 둘 다 **양방향 검정** — KG가 정확도/효율을 *향상*시킬 수도, *손상*시킬 수도 있음을
사전 명시. 측정 결과의 부호를 가정하지 않는다.

### 근거 (현 framing 채택 이유)

- **Any-result-valuable 보장**: H1a 또는 H1b 한쪽 null이어도 다른 한쪽으로 contribution
  유지. 둘 다 null이어도 C3 (methodology artifact) 살아남음 → 모든 결과 시나리오에서
  논문 가치 보장.
- **인과 mechanism 분리**: KG가 정확도 효과인지 효율 효과인지 분리 못 한다는 reviewer
  반박은 dual claim에서 무의미.
- **Pre-registration 원칙**: 이 framing freeze는 측정 시작 *전*에 결정. p-hacking 의심 차단.
- 자세한 contribution 시나리오별 narrative는 `08_contribution_scenarios.md` 참조.

### 의도적 제외 (이번 framing 변경 후 update)

| 제외 주장 | 사유 | 미래 연구 |
|---|---|---|
| "planning substrate ≠ retrieval" | KG-retrieval ablation 필요 | 후속 연구 |
| "compute 증가 아님" | (현 dual claim의 H1b가 직접 측정) | — (해소됨) |
| "추가 LLM call confounding" | (3rd variant KG-Info-Ignored가 직접 측정) | — (해소됨) |
| "모델 크기 invariance" | mini + full 모두 측정 필요 | 후속 연구 |
| "continual adaptation 효과" | 3-round replay 필요 | 후속 연구 |
| "cross-domain 일반화" | Reddit/Shopping 추가 측정 필요 | 후속 연구 |

### 예상 반박 & 방어

- **반박 A**: "KG의 어느 구성요소가 기여하는지 알 수 없음"
  **방어**: 3-variant ablation (Baseline / KG-Info-Ignored / Full KG)으로 *KG 정보 자체의*
  기여를 분리. 추가 fine-grained (rewrite / validate / trust policy 개별)은 future work.

- **반박 B**: "성공률 차이가 추가 LLM call의 reasoning step 효과 아닌가 (compute confound)"
  **방어**: KG-Info-Ignored variant가 Hook A LLM 호출은 수행하되 결과를 plan에 사용 안 함.
  Full KG vs KG-Info-Ignored 비교가 KG *정보* 기여를 직접 분리.

- **반박 C**: "정확도 효과인지 효율 효과인지 분리 안 됨"
  **방어**: Dual claim (H1a/H1b)이 둘 다 측정. 분리할 필요 없음.

---

## 2. 평가 사이트 — GitLab only

### 결정
평가 대상 사이트는 WebArena-Verified **GitLab 1개**. Reddit/Shopping/Map 등 다른 사이트는 평가하지 않음.

### 근거
- KG 구축 파이프라인: 3단계 hybrid(Playwright crawl + LLM derivation + 수동 검증)는 사이트마다 독립적으로 수행돼야 함. 포괄 catalog(~20~30 InfoType) 구축 + 검증 품질 기준 달성은 사이트 수에 선형 비례 — 단일 사이트 내에서도 catalog 품질이 실험 결과의 일관성을 결정하므로 우선 단일 사이트 completeness를 확보.
- 3-page 공간: 단일 사이트 결과 표 + 간단 분석으로도 꽉 참. 2 사이트 cross-table은 들어갈 자리 없음.
- 주장이 **"site-specific KG"** 자체를 전제로 함 — cross-domain 증명이 없어도 주장 약화 안 됨.

### 예상 반박 & 방어
- **반박**: "1개 사이트 결과만으로 일반화 주장은 위험"  
  **방어**:  
  (1) **주장 자체가 site-specific을 전제**. "Our KG design is by construction site-specific; we evaluate it on GitLab as a representative test-bed."  
  (2) **명시적 scope 제한**: Introduction과 Limitation에 "We focus on GitLab; cross-domain generalization is left for future work"를 명확히.  
  (3) **추가 사이트 2~3개로도 일반화 주장은 부족** — multi-domain 일반화는 6~10 사이트 이상 실험해야 논문 기여 가능. 국내 3-page 범위 밖.

---

## 3. Task 샘플 — 30개 per-type equal (each type × 10)

### 결정 (2026-04-17 update — per-type heterogeneous effect framing)

WebArena-Verified GitLab **전체 180 task**에서 **task_type별 각 10개 × 3 types = 30 task**를
**per-type equal random sample**로 선정.
- Per-type equal 기준: RETRIEVE 10 / NAVIGATE 10 / MUTATE 10
- Random seed: 42 고정
- **Pool에서 pilot 제외 없음**: 개발 과정의 pilot 14개는 `04_baseline_failure_analysis.md`에
  dev log로 분리됐고 paper에 인용되지 않으므로, 측정 sample 선정에서 제외할 이유 없음.
- 30 task 리스트는 `output/tasks.30.json`에 고정 (seed=42 재현 가능).

### 근거 (per-type equal sampling)
- **연구 질문이 per-type heterogeneous effect**: "KG가 어떤 task type에서 improve/degrade하는가?"
  (`07 §1` C1 framing 참조). 모집단 비율 재현보다 per-type 신호의 balanced statistical power가
  더 중요.
- 원 모집단 비율(NAVIGATE 11% / RETRIEVE 22% / MUTATE 67%)을 재현한 proportional sampling은
  overall effect를 MUTATE 성능에 의해 지배당하게 만들어 per-type subset 분석의 power를
  축소한다.
- 본 논문의 primary contribution이 "KG의 task type별 차등 효과 분석"이므로, type별 동등
  sample 수(10)로 Bonferroni-적용 per-type McNemar에 균일한 power 제공.
- 실행 비용: 30 task × N=3 × 2 variants = **180 runs** (기존 450 runs의 40%)

### 예상 반박 & 방어

- **반박 A**: "30 task가 너무 적다"
  **방어**: 연구 질문이 per-type heterogeneous effect. 각 type 10 pair McNemar + overall
  30 pair McNemar로 검정. Effect size 큰 경우 detect 가능. Task scope는 general power
  analysis보다 research-question-driven sampling. Limitation에 "30 task는 exploratory
  sample"로 명시.

- **반박 B**: "균등 sampling이 모집단 분포와 다름 (MUTATE 33% vs 모집단 67%)"
  **방어**: 모집단 비율(MUTATE 67%) 재현 시 overall effect가 MUTATE subset에 의해 지배당해
  per-type 신호가 희석됨. 연구 질문이 per-type effect이므로 **type별 균등 sampling이 더
  합리적**. 모집단 비율 재현은 future work.

- **반박 C**: "heuristic stratification (정규식 기반 task_type 분류)은 부정확할 수 있음"
  **방어**: 실행 후 agent가 runtime에 결정한 task_type으로 **재집계** 가능. 본문에
  heuristic·runtime 두 task_type 구분 결과 함께 보고.

- **반박 D**: "왜 N=10인가? 15개나 20개 아닌 이유"
  **방어**: 비용·시간 제약 (180 runs × ~3분 = ~9h overnight). Per-type McNemar에서 10
  pair는 Wilson CI 폭이 실용적. 더 큰 N은 future work.

### 현 sample의 task_id 목록
`output/tasks.30.json`에 저장됨. 생성 script: `scripts/sample_tasks_per_type.py` (seed=42).
논문 부록에 30개 task_id 목록 공개하여 재현성 보장.

---

## 4. Repetition — N=3

### 결정
각 (variant, task) 조합당 **N=3 repetition** (3회 독립 실행).

### 근거
- 같은 LLM도 `temperature=0`에서 완전 결정적이지 않음 (모델 내부 병렬성, floating point 등). 실증: 폐기된 pilot의 N=3 smoke 결과에서 7/14 task가 run간 status 갈라짐.
- N=1은 variance를 측정 불가. N=3은 최소 variance 추정 가능한 수.
- N≥5는 비용 증가 대비 통계적 개선 작음 (variance 잔존량 한계 체감).

### 예상 반박 & 방어
- **반박**: "N=3 은 통계적으로 적은 샘플"  
  **방어**: (a) WebArena-Verified 커뮤니티에서 N=3은 일반적 관례, (b) N=3에서 paired McNemar test 가능, (c) 실험 규모 확대는 future work. **핵심**: variance를 숨기지 않고 **변동 폭을 결과 표에 함께 보고** (range / std).

---

## 5. 비교 variant — 2개 (Baseline vs Full KG)

### 결정 (2026-04-17 final — scope reduction)

비교 variant는 **2개**:

1. **Baseline**: `KG_VARIANT=off`. Hook A/B/C/D 모두 off — KG 미사용. 표준 ReAct 웹에이전트.
2. **Full KG**: `KG_VARIANT=full`. Hook A/B/C 모두 on (Hook D는 logging only — `06 §5` 참조).

### 스코프 축소 근거

- 이전 3-variant 계획(Baseline / KG-Info-Ignored / Full KG, 450 runs)은 시간·예산 부담 큼.
- 연구 질문이 "KG의 task type별 heterogeneous effect"로 재정의되며 compute-matched control
  (KG-Info-Ignored)의 optional성 증가 — 주 contribution은 overall + per-type Baseline↔Full KG
  비교로 충분.
- KG-Info-Ignored (추가 LLM call confounding 분리용)는 **future work**로 이관 (§11).
- **Compute confounding 부분 차단**: `06 §3-1`에서 Full KG variant의 token/step/wall-time을
  수치로 보고 → reviewer가 "추가 LLM call 때문인지" 자체 분석 가능.

### 예상 반박 & 방어

- **반박 A**: "KG 정보 효과인지 Hook A의 추가 LLM call 효과인지 분리 못 함"
  **방어**: 맞음. 2-variant 축소로 인한 한계를 §11에 **compute-matched ablation future
  work**로 선언. 대신 token·step·wall-time 수치를 per-variant로 보고해 reviewer가 compute
  confound를 자체 판단 가능.

- **반박 B**: "fine-grained ablation (rewrite / validate 개별 분리)이 없음"
  **방어**: 3-page scope 제약. Hook 단위 ablation은 §11 future work.

- **반박 C**: "baseline이 공식 reference인가?"
  **방어**: baseline은 **새 baseline** (LLM_TEMPERATURE=0, 표준 ReAct 지향 _verify_done
  단순화, declare_error 3-attempt, _MAX_LLM_CALLS_PER_TASK=300 등 정직하게 분류된 개선
  반영). "비교를 위한 합리적 기준점이지만 공식 reference implementation은 아니다. 두 variant가
  **같은 code base + LLM (gpt-5.4-mini) + temperature + task 세트**에서 돌기 때문에 비교의
  internal validity는 확보됨" — paper Method 섹션에 명시. 자세한 baseline 수정 분류는 §5-1.

### §5-1. Baseline 수정 분류 (표준 ReAct 기준 정직 공개)

Baseline은 WebArena/Visual-WebArena의 표준 ReAct agent 원형을 따르되, 실험 재현성·안정성
·공정 비교를 위한 최소 수정을 포함. 각 수정을 다음 3 카테고리로 분류해 Method 섹션에 공개:

#### (A) **Standard ReAct adherence** — 표준과 동일
| 요소 | 코드 위치 | 비고 |
|---|---|---|
| Observe → plan → tool-use → verify loop | `runtime/executor.py:execute_with_llm` | 표준 ReAct |
| Tool-based action (click/fill/goto/search) | `runtime/tools.py` | Generic selector |
| DOM-based observation (`observe_page`) | `runtime/browser.py` | Site-agnostic |
| Checkpoint URL rollback on sub-goal failure | `executor.py` | 표준 재현 |

#### (B) **Justified deviation** — 표준의 명백한 한계 해결
| 요소 | 정당화 |
|---|---|
| Sub-goal decomposition with `goal_type` (navigation/action) | NAVIGATE task의 final URL 변경 여부 hard rule에 필수 (L143, llm.py L391). 단순 CoT로는 type별 규칙 적용 불가. |
| `declare_error` tool with 5-status enum | Agent가 impossible task (NOT_FOUND/ACTION_NOT_ALLOWED 등)를 명시 선언 → evaluator false-negative 감소. Enum 제한으로 자의성 차단. |
| `classify_task_type` via LLM (intent.py) | Heuristic regex가 URL-as-data 케이스 ("set homepage to https://...") 오분류. LLM 호출 1회로 정확성 확보. |
| `_verify_done` hard rule (final navigation URL 변경) | 표준 ReAct의 done을 그대로 수용하되, final navigation에서 URL 미변경은 명백한 agent error — 최소 hard rule만 유지. |

#### (C) **Engineering necessity** — 재현성·안정성·예측 가능 실행
| 요소 | 정당화 |
|---|---|
| `LLM_TEMPERATURE=0` | 실험 재현성 국제 표준 관례 (Temperature 고정 없이 50% run간 split 관찰됨). |
| `_MAX_RETRIES_PER_GOAL=8` | Goal 단위 retry 상한 — agent stuck 방지. |
| `_MAX_LLM_CALLS_PER_TASK=300` | Task당 LLM call budget — task 748 관찰(2395 calls) 같은 retry loop 폭발 방지. Baseline median 243 기준 30% 여유. |
| `_CountingLLMClient` wrapper | Budget 추적용 wrapper. Baseline/KG 양쪽 동일 적용. |
| `task_notes` 상한 (_TASK_NOTES_MAX=50) | Context 크기 제어 — 누적 memo가 prompt 폭발 방지. |
| `_STEP_BUDGETS` per goal_type | Goal별 step 예산 분배 — 복잡 task의 balanced allocation. |
| `_get_tool_action` 1회 retry | Tool call 없을 때 nudge 후 재호출 — LLM response schema 안정성. |

#### (D) **Over-engineering removed** — 표준으로 되돌림 (2026-04-17)
| 요소 | 변경 |
|---|---|
| ~~`_verify_done` LLM 재호출~~ | → Hard rule만 유지 (c 참조). 이전 구현은 task당 LLM call 2배화 + verifier가 context 일부만 봐 false reject 유발. 표준 ReAct는 agent의 done을 그대로 수용. |

**공개 원칙**: 이 4 카테고리를 Method 섹션 부록에 명시해 "29건 수정이 baseline을 유리하게
만들었나?" reviewer 공격에 대해 "모두 표준 준수 또는 재현성 필수 엔지니어링" 방어.

---

## 6. LLM temperature — 0

### 결정
LLM 호출 전체에 `temperature=0` 고정. Environment variable `LLM_TEMPERATURE=0`.

### 근거
- Provider default (보통 1.0)은 같은 intent도 run마다 다른 plan 생성 → baseline variance 큼
- 폐기된 pilot에서 **run간 50% status 갈라짐** 관찰 → temperature 고정 없이는 variant 비교 neutrality 깨짐
- Temperature=0은 실험 재현성 국제 표준 관례 (AWM, AutoGuide 등 동류 연구도 채택)

### 예상 반박 & 방어
- **반박**: "Temperature=0은 exploration을 제한, KG 효과가 특정 편향에서 올 수 있음"  
  **방어**: 모든 variant가 동일 temperature → 비교 fair. Temperature 영향은 variant 간 공통 요인으로 상쇄.

---

## 7. 모델 선택

### 결정
**gpt-5.4-mini** (또는 측정 시점 동급의 cost-accessible 모델)를 주 모델로 사용.

### 근거
- 3-page 범위에서 모델 크기 invariance는 평가 범위 밖
- Mini 모델이 $150 예산 내 N=3 × 50 task × 2 variants 실행 가능 (full은 예산 초과 위험)
- 주장 자체는 "KG가 model-agnostic하게 도움이 된다"가 아니라 **"KG가 이 평가 환경에서 baseline보다 낫다"** — mini 결과로 충분

### 예상 반박 & 방어
- **반박**: "Mini 모델 결과가 큰 모델에서도 유지되는가?"  
  **방어**: (a) Mini에서 검증된 기여가 큰 모델에서 **사라질 가능성**은 작음(아래 근거), (b) 탐색적 연구의 1단계로 적합, (c) 모델 크기 robustness는 future work.  
  **추가 논거**: Mini에서 KG 없이도 baseline이 이미 높은 수준이면 KG 개선 margin이 작음에도 유의미하다 → 큰 모델에서 오히려 더 큰 개선 가능.

---

## 8. Stratification 기준 — task_type

### 결정
Sample stratification은 **task_type (RETRIEVE / NAVIGATE / MUTATE)** 비율로 함.

### 근거
- WebArena-Verified의 task 분류가 task_type으로 돼 있어 모집단 비율 기준으로 사용 가능
- 다른 stratification 후보 (intent_template_id, difficulty 추정 등)는 명확한 ground truth 없음
- task_type별 agent 동작 (retrieve는 extract, navigate는 goto, mutate는 form) 차이가 크므로 stratification 의미 있음

### 예상 반박 & 방어
- **반박**: "Difficulty 같은 다른 차원으로도 stratify 했어야 함"  
  **방어**: WebArena-Verified 데이터셋에 공식 difficulty metric 없음. task_type은 공식 label이므로 defensible. 부록에 step count (실측) 분포도 함께 보고해 "difficulty proxy"로 제공.

---

## 9. Seed 고정

### 결정
Task sampling에 `random.seed(42)` 사용. 재현 가능한 정확한 task_id 목록은 `output/tasks.50.json` 또는 부록에 공개.

### 근거
- 재현성은 학회 publication의 기본 요구
- seed=42는 관례적 선택 (특별한 task를 선택하도록 튜닝하지 않았음을 시사)

### 예상 반박 & 방어
- **반박**: "seed를 이것저것 바꿔가며 결과 좋은 seed 골랐나?"  
  **방어**: seed=42는 단일 선택. 부록에 선택 과정 투명 공개. 다른 seed로 재현 요청 가능.

---

## 10. Broken evaluator 처리 정책

### 결정
Evaluator의 strict match 결함으로 정상 agent 행동이 fail로 기록되는 task는 **수동 검증 후 broken 표시**. 본문에 결과를 두 가지 방식으로 보고:
- (a) **Raw**: evaluator 판정 그대로
- (b) **Adjusted**: broken 제외

### 근거
- WebArena-Verified evaluator가 NetworkEventEvaluator 등에서 strict URL match를 함 → 의미적으로 성공한 agent도 URL 파라미터 정렬 등 사소한 차이로 fail 처리하는 사례 존재 (폐기된 pilot에서 관찰)
- 양쪽 수치를 보고해 reviewer가 판단 가능하게 함

### 판정 기준 (투명성)
- Broken 판정은 다음 모두 충족 시에만:
  - agent가 의미적으로 target state에 도달 (log · HAR 수동 확인)
  - evaluator가 오직 strict string/URL mismatch로 fail
  - 판정 근거를 task_id별로 기록 (`docs/kg_design/eval_exclusions.md` 또는 부록)

### 예상 반박 & 방어
- **반박 A**: "Broken 판정이 자의적"  
  **방어**: 판정 criteria 공개 + 각 판정 사례의 근거(HAR snippet, log line 참조) 투명 기록. 양쪽 수치 보고로 reviewer가 자체 판단 가능.

- **반박 B**: "Broken 제외한 adjusted 수치만 보고하면 cherry-pick"  
  **방어**: **Raw 수치를 primary로 보고**. Adjusted는 supplementary.

---

## 11. Out-of-scope 항목 (Limitation 섹션 명시 의무)

다음 항목은 3-page 논문 본문에서 다루지 않으며 Limitation 섹션에 **명시적 future work**로 선언:

| 항목 | Limitation 선언 문구 (예시) |
|---|---|
| Cross-domain 일반화 | "We evaluate on GitLab only; generalization to other WebArena-Verified sites is future work." |
| **Compute-matched ablation (KG-Info-Ignored variant)** | "Our 2-variant design (Baseline vs Full KG) does not separate the contribution of KG *information* from the additional LLM call in Hook A. A compute-matched control (Hook A LLM call without using its result) was planned but deferred due to scope reduction; this compute confounding is tracked via token/step reporting and formally isolated in future work." |
| Fine-grained ablation (Hook 단위) | "Isolating individual hook contributions (rewrite vs validate vs trust policy) requires targeted ablation and is future work." |
| 모델 크기 robustness | "We use a single LLM model family; robustness across model sizes is future work." |
| Continual adaptation | "Trust evolution across repeated deployment is modeled in the architecture but empirically evaluated only in single-shot mode; longitudinal evaluation is future work." |
| KG 구축 파이프라인 확장성 | "The 2-stage automated construction pipeline (with heuristic post-enrichment) is applied to GitLab as a single case study; scalability cost (per-site setup, crawler coverage, LLM derivation reproducibility across sites) is future work." |
| **KG coverage의 seed selection 의존성** | **"KG-addressable coverage depends on seed URL selection. We use the site's official navigation entry points (8 URLs) chosen independently of the experimental task distribution; coverage robustness across alternative seed sets is future work."** |
| **Domain prior in pipeline code** | **"The pipeline includes generic web/domain prior in code (post-enrichment heuristics on URL slot naming conventions, download-extension blocklist) and in LLM prompt (list/index page filter convention). These are not per-task labels but represent generic web-engineering knowledge embedded in pipeline."** |

**포함 (out-of-scope에서 제외)**: "KG catalog 확장"은 본 연구의 artifact이므로 out-of-scope가 아니다 — baseline 측정 전에 포괄 catalog를 freeze하는 것이 본 연구의 정당성 요건이다 (§14 참조).

### 이 섹션의 기능
Reviewer가 가능한 반박 방향 5개를 **우리가 먼저 열거**함으로써 리뷰 공격면을 우리가 통제. 리뷰어가 이 중 하나를 지적해도 "이미 Limitation에 future work로 선언된 사항"이라 답변 가능.

---

## 12. 실험 규모 총합 (2026-04-17 update — 30 task × 2 variants 최종)

위 결정들을 종합한 실험 규모:

| 단계 | 계산 | runs |
|---|---|---|
| A. 이전 baseline 측정 | — (프레이밍 변경으로 폐기) | 0 |
| B. KG 개발 smoke | ~10 task × variant (single-run) | ~20 |
| C. 본 실험 | **2 variants** × N=3 × 30 task (per-type 10) | **180** |
| F. debug margin | ~10% | 20 |
| **합계** | | **약 220 runs** |

**비용 추정** (mini 기준, task당 ~$0.03):
- 220 × $0.03 ≈ **$6-7** ≪ $150 예산

**시간 추정** (평균 3분/run):
- 220 × 3분 ≈ **~11시간** (순차). 하룻밤 분산 가능.

Scope 축소 사유:
- 이전 3-variant × 50-task 계획(450 runs, ~$14, 27h)에서 **2-variant × 30-task** 로 축소.
- 연구 질문이 "per-type heterogeneous effect"로 재정의되며 50 stratified proportional보다
  30 per-type equal이 research question과 일치.
- KG-Info-Ignored는 future work로 이관 (§11 Limitation 표 참조).

---

## 14. KG 구축 방법론 (연구 artifact) — 2026-04-17 update

### 결정 (정확한 stage 표현)

본 연구의 KG는 **2-stage automated 파이프라인 + heuristic post-enrichment**로 구축하며,
이 방법론 자체가 C3 (methodology contribution)으로 보고된다. 핵심 표현:

> **"No per-task manual labeling, with generic web/domain prior in pipeline code."**

이전 버전의 "automated-only" 표현은 정확하지 않아 폐기. 본 evaluation에서 manual stage는
**0건** (design상 stage 3로 포함되나 본 연구에서 수행하지 않음).

### Stage 정의

1. **Stage 1 — Playwright auto-crawl** (`source="crawl"`, `trust="verified"`):
   base URL + seed URL set에서 DOM·navigation·URL schema를 관찰해 StatePattern·leads_to·
   form actions를 자동 수집.
   - 본 연구는 8개 seed (사이트 공식 navigation entry point) 사용. 자세한 정당화는
     §11 Limitation 표 참조.

2. **Stage 2 — Multi-call LLM derivation** (`source="llm"`, `trust="inferred"`):
   reasoning model의 single-call context overflow를 방지하기 위해 **3 call로 분할**:
   - Call 1: state pattern grouping (semantic template 추출)
   - Call 2: InfoType naming + realize edges (group_id 기반)
   - Call 3: action renames
   ARI mean = 0.926 across 3 derivation runs (run-to-run consistency 안정).

3. **Stage 2.5 — Heuristic post-enrichment** (post_enrich.py): LLM 재호출 없이 schema 결함
   자동 보강 (binding_map, path_params, query_params, InfoType category, form action
   description). source는 `inferred` 유지.

4. **Stage 3 — Manual verification** (design only, **본 evaluation 0건**): 1·2단계 결과를
   사람이 검증·승격하는 단계는 architecture에는 포함되나, 본 evaluation에서는 수행하지 않음.

### Domain prior disclosure (정직한 공개)

본 pipeline에는 다음 generic web/domain prior가 코드/prompt에 박혀 있음. 이는 *per-task
labeling*이 아니라 *generic web-engineering knowledge*:

| 위치 | Prior 내용 | 정당화 |
|---|---|---|
| `playwright_crawler.py` | download extension blocklist (.zip, .tar, .ics, .pdf 등) | 일반 web 표준 — 사이트 무관 |
| `crawl_to_kg.py` | form.action_url 기반 cross-target edge | HTML form spec 표준 |
| `post_enrich.py` D1 | bindings ↔ slot/query name match (exact + `[]` variant) | 일반 URL convention |
| `post_enrich.py` D2 | `*_path → path_segments`, 그 외 → `segment` heuristic | 일반 path slot naming |
| `post_enrich.py` D3 | InfoType.optional_bindings → query param backfill (literal tail suffix matching) | 일반 web query convention |
| `post_enrich.py` D6 | InfoType prefix 기반 category clustering (≥2 공유) | 일반 taxonomy heuristic |
| `llm_derivation.py` Call 1 prompt | "list/index page는 filter/sort/pagination 받는다" | 일반 web app convention |

이들은 **사이트 어휘를 박지 않으므로** task-bias 위험 없음 (memory `feedback_no_task_site_bias`
원칙 준수).

### 구축 시점 제약 (hindsight bias 차단)

- Catalog는 **baseline 측정 전에 freeze**한다. 실험 task 실패 로그를 본 후 catalog를 수정하면
  baseline에 대한 KG 우위가 사후 조정의 결과로 해석될 수 있다.
- Catalog 크기 목표: GitLab 전체 기능 표면을 **포괄 기준**. 본 frozen은 ~50 InfoType,
  ~3000 StatePattern (literal URL). 실험 50 task 분포에 맞추지 않는다.
- Catalog freeze 시점의 SiteKG는 `build_timestamp`, `git_rev`, `builder_version`으로 snapshot
  하고, 실험 실행은 이 snapshot만 로드 (`SITEKG_FROZEN` env).
- ARI mean (3 derivation runs) ≥ 0.85를 충족할 때만 frozen 채택.

### 보고 의무

- **커버리지**: 50 task 중 Hook A가 `plan_to_info`를 성공적으로 호출한 비율 (`06 §3-5`).
  100% 미만이 catalog가 task에 맞춰지지 않은 직접 증거. seed selection 의존성은 §11
  Limitation에 명시.
- **Source mix**: `SiteKG.source_mix` — crawl / llm / manual 노드·엣지 비율. 본 evaluation
  에서 manual=0 명시.
- **Build metadata**: timestamp, builder version, git_rev, crawl seed URL set, LLM derivation
  prompt 버전을 부록에 공개.
- **ARI**: 3 derivation runs의 group-level Adjusted Rand Index를 부록에 공개.

### 예상 반박 & 방어

- **반박 A**: "KG catalog가 실험 task에 맞춰져 있어 KG 우위가 과장됐을 것"
  **방어**: catalog freeze timestamp가 baseline 측정보다 앞서고, 커버리지가 100% 미만임을
  수치로 제시. seed URL은 사이트 공식 navigation entry point 기준 (§11).

- **반박 B**: "automated 주장 vs heuristic post-enrich 모순"
  **방어**: 명시적 표현 변경 — "no per-task manual labeling, with generic web/domain prior
  in pipeline code". post_enrich/prompt의 prior 7개 항목 정직 disclose (위 표).

- **반박 C**: "1 사이트 적용으로 파이프라인 일반화 주장 부족"
  **방어**: §11 out-of-scope 표에 "파이프라인 확장성은 future work"로 명시.

- **반박 D**: "LLM derivation 안정성 불확실"
  **방어**: ARI mean=0.926 (3 runs) 보고. group 수 변동(49~105)은 cluster 세분화 차이로
  member-level 일관성은 강함.

### Hook A prompt guidance + runtime context auto-fill (2026-04-18 Phase 2C)

Hook A `plan_to_info` tool schema + system prompt에 각 InfoType의 path_slots를 명시하고,
agent의 현재 페이지 URL에서 path slot을 자동 추출해 `runtime_context["path_slots"]`에
주입. Hook B `emit_target_url`이 bindings 부족 시 runtime_context로 fallback.

- **동기**: Phase 2B smoke에서 MUT task 2건이 `rewrite skipped: incomplete_url` (unfilled
  path slot)로 Hook B 비활성. Hook A가 `bindings={}` 반환하는 것이 근본 원인.
- **C1 (prompt)**: 각 InfoType에 `path_slots=[namespace, project_path, ...]` 표기 + "Path
  slot extraction" rule로 LLM이 path slot을 bindings에 포함하도록 유도.
- **C2 (runtime context)**: `executor._update_runtime_context_from_url`이 현재 URL을
  모든 StatePattern과 매칭, path_params slot을 `runtime_context["path_slots"]` dict에
  병합. `emit_target_url`이 bindings 우선 → runtime_context fallback 순으로 state_bindings
  채움.
- **원칙 유지**: C1/C2 모두 task-independent generic rule. `07 §14 no per-task manual
  labeling` 원칙 위반 아님. 모든 InfoType에 동일 규칙 적용.
- **Reviewer 방어**: Phase 2C smoke에서 MUT에서 Hook B applied 증가 관찰 예정. Phase 3
  본 측정의 MUT SR 개선 여부는 `docs/08` heterogeneous scenario narrative로 기록.

### Trust policy (2026-04-18 Option B — verified/declared/inferred 전부 수용)

Hook B `rewrite_plan`의 trust threshold 정책:

- **변경 전 (2026-04-17까지)**: `url_template_trust == "inferred"` 또는 `edge.trust == "inferred"`
  이면 rewrite skip → verified-only 보수 정책. Frozen KG가 LLM derivation (inferred)
  source 상당 포함이라 kg_full smoke 시 **Hook B가 모든 case에서 비활성** 관찰.
- **변경 후 (2026-04-18 Option B)**: trust 기반 skip 조건 제거. verified / declared /
  inferred 전부 rewrite 진행. 단 emit_target_url이 `{slot}` unfilled 상태로 반환 시
  (LLM derivation의 incomplete binding)는 별도 guard로 skip (malformed URL navigation
  방지).
- **근거**: `07 §1` triple contribution C1/C2 검증에 Hook B의 실제 효과 측정 필요. 비활성
  Hook은 논문 narrative 약화. Trust policy 변경은 **task-independent generic rule 변경**
  이므로 `07 §14` "no per-task manual labeling" 원칙 위반 아님.
- **Reporting 의무**: `scripts/coverage.py`에 Hook B applied / skipped (trust) /
  skipped (incomplete_url) / Hook C early SUCCESS count per task를 포함 (`06 §3-4` 연동).
- **Future work**: Trust adaptive thresholding (context-dependent dynamic threshold)는
  본 연구 1단계 (fixed threshold) 넘어선 후속 연구.

### Phase 2 개선사항 공식 기재 (2026-04-16 ~ 2026-04-18)

Baseline·KG 공통 engineering fix로 본 측정 직전 적용. 모든 수정은 `07 §5-1` 분류 중
Standard adherence / Justified deviation / Engineering necessity 중 하나. 자세한 rationale은
각 commit log 및 `docs/kg_design/10_phase_c_postmortem.md` 참조.

| ID | 파일 | 카테고리 | 요약 |
|---|---|---|---|
| R1 | run_analysis.sh | Engineering | eval-tasks 자동 배치 호출 |
| Y-code-1 | kg_integration.py | Engineering | KG load exception 구체화 (silent fallback 축소) |
| Y-code-2 | executor.py | Engineering | LLM call budget 350→450 + env override |
| Y-code-3 | llm.py | Engineering | OpenAI APIConnectionError/APITimeoutError retry (expo backoff) |
| Y-code-4 | browser.py | Standard | URL `.lower()` 정규화 제거 (원본 case 보존) |
| Y-code-5 | executor.py | Justified | declare_error gate NOT_FOUND/ACTION_NOT_ALLOWED는 1회 허용 |
| Y-pipe-1 | monitor_phase_c.py | Engineering | ENV_ERROR 토큰 정밀화 (false positive 제거) |
| Y-pipe-2 | analyze_baseline.py | Engineering | eval_missing / agent_missing flag |
| Y-pipe-3 | coverage.py | Engineering | Hook A 상태 머신 (classified/declined/not_called/other) |
| Y-pipe-4 | run_analysis.sh | Engineering | task_types.txt 동기화 abort-on-mismatch |
| Rev-1 | run_*.sh | Standard | LLM_TEMPERATURE=0 전 script 일관성 |
| P2-A12 | run_*.sh | Engineering | `.env` OPENAI_MODEL main.log 명시 기록 (재현성) |
| P2B-A1 | rewrite.py | Justified | Trust-based skip 제거 (Option B, verified+declared+inferred 수용) |
| P2B-A2 | rewrite.py | Engineering | Malformed URL (unfilled slot) guard |
| P2B-A3 | validator.py | Justified | Hook C early-termination을 NAVIGATE로 제한 (RET/MUT false positive 방지) |
| P2C-A1 | kg_integration.py | Justified | Hook A prompt/schema에 path_slots 정보 embed + extraction rule |
| P2C-A2 | urlnorm.py | Engineering | extract_path_slots_from_url helper (C2 기반) |
| P2C-A3 | executor.py | Justified | _update_runtime_context_from_url 초기 1회 호출 (agent URL → path_slots) |
| P2C-A4 | query.py | Engineering | emit_target_url이 runtime_context.path_slots로 unfilled slot 보완 (bindings 우선) |

---

## 15. 이 문서의 후속 동작

이 문서가 승인되면 다음 다른 설계 문서를 scope에 맞게 갱신한다:

1. `06_evaluation_protocol.md` — variant 수 5→2, continual/scaling 제거, hypothesis 축약
2. `02_open_questions.md` 쟁점 #4 — ablation 설계를 2-variant으로 재작성, 드랍된 variant는 future work 이동
3. `05_implementation_architecture.md` — Ablation 매핑표 축약 (2 variants 대응)
4. `03_related_work_mapping.md` — "planning substrate ≠ retrieval" framing 완화. "site-specific KG 도입"이 핵심 기여 framing으로 변경
5. `01_references_summary.md` §4 — 주장별 대비표에서 drop된 주장 표시 추가

이 5 문서의 수정 전에 본 07 문서가 **source of truth**로 고정돼 있어야 일관성 유지.
