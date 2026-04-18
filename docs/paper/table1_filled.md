# Table 1 — Per-type × per-variant results (Template)

`scripts/make_paper_tables.py`가 `output/phase_c_180/paired/paired.csv` +
`overall_stats.json`을 읽어 아래 placeholder를 치환해 `table1_filled.md`로 생성한다.

---

## Table 1. Task success rate and compute by task type and variant.

**N=3 per (variant, task), binarized via majority vote. Wilson 95% CI reported.
McNemar paired test for success, Wilcoxon signed-rank for continuous metrics.**

| Task Type   | N  | Baseline SR         | Full KG SR         | Δ SR    | McNemar p  | OR       | Tokens B→K    | Steps B→K    | Time(s) B→K    |
|-------------|----|---------------------|--------------------|---------|------------|----------|---------------|--------------|----------------|
| **Overall** | 30 | `20.0% (9.5, 37.3)`  | `20.0% (9.5, 37.3)` | `+0.0 pp` | `1.0000 ns` | `115.00 [6.11, 2166.07]` | `380 → 429` | `35 → 39` | `101 → 90` |
| NAVIGATE    | 10 | `20.0% (5.7, 51.0)`      | `20.0% (5.7, 51.0)`     | `+0.0 pp`     | `1.0000 ns`     | `85.00 [1.32, 5478.48]`     | `243 → 312`     | `34 → 44`     | `89 → 93`     |
| RETRIEVE    | 10 | `30.0% (10.8, 60.3)`      | `30.0% (10.8, 60.3)`     | `+0.0 pp`     | `1.0000 ns`     | `12.00 [0.49, 294.59]`     | `103 → 93`     | `16 → 14`     | `53 → 48`     |
| MUTATE      | 10 | `10.0% (1.8, 40.4)`      | `10.0% (1.8, 40.4)`     | `+0.0 pp`     | `1.0000 ns`     | `57.00 [0.79, 4124.18]`     | `795 → 884`     | `69 → 72`     | `203 → 155`     |

**Significance codes** (after Bonferroni α=0.0167 for per-type, α=0.05 for overall):
- `***` p < 0.01
- `**`  p < 0.0167 (per-type) or p < 0.05 (overall)
- `ns`  not significant

**SR format**: `{percentage}% (CI_lo, CI_hi)` — e.g., `60.0% (38.7, 78.1)`
**Compute format**: `mean_baseline → mean_kg` — e.g., `14200 → 8100`
**OR format**: odds ratio with 95% CI — e.g., `2.3 [0.8, 6.8]`

---

## Auxiliary tables (separate files)

### Table 2. KG-addressable coverage per task type (from `coverage.py`)

| Task Type | N | Hook A `plan_to_info` success | Coverage % |
|---|---|---|---|
| NAVIGATE | 10 | `{{cov_nav_n}}` | `{{cov_nav_pct}}` |
| RETRIEVE | 10 | `{{cov_ret_n}}` | `{{cov_ret_pct}}` |
| MUTATE   | 10 | `{{cov_mut_n}}` | `{{cov_mut_pct}}` |
| **Overall** | 30 | `{{cov_overall_n}}` | `{{cov_overall_pct}}` |

### Table 3. Failure mode distribution (from `failure_mode.py`)

P/R/G/A/O categories (Perception / Reasoning / Grounding / Action / Other):

| Variant | P | R | G | A | O | Cohen's κ |
|---|---|---|---|---|---|---|
| Baseline | `{{f_b_p}}` | `{{f_b_r}}` | `{{f_b_g}}` | `{{f_b_a}}` | `{{f_b_o}}` | — |
| Full KG  | `{{f_k_p}}` | `{{f_k_r}}` | `{{f_k_g}}` | `{{f_k_a}}` | `{{f_k_o}}` | `{{kappa}}` |

---

## Placeholder reference

Total placeholders: 40 (Table 1) + 8 (Table 2) + 11 (Table 3) = **59**.

`make_paper_tables.py` expects the following JSON schema from `paired_stats.py`:

```json
{
  "overall": {
    "baseline": {"success_rate": float, "ci_lo": float, "ci_hi": float,
                 "tokens_mean": float, "steps_mean": float, "time_mean": float},
    "kg_full":  {...},
    "mcnemar_p": float, "odds_ratio": float, "or_ci": [lo, hi],
    "wilcoxon": {"tokens_p": float, "steps_p": float, "time_p": float}
  },
  "per_type": {
    "NAVIGATE": {...same structure...},
    "RETRIEVE": {...},
    "MUTATE":   {...}
  }
}
```

Coverage + failure_mode는 별도 JSON에서 읽음 (`coverage.json`, `failure_mode.json`).
