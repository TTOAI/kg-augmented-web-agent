# 사이트별 구조 지식 그래프는 웹 에이전트에 언제 도움이 되는가 — 효과·무효·부정 조건의 7-과제 특성화

## When Does a Site-Specific Structural Knowledge Graph Help an LLM Web Agent? — Characterization of Effective, Null, and Adverse Conditions on Seven GitLab Tasks

---

## 요 약

LLM 기반 웹 에이전트가 같은 사이트의 페이지 구조를 매번 관측에서 재발견하는 비효율을 해소하기 위해, 사이트 구조를 사전 계산된 지식 그래프(Knowledge Graph, KG)로 외부화하고 페이지 클래스 식별자를 숨긴 최소 힌트로 주입하는 접근을 제시한다. 본 연구는 KG의 *우월성을 주장하지 않고* WebArena-Verified GitLab의 7개 사전 등록 과제를 V0(KG 미사용)와 V1(KG 사용)로 각 3 trial 측정하여 KG 효과의 발생·무효·부정 조건을 특성화한다. (1) **효과 조건 1건**: 다중 hop 탐색 과제에서 V1이 V0의 15 step을 9 step으로 단축. (2) **무효·부정 조건 5건**: KG 미매핑 클래스 또는 baseline이 이미 효율적인 과제에서 +0~+2 step의 작은 비용 또는 동등한 step. (3) **부정 조건 1건**: 비ARIA 모달 내부에서 KG 기여가 소멸하며 두 변종 모두 시간 초과. 모든 과제에서 KG는 평가기 통과율을 변경하지 않으며 step 효율에만 영향한다. 결론적으로 KG는 보편적 가속이 아니라 *조건부 단축 도구*이며, 사전 진단 없이 적용하면 작은 페널티를 유발할 수 있다.

주요어: 지식 그래프, 웹 에이전트, 사이트별 구조, 힌트 주입, 효과 조건 특성화

---

## 1. 서 론

LLM 기반 웹 에이전트[1, 2]는 매 서브목표마다 (1) 어느 페이지 클래스가 과제를 담당하는지, (2) 그 페이지에 어떤 필터·버튼이 있는지, (3) 어느 URL 경로가 단축인지를 관측만으로 재발견한다. 이 반복은 같은 사이트의 과제마다 누적된다.

선행 연구는 사이트 지식의 사전 자산화에 집중했다. SteP[3]은 수동 정책 스택을, WALT[4]는 역공학 도구 함수를, AWM[5]은 실행 궤적 재사용을 제공한다. 본 연구는 *사이트 구조 자체*를 KG로 외부화하고 최소 힌트로 주입한다.

본 논문은 KG가 일반적으로 도움이 된다고 *주장하지 않는다*. 대신 다음 질문을 묻는다. **KG는 어떤 조건에서 step을 줄이고 어떤 조건에서 효과가 없거나 작은 페널티를 유발하는가?** 기여는 (C1) ARIA 표준 기반 사이트에 무관한 KG 구축 프로토콜과 "방향만 노출, 구체값은 에이전트가 직접 찾는다" 라는 최소 힌트 설계 원칙, (C2) 7-과제 사전 등록 측정으로 효과 발생 조건 1건·무효·부정 조건 6건을 정직하게 특성화한 점, (C3) KG 효과가 평가기 통과율과 직교한다는 관찰이다.

## 2. 방 법

### 2.1 KG 구축

세 단계로 수행한다. 1단계는 출발 URL 집합에서 너비 우선 탐색으로 페이지를 수집하고 URL 규칙으로 페이지 클래스를 할당한다. 2단계는 각 클래스 샘플에서 ARIA 역할 속성(메뉴 항목, 옵션, 탭, 대화상자 팝업 트리거)과 표준 폼 요소만을 근거로 액션·필터·대화상자를 수집한다. 의도적으로 사이트에 무관하며 비표준 컴포넌트는 포착하지 않는 대신 단일 구현으로 여러 사이트에 이식된다. 3단계는 URL 템플릿, 범위, 트리거 문구, 필터 카테고리를 결합해 클래스 카탈로그를 만든다. 현 GitLab KG는 139 클래스·23 클래스의 필터 카테고리·2,731 전이 엣지를 담는다.

### 2.2 실행 시점 통합과 최소 힌트 — "방향만, 구체값은 에이전트가"

실행 시점에서 KG는 세 모듈로 소비된다. **타겟 클래스 추론기**는 K=3 자기 일관성 LLM 호출로 task에서 목표 클래스를 결정한다. **경로 탐색기**는 6단계 단계별 후퇴로 현재 클래스에서 목표 클래스까지의 경로를 탐색한다. **힌트 생성기**는 경로 단축 URL과 현재 페이지 표면 정보(액션 카탈로그·필터 카테고리 존재)를 관측 메시지에 주입한다.

설계 원칙은 *KG는 구조적 방향만 노출하고 구체값은 에이전트가 페이지 상호작용에서 직접 찾는다* 이다. 최소 힌트 모드(`KG_MODE=minimal`)는 (i) URL 파라미터 레시피, (ii) 페이지 클래스 식별자, (iii) 필터 카테고리의 예시 값·옵션 값·기본 값을 모두 억제한다. 이 분리는 V1의 step 단축이 KG의 *구조 정보 우월*에서 오는지 *KG가 정답을 흘려서* 오는지 분리한다.

## 3. 실험 설정

WebArena-Verified GitLab 자가 호스팅 인스턴스를 사용한다. 에이전트 LLM은 OpenAI `gpt-5.4-mini` 단일 모델이다. 변종은 V0(`KG_ENABLED=0`)와 V1(`KG_ENABLED=1 KG_MODE=minimal`) 둘이며 각 (과제 × 변종) cell에 3 trial을 측정한다. 측정 방법론은 *task fixed-set 사전 lock이 아니라* iterative round + 약한 사전 등록이다. round 시작 전에 (a) 선정 규칙(archetype gap 기반), (b) stopping rule(세 archetype에 ≥1 task + 누적 task ≤ 8), (c) 모든 결과 보고 의무를 git에 commit한다. 본 측정은 Round 1·2 합계 7 과제 × 2 변종 × 3 trial = 42 trial이다.

## 4. 결 과

표 1은 7 과제의 cell-level outcome이다. step은 3 trial median이며 [min, max] 범위를 병기한다.

| 과제 ID | 유형 | V0 step | V1 step | KG 추론 클래스 | 평가기 V0/V1 |
|---|---|---|---|---|---|
| 102 | NAV | 15 [11,16] | **9 [8,12]** | project/issue_list | 실패/실패 |
| 156 | NAV | 4 [4,4] | 4 [4,6] | dashboard/merge_request_list | 통과/통과 |
| 309 | RET | 19 [13,54] | 21 [18,24] | project/main | 실패/실패 |
| 418 | MUT | 9 [8,18] | 11 [7,15] | account/edit | 통과/통과 |
| 568 | MUT | 시간초과 | 시간초과 | project/member_list | 오류/오류 |
| 44 | NAV | 2 [2,2] | 2 [2,2] | dashboard/todo_list | 통과/통과 |
| 664 | MUT | 14 [12,37] | 14 [14,16] | project/issue_detail | 실패/실패 |

이하 4개 조건으로 구분해 정성 분석한다.

### 4.1 효과 발생 조건 (1건)

**과제 102** (다중 hop NAV): "a11yproject/repo의 help wanted 라벨 이슈 목록 열기". V0는 프로젝트 진입→Issues→라벨 dropdown 탐색→라벨 적용의 3-hop을 평균 15 step에 처리한다. V1은 KG가 `project/issue_list`로 추론·`/-/issues` 경로를 단축으로 노출하고 *라벨 카테고리 존재* 만 알려주어 에이전트가 그 dropdown을 직접 클릭한다. 라벨 *값* "help wanted"는 task에서 추출한다. **V1 9 step (40% 단축)**. 단, 두 변종 모두 평가기는 strict-match로 실패하여 step 효율 향상이 통과율 변화로 이어지지 않는다.

### 4.2 효과 미발생 조건 (3건)

**과제 156**(scope 모호 NAV) 두 변종 모두 4 step. baseline이 이미 1-2 hop 효율적이라 KG가 추가 가치를 못 준다. **과제 309**(single URL RET) V1=21 vs V0=19 (Δ +2). KG가 `project/main`으로 추론했으나 contributor graph 페이지(`/-/graphs/{branch}`)로의 직접 안내가 약하고 V0는 검색 기능을 활용해 더 짧게 도달한다. **과제 418**(미매핑 MUT) V1=11 vs V0=9 (Δ +2). 사용자 status 설정 UI가 navbar avatar 팝오버에 위치하나 KG에 매핑되어 있지 않다. KG는 `account/edit`으로 confident 추론하지만 useful adjacent에 그쳐 V0보다 +2 step 비용이 발생한다. 사전 가설인 능동적 오도(timeout)는 관측되지 않았다.

### 4.3 효과 부정 조건 (1건)

**과제 568**(비ARIA 모달 MUT): "Invite members" 다이얼로그가 GitLab Pajamas Vue 컴포넌트로 ARIA-non-conformant이며 KG의 `project/member_list` 클래스에 modal 내부 액션 카탈로그가 비어 있다. V0/V1 모두 modal에 진입하지만 사용자 검색 입력·역할 선택을 처리하지 못해 20분 시간 초과한다. KG 기여는 modal 트리거 도달 직전까지로 한정되며 modal 내부에서 소멸한다.

### 4.4 무영향 조건 (2건)

**과제 44**(1-step 직접 링크 NAV) **과제 664**(텍스트 콘텐츠 중심 MUT) 두 변종 모두 동일 step. KG가 줄 구조 정보가 없거나 task 노력이 텍스트 입력에 있어 KG-orthogonal하다. active control이 정상 작동한다.

### 4.5 KG 효과와 평가기의 직교성

7 과제 모두에서 V0와 V1의 평가기 (응답·네트워크) 통과/실패 결과가 *동일* 하다. 즉 KG는 step 효율에는 영향하지만 task 통과율에는 영향하지 않는다. 답 포맷 strict-match·HTTP 요청 매칭 같은 평가 인공 요소는 KG 메커니즘과 별개로 작동한다.

## 5. 결론 및 향후 연구

본 연구는 사이트별 KG의 효과를 보편 주장 없이 7-과제 probe로 특성화하였다. **효과 발생 조건은 (i) target 클래스가 KG에 정확 매핑되고 (ii) baseline이 비효율적 multi-hop 경로를 거치며 (iii) KG가 직접 path goto를 줄 수 있을 때**로 좁다. **효과 미발생·부정 조건은 (i) target 미매핑으로 inferring이 adjacent 클래스로 routing되어 +2 step 페널티, (ii) baseline이 이미 1-2 hop 효율적인 경우, (iii) 비ARIA 컴포넌트 내부**로 분포한다. KG는 평가기 통과율과 직교하며 step 효율에만 영향한다. 실용 함의는 KG가 *보편 가속 도구가 아니라 조건부 단축 도구* 라는 점이며, 적용 시 "어느 과제에서 도움이 될 것인가" 사전 진단이 필요하다.

한계. N=7 과제·단일 사이트(GitLab)·단일 모델(OpenAI gpt-5.4-mini)·iterative 선정으로 일반화는 제한적이다. 향후 (i) cross-site (Reddit/Postmill) 측정으로 KG 구축 프로토콜의 사이트 무관성을 실증, (ii) cross-model 측정으로 효과 조건이 모델 의존인지 검증, (iii) 비ARIA 컴포넌트로 수집기 확장하여 모달 내부 한계 완화, (iv) 미매핑 클래스 인지 및 "unmapped" 옵션 도입으로 inferrer 페널티 억제를 진행한다.

## 참 고 문 헌

[1] S. Zhou et al., "WebArena: A Realistic Web Environment for Building Autonomous Agents," ICLR, 2024.

[2] WebArena-Verified Contributors, "WebArena-Verified: a Peer-Reviewed Benchmark for LLM Web Agent Evaluation," 2025.

[3] P. Sodhi et al., "SteP: Stacked LLM Policies for Web Actions," COLM, 2024.

[4] J. Y. Koh et al., "WALT: Web Agents that Learn Tools," arXiv:2510.01524, 2025.

[5] Z. Wang et al., "Agent Workflow Memory," ACL, 2024.
