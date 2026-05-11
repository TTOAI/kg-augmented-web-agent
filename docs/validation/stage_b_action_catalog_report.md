# Stage B — Action catalog report

**Date**: 2026-04-21

## Summary

- Classes processed: 130
- Classes with navigation actions: 124
- Total navigation actions (after dedup): 4035
- Unresolved target class (href 있지만 rule 미매칭): 21
- Self-edges (action stays in same class): 267
- Raw actions total: 8926

## Class별 action 요약 (top 20 by nav action count)

| class | instances | nav actions | internal actions | unresolved |
|---|---:|---:|---:|---:|
| `project/commit_list` | 2 | 115 | 18 | 0 |
| `project/settings_integrations` | 2 | 77 | 3 | 0 |
| `project/activity_list` | 2 | 69 | 3 | 0 |
| `project/branch_list` | 2 | 61 | 9 | 0 |
| `project/main` | 2 | 58 | 11 | 0 |
| `global/abuse_report_new_form` | 3 | 54 | 3 | 0 |
| `dashboard/project_list/yours` | 2 | 53 | 2 | 0 |
| `global/root_redirect` | 2 | 53 | 2 | 0 |
| `project/blame_view` | 2 | 53 | 74 | 0 |
| `project/settings_repository` | 2 | 52 | 20 | 0 |
| `dashboard/issue_list` | 2 | 51 | 7 | 0 |
| `dashboard/merge_request_list` | 2 | 50 | 7 | 0 |
| `project/merge_request_list` | 2 | 50 | 7 | 0 |
| `project/blob_detail` | 2 | 49 | 8 | 0 |
| `project/settings_ci_cd` | 2 | 47 | 16 | 1 |
| `project/pipeline_detail` | 2 | 46 | 17 | 4 |
| `project/commit_detail` | 2 | 42 | 30 | 0 |
| `project/settings_merge_requests` | 2 | 41 | 4 | 0 |
| `project/tag_list` | 2 | 41 | 7 | 0 |
| `project/webhook_list` | 2 | 40 | 4 | 0 |

## Example — project/issue_list navigation actions

| label | target_class | freq | href |
|---|---|---:|---|
| Dashboard | `global/root_redirect` | 2 | `/` |
| Create new... | `global/new_project_form` | 2 | `/projects/new` |
| 13 | `dashboard/issue_list` | 2 | `/dashboard/issues?assignee_username=byteblaze` |
| 8 | `dashboard/merge_request_list` | 2 | `/dashboard/merge_requests?assignee_username=byteblaze` |
| 5 | `dashboard/todo_list/pending` | 2 | `/dashboard/todos` |
| Help | `global/help_landing` | 2 | `/help` |
| Project information | `project/activity_list` | 2 | `/byteblaze/a11y-webring.club/activity` |
| Repository | `project/file_list` | 2 | `/byteblaze/a11y-webring.club/-/tree/main` |
| CI/CD | `project/pipeline_list` | 2 | `/byteblaze/a11y-webring.club/-/pipelines` |
| Security & Compliance | `project/security_config` | 2 | `/byteblaze/a11y-webring.club/-/security/configuration` |
| Deployments | `project/environment_list` | 2 | `/byteblaze/a11y-webring.club/-/environments` |
| Packages and registries | `project/package_list` | 2 | `/byteblaze/a11y-webring.club/-/packages` |
| Infrastructure | `project/cluster_list` | 2 | `/byteblaze/a11y-webring.club/-/clusters` |
| Monitor | `project/metric_dashboard` | 2 | `/byteblaze/a11y-webring.club/-/metrics` |
| Analytics | `project/value_stream_analytics` | 2 | `/byteblaze/a11y-webring.club/-/value_stream_analytics` |

## Next step (Stage C)

- Class pair → edge aggregation (예: `project/issue_list` → `project/issue_new_form`)
- Edge consolidation (majority target class vote)
- Edge trust (self-validation: 동일 edge가 여러 instance에서 관찰되면 high-trust)