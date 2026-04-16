# 08. Contribution Scenarios — Any-Result-Valuable Framing

## 이 문서의 목적

본 연구의 H1a (정확도) + H1b (효율) 측정 결과가 **positive / null / negative 어떤 시나리오**
로 나오더라도 논문 contribution이 살아남도록 **사전에** narrative를 고정한다.

측정 *후*에 framing을 조정하면 reviewer "결과 보고 narrative 바꿨다 (HARKing)" 의심 가능.
이 문서는 측정 시작 *전*에 freeze해 git history로 보존된다.

근거 framing: `07 §1` triple contribution (C1 정확도 / C2 효율 / C3 methodology).

---

## 1. 시나리오 매트릭스

H1a (성공률) × H1b (효율)의 9 시나리오 (각 +/null/−):

| H1a | H1b | 빈도 추정 | Primary contribution sentence |
|---|---|---|---|
| ✅ + | ✅ + | 강함 | "Site-specific KG가 정확도와 효율을 모두 개선" — 가장 강한 결과 |
| ✅ + | null | 중간 | "KG가 정확도 개선, 효율은 보존" — 정확도 효과가 추가 LLM call 비용을 정당화 |
| ✅ + | ❌ − | 드묾 | "정확도 개선 in cost of compute" — trade-off framing, 비용 정량화가 contribution |
| null | ✅ + | 흔함 | "충분 budget에서 KG의 정확도 효과는 미미하나 효율 개선이 실용적 가치" |
| null | null | 가능 | "단일 측정 budget에서 KG hooks의 정량 효과 미관측. C3 methodology + failure mode taxonomy가 contribution. failure mode 분포 분석으로 어느 task type에서 KG가 영향을 줄 가능성을 보여줌" |
| null | ❌ − | 가능 | "KG가 정확도 보존하나 추가 compute 비용. trade-off에서 KG가 net negative — 어떤 task에서는 cost-effective한가 분석" |
| ❌ − | ✅ + | 가능 | "KG의 over-rewrite가 정확도 손실, 효율은 개선 — schema/prompt 설계 trade-off 분석 + over-rewrite 경향이 큰 trust level 식별" |
| ❌ − | null | 드묾 | "KG가 정확도 손실, 효율 변화 없음 — confounding (KG-Info-Ignored 비교로 KG 정보가 negative인지, 추가 LLM step이 negative인지 분리)" |
| ❌ − | ❌ − | 드묾 | "KG가 양쪽 손실 — 본 site/setup에서 KG approach 부적합 증거. 어떤 trust level/Hook 조합에서 신중해야 하는지 학습" |

### 가장 중요한 점
- **모든 9개 시나리오에서 contribution sentence 작성 가능**.
- **C3 (methodology)는 모든 시나리오 공통 contribution** — 결과와 무관하게 살아남음.
- **Failure mode taxonomy** (`06 §3-2` P/R/G/A/O)가 모든 시나리오에서 nuanced 분석 제공.

---

## 2. Introduction 작성 가이드 (3-page scope)

본문 §1 Introduction에 다음 3 contribution을 명시:

```
Our contributions are:
(C1) We quantify the impact of site-specific knowledge graphs on LLM web-agent task
     success on WebArena-Verified GitLab (50 tasks, 3 variants, N=3 paired evaluation).
(C2) We quantify the compute trade-off (token, step, wall-time) of KG-augmented agents
     against a baseline and a compute-matched control variant.
(C3) We provide an automated 2-stage KG construction pipeline (Playwright crawl +
     multi-call LLM derivation) with heuristic post-enrichment as a reproducible
     research artifact, with no per-task manual labeling.
```

**부호 가정 금지**: "improve" 같은 양수 가정 표현 사용 안 함. "quantify the impact" /
"quantify the trade-off" 같은 *측정* 표현으로 framing.

---

## 3. Result 섹션 작성 가이드

측정 후 어떤 시나리오로 결정나도 다음 구조 유지:

### §3.1 H1a (정확도)
- Table 1 cell: 3 variant × success rate (Wilson 95% CI)
- McNemar test result (Baseline ↔ Full KG) + (Baseline ↔ KG-Info-Ignored) +
  (KG-Info-Ignored ↔ Full KG)
- *결과 부호와 무관하게* 같은 표 구조.

### §3.2 H1b (효율)
- Table 1 cell: 3 variant × token / step / wall-time 평균 (per task)
- Wilcoxon signed-rank test (paired)

### §3.3 KG 정보 vs 추가 compute (confounding 분리)
- KG-Info-Ignored ↔ Full KG의 차이 = KG 정보의 순수 기여
- Baseline ↔ KG-Info-Ignored의 차이 = 추가 LLM call의 reasoning step 효과

### §3.4 Failure mode 분석
- P/R/G/A/O 분포 × 3 variant
- 각 variant가 어느 카테고리 실패를 줄였는지/늘렸는지

### §3.5 KG-addressable coverage
- 50 task 중 Hook A `plan_to_info` 성공률
- task_type subset별

---

## 4. Discussion 섹션 작성 가이드 (시나리오별)

측정 후 결과를 보고 §1의 시나리오 매트릭스 행을 하나 골라 narrative 작성:

### Positive 시나리오 (H1a + or H1b +)
- "Our results validate / partially validate the hypothesis that..."
- KG가 도움 된 task의 패턴 분석 (failure mode + task_type)
- C3 methodology를 strength로 강조

### Null 시나리오 (H1a/H1b 둘 다 null)
- "Our results do not show a statistically significant effect on either accuracy or compute
  efficiency under the tested budget. We interpret this as..."
- 가능 해석:
  - "충분 budget에서 baseline의 BFS-like exploration이 sufficient"
  - "KG의 가치는 budget 제약이 더 강한 setting에서 드러날 가능성 (future work)"
- C3 methodology를 main contribution으로
- Failure mode 분포에서 KG가 *어떤 task에서* 영향을 줄 가능성을 분석 (qualitative)

### Negative 시나리오 (H1a − or H1b −)
- "Our results suggest that KG-augmented planning may introduce trade-offs..."
- 가능 해석:
  - Over-rewrite: KG의 inferred trust path가 baseline의 robust한 retry를 막음
  - Schema 정확도 한계: post_enrich heuristic이 부정확한 binding을 만들었을 가능성
- **이런 결과도 valuable** — 후속 연구에 "KG 도입 시 신중해야 할 design choice" 가이드 제공
- C3 methodology는 여전히 valid (방법론 자체가 negative result도 reproducible)

---

## 5. Limitation 섹션 작성 가이드

`06 §8` 7개 항목 그대로 + 시나리오별 추가:

### Null/Negative 시나리오 시 추가
- "Our single-budget evaluation may underestimate KG's value in budget-constrained settings.
  Budget sensitivity ablation is future work."

### Positive 시나리오 시 추가
- "Our 3-variant ablation isolates KG *information* contribution but not individual hook
  contributions (rewrite vs validate). Hook-level ablation is future work."

(공통: `07 §11` Limitation 표의 7 항목은 결과와 무관하게 declarative.)

---

## 6. 사전 결정 사항 (측정 시작 전 freeze)

다음은 측정 *후* 변경 금지 — git commit으로 freeze:

- [x] Triple contribution (C1/C2/C3) framing — `07 §1`
- [x] Dual H1 (H1a/H1b) two-tailed — `06 §4-4`
- [x] 3 variants (Baseline / KG-Info-Ignored / Full KG) — `07 §5`
- [x] Statistical test (McNemar paired binary, Wilcoxon paired continuous) — `06 §4`
- [x] Bonferroni correction (α=0.025 per sub-test) — `06 §4-3`
- [x] Per-run paired binarization rule (majority vote) — `06 §4-5`
- [x] 시나리오별 contribution sentence (이 문서)
- [x] Limitation 7개 항목 (`06 §8`)

측정 결과를 보고 위 항목 중 어느 하나라도 변경 시 **reviewer-proof 위반** — 변경하려면
별도 git commit + 명시적 사유 기록 필요.

---

## 7. Reviewer-proof 가드

- 이 문서의 git timestamp가 첫 baseline 측정 commit *보다 앞서야* 함.
- 측정 결과가 어느 시나리오에 해당하든 §3 narrative 구조 유지.
- "결과 보고 narrative 골랐다" 의심 차단을 위해 §1 매트릭스의 9개 시나리오 *전체*를 사전
  열거.
- "원래 positive 기대했지 않냐" 반박: H1 양방향 검정 (two-tailed) + 시나리오 매트릭스에 9개
  모두 contribution 있음을 보여 부호 가정 없음 명시.
