# Variants

본 측정은 두 변종만 사용한다. 동일 에이전트 코드·동일 LLM·동일 task 위에서 KG runtime 모듈 활성 여부만 다르다.

## V0 — baseline (KG 미사용)

KG runtime 완전 우회. 에이전트는 페이지 관측만으로 모든 sub-goal을 푼다.

```
KG_ENABLED=0
```

H/L/Null 모든 조건의 reference behavior. mechanism invocation log에 `[KG]` 라인이 *없어야* 한다.

## V1 — KG 최소 힌트 모드

KG의 세 runtime 모듈이 모두 활성화. 힌트는 minimal mode로 렌더링되어 페이지 클래스 식별자·URL 파라미터 레시피·클래스 화살표 주석을 모두 숨기고 단축 path와 가시 컨트롤만 노출. design principle "KG는 방향, agent는 값" ([`setup.md`](setup.md) §KG hint design principle) 그대로 구현.

```
KG_ENABLED=1
KG_MODE=minimal
```

활성 모듈:
- 타겟 클래스 추론기 (K=3 self-consistency)
- 경로 탐색기 (6단계 cascade)
- 힌트 생성기 (minimal mode — example values, option values, default values, placeholder 모두 suppress)

H/L/Null 모든 조건의 primary measurement variant.

## V1−tc — 본 측정 범위 외

V1−tc (target inferrer 비활성, page-surface only) variant는 pilot에서 page-surface info의 자체 효과로 clean control이 아님이 드러나 본 측정에서 제외. 상세 사유는 [`round_protocol.md`](round_protocol.md) §4. 코드 게이트 `KG_DISABLE_TARGET_INFERRER`는 dead-code로 유지되어 future ablation 시 즉시 재활성 가능.

## 공통 환경

```
LLM_PROVIDER=anthropic
ANTHROPIC_MODEL=claude-sonnet-4-6
LLM_TEMPERATURE=0
LLM_REQUEST_TIMEOUT=300
MAX_RETRIES_PER_GOAL=8
MAX_REPLANS_PER_TASK=3
LLM_CALL_LIMIT_PER_TASK=450
MAX_STEPS_PER_TASK=60
```

## 산출물 디렉터리

```
output/characterization/v0/<task_id>/trial_<n>/
output/characterization/v1/<task_id>/trial_<n>/
```

각 trial 디렉터리에 `agent_response.json`, `network.har`, `webarena_verified.log`, 그리고 (post-measurement) `eval_result.json`이 위치한다.
