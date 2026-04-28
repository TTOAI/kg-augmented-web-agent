# 사이트별 구조 지식 그래프는 웹 에이전트에 언제 도움이 되는가

## When Does a Site-Specific Structural Knowledge Graph Help an LLM Web Agent?

---

## 요 약

LLM 기반 웹 에이전트가 같은 사이트의 페이지 구조를 매번 관측에서 재발견하는 비효율을 해소하기 위해, 사이트 구조를 사전 계산된 지식 그래프(Knowledge Graph, KG)로 외부화하고 페이지 클래스 식별자를 숨긴 최소 힌트로 주입하는 접근을 제시한다. 본 연구는 KG의 _우월성을 주장하지 않고_ WebArena-Verified GitLab의 7개 사전 등록 과제를 V0(KG 미사용)와 V1(KG 사용)로 각 3 trial 측정하여 KG 효과의 발생·무효·부정 조건을 특성화한다. (1) **효과 발생 4건**: V1이 평균 step을 0.7~7.7 단축한다. 그 중 2건(309, 664)은 V0의 catastrophic trial(각 54·37 step)을 V1이 일관된 범위로 안정화하여 표준편차를 5~12배 감소시키는 *worst-case 안정화* 효과가 지배적이다. (2) **효과 미발생 1건**: baseline이 이미 1-hop 효율적이라 KG가 추가 가치를 못 준다. (3) **효과 부정 1건**: 비ARIA 모달 내부에서 KG 기여가 소멸하며 두 변종 모두 시간 초과한다. (4) **무영향 1건**: 1-step 직접 링크 과제로 active control이 작동한다. 모든 과제에서 KG는 평가기 통과율을 변경하지 않으며 step 효율에만 영향한다. 결론적으로 KG는 보편적 가속이 아니라 *평균 단축과 worst-case 안정화의 조건부 효과* 를 가지며, 비ARIA 컴포넌트 내부에서는 기여가 소멸한다.

주요어: 지식 그래프, 웹 에이전트, 사이트별 구조, 힌트 주입, 효과 조건 특성화

---

## 1. 서 론

LLM 기반 웹 에이전트[1, 2]는 매 서브목표마다 (1) 어느 페이지 클래스가 과제를 담당하는지, (2) 그 페이지에 어떤 필터·버튼이 있는지, (3) 어느 URL 경로가 단축인지를 관측만으로 재발견한다. 이 반복은 같은 사이트의 과제마다 누적된다.

선행 연구는 사이트 지식의 사전 자산화에 집중했다. SteP[3]은 수동 정책 스택을, WALT[4]는 역공학 도구 함수를, AWM[5]은 실행 궤적 재사용을 제공한다. 본 연구는 *사이트 구조 자체*를 KG로 외부화하고 최소 힌트로 주입한다.

본 논문은 KG가 일반적으로 도움이 된다고 _주장하지 않는다_. 대신 다음 질문을 묻는다. **KG는 어떤 조건에서 step을 줄이고, 어떤 조건에서 효과가 없거나 부정적인가?** 기여는 (C1) ARIA 표준 기반 사이트에 무관한 KG 구축 프로토콜과 "방향만 노출, 구체값은 에이전트가 직접 찾는다" 라는 최소 힌트 설계 원칙, (C2) 7-과제 사전 등록 측정으로 효과 발생 4건·미발생 1건·부정 1건·무영향 1건을 정직하게 특성화한 점이며, 그 중 V1이 V0의 catastrophic trial을 prevent하는 *worst-case 안정화* 가 효과 발생의 주요 메커니즘 중 하나임을 관찰한 점, (C3) KG 효과가 평가기 통과율과 직교하며 step 효율에만 영향한다는 관찰이다.

## 2. 방 법

### 2.1 KG 구축

세 단계로 수행한다. 1단계는 출발 URL 집합에서 너비 우선 탐색으로 페이지를 수집하고 URL 규칙으로 페이지 클래스를 할당한다. 2단계는 각 클래스 샘플에서 ARIA 역할 속성(메뉴 항목, 옵션, 탭, 대화상자 팝업 트리거)과 표준 폼 요소만을 근거로 액션·필터·대화상자를 수집한다. 의도적으로 사이트에 무관하며 비표준 컴포넌트는 포착하지 않는 대신 단일 구현으로 여러 사이트에 이식된다. 3단계는 URL 템플릿, 범위, 트리거 문구, 필터 카테고리를 결합해 클래스 카탈로그를 만든다. 현 GitLab KG는 139 클래스·23 클래스의 필터 카테고리·2,731 전이 엣지를 담는다.

### 2.2 실행 시점 통합과 최소 힌트 — "방향만, 구체값은 에이전트가"

실행 시점에서 KG는 세 모듈로 소비된다. **타겟 클래스 추론기**는 K=3 자기 일관성 LLM 호출로 task에서 목표 클래스를 결정한다. **경로 탐색기**는 6단계 단계별 후퇴로 현재 클래스에서 목표 클래스까지의 경로를 탐색한다. **힌트 생성기**는 경로 단축 URL과 현재 페이지 표면 정보(액션 카탈로그·필터 카테고리 존재)를 관측 메시지에 주입한다.

설계 원칙은 _KG는 구조적 방향만 노출하고 구체값은 에이전트가 페이지 상호작용에서 직접 찾는다_ 이다. 최소 힌트 모드(`KG_MODE=minimal`)는 (i) URL 파라미터 레시피, (ii) 페이지 클래스 식별자, (iii) 필터 카테고리의 예시 값·옵션 값·기본 값을 모두 억제한다. 이 분리는 V1의 step 단축이 KG의 *구조 정보 우월*에서 오는지 _KG가 정답을 흘려서_ 오는지 분리한다.

## 3. 실험 설정

WebArena-Verified GitLab 자가 호스팅 인스턴스를 사용한다. 에이전트 LLM은 OpenAI `gpt-5.4-mini` 단일 모델이다. 변종은 V0(`KG_ENABLED=0`)와 V1(`KG_ENABLED=1 KG_MODE=minimal`) 둘이며 각 (과제 × 변종) cell에 3 trial을 측정한다. 측정 방법론은 _task fixed-set 사전 lock이 아니라_ iterative round + 약한 사전 등록이다. round 시작 전에 (a) 선정 규칙(archetype gap 기반), (b) stopping rule(세 archetype에 ≥1 task + 누적 task ≤ 8), (c) 모든 결과 보고 의무를 git에 commit한다. 본 측정은 Round 1·2 합계 7 과제 × 2 변종 × 3 trial = 42 trial이다.

## 4. 결 과

그림 1은 7 과제의 per-trial step 분포를 V0/V1 box plot + raw 3 trial scatter로 보여준다. H1(309)·Null2(664) 두 과제에서 V0 box가 위로 길게 늘어진 것은 baseline의 catastrophic trial이 worst-case를 끌어올린 결과이며, 같은 과제의 V1 box가 좁게 붙어 있는 것이 *worst-case 안정화* 효과의 시각적 표지다. L2(568)는 두 변종 모두 timeout(붉은 ×)으로 표시된다. 표 1은 동일 데이터를 mean (sd) + raw trial 값으로 정량 표기한다.

![그림 1. 과제별 V0/V1 step 분포 (3 trial 각각, raw point + box). 회색 = V0(KG 미사용), 파랑 = V1(KG minimal mode). 568은 V0/V1 모두 시간 초과로 box 없이 ×로 표시.](figures/step_box.png)


| 과제 ID | 유형 | V0 trials | V0 mean (sd) | V1 trials | V1 mean (sd) | Δmean | KG 추론 클래스 | 평가기 V0/V1 |
|---------|------|-----------|--------------|-----------|--------------|-------|----------------|--------------|
| 102 | NAV | [11,15,16] | 14.0 (2.7) | [8,9,12] | **9.7 (2.1)** | **−4.3** | project/issue_list | 실패/실패 |
| 156 | NAV | [4,4,4] | 4.0 (0.0) | [4,4,6] | 4.7 (1.2) | +0.7 | dashboard/merge_request_list | 통과/통과 |
| 309 | RET | [13,19,54] | 28.7 (22.1) | [18,24]ᵃ | **21.0 (4.2)** | **−7.7** | project/main | 실패/실패 |
| 418 | MUT | [8,9,18] | 11.7 (5.5) | [7,11,15] | **11.0 (4.0)** | **−0.7** | account/edit | 통과/통과 |
| 568 | MUT | 시간초과×3 | — | 시간초과×3 | — | — | project/member_list | 오류/오류 |
| 44 | NAV | [2,2,2] | 2.0 (0.0) | [2,2,2] | 2.0 (0.0) | 0.0 | dashboard/todo_list | 통과/통과 |
| 664 | MUT | [12,14,37] | 21.0 (13.9) | [14,14,16] | **14.7 (1.2)** | **−6.3** | project/issue_detail | 실패/실패 |

ᵃ 309 V1은 trial 1에서 ERROR로 종료, 2 trial로 집계.

### 4.1 효과 발생 조건 (4건)

**과제 102** (다중 hop NAV): "a11yproject/repo의 help wanted 라벨 이슈 목록 열기". V1이 KG의 `project/issue_list` 추론과 `/-/issues` path 단축을 활용해 V0의 3-hop을 1-hop goto로 압축하고 라벨 *카테고리 존재* 만으로 dropdown을 직접 클릭한다. 라벨 *값* "help wanted"는 task에서 추출한다. **V1 mean 9.7 vs V0 mean 14.0 (Δ −4.3, 31% 단축).** 두 변종의 sd가 모두 작아 효과가 안정적으로 재현된다.

**과제 309·664 — *worst-case 안정화* 우세**: 두 과제 모두 V0의 한 trial이 catastrophic하게 폭주한다. **309**(single URL RET, "thoughtbot/administrate 최다 commit 사용자명 조회"): V0 trial이 [13, 19, **54**]로 분산이 매우 크다(sd 22.1). 54-step trial은 검색 결과를 신뢰하지 못해 commit 페이지·검색·필터 사이를 반복 왕복한 결과다. V1은 KG가 `project/main`으로 confident 추론해 commit 페이지 진입까지의 trajectory를 anchoring하여 [18, 24]로 안정화 (sd 4.2). **mean −7.7, sd 5배 감소**. **664**(issue 작성 MUT): V0 [12, 14, **37**] (sd 13.9). 37-step trial은 form 작성 중 잘못된 프로젝트 진입을 반복한 사례다. V1은 KG가 `project/issue_detail`로 직접 안내해 [14, 14, 16]으로 안정 (sd 1.2). **mean −6.3, sd 12배 감소**. 두 과제는 *KG의 anchored target이 baseline의 catastrophic trajectory를 prevent하는* 동일 메커니즘을 공유한다.

**과제 418** (status 설정 MUT): V1 mean 11.0 vs V0 mean 11.7 (Δ −0.7). 작은 평균 단축이지만 V0의 worst trial(18 step)을 V1이 15 step으로 약간 단축. KG가 `account/edit`으로 추론하는데 사용자 status는 navbar avatar 팝오버에 있어 useful adjacent에 그치지만 worst-case 페널티는 없다. 사전 가설인 능동적 오도(timeout)는 관측되지 않았다.

### 4.2 효과 미발생 조건 (1건)

**과제 156**(scope 모호 NAV) V0 mean 4.0 (sd 0) vs V1 mean 4.7 (sd 1.2). baseline이 이미 1-2 hop 효율적이라 KG가 추가 단축 여지를 못 준다. V1 trial 중 1건은 6 step으로 확장되어 KG가 *역효과*를 주는 경계 사례를 보인다.

### 4.3 효과 부정 조건 (1건)

**과제 568**(비ARIA 모달 MUT): "Invite members" 다이얼로그가 GitLab Pajamas Vue 컴포넌트로 ARIA-non-conformant이며 KG의 `project/member_list` 클래스에 modal 내부 액션 카탈로그가 비어 있다. V0/V1 모두 modal에 진입하지만 사용자 검색 입력·역할 선택을 처리하지 못해 3 trial 모두 20분 시간 초과한다. KG 기여는 modal 트리거 도달 직전까지로 한정되며 내부에서 소멸한다.

### 4.4 무영향 조건 (1건)

**과제 44**(1-step 직접 링크 NAV) V0=V1=2 step (sd 0). KG가 줄 추가 구조 정보가 없다. active control 작동 — 측정 instrument가 "차이 없음"을 출력할 능력을 가짐을 입증한다.

### 4.5 KG 효과와 평가기의 직교성

7 과제 모두에서 V0와 V1의 평가기 (응답·네트워크) 통과/실패 결과가 _동일_ 하다. 즉 KG는 step 효율에는 영향하지만 task 통과율에는 영향하지 않는다. 답 포맷 strict-match·HTTP 요청 매칭 같은 평가 인공 요소는 KG 메커니즘과 별개로 작동한다.

## 5. 결론 및 향후 연구

본 연구는 사이트별 KG의 효과를 보편 주장 없이 7-과제 probe로 특성화하였다. **효과 발생 조건은 (i) target 클래스가 KG에 정확 또는 useful adjacent로 매핑되고 (ii) baseline이 비효율적 multi-hop 또는 catastrophic 폭주 가능성이 있는 경로를 거칠 때**로 모인다. 7 과제 중 4 과제(102/309/418/664)에서 V1 평균 step이 0.7~7.7 단축됐으며, 그 중 2 과제(309, 664)에서는 V0의 catastrophic trial(54·37 step)을 V1이 일관된 범위로 안정화하여 표준편차를 5~12배 감소시키는 *worst-case 안정화* 가 효과의 주요 메커니즘이다. **효과 미발생 조건**은 baseline이 이미 효율적인 경우(156)이며, **효과 부정 조건**은 비ARIA 모달 내부에서 KG 기여 소멸(568)로 분포한다. KG는 평가기 통과율과 직교하며 step 효율에만 영향한다. 실용 함의는 KG가 _보편 가속 도구가 아니라 평균 단축과 worst-case 안정화의 조건부 도구_ 라는 점이다.

한계. N=7 과제·단일 사이트(GitLab)·단일 모델(OpenAI gpt-5.4-mini)·iterative 선정으로 일반화는 제한적이다. 향후 (i) cross-site (Reddit/Postmill) 측정으로 KG 구축 프로토콜의 사이트 무관성을 실증, (ii) cross-model 측정으로 효과 조건이 모델 의존인지 검증, (iii) 비ARIA 컴포넌트로 수집기 확장하여 모달 내부 한계 완화, (iv) 미매핑 클래스 인지 및 "unmapped" 옵션 도입으로 inferrer 페널티 억제를 진행한다.

## 참 고 문 헌

[1] S. Zhou et al., "WebArena: A Realistic Web Environment for Building Autonomous Agents," ICLR, 2024.

[2] WebArena-Verified Contributors, "WebArena-Verified: a Peer-Reviewed Benchmark for LLM Web Agent Evaluation," 2025.

[3] P. Sodhi et al., "SteP: Stacked LLM Policies for Web Actions," COLM, 2024.

[4] J. Y. Koh et al., "WALT: Web Agents that Learn Tools," arXiv:2510.01524, 2025.

[5] Z. Wang et al., "Agent Workflow Memory," ACL, 2024.
