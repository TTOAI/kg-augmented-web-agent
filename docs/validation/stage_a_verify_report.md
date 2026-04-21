# Stage A verify — Action set 실측 결과

**Date**: 2026-04-21
**Total pages measured**: 57

Broader selector (`a, button, [role=button], [role=tab]`) 기준 page-specific action (scope base chrome 제외) 비교.

## Phase 1 — Scope base (공유 chrome 수)

| Scope | 공유 chrome size | Source 페이지 |
|---|---:|---|
| `project` | 29 | project_main, project_tree, project_commits |
| `dashboard` | 7 | dashboard_home, dashboard_issues, dashboard_merge_requests |
| `account` | 21 | account_edit, account_preferences, account_notifications |
| `explore` | 12 | explore_projects, explore_projects_topics |
| `user` | 21 | user_profile, user_activity |
| `global` | 6 | help_page, new_project_form, search_page, global_snippets |

## 3.1 Detail widgets (5)

5 detail 페이지의 page-specific action 교집합·차이:

| page | specific size | 상위 action 샘플 |
|---|---:|---|
| `project_issue_detail` | 58 | #1, 3 years ago, 5 years ago, 6 years ago, @byteblaze, @ericwbailey |
| `project_blob_detail` | 79 | 10.09:1, 13.28:1, 4.51:1, 4.87:1, 5.02:1, 5.09:1 |
| `project_commit_detail` | 40 | 1 changed file, 62820763, Add a bullet list, Add a checklist, Add a collapsible section, Add a link (⌘K) |
| `project_mr_detail` | 55 | !19, #1824, 3 years ago, 4 years ago, 9179ebe2, @byteblaze |
| `project_tag_detail` | 17 | Branches, Commits, Compare, Contributors, Delete tag, E empathy-prompts |

**Detail 공통**: 0 action — []

**Pairwise Jaccard (유사도)**:

| pair | jaccard | &#124;intersect&#124; / &#124;union&#124; |
|---|---:|---|
| `project_issue_detail` ↔ `project_blob_detail` | 0.01 | 1/136 |
| `project_issue_detail` ↔ `project_commit_detail` | 0.23 | 18/80 |
| `project_issue_detail` ↔ `project_mr_detail` | 0.40 | 32/81 |
| `project_issue_detail` ↔ `project_tag_detail` | 0.00 | 0/75 |
| `project_blob_detail` ↔ `project_commit_detail` | 0.10 | 11/108 |
| `project_blob_detail` ↔ `project_mr_detail` | 0.01 | 1/133 |
| `project_blob_detail` ↔ `project_tag_detail` | 0.08 | 7/89 |
| `project_commit_detail` ↔ `project_mr_detail` | 0.25 | 19/76 |
| `project_commit_detail` ↔ `project_tag_detail` | 0.14 | 7/50 |
| `project_mr_detail` ↔ `project_tag_detail` | 0.06 | 4/68 |

**판정 가이드**: Jaccard < 0.5면 확실히 다른 class. > 0.8이면 같은 class 또는 variant 가능성.

## 3.2 Form widgets (4 new_form)

- `project_issue_new_form` (31 specific): Add a bullet list, Add a checklist, Add a collapsible section, Add a link (⌘K), Add a numbered list, Add a table
- `project_mr_new_form` (6 specific): Compare branches and continue, Eric Bailey, Merge requests, New, Select source branch, byteblaze/a11y-syntax-highlighting
- `project_branch_new_form` (10 specific): Branches, Cancel, Commits, Compare, Contributors, Create branch
- `project_tag_new_form` (12 specific): Branches, Cancel, Commits, Compare, Contributors, Create tag

**Form 공통**: 0 — []

| pair | jaccard |
|---|---:|
| `project_issue_new_form` ↔ `project_mr_new_form` | 0.03 |
| `project_issue_new_form` ↔ `project_branch_new_form` | 0.03 |
| `project_issue_new_form` ↔ `project_tag_new_form` | 0.02 |
| `project_mr_new_form` ↔ `project_branch_new_form` | 0.00 |
| `project_mr_new_form` ↔ `project_tag_new_form` | 0.00 |
| `project_branch_new_form` ↔ `project_tag_new_form` | 0.57 |

## 3.3 Settings widgets (5, 현재 flat) — 추가 검증

- `project_settings_general` (29 specific): Access Tokens, Add badge, Archive project, Choose file…, Close, Collapse
- `project_settings_repository` (37 specific): Access Tokens, Add key, Choose a file, Create deploy token, Enabled deploy keys 0, Expand
- `project_settings_ci_cd` (31 specific): Access Tokens, Add deploy freeze, Add project, Add trigger, Add variable, Automate building, testing, and deploying
- `project_settings_integrations` (45 specific): Access Tokens, Asana, Assembla, Atlassian Bamboo, Bugzilla, Buildkite
- `project_settings_access_tokens` (10 specific): Access Tokens, Clear date, Create project access token, General, Integrations, Learn more.

| pair | jaccard |
|---|---:|
| `project_settings_general` ↔ `project_settings_repository` | 0.16 |
| `project_settings_general` ↔ `project_settings_ci_cd` | 0.20 |
| `project_settings_general` ↔ `project_settings_integrations` | 0.09 |
| `project_settings_general` ↔ `project_settings_access_tokens` | 0.22 |
| `project_settings_repository` ↔ `project_settings_ci_cd` | 0.15 |
| `project_settings_repository` ↔ `project_settings_integrations` | 0.08 |
| `project_settings_repository` ↔ `project_settings_access_tokens` | 0.17 |
| `project_settings_ci_cd` ↔ `project_settings_integrations` | 0.09 |
| `project_settings_ci_cd` ↔ `project_settings_access_tokens` | 0.21 |
| `project_settings_integrations` ↔ `project_settings_access_tokens` | 0.12 |

## 3.4 CI/Infra lists (4)

- `project_pipelines` (13 specific): All 0, Branches, CI lint, Clear runner caches, Editor, Finished, Jobs, Pipelines
- `project_pipeline_schedules` (10 specific): Active 0, All 0, Dismiss, Editor, Inactive 0, Jobs, New schedule, Pipelines
- `project_environments` (8 specific): Available 0, Enable review app, Environments, Feature Flags, How do I create an environment?, New environment, Releases, Stopped 0
- `project_jobs` (8 specific): All 0, Create CI/CD configuration file, Editor, Finished, Jobs, Pipelines, Schedules, Search

| pair | jaccard |
|---|---:|
| `project_pipelines` ↔ `project_pipeline_schedules` | 0.28 |
| `project_pipelines` ↔ `project_environments` | 0.00 |
| `project_pipelines` ↔ `project_jobs` | 0.50 |
| `project_pipeline_schedules` ↔ `project_environments` | 0.00 |
| `project_pipeline_schedules` ↔ `project_jobs` | 0.38 |
| `project_environments` ↔ `project_jobs` | 0.00 |

## 3.5 Instance variance (5 pairs) — 가장 중요

Rule 일반화의 전제: 같은 class라 주장한 instance끼리 action set이 같아야 함.

| variance | vs base | jaccard | 공통 | variance only | base only |
|---|---|---:|---:|---:|---:|
| `webring_main` | `project_main` | 0.16 | 23 | 55 | 67 |
| `webring_issues` | `project_issues` | 0.39 | 15 | 17 | 6 |
| `empathy_main` | `project_main` | 0.10 | 19 | 91 | 71 |
| `empathy_merge_requests` | `project_merge_requests` | 0.28 | 7 | 14 | 4 |
| `a11yproject_issues` | `project_issues` | 0.17 | 15 | 67 | 6 |

**판정 가이드**: Jaccard < 0.7이면 instance variance 주장 약해짐. 차이 content 검토 필요.

## 3.6 Misc lists (10)

- `project_branches` (18 specific): 62820763, Active, All, Branches, Commits, Compare
- `project_tags` (10 specific): Branches, Commits, Compare, Contributors, Files, Graph
- `project_boards` (14 specific): Boards, Collapse, Create list, Development, Edit board, Issue Boards
- `project_wiki` (2 specific): Create your first page, Enable the Confluence Wiki integration
- `project_labels` (11 specific): Activity, All, Issues, Labels, Members, Merge requests
- `project_milestones` (6 specific): Boards, Learn more., List, Milestones, New milestone, Service Desk
- `project_members` (14 specific): Account, Activity, Administrator, Byte Blaze It's you @byteblaze, Import from a project, Invite a group
- `project_activity` (10 specific): Activity, All, Comments, Designs, Issue events, Labels
- `project_forks` (3 specific): Byte Blaze / a11y-syntax-highlighting, Created date, Fork
- `project_snippets` (8 specific): 0, All 2, Internal 0, New snippet, Private 0, Public 2

**Pairwise Jaccard (high-level):**

각 misc list가 서로 얼마나 유사/상이한지 (0.0 — 완전 다름, 1.0 — 동일):

- **유사도 > 0.8 (같은 class 의심)**: 0 pair
- **유사도 < 0.2 (확실히 다름)**: 42 pair

## 3.7 Cross-scope widget 비교

| cross pair | jaccard | 공통 | 설명 |
|---|---:|---:|---|
| `global_snippets` ↔ `project_snippets` | 0.67 | 8 | 같은 widget이 다른 scope에 있는지 검증 |
| `user_activity` ↔ `project_activity` | 0.00 | 0 | 같은 widget이 다른 scope에 있는지 검증 |
