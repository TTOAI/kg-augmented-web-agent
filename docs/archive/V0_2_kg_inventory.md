# V0.2 — Frozen KG Structure Inventory

**Date**: 2026-04-19
**Status**: Complete

## Question
현 Frozen KG의 StatePattern / Action / LeadsToEdge / InfoType / RealizesEdge 분포와 품질은?

## KG metadata
- Path: `config/sites/gitlab/frozen_kg/2026-04-16T16-46-55Z.json`
- File size: 11.7 MB
- build_timestamp: `2026-04-16T16:46:55.393249+00:00`
- git_rev: `534c49d`
- builder_version: `0.1.0-hybrid`
- site: `gitlab`
- Top-level keys: ['site', 'build_timestamp', 'builder_version', 'source_mix', 'git_rev', 'state_patterns', 'infotypes', 'actions', 'leads_to_edges']

## Source Mix (from KG metadata)
- crawl: 33150
- llm: 593
- manual: 0

## StatePatterns
- **Total**: 3040

### Source distribution
- crawl: 2991
- llm: 49

### Trust distribution
- verified: 2991
- inferred: 49

### path_params count distribution
- 0 params: 3014 patterns
- 1 params: 6 patterns
- 2 params: 12 patterns
- 3 params: 7 patterns
- 4 params: 1 patterns

### identity_query_params count distribution
- 0 query params: 1953 patterns
- 1 query params: 245 patterns
- 2 query params: 514 patterns
- 3 query params: 70 patterns
- 4 query params: 62 patterns
- 5 query params: 77 patterns
- 6 query params: 23 patterns
- 7 query params: 3 patterns
- 8 query params: 1 patterns
- 9 query params: 1 patterns
- 10 query params: 1 patterns
- 11 query params: 16 patterns
- 12 query params: 2 patterns
- 13 query params: 16 patterns
- 14 query params: 11 patterns
- 15 query params: 2 patterns
- 17 query params: 14 patterns
- 18 query params: 1 patterns
- 23 query params: 13 patterns
- 25 query params: 1 patterns
- 26 query params: 1 patterns
- 36 query params: 1 patterns
- 37 query params: 9 patterns
- 38 query params: 3 patterns

### Sample StatePatterns (first 10 by id)

| id | url_pattern | path_params | query_params | source | trust |
|---|---|---|---|---|---|
| `crawl:1063633088__d93ea8bc5c` | `/1063633088` |  |  | crawl | verified |
| `crawl:23nata__ba8fed30af` | `/23nata` |  |  | crawl | verified |
| `crawl:459737087__f4468bb9ce` | `/459737087` |  |  | crawl | verified |
| `crawl:932356674__8c432b4d17` | `/932356674` |  |  | crawl | verified |
| `crawl:A001007008__cf06ade7eb` | `/A001007008` |  |  | crawl | verified |
| `crawl:AaliaLokhandwala__d2f3d334bb` | `/AaliaLokhandwala` |  |  | crawl | verified |
| `crawl:AccessiT3ch__05d75a5885` | `/AccessiT3ch` |  |  | crawl | verified |
| `crawl:Adam_Oudaimah_SCASE__93426a0bb8` | `/Adam-Oudaimah-SCASE` |  |  | crawl | verified |
| `crawl:AdeSupriyadi__e1b51156b8` | `/AdeSupriyadi` |  |  | crawl | verified |
| `crawl:AkkiSeven__dc893b4d3b` | `/AkkiSeven` |  |  | crawl | verified |

## InfoTypes
- **Total**: 37

### Source distribution
- llm: 37

### Trust label distribution
- inferred: 37

### Category distribution
- misc: 19
- project: 4
- issue: 3
- merge: 3
- group: 2
- milestone: 2
- snippet: 2
- import: 2

### realizes count distribution (# of StatePatterns each InfoType maps to)
- 1 realizes: 26 infotypes
- 2 realizes: 7 infotypes
- 3 realizes: 3 infotypes
- 5 realizes: 1 infotypes

### Complete InfoType list

| name | description | required_bindings | realizes | category |
|---|---|---|---|---|
| `activity_feed` | Activity stream for the dashboard, a project, or a namespace feed. |  | 3 | misc |
| `commit_list` | List of commits for a project at a given ref. | namespace,project_path,ref | 1 | misc |
| `dashboard` | Personal dashboard home for a signed-in user. |  | 1 | misc |
| `explore_home` | Top-level explore landing page. |  | 1 | misc |
| `file_blob` | View of a specific file in a repository at a given ref. | namespace,project_path,ref,fil | 1 | misc |
| `fork_list` | List of forks of a project. | namespace,project_path | 1 | misc |
| `group_creation_form` | Form to create a new group. |  | 1 | group |
| `group_list` | A list of groups in a personal dashboard or public explore area. |  | 2 | group |
| `help_page` | Help landing page or a specific documentation page. |  | 2 | misc |
| `home_page` | Top-level landing page of the application. |  | 1 | misc |
| `import_creation_form` | Form to start a new import from an external provider. | provider | 1 | import |
| `import_history` | History of previous imports. |  | 1 | import |
| `issue_creation_form` | Form to create a new issue in a project. | namespace,project_path | 1 | issue |
| `issue_detail` | Detail page for a specific issue. | namespace,project_path,iid | 1 | issue |
| `issue_list` | A list of issues, either across the user's dashboard or within a specific projec | namespace,project_path | 3 | issue |
| `label_list` | List of labels in a project. | namespace,project_path | 1 | misc |
| `merge_request_creation_form` | Form to create a new merge request in a project. | namespace,project_path | 1 | merge |
| `merge_request_detail` | Detail page for a specific merge request. | namespace,project_path,iid | 1 | merge |
| `merge_request_list` | A list of merge requests, either across the user's dashboard or within a specifi | namespace,project_path | 3 | merge |
| `milestone_detail` | Detail page for a specific milestone in a project. | namespace,project_path,milesto | 1 | milestone |
| `milestone_list` | A list of milestones, such as milestones on the dashboard or within a project se |  | 2 | milestone |
| `namespace_page` | Overview page for a namespace such as a user or group space. | namespace | 1 | misc |
| `pipeline_detail` | Detail page for a specific pipeline run. | namespace,project_path,pipelin | 1 | misc |
| `profile_page` | User profile root or one of its settings/profile sections. |  | 2 | misc |
| `project_creation_form` | Form to create a new project. |  | 1 | project |
| `project_list` | A list of projects in either the user's dashboard, the public explore area, a na |  | 5 | project |
| `project_member_list` | List of members of a project. | namespace,project_path | 1 | project |
| `project_page` | Project overview page or a generic project section page. | namespace,project_path | 2 | project |
| `repository_tree` | Repository file tree for a project at a given ref. | namespace,project_path,ref | 1 | misc |
| `search_results` | Search results scoped globally or to a project/group. |  | 1 | misc |
| `snippet_creation_form` | Form to create a new snippet, either globally or inside a project. | namespace,project_path | 2 | snippet |
| `snippet_list` | A list of code snippets in the dashboard or explore area. |  | 2 | snippet |
| `starrer_list` | List of users who starred a project. | namespace,project_path | 1 | misc |
| `todo_list` | Personal todo items list. |  | 1 | misc |
| `topic_list` | A list of project topics in the explore area. |  | 1 | misc |
| `user_tab` | A specific user profile tab page. | username,tab | 1 | misc |
| `web_ide_page` | Web IDE or editor route for a repository context. | ide_path | 1 | misc |

## Actions
- **Total**: 4109

### Source distribution
- crawl: 3979
- llm: 130

### Prefix distribution (action id)
- `crawl:form`: 3978
- `(no prefix)`: 130
- `crawl:nav`: 1

### Sample Actions (first 10)

| id | description | source |
|---|---|---|
| `confirm_new_account_password` | Confirm the new account password. | llm |
| `crawl:form:Arachni_arachni_commits_experimental:search` | Crawler-observed form input 'search' on page '/Arachni/arach | crawl |
| `crawl:form:Arachni_arachni_commits_master:search` | Crawler-observed form input 'search' on page '/Arachni/arach | crawl |
| `crawl:form:Arachni_arachni_compare:authenticity_token` | Crawler-observed form input 'authenticity_token' on page '/A | crawl |
| `crawl:form:Arachni_arachni_compare:from` | Crawler-observed form input 'from' on page '/Arachni/arachni | crawl |
| `crawl:form:Arachni_arachni_compare:from_project_id` | Crawler-observed form input 'from_project_id' on page '/Arac | crawl |
| `crawl:form:Arachni_arachni_compare:straight` | Crawler-observed form input 'straight' on page '/Arachni/ara | crawl |
| `crawl:form:Arachni_arachni_compare:to` | Crawler-observed form input 'to' on page '/Arachni/arachni/- | crawl |
| `crawl:form:Arachni_arachni_compare:to_project_id` | Crawler-observed form input 'to_project_id' on page '/Arachn | crawl |
| `crawl:form:Arachni_arachni_forks:filter_projects` | Crawler-observed form input 'filter_projects' on page '/Arac | crawl |

## LeadsToEdges
- **Total**: 26503

### Trust distribution
- verified: 26180
- inferred: 323

### Source distribution
- crawl: 26180
- llm: 323

### Action type distribution in edges
- `crawl:form`: 23241
- `crawl`: 2939
- `set_search_query`: 46
- `toggle_search_snippets`: 46
- `filter_search_by_repository_ref`: 46
- `filter_search_by_project`: 20
- `set_search_scope`: 20
- `toggle_search_code`: 20
- `filter_groups`: 2
- `set_profile_status_emoji`: 1
- `set_profile_status_message`: 1
- `set_profile_availability`: 1
- `set_status_clear_time`: 1
- `set_profile_timezone`: 1
- `set_profile_name`: 1
- `set_profile_pronouns`: 1
- `set_profile_name_pronunciation`: 1
- `set_profile_commit_email`: 1
- `set_profile_validation_password`: 1
- `set_profile_public_email`: 1
- `set_commit_email_preference`: 1
- `set_profile_skype_username`: 1
- `set_profile_linkedin_url`: 1
- `set_profile_twitter_username`: 1
- `set_profile_website_url`: 1
- `set_profile_location`: 1
- `set_profile_job_title`: 1
- `set_profile_organization`: 1
- `set_profile_bio`: 1
- `toggle_private_profile`: 1
- `toggle_include_private_contributions`: 1
- `filter_milestones_by_title`: 1
- `filter_milestones_by_state`: 1
- `toggle_create_ci_cd_only_project`: 1
- `set_project_name`: 1
- `select_project_namespace`: 1
- `set_project_path`: 1
- `set_project_visibility`: 1
- `toggle_initialize_project_with_readme`: 1
- `toggle_initialize_project_with_sast`: 1
- `select_project_template`: 1
- `set_project_description`: 1
- `set_project_import_url`: 1
- `set_project_import_username`: 1
- `set_project_import_password`: 1
- `select_parent_group`: 1
- `set_group_name`: 1
- `set_group_path`: 1
- `set_group_visibility`: 1
- `toggle_group_setup_for_company`: 1
- `set_group_jobs_to_be_done`: 1
- `set_gitlab_instance_url`: 1
- `set_gitlab_access_token`: 1
- `select_import_parent_group`: 1
- `set_import_group_path`: 1
- `upload_group_import_file`: 1
- `set_theme`: 1
- `set_color_scheme`: 1
- `set_diff_deletion_color`: 1
- `set_diff_addition_color`: 1
- `set_layout_preference`: 1
- `set_dashboard_preference`: 1
- `set_project_view_preference`: 1
- `set_whitespace_rendering`: 1
- `toggle_show_whitespace_in_diffs`: 1
- `toggle_file_by_file_diff_view`: 1
- `toggle_markdown_surround_selection`: 1
- `toggle_markdown_automatic_lists`: 1
- `set_tab_width`: 1
- `set_preferred_language`: 1
- `set_first_day_of_week`: 1
- `toggle_relative_time_display`: 1
- `set_oauth_application_name`: 1
- `set_oauth_application_redirect_uri`: 1
- `toggle_oauth_application_confidential`: 1
- `select_oauth_application_scopes`: 1
- `set_personal_access_token_name`: 1
- `set_personal_access_token_expiration_date`: 1
- `select_personal_access_token_scopes`: 1
- `set_email_address`: 1
- `set_current_account_password`: 1
- `set_new_account_password`: 1
- `confirm_new_account_password`: 1
- `set_notification_email`: 1
- `toggle_marketing_emails`: 1
- `toggle_notify_on_own_activity`: 1
- `set_ssh_public_key`: 1
- `set_ssh_key_title`: 1
- `set_ssh_key_usage_type`: 1
- `set_ssh_key_expiration_date`: 1
- `set_gpg_public_key`: 1
- `select_import_namespace`: 1
- `set_github_personal_access_token`: 1
- `set_bitbucket_server_url`: 1
- `set_bitbucket_server_username`: 1
- `set_fogbugz_uri`: 1
- `set_fogbugz_email`: 1
- `set_fogbugz_password`: 1
- `set_gitea_host_url`: 1
- `set_gitea_personal_access_token`: 1
- `select_import_group`: 1
- `upload_import_manifest`: 1
- `set_phabricator_server_url`: 1
- `set_phabricator_api_token`: 1
- `set_webhook_url`: 1
- `set_webhook_secret_token`: 1
- `toggle_webhook_push_events`: 1
- `toggle_webhook_tag_push_events`: 1
- `toggle_webhook_note_events`: 1
- `toggle_webhook_confidential_note_events`: 1
- `toggle_webhook_issue_events`: 1
- `toggle_webhook_confidential_issue_events`: 1
- `toggle_webhook_merge_request_events`: 1
- `toggle_webhook_job_events`: 1
- `toggle_webhook_pipeline_events`: 1
- `toggle_webhook_wiki_page_events`: 1
- `toggle_webhook_deployment_events`: 1
- `toggle_webhook_feature_flag_events`: 1
- `toggle_webhook_release_events`: 1
- `toggle_webhook_ssl_verification`: 1
- `set_project_access_token_name`: 1
- `set_project_access_token_expiration_date`: 1
- `set_project_access_token_access_level`: 1
- `select_project_access_token_scopes`: 1
- `set_protected_branch_name`: 1
- `set_protected_tag_name`: 1
- `set_protected_tag_create_access_level`: 1
- `set_deploy_key_title`: 1
- `set_deploy_key`: 1
- `toggle_deploy_key_write_access`: 1
- `set_two_factor_pin_code`: 1
- `set_current_password`: 1

## RealizesEdges (CRITICAL)
- Flat `realizes_edges` list: 0
- Total `InfoType.realizes` entries: 54

→ `realizes_edges` top-level list는 **empty**지만 InfoType 내부 `realizes` field에는 총 54개 매핑이 존재 (InfoType → StatePattern).
→ `lessons_learned_kg_v2.md §6.2` 기록 확인: realizes_edges=0이라는 표현은 flat list 기준. 
   실제로는 InfoType catalog 안에 매핑 embedded.

### InfoType.realizes 분포
- 1 realizes: 26 infotypes
- 2 realizes: 7 infotypes
- 3 realizes: 3 infotypes
- 5 realizes: 1 infotypes

## Implications for Original Plan

### 재사용 가능
- **37 InfoType**: class catalog seed 후보로 재사용 가능
- **26503 LeadsToEdges**: 기존 transition graph (crawl 기반)
- **4109 Actions**: widget catalog (crawl 기반)
- **3040 StatePatterns**: instance-level URL 정보

### 재구축 필요
- StatePattern이 **URL-level (instance-like)** — class abstraction 없음
- Class-level layer는 InfoType 위에 새로 구축해야
- AXTree 기반 widget 정보는 없음 (Action은 crawler의 form/link URL only)

### Class 재구축 시 reuse 전략
- InfoType.realizes 매핑이 존재 → class↔instance 초기 매핑으로 활용
- 추가로 AXTree 기반 검증 필요 (same class의 instance들이 AXTree structure도 유사한지)

## Next step
- **V1** — 15-20 GitLab 페이지 수동 annotation → class identification rule 도출
- V1 수행 시 본 inventory의 **37 InfoType**을 candidate class seed로 사용
- V1 결과와 KG's current class layer (InfoType) 비교 → 얼마나 align되는지 측정
