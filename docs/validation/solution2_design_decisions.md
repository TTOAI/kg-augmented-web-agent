# Solution 2 — Design decisions (pre-implementation)

**Date**: 2026-04-21
**Status**: Pre-implementation, 설계 결정 사항 기록. 구현 세부는 별도 논의 예정.

## Context

Stage A-C 완료. 138 class, 141 rules, 2,813 edges 확보. Solution 2는 KG를 활용해 **agent가 task 수행 중 runtime에 navigation planning**하는 단계.

---

## 1. BFS path finder 기본 정책

### Option D cascade (unreachable target 처리)

Target class까지 경로가 없으면 hierarchical fallback:

1. **Exact**: target_class 정확히
2. **Family sibling**: 같은 widget family의 reachable 이웃 (e.g., `issue_detail` 못 가면 `issue_list`)
3. **Scope entry**: target의 scope entry point (e.g., `project/main`으로 일단 진입)
4. **Hub fallback**: 전역 hub (e.g., `dashboard/project_list/yours`)로 복귀
5. **Failed**: 어떤 것도 안 되면 실패 리턴 — agent가 직접 URL 입력 등 수동 조치

### 반환 메타데이터

```json
{
  "path": [...],
  "strategy": "exact|family_sibling|scope_entry|hub_fallback|failed",
  "actual_target": "실제 path의 끝 class (cascade fallback 시 원 target 아님)",
  "note": "자연어 설명"
}
```

---

## 2. KG resilience via runtime re-planning

Tree 대비 graph는 여러 in-path 있어 잘못된 위치에서도 재경로 가능. 활용법:

### Static path 맹신 금지

❌ 시작 시 full path 계산 → 맹목 실행  
✅ **매 step에서 현재 위치 classify → BFS 재계산**

```python
while not done and budget > 0:
    current = classify(current_url)
    if current == target: done = True; break
    paths = top_k_bfs(current, target, k=3)
    if not paths: fallback_cascade()
    for path in paths:
        if try_execute(path[0]): break  # edge 실행 시도
```

이탈해도 재-BFS로 복구. Drift robustness.

---

## 3. Trust level 해석 (정정)

**Trust는 edge existence 안정성 지표**이지 task 성공률과 무관.

- High trust = 해당 action/link이 class의 모든 instance에 존재 → runtime 실행 신뢰도 ↑
- Low trust = 일부 instance만 → runtime에 없을 수 있음

### 사용 방식

- **Path planning**: 모든 trust 범주 edge 활용 (배제 없음)
- **Tie-breaker**: 동일 hop 수 경로 중 high-trust 평균 높은 것 우선 — **이유는 execution reliability**
- **Low-trust threshold exclusion 금지**: 유일 경로면 low-trust도 써야

---

## 4. Path cost는 explicit edge만

Graph의 2,813 explicit edge 기반으로만 shortest path 계산.

- 명시적 edge (anchor href → class) → planning에 사용
- Implicit navigation (back button, URL bar, browser history) → KG 밖, agent가 필요 시 직접 사용 가능하지만 path 계산에 포함 안 함

---

## 5. Multiple paths (top-k)

### 전략 결정: **Dynamic re-planning + within-step top-k alternatives**

- Top-k는 **"같은 position에서의 대안 action"** 용도
- 전체 path retry 아님 (position 바뀌면 reset 비용 큼)
- Position 바뀌면 매 step BFS 재실행 (작은 graph, 즉시 계산)

### 실패 감지

1. **Mid-path mismatch**: next action 실행 후 classify(new_url) ≠ expected_next
2. **Dead end**: 계획한 action이 페이지에 없음 (low-trust edge에서 흔함)
3. **Budget exhaustion**: step 상한 도달
4. **Task evaluator 실패**: 최종 단계

---

## 6. Cascade 단계 수 + Progress check

### Full cascade 채택 (6단계)

```
1. exact            — target 직접
2. family_sibling   — target의 widget family 이웃
3. scope_entry      — target의 scope 진입점
4. hub_fallback     — 전역 hub
5. stay_and_explore — 현 위치가 target에 가장 가까움 (신규)
6. failed           — 모든 시도 실패
```

### Progress check — semantic reachability (구현 후 정정)

구현하면서 원안의 literal distance check가 **tautological**임을 발견:

- Exact BFS가 `current → target` 최단 경로를 이미 찾음. Exact가 실패했다는 건 두 클래스가 서로 다른 connected component에 있다는 뜻.
- Exact 실패 후 cascade가 실행될 때, `current`에서 reachable한 모든 후보 `cand`에 대해 `bfs_distance(cand, target) = ∞`. 동시에 `bfs_distance(current, target) = ∞`.
- 따라서 `d_cand < d_cur` (strict `∞ < ∞`)는 항상 false → literal check는 cascade를 모두 skip시키고 바로 stay_and_explore로 감. 의도와 맞지 않음.

**재정의**: progress는 *의미적 근접성(semantic proximity)*으로 해석. Cascade 단계 자체가 target과의 개념적 거리 순서를 내포:

1. `family_sibling` (target의 family 형제) — 가장 가까움
2. `scope_entry` (같은 scope의 대표 페이지) — 다음
3. `hub_fallback` (전역 hub) — 가장 먼 가중치

각 단계에서 candidate가 **현재 위치에서 reachable** (`bfs_distance(current, cand) < ∞`) AND **current와 다른 class**이면 accept. 단계 순서가 "더 멀어지지 않음"을 보장.

```python
# 각 cascade stage:
if candidate in all_classes and candidate != current:
    path = bfs(current, candidate)
    if path is not None:
        return path  # reachable + semantically nearest at this stage
# 모두 실패 → stay_and_explore
```

이유:
- Graph BFS 최단성으로 인해 "cascade가 target 방향으로 멀어지는" 시나리오는 제거 (cascade는 current의 component 내에서만 이동).
- Semantic ordering이 "어느 방향이 더 멀다"의 proxy 역할.
- Reviewer 방어: literal bfs_distance로는 무의미한 check임을 수식으로 설명 가능.

구현: `site_adaptive_webagent/kg_solution/path_finder.py`의 `find_path()`.

### 반환 예시 (stay_and_explore)

```json
{
  "strategy": "stay_and_explore",
  "confidence": "low",
  "path": null,
  "actual_target": "<current>",
  "note": "Current location is already closest reachable class to target. Explore locally via in-page links/buttons using LLM reasoning."
}
```

---

## 7. Action label 선택 정책 (multi-label edge)

### Hybrid approach

Edge가 여러 instance에서 variant label을 갖는 경우 (e.g., "Issues 1" vs "Issues 5" vs "Issues"):

**Step A — Normalize**:
```python
def normalize_action_label(label):
    s = label.strip()
    s = re.sub(r'\s+\d+$', '', s)         # trailing count 제거
    s = re.sub(r'\s+@\w+', '', s)          # username 제거
    s = re.sub(r'#\d+', '', s)             # issue # 제거
    return s.strip()
```

**Step B — Canonical select**: normalize 후 최빈 label
**Step C — Fallback**: canonical 없으면 highest-trust raw label
**Step D — Variance hint**: agent에 "click anything resembling 'Issues' (examples: 'Issues 1', 'Issues 5')" 안내

### 이유
- Variance label 자체는 instance-specific content (low-trust 원인)
- Normalize로 안정적 canonical 추출 → hint 품질 상승
- Examples도 함께 제공해 agent가 runtime matching할 때 참고

---

## 8. Natural language instruction 생성 — Hybrid

### Simple strategy (exact, stay_and_explore) → Rule-based template

```python
if strategy == "exact":
    return "Follow: " + " → ".join(f"[{s.action_label}] {s.class}" for s in path)
if strategy == "stay_and_explore":
    return f"Current location {current} is closest. Use LLM + page links."
```

**속도**: <1ms, **품질**: 일관

### Complex strategy (family_sibling, scope_entry, hub_fallback) → LLM 생성

```python
prompt = f"""
Task: {user_task}
Current: {current_class}
Intended target: {target_class}
Reached via {strategy}: {actual_target}
Path: {path}
Generate a concise instruction explaining how to reach target from actual_target.
"""
hint_text = llm_complete(prompt)
```

**속도**: +100-500ms, **품질**: 자연어·맥락 반영

### Cache
(path_pattern, strategy) 쌍 LLM 결과 cache → 동일 패턴 재방문 시 재사용.

---

## 9. Agent strategy 분기 — Hybrid

### exact + high confidence → Deterministic execution

```python
if hint.strategy == "exact" and hint.confidence == "high":
    for step in hint.path:
        execute_action(step.action_label)
        if classify(current_url) != step.class:  # drift
            break  # re-plan
```

빠름, 예측 가능.

### Fallback strategies → LLM-guided

```python
else:
    prompt = f"""
    KG hint: {hint.natural_language_instruction}
    Strategy: {hint.strategy}, confidence: {hint.confidence}
    Manual followup needed: {hint.manual_followup_hint}
    Decide next concrete action.
    """
    action = llm_agent(prompt)
    execute(action)
```

유연성, 복잡 case 대응.

### 이득
- Agent 코드 복잡도 낮음 (exact branch 하나 + 나머지는 LLM delegation)
- Exact path는 빠르고 deterministic
- Fallback은 LLM이 맥락·판단 제공

---

## 10. 결정 완료 항목 (이전에 미결이었던 것)

- **Top-k k 값**: **k=1**. 대안 경로는 매 step re-BFS로 자연 확보.
- **Step budget**: 기존 `max_steps` (executor.py 내 sub-goal 분배 로직) 재사용. KG 전용 budget 제거 (무의미).
- **Task → target class 추론**: Sub-goal 단위, LLM only, closed-set 138 class 강제. Auto-generated 1-line description per class (기존 annotations 활용). Bindings 추출하여 hint에 포함. Confidence는 **B+D hybrid** (K=3 self-consistency 불일치 시 no-hint, 제공 시 advisory binary).
- **Agent integration**: **Prompt injection**. `build_observation_message()` 호출 지점에 hint 섹션 append. Tool set 변경 없음.
- **Runtime classifier 연결**: `from scripts.validation.stage_a_classify import load_classifier` 재사용. run_agent 진입 시 1회 로드, 실패 시 graceful no-hint mode.
- **평가 설계**: V0 + V1 (primary) + V1b (exact-only, cascade 제거) + V1c (no-replan). Online-Mind2Web은 future work. Task N은 pilot-driven (env error 해소 → pilot → power analysis → 확정).

---

## 관련 문서

- `docs/validation/stage_c_edge_graph_report.md` — edge graph (2,813 edges, adjacency)
- `docs/validation/stage_b_action_catalog_report.md` — 4,816 actions
- `docs/validation/class_discovery_protocol.md` — CDIP v0.2
- `docs/validation/V1_protocol_spec.md` — class taxonomy v0.6
- `docs/research_roadmap.md` — 최종 goal + Stage 위상
