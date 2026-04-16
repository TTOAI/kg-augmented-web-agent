# Manual Review Notes — site=gitlab

## Design Decision: No Per-Task Manual Labeling

**본 evaluation에서 manual stage는 0건. 정확한 표현: "no per-task manual labeling, with
generic web/domain prior in pipeline code".** "Automated-only" 표현은 부정확해 폐기됨
(2026-04-17 — `07 §14` update 참조).

관련 docs: `docs/kg_design/07 §14` (KG 구축 방법론), `docs/kg_design/02 §3-7` (trust layer).

### 정확한 표현 (2026-04-17 update)

본 pipeline은 **2-stage automated (Playwright crawl + multi-call LLM derivation) +
heuristic post-enrichment**. Manual stage(Stage 3)는 architecture에 포함되나 본 evaluation
에서는 수행하지 않음. Pipeline에는 다음 generic web/domain prior가 박혀 있음 (정직 disclose):

- post_enrich 6개 helper의 heuristic 규칙 (URL slot naming convention, `*_path` →
  `path_segments` 등)
- LLM prompt에 "list/index page는 filter/sort/pagination 받는다" 같은 일반 web app convention
- crawler의 download extension blocklist (.zip, .tar, .ics 등 — 일반 web 표준)

이들은 **사이트 어휘를 박지 않으므로** task-bias 없음 (`memory: feedback_no_task_site_bias`).
자세한 prior 표는 `docs/kg_design/07 §14`의 "Domain prior disclosure" 표 참조.

### 이유 (Reviewer-proof 논거)

1. **재현성(Reproducibility) 우선**. 사람이 per-task labeling으로 개입한 catalog는 후속
   연구자가 pipeline을 재생산할 수 없다. 본 연구는 "no per-task manual labeling"으로 이
   재현성을 보장하되, generic web prior는 정직 disclose.
2. **Hindsight bias 원천 차단**. catalog freeze가 baseline 측정 *전*에 이뤄지며, post-hoc
   조정은 git history로 추적 가능. reviewer "결과 보고 고쳤냐" 공격 차단.
3. **Scalability 부분 주장**. 다른 사이트에 같은 pipeline 적용 가능 (Stage 1+2 코드 변경
   불필요). 단 site_config.yaml의 alias·identity_token 같은 설정은 사이트별 1회 작성 필요.
4. **자동 hallucination filter 이미 존재**. crawler가 관찰한 URL 위에서만 LLM이 grouping하며
   `member_ids`는 crawl id로 검증(`kg/seed/llm_derivation.py`).

### Pipeline 재현 지침

1. `python -m site_adaptive_webagent.kg.seed.run_crawl` — Playwright crawler (verified StatePattern)
2. `OPENAI_MODEL=<snapshot id> LLM_TEMPERATURE=0 python -m site_adaptive_webagent.kg.seed.run_derivation` — LLM grouping + InfoType + Action rename (inferred)
3. `python -m site_adaptive_webagent.kg.seed.run_freeze` — immutable snapshot
4. `SITEKG_FROZEN=<snapshot path> python3 run_webarena_verified.py …` — M5 본 실험

각 단계의 산출물은 `output/crawl/<ts>/`, `output/derivation/<ts>/`, `config/sites/<site>/frozen_kg/<ts>.json`에 timestamp별로 보관된다.

### Trust 매핑 (PROV-O 기반)

| 내부 trust | PROV-O 매핑 | 의미 |
|---|---|---|
| `verified` | `prov:wasDerivedFrom` (crawl 관찰) | Playwright 실측 |
| `declared` | `prov:wasAttributedTo` (사람·문서) | 수동 기재 |
| `inferred` | `prov:wasGeneratedBy` (LLM agent) | LLM 추정 |

본 연구 catalog는 `declared` + `manual` 항목이 0이며, `verified` + `inferred` 조합만으로
구성된다. 이는 **per-task manual labeling이 0건**이라는 의미이지, pipeline에 generic web/
domain prior가 0이라는 의미는 아님 (위 "정확한 표현" 참조).

### Freeze 이력

| timestamp (ISO UTC) | git_rev | source_mix | 노트 |
|---|---|---|---|
| (첫 freeze 후 채워짐) | (run_freeze.py가 자동 기록) | (자동) | (CLI `--note`로 기록) |

`config/sites/gitlab/frozen_kg/INDEX.md`가 자동 갱신됨.

### Limitations 선언

- **Crawler 커버리지**: `byteblaze` 계정 권한 범위 + `max_depth=2` 한계. Admin 영역, 일부 private area는 catalog에 없음. 이는 본 연구 Limitation 섹션에 명시.
- **LLM derivation 1회 호출의 비결정성**: `temperature=0`은 deterministic을 완전히 보장하지 않는다(Atil et al. 2024, Thinking Machines 2025). 안정성 측정은 별도 ARI(Adjusted Rand Index) 실험으로 보고.
- **Model snapshot**: 정확한 모델 ID(예: `gpt-5.4-YYYY-MM-DD`)가 `.env`와 git commit에 고정. Tier migration 시 재현 보장.
- **Filter-URL 관찰 부재**: crawler가 `?state=opened`, `?label_name[]=...` 같은 필터 URL을 직접 방문하지 않은 StatePattern은 `identity_query_params`가 비어 있을 수 있다. 해당 URL을 관찰하는 사이트 지식(예: GitLab issues는 state 필터를 받는다)을 pipeline에 박지 않기로 한 것은 **편향 금지 원칙** 때문이다. Hook B URL emit 시 해당 bindings는 fallback name-match 경로로만 reflect되며, 이 한계는 "automated construction 자체의 비용/커버리지 tradeoff"로 보고한다.

### Post-derivation enrichment (자동 보강)

Freeze 전 단계에 `site_adaptive_webagent/kg/seed/post_enrich.py`가 LLM 재호출 없이 적용된다. 각 helper는 특정 결함(0-entries / fallback-only schema)을 name·regex 기반 heuristic으로 채운다. 사이트·task 어휘 하드코딩 없음.

| Helper | 대상 결함 | 규칙 |
|---|---|---|
| `auto_fill_path_params` | StatePattern.path_params 공백 | url_template의 `{slot}` 추출, `*_path` → `path_segments`, 그 외 → `segment` |
| `backfill_query_params_from_form_actions` | StatePattern.identity_query_params 공백 | `crawl:form:*` edge의 `to_state_pattern_id`에 form input name을 query param으로 추가 + semantic_template suffix 일치하는 llm SP에 전파 |
| `auto_fill_query_params` | 동일 | InfoType.optional_bindings → 대응 StatePattern.identity_query_params (이미 path/query에 없는 경우) |
| `backfill_optional_bindings` | InfoType.optional_bindings 공백 | realize target StatePattern.identity_query_params 이름 역투영 |
| `auto_fill_binding_map` | RealizesEdge.binding_map 공백 | bindings를 target SP의 path slot·query param 이름과 name-match (exact / `[]` variant) |
| `assign_infotype_category` | InfoType.category 부재 | 이름 prefix 기반 group (≥2 공유) → explicit category, 그 외 → `misc` |
| `prune_unused_form_actions` | 사용되지 않는 form action catalog 잔존 | LeadsToEdge에 참조 안 되는 `crawl:form:*` 제거 |
| `auto_fill_action_descriptions` | Action.description 공백 | 이름 기반 자동 설명 |

또한 `crawl_to_kg`가 form input마다 LeadsToEdge를 만들 때 `form.action_url` path가 다른 crawled page와 일치하면 **cross-page edge**를 만들고, 실패 시 self-loop fallback한다. 이렇게 해야 글로벌 search bar 같은 cross-target form이 올바른 target state에 query param을 남긴다.

### 수동 편집 금지 선언

Freeze 이후 이 catalog(`config/sites/gitlab/frozen_kg/<ts>.json`)는 **immutable**이다. 수정이 필요하면 새 timestamp로 재freeze하고 INDEX에 추가. 기존 snapshot은 보존.

본 연구 M5 측정은 `SITEKG_FROZEN` env var로 단일 snapshot만 로드하므로, 이후 변경은 해당 측정에 영향을 주지 않는다.
