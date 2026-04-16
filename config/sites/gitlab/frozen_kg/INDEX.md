# Frozen KG snapshots — site=gitlab

- `2026-04-16T05-34-29Z` git=13cbfb9 mix={'crawl': 2901, 'llm': 211, 'manual': 0} note='M5 baseline 측정 전 freeze; 3-stage automated-only (crawl+llm); ARI=1.0 across 3 runs'
- `2026-04-16T13-21-01Z` git=c85b326 mix={'crawl': 2901, 'llm': 211, 'manual': 0} note='Iter1 post-enrichment 적용 (D1 binding_map, D2 path_params, D3 query_params, D6 category)'
- `2026-04-16T13-35-46Z` git=c85b326 mix={'crawl': 12338, 'llm': 465, 'manual': 0} note='Iter2 post-enrichment 적용 (D7 form self-loop edges + edge-based query param backfill + action description 자동화)'
- `2026-04-16T13-47-16Z` git=c85b326 mix={'crawl': 12338, 'llm': 465, 'manual': 0} note='Iter3 form edge target 정확화 (action_url → target state) + query param이 올바른 state에 박힘'
- `2026-04-16T13-54-06Z` git=c85b326 mix={'crawl': 12338, 'llm': 465, 'manual': 0} note='Iter4 site-separator(`/-/`) hardcode 제거 + literal tail suffix 일반화'
