# Appendix — Model Size Comparison (gpt-5.4-nano vs gpt-5.4-mini baseline)

## Method

Phase 2-C smoke에서 gpt-5.4-nano로 수행한 baseline과 Phase C (2026-04-17) 본 측정의
gpt-5.4-mini baseline (동일 task_types.txt sample)을 공통 task_id subset으로 비교.
각 task는 majority vote binary success로 이진화 (per-task), step/wall-time/llm_calls는
task 내 run 평균. Model size robustness future work (`docs/07 §11`)의 preliminary signal.

- Common tasks: 7
- Nano data: `output/smoke_nano_expanded/baseline`
- Mini data: `output/phase_c_180/baseline`

## Overall Success Rate

| Model | Success | Wilson 95% CI |
|---|---|---|
| **gpt-5.4-nano** | 1/7 (14.3%) | [2.6%, 51.3%] |
| **gpt-5.4-mini** | 3/7 (42.9%) | [15.8%, 75.0%] |

## Per-type Success Rate

| task_type | Nano | Mini |
|---|---|---|
| NAVIGATE | 1/3 (33.3%) | 1/3 (33.3%) |
| RETRIEVE | 0/3 (0.0%) | 2/3 (66.7%) |
| MUTATE | 0/1 (0.0%) | 0/1 (0.0%) |

## Per-task Detail

| task_id | type | Nano bin | Mini bin | Nano steps | Mini steps | Nano time | Mini time | Nano llm | Mini llm |
|---|---|---|---|---|---|---|---|---|---|
| 44 | NAVIGATE | 1 | 1 | 11.0 | 2.0 | 19.3 | 4.5 | 65 | 11 |
| 46 | RETRIEVE | 0 | 1 | 16.0 | 37.7 | 56.0 | 155.0 | 115 | 272 |
| 102 | NAVIGATE | 0 | 0 | 23.0 | 20.0 | 50.2 | 96.9 | 170 | 144 |
| 168 | RETRIEVE | 0 | 0 | 40.0 | 23.0 | 57.8 | 37.5 | 267 | 149 |
| 259 | RETRIEVE | 0 | 1 | — | 13.0 | — | 46.0 | 1180 | 84 |
| 339 | NAVIGATE | 0 | 0 | 74.0 | 51.0 | 501.3 | 143.1 | 576 | 373 |
| 411 | MUTATE | 0 | 0 | 272.0 | 83.0 | 628.3 | 452.2 | 1900 | 253 |

## Interpretation

Nano와 mini의 비교는 **model size robustness의 preliminary evidence**로 본 3-page
논문의 Limitation/Future Work 섹션에 인용된다. 본 실험은 mini 단일 모델로 진행됐고
(`docs/07 §7`), nano 비교는 동일 pipeline 하에서의 smoke 수준 관찰로 limited.