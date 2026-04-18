# Table 1 — Per-type × per-variant results (Template)

`scripts/make_paper_tables.py`가 `output/phase_c_180/paired/paired.csv` +
`overall_stats.json`을 읽어 아래 placeholder를 치환해 `table1_filled.md`로 생성한다.

---

## Table 1. Task success rate and compute by task type and variant.

**N=3 per (variant, task), binarized via majority vote. Wilson 95% CI reported.
McNemar paired test for success, Wilcoxon signed-rank for continuous metrics.**

| Task Type   | N  | Baseline SR         | Full KG SR         | Δ SR    | McNemar p  | OR       | Tokens B→K    | Steps B→K    | Time(s) B→K    |
|-------------|----|---------------------|--------------------|---------|------------|----------|---------------|--------------|----------------|
| **Overall** | 30 | `{{b_overall_sr}}`  | `{{k_overall_sr}}` | `{{d_overall}}` | `{{p_overall}}` | `{{or_overall}}` | `{{tok_overall}}` | `{{step_overall}}` | `{{time_overall}}` |
| NAVIGATE    | 10 | `{{b_nav_sr}}`      | `{{k_nav_sr}}`     | `{{d_nav}}`     | `{{p_nav}}`     | `{{or_nav}}`     | `{{tok_nav}}`     | `{{step_nav}}`     | `{{time_nav}}`     |
| RETRIEVE    | 10 | `{{b_ret_sr}}`      | `{{k_ret_sr}}`     | `{{d_ret}}`     | `{{p_ret}}`     | `{{or_ret}}`     | `{{tok_ret}}`     | `{{step_ret}}`     | `{{time_ret}}`     |
| MUTATE      | 10 | `{{b_mut_sr}}`      | `{{k_mut_sr}}`     | `{{d_mut}}`     | `{{p_mut}}`     | `{{or_mut}}`     | `{{tok_mut}}`     | `{{step_mut}}`     | `{{time_mut}}`     |

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
