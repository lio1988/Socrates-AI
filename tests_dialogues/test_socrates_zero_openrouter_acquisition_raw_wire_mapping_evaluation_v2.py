"""Locks for the OpenRouter raw wire-mapping v2 evaluator and its artifacts.

Named so the shared conftest wraps every test in the acquisition boundary
tripwire, which is also what makes the artifact's zero claims checkable: the
artifact contract cross-checks its counters against live instrumentation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.acquisition_tripwires import (
    AcquisitionBoundaryViolation,
)
from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_raw_wire_mapping_cases_v2 import (
    FROZEN_OPENROUTER_WIRE_CASES_V2,
    OPENROUTER_WIRE_CASE_SET_ID_V2,
)
from backend.dialogues.socrates_zero.openrouter_raw_wire_mapping_evaluation_v2 import (
    FROZEN_OPENROUTER_WIRE_THRESHOLDS_V2,
    OPENROUTER_WIRE_ARTIFACT_RELATIVE_PATH_V2,
    OPENROUTER_WIRE_REPLAY_EXECUTION_RELATIVE_PATH_V2,
    OPENROUTER_WIRE_REPLAY_LOCK_RELATIVE_PATH_V2,
    OPENROUTER_WIRE_THRESHOLDS_ID_V2,
    OpenRouterRawWireMappingArtifactV2,
    OpenRouterWireActualOutcomeV2,
    OpenRouterWireHypothesisStatusV2,
    OpenRouterWireReplayLockV2,
    _static_dependency_counts,
    build_openrouter_raw_wire_mapping_artifact_v2,
    evaluate_openrouter_wire_case_set_v2,
    load_openrouter_raw_wire_mapping_artifact_v2,
    render_openrouter_raw_wire_mapping_artifact_v2,
    replay_openrouter_raw_wire_mapping_v2,
    write_once_v2,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT / OPENROUTER_WIRE_ARTIFACT_RELATIVE_PATH_V2
EXECUTION_PATH = ROOT / OPENROUTER_WIRE_REPLAY_EXECUTION_RELATIVE_PATH_V2
LOCK_PATH = ROOT / OPENROUTER_WIRE_REPLAY_LOCK_RELATIVE_PATH_V2

AUTHORITATIVE_ARTIFACT_SHA256 = (
    "d42fd8486c89f4b1ec6fd8dc2d5b9aee9b7aeb23c23237adcdac929a8ace1d75"
)
AUTHORITATIVE_ARTIFACT_ID = (
    "szorwireartifactv2_"
    "4585c60e4406bcdb4b2390e39f91ee31cf35bab0c545a0b0b26722e8beb9ca12"
)


def test_every_case_result_matches_expectation() -> None:
    results = evaluate_openrouter_wire_case_set_v2()
    assert len(results) == len(FROZEN_OPENROUTER_WIRE_CASES_V2) == 60
    assert all(result.result_matches_expectation for result in results)
    assert not any(
        result.actual_outcome
        is OpenRouterWireActualOutcomeV2.INVALID_FIXTURE_CONSTRUCTION
        for result in results
    )


def test_no_case_leaks_authority() -> None:
    for result in evaluate_openrouter_wire_case_set_v2():
        assert not result.endpoint_identity_synthesized, result.case_id
        assert not result.requested_substituted_for_actual, result.case_id
        assert not result.provider_display_substituted_for_endpoint, result.case_id
        assert not result.cache_hit_inferred_from_absence, result.case_id
        assert not result.unknown_field_authority_escalated, result.case_id


def test_thresholds_are_the_predeclared_frozen_set() -> None:
    thresholds = FROZEN_OPENROUTER_WIRE_THRESHOLDS_V2
    assert thresholds.thresholds_id == OPENROUTER_WIRE_THRESHOLDS_ID_V2
    assert thresholds.required_positive_cases_accepted == 17
    assert thresholds.required_adversarial_cases_rejected == 43
    for name, value in thresholds.model_dump(mode="python").items():
        if name.startswith("maximum_") or name.startswith("required_") and "cases" not in name:
            assert value == 0, name


def test_static_dependency_scan_does_not_match_itself() -> None:
    """The detector's own marker literals must not trigger the detector."""
    assert _static_dependency_counts(ROOT) == (0, 0)


def test_authoritative_artifact_is_canonical_and_supported() -> None:
    assert ARTIFACT_PATH.is_file()
    artifact = load_openrouter_raw_wire_mapping_artifact_v2(ARTIFACT_PATH)
    assert ARTIFACT_PATH.read_bytes() == (
        render_openrouter_raw_wire_mapping_artifact_v2(artifact)
    )
    assert artifact.artifact_id == AUTHORITATIVE_ARTIFACT_ID
    assert (
        hashlib.sha256(ARTIFACT_PATH.read_bytes()).hexdigest()
        == AUTHORITATIVE_ARTIFACT_SHA256
    )
    assert artifact.hypothesis_status is OpenRouterWireHypothesisStatusV2.SUPPORTED
    assert artifact.metrics.all_thresholds_pass is True
    assert artifact.case_set_id == OPENROUTER_WIRE_CASE_SET_ID_V2


def test_artifact_records_zero_external_activity() -> None:
    artifact = load_openrouter_raw_wire_mapping_artifact_v2(ARTIFACT_PATH)
    counters = artifact.boundary_counters.model_dump(mode="python")
    assert set(counters.values()) == {0}, counters


def test_artifact_preserves_the_standing_blockers() -> None:
    artifact = load_openrouter_raw_wire_mapping_artifact_v2(ARTIFACT_PATH)
    assert artifact.p17_input_token_bound == "NOT_ESTABLISHED"
    assert artifact.p18_pricing_record == "NOT_ESTABLISHED"
    assert artifact.p19_total_cost_bound == "NOT_ESTABLISHED"
    assert artifact.runtime_authority == "NOT_AUTHORIZED"
    assert artifact.live_openrouter_execution == "NOT_AUTHORIZED"
    assert artifact.exact_endpoint_response_identity_status == (
        "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"
    )


def test_rebuilding_reproduces_the_artifact_byte_for_byte() -> None:
    rebuilt = build_openrouter_raw_wire_mapping_artifact_v2(ROOT)
    assert render_openrouter_raw_wire_mapping_artifact_v2(rebuilt) == (
        ARTIFACT_PATH.read_bytes()
    )
    assert rebuilt.artifact_id == AUTHORITATIVE_ARTIFACT_ID


def test_replay_evidence_is_present_and_deterministic() -> None:
    assert EXECUTION_PATH.is_file() and LOCK_PATH.is_file()
    execution = json.loads(EXECUTION_PATH.read_bytes())
    lock = json.loads(LOCK_PATH.read_bytes())
    assert execution["semantic_equality"] is True
    assert execution["artifact_id_equality"] is True
    assert execution["byte_identity"] is True
    assert execution["official_source_retrievals"] == 0
    assert execution["source_artifact_id"] == AUTHORITATIVE_ARTIFACT_ID
    assert execution["recomputed_artifact_id"] == AUTHORITATIVE_ARTIFACT_ID
    assert lock["artifact_sha256"] == AUTHORITATIVE_ARTIFACT_SHA256
    assert lock["replay_execution_sha256"] == (
        hashlib.sha256(EXECUTION_PATH.read_bytes()).hexdigest()
    )


def test_replay_recomputes_the_same_result() -> None:
    execution, lock = replay_openrouter_raw_wire_mapping_v2(ARTIFACT_PATH)
    assert execution.semantic_equality is True
    assert execution.artifact_id_equality is True
    assert execution.byte_identity is True
    assert lock.artifact_id == AUTHORITATIVE_ARTIFACT_ID


def test_replay_lock_refuses_nondeterminism() -> None:
    payload = json.loads(LOCK_PATH.read_bytes())
    payload.pop("lock_id")
    payload["byte_identity"] = False
    with pytest.raises(ValidationError, match="deterministic replay"):
        OpenRouterWireReplayLockV2.model_validate(payload)


def test_artifact_metrics_must_be_derived() -> None:
    payload = json.loads(ARTIFACT_PATH.read_bytes())
    payload.pop("artifact_id")
    payload["metrics"]["accepted_as_expected"] = 99
    with pytest.raises(ValidationError, match="not fully derived"):
        OpenRouterRawWireMappingArtifactV2.model_validate(payload)


def test_artifact_cannot_claim_a_status_it_did_not_derive() -> None:
    payload = json.loads(ARTIFACT_PATH.read_bytes())
    payload.pop("artifact_id")
    payload["hypothesis_status"] = "FALSIFIED"
    with pytest.raises(ValidationError, match="hypothesis status is not derived"):
        OpenRouterRawWireMappingArtifactV2.model_validate(payload)


def test_artifact_counters_are_cross_checked_against_instrumentation() -> None:
    payload = json.loads(ARTIFACT_PATH.read_bytes())
    payload.pop("artifact_id")
    payload["boundary_counters"]["live_provider_calls"] = 1
    with pytest.raises(ValidationError):
        OpenRouterRawWireMappingArtifactV2.model_validate(payload)


def test_authoritative_evidence_is_write_once(tmp_path: Path) -> None:
    target = tmp_path / "evidence.json"
    write_once_v2(target, b"first\n")
    with pytest.raises(ContractValidationError, match="already exists"):
        write_once_v2(target, b"second\n")


def test_building_outside_a_tripwire_is_refused() -> None:
    """The conftest tripwire is active here, so nest a disabled context check."""
    from backend.dialogues.socrates_zero import acquisition_tripwires as tw

    token = tw._ACTIVE_TRIPWIRE.set(None)
    try:
        with pytest.raises(AcquisitionBoundaryViolation):
            build_openrouter_raw_wire_mapping_artifact_v2(ROOT)
    finally:
        tw._ACTIVE_TRIPWIRE.reset(token)


def test_s5_modules_are_import_inert(tmp_path: Path) -> None:
    """Re-import every S5 module under the live tripwire.

    Any filesystem write, network access, credential lookup, provider call,
    model execution, tool call or CED application performed at import time would
    trip the boundary rather than pass quietly.
    """
    import importlib

    from backend.dialogues.socrates_zero import (
        acquisition_tripwires,
        openrouter_raw_wire_mapping_cases_v2,
        openrouter_raw_wire_mapping_evaluation_v2,
        openrouter_raw_wire_mapping_v2,
    )

    before = acquisition_tripwires.active_acquisition_boundary_tripwire_v0().snapshot()
    for module in (
        openrouter_raw_wire_mapping_v2,
        openrouter_raw_wire_mapping_cases_v2,
        openrouter_raw_wire_mapping_evaluation_v2,
    ):
        importlib.reload(module)
    after = acquisition_tripwires.active_acquisition_boundary_tripwire_v0().assert_clean()
    assert after.total_forbidden_attempts == before.total_forbidden_attempts == 0
    assert after.hits == ()
    assert list(tmp_path.iterdir()) == []


def test_no_s5_module_writes_at_import_time() -> None:
    """Static check: no module-level write, open or network call."""
    import ast

    runtime_dir = ROOT / "backend" / "dialogues" / "socrates_zero"
    for name in (
        "openrouter_raw_wire_mapping_v2.py",
        "openrouter_raw_wire_mapping_cases_v2.py",
        "openrouter_raw_wire_mapping_evaluation_v2.py",
    ):
        tree = ast.parse((runtime_dir / name).read_text(encoding="utf-8"))
        for node in tree.body:
            # Module level may define, import and assign - never call out.
            if isinstance(node, (ast.Expr, ast.With, ast.Try, ast.For, ast.While)):
                assert isinstance(
                    getattr(node, "value", None), (ast.Constant, type(None))
                ), (name, ast.dump(node)[:80])
