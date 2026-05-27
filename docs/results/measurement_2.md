# 측정 2 — characterization (진행/스캐폴드)

> 이 문서는 측정 2 완료 후 데이터로 채운다. 데이터 미확정 구간은 `(측정 후
> 채움)`. 성격·선정·confound은 `docs/evaluation/measurement_2_plan.md` 참조.

KG advisory hint가 에이전트에 미치는 **특성**(도움/무효/방해)을 대표 사례로
규명하는 2차 라운드. 확정 시험 아님. SOTA 목표 아님.

## 설계

| 항목 | 값 |
|---|---|
| 사이트 | WebArena-Verified GitLab |
| 변종 | v0=baseline(`KG_ENABLED=0`), v1=KG(`KG_ENABLED=1 KG_MODE=minimal`) |
| 반복 | task × variant × 3 trial |
| 모델 | gpt-5.4-mini (mindlogic 게이트웨이) |
| 측정일 | 2026-05-19 |

선정(rough purposeful, `measurement_2_plan.md` §3):

| 기대 | task | 성격 |
|---|---|---|
| KG 도움 | #308 (RET) | commits→contributor graph path 단축 |
| KG 무효/미묘 | #419 (MUT) | status 기능 KG 매핑돼 있음에도? |
| KG 한계 | #480 (MUT) | invite-members modal 내부 KG 공백 |
| scope 특성 | #357 (NAV) | dashboard MR scope disambiguation |
| replication | #102·#44·#664 | M1 H2·Null1·Null2 재현 |

### Confound (정직 — M1 대비)

- **LLM endpoint**: M1 직접 OpenAI / M2 mindlogic 게이트웨이. 동일 모델
  gpt-5.4-mini → endpoint-only.
- **viewport (영상 경로 한정)**: M1 no_viewport(800×600) / M2 `--record-video`
  경로 1280×720. 반응형 레이아웃 차이 가능 = 의도된 confound(demo 품질 우선).
- **task subset**: M2는 일부 task가 M1과 다름(#308·#357·#419·#480 신규).

→ M1↔M2 비교는 위 confound를 명시한 **특성 서술**이지 통제된 효과 추정 아님.

## 결과

서술 렌즈(`measurement_2_plan.md` §4: range-containment / raw 병기 /
mechanism-engagement / data-validity / low_resolution).

| task | 기대 | v0 raw / median | v1 raw / median | KG fired(예측→관측) | 서술 라벨 |
|------|------|-----------------|-----------------|---------------------|-----------|
| #308 | 도움 | 16,12,23 / 16 | 18,20,11 / 18 | project/contributor_graph (일치) | range-overlap, 단축 미관측 |
| #419 | 무효 | 1/3 finite (15) | 0/3 finite | account/edit (v1 t1만) | 데이터 공백 |
| #357 | scope | 4,5,4 / 4 | 4,4,4 / 4 | dashboard/merge_request_list (일치) | parity median, v1 분산 좁힘 |
| #480 | 한계 | 0/3 finite | 0/3 finite | — | 데이터 공백 |
| #102 | repl. | 12,19,11 / 12 | 13,25,16 / 16 | project/issue_list | M1 단축 효과 미재현 |
| #44  | repl. | 2,2,2 / 2 | 2,2,2 / 2 | dashboard/todo_list | parity 재현 |
| #664 | repl. | 0/3 finite | 0/3 finite | — | 데이터 공백 |

데이터 공백 사유: #480·#664는 v0·v1 trial 1/2/3 전부 LLM 게이트웨이 크레딧 부족(402),
#419는 v0 trial 2/3 rate-limit(429) + v1 trial 2/3 크레딧 부족(402). #419 v0 trial 1은
UI 한계(Profile status에 텍스트 필드 부재), v1 trial 1은 sub-goal exhaustion으로 종결.
재측정은 보류 — 데이터 공백 그대로 보고.

figure: `(측정 후 — render_figures 산출 링크)`

## M1 vs M2 특성 narrative (측정 후 채움)

- replication(#102·#44·#664): M1 특성 재현 여부 — `(측정 후)`
- 신규 픽(#308·#357·#419·#480): KG 도움/무효/한계/scope 특성 — `(측정 후)`
- #419 substrate caveat 검증: status가 frozen_kg 매핑돼 있을 때 KG 거동
  — `(측정 후)`

## 산출/재현

- 원천: `output/m2/{v0,v1}/<task>/trial_*/` (gitignore). 동결 번들·MANIFEST는
  측정 후 `output/measurements/m2_*/`.
- 영상: trial별 `video/*.webm` (1280×720). mp4 변환:
  `bash scripts/eval/videos_to_mp4.sh output/m2`.
- 재현 절차: `docs/evaluation/measurement_2_plan.md` §6.

## 한계 / 정직

- 표본 작음(3 trial) — 효과 *방향·특성* 탐색, 효과 크기 주장 아님.
- 단일 사이트·모델. rough purposeful 선정 → **대표 사례지 통계적 대표성 아님**.
- 위 §Confound 3건을 M1 비교 해석 시 항상 동반 명시.
