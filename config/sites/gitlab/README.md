# Site Config — gitlab

GitLab KG의 seed 데이터. `docs/kg_design/02_open_questions.md` §3 결정과 `07 §14` 구축 방법론의 구체 구현.

## 구축 파이프라인 (3단계 hybrid)

이 디렉토리는 **3단계 hybrid pipeline** 중 `source=manual` layer를 담는다 (`docs/kg_design/07 §14`).

| 단계 | source | trust | 산출물 |
|---|---|---|---|
| 1. Playwright auto-crawl | `crawl` | `verified` | url_template·path/query param·관찰된 leads_to |
| 2. LLM-assisted derivation | `llm` | `inferred` | InfoType 후보·realizes 매핑·일반화 |
| 3. Manual verification (여기) | `manual` | `declared` | decorative/alias/token·default·검증된 catalog |

M4 단계에서 1·2 layer가 이 디렉토리의 seed와 병합돼 포괄 catalog(~20~30 InfoType, ~30~50 StatePattern)로 확장된다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `site_config.yaml` | 사이트 공통 URL 정규화 규칙 (manual 전용) |
| `infotypes.yaml` | InfoType 카탈로그 seed + realizes 매핑 |
| `kg_seed.json` | 초기 KG seed (StatePattern + leads_to 엣지) |

모든 노드·엣지에 `source` 필드가 붙어 어느 layer의 기여인지 식별된다.

## 로딩 순서

```python
from kg_augmented_webagent.kg.seed import load_site_kg_from_dir

site_config, kg = load_site_kg_from_dir("config/sites/gitlab")
# kg.build_timestamp, kg.builder_version, kg.source_mix 가 자동 세팅됨
```

1. `site_config.yaml` 로드 → 정규화 규칙 설정
2. `infotypes.yaml` 로드 → InfoType 카탈로그 + realizes 엣지
3. `kg_seed.json` 로드 → StatePattern 노드 + leads_to 엣지 + trust 초기값
4. Build metadata 자동 기록: `build_timestamp`, `builder_version`, `source_mix`

## Source → Trust 기본 매핑

- `source="crawl"`  → `trust="verified"` (Playwright 관찰)
- `source="manual"` → `trust="declared"` (사람 검증)
- `source="llm"`    → `trust="inferred"` (LLM 일반화)

## Merge 정책

crawl 결과를 seed에 병합할 때는 `SiteKGStore.merge(other_kg)` 사용. 동일 key에서 source 우선순위(crawl > manual > llm)로 교체되고, 나머지는 기존 값 유지. 구현: `kg_augmented_webagent/kg/store.py`.

## 업데이트 정책

- `site_config.yaml`, `infotypes.yaml`은 사람이 수동 편집 후 커밋.
- `kg_seed.json`은 crawl 산출물 + 수동 검증 결과의 병합. 재생성 가능.
- 런타임 trust 업데이트(쟁점 #3 §3-7)는 `output/<run_id>/trust_snapshot.json`에 기록하며 이 디렉토리를 덮어쓰지 않는다.
