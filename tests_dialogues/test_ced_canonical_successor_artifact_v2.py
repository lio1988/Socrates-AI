"""Read-only post-result integrity locks for canonical-successor parity v2.

This module reads only the two committed JSON artifacts.  It never imports or
calls an evaluator, aggregate builder, replay builder, publisher, provider,
model, tool, or live path.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARTIFACT_DIRECTORY = (
    _REPO_ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-canonical-successor-parity-v2"
    / "artifacts"
)
_ARTIFACT_REPOSITORY_PATH = (
    "docs/branches/feature-socrates-zero-canonical-successor-parity-v2/"
    "artifacts/socrateszero_canonical_successor_parity_v2.json"
)
_REPLAY_LOCK_REPOSITORY_PATH = (
    "docs/branches/feature-socrates-zero-canonical-successor-parity-v2/"
    "artifacts/socrateszero_canonical_successor_parity_replay_lock_v2.json"
)
_ARTIFACT_PATH = _REPO_ROOT / _ARTIFACT_REPOSITORY_PATH
_REPLAY_LOCK_PATH = _REPO_ROOT / _REPLAY_LOCK_REPOSITORY_PATH

_ARTIFACT_ID = (
    "cedparityartifactv2_"
    "f3a9c85ef31dd5afc09c1353ff8fb67461ebce42ae5390a3dff1efb0f2e109e7"
)
_ARTIFACT_SHA256 = (
    "8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc"
)
_ARTIFACT_GIT_BLOB_ID = "130a7915c975979b8405b4f084d8b2f8716e7f59"
_REPLAY_LOCK_ID = (
    "cedparityreplaylockv2_"
    "e524b9e57fb070f67adc1098aeffe469d65b9f42bc0a9a77ddc9f3553e5f5280"
)
_REPLAY_LOCK_SHA256 = (
    "896ef4536a447ad9edbe49b59704b74f8f3a126486d02c4230d49897250fd224"
)
_REPLAY_LOCK_GIT_BLOB_ID = "5ef7a30dcf3ebe983acc20d032d96fb10afd9c8c"

_SUPPORTED_CASES = (
    "opening-empty-question",
    "opening-injection-question",
    "opening-invalid-json",
    "opening-schema-error",
    "opening-scripted-mock",
)
_ORTHOGONAL_PROBES = (
    "p8v2-o01-invalid-root-registration",
    "p8v2-o02-illegal-action-capability",
    "p8v2-o03-missing-observation",
    "p8v2-o04-invalid-observation-schema",
    "p8v2-o05-tampered-raw-digest",
    "p8v2-o06-wrong-task-agent",
    "p8v2-o07-wrong-root-question",
    "p8v2-o08-wrong-exact-model",
    "p8v2-o09-wrong-runtime-timeout",
    "p8v2-o10-future-label",
    "p8v2-o11-budget-exhausted",
)
_PRECEDENCE_PROBES = (
    "p8v2-p01-unsupported-family-vs-legality",
    "p8v2-p02-provider-roster-context",
    "p8v2-p03-root-plus-provider",
    "p8v2-p04-task-plus-model",
    "p8v2-p05-context-plus-tampered-digest",
    "p8v2-p06-illegal-plus-incompatible-observation",
    "p8v2-p07-caller-rebinding-vs-manifest",
)

_POSITIVE_EXPECTATIONS = {
    "opening-empty-question": (
        "applied_canonical_rejection",
        "socratic_content_rejected",
        None,
    ),
    "opening-injection-question": (
        "applied_canonical_rejection",
        "answer_injection_rejected",
        None,
    ),
    "opening-invalid-json": (
        "applied_canonical_rejection",
        "parser_rejected",
        None,
    ),
    "opening-schema-error": (
        "applied_canonical_rejection",
        "schema_rejected",
        None,
    ),
    "opening-scripted-mock": (
        "applied_accepted",
        None,
        "move_a0ac20327a5c",
    ),
}

_NEGATIVE_EXPECTATIONS = {
    "p8v2-o01-invalid-root-registration": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "invalid_root",
        "C1",
        "RAISED_UNAVAILABLE",
    ),
    "p8v2-o02-illegal-action-capability": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "illegal_action",
        "P8",
        "RAISED_UNAVAILABLE",
    ),
    "p8v2-o03-missing-observation": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "missing_observation",
        "A3",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-o04-invalid-observation-schema": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "invalid_observation",
        "A5",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-o05-tampered-raw-digest": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "invalid_observation_identity",
        "A5",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-o06-wrong-task-agent": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "observation_task_mismatch",
        "A9",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-o07-wrong-root-question": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "root_context_mismatch",
        "A8",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-o08-wrong-exact-model": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "observation_model_mismatch",
        "A11",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-o09-wrong-runtime-timeout": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "observation_config_mismatch",
        "A12",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-o10-future-label": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "future_label_forbidden",
        "A4",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-o11-budget-exhausted": (
        "orthogonal_cases",
        "ORTHOGONAL",
        "budget_exhausted",
        "P9",
        "RAISED_UNAVAILABLE",
    ),
    "p8v2-p01-unsupported-family-vs-legality": (
        "precedence_cases",
        "PRECEDENCE",
        "unsupported_action_family",
        "P7",
        "RAISED_UNAVAILABLE",
    ),
    "p8v2-p02-provider-roster-context": (
        "precedence_cases",
        "PRECEDENCE",
        "root_context_mismatch",
        "A8",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-p03-root-plus-provider": (
        "precedence_cases",
        "PRECEDENCE",
        "root_context_mismatch",
        "A8",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-p04-task-plus-model": (
        "precedence_cases",
        "PRECEDENCE",
        "observation_task_mismatch",
        "A9",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-p05-context-plus-tampered-digest": (
        "precedence_cases",
        "PRECEDENCE",
        "invalid_observation_identity",
        "A5",
        "RETURNED_UNAVAILABLE",
    ),
    "p8v2-p06-illegal-plus-incompatible-observation": (
        "precedence_cases",
        "PRECEDENCE",
        "illegal_action",
        "P8",
        "RAISED_UNAVAILABLE",
    ),
    "p8v2-p07-caller-rebinding-vs-manifest": (
        "precedence_cases",
        "PRECEDENCE",
        "invalid_observation_identity",
        "A7",
        "RETURNED_UNAVAILABLE",
    ),
}

_SNAPSHOT_FIELDS = (
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
_INVARIANT_STATES = {
    "PRESERVED",
    "INTENTIONALLY_CHANGED",
    "DEPENDENTLY_CHANGED",
    "NOT_APPLICABLE",
}
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_text(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _canonical_bytes(value: object) -> bytes:
    return (_canonical_text(value) + "\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _content_id(prefix: str, payload: dict[str, object]) -> str:
    return f"{prefix}_{_sha256(_canonical_text(payload).encode('utf-8'))}"


def _identified_payload(
    value: dict[str, object],
    identity_field: str,
) -> dict[str, object]:
    payload = dict(value)
    payload.pop(identity_field)
    return payload


def _git_blob_id(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _git_bytes(specification: str) -> bytes:
    return subprocess.run(
        ("git", "show", specification),
        cwd=_REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


@lru_cache(maxsize=1)
def _artifact_bytes_and_data() -> tuple[bytes, dict[str, object]]:
    payload = _ARTIFACT_PATH.read_bytes()
    return payload, json.loads(payload)


@lru_cache(maxsize=1)
def _replay_lock_bytes_and_data() -> tuple[bytes, dict[str, object]]:
    payload = _REPLAY_LOCK_PATH.read_bytes()
    return payload, json.loads(payload)


def _negative_case(probe_id: str) -> dict[str, object]:
    artifact = _artifact_bytes_and_data()[1]
    collection = _NEGATIVE_EXPECTATIONS[probe_id][0]
    return next(
        case for case in artifact[collection] if case["probe_id"] == probe_id
    )


def _called_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def test_test_source_cannot_call_result_or_runtime_paths() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any(name.startswith("backend") for name in imports)

    called_names = {
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (name := _called_name(node)) is not None
    }
    assert not {
        "_build_canonical_successor_parity_artifact_v2_in_order",
        "build_canonical_successor_parity_artifact_v2",
        "build_canonical_successor_parity_replay_artifact_v2",
        "build_canonical_successor_parity_artifact",
        "build_canonical_successor_parity_replay_artifact",
        "_evaluate_unavailable_probe_v2",
        "_evaluate_unavailable_probe_v2_strict",
        "_evaluate_parity_case",
        "_evaluate_v1_parity_case",
        "publish_canonical_successor_parity_artifact_once_v2",
        "publish_canonical_successor_parity_replay_lock_once_v2",
        "run_adapter",
        "_run_registry_phase",
        "generate_agent_move",
        "generate",
        "urlopen",
        "request",
    } & called_names


@pytest.mark.parametrize(
    ("repository_path", "expected_sha256", "expected_blob_id"),
    (
        (
            _ARTIFACT_REPOSITORY_PATH,
            _ARTIFACT_SHA256,
            _ARTIFACT_GIT_BLOB_ID,
        ),
        (
            _REPLAY_LOCK_REPOSITORY_PATH,
            _REPLAY_LOCK_SHA256,
            _REPLAY_LOCK_GIT_BLOB_ID,
        ),
    ),
)
def test_committed_json_bytes_are_canonical_and_exact(
    repository_path: str,
    expected_sha256: str,
    expected_blob_id: str,
) -> None:
    path = _REPO_ROOT / repository_path
    payload = path.read_bytes()
    parsed = json.loads(payload)
    assert payload == _canonical_bytes(parsed)
    assert payload.endswith(b"\n")
    assert not payload.endswith(b"\n\n")
    assert b"\r" not in payload
    assert _sha256(payload) == expected_sha256
    assert _git_blob_id(payload) == expected_blob_id

    head_payload = _git_bytes(f"HEAD:{repository_path}")
    index_payload = _git_bytes(f":{repository_path}")
    assert head_payload == index_payload == payload
    assert _sha256(head_payload) == _sha256(index_payload) == expected_sha256
    assert _git_blob_id(head_payload) == _git_blob_id(index_payload) == expected_blob_id

    staged = subprocess.run(
        ("git", "ls-files", "--stage", "--", repository_path),
        cwd=_REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()
    mode, blob_id, stage_and_path = staged.split(maxsplit=2)
    assert mode == "100644"
    assert blob_id == expected_blob_id
    assert stage_and_path == f"0\t{repository_path}"


def test_artifact_identity_lineage_core_and_historical_hashes_are_exact() -> None:
    payload, artifact = _artifact_bytes_and_data()
    assert _sha256(payload) == _ARTIFACT_SHA256
    assert artifact["artifact_id"] == _ARTIFACT_ID
    assert artifact["artifact_id"] == _content_id(
        "cedparityartifactv2",
        _identified_payload(artifact, "artifact_id"),
    )
    assert artifact["schema_version"] == "ced-canonical-successor-parity-artifact/v2"
    assert artifact["harness_id"] == "ced-canonical-successor-parity-harness/v2"
    assert artifact["hypothesis_status"] == "SUPPORTED"
    assert artifact["depth"] == 1
    assert artifact["recursive_successor"] is False
    assert artifact["production_authority"] == "none"

    expected_lineage = {
        "validation_order_id": "cedvalidationorder_2bbd60972e07a9afdc3ca6f2dd344cd891f39dab6f9edb4e92c4ba0552203a54",
        "failure_taxonomy_id": "cedfailuretaxonomy_73bef28686e43b201cafb33fcc536d19a863bd0773592db8aa6867b5a1189cf7",
        "failure_precedence_id": "cedfailureprecedence_4d75632cc9dac55daf59a87142dbd918e6c6573e48afec32f2225db10eaf7d7f",
        "compatibility_diagnostics_id": "cedcompatdiagnostics_b577167b4199464b250328b58dbc248194076a3f1a9370f8cf28022d56ebd44f",
        "probe_design_id": "cedprobedesign_fd7d21658acea185d164ccb32c726b498c0f7a3aa476b4c1698c82a1847f9e2f",
        "case_set_id": "cedparitycasesetv2_3706cb242dd60070acec46d00def5389c62fb90f869d98d932649fe023dc1233",
        "corpus_id": "cedparitycorpusv2_9d7d8563b931f1206c2e685c51d62dfa66b7a5ae66a40254fb63477f9c15524d",
        "corpus_canonical_sha256": "9d7d8563b931f1206c2e685c51d62dfa66b7a5ae66a40254fb63477f9c15524d",
        "thresholds_id": "cedparitythresholdsv2_e241fe357d1a6c36e7e19addd0a421e0c55332bf16d999a2aa895fcdccf9e210",
        "core_lock_id": "cedcorebloblockv2_2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957",
    }
    assert {name: artifact[name] for name in expected_lineage} == expected_lineage

    predecessor = artifact["core_lock"]["predecessor"]
    expected_predecessor = {
        "artifact_id": "cedparityartifactv1_893771ebb142e48b63dcdd623bdc734d7bb0da5697df251fadf73d3eda45f5e0",
        "artifact_sha256": "00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea",
        "artifact_commit": "07ec5ab14cd1599ffd6c8c4b6442d56d51129f11",
        "artifact_status": "FALSIFIED",
    }
    assert {name: predecessor[name] for name in expected_predecessor} \
        == expected_predecessor
    assert artifact["predecessor_artifact_id"] == expected_predecessor["artifact_id"]
    assert artifact["predecessor_artifact_sha256"] \
        == expected_predecessor["artifact_sha256"]
    assert artifact["predecessor_artifact_commit"] \
        == expected_predecessor["artifact_commit"]
    assert artifact["predecessor_status"] == expected_predecessor["artifact_status"]

    historical = {
        item["name"]: item["sha256"]
        for item in artifact["core_lock"]["historical_artifacts"]
    }
    assert historical == {
        "phase5_matched_compute_normalized": "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c",
        "phase7_value_v1_bestofn": "86b8f43c2dd9173100adfb7d5c84c6cc96df46a528407c203a3ce0930d117637",
        "phase7_value_v1_primary": "d8faecb7b3f134036afaa67a2fc84acc53e23a2e44a57971a45eefe4fdbaf8ca",
        "phase8_falsified_successor_parity_v1": "00f9ba13bc2f52c970da9021c725b4941be1ff3a37705ce95f02d369671587ea",
    }

    core_lock = artifact["core_lock"]
    core_payload = {
        "schema_version": core_lock["schema_version"],
        "core_blobs": core_lock["core_blobs"],
        "predecessor": core_lock["predecessor"],
        "historical_artifacts": core_lock["historical_artifacts"],
    }
    expected_fingerprint = _sha256(_canonical_text(core_payload).encode("utf-8"))
    assert core_lock["fingerprint"] == expected_fingerprint
    assert core_lock["lock_id"] == _content_id("cedcorebloblockv2", core_payload)
    assert core_lock["lock_id"] == artifact["core_lock_id"]
    assert len(core_lock["core_blobs"]) == 34
    assert tuple(item["path"] for item in core_lock["core_blobs"]) \
        == tuple(sorted(item["path"] for item in core_lock["core_blobs"]))
    assert len({item["path"] for item in core_lock["core_blobs"]}) == 34
    assert all(_HEX40.fullmatch(item["git_blob_id"]) for item in core_lock["core_blobs"])


def test_exact_membership_thresholds_metrics_and_zero_counters() -> None:
    artifact = _artifact_bytes_and_data()[1]
    parity = artifact["parity_cases"]
    orthogonal = artifact["orthogonal_cases"]
    precedence = artifact["precedence_cases"]
    case_set = artifact["case_set"]
    thresholds = artifact["thresholds"]
    metrics = artifact["metrics"]

    assert tuple(case["case_name"] for case in parity) == _SUPPORTED_CASES
    assert tuple(case["probe_id"] for case in orthogonal) == _ORTHOGONAL_PROBES
    assert tuple(case["probe_id"] for case in precedence) == _PRECEDENCE_PROBES
    assert (len(parity), len(orthogonal), len(precedence)) == (5, 11, 7)
    assert case_set["positive_reference_count"] == 5
    assert case_set["orthogonal_probe_count"] == 11
    assert case_set["precedence_probe_count"] == 7
    assert case_set["total_case_count"] == 23
    assert tuple(case_set["human_probe_ids"]) \
        == _ORTHOGONAL_PROBES + _PRECEDENCE_PROBES
    assert len(case_set["positive_case_references"]) == 5
    assert tuple(
        reference["case_name"] for reference in case_set["positive_case_references"]
    ) == _SUPPORTED_CASES
    assert len(case_set["probe_fingerprints"]) == 18
    assert len(set(case_set["probe_fingerprints"])) == 18
    assert all(_HEX64.fullmatch(value) for value in case_set["probe_fingerprints"])
    assert case_set["case_set_id"] == _content_id(
        "cedparitycasesetv2",
        _identified_payload(case_set, "case_set_id"),
    )

    assert thresholds["thresholds_id"] == artifact["thresholds_id"]
    assert thresholds["thresholds_id"] == _content_id(
        "cedparitythresholdsv2",
        _identified_payload(thresholds, "thresholds_id"),
    )
    assert {
        "cases_total": 23,
        "supported_authoritative_cases": 5,
        "accepted_reference_cases": 1,
        "canonical_rejection_reference_cases": 4,
        "orthogonal_negative_cases": 11,
        "precedence_negative_cases": 7,
        "required_supported_parity": 5,
        "required_accepted_parity": 1,
        "required_canonical_rejection_parity": 4,
        "required_orthogonal_primary_classifications": 11,
        "required_precedence_primary_classifications": 7,
        "required_historical_offline_fixture_dispatches": 5,
        "maximum_mismatch_or_failure_count": 0,
        "required_negative_probe_dispatches": 0,
        "required_aggregate_provider_dispatches": 0,
        "required_live_calls": 0,
        "required_model_calls": 0,
        "required_tool_calls": 0,
        "depth": 1,
        "recursive_successor": False,
    } == {
        name: thresholds[name]
        for name in (
            "cases_total",
            "supported_authoritative_cases",
            "accepted_reference_cases",
            "canonical_rejection_reference_cases",
            "orthogonal_negative_cases",
            "precedence_negative_cases",
            "required_supported_parity",
            "required_accepted_parity",
            "required_canonical_rejection_parity",
            "required_orthogonal_primary_classifications",
            "required_precedence_primary_classifications",
            "required_historical_offline_fixture_dispatches",
            "maximum_mismatch_or_failure_count",
            "required_negative_probe_dispatches",
            "required_aggregate_provider_dispatches",
            "required_live_calls",
            "required_model_calls",
            "required_tool_calls",
            "depth",
            "recursive_successor",
        )
    }

    nonzero_metrics = {
        "cases_total": 23,
        "supported_authoritative_cases": 5,
        "accepted_reference_cases": 1,
        "canonical_rejection_reference_cases": 4,
        "orthogonal_negative_cases": 11,
        "precedence_negative_cases": 7,
        "accepted_parity": 1,
        "canonical_rejection_parity": 4,
        "orthogonal_primary_classifications": 11,
        "precedence_primary_classifications": 7,
        "historical_offline_fixture_dispatches": 5,
    }
    assert {name: metrics[name] for name in nonzero_metrics} == nonzero_metrics
    assert metrics["schema_version"] == "ced-canonical-successor-parity-metrics/v2"
    for name, value in metrics.items():
        if name != "schema_version" and name not in nonzero_metrics:
            assert value == 0, name


@pytest.mark.parametrize("case_name", _SUPPORTED_CASES)
def test_each_supported_case_has_full_parity_and_isolation(case_name: str) -> None:
    artifact = _artifact_bytes_and_data()[1]
    case = next(item for item in artifact["parity_cases"] if item["case_name"] == case_name)
    expected_status, expected_rejection, expected_move_id = _POSITIVE_EXPECTATIONS[
        case_name
    ]
    receipt = case["receipt"]

    assert case["schema_version"] == "ced-canonical-successor-parity-case-result/v1"
    assert receipt["status"] == expected_status
    assert receipt["canonical_rejection_reason"] == expected_rejection
    assert receipt["resulting_move_id"] == expected_move_id
    for name in (
        "status_parity",
        "canonical_rejection_reason_parity",
        "semantic_parity",
        "search_state_v1_parity",
        "move_id_parity",
        "canonical_processor_parity",
        "observation_identity_match",
        "receipt_match",
        "resource_accounting_match",
        "source_unchanged",
        "sibling_unchanged",
        "production_unchanged",
        "idempotent_replay",
        "value_v1_read_only_compatible",
        "successor_created",
    ):
        assert case[name] is True, name
    assert case["source_runtime_fingerprint_before"] \
        == case["source_runtime_fingerprint_after"]
    assert case["production_runtime_fingerprint_before"] \
        == case["production_runtime_fingerprint_after"]
    assert case["sibling_result_digest_before"] == case["sibling_result_digest_after"]
    assert case["sibling_probe_successor_created"] is False
    assert case["primary_result_digest"] == case["replay_result_digest"]
    assert case["result_id"] == case["replay_result_id"]
    assert receipt["receipt_id"] == case["replay_receipt_id"]
    assert (
        case["source_provider_dispatches_before"],
        case["source_provider_dispatches_after"],
        case["production_provider_dispatches_before"],
        case["production_provider_dispatches_after"],
        case["aggregate_provider_dispatches"],
        case["live_calls"],
        case["tool_calls"],
        receipt["new_execution_usage"]["budget_delta"]["model_calls"],
        receipt["new_execution_usage"]["budget_delta"]["tool_calls"],
    ) == (0, 0, 0, 0, 0, 0, 0, 0, 0)
    assert len(case["parity_field_digests"]) == 13
    assert len({item["name"] for item in case["parity_field_digests"]}) == 13
    assert all(
        _HEX64.fullmatch(item["semantic_digest"])
        for item in case["parity_field_digests"]
    )
    assert case["case_result_id"] == _content_id(
        "cedparitycasev1",
        _identified_payload(case, "case_result_id"),
    )


@pytest.mark.parametrize("probe_id", tuple(_NEGATIVE_EXPECTATIONS))
def test_each_negative_case_locks_outcome_construction_and_diagnostics(
    probe_id: str,
) -> None:
    _, expected_class, expected_reason, expected_guard, expected_kind = (
        _NEGATIVE_EXPECTATIONS[probe_id]
    )
    case = _negative_case(probe_id)
    construction = case["construction_evidence"]
    diagnostics = case["diagnostics"]

    assert case["schema_version"] == "ced-canonical-successor-unavailable-case-result/v2"
    assert case["probe_class"] == expected_class
    assert case["expected_primary_reason"] == expected_reason
    assert case["actual_primary_reason"] == expected_reason
    assert case["observed_guard_id"] == expected_guard
    assert case["outcome_kind"] == expected_kind
    assert case["actual_status"] == (
        None if expected_kind == "RAISED_UNAVAILABLE" else "successor_unavailable"
    )
    for name in (
        "primary_reason_match",
        "guard_match",
        "diagnostic_match",
        "outcome_shape_match",
        "replay_match",
        "source_unchanged",
        "sibling_unchanged",
        "production_unchanged",
        "receipt_match",
        "resource_accounting_match",
    ):
        assert case[name] is True, name
    assert case["successor_created"] is False
    assert case["successor_capsule_id"] is None
    assert case["successor_branch_id"] is None
    assert case["successor_state_v1_id"] is None
    assert case["primary_outcome_digest"] == case["replay_outcome_digest"]
    assert case["replay_outcome_kind"] == case["outcome_kind"]
    assert case["replay_primary_reason"] == case["actual_primary_reason"]
    assert case["replay_status"] == case["actual_status"]
    assert case["source_runtime_fingerprint_before"] \
        == case["source_runtime_fingerprint_after"]
    assert case["sibling_runtime_fingerprint_before"] \
        == case["sibling_runtime_fingerprint_after"]
    assert case["production_runtime_fingerprint_before"] \
        == case["production_runtime_fingerprint_after"]
    assert case["sibling_control_capsule_id"] != case["source_capsule_id"]
    assert (
        case["source_provider_dispatches_before"],
        case["source_provider_dispatches_after"],
        case["sibling_provider_dispatches_before"],
        case["sibling_provider_dispatches_after"],
        case["production_provider_dispatches_before"],
        case["production_provider_dispatches_after"],
        case["negative_probe_dispatches"],
        case["aggregate_provider_dispatches"],
        case["live_calls"],
        case["primary_model_calls"],
        case["replay_model_calls"],
        case["model_calls"],
        case["tool_calls"],
    ) == (0,) * 13
    if expected_kind == "RAISED_UNAVAILABLE":
        assert case["receipt"] is None
        assert case["result_id"] is None
        assert case["transition_id"] is None
        assert case["replay_receipt_id"] is None
    else:
        receipt = case["receipt"]
        assert receipt["status"] == "successor_unavailable"
        assert receipt["unavailable_reason"] == expected_reason
        assert receipt["budget_before"] == receipt["budget_after"]
        assert receipt["new_execution_usage"] == {
            "budget_delta": {
                "cost_microusd": 0,
                "expansions": 0,
                "max_depth_observed": 0,
                "model_calls": 0,
                "nodes": 0,
                "tokens": 0,
                "tool_calls": 0,
                "wall_time_ms": 0,
            },
            "observation_applications": 0,
            "successor_evaluations": 0,
        }
        assert case["replay_result_id"] == case["result_id"]
        assert case["replay_transition_id"] == case["transition_id"]
        assert case["replay_receipt_id"] == receipt["receipt_id"]
    assert case["case_result_id"] == _content_id(
        "cedunavailablecasev2",
        _identified_payload(case, "case_result_id"),
    )

    assert construction["schema_version"] \
        == "ced-canonical-successor-probe-construction-evidence/v2"
    assert construction["probe_id"] == probe_id
    assert construction["probe_fingerprint"] == case["probe_fingerprint"]
    assert construction["observed_stage"] == case["stage"]
    assert construction["literal_mutations_match"] is True
    assert construction["ground_truth_firewall_passed"] is True
    assert construction["validity_gate_passed"] is True
    assert set(construction["measured_invariant_vector"]) == set(_SNAPSHOT_FIELDS)
    assert set(construction["measured_invariant_vector"].values()) \
        <= _INVARIANT_STATES
    assert len(construction["observed_literal_mutations"]) >= 1
    for path, before_json, after_json, independent in construction[
        "observed_literal_mutations"
    ]:
        assert path.strip()
        assert _canonical_text(json.loads(before_json)) == before_json
        assert _canonical_text(json.loads(after_json)) == after_json
        assert independent is True
    for snapshot_name in ("reference_snapshot", "candidate_snapshot"):
        snapshot = construction[snapshot_name]
        assert set(snapshot) == {"schema_version", *_SNAPSHOT_FIELDS}
        assert snapshot["schema_version"] \
            == "ced-canonical-successor-probe-component-snapshot/v2"
        assert all(
            value is None or _HEX64.fullmatch(value)
            for name, value in snapshot.items()
            if name != "schema_version"
        )
    assert construction["construction_evidence_id"] == _content_id(
        "cedprobeconstructionv2",
        _identified_payload(construction, "construction_evidence_id"),
    )

    assert diagnostics["schema_version"] \
        == "ced-canonical-successor-compatibility-diagnostic-evidence/v1"
    assert diagnostics["probe_id"] == probe_id
    assert diagnostics["expected_guard_id"] == expected_guard
    assert diagnostics["observed_guard_id"] == expected_guard
    assert diagnostics["expected_primary_mismatch_fields"] \
        == diagnostics["observed_primary_mismatch_fields"]
    assert diagnostics["expected_advisory_or_dominated_mismatch_fields"] \
        == diagnostics["observed_advisory_or_dominated_mismatch_fields"]
    assert diagnostics["expected_guard_evaluations"] \
        == diagnostics["observed_guard_evaluations"]
    assert diagnostics["expected_unreachable_guard_ids"] \
        == diagnostics["observed_unreachable_guard_ids"]
    assert diagnostics["expected_structured_future_scan_reached"] \
        is diagnostics["observed_structured_future_scan_reached"]
    assert diagnostics["canonical_parser_reached"] is False
    assert diagnostics["ced_application_reached"] is False
    assert diagnostics["authoritative_for_primary_result"] is False
    guard_trace = diagnostics["observed_guard_evaluations"]
    failed = [item["guard_id"] for item in guard_trace if item["state"] == "EVALUATED_FAILED"]
    assert failed == [expected_guard]
    assert diagnostics["field_comparisons"] == sorted(
        diagnostics["field_comparisons"], key=lambda item: item["name"]
    )
    assert len({item["name"] for item in diagnostics["field_comparisons"]}) \
        == len(diagnostics["field_comparisons"])
    assert all(
        _HEX64.fullmatch(item["observed_digest"])
        and _HEX64.fullmatch(item["required_digest"])
        for item in diagnostics["field_comparisons"]
    )
    assert diagnostics["immutable_inputs_digest"] == _sha256(
        _canonical_text(diagnostics["field_comparisons"]).encode("utf-8")
    )
    assert diagnostics["diagnostic_evidence_id"] == _content_id(
        "cedcompatdiagnosticevidence",
        _identified_payload(diagnostics, "diagnostic_evidence_id"),
    )


def test_all_negative_evidence_ids_are_complete_and_unique() -> None:
    artifact = _artifact_bytes_and_data()[1]
    cases = artifact["orthogonal_cases"] + artifact["precedence_cases"]
    assert len(cases) == 18
    assert len({case["case_result_id"] for case in cases}) == 18
    assert len(
        {case["construction_evidence"]["construction_evidence_id"] for case in cases}
    ) == 18
    assert len(
        {case["diagnostics"]["diagnostic_evidence_id"] for case in cases}
    ) == 18
    assert {
        case["construction_evidence"]["probe_id"] for case in cases
    } == set(_ORTHOGONAL_PROBES + _PRECEDENCE_PROBES)
    assert {
        case["diagnostics"]["probe_id"] for case in cases
    } == set(_ORTHOGONAL_PROBES + _PRECEDENCE_PROBES)

    p02 = next(
        case
        for case in artifact["precedence_cases"]
        if case["probe_id"] == "p8v2-p02-provider-roster-context"
    )
    assert p02["actual_primary_reason"] == "root_context_mismatch"
    assert p02["observed_guard_id"] == "A8"
    assert p02["primary_reason_match"] is True
    assert p02["guard_match"] is True


def test_replay_lock_attests_semantic_id_byte_sha_and_reverse_order_equality() -> None:
    payload, replay_lock = _replay_lock_bytes_and_data()
    assert _sha256(payload) == _REPLAY_LOCK_SHA256
    assert replay_lock["schema_version"] \
        == "ced-canonical-successor-parity-replay-lock/v2"
    assert replay_lock["replay_lock_id"] == _REPLAY_LOCK_ID
    assert replay_lock["replay_lock_id"] == _content_id(
        "cedparityreplaylockv2",
        _identified_payload(replay_lock, "replay_lock_id"),
    )
    assert replay_lock["authoritative_artifact_id"] \
        == replay_lock["replay_artifact_id"] \
        == _ARTIFACT_ID
    assert replay_lock["authoritative_sha256"] \
        == replay_lock["replay_sha256"] \
        == _ARTIFACT_SHA256
    assert replay_lock["semantic_equality"] is True
    assert replay_lock["artifact_id_equality"] is True
    assert replay_lock["byte_identity"] is True
    assert tuple(replay_lock["authoritative_supported_order"]) == _SUPPORTED_CASES
    assert tuple(replay_lock["authoritative_orthogonal_order"]) == _ORTHOGONAL_PROBES
    assert tuple(replay_lock["authoritative_precedence_order"]) == _PRECEDENCE_PROBES
    assert tuple(replay_lock["replay_supported_order"]) \
        == tuple(reversed(_SUPPORTED_CASES))
    assert tuple(replay_lock["replay_orthogonal_order"]) \
        == tuple(reversed(_ORTHOGONAL_PROBES))
    assert tuple(replay_lock["replay_precedence_order"]) \
        == tuple(reversed(_PRECEDENCE_PROBES))

    artifact = _artifact_bytes_and_data()[1]
    assert tuple(case["case_name"] for case in artifact["parity_cases"]) \
        == tuple(replay_lock["authoritative_supported_order"])
    assert tuple(case["probe_id"] for case in artifact["orthogonal_cases"]) \
        == tuple(replay_lock["authoritative_orthogonal_order"])
    assert tuple(case["probe_id"] for case in artifact["precedence_cases"]) \
        == tuple(replay_lock["authoritative_precedence_order"])
