# Measurement 2 — task note (light)

`measurement_2_plan.md` §6의 가벼운 note. 무거운 falsification 카드가 아니라
**기대·관측 포인트**만. 선정은 rough purposeful 추측. 관측된 모든 결과 보고
(plan §2 정직 바닥).

변종: v0=baseline(`KG_ENABLED=0`), v1=KG(`KG_ENABLED=1 KG_MODE=minimal`).
공통 start URL: `http://localhost:8023`. trial 3 (setup.md).

## 픽 (rough purposeful)

### #308 [RET] — KG 도움 예상
> Get the username(s) of the user(s) with the most commits to the primer/design project

- 기대: KG가 contributor graph 경로(`/-/graphs/`, frozen_kg 매핑됨)를 노출 →
  agent가 namespace/project 채워 `goto` 단축. baseline는 메뉴 탐색.
- 관측: v0 vs v1 step, KG fired class(contributor graph 계열인지), agent
  thought/`goto`에 `/-/graphs/` 인용, raw 3 trial.
- 예측 KG class: contributor graph 계열 (mechanism-engagement 렌즈용).

### #419 [MUT] — KG 무효/미묘 예상
> Set my gitlab status as Enjoying life.

- 기대: status 기능이 frozen_kg `/-/profile`에 `user[status][*]`로 **매핑돼
  있음에도** KG가 실질 단축을 주는지 불확실 — 그대로 관측·보고.
- caveat: M1은 status를 "미매핑"으로 전제(가공본 기준)했으나 tracked
  frozen_kg엔 매핑 존재. 이 substrate 불일치를 특성 해석에 명시.
- 관측: KG fired class, v0/v1 step, `/-/profile` 도달 경로, raw.
- 예측 KG class: account/profile 계열.

### #357 [NAV] — scope 특성
> Go to the merge requests requiring my review

- 기대: dashboard scope MR 리스트(`/dashboard/merge_requests`)로의 scope
  disambiguation. (M1 H3 "assigned to me"와 같은 메커니즘, 필터만 reviewer-큐
  — 사용자 확정.)
- 관측: scope(dashboard vs project 오라우팅), KG fired class, step, raw.
- 예측 KG class: dashboard MR list 계열.

### #480 [MUT] — KG 방해/한계 예상
> Invite yjlou as collaborator(s) to solarized-prism-theme repo

- 기대: members 페이지(`/-/project_members`, 매핑됨)까지는 KG 단축, invite
  **modal 내부**는 frozen_kg에 modal 자산 키 자체가 없어 공백 → 후반 baseline
  회귀. KG 기여가 닿는 경계를 보여줌.
- 관측: members 도달 step, modal 진입 후 KG 추가 발동 유무, v0/v1 후반 패턴.
  data-validity 주의(modal 실패로 무효 trial 가능 → "데이터 공백" 명시).
- 예측 KG class: project members 계열.

## 유지 (M1 재사용 — replication 특성)

### #102 [NAV] — M1 H2(KG 도움) 재현 확인
> Navigate to the page showing the list of open issues in a11yproject ... labels related to help wanted

- 기대: M1처럼 path 단축 + label filter category 인지로 단축.
- 관측: M1(v0 15 / v1 9, confirmed) 특성이 재현되는지.

### #44 [NAV] — M1 Null1(무영향) 재현 확인
> Open my todos page

- 기대: KG=baseline (가시 정보라 KG 추가가치 없음).
- 관측: M1(2/2 parity) 재현 여부. low_resolution(range 0) 가능 — 기술만.

### #664 [NAV(규칙)/MUT(의미)] — M1 Null2(무영향) 재현 확인
> Open an issue with title "Question on future usage of Python 3.11" ...

- 주: leading-verb 규칙은 "open"으로 NAV 분류하나 의미상 create-issue(MUT).
  M1 Null2 카드 정의(MUT, parity, KG-orthogonal 자유텍스트) 상속.
- 기대: KG=baseline.
- 관측: M1(14/14 parity, 단 예측 issue_new_form ≠ 관측 issue_detail) 재현 +
  class 불일치 특성 재확인.
