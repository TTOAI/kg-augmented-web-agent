# 비교 변종

본 측정은 두 에이전트만 비교한다. 동일 에이전트 코드·동일 LLM·동일 task 위에서 KG runtime 모듈 활성 여부만 다르다.

## baseline 에이전트 (KG 미사용)

KG runtime 완전 우회. 에이전트는 페이지 관측만으로 모든 sub-goal을 푼다.

```
KG_ENABLED=0
```

mechanism invocation log에 `[KG]` 라인이 *없어야* 한다. 코드 변종 식별자: `v0`.

## KG 에이전트

KG의 세 runtime 모듈이 모두 활성화. 힌트는 KG 힌트 모드(`KG_MODE=minimal`)로 렌더링되어 페이지 클래스 식별자·URL 파라미터 레시피·클래스 화살표 주석을 모두 숨기고 단축 path와 가시 컨트롤만 노출. 설계 원칙 "KG는 방향, 에이전트는 값" ([`setup.md`](setup.md) §KG 힌트 설계 원칙) 그대로 구현.

```
KG_ENABLED=1
KG_MODE=minimal
```

활성 모듈:
- 타겟 클래스 추론기 (K=3 self-consistency)
- 경로 탐색기 (6단계 cascade)
- 힌트 생성기 (KG 힌트 모드 — example values, option values, default values, placeholder 모두 suppress)

코드 변종 식별자: `v1`.

## 공통 환경

```
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-5.4-mini
LLM_TEMPERATURE=0
LLM_REQUEST_TIMEOUT=300
MAX_RETRIES_PER_GOAL=8
MAX_REPLANS_PER_TASK=3
LLM_CALL_LIMIT_PER_TASK=450
MAX_STEPS_PER_TASK=60
```

## 산출물 디렉터리

```
output/characterization/v0/<task_id>/trial_<n>/   # baseline
output/characterization/v1/<task_id>/trial_<n>/   # KG
```

각 trial 디렉터리에 `agent_response.json`, `network.har`, `webarena_verified.log`, 그리고 (post-measurement) `eval_result.json`이 위치한다.
