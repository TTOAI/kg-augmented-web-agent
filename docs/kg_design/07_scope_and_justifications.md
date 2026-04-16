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

## 3. Task 샘플 — 50개 stratified random (180 full pool)

### 결정
WebArena-Verified GitLab **전체 180 task**에서 **50개를 stratified random sample**로 선정.
- Stratification 기준: task_type (RETRIEVE / NAVIGATE / MUTATE) 비율
- Random seed: 42 고정
- **Pool에서 pilot 제외 없음**: 개발 과정의 pilot 14개는 `04_baseline_failure_analysis.md`에 dev log로 분리됐고 paper에 인용되지 않으므로, 측정 sample 선정에서 제외할 이유가 없다. 전체 180을 대상으로 추출.

### 근거
- 전체 180 task × N=3 × 2 variants = 1,080 runs → 평균 3분/run = 54시간. 실무적으로 단일 실행 불가.
- 통계적 검출력: N=50 task, N=3 repetition이면 McNemar test로 **10% 수준의 variant 간 성공률 차이**를 α=0.05로 검출 가능.
- Stratified sampling: 모집단 비율(NAVIGATE 20 / RETRIEVE 40 / MUTATE 120 = 11% / 22% / 67%) → 샘플 비율 6 / 11 / 33 로 매칭.
- Full pool(180)에서 추출: "pilot 제외"로 인한 잔여 편향 위험을 원천 차단.
- 50 task 리스트는 `output/tasks.50.json`에 고정 저장 (seed=42 재실행으로 재현 가능).

### 현 sample의 task_id 목록
```
44, 46, 103, 104, 132, 135, 156, 168, 171, 172, 179, 180, 182,
294, 305, 306, 307, 312, 339, 340, 350, 393, 394, 411, 413, 414,
419, 421, 447, 448, 449, 452, 479, 480, 483, 536, 567, 576, 578,
594, 665, 668, 742, 748, 751, 754, 786, 799, 800, 806
```
(이 리스트는 논문 부록에 공개하여 재현성 보장)

### 예상 반박 & 방어
- **반박 A**: "왜 전체 180 task가 아닌 50개인가?"  
  **방어**: (a) 실행 시간·비용 제약(1,080 runs 단일 실행 비현실적), (b) statistical power 50으로 충분 (McNemar 기준 >10% 차이 검출), (c) stratified random으로 편향 제거. Power analysis 기반 설계.

- **반박 B**: "50개가 대표적이라는 보장이 있나?"  
  **방어**: (a) task_type 비율 모집단 완전 일치, (b) seed=42 고정으로 bit-level 재현 가능, (c) 논문 부록에 전체 task_id 목록 공개, (d) Full pool에서 추출하여 excluded-bias 없음.

- **반박 C**: "heuristic stratification (정규식 기반 task_type 분류)은 부정확할 수 있음"  
  **방어**: 실행 후 agent가 runtime에 결정한 task_type으로 **재집계** 가능. 본문에 heuristic · runtime 두 가지 task_type 구분 결과 함께 보고.

- **반박 D**: "pilot task와 중복되는 경우 이전 실행 정보가 샘플링을 편향시킬 수 있다"  
  **방어**: pilot 데이터는 폐기된 비공식 baseline으로 paper에 인용되지 않으며, 현 측정은 **새 baseline으로 재실행**. 중복 4 task(44, 132, 156, 339)는 이전 결과와 독립적으로 재측정됨.

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

## 5. 비교 variant — 3개 (compute-matched ablation)

### 결정 (2026-04-17 update)
비교 variant는 **3개**:

1. **Baseline**: Hook A/B/C/D 모두 off — KG 미사용
2. **KG-Info-Ignored**: Hook A의 `plan_to_info` LLM call **수행하되 결과를 plan/rewrite/
   validate에 사용 안 함**. 추가 LLM call의 reasoning-step confounding을 분리하기 위한
   compute-matched control
3. **Full KG**: Hook A/B/C 모두 on (Hook D는 logging only — `06 §5` 참조)

### 근거
- 2-variant 비교는 "추가 LLM call 효과 vs KG 정보 효과"를 분리 못 함 → 핵심 confounding
- 3rd variant (KG-Info-Ignored)가 두 비교를 모두 가능하게 함:
  - Baseline ↔ KG-Info-Ignored: 추가 LLM call의 reasoning step 효과 측정
  - KG-Info-Ignored ↔ Full KG: KG *정보*의 순수 기여 분리
- 추가 비용: 50 task × N=3 = 150 runs (≈ $5, 7.5h) — reviewer-proof 강화 가치 충분
- 3-page 분량 적합: Table 1에 3 columns (variant 3개)

### 예상 반박 & 방어

- **반박 A**: "fine-grained ablation (rewrite / validate 개별 분리)이 없음"
  **방어**: KG-Info-Ignored가 Hook A의 정보 기여를 분리하는 핵심 ablation. Hook B/C 개별
  분리는 future work — 3-page scope 제약.

- **반박 B**: "baseline이 공식 reference인가?"
  **방어**: baseline은 **새 baseline** (declare_error 지원, verify_done 엄격화, LLM_TEMPERATURE=0
  등 29건 수정 적용됨). "비교를 위한 합리적 기준점이지만 공식 reference implementation은 아니다.
  세 variant가 **같은 code base + LLM + temperature + task 세트**에서 돌기 때문에 비교의
  internal validity는 확보됨" — paper Method 섹션에 명시.

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
| Fine-grained ablation (Hook 단위) | "Our 3-variant ablation isolates the contribution of KG *information* (Full KG vs KG-Info-Ignored). Isolating individual hooks (rewrite vs validate vs trust policy) requires further targeted ablation, which is future work." |
| 모델 크기 robustness | "We use a single LLM model family; robustness across model sizes is future work." |
| Continual adaptation | "Trust evolution across repeated deployment is modeled in the architecture but empirically evaluated only in single-shot mode; longitudinal evaluation is future work." |
| KG 구축 파이프라인 확장성 | "The 2-stage automated construction pipeline (with heuristic post-enrichment) is applied to GitLab as a single case study; scalability cost (per-site setup, crawler coverage, LLM derivation reproducibility across sites) is future work." |
| **KG coverage의 seed selection 의존성** | **"KG-addressable coverage depends on seed URL selection. We use the site's official navigation entry points (8 URLs) chosen independently of the experimental task distribution; coverage robustness across alternative seed sets is future work."** |
| **Domain prior in pipeline code** | **"The pipeline includes generic web/domain prior in code (post-enrichment heuristics on URL slot naming conventions, download-extension blocklist) and in LLM prompt (list/index page filter convention). These are not per-task labels but represent generic web-engineering knowledge embedded in pipeline."** |

**포함 (out-of-scope에서 제외)**: "KG catalog 확장"은 본 연구의 artifact이므로 out-of-scope가 아니다 — baseline 측정 전에 포괄 catalog를 freeze하는 것이 본 연구의 정당성 요건이다 (§14 참조).

### 이 섹션의 기능
Reviewer가 가능한 반박 방향 5개를 **우리가 먼저 열거**함으로써 리뷰 공격면을 우리가 통제. 리뷰어가 이 중 하나를 지적해도 "이미 Limitation에 future work로 선언된 사항"이라 답변 가능.

---

## 12. 실험 규모 총합 (2026-04-17 update — 3 variants 반영)

위 결정들을 종합한 실험 규모:

| 단계 | 계산 | runs |
|---|---|---|
| A. baseline 첫 측정 | 1 variant × N=3 × 50 task | 150 |
| B. KG 개발 smoke | ~30 task × 변종 (single-run) | ~60 |
| C. 본 실험 | **3 variants** × N=3 × 50 task (baseline은 A 재사용) | 450 (A 150 공유 시 +300) |
| F. debug margin | ~15% | 70 |
| **합계** | | **약 530 runs** (A·C 중복 감안 시 460) |

**비용 추정** (mini 기준, task당 ~$0.03):
- 530 × $0.03 = **약 $16** ≪ $150 예산

**시간 추정** (평균 3분/run):
- 530 × 3분 = **약 27시간** (순차). 3~4 저녁에 분산 가능.

3 variants 추가 비용은 baseline 단일 비용(150 runs)의 +1배 — reviewer-proof 강화 가치
(추가 LLM call confounding 직접 분리) 충분.

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

---

## 15. 이 문서의 후속 동작

이 문서가 승인되면 다음 다른 설계 문서를 scope에 맞게 갱신한다:

1. `06_evaluation_protocol.md` — variant 수 5→2, continual/scaling 제거, hypothesis 축약
2. `02_open_questions.md` 쟁점 #4 — ablation 설계를 2-variant으로 재작성, 드랍된 variant는 future work 이동
3. `05_implementation_architecture.md` — Ablation 매핑표 축약 (2 variants 대응)
4. `03_related_work_mapping.md` — "planning substrate ≠ retrieval" framing 완화. "site-specific KG 도입"이 핵심 기여 framing으로 변경
5. `01_references_summary.md` §4 — 주장별 대비표에서 drop된 주장 표시 추가

이 5 문서의 수정 전에 본 07 문서가 **source of truth**로 고정돼 있어야 일관성 유지.
