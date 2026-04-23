# Broken Evaluator Exclusions — site=gitlab

WebArena-Verified GitLab 평가에서 **evaluator의 strict match 결함**으로 정상 agent 행동이 `failure`로 기록되는 task를 수동 검증 후 여기 기록한다. 측정 이후 freeze하여 후속 비교 실험 사이에 pair를 유지한다.

---

## Freeze 원칙

1. **정식 측정 완료 직후** 이 파일을 작성·commit한다.
2. **후속 variant 측정 시작 이후 수정 금지**. 수정이 필요하면 별도 snapshot으로 추적하고 원본은 보존.
3. **모든 variant에 동일 적용**: 하나의 variant에서 broken으로 판정된 task는 다른 variant에서도 broken 간주. pair 유지로 McNemar 등 paired test의 공정성 확보.
4. **판정 기준은 객관적으로 문서화**: task별 근거(agent 로그 snippet + evaluator 실패 이유)를 1줄 이상 기록.

## 판정 기준

다음 **3가지 조건을 모두** 충족할 때만 broken으로 판정:

1. Agent 내부 `verify_done`이 SUCCESS로 판정 (`agent_response.json.status == "SUCCESS"`)
2. Evaluator strict match(`NetworkEventEvaluator` URL/파라미터, `AgentResponseEvaluator` 문자열) 실패
3. 수동 로그 검증에서 agent가 의미적으로 target state에 도달했음이 확인됨

## Broken task list

| task_id | 실패한 evaluator | 실패 이유 (요약) | 로그 증거 (경로) | 의미적 성공 근거 |
|---|---|---|---|---|
| _(측정 완료 후 채움)_ | | | | |

## 집계 규칙 (리포트)

- **Raw success rate**: 모든 task 포함 (broken도 failure로)
- **Adjusted success rate**: 이 목록의 task를 pair에서 제외 후 재계산
- 두 수치 **모두 논문 본문에 보고**. Adjusted만 보고하면 cherry-picking 반박 가능.

## Reviewer-proof 체크리스트

- [ ] 정식 측정 commit 이후 이 파일 freeze commit이 위치
- [ ] 후속 variant 측정 시작 commit 이전에 이 파일 freeze
- [ ] 각 task별 근거가 agent 로그 snippet을 참조 (log 파일 경로 + 라인 번호)
- [ ] 모든 variant 동일 적용 명시

## 참고

현재 파일은 원칙만 정의된 template 상태. 실제 broken task 식별은 baseline 재측정 완료 후 수행.
