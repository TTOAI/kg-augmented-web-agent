# site-adaptive-webagent

사이트별 지식 그래프(site-specific KG)를 planning substrate로 사용하는 text-centric web agent 연구 프로젝트.

## 현재 브랜치 상태 (feature/kg-v2)

- `main`: V2.5 baseline
- `baseline/clean`: V2.5 baseline (KG 없음) — 측정용 고정 브랜치
- `feature/kg-v2`: KG 재설계 진행 중 (현재 브랜치)

baseline 코드는 그대로 유지하고, 옆에 KG 모듈을 추가하는 구조. KG 설계 논의 및 결정은 `docs/kg_design/`에 단계별 문서로 누적.

## 디렉터리 구조

- `site_adaptive_webagent/`: V2.5 baseline 에이전트 코드와 벤치마크 어댑터
- `site_adaptive_webagent/benchmarks/webarena_verified/`: WebArena-Verified 어댑터와 러너
- `config/`: 벤치마크별 설정 파일
- `config/sites/<site>/`: 사이트별 KG seed 데이터 (site_config, infotypes, kg_seed) — feature/kg-v2 신규
- `docs/kg_design/`: KG 설계 논의·결정 문서 (01~06)
- `docs/research_proposal/`: 연구 계획서
- `output/`: 로컬 실행 산출물 (git ignore)

## KG 설계 문서 (docs/kg_design/)

| 문서 | 내용 |
|---|---|
| 01_references_summary | KG/Agent/Web agent 배경 문헌 요약 + Introduction 초안 대비 |
| 02_open_questions | 설계 쟁점 #1~#4 결정 로그 + 모델·예산 결정 |
| 03_related_work_mapping | 기존 12개 접근과의 차별성 매핑 |
| 04_baseline_failure_analysis | Phase 1 failure taxonomy (14 task pilot) |
| 05_implementation_architecture | 모듈 경계·hook 구조·구현 순서 |
| 06_evaluation_protocol | 측정·분석·재현 protocol |

## 외부 벤치마크 목록

- `webarena-verified`

## WebArena-Verified

### 설치

```bash
# 의존성 설치 (uv 권장)
uv pip install -e .
uv pip install playwright
playwright install chromium
```

### LLM 설정

```bash
cp .env.example .env
# .env 안에 사용할 provider와 API 키 입력
```

`.env` 예시:

```bash
LLM_PROVIDER=openai          # 또는 anthropic
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_MODEL=gpt-4o        # provider별 모델 override (선택)
# ANTHROPIC_MODEL=claude-sonnet-4-6
# LLM_TEMPERATURE=0          # 실험 재현성을 위해 0 권장. 빈 값이면 provider default(보통 1.0) 사용
```

API 키가 없으면 LLM 없이 규칙 기반으로 폴백된다.

**실험 재현성 주의**: 기본값은 provider temperature(대개 1.0)라 같은 task도 실행마다 결과가 달라질 수 있다. 논문 실험처럼 baseline을 안정화해야 하는 경우 `LLM_TEMPERATURE=0`으로 설정해 deterministic 모드로 돌린다.

### config 준비

```bash
cp config/webarena_verified.example.json config/webarena_verified.json
```

`config/webarena_verified.json` 안의 URL, 포트, 계정 정보는 현재 로컬에서 띄운 benchmark 환경에 맞게 수정

### 환경 실행

```bash
webarena-verified env start --site shopping
webarena-verified env start --site shopping_admin
webarena-verified env start --site reddit
webarena-verified env start --site gitlab
```

환경 중지

```bash
webarena-verified env stop --site shopping
webarena-verified env stop-all
```

`wikipedia`, `map`은 추가 setup 필요

```bash
webarena-verified env setup init --site wikipedia --data-dir ./downloads
webarena-verified env start --site wikipedia --data-dir ./downloads

webarena-verified env setup init --site map --data-dir ./downloads
webarena-verified env start --site map
```

### 환경 리셋

MUTATE task(코멘트 작성, 상태 변경 등)는 사이트 상태를 변경하므로, 재실험 전에 사이트를 초기 상태로 리셋해야 정확한 측정이 가능하다.

```bash
webarena-verified env stop --site gitlab
webarena-verified env start --site gitlab
```

### task export

task 입력 준비

```bash
webarena-verified agent-input-get \
  --task-ids 44 \
  --config config/webarena_verified.json \
  --output output/tasks.demo.json
```

여러 task를 한 번에 export하거나 site 기준으로 필터링 가능

```bash
webarena-verified agent-input-get \
  --task-ids 44,45,46 \
  --config config/webarena_verified.json \
  --output output/tasks.multi.json

webarena-verified agent-input-get \
  --sites shopping \
  --config config/webarena_verified.json \
  --output output/tasks.shopping.json
```

### agent 실행

export된 task JSON을 읽어 agent 실행

```bash
.venv/bin/python run_webarena_verified.py \
  --tasks-file output/tasks.demo.json \
  --task-id 44 \
  --config config/webarena_verified.json \
  --run-root output \
  --headed
```

주요 옵션:

- `--headed`: 브라우저를 직접 띄워서 에이전트 행동 확인
- `--run-root output`: task별 산출물을 `output/` 아래에 저장

### 평가

특정 task만 평가

```bash
webarena-verified eval-tasks \
  --task-ids 44 \
  --output-dir output \
  --config config/webarena_verified.json
```

완료된 output 전체 평가

```bash
webarena-verified eval-tasks \
  --output-dir output \
  --config config/webarena_verified.json
```

### 출력물 구조

```text
output/
├── tasks.demo.json
└── 44/
    ├── agent_response.json
    └── network.har
```

task를 여러 번 실행하면 기존 task 디렉터리는 `44_bkp_1`, `44_bkp_2` 같은 이름으로 백업됨
