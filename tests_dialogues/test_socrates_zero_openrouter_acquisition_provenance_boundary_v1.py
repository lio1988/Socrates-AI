"""Adversarial locks for the OpenRouter provenance boundary v1.

The boundary claims that historical scientific provenance can be carried by
immutable identities instead of raw predecessor source and test paths, without
losing mutation protection and without disturbing one byte of sealed evidence.
Every clause of that claim is attacked here.

The module name deliberately starts with ``test_socrates_zero_openrouter_acquisition``
so the shared conftest wraps every test below in the acquisition boundary
tripwire: zero network, credential, provider, model, tool or CED activity.
"""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero import (
    openrouter_route_controls_evaluation as evaluation,
)
from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_provenance_boundary_v1 import (
    FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1,
    OPENROUTER_PROVENANCE_BOUNDARY_ID_V1,
    OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
    OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1,
    OpenRouterProvenanceRecordV1,
    openrouter_provenance_record_v1,
)
from backend.dialogues.socrates_zero.openrouter_route_controls_cases import (
    FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1,
    FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1,
    FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1,
    OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1,
    OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1,
)
from tests_dialogues.test_socrates_zero_openrouter_acquisition_cases import (
    test_expected_labels_are_evaluator_side_and_cases_module_is_data_only
    as _canonical_static_inventory_node,
)

ROOT = Path(__file__).resolve().parents[1]

RUNTIME_DIR = ROOT / "backend" / "dialogues" / "socrates_zero"
EVALUATION_SOURCE = RUNTIME_DIR / "openrouter_route_controls_evaluation.py"
BOUNDARY_SOURCE = RUNTIME_DIR / "openrouter_provenance_boundary_v1.py"

# The predecessor reference the boundary exists to remove from runtime code.
# Assembled at test time from two halves so this lock file can name the thing it
# forbids without itself becoming a runtime carrier of it.  Nothing under
# ``backend/`` or ``scripts/`` may contain it.
_FORBIDDEN_RAW_REFERENCE = "openrouter_acquisition" + "_cases"

# Modules that predate the boundary and are exempt in the canonical static node.
_PREDECESSOR_MODULES = {
    "openrouter_acquisition_evaluation.py",
    _FORBIDDEN_RAW_REFERENCE + ".py",
}

SEALED_ARTIFACT_PATH = (
    ROOT
    / "docs/branches/feature-socrates-zero-openrouter-route-controls-v1"
    / "artifacts/socrateszero_openrouter_route_controls_v1.json"
)

FROZEN_SURFACE_SHA256 = {
    "docs/branches/feature-socrates-zero-openrouter-route-controls-v1/artifacts/socrateszero_openrouter_route_controls_v1.json": "61043f033e8c2afb73e72f0f3e9199ea008c8baf114e33f4b9829d0e70b90661",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/evidence/openrouter_official_wire_specification_manifest_v1.json": "cafd9364db1357b9aa676a7b45baeac2ef8a9f1b4288044fbaed95fcb3d4397b",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/artifacts/openrouter_wire_specification_manifest_validation_v1.json": "26c4616bb6b07ca3e5d2d0a1385c2d10aa8e9d523f90ca2c87d9872dc2ee4bc7",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/artifacts/openrouter_wire_specification_manifest_revalidation_v1.json": "c389c1816b364e787ba5270b121fdeb820a7426182f6d1d69e6a51aa796f187b",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/evidence/openrouter_wire_retrieval_log_v1.json": "8e9a6ecfe41c444323cf01c0e8d6d11ad1fd1e09d5400c14b5bf4c63278d5fd3",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/evidence/openrouter_wire_source_plan_v1.json": "cfaec71b93a88114e9378fe297d8cd5ec9645e6c747877eadd622003de9760a5",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/openrouter_official_wire_specification_manifest_v2r1.json": "3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/artifacts/openrouter_wire_specification_manifest_validation_v2r1.json": "7a75d644d0d6e61d3a9c5e5ef04bf5f16cd292206bc998e6952219b7ac11fb85",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/artifacts/openrouter_wire_specification_manifest_revalidation_v2r1.json": "75442d3bf74aeb5217a2e20db2580aacebe55d0fe21ee6d18288f38cb8defa1a",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/openapi.yaml": "bd144e3de11198e6ac72f12c4d8986949d7fcd651c02f6ef671afd62429b3713",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/router-metadata.mdx": "4e99ac8a12a5aea0ae83372f7fbd3c1e790edefb90a2a18355de5e77be3279f6",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/api-reference-overview.mdx": "8647d02d0e3ccb000e8870200e0284d2516973bf0ef7cf8f8a0353219ea87d3e",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/response-caching.mdx": "89e423514f98c2bdc5e288d5ea17159e78df29ea6ff56ea82cd8b68da1302f3e",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/provider-selection.mdx": "2781071f570c53040c0c01a9f1840097a43e6032ebd4e3d9ab2dfbeb01bb2252",
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/evidence/sources/model-fallbacks.mdx": "6d77e3242812a2b669bf22f9c9c6ac59a5d838906271d1593b2fff864c6550c1",
}


def _sealed_artifact() -> dict:
    return json.loads(SEALED_ARTIFACT_PATH.read_bytes())


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(("." * node.level) + (node.module or ""))
    return modules


def _replace_record(reference_id: str, **overrides) -> tuple:
    """Return the boundary with one record's identity fields overridden."""
    patched = []
    for record in FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1:
        if record.reference_id == reference_id:
            payload = record.model_dump(mode="python")
            payload.pop("record_id")
            payload.update(overrides)
            record = OpenRouterProvenanceRecordV1.model_validate(payload)
        patched.append(record)
    return tuple(patched)


def _capture_with_boundary(monkeypatch: pytest.MonkeyPatch, boundary: tuple):
    monkeypatch.setattr(
        evaluation, "FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1", boundary
    )
    return evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)


# ---------------------------------------------------------------- boundary ---


def test_canonical_static_inventory_node_passes() -> None:
    """Requirement 1: the exact static node, executed, not paraphrased."""
    _canonical_static_inventory_node()


def test_route_controls_runtime_does_not_import_predecessor_cases() -> None:
    """Requirement 2."""
    modules = _imported_modules(EVALUATION_SOURCE) | _imported_modules(BOUNDARY_SOURCE)
    assert not any(_FORBIDDEN_RAW_REFERENCE in module for module in modules)
    assert not any("acquisition_evaluation" in module for module in modules)


def test_route_controls_runtime_does_not_import_predecessor_tests() -> None:
    """Requirement 3."""
    modules = _imported_modules(EVALUATION_SOURCE) | _imported_modules(BOUNDARY_SOURCE)
    assert not any(
        module.startswith("test_")
        or "tests_dialogues" in module
        or ".test_" in module
        for module in modules
    )


def test_predecessor_expected_labels_are_not_consumed() -> None:
    """Requirement 4."""
    for source_path in (EVALUATION_SOURCE, BOUNDARY_SOURCE):
        source = source_path.read_text(encoding="utf-8")
        for token in (
            "FROZEN_OPENROUTER_ADAPTER",
            "OpenRouterAdapterGuardId",
            "OpenRouterAdapterCaseSetV0",
            "expected_label",
            "importlib",
            "__import__",
        ):
            assert token not in source, (source_path.name, token)
    # The boundary carries frozen literals only; it never reaches predecessor
    # semantics to establish provenance.
    assert _imported_modules(BOUNDARY_SOURCE) == {
        "__future__",
        "enum",
        "typing",
        "pydantic",
        ".contracts",
    }


def test_forbidden_raw_predecessor_reference_is_absent_from_runtime_python() -> None:
    """Requirement 5."""
    offenders = []
    for base in (ROOT / "backend", ROOT / "scripts"):
        for path in sorted(base.rglob("*.py")):
            if path.name in _PREDECESSOR_MODULES:
                continue
            if _FORBIDDEN_RAW_REFERENCE in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


# ------------------------------------------------------ identity tampering ---


@pytest.mark.parametrize(
    ("field", "value", "requirement"),
    (
        (
            "artifact_sha256",
            "0" * 64,
            "6: artifact SHA tampering is detected",
        ),
        (
            "artifact_id",
            "szoracqevaluation_" + "1" * 64,
            "7: artifact ID tampering is detected",
        ),
        (
            "case_set_id",
            "oracqcasesetv0_" + "2" * 64,
            "8: case-set identity tampering is detected",
        ),
        (
            "sealed_commit_sha",
            "3" * 40,
            "9: sealed commit identity tampering is detected",
        ),
        (
            "validation_order_id",
            "oracqvalidationv0_" + "4" * 64,
            "9b: validation-order tampering is detected",
        ),
        (
            "git_object_sha1",
            "5" * 40,
            "9c: Git object identity tampering is detected",
        ),
        (
            "semantic_id",
            "socrateszero-openrouter-acquisition-case-set/v9",
            "9d: semantic identity tampering is detected",
        ),
        (
            "sealed_content_sha256",
            "6" * 64,
            "9e: sealed content identity tampering is detected",
        ),
    ),
)
def test_provenance_identity_tampering_is_detected_as_mutation(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
    requirement: str,
) -> None:
    before = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    tampered = _replace_record(
        OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
        **{field: value},
    )
    after = _capture_with_boundary(monkeypatch, tampered)
    assert before.snapshot_id != after.snapshot_id, requirement
    mutation_evidence = (
        evaluation.compare_openrouter_route_control_scoped_snapshots_v1(before, after)
    )
    assert mutation_evidence.sibling_mutations == 1, requirement
    assert mutation_evidence.source_mutations == 0
    assert mutation_evidence.production_mutations == 0
    assert mutation_evidence.changed_paths == (
        OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
    )


def test_unrelated_artifact_substitution_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement 10, first form: a different reference cannot be swapped in."""
    substituted = tuple(
        record
        for record in FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1
        if record.reference_id != OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1
    ) + (
        OpenRouterProvenanceRecordV1(
            reference_id="provenance://socrateszero/unrelated-experiment/v0",
            semantic_id="socrateszero-unrelated/v0",
            scientific_role=(
                FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1[1].scientific_role
            ),
            artifact_id="szorunrelated_" + "7" * 64,
            artifact_sha256="8" * 64,
            case_set_id="unrelated_" + "9" * 64,
            validation_order_id="unrelated_" + "a" * 64,
            sealed_commit_sha="b" * 40,
            sealed_content_sha256="c" * 64,
        ),
    )
    monkeypatch.setattr(
        evaluation, "FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1", substituted
    )
    with pytest.raises(ContractValidationError):
        evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)


def test_provenance_reference_may_not_be_a_repository_path() -> None:
    """Requirement 10, second form: the boundary refuses to carry a raw path."""
    payload = FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1[0].model_dump(mode="python")
    payload.pop("record_id")
    payload["reference_id"] = (
        "backend/dialogues/socrates_zero/" + _FORBIDDEN_RAW_REFERENCE + ".py"
    )
    # pydantic wraps the contract error raised inside the model validator.
    with pytest.raises(ValidationError, match="must not be a repository path"):
        OpenRouterProvenanceRecordV1.model_validate(payload)


def test_provenance_record_id_tampering_is_rejected() -> None:
    payload = FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1[0].model_dump(mode="python")
    payload["record_id"] = "szorprovenancerecordv1_" + "0" * 64
    with pytest.raises(ValidationError, match="record ID mismatch"):
        OpenRouterProvenanceRecordV1.model_validate(payload)


def test_provenance_records_are_content_addressed_and_distinct() -> None:
    records = FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1
    assert len(records) == 2
    assert len({record.record_id for record in records}) == 2
    assert len({record.reference_id for record in records}) == 2
    for record in records:
        assert record.record_id == "szorprovenancerecordv1_" + record.record_sha256
        assert len(record.record_sha256) == 64
    assert OPENROUTER_PROVENANCE_BOUNDARY_ID_V1.startswith(
        "szorprovenanceboundaryv1_"
    )
    assert openrouter_provenance_record_v1("provenance://absent/v0") is None


# ------------------------------------------ current mutation protection ------


def test_genuine_current_route_control_source_mutation_is_still_detected(
    tmp_path: Path,
) -> None:
    """Requirement 11: file-backed coverage is real, not relocated away."""
    before = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)

    mirror = tmp_path / "mirror"
    mutated_relative = (
        "backend/dialogues/socrates_zero/openrouter_route_controls_parser.py"
    )
    file_backed = tuple(
        relative_path
        for _, paths in evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1
        for relative_path in paths
        if openrouter_provenance_record_v1(relative_path) is None
    )
    assert mutated_relative in file_backed
    for relative_path in file_backed:
        destination = mirror / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative_path, destination)

    unchanged = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(mirror)
    assert unchanged.snapshot_id == before.snapshot_id

    target = mirror / mutated_relative
    target.write_bytes(target.read_bytes() + b"\n# mutation\n")
    after = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(mirror)

    mutation_evidence = (
        evaluation.compare_openrouter_route_control_scoped_snapshots_v1(before, after)
    )
    assert mutation_evidence.source_mutations == 1
    assert mutation_evidence.sibling_mutations == 0
    assert mutation_evidence.production_mutations == 0
    assert mutation_evidence.changed_paths == (mutated_relative,)


def test_scoped_inventory_still_covers_every_current_route_control_source() -> None:
    snapshot = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    covered = {row.relative_path for row in snapshot.rows}
    assert {
        "backend/dialogues/socrates_zero/openrouter_route_controls_contracts.py",
        "backend/dialogues/socrates_zero/openrouter_route_controls_renderer.py",
        "backend/dialogues/socrates_zero/openrouter_route_controls_parser.py",
        "backend/dialogues/socrates_zero/openrouter_route_controls_cases.py",
        "backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py",
    } <= covered
    assert set(
        (
            OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
            OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1,
        )
    ) <= covered
    for row in snapshot.rows:
        if openrouter_provenance_record_v1(row.relative_path) is None:
            assert (ROOT / row.relative_path).is_file()


# ------------------------------------- historical versus current generation ---


def test_historical_and_current_inventory_generations_are_distinct() -> None:
    assert (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1
        != evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1
    )
    sealed = _sealed_artifact()
    assert sealed["scoped_before_snapshot"]["inventory_id"] == (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1
    )
    assert sealed["scoped_after_snapshot"]["inventory_id"] == (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1
    )
    assert sealed["scoped_before_snapshot"]["snapshot_id"] == (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_SNAPSHOT_ID_V1
    )
    assert len(sealed["scoped_before_snapshot"]["rows"]) == (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_ROW_COUNT_V1
    )
    # The current generation still describes the same number of scoped entries.
    current = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    assert len(current.rows) == (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_ROW_COUNT_V1
    )
    assert current.snapshot_id != (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_SNAPSHOT_ID_V1
    )


def test_historical_generation_rows_cannot_be_tampered() -> None:
    payload = _sealed_artifact()["scoped_before_snapshot"]
    payload.pop("snapshot_id")
    payload["rows"][0]["sha256"] = "0" * 64
    with pytest.raises(
        ValidationError, match="historical scoped snapshot identity changed"
    ):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


def test_historical_generation_row_count_cannot_be_tampered() -> None:
    payload = _sealed_artifact()["scoped_before_snapshot"]
    payload.pop("snapshot_id")
    payload["rows"] = payload["rows"][:-1]
    with pytest.raises(
        ValidationError, match="historical scoped snapshot row count changed"
    ):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


def test_unknown_inventory_generation_is_rejected() -> None:
    payload = _sealed_artifact()["scoped_before_snapshot"]
    payload.pop("snapshot_id")
    payload["inventory_id"] = "szorroutepathinventoryv1_" + "0" * 64
    with pytest.raises(ValidationError):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


def test_current_generation_membership_is_still_enforced() -> None:
    snapshot = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    payload = snapshot.model_dump(mode="json")
    payload.pop("snapshot_id")
    payload["rows"] = list(reversed(payload["rows"]))
    with pytest.raises(ValidationError, match="membership or order changed"):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


# ------------------------------------------------- frozen semantics remain ---


def _evaluated_results_by_case_id() -> dict:
    return {
        result.case_id: result.model_dump(mode="json")
        for result in (
            evaluation.evaluate_openrouter_route_control_case_v1(case)
            for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
        )
    }


def test_parser_outputs_remain_unchanged() -> None:
    """Requirement 12."""
    sealed = _sealed_artifact()
    assert sealed["metadata_parser_version"] == (
        "socrateszero-openrouter-router-metadata-parser/v1"
    )
    assert sealed["canned_response_parser_status"] == (
        "PROVEN_OFFLINE_LOCAL_NORMALIZED_CONTRACT_ONLY"
    )
    observed = _evaluated_results_by_case_id()
    for recorded in sealed["case_results"]:
        current = observed[recorded["case_id"]]
        for field in (
            "route_attestation",
            "route_attestation_id",
            "metadata_receipt",
            "metadata_receipt_id",
            "response_exact_endpoint_attestation",
            "semantic_headers_sha256",
            "raw_response_evidence",
        ):
            assert current[field] == recorded[field], (recorded["case_id"], field)


def test_renderer_outputs_remain_unchanged() -> None:
    """Requirement 13."""
    sealed = _sealed_artifact()
    assert sealed["renderer_version"] == "socrateszero-openrouter-route-renderer/v1"
    artifact = evaluation.load_openrouter_route_control_artifact_v1(
        SEALED_ARTIFACT_PATH
    )
    assert SEALED_ARTIFACT_PATH.read_bytes() == (
        evaluation.render_openrouter_route_control_artifact_v1(artifact)
    )
    observed = _evaluated_results_by_case_id()
    for recorded in sealed["case_results"]:
        current = observed[recorded["case_id"]]
        for field in (
            "request_body_sha256",
            "candidate_request_evidence_id",
            "request_intent_receipt_ids",
        ):
            assert current[field] == recorded[field], (recorded["case_id"], field)


def test_route_control_case_ids_remain_unchanged() -> None:
    """Requirement 14."""
    sealed = _sealed_artifact()
    assert OPENROUTER_ROUTE_CONTROL_CASE_SET_ID_V1 == sealed["case_set_id"]
    assert tuple(case.case_id for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1) == (
        tuple(recorded["case_id"] for recorded in sealed["case_results"])
    )
    observed = _evaluated_results_by_case_id()
    for recorded in sealed["case_results"]:
        assert observed[recorded["case_id"]]["case_fingerprint"] == (
            recorded["case_fingerprint"]
        )


def test_guard_order_remains_unchanged() -> None:
    """Requirement 15."""
    sealed = _sealed_artifact()
    assert FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1.validation_order_id == (
        sealed["validation_order_id"]
    )
    assert tuple(
        guard.value for guard in FROZEN_ROUTE_CONTROL_GUARD_ORDER_V1
    ) == tuple(
        step["guard_id"]
        for step in FROZEN_OPENROUTER_ROUTE_CONTROL_VALIDATION_ORDER_V1.model_dump(
            mode="json"
        )["steps"]
    )
    observed = _evaluated_results_by_case_id()
    for recorded in sealed["case_results"]:
        current = observed[recorded["case_id"]]
        assert current["guard_trace"] == recorded["guard_trace"], recorded["case_id"]
        assert current["actual_guard_id"] == recorded["actual_guard_id"]
        assert current["actual_failure_code"] == recorded["actual_failure_code"]


def test_thresholds_remain_unchanged() -> None:
    """Requirement 16."""
    sealed = _sealed_artifact()
    assert OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1 == sealed["thresholds_id"]
    assert FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1.model_dump(mode="json") == (
        sealed["thresholds"]
    )


# ------------------------------------------------------ sealed evidence ------


@pytest.mark.parametrize(
    "relative_path", sorted(FROZEN_SURFACE_SHA256), ids=lambda value: value.split("/")[-1]
)
def test_frozen_scientific_surfaces_remain_byte_identical(relative_path: str) -> None:
    """Requirements 17, 18 and 19."""
    path = ROOT / relative_path
    assert path.is_file(), relative_path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        FROZEN_SURFACE_SHA256[relative_path]
    ), relative_path


def test_sealed_route_control_artifact_still_loads_and_stays_falsified() -> None:
    artifact = evaluation.load_openrouter_route_control_artifact_v1(
        SEALED_ARTIFACT_PATH
    )
    assert artifact.hypothesis_status.value == "FALSIFIED"
    assert artifact.artifact_id == _sealed_artifact()["artifact_id"]
    assert artifact.metrics.all_thresholds_pass is False
    assert artifact.scoped_mutation_evidence.source_mutations == 0
    assert artifact.scoped_mutation_evidence.sibling_mutations == 0
    assert artifact.scoped_mutation_evidence.production_mutations == 0


def test_predecessor_scientific_identity_matches_the_sealed_record() -> None:
    """The boundary carries the predecessor identity the artifact recorded."""
    sealed = _sealed_artifact()
    for record in FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1:
        assert record.artifact_id == sealed["predecessor_artifact_id"]
        assert record.artifact_sha256 == sealed["predecessor_artifact_sha256"]
    predecessor_path = (
        ROOT
        / "docs/branches/feature-socrates-zero-provider-adapter-controls-v0"
        / "artifacts/socrateszero_openrouter_acquisition_adapter_controls_v0.json"
    )
    predecessor = json.loads(predecessor_path.read_bytes())
    design = openrouter_provenance_record_v1(
        OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1
    )
    assert design is not None
    assert design.artifact_id == predecessor["artifact_id"]
    assert design.case_set_id == predecessor["case_set_id"]
    assert hashlib.sha256(predecessor_path.read_bytes()).hexdigest() == (
        design.artifact_sha256
    )
