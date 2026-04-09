"""GitLab Prior Seed 데이터.

GitLab 사이트의 구조적 사전 지식을 SQLite에 주입한다.
"""
from __future__ import annotations

import json
import sqlite3


def seed_gitlab_prior(conn: sqlite3.Connection, *, base_url: str) -> None:
    """GitLab Prior 데이터를 DB에 INSERT한다."""
    cur = conn.cursor()

    # --- SiteProfile ---
    cur.execute(
        "INSERT OR REPLACE INTO site_profiles VALUES (?, ?, ?, ?, ?, ?)",
        ("gitlab", "GitLab", base_url, "session", "active", "sufficient"),
    )

    # --- PageTypes ---
    page_types = [
        {
            "page_type_id": "gitlab_dashboard",
            "page_key": "dashboard",
            "display_name": "Dashboard",
            "description": "User dashboard with project list, todos, issues overview",
            "url_patterns": ["/", "/dashboard", "/dashboard/projects"],
        },
        {
            "page_type_id": "gitlab_project_overview",
            "page_key": "project_overview",
            "display_name": "Project Overview",
            "description": "Project main page with README, file tree, and sidebar navigation",
            "url_patterns": ["/{namespace}/{project}"],
        },
        {
            "page_type_id": "gitlab_issues_list",
            "page_key": "issues_list",
            "display_name": "Issues List",
            "description": "Issue list with filters. Default: open issues sorted by created date desc. Filters via Label/Assignee dropdowns, not text input.",
            "url_patterns": ["/-/issues"],
        },
        {
            "page_type_id": "gitlab_merge_requests",
            "page_key": "merge_requests",
            "display_name": "Merge Requests",
            "description": "MR list. Dashboard MRs at /dashboard/merge_requests, project MRs at /-/merge_requests",
            "url_patterns": ["/-/merge_requests", "/dashboard/merge_requests"],
        },
        {
            "page_type_id": "gitlab_commits",
            "page_key": "commits_list",
            "display_name": "Commits",
            "description": "Commit history for a branch. Shows author, date, message. Navigate via Repository > Commits.",
            "url_patterns": ["/-/commits"],
        },
        {
            "page_type_id": "gitlab_contributors",
            "page_key": "contributors",
            "display_name": "Contributors",
            "description": "Contributor statistics with commit counts, additions, deletions per author. Navigate via Repository > Contributors.",
            "url_patterns": ["/-/graphs"],
        },
        {
            "page_type_id": "gitlab_explore_projects",
            "page_key": "explore_projects",
            "display_name": "Explore Projects",
            "description": "Public project listing. Use visibility_level=20 for public only. Tabs: All, Most stars, Trending.",
            "url_patterns": ["/explore/projects", "/explore"],
        },
        {
            "page_type_id": "gitlab_user_projects",
            "page_key": "user_projects",
            "display_name": "User Projects",
            "description": "Personal projects of a user. Shows star count per project.",
            "url_patterns": ["/users/{user}/projects"],
        },
        {
            "page_type_id": "gitlab_user_settings",
            "page_key": "user_settings",
            "display_name": "User Settings",
            "description": "Profile, account, access tokens, SSH keys, etc. RSS feed token is under Access Tokens page.",
            "url_patterns": ["/-/profile"],
        },
    ]

    for pt in page_types:
        cur.execute(
            "INSERT OR REPLACE INTO page_types VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                pt["page_type_id"],
                "gitlab",
                pt["page_key"],
                pt["display_name"],
                pt["description"],
                json.dumps(pt["url_patterns"]),
                json.dumps([]),  # structural_signals
            ),
        )

    # --- ActionSchemas ---
    action_schemas = [
        {
            "action_schema_id": "gitlab_open_public_projects",
            "action_key": "open_public_projects",
            "display_name": "Open Public Projects",
            "description": "Navigate to public projects listing. URL: /explore?visibility_level=20",
            "source_page_key": "any",
            "target_page_key": "explore_projects",
        },
        {
            "action_schema_id": "gitlab_filter_issues_by_label",
            "action_key": "filter_issues_by_label",
            "display_name": "Filter Issues by Label",
            "description": "On issues page: click search input → click Label from dropdown → select operator → select label value → click Search button",
            "source_page_key": "issues_list",
            "target_page_key": "issues_list",
        },
        {
            "action_schema_id": "gitlab_view_contributors",
            "action_key": "view_contributors",
            "display_name": "View Contributors",
            "description": "Navigate to contributor stats: Repository > Contributors, or URL /-/graphs/{branch}",
            "source_page_key": "project_overview",
            "target_page_key": "contributors",
        },
        {
            "action_schema_id": "gitlab_view_commits",
            "action_key": "view_commits",
            "display_name": "View Commits",
            "description": "Navigate to commit history: Repository > Commits, or URL /-/commits/{branch}",
            "source_page_key": "project_overview",
            "target_page_key": "commits_list",
        },
        {
            "action_schema_id": "gitlab_list_user_projects",
            "action_key": "list_user_projects",
            "display_name": "List User Projects",
            "description": "Navigate to a user's personal project list: /users/{username}/projects. Shows star count per project.",
            "source_page_key": "any",
            "target_page_key": "user_projects",
        },
    ]

    for action in action_schemas:
        cur.execute(
            "INSERT OR REPLACE INTO action_schemas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                action["action_schema_id"],
                "gitlab",
                action["action_key"],
                action["display_name"],
                action["description"],
                action["source_page_key"],
                action.get("target_page_key"),
                json.dumps([]),  # preconditions
                json.dumps([]),  # postconditions
                "",  # locator_strategy
                "",  # locator_value
            ),
        )

    conn.commit()
