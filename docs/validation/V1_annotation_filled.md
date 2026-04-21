# V1 — Annotation Filled (검증용)

**Date**: 2026-04-18
**Status**: Assistant 채움, 사용자 verify 대기
**Total pages**: 190

## Workflow (Stage A)

1. **Stage A.a**: 페이지 AXTree 수집
2. **Stage A.b**: LLM annotation (동일 prompt/model)
3. **Stage A.c**: Assistant가 convention 적용 → `user_class`/`user_reason` 확정
4. **Stage A.e (다음)**: URL → class rule 추출
5. **Stage A.f**: Rule을 Frozen KG 3,040 StatePattern에 적용

## Naming convention (protocol v0.5 — class inheritance tree)

표기: `{scope-class}/{…}/{leaf-class}[/{variant}]` — root `site` 생략

**Scope class (tree 최상위)** — 공유 chrome(sidebar/header)으로 결정:
- `project` — 사이드바 공유 action (실측)
- `dashboard` — 헤더 공유 28 action
- `explore` — explore 상단 탭
- `user` — public user view (/username 류)
- `account` — 로그인한 본인 계정 관리 (/-/profile/* 전용 사이드바 14 action)
- `global` — 특정 scope 없음 (help, search, /projects/new 등)

**Leaf class (tree 잎, 구체 페이지)** — core content widget으로 식별. 구조 접미사:
- `_list`: flat 반복 항목 (issue_list, merge_request_list, commit_list, pipeline_list, ...)
- `_detail`: 단일 entity view (issue_detail, blob_detail, commit_detail, ...)
- `_new_form`: 생성 form (issue_new_form, branch_new_form, ...)
- `settings_*`: settings 관련 form (settings_general/repository/ci_cd/...)
- 기타: `main`, `help_landing`, `topic_list`, `wiki`, `search_page`, `profile`, `preferences`, `notifications`, `edit` 등

**Variant (leaf 내부 sub-division, optional)** — action 차이가 filter/sort/state 축뿐일 때. 예: `todo_list/pending`·`/done`, `project_list/yours`·`/starred`.

Reason 작성: URL > scope chrome 근거 > widget 구조 > widget-specific action. Title 단독 근거 금지 (SPA back-nav 복원 이슈).

## Annotations (190)

| # | name | URL | class | reason |
|---|---|---|---|---|
| 1 | `a11yproject_issues` | `/a11yproject/a11yproject.com/-/issues` | **`project/issue_list`** | Scope=project. Widget=issue_list. Instance: a11yproject/a11yproject.com (다른 namespace). Namespace 변형 검증용. |
| 2 | `account_edit` | `/-/profile` | **`account/edit`** | Scope=account (v0.5 신규, `/-/profile/*` 전용 사이드바 14 action 실측: Account/Applications/SSH Keys 등). Widget=edit — `/-/profile`, profile edit form. |
| 3 | `account_notifications` | `/-/profile/notifications` | **`account/notifications`** | Scope=account. Widget=notifications — URL `/-/profile/notifications`, notification settings form. Same sidebar. |
| 4 | `account_preferences` | `/-/profile/preferences` | **`account/preferences`** | Scope=account. Widget=preferences — URL `/-/profile/preferences`, preferences form. Same sidebar (14 action). |
| 5 | `dashboard_groups` | `/dashboard/groups` | **`dashboard/group_list`** | Scope=dashboard. Widget=group_list (h1=Groups, filter form 3 + li=39 그룹 카드). 사용자 소속 group flat list. |
| 6 | `dashboard_home` | `/dashboard` | **`dashboard/project_list/yours`** | Scope=dashboard (공유 헤더 28 action, 실측). Widget=project_list (h2 project 이름 반복, li=73). Variant=yours (filter bar All/Personal). `/dashboard`는 Projects Yours 탭 기본 landing. |
| 7 | `dashboard_issues` | `/dashboard/issues` | **`dashboard/issue_list`** | Scope=dashboard. Widget=issue_list (filter form + issue row). Dashboard scope는 `New issue`/`Edit issues`(bulk)/`Import/Export CSV` 없음(template에 부재, empty state 무관). `Select project to create issue`로 compensation. |
| 8 | `dashboard_merge_requests` | `/dashboard/merge_requests` | **`dashboard/merge_request_list`** | Scope=dashboard. Widget=merge_request_list (filter form + MR row). `New MR`, `Edit MR`(bulk), `Export CSV`, `Subscribe` 없음. `Select project to create MR`로 compensation. |
| 9 | `dashboard_projects` | `/dashboard/projects` | **`dashboard/project_list/yours`** | Scope=dashboard. Widget=project_list (h1=Projects, h2 반복, li=73). Variant=yours (filter All/Personal). `dashboard_home`과 동일 class. |
| 10 | `dashboard_projects_starred` | `/dashboard/projects/starred` | **`dashboard/project_list/starred`** | Scope=dashboard. Widget=project_list. Variant=starred — `/yours`와 action 다름(filter_all/filter_personal 없음, 실측). 상단 탭 Starred active. |
| 11 | `dashboard_todos` | `/dashboard/todos` | **`dashboard/todo_list/pending`** | Scope=dashboard. Widget=todo_list. Variant=pending (default). Action: `Mark all as done`/`Undo mark all as done` 포함. URL `/dashboard/todos`. |
| 12 | `dashboard_todos_done` | `/dashboard/todos?state=done` | **`dashboard/todo_list/done`** | Scope=dashboard. Widget=todo_list. Variant=done — `Mark all as done`/`Undo` 2개 action 누락 (`state=done` query로 routing). URL `?state=done`. |
| 13 | `empathy_main` | `/byteblaze/empathy-prompts` | **`project/main`** | Scope=project. Widget=main. Instance: byteblaze/empathy-prompts. Rule 일반화 검증용. |
| 14 | `empathy_merge_requests` | `/byteblaze/empathy-prompts/-/merge_requests` | **`project/merge_request_list`** | Scope=project. Widget=merge_request_list. Instance: byteblaze/empathy-prompts의 MR 리스트 (MR 존재 project). Rule 일반화 검증용. |
| 15 | `explore_projects` | `/explore/projects` | **`explore/project_list/all`** | Scope=explore. Widget=project_list. Variant=all (default tab). URL `/explore/projects`. Filter bar: All/Most stars/Trending + Visibility. `/starred`·`/trending` siblings. |
| 16 | `explore_projects_topics` | `/explore/projects/topics` | **`explore/topic_list`** | Scope=explore. Widget=topic_list — project_list의 filter tab bar 없음, item은 avatar+이름 minimal tile (rich project card와 대조). 실측으로 widget 다름 확인. |
| 17 | `global_snippets` | `/dashboard/snippets` | **`global/snippet_list`** | Scope=global (URL `/snippets`, 특정 scope 없음). Widget=snippet_list — global 범위 snippet 반복 list. `project/snippet_list`와 sibling widget (다른 scope). |
| 18 | `help_page` | `/help` | **`global/help_landing`** | Scope=global (URL `/help`, 특정 scope 사이드바 없음). Widget=help_landing — h2 multi-section(Popular topics, DevOps lifecycle 등 5+), table 6. List/form 아닌 multi-section landing. |
| 19 | `iter2_` | `/` | **`global/root_redirect`** | URL `/`. Bare root. Redirects to dashboard/projects. Kept as global/root_redirect class. |
| 20 | `iter2_abuse_reports_new` | `/-/abuse_reports/new?ref_url=http%3A%2F%2Flocalhost%3A8023%2Fbyteblaze%2Fempathy-prompts%2F-%2Fissues%2F10&user_id=2393` | **`global/abuse_report_new_form`** | Scope=global. URL `/-/abuse_reports/new`. Abuse report submission form. |
| 21 | `iter2_explore_projects_starred` | `/explore/projects/starred` | **`explore/project_list/starred`** | Scope=explore. Widget=project_list. Variant=starred. URL `/explore/projects/starred`. |
| 22 | `iter2_explore_projects_topics_topic_name` | `/explore/projects/topics/accessibility` | **`explore/topic_detail`** | Scope=explore. Widget=topic_detail — URL `/explore/projects/topics/{topic_name}`. 특정 topic에 속한 project 목록 (topic_list의 detail instance). |
| 23 | `iter2_explore_projects_trending` | `/explore/projects/trending` | **`explore/project_list/trending`** | Scope=explore. Widget=project_list. Variant=trending. URL `/explore/projects/trending`. |
| 24 | `iter2_help_api_file` | `/help/api/index.md` | **`global/help_page`** | Help page `/help/api/*`. |
| 25 | `iter2_help_api_graphql_file` | `/help/api/graphql/index.md` | **`global/help_page`** | Help page `/help/api/graphql/*`. |
| 26 | `iter2_help_ci_jobs_file` | `/help/ci/jobs/index.md` | **`global/help_page`** | Help page `/help/ci/jobs/*`. |
| 27 | `iter2_help_ci_pipelines_file` | `/help/ci/pipelines/merge_trains.md` | **`global/help_page`** | Help page `/help/ci/pipelines/*`. |
| 28 | `iter2_help_ci_runners_file` | `/help/ci/runners/runners_scope.md` | **`global/help_page`** | Help page `/help/ci/runners/*`. |
| 29 | `iter2_help_ci_variables_file` | `/help/ci/variables/where_variables_can_be_used.md` | **`global/help_page`** | Help page `/help/ci/variables/*`. |
| 30 | `iter2_help_ci_yaml_file` | `/help/ci/yaml/index.md` | **`global/help_page`** | Help page `/help/ci/yaml/*`. |
| 31 | `iter2_help_development_contributing_file` | `/help/development/contributing/issue_workflow.md` | **`global/help_page`** | Help page `/help/development/contributing/*`. |
| 32 | `iter2_help_development_documentation_file` | `/help/development/documentation/index.md` | **`global/help_page`** | Help page `/help/development/documentation/*`. |
| 33 | `iter2_help_development_documentation_site_architecture_file` | `/help/development/documentation/site_architecture/index.md` | **`global/help_page`** | Help page nested under development/documentation. |
| 34 | `iter2_help_development_file` | `/help/development/index.md` | **`global/help_page`** | Help page `/help/development/*`. |
| 35 | `iter2_help_install_file` | `/help/install/install_methods.md` | **`global/help_page`** | Help page `/help/install/*`. |
| 36 | `iter2_help_integration_file` | `/help/integration/index.md` | **`global/help_page`** | Help page `/help/integration/*`. |
| 37 | `iter2_help_operations_file` | `/help/operations/index.md` | **`global/help_page`** | Help page `/help/operations/*`. |
| 38 | `iter2_help_operations_incident_management_file` | `/help/operations/incident_management/alerts.md` | **`global/help_page`** | Help page nested under operations. |
| 39 | `iter2_help_raketasks_file` | `/help/raketasks/backup_restore.md` | **`global/help_page`** | Help page `/help/raketasks/*`. |
| 40 | `iter2_help_security_file` | `/help/security/reset_user_password.md` | **`global/help_page`** | Help page `/help/security/*`. |
| 41 | `iter2_help_subscriptions_img_file` | `/help/subscriptions/img/add-license.png` | **`global/help_image`** | Help image asset (.png) under /help/*/img/*. |
| 42 | `iter2_help_topics_autodevops_file` | `/help/topics/autodevops/index.md` | **`global/help_page`** | Help page `/help/topics/autodevops/*`. |
| 43 | `iter2_help_topics_file` | `/help/topics/set_up_organization.md` | **`global/help_page`** | Help page `/help/topics/*`. |
| 44 | `iter2_help_tutorials_file` | `/help/tutorials/index.md` | **`global/help_page`** | Help page `/help/tutorials/*`. |
| 45 | `iter2_help_update_file` | `/help/update/index.md` | **`global/help_page`** | Help page `/help/update/*`. |
| 46 | `iter2_help_user_analytics_file` | `/help/user/analytics/index.md` | **`global/help_page`** | Help page `/help/user/analytics/*`. |
| 47 | `iter2_help_user_application_security_file` | `/help/user/application_security/index.md` | **`global/help_page`** | Help page `/help/user/application_security/*`. |
| 48 | `iter2_help_user_application_security_sast_file` | `/help/user/application_security/sast/analyzers.md` | **`global/help_page`** | Help page nested under application_security/sast. |
| 49 | `iter2_help_user_file` | `/help/user/index.md` | **`global/help_page`** | Help page `/help/user/*`. |
| 50 | `iter2_help_user_group_epics_file` | `/help/user/group/epics/index.md` | **`global/help_page`** | Help page `/help/user/group/epics/*`. |
| 51 | `iter2_help_user_group_file` | `/help/user/group/index.md` | **`global/help_page`** | Help page `/help/user/group/*`. |
| 52 | `iter2_help_user_img_file` | `/help/user/img/inline_diff_01_v13_3.png` | **`global/help_image`** | Help image asset under /help/user/img/*. |
| 53 | `iter2_help_user_profile_file` | `/help/user/profile/index.md` | **`global/help_page`** | Help page `/help/user/profile/*`. |
| 54 | `iter2_help_user_profile_img_file` | `/help/user/profile/img/personal_readme_setup_v14_5.png` | **`global/help_image`** | Help image asset under /help/user/profile/img/*. |
| 55 | `iter2_help_user_project_file` | `/help/user/project/service_desk.html` | **`global/help_page`** | Help page `/help/user/project/*`. |
| 56 | `iter2_help_user_project_import_file` | `/help/user/project/import/index.md` | **`global/help_page`** | Help page `/help/user/project/import/*`. |
| 57 | `iter2_help_user_project_issues_file` | `/help/user/project/issues/managing_issues.md` | **`global/help_page`** | Help page `/help/user/project/issues/*`. |
| 58 | `iter2_help_user_project_merge_requests_file` | `/help/user/project/merge_requests/squash_and_merge.md` | **`global/help_page`** | Help page `/help/user/project/merge_requests/*`. |
| 59 | `iter2_help_user_project_releases_file` | `/help/user/project/releases/index.md` | **`global/help_page`** | Help page `/help/user/project/releases/*`. |
| 60 | `iter2_help_user_project_repository_file` | `/help/user/project/repository/web_editor.md` | **`global/help_page`** | Help page `/help/user/project/repository/*`. |
| 61 | `iter2_help_user_project_settings_file` | `/help/user/project/settings/index.md` | **`global/help_page`** | Help page `/help/user/project/settings/*`. |
| 62 | `iter2_ide_project_a11yproject_a11yproject_com_merge_requests_id` | `/-/ide/project/a11yproject/a11yproject.com/tree/github/fork/Roshanjossey/1478-fix-404-urls/-/src/_data/resources.json/` | **`ide/mr_view`** | Scope=ide (new scope, Web IDE). URL `/-/ide/project/{ns}/{proj}/tree/{branch}/...` or `/merge_requests/{id}`. In-browser code editor for MR review. |
| 63 | `iter2_ns_proj_alert_management` | `/byteblaze/a11y-syntax-highlighting/-/alert_management` | **`project/alert_management`** | Scope=project. URL `/-/alert_management`. Alert management dashboard. |
| 64 | `iter2_ns_proj_ci_editor` | `/byteblaze/a11y-syntax-highlighting/-/ci/editor?branch_name=main` | **`project/ci_editor`** | Scope=project. URL `/-/ci/editor?branch_name={branch}`. Interactive pipeline yaml editor. |
| 65 | `iter2_ns_proj_clusters` | `/byteblaze/a11y-syntax-highlighting/-/clusters` | **`project/cluster_list`** | Scope=project. URL `/-/clusters`. Kubernetes clusters 반복 list. |
| 66 | `iter2_ns_proj_compare` | `/byteblaze/a11y-syntax-highlighting/-/compare?from=main&to=main` | **`project/compare_form`** | Scope=project. URL `/-/compare`. Branch/ref comparison form with diff output. |
| 67 | `iter2_ns_proj_error_tracking` | `/byteblaze/a11y-syntax-highlighting/-/error_tracking` | **`project/error_tracking`** | Scope=project. URL `/-/error_tracking`. Error tracking dashboard. |
| 68 | `iter2_ns_proj_feature_flags` | `/byteblaze/a11y-syntax-highlighting/-/feature_flags` | **`project/feature_flag_list`** | Scope=project. URL `/-/feature_flags`. Feature flag 반복 list. |
| 69 | `iter2_ns_proj_forks_new` | `/byteblaze/a11y-syntax-highlighting/-/forks/new` | **`project/fork_new_form`** | Scope=project. URL `/-/forks/new`. Fork creation form. |
| 70 | `iter2_ns_proj_graphs_branch` | `/byteblaze/a11y-syntax-highlighting/-/graphs/main` | **`project/contributor_graph`** | Scope=project. URL `/-/graphs/{branch}`. Contributors visualization (commits over time). |
| 71 | `iter2_ns_proj_graphs_branch_charts` | `/byteblaze/a11y-syntax-highlighting/-/graphs/main/charts` | **`project/repository_analytics`** | Scope=project. URL `/-/graphs/{branch}/charts`. Repository analytics charts. |
| 72 | `iter2_ns_proj_hooks` | `/byteblaze/a11y-syntax-highlighting/-/hooks` | **`project/webhook_list`** | Scope=project. URL `/-/hooks`. Webhook 반복 list. |
| 73 | `iter2_ns_proj_import_jira` | `/byteblaze/a11y-syntax-highlighting/-/import/jira` | **`project/jira_import_form`** | Scope=project. URL `/-/import/jira`. Jira issue import form. |
| 74 | `iter2_ns_proj_incidents` | `/byteblaze/a11y-syntax-highlighting/-/incidents` | **`project/incident_list`** | Scope=project. URL `/-/incidents`. Incident 반복 list (monitoring). |
| 75 | `iter2_ns_proj_infrastructure_registry` | `/byteblaze/a11y-syntax-highlighting/-/infrastructure_registry` | **`project/infrastructure_registry`** | Scope=project. URL `/-/infrastructure_registry`. Terraform/cluster infrastructure registry. |
| 76 | `iter2_ns_proj_issues_atom` | `/byteblaze/a11y-syntax-highlighting/-/issues.atom?feed_token=TMN_bBn9Z48qVbUFZV45` | **`project/issue_feed`** | Scope=project. URL `/-/issues.atom`. Atom RSS feed for issues (machine-readable). |
| 77 | `iter2_ns_proj_labels_id_edit` | `/byteblaze/a11y-syntax-highlighting/-/labels/1912/edit` | **`project/label_edit_form`** | Scope=project. URL `/-/labels/{id}/edit`. Label edit form. |
| 78 | `iter2_ns_proj_merge_requests_atom_state_opened` | `/byteblaze/a11y-syntax-highlighting/-/merge_requests.atom?feed_token=TMN_bBn9Z48qVbUFZV45&state=opened` | **`project/merge_request_feed`** | Scope=project. URL `/-/merge_requests.atom`. Atom RSS feed for MRs. |
| 79 | `iter2_ns_proj_merge_requests_id_commits` | `/byteblaze/a11y-webring.club/-/merge_requests/40/commits` | **`project/merge_request_commits`** | Scope=project. URL `/-/merge_requests/{id}/commits`. MR commits tab — chronological commit list within MR. |
| 80 | `iter2_ns_proj_merge_requests_id_diffs` | `/byteblaze/a11y-webring.club/-/merge_requests/40/diffs` | **`project/merge_request_diff`** | Scope=project. URL `/-/merge_requests/{id}/diffs`. MR diff tab — code change visualization. |
| 81 | `iter2_ns_proj_merge_requests_id_edit` | `/byteblaze/a11y-webring.club/-/merge_requests/40/edit` | **`project/merge_request_edit_form`** | Scope=project. URL `/-/merge_requests/{id}/edit`. MR edit form. |
| 82 | `iter2_ns_proj_merge_requests_id_pipelines` | `/byteblaze/a11y-webring.club/-/merge_requests/40/pipelines` | **`project/merge_request_pipelines`** | Scope=project. URL `/-/merge_requests/{id}/pipelines`. MR pipelines tab — CI runs for this MR. |
| 83 | `iter2_ns_proj_metrics` | `/byteblaze/a11y-syntax-highlighting/-/metrics` | **`project/metric_dashboard`** | Scope=project. URL `/-/metrics`. Performance metrics dashboard. |
| 84 | `iter2_ns_proj_milestones_id` | `/a11yproject/a11yproject.com/-/milestones/6#tab-issues` | **`project/milestone_detail`** | Scope=project. URL `/-/milestones/{id}`. Single milestone entity view. |
| 85 | `iter2_ns_proj_milestones_id_edit` | `/a11yproject/a11yproject.com/-/milestones/6/edit` | **`project/milestone_edit_form`** | Scope=project. URL `/-/milestones/{id}/edit`. Milestone edit form. |
| 86 | `iter2_ns_proj_network_branch` | `/byteblaze/a11y-syntax-highlighting/-/network/main` | **`project/network_graph`** | Scope=project. URL `/-/network/{branch}`. Git branch network visualization. |
| 87 | `iter2_ns_proj_new` | `/import/github/new` | **`global/import_form`** | Scope=global. URL `/import/{service}/new`. Third-party repo import form (generalized). |
| 88 | `iter2_ns_proj_new_main` | `/byteblaze/a11y-webring.club/-/new/main/` | **`project/file_new_form`** | Scope=project. URL `/-/new/{branch}`. New file creation form. |
| 89 | `iter2_ns_proj_packages` | `/byteblaze/a11y-syntax-highlighting/-/packages` | **`project/package_list`** | Scope=project. URL `/-/packages`. Package registry list. |
| 90 | `iter2_ns_proj_pipelines_charts` | `/byteblaze/a11y-syntax-highlighting/-/pipelines/charts` | **`project/cicd_analytics`** | Scope=project. URL `/-/pipelines/charts`. CI/CD pipeline analytics charts. |
| 91 | `iter2_ns_proj_pipelines_id` | `/byteblaze/a11y-webring.club/-/pipelines/1823` | **`project/pipeline_detail`** | Scope=project. URL `/-/pipelines/{id}`. Single pipeline entity view. |
| 92 | `iter2_ns_proj_releases` | `/byteblaze/a11y-syntax-highlighting/-/releases` | **`project/release_list`** | Scope=project. URL `/-/releases`. Project release 반복 list. |
| 93 | `iter2_ns_proj_security_configuration` | `/byteblaze/a11y-syntax-highlighting/-/security/configuration` | **`project/security_config`** | Scope=project. URL `/-/security/configuration`. Security scanning configuration. |
| 94 | `iter2_ns_proj_settings_merge_requests` | `/byteblaze/a11y-syntax-highlighting/-/settings/merge_requests` | **`project/settings_merge_requests`** | Scope=project. URL `/-/settings/merge_requests`. MR settings form. Flat (no sub-nav). |
| 95 | `iter2_ns_proj_settings_operations` | `/byteblaze/a11y-syntax-highlighting/-/settings/operations` | **`project/settings_operations`** | Scope=project. URL `/-/settings/operations`. Monitoring/operations settings. |
| 96 | `iter2_ns_proj_settings_packages_and_registries` | `/byteblaze/a11y-syntax-highlighting/-/settings/packages_and_registries` | **`project/settings_packages`** | Scope=project. URL `/-/settings/packages_and_registries`. Package/registry settings. |
| 97 | `iter2_ns_proj_snippets_new` | `/byteblaze/a11y-syntax-highlighting/-/snippets/new` | **`project/snippet_new_form`** | Scope=project. URL `/-/snippets/new`. Snippet creation form. |
| 98 | `iter2_ns_proj_starrers` | `/byteblaze/a11y-syntax-highlighting/-/starrers` | **`project/starrer_list`** | Scope=project. URL `/{ns}/{proj}/-/starrers`. Users who starred this project. |
| 99 | `iter2_ns_proj_terraform` | `/byteblaze/a11y-syntax-highlighting/-/terraform` | **`project/terraform_list`** | Scope=project. URL `/-/terraform`. Terraform state 반복 list. |
| 100 | `iter2_ns_proj_tree_branch_path` | `/byteblaze/a11y-webring.club/-/tree/github/fork/davepgreene/add-verification-function` | **`project/file_list`** | Scope=project. URL `/-/tree/{branch}/{path*}` with multi-segment branch name (e.g., `github/fork/...`). Same widget as `project/file_list` — rule 일반화 instance. |
| 101 | `iter2_ns_proj_usage_quotas` | `/byteblaze/a11y-syntax-highlighting/-/usage_quotas` | **`project/usage_quota`** | Scope=project. URL `/-/usage_quotas`. Storage/compute usage quotas page. |
| 102 | `iter2_ns_proj_value_stream_analytics` | `/byteblaze/a11y-syntax-highlighting/-/value_stream_analytics?created_after=2026-03-22&created_before=2026-04-20&stage_id=issue&sort=end_event&direction=desc&page=1` | **`project/value_stream_analytics`** | Scope=project. URL `/-/value_stream_analytics`. Value stream metrics dashboard. |
| 103 | `iter2_personal_true` | `/?personal=true&sort=name_asc` | **`global/root_redirect`** | URL `/?personal=true&sort=name_asc`. Bare root with query. Redirects to dashboard in browser but URL-wise unique. Kept as global/root_redirect to avoid rule template conflict. |
| 104 | `iter2_users_username_contributed` | `/users/byteblaze/contributed` | **`user/contributed_project_list`** | Scope=user. URL `/users/{username}/contributed`. Contributed projects tab of user profile. |
| 105 | `iter2_users_username_followers` | `/users/byteblaze/followers` | **`user/follower_list`** | Scope=user. URL `/users/{username}/followers`. Followers tab. |
| 106 | `iter2_users_username_following` | `/users/byteblaze/following` | **`user/following_list`** | Scope=user. URL `/users/{username}/following`. Following tab. |
| 107 | `iter2_users_username_groups` | `/users/byteblaze/groups` | **`user/group_list`** | Scope=user. URL `/users/{username}/groups`. Groups tab. |
| 108 | `iter2_users_username_projects` | `/users/byteblaze/projects` | **`user/project_list`** | Scope=user. URL `/users/{username}/projects`. Personal projects tab. |
| 109 | `iter2_users_username_snippets` | `/users/byteblaze/snippets` | **`user/snippet_list`** | Scope=user. URL `/users/{username}/snippets`. User snippets tab. |
| 110 | `iter2_users_username_starred` | `/users/byteblaze/starred` | **`user/starred_project_list`** | Scope=user. URL `/users/{username}/starred`. Starred projects tab. |
| 111 | `iter3_account_account` | `/-/profile/account` | **`account/account`** | Scope=account. URL `/-/profile/account`. Basic account info (username, email). |
| 112 | `iter3_account_active_sessions` | `/-/profile/active_sessions` | **`account/active_sessions`** | Scope=account. URL `/-/profile/active_sessions`. Active browser sessions. |
| 113 | `iter3_account_applications` | `/-/profile/applications` | **`account/applications`** | Scope=account. URL `/-/profile/applications`. OAuth applications page. |
| 114 | `iter3_account_audit_log` | `/-/profile/audit_log` | **`account/audit_log`** | Scope=account. URL `/-/profile/audit_log`. Authentication/activity audit log. |
| 115 | `iter3_account_chat_names` | `/-/profile/chat_names` | **`account/chat_names`** | Scope=account. URL `/-/profile/chat_names`. Chat integration names page. |
| 116 | `iter3_account_emails` | `/-/profile/emails` | **`account/emails`** | Scope=account. URL `/-/profile/emails`. Email management. |
| 117 | `iter3_account_gpg_keys` | `/-/profile/gpg_keys` | **`account/gpg_keys`** | Scope=account. URL `/-/profile/gpg_keys`. GPG key management. |
| 118 | `iter3_account_keys` | `/-/profile/keys` | **`account/keys`** | Scope=account. URL `/-/profile/keys`. SSH key management page. |
| 119 | `iter3_account_password_edit` | `/-/profile/password/edit` | **`account/password_edit`** | Scope=account. URL `/-/profile/password/edit`. Password change form. |
| 120 | `iter3_account_personal_access_tokens` | `/-/profile/personal_access_tokens` | **`account/personal_access_tokens`** | Scope=account. URL `/-/profile/personal_access_tokens`. Personal access token management. |
| 121 | `iter3_account_two_factor_auth` | `/-/profile/two_factor_auth` | **`account/two_factor_auth`** | Scope=account. URL `/-/profile/two_factor_auth`. 2FA setup page. |
| 122 | `iter3_global_snippet_new` | `/-/snippets/new` | **`global/snippet_new_form`** | Scope=global. URL `/-/snippets/new`. Global snippet creation form. |
| 123 | `iter3_ide_edit` | `/-/ide/project/byteblaze/a11y-syntax-highlighting/edit/main/-/` | **`ide/edit_view`** | Scope=ide. URL `/-/ide/project/{ns}/{proj}/edit/{branch}/...`. Web IDE edit mode for file. |
| 124 | `iter3_ide_mr` | `/-/ide/project/byteblaze/a11y-webring.club/merge_requests/40` | **`ide/mr_detail`** | Scope=ide. URL `/-/ide/project/{ns}/{proj}/merge_requests/{id}`. Web IDE showing MR changes. |
| 125 | `iter3_import_bitbucket_server` | `/import/bitbucket_server/new` | **`global/import_form`** | Bitbucket Server import form — same class as github/jira. |
| 126 | `iter3_import_fogbugz` | `/import/fogbugz/new` | **`global/import_form`** | Fogbugz import form — same class. |
| 127 | `iter3_import_github` | `/import/github/new` | **`global/import_form`** | Scope=global. URL `/import/{service}/new`. Third-party import form (GitHub/Bitbucket/etc.). |
| 128 | `iter3_project_branches_active` | `/byteblaze/a11y-syntax-highlighting/-/branches/active` | **`project/branch_list`** | Instance of project/branch_list with filter suffix `/active`. Same widget. |
| 129 | `iter3_project_branches_all` | `/byteblaze/a11y-syntax-highlighting/-/branches/all` | **`project/branch_list`** | Instance of project/branch_list with filter suffix `/all`. Same widget. |
| 130 | `iter3_project_branches_stale` | `/byteblaze/a11y-syntax-highlighting/-/branches/stale` | **`project/branch_list`** | Instance of project/branch_list with filter suffix `/stale`. Same widget. |
| 131 | `iter3_project_ci_lint` | `/byteblaze/a11y-syntax-highlighting/-/ci/lint` | **`project/ci_lint`** | Scope=project. URL `/-/ci/lint`. CI yaml syntax validator. |
| 132 | `iter3_project_clusters_new_docs` | `/byteblaze/a11y-syntax-highlighting/-/clusters/new_cluster_docs` | **`project/cluster_new_docs`** | Scope=project. URL `/-/clusters/new_cluster_docs`. Kubernetes cluster setup docs. |
| 133 | `iter3_project_environment_new` | `/byteblaze/a11y-syntax-highlighting/-/environments/new` | **`project/environment_new_form`** | Scope=project. URL `/-/environments/new`. Environment creation form. |
| 134 | `iter3_project_feature_flag_new` | `/byteblaze/a11y-syntax-highlighting/-/feature_flags/new` | **`project/feature_flag_new_form`** | Scope=project. URL `/-/feature_flags/new`. Feature flag creation form. |
| 135 | `iter3_project_feature_flags_user_lists` | `/byteblaze/a11y-syntax-highlighting/-/feature_flags_user_lists` | **`project/feature_flag_user_list`** | Scope=project. URL `/-/feature_flags_user_lists`. User lists for feature flags. |
| 136 | `iter3_project_find_file` | `/byteblaze/a11y-syntax-highlighting/-/find_file/main` | **`project/file_search`** | Scope=project. URL `/-/find_file/{branch}`. File search in repo. |
| 137 | `iter3_project_history` | `/byteblaze/a11y-syntax-highlighting/history` | **`project/history`** | Scope=project. URL `/{ns}/{proj}/history`. Repository history (redirect alias). |
| 138 | `iter3_project_label_new` | `/byteblaze/a11y-syntax-highlighting/-/labels/new` | **`project/label_new_form`** | Scope=project. URL `/-/labels/new`. Label creation form. |
| 139 | `iter3_project_pipeline_schedule_new` | `/byteblaze/a11y-syntax-highlighting/-/pipeline_schedules/new` | **`project/pipeline_schedule_new_form`** | Scope=project. URL `/-/pipeline_schedules/new`. Pipeline schedule creation. |
| 140 | `iter3_project_protected_branches` | `/byteblaze/a11y-syntax-highlighting/-/protected_branches/170` | **`project/protected_branch_detail`** | Scope=project. URL `/-/protected_branches/{id}`. Protected branch rule. |
| 141 | `iter3_project_release_new` | `/byteblaze/a11y-syntax-highlighting/-/releases/new` | **`project/release_new_form`** | Scope=project. URL `/-/releases/new`. Release creation form. |
| 142 | `iter3_project_settings_integration_edit` | `/byteblaze/a11y-syntax-highlighting/-/settings/integrations/asana/edit` | **`project/settings_integration_edit`** | Scope=project. URL `/-/settings/integrations/{service}/edit`. Integration config form (Asana/Assembla/Bamboo/etc.). |
| 143 | `iter3_project_snippet_detail` | `/byteblaze/a11y-syntax-highlighting/-/snippets/1` | **`project/snippet_detail`** | Scope=project. URL `/-/snippets/{id}`. Single snippet view. |
| 144 | `iter3_project_upload_file` | `/byteblaze/empathy-prompts/uploads/2f21c9b357b42751d8cb814c6d06824b/test.gif` | **`project/upload_file`** | Scope=project. URL `/{ns}/{proj}/uploads/{sha}/{file}`. Uploaded media asset. |
| 145 | `iter4_project_blame` | `/byteblaze/empathy-prompts/-/blame/main/CONTRIBUTING.md` | **`project/blame_view`** | Scope=project. URL `/{ns}/{proj}/-/blame/{branch}/{path*}`. Git blame view. |
| 146 | `iter4_project_feature_flag_user_list_new` | `/byteblaze/a11y-syntax-highlighting/-/feature_flags_user_lists/new` | **`project/feature_flag_user_list_new_form`** | Scope=project. URL `/-/feature_flags_user_lists/new`. |
| 147 | `iter4_project_raw_file` | `/byteblaze/empathy-prompts/-/raw/main/CONTRIBUTING.md` | **`project/raw_file`** | Scope=project. URL `/{ns}/{proj}/-/raw/{branch}/{path*}`. Raw file content. |
| 148 | `iter4_project_release_detail` | `/byteblaze/empathy-prompts/-/releases/v0.1.0` | **`project/release_detail`** | Scope=project. URL `/{ns}/{proj}/-/releases/{tag}`. Single release detail. |
| 149 | `iter4_project_release_edit` | `/byteblaze/empathy-prompts/-/releases/v0.1.0/edit` | **`project/release_edit_form`** | Scope=project. URL `/{ns}/{proj}/-/releases/{tag}/edit`. Release edit form. |
| 150 | `iter5_ide_edit_master` | `/-/ide/project/byteblaze/solarized-prism-theme/edit/master/-` | **`ide/edit_view`** | Same class as iter3 /-/ide/.../edit/main/-; add master variant for {branch} generalization. |
| 151 | `iter5_project_file_new_master` | `/byteblaze/solarized-prism-theme/-/new/master` | **`project/file_new_form`** | Same class as iter2 /-/new/main; add master variant to trigger {branch} generalization. |
| 152 | `new_project_form` | `/projects/new` | **`global/new_project_form`** | Scope=global (URL `/projects/new`, project scope 아직 없음). Widget=new_project_form — h2='Create new project', form 5개, li=43 입력 필드 그룹. |
| 153 | `project_activity` | `/byteblaze/a11y-syntax-highlighting/activity` | **`project/activity_list`** | Scope=project. Widget=activity_list (URL `/activity`, event 시간순 반복 list). |
| 154 | `project_blob_detail` | `/byteblaze/a11y-syntax-highlighting/-/blob/main/README.md` | **`project/blob_detail`** | Scope=project. Widget=blob_detail — URL `/-/blob/{branch}/{path}`, 파일 한 건 내용 view. |
| 155 | `project_boards` | `/byteblaze/a11y-syntax-highlighting/-/boards` | **`project/issue_board`** | Scope=project. Widget=issue_board — URL `/-/boards`, kanban layout(list와 다른 widget). `project/issue_list`와 sibling class. |
| 156 | `project_branch_new_form` | `/byteblaze/a11y-syntax-highlighting/-/branches/new` | **`project/branch_new_form`** | Scope=project. Widget=branch_new_form — URL `/-/branches/new`, branch 생성 form. |
| 157 | `project_branches` | `/byteblaze/a11y-syntax-highlighting/-/branches` | **`project/branch_list`** | Scope=project. Widget=branch_list — URL `/-/branches`, branch row 반복 list. |
| 158 | `project_commit_detail` | `/byteblaze/a11y-syntax-highlighting/-/commit/62820763d9b5f3b25720596f542aaf89d917fb17` | **`project/commit_detail`** | Scope=project. Widget=commit_detail — URL `/-/commit/{sha}`, 단일 commit entity view. |
| 159 | `project_commits` | `/byteblaze/a11y-syntax-highlighting/-/commits/main` | **`project/commit_list`** | Scope=project. Widget=commit_list (URL `/-/commits/{branch}`, commit row 시간순 반복 list). |
| 160 | `project_environments` | `/byteblaze/a11y-syntax-highlighting/-/environments` | **`project/environment_list`** | Scope=project. Widget=environment_list — URL `/-/environments`, environment row 반복 list. |
| 161 | `project_forks` | `/byteblaze/a11y-syntax-highlighting/-/forks` | **`project/fork_list`** | Scope=project. Widget=fork_list (URL `/-/forks`, fork된 project 반복 list). |
| 162 | `project_issue_detail` | `/byteblaze/a11y-syntax-highlighting/-/issues/1` | **`project/issue_detail`** | Scope=project. Widget=issue_detail — URL `/-/issues/{id}`, 단일 issue entity view. |
| 163 | `project_issue_new_form` | `/byteblaze/a11y-syntax-highlighting/-/issues/new` | **`project/issue_new_form`** | Scope=project. Widget=issue_new_form — URL `/-/issues/new`, issue 생성 form. |
| 164 | `project_issues` | `/byteblaze/a11y-syntax-highlighting/-/issues` | **`project/issue_list`** | Scope=project. Widget=issue_list — `New issue`, `Edit issues`(bulk), `Import/Export CSV`, 확장 정렬(Priority/Popularity/Label priority) 포함. Dashboard scope와 다른 action 17+. |
| 165 | `project_jobs` | `/byteblaze/a11y-syntax-highlighting/-/jobs` | **`project/job_list`** | Scope=project. Widget=job_list — URL `/-/jobs`, CI job row 반복 list. |
| 166 | `project_labels` | `/byteblaze/a11y-syntax-highlighting/-/labels` | **`project/label_list`** | Scope=project. Widget=label_list (URL `/-/labels`, label 반복 list). |
| 167 | `project_main` | `/byteblaze/a11y-syntax-highlighting` | **`project/main`** | Scope=project (공유 사이드바 57 action, 실측 100% 동일). Widget=main — project root `/{namespace}/{project}`에서 navigation shell만 나타나는 entity landing. |
| 168 | `project_members` | `/byteblaze/a11y-syntax-highlighting/-/project_members` | **`project/member_list`** | Scope=project. Widget=member_list (URL `/-/project_members`, project 멤버 반복 list). |
| 169 | `project_merge_requests` | `/byteblaze/a11y-syntax-highlighting/-/merge_requests` | **`project/merge_request_list`** | Scope=project. Widget=merge_request_list — `New MR`, `Edit MR`(bulk), `Export CSV`, `Subscribe/Unsubscribe`, `Target-Branch` filter 포함. |
| 170 | `project_milestones` | `/byteblaze/a11y-syntax-highlighting/-/milestones` | **`project/milestone_list`** | Scope=project. Widget=milestone_list (URL `/-/milestones`, milestone 반복 list). |
| 171 | `project_mr_detail` | `/byteblaze/empathy-prompts/-/merge_requests/19` | **`project/merge_request_detail`** | Scope=project. Widget=merge_request_detail — URL `/-/merge_requests/{id}`, 단일 MR entity view. Instance는 empathy-prompts의 #19. |
| 172 | `project_mr_new_form` | `/byteblaze/a11y-syntax-highlighting/-/merge_requests/new` | **`project/merge_request_new_form`** | Scope=project. Widget=merge_request_new_form — URL `/-/merge_requests/new`, MR 생성 form. |
| 173 | `project_pipeline_schedules` | `/byteblaze/a11y-syntax-highlighting/-/pipeline_schedules` | **`project/schedule_list`** | Scope=project. Widget=schedule_list — URL `/-/pipeline_schedules`, schedule row 반복 list. |
| 174 | `project_pipelines` | `/byteblaze/a11y-syntax-highlighting/-/pipelines` | **`project/pipeline_list`** | Scope=project. Widget=pipeline_list — URL `/-/pipelines`, pipeline row 반복 list. |
| 175 | `project_settings_access_tokens` | `/byteblaze/a11y-syntax-highlighting/-/settings/access_tokens` | **`project/settings_access_tokens`** | Scope=project. Widget=settings_access_tokens — URL `/-/settings/access_tokens`. Flat. |
| 176 | `project_settings_ci_cd` | `/byteblaze/a11y-syntax-highlighting/-/settings/ci_cd` | **`project/settings_ci_cd`** | Scope=project. Widget=settings_ci_cd — URL `/-/settings/ci_cd`. Flat. |
| 177 | `project_settings_general` | `/byteblaze/a11y-syntax-highlighting/edit` | **`project/settings_general`** | Scope=project. Widget=settings_general — URL `/edit` (project 최상위 edit). v0.5 retract: settings 전용 sub-nav 없음(사이드바 artifact) → flat widget. |
| 178 | `project_settings_integrations` | `/byteblaze/a11y-syntax-highlighting/-/settings/integrations` | **`project/settings_integrations`** | Scope=project. Widget=settings_integrations — URL `/-/settings/integrations`. Flat. |
| 179 | `project_settings_repository` | `/byteblaze/a11y-syntax-highlighting/-/settings/repository` | **`project/settings_repository`** | Scope=project. Widget=settings_repository — URL `/-/settings/repository`. Flat (내부 sub-nav 아님). |
| 180 | `project_snippets` | `/byteblaze/a11y-syntax-highlighting/-/snippets` | **`project/snippet_list`** | Scope=project. Widget=snippet_list — URL `/-/snippets`, project 범위 snippet 반복 list. |
| 181 | `project_tag_detail` | `/byteblaze/empathy-prompts/-/tags/v0.1.0` | **`project/tag_detail`** | Scope=project. Widget=tag_detail — URL `/-/tags/{name}`, 단일 tag view. Instance는 byteblaze/empathy-prompts의 v0.1.0. |
| 182 | `project_tag_new_form` | `/byteblaze/a11y-syntax-highlighting/-/tags/new` | **`project/tag_new_form`** | Scope=project. Widget=tag_new_form — URL `/-/tags/new`, tag 생성 form. |
| 183 | `project_tags` | `/byteblaze/a11y-syntax-highlighting/-/tags` | **`project/tag_list`** | Scope=project. Widget=tag_list — URL `/-/tags`, tag row 반복 list. |
| 184 | `project_tree` | `/byteblaze/a11y-syntax-highlighting/-/tree/main` | **`project/file_list`** | Scope=project. Widget=file_list (URL `/-/tree/{branch}(/{path*})?`, 폴더/파일 flat table). 하위 폴더 이동 시 URL 깊어져도 같은 class. |
| 185 | `project_wiki` | `/byteblaze/a11y-syntax-highlighting/-/wikis/home` | **`project/wiki`** | Scope=project. Widget=wiki — URL `/-/wikis`. 현 인스턴스 empty state('Create your first page' CTA). Template 자체는 wiki page landing. |
| 186 | `search_page` | `/search` | **`global/search_page`** | Scope=global (URL `/search`, 특정 scope 없음). Widget=search_page — 검색 form + 결과 영역. |
| 187 | `user_activity` | `/users/byteblaze/activity` | **`user/activity_list`** | Scope=user (public user view). Widget=activity_list — URL `/users/{username}/activity`, user의 event 시간순 반복 list. `user/profile`(/byteblaze)과 sibling. |
| 188 | `user_profile` | `/byteblaze` | **`user/profile`** | Scope=user (URL `/{username}`은 user entity root). Widget=profile — h1=username, h2 project 이름 sub-list, form=2, li=56. User profile info + owned project sub-section. |
| 189 | `webring_issues` | `/byteblaze/a11y-webring.club/-/issues` | **`project/issue_list`** | Scope=project. Widget=issue_list. Instance: byteblaze/a11y-webring.club의 issue_list. Rule 일반화 검증용. |
| 190 | `webring_main` | `/byteblaze/a11y-webring.club` | **`project/main`** | Scope=project. Widget=main. Instance: byteblaze/a11y-webring.club (기존 a11y-syntax-highlighting과 다른 project). Rule 일반화 검증용. |

## 집계

- Total annotations: 190
- Unique class count: **138**
- Classes: `account/account`, `account/active_sessions`, `account/applications`, `account/audit_log`, `account/chat_names`, `account/edit`, `account/emails`, `account/gpg_keys`, `account/keys`, `account/notifications`, `account/password_edit`, `account/personal_access_tokens`, `account/preferences`, `account/two_factor_auth`, `dashboard/group_list`, `dashboard/issue_list`, `dashboard/merge_request_list`, `dashboard/project_list/starred`, `dashboard/project_list/yours`, `dashboard/todo_list/done`, `dashboard/todo_list/pending`, `explore/project_list/all`, `explore/project_list/starred`, `explore/project_list/trending`, `explore/topic_detail`, `explore/topic_list`, `global/abuse_report_new_form`, `global/help_image`, `global/help_landing`, `global/help_page`, `global/import_form`, `global/new_project_form`, `global/root_redirect`, `global/search_page`, `global/snippet_list`, `global/snippet_new_form`, `ide/edit_view`, `ide/mr_detail`, `ide/mr_view`, `project/activity_list`, `project/alert_management`, `project/blame_view`, `project/blob_detail`, `project/branch_list`, `project/branch_new_form`, `project/ci_editor`, `project/ci_lint`, `project/cicd_analytics`, `project/cluster_list`, `project/cluster_new_docs`, `project/commit_detail`, `project/commit_list`, `project/compare_form`, `project/contributor_graph`, `project/environment_list`, `project/environment_new_form`, `project/error_tracking`, `project/feature_flag_list`, `project/feature_flag_new_form`, `project/feature_flag_user_list`, `project/feature_flag_user_list_new_form`, `project/file_list`, `project/file_new_form`, `project/file_search`, `project/fork_list`, `project/fork_new_form`, `project/history`, `project/incident_list`, `project/infrastructure_registry`, `project/issue_board`, `project/issue_detail`, `project/issue_feed`, `project/issue_list`, `project/issue_new_form`, `project/jira_import_form`, `project/job_list`, `project/label_edit_form`, `project/label_list`, `project/label_new_form`, `project/main`, `project/member_list`, `project/merge_request_commits`, `project/merge_request_detail`, `project/merge_request_diff`, `project/merge_request_edit_form`, `project/merge_request_feed`, `project/merge_request_list`, `project/merge_request_new_form`, `project/merge_request_pipelines`, `project/metric_dashboard`, `project/milestone_detail`, `project/milestone_edit_form`, `project/milestone_list`, `project/network_graph`, `project/package_list`, `project/pipeline_detail`, `project/pipeline_list`, `project/pipeline_schedule_new_form`, `project/protected_branch_detail`, `project/raw_file`, `project/release_detail`, `project/release_edit_form`, `project/release_list`, `project/release_new_form`, `project/repository_analytics`, `project/schedule_list`, `project/security_config`, `project/settings_access_tokens`, `project/settings_ci_cd`, `project/settings_general`, `project/settings_integration_edit`, `project/settings_integrations`, `project/settings_merge_requests`, `project/settings_operations`, `project/settings_packages`, `project/settings_repository`, `project/snippet_detail`, `project/snippet_list`, `project/snippet_new_form`, `project/starrer_list`, `project/tag_detail`, `project/tag_list`, `project/tag_new_form`, `project/terraform_list`, `project/upload_file`, `project/usage_quota`, `project/value_stream_analytics`, `project/webhook_list`, `project/wiki`, `user/activity_list`, `user/contributed_project_list`, `user/follower_list`, `user/following_list`, `user/group_list`, `user/profile`, `user/project_list`, `user/snippet_list`, `user/starred_project_list`

중복 class (여러 페이지가 같은 class로 묶인 경우):
- `global/help_page` (35): iter2_help_api_file, iter2_help_api_graphql_file, iter2_help_ci_jobs_file, iter2_help_ci_pipelines_file, iter2_help_ci_runners_file, iter2_help_ci_variables_file, iter2_help_ci_yaml_file, iter2_help_development_contributing_file, iter2_help_development_documentation_file, iter2_help_development_documentation_site_architecture_file, iter2_help_development_file, iter2_help_install_file, iter2_help_integration_file, iter2_help_operations_file, iter2_help_operations_incident_management_file, iter2_help_raketasks_file, iter2_help_security_file, iter2_help_topics_autodevops_file, iter2_help_topics_file, iter2_help_tutorials_file, iter2_help_update_file, iter2_help_user_analytics_file, iter2_help_user_application_security_file, iter2_help_user_application_security_sast_file, iter2_help_user_file, iter2_help_user_group_epics_file, iter2_help_user_group_file, iter2_help_user_profile_file, iter2_help_user_project_file, iter2_help_user_project_import_file, iter2_help_user_project_issues_file, iter2_help_user_project_merge_requests_file, iter2_help_user_project_releases_file, iter2_help_user_project_repository_file, iter2_help_user_project_settings_file
- `global/import_form` (4): iter2_ns_proj_new, iter3_import_github, iter3_import_bitbucket_server, iter3_import_fogbugz
- `project/branch_list` (4): project_branches, iter3_project_branches_active, iter3_project_branches_stale, iter3_project_branches_all
- `global/help_image` (3): iter2_help_subscriptions_img_file, iter2_help_user_img_file, iter2_help_user_profile_img_file
- `project/issue_list` (3): project_issues, a11yproject_issues, webring_issues
- `project/main` (3): project_main, empathy_main, webring_main
- `dashboard/project_list/yours` (2): dashboard_home, dashboard_projects
- `global/root_redirect` (2): iter2_, iter2_personal_true
- `ide/edit_view` (2): iter3_ide_edit, iter5_ide_edit_master
- `project/file_list` (2): project_tree, iter2_ns_proj_tree_branch_path
- `project/file_new_form` (2): iter2_ns_proj_new_main, iter5_project_file_new_master
- `project/merge_request_list` (2): project_merge_requests, empathy_merge_requests

## Class tree

```
site/ (190 pages)
├── account/ (14 pages)
│   ├── account
│   ├── active_sessions
│   ├── applications
│   ├── audit_log
│   ├── chat_names
│   ├── edit
│   ├── emails
│   ├── gpg_keys
│   ├── keys
│   ├── notifications
│   ├── password_edit
│   ├── personal_access_tokens
│   ├── preferences
│   └── two_factor_auth
├── dashboard/ (8 pages)
│   ├── project_list/ (3 pages)
│   │   ├── starred
│   │   └── yours (×2)
│   ├── todo_list/ (2 pages)
│   │   ├── done
│   │   └── pending
│   ├── group_list
│   ├── issue_list
│   └── merge_request_list
├── explore/ (5 pages)
│   ├── project_list/ (3 pages)
│   │   ├── all
│   │   ├── starred
│   │   └── trending
│   ├── topic_detail
│   └── topic_list
├── global/ (50 pages)
│   ├── abuse_report_new_form
│   ├── help_image (×3)
│   ├── help_landing
│   ├── help_page (×35)
│   ├── import_form (×4)
│   ├── new_project_form
│   ├── root_redirect (×2)
│   ├── search_page
│   ├── snippet_list
│   └── snippet_new_form
├── ide/ (4 pages)
│   ├── edit_view (×2)
│   ├── mr_detail
│   └── mr_view
├── project/ (100 pages)
│   ├── activity_list
│   ├── alert_management
│   ├── blame_view
│   ├── blob_detail
│   ├── branch_list (×4)
│   ├── branch_new_form
│   ├── ci_editor
│   ├── ci_lint
│   ├── cicd_analytics
│   ├── cluster_list
│   ├── cluster_new_docs
│   ├── commit_detail
│   ├── commit_list
│   ├── compare_form
│   ├── contributor_graph
│   ├── environment_list
│   ├── environment_new_form
│   ├── error_tracking
│   ├── feature_flag_list
│   ├── feature_flag_new_form
│   ├── feature_flag_user_list
│   ├── feature_flag_user_list_new_form
│   ├── file_list (×2)
│   ├── file_new_form (×2)
│   ├── file_search
│   ├── fork_list
│   ├── fork_new_form
│   ├── history
│   ├── incident_list
│   ├── infrastructure_registry
│   ├── issue_board
│   ├── issue_detail
│   ├── issue_feed
│   ├── issue_list (×3)
│   ├── issue_new_form
│   ├── jira_import_form
│   ├── job_list
│   ├── label_edit_form
│   ├── label_list
│   ├── label_new_form
│   ├── main (×3)
│   ├── member_list
│   ├── merge_request_commits
│   ├── merge_request_detail
│   ├── merge_request_diff
│   ├── merge_request_edit_form
│   ├── merge_request_feed
│   ├── merge_request_list (×2)
│   ├── merge_request_new_form
│   ├── merge_request_pipelines
│   ├── metric_dashboard
│   ├── milestone_detail
│   ├── milestone_edit_form
│   ├── milestone_list
│   ├── network_graph
│   ├── package_list
│   ├── pipeline_detail
│   ├── pipeline_list
│   ├── pipeline_schedule_new_form
│   ├── protected_branch_detail
│   ├── raw_file
│   ├── release_detail
│   ├── release_edit_form
│   ├── release_list
│   ├── release_new_form
│   ├── repository_analytics
│   ├── schedule_list
│   ├── security_config
│   ├── settings_access_tokens
│   ├── settings_ci_cd
│   ├── settings_general
│   ├── settings_integration_edit
│   ├── settings_integrations
│   ├── settings_merge_requests
│   ├── settings_operations
│   ├── settings_packages
│   ├── settings_repository
│   ├── snippet_detail
│   ├── snippet_list
│   ├── snippet_new_form
│   ├── starrer_list
│   ├── tag_detail
│   ├── tag_list
│   ├── tag_new_form
│   ├── terraform_list
│   ├── upload_file
│   ├── usage_quota
│   ├── value_stream_analytics
│   ├── webhook_list
│   └── wiki
└── user/ (9 pages)
    ├── activity_list
    ├── contributed_project_list
    ├── follower_list
    ├── following_list
    ├── group_list
    ├── profile
    ├── project_list
    ├── snippet_list
    └── starred_project_list
```

- `/` 접미사 = internal node (scope 또는 intermediate class)
- `×N` = 같은 leaf class에 속한 instance 수 (variant 미포함 시 instance, variant 있으면 variant 아래 instance)

## 검증 방법

- 각 행의 user_class/user_reason이 적절한지 검토
- 수정 필요하면 말씀 → 수정 후 진행
- OK면 Stage A.e (rule 추출) 진행
