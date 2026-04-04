# site-adaptive-webagent

## 디렉터리 구조

- `site_adaptive_webagent/`: 공용 에이전트 코드와 벤치마크 인터페이스
- `site_adaptive_webagent/benchmarks/webarena_verified/`: WebArena-Verified 어댑터와 러너
- `config/`: 벤치마크별 설정 파일
- `output/`: 로컬 실행 산출물 저장 위치 (`git`에서 무시됨)

## 외부 벤치마크 목록

- `webarena-verified`

## WebArena-Verified

### 설치

```bash
python3 -m pip install webarena-verified
python3 -m pip install playwright
python3 -m playwright install chromium
```

혹은

```bash
uvx webarena-verified --help
```

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
python3 run_webarena_verified.py \
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
