# Measurement 2 — 계획 (characterization)

작성 2026-05-19 · 사이트 GitLab · 모델 `gpt-5.4-mini`

## 1. 성격·목적

- **확정 시험이 아니라 특성 규명(characterization)**: "KG를 Web Agent에
  도입하니 이런 특징(도움/무효/방해)이 나타나더라"를 대표 사례로 공유.
- SOTA·성능 향상 목표 아님. 부 목적: task 수행 영상(`--record-video`).
- measurement 1 대비 변화: task subset(M1 겹침 허용) + 영상. 모델·예산·환경
  처리·trial 수는 `setup.md` 그대로.

## 2. 정직 바닥 (반드시 유지)

- 관측된 **모든 trial 결과 보고** — KG가 방해/무효인 사례도 그대로.
- 한계(예: substrate 가공본≠원본, 표본 작음)를 숨기지 않고 **특성의 일부로
  서술**.
- "보여주고 싶은 것만 보여줬다"는 금지. rough 선정이라도 adverse 사례 은폐 X.

## 3. 대표 task (rough purposeful 선정)

추측 기반 3-bucket. 기계적 술어·결정적 규칙·불가침 사전등록 없음. M1 겹침 무방.

| 기대 | task | 무엇을 보여주려는가 |
|---|---|---|
| KG **도움** | #308 (RET) | commits→contributor graph path 단축 (frozen_kg `/-/graphs/` 매핑) |
| KG **무효/미묘** | #419 (MUT) | status 기능이 KG에 **매핑돼 있음에도** 실질 단축을 주는가 |
| KG **방해/한계** | #480 (MUT) | invite-members modal 내부는 KG 공백 — KG가 닿는 경계 |
| scope 특성 | #357 (NAV) | dashboard MR scope disambiguation |
| replication (유지) | #102·#44·#664 | M1 task 재사용 — M1 특성이 재현되는지 |

선정 근거는 합리적 추측. #419는 "미매핑 L1" 정의에 끼우지 않는다 — "매핑돼
있는데 KG가 도왔나/무효였나"를 관측·보고하는 것 자체가 특성 사례다.

## 4. 서술 렌즈 (판정 게이트 아님 — 특징 읽는 도구)

- **range-containment**: v1 median이 v0 trial [min,max] 안/밖 → 효과 유무 감각
- **raw 3 trial 항상 병기** — 라벨로 collapse 안 함
- **mechanism-engagement**: 예측 KG class vs 관측 KG-fired의 일치/불일치를
  특성으로 서술 (H·L 성격 task만; Null 성격은 제외)
- **data-validity**: valid trial < 2 → "데이터 공백"으로 명시
- **low_resolution**: v0 trial range ≤ 1 → 효과 주장 보류, 기술 통계만

## 5. substrate caveat (재현 주의 — 게이트 아님)

- KG 원본 = tracked `config/sites/gitlab/frozen_kg/2026-04-16T...json`.
  `output/validation/*`는 gitignore 가공본. M1 일부 전제(L1 status "미매핑")는
  가공본 기준이라 원본과 불일치 — 원본엔 `/-/profile`에 `user[status][*]` 폼이
  존재. 이 점을 KG 효과 해석 시 caveat로 명시.
- 후보 universe: `docs/evaluation/task_universe.gitlab.json` (180 task, type
  분류 포함 — 선정 보조 참고자료, freeze됨).
- **LLM endpoint**: M1은 직접 OpenAI(gpt-5.4-mini). M2는 mindlogic 게이트웨이
  (`OPENAI_BASE_URL=.../v1/gateway`)로 **동일 모델 gpt-5.4-mini** 서빙 →
  endpoint-only 차이(모델 동일). 낮은 confound지만 M1↔M2 비교 시 endpoint 변경을
  명시. 코드 불변(openai SDK가 env의 base_url 자동 인식).
- **viewport (영상 경로 한정)**: M1은 no_viewport(headless 기본 800×600). M2는
  데모 영상 품질을 위해 `--record-video` 경로에서 viewport 1280×720으로 렌더.
  반응형 레이아웃이 달라 에이전트 관측이 M1과 다를 수 있음 = **의도된 confound**
  (demo 품질 우선, characterization이라 수용). M1↔M2 step 비교 시 이 변경을
  명시. record_video 미사용 경로는 no_viewport 유지(M1 재현 불변).

## 6. 실행

```
1. 픽 4개(#308 #419 #357 #480) + 유지 3개(#102 #44 #664) 확정
   → 각 task 간단 note (기대·관측 포인트; 무거운 falsification 카드 아님)
2. pre-measurement smoke 1 trial
3. measurement 2 1회 실행 (--record-video)
4. 서술 렌즈(§4) 적용 → cells/figures
5. M1 vs M2 특성 비교 narrative + 영상 링크
   산출 output/measurements/m2_*/, tracked 요약 docs/results/measurement_2.md
```

## 7. 한계 / 정직

- 표본 작음(3 trial) — 효과 *방향·특성* 탐색이지 효과 크기 주장 아님.
- 단일 사이트·단일 모델.
- 픽이 rough purposeful → **"대표 사례"이지 통계적 대표성 주장 아님**. 이 점을
  결과 보고에 명시한다.
