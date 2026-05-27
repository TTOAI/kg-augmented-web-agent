# GitLab KG — 최종 구조 요약

**Date**: 2026-04-28 (build lineage: frozen 2026-04-16/17 → stage 2026-04-24)
**Source**: `output/validation/kg_solution/class_descriptions.json`, `output/validation/stage_b/action_catalog.json`, `docs/validation/stage_c_edge_graph_report.md`

한 화면에서 GitLab KG 구조를 파악하기 위한 통합 요약. 단계별 상세는 `docs/method/stage_{a,b,c}_*.md` 및 같은 폴더의 `stage_{a,b,c}_*_report.md` 참조.

---

## 단계별 클래스 수 변동

| 단계 | 수 | 의미 | 출처 |
|---|---:|---|---|
| Stage A | 141 | URL → 클래스 분류 규칙 | `stage_a_rules_report.md` |
| Stage finalize | **139** | 최종 catalog entry | `kg_solution/class_descriptions.json: total_classes` |
| Stage B | 130 | navigate action을 가진 클래스 | `stage_b/action_catalog.json: summary.classes` |
| Stage C | 131 | 엣지 그래프 노드 | `stage_c_edge_graph_report.md` |

141 → 139: 동일 template 공유 rule의 query-variant 병합으로 2 감소.
139 → 130: 9개 dead entry (action 미캡처, 아래 참조).
130 → 131: stage C에 unresolved target 1건 추가.

---

## 139 클래스의 분포

### scope별
| scope | 수 |
|---|---:|
| project | 90 |
| account | 14 |
| global | 10 |
| user_profile | 9 |
| user | 8 |
| site | 5 |
| ide | 3 |

### role별 (heuristic — role 필드 키워드 분류)
| role | 수 |
|---|---:|
| list | 50 |
| form | 22 |
| settings | 8 |
| edit | 5 |
| other | 54 |

### 위계 구조
- 평면 단일 클래스: 136
- Parent-variant cluster: 1 (3 entries)
  - `dashboard/todo_list` (parent) + `/pending` + `/done`
  - 의미 정보는 두 변종에 보유, parent는 URL 분류용 entry

---

## Filter coverage

- **23 / 139 (16.5%)** 클래스가 `filter_templates` 보유
- 총 29 filter_template entry (한 클래스에 다중 가능)
- 코드 키 `filter_templates`는 URL 쿼리 시그니처 관측 패턴. action_catalog의 `filter_categories` (3개 클래스) 와 다른 데이터.

### 23개 클래스 목록
| 영역 | 클래스 |
|---|---|
| dashboard | `issue_list` (2) · `merge_request_list` (4) · `project_list/yours` (1) · `todo_list/done` (1) · `todo_list/pending` (1) |
| project 목록 | `issue_list` (1) · `merge_request_list` (2) · `commit_list` (1) · `pipeline_list` (1) · `label_list` (1) · `fork_list` (1) · `tag_list` (1) · `schedule_list` (1) · `environment_list` (1) |
| project 기타 | `commit_detail` (2) · `issue_detail` (1) · `blame_view` (1) · `ci_editor` (1) · `compare_form` (1) · `security_config` (1) · `wiki` (1) |
| 기타 | `global/root_redirect` (1) · `user/profile` (1) |

(괄호 안: filter_template entry 수)

---

## 페이지 간 이동 관계 (Stage C)

- **2,731 unique edges** (source → target, distinct)
- Self-edges: 119
- Unresolved target action: 21
- Isolated source (out-degree 0): 6
- Unreachable (in-degree 0): 10

### Top 9 hubs (out-degree 기준)
| 클래스 | out | in |
|---|---:|---:|
| `project/main` | 38 | 94 |
| `project/blob_detail` | 33 | 4 |
| `project/blame_view` | 32 | 1 |
| `project/tag_list` | 32 | 15 |
| `project/settings_integrations` | 32 | 10 |
| `project/settings_integration_edit` | 32 | 3 |
| `project/settings_repository` | 32 | 9 |
| `project/settings_ci_cd` | 31 | 11 |
| `project/branch_list` | 31 | 14 |

### Trust 분포
| trust | count |
|---|---:|
| high | 2230 |
| medium | 492 |
| low | 9 |

---

## Dead entries — catalog ∋ but stage B 미캡처

총 **9개**. Catalog entry로 존재하나 navigate action이 캡처되지 않아 그래프 사용 시 dead node에 가까움.

- `dashboard/todo_list` (parent — action은 변종에 있음)
- `explore/project_list/all`
- `explore/project_list/starred`
- `explore/project_list/trending`
- `ide/mr_view`
- `project/ci_lint`
- `project/history`
- `project/milestone_edit_form`
- `project/upload_file`

---

## Coverage (139 기준)

| 필드 | 보유 | 비율 |
|---|---:|---:|
| description | 138 | 99.3% |
| url_template | 137 | 98.6% |
| filter_templates | 23 | 16.5% |
| scope | 139 | 100.0% |
| triggers | 84 | 60.4% |

description 미보유 1건 = `dashboard/todo_list` (parent, 변종으로 의미 이전).
url_template 미보유 2건 = `dashboard/todo_list/{done,pending}` (query-only variant).
