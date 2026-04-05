from __future__ import annotations

import json
import sqlite3

from .enums import PriorConfidence, SiteOnboardingStatus, TaskRunStatus
from .types import (
    ActionSchema,
    ApprovalEvent,
    FailurePattern,
    PageType,
    PolicyRule,
    PriorBundle,
    RecoveryRecord,
    SiteProfile,
    StepRecord,
    TaskRun,
    ValidationRecord,
    ValidatorRule,
    WorkflowHint,
)


class PriorStore:
    """prior 테이블 조회 전용 store."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def get_site_profile(self, site_id: str) -> SiteProfile | None:
        row = self._conn.execute(
            "SELECT site_id, site_key, domain, login_type, onboarding_status, "
            "default_execution_mode, prior_confidence "
            "FROM site_profiles WHERE site_id = ?",
            (site_id,),
        ).fetchone()
        if row is None:
            return None
        return SiteProfile(
            site_id=row[0],
            site_key=row[1],
            domain=row[2],
            login_type=row[3],
            onboarding_status=SiteOnboardingStatus(row[4]),
            default_execution_mode=row[5],
            prior_confidence=PriorConfidence(row[6]),
        )

    def get_page_types(self, site_id: str) -> list[PageType]:
        rows = self._conn.execute(
            "SELECT page_type_id, site_id, page_key, url_patterns, structural_signals "
            "FROM page_types WHERE site_id = ?",
            (site_id,),
        ).fetchall()
        return [
            PageType(
                page_type_id=row[0],
                site_id=row[1],
                page_key=row[2],
                url_patterns=json.loads(row[3]),
                structural_signals=json.loads(row[4]),
            )
            for row in rows
        ]

    def get_workflow_hints(self, site_id: str, task_family: str) -> list[WorkflowHint]:
        rows = self._conn.execute(
            "SELECT workflow_hint_id, site_id, task_family, typical_step_order, "
            "branch_points, expected_terminal_states "
            "FROM workflow_hints WHERE site_id = ? AND task_family = ?",
            (site_id, task_family),
        ).fetchall()
        return [
            WorkflowHint(
                workflow_hint_id=row[0],
                site_id=row[1],
                task_family=row[2],
                typical_step_order=json.loads(row[3]),
                branch_points=json.loads(row[4]),
                expected_terminal_states=json.loads(row[5]),
            )
            for row in rows
        ]

    def get_action_schemas(self, site_id: str) -> list[ActionSchema]:
        rows = self._conn.execute(
            "SELECT action_schema_id, site_id, action_key, preconditions, "
            "postconditions, preferred_locator_strategy "
            "FROM action_schemas WHERE site_id = ?",
            (site_id,),
        ).fetchall()
        return [
            ActionSchema(
                action_schema_id=row[0],
                site_id=row[1],
                action_key=row[2],
                preconditions=json.loads(row[3]),
                postconditions=json.loads(row[4]),
                preferred_locator_strategy=row[5],
            )
            for row in rows
        ]

    def get_validator_rules(self, site_id: str, task_family: str) -> list[ValidatorRule]:
        rows = self._conn.execute(
            "SELECT validator_rule_id, site_id, task_family, rule_type, pass_criteria "
            "FROM validator_rules WHERE site_id = ? AND task_family = ?",
            (site_id, task_family),
        ).fetchall()
        return [
            ValidatorRule(
                validator_rule_id=row[0],
                site_id=row[1],
                task_family=row[2],
                rule_type=row[3],
                pass_criteria=row[4],
            )
            for row in rows
        ]

    def get_policy_rules(self, site_id: str) -> list[PolicyRule]:
        rows = self._conn.execute(
            "SELECT policy_rule_id, site_id, action_key, policy_type, policy_decision "
            "FROM policy_rules WHERE site_id = ?",
            (site_id,),
        ).fetchall()
        return [
            PolicyRule(
                policy_rule_id=row[0],
                site_id=row[1],
                action_key=row[2],
                policy_type=row[3],
                policy_decision=row[4],
            )
            for row in rows
        ]

    def get_failure_patterns(self, site_id: str) -> list[FailurePattern]:
        rows = self._conn.execute(
            "SELECT failure_pattern_id, site_id, failure_type, detection_signal, "
            "recommended_recovery "
            "FROM failure_patterns WHERE site_id = ?",
            (site_id,),
        ).fetchall()
        return [
            FailurePattern(
                failure_pattern_id=row[0],
                site_id=row[1],
                failure_type=row[2],
                detection_signal=row[3],
                recommended_recovery=row[4],
            )
            for row in rows
        ]

    def get_prior_bundle(self, site_id: str, task_family: str) -> PriorBundle | None:
        """site_id 기준 prior 전체를 묶어 반환한다. site_profile이 없으면 None."""
        site_profile = self.get_site_profile(site_id)
        if site_profile is None:
            return None
        return PriorBundle(
            site_profile=site_profile,
            page_types=self.get_page_types(site_id),
            action_schemas=self.get_action_schemas(site_id),
            workflow_hints=self.get_workflow_hints(site_id, task_family),
            validator_rules=self.get_validator_rules(site_id, task_family),
            policy_rules=self.get_policy_rules(site_id),
            failure_patterns=self.get_failure_patterns(site_id),
        )


class ExecutionStore:
    """execution memory 테이블 저장 전용 store."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def save_task_run(self, task_run: TaskRun) -> None:
        self._conn.execute(
            "INSERT INTO task_runs "
            "(task_run_id, request_text, site_id, task_family, run_mode, status, "
            "started_at, ended_at, prior_used, validator_used, recovery_used) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                task_run.task_run_id,
                task_run.request_text,
                task_run.site_id,
                task_run.task_family,
                task_run.run_mode,
                task_run.status,
                task_run.started_at,
                task_run.ended_at,
                int(task_run.prior_used),
                int(task_run.validator_used),
                int(task_run.recovery_used),
            ),
        )
        self._conn.commit()

    def update_task_run_status(
        self,
        task_run_id: str,
        status: TaskRunStatus,
        ended_at: str,
    ) -> None:
        self._conn.execute(
            "UPDATE task_runs SET status = ?, ended_at = ? WHERE task_run_id = ?",
            (status, ended_at, task_run_id),
        )
        self._conn.commit()

    def save_step_record(self, step_record: StepRecord) -> None:
        self._conn.execute(
            "INSERT INTO step_records "
            "(step_record_id, task_run_id, step_index, step_type, status, "
            "pre_state_summary, post_state_summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                step_record.step_record_id,
                step_record.task_run_id,
                step_record.step_index,
                step_record.step_type,
                step_record.status,
                step_record.pre_state_summary,
                step_record.post_state_summary,
            ),
        )
        self._conn.commit()

    def save_validation_record(self, record: ValidationRecord) -> None:
        self._conn.execute(
            "INSERT INTO validation_records "
            "(validation_record_id, task_run_id, validator_rule_id, result, validated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                record.validation_record_id,
                record.task_run_id,
                record.validator_rule_id,
                record.result,
                record.validated_at,
            ),
        )
        self._conn.commit()

    def save_recovery_record(self, record: RecoveryRecord) -> None:
        self._conn.execute(
            "INSERT INTO recovery_records "
            "(recovery_record_id, task_run_id, failure_pattern_id, recovery_action, "
            "recovery_result, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                record.recovery_record_id,
                record.task_run_id,
                record.failure_pattern_id,
                record.recovery_action,
                record.recovery_result,
                record.recorded_at,
            ),
        )
        self._conn.commit()

    def save_approval_event(self, event: ApprovalEvent) -> None:
        self._conn.execute(
            "INSERT INTO approval_events "
            "(approval_event_id, task_run_id, action_key, approval_status, reason, recorded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.approval_event_id,
                event.task_run_id,
                event.action_key,
                event.approval_status,
                event.reason,
                event.recorded_at,
            ),
        )
        self._conn.commit()
