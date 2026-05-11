# Site-Adaptive Web Agent

사이트별 지식 그래프(site-specific KG)를 planning substrate로 사용하는 KG-augmented web agent. KG는 대상 사이트 자체로부터 site-agnostic discovery protocol을 통해 빌드된다.

## Overview

웹 에이전트는 매 step마다 "어디로 갈지", "어떤 filter가 있는지", "URL을 어떻게 만들지"를 결정해야 한다. 이 프로젝트는 LLM 일반 추론에만 맡기지 않고, 사이트의 구조 정보를 KG로 정리해 runtime hint로 주입하는 접근을 구현·실험한다.

핵심 구성 요소:

- **Agent loop** (ReAct + tool-use): `analyze_intent()` → `build_plan()` → sub-goal loop with tool-use LLM → `_verify_done()`. 구현은 `site_adaptive_webagent/agent/`, `site_adaptive_webagent/runtime/`.
- **KG runtime**: sub-goal target page class를 LLM self-consistency로 추론 → BFS 6-stage cascade로 path 산출 → advisory hint를 LLM에 전달. 구현은 `site_adaptive_webagent/kg/runtime/`.
- **KG seed builder** (Stage A/B/C): URL 분류 규칙 → action catalog + filter category → class-to-class edge graph. 구현은 `site_adaptive_webagent/kg/seed/`, `scripts/kg/`.
- **Benchmark adapter**: WebArena-Verified GitLab 사이트에 대한 Playwright 기반 측정 어댑터. 구현은 `site_adaptive_webagent/benchmarks/webarena_verified/`.

## KG 설계 원칙: 구조는 KG, 구체값은 에이전트

KG는 사이트의 **구조 정보**(어떤 페이지·경로·필터 카테고리·컨트롤이 존재하는지)까지만 노출하고, **구체값**(필터 라벨 값·URL 쿼리 파라미터 값·자유 텍스트 콘텐츠)은 LLM 에이전트가 페이지를 직접 보고 수집한다.

이 분리에는 두 가지 근거가 있다.

1. **데이터 노후화 회피**: KG가 구체값을 박으면 사이트 UI가 바뀔 때마다 KG를 갱신해야 한다.
2. **LLM의 직접 관측이 더 안전**: LLM이 자신의 판단에 따라 구체값을 실시간으로 직접 수집하여 행동하는 것이, KG로 수동적으로 주입받는 것보다 워크플로우에 더 합리적이며 정보의 안전성과 신뢰성이 더 높다.

## Requirements

```bash
uv pip install -e .
uv pip install playwright
playwright install chromium
```

## LLM 설정

```bash
cp .env.example .env
```

`.env` 예시:

```bash
LLM_PROVIDER=openai          # 또는 anthropic
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_MODEL=gpt-4o
# ANTHROPIC_MODEL=claude-sonnet-4-6
# LLM_TEMPERATURE=0          # 결정론적 실행 원하면 0
```

API 키가 없으면 LLM 없이 규칙 기반으로 폴백된다.

## Usage

### 환경 준비

```bash
cp config/webarena_verified.example.json config/webarena_verified.json
# config 안의 URL/포트/계정을 로컬 환경에 맞게 수정

webarena-verified env start --site gitlab --port 8023 --env-ctrl-port 8024
```

### Task 입력 export

```bash
webarena-verified agent-input-get \
  --task-ids 44 \
  --config config/webarena_verified.json \
  --output output/tasks.demo.json
```

### Agent 실행

```bash
.venv/bin/python run_webarena_verified.py \
  --tasks-file output/tasks.demo.json \
  --task-id 44 \
  --config config/webarena_verified.json \
  --run-root output \
  --headed
```

옵션:
- `--headed` — 브라우저를 띄워서 행동 관찰
- `--run-root` — task별 산출물 저장 위치

### 평가

```bash
webarena-verified eval-tasks \
  --task-ids 44 \
  --output-dir output \
  --config config/webarena_verified.json
```

### 환경 리셋 (MUTATE task 후)

MUTATE task는 사이트 상태를 변경하므로 재실험 전 초기 상태로 리셋해야 정확한 측정이 된다.

```bash
webarena-verified env stop --site gitlab
webarena-verified env start --site gitlab
```

## Building the KG

GitLab 기준:

```bash
# 1. 환경 띄우고 인증 갱신
webarena-verified env start --site gitlab --port 8023 --env-ctrl-port 8024
python -m scripts.kg.utils.refresh_auth

# 2. Stage A — URL 수집 + 분류 규칙 산출
python -m scripts.kg.build.crawl
python -m scripts.kg.build.classify_rules

# 3. Stage B — action catalog + filter category 추출
python -m scripts.kg.build.collect_actions
python -m scripts.kg.build.action_catalog

# 4. Stage C — class-to-class edge graph 빌드
python -m scripts.kg.build.edge_graph
python scripts/kg/build/class_catalog.py
```

산출 위치: `output/validation/` (사이트 공통 path).
Runtime은 `output/validation/kg_solution/class_descriptions.json`을 읽는다.

## Evaluation

`scripts/eval/`에 측정·분석 도구가 있다:

```bash
# 사전 정의된 condition set으로 측정
bash scripts/eval/run_round_1.sh
bash scripts/eval/run_round_2.sh

# raw log → trial signal 추출
.venv/bin/python -m scripts.eval.extract_signals \
  output/<run>/v0/*/trial_*/ output/<run>/v1/*/trial_*/

# trial → cell aggregate
.venv/bin/python -m scripts.eval.aggregate_cells output/<run>/

# step distribution box plot + per-task statistics table
.venv/bin/python -m scripts.eval.render_figures output/<run>
```

산출물: `output/<run>/figures/step_box.png`, `output/<run>/step_table.md`.

Task 선정 / metric / exclusion 정책은 `docs/evaluation/`에 정리.

## Repository structure

```
site_adaptive_webagent/    # agent + KG runtime + KG seed
├── agent/                 # high-level agent entrypoint
├── runtime/               # ReAct + tool-use loop, browser primitives, LLM client
├── kg/
│   ├── seed/              # Stage A/B/C seed builder
│   ├── runtime/           # task inferrer, path finder, hint generator
│   └── ...
└── benchmarks/
    └── webarena_verified/ # benchmark adapter

config/sites/<site>/       # site-specific KG seed + cascade config
scripts/kg/                # KG seed build pipeline (Stage A/B/C)
scripts/eval/              # measurement + analysis pipeline
tests/
docs/
├── method/                # KG construction protocol
├── evaluation/            # task selection, metrics, exclusions, round protocol
└── validation/            # KG seed validation reports
run_webarena_verified.py   # benchmark entry point
```

## Output 구조

각 task 실행은 다음을 산출한다:

```
output/<task_id>/
├── agent_response.json    # task_type, status, retrieved_data
└── network.har            # raw network capture
```

같은 task를 다시 실행하면 기존 디렉토리는 `<task_id>_bkp_N`으로 백업된다.
