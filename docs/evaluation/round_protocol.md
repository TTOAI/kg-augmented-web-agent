# Round protocol — iterative observation

본 측정은 8 task fixed-set이 아니라 **round별 task 선정 + 누적 관찰** 방식이다. cherry-picking 위험을 막기 위해 다음 셋을 측정 시작 *전*에 main 브랜치로 commit한다.

## 1. 선정 규칙 (selection rule)

각 round 시작 전:

1. 다음 round의 task 후보를 archetype 라벨(H효과 / L한계 / Null)과 함께 `task_cards/<COND>_<task_id>.md`에 신규 commit한다.
2. 카드는 condition label, predicted V0/V1 행동, mechanism invocation signal, falsification criterion을 모두 포함한다.
3. round 측정 commit *이전*의 git SHA에서 카드가 lock되어야 한다 — 측정과 같은 commit에 카드를 함께 넣지 않는다 (timeline의 git 증거 확보).
4. **선정 사유는 archetype gap에 근거**한다. 예: "현 L 관측 0건 → L 후보로 task 418 선택". "promising / V1 효과가 클 것 같은" 같은 결과 편향 어휘 사용 금지.

## 2. Stopping rule

다음 *둘 다* 충족하면 측정 종료:

- 세 archetype (H, L, Null) 각각에 **최소 1 task의 outcome 관측 (3 trial 이상)** 확보
- 누적 task 수 **≤ 8** OR round 수 **≤ 4**

stopping을 결과로 정의하지 않는다 ("효과가 보일 때까지" 같은 정의 금지). 위 조건 충족 직후 다음 round를 시작하지 않고 종료.

## 3. 전건 보고 (report-all rule)

`task_cards/`에 commit된 모든 task의 outcome은 paper §4에 등장한다. 가설이 refuted되거나 inconclusive로 끝난 task도 drop 금지. 현재 archived `pilot/411` 의 L1 refuted 결과가 representative 사례.

drop 사유로 인정되는 것은 *infrastructure 이슈* 한정 (browser hang, evaluator crash 등 KG와 무관한 시스템 오류). 이 경우 별도 `infra_excluded.md`에 기록.

## 4. 변종 (variants)

본 round 1 시점부터 V1−tc는 측정 범위에서 제외. **V0 (KG 미사용) vs V1 (KG_MODE=minimal)** 두 변종만 측정한다. 사유: pilot에서 V1−tc가 page-surface info의 자체 효과로 clean control이 아님이 확인되어, 추론기-단독 효과 분리 주장 자체가 reviewer-vulnerable.

V1−tc 코드 게이트 (`KG_DISABLE_TARGET_INFERRER`)는 dead-code로 유지 (future ablation 재활성 가능).

## 5. Trial / metric

- per (task × variant) cell **3 trial**
- metric은 [`metrics.md`](metrics.md) 그대로 (4 신호 — V1−tc 분석 부분만 무시)
- 분석 파이프라인: `extract_signals.py` → `aggregate_cells.py` → `render_figures.py`

## Round 1 정의

선정 사유 (archetype gap):

| Cond | task | gap-based 선정 사유 |
|---|---|---|
| H (효과) | 102 | pilot 1 trial에서 V1=15 vs V0=29 강한 단축 신호. 3 trial 안정성 확보로 H archetype 첫 정량 lock. |
| L (한계) | 418 | pilot으로 검증된 task 411의 L1 가설 refuted (KG inferrer가 useful adjacent 클래스 안내). 진짜 active misdirection 후보로 task 418 (set GitLab status) 선택 — KG 클래스 카탈로그·액션 카탈로그 모두 status 매핑 0건 확인됨. |
| Null | 44 | smoke 1 trial × 2 variant에서 V0=V1=2 step 확인. 3 trial로 active control 안정성 lock. |

Round 1 후 stopping criterion 평가 → 충족 시 종료, 미충족 시 Round 2 task 선정.
