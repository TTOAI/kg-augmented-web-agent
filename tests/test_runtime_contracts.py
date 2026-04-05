from __future__ import annotations

from dataclasses import fields
import sqlite3
import unittest

from site_adaptive_webagent.runtime.enums import (
    ApprovalEventStatus,
    ApprovalState,
    PriorConfidence,
    RecoveryResult,
    RouteKind,
    SiteOnboardingStatus,
    StepRecordStatus,
    TaskRunStatus,
    ValidationResult,
)
from site_adaptive_webagent.runtime.router import RouteInput, StrategyRouter
from site_adaptive_webagent.runtime.schema import bootstrap_runtime_schema
from site_adaptive_webagent.runtime.types import (
    ActionSchema,
    ApprovalEvent,
    FailurePattern,
    PageType,
    PolicyRule,
    PriorBundle,
    RecoveryRecord,
    RunContext,
    RunRequest,
    SiteProfile,
    StepRecord,
    TaskRun,
    ValidationRecord,
    ValidatorRule,
    WorkflowHint,
)


class RuntimeContractTests(unittest.TestCase):
    def test_run_request_has_documented_fields(self) -> None:
        self.assertEqual(
            {field.name for field in fields(RunRequest)},
            {"request_text", "task_family", "user_constraints", "risk_tolerance"},
        )

    def test_run_context_has_documented_fields(self) -> None:
        self.assertEqual(
            {field.name for field in fields(RunContext)},
            {"site_id", "page_type_id", "task_family", "state_summary", "approval_state"},
        )

    def test_prior_bundle_has_documented_fields(self) -> None:
        self.assertEqual(
            {field.name for field in fields(PriorBundle)},
            {
                "site_profile",
                "page_types",
                "action_schemas",
                "workflow_hints",
                "validator_rules",
                "policy_rules",
                "failure_patterns",
            },
        )

    def test_prior_entities_have_documented_fields(self) -> None:
        entity_fields = {
            SiteProfile: {
                "site_id",
                "site_key",
                "domain",
                "login_type",
                "onboarding_status",
                "default_execution_mode",
                "prior_confidence",
            },
            PageType: {"page_type_id", "site_id", "page_key", "url_patterns", "structural_signals"},
            ActionSchema: {
                "action_schema_id",
                "site_id",
                "action_key",
                "preconditions",
                "postconditions",
                "preferred_locator_strategy",
            },
            WorkflowHint: {
                "workflow_hint_id",
                "site_id",
                "task_family",
                "typical_step_order",
                "branch_points",
                "expected_terminal_states",
            },
            ValidatorRule: {
                "validator_rule_id",
                "site_id",
                "task_family",
                "rule_type",
                "pass_criteria",
            },
            PolicyRule: {
                "policy_rule_id",
                "site_id",
                "action_key",
                "policy_type",
                "policy_decision",
            },
            FailurePattern: {
                "failure_pattern_id",
                "site_id",
                "failure_type",
                "detection_signal",
                "recommended_recovery",
            },
        }

        for entity_type, expected_fields in entity_fields.items():
            with self.subTest(entity_type=entity_type.__name__):
                self.assertEqual({field.name for field in fields(entity_type)}, expected_fields)

    def test_execution_records_have_documented_fields(self) -> None:
        entity_fields = {
            TaskRun: {
                "task_run_id",
                "request_text",
                "site_id",
                "task_family",
                "run_mode",
                "status",
                "started_at",
                "ended_at",
                "prior_used",
                "validator_used",
                "recovery_used",
            },
            StepRecord: {
                "step_record_id",
                "task_run_id",
                "step_index",
                "step_type",
                "status",
                "pre_state_summary",
                "post_state_summary",
            },
            ValidationRecord: {
                "validation_record_id",
                "task_run_id",
                "validator_rule_id",
                "result",
                "validated_at",
            },
            RecoveryRecord: {
                "recovery_record_id",
                "task_run_id",
                "failure_pattern_id",
                "recovery_action",
                "recovery_result",
                "recorded_at",
            },
            ApprovalEvent: {
                "approval_event_id",
                "task_run_id",
                "action_key",
                "approval_status",
                "reason",
                "recorded_at",
            },
        }

        for entity_type, expected_fields in entity_fields.items():
            with self.subTest(entity_type=entity_type.__name__):
                self.assertEqual({field.name for field in fields(entity_type)}, expected_fields)

    def test_documented_enums_match_expected_values(self) -> None:
        self.assertEqual([member.value for member in PriorConfidence], ["sufficient", "insufficient"])
        self.assertEqual([member.value for member in ApprovalState], ["not_required", "requested", "approved", "rejected"])
        self.assertEqual(
            [member.value for member in TaskRunStatus],
            ["pending", "running", "approval_wait", "validated", "failed", "handoff", "cancelled"],
        )
        self.assertEqual([member.value for member in StepRecordStatus], ["pending", "running", "succeeded", "failed", "skipped"])
        self.assertEqual([member.value for member in ValidationResult], ["pass", "fail", "partial"])
        self.assertEqual([member.value for member in RecoveryResult], ["success", "failed", "handoff", "approval_wait"])
        self.assertEqual([member.value for member in SiteOnboardingStatus], ["draft", "active", "stale", "disabled"])
        self.assertEqual([member.value for member in ApprovalEventStatus], ["requested", "approved", "rejected"])
        self.assertEqual(
            [member.value for member in RouteKind],
            ["fast_path", "partial_prior", "fallback", "approval_first"],
        )

    def test_run_context_accepts_unresolved_page_type(self) -> None:
        context = RunContext(
            site_id="gitlab",
            page_type_id="unresolved",
            task_family="dashboard_lookup",
            state_summary="unknown",
        )

        self.assertEqual(context.page_type_id, "unresolved")
        self.assertEqual(context.approval_state, ApprovalState.NOT_REQUIRED)


class RuntimeSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        bootstrap_runtime_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_bootstrap_creates_prior_and_execution_tables(self) -> None:
        tables = {
            row[0]
            for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

        self.assertTrue(
            {
                "site_profiles",
                "page_types",
                "action_schemas",
                "workflow_hints",
                "validator_rules",
                "policy_rules",
                "failure_patterns",
                "task_runs",
                "step_records",
                "validation_records",
                "recovery_records",
                "approval_events",
            }.issubset(tables)
        )

    def test_task_run_child_tables_keep_foreign_keys(self) -> None:
        child_tables = {
            "step_records": {"task_runs"},
            "validation_records": {"task_runs", "validator_rules"},
            "recovery_records": {"task_runs", "failure_patterns"},
            "approval_events": {"task_runs"},
        }

        for table_name, expected_refs in child_tables.items():
            with self.subTest(table_name=table_name):
                refs = {
                    row[2]
                    for row in self.connection.execute(f"PRAGMA foreign_key_list({table_name})")
                }
                self.assertEqual(refs, expected_refs)

    def test_prior_and_execution_groups_are_separate(self) -> None:
        prior_tables = {
            "site_profiles",
            "page_types",
            "action_schemas",
            "workflow_hints",
            "validator_rules",
            "policy_rules",
            "failure_patterns",
        }
        execution_tables = {
            "task_runs",
            "step_records",
            "validation_records",
            "recovery_records",
            "approval_events",
        }

        tables = {
            row[0]
            for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        self.assertTrue(prior_tables.issubset(tables))
        self.assertTrue(execution_tables.issubset(tables))
        self.assertTrue(prior_tables.isdisjoint(execution_tables))


class StrategyRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = StrategyRouter()

    def test_selects_fast_path_when_all_conditions_are_met(self) -> None:
        decision = self.router.route(
            RouteInput(
                site_onboarding_status=SiteOnboardingStatus.ACTIVE,
                task_family_matches=True,
                prior_confidence=PriorConfidence.SUFFICIENT,
                approval_required=False,
                workflow_hint_available=True,
                action_schema_available=True,
                page_type_id="dashboard",
            )
        )

        self.assertEqual(decision.route, RouteKind.FAST_PATH)

    def test_selects_partial_prior_when_task_family_does_not_match(self) -> None:
        decision = self.router.route(
            RouteInput(
                site_onboarding_status=SiteOnboardingStatus.ACTIVE,
                task_family_matches=False,
                prior_confidence=PriorConfidence.SUFFICIENT,
                approval_required=False,
                workflow_hint_available=True,
                action_schema_available=True,
                page_type_id="dashboard",
            )
        )

        self.assertEqual(decision.route, RouteKind.PARTIAL_PRIOR)

    def test_selects_partial_prior_when_confidence_is_insufficient(self) -> None:
        decision = self.router.route(
            RouteInput(
                site_onboarding_status=SiteOnboardingStatus.ACTIVE,
                task_family_matches=True,
                prior_confidence=PriorConfidence.INSUFFICIENT,
                approval_required=False,
                workflow_hint_available=True,
                action_schema_available=True,
                page_type_id="dashboard",
            )
        )

        self.assertEqual(decision.route, RouteKind.PARTIAL_PRIOR)

    def test_selects_partial_prior_when_required_prior_is_missing(self) -> None:
        decision = self.router.route(
            RouteInput(
                site_onboarding_status=SiteOnboardingStatus.ACTIVE,
                task_family_matches=True,
                prior_confidence=PriorConfidence.SUFFICIENT,
                approval_required=False,
                workflow_hint_available=False,
                action_schema_available=True,
                page_type_id="dashboard",
            )
        )

        self.assertEqual(decision.route, RouteKind.PARTIAL_PRIOR)

    def test_selects_fallback_when_page_type_is_unresolved(self) -> None:
        decision = self.router.route(
            RouteInput(
                site_onboarding_status=SiteOnboardingStatus.ACTIVE,
                task_family_matches=True,
                prior_confidence=PriorConfidence.SUFFICIENT,
                approval_required=False,
                workflow_hint_available=True,
                action_schema_available=True,
                page_type_id="unresolved",
            )
        )

        self.assertEqual(decision.route, RouteKind.FALLBACK)

    def test_selects_fallback_when_site_is_not_active(self) -> None:
        decision = self.router.route(
            RouteInput(
                site_onboarding_status=SiteOnboardingStatus.DRAFT,
                task_family_matches=True,
                prior_confidence=PriorConfidence.SUFFICIENT,
                approval_required=False,
                workflow_hint_available=True,
                action_schema_available=True,
                page_type_id="dashboard",
            )
        )

        self.assertEqual(decision.route, RouteKind.FALLBACK)

    def test_approval_first_overrides_other_conditions(self) -> None:
        decision = self.router.route(
            RouteInput(
                site_onboarding_status=SiteOnboardingStatus.ACTIVE,
                task_family_matches=True,
                prior_confidence=PriorConfidence.SUFFICIENT,
                approval_required=True,
                workflow_hint_available=True,
                action_schema_available=True,
                page_type_id="dashboard",
            )
        )

        self.assertEqual(decision.route, RouteKind.APPROVAL_FIRST)


if __name__ == "__main__":
    unittest.main()
