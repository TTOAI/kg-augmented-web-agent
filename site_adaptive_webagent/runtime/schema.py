from __future__ import annotations

import sqlite3


PRIOR_STORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS site_profiles (
    site_id TEXT PRIMARY KEY,
    site_key TEXT NOT NULL,
    domain TEXT NOT NULL,
    login_type TEXT NOT NULL,
    onboarding_status TEXT NOT NULL,
    default_execution_mode TEXT NOT NULL,
    prior_confidence TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS page_types (
    page_type_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    page_key TEXT NOT NULL,
    url_patterns TEXT NOT NULL,
    structural_signals TEXT NOT NULL,
    FOREIGN KEY (site_id) REFERENCES site_profiles(site_id)
);

CREATE TABLE IF NOT EXISTS action_schemas (
    action_schema_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    action_key TEXT NOT NULL,
    preconditions TEXT NOT NULL,
    postconditions TEXT NOT NULL,
    preferred_locator_strategy TEXT NOT NULL,
    FOREIGN KEY (site_id) REFERENCES site_profiles(site_id)
);

CREATE TABLE IF NOT EXISTS validator_rules (
    validator_rule_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    task_family TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    pass_criteria TEXT NOT NULL,
    FOREIGN KEY (site_id) REFERENCES site_profiles(site_id)
);

CREATE TABLE IF NOT EXISTS policy_rules (
    policy_rule_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    action_key TEXT NOT NULL,
    policy_type TEXT NOT NULL,
    policy_decision TEXT NOT NULL,
    FOREIGN KEY (site_id) REFERENCES site_profiles(site_id)
);

CREATE TABLE IF NOT EXISTS failure_patterns (
    failure_pattern_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    failure_type TEXT NOT NULL,
    detection_signal TEXT NOT NULL,
    recommended_recovery TEXT NOT NULL,
    FOREIGN KEY (site_id) REFERENCES site_profiles(site_id)
);
"""


EXECUTION_MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS task_runs (
    task_run_id TEXT PRIMARY KEY,
    request_text TEXT NOT NULL,
    site_id TEXT NOT NULL,
    task_family TEXT NOT NULL,
    run_mode TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    prior_used INTEGER NOT NULL,
    validator_used INTEGER NOT NULL,
    recovery_used INTEGER NOT NULL,
    FOREIGN KEY (site_id) REFERENCES site_profiles(site_id)
);

CREATE TABLE IF NOT EXISTS step_records (
    step_record_id TEXT PRIMARY KEY,
    task_run_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    status TEXT NOT NULL,
    pre_state_summary TEXT NOT NULL,
    post_state_summary TEXT NOT NULL,
    FOREIGN KEY (task_run_id) REFERENCES task_runs(task_run_id)
);

CREATE TABLE IF NOT EXISTS validation_records (
    validation_record_id TEXT PRIMARY KEY,
    task_run_id TEXT NOT NULL,
    validator_rule_id TEXT NOT NULL,
    result TEXT NOT NULL,
    validated_at TEXT NOT NULL,
    FOREIGN KEY (task_run_id) REFERENCES task_runs(task_run_id),
    FOREIGN KEY (validator_rule_id) REFERENCES validator_rules(validator_rule_id)
);

CREATE TABLE IF NOT EXISTS recovery_records (
    recovery_record_id TEXT PRIMARY KEY,
    task_run_id TEXT NOT NULL,
    failure_pattern_id TEXT NOT NULL,
    recovery_action TEXT NOT NULL,
    recovery_result TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (task_run_id) REFERENCES task_runs(task_run_id),
    FOREIGN KEY (failure_pattern_id) REFERENCES failure_patterns(failure_pattern_id)
);

CREATE TABLE IF NOT EXISTS approval_events (
    approval_event_id TEXT PRIMARY KEY,
    task_run_id TEXT NOT NULL,
    action_key TEXT NOT NULL,
    approval_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (task_run_id) REFERENCES task_runs(task_run_id)
);
"""


def bootstrap_runtime_schema(connection: sqlite3.Connection) -> None:
    """runtime schema를 생성한다."""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(PRIOR_STORE_SCHEMA)
    connection.executescript(EXECUTION_MEMORY_SCHEMA)
    connection.commit()
