# 08. Contribution Scenarios — Any-Result-Valuable Framing

## 이 문서의 목적

본 연구의 H1a (정확도) + H1b (효율) 측정 결과가 **positive / null / negative 어떤 시나리오**
로 나오더라도 논문 contribution이 살아남도록 **사전에** narrative를 고정한다.

측정 *후*에 framing을 조정하면 reviewer "결과 보고 narrative 바꿨다 (HARKing)" 의심 가능.
이 문서는 측정 시작 *전*에 freeze해 git history로 보존된다.

근거 framing: `07 §1` triple contribution (C1 정확도 / C2 효율 / C3 methodology).

---

## 1. 시나리오 매트릭스 (2026-04-17 update — 2 variants × per-type)

### 1-1. Overall 시나리오 (4개)

H1a_overall × H1b_overall (each +/null/−, 주요 4 case):

| H1a_overall | H1b_overall | Primary contribution sentence |
|---|---|---|
| **significant (any dir)** | **significant (any dir)** | "KG가 정확도와 효율에 동시 유의미 영향 (부호는 측정 결과로 특정). per-type breakdown이 heterogeneous mechanism 분석 제공" |
| **significant** | null | "KG가 정확도에만 유의미 영향. compute neutral 확인 — per-type 분석이 어떤 task에서 영향이 집중되는지 보임" |
| null | **significant** | "KG가 정확도는 불변시키나 효율 유의미 영향. compute trade-off 정량화가 contribution. per-type 분석이 어느 task type에서 효율 효과가 큰지 보임" |
| null | null | "overall null. C3 methodology contribution + per-type heterogeneous analysis + failure mode taxonomy가 주요 기여. 'KG가 균일하게 영향 주지 않는다'는 empirical finding도 valid" |

**부호 가정 없음** (two-tailed): significant일 때 부호는 결과로 해석. "improve" / "degrade" 중립 표현.

### 1-2. Per-type heterogeneous 시나리오

3 task types (NAVIGATE / RETRIEVE / MUTATE) × 2 variants 비교에서 type별 effect 방향이
다를 가능성. 가장 흥미로운 contribution:

| Pattern | 예 | Contribution sentence |
|---|---|---|
| **Uniform positive** | 3 types 모두 significant +  | "KG가 task type에 무관하게 개선" |
| **Uniform null** | 3 types 모두 null | "KG 효과 미관측, methodology + failure mode가 contribution" |
| **Heterogeneous (예: NAV+, MUT−)** | NAV 개선, MUT 손실 | "KG의 이득은 task type에 의존 — emit_url/rewrite이 NAVIGATE에 유리, MUTATE form interaction에는 over-rewrite risk. schema/hook 설계 가이드. **Phase 2C Hook A path-slot guidance + runtime context auto-fill**로 MUT Hook B activation 증가 시도" |
| **Selective positive** | 1 type만 significant | "KG effect가 특정 task kind에 집중 — 어느 hook이 어느 task에 기여하는지 qualitative 분석" |

Per-type heterogeneous pattern은 **단순 "KG > baseline"보다 훨씬 informative** —
3-page 논문의 scientific value를 높임. any-result-valuable framing의 핵심.

### 가장 중요한 점
- **모든 시나리오에서 contribution sentence 작성 가능** (null/negative 포함).
- **C3 (methodology)는 모든 시나리오 공통 contribution** — 결과와 무관하게 살아남음.
- **Failure mode taxonomy** (`06 §3-2` P/R/G/A/O) × task_type 2D 분석으로 어디서 KG가
  어떤 실패를 줄였는지/늘렸는지 nuanced 분석 제공.
- **Heterogeneous pattern 자체가 contribution** — "모든 task에서 KG가 uniform하게
  작동하지 않는다"는 empirical finding이 후속 연구 가이드.

---

## 2. Introduction 작성 가이드 (3-page scope)

본문 §1 Introduction에 다음 3 contribution을 명시:

```
Our contributions are:
(C1) We quantify the heterogeneous impact of site-specific knowledge graphs on LLM
     web-agent task success across task types on WebArena-Verified GitLab (30 tasks,
     10 per type, 2 variants, N=3 paired evaluation with per-type McNemar).
(C2) We quantify the compute trade-off (token, step, wall-time) of KG-augmented agents
     against a baseline, reported per task type.
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
- Table 1 cell: 2 variant × success rate (Wilson 95% CI) × 4 row (overall + NAV/RET/MUT)
- McNemar exact test (Baseline ↔ Full KG), overall α=0.05, per-type α=0.0167 (Bonferroni 3)
- *결과 부호와 무관하게* 같은 표 구조.

### §3.2 H1b (효율)
- Table 1 cell: 2 variant × token / step / wall-time 평균 (per task)
- Wilcoxon signed-rank test (paired)

### §3.3 KG 정보 vs 추가 compute (confounding 분리) — future work
- 3rd variant KG-Info-Ignored는 scope 축소로 future work (`07 §11`)
- 본 연구는 Baseline ↔ Full KG 2-variant 비교로 한정
- Compute confounding은 token/step 수치 보고로 partial 차단

### §3.4 Failure mode 분석
- P/R/G/A/O 분포 × 2 variant
- 각 variant가 어느 카테고리 실패를 줄였는지/늘렸는지

### §3.5 KG-addressable coverage
- 30 task 중 Hook A `plan_to_info` 성공률
- task_type subset별

### §3.6 Hook 세분 발동 통계 (2026-04-18 Option B 이후)
- Hook A classified / declined / not_called / other (기존)
- **Hook B applied / skipped (trust) / skipped (incomplete_url)** — Option B 활성 후 신규
- **Hook C early SUCCESS** — NAVIGATE에서만 (RET/MUT suppressed by task_type gate)
- `scripts/coverage.py` 자동 집계 → `output/phase_c_180/coverage.md` 참조

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
- [x] 2 variants (Baseline / Full KG) — `07 §5` (2026-04-17 scope reduction, KG-Info-Ignored future work)
- [x] Trust policy Option B (verified/declared/inferred 전부 수용) — `07 §14` (2026-04-18)
- [x] Hook C early-termination NAVIGATE-only gate — `05 §5` (2026-04-18)
- [x] Statistical test (McNemar paired binary, Wilcoxon paired continuous) — `06 §4`
- [x] Statistical test: overall α=0.05 (single pairwise), per-type α=0.0167 (Bonferroni 3) — `06 §4-3`
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
