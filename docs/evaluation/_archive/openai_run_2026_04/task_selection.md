# Task selection — curated 15-task mechanism coverage

## Motivation

Statistical-power sampling (e.g., N=30 random stratified) at this scale gives a single aggregate number (V0 vs V1 success rate delta) that hides **which KG mechanism** drives the gap. The paper's contribution claim is mechanism-level:

1. **Pre-action navigation planning** via graph pre-solve → 1-step directed plan.
2. **Interaction-surface compression**: structure not immediately observable (or revealed only after multi-step interaction) is pre-investigated and surfaced in 1 step.

A curated sample that deliberately covers 5 scenario archetypes across 3 task types lets each cell in the design matrix isolate one mechanism — including transparent **null** and **limitation** cells that protect against over-claiming.

## Scenario archetypes

| ID | Name | Definition | Intended KG role |
|---|---|---|---|
| S1 | Effect-best | Clean single-target task | target_class + URL template fires directly |
| S2 | Multi-hop | Path compresses 2+ edges | path_finder / compound edge |
| S3 | Ambiguous | Scope must be disambiguated | task_inferrer triggers / not_for |
| S4 | Limitation | Known KG gap (e.g., non-ARIA modal) | Surfaces negative result transparently |
| S5 | Null / parity | Trivial enough that KG adds nothing | Regression check (V1 must not regress V0) |

Each task type × scenario cell contains exactly one task → 15 total.

## Pre-registration

This document is written **before V0 / V1 measurement runs** on any of these tasks other than the smoke pair (168, 397). The scenario label was assigned from task intent text and the current KG artefact (`output/validation/kg_solution/class_descriptions.json`, rebuilt 2026-04-24), not from measured outcomes. The prediction column below is therefore a pre-hoc hypothesis, not a post-hoc label.

## Task matrix

### NAVIGATE

| task | intent (short) | scenario | predicted V0 vs V1 | KG mechanism under test |
|---|---|---|---|---|
| 44  | Open my todos page | S5 null | V0=V1 success | single URL, no KG gain |
| 45  | Issues page filtered recent open | S1 best | V1 fewer steps | project/issue_list + sort/state filter_categories |
| 102 | Open issues with label X in a11yproject/repo | S2 multi-hop | V1 directer | cross-project URL template + label_name[] filter |
| 156 | Merge requests assigned to me | S3 ambiguous | V1 correct scope | dashboard/merge_requests vs project/merge_requests via triggers |
| 342 | Issues about OPT model | S4 limitation | V1 = V0 (fuzzy) | label semantic matching — KG exposes structure but not values |

### RETRIEVE

| task | intent (short) | scenario | predicted V0 vs V1 | KG mechanism under test |
|---|---|---|---|---|
| 133 | Commits by Eric on 2023-03-02 | S5 null | V0=V1 success | commit history page — minimal KG gain |
| 309 | Username with most commits to thoughtbot/administrate | S1 best | V1 fewer steps | project/contributor_graph URL template |
| 296 | SSH URL of best GAN python impl | S2 multi-hop | V1 directer | explore → pick → clone-dialog compression |
| 168 | Personal projects with >100 stars | S3 ambiguous | V1 detects absence | user.projects scope; scaffold-fix NOT_FOUND path (smoke: V0 passed) |
| 176 | Boolean: is theme-editor issue closed | S4 limitation | V1 may regress | Known V1 boolean-RETRIEVE weakness (task #233 diagnosis) |

### MUTATE

| task | intent (short) | scenario | predicted V0 vs V1 | KG mechanism under test |
|---|---|---|---|---|
| 664 | Create simple issue (Python 3.11 question) | S5 null | V0=V1 success | issue_new_form direct — baseline parity |
| 476 | Create new repo "awesome_llm_reading" | S1 best | V1 fewer steps | project_new URL template + form schema hint |
| 742 | Create private project + add members | S2 multi-hop | V1 directer | project_new → members/invite compound edge |
| 535 | Follow [Jakub K, ghost, Benoît Blanchon] | S3 ambiguous | V1 correct target | user/profile scope, follow action disambiguation |
| 568 | Invite Abishek, Vinta as collaborators | S4 limitation | V0=V1 (no modal hint) | GitLab Pajamas non-ARIA dialog — modal_structures empty |

## Success criteria for the paper claim

The 15-task curation produces a 5 × 3 cell matrix. Claims we will be willing to make:

- **Per-cell mechanism claim**: "In cell X, V1 <outcome> and the V1 log shows <mechanism> firing at step N." — one claim per cell, supported by log evidence.
- **S1 aggregate** (3 tasks): if ≥2 of 3 S1 tasks show V1 step reduction with the predicted mechanism in log, the "1-step directed plan" contribution is supported at the mechanism level.
- **S4 aggregate** (3 tasks): parity between V0 and V1 **confirms the transparent limitation** — this is a feature of the paper, not a failure.
- **S5 aggregate**: V1 must not regress V0 in any S5 task. Regression in an S5 cell is a blocker.

We will **not** claim:

- "V1 > V0 by X percentage points" as a population estimate.
- Statistical significance (N=15 paired-test power is insufficient).

## Excluded considerations

- **Cross-site**: Reddit is not in this measurement; cross-site generalization is mentioned as future work only.
- **Ablation variants** (V1b = KG hint off / V1c = path_finder off / etc.): reserved for a separate ablation study.
- **Token/latency cost**: reported descriptively in the results table but not a primary metric.

## Environment protocol

- MUTATE tasks run with `webarena-verified env stop` + `env start` before execution to guarantee clean container state. Auth refreshed per restart.
- NAVIGATE / RETRIEVE tasks run back-to-back without reset.
- Per-task wall-clock timeout: 20 minutes (`run_with_timeout.py 1200`).
- LLM: `gpt-5.4-mini` via OpenAI (same as all prior pilot/smoke runs in this branch).
- Run roots:
  - V0: `output/main_measurement/v0/<task_id>/`
  - V1: `output/main_measurement/v1/<task_id>/`

## Reproducibility artefacts

After execution, the following are committed:

- `output/main_measurement/v0/` and `/v1/` (agent_response.json + network.har + eval_result.json + logs)
- KG artefact snapshot: `output/validation/kg_solution/class_descriptions.json` (git-tracked)
- This plan document (pre-registration record)
- Per-task mechanism-check notes in `docs/evaluation/results.md` (populated post-run)
