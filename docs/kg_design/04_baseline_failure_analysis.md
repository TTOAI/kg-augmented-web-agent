# 04. Pilot 실패 분석 — 개발 로그 (**paper 내용 아님**)

## ⚠️ 이 문서의 위치 (중요)

본 문서는 **개발 초기의 비공식 baseline**(이후 다수 버그가 발견돼 전면 재작성됨)이 만든 실패 case 6건에 대한 정성 분석이다. 이 pilot은:

- **논문에 들어가지 않는다**. 분석 대상 baseline이 임의로 만든 1차 구현이라 객관성·공식성이 없기 때문.
- **내부 개발 로그**로만 의미를 가진다. pilot이 드러낸 패턴들이 이후의 코드 재작성(declare_error, verify_done 엄격화, NAVIGATE guard, classify 개선, LLM_TEMPERATURE=0 등 27건의 수정)을 유도했다.
- **paper의 baseline failure 분석은 새 baseline의 첫 공식 측정 결과로 별도 작성**한다.

이 문서의 표·분류·수치는 개발 당시의 기록이며, **새 baseline의 결과와 다를 수 있다**. Paper methodology 섹션에서 인용하지 않는다.

---

## 1. 분석 대상 (6건)

baseline/clean 브랜치 N=1 측정 (2026-04-15). 실행 환경: gitlab site, 600초 task timeout.

| task | intent | task_type | agent 선언 | eval 결과 | 실패 평가기 |
|------|--------|-----------|-----------|----------|-------------|
| 102 | help-wanted label이 있는 open issues 페이지로 이동 | NAVIGATE | SUCCESS | failure | NetworkEventEvaluator |
| 156 | assigned-to-me merge requests 보기 | NAVIGATE | SUCCESS | failure | NetworkEventEvaluator |
| 169 | 별 가장 많이 받은 personal project의 project ID | RETRIEVE | SUCCESS → "183" | failure | AgentResponseEvaluator |
| 258 | public projects listing 열기 | NAVIGATE | SUCCESS | failure | NetworkEventEvaluator |
| 308 | primer/design에 가장 많이 commit한 사용자명 | RETRIEVE | — (600s timeout) | error | — |
| 339 | 현재 project의 open bug issues 리스트로 이동 | NAVIGATE | SUCCESS | failure | NetworkEventEvaluator |

관찰 1: 6건 중 4건이 agent는 SUCCESS로 자기선언했으나 NetworkEventEvaluator가 URL 일치 실패로 탈락. 즉 **agent의 self-verification과 evaluator 사이 systematic gap**이 있다.

관찰 2: RETRIEVE 과제에서 평가 실패 양상이 두 가지. 169는 extract된 값이 틀림, 308은 아예 도달하지 못하고 timeout.

---

## 2. task별 정성 분석

### 2.1 task 339 — NAVIGATE: open bug issues 리스트

**baseline plan (LLM 생성)**

```
1. Open the project issues page [navigation]       → 2 step, verified
2. Apply the open issues filter [action]           → 3 step, verified
3. Filter issues to bug reports [action]           → 4 step, verified
4. Arrive at the list of open bug issues for this project [navigation]
                                                   → 16+ step, REJECTED 반복 → 자동 SUCCESS 선언
```

**실패 구조**
- sub-goal 2와 3에서 이미 `?state=opened&label_name[]=bug` 상태에 도달함. URL은 이미 target.
- sub-goal 4는 "이미 도달한 상태"를 다시 요구하는 **중복 sub-goal**. v2.5 baseline의 hard rule(마지막 navigation sub-goal은 URL 변경을 요구함)에 걸려 reject 루프.
- LLM은 돌파하려 다른 이슈 detail 페이지로 잠깐 이동(/issues/1478)하는 등의 오동작을 함.
- 최종적으로 self-verification은 넘겼지만 최종 URL이 target에서 벗어남 → NetworkEventEvaluator fail.

**부재한 지식**
- "GitLab에서 label 필터를 적용하면 URL이 `?label_name[]=bug`로 바뀌고 그 자체가 target이다. 별도 navigation 필요 없음."
- 즉 **action 완료 == 목표 상태 도달** 의 site-specific 매핑.

---

### 2.2 task 102 — NAVIGATE: help-wanted label 이슈 리스트

**baseline plan**

```
1. Open the a11yproject/a11yproject.com project page [navigation]  → verified
2. Navigate to the repository issues list [navigation]              → verified
3. Apply the open-issues and help-wanted label filters [action]     → 6 step, verified
4. Arrive at the filtered issues page URL [navigation]              → REJECTED 반복 → attempt 2에 verified
```

**실패 구조**: task 339와 동형. sub-goal 3 완료 시점에 이미 target 상태. sub-goal 4는 중복, hard rule 트랩. attempt 2에서 verified로 넘어갔지만 URL 파라미터가 완전히 일치하지 않아 network eval fail.

**부재한 지식**: task 339와 동일 계열. plus "GitLab의 label 필터는 URL에 `label_name[]=...` 파라미터로 직렬화된다"는 URL schema 지식.

---

### 2.3 task 156 — NAVIGATE: assigned-to-me merge requests

**baseline plan**

```
1. Open the dashboard merge requests page. [navigation]  → 3 step, verified
2. Navigate to the merge requests assigned to me view. [navigation]
   → 23+ step, REJECTED 반복, 돌파 실패
```

**실패 구조**
- dashboard/merge_requests는 기본적으로 "assigned to me"가 기본 탭이거나 URL 파라미터로 드러남.
- LLM은 "assigned to me" 필터/탭을 찾으려 DOM을 돌아다니다가 특정 merge request detail 페이지(/merge_requests/40)로 잘못 진입하기도 함.
- verifier가 "URL에 assigned-to-me 파라미터가 없다"며 계속 reject.

**부재한 지식**
- "GitLab `/dashboard/merge_requests`는 author_username / assignee_username 같은 URL 파라미터로 탭을 표현한다"
- 또는 "이 사이트에서 기본 dashboard MR 페이지가 이미 assigned-to-me이다"(사이트에 따라 다를 수 있음)
- 즉 **URL schema** + **필터 기본값 semantics**.

---

### 2.4 task 258 — NAVIGATE: public projects listing

**baseline plan**

```
1. Navigate to the public projects listing page. [navigation]  → 2 step, verified
```

**실패 구조**: plan 자체는 1-sub-goal로 단순. agent가 도달한 URL이 **evaluator가 기대한 URL과 다름**. 둘 다 "public projects listing"으로 부를 수 있는 후보가 여러 개 존재(GitLab에는 `/explore`, `/explore/projects`, `/public` 등). LLM의 선택이 평가 기준과 일치하지 않음.

**부재한 지식**
- "이 사이트에서 `/explore` 대신 정확한 target URL은 무엇인가"에 대한 canonical mapping.
- 또는 evaluator가 기대하는 URL을 유추할 근거.

*주의*: 이것이 실질적 실패인지, evaluator strict match의 artifact인지 경계에 있음. 본 연구 메모리의 "broken eval task 처리 원칙"을 염두에 두고 Phase 2에서 재확인 필요.

---

### 2.5 task 169 — RETRIEVE: 가장 별 많은 personal project ID

**baseline plan**

```
1. Open the list of your personal projects. [navigation]                → verified
2. Identify the personal project or projects with the highest star count. [action]
                                                                        → 3 step, verified
3. Extract the project ID or IDs for those top-starred personal projects. [action]
                                                                        → 22+ step, 결국 "183" 반환
```

**실패 구조**
- LLM이 반환한 project ID `"183"`은 정답이 아님.
- sub-goal 2가 "verified"로 넘어갔지만, 실제로 top-starred를 올바로 식별했는지 의문.
- 두 가지 가능: (a) top-starred 식별이 틀렸다, (b) 식별은 맞았는데 project ID 추출이 틀렸다.

**부재한 지식**
- GitLab에서 project ID를 찾는 경로(URL의 `project_id=...`, settings > general에 numeric ID 노출, 또는 API path) — 여러 지점에 흩어짐.
- 정렬 기준 제어(별 개수로 정렬) + "personal" 필터의 정확한 의미.

**분류 주의**
- 이 실패는 **site plan 구조 부재가 아니라 extraction/grounding 정확도** 문제에 가깝다. KG가 도울 여지는 "project ID는 URL의 X 위치에서 읽는다"식 schema 제공 정도.

---

### 2.6 task 308 — RETRIEVE: primer/design 최다 commit 사용자 (timeout)

**baseline plan**

```
1. Open the primer/design project page. [navigation]               → verified
2. Find the commit history or contributor list for the project. [action]
                                                                   → verified
3. Identify the user(s) with the highest commit count. [action]
                                                                   → 24+ step, REJECTED 지속, 600s timeout
```

**실패 구조**
- GitLab UI에는 기본적으로 "committers by count" 집계 뷰가 눈에 띄지 않음. `/-/graphs/<branch>`에 contributor graph가 있지만 LLM이 접근하지 못함.
- LLM은 `search=cole+bemis` 같은 추측성 쿼리 파라미터로 commit을 필터링하며 맴돎.
- verifier는 "top committer 근거가 없다"며 계속 reject → 시간 초과.

**부재한 지식**
- "commits per author를 구하는 GitLab 경로는 `/project/-/graphs/<branch>` 또는 `/project_members` 또는 contributor API" — **procedural/route 지식**.
- 즉 task 자체가 **site 안에 해당 정보가 있는 위치**를 알아야만 풀리는 구조.

---

## 3. 실패 유형 초안 taxonomy

6건을 카테고리화. 한 task가 여러 카테고리에 해당할 수 있음(겹침 표기).

**Category P — Plan-structural (sub-goal 구조 오류)**
- 정의: LLM의 plan이 site 특성상 중복이거나 빠진 sub-goal이 있어 실행 불가·비효율.
- 핵심 부재 지식: **action → 상태 전이 매핑** (어떤 action을 수행하면 어떤 URL/상태가 되는가).
- 해당: **102, 156, 339** (강한 신호). 258, 308도 약하게 연관.

**Category R — Route-knowledge (경로 지식 부재)**
- 정의: 목표 정보/상태에 도달하는 site 내부 경로를 LLM이 모름.
- 핵심 부재 지식: "X를 얻으려면 어느 페이지·URL 패턴·필터·API를 거쳐야 하는가" — **path + URL schema**.
- 해당: **156** (assigned-to-me URL param), **258** (canonical public listing URL), **308** (commits-per-author route), 102/339의 label URL schema.

**Category G — Grounding/extraction (DOM 해석·값 추출 오류)**
- 정의: plan은 맞는데 페이지 읽기 또는 값 추출이 틀림.
- 해당: **169** (강한 신호). 다른 task에서는 약함.

**Category A — Verifier/evaluator artifact (검증기·평가기 인공물)**
- 정의: v2.5 hard rule 또는 NetworkEventEvaluator strict match에 의해 실질 성공이 실패로 기록됨.
- 해당: **102, 156, 339** (hard rule), **258** (eval strict URL match). 108, 258은 KG만으로 해결 불가능한 artifact 성격도 있음.

### 카테고리 교차표

| task | P | R | G | A |
|------|---|---|---|---|
| 102  | ● | ● |   | ● |
| 156  | ● | ● |   | ● |
| 169  |   |   | ● |   |
| 258  | △ | ● |   | △ |
| 308  | △ | ● | △ |   |
| 339  | ● |   |   | ● |

●: 주요 원인, △: 부분 원인.

---

## 4. 이 pilot이 Introduction 주장 1에 주는 함의

Introduction 초안 주장 1은 "web agent 병목이 grounding보다 planning에 있다". 본 pilot의 6건을 놓고 보면:

- **순수 grounding 실패(G 단독)는 1건(169)**.
- **plan 구조 또는 경로 지식 부재(P·R 단독 또는 결합)는 4~5건**.
- 다만 P 중 3건은 **v2.5 hard rule과 얽혀 있어** "planning 지식 부재가 주원인인가 / hard rule이 증폭기인가"를 분리해야 한다.

잠정 결론: 본 연구의 설정에서도 **planning 계열 부재 지식이 실패의 주원인**이라는 방향은 약하게 지지된다. 단,
1. 표본이 작고 선정 편향이 있어 Phase 2에서 확인 필요.
2. "P 실패"의 상당 부분이 **action → 상태 전이 매핑** 부재와 **URL schema** 부재에 집중된다는 점이 특히 흥미롭다. 이는 본 연구 KG 설계에 구체적 입력이 된다.
3. hard rule이 P 범주 실패를 시스템적으로 증폭하는 방향이어서, baseline 자체의 이 규칙을 그대로 둘지 평가 설계에서 고려해야 한다.

---

## 5. KG 내용 결정에 대한 함의

대화의 Level A vs Level B 논의로 돌아가면, 이 pilot은 **Level A 안에서 두 하위 형태를 구분**하도록 요구한다.

- **Level A1 — procedural UI sequence**: "bug 필터를 걸려면 `click[label dropdown] → click[= operator] → type[bug] → Enter`" 같은 저수준 DOM 액션 시퀀스.
  - pilot에서 이 수준의 부재가 **직접 실패의 원인이었다는 증거는 약하다**. LLM은 sub-goal 2·3을 실제로 수행했다.
- **Level A2 — state-transition + URL schema**: "label 필터 action은 URL을 `?label_name[]=<name>`으로 바꾸며, 이것이 target state다", "assigned-to-me는 `assignee_username=<me>` URL param으로 표현된다", "commits-per-author는 `/-/graphs/<branch>` 경로에 있다".
  - pilot의 주된 부재 지식이 이쪽.

즉 본 pilot이 지지하는 KG의 **1차 내용물**은
- page ⇄ URL pattern ⇄ action의 삼각 관계
- "action 완료 후 도달하는 상태"의 매핑
- target 정보별 canonical route

로 보인다. 이것은 과거 m0-sitekg의 `PageNode / WidgetNode / NavigationEdge / InteractionEdge` 스키마와 **일부 겹치지만**, 핵심 차이는

- m0에서는 노드를 채우기는 했지만 **"action 완료 시 어느 상태로 가는가"를 planner가 사용 가능한 형태로 제공하지 못했을 가능성**.
- 이번 설계에서는 **state-transition과 URL schema를 1급 표현 단위**로 올려, planner가 sub-goal 생성 시 이를 직접 참조하도록 강제해야 한다.

이 함의는 다음 단계 쟁점(02_open_questions.md §3 — minimum viable KG 스키마)에서 구체화한다.

---

## 6. Phase 2 설계 입력

pilot을 토대로 Phase 2는 다음을 확인해야 한다.

1. **카테고리 P의 비율이 일반화되는가** (hard rule을 빼고 보더라도 plan-structural 부재 실패가 다수인지).
2. **Category R(경로 지식)의 비율**. 본 pilot에서 눈에 띄게 잦은데, 소표본 우연일 수도 있음.
3. **G(grounding/extraction)의 비율**. 169 같은 pure G 실패가 더 많아지면 KG의 기여 공간이 좁아진다.
4. **hard rule을 완화/제거한 "fair baseline"에서도 P가 여전히 주원인인가**.

Phase 2 실행 설계 초안은 별도 문서에서 정리. pilot이 규정한 방향은 "P + R 실패 패턴에 집중한 KG 설계가 타당한가"를 검증하는 쪽이다.

---

## 7. 이 문서가 고의로 다루지 않은 것

- 각 task의 DOM 관찰 내용과 action trace 전체. 필요시 `output/baseline_clean_n1/<task>/webarena_verified.log`를 직접 참조.
- 성공한 8개 task(44, 45, 132, 205, 259, 293, 357, 390)의 plan 패턴. 성공 케이스의 plan 구조와 실패 케이스의 plan 구조를 대비하는 작업은 Phase 2와 병행할 가치가 있지만 이 pilot의 범위 밖.
- 14개 task 전체 budget/step 분포 통계. 성능 문서가 아니라 failure-mode 분류 문서이므로 의도적으로 제외.
