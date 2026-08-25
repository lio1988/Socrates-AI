"""Frozen case-set, mutation-vector, and evaluator-firewall locks."""

from __future__ import annotations

from pathlib import Path

from backend.dialogues.socrates_zero.acquisition_cases import (
    MUTATION_VECTOR_FIELD_NAMES,
    ORTHOGONAL_PROBE_IDS_V0,
    POSITIVE_CASE_IDS_V0,
    PRECEDENCE_PROBE_IDS_V0,
    AcquisitionCaseClass,
    MutationState,
    FROZEN_ACQUISITION_CASE_SET_V0,
    FROZEN_ACQUISITION_GUARD_DESIGN_V0,
    FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0,
    FROZEN_ACQUISITION_POSITIVE_CASES_V0,
    FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0,
    FROZEN_ACQUISITION_THRESHOLDS_V0,
    FROZEN_BASELINE_CAPABILITY_FIXTURE_V0,
    FROZEN_BASELINE_CONTROL_POLICY_FIXTURE_V0,
    FROZEN_BASELINE_SEMANTIC_REQUEST_FIXTURE_V0,
    FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0,
    frozen_acquisition_case_set_sha256_v0,
)
from backend.dialogues.socrates_zero.acquisition_contracts import (
    ACQUISITION_GUARD_ORDER,
    AcquisitionGuardStage,
    AcquisitionGuardState,
)
from backend.dialogues.socrates_zero.contracts import canonical_json


def test_case_membership_order_and_exact_frozen_totals() -> None:
    assert POSITIVE_CASE_IDS_V0 == (
        "acqv0-s01-complete-deterministic",
        "acqv0-s02-content-opaque-invalid-json",
        "acqv0-s03-sibling-byte-identity",
        "acqv0-s04-repeat-semantic-identity",
        "acqv0-s05-seed-explicitly-unsupported",
        "acqv0-s06-historical-usage-unknown",
    )
    assert ORTHOGONAL_PROBE_IDS_V0 == tuple(
        item.probe_id for item in FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
    )
    assert ORTHOGONAL_PROBE_IDS_V0[-6:] == (
        "acqv0-o38-fallback-known-adverse",
        "acqv0-o39-retry-known-adverse",
        "acqv0-o40-sdk-hidden-retry-known-adverse",
        "acqv0-o41-termination-known-adverse",
        "acqv0-o42-isolation-precondition-failed",
        "acqv0-o43-valid-capability-snapshot-detached",
    )
    assert PRECEDENCE_PROBE_IDS_V0 == tuple(
        item.probe_id for item in FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
    )
    assert (len(POSITIVE_CASE_IDS_V0), len(ORTHOGONAL_PROBE_IDS_V0), len(PRECEDENCE_PROBE_IDS_V0)) == (
        6,
        43,
        7,
    )
    case_set = FROZEN_ACQUISITION_CASE_SET_V0
    assert case_set.total_case_count == 56
    assert case_set.total_attempt_receipts == 58
    assert case_set.total_canned_transport_invocations == 32
    assert sum(item.attempt_count for item in FROZEN_ACQUISITION_POSITIVE_CASES_V0) == 8
    assert sum(
        item.expected_canned_invocations
        for item in FROZEN_ACQUISITION_POSITIVE_CASES_V0
    ) == 8


def test_case_set_and_threshold_ids_are_content_addressed() -> None:
    case_set = FROZEN_ACQUISITION_CASE_SET_V0
    thresholds = FROZEN_ACQUISITION_THRESHOLDS_V0
    assert case_set.case_set_id == (
        "acqcasesetv0_"
        "80d001ddf60c390521414a50475fec53fb0d98dc81ae9a3e8d9c219f5d125c36"
    )
    assert case_set.case_set_id == "acqcasesetv0_" + frozen_acquisition_case_set_sha256_v0()
    assert thresholds.thresholds_id == (
        "acqthresholdsv0_"
        "b1ac8151eeca12bc3ad8f8a3005be9457ab97071d5cbea8f1e41c525e53cdc2c"
    )
    assert case_set.thresholds_id == thresholds.thresholds_id
    assert case_set.guard_ids == ACQUISITION_GUARD_ORDER
    assert tuple(step.guard_id for step in FROZEN_ACQUISITION_GUARD_DESIGN_V0) == (
        ACQUISITION_GUARD_ORDER
    )


def test_known_adverse_control_probes_are_exact_and_predispatch() -> None:
    expected = (
        (
            "acqv0-o38-fallback-known-adverse",
            "P09_FALLBACK_DISABLED",
            "FALLBACK_CONTROL_UNPROVEN",
            "capability.fallback",
            '"PROVEN_SUPPORTED"',
        ),
        (
            "acqv0-o39-retry-known-adverse",
            "P10_RETRY_DISABLED",
            "RETRY_CONTROL_UNPROVEN",
            "capability.retry",
            '"PROVEN_SUPPORTED"',
        ),
        (
            "acqv0-o40-sdk-hidden-retry-known-adverse",
            "P11_SDK_INTERNAL_RETRY_DISABLED",
            "SDK_INTERNAL_RETRY_CONTROL_UNPROVEN",
            "capability.sdk_internal_retry",
            '"PROVEN_SUPPORTED"',
        ),
        (
            "acqv0-o41-termination-known-adverse",
            "P13_TIMEOUT_WORKER_TERMINATION",
            "TIMEOUT_CANCELLATION_UNPROVEN",
            "capability.worker_termination",
            '"PROVEN_UNSUPPORTED"',
        ),
    )
    for probe, lock in zip(FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0[-6:-2], expected):
        probe_id, guard_id, failure, path, after_json = lock
        assert probe.probe_id == probe_id
        assert probe.expected_guard_id.value == guard_id
        assert probe.expected_primary_failure.value == failure
        assert probe.stage is AcquisitionGuardStage.PRE_DISPATCH
        assert probe.expected_canned_invocations == 0
        assert probe.literal_mutations[0].path == path
        assert probe.literal_mutations[0].after_json == after_json


def test_probe_dispatch_counts_match_frozen_guard_stages() -> None:
    orthogonal = FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
    precedence = FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
    assert sum(
        item.stage is AcquisitionGuardStage.PRE_DISPATCH for item in orthogonal
    ) == 22
    assert sum(
        item.stage is AcquisitionGuardStage.POST_DISPATCH for item in orthogonal
    ) == 21
    assert sum(
        item.stage is AcquisitionGuardStage.PRE_DISPATCH for item in precedence
    ) == 4
    assert sum(
        item.stage is AcquisitionGuardStage.POST_DISPATCH for item in precedence
    ) == 3
    assert sum(
        item.expected_canned_invocations for item in orthogonal + precedence
    ) == 24
    assert all(
        item.expected_canned_invocations
        == int(item.stage is AcquisitionGuardStage.POST_DISPATCH)
        for item in orthogonal + precedence
    )


def test_orthogonal_and_precedence_mutations_are_structurally_distinct() -> None:
    for probe in FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0:
        assert probe.probe_class is AcquisitionCaseClass.ORTHOGONAL
        assert len(probe.literal_mutations) == 1
        assert sum(
            getattr(probe.mutation_vector, name)
            is MutationState.INTENTIONALLY_CHANGED
            for name in MUTATION_VECTOR_FIELD_NAMES
        ) >= 1
    for probe in FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0:
        assert probe.probe_class is AcquisitionCaseClass.PRECEDENCE
        assert len(probe.literal_mutations) == 2
        assert sum(
            getattr(probe.mutation_vector, name)
            is MutationState.INTENTIONALLY_CHANGED
            for name in MUTATION_VECTOR_FIELD_NAMES
        ) >= 2


def test_every_probe_freezes_first_guard_wins_trace() -> None:
    for probe in (
        FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
        + FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
    ):
        states = tuple(item.state for item in probe.expected_guard_trace)
        failed_at = ACQUISITION_GUARD_ORDER.index(probe.expected_guard_id)
        assert states == (
            (AcquisitionGuardState.PASSED,) * failed_at
            + (AcquisitionGuardState.FAILED,)
            + (AcquisitionGuardState.NOT_REACHED,)
            * (len(ACQUISITION_GUARD_ORDER) - failed_at - 1)
        )


def test_baseline_fixture_is_canned_public_and_contains_no_transport_entropy() -> None:
    visible = FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0
    assert visible.decode("utf-8").encode("utf-8") == visible
    assert not visible.endswith(b"\n")
    forbidden = (
        b"branch_id",
        b"transport_attempt_id",
        b"experiment_id",
        b"timestamp",
        b"nonce",
        b"api_key",
        b"credential",
        b"C:\\\\",
    )
    assert all(canary not in visible for canary in forbidden)
    assert canonical_json(dict(FROZEN_BASELINE_CAPABILITY_FIXTURE_V0))
    assert canonical_json(dict(FROZEN_BASELINE_CONTROL_POLICY_FIXTURE_V0))
    assert canonical_json(dict(FROZEN_BASELINE_SEMANTIC_REQUEST_FIXTURE_V0))


def test_expected_labels_are_evaluator_side_and_runtime_does_not_import_cases() -> None:
    runtime_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "dialogues"
        / "socrates_zero"
        / "acquisition.py"
    )
    runtime_source = runtime_path.read_text(encoding="utf-8")
    assert "acquisition_cases" not in runtime_source
    for probe in (
        FROZEN_ACQUISITION_ORTHOGONAL_PROBES_V0
        + FROZEN_ACQUISITION_PRECEDENCE_PROBES_V0
    ):
        assert probe.probe_id not in runtime_source
        assert probe.expected_primary_failure.value not in (
            FROZEN_PROVIDER_VISIBLE_REQUEST_BYTES_V0.decode("utf-8")
        )


def test_strict_thresholds_accept_no_safety_or_methodology_mismatch() -> None:
    values = FROZEN_ACQUISITION_THRESHOLDS_V0.model_dump(mode="json")
    assert values["cases_total"] == 56
    assert values["required_positive_attempt_receipts"] == 8
    assert values["required_attempt_receipts_total"] == 58
    assert values["required_canned_transport_invocations"] == 32
    zero_fields = {
        name: value
        for name, value in values.items()
        if name.startswith("required_") and name not in {
            "required_positive_complete_case_results",
            "required_positive_attempt_receipts",
            "required_orthogonal_exact_primary_results",
            "required_precedence_exact_primary_results",
            "required_attempt_receipts_total",
            "required_canned_transport_invocations",
        }
    }
    assert all(value == 0 for value in zero_fields.values())
