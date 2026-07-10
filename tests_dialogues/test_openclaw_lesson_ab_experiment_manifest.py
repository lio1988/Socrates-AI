"""Adversarial tests for the bound single-agent A/B experiment manifest."""

import copy
import importlib.util
from pathlib import Path

import pytest

from backend.dialogues.openclaw_identity import AGENT_LESSON_AB_REPORT_VERSION

_ROOT = Path(__file__).resolve().parents[1]
AGENT = "local_apprentice_001"
LESSON = "LESSON-0007"
LESSON_FP = "a" * 64


@pytest.fixture(scope="module")
def bridge():
    path = _ROOT / "scripts" / "openclaw_attest_lesson_ab.py"
    spec = importlib.util.spec_from_file_location(
        "openclaw_lesson_ab_manifest_bridge", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _report(**updates):
    value = {
        "schema_version": AGENT_LESSON_AB_REPORT_VERSION,
        "target_agent_id": AGENT,
        "lesson_id": LESSON,
        "treatment_scope": "single_agent",
        "tested": 4,
    }
    value.update(updates)
    return value


def _bindings():
    return {
        "lesson_fingerprint": LESSON_FP,
        "target_identity_fingerprint": "b" * 64,
        "experiment_fingerprint": "c" * 64,
    }


def _manifest():
    return {
        "schema_version": "openclaw_agent_lesson_ab_experiment_v1",
        "target_agent_id": AGENT,
        "lesson_id": LESSON,
        "treatment_scope": "single_agent",
        "question_hashes": ["1" * 64, "2" * 64, "3" * 64, "4" * 64],
        "control_configuration": {
            "base_configuration_fingerprint": "d" * 64,
            "injected_lesson_fingerprints": [],
            "injection_target_agent_id": "",
        },
        "treatment_configuration": {
            "base_configuration_fingerprint": "d" * 64,
            "injected_lesson_fingerprints": [LESSON_FP],
            "injection_target_agent_id": AGENT,
        },
        "execution_mode": "deterministic-mock",
        "provider_ids": ["mock-a", "mock-b"],
        "judge_configuration": {
            "judge_set_fingerprint": "e" * 64,
            "self_judging_allowed": False,
        },
        "random_seeds": [1, 2, 3, 4],
        "arm_orders": [
            ["control", "treatment"],
            ["treatment", "control"],
            ["control", "treatment"],
            ["treatment", "control"],
        ],
        "counterbalanced": True,
        "compute_budget": {
            "token_limit": 1000,
            "timeout_seconds": 30.0,
            "retry_limit": 0,
        },
        "producer_version": "test-v1",
    }


def _validate(bridge, manifest=None, report=None):
    bridge._validate_experiment_manifest(
        manifest or _manifest(),
        report=report or _report(),
        bindings=_bindings(),
    )


def test_valid_manifest_passes(bridge):
    _validate(bridge)


def test_manifest_identity_lesson_and_scope_must_match_report(bridge):
    manifest = _manifest()
    manifest["target_agent_id"] = "agent_beta"
    with pytest.raises(ValueError, match="target_agent_id does not match"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["lesson_id"] = "LESSON-9999"
    with pytest.raises(ValueError, match="lesson_id does not match"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["treatment_scope"] = "whole_council"
    with pytest.raises(ValueError, match="single_agent"):
        _validate(bridge, manifest)


def test_question_seed_and_arm_rows_are_matched_and_replay_safe(bridge):
    manifest = _manifest()
    manifest["question_hashes"][1] = manifest["question_hashes"][0]
    with pytest.raises(ValueError, match="question_hashes must be distinct"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["random_seeds"] = [1, 2]
    with pytest.raises(ValueError, match="random_seeds must align"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["arm_orders"][0] = ["control", "control"]
    with pytest.raises(ValueError, match="control and treatment exactly once"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["arm_orders"] = [
        ["control", "treatment"] for _ in range(4)
    ]
    with pytest.raises(ValueError, match="exercise both arm orders"):
        _validate(bridge, manifest)


def test_control_is_clean_and_treatment_changes_only_bound_lesson(bridge):
    manifest = _manifest()
    manifest["control_configuration"]["injected_lesson_fingerprints"] = [
        LESSON_FP]
    with pytest.raises(ValueError, match="control configuration"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["treatment_configuration"]["injected_lesson_fingerprints"] = [
        "f" * 64]
    with pytest.raises(ValueError, match="exactly the bound lesson"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["treatment_configuration"]["injection_target_agent_id"] = \
        "agent_beta"
    with pytest.raises(ValueError, match="only into the target agent"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["treatment_configuration"][
        "base_configuration_fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="share one base configuration"):
        _validate(bridge, manifest)


def test_provider_judge_and_budget_constraints_fail_closed(bridge):
    manifest = _manifest()
    manifest["provider_ids"] = ["mock-a", "mock-a"]
    with pytest.raises(ValueError, match="provider_ids must be distinct"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["judge_configuration"]["self_judging_allowed"] = True
    with pytest.raises(ValueError, match="forbids self-judging"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["compute_budget"]["token_limit"] = 0
    with pytest.raises(ValueError, match="positive integer"):
        _validate(bridge, manifest)

    manifest = _manifest()
    manifest["compute_budget"]["timeout_seconds"] = float("inf")
    with pytest.raises(ValueError, match="positive finite"):
        _validate(bridge, manifest)


def test_report_tested_count_cannot_exceed_manifest_questions(bridge):
    with pytest.raises(ValueError, match="exceeds experiment question count"):
        _validate(bridge, report=_report(tested=5))


def test_manifest_field_sets_are_exact(bridge):
    manifest = _manifest()
    manifest["authority"] = "grant"
    with pytest.raises(ValueError, match="missing or unknown fields"):
        _validate(bridge, manifest)

    manifest = _manifest()
    del manifest["compute_budget"]["retry_limit"]
    with pytest.raises(ValueError, match="compute_budget contains"):
        _validate(bridge, manifest)


def test_unpacked_envelope_verifies_manifest_digest_and_secrets(bridge):
    manifest = _manifest()
    envelope = {
        "schema_version": bridge.ATTESTATION_SCHEMA_VERSION,
        "lesson_fingerprint": LESSON_FP,
        "target_identity_fingerprint": "b" * 64,
        "experiment_fingerprint": bridge._canonical_digest(
            manifest, field="experiment_manifest"),
        "experiment_manifest": manifest,
        "instrument_report": _report(),
    }
    _, bindings, returned = bridge._unpack_envelope(envelope)
    assert returned == manifest
    assert bindings["experiment_fingerprint"] == envelope[
        "experiment_fingerprint"]

    mismatch = copy.deepcopy(envelope)
    mismatch["experiment_manifest"]["producer_version"] = "changed"
    with pytest.raises(ValueError, match="does not match experiment_manifest"):
        bridge._unpack_envelope(mismatch)

    secret = copy.deepcopy(envelope)
    secret["experiment_manifest"]["producer_version"] = \
        "api_key=abcdefgh12345678"
    secret["experiment_fingerprint"] = bridge._canonical_digest(
        secret["experiment_manifest"], field="experiment_manifest")
    with pytest.raises(ValueError, match="secret-shaped"):
        bridge._unpack_envelope(secret)
