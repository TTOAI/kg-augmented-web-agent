# Lab Report 005 — v5 Tool Use 아키텍처 전환

**날짜**: 2026-04-09  
**목적**: 프롬프트 기반 JSON 생성(v4)에서 Tool Use API 기반 구조적 제약(v5)으로 전환하여, baseline 에이전트의 아키텍처를 최신 에이전트 엔지니어링 기법으로 업그레이드.

---

## 동기

v4는 LLM에게 "JSON으로 응답해라"고 프롬프트로 부탁하고 텍스트를 파싱하는 구조였다. 이 접근의 근본적 한계:

1. **규칙 위반이 구조적으로 불가능하지 않다** — "goto 금지"를 프롬프트에 써도 LLM이 어길 수 있음
2. **JSON 파싱 취약** — 마크다운 펜스 누락, 불완전 JSON 등 파싱 실패
3. **정보 수집이 수동적** — NOTE/note 메커니즘을 프롬프트에 설명해도 LLM이 일관되게 사용하지 않음
4. **규칙이 많을수록 LLM 판단이 흐려짐** — 컨텍스트 비대화

프로젝트의 가설 검증(Prior 효과 측정)을 위해, baseline 자체를 현재 최선의 아키텍처로 구성하기로 결정.

---

## v5 핵심 변경

### 1. Tool Use API 전환

Anthropic/OpenAI SDK의 `tools` 파라미터를 사용하여, LLM이 구조화된 tool call로 행동을 결정.

| v4 | v5 |
|---|---|
| System prompt에 JSON 형식 설명 | Tool definition (JSON Schema) |
| `parse_llm_action()` 텍스트 파싱 | API가 구조 보장 — 파싱 불필요 |
| 프롬프트 규칙 (소프트 제약) | Tool 존재 여부 (하드 제약) |

**파일**: `runtime/llm.py` — `LLMClient.complete_with_tools()` Protocol + Anthropic/OpenAI 구현

### 2. 동적 Tool 목록

sub-goal 위치에 따라 제공되는 tool이 달라진다:

| sub-goal 위치 | 사용 가능 tool |
|---|---|
| 중간 goal | click, fill, search, goback, observe, remember, recall, done |
| 마지막 goal (RETRIEVE) | + extract |
| 마지막 goal (NAVIGATE/MUTATE) | + failure tools |

**핵심**: goto tool 자체를 미제공 → 구조적으로 URL 추측 불가. extract는 마지막 RETRIEVE goal에서만 제공 → 조기 추출 불가.

**파일**: `runtime/tools.py` — `tools_for_goal()`, 13개 tool 정의

### 3. Observation 구조화 (ACI 패턴)

평문 리스트 → 마크다운 섹션 구조:

```
## Task / ## Current Objective / ## Last Action Result / ## Page State / ## Interactive Elements
```

SWE-agent(Yang et al., 2024)의 Agent-Computer Interface 패턴 적용.

**파일**: `runtime/llm.py` — `build_observation_message()`

### 4. System Prompt 축소

v4의 Rules + Actions 섹션 → v5의 Strategy 섹션만. Actions 설명은 tool definition이 대체하므로 프롬프트에서 제거. 분량 50%+ 축소.

**파일**: `runtime/llm.py` — `build_tool_use_system_prompt()`

### 5. Replan도 Tool Use 전환

`_replan()`이 `llm.complete()` + `parse_llm_action()` → `llm.complete_with_tools()` + `replan_tool()`. Executor에서 JSON 파싱(`parse_llm_action`) 의존 완전 제거.

### 6. Dead code 정리

- `_execute_goto()` 함수 제거 (tool 미제공으로 도달 불가)
- `_summarize_action_result()`의 goto 분기 제거
- 미사용 import 정리

---

## OpenAI Tool Use 호환성 이슈

### parallel_tool_calls

OpenAI가 여러 tool call을 동시 반환 → 첫 번째만 처리하고 나머지 tool_result 미응답 → API 에러.

**해결**: `parallel_tool_calls=False` 설정으로 1턴 1 tool call 강제.

### 메시지 트리밍과 tool_use/tool_result 쌍 무결성

대화 히스토리를 `_MAX_MESSAGES`로 트리밍할 때, assistant(tool_use)와 대응하는 user(tool_result)가 분리되면 OpenAI가 거부.

**해결**: `_trim_messages()` — 트리밍 후 orphaned tool_call_id 메시지를 자동 제거.

### browser action 후 tool_result 누락

browser action 실행 후 `format_tool_result()`를 messages에 추가하지 않으면, 다음 user(observation) 메시지가 tool_result 없이 바로 오게 됨.

**해결**: browser action 경로에도 `messages.append(format_tool_result(...))` 추가.

---

## Skill Library 시도 및 철회

### 시도한 것

169(multi-value RETRIEVE)에서 LLM이 remember를 일관되게 호출하지 않는 문제를 해결하기 위해:

- `scan_and_remember` skill: 현재 페이지에서 task 관련 사실을 자동 식별+저장
- `verified_extract` skill: 저장된 facts와 대조하여 검증된 답 추출
- Planning 프롬프트에 "scan_and_remember 사용" 단계 명시

### 결과

| 실행 | 두 값 찾음 | ID 반환 | 비고 |
|---|---|---|---|
| Skill + plan 1차 | O | X (이름 반환) | scan_and_remember 16 facts 저장 |
| Skill + plan 2차 | X | X | LLM이 엉뚱한 경로 |
| Skill + plan 3차 | O | X (이름 반환) | 205초 소요 |

### 철회 이유

1. LLM이 skill을 일관되게 활용하지 못함 — **LLM 비결정성이 병목**
2. scan_and_remember가 저장하는 fact에 ID가 포함되지 않으면 verified_extract도 무의미
3. 코드 복잡도 증가 대비 효과 불안정

**결론**: Skill Library는 Prior 이후에 재방문. 현재는 v5 baseline 유지.

---

## 빠른 실패 + 다양한 retry

### 변경

| 파라미터 | 이전 (v4) | 이후 (v5) | 이유 |
|---|---|---|---|
| min step budget | 10 | **6** | 잘못된 길에서 빠르게 탈출 |
| retry/goal | 5 | **8** | 더 다양한 접근 시도 |

### Graduated retry 3단계

| 구간 | 피드백 |
|---|---|
| ≤2회 | "goback으로 돌아가서 다른 접근 시도" |
| 3~5회 | "완전히 다른 네비게이션 경로. goback 적극 활용" |
| 6+회 | "시작 페이지로 돌아가서 전혀 다른 경로" |

### Strategy rule 4 변경

"Try a different approach" → "Use goback to return to a known page and try a different path"

---

## done 검증

### 문제

LLM이 목표 미달성 상태에서 done을 선언하는 경우가 빈번. 예: 339에서 bug 필터 미적용 상태에서 done → 이후 goal들이 필터 없는 상태에서 시작.

### 해결: 2중 검증

1. **done tool에 reason 필드 추가** (required) — LLM이 완료 근거를 명시적으로 적어야 함
2. **`_verify_done()` LLM 검증** — 별도 LLM 호출로 "agent가 이렇게 주장하는데 실제 페이지와 맞나?" 확인

```
done(reason="URL contains label_name=bug") → _verify_done(goal, reason, current_obs) → achieved: true/false
```

미달성 시: "Done rejected — goal not yet achieved: {이유}. Keep working." 피드백 → step loop 계속.

**원칙 3 준수**: executor가 판단하지 않음. LLM이 검증.

---

## 최종 벤치마크 결과

### Task 339 (NAVIGATE — bug 필터 적용)

| 버전 | 결과 | 시간 | 스텝 |
|---|---|---|---|
| v4 baseline | 비결정적 (18~99초) | — | — |
| v5 + done 검증 | **SUCCESS** | **41.2s** | **16** |

### Task 45 (NAVIGATE — 최근 이슈)

| 버전 | 결과 | 시간 | 스텝 |
|---|---|---|---|
| v4 baseline | SUCCESS | 44.3s | 6 |
| v5 + done 검증 | **SUCCESS** | **16.6s** | **8** |

### Task 357 (NAVIGATE — MR 리뷰)

| 버전 | 결과 | 시간 | 스텝 |
|---|---|---|---|
| v4 baseline | SUCCESS | 8.0s | 4 |
| v5 + done 검증 | **SUCCESS** | **9.4s** | **4** |

### Task 169 (RETRIEVE — 프로젝트 ID 다수 추출)

| 버전 | 결과 | 시간 | 스텝 |
|---|---|---|---|
| v4 baseline | `["183"]` (하나만) | 126.1s | 24 |
| v5 + done 검증 | **`["183", "187"]` (정답)** | **173.2s** | **45** |

169는 **처음으로 완전한 정답**을 추출. 시간이 긴 건 LLM이 search 페이지에서 헤매다 결국 프로젝트 목록으로 복귀한 것 — Prior가 해결할 영역.

---

## 현재 아키텍처 요약

```
태스크 수신 → task_type 분류 → Planning (2~5 sub-goals)
    ↓
Sub-goal 루프 (Tool Use ReAct):
    관측 → LLM tool call → Executor 실행 → tool_result → 반복
    done(reason) → _verify_done → 통과/거부
    ↓
    성공 → checkpoint → 다음 goal
    실패 → checkpoint 복원 → retry (8회, graduated, goback 유도)
    retry 소진 → replan (3회, Tool Use)
```

### 변경되지 않은 것

- Checkpoint 스택 + 점진적 롤백
- DOM 안정화 (연속 안정 2x, 500ms, 최대 3초)
- 클릭 매칭 6단계 (드롭다운 → element_type → 충돌감지 → links → role → fallback)
- 콘텐츠 delta 피드백
- NAVIGATE 최종 URL 체크

---

## 다음 단계

1. **Prior layer 구현** — 가설 검증의 핵심. 사이트별 사전 지식 주입.
2. **169 시간 개선** — LLM이 search 페이지에서 헤매는 문제는 Prior("프로젝트 목록은 /users/byteblaze/projects")로 해결 가능.
3. **더 많은 task 벤치마크** — 현재 4개만 측정. GitLab 전체 task 커버리지 확대.
