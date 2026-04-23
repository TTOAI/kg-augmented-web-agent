# V0.1 — AXTree Collection Pipeline Sanity

**Date**: 2026-04-19
**Status**: **PASS** (pipeline reproducibility 100%, auth refreshed)

## Question

Playwright로 GitLab 페이지의 AXTree-like structure를 일관되게 얻을 수 있나?

## Method

- Test pages (5): `/dashboard`, `/dashboard/projects`, `/dashboard/issues`, `/explore/projects`, `/byteblaze`
- DOM structure extraction via `page.evaluate()` (Playwright async_api의 `page.accessibility` 미지원)
  - Walk DOM tree, extract role + label + children
  - Skip non-interactive empty nodes
- Storage state: `output/phase_c_180_contaminated/baseline_N3/102/.storage_state.json`
- 2회 independent run으로 consistency 측정 (difflib ratio)

## Data

- Pages visited (each run): 5
- JSON output size: 10KB (login page) / 193KB (public pages) / 192KB (profile)
- Saved to: `output/validation/V0_1_axtree_samples/{run1,run2}/*.json`

## Result

### Pipeline consistency
- **5/5 pages** reached 1.0000 similarity (threshold 0.98 pass)
- Pipeline reproducibility: **perfect**

### Auth refresh 후 최종 결과
Fresh auth (`ui_login` 재활용, `scripts/validation/v0_1_refresh_auth.py`) 후 재측정:

| Page | Title | Status |
|---|---|---|
| `/dashboard` | Projects · Dashboard · GitLab | ✓ authenticated |
| `/dashboard/projects` | Projects · Dashboard · GitLab | ✓ authenticated |
| `/dashboard/issues` | Issues · Dashboard · GitLab | ✓ authenticated |
| `/explore/projects` | Projects · Explore · GitLab | ✓ public |
| `/byteblaze` | Byte Blaze · GitLab | ✓ public profile |

- AXTree line counts: 382-743 (의미 있는 내용)
- JSON size: 125-230KB (real pages)

## Success / Failure

### Pipeline sanity
- **PASS** — 동일 URL 2회 방문 시 AXTree 100% 일치 (5/5 pages, similarity 1.0000). Pipeline 자체는 validation chain의 나머지에 안전하게 사용 가능.

### Auth state
- **PASS** — `ui_login` 재활용으로 fresh auth 발급, `output/validation/.storage_state.json` 저장. 5/5 authenticated pages 정상 접근.

## Implications

1. **Pipeline 재현성 확인** — AXTree 수집 자체는 deterministic. 이후 V1-V22에서 pipeline 결과를 신뢰 가능
2. **Storage state 재생성 필요** — V0.2 진행 전 fresh login flow 실행
3. **JS-based extraction 확정** — Playwright 현 버전에서 `page.accessibility` 미지원, `page.evaluate()` JS walk로 대체. 모든 후속 validation에 동일 접근 사용
4. **Extract 포맷 확정**:
   - Interactive tags (a, button, input, form, nav, main, h1-h6 등)만 포함
   - Max depth 20
   - Label: aria-label > alt > title > innerText > href (이 순서)

## Next step

- **V0.1-b**: Storage state refresh (WebArena-Verified의 auth helper 재활용)
- **V0.2**: Frozen KG 구조 파악
- **V1**: 수동 annotation (auth 복원 후)

## Artifacts

- Script: `scripts/validation/v0_1_axtree_sanity.py`
- Data: `output/validation/V0_1_axtree_samples/run1/`, `run2/`
- Diff report: `output/validation/V0_1_axtree_samples/diff_report.md`
