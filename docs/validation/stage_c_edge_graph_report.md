# Stage C — Navigation edge graph report

**Date**: 2026-04-21

## Summary

- Total classes in graph: 137
- Classes in catalog (source-side): 134
- **Unique edges** (source → target, distinct): **2813**
- Self-edges (within-class): 124
- Actions with unresolved target: 17
- Isolated source classes (out-degree 0): 5
- Unreachable classes (in-degree 0): 10

## Trust distribution

| trust | count |
|---|---:|
| `high` | 2401 |
| `medium` | 149 |
| `low` | 263 |
| `unknown` | 0 |

## Top out-degree classes (hubs)

| class | out-degree | in-degree |
|---|---:|---:|
| `project/main` | 39 | 100 |
| `project/settings_integration_edit` | 32 | 3 |
| `project/settings_repository` | 32 | 10 |
| `project/blame_view` | 32 | 1 |
| `project/tag_list` | 32 | 14 |
| `project/settings_integrations` | 32 | 11 |
| `project/webhook_list` | 31 | 10 |
| `project/blob_detail` | 31 | 3 |
| `project/settings_general` | 31 | 81 |
| `project/settings_ci_cd` | 31 | 12 |
| `project/usage_quota` | 31 | 11 |
| `project/branch_list` | 31 | 14 |
| `project/settings_operations` | 31 | 12 |
| `project/settings_merge_requests` | 31 | 10 |
| `project/settings_access_tokens` | 31 | 10 |

## Top in-degree classes (destinations)

| class | in-degree | out-degree |
|---|---:|---:|
| `dashboard/todo_list/pending` | 128 | 6 |
| `global/new_project_form` | 128 | 5 |
| `dashboard/issue_list` | 128 | 9 |
| `global/root_redirect` | 128 | 15 |
| `global/help_landing` | 128 | 6 |
| `dashboard/merge_request_list` | 128 | 9 |
| `user/profile` | 101 | 27 |
| `project/main` | 100 | 39 |
| `project/merge_request_list` | 90 | 25 |
| `project/issue_list` | 90 | 26 |
| `project/value_stream_analytics` | 81 | 23 |
| `project/security_config` | 81 | 23 |
| `project/pipeline_list` | 81 | 26 |
| `project/file_list` | 81 | 29 |
| `project/environment_list` | 81 | 25 |

## Isolated source (no out-edges)

- `project/raw_file` (instance count: 2)
- `global/help_image` (instance count: 3)
- `project/upload_file` (instance count: 2)
- `project/issue_feed` (instance count: 3)
- `project/merge_request_feed` (instance count: 3)

## Unreachable classes (no in-edges)

- `global/help_image` (out-degree: 0)
- `project/upload_file` (out-degree: 0)
- `dashboard/group_list` (out-degree: 7)
- `global/snippet_list` (out-degree: 10)
- `project/cluster_new_docs` (out-degree: 24)
- `ide/mr_detail` (out-degree: 7)
- `global/import_form` (out-degree: 7)
- `project/history` (out-degree: 7)
- `project/jira_import_form` (out-degree: 23)
- `global/search_page` (out-degree: 6)

## Example edges — project/issue_list outgoing

| target | trust | actions |
|---|---|---|
| `global/root_redirect` | `high` | Dashboard |
| `global/new_project_form` | `high` | Create new... |
| `dashboard/issue_list` | `high` | 13 |
| `dashboard/merge_request_list` | `high` | 8 |
| `dashboard/todo_list/pending` | `high` | To-Do List |
| `global/help_landing` | `high` | Help |
| `project/activity_list` | `high` | Project information |
| `project/file_list` | `high` | Repository |
| `project/issue_board` | `high` | Boards |
| `project/issue_detail` | `high` | Service Desk |
| `project/milestone_list` | `high` | Milestones |
| `project/pipeline_list` | `high` | CI/CD |
| `project/security_config` | `high` | Security & Compliance |
| `project/environment_list` | `high` | Deployments |
| `project/package_list` | `high` | Packages and registries |
| `project/cluster_list` | `high` | Infrastructure |
| `project/metric_dashboard` | `high` | Monitor |
| `project/value_stream_analytics` | `high` | Analytics |
| `project/wiki` | `high` | Wiki |
| `project/snippet_list` | `high` | Snippets |
| `project/settings_general` | `high` | Settings |
| `project/issue_feed` | `high` | Subscribe to RSS feed |
| `project/issue_new_form` | `high` | New issue |
| `user/profile` | `medium` | Byte Blaze, The A11Y Project |
| `project/main` | `low` | A a11y-syntax-highlighting, a11y-syntax-highlighting, A a11y-webring.club |
| `project/merge_request_list` | `low` | Merge requests 0, Merge requests 1, Merge requests 10 |

## Next (Solution 2)

- Adjacency list / reverse adjacency 이미 저장됨 (`edge_graph.json`)
- BFS from (current_class) to (target_class) 가능
- Trust-weighted path ranking 가능
- Path → agent hint (URL sequence) 변환은 Solution 2의 별도 단계