# Manual Review Notes — site=gitlab

## Design Decision: Automated-Only KG Construction

**사람의 수동 검증 단계는 본 연구 설계에서 의도적으로 생략되었다 (no human review by design).**

관련 docs: `docs/kg_design/07 §14` (KG 구축 방법론), `docs/kg_design/02 §3-7` (trust layer).

### 이유 (Reviewer-proof 논거)

1. **재현성(Reproducibility) 우선**. 사람이 개입한 catalog는 artifact이지 instrument이 아니다. 후속 연구자가 pipeline을 그대로 재생산할 수 없다. 본 연구의 기여는 "automated construction pipeline"이므로 사람 검증을 배제한다.
2. **Hindsight bias 원천 차단**. 사람이 baseline 측정 후 catalog를 조정할 경우 reviewer가 "결과 보고 고쳤냐"를 반박할 수 있다. 완전 자동 pipeline은 이 공격면을 없앤다.
3. **Scalability 주장**. 다른 사이트에 같은 pipeline을 그대로 돌리면 된다. 사람 손이 필요하면 이 주장이 약화된다.
4. **자동 hallucination filter 이미 존재**. crawler가 관찰한 URL 위에서만 LLM이 grouping하며 `member_ids`는 crawl id로 검증(`kg/seed/llm_derivation.py`). 즉 "LLM이 존재하지 않는 페이지를 만들어냄" risk는 이미 차단.

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

본 연구 catalog는 `declared` 항목이 0이며, `verified` + `inferred` 조합만으로 구성된다 — 완전 자동화의 직접 증거.

### Freeze 이력

| timestamp (ISO UTC) | git_rev | source_mix | 노트 |
|---|---|---|---|
| (첫 freeze 후 채워짐) | (run_freeze.py가 자동 기록) | (자동) | (CLI `--note`로 기록) |

`config/sites/gitlab/frozen_kg/INDEX.md`가 자동 갱신됨.

### Limitations 선언

- **Crawler 커버리지**: `byteblaze` 계정 권한 범위 + `max_depth=2` 한계. Admin 영역, 일부 private area는 catalog에 없음. 이는 본 연구 Limitation 섹션에 명시.
- **LLM derivation 1회 호출의 비결정성**: `temperature=0`은 deterministic을 완전히 보장하지 않는다(Atil et al. 2024, Thinking Machines 2025). 안정성 측정은 별도 ARI(Adjusted Rand Index) 실험으로 보고.
- **Model snapshot**: 정확한 모델 ID(예: `gpt-5.4-YYYY-MM-DD`)가 `.env`와 git commit에 고정. Tier migration 시 재현 보장.

### 수동 편집 금지 선언

Freeze 이후 이 catalog(`config/sites/gitlab/frozen_kg/<ts>.json`)는 **immutable**이다. 수정이 필요하면 새 timestamp로 재freeze하고 INDEX에 추가. 기존 snapshot은 보존.

본 연구 M5 측정은 `SITEKG_FROZEN` env var로 단일 snapshot만 로드하므로, 이후 변경은 해당 측정에 영향을 주지 않는다.
