# Stage C — Navigation edge graph report

**Date**: 2026-04-21

## Summary

- Total classes in graph: 131
- Classes in catalog (source-side): 130
- **Unique edges** (source → target, distinct): **2757**
- Self-edges (within-class): 119
- Actions with unresolved target: 25
- Isolated source classes (out-degree 0): 6
- Unreachable classes (in-degree 0): 9

## Trust distribution

| trust | count |
|---|---:|
| `high` | 2464 |
| `medium` | 284 |
| `low` | 9 |
| `unknown` | 0 |

## Top out-degree classes (hubs)

| class | out-degree | in-degree |
|---|---:|---:|
| `project/main` | 38 | 96 |
| `project/blob_detail` | 33 | 4 |
| `project/settings_integrations` | 32 | 11 |
| `project/blame_view` | 32 | 1 |
| `project/settings_integration_edit` | 32 | 3 |
| `project/tag_list` | 32 | 15 |
| `project/settings_repository` | 32 | 10 |
| `project/branch_list` | 31 | 15 |
| `project/settings_ci_cd` | 31 | 12 |
| `project/commit_detail` | 31 | 9 |
| `project/tag_detail` | 31 | 3 |
| `project/webhook_list` | 31 | 10 |
| `project/settings_operations` | 31 | 12 |
| `project/settings_general` | 31 | 81 |
| `project/settings_merge_requests` | 31 | 10 |

## Top in-degree classes (destinations)

| class | in-degree | out-degree |
|---|---:|---:|
| `dashboard/merge_request_list` | 123 | 9 |
| `global/root_redirect` | 123 | 14 |
| `global/new_project_form` | 123 | 5 |
| `global/help_landing` | 123 | 6 |
| `dashboard/issue_list` | 123 | 9 |
| `dashboard/todo_list/pending` | 123 | 9 |
| `user/profile` | 100 | 18 |
| `project/main` | 96 | 38 |
| `project/issue_list` | 87 | 26 |
| `project/merge_request_list` | 87 | 25 |
| `project/file_list` | 81 | 29 |
| `project/environment_list` | 81 | 25 |
| `project/security_config` | 81 | 23 |
| `project/pipeline_list` | 81 | 26 |
| `project/activity_list` | 81 | 23 |

## Isolated source (no out-edges)

- `project/issue_feed` (instance count: 2)
- `project/raw_file` (instance count: 2)
- `global/help_image` (instance count: 2)
- `explore/topic_detail` (instance count: 2)
- `project/snippet_detail` (instance count: 2)
- `project/merge_request_feed` (instance count: 2)

## Unreachable classes (no in-edges)

- `dashboard/group_list` (out-degree: 7)
- `project/jira_import_form` (out-degree: 23)
- `global/import_form` (out-degree: 7)
- `global/search_page` (out-degree: 6)
- `global/snippet_list` (out-degree: 9)
- `explore/topic_detail` (out-degree: 0)
- `project/cluster_new_docs` (out-degree: 24)
- `project/snippet_detail` (out-degree: 0)
- `ide/mr_detail` (out-degree: 7)

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
| `user/profile` | `high` | Byte Blaze |
| `project/issue_feed` | `high` | Subscribe to RSS feed |
| `project/issue_new_form` | `high` | New issue |
| `project/main` | `medium` | A a11y-webring.club, a11y-webring.club, E empathy-prompts |
| `project/merge_request_list` | `medium` | Merge requests 1, Merge requests 2 |

## Next (Solution 2)

- Adjacency list / reverse adjacency 이미 저장됨 (`edge_graph.json`)
- BFS from (current_class) to (target_class) 가능
- Trust-weighted path ranking 가능
- Path → agent hint (URL sequence) 변환은 Solution 2의 별도 단계