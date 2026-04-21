# Stage A.g — Retrospective

**Date**: 2026-04-21
**Status**: Stage A (class identification) complete. Handoff to Stage B.

## Executive summary

GitLab 사이트에서 site-specific class taxonomy를 **CDIP v0.2 (Class Discovery Iteration Protocol)**으로 도출 완료. 최종 taxonomy는 **7 scope × 138 unique class**, **141 rules** self-validation 100%, **combined URL pool 1695개 100% coverage**.

연구 기여물은:
1. **CDIP 프로토콜** (site-agnostic class discovery method)
2. **GitLab taxonomy** (worked example)
3. **Rule extractor** (re-usable tool)

---

## Journey — 주요 단계

### Stage A.a–c: Initial sample
- 23 페이지 → LLM annotate → convention 적용
- 확장 22 → 57 (dashboard filter tabs, topics, instance variance)
- Scope-first hierarchical class 체계 합의

### Stage A.verify: Action set 실측
- 57 sample의 core widget + action set 측정
- False-positive 2건 correction (settings/issues sub-nav artifact)
- `account/` scope 신설 (`/-/profile/*` 전용 사이드바 14 action)

### Stage A.e: Rule 추출
- 57 annotation → 51 rules + self-validation 57/57 = 100%
- URL template + path_params + variant_queries 구조

### Stage A.f: Stepwise discovery
- **Step 1**: 6 initial seeds → 1500 URL BFS → within-step compression 4 iter → 100%
- **Step 2' (frontier-BFS)**: Step 1 leaves → 238 new URL → rule generalization → 100%
- Total: 1695 URLs, 138 classes, 141 rules

---

## Protocol version history (snapshot)

| Version | 핵심 변경 | 파일 |
|---|---|---|
| V1_protocol_spec v0.1 | Initial provisional draft | `docs/validation/V1_protocol_spec.md` |
| v0.2 | 확장 (level별 분류, parent-variant semantics, 5 core principles, 경계 case) | |
| v0.3 | Scope-first 3-tier 체계 | |
| v0.4 | Recursive class inheritance tree로 일반화 (고정 → 가변 N-tier) | |
| v0.5 | `account` scope 신설, methodology notes (broader selector first, false-positive checklist) | |
| **v0.6** | **Naming 우선순위 (convention → page label respect), leaf 재사용 원칙 명시** | **현재** |
| | | |
| CDIP v0.1 | Site-agnostic discovery protocol 초안 | `docs/validation/class_discovery_protocol.md` |
| **CDIP v0.2** | **Step/within-step 분리, Option 1 frontier-BFS, global/local budget** | **현재** |

---

## Key empirical findings

### 1. Compression by rule expansion (within-step)

Step 1 내부에서 rule 반복 확장만으로 coverage 14.3% → 100%. URL 재수집 없이 기존 1457 URL의 unmatched 1248개를 0으로. Compression ratio 이점 입증.

### 2. Frontier-BFS의 진정한 coverage 확장 (across-step)

Step 2'에서 238 new URL (step 1 영역 밖) 발견. 이 중 7개는 branch variant (structural new class 아님) → 2 instance 추가로 rule 자동 generalization. Option 1 스타일의 실효성 증명.

### 3. Rule 일반화 cross-namespace

138 class 중 instance variance 있는 class (e.g., project/main, project/issue_list)가 byteblaze, a11yproject, the-a11y-project, solarized-prism-theme 등 여러 namespace에서 일관 매칭. namespace를 `{namespace}` path_param으로 일반화하는 extractor 로직 효과적.

### 4. Template-level 기준 (state-independent)

`/dashboard/issues`에 "New issue" 버튼이 **issue 개수와 무관하게** 부재 — dashboard scope의 template 특성. action-gating 아니라 template 경계. Class 정의가 template level임을 실증.

### 5. Broader-selector first methodology

Narrow selector (`button, a[role=button], .gl-button`)가 sidebar anchor miss → settings/issues sub-nav false positive. Broader selector (`a, button, [role=button], [role=tab]`)로 재측정 → artifact 철회 + account scope 발견.

---

## Taxonomy 최종

### Scope 분포

| Scope | Classes | 대표 |
|---|---:|---|
| project | 85 | main, issue_list, merge_request_list, file_list, commit_list, settings_*, detail류 등 |
| account | 14 | edit, preferences, keys, emails, gpg_keys, personal_access_tokens 등 |
| global | 10 | help_landing, help_page, snippet_list, search_page, new_project_form, import_form 등 |
| user | 9 | profile, activity_list, contributed_project_list, follower_list 등 |
| dashboard | 7 | project_list/yours, issue_list, merge_request_list, todo_list/pending-done, group_list |
| explore | 5 | project_list/all-starred-trending, topic_list, topic_detail |
| ide | 3 | edit_view, mr_view, mr_detail |

### Variant 사용

- `dashboard/project_list/yours`, `/starred` (2)
- `dashboard/todo_list/pending`, `/done` (2)
- `explore/project_list/all`, `/starred`, `/trending` (3)

### Compression ratio (참고)

- URL pool 1695 → 138 class = **12.3× compression**
- Site 전체는 pool보다 훨씬 많을 것 → 실 compression은 더 클 수 있음

---

## Limitations (honest accounting)

### Scope
- **GitLab 1 site만 실행** — cross-site reproducibility는 future work
- **WebArena-Verified instance 특이성** (admin 없음, group 거의 없음 등) 관찰
- **Empty class (group scope)** — 이 인스턴스에 group 데이터 없어 group scope 미관찰

### Protocol
- **Convergence threshold 정량 기준 미확정** — "새 class 0 + unmatched 0" 달성으로 ad-hoc 수렴 선언. Pre-commit 정량 기준(예: κ, coverage %)은 Part C에 미결 항목으로 기록됨
- **Site-specific constants hardcoded** — KNOWN_NAMESPACES, ACTION_KEYWORDS, forbidden patterns 등이 Python 상수. Config 외부화는 future work

### Measurement
- **Single snapshot** — Drop-down 내부, hover/click으로 mount되는 content는 캡처 못 함 (D3, Stage B에서 stateful crawl로 해결)
- **Accname 미계산** — 현 추출기는 DOM-walk 기반, W3C accname 알고리즘 미적용 (D2)
- **href discard in label** — innerText 있으면 href 정보 잃음 (D1)

### Annotation quality
- **Assistant 채움 후 사용자 검토** 프로세스 — inter-annotator agreement는 단일 annotator 기반
- **"새 class == 0" 기준** — edge-case URL은 실제로 새 class여도 instance 1이면 확인 어려움

### Solution 2 연결
- **Action catalog 미구축** — class 간 navigation edge 없이는 Solution 2 불가. Stage B에서 수행.

---

## Artifacts (final inventory)

### Protocol docs
- `docs/validation/V1_protocol_spec.md` — Class taxonomy v0.6
- `docs/validation/class_discovery_protocol.md` — CDIP v0.2
- `docs/validation/V1_deferred_issues.md` — D1-D4 기술 부채

### Execution reports
- `docs/validation/stage_a_rules_report.md` — Rule extraction
- `docs/validation/stage_a_f_fresh_crawl_report.md` — Step 1 crawl
- `docs/validation/stage_a_f_step2_report.md` — Step 2' frontier
- `docs/validation/stage_a_verify_report.md` — Action set 실측
- `docs/validation/V1_annotation_filled.md` — 190 annotation + class tree

### Data
- `output/validation/rules/class_rules.json` — 141 rules
- `output/validation/V1_pages/all_annotated.json` — 190 annotations (per page)
- `output/validation/V1_pages/all_llm_annotated.json` — LLM raw outputs
- `output/validation/V1_pages/pages/*.json` — per-page AXTree (~150)
- `output/validation/stage_a_f/classified.json` — Step 1 pool 1457
- `output/validation/stage_a_f/step/step_2_new.json` — Step 2' 238
- `output/validation/stage_a_f_final/crawled_urls.json` — (deprecated, superseded by step_2)

### Scripts (`scripts/validation/`)
- `v0_1_axtree_sanity.py`, `v0_1_refresh_auth.py`, `v0_2_kg_inspect.py`
- `v1_a_collect_axtrees.py`, `v1_a_recollect.py`, `v1_b_llm_annotate.py`, `v1_c_fill_annotations.py`
- `stage_a_verify.py`, `stage_a_extract_rules.py`, `stage_a_classify.py`
- `stage_a_f_crawl.py`, `stage_a_f_apply.py`, `stage_a_f_cluster.py`, `stage_a_f_collect_samples.py`, `stage_a_f_step.py`, `stage_a_f_final_check.py`

---

## Handoff to Stage B

### Stage B goal (research_roadmap.md 기반)
각 class의 **action catalog** 수집 — navigation-inducing action (class_A에서 실행하면 class_B로 이동) + 주요 action description.

### Stage B input (from Stage A)
- 141 rules (class → URL template 매칭)
- 138 leaf classes + 7 scopes
- 190 annotations with AXTree samples
- Site_config, storage_state

### Stage B scope
1. For each class, collect sample URLs (1-3 per class).
2. For each sample, extract actionable elements (a href, buttons).
3. Filter to navigation-inducing (href 존재 + 다른 class로 이동).
4. Aggregate as `{class: [{action_label, action_type, href, target_class_candidate}]}`.
5. Construct action catalog JSON.

### 잠재 이슈
- Non-navigating action (form submit, modal open) 처리 범위
- Dynamic JS 기반 action (href="#") 제외 기준
- Cross-scope link (project → global) 범주화
- Action catalog size 예상: 138 class × 평균 ~20 action ≈ 2000-3000 entry

### Stage B 출구 조건 (예상)
- 138 class 각각의 top-N action 목록 완성
- Action → target class 매핑 정확도 ≥ X% (pre-commit TBD)
- 문서: `docs/validation/stage_b_action_catalog_report.md`
