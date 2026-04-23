"""Stage A.c — Assistant-filled annotations for collected pages.

Workflow:
1. LLM annotates all pages (Stage A.b, output: all_llm_annotated.json)
2. Assistant applies naming convention → user_class + user_reason (this script)
3. Researcher reviews docs/validation/V1_annotation_filled.md

Convention (recursive class inheritance tree, protocol v0.5):
- Format: `{scope-class}/{…}/{leaf-class}[/{variant}]` (root `site` 생략)
- Model: class tree + optional leaf-internal variant. scope/widget은 class의 depth 별명 (독립 tier 아님)
- Scope classes: `project`, `dashboard`, `explore`, `user`, `account`, `global` — 공유 chrome으로 식별
- Leaf classes: core content widget (`_list`, `_detail`, `_new_form`, `settings_*`, 기타)
- Variant: leaf 내부 action(filter/sort/state) 차이 있을 때만
Reason priority: URL > scope chrome 공유 근거 > leaf class 구조 > leaf-specific action.

Output:
  output/validation/V1_pages/all_annotated.json
  docs/validation/V1_annotation_filled.md
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

INPUT_DIR = Path("output/validation/V1_pages")
LLM_PATH = INPUT_DIR / "all_llm_annotated.json"
OUTPUT_PATH = INPUT_DIR / "all_annotated.json"
DOC_OUT = Path("docs/validation/V1_annotation_filled.md")

# Assistant-filled final annotation (user_class + user_reason) for all collected pages.
# Derived by applying naming convention (protocol v0.5) to each page's URL + AXTree structure.
ANNOTATIONS = {
    # ── scope=dashboard ─────────────────────────────────────────
    "dashboard_home": {
        "user_class": "dashboard/project_list/yours",
        "user_reason": "Scope=dashboard (공유 헤더 28 action, 실측). Widget=project_list (h2 project 이름 반복, li=73). Variant=yours (filter bar All/Personal). `/dashboard`는 Projects Yours 탭 기본 landing.",
    },
    "dashboard_projects": {
        "user_class": "dashboard/project_list/yours",
        "user_reason": "Scope=dashboard. Widget=project_list (h1=Projects, h2 반복, li=73). Variant=yours (filter All/Personal). `dashboard_home`과 동일 class.",
    },
    "dashboard_projects_starred": {
        "user_class": "dashboard/project_list/starred",
        "user_reason": "Scope=dashboard. Widget=project_list. Variant=starred — `/yours`와 action 다름(filter_all/filter_personal 없음, 실측). 상단 탭 Starred active.",
    },
    "dashboard_issues": {
        "user_class": "dashboard/issue_list",
        "user_reason": "Scope=dashboard. Widget=issue_list (filter form + issue row). Dashboard scope는 `New issue`/`Edit issues`(bulk)/`Import/Export CSV` 없음(template에 부재, empty state 무관). `Select project to create issue`로 compensation.",
    },
    "dashboard_merge_requests": {
        "user_class": "dashboard/merge_request_list",
        "user_reason": "Scope=dashboard. Widget=merge_request_list (filter form + MR row). `New MR`, `Edit MR`(bulk), `Export CSV`, `Subscribe` 없음. `Select project to create MR`로 compensation.",
    },
    "dashboard_todos": {
        "user_class": "dashboard/todo_list/pending",
        "user_reason": "Scope=dashboard. Widget=todo_list. Variant=pending (default). Action: `Mark all as done`/`Undo mark all as done` 포함. URL `/dashboard/todos`.",
    },
    "dashboard_todos_done": {
        "user_class": "dashboard/todo_list/done",
        "user_reason": "Scope=dashboard. Widget=todo_list. Variant=done — `Mark all as done`/`Undo` 2개 action 누락 (`state=done` query로 routing). URL `?state=done`.",
    },
    "dashboard_groups": {
        "user_class": "dashboard/group_list",
        "user_reason": "Scope=dashboard. Widget=group_list (h1=Groups, filter form 3 + li=39 그룹 카드). 사용자 소속 group flat list.",
    },

    # ── scope=explore ───────────────────────────────────────────
    "explore_projects": {
        "user_class": "explore/project_list/all",
        "user_reason": "Scope=explore. Widget=project_list. Variant=all (default tab). URL `/explore/projects`. Filter bar: All/Most stars/Trending + Visibility. `/starred`·`/trending` siblings.",
    },
    "explore_projects_topics": {
        "user_class": "explore/topic_list",
        "user_reason": "Scope=explore. Widget=topic_list — project_list의 filter tab bar 없음, item은 avatar+이름 minimal tile (rich project card와 대조). 실측으로 widget 다름 확인.",
    },

    # ── scope=project ───────────────────────────────────────────
    "project_main": {
        "user_class": "project/main",
        "user_reason": "Scope=project (공유 사이드바 57 action, 실측 100% 동일). Widget=main — project root `/{namespace}/{project}`에서 navigation shell만 나타나는 entity landing.",
    },
    "project_activity": {
        "user_class": "project/activity_list",
        "user_reason": "Scope=project. Widget=activity_list (URL `/activity`, event 시간순 반복 list).",
    },
    "project_tree": {
        "user_class": "project/file_list",
        "user_reason": "Scope=project. Widget=file_list (URL `/-/tree/{branch}(/{path*})?`, 폴더/파일 flat table). 하위 폴더 이동 시 URL 깊어져도 같은 class.",
    },
    "project_commits": {
        "user_class": "project/commit_list",
        "user_reason": "Scope=project. Widget=commit_list (URL `/-/commits/{branch}`, commit row 시간순 반복 list).",
    },
    "project_issues": {
        "user_class": "project/issue_list",
        "user_reason": "Scope=project. Widget=issue_list — `New issue`, `Edit issues`(bulk), `Import/Export CSV`, 확장 정렬(Priority/Popularity/Label priority) 포함. Dashboard scope와 다른 action 17+.",
    },
    "project_merge_requests": {
        "user_class": "project/merge_request_list",
        "user_reason": "Scope=project. Widget=merge_request_list — `New MR`, `Edit MR`(bulk), `Export CSV`, `Subscribe/Unsubscribe`, `Target-Branch` filter 포함.",
    },
    "project_labels": {
        "user_class": "project/label_list",
        "user_reason": "Scope=project. Widget=label_list (URL `/-/labels`, label 반복 list).",
    },
    "project_milestones": {
        "user_class": "project/milestone_list",
        "user_reason": "Scope=project. Widget=milestone_list (URL `/-/milestones`, milestone 반복 list).",
    },
    "project_members": {
        "user_class": "project/member_list",
        "user_reason": "Scope=project. Widget=member_list (URL `/-/project_members`, project 멤버 반복 list).",
    },
    "project_forks": {
        "user_class": "project/fork_list",
        "user_reason": "Scope=project. Widget=fork_list (URL `/-/forks`, fork된 project 반복 list).",
    },

    # ── scope=user ──────────────────────────────────────────────
    "user_profile": {
        "user_class": "user/profile",
        "user_reason": "Scope=user (URL `/{username}`은 user entity root). Widget=profile — h1=username, h2 project 이름 sub-list, form=2, li=56. User profile info + owned project sub-section.",
    },

    # ── scope=global ────────────────────────────────────────────
    "help_page": {
        "user_class": "global/help_landing",
        "user_reason": "Scope=global (URL `/help`, 특정 scope 사이드바 없음). Widget=help_landing — h2 multi-section(Popular topics, DevOps lifecycle 등 5+), table 6. List/form 아닌 multi-section landing.",
    },
    "new_project_form": {
        "user_class": "global/new_project_form",
        "user_reason": "Scope=global (URL `/projects/new`, project scope 아직 없음). Widget=new_project_form — h2='Create new project', form 5개, li=43 입력 필드 그룹.",
    },

    # ═══════════════════════════════════════════════════════════
    # Stage A.1 expansion (+34)
    # ═══════════════════════════════════════════════════════════

    # ── Project scope: detail pages (5) ─────────────────────────
    "project_issue_detail": {
        "user_class": "project/issue_detail",
        "user_reason": "Scope=project. Widget=issue_detail — URL `/-/issues/{id}`, 단일 issue entity view.",
    },
    "project_blob_detail": {
        "user_class": "project/blob_detail",
        "user_reason": "Scope=project. Widget=blob_detail — URL `/-/blob/{branch}/{path}`, 파일 한 건 내용 view.",
    },
    "project_commit_detail": {
        "user_class": "project/commit_detail",
        "user_reason": "Scope=project. Widget=commit_detail — URL `/-/commit/{sha}`, 단일 commit entity view.",
    },
    "project_tag_detail": {
        "user_class": "project/tag_detail",
        "user_reason": "Scope=project. Widget=tag_detail — URL `/-/tags/{name}`, 단일 tag view. Instance는 byteblaze/empathy-prompts의 v0.1.0.",
    },
    "project_mr_detail": {
        "user_class": "project/merge_request_detail",
        "user_reason": "Scope=project. Widget=merge_request_detail — URL `/-/merge_requests/{id}`, 단일 MR entity view. Instance는 empathy-prompts의 #19.",
    },

    # ── Project scope: form pages (4) ───────────────────────────
    "project_issue_new_form": {
        "user_class": "project/issue_new_form",
        "user_reason": "Scope=project. Widget=issue_new_form — URL `/-/issues/new`, issue 생성 form.",
    },
    "project_mr_new_form": {
        "user_class": "project/merge_request_new_form",
        "user_reason": "Scope=project. Widget=merge_request_new_form — URL `/-/merge_requests/new`, MR 생성 form.",
    },
    "project_branch_new_form": {
        "user_class": "project/branch_new_form",
        "user_reason": "Scope=project. Widget=branch_new_form — URL `/-/branches/new`, branch 생성 form.",
    },
    "project_tag_new_form": {
        "user_class": "project/tag_new_form",
        "user_reason": "Scope=project. Widget=tag_new_form — URL `/-/tags/new`, tag 생성 form.",
    },

    # ── Project scope: settings (5) — v0.5 retract 후 flat ──────
    "project_settings_general": {
        "user_class": "project/settings_general",
        "user_reason": "Scope=project. Widget=settings_general — URL `/edit` (project 최상위 edit). v0.5 retract: settings 전용 sub-nav 없음(사이드바 artifact) → flat widget.",
    },
    "project_settings_repository": {
        "user_class": "project/settings_repository",
        "user_reason": "Scope=project. Widget=settings_repository — URL `/-/settings/repository`. Flat (내부 sub-nav 아님).",
    },
    "project_settings_ci_cd": {
        "user_class": "project/settings_ci_cd",
        "user_reason": "Scope=project. Widget=settings_ci_cd — URL `/-/settings/ci_cd`. Flat.",
    },
    "project_settings_integrations": {
        "user_class": "project/settings_integrations",
        "user_reason": "Scope=project. Widget=settings_integrations — URL `/-/settings/integrations`. Flat.",
    },
    "project_settings_access_tokens": {
        "user_class": "project/settings_access_tokens",
        "user_reason": "Scope=project. Widget=settings_access_tokens — URL `/-/settings/access_tokens`. Flat.",
    },

    # ── Project scope: CI/CD & infra (4) ────────────────────────
    "project_pipelines": {
        "user_class": "project/pipeline_list",
        "user_reason": "Scope=project. Widget=pipeline_list — URL `/-/pipelines`, pipeline row 반복 list.",
    },
    "project_pipeline_schedules": {
        "user_class": "project/schedule_list",
        "user_reason": "Scope=project. Widget=schedule_list — URL `/-/pipeline_schedules`, schedule row 반복 list.",
    },
    "project_environments": {
        "user_class": "project/environment_list",
        "user_reason": "Scope=project. Widget=environment_list — URL `/-/environments`, environment row 반복 list.",
    },
    "project_jobs": {
        "user_class": "project/job_list",
        "user_reason": "Scope=project. Widget=job_list — URL `/-/jobs`, CI job row 반복 list.",
    },

    # ── Project scope: 기타 (5) ─────────────────────────────────
    "project_branches": {
        "user_class": "project/branch_list",
        "user_reason": "Scope=project. Widget=branch_list — URL `/-/branches`, branch row 반복 list.",
    },
    "project_tags": {
        "user_class": "project/tag_list",
        "user_reason": "Scope=project. Widget=tag_list — URL `/-/tags`, tag row 반복 list.",
    },
    "project_boards": {
        "user_class": "project/issue_board",
        "user_reason": "Scope=project. Widget=issue_board — URL `/-/boards`, kanban layout(list와 다른 widget). `project/issue_list`와 sibling class.",
    },
    "project_wiki": {
        "user_class": "project/wiki",
        "user_reason": "Scope=project. Widget=wiki — URL `/-/wikis`. 현 인스턴스 empty state('Create your first page' CTA). Template 자체는 wiki page landing.",
    },
    "project_snippets": {
        "user_class": "project/snippet_list",
        "user_reason": "Scope=project. Widget=snippet_list — URL `/-/snippets`, project 범위 snippet 반복 list.",
    },

    # ── Project scope: instance variance (5) ────────────────────
    "webring_main": {
        "user_class": "project/main",
        "user_reason": "Scope=project. Widget=main. Instance: byteblaze/a11y-webring.club (기존 a11y-syntax-highlighting과 다른 project).",
    },
    "webring_issues": {
        "user_class": "project/issue_list",
        "user_reason": "Scope=project. Widget=issue_list. Instance: byteblaze/a11y-webring.club의 issue_list.",
    },
    "empathy_main": {
        "user_class": "project/main",
        "user_reason": "Scope=project. Widget=main. Instance: byteblaze/empathy-prompts.",
    },
    "empathy_merge_requests": {
        "user_class": "project/merge_request_list",
        "user_reason": "Scope=project. Widget=merge_request_list. Instance: byteblaze/empathy-prompts의 MR 리스트 (MR 존재 project).",
    },
    "a11yproject_issues": {
        "user_class": "project/issue_list",
        "user_reason": "Scope=project. Widget=issue_list. Instance: a11yproject/a11yproject.com (다른 namespace).",
    },

    # ── Account scope (3): v0.5 신규, /-/profile/* 전용 14-action 사이드바 ──
    "account_edit": {
        "user_class": "account/edit",
        "user_reason": "Scope=account (v0.5 신규, `/-/profile/*` 전용 사이드바 14 action 실측: Account/Applications/SSH Keys 등). Widget=edit — `/-/profile`, profile edit form.",
    },
    "account_preferences": {
        "user_class": "account/preferences",
        "user_reason": "Scope=account. Widget=preferences — URL `/-/profile/preferences`, preferences form. Same sidebar (14 action).",
    },
    "account_notifications": {
        "user_class": "account/notifications",
        "user_reason": "Scope=account. Widget=notifications — URL `/-/profile/notifications`, notification settings form. Same sidebar.",
    },

    # ── User scope: activity (1) ────────────────────────────────
    "user_activity": {
        "user_class": "user/activity_list",
        "user_reason": "Scope=user (public user view). Widget=activity_list — URL `/users/{username}/activity`, user의 event 시간순 반복 list. `user/profile`(/byteblaze)과 sibling.",
    },

    # ── Global scope 추가 (2) ───────────────────────────────────
    "search_page": {
        "user_class": "global/search_page",
        "user_reason": "Scope=global (URL `/search`, 특정 scope 없음). Widget=search_page — 검색 form + 결과 영역.",
    },
    "global_snippets": {
        "user_class": "global/snippet_list",
        "user_reason": "Scope=global (URL `/snippets`, 특정 scope 없음). Widget=snippet_list — global 범위 snippet 반복 list. `project/snippet_list`와 sibling widget (다른 scope).",
    },

    # ═══════════════════════════════════════════════════════════
    # Stage A.f iter 2 — cluster representative 92개 (count >= 3)
    # ═══════════════════════════════════════════════════════════

    # ── User scope: profile tabs (7 new tabs) ──────────────────
    "iter2_users_username_contributed": {
        "user_class": "user/contributed_project_list",
        "user_reason": "Scope=user. URL `/users/{username}/contributed`. Contributed projects tab of user profile.",
    },
    "iter2_users_username_followers": {
        "user_class": "user/follower_list",
        "user_reason": "Scope=user. URL `/users/{username}/followers`. Followers tab.",
    },
    "iter2_users_username_following": {
        "user_class": "user/following_list",
        "user_reason": "Scope=user. URL `/users/{username}/following`. Following tab.",
    },
    "iter2_users_username_groups": {
        "user_class": "user/group_list",
        "user_reason": "Scope=user. URL `/users/{username}/groups`. Groups tab.",
    },
    "iter2_users_username_projects": {
        "user_class": "user/project_list",
        "user_reason": "Scope=user. URL `/users/{username}/projects`. Personal projects tab.",
    },
    "iter2_users_username_snippets": {
        "user_class": "user/snippet_list",
        "user_reason": "Scope=user. URL `/users/{username}/snippets`. User snippets tab.",
    },
    "iter2_users_username_starred": {
        "user_class": "user/starred_project_list",
        "user_reason": "Scope=user. URL `/users/{username}/starred`. Starred projects tab.",
    },

    # ── Project scope: list widgets (new) ──────────────────────
    "iter2_ns_proj_starrers": {
        "user_class": "project/starrer_list",
        "user_reason": "Scope=project. URL `/{ns}/{proj}/-/starrers`. Users who starred this project.",
    },
    "iter2_ns_proj_releases": {
        "user_class": "project/release_list",
        "user_reason": "Scope=project. URL `/-/releases`. Project release 반복 list.",
    },
    "iter2_ns_proj_packages": {
        "user_class": "project/package_list",
        "user_reason": "Scope=project. URL `/-/packages`. Package registry list.",
    },
    "iter2_ns_proj_incidents": {
        "user_class": "project/incident_list",
        "user_reason": "Scope=project. URL `/-/incidents`. Incident 반복 list (monitoring).",
    },
    "iter2_ns_proj_terraform": {
        "user_class": "project/terraform_list",
        "user_reason": "Scope=project. URL `/-/terraform`. Terraform state 반복 list.",
    },
    "iter2_ns_proj_clusters": {
        "user_class": "project/cluster_list",
        "user_reason": "Scope=project. URL `/-/clusters`. Kubernetes clusters 반복 list.",
    },
    "iter2_ns_proj_feature_flags": {
        "user_class": "project/feature_flag_list",
        "user_reason": "Scope=project. URL `/-/feature_flags`. Feature flag 반복 list.",
    },
    "iter2_ns_proj_hooks": {
        "user_class": "project/webhook_list",
        "user_reason": "Scope=project. URL `/-/hooks`. Webhook 반복 list.",
    },

    # ── Project scope: graph/analytics (distinct widgets) ───────
    "iter2_ns_proj_compare": {
        "user_class": "project/compare_form",
        "user_reason": "Scope=project. URL `/-/compare`. Branch/ref comparison form with diff output.",
    },
    "iter2_ns_proj_graphs_branch": {
        "user_class": "project/contributor_graph",
        "user_reason": "Scope=project. URL `/-/graphs/{branch}`. Contributors visualization (commits over time).",
    },
    "iter2_ns_proj_graphs_branch_charts": {
        "user_class": "project/repository_analytics",
        "user_reason": "Scope=project. URL `/-/graphs/{branch}/charts`. Repository analytics charts.",
    },
    "iter2_ns_proj_network_branch": {
        "user_class": "project/network_graph",
        "user_reason": "Scope=project. URL `/-/network/{branch}`. Git branch network visualization.",
    },
    "iter2_ns_proj_pipelines_charts": {
        "user_class": "project/cicd_analytics",
        "user_reason": "Scope=project. URL `/-/pipelines/charts`. CI/CD pipeline analytics charts.",
    },
    "iter2_ns_proj_value_stream_analytics": {
        "user_class": "project/value_stream_analytics",
        "user_reason": "Scope=project. URL `/-/value_stream_analytics`. Value stream metrics dashboard.",
    },
    "iter2_ns_proj_metrics": {
        "user_class": "project/metric_dashboard",
        "user_reason": "Scope=project. URL `/-/metrics`. Performance metrics dashboard.",
    },
    "iter2_ns_proj_error_tracking": {
        "user_class": "project/error_tracking",
        "user_reason": "Scope=project. URL `/-/error_tracking`. Error tracking dashboard.",
    },
    "iter2_ns_proj_alert_management": {
        "user_class": "project/alert_management",
        "user_reason": "Scope=project. URL `/-/alert_management`. Alert management dashboard.",
    },
    "iter2_ns_proj_security_configuration": {
        "user_class": "project/security_config",
        "user_reason": "Scope=project. URL `/-/security/configuration`. Security scanning configuration.",
    },
    "iter2_ns_proj_infrastructure_registry": {
        "user_class": "project/infrastructure_registry",
        "user_reason": "Scope=project. URL `/-/infrastructure_registry`. Terraform/cluster infrastructure registry.",
    },
    "iter2_ns_proj_usage_quotas": {
        "user_class": "project/usage_quota",
        "user_reason": "Scope=project. URL `/-/usage_quotas`. Storage/compute usage quotas page.",
    },

    # ── Project scope: detail pages (new) ──────────────────────
    "iter2_ns_proj_pipelines_id": {
        "user_class": "project/pipeline_detail",
        "user_reason": "Scope=project. URL `/-/pipelines/{id}`. Single pipeline entity view.",
    },
    "iter2_ns_proj_milestones_id": {
        "user_class": "project/milestone_detail",
        "user_reason": "Scope=project. URL `/-/milestones/{id}`. Single milestone entity view.",
    },

    # ── Project scope: form pages (new) ────────────────────────
    "iter2_ns_proj_forks_new": {
        "user_class": "project/fork_new_form",
        "user_reason": "Scope=project. URL `/-/forks/new`. Fork creation form.",
    },
    "iter2_ns_proj_snippets_new": {
        "user_class": "project/snippet_new_form",
        "user_reason": "Scope=project. URL `/-/snippets/new`. Snippet creation form.",
    },
    "iter2_ns_proj_new_main": {
        "user_class": "project/file_new_form",
        "user_reason": "Scope=project. URL `/-/new/{branch}`. New file creation form.",
    },
    "iter2_ns_proj_labels_id_edit": {
        "user_class": "project/label_edit_form",
        "user_reason": "Scope=project. URL `/-/labels/{id}/edit`. Label edit form.",
    },
    "iter2_ns_proj_milestones_id_edit": {
        "user_class": "project/milestone_edit_form",
        "user_reason": "Scope=project. URL `/-/milestones/{id}/edit`. Milestone edit form.",
    },
    "iter2_ns_proj_merge_requests_id_edit": {
        "user_class": "project/merge_request_edit_form",
        "user_reason": "Scope=project. URL `/-/merge_requests/{id}/edit`. MR edit form.",
    },
    "iter2_ns_proj_import_jira": {
        "user_class": "project/jira_import_form",
        "user_reason": "Scope=project. URL `/-/import/jira`. Jira issue import form.",
    },

    # ── Project scope: settings (new) ──────────────────────────
    "iter2_ns_proj_settings_merge_requests": {
        "user_class": "project/settings_merge_requests",
        "user_reason": "Scope=project. URL `/-/settings/merge_requests`. MR settings form. Flat (no sub-nav).",
    },
    "iter2_ns_proj_settings_operations": {
        "user_class": "project/settings_operations",
        "user_reason": "Scope=project. URL `/-/settings/operations`. Monitoring/operations settings.",
    },
    "iter2_ns_proj_settings_packages_and_registries": {
        "user_class": "project/settings_packages",
        "user_reason": "Scope=project. URL `/-/settings/packages_and_registries`. Package/registry settings.",
    },

    # ── Project scope: MR detail sub-tabs (separate widgets) ────
    "iter2_ns_proj_merge_requests_id_commits": {
        "user_class": "project/merge_request_commits",
        "user_reason": "Scope=project. URL `/-/merge_requests/{id}/commits`. MR commits tab — chronological commit list within MR.",
    },
    "iter2_ns_proj_merge_requests_id_diffs": {
        "user_class": "project/merge_request_diff",
        "user_reason": "Scope=project. URL `/-/merge_requests/{id}/diffs`. MR diff tab — code change visualization.",
    },
    "iter2_ns_proj_merge_requests_id_pipelines": {
        "user_class": "project/merge_request_pipelines",
        "user_reason": "Scope=project. URL `/-/merge_requests/{id}/pipelines`. MR pipelines tab — CI runs for this MR.",
    },

    # ── Project scope: CI editor + atom feeds + tree multi-seg ─
    "iter2_ns_proj_ci_editor": {
        "user_class": "project/ci_editor",
        "user_reason": "Scope=project. URL `/-/ci/editor?branch_name={branch}`. Interactive pipeline yaml editor.",
    },
    "iter2_ns_proj_issues_atom": {
        "user_class": "project/issue_feed",
        "user_reason": "Scope=project. URL `/-/issues.atom`. Atom RSS feed for issues (machine-readable).",
    },
    "iter2_ns_proj_merge_requests_atom_state_opened": {
        "user_class": "project/merge_request_feed",
        "user_reason": "Scope=project. URL `/-/merge_requests.atom`. Atom RSS feed for MRs.",
    },
    "iter2_ns_proj_tree_branch_path": {
        "user_class": "project/file_list",
        "user_reason": "Scope=project. URL `/-/tree/{branch}/{path*}` with multi-segment branch name (e.g., `github/fork/...`). Same widget as `project/file_list` — rule 일반화 instance.",
    },

    # ── Import form (generalized for any service in iter 3) ────
    "iter2_ns_proj_new": {
        "user_class": "global/import_form",
        "user_reason": "Scope=global. URL `/import/{service}/new`. Third-party repo import form (generalized).",
    },

    # ── Explore scope: project_list variants + topic_detail ─────
    "iter2_explore_projects_starred": {
        "user_class": "explore/project_list/starred",
        "user_reason": "Scope=explore. Widget=project_list. Variant=starred. URL `/explore/projects/starred`.",
    },
    "iter2_explore_projects_trending": {
        "user_class": "explore/project_list/trending",
        "user_reason": "Scope=explore. Widget=project_list. Variant=trending. URL `/explore/projects/trending`.",
    },
    "iter2_explore_projects_topics_topic_name": {
        "user_class": "explore/topic_detail",
        "user_reason": "Scope=explore. Widget=topic_detail — URL `/explore/projects/topics/{topic_name}`. 특정 topic에 속한 project 목록 (topic_list의 detail instance).",
    },

    # ── Root URL redirects (treated as distinct root class to avoid
    #     mixing with /dashboard-rooted templates) ─────────────────
    "iter2_personal_true": {
        "user_class": "global/root_redirect",
        "user_reason": "URL `/?personal=true&sort=name_asc`. Bare root with query. Redirects to dashboard in browser but URL-wise unique. Kept as global/root_redirect to avoid rule template conflict.",
    },
    "iter2_": {
        "user_class": "global/root_redirect",
        "user_reason": "URL `/`. Bare root. Redirects to dashboard/projects. Kept as global/root_redirect class.",
    },

    # ── Global scope: abuse report ─────────────────────────────
    "iter2_abuse_reports_new": {
        "user_class": "global/abuse_report_new_form",
        "user_reason": "Scope=global. URL `/-/abuse_reports/new`. Abuse report submission form.",
    },

    # ── IDE (Web IDE — new scope) ──────────────────────────────
    "iter2_ide_project_a11yproject_a11yproject_com_merge_requests_id": {
        "user_class": "ide/mr_view",
        "user_reason": "Scope=ide (new scope, Web IDE). URL `/-/ide/project/{ns}/{proj}/tree/{branch}/...` or `/merge_requests/{id}`. In-browser code editor for MR review.",
    },

    # ── Global scope: help (38 entries — unify as global/help_page, images as global/help_image) ──
    "iter2_help_api_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/api/*`."},
    "iter2_help_api_graphql_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/api/graphql/*`."},
    "iter2_help_ci_jobs_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/ci/jobs/*`."},
    "iter2_help_ci_pipelines_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/ci/pipelines/*`."},
    "iter2_help_ci_runners_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/ci/runners/*`."},
    "iter2_help_ci_variables_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/ci/variables/*`."},
    "iter2_help_ci_yaml_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/ci/yaml/*`."},
    "iter2_help_development_contributing_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/development/contributing/*`."},
    "iter2_help_development_documentation_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/development/documentation/*`."},
    "iter2_help_development_documentation_site_architecture_file": {"user_class": "global/help_page", "user_reason": "Help page nested under development/documentation."},
    "iter2_help_development_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/development/*`."},
    "iter2_help_install_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/install/*`."},
    "iter2_help_integration_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/integration/*`."},
    "iter2_help_operations_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/operations/*`."},
    "iter2_help_operations_incident_management_file": {"user_class": "global/help_page", "user_reason": "Help page nested under operations."},
    "iter2_help_raketasks_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/raketasks/*`."},
    "iter2_help_security_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/security/*`."},
    "iter2_help_topics_autodevops_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/topics/autodevops/*`."},
    "iter2_help_topics_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/topics/*`."},
    "iter2_help_tutorials_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/tutorials/*`."},
    "iter2_help_update_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/update/*`."},
    "iter2_help_user_analytics_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/analytics/*`."},
    "iter2_help_user_application_security_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/application_security/*`."},
    "iter2_help_user_application_security_sast_file": {"user_class": "global/help_page", "user_reason": "Help page nested under application_security/sast."},
    "iter2_help_user_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/*`."},
    "iter2_help_user_group_epics_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/group/epics/*`."},
    "iter2_help_user_group_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/group/*`."},
    "iter2_help_user_profile_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/profile/*`."},
    "iter2_help_user_project_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/project/*`."},
    "iter2_help_user_project_import_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/project/import/*`."},
    "iter2_help_user_project_issues_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/project/issues/*`."},
    "iter2_help_user_project_merge_requests_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/project/merge_requests/*`."},
    "iter2_help_user_project_releases_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/project/releases/*`."},
    "iter2_help_user_project_repository_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/project/repository/*`."},
    "iter2_help_user_project_settings_file": {"user_class": "global/help_page", "user_reason": "Help page `/help/user/project/settings/*`."},

    "iter2_help_subscriptions_img_file": {"user_class": "global/help_image", "user_reason": "Help image asset (.png) under /help/*/img/*."},
    "iter2_help_user_img_file": {"user_class": "global/help_image", "user_reason": "Help image asset under /help/user/img/*."},
    "iter2_help_user_profile_img_file": {"user_class": "global/help_image", "user_reason": "Help image asset under /help/user/profile/img/*."},

    # ═══════════════════════════════════════════════════════════
    # Stage A.f iter 3 — tail cleanup (account sub-pages, edge cases)
    # These are added by URL-pattern inference; actual AXTree collection skipped
    # for iter 3 (tail is low-value). If deep verification needed later, collect.
    # ═══════════════════════════════════════════════════════════
}
# iter 3 patches appended below (URL-pattern based, no AXTree collection)
_ITER3_PATCH = {
    # Account scope sub-pages (each = new class under account/)
    "iter3_account_keys": {
        "__url__": "/-/profile/keys",
        "user_class": "account/keys",
        "user_reason": "Scope=account. URL `/-/profile/keys`. SSH key management page.",
    },
    "iter3_account_account": {
        "__url__": "/-/profile/account",
        "user_class": "account/account",
        "user_reason": "Scope=account. URL `/-/profile/account`. Basic account info (username, email).",
    },
    "iter3_account_applications": {
        "__url__": "/-/profile/applications",
        "user_class": "account/applications",
        "user_reason": "Scope=account. URL `/-/profile/applications`. OAuth applications page.",
    },
    "iter3_account_audit_log": {
        "__url__": "/-/profile/audit_log",
        "user_class": "account/audit_log",
        "user_reason": "Scope=account. URL `/-/profile/audit_log`. Authentication/activity audit log.",
    },
    "iter3_account_chat_names": {
        "__url__": "/-/profile/chat_names",
        "user_class": "account/chat_names",
        "user_reason": "Scope=account. URL `/-/profile/chat_names`. Chat integration names page.",
    },
    "iter3_account_emails": {
        "__url__": "/-/profile/emails",
        "user_class": "account/emails",
        "user_reason": "Scope=account. URL `/-/profile/emails`. Email management.",
    },
    "iter3_account_gpg_keys": {
        "__url__": "/-/profile/gpg_keys",
        "user_class": "account/gpg_keys",
        "user_reason": "Scope=account. URL `/-/profile/gpg_keys`. GPG key management.",
    },
    "iter3_account_personal_access_tokens": {
        "__url__": "/-/profile/personal_access_tokens",
        "user_class": "account/personal_access_tokens",
        "user_reason": "Scope=account. URL `/-/profile/personal_access_tokens`. Personal access token management.",
    },
    "iter3_account_active_sessions": {
        "__url__": "/-/profile/active_sessions",
        "user_class": "account/active_sessions",
        "user_reason": "Scope=account. URL `/-/profile/active_sessions`. Active browser sessions.",
    },
    "iter3_account_password_edit": {
        "__url__": "/-/profile/password/edit",
        "user_class": "account/password_edit",
        "user_reason": "Scope=account. URL `/-/profile/password/edit`. Password change form.",
    },
    "iter3_account_two_factor_auth": {
        "__url__": "/-/profile/two_factor_auth",
        "user_class": "account/two_factor_auth",
        "user_reason": "Scope=account. URL `/-/profile/two_factor_auth`. 2FA setup page.",
    },

    # Global scope: snippet creation
    "iter3_global_snippet_new": {
        "__url__": "/-/snippets/new",
        "user_class": "global/snippet_new_form",
        "user_reason": "Scope=global. URL `/-/snippets/new`. Global snippet creation form.",
    },

    # Project scope: new forms (missing)
    "iter3_project_label_new": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/labels/new",
        "user_class": "project/label_new_form",
        "user_reason": "Scope=project. URL `/-/labels/new`. Label creation form.",
    },
    "iter3_project_release_new": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/releases/new",
        "user_class": "project/release_new_form",
        "user_reason": "Scope=project. URL `/-/releases/new`. Release creation form.",
    },
    "iter3_project_environment_new": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/environments/new",
        "user_class": "project/environment_new_form",
        "user_reason": "Scope=project. URL `/-/environments/new`. Environment creation form.",
    },
    "iter3_project_feature_flag_new": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/feature_flags/new",
        "user_class": "project/feature_flag_new_form",
        "user_reason": "Scope=project. URL `/-/feature_flags/new`. Feature flag creation form.",
    },
    "iter3_project_pipeline_schedule_new": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/pipeline_schedules/new",
        "user_class": "project/pipeline_schedule_new_form",
        "user_reason": "Scope=project. URL `/-/pipeline_schedules/new`. Pipeline schedule creation.",
    },

    # Project scope: branches filter variants — all same widget as project/branch_list
    # (filter is a view-mode on same list, merging keeps tree clean)
    "iter3_project_branches_active": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/branches/active",
        "user_class": "project/branch_list",
        "user_reason": "Instance of project/branch_list with filter suffix `/active`. Same widget.",
    },
    "iter3_project_branches_stale": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/branches/stale",
        "user_class": "project/branch_list",
        "user_reason": "Instance of project/branch_list with filter suffix `/stale`. Same widget.",
    },
    "iter3_project_branches_all": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/branches/all",
        "user_class": "project/branch_list",
        "user_reason": "Instance of project/branch_list with filter suffix `/all`. Same widget.",
    },
    "iter3_project_find_file": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/find_file/main",
        "user_class": "project/file_search",
        "user_reason": "Scope=project. URL `/-/find_file/{branch}`. File search in repo.",
    },
    "iter3_project_history": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/history",
        "user_class": "project/history",
        "user_reason": "Scope=project. URL `/{ns}/{proj}/history`. Repository history (redirect alias).",
    },
    "iter3_project_snippet_detail": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/snippets/1",
        "user_class": "project/snippet_detail",
        "user_reason": "Scope=project. URL `/-/snippets/{id}`. Single snippet view.",
    },
    "iter3_project_ci_lint": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/ci/lint",
        "user_class": "project/ci_lint",
        "user_reason": "Scope=project. URL `/-/ci/lint`. CI yaml syntax validator.",
    },
    "iter3_project_feature_flags_user_lists": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/feature_flags_user_lists",
        "user_class": "project/feature_flag_user_list",
        "user_reason": "Scope=project. URL `/-/feature_flags_user_lists`. User lists for feature flags.",
    },
    "iter3_project_clusters_new_docs": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/clusters/new_cluster_docs",
        "user_class": "project/cluster_new_docs",
        "user_reason": "Scope=project. URL `/-/clusters/new_cluster_docs`. Kubernetes cluster setup docs.",
    },
    "iter3_project_protected_branches": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/protected_branches/170",
        "user_class": "project/protected_branch_detail",
        "user_reason": "Scope=project. URL `/-/protected_branches/{id}`. Protected branch rule.",
    },
    "iter3_project_settings_integration_edit": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/settings/integrations/asana/edit",
        "user_class": "project/settings_integration_edit",
        "user_reason": "Scope=project. URL `/-/settings/integrations/{service}/edit`. Integration config form (Asana/Assembla/Bamboo/etc.).",
    },
    "iter3_project_upload_file": {
        "__url__": "/byteblaze/empathy-prompts/uploads/2f21c9b357b42751d8cb814c6d06824b/test.gif",
        "user_class": "project/upload_file",
        "user_reason": "Scope=project. URL `/{ns}/{proj}/uploads/{sha}/{file}`. Uploaded media asset.",
    },

    # Global scope: import forms
    "iter3_import_github": {
        "__url__": "/import/github/new",
        "user_class": "global/import_form",
        "user_reason": "Scope=global. URL `/import/{service}/new`. Third-party import form (GitHub/Bitbucket/etc.).",
    },
    "iter3_import_bitbucket_server": {
        "__url__": "/import/bitbucket_server/new",
        "user_class": "global/import_form",
        "user_reason": "Bitbucket Server import form — same class as github/jira.",
    },
    "iter3_import_fogbugz": {
        "__url__": "/import/fogbugz/new",
        "user_class": "global/import_form",
        "user_reason": "Fogbugz import form — same class.",
    },

    # IDE scope variants
    "iter3_ide_edit": {
        "__url__": "/-/ide/project/byteblaze/a11y-syntax-highlighting/edit/main/-/",
        "user_class": "ide/edit_view",
        "user_reason": "Scope=ide. URL `/-/ide/project/{ns}/{proj}/edit/{branch}/...`. Web IDE edit mode for file.",
    },
    "iter3_ide_mr": {
        "__url__": "/-/ide/project/byteblaze/a11y-webring.club/merge_requests/40",
        "user_class": "ide/mr_detail",
        "user_reason": "Scope=ide. URL `/-/ide/project/{ns}/{proj}/merge_requests/{id}`. Web IDE showing MR changes.",
    },

    # ═══════════════════════════════════════════════════════════
    # iter 4 — final convergence check discoveries
    # ═══════════════════════════════════════════════════════════
    "iter4_project_blame": {
        "__url__": "/byteblaze/empathy-prompts/-/blame/main/CONTRIBUTING.md",
        "user_class": "project/blame_view",
        "user_reason": "Scope=project. URL `/{ns}/{proj}/-/blame/{branch}/{path*}`. Git blame view.",
    },
    "iter4_project_raw_file": {
        "__url__": "/byteblaze/empathy-prompts/-/raw/main/CONTRIBUTING.md",
        "user_class": "project/raw_file",
        "user_reason": "Scope=project. URL `/{ns}/{proj}/-/raw/{branch}/{path*}`. Raw file content.",
    },
    "iter4_project_release_detail": {
        "__url__": "/byteblaze/empathy-prompts/-/releases/v0.1.0",
        "user_class": "project/release_detail",
        "user_reason": "Scope=project. URL `/{ns}/{proj}/-/releases/{tag}`. Single release detail.",
    },
    "iter4_project_release_edit": {
        "__url__": "/byteblaze/empathy-prompts/-/releases/v0.1.0/edit",
        "user_class": "project/release_edit_form",
        "user_reason": "Scope=project. URL `/{ns}/{proj}/-/releases/{tag}/edit`. Release edit form.",
    },
    "iter4_project_feature_flag_user_list_new": {
        "__url__": "/byteblaze/a11y-syntax-highlighting/-/feature_flags_user_lists/new",
        "user_class": "project/feature_flag_user_list_new_form",
        "user_reason": "Scope=project. URL `/-/feature_flags_user_lists/new`.",
    },

    # ═══════════════════════════════════════════════════════════
    # iter 5 — step 2' (frontier-BFS) branch variant instances
    # Adding master-branch instances so rule extractor generalizes {branch} slot
    # ═══════════════════════════════════════════════════════════
    "iter5_project_file_new_master": {
        "__url__": "/byteblaze/solarized-prism-theme/-/new/master",
        "user_class": "project/file_new_form",
        "user_reason": "Same class as iter2 /-/new/main; add master variant to trigger {branch} generalization.",
    },
    "iter5_ide_edit_master": {
        "__url__": "/-/ide/project/byteblaze/solarized-prism-theme/edit/master/-",
        "user_class": "ide/edit_view",
        "user_reason": "Same class as iter3 /-/ide/.../edit/main/-; add master variant for {branch} generalization.",
    },
}

# Merge iter3 patches into ANNOTATIONS at import time. These are URL-pattern-only
# entries (no AXTree / LLM pipeline) — for long-tail classes seen in iter 2 unmatched.
for _k, _v in _ITER3_PATCH.items():
    _entry = {k: v for k, v in _v.items() if not k.startswith("__")}
    ANNOTATIONS[_k] = _entry


def main():
    if not LLM_PATH.exists():
        print(f"ERROR: {LLM_PATH} not found. Run v1_b_llm_annotate first.")
        return

    llm_records = json.loads(LLM_PATH.read_text(encoding="utf-8"))

    merged = []
    llm_names = set()
    for rec in llm_records:
        name = rec["name"]
        llm_names.add(name)
        ann = ANNOTATIONS.get(name)
        if ann is None:
            print(f"  WARN: no assistant annotation for {name}")
            merged.append({
                **rec,
                "user_class": "",
                "user_reason": "",
                "user_reviewed": False,
            })
            continue
        merged.append({
            "name": name,
            "url": rec["url"],
            "title": rec["title"],
            "llm_class": rec.get("llm_class"),
            "llm_reason": rec.get("llm_reason"),
            "user_class": ann["user_class"],
            "user_reason": ann["user_reason"],
            "user_reviewed": False,
        })

    # iter3+ URL-pattern-only entries (no AXTree/LLM): pull from _ITER3_PATCH
    BASE_URL = "http://localhost:8023"
    for name, patch in _ITER3_PATCH.items():
        if name in llm_names:
            continue
        ann = ANNOTATIONS.get(name, {})
        url = BASE_URL + patch["__url__"]
        merged.append({
            "name": name,
            "url": url,
            "title": "",
            "llm_class": None,
            "llm_reason": None,
            "user_class": ann.get("user_class", ""),
            "user_reason": ann.get("user_reason", ""),
            "user_reviewed": False,
            "_url_pattern_only": True,
        })

    OUTPUT_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Saved: {OUTPUT_PATH}")

    # Review doc
    lines = []
    lines.append("# V1 — Annotation Filled (검증용)")
    lines.append("")
    lines.append("**Date**: 2026-04-18")
    lines.append("**Status**: Assistant 채움, 사용자 verify 대기")
    lines.append(f"**Total pages**: {len(merged)}")
    lines.append("")
    lines.append("## Workflow (Stage A)")
    lines.append("")
    lines.append("1. **Stage A.a**: 페이지 AXTree 수집")
    lines.append("2. **Stage A.b**: LLM annotation (동일 prompt/model)")
    lines.append("3. **Stage A.c**: Assistant가 convention 적용 → `user_class`/`user_reason` 확정")
    lines.append("4. **Stage A.e (다음)**: URL → class rule 추출")
    lines.append("5. **Stage A.f**: Rule을 Frozen KG 3,040 StatePattern에 적용")
    lines.append("")
    lines.append("## Naming convention (protocol v0.5 — class inheritance tree)")
    lines.append("")
    lines.append("표기: `{scope-class}/{…}/{leaf-class}[/{variant}]` — root `site` 생략")
    lines.append("")
    lines.append("**Scope class (tree 최상위)** — 공유 chrome(sidebar/header)으로 결정:")
    lines.append("- `project` — 사이드바 공유 action (실측)")
    lines.append("- `dashboard` — 헤더 공유 28 action")
    lines.append("- `explore` — explore 상단 탭")
    lines.append("- `user` — public user view (/username 류)")
    lines.append("- `account` — 로그인한 본인 계정 관리 (/-/profile/* 전용 사이드바 14 action)")
    lines.append("- `global` — 특정 scope 없음 (help, search, /projects/new 등)")
    lines.append("")
    lines.append("**Leaf class (tree 잎, 구체 페이지)** — core content widget으로 식별. 구조 접미사:")
    lines.append("- `_list`: flat 반복 항목 (issue_list, merge_request_list, commit_list, pipeline_list, ...)")
    lines.append("- `_detail`: 단일 entity view (issue_detail, blob_detail, commit_detail, ...)")
    lines.append("- `_new_form`: 생성 form (issue_new_form, branch_new_form, ...)")
    lines.append("- `settings_*`: settings 관련 form (settings_general/repository/ci_cd/...)")
    lines.append("- 기타: `main`, `help_landing`, `topic_list`, `wiki`, `search_page`, `profile`, `preferences`, `notifications`, `edit` 등")
    lines.append("")
    lines.append("**Variant (leaf 내부 sub-division, optional)** — action 차이가 filter/sort/state 축뿐일 때. "
                 "예: `todo_list/pending`·`/done`, `project_list/yours`·`/starred`.")
    lines.append("")
    lines.append("Reason 작성: URL > scope chrome 근거 > widget 구조 > widget-specific action. "
                 "Title 단독 근거 금지 (SPA back-nav 복원 이슈).")
    lines.append("")
    lines.append(f"## Annotations ({len(merged)})")
    lines.append("")
    lines.append("| # | name | URL | class | reason |")
    lines.append("|---|---|---|---|---|")
    for i, rec in enumerate(sorted(merged, key=lambda r: r["name"]), 1):
        url = rec["url"].replace("http://localhost:8023", "")
        usr = rec["user_class"]
        lines.append(
            f"| {i} | `{rec['name']}` | `{url}` | **`{usr}`** | {rec['user_reason']} |"
        )
    lines.append("")
    lines.append("## 집계")
    lines.append("")
    classes = [r["user_class"] for r in merged]
    cnt = Counter(classes)
    lines.append(f"- Total annotations: {len(merged)}")
    lines.append(f"- Unique class count: **{len(cnt)}**")
    lines.append(f"- Classes: {', '.join(f'`{c}`' for c in sorted(cnt))}")
    lines.append("")
    lines.append("중복 class (여러 페이지가 같은 class로 묶인 경우):")
    for c, n in sorted(cnt.items(), key=lambda x: (-x[1], x[0])):
        if n > 1:
            which = [r["name"] for r in merged if r["user_class"] == c]
            lines.append(f"- `{c}` ({n}): {', '.join(which)}")
    lines.append("")

    # Tree view
    lines.append("## Class tree")
    lines.append("")
    lines.append("```")
    tree: dict = {}
    for c, n in cnt.items():
        parts = c.split("/")
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        # leaf (possibly with count)
        leaf_key = parts[-1]
        node[leaf_key] = node.get(leaf_key, 0) + n

    def render(node, prefix: str = "", is_last: bool = True):
        if isinstance(node, int):
            return
        items = sorted(node.items(), key=lambda x: (isinstance(x[1], int), x[0]))
        for i, (key, child) in enumerate(items):
            last = i == len(items) - 1
            branch = "└── " if last else "├── "
            if isinstance(child, int):
                tag = f" (×{child})" if child > 1 else ""
                lines.append(f"{prefix}{branch}{key}{tag}")
            else:
                total = count_leaves(child)
                lines.append(f"{prefix}{branch}{key}/ ({total} page{'s' if total > 1 else ''})")
                new_prefix = prefix + ("    " if last else "│   ")
                render(child, new_prefix, last)

    def count_leaves(node):
        if isinstance(node, int):
            return node
        return sum(count_leaves(v) for v in node.values())

    total = count_leaves(tree)
    lines.append(f"site/ ({total} pages)")
    render(tree, "", True)
    lines.append("```")
    lines.append("")
    lines.append("- `/` 접미사 = internal node (scope 또는 intermediate class)")
    lines.append("- `×N` = 같은 leaf class에 속한 instance 수 (variant 미포함 시 instance, variant 있으면 variant 아래 instance)")
    lines.append("")

    lines.append("## 검증 방법")
    lines.append("")
    lines.append("- 각 행의 user_class/user_reason이 적절한지 검토")
    lines.append("- 수정 필요하면 말씀 → 수정 후 진행")
    lines.append("- OK면 Stage A.e (rule 추출) 진행")
    lines.append("")

    DOC_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOC_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Review doc: {DOC_OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
