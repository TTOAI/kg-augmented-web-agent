# Metrics

## Primary signals (per trial)

### 1. 평가기 결과
- **Agent evaluator** (`AgentResponseEvaluator`): `agent_response.json`의 `status`/`retrieved_data` 매칭. PASS / FAIL.
- **Network evaluator** (`NetworkEventEvaluator`): HAR의 URL/parameter 매칭. PASS / FAIL / N/A (해당 task가 network rule 미정의).

평가기 결함으로 의미적 성공이 fail로 기록된 경우는 [`eval_exclusions.md`](eval_exclusions.md)에 사전 정의된 기준으로 분류·집계.

### 2. Step 수
`webarena_verified.log`의 `[LLM] all goals complete in X.Xs (N steps)` 라인에서 추출. 시간 초과(timeout)는 `step=∞`로 처리.

### 3. Mechanism invocation log (V1 / V1−tc 만)
각 task card의 `mechanism_invocation_signal` 패턴이 V1 trial 로그에서 발동했는지 binary flag로 기록.

수집 형식 (per trial):
```
task_id: <id>
variant: <v1|v1_tc>
trial: <n>
kg_session_loaded: bool
kg_inferred_target: <class_name | none>
kg_inferred_agreement: <K/K>
kg_path_found: bool
predicted_mechanism_fired: bool   # task card의 signal과 매칭
agent_thought_quotes_kg_label: bool  # agent thought에 KG 노출 라벨이 등장했는가 (정규식 + 수동 검증)
```

`predicted_mechanism_fired`는 task card별로 정의된 expected fingerprint를 만족하는지 별도 분석 스크립트가 추출. `agent_thought_quotes_kg_label`은 자동 추출 후 ambiguous case는 수동 raters로 confirm.

### 4. Trajectory divergence step
V0와 V1의 trial이 동일 task에서 처음 다른 액션을 취한 step 번호. step 0은 시작 페이지 관측, step k는 k번째 tool 호출.

per task × trial 쌍 (V0 trial i vs V1 trial i):
- `divergence_step`: 정수 또는 `same` (모든 step 동일)
- `v0_outcome_at_divergence`: V0가 divergence step에서 취한 액션 요약
- `v1_outcome_at_divergence`: V1이 divergence step에서 취한 액션 요약

### 5. Token / latency (보조)
- 총 input/output/cache_create/cache_read 토큰 (per trial, summed from `[LLM] tokens` log lines).
- 총 wall-clock 시간 (per trial).

본 연구의 primary claim은 cost가 아니지만, characterization narrative에 "KG가 step은 줄이지만 wall-clock은 늘린다" 같은 trade-off가 있을 경우 보고한다.

## Aggregation

### Per-cell outcome (task × variant 단위)
3 trial을 다음 규칙으로 합쳐 cell-level outcome 산출:

- **Agent evaluator outcome**: 3 trial 중 2 이상 PASS → cell PASS. 1 PASS → mixed (narrative). 0 PASS → cell FAIL.
- **Network evaluator outcome**: 동일 majority 규칙.
- **Step 수**: 3 trial median 보고, range를 괄호로 (`12 [10–14]` 같은 표기).
- **Mechanism fired**: 3 trial 중 1 이상 발동 → "fired". 0 → "not fired".

### Per-condition synthesis (H1~H3 / L1~L3 / Null1~Null2 단위)
각 condition에 1 task만 매핑되므로, 그 task의 cell outcome이 곧 condition 결과. paper §4 각 subsection은:

1. **사전 가설** (task card에서 인용)
2. **측정 결과** (cell outcome 표 + step / mechanism log)
3. **가설 대비 평가** — 사전 falsification criterion에 비추어 confirm / refute / inconclusive 중 하나로 라벨.

### V1 vs V1−tc (L1 ablation 분석 전용)
L1 task (411)에서 V1과 V1−tc의 outcome·step·divergence를 직접 비교해 능동적 오도의 원인을 다음 중 하나로 분류:

- **추론기 탓**: V1 timeout, V1−tc 통과 또는 V0와 유사
- **hint 자체 탓**: 둘 다 timeout
- **양쪽 기여**: 중간 결과

## Exclusions

[`eval_exclusions.md`](eval_exclusions.md) 적용:
- evaluator strict-match 결함으로 의미적 성공이 fail로 기록된 trial은 raw 결과와 adjusted 결과 모두 보고.
- V0와 V1·V1−tc에서 동일 task가 broken evaluator에 걸리면 paired exclusion으로 간주.

## Outcome categories (per condition)

각 condition은 측정 후 다음 4개 라벨 중 하나로 분류된다:

| 라벨 | 의미 |
|---|---|
| `confirmed` | 사전 가설과 일치 |
| `refuted` | 사전 가설과 반대 결과 (가설 반증 — 메커니즘 모델 수정 필요) |
| `partial` | 일부 trial에서 가설 일치, 일부 미일치 |
| `inconclusive` | 평가기 결함이나 infrastructure 이슈로 신호 추출 불가 |

paper §4에는 8 condition × 4 라벨 분포가 첫 줄에 등장한다.

## Analysis pipeline (post-measurement)

1. trial 로그 → 위 5개 신호 자동 추출 (`scripts/eval/extract_signals.py` — phase 0 종료 직전 작성)
2. cell-level aggregation (`scripts/eval/aggregate_cells.py`)
3. condition-level synthesis (수동 — narrative 작성)
4. paper §4 표·그림 생성 (`scripts/eval/render_figures.py`)

스크립트 자체도 phase 0에 사전 작성·smoke test하여 본측정 후 인공적 변형 여지를 차단한다.
