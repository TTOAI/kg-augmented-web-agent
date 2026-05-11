# Stage C — Navigation edge graph report

**Date**: 2026-04-21

## Summary

- Total classes in graph: 131
- Classes in catalog (source-side): 130
- **Unique edges** (source → target, distinct): **2731**
- Self-edges (within-class): 119
- Actions with unresolved target: 21
- Isolated source classes (out-degree 0): 6
- Unreachable classes (in-degree 0): 10

## Trust distribution

| trust | count |
|---|---:|
| `high` | 2230 |
| `medium` | 492 |
| `low` | 9 |
| `unknown` | 0 |

## Top out-degree classes (hubs)

| class | out-degree | in-degree |
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
| `project/webhook_list` | 31 | 9 |
| `project/settings_operations` | 31 | 11 |
| `project/settings_merge_requests` | 31 | 10 |
| `project/usage_quota` | 31 | 10 |
| `project/settings_access_tokens` | 31 | 9 |
| `project/commit_detail` | 30 | 9 |

## Top in-degree classes (destinations)

| class | in-degree | out-degree |
|---|---:|---:|
| `global/help_landing` | 123 | 6 |
| `global/new_project_form` | 123 | 5 |
| `global/root_redirect` | 123 | 14 |
| `dashboard/todo_list/pending` | 123 | 9 |
| `dashboard/issue_list` | 123 | 9 |
| `dashboard/merge_request_list` | 123 | 9 |
| `user/profile` | 100 | 15 |
| `project/main` | 94 | 38 |
| `project/merge_request_list` | 86 | 25 |
| `project/issue_list` | 86 | 26 |
| `project/package_list` | 81 | 23 |
| `project/cluster_list` | 81 | 22 |
| `project/environment_list` | 81 | 25 |
| `project/snippet_list` | 81 | 23 |
| `project/value_stream_analytics` | 81 | 23 |

## Isolated source (no out-edges)

- `explore/topic_detail` (instance count: 2)
- `project/issue_feed` (instance count: 2)
- `project/raw_file` (instance count: 2)
- `global/help_image` (instance count: 2)
- `project/snippet_detail` (instance count: 2)
- `project/merge_request_feed` (instance count: 2)

## Unreachable classes (no in-edges)

- `project/cluster_new_docs` (out-degree: 24)
- `global/snippet_list` (out-degree: 9)
- `project/jira_import_form` (out-degree: 23)
- `global/import_form` (out-degree: 7)
- `explore/topic_detail` (out-degree: 0)
- `global/abuse_report_new_form` (out-degree: 15)
- `ide/mr_detail` (out-degree: 7)
- `dashboard/group_list` (out-degree: 7)
- `global/search_page` (out-degree: 6)
- `project/snippet_detail` (out-degree: 0)

## Example edges — project/issue_list outgoing

| target | trust | actions |
|---|---|---|
| `global/root_redirect` | `high` | Dashboard |
| `global/new_project_form` | `high` | Create new... |
| `dashboard/issue_list` | `high` | 13 |
| `dashboard/merge_request_list` | `high` | 8 |
| `dashboard/todo_list/pending` | `high` | 5 |
| `global/help_landing` | `high` | Help |
| `project/activity_list` | `high` | Project information |
| `project/file_list` | `high` | Repository |
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
| `user/profile` | `high` | Byte Blaze |
| `project/issue_feed` | `high` | Subscribe to RSS feed |
| `project/issue_new_form` | `high` | New issue |
| `project/main` | `medium` | A a11y-webring.club, a11y-webring.club, E empathy-prompts |
| `project/merge_request_list` | `medium` | Merge requests 1, Merge requests 2 |
| `project/issue_board` | `medium` | Boards |
| `project/issue_detail` | `medium` | Service Desk |
| `project/milestone_list` | `medium` | Milestones |

## Next (Solution 2)

- Adjacency list / reverse adjacency 이미 저장됨 (`edge_graph.json`)
- BFS from (current_class) to (target_class) 가능
- Trust-weighted path ranking 가능
- Path → agent hint (URL sequence) 변환은 Solution 2의 별도 단계