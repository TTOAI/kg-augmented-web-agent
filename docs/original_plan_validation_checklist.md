# Original Plan — Validation Checklist

**작성일**: 2026-04-19
**목적**: Original plan (Solution 1 Browser Agent class-based KG + Solution 2 multi-hop simulation)을 최대한 수용하면서 각 critical issue를 **empirical하게 직접 검증**. 이론적 논쟁 대신 실제 GitLab에서 DOM 탐색 + pilot 실행으로 답변.

**검증 대상 환경**: WebArena-Verified GitLab (localhost:8023)
**검증 사용 KG**: 현 Frozen KG `2026-04-16T16-46-55Z.json` (비교/참조 용도)
**검증 원칙**: 순차적, 각 item의 결과가 다음 item design 가이드

---

## Phase 구분

- **Phase A** (V0-V5): 수동 탐색 + Class identification rule 도출
- **Phase B** (V6-V10): KG construction pipeline pilot
- **Phase C** (V11-V14): Simulation capability pilot
- **Phase D** (V15-V18): Task-class mapping pilot
- **Phase E** (V19-V22): Quality / reproducibility
- **Phase F** (V23-V24): Cost / timeline aggregation

각 item의 결과는 `docs/validation/V{N}_result.md`로 기록.

---

## Phase A — 수동 탐색 + Class Identification Rule

### V0. Foundation sanity

**V0.1. GitLab 환경 접근 및 AXTree 수집 pipeline**
- **검증 질문**: Playwright로 GitLab 페이지의 AXTree를 일관되게 얻을 수 있나?
- **방법**:
  - `webarena-verified env start --site gitlab` 실행
  - 기존 `playwright_crawler.py` 또는 간단 script로 5 페이지 AXTree 수집
  - 2회 재실행 시 AXTree 동일성 확인
- **Success**: 동일 URL 5회 방문 시 AXTree 98%+ 일치 (동적 timestamp 제외)
- **산출**: `output/validation/V0_1_axtree_samples/`

**V0.2. 기존 Frozen KG 구조 파악**
- **검증 질문**: 현 KG의 StatePattern / Action / LeadsToEdge / InfoType / RealizesEdge 분포와 품질
- **방법**:
  - `scripts/kg_inspect.py` (신규) — KG load 후 요소 수·분포·sample dump
  - RealizesEdges = 0 재확인 + 왜 empty인가
  - 37 InfoType이 실제 어떤 category인지 list화
- **Success**: KG 구조 보고서. 재사용 가능한 부분·재구축 필요 부분 분리
- **산출**: `docs/validation/V0_2_kg_inventory.md`

### V1. Page Class Identification (수동 annotation)

- **검증 질문**: 같은 type의 페이지를 deterministic rule로 식별할 수 있나?
- **방법**:
  - 15-20 GitLab 페이지 수동 선정 (주요 section 다양하게)
    - Home, dashboard, project pages, issue list/detail, MR list/detail, commits, wiki, CI, user profile, explore
  - 각 페이지 AXTree 수집
  - 수동 annotation: "이 페이지의 class 이름" + "class 판단 근거"
  - Rule 추출: AXTree role (main) + heading text + URL template + repeated sibling pattern의 어떤 조합
- **Success**: deterministic rule로 15-20 페이지 중 80%+ 맞춤. 실패 case 원인 분석
- **산출**: `docs/validation/V1_class_annotation.md` + `docs/validation/V1_rules.md`

### V2. 반복 Element (list) 단일 Class 압축

- **검증 질문**: "게시물 list 안의 각 게시물"을 단일 class로 압축할 수 있나?
- **방법**:
  - V1 페이지들 중 list가 있는 페이지 선정 (issue list, project list, MR list 등)
  - AXTree에서 **반복 sibling pattern 탐지**
    - 같은 role + 같은 attribute set의 n개 element
  - 반복 element의 내부 구조 (field set)가 일관되는지 확인
  - 각 list에서 item class를 1개로 압축하는 rule 도출
- **Success**: 5+ list에서 반복 pattern 90%+ 정확히 탐지
- **산출**: `docs/validation/V2_list_compression.md`

### V3. Context-dependent Class 구분

- **검증 질문**: "최신 posts" vs "내 posts" 같은 context 차이를 KG에 어떻게 표현?
- **방법**:
  - 같은 page template이 다른 context로 나타나는 사례 3개 이상 탐색
    - 예: /dashboard/issues vs /{project}/-/issues
    - 예: /explore/projects vs /dashboard/projects
  - AXTree 비교 → 유사도 측정
  - Solution: 같은 class + parent class로 구분 vs 별개 class
- **Success**: Context 구분 방법 결정 (parent-child edge or separate class)
- **산출**: `docs/validation/V3_context_handling.md`

### V4. Deterministic Rule vs LLM 경계

- **검증 질문**: 어느 class identification 단계에서 LLM이 필요한가?
- **방법**:
  - V1-V3 결과 분석
  - Deterministic rule로 풀 수 있는 비율 계산
  - LLM 필요한 case 분류 (예: class name 명명, semantic grouping)
  - LLM 사용 시 cost 예측
- **Success**: Rule-based 70%+ + LLM fallback 30% 이하. Hybrid algorithm 확정
- **산출**: `docs/validation/V4_rule_llm_boundary.md`

### V5. Class ID Consistency (pilot ARI)

- **검증 질문**: 동일 사이트를 두 번 scan하면 같은 class가 나오나?
- **방법**:
  - V1 rule + V4 hybrid algorithm으로 pilot script 작성
  - 20 페이지 × 2 run
  - Class assignment 비교
  - Adjusted Rand Index (ARI) 측정
- **Success**: ARI ≥ 0.85 (과거 KG derivation ARI=0.93 수준)
- **산출**: `docs/validation/V5_consistency.md`

---

## Phase B — KG Construction Pipeline Pilot

### V6. Browser Agent BFS Exploration Cost

- **검증 질문**: 10-hop exploration이 실제 비용은 얼마?
- **방법**:
  - Simple Browser Agent prototype 작성 (GPT-5.4-nano 사용)
  - 2-hop pilot (home → 1st level → 2nd level)
  - 페이지당 비용 측정 (LLM tokens, time)
  - 10-hop extrapolation (fan-out 고려)
- **Success**: 10-hop 총 비용 ≤ $150 추정
- **산출**: `docs/validation/V6_agent_cost.md`

### V7. Class 수 실측

- **검증 질문**: GitLab의 실제 class 수 범위는?
- **방법**:
  - V6의 2-hop pilot 결과 class 수 count
  - 10-hop extrapolation
- **Success**: 20-80 범위 (원래 예상). >200이면 abstraction 실패 신호
- **산출**: `docs/validation/V7_class_count.md`

### V8. Class-Instance 매핑 자동화

- **검증 질문**: 기존 StatePattern 3,040개 중 sample 50개를 새 class에 자동 매핑 가능?
- **방법**:
  - V5의 class catalog (예: 30-50 class)
  - 기존 StatePattern 50개 random sample
  - 각 StatePattern의 URL template과 class 비교 → 자동 매핑 rule
  - Manual ground truth와 accuracy 비교
- **Success**: 자동 매핑 accuracy ≥ 80%
- **산출**: `docs/validation/V8_mapping_automation.md`

### V9. Widget-level Identification DOM Fragility

- **검증 질문**: DOM structure 기반 widget 식별이 robust한가?
- **방법**:
  - V1 페이지들의 AXTree 수집 후 1주일 뒤 재수집 (또는 GitLab version check)
  - Widget identifier (role + label + attribute) 변화율 측정
- **Success**: 변화율 ≤ 5% (robust). 높으면 fallback strategy 필요
- **산출**: `docs/validation/V9_dom_fragility.md`

### V10. Class Hierarchy (Containment) 처리

- **검증 질문**: "게시판 class는 게시물 class list를 가진다"를 KG에 어떻게 표현?
- **방법**:
  - V2의 list compression 결과 + V1의 class catalog
  - Hierarchy edge type 제안: `contains` vs `leads_to` 구분
  - Flat graph vs nested 구조 비교
- **Success**: Hierarchy 표현 schema 확정
- **산출**: `docs/validation/V10_hierarchy.md`

---

## Phase C — Simulation Capability Pilot

### V11. Class-level Graph BFS Simulation

- **검증 질문**: Class-level graph에서 BFS로 multi-hop path 찾을 수 있나?
- **방법**:
  - V5 class catalog + V6 pilot에서 발견된 class-level edges
  - Sample start class 5개 × target class 5개 = 25 path query
  - BFS simulation 돌려서 reachability 측정
- **Success**: 25 path 중 ≥ 15개 path 발견 (60%+ reachability)
- **산출**: `docs/validation/V11_simulation_basic.md`

### V12. Class Simulation → Instance URL 변환

- **검증 질문**: Class target이 주어졌을 때 실제 instance URL 생성 가능?
- **방법**:
  - V11의 발견된 path 5개 선택
  - 각 path의 target class → instance URL 생성 시도
  - Bindings extraction (v3의 3-tier 사용)
  - 실제 browser.goto() 시도
- **Success**: 5개 중 ≥ 3개 성공적 goto
- **산출**: `docs/validation/V12_class_to_instance.md`

### V13. Filter/Sort State의 Class 표현

- **검증 질문**: `?state=open&label=bug` 같은 dynamic filter state를 KG에 어떻게 담나?
- **방법**:
  - GitLab issue list에서 filter 조합 10개 pilot
  - 각각의 URL + DOM 비교
  - 별개 class vs 같은 class의 parameterized variant 판단
- **Success**: Filter 처리 policy 결정
- **산출**: `docs/validation/V13_filter_state.md`

### V14. Cross-class Navigation Accuracy

- **검증 질문**: Simulation이 제안한 path를 실제 실행하면 도달?
- **방법**:
  - V11의 발견된 path 10개
  - 각각 실제 browser로 실행 (click through)
  - Target class에 도달한 비율
- **Success**: ≥ 60% 실제 도달
- **산출**: `docs/validation/V14_path_accuracy.md`

---

## Phase D — Task-Class Mapping Pilot

### V15. Sub-goal → Target Class Classification

- **검증 질문**: Sub-goal text를 class에 mapping 정확도는?
- **방법**:
  - Eval task 50개 중 build_plan 실행 (기존 LLM)
  - 각 sub-goal을 class catalog에 수동 매핑 (ground truth)
  - 자동 매핑 (keyword + LLM) vs ground truth 비교
- **Success**: Top-3 accuracy ≥ 80% (ground truth class가 top-3 후보에 포함)
- **산출**: `docs/validation/V15_subgoal_classification.md`

### V16. Keyword Match Rate

- **검증 질문**: Deterministic keyword match만으로 어디까지 커버?
- **방법**:
  - V15 sub-goal 결과에서 keyword match 적용
  - Match rate / coverage 측정
- **Success**: Keyword match ≥ 50% (나머지 LLM fallback). 80%+면 LLM 거의 불필요
- **산출**: `docs/validation/V16_keyword_rate.md`

### V17. "가장 가까운 Page" 정의 실용성

- **검증 질문**: Simulation target을 "가장 가까운 page class"로 잡는 것이 실제로 합리적?
- **방법**:
  - V15의 10 task × "이상적 target 1개" vs "도달 가능 target 여러개 중 가장 가까운"
  - 후자 선택 → agent의 마지막 단계 추가 복잡도 측정 (filter/sort 적용 등)
- **Success**: 가장 가까운 page 도달 후 agent가 마지막 단계 수행 성공률 ≥ 60%
- **산출**: `docs/validation/V17_nearest_target.md`

### V18. Agent Compliance with Hint

- **검증 질문**: Hint가 주어졌을 때 agent가 따르는 비율?
- **방법**:
  - 3 task × hint 주입 vs 미주입
  - Agent first action이 hint의 first step과 일치하는 비율
- **Success**: Compliance ≥ 60% (hint가 reasonable하면 agent가 따름)
- **산출**: `docs/validation/V18_agent_compliance.md`

---

## Phase E — Quality / Reproducibility

### V19. Browser Agent 재실행 ARI

- **검증 질문**: 같은 site exploration 2회 결과 consistency?
- **방법**:
  - V6 Browser Agent를 2회 돌림 (different random seed)
  - 각 run의 class catalog 비교
  - ARI 측정
- **Success**: ARI ≥ 0.80
- **산출**: `docs/validation/V19_reproducibility.md`

### V20. Manual Annotation vs Automated 일치율

- **검증 질문**: Automated가 manual ground truth를 얼마나 reproduce?
- **방법**:
  - V1의 15-20 manual annotation을 ground truth로 사용
  - V6 automated result와 비교
  - Class assignment agreement 측정
- **Success**: Agreement ≥ 75%
- **산출**: `docs/validation/V20_manual_auto_agreement.md`

### V21. NET Eval과 KG URL 정합성

- **검증 질문**: Class-level KG로 도달한 URL이 NET evaluator가 기대하는 URL과 일치?
- **방법**:
  - Eval task 10개 선택
  - Task의 expected URL (eval_result.json의 NetworkEventEvaluator expected) 수집
  - Class KG로 simulation → 도달 URL vs expected
- **Success**: Match rate ≥ 60%
- **산출**: `docs/validation/V21_eval_alignment.md`

### V22. Failure Mode Taxonomy (pilot 기반)

- **검증 질문**: 어떤 실패 유형이 발생하는가?
- **방법**:
  - V11-V14, V15-V18의 실패 case 수집
  - Taxonomy 생성 (class ID error, bindings incomplete, goto redirect, etc.)
- **Success**: 명확한 taxonomy + 각 유형 빈도
- **산출**: `docs/validation/V22_failure_taxonomy.md`

---

## Phase F — Cost / Timeline 통합

### V23. Total Phase 비용 추정

- **검증 질문**: Phase 0 + Phase 1 + Phase 2 총 비용?
- **방법**:
  - V6 (Browser Agent) + V8 (mapping) + simulation + measurement 비용 aggregation
- **Success**: Total ≤ $500 수용 가능
- **산출**: `docs/validation/V23_cost_estimate.md`

### V24. Fallback 경로

- **검증 질문**: 각 step 실패 시 회피 경로?
- **방법**:
  - V1-V22 결과 기반 failure matrix
  - 각 failure에 대응하는 fallback (예: Class ID 실패 → Hybrid로 downgrade)
- **Success**: 모든 failure에 대응 fallback 존재
- **산출**: `docs/validation/V24_fallback_matrix.md`

---

## 우선순위 및 Dependency

```
V0 (foundation)
  ↓
V1 (manual annotation) → V2 (list compression) → V3 (context)
  ↓                        ↓                       ↓
V4 (rule/LLM boundary)
  ↓
V5 (consistency ARI)
  ↓
V6 (agent cost) → V7 (class count)
  ↓
V8 (mapping automation)
  ↓
V9 (DOM fragility) || V10 (hierarchy)
  ↓
V11 (simulation) → V12 (URL generation) → V13 (filter) → V14 (navigation)
  ↓
V15 (subgoal classification) → V16 (keyword rate) → V17 (nearest) → V18 (compliance)
  ↓
V19-V20-V21 (quality) || V22 (failure)
  ↓
V23-V24 (aggregation)
```

**Critical path**: V0 → V1 → V4 → V5 → V6 → V11 → V15 → Go/No-Go

---

## 실행 순서 (제안)

### Sprint 1 (V0-V5) — 수동 + 1st pilot, 4-5일
1. V0.1 + V0.2 (Day 1)
2. V1 + V2 + V3 (Day 2-3)
3. V4 + V5 (Day 4-5)

**체크포인트 1**: Deterministic rule 커버리지 ≥ 70%? ARI ≥ 0.85? → Go/No-Go

### Sprint 2 (V6-V10) — Browser Agent pilot, 4-5일
4. V6 + V7 (Day 6-7)
5. V8 + V9 + V10 (Day 8-10)

**체크포인트 2**: 10-hop 비용 < $150? Mapping accuracy ≥ 80%? → Go/No-Go

### Sprint 3 (V11-V14) — Simulation pilot, 3-4일
6. V11 + V12 (Day 11-12)
7. V13 + V14 (Day 13-14)

**체크포인트 3**: Path accuracy ≥ 60%? → Go/No-Go

### Sprint 4 (V15-V18) — Task mapping pilot, 3-4일
8. V15 + V16 (Day 15-16)
9. V17 + V18 (Day 17-18)

**체크포인트 4**: Sub-goal classification top-3 accuracy ≥ 80%? → Go/No-Go

### Sprint 5 (V19-V24) — Quality + aggregation, 2-3일
10. V19-V22 (Day 19-20)
11. V23-V24 (Day 21)

**Final decision**: Full Original vs Hybrid vs v3

**총 21일 (3주)**. 매 Sprint 종료 시 go/no-go.

---

## 각 Validation item의 output format

```markdown
# V{N} — {Title}

**Date**: YYYY-MM-DD
**Status**: In Progress / Complete / Blocked / Skipped

## Question
{검증 질문}

## Method
{수행 방법 + 사용 도구}

## Data
{수집한 데이터 요약, 상세는 output/ 디렉토리}

## Result
{측정 결과 + 수치}

## Success / Failure
{사전 기준 대비 판정}

## Implications
{이 결과가 Original plan에 주는 영향}

## Next step
{다음 validation item 또는 blocker}
```

---

## 전체 Validation의 최종 output

모든 V0-V24 완료 후 `docs/validation/summary.md`에:

1. 각 item 결과 1-line 요약
2. Go/No-Go 판정 트리 (Full Original / Hybrid / v3)
3. Refined design (Phase 1 specification)
4. Timeline + cost 확정
5. Paper contribution framing

---

## 승인 필요

1. **이 checklist로 Sprint 1 시작** 동의?
2. V0 foundation 먼저 (Day 1)?
3. 각 V item의 output md 형식 OK?
4. Sprint 종료 시 gate 기준 사용 OK (위 명시)?
5. 전체 3주 validation 후 Phase 1 설계 결정 — OK?
