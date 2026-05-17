# KG-Augmented Web Agent

LLM 웹 에이전트에 **사이트 구조 지식을 참고용(advisory) 힌트로 주입**해 행동 안정성을 실험한 프로젝트. 사이트별 지식 그래프(site-specific knowledge graph, KG)를 오프라인에서 만들고, 실행 중에는 에이전트가 강제 없이 참고만 하도록 주입한다.

## 문제

웹 에이전트는 매 step마다 "어디로 갈지", "어떤 필터가 있는지", "URL을 어떻게 만들지"를 결정해야 한다. 이를 LLM의 일반 추론에만 맡기면 같은 task에서도 행동이 흔들리고(궤적 분산), 사이트 구조를 매번 탐색으로 재발견하느라 step이 길어진다.

질문: **사이트 구조를 KG로 미리 정리해 runtime hint로 주입하면, 에이전트의 행동이 더 안정되는가?**

## 접근

사이트의 구조 정보를 오프라인에서 KG로 빌드하고, 실행 중 advisory hint로 주입한다.

- **구조는 KG, 구체값은 에이전트.** KG는 *어떤 page class·경로·필터 카테고리·컨트롤이 존재하는지*(구조적 방향)까지만 노출한다. *필터에 넣을 값·URL 쿼리 값·자유 텍스트*(구체값)는 에이전트가 페이지를 직접 보고 수집한다.
  - 근거 ① **데이터 노후화 회피**: KG에 구체값을 박으면 UI 변경 때마다 KG를 갱신해야 한다.
  - 근거 ② **직접 관측이 더 안전**: LLM이 실시간으로 직접 수집해 행동하는 것이, KG로 수동 주입받는 것보다 정보의 안전성·신뢰성이 높다.
- **KG는 advisory·additive.** 힌트 문자열만 주입하고 실행 루프는 KG 유무에 불변하다. KG를 끄면 baseline과 완전히 동일한 코드 경로를 탄다 — 단일 env 스위치로 baseline ↔ KG를 비교하는 깨끗한 ablation이 가능하다.

## 설계 핵심

| 결정 | 내용 |
|---|---|
| **Benchmark Adapter 격리** | 벤치마크 결합을 단일 계층(`benchmarks/`)에 가둔다. 에이전트·런타임은 벤치마크를 모르고 파일 계약으로만 소통 → 에이전트 이식성. |
| **중립 판정 ↔ 상태 분리** | 에이전트는 벤치마크 무관한 중립 판정(verdict)만 배출. `classify_outcome`만 WebArena status로 번역 — 유일한 결합 지점. 관심사 분리를 코드로 강제. |
| **에이전트 신뢰성 엔진** | 2중 루프(orchestration/ReAct) + 점진 복구 ladder(retry → replan → deep rollback) + 검증 게이트 + 독립 2차원 예산 가드. |
| **의도적 최소 검증** | `_verify_done`은 단일 hard-rule(이동 안 한 navigation만 reject). 정답 검증은 evaluator에 위임 — LLM self-judge는 ablation 교란·자기 환각 rubber-stamp 위험. |
| **KG 빌드/런타임 분리** | 오프라인이 `output/validation/*` 생산, 런타임은 읽기만, 측정이 baseline/KG로 반복. |

구조 상세는 [ARCHITECTURE.md](ARCHITECTURE.md).

## 결과

WebArena-Verified GitLab에서 7개 condition, baseline(v0) vs KG(v1), 각 3 trial로 측정했다. condition은 KG가 도울 것으로 본 **가설(H1–H3)**, 확신이 낮은 **저신뢰(L1–L2)**, KG와 무관해야 하는 **대조군(Null1–Null2)** 으로 구성된다. 개별 가설·task 정의는 [`docs/evaluation/`](docs/evaluation/) 참조.

**step 분포 (baseline 회색 vs KG 파랑, 3 trial, raw point overlay)**
![per-task step distribution](docs/assets/step_box.png)

**median step (조건 × 변종)**
![median step counts](docs/assets/step_counts.png)

| Cond | Task | V0 step | V1 step | 판정 |
|------|-----:|--------:|--------:|------|
| H1 | 309 | 19 | 21 | refuted |
| H2 | 102 | 15 | 9 | confirmed |
| H3 | 156 | 4 | 4 | partial |
| L1 | 418 | 9 | 11 | needs_review |
| L2 | 568 | timeout | timeout | parity_review |
| Null1 | 44 | 2 | 2 | confirmed_parity |
| Null2 | 664 | 14 | 14 | confirmed_parity |

판정 라벨 (automated triage):

- **confirmed** — KG가 step을 줄임 (가설 지지)
- **refuted** — KG가 step을 줄이지 못함/늘림 (가설 기각)
- **partial** — 차이가 미미하거나 부분적
- **needs_review** — 자동 판정 보류, 수동 검토 필요
- **parity_review** — 데이터 부족(예: 양쪽 timeout)으로 판정 보류
- **confirmed_parity** — 대조군에서 KG 영향 없음을 확인 (의도된 결과)

**정직한 해석**:

- median step 효과는 **혼재**한다 — KG가 줄인 경우(H2)도, 늘린 경우(H1)도 있다. "KG가 일관되게 step을 줄인다"는 결론은 **나오지 않았다**.
- 다만 step **분포**(박스플롯)에서 KG는 baseline의 큰 분산을 좁히는 경향을 보인다(H1·Null2: baseline 넓은 분산 → KG 좁은 분산). 단 L1처럼 역행하는 cell도 있어 일관 효과로 주장하지 않는다.
- 대조군(Null1·Null2)이 모두 parity(KG를 켜도 무관한 task에서 변화 없음) → 실험 설계 자체가 의도대로 작동함을 뒷받침한다.

automated triage 수준이며 cell별 수동 narrative는 미완이다. 상세 수치는 [`docs/assets/results_condition_synthesis.md`](docs/assets/results_condition_synthesis.md).

> **이 프로젝트의 산출**은 "KG가 효과 있다"는 입증이 아니라 — (1) 단일 변수만 바꾸는 **재현 가능한 ablation 인프라**(코드 동일, env 스위치만 차이; 통계 검정까지 외부 의존 없이 자체 구현)와, (2) 가설이 깨지는 결과(refuted)까지 그대로 보고하는 **연구 태도**다. 대조군이 의도대로 무효과를 보인 것은 그 인프라가 실제로 작동함을 보인다.

## 한계 / 향후

- 단일 사이트(GitLab)·단일 모델(`gpt-5.4-mini`). cross-site·cross-model 일반화는 향후 과제.
- KG seed는 hybrid(crawl + LLM + manual)로 빌드된다. 사이트별 시딩 비용을 줄이는 자동 구축이 다음 방향.
- 표본이 작아(condition당 3 trial) 통계 검정력이 제한적이다. 본 측정은 효과 *방향* 탐색이며 확정적 효과 크기 주장이 아니다.

## Quick Start

> 전체 재현 절차(요구사항·환경 구성·KG 빌드·측정)는 [docs/usage.md](docs/usage.md). 아래는 흐름 개요다 — `uv`([설치](https://docs.astral.sh/uv/)) 와 WebArena-Verified 환경 구성이 선행되어야 실제 동작한다.

```bash
uv pip install -e . && uv pip install playwright && playwright install chromium
cp .env.example .env                                   # LLM 키 설정
cp config/webarena_verified.example.json config/webarena_verified.json

webarena-verified env start --site gitlab --port 8023 --env-ctrl-port 8024
webarena-verified agent-input-get --task-ids 44 \
  --config config/webarena_verified.json --output output/tasks.demo.json
.venv/bin/python run_webarena_verified.py --tasks-file output/tasks.demo.json \
  --task-id 44 --config config/webarena_verified.json --run-root output --headed
```

## Repository structure

```
kg_augmented_webagent/
├── agent/                 # run_agent entrypoint (composition root)
├── runtime/               # ReAct + tool-use 실행 엔진, browser primitive, LLM client
├── kg/
│   ├── seed/              # Stage A/B/C seed builder
│   └── runtime/           # task inferrer, path finder, hint generator
└── benchmarks/
    └── webarena_verified/ # benchmark adapter

config/sites/<site>/       # 사이트별 KG seed + cascade config
scripts/kg/                # KG seed build pipeline (Stage A/B/C)
scripts/eval/              # measurement + analysis pipeline
docs/
├── usage.md               # 실행 매뉴얼
├── method/                # KG 구축 프로토콜
├── evaluation/            # 측정 실험 설계 (task 선정/metric/exclusion)
└── validation/            # KG seed 검증 보고서
ARCHITECTURE.md            # 시스템 구조
```

## License

[MIT](LICENSE).
