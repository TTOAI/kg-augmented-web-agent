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

## 1. 주장 범위 (narrow claim)

### 결정
논문의 핵심 주장을 다음 한 문장으로 좁힌다:

> **"Text-centric web agent에 site-specific Knowledge Graph를 결합하면, WebArena-Verified GitLab task에서 baseline 대비 task 성공률이 유의미하게 향상된다."**

### 근거
- 3-page 분량에서 뒷받침 가능한 주장 밀도는 1개 핵심 주장 + 부속 관찰 수준
- 세분된 주장("KG가 retrieval 아닌 planning substrate", "모델 크기 invariant", "continual adaptation 효과")은 각각 전용 ablation을 요구하며 분량 불가
- 단일 핵심 주장은 **2-variant 비교(Baseline vs Full KG)**로 반박 불가 수준 입증 가능

### 의도적 제외
| 제외 주장 | 탑티어용이라 drop | 미래 연구로 분리 |
|---|---|---|
| "planning substrate ≠ retrieval" | KG-retrieval ablation 필요 | 후속 연구 |
| "compute 증가 아님" | compute-matched ablation 필요 | 후속 연구 (대신 token/step 수치 함께 보고) |
| "모델 크기 invariance" | mini + full 모두 측정 필요 | 후속 연구 |
| "continual adaptation 효과" | 3-round replay 필요 | 후속 연구 |
| "cross-domain 일반화" | Reddit/Shopping 추가 측정 필요 | 후속 연구 |

### 예상 반박 & 방어
- **반박 A**: "KG의 어느 구성요소가 기여하는지 알 수 없음"  
  **방어**: Future Work 섹션에 "fine-grained ablation (rewrite / validate / trust policy 분리)은 후속 연구"를 명시. 3-page scope에서는 KG 도입 자체의 전체적 효과만 주장.

- **반박 B**: "단순 compute 증가 효과일 수 있음"  
  **방어**: Method + Result 섹션에 **token · step · wall-time 수치를 표로 포함**. "Full KG variant의 평균 step은 baseline 대비 X% 수준"을 함께 보고 → ablation 없이 compute confound 사전 차단.

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

## 5. 비교 variant — 2개

### 결정
비교 variant는 **2개**: (1) Baseline (KG 없음), (2) Full KG (Hook A/B/C/D 전부 on).

### 근거
- 3-page 분량에서 5-variant ablation은 표 + 분석이 들어갈 공간이 없음
- 핵심 주장("KG가 baseline을 개선한다")은 2 variant 비교로 충분
- 세분 ablation은 주장을 **강화**하는 것이지 주장의 **성립 조건**이 아님

### 예상 반박 & 방어
- **반박 A**: "ablation 없이 KG의 어느 부분이 기여하는지 알 수 없음"  
  **방어**: 주장의 scope가 "KG 도입 전체"이며, 내부 요소별 기여 분석은 future work. 3-page 포맷상 제약이 명시적.

- **반박 B**: "baseline이 공식 reference인가?"  
  **방어**: baseline은 **새 baseline** (declare_error 지원, verify_done 엄격화, LLM_TEMPERATURE=0 등 29건 수정 적용됨). "비교를 위한 합리적 기준점이지만 공식 reference implementation은 아니다. 두 variant가 **같은 code base + LLM + temperature + task 세트**에서 돌기 때문에 비교의 internal validity는 확보됨" — paper Method 섹션에 명시.

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
| Fine-grained ablation | "Isolating individual contributions of rewrite / validate / trust policy requires targeted ablation, which is future work." |
| Compute-matched baseline | "We report token/step counts alongside success rate; a formal compute-matched ablation is future work." |
| 모델 크기 robustness | "We use a single LLM model family; robustness across model sizes is future work." |
| Continual adaptation | "Trust evolution across repeated deployment is modeled in the architecture but empirically evaluated only in single-shot mode; longitudinal evaluation is future work." |
| KG 구축 파이프라인 확장성 | "The 3-stage hybrid construction pipeline is applied to GitLab as a single case study; scalability cost (human-hours per site, crawler coverage, LLM derivation reproducibility across sites) is future work." |

**포함 (out-of-scope에서 제외)**: "KG catalog 확장"은 본 연구의 artifact이므로 out-of-scope가 아니다 — baseline 측정 전에 포괄 catalog를 freeze하는 것이 본 연구의 정당성 요건이다 (§14 참조).

### 이 섹션의 기능
Reviewer가 가능한 반박 방향 5개를 **우리가 먼저 열거**함으로써 리뷰 공격면을 우리가 통제. 리뷰어가 이 중 하나를 지적해도 "이미 Limitation에 future work로 선언된 사항"이라 답변 가능.

---

## 12. 실험 규모 총합

위 결정들을 종합한 실험 규모:

| 단계 | 계산 | runs |
|---|---|---|
| A. baseline 첫 측정 | 1 variant × N=3 × 50 task | 150 |
| B. KG 개발 smoke | ~30 task × 2 variants (single-run) | ~60 |
| C. 본 실험 | 2 variants × N=3 × 50 task (baseline은 A 재사용 가능) | 300 (이미 150 공유) |
| F. debug margin | ~15% | 60 |
| **합계** | | **약 370 runs** (A·C 중복 감안 시 310) |

**비용 추정** (mini 기준, task당 ~$0.03):
- 370 × $0.03 = **약 $11** ≪ $150 예산

**시간 추정** (평균 3분/run):
- 370 × 3분 = **약 19시간** (순차). 2~3 저녁에 분산 가능.

---

## 14. KG 구축 방법론 (연구 artifact)

### 결정

본 연구의 KG는 **3단계 hybrid 파이프라인**으로 구축하며, 이 방법론 자체가 연구 artifact의 일부로 보고된다.

1. **Playwright auto-crawl** — base URL + seed URL set에서 DOM·navigation·URL schema를 관찰해 StatePattern·leads_to 엣지를 자동 수집. 결과는 `source="crawl"`, `trust="verified"`.
2. **LLM-assisted derivation** — crawl 산출물을 LLM에게 주고 InfoType 후보·description·realizes 매핑·사이트간 공통 일반화를 도출. 결과는 `source="llm"`, `trust="inferred"`.
3. **Manual verification** — 1·2단계 결과를 사람이 검증해 부정확한 항목을 제거·보정·승격. decorative param, identity token, alias 같은 관찰로 잡히지 않는 항목을 채움. 결과는 `source="manual"`, `trust="declared"`.

### 구축 시점 제약 (hindsight bias 차단)

- Catalog는 **baseline 측정 전에 freeze**한다. 실험 task 실패 로그를 본 후 catalog를 수정하면 baseline에 대한 KG 우위가 사후 조정의 결과로 해석될 수 있다.
- Catalog 크기 목표: GitLab 전체 기능 표면을 **포괄 기준**으로 `~20~30 InfoType`, `~30~50 StatePattern`. 실험 50 task 분포에 맞추지 않는다.
- Catalog freeze 시점의 SiteKG는 `build_timestamp`와 `builder_version`으로 snapshot하고, 실험 실행은 이 snapshot만 로드한다.

### 보고 의무

- **커버리지**: 50 task 중 Hook A가 `plan_to_info`를 성공적으로 호출한 비율(§06 §3-5). 100% 미만이어야 "catalog가 task에 맞춰져 있지 않다"는 증거가 됨.
- **Source mix**: `SiteKG.source_mix` — crawl / llm / manual 노드·엣지 비율. 세 source 모두 0이 아닌 분포.
- **Build metadata**: timestamp, builder version, crawl seed URL set, LLM derivation prompt 버전을 부록에 공개.

### 예상 반박 & 방어

- **반박 A**: "KG catalog가 실험 task에 맞춰져 있어 KG 우위가 과장됐을 것"  
  **방어**: catalog freeze timestamp가 baseline 측정보다 앞서고, 커버리지가 100% 미만(즉 task 중 일부는 KG-addressable하지 않음)임을 수치로 제시. 포괄 범위(~20~30 InfoType)는 실험 task 수(50)보다 훨씬 많지 않으며 사이트 기능 표면 기준으로 설정됐음을 §14에 공개.
- **반박 B**: "수동 단계가 있어 재현 불가"  
  **방어**: 수동 단계의 산출물(site_config, infotypes YAML, kg_seed JSON)은 `config/sites/gitlab/`에 공개. source 필드와 build metadata로 어느 항목이 manual 기원인지 투명하게 구분. LLM derivation prompt와 crawl seed URL set도 부록 공개.
- **반박 C**: "1 사이트 적용으로 파이프라인 일반화 주장 부족"  
  **방어**: §11 out-of-scope 표에 "파이프라인 확장성은 future work"로 명시.

---

## 15. 이 문서의 후속 동작

이 문서가 승인되면 다음 다른 설계 문서를 scope에 맞게 갱신한다:

1. `06_evaluation_protocol.md` — variant 수 5→2, continual/scaling 제거, hypothesis 축약
2. `02_open_questions.md` 쟁점 #4 — ablation 설계를 2-variant으로 재작성, 드랍된 variant는 future work 이동
3. `05_implementation_architecture.md` — Ablation 매핑표 축약 (2 variants 대응)
4. `03_related_work_mapping.md` — "planning substrate ≠ retrieval" framing 완화. "site-specific KG 도입"이 핵심 기여 framing으로 변경
5. `01_references_summary.md` §4 — 주장별 대비표에서 drop된 주장 표시 추가

이 5 문서의 수정 전에 본 07 문서가 **source of truth**로 고정돼 있어야 일관성 유지.
