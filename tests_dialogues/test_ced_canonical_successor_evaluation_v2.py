"""Independent pre-result locks for the Phase 8 v2 successor evaluator.

Every executable check in this module is case-local.  The authoritative and
replay aggregate builders, artifact publishers, providers, models, tools, and
live paths are never called.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import backend.dialogues.ced_canonical_successor_evaluation_v2 as evaluation
from backend.dialogues.ced_canonical_successor_cases_v2 import (
    FROZEN_CANONICAL_SUCCESSOR_PROBES_V2,
    InvariantState,
    ProbeInvariantVector,
    ProbeStage,
)
from backend.dialogues.ced_canonical_successor_contracts import (
    CanonicalTransitionStatus,
    SuccessorUnavailableReason,
)
from backend.dialogues.socrates_zero.contracts import ContractValidationError


_VECTOR_FIELDS = (
    "root_identity",
    "capsule_identity",
    "pending_identity",
    "task_semantic_identity",
    "public_context_digest",
    "council_roster_digest",
    "action_identity",
    "observation_manifest_identity",
    "observation_payload_digest",
    "provider_binding",
    "exact_model_binding",
    "configuration_binding",
    "lineage_binding",
    "future_label_status",
    "budget_status",
)

_PROBE_EXPECTATIONS = {
    "p8v2-o01-invalid-root-registration": (
        evaluation.ProbeOutcomeKind.RAISED_UNAVAILABLE,
        "C1",
        SuccessorUnavailableReason.INVALID_ROOT,
        "INNPPPPPPPPPNPP",
    ),
    "p8v2-o02-illegal-action-capability": (
        evaluation.ProbeOutcomeKind.RAISED_UNAVAILABLE,
        "P8",
        SuccessorUnavailableReason.ILLEGAL_ACTION,
        "PPNPPPIPPPPPPPP",
    ),
    "p8v2-o03-missing-observation": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A3",
        SuccessorUnavailableReason.MISSING_OBSERVATION,
        "PPPPPPPINPPPPPP",
    ),
    "p8v2-o04-invalid-observation-schema": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A5",
        SuccessorUnavailableReason.INVALID_OBSERVATION,
        "PPPPPPPNIPPPPPP",
    ),
    "p8v2-o05-tampered-raw-digest": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A5",
        SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
        "PPPPPPPIPPPPPPP",
    ),
    "p8v2-o06-wrong-task-agent": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A9",
        SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH,
        "DDDIPPPPPPPDDPP",
    ),
    "p8v2-o07-wrong-root-question": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A8",
        SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
        "IDDDPPPPPPPPDPP",
    ),
    "p8v2-o08-wrong-exact-model": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A11",
        SuccessorUnavailableReason.OBSERVATION_MODEL_MISMATCH,
        "DDDDPPPPPPIDDPP",
    ),
    "p8v2-o09-wrong-runtime-timeout": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A12",
        SuccessorUnavailableReason.OBSERVATION_CONFIG_MISMATCH,
        "DDDPPPPPPPPIDPP",
    ),
    "p8v2-o10-future-label": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A4",
        SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN,
        "PPPPPPPPPPPPPIP",
    ),
    "p8v2-o11-budget-exhausted": (
        evaluation.ProbeOutcomeKind.RAISED_UNAVAILABLE,
        "P9",
        SuccessorUnavailableReason.BUDGET_EXHAUSTED,
        "DDNPPPPPPPPPDPI",
    ),
    "p8v2-p01-unsupported-family-vs-legality": (
        evaluation.ProbeOutcomeKind.RAISED_UNAVAILABLE,
        "P7",
        SuccessorUnavailableReason.UNSUPPORTED_ACTION_FAMILY,
        "PPNPPPIPPPPPPPP",
    ),
    "p8v2-p02-provider-roster-context": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A8",
        SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
        "DDDDDIPPPDPDDPP",
    ),
    "p8v2-p03-root-plus-provider": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A8",
        SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
        "IDDDDIPPPDPDDPP",
    ),
    "p8v2-p04-task-plus-model": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A9",
        SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH,
        "DDDIPPPPPPIDDPP",
    ),
    "p8v2-p05-context-plus-tampered-digest": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A5",
        SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
        "IDDDPPPIPPPPDPP",
    ),
    "p8v2-p06-illegal-plus-incompatible-observation": (
        evaluation.ProbeOutcomeKind.RAISED_UNAVAILABLE,
        "P8",
        SuccessorUnavailableReason.ILLEGAL_ACTION,
        "IDNDPPIPPPPPDPP",
    ),
    "p8v2-p07-caller-rebinding-vs-manifest": (
        evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
        "A7",
        SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
        "IIIIPPPIPIIDIPP",
    ),
}

_CRITICAL_LITERAL_VALUES = {
    "p8v2-o05-tampered-raw-digest": (
        (
            "observation.raw_output_digest",
            '"912c229dca5ecb8d0ad0736b5e5241dae6e5a3a6ddf9151e323d1bc321d24f62"',
            '"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"',
            True,
        ),
    ),
    "p8v2-o06-wrong-task-agent": (
        (
            "root.active_agent_id",
            '"phase8-recorded-agent-1"',
            '"phase8-recorded-agent-1-v2"',
            True,
        ),
    ),
    "p8v2-o07-wrong-root-question": (
        (
            "root.question",
            '"Is knowledge merely justified true belief?"',
            '"What is knowledge?"',
            True,
        ),
    ),
    "p8v2-o08-wrong-exact-model": (
        (
            "root.active_model_id",
            '"phase8-recorded-model/1"',
            '"phase8-recorded-model/1-v2-orthogonal"',
            True,
        ),
    ),
    "p8v2-o09-wrong-runtime-timeout": (
        ("runtime.provider_timeout_seconds", "30.0", "31.0", True),
    ),
    "p8v2-o10-future-label": (
        ("observation.reward", "null", "1", True),
    ),
    "p8v2-o11-budget-exhausted": (
        ("budget.max_nodes", "4", "1", True),
    ),
    "p8v2-p07-caller-rebinding-vs-manifest": (
        (
            "caller.binding_case",
            '"opening-scripted-mock"',
            '"opening-empty-question"',
            True,
        ),
    ),
}

_POSITIVE_EXPECTATIONS = {
    "opening-empty-question": (
        CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        "socratic_content_rejected",
        None,
    ),
    "opening-injection-question": (
        CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        "answer_injection_rejected",
        None,
    ),
    "opening-invalid-json": (
        CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        "parser_rejected",
        None,
    ),
    "opening-schema-error": (
        CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        "schema_rejected",
        None,
    ),
    "opening-scripted-mock": (
        CanonicalTransitionStatus.APPLIED_ACCEPTED,
        None,
        "move_a0ac20327a5c",
    ),
}

_ADVISORY_PRECEDENCE = {
    "p8v2-p01-unsupported-family-vs-legality": (
        "P7",
        ("action_family",),
        ("not_in_legal_set",),
    ),
    "p8v2-p02-provider-roster-context": (
        "A8",
        ("context_digest", "request_semantic_digest"),
        (
            "model_config_digest",
            "provider_id",
            "source_capsule_id",
            "source_configuration_digest",
            "source_execution_id",
            "task_model_config_digest",
            "task_semantic_digest",
        ),
    ),
    "p8v2-p04-task-plus-model": (
        "A9",
        ("agent_id", "task_semantic_digest"),
        (
            "actual_model_id",
            "configured_model_id",
            "model_config_digest",
            "source_capsule_id",
            "source_configuration_digest",
            "source_execution_id",
            "task_model_config_digest",
        ),
    ),
    "p8v2-p05-context-plus-tampered-digest": (
        "A5",
        ("raw_output_digest",),
        (
            "request_semantic_digest",
            "source_capsule_id",
            "source_execution_id",
            "source_session_semantic_id",
            "task_semantic_digest",
        ),
    ),
    "p8v2-p06-illegal-plus-incompatible-observation": (
        "P8",
        ("required_capabilities",),
        (
            "action_id",
            "request_semantic_digest",
            "source_capsule_id",
            "source_execution_id",
            "source_session_semantic_id",
            "task_semantic_digest",
        ),
    ),
    "p8v2-p07-caller-rebinding-vs-manifest": (
        "A7",
        ("manifest_exact_observation",),
        (
            "actual_model_id",
            "agent_id",
            "configured_model_id",
            "model_config_digest",
            "provider_id",
            "request_semantic_digest",
            "source_capsule_id",
            "source_execution_id",
            "source_session_semantic_id",
            "task_model_config_digest",
            "task_semantic_digest",
        ),
    ),
}

_FIREWALL_GLOBAL_TRUTH = SimpleNamespace(
    payload={"opaque": ["A8", "root_context_mismatch"]}
)


def _operation_using_global_truth() -> object:
    return _FIREWALL_GLOBAL_TRUTH


def _probe(probe_id: str):
    return next(
        probe
        for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
        if probe.probe_id == probe_id
    )


def _vector_symbols(vector: ProbeInvariantVector) -> str:
    symbols = {
        InvariantState.PRESERVED: "P",
        InvariantState.INTENTIONALLY_CHANGED: "I",
        InvariantState.DEPENDENTLY_CHANGED: "D",
        InvariantState.NOT_APPLICABLE: "N",
    }
    return "".join(symbols[getattr(vector, name)] for name in _VECTOR_FIELDS)


def _green_metrics(**updates: int) -> evaluation.CanonicalSuccessorParityMetricsV2:
    values = {
        name: 0
        for name in evaluation.CanonicalSuccessorParityMetricsV2.model_fields
        if name != "schema_version"
    }
    values.update(
        cases_total=23,
        supported_authoritative_cases=5,
        accepted_reference_cases=1,
        canonical_rejection_reference_cases=4,
        orthogonal_negative_cases=11,
        precedence_negative_cases=7,
        accepted_parity=1,
        canonical_rejection_parity=4,
        orthogonal_primary_classifications=11,
        precedence_primary_classifications=7,
        historical_offline_fixture_dispatches=5,
    )
    values.update(updates)
    return evaluation.CanonicalSuccessorParityMetricsV2(**values)


def _schema_property_names(value: object) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
        for nested in value.values():
            names.update(_schema_property_names(nested))
    elif isinstance(value, list):
        for nested in value:
            names.update(_schema_property_names(nested))
    return names


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def test_versions_signatures_and_import_path_are_pre_result_only() -> None:
    assert {
        "harness": evaluation.CANONICAL_SUCCESSOR_PARITY_HARNESS_ID_V2,
        "unavailable": evaluation.CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION_V2,
        "failure": evaluation.CANONICAL_SUCCESSOR_PROBE_EVALUATION_FAILURE_VERSION_V2,
        "snapshot": evaluation.CANONICAL_SUCCESSOR_PROBE_COMPONENT_SNAPSHOT_VERSION_V2,
        "construction": evaluation.CANONICAL_SUCCESSOR_PROBE_CONSTRUCTION_EVIDENCE_VERSION_V2,
        "diagnostics": evaluation.CANONICAL_SUCCESSOR_COMPATIBILITY_DIAGNOSTIC_EVIDENCE_VERSION_V1,
        "metrics": evaluation.CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION_V2,
        "thresholds": evaluation.CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION_V2,
        "artifact": evaluation.CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION_V2,
        "replay_lock": evaluation.CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION_V2,
    } == {
        "harness": "ced-canonical-successor-parity-harness/v2",
        "unavailable": "ced-canonical-successor-unavailable-case-result/v2",
        "failure": "ced-canonical-successor-probe-evaluation-failure/v2",
        "snapshot": "ced-canonical-successor-probe-component-snapshot/v2",
        "construction": "ced-canonical-successor-probe-construction-evidence/v2",
        "diagnostics": "ced-canonical-successor-compatibility-diagnostic-evidence/v1",
        "metrics": "ced-canonical-successor-parity-metrics/v2",
        "thresholds": "ced-canonical-successor-parity-thresholds/v2",
        "artifact": "ced-canonical-successor-parity-artifact/v2",
        "replay_lock": "ced-canonical-successor-parity-replay-lock/v2",
    }
    assert tuple(
        inspect.signature(
            evaluation.build_canonical_successor_parity_artifact_v2
        ).parameters
    ) == ()
    assert tuple(
        inspect.signature(
            evaluation.build_canonical_successor_parity_replay_artifact_v2
        ).parameters
    ) == ("authoritative",)
    assert tuple(
        inspect.signature(evaluation._build_probe_execution_v2).parameters
    ) == ("probe_id",)
    assert tuple(
        inspect.signature(evaluation._construction_evidence_v2).parameters
    ) == ("probe", "execution")
    assert tuple(
        inspect.signature(evaluation._evaluate_unavailable_probe_v2).parameters
    ) == ("probe",)
    assert tuple(
        inspect.signature(evaluation.write_once_canonical_bytes_v2).parameters
    ) == ("destination", "payload")

    source = Path(evaluation.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls: set[str] = set()
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        top_level_calls.update(
            name
            for node in ast.walk(statement)
            if isinstance(node, ast.Call) and (name := _call_name(node)) is not None
        )
    assert not {
        "_build_canonical_successor_parity_artifact_v2_in_order",
        "build_canonical_successor_parity_artifact_v2",
        "build_canonical_successor_parity_replay_artifact_v2",
        "_evaluate_v1_parity_case",
        "_evaluate_unavailable_probe_v2",
        "_build_probe_execution_v2",
        "_actual_core_lock_mismatches",
        "_actual_predecessor_lock_mismatches",
    } & top_level_calls

    all_calls = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and (name := _call_name(node)) is not None
    }
    assert not {
        "_run_registry_phase",
        "run_adapter",
        "generate_agent_move",
        "capture_canonical_opening_observation",
        "generate",
    } & all_calls
    assert "build_canonical_successor_parity_artifact_v2" not in inspect.getsource(
        evaluation.publish_canonical_successor_parity_artifact_once_v2
    )
    assert "build_canonical_successor_parity_replay_artifact_v2" not in inspect.getsource(
        evaluation.publish_canonical_successor_parity_replay_lock_once_v2
    )

    test_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    called_by_tests = {
        name
        for node in ast.walk(test_tree)
        if isinstance(node, ast.Call) and (name := _call_name(node)) is not None
    }
    assert not {
        "_build_canonical_successor_parity_artifact_v2_in_order",
        "build_canonical_successor_parity_artifact_v2",
        "build_canonical_successor_parity_replay_artifact_v2",
        "publish_canonical_successor_parity_artifact_once_v2",
        "publish_canonical_successor_parity_replay_lock_once_v2",
    } & called_by_tests


def test_schema_surface_is_exact_frozen_and_extra_forbid() -> None:
    assert tuple(
        evaluation.CanonicalSuccessorProbeComponentSnapshotV2.model_fields
    ) == ("schema_version",) + _VECTOR_FIELDS
    assert tuple(ProbeInvariantVector.model_fields) == _VECTOR_FIELDS
    assert tuple(
        evaluation.CanonicalSuccessorProbeConstructionEvidenceV2.model_fields
    ) == (
        "schema_version",
        "construction_evidence_id",
        "probe_id",
        "probe_fingerprint",
        "reference_snapshot",
        "candidate_snapshot",
        "measured_invariant_vector",
        "observed_literal_mutations",
        "literal_mutations_match",
        "observation_submission",
        "observed_stage",
        "ground_truth_firewall_passed",
        "validity_gate_passed",
    )
    unavailable_fields = evaluation.CanonicalSuccessorUnavailableCaseResultV2.model_fields
    assert {
        "construction_evidence",
        "diagnostics",
        "source_runtime_fingerprint_before",
        "source_runtime_fingerprint_after",
        "sibling_runtime_fingerprint_before",
        "sibling_runtime_fingerprint_after",
        "production_runtime_fingerprint_before",
        "production_runtime_fingerprint_after",
        "replay_outcome_digest",
        "receipt_match",
        "resource_accounting_match",
        "negative_probe_dispatches",
        "aggregate_provider_dispatches",
        "live_calls",
        "model_calls",
        "tool_calls",
    } <= set(unavailable_fields)
    artifact_schema = evaluation.CanonicalSuccessorParityArtifactV2.model_json_schema()
    assert artifact_schema["properties"]["depth"]["const"] == 1
    assert artifact_schema["properties"]["recursive_successor"]["const"] is False
    assert artifact_schema["properties"]["production_authority"]["const"] == "none"
    property_names = _schema_property_names(artifact_schema)
    assert not {"created_at", "updated_at", "timestamp", "latency"} & property_names

    with pytest.raises(ValidationError):
        evaluation.CanonicalSuccessorProbeComponentSnapshotV2.model_validate(
            {"unexpected": True}
        )
    snapshot = evaluation.CanonicalSuccessorProbeComponentSnapshotV2()
    with pytest.raises(ValidationError):
        snapshot.root_identity = "0" * 64
    with pytest.raises(ValidationError):
        evaluation.CanonicalSuccessorParityMetricsV2.model_validate(
            {**_green_metrics().model_dump(mode="python"), "unexpected": 1}
        )


@pytest.mark.parametrize("probe_id", tuple(_PROBE_EXPECTATIONS))
def test_each_probe_build_and_construction_are_independently_valid(
    probe_id: str,
) -> None:
    expected_kind, expected_guard, expected_reason, expected_vector = (
        _PROBE_EXPECTATIONS[probe_id]
    )
    probe = _probe(probe_id)
    execution = evaluation._build_probe_execution_v2(probe_id)
    evidence = evaluation._construction_evidence_v2(probe, execution)
    expected_literals = tuple(
        (
            mutation.path,
            mutation.before_json,
            mutation.after_json,
            mutation.independent_authoritative_input,
        )
        for mutation in probe.literal_mutations
    )

    assert execution.probe_id == probe_id
    assert execution.invocation_stage is probe.stage
    assert execution.observation_submission is probe.observation_submission
    assert evaluation._provider_dispatches_v2(execution.source_adapters) == 0
    assert evidence.observed_stage is probe.stage
    assert evidence.measured_invariant_vector == probe.invariant_vector
    assert _vector_symbols(evidence.measured_invariant_vector) == expected_vector
    assert evidence.observed_literal_mutations == execution.literal_values
    assert evidence.observed_literal_mutations == expected_literals
    assert evidence.literal_mutations_match is True
    assert evidence.ground_truth_firewall_passed is True
    assert evidence.validity_gate_passed is True
    assert evidence.construction_evidence_id
    assert type(evidence).model_validate_json(evidence.model_dump_json()) == evidence
    if probe_id in _CRITICAL_LITERAL_VALUES:
        assert execution.literal_values == _CRITICAL_LITERAL_VALUES[probe_id]

    expected_status = (
        None
        if expected_kind is evaluation.ProbeOutcomeKind.RAISED_UNAVAILABLE
        else CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    )
    synthetic_outcome = evaluation._ProbeInvocationOutcomeV2(
        kind=expected_kind,
        reason=expected_reason,
        status=expected_status,
        result=None,
        outcome_digest="0" * 64,
    )
    assert evaluation._observed_guard_id(execution, synthetic_outcome) == expected_guard
    assert evaluation._measured_diagnostic_fields(
        execution, expected_guard
    ) == (
        probe.expected_primary_mismatch_fields,
        probe.advisory_or_dominated_mismatch_fields,
    )
    assert evaluation._observed_structured_scan(
        execution, expected_guard
    ) is probe.structured_future_scan_reached


@pytest.mark.parametrize("probe_id", tuple(_PROBE_EXPECTATIONS))
def test_each_focused_unavailable_probe_has_exact_outcome_and_zero_calls(
    probe_id: str,
) -> None:
    expected_kind, expected_guard, expected_reason, expected_vector = (
        _PROBE_EXPECTATIONS[probe_id]
    )
    probe = _probe(probe_id)
    result = evaluation._evaluate_unavailable_probe_v2(probe)

    assert isinstance(result, evaluation.CanonicalSuccessorUnavailableCaseResultV2)
    assert not isinstance(result, evaluation.CanonicalSuccessorProbeEvaluationFailureV2)
    assert result.probe_id == probe_id
    assert result.probe_fingerprint == probe.probe_fingerprint
    assert result.probe_class is probe.probe_class
    assert result.stage is probe.stage
    assert result.actual_primary_reason is expected_reason
    assert result.expected_primary_reason is expected_reason
    assert result.observed_guard_id == expected_guard
    assert result.outcome_kind is expected_kind
    assert result.actual_status is (
        None
        if expected_kind is evaluation.ProbeOutcomeKind.RAISED_UNAVAILABLE
        else CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    )
    assert result.construction_evidence.observed_stage is probe.stage
    assert result.construction_evidence.validity_gate_passed is True
    assert _vector_symbols(
        result.construction_evidence.measured_invariant_vector
    ) == expected_vector
    assert result.diagnostics.observed_primary_mismatch_fields \
        == probe.expected_primary_mismatch_fields
    assert result.diagnostics.observed_advisory_or_dominated_mismatch_fields \
        == probe.advisory_or_dominated_mismatch_fields
    assert result.diagnostics.observed_guard_evaluations == probe.guard_evaluations
    assert result.diagnostics.observed_unreachable_guard_ids \
        == probe.unreachable_guard_ids
    assert result.diagnostics.observed_structured_future_scan_reached \
        is probe.structured_future_scan_reached
    assert result.diagnostics.authoritative_for_primary_result is False
    assert result.diagnostics.canonical_parser_reached is False
    assert result.diagnostics.ced_application_reached is False

    assert result.primary_reason_match is True
    assert result.guard_match is True
    assert result.diagnostic_match is True
    assert result.outcome_shape_match is True
    assert result.replay_match is True
    assert result.primary_outcome_digest == result.replay_outcome_digest
    assert result.replay_outcome_kind is expected_kind
    assert result.replay_primary_reason is expected_reason
    assert result.replay_status is result.actual_status
    assert result.source_unchanged is True
    assert result.sibling_unchanged is True
    assert result.production_unchanged is True
    assert result.source_runtime_fingerprint_before \
        == result.source_runtime_fingerprint_after
    assert result.sibling_runtime_fingerprint_before \
        == result.sibling_runtime_fingerprint_after
    assert result.production_runtime_fingerprint_before \
        == result.production_runtime_fingerprint_after
    assert result.sibling_control_capsule_id != result.source_capsule_id
    assert result.receipt_match is True
    assert result.resource_accounting_match is True
    assert result.successor_created is False
    assert result.successor_capsule_id is None
    assert result.successor_branch_id is None
    assert result.successor_state_v1_id is None
    assert result.unavailable_passed is True
    assert (
        result.negative_probe_dispatches,
        result.aggregate_provider_dispatches,
        result.live_calls,
        result.primary_model_calls,
        result.replay_model_calls,
        result.model_calls,
        result.tool_calls,
    ) == (0, 0, 0, 0, 0, 0, 0)
    assert (
        result.source_provider_dispatches_before,
        result.source_provider_dispatches_after,
        result.sibling_provider_dispatches_before,
        result.sibling_provider_dispatches_after,
        result.production_provider_dispatches_before,
        result.production_provider_dispatches_after,
    ) == (0, 0, 0, 0, 0, 0)

    if expected_kind is evaluation.ProbeOutcomeKind.RAISED_UNAVAILABLE:
        assert result.transition_id is None
        assert result.result_id is None
        assert result.receipt is None
        assert result.replay_transition_id is None
        assert result.replay_result_id is None
        assert result.replay_receipt_id is None
    else:
        assert result.transition_id is not None
        assert result.result_id is not None
        assert result.receipt is not None
        assert result.receipt.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
        assert result.receipt.unavailable_reason is expected_reason
        assert result.receipt.budget_before == result.receipt.budget_after
        assert not result.receipt.new_execution_usage.applied
        assert result.replay_transition_id == result.transition_id
        assert result.replay_result_id == result.result_id
        assert result.replay_receipt_id == result.receipt.receipt_id

    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_positive_reference_matrix_is_exactly_one_accepted_and_four_rejected() -> None:
    corpus = evaluation.FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1
    assert tuple(case.case_name for case in corpus.cases) == tuple(
        _POSITIVE_EXPECTATIONS
    )
    assert sum(
        case.reference.status is CanonicalTransitionStatus.APPLIED_ACCEPTED
        for case in corpus.cases
    ) == 1
    assert sum(
        case.reference.status
        is CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION
        for case in corpus.cases
    ) == 4
    assert all(case.reference.offline_fixture_dispatches == 1 for case in corpus.cases)


@pytest.mark.parametrize("case_name", tuple(_POSITIVE_EXPECTATIONS))
def test_each_v1_reference_case_is_evaluated_individually_with_full_parity(
    case_name: str,
) -> None:
    expected_status, expected_rejection, expected_move_id = _POSITIVE_EXPECTATIONS[
        case_name
    ]
    case = evaluation.FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        case_name
    )
    result = evaluation._evaluate_v1_parity_case(case)

    assert isinstance(result, evaluation.V1CanonicalSuccessorParityCaseResult)
    assert not isinstance(result, evaluation.V1CanonicalSuccessorParityEvaluationFailure)
    assert result.case_name == case_name
    assert result.case_id == case.case_id
    assert result.reference_id == case.reference.reference_id
    assert result.observation_id == case.observation.observation_id
    assert result.receipt.status is expected_status
    actual_rejection = (
        result.receipt.canonical_rejection_reason.value
        if result.receipt.canonical_rejection_reason is not None
        else None
    )
    assert actual_rejection == expected_rejection
    assert result.receipt.resulting_move_id == expected_move_id
    assert result.parity_passed is True
    assert result.status_parity is True
    assert result.canonical_rejection_reason_parity is True
    assert result.semantic_parity is True
    assert result.search_state_v1_parity is True
    assert result.move_id_parity is True
    assert result.canonical_processor_parity is True
    assert result.observation_identity_match is True
    assert result.receipt_match is True
    assert result.resource_accounting_match is True
    assert result.source_unchanged is True
    assert result.sibling_unchanged is True
    assert result.production_unchanged is True
    assert result.idempotent_replay is True
    assert result.value_v1_read_only_compatible is True
    assert result.successor_created is True
    assert result.primary_result_digest == result.replay_result_digest
    assert result.result_id == result.replay_result_id
    assert result.receipt.receipt_id == result.replay_receipt_id
    assert result.source_runtime_fingerprint_before \
        == result.source_runtime_fingerprint_after
    assert result.production_runtime_fingerprint_before \
        == result.production_runtime_fingerprint_after
    assert result.sibling_result_digest_before == result.sibling_result_digest_after
    assert result.sibling_probe_successor_created is False
    assert result.aggregate_provider_dispatches == 0
    assert result.live_calls == 0
    assert result.tool_calls == 0
    assert result.receipt.new_execution_usage.budget_delta.model_calls == 0
    assert result.receipt.new_execution_usage.budget_delta.tool_calls == 0
    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_thresholds_require_exact_one_of_one_and_four_of_four() -> None:
    thresholds = evaluation.FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_V2
    assert thresholds.thresholds_id == (
        "cedparitythresholdsv2_e241fe357d1a6c36e7e19addd0a421e0c55332bf16d999a2aa895fcdccf9e210"
    )
    assert (
        thresholds.cases_total,
        thresholds.supported_authoritative_cases,
        thresholds.accepted_reference_cases,
        thresholds.canonical_rejection_reference_cases,
        thresholds.orthogonal_negative_cases,
        thresholds.precedence_negative_cases,
        thresholds.required_supported_parity,
        thresholds.required_accepted_parity,
        thresholds.required_canonical_rejection_parity,
        thresholds.required_orthogonal_primary_classifications,
        thresholds.required_precedence_primary_classifications,
    ) == (23, 5, 1, 4, 11, 7, 5, 1, 4, 11, 7)
    assert thresholds.maximum_mismatch_or_failure_count == 0
    assert (
        thresholds.required_negative_probe_dispatches,
        thresholds.required_aggregate_provider_dispatches,
        thresholds.required_live_calls,
        thresholds.required_model_calls,
        thresholds.required_tool_calls,
    ) == (0, 0, 0, 0, 0)
    assert thresholds.depth == 1
    assert thresholds.recursive_successor is False

    green = _green_metrics()
    assert thresholds.supports(green)
    green_payload = green.model_dump(mode="python")
    for name in evaluation.CanonicalSuccessorParityMetricsV2.model_fields:
        if name != "schema_version" and getattr(green, name) == 0:
            payload = {**green_payload, name: 1}
            assert not thresholds.supports(
                evaluation.CanonicalSuccessorParityMetricsV2(**payload)
            ), name
    for name in (
        "cases_total",
        "supported_authoritative_cases",
        "accepted_reference_cases",
        "canonical_rejection_reference_cases",
        "orthogonal_negative_cases",
        "precedence_negative_cases",
        "accepted_parity",
        "canonical_rejection_parity",
        "orthogonal_primary_classifications",
        "precedence_primary_classifications",
        "historical_offline_fixture_dispatches",
    ):
        current = getattr(green, name)
        for replacement in (current - 1, current + 1):
            payload = {**green_payload, name: replacement}
            assert not thresholds.supports(
                evaluation.CanonicalSuccessorParityMetricsV2(**payload)
            ), (name, replacement)

    with pytest.raises(ValidationError):
        evaluation.CanonicalSuccessorParityMetricsV2(
            **{**green_payload, "accepted_parity": True}
        )
    with pytest.raises(ValidationError):
        evaluation.CanonicalSuccessorParityThresholdsV2(
            required_accepted_parity=0
        )
    with pytest.raises(ValidationError):
        evaluation.CanonicalSuccessorParityThresholdsV2.model_validate(
            {**thresholds.model_dump(mode="python"), "unexpected": 1}
        )


def test_ground_truth_firewall_rejects_names_values_and_serialized_carriers() -> None:
    safe_runtime_value = {"timeout_seconds": 31, "attempt": 1}

    def safe_operation(timeout_seconds: int = 30, *, retry_count: int = 0) -> object:
        return safe_runtime_value, timeout_seconds, retry_count

    def banned_positional_name(expected_reason: str = "ordinary") -> str:
        return expected_reason

    def banned_keyword_name(*, expected_guard_id: str = "ordinary") -> str:
        return expected_guard_id

    probe_truth = _probe("p8v2-o07-wrong-root-question")
    nested_truth = {"opaque": ["A8", {"value": "root_context_mismatch"}]}
    wrapped_truth = SimpleNamespace(
        opaque={"nested": [CanonicalTransitionStatus.APPLIED_ACCEPTED]}
    )

    def capture(value: object):
        def operation() -> object:
            return value

        return operation

    def enum_default(
        value: object = SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
    ) -> object:
        return value

    def serialized_default(
        value: object = SimpleNamespace(expected_result={"opaque": ["A8"]}),
    ) -> object:
        return value

    def outcome_default(
        value: object = evaluation.ProbeOutcomeKind.RETURNED_UNAVAILABLE,
    ) -> object:
        return value

    def status_default(
        value: object = CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
    ) -> object:
        return value

    def attributed_operation() -> None:
        return None

    attributed_operation.expected_result = {"opaque": ["A8"]}

    class SlottedCarrier:
        __slots__ = ("expected_reason",)

        def __init__(self) -> None:
            self.expected_reason = "root_context_mismatch"

    def serialized_generator():
        yield "A8"

    hidden_helper_truth = {"opaque": ["A8"]}

    def hidden_helper() -> object:
        return hidden_helper_truth

    def indirect_operation() -> object:
        return hidden_helper()

    class InspectUnsupported:
        def __call__(self) -> None:
            return None

    assert evaluation._ground_truth_firewall_passed(safe_operation) is True
    assert evaluation._ground_truth_firewall_passed(banned_positional_name) is False
    assert evaluation._ground_truth_firewall_passed(banned_keyword_name) is False
    assert evaluation._ground_truth_firewall_passed(capture(probe_truth)) is False
    assert evaluation._ground_truth_firewall_passed(capture(nested_truth)) is False
    assert evaluation._ground_truth_firewall_passed(capture(wrapped_truth)) is False
    assert evaluation._ground_truth_firewall_passed(enum_default) is False
    assert evaluation._ground_truth_firewall_passed(serialized_default) is False
    assert evaluation._ground_truth_firewall_passed(outcome_default) is False
    assert evaluation._ground_truth_firewall_passed(status_default) is False
    assert evaluation._ground_truth_firewall_passed(attributed_operation) is False
    assert evaluation._ground_truth_firewall_passed(_operation_using_global_truth) is False
    assert evaluation._ground_truth_firewall_passed(
        capture(SlottedCarrier())
    ) is False
    assert evaluation._ground_truth_firewall_passed(
        capture(serialized_generator())
    ) is False
    assert evaluation._ground_truth_firewall_passed(indirect_operation) is False
    assert evaluation._ground_truth_firewall_passed(InspectUnsupported()) is False


def test_validity_gate_refuses_unexpected_vector_before_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _probe("p8v2-o02-illegal-action-capability")
    execution = evaluation._build_probe_execution_v2(probe.probe_id)
    calls = {"count": 0}

    def sentinel_operation() -> None:
        calls["count"] += 1

    assert execution.candidate_snapshot.budget_status != "0" * 64
    changed_candidate = execution.candidate_snapshot.model_copy(
        update={"budget_status": "0" * 64}
    )
    invalid_execution = replace(
        execution,
        operation=sentinel_operation,
        candidate_snapshot=changed_candidate,
    )
    monkeypatch.setattr(
        evaluation,
        "_build_probe_execution_v2",
        lambda probe_id: invalid_execution,
    )

    failure = evaluation._evaluate_unavailable_probe_v2_strict(probe)
    assert isinstance(failure, evaluation.CanonicalSuccessorProbeEvaluationFailureV2)
    assert failure.failure_code is evaluation.ProbeEvaluationFailureCode.INVALID_PROBE_CONSTRUCTION
    assert failure.operation_invoked is False
    assert failure.construction_evidence is not None
    assert failure.construction_evidence.measured_invariant_vector \
        != probe.invariant_vector
    assert failure.construction_evidence.validity_gate_passed is False
    assert failure.unavailable_passed is False
    assert calls["count"] == 0
    assert (
        failure.negative_probe_dispatches,
        failure.aggregate_provider_dispatches,
        failure.live_calls,
        failure.model_calls,
        failure.tool_calls,
    ) == (0, 0, 0, 0, 0)


def test_validity_gate_refuses_wrong_invocation_stage_before_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _probe("p8v2-o02-illegal-action-capability")
    execution = evaluation._build_probe_execution_v2(probe.probe_id)
    calls = {"count": 0}

    def sentinel_operation() -> None:
        calls["count"] += 1

    invalid_execution = replace(
        execution,
        invocation_stage=ProbeStage.APPLY,
        operation=sentinel_operation,
    )
    monkeypatch.setattr(
        evaluation,
        "_build_probe_execution_v2",
        lambda probe_id: invalid_execution,
    )
    failure = evaluation._evaluate_unavailable_probe_v2_strict(probe)
    assert isinstance(failure, evaluation.CanonicalSuccessorProbeEvaluationFailureV2)
    assert failure.failure_code is evaluation.ProbeEvaluationFailureCode.INVALID_PROBE_CONSTRUCTION
    assert failure.operation_invoked is False
    assert failure.construction_evidence is not None
    assert failure.construction_evidence.observed_stage is ProbeStage.APPLY
    assert failure.construction_evidence.validity_gate_passed is False
    assert calls["count"] == 0


def test_firewall_gate_refuses_serialized_truth_before_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _probe("p8v2-o02-illegal-action-capability")
    execution = evaluation._build_probe_execution_v2(probe.probe_id)
    calls = {"count": 0}
    serialized_truth = {"opaque": ["P8", "illegal_action"]}

    def blocked_operation() -> object:
        calls["count"] += 1
        return serialized_truth

    invalid_execution = replace(execution, operation=blocked_operation)
    monkeypatch.setattr(
        evaluation,
        "_build_probe_execution_v2",
        lambda probe_id: invalid_execution,
    )
    failure = evaluation._evaluate_unavailable_probe_v2_strict(probe)
    assert isinstance(failure, evaluation.CanonicalSuccessorProbeEvaluationFailureV2)
    assert failure.failure_code \
        is evaluation.ProbeEvaluationFailureCode.GROUND_TRUTH_FIREWALL_FAILED
    assert failure.operation_invoked is False
    assert failure.construction_evidence is not None
    assert failure.construction_evidence.ground_truth_firewall_passed is False
    assert failure.construction_evidence.validity_gate_passed is False
    assert calls["count"] == 0


@pytest.mark.parametrize("probe_id", tuple(_ADVISORY_PRECEDENCE))
def test_advisory_diagnostics_never_override_first_canonical_guard(
    probe_id: str,
) -> None:
    expected_guard, expected_primary, expected_advisory = _ADVISORY_PRECEDENCE[
        probe_id
    ]
    expected_reason = _PROBE_EXPECTATIONS[probe_id][2]
    result = evaluation._evaluate_unavailable_probe_v2(_probe(probe_id))
    assert isinstance(result, evaluation.CanonicalSuccessorUnavailableCaseResultV2)
    assert result.actual_primary_reason is expected_reason
    assert result.observed_guard_id == expected_guard
    assert result.diagnostics.observed_primary_mismatch_fields == expected_primary
    assert result.diagnostics.observed_advisory_or_dominated_mismatch_fields \
        == expected_advisory
    assert result.diagnostics.authoritative_for_primary_result is False
    assert result.primary_reason_match is True
    assert result.guard_match is True


def test_evidence_ids_are_deterministic_and_tampering_is_refused() -> None:
    probe = _probe("p8v2-o08-wrong-exact-model")
    first_execution = evaluation._build_probe_execution_v2(probe.probe_id)
    second_execution = evaluation._build_probe_execution_v2(probe.probe_id)
    first_construction = evaluation._construction_evidence_v2(
        probe, first_execution
    )
    second_construction = evaluation._construction_evidence_v2(
        probe, second_execution
    )
    assert first_construction == second_construction
    assert first_construction.construction_evidence_id \
        == second_construction.construction_evidence_id

    first_result = evaluation._evaluate_unavailable_probe_v2(probe)
    second_result = evaluation._evaluate_unavailable_probe_v2(probe)
    assert isinstance(first_result, evaluation.CanonicalSuccessorUnavailableCaseResultV2)
    assert isinstance(second_result, evaluation.CanonicalSuccessorUnavailableCaseResultV2)
    assert first_result == second_result
    assert first_result.case_result_id == second_result.case_result_id
    assert first_result.diagnostics.diagnostic_evidence_id \
        == second_result.diagnostics.diagnostic_evidence_id

    construction_payload = first_construction.model_dump(mode="json")
    construction_payload["construction_evidence_id"] = "f" * 64
    with pytest.raises((ValidationError, ContractValidationError)):
        evaluation.CanonicalSuccessorProbeConstructionEvidenceV2.model_validate(
            construction_payload
        )

    diagnostic_payload = first_result.diagnostics.model_dump(mode="json")
    diagnostic_payload["diagnostic_evidence_id"] = "f" * 64
    with pytest.raises((ValidationError, ContractValidationError)):
        evaluation.CanonicalSuccessorCompatibilityDiagnosticEvidenceV1.model_validate(
            diagnostic_payload
        )

    result_payload = first_result.model_dump(mode="json")
    result_payload["case_result_id"] = "f" * 64
    with pytest.raises((ValidationError, ContractValidationError)):
        evaluation.CanonicalSuccessorUnavailableCaseResultV2.model_validate(
            result_payload
        )
    result_payload = first_result.model_dump(mode="json")
    result_payload.update(case_result_id=None, primary_reason_match=False)
    with pytest.raises((ValidationError, ContractValidationError)):
        evaluation.CanonicalSuccessorUnavailableCaseResultV2.model_validate(
            result_payload
        )
    with pytest.raises(ValidationError):
        evaluation.CanonicalSuccessorUnavailableCaseResultV2.model_validate(
            {**first_result.model_dump(mode="json"), "unexpected": True}
        )


def test_core_and_predecessor_locks_are_exact_and_clean() -> None:
    lock = evaluation.FROZEN_CANONICAL_SUCCESSOR_CORE_BLOB_LOCK_V2
    # Re-pinned once, deliberately. backend/dialogues/ced.py gained
    # rule_on_round_objections_v1, a non-governing pass that rules on a round's
    # objections while the dialogue can still read them; every governing path -
    # run_objection_verification, claim state, the release seam - is unchanged.
    # The previous lock was
    # cedcorebloblockv2_192c688821bfeca9914f23a06c9df1a7392997a4b09c3e7d04c434bf5695f6a5
    # and this line moving without that being the intended change is a defect.
    # Re-pinned a second time to gate the pass behind
    # mid_round_objection_rulings_v1, so a control arm can switch it off on
    # identical code instead of an older build.
    # Re-pinned a third time for the three-attempt rescue: the same seat is
    # asked again before the question passes to another, because a first
    # failure may be misunderstanding and a second is not.
    assert lock.lock_id == (
        "cedcorebloblockv2_234f0c5fc23941772da222fc0ba544a221b12a3f4e6ae3353c9125cf44f50675"
    )
    assert evaluation.SEALED_PHASE8_ARTIFACT_ID == (
        "cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0"
    )
    assert evaluation.SEALED_PHASE8_ARTIFACT_SHA256 == (
        "00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea"
    )
    assert evaluation.SEALED_PHASE8_ARTIFACT_COMMIT == (
        "07ec5ab14cd1599ffd6c8c4b6442d56d51129f11"
    )
    assert evaluation._actual_core_lock_mismatches() == 0
    assert evaluation._actual_predecessor_lock_mismatches() == 0


def test_replay_lock_is_frozen_deterministic_and_tamper_refusing() -> None:
    artifact_id = "cedparityartifactv2_contract"
    digest = "a" * 64
    replay_lock = evaluation.CanonicalSuccessorParityReplayLockV2(
        authoritative_artifact_id=artifact_id,
        replay_artifact_id=artifact_id,
        authoritative_sha256=digest,
        replay_sha256=digest,
    )
    assert replay_lock.authoritative_supported_order \
        == evaluation.FROZEN_SUPPORTED_CASE_ORDER_V2
    assert replay_lock.authoritative_orthogonal_order \
        == evaluation.FROZEN_ORTHOGONAL_PROBE_ORDER_V2
    assert replay_lock.authoritative_precedence_order \
        == evaluation.FROZEN_PRECEDENCE_PROBE_ORDER_V2
    assert replay_lock.replay_supported_order \
        == evaluation.FROZEN_REPLAY_SUPPORTED_CASE_ORDER_V2
    assert replay_lock.replay_orthogonal_order \
        == evaluation.FROZEN_REPLAY_ORTHOGONAL_PROBE_ORDER_V2
    assert replay_lock.replay_precedence_order \
        == evaluation.FROZEN_REPLAY_PRECEDENCE_PROBE_ORDER_V2
    assert replay_lock.replay_supported_order \
        == tuple(reversed(replay_lock.authoritative_supported_order))
    assert replay_lock.replay_orthogonal_order \
        == tuple(reversed(replay_lock.authoritative_orthogonal_order))
    assert replay_lock.replay_precedence_order \
        == tuple(reversed(replay_lock.authoritative_precedence_order))
    assert replay_lock.semantic_equality is True
    assert replay_lock.artifact_id_equality is True
    assert replay_lock.byte_identity is True
    assert replay_lock.replay_lock_id
    assert type(replay_lock).model_validate_json(replay_lock.model_dump_json()) \
        == replay_lock

    rendered = evaluation.render_canonical_successor_parity_replay_lock_v2(
        replay_lock
    )
    assert rendered.endswith("\n")
    assert evaluation.replay_canonical_successor_parity_replay_lock_v2(
        rendered
    ) == replay_lock
    with pytest.raises(ContractValidationError):
        evaluation.replay_canonical_successor_parity_replay_lock_v2(
            rendered.removesuffix("\n") + " \n"
        )

    altered = replay_lock.model_dump(mode="python")
    altered.update(
        replay_lock_id=None,
        authoritative_supported_order=("x",),
        authoritative_orthogonal_order=("y",),
        authoritative_precedence_order=("z",),
        replay_supported_order=("x",),
        replay_orthogonal_order=("y",),
        replay_precedence_order=("z",),
    )
    with pytest.raises((ValidationError, ContractValidationError)):
        evaluation.CanonicalSuccessorParityReplayLockV2.model_validate(altered)

    stale_id = replay_lock.model_dump(mode="python")
    stale_id["replay_lock_id"] = "cedparityreplaylockv2_stale"
    with pytest.raises((ValidationError, ContractValidationError)):
        evaluation.CanonicalSuccessorParityReplayLockV2.model_validate(stale_id)
    with pytest.raises(ValidationError):
        evaluation.CanonicalSuccessorParityReplayLockV2.model_validate(
            {**replay_lock.model_dump(mode="python"), "unexpected": True}
        )


@pytest.mark.parametrize("blank_id", ("", "   "))
def test_replay_lock_rejects_blank_artifact_ids(blank_id: str) -> None:
    with pytest.raises((ValidationError, ContractValidationError)):
        evaluation.CanonicalSuccessorParityReplayLockV2(
            authoritative_artifact_id=blank_id,
            replay_artifact_id=blank_id,
            authoritative_sha256="a" * 64,
            replay_sha256="a" * 64,
        )


def test_write_once_bytes_are_idempotent_and_conflict_refusing(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "phase8-v2-pre-result-contract.json"
    payload = b'{"phase8":"v2-pre-result-contract"}\n'
    digest = hashlib.sha256(payload).hexdigest()
    with pytest.raises(ContractValidationError):
        evaluation.write_once_canonical_bytes_v2(destination, b"")
    assert not destination.exists()
    assert evaluation.write_once_canonical_bytes_v2(destination, payload) == digest
    assert evaluation.write_once_canonical_bytes_v2(str(destination), payload) == digest
    assert destination.read_bytes() == payload
    with pytest.raises(ContractValidationError):
        evaluation.write_once_canonical_bytes_v2(
            destination, b'{"phase8":"different"}\n'
        )
    assert destination.read_bytes() == payload
