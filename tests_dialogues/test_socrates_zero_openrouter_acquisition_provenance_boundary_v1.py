"""Adversarial locks for the OpenRouter provenance boundary v1.

The boundary claims that historical scientific provenance can be carried by
immutable identities instead of raw predecessor source and test paths, without
losing mutation protection and without disturbing one byte of sealed evidence.
Every clause of that claim is attacked here.

Two generations, two contracts, two operations:

- ``OpenRouterScopedPathSnapshotV1`` is the SEALED HISTORICAL contract. It is
  never widened to describe the repository as it stands today.
- ``OpenRouterCurrentScopedSnapshotV1`` is the CURRENT contract, with its own
  schema and its own identity namespace.

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
    openrouter_provenance_boundary_v1 as boundary,
)
from backend.dialogues.socrates_zero import (
    openrouter_route_controls_evaluation as evaluation,
)
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    stable_contract_id,
)
from backend.dialogues.socrates_zero.openrouter_provenance_boundary_v1 import (
    FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1,
    OPENROUTER_PROVENANCE_BOUNDARY_ID_V1,
    OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
    OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1,
    OpenRouterCurrentScopedSnapshotV1,
    OpenRouterProvenanceRecordV1,
    compare_openrouter_current_scoped_snapshots_v1,
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


def _historical_snapshot_payload() -> dict:
    """The sealed historical snapshot, with its declared identity removed."""
    payload = _sealed_artifact()["scoped_before_snapshot"]
    payload.pop("snapshot_id")
    return payload


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


def _capture_with_boundary(monkeypatch: pytest.MonkeyPatch, records: tuple):
    """Substitute the frozen boundary itself, so every reader sees one truth."""
    monkeypatch.setattr(
        boundary, "FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1", records
    )
    return evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)


# ------------------------------------------------- I: the boundary itself ----


def test_canonical_static_inventory_node_passes() -> None:
    """Proof I: the exact static node, executed, not paraphrased."""
    _canonical_static_inventory_node()


def test_route_controls_runtime_does_not_import_predecessor_cases() -> None:
    modules = _imported_modules(EVALUATION_SOURCE) | _imported_modules(BOUNDARY_SOURCE)
    assert not any(_FORBIDDEN_RAW_REFERENCE in module for module in modules)
    assert not any("acquisition_evaluation" in module for module in modules)


def test_route_controls_runtime_does_not_import_predecessor_tests() -> None:
    modules = _imported_modules(EVALUATION_SOURCE) | _imported_modules(BOUNDARY_SOURCE)
    assert not any(
        module.startswith("test_")
        or "tests_dialogues" in module
        or ".test_" in module
        for module in modules
    )


def test_predecessor_expected_labels_are_not_consumed() -> None:
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
    offenders = []
    for base in (ROOT / "backend", ROOT / "scripts"):
        for path in sorted(base.rglob("*.py")):
            if path.name in _PREDECESSOR_MODULES:
                continue
            if _FORBIDDEN_RAW_REFERENCE in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_current_inventory_excludes_the_predecessor_raw_paths() -> None:
    membership = tuple(
        reference
        for _, references in evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1
        for reference in references
    )
    assert not any(_FORBIDDEN_RAW_REFERENCE in reference for reference in membership)
    assert OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1 in membership
    assert OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1 in membership


# ------------------------------------- the two generations are two contracts --


def test_historical_and_current_are_distinct_contracts() -> None:
    assert (
        evaluation.OpenRouterScopedPathSnapshotV1
        is not boundary.OpenRouterCurrentScopedSnapshotV1
    )
    assert not issubclass(
        boundary.OpenRouterCurrentScopedSnapshotV1,
        evaluation.OpenRouterScopedPathSnapshotV1,
    )
    assert not issubclass(
        evaluation.OpenRouterScopedPathSnapshotV1,
        boundary.OpenRouterCurrentScopedSnapshotV1,
    )
    historical_field = evaluation.OpenRouterScopedPathSnapshotV1.model_fields[
        "inventory_id"
    ]
    # The sealed contract admits exactly one inventory identity: the historical
    # one. It was not widened to also admit the current generation.
    assert historical_field.annotation.__args__ == (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1,
    )
    assert (
        evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1
        not in historical_field.annotation.__args__
    )
    assert (
        boundary.OPENROUTER_CURRENT_SCOPED_SNAPSHOT_SCHEMA_V1
        != evaluation.OPENROUTER_ROUTE_CONTROL_SCOPED_SNAPSHOT_SCHEMA_V1
    )


def test_the_two_generations_have_separate_identity_namespaces() -> None:
    assert evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1.startswith(
        "szorroutepathinventoryv1_"
    )
    assert evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1.startswith(
        "szorcurrentpathinventoryv1_"
    )
    assert (
        evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1
        != evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_PATH_INVENTORY_ID_V1
    )


def test_historical_and_current_verification_are_separate_operations() -> None:
    """Neither comparison accepts the other generation's snapshot."""
    current = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    historical = evaluation.load_openrouter_route_control_artifact_v1(
        SEALED_ARTIFACT_PATH
    ).scoped_before_snapshot
    with pytest.raises(ContractValidationError, match="sealed historical"):
        evaluation.compare_openrouter_route_control_scoped_snapshots_v1(
            current, current
        )
    with pytest.raises(ContractValidationError, match="current snapshot contract"):
        compare_openrouter_current_scoped_snapshots_v1(historical, historical)


def test_sealed_v1_artifact_cannot_be_rebuilt_from_the_current_generation() -> None:
    """The frozen artifact schema was not made permissive to fit today."""
    with pytest.raises(ContractValidationError, match="sealed historical"):
        evaluation._build_route_control_artifact_v1(
            reverse_case_order=True,
            root=ROOT,
        )


# ---------------------------------- C, D, E, F: sealed historical snapshot ----


def test_sealed_artifact_recomputes_the_historical_snapshot_identity() -> None:
    """Proof C."""
    artifact = evaluation.load_openrouter_route_control_artifact_v1(
        SEALED_ARTIFACT_PATH
    )
    frozen_id = evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_SNAPSHOT_ID_V1
    for snapshot in (
        artifact.scoped_before_snapshot,
        artifact.scoped_after_snapshot,
    ):
        assert snapshot.snapshot_id == frozen_id
        # Recomputed independently here from the snapshot's own rows.
        assert stable_contract_id(
            "szorroutesnapshotv1",
            snapshot.model_dump(mode="json", exclude={"snapshot_id"}),
        ) == frozen_id
        assert len(snapshot.rows) == (
            evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_ROW_COUNT_V1
        )


def test_historical_row_path_mutation_fails() -> None:
    """Proof D."""
    payload = _historical_snapshot_payload()
    payload["rows"][0]["relative_path"] = "backend/dialogues/socrates_zero/other.py"
    with pytest.raises(
        ValidationError, match="historical scoped snapshot identity changed"
    ):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


def test_historical_row_sha_mutation_fails() -> None:
    """Proof E."""
    payload = _historical_snapshot_payload()
    payload["rows"][0]["sha256"] = "0" * 64
    with pytest.raises(
        ValidationError, match="historical scoped snapshot identity changed"
    ):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


def test_historical_row_reordering_fails() -> None:
    """Proof F."""
    payload = _historical_snapshot_payload()
    payload["rows"] = list(reversed(payload["rows"]))
    with pytest.raises(
        ValidationError, match="historical scoped snapshot identity changed"
    ):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


def test_historical_row_count_mutation_fails() -> None:
    payload = _historical_snapshot_payload()
    payload["rows"] = payload["rows"][:-1]
    with pytest.raises(
        ValidationError, match="historical scoped snapshot row count changed"
    ):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


def test_declared_historical_snapshot_id_is_never_trusted() -> None:
    """A caller cannot bless tampered rows by declaring the frozen identity."""
    payload = _historical_snapshot_payload()
    payload["rows"][0]["sha256"] = "0" * 64
    payload["snapshot_id"] = (
        evaluation.FROZEN_ROUTE_CONTROL_HISTORICAL_SCOPED_SNAPSHOT_ID_V1
    )
    with pytest.raises(
        ValidationError, match="historical scoped snapshot identity changed"
    ):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)

    # ... and an untampered snapshot still rejects a wrong declared identity.
    honest = _historical_snapshot_payload()
    honest["snapshot_id"] = "szorroutesnapshotv1_" + "0" * 64
    with pytest.raises(ValidationError, match="scoped snapshot ID mismatch"):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(honest)


def test_historical_contract_rejects_the_current_inventory_id() -> None:
    payload = _historical_snapshot_payload()
    payload["inventory_id"] = (
        evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1
    )
    with pytest.raises(ValidationError):
        evaluation.OpenRouterScopedPathSnapshotV1.model_validate(payload)


# ------------------------------------------ G: the current scoped snapshot ----


def test_current_snapshot_uses_the_new_inventory_id_and_exact_membership() -> None:
    """Proof G."""
    snapshot = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    assert type(snapshot) is OpenRouterCurrentScopedSnapshotV1
    assert snapshot.inventory_id == (
        evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_ID_V1
    )
    expected_membership = tuple(
        (boundary.OpenRouterCurrentScopeV1(scope.value), reference)
        for scope, references in evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1
        for reference in references
    )
    assert tuple((row.scope, row.reference) for row in snapshot.rows) == (
        expected_membership
    )
    assert snapshot.inventory_id == boundary.openrouter_current_scoped_inventory_id_v1(
        expected_membership
    )
    assert snapshot.snapshot_id is not None
    assert snapshot.snapshot_id.startswith("szorcurrentsnapshotv1_")


def test_current_snapshot_membership_and_order_are_enforced() -> None:
    snapshot = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    for mutate in (
        lambda rows: list(reversed(rows)),
        lambda rows: rows[:-1],
        lambda rows: rows + [dict(rows[0])],
    ):
        payload = snapshot.model_dump(mode="json")
        payload.pop("snapshot_id")
        payload["rows"] = mutate(list(payload["rows"]))
        with pytest.raises(ValidationError):
            OpenRouterCurrentScopedSnapshotV1.model_validate(payload)


def test_declared_current_snapshot_id_is_never_trusted() -> None:
    snapshot = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    payload = snapshot.model_dump(mode="json")
    payload["snapshot_id"] = "szorcurrentsnapshotv1_" + "0" * 64
    with pytest.raises(ValidationError, match="current scoped snapshot ID mismatch"):
        OpenRouterCurrentScopedSnapshotV1.model_validate(payload)


def test_current_snapshot_requires_the_immutable_provenance_digest() -> None:
    snapshot = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    payload = snapshot.model_dump(mode="json")
    payload.pop("snapshot_id")
    for row in payload["rows"]:
        if row["reference"] == OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1:
            row["sha256"] = "0" * 64
    with pytest.raises(
        ValidationError, match="not the immutable\\s+record identity"
    ):
        OpenRouterCurrentScopedSnapshotV1.model_validate(payload)


# ---------------------------------------- 6-9: provenance identity tampering --


@pytest.mark.parametrize(
    ("field", "value", "requirement"),
    (
        ("artifact_sha256", "0" * 64, "artifact SHA tampering"),
        ("artifact_id", "szoracqevaluation_" + "1" * 64, "artifact ID tampering"),
        ("case_set_id", "oracqcasesetv0_" + "2" * 64, "case-set identity tampering"),
        ("sealed_commit_sha", "3" * 40, "sealed commit identity tampering"),
        (
            "validation_order_id",
            "oracqvalidationv0_" + "4" * 64,
            "validation-order tampering",
        ),
        ("git_object_sha1", "5" * 40, "Git object identity tampering"),
        (
            "semantic_id",
            "socrateszero-openrouter-acquisition-case-set/v9",
            "semantic identity tampering",
        ),
        ("sealed_content_sha256", "6" * 64, "sealed content identity tampering"),
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
    evidence = compare_openrouter_current_scoped_snapshots_v1(before, after)
    assert evidence.sibling_mutations == 1, requirement
    assert evidence.source_mutations == 0
    assert evidence.production_mutations == 0
    assert evidence.changed_references == (
        OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
    )


def test_unrelated_artifact_substitution_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        boundary, "FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1", substituted
    )
    with pytest.raises((ContractValidationError, ValidationError)):
        evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)


def test_provenance_reference_may_not_be_a_repository_path() -> None:
    payload = FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1[0].model_dump(mode="python")
    payload.pop("record_id")
    payload["reference_id"] = (
        "backend/dialogues/socrates_zero/" + _FORBIDDEN_RAW_REFERENCE + ".py"
    )
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


def test_current_and_historical_scope_vocabularies_cannot_drift() -> None:
    assert {scope.value for scope in boundary.OpenRouterCurrentScopeV1} == (
        {scope.value for scope in evaluation.OpenRouterRouteControlMutationScopeV1}
    )


# --------------------------------- H: current mutation protection is real -----


def test_genuine_current_route_control_source_mutation_is_still_detected(
    tmp_path: Path,
) -> None:
    """Proof H: file-backed coverage is real, not relocated away."""
    before = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)

    mirror = tmp_path / "mirror"
    mutated_reference = (
        "backend/dialogues/socrates_zero/openrouter_route_controls_parser.py"
    )
    file_backed = tuple(
        reference
        for _, references in evaluation.FROZEN_ROUTE_CONTROL_SCOPED_PATH_INVENTORY_V1
        for reference in references
        if openrouter_provenance_record_v1(reference) is None
    )
    assert mutated_reference in file_backed
    assert len(file_backed) == len(before.rows) - len(
        FROZEN_OPENROUTER_PROVENANCE_BOUNDARY_V1
    )
    for reference in file_backed:
        destination = mirror / reference
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / reference, destination)

    unchanged = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(mirror)
    assert unchanged.snapshot_id == before.snapshot_id

    target = mirror / mutated_reference
    target.write_bytes(target.read_bytes() + b"\n# mutation\n")
    after = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(mirror)

    evidence = compare_openrouter_current_scoped_snapshots_v1(before, after)
    assert evidence.source_mutations == 1
    assert evidence.sibling_mutations == 0
    assert evidence.production_mutations == 0
    assert evidence.changed_references == (mutated_reference,)
    assert evidence.evidence_id is not None


def test_scoped_inventory_still_covers_every_current_route_control_source() -> None:
    snapshot = evaluation.capture_openrouter_route_control_scoped_snapshot_v1(ROOT)
    covered = {row.reference for row in snapshot.rows}
    assert {
        "backend/dialogues/socrates_zero/openrouter_route_controls_contracts.py",
        "backend/dialogues/socrates_zero/openrouter_route_controls_renderer.py",
        "backend/dialogues/socrates_zero/openrouter_route_controls_parser.py",
        "backend/dialogues/socrates_zero/openrouter_route_controls_cases.py",
        "backend/dialogues/socrates_zero/openrouter_route_controls_evaluation.py",
        OPENROUTER_PROVENANCE_PREDECESSOR_CASE_DESIGN_REFERENCE_V1,
        OPENROUTER_PROVENANCE_PREDECESSOR_CASE_SUITE_REFERENCE_V1,
    } <= covered
    for row in snapshot.rows:
        if openrouter_provenance_record_v1(row.reference) is None:
            assert (ROOT / row.reference).is_file()
            assert row.sha256 == hashlib.sha256(
                (ROOT / row.reference).read_bytes()
            ).hexdigest()


# ------------------------------------------------- frozen semantics remain ----


def _evaluated_results_by_case_id() -> dict:
    return {
        result.case_id: result.model_dump(mode="json")
        for result in (
            evaluation.evaluate_openrouter_route_control_case_v1(case)
            for case in FROZEN_OPENROUTER_ROUTE_CONTROL_CASES_V1
        )
    }


def test_parser_outputs_remain_unchanged() -> None:
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
    sealed = _sealed_artifact()
    assert OPENROUTER_ROUTE_CONTROL_THRESHOLDS_ID_V1 == sealed["thresholds_id"]
    assert FROZEN_OPENROUTER_ROUTE_CONTROL_THRESHOLDS_V1.model_dump(mode="json") == (
        sealed["thresholds"]
    )


# ------------------------------------------- A, B, L: sealed evidence bytes ---


@pytest.mark.parametrize(
    "relative_path", sorted(FROZEN_SURFACE_SHA256), ids=lambda value: value.split("/")[-1]
)
def test_frozen_scientific_surfaces_remain_byte_identical(relative_path: str) -> None:
    """Proofs A, B and L."""
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
    assert artifact.scoped_mutation_evidence.mutations == ()
    assert artifact.scoped_mutation_evidence.source_mutations == 0
    assert artifact.scoped_mutation_evidence.sibling_mutations == 0
    assert artifact.scoped_mutation_evidence.production_mutations == 0


def test_predecessor_scientific_identity_matches_the_sealed_record() -> None:
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
