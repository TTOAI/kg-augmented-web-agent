# Usage

설치부터 KG 빌드·측정까지의 실행 절차. 시스템 구조는 [ARCHITECTURE.md](../ARCHITECTURE.md), 측정 실험 설계는 [evaluation/](evaluation/) 참조.

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

## 에이전트 실행

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

## KG 빌드

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

KG 구축 프로토콜은 [method/](method/), seed 검증 보고서는 [validation/](validation/) 참조.

## 측정 / 분석

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

task 선정 / metric / exclusion 정책은 [evaluation/](evaluation/) 참조.

## Output 구조

각 task 실행은 다음을 산출한다:

```
output/<task_id>/
├── agent_response.json    # task_type, status, retrieved_data
└── network.har            # raw network capture
```

같은 task를 다시 실행하면 기존 디렉토리는 `<task_id>_bkp_N`으로 백업된다.
