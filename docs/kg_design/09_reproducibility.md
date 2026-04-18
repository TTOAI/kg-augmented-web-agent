# 09. Reproducibility

## 이 문서의 목적

본 연구의 측정 결과를 제3자가 재현할 수 있도록 구축·실행·분석 전 과정의 artifact,
버전, 시드, 명령을 한 곳에 모은다. Reviewer 재현성 방어용 체크리스트.

---

## 1. Code & Environment

### 1-1. Repository
- Branch: `feature/kg-v2`
- Git rev (measurement start): `bd00bd8` (2026-04-17 기준 HEAD)
- Working dir: `site-adaptive-webagent/`

### 1-2. Python & Dependencies
- Python: 3.11 (`.venv/` via `pyenv` or system)
- Install: `pip install -e .` (editable mode)
- Playwright: `pip install playwright; playwright install chromium`
- Key dependencies: `openai`, `playwright`, `pydantic`, `python-dotenv`

### 1-3. LLM Models
| 용도 | Model ID | API | 특수 파라미터 |
|---|---|---|---|
| Agent task execution | `gpt-5.4-mini` | `chat.completions` (multi-turn tool_calls) | `LLM_TEMPERATURE=0` |
| KG derivation (3-call) | `gpt-5.4` | `responses` (Responses API) | `reasoning_effort="low"` |

- `.env` 파일에 `OPENAI_API_KEY` 설정. `OPENAI_MODEL` 생략 시 default (mini).
- `LLM_TEMPERATURE=0` env var로 고정 (필수).

### 1-3-bis. Critical environment variables (본 측정 필수)

| env var | 값 | 용도 |
|---|---|---|
| `OPENAI_MODEL` | `gpt-5.4-mini` | Agent 모델 (nano/full은 측정 무효) |
| `LLM_TEMPERATURE` | `0` | 재현성 |
| `SITEKG_ENABLED` | `1` | **kg_full variant에서 필수** (미설정 시 Hook A/B/C 전부 비활성 → baseline 경로로 silent fallback) |
| `KG_VARIANT` | `off` / `full` | variant dispatch |
| `SITEKG_FROZEN` | `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json` | Frozen KG path |
| `LLM_CALL_LIMIT_PER_TASK` | `450` (default) | Phase 2 개선 |

**CRITICAL**: Phase C 첫 측정(2026-04-17)은 `SITEKG_ENABLED=1` 누락으로 kg_full variant가
baseline처럼 실행되어 무효. 자세한 내용은 `10_phase_c_postmortem.md` 참조.

### 1-6. Phase 2 개선 적용 상태

본 reproducibility document는 Phase 2/2B 완료 (2026-04-18 이후) 기준. Baseline 안정성·
KG 정확성·분석 파이프라인 15건 improvement 적용. 자세한 list는 `07 §5-1` Phase 2 개선사항 표 참조.

### 1-4. Docker (WebArena-Verified GitLab)
- Image: `webarena/gitlab-v1.15-verified`
- Container name: `webarena_verified_gitlab`
- Port: 8023
- 기동: `webarena-verified env start --site gitlab`
- 정지: `webarena-verified env stop --site gitlab`

### 1-5. OS·Hardware
- Platform: macOS (Darwin 25.2.0), Linux 지원 (CI 외 실험은 macOS 기준)
- Browser: Playwright Chromium (headed/headless 동일 결과 기대)

---

## 2. Random Seeds

| 대상 | Seed | 파일 |
|---|---|---|
| Task sampling (per-type 10 × 3 = 30) | `42` | `scripts/sample_tasks_per_type.py` |
| LLM decoding | N/A (`temperature=0`) | — |
| Crawler URL discovery order | deterministic (BFS + seed URL 고정) | `kg/seed/playwright_crawler.py` |
| LLM derivation | N/A (`reasoning_effort=low`, Responses API) — single-shot per call | `kg/seed/llm_derivation.py` |

**Note**: LLM은 `temperature=0`에서도 완전 결정적이지 않음 (provider 내부 병렬성,
floating-point). 본 연구는 N=3 반복으로 run-to-run variance를 직접 측정.

---

## 3. Artifacts (Immutable)

### 3-1. Frozen KG
- Path: `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json`
- Meta: `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.meta.json`
- Build timestamp: `2026-04-16T16:46:55Z`
- Git rev at build: `534c49d`
- Source mix: `crawl=33150, llm=593, manual=0`
- Builder version: `0.1.0-hybrid`
- Crawl dir: `output/crawl/20260416_231931_v4`
- Derivation dir: `output/derivation/20260417_011348_v9_run1`
- ARI (3 derivation runs, group-level): **0.9264**

### 3-2. Task sample
- File: `output/tasks.30.json` (30 task definitions)
- Types: `output/tasks.30.task_types.txt` (task_id ↔ NAVIGATE/RETRIEVE/MUTATE)
- Generation: `python scripts/sample_tasks_per_type.py --seed 42 --per-type 10`
- Source pool: WebArena-Verified GitLab 180 task (공식 vendor 데이터셋)

### 3-3. Broken evaluator exclusions
- `docs/kg_design/eval_exclusions.md` — strict-match evaluator 결함으로 정상 행동이
  fail 기록되는 task 목록 + 사유 (HAR snippet 또는 log reference).

---

## 4. Measurement Recipe

### 4-1. Pre-measurement checks
```bash
# 1. Tests pass
.venv/bin/python -m unittest discover -t . -s tests/

# 2. Env reachable
webarena-verified env start --site gitlab
curl -sI http://localhost:8023/ | head -1   # HTTP/1.1 200 or 302

# 3. Frozen KG accessible
ls -la config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json
```

### 4-2. Run 180-run measurement
```bash
bash run_phase_c_180.sh  # ~11h overnight
# Background monitor (optional):
nohup python3 scripts/monitor_phase_c.py \
    --run-root output/phase_c_180 \
    --total-runs 180 \
    --check-interval 30 \
    > output/phase_c_180/monitor_console.log 2>&1 &
```

본 runner가 내부적으로:
- 30 task × N=3 × 2 variants = 180 runs
- Per task `TIMEOUT=750s` via `run_with_timeout.py`
- MUTATE task 후 env stop/start (state reset)
- Round boundary (baseline N=k 종료 후, kg_full N=k 종료 후) env reset
- `LLM_TEMPERATURE=0`, `KG_VARIANT=off|full`, `SITEKG_FROZEN=frozen_kg/2026-04-16T16-46-55Z.json`

### 4-3. Post-measurement analysis
```bash
bash scripts/run_analysis.sh output/phase_c_180
# 순차 수행:
# [1/5] analyze_baseline.py × 2 variants
# [2/5] paired_stats.py (overall + per-type McNemar/Wilcoxon)
# [3/5] coverage.py (Hook A per-type coverage)
# [4/5] failure_mode.py template (수동 라벨링 대상 CSV 생성)
# [5/5] make_paper_tables.py (Table 1 placeholder → 수치 치환)
```

### 4-4. Failure labeling (manual, 2-rater)
`failure_template.csv`를 rater 1, rater 2가 독립적으로 P/R/G/A/O 라벨링
(Perception / Reasoning / Grounding / Action / Other) → rater1.csv, rater2.csv →

```bash
python scripts/failure_mode.py kappa \
    --rate1 output/phase_c_180/failure_rater1.csv \
    --rate2 output/phase_c_180/failure_rater2.csv \
    --output output/phase_c_180/failure_kappa.md
```

Cohen's κ ≥ 0.60이면 결과 라벨은 rater 합의로 최종화, < 0.60이면 3rd rater 도입.

---

## 5. Reproducibility from Scratch (build KG + run agent)

Frozen KG 없이 0에서 재현하려면:

```bash
# 1. Crawl (~30 min, 0 LLM calls)
.venv/bin/python -m site_adaptive_webagent.kg.seed.run_crawl \
    --site gitlab \
    --base-url http://localhost:8023 \
    --seed-urls <사이트 공식 navigation entry 8개> \
    --output output/crawl/<timestamp>

# 2. LLM derivation (3-call, ~5 min + ~$0.5)
.venv/bin/python -m site_adaptive_webagent.kg.seed.run_derivation \
    --crawl-dir output/crawl/<timestamp> \
    --output output/derivation/<timestamp>

# 3. Freeze (post_enrich + immutable snapshot)
.venv/bin/python -m site_adaptive_webagent.kg.seed.run_freeze \
    --crawl-dir output/crawl/<timestamp> \
    --derivation-dir output/derivation/<timestamp> \
    --output config/sites/gitlab/frozen_kg/<ts>.json
```

Each stage outputs its artifact + `.meta.json` with git rev + source mix.

**ARI check**: 3 independent derivation runs → `scripts/measure_ari.py` → ≥ 0.85 달성
시에만 frozen 채택 (본 연구: 0.9264).

---

## 6. 재현 시 예상되는 변동 요인

### 6-1. 결정적 (변동 없음)
- Task sample (seed=42 고정)
- Frozen KG (immutable artifact)
- Hook A/B/C 로직 (pure function)

### 6-2. 준결정적 (minor variance 가능)
- LLM decoding (`temperature=0`에도 provider 내부 병렬성)
- Playwright DOM observation (non-deterministic async rendering order)

### 6-3. 비결정적 (환경 의존)
- Docker container state (MUTATE 누적 side effect는 env reset으로 격리)
- Network latency (Docker 내부 API 응답 속도)
- LLM provider side (model 업데이트 시 결과 drift 가능)

**완화**: N=3 반복 + majority vote binarization으로 minor variance 흡수 (`06 §4-5`).

---

## 7. 파일 · 경로 레퍼런스

| 항목 | Path |
|---|---|
| Main runner | `run_phase_c_180.sh` |
| Monitor | `scripts/monitor_phase_c.py` |
| Analysis orchestrator | `scripts/run_analysis.sh` |
| Individual analysis | `scripts/{analyze_baseline,paired_stats,coverage,failure_mode,make_paper_tables}.py` |
| Frozen KG | `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json` |
| Task sample | `output/tasks.30.json`, `output/tasks.30.task_types.txt` |
| Paper draft | `docs/paper/draft.md` |
| Table template | `docs/paper/table1_template.md` |
| Final table (after run_analysis) | `docs/paper/table1_filled.md` |

---

## 8. Contact / Issue tracking

Reproducibility 문의는 GitHub issue (`anthropics/claude-code` 아님 — 본 연구의
privately-hosted repo). Dataset 관련은 WebArena-Verified 공식 저장소 참조.
