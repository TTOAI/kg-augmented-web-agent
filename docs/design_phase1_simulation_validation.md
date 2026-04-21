# Phase 1 설계안 (v3) — KG-based Multi-hop Simulation Feasibility Validation

**작성일**: 2026-04-19 (v3 = Tier S 4 + Tier A 6 추가 반영)
**범위**: Phase 1 simulation feasibility 검증. Phase 2 (Browser Agent / class-based KG 재구축)는 future work
**기존 자산**: Frozen KG `2026-04-16T16-46-55Z.json` 재사용
**Target**: 3-page 한국 학회
**Model**: GPT-5.4-mini (snapshot ID 고정, `.env` OPENAI_MODEL 명시)
**예상 비용**: ~$130-170
**기간**: 3주 (15일)

---

## 0. v2 → v3 변경 요약

### Tier S (4개)
| # | v2 | v3 |
|---|---|---|
| S1 | 2 variants (baseline / kg_enriched) | **3 variants** (baseline / kg_compute_matched / kg_enriched) — compute-matched control 복원 |
| S2 | Audit = BFS reachability만 | **End-to-end audit** — 5 task mini live execution으로 실제 goto/hint 작동률 측정 |
| S3 | 연속 측정 | **Chunked + checkpoint + resume** infrastructure |
| S4 | Strict verify_done 양 variant 적용만 | **Strict rule 사전 smoke** — original vs strict baseline 3-way compare |

### Tier A (6개)
| # | v3 반영 |
|---|---|
| A1 | KG-aware build_plan을 양 variant 적용 — **pure baseline(InfoType 정보 미제공)은 부록에 별도 측정** |
| A2 | Goto는 **sub-goal 시작 시에만** trigger (중간 action 후 goto 금지) |
| A3 | Strict rule에 **"URL changed after action"** 조건 추가 (filter 등 URL 변화 없는 navigation 오발동 방지) |
| A4 | **Hint format A/B** 사전 smoke로 optimal format 결정 |
| A5 | Hint에 **uncertainty language** 명시 ("suggestion may be outdated") |
| A6 | **Observation tier bindings** 명시적 구현 (DOM h1 tag + URL segment common tokens) |

### Tier B (정리)
- 50 tasks 선정 정당성 논문 §에 명시
- Component fire rate 실시간 monitoring
- Model snapshot ID 고정
- Sequential variant execution
- KG shared module cache

---

## 1. 가설 + Contribution

### 가설 (정식)

> **H**: WebArena-Verified GitLab에서 LLM 웹 에이전트에 Frozen KG 기반 multi-hop simulation의 결과를 navigation context로 제공하면, compute-matched baseline 대비 task success rate가 개선된다. 결과(positive/null 어느 쪽이든) empirical analysis로 KG의 현실적 활용 가능성과 한계를 정량화한다.

### Contribution 4 시나리오

1. **Positive**: simulation의 empirical 이득 (compute 통제 후) + class-based KG (Solution 1) 확장 근거
2. **Partial**: task-type별 heterogeneous effect 분석
3. **Null**: coverage + end-to-end feasibility 데이터로 "current KG granularity 한계" empirical 증명 → Solution 1 필요성
4. **Negative**: failure mode taxonomy (hint pitfall, goto redirect 등)

---

## 2. 아키텍처 (8 components)

### 2.1 Class Identity Resolver (deterministic)

```python
def identify_current_page(url: str) -> StatePattern | None:
    matches = [sp for sp in kg.state_patterns.values()
               if match_pattern(normalize_url(url, site_config), sp)]
    if not matches:
        return None
    return max(matches, key=lambda sp: (
        sp.path_pattern.count("/"),
        len(sp.path_params),
        -sp.path_pattern.count("{"),
    ))
```

### 2.2 Bindings Extraction (3-tier + 구현 명세)

```python
def extract_bindings(target_sp, current_url, task_text, observation) -> dict:
    bindings = {}
    
    # Tier 1: current URL
    current_sp = identify_current_page(current_url)
    if current_sp:
        cur_bindings = match_pattern_extract(current_url, current_sp)
        for param in target_sp.path_params:
            if param in cur_bindings:
                bindings[param] = cur_bindings[param]
    
    # Tier 2: task text regex (명시적 rule set)
    # namespace/project 패턴, ID 패턴, 인용 문자열
    quoted = re.findall(r'["\']([^"\']+)["\']', task_text)
    user_proj = re.findall(r'([a-zA-Z][\w-]+)/([a-zA-Z][\w-]+)', task_text)
    ids = re.findall(r'#(\d+)', task_text) + re.findall(r'issue\s+(\d+)', task_text, re.I)
    
    PARAM_HINTS = {
        ("namespace", "username", "user"): lambda: user_proj[0][0] if user_proj else None,
        ("project", "project_path", "repo"): lambda: user_proj[0][1] if user_proj else None,
        ("id", "issue_id", "mr_id"): lambda: ids[0] if ids else None,
    }
    for param in target_sp.path_params:
        if param in bindings:
            continue
        for name_group, extractor in PARAM_HINTS.items():
            if param in name_group:
                val = extractor()
                if val:
                    bindings[param] = val
                    break
    
    # Tier 3: observation (Tier A6 — 명시적 구현)
    # DOM h1/h2 tags + URL path segments 공통 토큰
    for param in target_sp.path_params:
        if param in bindings:
            continue
        headers = extract_axtree_headings(observation)  # main region h1/h2/h3
        url_segments = current_url.split("/")
        candidates = set()
        for h in headers:
            tokens = h.split()
            for tok in tokens:
                if tok.lower() in [s.lower() for s in url_segments]:
                    candidates.add(tok)
        # param name과 유사한 candidate 선택 (간단 heuristic)
        for cand in candidates:
            if param.lower() in cand.lower() or cand.lower() in param.lower():
                bindings[param] = cand
                break
    
    return bindings
```

### 2.3 KG-aware build_plan (Tier A1 — 부록 별도 측정 포함)

**주 실험 변형**: KG-aware build_plan을 **3 variants 모두 사용** (confound 제거).

**부록 별도 측정 (Day 11 sanity)**:
- 6 task × "pure baseline (InfoType 정보 없음)" × N=1
- KG-aware vs pure baseline 차이 정량화
- 결과: 차이 유의미하면 논문 Limitation에 명시

**Prompt** (양 variant 공통):
```
Site structure context:
Available page types in GitLab:
- issue_list: list of issues in a project
- merge_request_list: list of merge requests
... (37개)

Decompose the task into 2-5 sub-goals. For each sub-goal, specify:
- goal: description
- type: "navigation" | "action"
- infotype: target page type (null if not applicable, e.g., filter/submit)

Prefer page-level decomposition when meaningful. Do NOT force-fit 
sub-goals to infotypes that don't match.

Response JSON:
{"sub_goals": [{"goal": "...", "type": "navigation|action", "infotype": "..." | null}]}
```

### 2.4 Candidate Target Generator (Method C)

**Keyword 1차**:
```python
STOP_WORDS = {"a", "an", "the", "of", "for", "to", "in", "on", ...}

def match_by_keyword(sub_goal_text: str) -> list[InfoType]:
    text = sub_goal_text.lower()
    matches = set()
    for it in kg.infotypes.values():
        # Name 토큰 전체 포함 check
        name_tokens = [t.lower() for t in it.name.replace("_", " ").split()
                      if t.lower() not in STOP_WORDS]
        if name_tokens and all(tok in text for tok in name_tokens):
            matches.add(it.name)
        # Intent examples overlap
        for ex in it.intent_examples[:3]:
            ex_tokens = {t.lower() for t in ex.split() if t.lower() not in STOP_WORDS}
            text_tokens = {t.lower() for t in text.split()}
            if len(ex_tokens & text_tokens) >= 3:
                matches.add(it.name)
                break
    return [kg.infotypes[n] for n in matches]
```

**LLM fallback** (kw 실패 시):
- candidate LLM call
- 결과: top 3-5 infotype

### 2.5 Simulation Engine (BFS + task-type filter + trust filter)

```python
READONLY_PREFIXES = ("crawl:link:",)
POTENTIALLY_DESTRUCTIVE_PREFIXES = ("crawl:form:",)
TRUST_ORDER = {"verified": 0, "declared": 1, "inferred": 2}

def bfs_simulate(current_sp, target_sps, max_hops, task_type):
    frontier = [(current_sp.id, [], 0)]  # (sp_id, path, trust_penalty)
    visited = {current_sp.id}
    found_paths = []
    
    for depth in range(max_hops):
        if not frontier:
            break
        next_frontier = []
        for (sp_id, path, penalty) in frontier:
            out_edges = [e for e in kg.leads_to_edges if e.from_state_pattern_id == sp_id]
            
            # Tier S2: task-type filter
            if task_type in ("NAVIGATE", "RETRIEVE"):
                out_edges = [e for e in out_edges
                            if e.action_name.startswith(READONLY_PREFIXES)]
            
            for edge in out_edges:
                next_id = edge.to_state_pattern_id
                new_penalty = penalty + TRUST_ORDER.get(edge.trust, 2)
                # inferred-only path는 deep BFS 제한
                if new_penalty > max_hops:
                    continue
                new_path = path + [edge]
                if next_id in target_sps:
                    found_paths.append((new_path, new_penalty))
                if next_id not in visited:
                    visited.add(next_id)
                    next_frontier.append((next_id, new_path, new_penalty))
        frontier = next_frontier
    
    # Sort: shortest path + trust penalty
    found_paths.sort(key=lambda x: (len(x[0]), x[1]))
    return [p for p, _ in found_paths]
```

### 2.6 Navigation Executor (goto + hint, Tier A2, A5)

**Goto는 sub-goal 시작에만** (Tier A2). 중간 action 후 goto 금지.

```python
def execute_simulation_output(best_path, current_bindings, task_text, obs,
                              target_sp, sub_goal_context):
    # Tier A2: sub-goal이 방금 시작되었는지 check
    if sub_goal_context.steps_taken > 0:
        # 이미 이 sub-goal 내에서 action 했으면 goto 대신 hint
        return HintFallback(hint=format_path_as_hint(best_path))
    
    # Bindings extraction
    bindings = extract_bindings(target_sp, page.url, task_text, obs)
    
    if not all(p in bindings for p in target_sp.path_params):
        return HintFallback(hint=format_path_as_hint(best_path))
    
    target_url = target_sp.emit_url(bindings)
    
    try:
        await page.goto(target_url)
        new_sp = identify_current_page(page.url)
        if new_sp and new_sp.id == target_sp.id:
            return GotoSuccess(url=target_url)
        if new_sp is None and page.url.startswith(target_url.split("?")[0]):
            return GotoSuccess(url=target_url, partial_match=True)
        logger.warn("[KG] goto landed on different page")
        return HintFallback(hint=format_path_as_hint(best_path))
    except Exception as e:
        logger.warn(f"[KG] goto failed: {e}")
        return HintFallback(hint=format_path_as_hint(best_path))


def format_path_as_hint(path) -> str:
    """Tier A5: uncertainty language 포함"""
    hint_lines = [
        "[KG Navigation Hint (suggestion, may be outdated or incorrect — "
        "verify with current observation)]",
        f"Based on site structure graph, a {len(path)}-hop path to target:",
    ]
    for i, edge in enumerate(path):
        hint_lines.append(
            f"  Step {i+1}: from {edge.from_state_pattern_id}, "
            f"click widget matching action '{edge.action_name}' "
            f"→ leads to {edge.to_state_pattern_id}"
        )
    hint_lines.append("If the suggested widget is not visible, proceed with your own judgment.")
    return "\n".join(hint_lines)
```

### 2.7 Strict verify_done (Tier A3 — URL changed 조건)

```python
def verify_done_strict(sub_goal, current_url, pre_action_url, 
                       expected_target_sp=None):
    if sub_goal.type != "navigation":
        return original_verify_done()
    
    # Tier A3: URL이 바뀌지 않았으면 strict rule 면제 (filter action 등)
    if current_url == pre_action_url:
        return original_verify_done()
    
    # URL 바뀐 경우: StatePattern match 확인
    current_sp = identify_current_page(current_url)
    if not current_sp:
        return False  # navigation 후 unknown URL이면 done 불가
    
    if expected_target_sp and current_sp.id != expected_target_sp.id:
        return original_verify_done()  # soft check
    
    return original_verify_done()
```

### 2.8 Component Fire Rate Monitor (Tier B)

```python
@dataclass
class KGEnrichmentMetrics:
    build_plan_calls: int = 0
    method_c_keyword_matches: int = 0
    method_c_llm_fallback_calls: int = 0
    simulation_attempts: int = 0
    simulation_found_path: int = 0
    navigation_goto_attempts: int = 0
    navigation_goto_success: int = 0
    navigation_hint_fallback: int = 0
    strict_verify_rejections: int = 0

# Persisted per task in agent_response.json meta
```

Day 9 저녁 (측정 중간) — fire rate 확인. Simulation 발견율 < 15%면 즉시 abort + 분석.

---

## 3. Task 수행 흐름 (v3)

```
[Task start]
  ↓
analyze_intent → task_type
  ↓
3 variants 모두: KG-aware build_plan (동일 prompt)
  → sub_goals with type + infotype
  ↓
Per sub_goal:
  ┌─────────────────────────────────────────────┐
  │ [sub_goal 시작 at step 0]                    │
  │                                              │
  │ baseline: Method C·Simulation·Navigator skip │
  │ kg_compute_matched: Method C + Simulation 수행 │
  │   but 결과 **discard** (hint 주입 안 함)     │
  │   → LLM call 동일, content 효과 없음         │
  │ kg_enriched: Method C + Simulation + Nav full │
  │   → goto or hint                              │
  │                                              │
  │ Agent baseline loop (observation → action)   │
  │                                              │
  │ Per action:                                   │
  │   execute → observe new URL                   │
  │   if sub_goal.type=navigation:                │
  │     strict verify_done (URL changed 조건 포함) │
  │   else:                                       │
  │     original verify_done                      │
  └─────────────────────────────────────────────┘
  ↓
Next sub_goal
```

---

## 4. 측정 설계

### 4.1 Variants (3, Tier S1 복원)

| Variant | KG-aware build_plan | Method C + Simulation | Hint/Goto 주입 | Strict verify_done |
|---|---|---|---|---|
| **baseline** | ✓ | ✗ | ✗ | ✓ |
| **kg_compute_matched** | ✓ | ✓ | ✗ (결과 폐기) | ✓ |
| **kg_enriched** | ✓ | ✓ | ✓ | ✓ |

**분리 측정 가능한 이득**:
- `baseline vs kg_compute_matched`: Method C LLM call의 compute 효과 (should be ≈0)
- `kg_compute_matched vs kg_enriched`: **KG content의 순수 효과** ← Primary

### 4.2 Pre-experiment Coverage Audit (Tier S2 — end-to-end)

**Day 1-2 실행**:

**Part A (dry-run, LLM 최소)**:
- 50 task × build_plan 1회 LLM
- 각 sub_goal → Method C (keyword + LLM fallback)
- BFS reachability 측정
- Keyword match rate / LLM fallback rate / reachability rate / average path length

**Part B (mini end-to-end live, Tier S2 핵심)**:
- **5 task × kg_enriched 1 run each** (실제 browser 실행)
- Pre-audit mini measurement:
  - Bindings completeness rate
  - Goto attempt / success rate
  - Hint fallback rate
  - Goto 후 target sp match rate
  - Agent's first-action-after-hint match (compliance proxy)

**비용**: Part A ~$5, Part B ~$10. 총 ~$15.

**Go/No-Go Gate 1 (Day 2)**:
| Metric | Gate |
|---|---|
| Reachability (Part A) | ≥40% |
| Bindings completeness (Part B) | ≥50% |
| Goto success (Part B) | ≥40% |
| End-to-end feasibility rate (ALL conditions) | **≥15%** |

- 모든 gate pass → Go
- 일부 fail → 설계 조정 1-2일 (max_hops 조정 / bindings regex 보강 / prompt tuning)
- End-to-end < 10% → No-Go 또는 narrative 피벗 (Solution 1 필요성 증명으로)

### 4.3 Strict verify_done Pre-smoke (Tier S4)

**Day 7 실행 (정식 smoke 전)**:
- 6 task × 3 configs × N=1 = 18 runs
- Configs:
  - **Original baseline** (strict 없음)
  - **Strict baseline** (strict rule 적용한 baseline)
  - **kg_enriched** (strict + KG)

**목적**: Strict rule이 baseline에 미치는 영향 isolate.
- Strict baseline이 original과 유사 (±1 task) → OK, 본 측정 진행
- Strict baseline이 original 대비 regression ≥2 → **strict rule 범위 조정** (너무 엄격)

### 4.4 Hint Format A/B (Tier A4)

**Day 6 smoke**:
- 6 task × hint format {A, B} × N=1 = 12 runs
- Format A: verbose "Step 1 from ... click widget matching ... → leads to ..."
- Format B: concise "To reach issue_list, click the 'Issues' link."

**결과로 본 측정 format 결정**.

### 4.5 본 측정 Scale

**50 task × 3 variants × N=3 = 450 runs**

Task selection:
- `scripts/sample_tasks_per_type.py --seed 42 --per-type 17`
- NAV 17 + RET 17 + MUT 16 = 50
- Broken eval 사전 제외 (pre-audit에서 확인)

### 4.6 Chunked Measurement + Checkpoint (Tier S3)

**`run_phase1_measurement.sh` 구조**:
```bash
CHUNKS=(
    "baseline N1"
    "baseline N2"
    "baseline N3"
    "kg_compute_matched N1"
    "kg_compute_matched N2"
    "kg_compute_matched N3"
    "kg_enriched N1"
    "kg_enriched N2"
    "kg_enriched N3"
)
# 9 chunks × 50 task = 50 tasks per chunk × 9 chunks

for chunk in "${CHUNKS[@]}"; do
    variant=$(echo $chunk | awk '{print $1}')
    N=$(echo $chunk | awk '{print $2}')
    
    # Resume check
    completed=$(count_completed_tasks output/phase1_measurement/$variant/$N/)
    start_idx=$completed  # 다음 task부터
    
    # Pre-chunk env reset
    webarena-verified env stop --site gitlab
    webarena-verified env start --site gitlab
    sleep 3
    
    # Pre-chunk quota check
    python3 scripts/check_api_quota.py || exit 1
    
    for ((i=start_idx; i<50; i++)); do
        task=${TASKS[$i]}
        run_single_task "$variant" "$N" "$task"
        # Per-task checkpoint (agent_response.json 저장)
        
        # MUTATE 후 env reset
        if [[ "$(task_type $task)" == "MUTATE" ]]; then
            webarena-verified env stop --site gitlab
            webarena-verified env start --site gitlab
        fi
    done
    
    # Post-chunk fire rate check (kg_enriched만)
    if [[ "$variant" == "kg_enriched" ]]; then
        python3 scripts/check_fire_rate.py --variant $variant --n $N
    fi
done
```

**특성**:
- Chunk = variant × N 조합 (9개)
- Resume: 기존 완료 task는 skip
- Per-chunk quota check
- Per-chunk env reset
- Per-task checkpoint
- MUTATE 후 env reset
- kg_enriched chunks 완료 후 fire rate 확인

### 4.7 Metrics

**Primary**:
- NET success rate
- **Paired McNemar**: `kg_compute_matched vs kg_enriched` (KG content 순수 효과)
- **Sanity McNemar**: `baseline vs kg_compute_matched` (compute 효과, should be ≈0)

**Secondary**:
| Metric | 계산 |
|---|---|
| Reachability rate | sub-goal 중 path found % |
| Bindings complete rate | goto 시도 전 all path_params 채워진 % |
| Goto attempts / success rate | |
| Hint fallback rate | |
| Agent compliance rate | hint의 first widget description가 agent first action과 매치 % |
| Strict verify_done rejection rate | navigation sub-goal 중 strict rule fail % |
| Step count delta | variant 간 |
| LLM call delta | variant 간 |
| Component fire rate | kg_enriched 전용 |

**Broken eval**:
- `docs/kg_design/eval_exclusions.md` 기반
- Pre-audit에서 identified, 사전 exclusion
- 분석 시 Raw + Adjusted 두 버전 보고

**Compute-matched 검증**:
- `baseline vs kg_compute_matched` LLM call count delta 비교
- ≈0 이어야 compute-matched 주장 성립
- 아니면 논문에 차이 명시

### 4.8 Model 설정

```
.env 파일:
OPENAI_MODEL=gpt-5.4-mini-YYYYMMDD  # snapshot ID 고정
LLM_TEMPERATURE=0
```

논문 §4.1 Setup에 snapshot date 명시.

---

## 5. Risk Mitigation 매트릭스 (v3 통합)

| Tier | Issue | Mitigation |
|---|---|---|
| S1 | Compute confound | 3-variant (compute_matched control) |
| S2 | Audit ≠ e2e success | Part B end-to-end mini live execution |
| S3 | 10h 측정 불안정 | Chunked + checkpoint + resume + quota check |
| S4 | Strict rule baseline 영향 미검증 | Day 7 pre-smoke 3-way compare |
| A1 | KG-aware plan confound | 부록에 pure baseline 6-task 별도 측정 |
| A2 | Middle-sub-goal goto state loss | Sub-goal 시작 시에만 goto |
| A3 | Strict rule filter action 오발동 | "URL changed" 조건 추가 |
| A4 | Hint format sensitivity | Day 6 format A/B smoke |
| A5 | Hint implicit command | Uncertainty language 명시 |
| A6 | Observation tier bindings 미구현 | DOM heading + URL segment common token 구현 |
| B | 50 task 정당성 | seed=42 + balanced + cost 명시 |
| B | Fire rate 미관측 | Day 9 저녁 중간 check + abort threshold |
| B | Model drift | snapshot ID 고정 |
| B | Parallelism risk | Sequential only (per chunk) |

---

## 6. Implementation Plan (3주, 15일)

### Week 1 — Audit + Core Components

| Day | 작업 | 산출물 |
|---|---|---|
| 1 | Pre-audit Part A 구현 + 실행 (dry-run 50 task) | `scripts/coverage_audit_dryrun.py`, Part A report |
| 2 | Pre-audit Part B 구현 + 실행 (5 task live) + Gate 1 결정 | `scripts/coverage_audit_live.py`, Part B report, decision log |
| 3 | Class Identity Resolver + Bindings Extraction (3-tier 구현 명세) + unit test | `runtime/kg_resolve.py`, `runtime/kg_bindings.py` |
| 4 | Simulation Engine (BFS + task-type filter + trust filter) + unit test | `runtime/kg_simulate.py` |
| 5 | Method C (keyword + LLM fallback) + Component Fire Rate Monitor | `runtime/kg_plan.py`, `runtime/kg_metrics.py` |

### Week 2 — Integration + Smokes

| Day | 작업 | 산출물 |
|---|---|---|
| 6 | KG-aware build_plan + Navigation Executor + Strict verify_done (URL-changed 조건) + executor 통합 | modified `agent/core.py`, `runtime/llm.py`, `runtime/executor.py` |
| 7 | **Strict verify_done Pre-smoke** (Tier S4): 6 task × 3 configs × N=1 + decision | smoke report |
| 8 | **Hint format A/B smoke** (Tier A4): 6 task × 2 formats × N=1 + format 결정 | smoke report |
| 9 | Integration smoke: 6 task × 3 variants × N=1 + Gate 2 | smoke report |
| 10 | Smoke 결과 기반 수정 + 본 측정 script 준비 (chunked + resume) | `run_phase1_measurement.sh` |

### Week 3 — 본 측정 + 분석 + 논문

| Day | 작업 | 산출물 |
|---|---|---|
| 11 | 본 측정 Chunk 1-3 (baseline N1/N2/N3) = 150 runs | 중간 outputs |
| 12 | 본 측정 Chunk 4-6 (kg_compute_matched N1/N2/N3) = 150 runs + 중간 fire rate check | 중간 outputs |
| 13 | 본 측정 Chunk 7-9 (kg_enriched N1/N2/N3) = 150 runs + fire rate final | `output/phase1_measurement/` 완성 + Pure baseline 부록 smoke |
| 14 | 분석 (primary McNemar + sanity + secondary + failure mode) + broken eval adjusted | `docs/phase1_measurement_report.md` |
| 15 | 논문 draft 작성 (3-page) + figure preparation | `docs/paper_draft.md` |

---

## 7. Deliverables

### Code
- `runtime/kg_resolve.py` — Class Identity Resolver
- `runtime/kg_bindings.py` — 3-tier Bindings Extraction
- `runtime/kg_simulate.py` — BFS + filters
- `runtime/kg_plan.py` — Method C + Navigation Executor
- `runtime/kg_metrics.py` — Fire Rate Monitor
- Modified `agent/core.py`, `runtime/llm.py`, `runtime/executor.py`
- `scripts/coverage_audit_dryrun.py`
- `scripts/coverage_audit_live.py`
- `scripts/check_api_quota.py`
- `scripts/check_fire_rate.py`
- `scripts/analyze_phase1.py` (paired stats, compute-matched sanity, adjusted analysis)
- `run_phase1_audit.sh`
- `run_phase1_smoke.sh`
- `run_phase1_measurement.sh` (chunked + resume + env reset)
- Unit + integration tests

### Documents
- `docs/phase1_audit_report.md` (Part A + Part B + Gate 1 decision)
- `docs/phase1_smoke_report.md` (Day 7-9 smokes + Gate 2)
- `docs/phase1_measurement_report.md` (primary + secondary + broken eval adjusted)
- `docs/paper_draft.md` (3-page)

### Outputs
- `output/phase1_audit/part_a/`, `part_b/`
- `output/phase1_smoke/strict_check/`, `hint_format/`, `integration/`
- `output/phase1_measurement/` (9 chunks)

---

## 8. Future Work Roadmap (Solution 1, 3-step)

논문 §5에 명시:

**Step 1 — Dedicated Site-Mapping Browser Agent**:
- Cheap LLM (GPT-5.4-nano) 사용
- Task-agnostic exploration 10-hop from homepage
- DOM 요소의 class identity 추출:
  - AXTree role + heading + repeated sibling pattern
  - URL pattern + path_params
- 산출: class-based KG (현 3,040 StatePatterns → 수십 class)

**Step 2 — Class-based KG Schema**:
- Entity: class (page/widget type)
- Relation: `has_widget`, `leads_to`, `requires`
- Abstraction ratio: crawl KG 대비 1-2% 수준 목표

**Step 3 — Class Graph 위 Simulation**:
- 본 연구의 simulation 재적용
- 더 작은 search space → 더 높은 reachability 기대
- Cross-site transfer 실험 가능

---

## 9. 3-page 논문 구성

| 섹션 | 내용 |
|---|---|
| §1 Intro (12 lines) | Multi-hop navigation 병목 + KG simulation 가능성 |
| §2 Related (10 lines + Table) | SteP/WALT/CBA/AVENIR/LCoW 매트릭스 — simulation 공백 |
| §3 Method (25 lines + Figure 1) | Architecture 8 components 개요 + KG-aware plan + 3 variants rationale |
| §4 Experiment (25 lines + 2 Tables) | 50 task × 3 variants × N=3 / pre-audit coverage / main result |
| §5 Discussion + Future (15 lines) | Primary finding + limitations + Solution 1 roadmap |

**압축 원칙**: Bindings extraction 3-tier 등 구체 구현은 **GitHub repo reference**만. 논문에선 핵심 아이디어 + 실험 결과.

---

## 10. Expected Outcome 4 시나리오

### A. Positive (kg_compute_matched < kg_enriched, p<0.05)
> "Multi-hop KG simulation의 content 효과 (compute 통제 후) empirical 검증. +{Δ}%p 개선 at coverage {C}%."

### B. Partial (task-type별)
> "NAVIGATE task에서만 유의. RETRIEVE/MUTATE는 filter/form 단위 granularity로 KG 한계."

### C. Null (no significant difference)
> "현 URL-level Frozen KG의 end-to-end simulation 이득 검출 안 됨. Coverage {C}% + goto success {G}%가 한계 증명. Class abstraction (Solution 1)이 필요한 empirical 근거."

### D. Negative (kg_enriched < kg_compute_matched)
> "Hint misleading cases 관찰 → negative transfer. Failure mode taxonomy + mitigation guidelines."

---

## 11. Go/No-Go Gates

### Gate 1 (Day 2) — Post-audit
| Condition | Decision |
|---|---|
| Part A reachability ≥40% AND Part B e2e feasibility ≥15% | **Go** |
| Partial pass | Go + narrative pivot 준비 |
| e2e feasibility <10% | **No-Go** — 설계 조정 or Solution 1 논문으로 피벗 |

### Gate 2a (Day 7) — Strict verify_done pre-smoke
| Condition | Decision |
|---|---|
| Strict baseline ≈ original baseline (±1 task) | **Go** |
| Strict baseline regression ≥2 | **Strict rule 재조정** |

### Gate 2b (Day 9) — Integration smoke
| Condition | Decision |
|---|---|
| kg_enriched regression < 2/6 vs strict baseline | **Go** |
| Regression ≥ 2 | Navigation Executor stability 재검토 |

### Gate 3 (Day 14) — Component fire rate
| Condition | Decision |
|---|---|
| Simulation found path rate ≥ 20% in kg_enriched runs | 측정 유효 |
| < 15% | 분석에서 "coverage 한계" narrative 명시 |

### Gate 4 (Day 15) — 논문 narrative 확정
4 시나리오 중 1개 + initial draft.

---

## 12. 불확실성 (진행 중 결정)

1. LLM fallback 빈도 — Part A에서 측정
2. max_hops — Part A 분포 기반 ±2 조정 (default 5)
3. Trust penalty parameter — smoke에서 튜닝
4. Cross-project bindings 빈도 — Part A로 측정, 많으면 Tier 2 regex 강화
5. Hint format final — Day 8 smoke 결과

---

## 13. 승인 완료 항목 (v3 작성 확정)

- [x] Tier S 1-4 반영 (3 variants / e2e audit / chunked / strict pre-smoke)
- [x] Tier A 1-6 반영 (KG-aware separate test / sub-goal start only / URL-changed / format AB / uncertainty / obs tier)
- [x] Tier B 정리 (task 정당성 / fire rate / snapshot ID / sequential / cache)
- [x] Task scale 30 → 50
- [x] Variants 2 → 3 (compute-matched 복원)
- [x] Timeline 2.5주 → 3주
- [x] Cost $100-150 → $130-170
- [x] Model snapshot gpt-5.4-mini-YYYYMMDD 고정
- [x] 3-page 한국 학회 scope 유지
