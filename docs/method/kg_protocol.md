# CDIP — Class Discovery Iteration Protocol

**Version**: 0.2 (step/within-step 개념 분리, Option 1 frontier-BFS 채택)
**Date**: 2026-04-21

## Positioning

**Site-agnostic protocol**: 웹 사이트의 URL 집합에서 page class taxonomy를 반복적(iterative)으로 도출하기 위한 절차. 연구 contribution은 protocol이며, site별 taxonomy는 protocol의 output(worked example)이다.

**목표**:
- Input: 사이트 base URL + 초기 seed URL
- Output: 해당 사이트의 URL → class 매핑 rule + class taxonomy (leaf classes, variants, instance bindings)
- 보장: protocol만 고정하면 다른 사이트에서도 같은 절차로 재현 가능 (site별 구현 상수만 교체)

**전제**:
- Class 정의는 `V1_protocol_spec.md` (protocol v0.6) 를 따름 — recursive class inheritance tree + action-repertoire equivalence criterion
- 각 URL은 HTTP 200 기준, template-level로 분류 (instance data에 흔들리지 않음)

---

## Terminology (v0.2 refined)

**Step** (외부 loop): 1회 complete cycle — {crawl (frontier-based) → cluster unmatched → annotate → rule 재추출 → validate → 필요 시 재cluster}. 각 step이 새 URL을 실제로 추가하고 class taxonomy를 확장.

**Within-step rule compression** (내부 loop): step의 crawl 단계가 끝난 뒤, 현재까지 누적된 accumulated URL pool에 대해 {cluster unmatched → annotate → rule 재추출 → re-classify}를 여러 사이클 돌려 unmatched=0에 수렴시키는 사이드 loop.

**Iteration**이라는 표현은 모호하므로 사용하지 않음. **Step** 또는 **within-step compression cycle** 중 택일.

## Key insights

### "Compression by rule expansion" (within-step)

같은 pool 내 새 class 발견·rule 추가만으로 unmatched를 matched로 전환. URL 재수집 없이 coverage 확장. 하지만 이 메커니즘은 **이미 crawl된 영역 내에서만** 작동. 새 영역(site 내 미탐사 branch)은 다음 step의 crawl에서 도달해야.

### "Frontier-BFS expansion" (across steps, Option 1)

각 step은 **이전 step의 BFS tree leaves (혹은 parents of leaves)**에서 시작해 새 URL을 BFS로 확장. 이미 방문한 URL은 skip. 새 URL pool에 accumulate하고 다시 within-step compression 실행.

→ **Option 1 스타일** — 각 step이 실제로 새 site 영역 탐색. Iter-to-iter arbitrary random seeds와 다름.

### Budget 이중 구조

- **Global budget** (무한 loop 방지):
  - `GLOBAL_MAX_URL`: 모든 step 누적 URL 상한 (e.g., 5000-10000)
  - `GLOBAL_MAX_CLASS`: 누적 class 상한 (e.g., 200)
- **Step-local budget**:
  - `STEP_MAX_URL`: step당 새 URL 상한 (e.g., 1500)
  - `STEP_MAX_DEPTH`: step 내 BFS depth 상한 (e.g., 5)

---

## Step loop (CDIP v0.2 — Option 1 frontier-BFS)

```
# Pre-conditions
accumulated_urls = {}        # 누적 URL pool
rules = initial_rules        # (e.g., 비어있음, 또는 Stage A.c~A.e 기반)
global_url_count = 0
global_class_count = 0

# Step 1 (initial)
frontier_seeds = initial_base_urls  # site entry point
new_urls = BFS(frontier_seeds, STEP_MAX_URL, STEP_MAX_DEPTH, skip=accumulated_urls)
accumulated_urls ∪= new_urls
global_url_count += |new_urls|

while True:
    # Within-step compression (rule 반복 확장, 같은 pool 내에서)
    while True:
        matched, unmatched = classify_all(accumulated_urls, rules)
        if not unmatched or new_class_count_in_compression == 0:
            break
        clusters = cluster(unmatched)
        new_class_count_in_compression = 0
        for cluster in clusters:
            rep = pick_representative(cluster)
            collect_axtree(rep)
            llm_annotate(rep)
            user_class = apply_convention(llm, v0.6)
            new_class_count_in_compression += 1
        rules = extract_rules(all_annotations)
        self_validate(rules)
    
    # Convergence check (step-level)
    step_new_classes = count_new_classes_this_step()
    step_unmatched = len(unmatched)
    if step_new_classes == 0 and step_unmatched == 0:
        break  # converged
    if global_url_count >= GLOBAL_MAX_URL:
        break  # safety
    if global_class_count >= GLOBAL_MAX_CLASS:
        break  # safety
    
    # Next step: frontier expansion
    prev_leaves = leaves_of_bfs_tree(new_urls)  # 또는 parents of leaves
    frontier_seeds = [r.url for r in prev_leaves]
    new_urls = BFS(frontier_seeds, STEP_MAX_URL, STEP_MAX_DEPTH, skip=accumulated_urls)
    accumulated_urls ∪= new_urls
    global_url_count += |new_urls|

# Final (optional): convergence 검증 fresh crawl
fresh = BFS_crawl(original_seeds, rules, params=final_check)
verify_unmatched_stable(fresh, rules)
```

---

## Per-iteration strategy evolution

각 iteration은 crawl·cluster·annotate·rule·validate 단계로 구성되지만, **iteration 번호에 따라 세부 전략을 진화**시켜 discovery 효율 극대화.

| Iter | Crawl 여부 | Seeds | Known-cap | Max URL | Max depth | Link-extract-on-skip | 목적 |
|---|---|---|---:|---:|---:|---|---|
| 1 | **Fresh BFS** | initial (사이트 대표 진입점) | 5 | 1500 | 5 | No (cap 도달 시 skip 완전) | Rule 일반화 검증 + 초기 URL pool |
| 2 | **Skip** (기존 pool 재분류) | — | — | — | — | — | 주 compression — unmatched 축소 |
| 3+ | Optional (frontier 확장 or gap-centric) | initial + prev iter의 unmatched cluster 대표 | 2 | 2000 | 7 | **Yes** (숨은 링크 발견) | Residual gap 해소 |
| Final | **Fresh BFS** (convergence 확인) | initial | 5 | 500-1000 | 5 | No | 새 URL에서 unmatched 0인가 확인 |

**Strategy 기법**:
- **Link-extract-on-skip**: known-cap 도달한 URL도 페이지 방문해서 링크만 추출 (새 URL 발견 목적). Iter 3+에서 도입
- **Gap-centric seeds**: 이전 iter unmatched cluster 대표를 seed에 추가 → 해당 영역 주변 탐색
- **Cap 축소**: iter 2+는 rule 이미 검증되었으므로 known-cap 1-2로 낮춰 budget을 discovery에 집중
- **Depth 확장**: Known이 빨리 cap되어 queue에 여유 생기면 더 깊이 탐색 가능

---

## Convergence criteria (후보)

정량 기준은 사이트·iteration 실행 경험을 바탕으로 확정. 후보:

| 기준 | 설명 | 장점 | 단점 |
|---|---|---|---|
| **새 class 발견 수 = 0** | 이번 iter에서 발견한 신규 class 0 | 깨끗한 종료 | Long-tail edge case가 항상 있으면 도달 불가 |
| **Unmatched URL < X** | Unmatched 수가 threshold 아래 | 정량, 실용적 | X 선정 임의성 |
| **Unmatched 감소율 < Y%** | 두 iter 간 감소 비율 plateau | Diminishing returns 포착 | 일시적 plateau에 오도 가능 |
| **Iteration 횟수 상한** | 고정 N회 반복 후 stop | 시간 통제 | 수렴 보장 못함 |

권장: **(새 class == 0) OR (unmatched 감소율 < Y%)** 조합. Tail은 accept, plateau 도달 시 stop.

---

## Site-agnostic vs site-specific 요소

**Positioning 원칙**: CDIP는 **개념적으로 site-agnostic 프로토콜**이며, 현 구현은 **WebArena-Verified GitLab에 대한 구체화(concrete realization)**이다. Protocol skeleton (step loop, BFS + cluster + rule extract + validate의 순환, compression-by-rule-expansion, frontier-BFS 개념)은 site에 의존하지 않으나, 각 stage 내부의 **구성 상수와 일부 URL scheme 휴리스틱**은 GitLab에 결합되어 있다.

| 요소 | 종류 | 현재 위치 | 추후 site 이식 시 |
|---|---|---|---|
| BFS 알고리즘 | **generic** | `scripts/validation/stage_a_f_crawl.py` | 재사용 |
| URL 정규화 | **generic** | `site_adaptive_webagent/kg/urlnorm.py` (단 site_config.yaml 필요) | config 교체 |
| Clustering 알고리즘 (placeholder 치환) | **generic** | `stage_a_f_cluster.py` | 재사용 |
| Rule 도출 알고리즘 skeleton (template inference, specificity) | **generic** | `stage_a_extract_rules.py` | 재사용 |
| URL scheme 휴리스틱 (`_derive_from_single`) | **GitLab realization** | `stage_a_extract_rules.py::_derive_from_single()` | **site-specific 함수 교체 필요** (예: GitHub의 다른 path 구조) — 다른 site 이식 시 이 함수를 override |
| 명명 convention (scope/family/type) | **generic** | `V1_protocol_spec.md` v0.6 | 재사용 |
| Class criterion (action equivalence) | **generic** | `V1_protocol_spec.md` Step 2 | 재사용 |
| Seed URLs | **site-specific** | `config/sites/<site>/crawl.yaml` | config 교체 ( 완료 ✓) |
| KNOWN_NAMESPACES, KNOWN_USERNAMES, ACTION_KEYWORDS, sample_values | **site-specific** | `config/sites/<site>/entities.yaml` | config 교체 ( 완료 ✓) |
| Forbidden URL patterns + allowed_hosts + base_url | **일부 site-specific** | `config/sites/<site>/crawl.yaml` | config 교체 ( 완료 ✓) |
| `site_config.yaml` (decorative_params, identity_tokens 등) | **site-specific** | `config/sites/<site>/site_config.yaml` | config 교체 (기존 ✓) |
| Cascade config (scope_entries, hub) — runtime | **site-specific** | `config/sites/<site>/cascade.yaml` | config 교체 ( 완료 ✓) |
| MUTATE checklist + filter preamble + tool desc — runtime | **site-specific** | `config/sites/<site>/prompts.yaml` | config 교체 ( 완료 ✓) |

**현 이식 대가**:

- **Config 계층 (값 이관)**: -2 완료. 다른 site로 옮길 때 `config/sites/<site>/*.yaml` 6개 파일만 작성하면 protocol skeleton이 그대로 동작.
- **Algorithm 계층 (GitLab 휴리스틱)**: `_derive_from_single()`의 URL scheme 분기 (`/-/` prefix, `tree/blob/raw/commits/blame` ref keywords 등)는 **GitLab 구체화 그대로 잔존**. 다른 site 이식 시 해당 함수를 site-specific 버전으로 교체해야 한다. Protocol paper에서는 이 함수를 "GitLab realization of the template derivation step" 으로 소개하는 것이 정직.

**결론 (framing)**: CDIP **개념** = site-agnostic, CDIP **GitLab 구현** = 본 repo의 `scripts/validation/` 계열. 논문에서는 protocol의 추상적 procedure를 기술하고, 구체화는 GitLab worked example로 제시. Cross-site generalization은 explicit future work (plugin 교체 + config 작성 + 재측정).

---

## Tool chain (step별 script 매핑)

| Step | 도구 | 성격 |
|---|---|---|
| Crawl | `stage_a_f_crawl.py` | 신규 (iter 1에서 작성) |
| Classify (pre-visit or post) | `stage_a_classify.py` | 신규 (Stage A.e 산출) |
| Cluster unmatched | `stage_a_f_cluster.py` | **iter 2에서 신규** |
| Representative sample AXTree 수집 | `stage_a_f_collect_samples.py` | **iter 2에서 신규** (v1_a의 `collect_page()` 재사용) |
| LLM annotation | `v1_b_llm_annotate.py` | 재사용 (skip-existing) |
| Assistant convention 적용 | `v1_c_fill_annotations.py` | 재사용 (ANNOTATIONS dict 확장) |
| Rule 도출 | `stage_a_extract_rules.py` | 재사용 |
| Rule 재적용 + coverage 분석 | `stage_a_f_apply.py` | 재사용 |

---

## Worked example — GitLab

### Stage A.a-e (sample build + rule init)
| Stage | 결과 |
|---|---|
| A.a | 23 → 57 page AXTree 수집 |
| A.b | 57 LLM annotation |
| A.c | 57 user_class 확정 (51 unique class) |
| A.verify | Action set 실측, class criterion 검증 |
| A.e | 51 rule 추출, self-validation 57/57 = 100% |

### Stage A.f — Step 실행 (CDIP v0.2 Option 1 frontier-BFS)

#### Step 1: Fresh BFS + within-step compression
- Crawl: 6 initial seeds, max 1500 URL, depth 5 → 1457 HTTP 200 records
- Within-step compression: 1457 URLs에 rule 반복 재추출 (iter 1→2→3→4)
  - 초기 rule: 51 → compression iter 4: 141 rule
  - Annotation: 57 → 188
  - Coverage: 14.3% → 100% (1457/1457)
- 산출: class_rules.json(141), all_annotated.json(188), classified.json(1457)

#### Step 2': Frontier-BFS expansion
- Frontier = Step 1 BFS의 max-depth leaves (454 URLs)
- 각 leaf 재방문하여 outbound link 추출 (children at depth 4+)
- Children BFS, Step 1 pool skip
- 결과: 238 new records (94.6% matched)
- 남은 7 unmatched = branch variant 문제 (같은 class, 다른 branch)
  - Iter 5 patch: master 브랜치 인스턴스 추가 → rule extractor 자동 generalization
- Step 2' convergence: **새 class 0, unmatched 0**

#### Combined pool (step 1 + step 2')
- 1695 URLs, 1619 HTTP 200, **100% coverage (1619/1619)**
- 141 rules, 190 annotations, 138 classes, 7 scopes
- 진정한 convergence 선언

---

## Limitation (현 시점)

1. **GitLab 1 사이트**에서만 실행됨 — cross-site reproducibility는 future work
2. **Convergence threshold 정량 기준 미확정** — 본 loop 돌려가며 실증 선정
3. **Scripts의 site-agnostic refactor 미완** — 현재 상수 hardcoded
4. **Link-extract-on-skip 미구현** — iter 3+에서 필요 시 추가

## Related docs

- `docs/validation/V1_protocol_spec.md` — class taxonomy 정의 protocol (v0.6)
- `docs/validation/V1_annotation_filled.md` — 현 57 annotation + class tree
- `docs/validation/V1_deferred_issues.md` — 관측 한계 (accname, href, lazy-render 등)
- `docs/validation/stage_a_rules_report.md` — Stage A.e rule 추출 결과
- `docs/validation/stage_a_f_fresh_crawl_report.md` — Iter 1 결과
- `docs/research_roadmap.md` — 전체 연구 목적 + Stage A-B-C 위상
