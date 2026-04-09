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
        ("gitlab_dashboard", "dashboard", "Dashboard", "Projects, todos, issues", ["/", "/dashboard"]),
        ("gitlab_project_overview", "project_overview", "Project", "README, files, sidebar nav", ["/{ns}/{project}"]),
        ("gitlab_issues_list", "issues_list", "Issues", "Default: open, created desc", ["/-/issues"]),
        ("gitlab_merge_requests", "merge_requests", "Merge Requests", "", ["/-/merge_requests", "/dashboard/merge_requests"]),
        ("gitlab_commits", "commits_list", "Commits", "Repository > Commits", ["/-/commits"]),
        ("gitlab_contributors", "contributors", "Contributors", "Repository > Contributors", ["/-/graphs"]),
        ("gitlab_explore_projects", "explore_projects", "Explore", "Public: ?visibility_level=20", ["/explore", "/explore/projects"]),
        ("gitlab_user_projects", "user_projects", "User Projects", "Star counts per project", ["/users/{user}/projects"]),
        ("gitlab_user_settings", "user_settings", "Settings", "Access Tokens, SSH Keys, RSS", ["/-/profile"]),
    ]

    for pt_id, key, name, desc, patterns in page_types:
        cur.execute(
            "INSERT OR REPLACE INTO page_types VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pt_id, "gitlab", key, name, desc, json.dumps(patterns), json.dumps([])),
        )

    # --- ActionSchemas ---
    # (id, key, name, description, source, target)
    action_schemas = [
        ("gitlab_open_public_projects", "open_public_projects", "Public Projects",
         "goto /explore?visibility_level=20", "any", "explore_projects"),
        ("gitlab_filter_by_label", "filter_issues_by_label", "Filter by Label",
         "Click search → Label → select → Search", "issues_list", "issues_list"),
        ("gitlab_view_contributors", "view_contributors", "Contributors",
         "goto /-/graphs/{branch}", "project_overview", "contributors"),
        ("gitlab_view_commits", "view_commits", "Commits",
         "goto /-/commits/{branch}", "project_overview", "commits_list"),
        ("gitlab_list_user_projects", "list_user_projects", "User Projects",
         "goto /users/{user}/projects", "any", "user_projects"),
    ]

    for a_id, key, name, desc, src, tgt in action_schemas:
        cur.execute(
            "INSERT OR REPLACE INTO action_schemas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (a_id, "gitlab", key, name, desc, src, tgt, json.dumps([]), json.dumps([]), "", ""),
        )

    conn.commit()
