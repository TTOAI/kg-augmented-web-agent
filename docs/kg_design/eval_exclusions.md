# Broken Evaluator Exclusions — site=gitlab

WebArena-Verified GitLab 평가에서 **evaluator의 strict match 결함**으로 정상 agent 행동이 `failure`로 기록되는 task를 수동 검증 후 여기 기록한다. 이 목록은 **baseline 재측정 직후에 freeze**되며, M5(KG variant)에도 **동일하게 적용**되어 pair를 유지한다.

관련 docs: `06_evaluation_protocol.md §2-2 Broken eval task`, `§6 Evaluator quirks`, `§4-5 Per-run paired 이진화 규칙`.

---

## Freeze 원칙

1. **Baseline 재측정 완료 직후** 이 파일을 작성·commit한다.
2. **M5 KG variant 측정 시작 이후 수정 금지**. 수정이 필요하면 별도 snapshot으로 추적하고 원본은 보존.
3. **양 variant에 동일 적용**: baseline에서 broken으로 판정된 task는 M5에서도 broken 간주. pair 유지로 McNemar test의 공정성 확보.
4. **판정 기준은 객관적으로 문서화**: task별 근거(agent 로그 snippet + evaluator 실패 이유)를 1줄 이상 기록.

## 판정 기준 (06 §2-2 전재)

다음 **3가지 조건을 모두** 충족할 때만 broken으로 판정:

1. Agent의 내부 `verify_done`이 SUCCESS로 판정 (`agent_response.json.status == "SUCCESS"`)
2. Evaluator strict match(`NetworkEventEvaluator` URL/파라미터, `AgentResponseEvaluator` 문자열) 실패
3. 수동 로그 검증에서 agent가 의미적으로 target state에 도달했음이 확인됨

## Broken task list (아직 미작성)

> _baseline 재측정 완료 후 채움. 현재는 placeholder._

| task_id | 실패한 evaluator | 실패 이유 (요약) | 로그 증거 (경로) | 의미적 성공 근거 |
|---|---|---|---|---|
| _(TBD)_ | _(TBD)_ | _(TBD)_ | _(TBD)_ | _(TBD)_ |

## 집계 규칙 (리포트)

- **Raw success rate**: 모든 task 포함 (broken도 failure로)
- **Adjusted success rate**: 이 목록의 task를 pair에서 제외 후 재계산
- 두 수치 **모두 논문 본문에 보고**. Adjusted만 보고하면 cherry-picking 반박 가능.

## Reviewer-proof 체크리스트

- [ ] baseline 재측정 commit 이후 이 파일 freeze commit이 위치
- [ ] M5 측정 시작 commit 이전에 이 파일 freeze
- [ ] 각 task별 근거가 agent 로그 snippet을 참조 (`output/baseline_n3/N*/{task_id}/webarena_verified.log` 라인 번호)
- [ ] 양 variant 동일 적용 명시

## 현재 상태

**baseline N=3 재측정 대기 중**. 이전 측정(commit `ebbca4f` 이전)은 N2·N3가 OpenAI `insufficient_quota`로 오염돼 무효. 재측정 완료 후 이 파일을 채우고 commit한다.
