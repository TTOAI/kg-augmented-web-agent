from __future__ import annotations

import sqlite3
import unittest

from site_adaptive_webagent.runtime.enums import (
    PriorConfidence,
    RecoveryResult,
    SiteOnboardingStatus,
    StepRecordStatus,
    TaskRunStatus,
    ValidationResult,
)
from site_adaptive_webagent.runtime.schema import bootstrap_runtime_schema
from site_adaptive_webagent.runtime.store import ExecutionStore, PriorStore
from site_adaptive_webagent.runtime.types import (
    ActionSchema,
    ApprovalEvent,
    FailurePattern,
    PageType,
    PolicyRule,
    RecoveryRecord,
    SiteProfile,
    StepRecord,
    TaskRun,
    ValidationRecord,
    ValidatorRule,
)

from .fixtures import (
    make_action_schema,
    make_approval_event,
    make_failure_pattern,
    make_page_type,
    make_policy_rule,
    make_recovery_record,
    make_site_profile,
    make_step_record,
    make_task_run,
    make_validation_record,
    make_validator_rule,
)


class PriorStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        bootstrap_runtime_schema(self.connection)
        self.store = PriorStore(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def _insert_site_profile(self, profile: SiteProfile) -> None:
        self.connection.execute(
            "INSERT INTO site_profiles VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                profile.site_id,
                profile.site_key,
                profile.domain,
                profile.login_type,
                profile.onboarding_status,
                profile.default_execution_mode,
                profile.prior_confidence,
            ),
        )
        self.connection.commit()

    def _insert_action_schema(self, schema: ActionSchema) -> None:
        import json

        self.connection.execute(
            "INSERT INTO action_schemas VALUES (?, ?, ?, ?, ?, ?)",
            (
                schema.action_schema_id,
                schema.site_id,
                schema.action_key,
                json.dumps(schema.preconditions),
                json.dumps(schema.postconditions),
                schema.preferred_locator_strategy,
            ),
        )
        self.connection.commit()

    def _insert_validator_rule(self, rule: ValidatorRule) -> None:
        self.connection.execute(
            "INSERT INTO validator_rules VALUES (?, ?, ?, ?, ?)",
            (
                rule.validator_rule_id,
                rule.site_id,
                rule.task_family,
                rule.rule_type,
                rule.pass_criteria,
            ),
        )
        self.connection.commit()

    def _insert_policy_rule(self, rule: PolicyRule) -> None:
        self.connection.execute(
            "INSERT INTO policy_rules VALUES (?, ?, ?, ?, ?)",
            (
                rule.policy_rule_id,
                rule.site_id,
                rule.action_key,
                rule.policy_type,
                rule.policy_decision,
            ),
        )
        self.connection.commit()

    def _insert_failure_pattern(self, pattern: FailurePattern) -> None:
        self.connection.execute(
            "INSERT INTO failure_patterns VALUES (?, ?, ?, ?, ?)",
            (
                pattern.failure_pattern_id,
                pattern.site_id,
                pattern.failure_type,
                pattern.detection_signal,
                pattern.recommended_recovery,
            ),
        )
        self.connection.commit()

    def _insert_page_type(self, page_type: PageType) -> None:
        import json

        self.connection.execute(
            "INSERT INTO page_types VALUES (?, ?, ?, ?, ?)",
            (
                page_type.page_type_id,
                page_type.site_id,
                page_type.page_key,
                json.dumps(page_type.url_patterns),
                json.dumps(page_type.structural_signals),
            ),
        )
        self.connection.commit()

    def test_get_site_profile_returns_none_when_not_found(self) -> None:
        result = self.store.get_site_profile("nonexistent")
        self.assertIsNone(result)

    def test_get_site_profile_round_trip(self) -> None:
        profile = make_site_profile()
        self._insert_site_profile(profile)
        result = self.store.get_site_profile(profile.site_id)
        self.assertEqual(result, profile)

    def test_get_action_schemas_round_trip(self) -> None:
        profile = make_site_profile()
        self._insert_site_profile(profile)
        schema = make_action_schema(site_id=profile.site_id)
        self._insert_action_schema(schema)
        results = self.store.get_action_schemas(profile.site_id)
        self.assertEqual(results, [schema])

    def test_get_validator_rules_round_trip(self) -> None:
        profile = make_site_profile()
        self._insert_site_profile(profile)
        rule = make_validator_rule(site_id=profile.site_id)
        self._insert_validator_rule(rule)
        results = self.store.get_validator_rules(profile.site_id, rule.task_family)
        self.assertEqual(results, [rule])

    def test_get_policy_rules_round_trip(self) -> None:
        profile = make_site_profile()
        self._insert_site_profile(profile)
        rule = make_policy_rule(site_id=profile.site_id)
        self._insert_policy_rule(rule)
        results = self.store.get_policy_rules(profile.site_id)
        self.assertEqual(results, [rule])

    def test_get_failure_patterns_round_trip(self) -> None:
        profile = make_site_profile()
        self._insert_site_profile(profile)
        pattern = make_failure_pattern(site_id=profile.site_id)
        self._insert_failure_pattern(pattern)
        results = self.store.get_failure_patterns(profile.site_id)
        self.assertEqual(results, [pattern])

    def test_get_page_types_round_trip(self) -> None:
        profile = make_site_profile()
        self._insert_site_profile(profile)
        page_type = make_page_type(site_id=profile.site_id)
        self._insert_page_type(page_type)
        results = self.store.get_page_types(profile.site_id)
        self.assertEqual(results, [page_type])

    def test_get_prior_bundle_returns_none_when_site_not_found(self) -> None:
        result = self.store.get_prior_bundle("nonexistent", "task_family")
        self.assertIsNone(result)

    def test_get_prior_bundle_assembles_all_prior_data(self) -> None:
        profile = make_site_profile()
        schema = make_action_schema(site_id=profile.site_id)
        rule = make_validator_rule(site_id=profile.site_id)
        self._insert_site_profile(profile)
        self._insert_action_schema(schema)
        self._insert_validator_rule(rule)

        bundle = self.store.get_prior_bundle(profile.site_id, rule.task_family)
        self.assertIsNotNone(bundle)
        assert bundle is not None
        self.assertEqual(bundle.site_profile, profile)
        self.assertEqual(bundle.action_schemas, [schema])
        self.assertEqual(bundle.validator_rules, [rule])


class ExecutionStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        bootstrap_runtime_schema(self.connection)
        self.prior_store = PriorStore(self.connection)
        self.store = ExecutionStore(self.connection)
        profile = make_site_profile()
        self.connection.execute(
            "INSERT INTO site_profiles VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                profile.site_id,
                profile.site_key,
                profile.domain,
                profile.login_type,
                profile.onboarding_status,
                profile.default_execution_mode,
                profile.prior_confidence,
            ),
        )
        rule = make_validator_rule(site_id=profile.site_id)
        self.connection.execute(
            "INSERT INTO validator_rules VALUES (?, ?, ?, ?, ?)",
            (rule.validator_rule_id, rule.site_id, rule.task_family, rule.rule_type, rule.pass_criteria),
        )
        pattern = make_failure_pattern(site_id=profile.site_id)
        self.connection.execute(
            "INSERT INTO failure_patterns VALUES (?, ?, ?, ?, ?)",
            (pattern.failure_pattern_id, pattern.site_id, pattern.failure_type, pattern.detection_signal, pattern.recommended_recovery),
        )
        self.connection.commit()
        self.site_id = profile.site_id
        self.validator_rule_id = rule.validator_rule_id
        self.failure_pattern_id = pattern.failure_pattern_id

    def tearDown(self) -> None:
        self.connection.close()

    def test_save_and_update_task_run(self) -> None:
        task_run = make_task_run(site_id=self.site_id)
        self.store.save_task_run(task_run)

        row = self.connection.execute(
            "SELECT status FROM task_runs WHERE task_run_id = ?",
            (task_run.task_run_id,),
        ).fetchone()
        self.assertEqual(row[0], TaskRunStatus.RUNNING)

        self.store.update_task_run_status(
            task_run.task_run_id, TaskRunStatus.VALIDATED, "2025-01-01T00:00:01Z"
        )
        row = self.connection.execute(
            "SELECT status FROM task_runs WHERE task_run_id = ?",
            (task_run.task_run_id,),
        ).fetchone()
        self.assertEqual(row[0], TaskRunStatus.VALIDATED)

    def test_save_step_record_with_fk(self) -> None:
        task_run = make_task_run(site_id=self.site_id)
        self.store.save_task_run(task_run)
        step = make_step_record(task_run_id=task_run.task_run_id)
        self.store.save_step_record(step)

        row = self.connection.execute(
            "SELECT task_run_id FROM step_records WHERE step_record_id = ?",
            (step.step_record_id,),
        ).fetchone()
        self.assertEqual(row[0], task_run.task_run_id)

    def test_save_validation_record_with_fk(self) -> None:
        task_run = make_task_run(site_id=self.site_id)
        self.store.save_task_run(task_run)
        record = make_validation_record(
            task_run_id=task_run.task_run_id,
            validator_rule_id=self.validator_rule_id,
        )
        self.store.save_validation_record(record)

        row = self.connection.execute(
            "SELECT task_run_id FROM validation_records WHERE validation_record_id = ?",
            (record.validation_record_id,),
        ).fetchone()
        self.assertEqual(row[0], task_run.task_run_id)

    def test_save_recovery_record_with_fk(self) -> None:
        task_run = make_task_run(site_id=self.site_id)
        self.store.save_task_run(task_run)
        record = make_recovery_record(
            task_run_id=task_run.task_run_id,
            failure_pattern_id=self.failure_pattern_id,
        )
        self.store.save_recovery_record(record)

        row = self.connection.execute(
            "SELECT task_run_id FROM recovery_records WHERE recovery_record_id = ?",
            (record.recovery_record_id,),
        ).fetchone()
        self.assertEqual(row[0], task_run.task_run_id)

    def test_save_approval_event_with_fk(self) -> None:
        task_run = make_task_run(site_id=self.site_id)
        self.store.save_task_run(task_run)
        event = make_approval_event(task_run_id=task_run.task_run_id)
        self.store.save_approval_event(event)

        row = self.connection.execute(
            "SELECT task_run_id FROM approval_events WHERE approval_event_id = ?",
            (event.approval_event_id,),
        ).fetchone()
        self.assertEqual(row[0], task_run.task_run_id)


if __name__ == "__main__":
    unittest.main()
