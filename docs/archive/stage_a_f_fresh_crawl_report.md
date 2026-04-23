# Stage A.f — Fresh BFS crawl rule validation

**Date**: 2026-04-21
**Total crawled**: 1500
**HTTP 200**: 1457
**Non-200**: 43

## Coverage

- Matched: **1457/1457 = 100.0%**
- Unmatched: 0
- Pre-visit classify vs final classify 일치: 204/1457

## Scope 분포

| scope | count |
|---|---:|
| `project` | 836 |
| `global` | 488 |
| `explore` | 51 |
| `dashboard` | 31 |
| `user` | 29 |
| `account` | 15 |
| `ide` | 7 |

## Per-class 분포

| class | instance 수 | unique namespace 수 |
|---|---:|---:|
| `global/help_page` | 414 | 0 |
| `project/starrer_list` | 70 | 51 |
| `project/settings_integration_edit` | 37 | 1 |
| `global/root_redirect` | 31 | 0 |
| `project/compare_form` | 30 | 16 |
| `project/contributor_graph` | 29 | 16 |
| `project/network_graph` | 29 | 16 |
| `project/release_list` | 29 | 16 |
| `project/package_list` | 29 | 16 |
| `project/infrastructure_registry` | 29 | 16 |
| `project/incident_list` | 29 | 16 |
| `project/value_stream_analytics` | 29 | 16 |
| `project/cicd_analytics` | 28 | 15 |
| `project/repository_analytics` | 28 | 15 |
| `explore/topic_detail` | 22 | 0 |
| `project/ci_editor` | 16 | 3 |
| `project/snippet_new_form` | 14 | 3 |
| `project/security_config` | 14 | 3 |
| `project/feature_flag_list` | 14 | 3 |
| `project/cluster_list` | 14 | 3 |
| `project/terraform_list` | 14 | 3 |
| `project/metric_dashboard` | 14 | 3 |
| `project/error_tracking` | 14 | 3 |
| `project/alert_management` | 14 | 3 |
| `global/help_image` | 14 | 0 |
| `project/webhook_list` | 13 | 2 |
| `project/settings_merge_requests` | 13 | 2 |
| `project/settings_packages` | 13 | 2 |
| `project/settings_operations` | 13 | 2 |
| `project/usage_quota` | 13 | 2 |
| `explore/project_list/starred` | 12 | 0 |
| `explore/project_list/trending` | 11 | 0 |
| `project/commit_list` | 11 | 3 |
| `project/file_list` | 10 | 3 |
| `global/abuse_report_new_form` | 10 | 0 |
| `project/milestone_detail` | 9 | 2 |
| `project/pipeline_detail` | 9 | 2 |
| `project/branch_list` | 8 | 3 |
| `project/label_edit_form` | 8 | 1 |
| `global/import_form` | 7 | 1 |
| `dashboard/project_list/yours` | 5 | 0 |
| `explore/project_list/all` | 5 | 0 |
| `user/profile` | 5 | 4 |
| `project/main` | 5 | 1 |
| `global/search_page` | 5 | 0 |
| `dashboard/issue_list` | 5 | 0 |
| `dashboard/merge_request_list` | 5 | 0 |
| `dashboard/todo_list/pending` | 5 | 0 |
| `dashboard/project_list/starred` | 5 | 0 |
| `project/fork_list` | 5 | 4 |
| `project/merge_request_list` | 5 | 4 |
| `project/issue_list` | 5 | 4 |
| `project/issue_new_form` | 5 | 3 |
| `project/merge_request_new_form` | 5 | 2 |
| `project/member_list` | 5 | 3 |
| `project/activity_list` | 5 | 3 |
| `project/label_list` | 5 | 3 |
| `project/tag_list` | 5 | 3 |
| `project/issue_board` | 5 | 3 |
| `project/issue_detail` | 5 | 1 |
| `project/milestone_list` | 5 | 3 |
| `project/pipeline_list` | 5 | 3 |
| `project/job_list` | 5 | 3 |
| `project/schedule_list` | 5 | 3 |
| `project/environment_list` | 5 | 3 |
| `project/wiki` | 5 | 3 |
| `project/snippet_list` | 5 | 3 |
| `project/settings_general` | 5 | 2 |
| `project/settings_integrations` | 5 | 2 |
| `project/settings_access_tokens` | 5 | 2 |
| `project/settings_repository` | 5 | 2 |
| `project/settings_ci_cd` | 5 | 2 |
| `project/merge_request_detail` | 5 | 2 |
| `dashboard/todo_list/done` | 5 | 0 |
| `project/fork_new_form` | 5 | 4 |
| `project/commit_detail` | 5 | 1 |
| `project/merge_request_edit_form` | 5 | 2 |
| `ide/mr_detail` | 5 | 0 |
| `project/merge_request_commits` | 5 | 2 |
| `project/merge_request_pipelines` | 5 | 2 |
| `project/merge_request_diff` | 5 | 2 |
| `global/snippet_list` | 4 | 0 |
| `project/file_new_form` | 4 | 1 |
| `project/milestone_edit_form` | 4 | 1 |
| `user/follower_list` | 3 | 0 |
| `user/following_list` | 3 | 0 |
| `user/activity_list` | 3 | 0 |
| `user/group_list` | 3 | 0 |
| `user/contributed_project_list` | 3 | 0 |
| `user/project_list` | 3 | 0 |
| `user/starred_project_list` | 3 | 0 |
| `user/snippet_list` | 3 | 0 |
| `project/merge_request_feed` | 3 | 2 |
| `project/issue_feed` | 3 | 2 |
| `project/jira_import_form` | 3 | 2 |
| `account/edit` | 2 | 0 |
| `project/snippet_detail` | 2 | 1 |
| `project/file_search` | 2 | 1 |
| `ide/edit_view` | 2 | 0 |
| `project/blob_detail` | 2 | 1 |
| `project/upload_file` | 2 | 2 |
| `global/help_landing` | 1 | 0 |
| `dashboard/group_list` | 1 | 0 |
| `global/new_project_form` | 1 | 0 |
| `global/snippet_new_form` | 1 | 0 |
| `account/preferences` | 1 | 0 |
| `explore/topic_list` | 1 | 0 |
| `account/keys` | 1 | 0 |
| `account/account` | 1 | 0 |
| `account/applications` | 1 | 0 |
| `account/chat_names` | 1 | 0 |
| `account/personal_access_tokens` | 1 | 0 |
| `account/emails` | 1 | 0 |
| `account/password_edit` | 1 | 0 |
| `account/notifications` | 1 | 0 |
| `account/gpg_keys` | 1 | 0 |
| `account/active_sessions` | 1 | 0 |
| `account/audit_log` | 1 | 0 |
| `project/history` | 1 | 1 |
| `project/label_new_form` | 1 | 1 |
| `project/branch_new_form` | 1 | 1 |
| `project/tag_new_form` | 1 | 1 |
| `project/ci_lint` | 1 | 1 |
| `project/pipeline_schedule_new_form` | 1 | 1 |
| `project/environment_new_form` | 1 | 1 |
| `project/feature_flag_user_list` | 1 | 1 |
| `project/feature_flag_new_form` | 1 | 1 |
| `project/release_new_form` | 1 | 1 |
| `project/cluster_new_docs` | 1 | 1 |
| `project/protected_branch_detail` | 1 | 1 |
| `account/two_factor_auth` | 1 | 0 |

## Instance variance 검증

**Multi-namespace class** (63개) — rule이 여러 project에서 일반화됨:
- `project/starrer_list`: 51 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'Ink', 'Media-Smart', 'OpenAPITools']
- `project/contributor_graph`: 16 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/network_graph`: 16 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/compare_form`: 16 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/release_list`: 16 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/package_list`: 16 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/infrastructure_registry`: 16 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/incident_list`: 16 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/value_stream_analytics`: 16 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/cicd_analytics`: 15 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `project/repository_analytics`: 15 namespaces → ['0ang3el', 'Arachni', 'CellularPrivacy', 'a11yproject', 'abisubramanya27', 'amwhalen']
- `user/profile`: 4 namespaces → ['byteblaze', 'byteblaze.atom', 'earlev4', 'rik-williams']
- `project/fork_list`: 4 namespaces → ['a11yproject', 'abisubramanya27', 'byteblaze', 'yjlou']
- `project/merge_request_list`: 4 namespaces → ['a11yproject', 'abisubramanya27', 'byteblaze', 'yjlou']
- `project/issue_list`: 4 namespaces → ['a11yproject', 'abisubramanya27', 'byteblaze', 'yjlou']
- `project/fork_new_form`: 4 namespaces → ['a11yproject', 'abisubramanya27', 'byteblaze', 'yjlou']
- `project/issue_new_form`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/snippet_new_form`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/member_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/activity_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/label_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/file_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/commit_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/branch_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/tag_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/issue_board`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/milestone_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/pipeline_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/ci_editor`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/job_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/schedule_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/security_config`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/environment_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/feature_flag_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/cluster_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/terraform_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/metric_dashboard`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/error_tracking`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/alert_management`: 3 namespaces → ['a11yproject', 'byteblaze', 'primer']
- `project/wiki`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/snippet_list`: 3 namespaces → ['a11yproject', 'byteblaze', 'yjlou']
- `project/merge_request_new_form`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/settings_general`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/settings_integrations`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/webhook_list`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/settings_access_tokens`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/settings_repository`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/settings_merge_requests`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/settings_ci_cd`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/settings_packages`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/settings_operations`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/usage_quota`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/milestone_detail`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/merge_request_detail`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/pipeline_detail`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/merge_request_feed`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/issue_feed`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/jira_import_form`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/upload_file`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/merge_request_edit_form`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/merge_request_commits`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/merge_request_pipelines`: 2 namespaces → ['a11yproject', 'byteblaze']
- `project/merge_request_diff`: 2 namespaces → ['a11yproject', 'byteblaze']

## Unmatched URL (rule gap)

총 0개. 샘플 (최대 40개):

| depth | final_url | title | linked_from |
|---|---|---|---|

## Non-200 샘플

| http_status | url |
|---|---|
| 500 | `/byteblaze/a11y-syntax-highlighting/-/google_cloud/configuration` |
| 500 | `/import/gitlab/status` |
| 500 | `/import/bitbucket/status` |
| error | `/byteblaze/a11y-syntax-highlighting/-/issues.ics?due_date=next_month_and_previous_two_weeks&feed_token=TMN_bBn9Z48qVbUFZV45&sort=closest_future_date` |
| 500 | `/byteblaze/a11y-webring.club/-/google_cloud/configuration` |
| error | `/byteblaze/a11y-webring.club/-/archive/main/a11y-webring.club-main.zip` |
| error | `/byteblaze/a11y-webring.club/-/archive/main/a11y-webring.club-main.tar.gz` |
| error | `/byteblaze/a11y-webring.club/-/archive/main/a11y-webring.club-main.tar.bz2` |
| error | `/byteblaze/a11y-webring.club/-/archive/main/a11y-webring.club-main.tar` |
| 404 | `/byteblaze/git@localhost:byteblaze/a11y-webring.club.git` |
| error | `/byteblaze/a11y-webring.club/-/issues.ics?due_date=next_month_and_previous_two_weeks&feed_token=TMN_bBn9Z48qVbUFZV45&sort=closest_future_date` |
| 500 | `/a11yproject/a11yproject.com/-/google_cloud/configuration` |
| error | `/a11yproject/a11yproject.com/-/issues.ics?due_date=next_month_and_previous_two_weeks&feed_token=TMN_bBn9Z48qVbUFZV45&sort=closest_future_date` |
| 500 | `/byteblaze/accessible-html-content-patterns/-/google_cloud/configuration` |
| error | `/byteblaze/a11y-syntax-highlighting/-/archive/main/a11y-syntax-highlighting-main.zip` |

## Gate 검증

- Coverage ≥ 80%: ✅ (100.0%)
- Unmatched 수집: — (0 URL)
- Multi-namespace class: ✅ (63개)
