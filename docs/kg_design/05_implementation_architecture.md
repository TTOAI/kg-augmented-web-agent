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
│       ├── playwright_crawler.py   # [단계 1] 관찰 기반 자동 수집 → verified
│       └── llm_derivation.py       # [단계 2] InfoType·realizes 일반화 → inferred
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
| **Full KG** (본 연구) | ✓ | ✓ (adaptive) | ✓ | ✓ (로깅 전용, trust 변동 없음) |

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
