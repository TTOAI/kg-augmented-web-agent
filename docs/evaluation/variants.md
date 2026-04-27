# Variants

세 변종은 동일 에이전트 코드·동일 LLM·동일 task 세트 위에서 KG runtime 모듈만 다르게 활성화한다.

## V0 — baseline (KG 미사용)

KG runtime을 완전히 우회. 에이전트는 페이지 관측만으로 모든 sub-goal을 푼다.

```
KG_ENABLED=0
```

H/L/Null 모든 조건의 reference behavior. mechanism invocation log에 `[KG]` 라인이 *없어야* 한다.

## V1 — KG 최소 힌트 모드 전체 활성

KG의 세 runtime 모듈이 모두 활성화. 힌트는 minimal mode로 렌더링되어 페이지 클래스 식별자·URL 파라미터 레시피·클래스 화살표 주석을 모두 숨기고 단축 URL과 가시 요소만 노출.

```
KG_ENABLED=1
KG_MODE=minimal
```

활성 모듈:
- 타겟 클래스 추론기 (K=3 self-consistency)
- 경로 탐색기 (6단계 cascade)
- 힌트 생성기 (minimal mode)

H/L 조건의 메커니즘 가설을 검증하는 primary variant.

## V1−tc — page-surface only (target classifier 비활성)

타겟 클래스 추론기를 끄고 path/target 안내를 제거. 힌트 생성기는 현재 페이지 클래스의 액션 카탈로그·필터 카테고리·모달 트리거만 노출.

```
KG_ENABLED=1
KG_MODE=minimal
KG_DISABLE_TARGET_INFERRER=1
```

(env 키는 phase 0 마지막에 hint_generator + integration에 추가하는 게이트. 현 코드에 미존재 시 `task_cards/L1_411.md`의 implementation note에 명시한다.)

L1 (미매핑 클래스 능동적 오도) 가설 검증 전용 ablation. V1과 V1−tc 결과 차이로 "능동적 오도가 추론기 탓인가 hint 자체 탓인가"를 분리.

## 공통 환경

```
LLM_PROVIDER=anthropic
ANTHROPIC_MODEL=claude-sonnet-4-6
LLM_TEMPERATURE=0          # 재현성. K=3 inferrer는 internal seed 변동으로만 self-consistency 측정
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
output/characterization/v1_tc/<task_id>/trial_<n>/
```

각 trial 디렉터리에 `agent_response.json`, `network.har`, `webarena_verified.log`, 그리고 (post-measurement) `eval_result.json`이 위치한다.

## V1−tc 적용 범위

V1−tc는 8 task 전부에 돌릴 필요는 없다. **L1 (411) 한 task만 V1−tc trial 추가**해도 ablation 비용을 1×3=3 run으로 제한할 수 있다. 본 측정에서는 보수적으로 8 task 전체 V1−tc도 측정해 추후 다른 가설(L2/L3에서 추론기의 부수효과)도 사후 점검 가능하게 한다. 비용 부담 시 L1 단일 task만으로 축소하는 옵션은 measurement 직전 결정.
