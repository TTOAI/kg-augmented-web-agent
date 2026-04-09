# Architecture v3 — Tool Use + Done 검증

**기간**: v5 Tool Use 전환 ~ 현재  
**상태**: 현행

---

## 개요

v2의 실행 구조(sub-goal, checkpoint, retry, replan)를 유지하면서, LLM 인터페이스를 프롬프트 기반 JSON에서 Tool Use API로 전환. 프롬프트 규칙을 구조적 제약으로 대체.

```
태스크 → task_type 분류 → Planning (2~5 sub-goals)
    ↓
Sub-goal 루프 (Tool Use):
    관측(마크다운) → LLM tool call → Executor 실행 → tool_result → 반복
    done(reason) → _verify_done 검증 → 통과/거부
    ↓
    성공 → checkpoint → 다음 goal
    실패 → checkpoint 복원 → retry (8회, graduated, goback 유도)
    retry 소진 → replan (3회, Tool Use)
```

---

## 핵심 변경 (v2 대비)

### 1. Tool Use API

Anthropic/OpenAI SDK의 `tools` 파라미터로 LLM에게 구조화된 tool을 제공. LLM이 tool call로 행동을 결정하고, API가 파라미터 구조를 보장.

| v2 | v3 |
|---|---|
| `{"action": "click", "target": "X"}` 텍스트 | `click(target="X")` tool call |
| `parse_llm_action()` 파싱 필요 | API가 구조 보장 — 파싱 불필요 |
| 프롬프트 규칙 (소프트) | Tool 존재 여부 (하드) |

**파일**: `runtime/llm.py` — `LLMClient.complete_with_tools()`, `runtime/tools.py` — tool 정의

### 2. 동적 Tool 목록

sub-goal 위치에 따라 제공 tool이 달라진다:

| sub-goal 위치 | 사용 가능 tool |
|---|---|
| 중간 goal | click, fill, search, goback, observe, remember, recall, done |
| 마지막 goal (RETRIEVE) | + extract |
| 마지막 goal (NAVIGATE/MUTATE) | + failure tools (not_found, permission_denied, ...) |

goto tool 자체를 미제공 → URL 추측이 구조적으로 불가능.

**파일**: `runtime/tools.py` — `tools_for_goal()`

### 3. done 검증

LLM이 `done(reason="...")` 호출 시:
1. reason 필드 필수 — LLM이 완료 근거를 명시적으로 작성
2. `_verify_done()` — 별도 LLM 호출로 "agent의 주장 vs 실제 페이지 상태" 대조 검증
3. 미달성 시 거부 → step loop 계속

**파일**: `runtime/executor.py` — `_verify_done()`

### 4. Observation 구조화 (ACI 패턴)

평문 리스트 → 마크다운 섹션:

```
## Task / ## Current Objective / ## Last Action Result / ## Page State / ## Interactive Elements
```

**파일**: `runtime/llm.py` — `build_observation_message()`

### 5. System Prompt 축소

v2의 Rules + Actions 섹션 → Strategy 섹션만. Actions 설명은 tool definition이 대체.

```
## Strategy
1. Act on what you SEE, not what you KNOW. Click to explore.
2. Click before typing. Reveal options first.
3. After filters/options, click Search/Submit. Check URL params.
4. Never repeat a failed action. Use goback to return and try a different path.
5. Use remember to save important facts.
6. Before extract or done, use recall to verify completeness.
```

**파일**: `runtime/llm.py` — `build_tool_use_system_prompt()`

---

## 실행 구조 (v2에서 계승)

### Sub-goal 분해
- Planning: LLM 1회 호출로 2~5개 sub-goal 생성 (`build_plan()`)
- 각 goal에 navigation/action/cognition 타입
- NAVIGATE 마지막 goal = navigation 강제

### Checkpoint 스택
- goal 성공 → `checkpoint_stack.append(page.url)`
- 실패 → `page.goto(checkpoint_stack[-1])`
- 2차+ replan → 이전 checkpoint로 점진적 롤백

### Graduated Retry (8회)
- ≤2회: "goback으로 돌아가서 다른 접근"
- 3~5회: "완전히 다른 네비게이션 경로. goback 적극 활용"
- 6+회: "시작 페이지로 돌아가서 전혀 다른 경로"

### Replan (3회, Tool Use)
- `llm.complete_with_tools()` + `replan_tool()`
- 실패 goal + 이력을 전달, 새 sub-goal 목록 생성

### NAVIGATE 최종 URL 체크
- 모든 goal 완료 후, URL == 시작 URL → replan 발동

### RETRIEVE 최종 Extract
- 모든 goal 완료 후 `llm.complete_with_tools(tools=[_extract_tool()])` 1회 호출
- task_notes 포함하여 cross-check 요청

---

## Tool 목록

### Browser
| tool | 설명 | 필수 필드 |
|---|---|---|
| click | 요소 클릭 | target |
| fill | 입력 필드 텍스트 | target, value |
| search | 검색 실행 | query |
| goback | 이전 페이지 | — |

### Cognition
| tool | 설명 | 필수 필드 |
|---|---|---|
| observe | 키워드 필터링 관측 | keyword |
| remember | 사실 저장 | fact |
| recall | 저장된 사실 조회 | — |

### Terminal
| tool | 설명 | 필수 필드 |
|---|---|---|
| done | 목표 완료 선언 | reason |
| extract | 데이터 추출 (RETRIEVE) | value |
| not_found | 정보 없음 | reason |
| permission_denied | 접근 거부 | reason |
| action_not_allowed | 허용 안 됨 | reason |
| unknown_error | 알 수 없는 오류 | reason |

---

## 하이퍼파라미터

| 파라미터 | 값 | 설명 |
|---|---|---|
| max_steps | 50 | 전체 스텝 풀 |
| min budget/attempt | 6 | attempt당 최소 스텝 |
| budget 공식 | `max(6, 남은스텝 // 남은goal수)` | 균등 배분 |
| retry/goal | 8 | graduated + goback 유도 |
| replan | 3 | 1차 현재, 2차+ 롤백 |
| DOM 안정화 | 500ms × 6라운드, 연속 안정 2회 | 최대 3초 |
| messages | 10 | 최근 N개만 유지 |
| sub-goal 개수 | 2~5 | planning 시 분해 |

---

## 모듈 구조

```
site_adaptive_webagent/runtime/
├── executor.py    — 실행 엔진: sub-goal 루프, retry, replan, 클릭 매칭, done 검증
├── llm.py         — LLM 인터페이스: Tool Use protocol, planning, observation 구조화
├── tools.py       — Tool 정의: 13개 tool schema, 동적 tool 목록, 메시지 헬퍼
├── browser.py     — 브라우저 관측: observe_page, 요소 추출, 클릭/입력 실행
└── types.py       — 데이터 타입: ExecutionOutcome, PageObservation 등
```

## 참고

- `docs/archive/08_agent_execution_architecture_v5.md` — v5 초기 설계 문서
- `docs/lab_reports/005_v5_tool_use_architecture.md` — v5 전환 과정 및 벤치마크 결과
