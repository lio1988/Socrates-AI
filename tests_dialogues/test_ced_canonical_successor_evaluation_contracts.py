"""Pre-result contract locks for the Phase 8 v1 aggregate evaluator.

These tests never call either aggregate builder.  They freeze only schemas,
case membership, thresholds, the independent reverse-order replay procedure,
and conflict-safe publication behavior before any authoritative result exists.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

import pytest
from pydantic import ValidationError

import backend.dialogues.ced_canonical_successor_evaluation as evaluation
from backend.dialogues.ced_canonical_successor_cases_v1 import (
    CANONICAL_SUCCESSOR_CORPUS_VERSION,
    CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION,
    FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1,
)
from backend.dialogues.ced_canonical_successor_contracts import (
    CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION,
    CANONICAL_SUCCESSOR_ENV_ID,
    CANONICAL_TASK_SEMANTIC_IDENTITY_SCHEMA_VERSION,
    CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION,
    CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION,
    PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION,
    RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION,
    SuccessorUnavailableReason,
)
from backend.dialogues.ced_canonical_successor_evaluation import (
    CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION,
    CANONICAL_SUCCESSOR_PARITY_CASE_RESULT_VERSION,
    CANONICAL_SUCCESSOR_PARITY_CASE_SET_VERSION,
    CANONICAL_SUCCESSOR_PARITY_EVALUATION_FAILURE_VERSION,
    CANONICAL_SUCCESSOR_PARITY_HARNESS_ID,
    CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION,
    CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION,
    CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION,
    CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION,
    CANONICAL_SUCCESSOR_UNAVAILABLE_PROBE_VERSION,
    FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET,
    FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS,
    FROZEN_REPLAY_SUPPORTED_CASE_ORDER,
    FROZEN_REPLAY_UNAVAILABLE_CASE_ORDER,
    FROZEN_SUPPORTED_CASE_ORDER,
    FROZEN_UNAVAILABLE_CASE_ORDER,
    FROZEN_UNAVAILABLE_PROBES,
    CanonicalSuccessorParityArtifact,
    CanonicalSuccessorParityCaseResult,
    CanonicalSuccessorParityEvaluationFailure,
    CanonicalSuccessorParityMetrics,
    CanonicalSuccessorParityReplayLock,
    CanonicalSuccessorUnavailableCaseResult,
    ParityEvaluationFailureCode,
    ParityEvaluationFailureStage,
    UnavailableProbeStage,
    build_canonical_successor_parity_artifact,
    build_canonical_successor_parity_replay_artifact,
    publish_canonical_successor_parity_replay_lock_once,
    render_canonical_successor_parity_replay_lock,
    replay_canonical_successor_parity_replay_lock,
    write_once_canonical_bytes,
)
from backend.dialogues.ced_canonical_successor_recording_contracts import (
    CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION,
    CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID,
)
from backend.dialogues.socrates_zero.contracts import ContractValidationError


_EXPECTED_NEGATIVE_MATRIX = {
    "budget-exhausted": (
        UnavailableProbeStage.PREPARE,
        SuccessorUnavailableReason.BUDGET_EXHAUSTED,
    ),
    "caller-rebinding": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
    ),
    "future-label-forbidden": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN,
    ),
    "illegal-action": (
        UnavailableProbeStage.PREPARE,
        SuccessorUnavailableReason.ILLEGAL_ACTION,
    ),
    "invalid-observation": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.INVALID_OBSERVATION,
    ),
    "invalid-root": (
        UnavailableProbeStage.CAPTURE,
        SuccessorUnavailableReason.INVALID_ROOT,
    ),
    "missing-observation": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.MISSING_OBSERVATION,
    ),
    "tampered-observation-identity": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
    ),
    "unsupported-action-family": (
        UnavailableProbeStage.PREPARE,
        SuccessorUnavailableReason.UNSUPPORTED_ACTION_FAMILY,
    ),
    "wrong-configuration": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.OBSERVATION_CONFIG_MISMATCH,
    ),
    "wrong-model": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.OBSERVATION_MODEL_MISMATCH,
    ),
    "wrong-provider": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.OBSERVATION_PROVIDER_MISMATCH,
    ),
    "wrong-root-context": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
    ),
    "wrong-task": (
        UnavailableProbeStage.APPLY,
        SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH,
    ),
}


def _green_metrics(**updates: int) -> CanonicalSuccessorParityMetrics:
    values = {
        name: 0
        for name in CanonicalSuccessorParityMetrics.model_fields
        if name != "schema_version"
    }
    values.update(
        cases_total=19,
        supported_authoritative_cases=5,
        accepted_reference_cases=1,
        canonical_rejection_reference_cases=4,
        unavailable_negative_cases=14,
        accepted_parity=1,
        canonical_rejection_parity=4,
        unavailable_passed=14,
        historical_offline_fixture_dispatches=5,
    )
    values.update(updates)
    return CanonicalSuccessorParityMetrics(**values)


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


def _passing_unavailable_result(probe) -> CanonicalSuccessorUnavailableCaseResult:
    source_capsule_id = "cedcapsule_contract-negative"
    source_branch_id = evaluation._root_branch_id(source_capsule_id)
    source_fingerprint = "a" * 64
    production_capsule_id = "cedcapsule_contract-control"
    production_fingerprint = "b" * 64
    return CanonicalSuccessorUnavailableCaseResult(
        probe_id=probe.probe_id or "",
        case_name=probe.case_name,
        stage=probe.stage,
        expected_reason=probe.expected_reason,
        actual_reason=probe.expected_reason,
        replay_reason=probe.expected_reason,
        primary_outcome_digest="c" * 64,
        replay_outcome_digest="c" * 64,
        source_capsule_id=source_capsule_id,
        source_branch_id=source_branch_id,
        source_state_v1_id="szstatev1_contract-negative",
        source_isolation_evidence_digest=evaluation._isolation_evidence_digest(
            capsule_id=source_capsule_id,
            branch_id=source_branch_id,
            state_v1_id="szstatev1_contract-negative",
            runtime_before=source_fingerprint,
            runtime_after=source_fingerprint,
            dispatches_before=0,
            dispatches_after=0,
        ),
        source_runtime_fingerprint_before=source_fingerprint,
        source_runtime_fingerprint_after=source_fingerprint,
        source_provider_dispatches_before=0,
        source_provider_dispatches_after=0,
        production_control_capsule_id=production_capsule_id,
        production_isolation_evidence_digest=evaluation._isolation_evidence_digest(
            capsule_id=production_capsule_id,
            branch_id=None,
            state_v1_id=None,
            runtime_before=production_fingerprint,
            runtime_after=production_fingerprint,
            dispatches_before=0,
            dispatches_after=0,
        ),
        production_runtime_fingerprint_before=production_fingerprint,
        production_runtime_fingerprint_after=production_fingerprint,
        production_provider_dispatches_before=0,
        production_provider_dispatches_after=0,
        aggregate_provider_dispatches=0,
        live_calls=0,
        tool_calls=0,
        reason_match=True,
        replay_match=True,
        source_unchanged=True,
        production_unchanged=True,
        receipt_match=True,
        resource_accounting_match=True,
        successor_created=False,
    )


def test_evaluator_versions_change_only_the_repaired_lineages() -> None:
    assert CANONICAL_SUCCESSOR_PARITY_HARNESS_ID \
        == "ced-canonical-successor-parity-harness/v1"
    assert CANONICAL_SUCCESSOR_PARITY_CASE_RESULT_VERSION \
        == "ced-canonical-successor-parity-case-result/v1"
    assert CANONICAL_SUCCESSOR_PARITY_EVALUATION_FAILURE_VERSION \
        == "ced-canonical-successor-parity-evaluation-failure/v1"
    assert CANONICAL_SUCCESSOR_UNAVAILABLE_PROBE_VERSION \
        == "ced-canonical-successor-unavailable-probe/v1"
    assert CANONICAL_SUCCESSOR_UNAVAILABLE_CASE_RESULT_VERSION \
        == "ced-canonical-successor-unavailable-case-result/v1"
    assert CANONICAL_SUCCESSOR_PARITY_METRICS_VERSION \
        == "ced-canonical-successor-parity-metrics/v1"
    assert CANONICAL_SUCCESSOR_PARITY_CASE_SET_VERSION \
        == "ced-canonical-successor-parity-case-set/v1"
    assert CANONICAL_SUCCESSOR_PARITY_THRESHOLDS_VERSION \
        == "ced-canonical-successor-parity-thresholds/v1"
    assert CANONICAL_SUCCESSOR_PARITY_ARTIFACT_VERSION \
        == "ced-canonical-successor-parity-artifact/v1"
    assert CANONICAL_SUCCESSOR_PARITY_REPLAY_LOCK_VERSION \
        == "ced-canonical-successor-parity-replay-lock/v1"

    assert CANONICAL_SUCCESSOR_CORPUS_VERSION \
        == "ced-canonical-successor-parity-corpus/v1"
    assert CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION \
        == "ced-canonical-successor-reference/v1"
    assert CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID \
        == "ced-canonical-successor-recording/v0"
    assert CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION \
        == "ced-canonical-successor-capture-manifest/v0"
    assert CANONICAL_TASK_SEMANTIC_IDENTITY_SCHEMA_VERSION \
        == "ced-canonical-task-semantic-identity/v0"
    assert RECORDED_CANONICAL_OBSERVATION_SCHEMA_VERSION \
        == "ced-recorded-observation/v1"

    # Environment/capsule/pending/result/receipt semantics were not arbitrarily
    # re-versioned by the repaired corpus/evaluator lineages.
    assert CANONICAL_SUCCESSOR_ENV_ID == "ced-canonical-successor-env/v0"
    assert CANONICAL_BRANCH_CAPSULE_SCHEMA_VERSION \
        == "ced-canonical-branch-capsule/v0"
    assert PENDING_CANONICAL_TRANSITION_SCHEMA_VERSION \
        == "ced-pending-canonical-transition/v0"
    assert CANONICAL_TRANSITION_RESULT_SCHEMA_VERSION \
        == "ced-canonical-transition-result/v0"
    assert CANONICAL_TRANSITION_RECEIPT_SCHEMA_VERSION \
        == "ced-canonical-transition-receipt/v0"


def test_case_set_and_failure_taxonomy_are_exactly_frozen() -> None:
    case_set = FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1
    assert case_set.case_set_id == (
        "cedparitycaseset_4c6b248fe69d4714076f7cbd8f5fe06ed54c956e5ade9727c65a589b474983e3"
    )
    assert case_set.case_set_fingerprint \
        == "4c6b248fe69d4714076f7cbd8f5fe06ed54c956e5ade9727c65a589b474983e3"
    assert set(case_set.supported_case_ids) == {
        case.case_id for case in corpus.cases
    }
    assert set(case_set.reference_ids) == {
        case.reference.reference_id for case in corpus.cases
    }
    assert len(case_set.supported_case_ids) == len(case_set.reference_ids) == 5
    assert len(case_set.unavailable_probes) == 14

    actual = {
        probe.case_name: (probe.stage, probe.expected_reason)
        for probe in FROZEN_UNAVAILABLE_PROBES
    }
    assert actual == _EXPECTED_NEGATIVE_MATRIX
    assert FROZEN_UNAVAILABLE_CASE_ORDER == tuple(sorted(_EXPECTED_NEGATIVE_MATRIX))
    assert SuccessorUnavailableReason.CANONICAL_PROCESSING_REJECTED not in {
        probe.expected_reason for probe in FROZEN_UNAVAILABLE_PROBES
    }
    assert SuccessorUnavailableReason.SUCCESSOR_UNAVAILABLE not in {
        probe.expected_reason for probe in FROZEN_UNAVAILABLE_PROBES
    }

    round_trip = type(case_set).model_validate_json(case_set.model_dump_json())
    assert round_trip == case_set
    tampered_case_set = case_set.model_dump(mode="python")
    tampered_case_set.update(
        case_set_id=None,
        case_set_fingerprint=None,
        supported_case_ids=("cedobscasev1_wrong",) + case_set.supported_case_ids[1:],
    )
    with pytest.raises((ValidationError, ContractValidationError)):
        type(case_set).model_validate(tampered_case_set)
    with pytest.raises(ValidationError):
        type(FROZEN_UNAVAILABLE_PROBES[0]).model_validate(
            {
                **FROZEN_UNAVAILABLE_PROBES[0].model_dump(mode="python"),
                "unexpected": True,
            }
        )


def test_thresholds_are_exact_and_every_reported_failure_falsifies() -> None:
    thresholds = FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS
    assert thresholds.thresholds_id == (
        "cedparitythresholds_0760039f86e67235bb3d955e0db7a1b8ef0330cb15c518305646cfe68a629efd"
    )
    assert thresholds.cases_total == 19
    assert thresholds.supported_authoritative_cases == 5
    assert thresholds.accepted_reference_cases == 1
    assert thresholds.canonical_rejection_reference_cases == 4
    assert thresholds.unavailable_negative_cases == 14
    assert thresholds.required_supported_parity_numerator == 5
    assert thresholds.required_supported_parity_denominator == 5
    assert thresholds.required_unavailable_passed == 14
    assert thresholds.maximum_evaluation_failures == 0
    assert thresholds.depth == 1
    assert thresholds.recursive_successor is False
    assert thresholds.supports(_green_metrics())

    zero_gated = (
        "evaluation_failures",
        "unavailable_reason_mismatches",
        "status_mismatches",
        "canonical_rejection_reason_mismatches",
        "semantic_mismatches",
        "accepted_move_id_mismatches",
        "task_log_mismatches",
        "commitment_mismatches",
        "phase_role_mismatches",
        "search_state_v1_mismatches",
        "canonical_processor_mismatches",
        "observation_identity_mismatches",
        "context_binding_failures",
        "task_binding_failures",
        "provider_binding_failures",
        "model_binding_failures",
        "configuration_binding_failures",
        "source_isolation_failures",
        "sibling_isolation_failures",
        "production_mutations",
        "receipt_mismatches",
        "resource_accounting_mismatches",
        "value_v1_compatibility_mismatches",
        "idempotence_failures",
        "fabricated_observations",
        "future_label_violations",
        "aggregate_provider_dispatches",
        "live_calls",
        "tool_calls",
    )
    for name in zero_gated:
        assert not thresholds.supports(_green_metrics(**{name: 1})), name
    assert not thresholds.supports(_green_metrics(accepted_parity=0))
    assert not thresholds.supports(_green_metrics(canonical_rejection_parity=3))
    assert not thresholds.supports(_green_metrics(unavailable_passed=13))
    assert not thresholds.supports(
        _green_metrics(historical_offline_fixture_dispatches=4)
    )


def test_artifact_and_result_schemas_freeze_auditable_evidence() -> None:
    artifact_properties = CanonicalSuccessorParityArtifact.model_json_schema()[
        "properties"
    ]
    assert {
        "environment_id",
        "branch_capsule_id",
        "pending_transition_id",
        "recording_contract_id",
        "capture_manifest_schema_id",
        "capture_manifest_id",
        "task_semantic_identity_id",
        "recorded_observation_id",
        "reference_schema_id",
        "transition_result_id",
        "transition_receipt_id",
        "parity_definition_id",
        "corpus_id",
        "corpus_canonical_sha256",
        "case_set_id",
        "case_set_fingerprint",
        "thresholds_id",
        "case_set",
        "thresholds",
        "metrics",
        "hypothesis_status",
    } <= set(artifact_properties)
    assert artifact_properties["depth"]["const"] == 1
    assert artifact_properties["recursive_successor"]["const"] is False
    assert artifact_properties["production_authority"]["const"] == "none"

    parity_fields = CanonicalSuccessorParityCaseResult.model_fields
    unavailable_fields = CanonicalSuccessorUnavailableCaseResult.model_fields
    for fields in (parity_fields, unavailable_fields):
        assert {
            "source_runtime_fingerprint_before",
            "source_runtime_fingerprint_after",
            "source_isolation_evidence_digest",
            "production_runtime_fingerprint_before",
            "production_runtime_fingerprint_after",
            "production_isolation_evidence_digest",
            "aggregate_provider_dispatches",
            "live_calls",
            "tool_calls",
        } <= set(fields)
    assert {
        "sibling_probe_observation_id",
        "sibling_probe_status",
        "sibling_probe_unavailable_reason",
        "sibling_probe_outcome_digest",
        "sibling_probe_successor_created",
        "sibling_isolation_evidence_digest",
        "replay_result_id",
        "replay_receipt_id",
    } <= set(parity_fields)
    assert {
        "actual_status",
        "actual_reason",
        "replay_status",
        "replay_reason",
        "successor_created",
    } <= set(unavailable_fields)

    property_names = _schema_property_names(
        CanonicalSuccessorParityArtifact.model_json_schema()
    )
    assert "created_at" not in property_names
    assert "updated_at" not in property_names
    assert "timestamp" not in property_names
    assert "latency" not in property_names


def test_supported_evaluation_failure_is_deterministic_and_never_a_pass() -> None:
    case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-scripted-mock"
    )
    failure = CanonicalSuccessorParityEvaluationFailure(
        case_id=case.case_id or "",
        case_name=case.case_name,
        fixture_role=case.fixture_role,
        reference_id=case.reference.reference_id or "",
        capture_receipt_id=case.reference.capture_receipt_id,
        observation_id=case.observation.observation_id or "",
        stage=ParityEvaluationFailureStage.ROOT_RECONSTRUCTION,
        failure_code=ParityEvaluationFailureCode.ROOT_LINEAGE_MISMATCH,
        exception_type="ContractValidationError",
    )
    assert failure.parity_passed is False
    assert failure.failure_evidence_digest
    assert failure.case_result_id
    assert failure.source_unchanged is False
    assert failure.production_unchanged is False
    assert type(failure).model_validate_json(failure.model_dump_json()) == failure
    assert not FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS.supports(
        _green_metrics(evaluation_failures=1)
    )

    metrics = evaluation._calculate_metrics(
        (failure,),
        tuple(
            _passing_unavailable_result(probe)
            for probe in FROZEN_UNAVAILABLE_PROBES
        ),
    )
    assert metrics.evaluation_failures == 1
    for name in (
        "status_mismatches",
        "canonical_rejection_reason_mismatches",
        "semantic_mismatches",
        "accepted_move_id_mismatches",
        "task_log_mismatches",
        "commitment_mismatches",
        "phase_role_mismatches",
        "search_state_v1_mismatches",
        "canonical_processor_mismatches",
        "observation_identity_mismatches",
        "source_isolation_failures",
        "sibling_isolation_failures",
        "production_mutations",
        "receipt_mismatches",
        "resource_accounting_mismatches",
        "value_v1_compatibility_mismatches",
        "idempotence_failures",
    ):
        assert getattr(metrics, name) == 1, name
    assert metrics.accepted_parity == 0
    assert metrics.unavailable_passed == 14
    assert metrics.aggregate_provider_dispatches == 0
    assert not FROZEN_CANONICAL_SUCCESSOR_PARITY_THRESHOLDS.supports(metrics)

    tampered = failure.model_dump(mode="python")
    tampered["failure_evidence_digest"] = "f" * 64
    tampered["case_result_id"] = None
    with pytest.raises((ValidationError, ContractValidationError)):
        CanonicalSuccessorParityEvaluationFailure.model_validate(tampered)
    with pytest.raises((ValidationError, ContractValidationError)):
        CanonicalSuccessorParityEvaluationFailure(
            case_id=case.case_id or "",
            case_name=case.case_name,
            fixture_role=case.fixture_role,
            reference_id=case.reference.reference_id or "",
            capture_receipt_id=case.reference.capture_receipt_id,
            observation_id=case.observation.observation_id or "",
            stage=ParityEvaluationFailureStage.OBSERVATION_APPLICATION,
            failure_code=ParityEvaluationFailureCode.ROOT_LINEAGE_MISMATCH,
            exception_type="ContractValidationError",
        )

    artifact_schema = CanonicalSuccessorParityArtifact.model_json_schema()
    assert "CanonicalSuccessorParityEvaluationFailure" in str(artifact_schema)


def test_reverse_order_replay_and_lock_contract_are_predeclared() -> None:
    assert FROZEN_SUPPORTED_CASE_ORDER == tuple(
        case.case_name
        for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases
    )
    assert FROZEN_REPLAY_SUPPORTED_CASE_ORDER \
        == tuple(reversed(FROZEN_SUPPORTED_CASE_ORDER))
    assert FROZEN_REPLAY_UNAVAILABLE_CASE_ORDER \
        == tuple(reversed(FROZEN_UNAVAILABLE_CASE_ORDER))
    assert not inspect.signature(build_canonical_successor_parity_artifact).parameters
    assert not inspect.signature(
        build_canonical_successor_parity_replay_artifact
    ).parameters
    assert "FROZEN_SUPPORTED_CASE_ORDER" in inspect.getsource(
        build_canonical_successor_parity_artifact
    )
    assert "FROZEN_REPLAY_SUPPORTED_CASE_ORDER" in inspect.getsource(
        build_canonical_successor_parity_replay_artifact
    )

    publish_signature = inspect.signature(
        publish_canonical_successor_parity_replay_lock_once
    )
    assert tuple(publish_signature.parameters) == (
        "destination",
        "authoritative",
        "replay",
    )
    publish_source = inspect.getsource(
        publish_canonical_successor_parity_replay_lock_once
    )
    assert "create_canonical_successor_parity_replay_lock(" in publish_source

    lock = CanonicalSuccessorParityReplayLock(
        authoritative_artifact_id="cedparityartifactv1_contract",
        replay_artifact_id="cedparityartifactv1_contract",
        authoritative_sha256="a" * 64,
        replay_sha256="a" * 64,
    )
    rendered = render_canonical_successor_parity_replay_lock(lock)
    assert rendered.endswith("\n")
    assert replay_canonical_successor_parity_replay_lock(rendered) == lock
    assert lock.replay_lock_id
    with pytest.raises(ContractValidationError):
        evaluation.create_canonical_successor_parity_replay_lock(lock, lock)
    with pytest.raises(TypeError):
        publish_signature.bind(Path("unused-lock.json"), lock)
    assert "does not attest" in (
        inspect.getdoc(render_canonical_successor_parity_replay_lock) or ""
    )
    assert "never for self-attestation" in (
        inspect.getdoc(replay_canonical_successor_parity_replay_lock) or ""
    )
    with pytest.raises((ValidationError, ContractValidationError)):
        CanonicalSuccessorParityReplayLock(
            authoritative_artifact_id="cedparityartifactv1_primary",
            replay_artifact_id="cedparityartifactv1_different",
            authoritative_sha256="a" * 64,
            replay_sha256="a" * 64,
        )
    with pytest.raises((ValidationError, ContractValidationError)):
        CanonicalSuccessorParityReplayLock(
            authoritative_artifact_id="cedparityartifactv1_contract",
            replay_artifact_id="cedparityartifactv1_contract",
            authoritative_sha256="a" * 64,
            replay_sha256="b" * 64,
        )


def test_write_once_bytes_are_identical_idempotent_and_conflict_refusing(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "phase8-pre-result-contract.json"
    payload = b'{"phase8":"pre-result-contract"}\n'
    digest = hashlib.sha256(payload).hexdigest()
    assert write_once_canonical_bytes(destination, payload) == digest
    assert write_once_canonical_bytes(destination, payload) == digest
    assert destination.read_bytes() == payload
    with pytest.raises(ContractValidationError):
        write_once_canonical_bytes(destination, b'{"different":true}\n')
    assert destination.read_bytes() == payload


def test_evaluator_has_zero_provider_dispatch_or_second_ced_authority() -> None:
    source_path = Path(evaluation.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden_calls = {
        "_run_registry_phase",
        "run_adapter",
        "generate_agent_move",
        "capture_canonical_opening_observation",
    }
    called_names = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    } | {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (forbidden_calls & called_names)
    assert "ProviderStatus" not in source
    assert "canonical_transition_outcome" not in source
    assert "canonical_capsule_semantic_snapshot" in source
    assert "canonical_successor_reference_field_digests" in source
    assert "_normalize_root_audit_clock" in source
    assert "datetime(2000, 1, 1" in source

    # Import-time contract freezing may instantiate Pydantic records, but the
    # aggregate builders themselves must remain definitions only.
    top_level_called = {
        node.value.func.id
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
    }
    assert "build_canonical_successor_parity_artifact" not in top_level_called
    assert "build_canonical_successor_parity_replay_artifact" not in top_level_called
