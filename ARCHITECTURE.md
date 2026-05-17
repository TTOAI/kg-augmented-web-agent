# Architecture

이 문서는 시스템이 **어떻게** 구성되는지를 다룬다. **왜·무엇·결과**는 [README](README.md)를 참조.

시스템은 세 흐름과 그 사이의 타입 계약으로 구성된다.

1. 런타임 실행 (task 1건 수행)
2. KG 빌드 lineage (오프라인, 측정 전 1회)
3. 측정/평가 파이프라인

---

## 1. 런타임 실행 흐름

task 1건은 다음 경로로 수행된다.

```
run_webarena_verified.py            (루트 shim)
  → runner.py                       (CLI 경계: 인자 파싱 → adapter)
  → adapter.py  WebArenaVerifiedAdapter.run_task
       backup → logging → load_agent_input(검증)
       → setup_storage_state(사이트별 인증)
       → init_browser(HAR) → open_start_pages
       → run_agent(...)                          [벤치마크 무관]
       → classify_outcome(중립 판정 → status)
       → write_agent_response(agent_response.json) + network.har
  → agent/core.py  run_agent          (composition root)
       make_llm_client → analyze_intent → observe_page
       → build_kg_session              [KG_ENABLED일 때, 아니면 None=baseline]
       → execute_with_llm → ExecutionOutcome → AgentRunResult
  → runtime/executor.py  execute_with_llm   (2중 루프 실행 엔진)
```

### 1.1 벤치마크 어댑터 (`benchmarks/webarena_verified/`)

어댑터는 벤치마크와 **파일 계약**으로만 소통한다: tasks JSON이 입력, `agent_response.json` + `network.har`이 출력. 어댑터가 양끝을 fail-fast로 검증·번역하며, 에이전트는 파일 형식을 모른다. `adapter.py`가 인증(사이트별 UI 로그인 또는 header 기반)·브라우저/컨텍스트 수명·HAR 기록·출력 검증을 소유한다.

### 1.2 실행 엔진 (`runtime/executor.py`)

`execute_with_llm`은 **2중 루프 + 점진 복구 + 검증 게이트 + 예산 가드**로 구성된다.

- **바깥 루프** (`execute_with_llm`): `build_plan`(LLM)으로 sub-goal 목록을 만들고, sub-goal마다 `step_budget`을 남은 예산에서 공정 분배한 뒤 안쪽 루프를 호출한다. 실패 시 복구 ladder를 탄다.
- **안쪽 루프** (`_try_sub_goal`): step마다 `observe_page` → (KG가 있으면) advisory 힌트 합성·주입 → tool-use LLM → tool 실행 → 피드백. tool로 종결(`report_success`/`report_failure`)을 선언한다.

**복구 ladder (3단)**:

```
retry      : 같은 sub-goal 재시도 + checkpoint URL 복원 (_MAX_RETRIES_PER_GOAL, 기본 2)
  ↓ 소진
replan     : 실패 지점 이후 계획을 새로 생성 (_MAX_REPLANS_PER_TASK, 기본 1)
             2차+ replan은 deep rollback (이전 checkpoint로 되감기 — 기본값에선 미발동)
  ↓ 소진
stuck      : 더 복구할 수 없음 → 종결
```

`checkpoint_stack`은 성공한 sub-goal의 도착 URL을 쌓는다. retry는 마지막 checkpoint로 복원하고, deep rollback은 마지막 checkpoint를 버려 직전 sub-goal부터 다시 계획한다.

**검증 게이트 `_verify_done`**: 의도적으로 최소화된 단일 hard-rule. 마지막 sub-goal이 navigation 타입인데 task·sub-goal 두 기준 URL 모두 변하지 않았으면(이동 환각) reject, 그 외에는 에이전트의 `report_success`를 그대로 수용한다. RETRIEVE의 정답 검증은 벤치마크 evaluator에 위임한다(에이전트가 자기 답을 self-judge하면 ablation 교란·환각 rubber-stamp 위험). reject는 종결이 아니라 피드백 주입 후 ReAct 루프를 계속한다(연속 3회 이상이면 강화 피드백).

**예산 가드 (독립 2차원)**:

- `_CountingLLMClient`: task 전역 LLM 호출 총량 상한(기본 200). 초과 시 예외로 탈출 → `stuck`.
- `step_budget`: sub-goal별 ReAct step 상한. 남은 step을 남은 sub-goal 수로 균등 분배(하한 6).

### 1.3 중립 판정과 상태 분리

에이전트는 벤치마크를 모르는 **중립 판정(verdict)** 만 배출한다: `done_with_answer` / `done_no_answer` / `abandoned` / `stuck` / `sub_goal_failed`. `sub_goal_failed`만 terminal이 아니라 바깥 루프에 retry/replan 신호이고 나머지는 task 종결이다.

`classify_outcome`(`outcome_classifier.py`)이 이 중립 판정을 WebArena-Verified status enum으로 번역한다 — 에이전트/런타임과 벤치마크 사이의 **유일한 결합 지점**. 결정적인 것은 hard-rule(`stuck`→`UNKNOWN_ERROR`, `done_no_answer`→`SUCCESS`), 모호한 것(`done_with_answer` RETRIEVE / `abandoned`)만 LLM으로 의미적 실패 모드를 분류한다. LLM이 없어도 hard-rule로 완결되어 offline에서 안전하다.

### 1.4 KG 런타임 (`kg/runtime/`)

`build_kg_session`이 자산·LLM·설정·노브를 `KGSession` 하나로 조립한다. `KGSession`이 None이면 baseline과 **동일 경로**다(KG는 advisory·additive — 힌트 문자열만 주입, 실행 루프는 KG 유무에 불변).

- **`task_inferrer`**: sub-goal을 닫힌 class 집합으로 매핑하는 K-sample self-consistency 분류기(기본 K=3). 닫힌 집합 밖 응답은 reject(환각 차단). strict majority `floor(K/2)+1` 미달이면 `target_class=None` → 힌트 없음(틀린 힌트보다 무힌트가 낫다는 설계 선택). sub-goal당 1회, retry 간 캐시.
- **`path_finder`**: class edge graph 위 6-stage cascade — `failed`(입력 검증) → `exact`(BFS 최단경로) → `family_sibling` → `scope_entry` → `hub_fallback` → `stay_and_explore`. BFS는 trust(high→low) 우선으로 펼쳐 동일 hop에서 신뢰도 높은 edge를 먼저 잡는다. exact가 없으면(다른 graph component) 거리 비교가 무의미하므로 cascade 단계 순서 자체가 semantic progress를 강제한다.
- **`hint_generator`**: strategy별 분기 — `failed`→힌트 없음(baseline) / `exact`·`stay_and_explore`→규칙 템플릿(LLM 호출 0, 결정적·재현 가능) / cascade fallback→LLM+캐시(cross-class 라우팅의 자연어 설명). 힌트는 항상 `[KG navigation hint — advisory]` 접두를 달아 참고용임을 명시한다.

**KG 설계 원칙**: KG는 **구조 정보**(어떤 page class·경로·필터 카테고리·컨트롤이 존재하는지)까지만 노출하고, **구체값**(필터 값·URL 쿼리 값·자유 텍스트)은 에이전트가 페이지를 직접 보고 수집한다. 이 분리의 근거는 [README](README.md#접근) 참조.

---

## 2. KG 빌드 lineage (오프라인)

런타임이 읽는 KG 자산은 측정 전 1회 오프라인으로 빌드된다.

```
kg/seed/run_crawl → run_derivation → run_freeze     (hybrid: crawl + LLM + manual)
   → config/sites/<site>/frozen_kg/<timestamp>.json
scripts/kg/build/*  (classify_rules가 frozen_kg를 reference로 소비 + 자체 crawl)
   → output/validation/{rules, stage_c, kg_solution, stage_b}.json
build_kg_session 이 위 4개를 DEFAULT_*_PATH로 로드             → 측정
```

두 파이프라인은 경쟁이 아니라 **직렬 lineage**다(hybrid 자동 빌드 → frozen_kg → Stage A/B/C → runtime). 빌드와 런타임은 분리된다: 오프라인이 `output/validation/*`를 생산하고, 런타임은 읽기만 하며, 측정이 런타임을 baseline/KG로 반복한다.

class별 `triggers`/`not_for`(target 추론 disambiguation 신호)는 `scripts/kg/build/class_catalog.py`가 scope×role 보편 규칙(코드)과 사이트별 어휘(site plugin extras)로 결정적으로 생성한다 — 특정 사이트 어휘를 코드에 박지 않는다.

KG 구축 프로토콜은 [`docs/method/`](docs/method/), seed 검증 보고서는 [`docs/validation/`](docs/validation/) 참조.

---

## 3. 측정/평가 파이프라인 (`scripts/eval/`)

```
run_round_{1,2}.sh
   task × {v0=baseline(KG_ENABLED=0), v1=KG(KG_ENABLED=1, KG_MODE=minimal)} × 3 trial
   → output/characterization/{v0,v1}/<task>/trial_*/{webarena_verified.log, agent_response.json}
extract_signals  → trial별 signals.json (외부 공식 채점 + 자체 측정 로그 합본)
aggregate_cells  → (task × variant) cell 집계 (cells.json, cells_summary.md)
render_figures   → figures/ (step 분포 박스플롯, median 막대)
                 + condition_synthesis.md
```

- **단일 노브 ablation**: baseline(v0)과 KG(v1)는 코드 경로가 동일하고 env 스위치 2개(`KG_ENABLED`, `KG_MODE`)만 다르다. 교란변수를 최소화한다.
- **비침습 측정**: `extract_signals`는 실행 경로에 개입하지 않고 로그를 사후 정규식 파싱한다. `network.har`는 그대로 둔다.
- **외부 채점 + 자체 측정 합본**: 성공/실패(`agent_evaluator`/`network_evaluator`)는 외부 공식 채점기(`webarena-verified eval-tasks`)가 정하고, step·token·trajectory·KG mechanism은 로그에서 자체 측정한다. 둘이 trial별 `signals.json`으로 합쳐진다.
- **정직한 집계**: cell 단위 다수결이 갈리면 `mixed`로 표기하고, timeout은 median에서 분리하며, 결측 cell은 명시한다.
- **paired 통계**(`paired_stats.py`): McNemar exact + Wilcoxon signed-rank + Wilson CI + Bonferroni를 scipy 의존 없이 자체 구현(reviewer 즉시 재현). 같은 task를 v0 vs v1로 paired 비교해 task 난이도 교란을 제거하고, binary(성공)와 continuous(비용)를 분리 검정한다. 단 이 스크립트는 `analyze_baseline.py` 산출 `paired.csv`를 입력으로 하는 별도 분석 라인으로, characterization 경로의 종착은 `condition_synthesis.md` + `figures/`다.

task 선정·metric·exclusion 정책은 [`docs/evaluation/`](docs/evaluation/) 참조.

---

## 4. 타입 계약 (레이어 경계)

| 모듈 | 정의 |
|---|---|
| `runtime/types.py` | `IntentPlan` · `PageObservation` · `ExecutionOutcome` · `AgentVerdict` · `TaskType` · `BrowserSession` |
| `agent/types.py` | `AgentRunResult` (중립 판정, 벤치마크 무관) |
| `benchmarks/webarena_verified/types.py` | `WebArenaRunResult` · `WebArenaStatus` · `TASK_LOG_FILENAME` |
| `kg/types.py` | `SiteKG` 스키마: `StatePattern` · `InfoType` · `Action` · `RealizesEdge` · `LeadsToEdge` · `SiteConfig` · `IdentityParam` |

---

## 5. 핵심 설계 경계·불변식

- **agent/runtime은 벤치마크 무관.** 에이전트는 중립 판정만 배출하고, WebArena status는 `classify_outcome`만 안다 — 유일한 결합 지점.
- **KG는 advisory·additive.** `build_kg_session`이 None이면 baseline과 동일 경로. KG는 힌트 문자열만 주입, 실행 루프는 KG 유무에 불변. ablation 노브가 전부 KG 주입 지점 한 곳으로 수렴.
- **빌드 ↔ 런타임 분리.** 오프라인이 `output/validation/*` 생산, 런타임이 읽기만, 측정이 baseline/KG로 반복.
- **벤치마크는 파일 계약으로 소통.** tasks JSON in → agent_response.json + network.har out. 어댑터가 양끝을 fail-fast로 검증·번역.
