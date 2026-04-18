# 05. 구현 아키텍처 (상위 레벨)

## 이 문서의 scope

쟁점 #2~#4 결정을 코드로 옮기기 위한 **상위 레벨 구조**만 정리한다. 구체 dataclass 필드, InfoType 카탈로그, URL 정규화 세부 규칙 등은 Phase 2 결과를 본 뒤 결정.

목표: Phase 2 완료 직후 구현에 바로 착수 가능한 상태로 아키텍처·모듈 경계·통합 지점을 확정.

---

## 1. 디렉토리 레이아웃

기존 baseline(`site_adaptive_webagent/`)을 건드리지 않고 KG를 옆에 두는 구조.

```
site_adaptive_webagent/
├── agent/                          # 기존 baseline
│   ├── core.py                     # run_agent (KG hook 추가 지점)
│   └── types.py
├── runtime/                        # 기존 baseline
│   ├── browser.py
│   ├── executor.py                 # sub-goal loop (KG hook 추가 지점)
│   ├── llm.py
│   └── tools.py
├── kg/                             # [신규] KG 모듈
│   ├── types.py                    # StatePattern / InfoType / Action / Trust (schema: Phase 2 후 확정)
│   ├── store.py                    # 그래프 저장소 (노드·엣지 관리, 조회)
│   ├── query.py                    # 4 primitive 연산 구현
│   │   ├─ route_to
│   │   ├─ final_state
│   │   ├─ state_matches
│   │   └─ emit_url
│   ├── rewrite.py                  # (b) plan rewrite 파이프라인
│   ├── validator.py                # (c) runtime state validation
│   ├── trust.py                    # trust 평가·업데이트 정책
│   ├── urlnorm.py                  # URL 정규화 (site config + StatePattern 규칙)
│   ├── io.py                       # KG 저장/로드 (JSON/YAML)
│   └── seed/
│       ├── manual_config.py        # site_config.yaml 로더
│       ├── infotype_catalog.py     # infotypes.yaml 로더
│       ├── seed_loader.py          # 3 source를 병합해 SiteKG 구성
│       ├── playwright_crawler.py   # [Stage 1] 관찰 기반 자동 수집 → verified
│       │                              (signature dedupe, download blocklist, form action_url
│       │                               cross-target lookup)
│       ├── crawl_to_kg.py          # CrawlResult → SiteKG 변환 (form input → LeadsToEdge)
│       ├── llm_derivation.py       # [Stage 2] LLM derivation (3-call 분할):
│       │                              Call 1: state pattern grouping
│       │                              Call 2: InfoType + realize (group_id 참조)
│       │                              Call 3: action renames
│       │                              → Responses API + reasoning_effort=low
│       ├── derivation_to_kg.py     # DerivationResult → llm SiteKG (group expansion)
│       ├── post_enrich.py          # [Stage 2.5] LLM 재호출 없이 schema 결함 보강
│       │                              (binding_map, path_params, query_params, category)
│       │                              source 유지: inferred
│       ├── run_crawl.py            # CLI: Stage 1 entrypoint
│       ├── run_derivation.py       # CLI: Stage 2 entrypoint
│       └── run_freeze.py           # CLI: 통합 + post_enrich + immutable snapshot
├── agent/
│   └── kg_integration.py           # [신규] 기존 agent와 kg 모듈을 잇는 얇은 bridge
config/
├── sites/
│   └── gitlab/
│       ├── site_config.yaml        # URL 정규화 / identity tokens / aliases
│       ├── infotypes.yaml          # InfoType 카탈로그
│       └── kg_seed.json            # 초기 KG (crawl + 수동 병합 결과)
```

### 모듈 책임 원칙

- **types**: 데이터만. 연산 없음.
- **store**: 그래프 구조의 CRUD. 노드 추가, 엣지 추가, 필터 조회. 질의 의미는 모름.
- **query**: 4 primitive 구현. store를 소비하되 store의 구조는 추상화.
- **rewrite/validator**: query를 사용하는 상위 로직. baseline에 노출되는 진입점.
- **trust**: 정책만. store 수정 권한 있음.
- **urlnorm**: 순수 함수 모음. 다른 모듈에서 util로 호출.
- **io**: 직렬화만.
- **seed**: 오프라인 실행. 런타임 경로엔 없음.

---

## 2. Baseline과의 통합 지점 (4 hook)

```
run_agent(intent, pages):
  task_type = analyze_intent(intent)                        # 기존

  ┌── HOOK A: KG plan_to_info ─────────────────────────┐
  │ lookup = kg.query.plan_to_info(intent, task_type)   │
  │   → (infotype, bindings) 또는 None (fallback)       │
  └─────────────────────────────────────────────────────┘

  sub_goals = build_plan(intent, task_type, obs)             # 기존

  ┌── HOOK B: KG rewrite ──────────────────────────────┐
  │ if lookup is not None:                              │
  │   sub_goals = kg.rewrite.apply(sub_goals, lookup,   │
  │                                trust_policy)        │
  │   # trust-adaptive: verified-only/all/none          │
  └─────────────────────────────────────────────────────┘

  for sub_goal in sub_goals:
    _try_sub_goal(sub_goal):
      loop:
        observation = observe_page()
        tool_call = llm.complete_with_tools(obs, sub_goal)
        execute(tool_call)

        ┌── HOOK C: KG validator ─────────────────────┐
        │ if lookup is not None:                       │
        │   if kg.validator.target_reached(            │
        │         current_url, lookup.target):         │
        │     return SUCCESS                           │
        │   # early termination                        │
        └──────────────────────────────────────────────┘

        if verify_done(sub_goal): break

  result = AgentRunResult(...)

  ┌── HOOK D: KG trust update ─────────────────────────┐
  │ if lookup is not None:                              │
  │   kg.trust.record(lookup, path_taken, result)       │
  │   # verified → declared → inferred 승격/강등        │
  └─────────────────────────────────────────────────────┘

  return result
```

### Hook 설계 원칙

- **fallback은 조용히**: `plan_to_info`가 None을 반환하면 기존 baseline 흐름으로. KG 없었던 것처럼 동작.
- **rewrite·validator는 optional**: KG 호출 실패·trust 부족 시 baseline plan을 그대로 사용.
- **trust update는 side effect**: 실패해도 agent run 결과에 영향 없음. 로깅만.
- **baseline의 기존 hard rule과의 상호작용**: rewrite가 plan을 축약하면 hard rule 충돌이 자동 완화됨. 별도 처리 불필요.

---

## 3. KG 초기화와 주입 흐름

```
시작 시:
  kg = KG.from_disk("config/sites/gitlab/kg_seed.json")
  kg.site_config = SiteConfig.from_yaml("config/sites/gitlab/site_config.yaml")
  kg.infotype_catalog = InfoTypeCatalog.from_yaml(
    "config/sites/gitlab/infotypes.yaml")

  run_agent(intent, pages, kg=kg)

끝난 뒤:
  kg.save_trust_snapshot(f"output/<run_id>/trust_snapshot.json")
  # Continual 셋업에서는 kg 자체를 다음 run으로 넘김
```

### Continual 셋업 (주장 7 — trust evolution)

```
kg = initial_kg
for i in range(N_rounds):
  for task in task_pool:
    run_agent(task, pages, kg=kg)
  kg.save_trust_snapshot(f"round_{i}.json")
```

trust가 success/fail 피드백으로 업데이트되면서 다음 round의 rewrite 행동이 달라짐.

---

## 4. 주요 데이터 흐름 — task 339 예시

```
intent: "Go to the list of all opened issues that report bugs for the current project"

HOOK A:
  plan_to_info(intent, "NAVIGATE")
  → LLM tool use → plan_to_info(
      target_infotype="issues_filtered",
      bindings={project="a11yproject/...", label="bug", state="opened"})
  → lookup = (infotype, bindings, target_state_pattern)

build_plan → ["Open project page [nav]", "Navigate to issues [nav]",
             "Apply label filter [action]", "Arrive at URL [nav]"]  (4 sub-goals)

HOOK B:
  rewrite.apply(sub_goals, lookup, trust_policy="adaptive")
  → query.route_to(infotype, bindings)
  → query.final_state(path) 시뮬레이션
  → 경로가 target_state_pattern과 state_matches
  → 모든 엣지 trust == verified
  → rewrite: ["Navigate to /.../issues?state=opened&label_name[]=bug"]
     (single navigate_to)

executor loop:
  step 1: navigate_to(URL)
  HOOK C: validator.target_reached → True → SUCCESS

HOOK D:
  trust.record(lookup, path=[navigate_to_url], success=True)
  → 모든 verified 엣지 trust 유지
```

축약 불가능한 case (예: MUTATE form):
- rewrite가 plan을 건드리지 않거나 부분 재작성
- executor는 multi-step으로 실행
- HOOK C가 의미 있는 early termination을 못 할 수 있음 → 기존 verify_done이 처리

---

## 5. Variant 구현 매핑 (쟁점 #4, scope 축소 반영)

본 논문은 **2 variant만** 비교 (`07_scope_and_justifications.md §5`, `02 쟁점 #4-1`):

| variant | HOOK A | HOOK B | HOOK C | HOOK D |
|---|---|---|---|---|
| **Baseline** | ✗ | ✗ | ✗ | ✗ |
| **Full KG** (본 연구) | ✓ | ✓ (trust=verified/declared/inferred, Option B) | ✓ (NAVIGATE only) | ✓ (로깅 전용, trust 변동 없음) |

### Hook A path-slot guidance (2026-04-18 Phase 2C)
- `build_plan_to_info_tool` + `build_plan_to_info_system_prompt`가 각 InfoType별
  path_slots (namespace, project_path, ref 등)을 명시
- LLM에게 "Path slot extraction" rule 제공 → MUT task에서도 path slot을 bindings에 포함
- 기존 required/optional_bindings + 신규 path_slots 3단 표기

### Runtime context auto-fill (2026-04-18 Phase 2C, C2)
- `executor._update_runtime_context_from_url(page.url, kg_context)` 초기 1회 호출
- 모든 StatePattern에 대해 URL → path_params slot 추출 (`urlnorm.extract_path_slots_from_url`)
- `kg_context.runtime_context["path_slots"]` dict에 병합
- `emit_target_url`이 bindings 우선, runtime_context.path_slots fallback
- 목적: Hook A가 bindings={} 반환해도 agent 현재 URL의 slot으로 Hook B가 rewrite 가능

### Hook B trust policy (2026-04-18 Option B)
- verified / declared / inferred 전부 수용 (2026-04-17 verified-only 정책에서 확장)
- Malformed URL (unfilled `{slot}`) 만 skip (Incomplete URL guard in `kg/rewrite.py`)
- 자세한 규칙: `07 §14 Trust policy` 참조

### Hook C early-termination gate (2026-04-18 Issue #1 fix)
- `kg/validator.py:target_reached(..., task_type)`에 task_type 인자 추가
- NAVIGATE: URL 도달만으로 SUCCESS 선언 → early-termination 활성
- RETRIEVE / MUTATE: URL 도달만으로 불충분 (data 추출 / form submit 필요) → suppress
- `executor.py`의 Hook C caller가 현 task_type 명시 전달

하나의 `kg_integration.py`에 `enabled_hooks: set[Hook]` 파라미터로 control:
- Baseline: `enabled_hooks = set()`
- Full KG: `enabled_hooks = {A, B, C, D}`

### 확장 가능 (future work용)

동일 구조로 추가 가능한 variant (현 논문에서는 비실험):

| variant | 정의 | 용도 |
|---|---|---|
| compute-matched no-KG | Baseline + retry/longer CoT | 단순 compute 증가 vs KG 분리 |
| URL-emission-only | A + B(emit_url만) | plan rewrite 기여 분리 |
| KG-retrieval | A + B(facts prompt 주입) | retrieval vs structural operator 분리 |

코드베이스 설계는 이 확장을 수용하도록 만들되, 본 논문 실험에선 **Baseline / Full KG** 두 개만 돌림. 후속 연구에서 `enabled_hooks` 조합만 바꿔 확장 가능.

---

## 5-1. Multi-call LLM derivation — 3-call decomposition 상세

Stage 2 (LLM derivation)는 reasoning model의 single-call context overflow + tool-call
complexity 문제를 피하기 위해 **3개의 독립 tool call**로 분할한다. `site_adaptive_webagent/
kg/seed/llm_derivation.py`에 구현됨.

### Pipeline

```
CrawlResult
    │ (StatePattern 3040개, literal URL)
    ▼
┌──────────────────────────────────────────────────┐
│ Call 1 — derive_state_pattern_groups             │
│   Input:  literal StatePattern list              │
│   Output: {group_id: [pattern_id, ...]} +        │
│           semantic template (path/query slot)     │
│   _TOOL_GROUPS tool schema, max_tokens=65536      │
└──────────────────────────────────────────────────┘
    │ (StatePatternGroup, 49-105개 — run-to-run)
    ▼
┌──────────────────────────────────────────────────┐
│ Call 2 — derive_infotypes                        │
│   Input:  StatePatternGroup list + group_id      │
│   Output: InfoType 명명 + realize edges          │
│           (InfoType → StatePatternGroup)          │
│   _TOOL_INFOTYPES tool schema, max_tokens=32768   │
└──────────────────────────────────────────────────┘
    │ (InfoType ~37개)
    ▼
┌──────────────────────────────────────────────────┐
│ Call 3 — derive_action_renames                   │
│   Input:  LeadsToEdge 후보 목록                  │
│   Output: action 이름 표준화                     │
│   _TOOL_ACTIONS tool schema, max_tokens=16384     │
└──────────────────────────────────────────────────┘
    │
    ▼
DerivationResult → derivation_to_kg → inferred-trust SiteKG
    │
    ▼
post_enrich.py (LLM 재호출 0)
    │ D1: binding_map (bindings ↔ slot/query name exact match + [] variant)
    │ D2: path_params (*_path → path_segments, else segment)
    │ D3: query_params (optional_bindings → query param backfill)
    │ D6: InfoType category (prefix-based taxonomy clustering)
    ▼
Frozen SiteKG (immutable)
```

### Reasoning model settings

- Model: `gpt-5.4` (Reasoning model, `responses` API)
- `reasoning_effort="low"` — 3-call 분할 후 각 call의 tokens-in-context가 충분히 작아
  low effort로도 안정적 (ARI mean = 0.9264, N=3 runs)
- 각 call의 tool schema는 strict JSON schema validation으로 응답 구조 보장
- Retry 없음 — tool_call 실패 시 즉시 hard failure (derivation 재시작)

### 왜 3-call인가 (decomposition 설계 근거)

1. **Context overflow 방지**: single-call로 3040개 literal StatePattern + groupig +
   InfoType + action renames을 모두 출력시키면 reasoning context가 폭발해 quality degrade
   + timeout 빈도 증가. 각 call을 한 task에 집중시켜 context 효율 확보.
2. **Tool schema granularity**: 3 subtask는 출력 구조가 근본적으로 다름 (group_id map,
   realize edges, action renames). Single tool로 묶으면 schema complexity가 높아져
   validation 실패 빈번.
3. **Error recovery**: 특정 call만 실패 시 부분 재시도 가능 (현 코드는 전체 재시작이나,
   확장 여지 설계).

### Reproducibility

3회 독립 derivation run (seed 변경 없음 — LLM 자체 비결정성만):
- ARI (group-level, 3-run Adjusted Rand Index mean) = **0.9264**
- Group 수 variance: 49~105 (cluster 세분화 차이는 있되 member 일관성 강함)
- 최종 InfoType count (post_enrich 후): 37

Pipeline CLI:
```bash
.venv/bin/python -m site_adaptive_webagent.kg.seed.run_derivation \
    --crawl-dir output/crawl/<timestamp> \
    --output output/derivation/<timestamp>
```

---

## 6. 구현 순서

1. **kg/types.py, kg/store.py**: 데이터 구조 + CRUD. `source` 필드(crawl/llm/manual)는 모든 노드·엣지의 1급 시민. SiteKG에 `build_timestamp`, `source_mix`, `builder_version` 메타데이터.
2. **kg/urlnorm.py**: 정규화 함수. 단위 테스트로 먼저 검증.
3. **kg/seed/manual_config.py, kg/seed/infotype_catalog.py, kg/seed/seed_loader.py**: 수동 config·infotypes 로더. source 필드 보존.
4. **kg/seed/playwright_crawler.py [핵심 단계 1]**: 관찰 기반 자동 수집 → `source=crawl`/`trust=verified`. 구축 파이프라인의 first-class 단계. 수동 config로 대체 불가.
5. **kg/seed/llm_derivation.py [핵심 단계 2]**: crawl 결과를 LLM에 주고 InfoType·realizes 일반화 → `source=llm`/`trust=inferred`.
6. **kg/query.py**: 4 primitive. trust-aware edge selection (verified > declared > inferred).
7. **kg/rewrite.py, kg/validator.py**: 상위 로직. `url_template_trust=inferred`면 rewrite 보류.
8. **kg/trust.py**: 업데이트 정책.
9. **agent/kg_integration.py**: baseline과의 bridge. variant flag 포함.

### 마일스톤

- **M1 — URL normalization 완성**: kg/urlnorm.py + 단위 테스트 통과.
- **M2 — 수동 seed 기반 rewrite 동작**: types + store + query + rewrite + 수동 seed. smoke task 동작 확인.
- **M3 — Full hook 통합**: Hook A~D 전부 통합. smoke 회귀 확인.
- **M4 — KG 구축 (3단계 hybrid, baseline 측정 전에 완료)**:
  1. Playwright crawler로 GitLab 주요 기능 표면을 crawl → verified StatePattern·leads_to.
  2. LLM derivation으로 InfoType 후보·realizes·description 도출 → inferred.
  3. 수동 검증으로 승격·보정·제거 → declared. 포괄 catalog (~20~30 InfoType, ~30~50 StatePattern) 달성.
  4. `SiteKG.source_mix`·`build_timestamp` 기록, catalog freeze (baseline 측정 전).
- **M5 — 본 실험 (50 task × N=3 × 2 variants)**: Baseline vs Full KG 공식 측정 = 300 runs. KG-addressable 커버리지 보고 (`06 §3`).
- **M6 (future work) — Fine-grained ablation variants**: compute-matched / URL-emission-only / KG-retrieval 추가 구현·측정.
- **M7 (future work) — Continual replay · scaling**: trust evolution 반복 측정, mini/full 모델 비교.

---

## 7. 위험과 대응

### R1: KG 구현이 쟁점 #3 스키마 미확정으로 블로킹
- **대응**: Phase 2 끝날 때까지 kg/types.py 구체 필드는 손대지 않음. 이 문서의 모듈 경계·hook 구조는 스키마가 바뀌어도 유효.

### R2: Baseline 코드를 수정해야 하는데 기존 구조가 경직
- **대응**: agent/kg_integration.py를 얇게 두고, baseline 코드에는 **4개의 조건 호출**만 추가. 주입된 kg가 None이면 아무 일도 안 함.
- 기존 `executor.py`의 sub-goal 루프에 HOOK C 추가가 가장 침투적인 부분. 이 수정은 1~2 줄 이내로 제한.

### R3: Trust 업데이트가 Continual 셋업에서 noise만 증폭
- **대응**: 초기 구현은 trust 승격·강등을 보수적으로(e.g., 3회 연속 성공 시만 승격). 실험에서 continual 효과 없으면 주장 7 retreat.

### R4: LLM의 `plan_to_info` tool use 호출이 불안정
- **대응**: full 모델 사용으로 완화. mini에서도 fallback(no-tool-call)이 동작해 baseline으로 떨어짐. 치명적 실패 아님.

### R5: crawl이 GitLab Docker 환경의 동적 URL을 다 포착하지 못함
- **대응**: 3단계 hybrid(crawl + LLM derivation + 수동 검증)는 어느 한 단계도 생략하지 않는다. crawl이 못 잡는 경로는 수동 검증 단계에서 `source=manual`로 보강하고, 관찰만으로 분류 불가한 추상 카테고리는 LLM derivation이 채운다. 단일 source로 퇴행하면 catalog 품질이 정책(trust-aware rewrite)에 반영되지 않으므로 3단계 모두 필수.

---

## 8. Phase 2 결과가 이 문서에 줄 수 있는 영향

Phase 2 결과에 따라 이 문서에서 **변경될 수 있는 부분**:

- Failure taxonomy 분포가 pilot과 크게 다름 → ablation 우선순위(쟁점 #4) 재조정 → §5 매핑 업데이트
- MUTATE task 실패 패턴이 Level 2 observable predicate를 요구함 → kg/types.py 스키마에 Level 2 슬롯 포함 필요
- URL normalization 의존도가 낮은 실패가 다수 → urlnorm 우선순위 낮춤

**변경되지 않을 부분**:
- §1 디렉토리 레이아웃
- §2 4 hook 통합 지점
- §3 KG 초기화·continual 흐름
- §5 ablation 구현 매핑의 구조 (내용은 조정 가능)
- §6 구현 순서 1~3
