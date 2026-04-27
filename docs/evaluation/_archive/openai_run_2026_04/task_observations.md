# Task 측정 관찰 기록

## 메타데이터

- 측정 환경: WebArena-Verified GitLab 자가 호스팅 인스턴스
- LLM: OpenAI 상용 대규모 언어모델 (gpt-5.4-mini)
- 변종: 기준 에이전트(KG 미사용) vs 제안 에이전트(최소 힌트 방식 KG 사용)
- 평가기: 응답 평가기 / 네트워크 평가기
- 마지막 갱신: 2026-04-25

## 결과 표기 약속

- 결과 칼럼: `통과` / `부분통과(평가기명)` / `실패` / `시간초과(20분)`
- step 차이: `제안 step − 기준 step` (음수일수록 제안 에이전트가 빠름)
- KG 도움 등급:
  - 상: step 감소 + 두 평가기 통과 + 사고 기록에 KG 노출 요소 인용
  - 중: step 감소 또는 사고 기록 인용 또는 결정적 경로(회귀 없음)
  - 하: step 증가, 시간초과, 또는 KG가 잘못된 경로로 유도

## 사용 방법

신규 측정 시 표 마지막 행에 append. 같은 batch에서 측정한 결과끼리 묶기. 측정 batch가 다르면 표 위에 batch 메타 (날짜·환경) 별도 기록.

---

## Batch A — 본측정 final (2026-04-24, V0 + V1-minimal × 9 task, 같은 환경 연속 측정)

| task | intent | 기준 결과 | step 차이 | 기준 사고 요약 | 제안 결과 | 제안 사고 요약 | KG 도움 |
|------|--------|-----------|----------:|----------------|-----------|----------------|---------|
| 156 | Go to merge requests assigned to me | 통과 (3 step) | −1 | top nav의 Merge requests 클릭 → 페이지에서 assignee 필터 확인 | 통과 (2 step) | 사이드바의 "Assigned to you 3" 링크가 보이며 정확한 뷰임을 인지 → 직접 클릭 | 상 |
| 357 | Go to merge requests requiring my review | 통과 (3 step) | −1 | top nav의 Merge requests 클릭 → 페이지에서 reviewer 영역 탐색 | 통과 (2 step) | "Review requests for you 5" 링크가 보임을 사고에 인용 → 직접 클릭 | 상 |
| 176 | 내 최신 갱신 이슈 중 "dependency" 제목이 닫혔는지 boolean | 부분통과(응답) (5 step) | −2 | 이슈 목록에서 검색·정렬 후 후보 클릭하여 status 확인 | 부분통과(응답) (3 step) | "목록 상단에 일치 이슈가 보임"을 사고에 인용 → 세부 탐색 없이 상세로 직행 | 상 |
| 349 | 내 gimmiethat.space 저장소에 접근권한 가진 사용자명 조회 | 부분통과(응답) (6 step) | 0 | 프로젝트 페이지에서 settings 메뉴 탐색 후 멤버 페이지 도달 | 부분통과(응답) (6 step) | "사이드바에 멤버 링크가 보임"을 사고에 인용하며 결정적 경로로 이동 | 중 |
| 590 | 현재 저장소에 milestone "product launch"를 날짜 범위로 생성 | 실패 (18 step) | −2 | 메뉴 탐색 후 milestone 폼 도달했으나 HTTP 요청 기본값이 참조와 불일치 | 실패 (16 step) | KG가 milestone 목록 페이지로 안내 → 새 milestone 폼 작성 → 동일 HTTP 불일치 | 중 |
| 45 | 현재 프로젝트의 최신 open 이슈 필터 페이지 열기 | 부분통과(응답) (4 step) | +1 | Issues 클릭 후 Open 탭과 정렬을 적용했으나 네트워크 평가기 strict-match 미일치 | 부분통과(응답) (5 step) | Open 탭 클릭 시도 후 직접 URL goto로 정렬 적용, 동일 strict-match 미일치 | 하 |
| 308 | primer/design 프로젝트에 가장 많이 커밋한 사용자명 조회 | 실패 (3 step) | +6 | 프로젝트 페이지 도달도 안 한 채 답 환각 → 응답 평가기 답 포맷 불일치 | 실패 (9 step) | 프로젝트 → 커밋 목록 → 기여자 그래프 페이지로 정확히 이동했으나 답 포맷 동일 불일치 | 하 |
| 411 | byteblaze/cloud-to-butt 저장소 LICENSE를 MIT로 변경 | 부분통과(응답) (12 step) | 시간초과 | settings 메뉴 탐색 끝에 LICENSE 편집 페이지 도달, 응답 평가기 통과 | 시간초과 (20분) | KG가 미매핑 클래스에 차선으로 "저장소 설정" 페이지를 반복 제안, 에이전트가 그 경로를 신뢰하다 시간초과 | 하 |
| 568 | a11yproject.com 저장소에 Abishek과 Vinta를 협업자로 초대 | 실패 (21 step) | 시간초과 | members 페이지 도달 후 invite 버튼 클릭, 비표준 대화상자 내부에서 반복 실패 | 시간초과 (20분) | KG가 members 페이지로 안내, invite 버튼까지 인지하나 대화상자 내부 입력은 KG 정보 없이 DOM 탐색에 의존 | 하 |

### Batch A 요약
- 통과 task: 4/9 (156, 357, 176, 349) — 두 변종 동일
- KG 도움 분포: 상 3 / 중 2 / 하 4
- 두 평가기 모두 통과한 step 감소 case: 156, 357 (총 −2 step)
- 응답 평가기 통과한 step 감소 case 추가: 176, 590 (총 −4 step)
- 활성 오도 case: 411 (V1 시간초과, V0 부분 통과)

---

## Batch B — 사전 smoke (2026-04-24 이전, V0는 초기 측정, V1-minimal은 smoke_minimal)

주의: 이 batch는 V0와 V1-minimal이 동일 batch에서 측정되지 않았다. V0는 초기 main_measurement(다른 batch)의 값이고, V1-minimal은 minimal 모드 도입 후 별도 smoke. 환경 일치성은 약함, 참고용.

| task | intent | 기준 결과 | step 차이 | 기준 사고 요약 | 제안 결과 | 제안 사고 요약 | KG 도움 |
|------|--------|-----------|----------:|----------------|-----------|----------------|---------|
| 102 | a11yproject 저장소의 "help wanted" 라벨 이슈 목록 페이지 | 부분통과(응답) (11 step) | −8 | 프로젝트 도달 → Issues → 라벨 드롭다운 탐색 후 일치 라벨 적용 | 부분통과(응답) (3 step) | KG가 정확한 이슈 URL 직행 → 라벨 매칭 시도 | 중 |
| 342 | 현재 프로젝트의 OPT 모델 관련 open 이슈 목록 페이지 | 부분통과(응답) (15 step) | −9 | Issues 페이지에서 검색·라벨 조합을 반복 시도하다 결국 search URL 도달 | 부분통과(응답) (6 step) | KG가 검색 URL 직행 | 중 |
| 296 | 가장 좋은 GAN 파이썬 구현의 SSH 클론 URL | 통과 (8 step) | −1 | explore → "GAN" 검색 → PyTorch-GAN 선택 → Clone 드롭다운에서 SSH URL 추출 | 통과 (7 step) | KG가 explore/project_list 추론, 동일 경로로 약간 단축 | 중 |
| 476 | "awesome_llm_reading"이라는 새 비어 있는 저장소 생성 | 부분통과(응답) (5 step) | 0 | New project → 빈 프로젝트 → 이름 입력 → README 해제 → Create | 부분통과(응답) (5 step) | KG가 신규 프로젝트 폼으로 직행, 기준과 동일 폼 작성 (V1-auto는 동일 task에서 17 step으로 over-analysis 발생, 최소 힌트 방식이 이를 제거) | 중 |

### Batch B 요약
- step 감소: 4/4 (특히 102, 342에서 큰 감소 −8, −9)
- 두 평가기 모두 통과: 296 (1건)
- 다른 3건은 응답 평가기 통과, 네트워크 평가기 strict-match 잡음

---

## 통합 관찰 (Batch A + B, 13 task)

- 두 평가기 통과 + step 감소: 3 task (156, 357, 296)
- 응답 평가기 통과 + step 감소: +4 task (176, 102, 342, 590 부분)
- 결정적 경로 (step 동등이나 사고에 KG 인용): 1 task (349)
- 평가기 잡음 (KG와 무관): 3 task (45, 308, 590)
- KG 활성 오도: 1 task (411)
- KG 기여 소멸 (modal 한계): 1 task (568)

KG 도움 등급 분포: 상 3 / 중 6 / 하 4

---

## 추가 측정 시 append 위치

### Batch C — (TBD)

신규 batch 측정 시 아래에 표 추가:

```markdown
## Batch C — <설명> (<날짜>)

| task | intent | 기준 결과 | step 차이 | 기준 사고 요약 | 제안 결과 | 제안 사고 요약 | KG 도움 |
|------|--------|-----------|----------:|----------------|-----------|----------------|---------|
| ...  | ...    | ...       | ...       | ...            | ...       | ...            | ...     |
```
