# Null1: task 44 — 시작 페이지 1-step 직접 링크 (NAV)

**Type**: NAVIGATE
**Source**: WebArena-Verified task 44
**Round**: 1 (smoke 1 trial: baseline=KG=2 step. Round 1에서 3 trial active control 안정성 확보)

## Intent
> Open my todos page

Start URL: `http://localhost:8023`

## Hypothesis
Dashboard 사이드바에 "To-Do List → /dashboard/todos" 링크가 직접 노출되어 있다. baseline는 그 링크를 보고 1-step 클릭으로 도달. KG가 제공할 수 있는 정보 (target class, URL 템플릿, sidebar 카운트 뱃지)는 모두 *agent가 이미 페이지에서 직접 관측*하고 있는 정보이므로 KG가 baseline 대비 추가로 줄 가치가 거의 없다. **KG과 baseline의 step 수는 같아야** 한다.

## Predicted baseline
- step 1: dashboard 페이지 도달 후 "To-Do List" 링크 식별 및 클릭.
- step 2: /dashboard/todos 도달 → report_success.
- 예상 step 수: 2

## Predicted KG
- step 1: KG 힌트는 "To-Do List" 라벨을 노출하지만 baseline가 이미 보고 있는 정보. 에이전트는 동일하게 1-step에 클릭.
- step 2: report_success.
- 예상 step 수: 2

(이미 phase 0 smoke에서 baseline=KG=2 step으로 확인됨.)

## Mechanism invocation signal (KG log)
- `[KG] inferred target=dashboard/todo_list` (smoke에서 확인됨, agreement 3/3)
- KG 힌트가 baseline가 못 보던 정보를 추가로 노출하지 *않음*

## Falsification criterion (Null의 의미)
Null의 falsification은 KG=baseline가 *깨지는* 경우다.

- KG step > baseline step → KG가 *방해*. 메커니즘 모델 수정 필요.
- KG step < baseline step → KG가 baseline 가시 정보 외에 추가 신호를 주입. KG 힌트 모드 동작 검토 필요.

→ 둘 중 하나라도 성립하면 refuted (active control 실패).

## Notes
- 본 cell은 active control. 측정 instrument가 "차이 없음"을 출력할 능력을 보유함을 입증.
- KG과 baseline의 wall-clock은 KG session load + K=3 inferrer로 KG이 길지만, step 수는 같아야 함.
- Phase 0 smoke 결과 (baseline=2, KG=2): 사전 가설과 부합. 본측정 3 trial × 2 variant에서 안정성 검증.
