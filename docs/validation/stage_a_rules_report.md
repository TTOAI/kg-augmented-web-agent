# Stage A.e — URL → class rule 추출 결과

**Date**: 2026-04-21
**Total rules**: 141
**Self-validation**: 190/190 = 100.0%
**Frozen KG template 재사용**: 31/141 rules

## Approach

- 각 user_class를 독립 rule로 취급
- Instance URL들로부터 template 도출 (varying segment → path param)
- 같은 template 공유하는 rule들 → query-variant group으로 post-hoc 병합
- Specificity 정렬 (literal ×10 + 총 segment − path_segments penalty)

## Self-validation

✅ **전부 self-consistent** — 모든 annotation이 rule로 정확히 재분류됨.

## Rules (specificity desc)

| # | class | url_template | path_params | variant_queries | spec | frozen | instances |
|---|---|---|---|---|---:|---|---:|
| 1 | **`ide/edit_view`** | `/-/ide/project/{namespace}/{project}/edit/{slot_2}/-` | namespace,project,slot_2 | — | 58 | — | 2 |
| 2 | **`global/help_image`** | `/help/user/profile/img/personal_readme_setup_v14_5.png` | — | — | 55 | — | 3 |
| 3 | **`project/settings_integration_edit`** | `/{namespace}/{project}/-/settings/integrations/{service}/edit` | namespace,project,service | — | 47 | — | 1 |
| 4 | **`ide/mr_detail`** | `/-/ide/project/{namespace}/{project}/merge_requests/{id}` | namespace,project,id | — | 47 | — | 1 |
| 5 | **`account/password_edit`** | `/-/profile/password/edit` | — | — | 44 | ✓ | 1 |
| 6 | **`ide/mr_view`** | `/-/ide/project/{namespace}/{project}/tree/{branch_path}` | namespace,project,branch_path | — | 42 | — | 1 |
| 7 | **`project/repository_analytics`** | `/{namespace}/{project}/-/graphs/{branch}/charts` | namespace,project,branch | — | 36 | — | 1 |
| 8 | **`project/label_edit_form`** | `/{namespace}/{project}/-/labels/{id}/edit` | namespace,project,id | — | 36 | — | 1 |
| 9 | **`project/merge_request_commits`** | `/{namespace}/{project}/-/merge_requests/{id}/commits` | namespace,project,id | — | 36 | — | 1 |
| 10 | **`project/merge_request_diff`** | `/{namespace}/{project}/-/merge_requests/{id}/diffs` | namespace,project,id | — | 36 | — | 1 |
| 11 | **`project/merge_request_edit_form`** | `/{namespace}/{project}/-/merge_requests/{id}/edit` | namespace,project,id | — | 36 | — | 1 |
| 12 | **`project/merge_request_pipelines`** | `/{namespace}/{project}/-/merge_requests/{id}/pipelines` | namespace,project,id | — | 36 | — | 1 |
| 13 | **`project/milestone_edit_form`** | `/{namespace}/{project}/-/milestones/{id}/edit` | namespace,project,id | — | 36 | — | 1 |
| 14 | **`project/release_edit_form`** | `/{namespace}/{project}/-/releases/{tag}/edit` | namespace,project,tag | — | 36 | — | 1 |
| 15 | **`project/branch_new_form`** | `/{namespace}/{project}/-/branches/new` | namespace,project | — | 35 | — | 1 |
| 16 | **`project/issue_new_form`** | `/{namespace}/{project}/-/issues/new` | namespace,project | — | 35 | — | 1 |
| 17 | **`project/merge_request_new_form`** | `/{namespace}/{project}/-/merge_requests/new` | namespace,project | — | 35 | — | 1 |
| 18 | **`project/settings_access_tokens`** | `/{namespace}/{project}/-/settings/access_tokens` | namespace,project | — | 35 | — | 1 |
| 19 | **`project/settings_ci_cd`** | `/{namespace}/{project}/-/settings/ci_cd` | namespace,project | — | 35 | — | 1 |
| 20 | **`project/settings_integrations`** | `/{namespace}/{project}/-/settings/integrations` | namespace,project | — | 35 | — | 1 |
| 21 | **`project/settings_repository`** | `/{namespace}/{project}/-/settings/repository` | namespace,project | — | 35 | — | 1 |
| 22 | **`project/tag_new_form`** | `/{namespace}/{project}/-/tags/new` | namespace,project | — | 35 | — | 1 |
| 23 | **`project/wiki`** | `/{namespace}/{project}/-/wikis/home` | namespace,project | — | 35 | — | 1 |
| 24 | **`project/ci_editor`** | `/{namespace}/{project}/-/ci/editor` | namespace,project | — | 35 | — | 1 |
| 25 | **`project/fork_new_form`** | `/{namespace}/{project}/-/forks/new` | namespace,project | — | 35 | — | 1 |
| 26 | **`project/cicd_analytics`** | `/{namespace}/{project}/-/pipelines/charts` | namespace,project | — | 35 | — | 1 |
| 27 | **`project/security_config`** | `/{namespace}/{project}/-/security/configuration` | namespace,project | — | 35 | — | 1 |
| 28 | **`project/settings_merge_requests`** | `/{namespace}/{project}/-/settings/merge_requests` | namespace,project | — | 35 | — | 1 |
| 29 | **`project/settings_operations`** | `/{namespace}/{project}/-/settings/operations` | namespace,project | — | 35 | — | 1 |
| 30 | **`project/settings_packages`** | `/{namespace}/{project}/-/settings/packages_and_registries` | namespace,project | — | 35 | — | 1 |
| 31 | **`project/snippet_new_form`** | `/{namespace}/{project}/-/snippets/new` | namespace,project | — | 35 | — | 1 |
| 32 | **`project/label_new_form`** | `/{namespace}/{project}/-/labels/new` | namespace,project | — | 35 | — | 1 |
| 33 | **`project/release_new_form`** | `/{namespace}/{project}/-/releases/new` | namespace,project | — | 35 | — | 1 |
| 34 | **`project/environment_new_form`** | `/{namespace}/{project}/-/environments/new` | namespace,project | — | 35 | — | 1 |
| 35 | **`project/feature_flag_new_form`** | `/{namespace}/{project}/-/feature_flags/new` | namespace,project | — | 35 | — | 1 |
| 36 | **`project/pipeline_schedule_new_form`** | `/{namespace}/{project}/-/pipeline_schedules/new` | namespace,project | — | 35 | — | 1 |
| 37 | **`project/ci_lint`** | `/{namespace}/{project}/-/ci/lint` | namespace,project | — | 35 | — | 1 |
| 38 | **`project/cluster_new_docs`** | `/{namespace}/{project}/-/clusters/new_cluster_docs` | namespace,project | — | 35 | — | 1 |
| 39 | **`project/feature_flag_user_list_new_form`** | `/{namespace}/{project}/-/feature_flags_user_lists/new` | namespace,project | — | 35 | — | 1 |
| 40 | **`explore/topic_detail`** | `/explore/projects/topics/{topic_name}` | topic_name | — | 34 | — | 1 |
| 41 | **`dashboard/project_list/starred`** | `/dashboard/projects/starred` | — | — | 33 | ✓ | 1 |
| 42 | **`explore/topic_list`** | `/explore/projects/topics` | — | — | 33 | ✓ | 1 |
| 43 | **`account/notifications`** | `/-/profile/notifications` | — | — | 33 | ✓ | 1 |
| 44 | **`account/preferences`** | `/-/profile/preferences` | — | — | 33 | ✓ | 1 |
| 45 | **`global/abuse_report_new_form`** | `/-/abuse_reports/new` | — | — | 33 | — | 1 |
| 46 | **`explore/project_list/starred`** | `/explore/projects/starred` | — | — | 33 | ✓ | 1 |
| 47 | **`explore/project_list/trending`** | `/explore/projects/trending` | — | — | 33 | ✓ | 1 |
| 48 | **`account/keys`** | `/-/profile/keys` | — | — | 33 | ✓ | 1 |
| 49 | **`account/account`** | `/-/profile/account` | — | — | 33 | ✓ | 1 |
| 50 | **`account/applications`** | `/-/profile/applications` | — | — | 33 | ✓ | 1 |
| 51 | **`account/audit_log`** | `/-/profile/audit_log` | — | — | 33 | ✓ | 1 |
| 52 | **`account/chat_names`** | `/-/profile/chat_names` | — | — | 33 | ✓ | 1 |
| 53 | **`account/emails`** | `/-/profile/emails` | — | — | 33 | ✓ | 1 |
| 54 | **`account/gpg_keys`** | `/-/profile/gpg_keys` | — | — | 33 | ✓ | 1 |
| 55 | **`account/personal_access_tokens`** | `/-/profile/personal_access_tokens` | — | — | 33 | ✓ | 1 |
| 56 | **`account/active_sessions`** | `/-/profile/active_sessions` | — | — | 33 | ✓ | 1 |
| 57 | **`account/two_factor_auth`** | `/-/profile/two_factor_auth` | — | — | 33 | ✓ | 1 |
| 58 | **`global/snippet_new_form`** | `/-/snippets/new` | — | — | 33 | ✓ | 1 |
| 59 | **`project/branch_list`** | `/{namespace}/{project}/-/branches/{slot_2}` | namespace,project,slot_2 | — | 25 | — | 4 |
| 60 | **`project/commit_detail`** | `/{namespace}/{project}/-/commit/{sha}` | namespace,project,sha | — | 25 | — | 1 |
| 61 | **`project/issue_detail`** | `/{namespace}/{project}/-/issues/{id}` | namespace,project,id | — | 25 | — | 1 |
| 62 | **`project/merge_request_detail`** | `/{namespace}/{project}/-/merge_requests/{id}` | namespace,project,id | — | 25 | — | 1 |
| 63 | **`project/tag_detail`** | `/{namespace}/{project}/-/tags/{tag_name}` | namespace,project,tag_name | — | 25 | — | 1 |
| 64 | **`project/contributor_graph`** | `/{namespace}/{project}/-/graphs/{branch}` | namespace,project,branch | — | 25 | — | 1 |
| 65 | **`project/jira_import_form`** | `/{namespace}/{project}/-/import/{service}` | namespace,project,service | — | 25 | — | 1 |
| 66 | **`project/milestone_detail`** | `/{namespace}/{project}/-/milestones/{id}` | namespace,project,id | — | 25 | — | 1 |
| 67 | **`project/network_graph`** | `/{namespace}/{project}/-/network/{branch}` | namespace,project,branch | — | 25 | — | 1 |
| 68 | **`project/file_new_form`** | `/{namespace}/{project}/-/new/{slot_2}` | namespace,project,slot_2 | — | 25 | — | 2 |
| 69 | **`project/pipeline_detail`** | `/{namespace}/{project}/-/pipelines/{id}` | namespace,project,id | — | 25 | — | 1 |
| 70 | **`project/snippet_detail`** | `/{namespace}/{project}/-/snippets/{id}` | namespace,project,id | — | 25 | — | 1 |
| 71 | **`project/protected_branch_detail`** | `/{namespace}/{project}/-/protected_branches/{id}` | namespace,project,id | — | 25 | — | 1 |
| 72 | **`project/release_detail`** | `/{namespace}/{project}/-/releases/{tag}` | namespace,project,tag | — | 25 | — | 1 |
| 73 | **`project/fork_list`** | `/{namespace}/{project}/-/forks` | namespace,project | — | 24 | — | 1 |
| 74 | **`project/issue_list`** | `/{namespace}/{project}/-/issues` | namespace,project | — | 24 | — | 3 |
| 75 | **`project/label_list`** | `/{namespace}/{project}/-/labels` | namespace,project | — | 24 | — | 1 |
| 76 | **`project/member_list`** | `/{namespace}/{project}/-/project_members` | namespace,project | — | 24 | — | 1 |
| 77 | **`project/merge_request_list`** | `/{namespace}/{project}/-/merge_requests` | namespace,project | — | 24 | — | 2 |
| 78 | **`project/milestone_list`** | `/{namespace}/{project}/-/milestones` | namespace,project | — | 24 | — | 1 |
| 79 | **`project/issue_board`** | `/{namespace}/{project}/-/boards` | namespace,project | — | 24 | — | 1 |
| 80 | **`project/branch_list`** | `/{namespace}/{project}/-/branches` | namespace,project | — | 24 | — | 4 |
| 81 | **`project/environment_list`** | `/{namespace}/{project}/-/environments` | namespace,project | — | 24 | — | 1 |
| 82 | **`project/job_list`** | `/{namespace}/{project}/-/jobs` | namespace,project | — | 24 | — | 1 |
| 83 | **`project/schedule_list`** | `/{namespace}/{project}/-/pipeline_schedules` | namespace,project | — | 24 | — | 1 |
| 84 | **`project/pipeline_list`** | `/{namespace}/{project}/-/pipelines` | namespace,project | — | 24 | — | 1 |
| 85 | **`project/snippet_list`** | `/{namespace}/{project}/-/snippets` | namespace,project | — | 24 | — | 1 |
| 86 | **`project/tag_list`** | `/{namespace}/{project}/-/tags` | namespace,project | — | 24 | — | 1 |
| 87 | **`global/help_image`** | `/help/{project}/img/{slot_1}` | project,slot_1 | — | 24 | — | 3 |
| 88 | **`project/alert_management`** | `/{namespace}/{project}/-/alert_management` | namespace,project | — | 24 | — | 1 |
| 89 | **`project/cluster_list`** | `/{namespace}/{project}/-/clusters` | namespace,project | — | 24 | — | 1 |
| 90 | **`project/compare_form`** | `/{namespace}/{project}/-/compare` | namespace,project | — | 24 | — | 1 |
| 91 | **`project/error_tracking`** | `/{namespace}/{project}/-/error_tracking` | namespace,project | — | 24 | — | 1 |
| 92 | **`project/feature_flag_list`** | `/{namespace}/{project}/-/feature_flags` | namespace,project | — | 24 | — | 1 |
| 93 | **`project/webhook_list`** | `/{namespace}/{project}/-/hooks` | namespace,project | — | 24 | — | 1 |
| 94 | **`project/incident_list`** | `/{namespace}/{project}/-/incidents` | namespace,project | — | 24 | — | 1 |
| 95 | **`project/infrastructure_registry`** | `/{namespace}/{project}/-/infrastructure_registry` | namespace,project | — | 24 | — | 1 |
| 96 | **`project/issue_feed`** | `/{namespace}/{project}/-/issues.atom` | namespace,project | — | 24 | — | 1 |
| 97 | **`project/merge_request_feed`** | `/{namespace}/{project}/-/merge_requests.atom` | namespace,project | — | 24 | — | 1 |
| 98 | **`project/metric_dashboard`** | `/{namespace}/{project}/-/metrics` | namespace,project | — | 24 | — | 1 |
| 99 | **`project/package_list`** | `/{namespace}/{project}/-/packages` | namespace,project | — | 24 | — | 1 |
| 100 | **`project/release_list`** | `/{namespace}/{project}/-/releases` | namespace,project | — | 24 | — | 1 |
| 101 | **`project/starrer_list`** | `/{namespace}/{project}/-/starrers` | namespace,project | — | 24 | — | 1 |
| 102 | **`project/terraform_list`** | `/{namespace}/{project}/-/terraform` | namespace,project | — | 24 | — | 1 |
| 103 | **`project/usage_quota`** | `/{namespace}/{project}/-/usage_quotas` | namespace,project | — | 24 | — | 1 |
| 104 | **`project/value_stream_analytics`** | `/{namespace}/{project}/-/value_stream_analytics` | namespace,project | — | 24 | — | 1 |
| 105 | **`project/feature_flag_user_list`** | `/{namespace}/{project}/-/feature_flags_user_lists` | namespace,project | — | 24 | — | 1 |
| 106 | **`user/activity_list`** | `/users/{username}/activity` | username | — | 23 | — | 1 |
| 107 | **`global/import_form`** | `/import/{project}/new` | project | — | 23 | — | 4 |
| 108 | **`user/contributed_project_list`** | `/users/{username}/contributed` | username | — | 23 | — | 1 |
| 109 | **`user/follower_list`** | `/users/{username}/followers` | username | — | 23 | — | 1 |
| 110 | **`user/following_list`** | `/users/{username}/following` | username | — | 23 | — | 1 |
| 111 | **`user/group_list`** | `/users/{username}/groups` | username | — | 23 | — | 1 |
| 112 | **`user/project_list`** | `/users/{username}/projects` | username | — | 23 | — | 1 |
| 113 | **`user/snippet_list`** | `/users/{username}/snippets` | username | — | 23 | — | 1 |
| 114 | **`user/starred_project_list`** | `/users/{username}/starred` | username | — | 23 | — | 1 |
| 115 | **`dashboard/group_list`** | `/dashboard/groups` | — | — | 22 | ✓ | 1 |
| 116 | **`dashboard/project_list/yours`** | `/dashboard/projects` | — | — | 22 | ✓ | 2 |
| 117 | **`dashboard/issue_list`** | `/dashboard/issues` | — | — | 22 | ✓ | 1 |
| 118 | **`dashboard/merge_request_list`** | `/dashboard/merge_requests` | — | — | 22 | ✓ | 1 |
| 119 | **`dashboard/todo_list`** | `/dashboard/todos` | — | key=`state`, {'__absent__': 'pending', 'done': 'done'} | 22 | ✓ | 2 |
| 120 | **`explore/project_list/all`** | `/explore/projects` | — | — | 22 | ✓ | 1 |
| 121 | **`global/new_project_form`** | `/projects/new` | — | — | 22 | ✓ | 1 |
| 122 | **`account/edit`** | `/-/profile` | — | — | 22 | ✓ | 1 |
| 123 | **`global/snippet_list`** | `/dashboard/snippets` | — | — | 22 | ✓ | 1 |
| 124 | **`project/commit_list`** | `/{namespace}/{project}/-/commits/{branch_path}` | namespace,project,branch_path | — | 20 | — | 1 |
| 125 | **`project/file_list`** ⚠️same template as: ['project/file_list'], no query differentiator | `/{namespace}/{project}/-/tree/{branch_path}` | namespace,project,branch_path | — | 20 | — | 2 |
| 126 | **`project/file_list`** ⚠️same template as: ['project/file_list'], no query differentiator | `/{namespace}/{project}/-/tree/{branch_path}` | namespace,project,branch_path | — | 20 | — | 2 |
| 127 | **`project/blob_detail`** | `/{namespace}/{project}/-/blob/{branch_path}` | namespace,project,branch_path | — | 20 | — | 1 |
| 128 | **`project/file_search`** | `/{namespace}/{project}/-/find_file/{branch_path}` | namespace,project,branch_path | — | 20 | — | 1 |
| 129 | **`project/blame_view`** | `/{namespace}/{project}/-/blame/{branch_path}` | namespace,project,branch_path | — | 20 | — | 1 |
| 130 | **`project/raw_file`** | `/{namespace}/{project}/-/raw/{branch_path}` | namespace,project,branch_path | — | 20 | — | 1 |
| 131 | **`project/upload_file`** | `/{namespace}/{project}/uploads/{sha}/{file}` | namespace,project,sha,file | — | 15 | — | 1 |
| 132 | **`project/activity_list`** | `/{namespace}/{project}/activity` | namespace,project | — | 13 | — | 1 |
| 133 | **`project/settings_general`** | `/{namespace}/{project}/edit` | namespace,project | — | 13 | — | 1 |
| 134 | **`project/history`** | `/{namespace}/{project}/history` | namespace,project | — | 13 | — | 1 |
| 135 | **`dashboard/project_list/yours`** | `/dashboard` | — | — | 11 | ✓ | 2 |
| 136 | **`global/help_landing`** | `/help` | — | — | 11 | ✓ | 1 |
| 137 | **`global/search_page`** | `/search` | — | — | 11 | ✓ | 1 |
| 138 | **`global/help_page`** | `/help/{path}` | path | — | 7 | — | 35 |
| 139 | **`project/main`** | `/{namespace}/{project}` | namespace,project | — | 2 | — | 3 |
| 140 | **`user/profile`** | `/{username}` | username | — | 1 | — | 1 |
| 141 | **`global/root_redirect`** | `/` | — | — | 0 | ✓ | 2 |

## 다음 단계

- **Stage A.f**: Rule을 Frozen KG 3,040 StatePattern에 적용
- **Stage A.f.post**: Coverage, compression ratio, unmatched SP 분석