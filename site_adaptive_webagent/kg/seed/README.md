# kg/seed/ — Site KG Collector

Playwright 기반 사이트 크롤링 + LLM 파생 + immutable snapshot 생성 파이프라인.

## 산출

```
config/sites/<site>/frozen_kg/<ISO_timestamp>.json
config/sites/<site>/frozen_kg/<ISO_timestamp>.meta.json
```

## 4-step pipeline

```bash
# 1. Playwright BFS crawl → verified layer StatePattern/Action/LeadsTo
python -m site_adaptive_webagent.kg.seed.run_crawl \
    --site gitlab \
    --config config/webarena_verified.json \
    --storage-state output/<task>/.storage_state.json \
    --max-depth 2 \
    --output output/crawl/$(date +%Y%m%d_%H%M%S)/

# 2. LLM derivation → inferred layer (group/classify/rename, 3-call decomposition)
OPENAI_MODEL=<snapshot_id> LLM_TEMPERATURE=0 \
python -m site_adaptive_webagent.kg.seed.run_derivation \
    --site gitlab \
    --crawl-dir output/crawl/<ts>/ \
    --output output/derivation/$(date +%Y%m%d_%H%M%S)/

# 3. (선택) Manual seed와 crawl/derivation 사이 diff review
python -m site_adaptive_webagent.kg.seed.run_review_diff \
    --site gitlab \
    --derivation-dir output/derivation/<ts>/

# 4. Immutable freeze (seed + crawl + derivation + post_enrich 통합)
python -m site_adaptive_webagent.kg.seed.run_freeze \
    --site gitlab \
    --crawl-dir output/crawl/<ts>/ \
    --derivation-dir output/derivation/<ts>/ \
    --note "<설명>"
```

## 환경 변수

| Var | 필수 | 용도 |
|---|---|---|
| `OPENAI_MODEL` | derivation | 사용 모델 snapshot ID |
| `OPENAI_API_KEY` | derivation | OpenAI API |
| `LLM_TEMPERATURE` | derivation | `0` 권장 (비결정성 최소화) |

## 모듈 구성

| 파일 | 역할 |
|---|---|
| `run_crawl.py` / `run_derivation.py` / `run_freeze.py` / `run_review_diff.py` | CLI entrypoints |
| `playwright_crawler.py` | BFS crawler (signature dedupe + GET form input → query URL 큐) |
| `crawl_to_kg.py` | crawl 결과 → SiteKG (form action_url cross-page edge) |
| `llm_derivation.py` | 3-call decomposition (group → classify → rename) |
| `derivation_to_kg.py` | derivation 결과 → SiteKG |
| `post_enrich.py` | LLM 재호출 없는 heuristic 보강 (path_params, query_params, binding_map, category) |
| `review_diff.py` | manual seed vs crawl/derivation diff helper |
| `seed_loader.py` | 3 source (manual + crawl + llm) 통합 |
| `manual_config.py` / `infotype_catalog.py` | YAML 로더 |

## 제약

- **Crawler coverage**: `max-depth` + 로그인 계정 권한 범위. admin 영역이나 private 일부는 누락 가능
- **LLM 비결정성**: `temperature=0`도 완전한 deterministic은 아님 (Atil et al. 2024). ARI 측정은 별도 수행
- **Filter URL 관찰 부재**: crawler가 방문 안 한 filter URL(`?state=opened` 등)은 `identity_query_params`가 비어있을 수 있음 — post_enrich에서 부분 보강

## 참고

전략 변경·재설계 맥락은 `docs/lessons_learned_kg_v2.md` §3 (schema + 3-stage pipeline), §7.4 (데이터 원칙) 참조.
