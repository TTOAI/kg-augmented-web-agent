# V1 — Deferred Issues (후속 과제)

**Date**: 2026-04-18
**Purpose**: V1 (class identification) 수행 중 발견했지만 **Stage B 이후** 단계에서 다룰 과제 기록.

## 원칙

V1 scope = "이 페이지가 무슨 class인가" — URL pattern + main content 구조로 충분.
아래 이슈들은 class identification에 영향 없음. Widget catalog / navigation edge / runtime matching 단계에서 해결.

---

## D1. AXTree 추출기: href 손실

**현상**
`scripts/validation/v1_a_collect_axtrees.py:labelOf`가 innerText 우선 반환, 이후 href는 discard.
- 예: `<a href="/-/forks">0</a>` → AXTree에 `a: 0`만 남고 href 손실
- 예: project_main 페이지 fork counter "0" 링크의 destination `/-/forks` 추출 불가

**영향 범위**
- V1 class identification: 영향 없음 (URL path + main 구조만 사용)
- Stage B (class 간 navigation edge 추출): 영향 있음 — href 필요

**해결 방향**
- Option A: `<a>` 태그에 대해 innerText + href 둘 다 보존 (`"0 [href: /-/forks]"`)
- Option B: 별도 field로 분리 (`{label: "0", href: "/-/forks"}`)

**난이도**: 낮음 (5줄 수정)

---

## D2. AXTree 추출기: Accessible name 미계산

**현상**
aria-label, alt, title, innerText 모두 없는 element의 semantic label이 비어있음.
- 예: `<a role=button><svg aria-hidden=true></a>` (hamburger) → label이 `[href: #]`로 fallback
- 실제 browser accname 알고리즘이 계산하는 "Main menu" 같은 이름은 손실

**영향 범위**
- V1: 영향 없음 (header widget 구분 불필요)
- Stage B (widget catalog — 어떤 button이 어떤 action 수행): 영향 있음

**해결 방향**
- `axe-core` 라이브러리 주입 또는 W3C accname 알고리즘 직접 구현
- 또는 Playwright `page.accessibility.snapshot()` 지원 시 마이그레이션 검토

**난이도**: 높음 (accname 알고리즘 구현 또는 외부 라이브러리 통합)

---

## D3. 단일 snapshot의 lazy-rendered content 누락

**현상**
`page.goto()` + 1.5s 대기로 단일 snapshot 캡처 → click/hover로만 mount되는 content 놓침.
- 예: top-nav drop-down의 현재 active tab 외 다른 tab pane (Projects pane은 일부 페이지에만 pre-render, Groups pane은 어디서도 pre-render 안 됨)
- 시간 대기 무의미 확인 (t=0/3/8s 동일, event-driven)

**영향 범위**
- V1: 영향 없음 (main 영역 기반 class ID)
- Stage B (drop-down 내부의 navigation target 파악): 영향 있음

**해결 방향**
- Stateful crawl — 각 drop-down trigger를 click → snapshot → 병합
- 또는 SPA 초기 state에서 server-rendered 부분만 일관성 있게 사용

**난이도**: 중간 (interaction sequence 설계 + 중복 수집 방지)

---

## D4. Title 변동성 (runtime matching 문제)

**현상**
GitLab SPA가 back-navigation 시 `document.title`을 복원 안 함.
- 예: `/-/tree/main` fresh load → `Files · main · …`, 하위 폴더 클릭 후 뒤로 → `Byte Blaze / … · GitLab`

**영향 범위**
- V1 annotation data (fresh load 상태로 수집): 영향 없음
- Runtime class matching (agent가 실제 browsing 중 page match): 영향 있음. title을 신호로 쓰면 불안정

**해결 방향**
- Class rule을 **URL pattern primary**로 설계 (title 배제) — V1에서 이미 원칙 채택
- Runtime에서 title 사용 금지 재확인
- 필요 시 GitLab 이슈 리포트 또는 fork patch

**난이도**: 설계 원칙 수준. 코드 fix는 N/A.

---

## 정리

| ID | 이슈 | V1 영향 | Stage B 영향 | 난이도 |
|---|---|---|---|---|
| D1 | href 손실 | ✕ | ✓ | 낮음 |
| D2 | accname 미계산 | ✕ | ✓ | 높음 |
| D3 | lazy content 누락 | ✕ | ✓ | 중간 |
| D4 | title 변동성 | ✕ | runtime 영향 | 설계 원칙 |

V1 완료 후 Stage B 진입 시 D1-D3 순으로 해결 권장 (영향 크기 × 난이도 역순).
