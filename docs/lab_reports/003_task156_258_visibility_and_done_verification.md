# Lab Report 003 — Task 156·258: Visibility 필터, DOM 변경 감지, Done 검증

**날짜**: 2026-04-07  
**목적**: Task 156(드롭다운 상호작용 실패), Task 258(premature done) 분석 및 수정. Baseline 한계와 prior 필요 지점 식별.

---

## 002 대비 변경 사항 요약

### 관측 레이어 개선

| 개선 | 내용 |
|---|---|
| Visibility 필터 | `extract_ax_links()` JS에 `el.offsetWidth > 0 \|\| el.offsetHeight > 0` 추가 → 숨겨진 드롭다운 항목 제거 |
| innerText 정규화 | `(el.innerText \|\| '').replace(/\s+/g, ' ').trim()` → `\n` 포함 링크명 정리 |

### 실행 레이어 개선

| 개선 | 내용 |
|---|---|
| DOM 변경 감지 | 액션 전후 `set(links)`, `set(buttons)` 비교 → URL 불변이어도 "page content changed" 피드백 |
| 피드백 세분화 | "URL unchanged" → "page content changed" / "no visible change" 구분 |

### 프롬프트 개선

| 개선 | 내용 |
|---|---|
| Done 검증 지침 | done 선언 전 현재 페이지 상태(URL, 제목, 링크, 버튼, 필터)와 task 목표의 정확한 일치 확인 요구 |

---

## Task 156: 드롭다운 상호작용

### 실험 조건

| 항목 | 값 |
|---|---|
| Task ID | 156 |
| Intent | "Go to the merge requests assigned to me" |
| Site | GitLab (`http://localhost:8023`) |
| Task Type | NAVIGATE |

### 수정 전 실패 원인

1. **숨겨진 링크 노출**: 드롭다운 내부의 `'Assigned to you 3'`이 DOM에 존재하지만 숨겨진 상태로 관측에 포함됨
2. **클릭 실패 반복**: LLM이 숨겨진 요소를 5회 클릭 시도 → 전부 "element not found"
3. **변화 미감지**: 'Merge requests' 클릭으로 드롭다운이 열려도 URL 불변 → "URL unchanged" → LLM이 클릭 무효로 판단

### 수정 후 실행 트레이스

```
step=1  url=http://localhost:8023/
step=1  action=click  target='Merge requests'
step=1  result=click 'Merge requests': page content changed    ← DOM 변경 감지
step=2  url=http://localhost:8023/
step=2  links=[..., 'Assigned to you 3 → /dashboard/merge_requests', ...]  ← visibility 필터로 드롭다운 열린 후에만 노출
step=2  action=click  target='Assigned to you'
step=2  result=click 'Assigned to you': navigated to .../merge_requests?assignee_username=byteblaze
step=3  action=done → SUCCESS
```

### 결과

| 지표 | 수정 전 | 수정 후 |
|---|---|---|
| 결과 | FAIL (5스텝 소진) | **SUCCESS (3스텝)** |
| 실패 원인 | 숨겨진 요소 반복 클릭 | - |
| 드롭다운 인식 | URL unchanged → 무시 | **page content changed** |

### 수정별 기여도

| 수정 | 효과 |
|---|---|
| Visibility 필터 | step 1에서 숨겨진 'Assigned to you' 제거 → LLM이 먼저 'Merge requests' 클릭 유도 |
| DOM 변경 감지 | 드롭다운 열림을 "page content changed"로 인식 → step 2에서 새 링크 활용 |

---

## Task 258: Premature Done

### 실험 조건

| 항목 | 값 |
|---|---|
| Task ID | 258 |
| Intent | "Open the public projects listing" |
| Site | GitLab (`http://localhost:8023`) |
| Task Type | NAVIGATE |
| 정답 URL | `/explore?visibility_level=20` |

### 실행 결과

#### 시도 1: done 프롬프트 개선 전

```
step=1  url=http://localhost:8023/
step=1  action=done  reasoning='The public projects listing is already visible'
→ FAIL (대시보드를 public projects로 오인)
```

#### 시도 2: done 프롬프트 개선 후 (1차)

```
step=1  url=http://localhost:8023/
step=1  action=click  target='Explore'
step=1  result=navigated to http://localhost:8023/explore
step=2  url=http://localhost:8023/explore
step=2  action=done  reasoning='The public projects listing is now open on the Explore page'
→ FAIL (eval: /explore는 도달했으나 ?visibility_level=20 누락)
```

#### 시도 3: done 프롬프트 개선 후 (2차)

```
step=1  url=http://localhost:8023/
step=1  action=done  reasoning='The current page is the projects dashboard showing a public projects list'
→ FAIL (비결정성: 같은 프롬프트인데 다시 premature done)
```

### Eval 상세

```json
{
  "AgentResponseEvaluator": "success (1.0)",
  "NetworkEventEvaluator": "failure (0.0) — expected query_params: {visibility_level: ['20']}"
}
```

에이전트는 SUCCESS를 보고했으나, 실제 네트워크 이벤트에 `visibility_level=20` 쿼리 파라미터가 없어서 eval 실패.

### 분석: 프롬프트 한계

| 단계 | 프롬프트로 해결 가능? | 설명 |
|---|---|---|
| 대시보드 → /explore 이동 | △ (비결정적) | 때로는 Explore 클릭, 때로는 대시보드에서 done |
| /explore → ?visibility_level=20 | ✗ | "Any" 버튼이 visibility 필터라는 걸 아는 건 사이트 지식 |

### 결론

**Task 258은 prior가 필요한 문제로 분류.**

- 프롬프트 강화로 `/explore` 도달 확률은 올릴 수 있으나 안정적이지 않음
- `?visibility_level=20` 필터 적용은 사이트 특화 지식 없이 불가능
- Prior에서 "public projects = /explore?visibility_level=20" 매핑 제공 시 해결 가능

---

## 변경 파일 요약

| 파일 | 변경 |
|---|---|
| `runtime/browser.py` | `extract_ax_links()`: visibility 필터, innerText 정규화 |
| `runtime/executor.py` | `_execute_with_llm()`: prev_links/prev_buttons 추적, content changed 피드백 |
| `runtime/llm.py` | `build_system_prompt()`: done 검증 지침 추가 |

---

## 잔존 문제 및 다음 액션

1. **Task 258**: prior 필요 → runtime prior store에 사이트 지식 등록 후 재실험
2. **다른 task 실험 계속**: 357, 45, 339 등으로 baseline 범위 확인
3. **Prior 효과 측정**: baseline이 못 푸는 문제(258 등)에 prior 적용 후 비교
