# Stage B — Action catalog report

**Date**: 2026-04-21

## Summary

- Classes processed: 134
- Classes with navigation actions: 129
- Total navigation actions (after dedup): 4816
- Unresolved target class (href 있지만 rule 미매칭): 17
- Self-edges (action stays in same class): 365
- Raw actions total: 14927

## Class별 action 요약 (top 20 by nav action count)

| class | instances | nav actions | internal actions | unresolved |
|---|---:|---:|---:|---:|
| `project/commit_list` | 3 | 156 | 26 | 0 |
| `project/merge_request_list` | 3 | 94 | 6 | 0 |
| `explore/project_list/starred` | 3 | 93 | 10 | 0 |
| `user/profile` | 3 | 83 | 4 | 0 |
| `project/settings_integrations` | 3 | 82 | 2 | 0 |
| `project/branch_list` | 3 | 76 | 8 | 0 |
| `project/main` | 3 | 75 | 11 | 0 |
| `explore/project_list/all` | 3 | 73 | 4 | 0 |
| `project/tag_list` | 3 | 62 | 6 | 0 |
| `project/settings_repository` | 3 | 57 | 19 | 0 |
| `project/starrer_list` | 3 | 57 | 5 | 0 |
| `dashboard/project_list/yours` | 3 | 55 | 3 | 0 |
| `global/root_redirect` | 3 | 55 | 3 | 0 |
| `dashboard/issue_list` | 3 | 54 | 9 | 0 |
| `project/merge_request_detail` | 3 | 54 | 37 | 0 |
| `dashboard/merge_request_list` | 3 | 53 | 8 | 0 |
| `project/settings_ci_cd` | 3 | 53 | 17 | 1 |
| `project/settings_general` | 3 | 53 | 15 | 3 |
| `project/milestone_list` | 3 | 51 | 3 | 0 |
| `project/merge_request_commits` | 3 | 49 | 8 | 0 |

## Example — project/issue_list navigation actions

| label | target_class | freq | href |
|---|---|---:|---|
| Dashboard | `global/root_redirect` | 3 | `/` |
| Create new... | `global/new_project_form` | 3 | `/projects/new` |
| 13 | `dashboard/issue_list` | 3 | `/dashboard/issues?assignee_username=byteblaze` |
| 8 | `dashboard/merge_request_list` | 3 | `/dashboard/merge_requests?assignee_username=byteblaze` |
| To-Do List | `dashboard/todo_list/pending` | 3 | `/dashboard/todos` |
| Help | `global/help_landing` | 3 | `/help` |
| Project information | `project/activity_list` | 3 | `/byteblaze/a11y-syntax-highlighting/activity` |
| Repository | `project/file_list` | 3 | `/byteblaze/a11y-syntax-highlighting/-/tree/main` |
| List | `project/issue_list` | 3 | `/byteblaze/a11y-syntax-highlighting/-/issues` |
| Boards | `project/issue_board` | 3 | `/byteblaze/a11y-syntax-highlighting/-/boards` |
| Service Desk | `project/issue_detail` | 3 | `/byteblaze/a11y-syntax-highlighting/-/issues/service_desk` |
| Milestones | `project/milestone_list` | 3 | `/byteblaze/a11y-syntax-highlighting/-/milestones` |
| CI/CD | `project/pipeline_list` | 3 | `/byteblaze/a11y-syntax-highlighting/-/pipelines` |
| Security & Compliance | `project/security_config` | 3 | `/byteblaze/a11y-syntax-highlighting/-/security/configuration` |
| Deployments | `project/environment_list` | 3 | `/byteblaze/a11y-syntax-highlighting/-/environments` |

## Next step (Stage C)

- Class pair → edge aggregation (예: `project/issue_list` → `project/issue_new_form`)
- Edge consolidation (majority target class vote)
- Edge trust (self-validation: 동일 edge가 여러 instance에서 관찰되면 high-trust)