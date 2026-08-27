"""Locks for the additive OpenRouter live-safety closure v1.

The filename deliberately matches the shared acquisition-tripwire prefix, so
every test runs with network, credential, provider, model, tool and CED seams
instrumented and fail-closed.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import multiprocessing.process
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.openrouter_live_request_overlay_v2 import (
    OPENROUTER_MAX_SAFE_PICODOLLARS_V1,
)
from backend.dialogues.socrates_zero.openrouter_live_safety_cases_v1 import (
    FROZEN_OPENROUTER_AUTHORIZATION_CASES_V1,
    FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1,
    FROZEN_OPENROUTER_LIVE_SAFETY_REQUIREMENT_TAGS_V1,
    FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1,
    FROZEN_OPENROUTER_METAMORPHIC_CASES_V1,
    FROZEN_OPENROUTER_P17_CASES_V1,
    FROZEN_OPENROUTER_P19_CASES_V1,
    OPENROUTER_AUTHORIZATION_CASE_SET_ID_V1,
    OPENROUTER_LIVE_SAFETY_CASE_SET_ID_V1,
    OPENROUTER_LIVE_SAFETY_THRESHOLDS_ID_V1,
    OPENROUTER_METAMORPHIC_CASE_SET_ID_V1,
    OPENROUTER_P17_CASE_SET_ID_V1,
    OPENROUTER_P19_CASE_SET_ID_V1,
    OpenRouterLiveSafetyCaseKindV1,
    OpenRouterLiveSafetyCaseV1,
)
from backend.dialogues.socrates_zero.openrouter_live_safety_closure_v1 import (
    FROZEN_OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_V1,
    OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_ID_V1,
    OpenRouterClaimStoreReadinessAttestationV1,
    OpenRouterLiveSafetyModeV1,
    OpenRouterOneCallAuthorizationV1,
    OpenRouterOneLiveCallFailureCodeV1,
    OpenRouterOneLiveCallPreflightResultV1,
    OpenRouterOneLiveCallVerdictV1,
    OpenRouterP19CostComponentV1,
    openrouter_claim_store_id_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_safety_evaluation_v1 import (
    OPENROUTER_LIVE_SAFETY_ARTIFACT_RELATIVE_PATH_V1,
    OPENROUTER_LIVE_SAFETY_REPLAY_EXECUTION_RELATIVE_PATH_V1,
    OPENROUTER_LIVE_SAFETY_REPLAY_LOCK_RELATIVE_PATH_V1,
    OpenRouterLiveSafetyActualOutcomeV1,
    OpenRouterLiveSafetyArtifactV1,
    OpenRouterLiveSafetyPredecessorSurfaceV1,
    OpenRouterLiveSafetyReplayExecutionV1,
    OpenRouterLiveSafetyReplayLockV1,
    _authorized_preflight_v1,
    _claim_store_readiness_v1,
    _consume_authorized_preflight_v1,
    _fixture_v1,
    _preflight_v1,
    build_openrouter_live_safety_artifact_v1,
    evaluate_openrouter_live_safety_case_v1,
    evaluate_openrouter_live_safety_predecessor_integrity_v1,
    render_openrouter_live_safety_replay_execution_v1,
    render_openrouter_live_safety_replay_lock_v1,
    replay_openrouter_live_safety_v1,
    scan_openrouter_live_safety_artifact_privacy_v1,
    write_once_v1,
)
from backend.dialogues.socrates_zero.openrouter_pre_live_safety_v1 import (
    OpenRouterChargeClassStateV1,
)


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "backend" / "dialogues" / "socrates_zero"
S7A_MODULES = (
    "openrouter_live_request_overlay_v2.py",
    "openrouter_live_safety_closure_v1.py",
    "openrouter_live_safety_cases_v1.py",
    "openrouter_live_safety_evaluation_v1.py",
)


def test_frozen_case_inventory_has_the_predeclared_shape() -> None:
    cases = FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
    assert len(cases) == 73
    assert sum(case.kind is OpenRouterLiveSafetyCaseKindV1.POSITIVE for case in cases) == 20
    assert sum(case.kind is OpenRouterLiveSafetyCaseKindV1.ADVERSARIAL for case in cases) == 53
    assert len(FROZEN_OPENROUTER_P17_CASES_V1) == 20
    assert len(FROZEN_OPENROUTER_P19_CASES_V1) == 24
    assert len(FROZEN_OPENROUTER_AUTHORIZATION_CASES_V1) == 20
    assert len(FROZEN_OPENROUTER_METAMORPHIC_CASES_V1) == 9


def test_every_numbered_s35_through_s40_requirement_is_covered() -> None:
    actual = {
        tag
        for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
        for tag in case.requirement_tags
    }
    expected = set(FROZEN_OPENROUTER_LIVE_SAFETY_REQUIREMENT_TAGS_V1)
    assert len(expected) == 73
    assert actual == expected


def test_case_and_threshold_id_namespaces_are_frozen() -> None:
    assert OPENROUTER_P17_CASE_SET_ID_V1.startswith("szorlivesafetycasesetv1_")
    assert OPENROUTER_P19_CASE_SET_ID_V1.startswith("szorlivesafetycasesetv1_")
    assert OPENROUTER_AUTHORIZATION_CASE_SET_ID_V1.startswith(
        "szorlivesafetycasesetv1_"
    )
    assert OPENROUTER_METAMORPHIC_CASE_SET_ID_V1.startswith(
        "szorlivesafetycasesetv1_"
    )
    assert OPENROUTER_LIVE_SAFETY_CASE_SET_ID_V1.startswith(
        "szorlivesafetycasesetv1_"
    )
    assert OPENROUTER_LIVE_SAFETY_THRESHOLDS_ID_V1.startswith(
        "szorlivesafetythresholdsv1_"
    )


def test_threshold_counts_equal_the_frozen_inventory() -> None:
    thresholds = FROZEN_OPENROUTER_LIVE_SAFETY_THRESHOLDS_V1
    assert thresholds.required_total_cases == 73
    assert thresholds.required_positive_accepted == 20
    assert thresholds.required_adversarial_rejected == 53
    assert thresholds.required_p17_cases == 20
    assert thresholds.required_p19_cases == 24
    assert thresholds.required_authorization_cases == 20
    assert thresholds.required_metamorphic_cases == 9
    assert thresholds.required_requirement_tags_covered == 73
    assert thresholds.thresholds_id == OPENROUTER_LIVE_SAFETY_THRESHOLDS_ID_V1


def test_case_description_is_part_of_the_fingerprint() -> None:
    case = FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1[0]
    payload = case.model_dump(mode="json")
    payload["description"] += " changed"
    with pytest.raises(ValidationError, match="fingerprint mismatch"):
        OpenRouterLiveSafetyCaseV1.model_validate(payload)


def test_case_ids_are_unique_and_stably_sorted() -> None:
    ids = tuple(case.case_id for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1)
    assert len(ids) == len(set(ids))
    assert ids == tuple(sorted(ids))


@pytest.mark.parametrize(
    "case",
    FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1,
    ids=lambda case: case.case_id,
)
def test_every_frozen_case_matches_the_real_contracts(case) -> None:
    result = evaluate_openrouter_live_safety_case_v1(
        case,
        repository_root=ROOT,
    )
    assert result.result_matches_expectation, (
        result.case_id,
        result.actual_outcome,
        result.actual_failure_code,
        result.core_signal,
    )
    assert result.actual_outcome is not (
        OpenRouterLiveSafetyActualOutcomeV1.INVALID_FIXTURE_CONSTRUCTION
    )
    assert result.result_id.startswith("szorlivesafetyresultv1_")
    assert result.core_signal != "UNHANDLED_EVALUATOR_FIXTURE_ERROR"


def test_all_symbolic_probes_are_unique_and_evaluator_dispatchable() -> None:
    probes = tuple(case.probe for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1)
    assert len(probes) == len(set(probes)) == 73
    evaluation_source = (RUNTIME_DIR / "openrouter_live_safety_evaluation_v1.py").read_text(
        encoding="utf-8"
    )
    for probe in probes:
        assert f'probe == "{probe}"' in evaluation_source or (
            probe
            in {
                "P19_REQUEST_FEE_ABSENT",
                "P19_REQUEST_FEE_NONE",
                "P19_REQUEST_FEE_MALFORMED",
                "P19_REQUEST_FEE_NEGATIVE",
                "P19_REQUEST_FEE_FLOAT",
                "P19_PROMPT_CEILING_ABSENT",
                "P19_COMPLETION_CEILING_ABSENT",
            }
            and f'"{probe}"' in evaluation_source
        )


def test_preflight_guard_order_is_explicit_reachable_and_content_addressed() -> None:
    codes = tuple(code.value for code in FROZEN_OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_V1)
    assert len(codes) == len(set(codes))
    assert codes[0] == "SAFETY_CONTRACT_MISMATCH"
    assert codes[-1] == "AUTHORIZATION_ALREADY_CONSUMED"
    assert OPENROUTER_ONE_LIVE_CALL_GUARD_ORDER_ID_V1.startswith(
        "szorlivepreflightguardsv1_"
    )


def test_claim_store_readiness_binds_path_scope_authorization_and_consumption(
    tmp_path: Path,
) -> None:
    fixture = _fixture_v1(ROOT)
    readiness = _claim_store_readiness_v1(tmp_path)
    assert type(readiness) is OpenRouterClaimStoreReadinessAttestationV1
    assert readiness.mode is OpenRouterLiveSafetyModeV1.SYNTHETIC_OFFLINE
    assert readiness.claim_store_id == openrouter_claim_store_id_v1(tmp_path)
    assert readiness.authorization_evidence_id.startswith(
        "szorclaimstorefixturev1_"
    )

    preflight = _authorized_preflight_v1(
        fixture,
        tmp_path,
        claim_store_readiness=readiness,
    )
    authorization = preflight.authorization
    assert authorization is not None
    assert (
        authorization.claim_store_readiness_attestation_id
        == readiness.attestation_id
    )
    consumption = _consume_authorized_preflight_v1(
        preflight,
        fixture=fixture,
        claim_directory=tmp_path,
        rendered_request=fixture.request,
        transport_policy=fixture.transport,
    )
    assert (
        consumption.claim_store_readiness_attestation_id
        == readiness.attestation_id
    )


def test_preflight_refuses_readiness_attested_for_a_sibling_store(
    tmp_path: Path,
) -> None:
    fixture = _fixture_v1(ROOT)
    readiness = _claim_store_readiness_v1(tmp_path / "store-a")
    result = _preflight_v1(
        fixture,
        tmp_path / "store-b",
        claim_store_readiness=readiness,
    )
    assert result.verdict is OpenRouterOneLiveCallVerdictV1.REFUSED
    assert (
        result.first_failure_code
        is OpenRouterOneLiveCallFailureCodeV1.CLAIM_STORE_UNAVAILABLE
    )


def test_claim_store_readiness_evidence_cannot_cross_authority_scope(
    tmp_path: Path,
) -> None:
    readiness = _claim_store_readiness_v1(tmp_path)
    payload = readiness.model_dump(mode="python")
    payload.update(
        mode=OpenRouterLiveSafetyModeV1.LIVE_JIT,
        attestation_id=None,
    )
    with pytest.raises(ValidationError, match="wrong authority scope"):
        OpenRouterClaimStoreReadinessAttestationV1.model_validate(payload)


def test_preflight_first_failure_precedes_claim_store_resolution(
    tmp_path: Path,
) -> None:
    fixture = _fixture_v1(ROOT)
    readiness = _claim_store_readiness_v1(tmp_path)
    resolver = (
        "backend.dialogues.socrates_zero.openrouter_live_safety_closure_v1."
        "openrouter_claim_store_id_v1"
    )
    with patch(resolver, side_effect=OSError("synthetic unavailable store")):
        invalid_input = _preflight_v1(
            fixture,
            tmp_path,
            p17="not-an-exact-P17-contract",  # type: ignore[arg-type]
            claim_store_readiness=readiness,
        )
        ced_enabled = _preflight_v1(
            fixture,
            tmp_path,
            claim_store_readiness=readiness,
            ced_authority_enabled=True,
        )
        store_unavailable = _preflight_v1(
            fixture,
            tmp_path,
            claim_store_readiness=readiness,
        )
    assert (
        invalid_input.first_failure_code
        is OpenRouterOneLiveCallFailureCodeV1.SAFETY_CONTRACT_MISMATCH
    )
    assert (
        ced_enabled.first_failure_code
        is OpenRouterOneLiveCallFailureCodeV1.CED_AUTHORITY_ENABLED
    )
    assert (
        store_unavailable.first_failure_code
        is OpenRouterOneLiveCallFailureCodeV1.CLAIM_STORE_UNAVAILABLE
    )


def test_zero_quantity_cannot_bypass_p19_safe_unit_price_domain() -> None:
    with pytest.raises(ValidationError):
        OpenRouterP19CostComponentV1(
            charge_class="prompt",
            state=OpenRouterChargeClassStateV1.INCLUDED,
            quantity=0,
            quantity_unit="TOKEN",
            ceiling_picodollars_per_unit=(
                OPENROUTER_MAX_SAFE_PICODOLLARS_V1 + 1
            ),
            subtotal_picodollars=0,
        )


def test_s38_12_rejects_freshness_mutation_and_reuse_in_attested_store() -> None:
    case = next(
        case
        for case in FROZEN_OPENROUTER_LIVE_SAFETY_CASES_V1
        if case.probe == "AUTH_CONSUMPTION_ROLLBACK"
    )
    result = evaluate_openrouter_live_safety_case_v1(
        case,
        repository_root=ROOT,
    )
    assert result.result_matches_expectation
    assert result.actual_failure_code == "CONSUMPTION_ROLLBACK"
    assert (
        result.core_signal
        == "ATTESTED_STORE_REJECTS_FRESHNESS_MUTATION_AND_REUSE"
    )


def test_physical_claim_store_realization_is_explicitly_deferred_to_s7b() -> None:
    field = OpenRouterLiveSafetyArtifactV1.model_fields[
        "physical_claim_store_realization"
    ]
    assert field.default == "S7B_JIT_PENDING"


def test_s6_predecessor_blob_and_artifact_integrity_is_eight_of_eight() -> None:
    integrity = evaluate_openrouter_live_safety_predecessor_integrity_v1(ROOT)
    assert len(integrity.surfaces) == 8
    assert integrity.unchanged_surfaces == 8
    assert integrity.all_unchanged is True
    assert sum(
        surface.digest_algorithm == "GIT_BLOB_SHA1"
        for surface in integrity.surfaces
    ) == 5
    assert sum(
        surface.digest_algorithm == "SHA256"
        for surface in integrity.surfaces
    ) == 3
    assert integrity.integrity_id.startswith(
        "szorlivepredecessorintegrityv1_"
    )


def test_predecessor_unchanged_claim_cannot_disagree_with_digests() -> None:
    with pytest.raises(ValidationError, match="not digest-derived"):
        OpenRouterLiveSafetyPredecessorSurfaceV1(
            relative_path="sealed.txt",
            digest_algorithm="SHA256",
            expected_digest="a" * 64,
            actual_digest="b" * 64,
            unchanged=True,
        )


@pytest.mark.parametrize(
    "leak",
    (
        '{"credential_value":"s7a-secret-sentinel-value"}',
        '{"credential_hash":"' + "a" * 64 + '"}',
        '{"Authorization":"Bearer synthetic"}',
        '{"raw_response_bytes":"synthetic"}',
        '{"response_mutation_payload":"czdhLXNlY3JldC1zZW50aW5lbC12YWx1ZQ=="}',
        '{"canonical_body_json":"duplicate prompt"}',
    ),
)
def test_privacy_scanner_detects_forbidden_artifact_content(leak: str) -> None:
    assert scan_openrouter_live_safety_artifact_privacy_v1(leak) > 0


def test_privacy_scanner_accepts_compact_identity_only_payload() -> None:
    payload = json.dumps(
        {
            "body_sha256": "a" * 64,
            "body_length": 521,
            "credential_available": "YES",
            "authorization_id": "szoronecallauthorizationv1_" + "b" * 64,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    assert scan_openrouter_live_safety_artifact_privacy_v1(payload) == 0


def test_evaluator_source_does_not_embed_the_synthetic_secret() -> None:
    source = (RUNTIME_DIR / "openrouter_live_safety_evaluation_v1.py").read_text(
        encoding="utf-8"
    )
    assert "s7a-secret-sentinel-value" not in source
    assert "sk-or-" not in source


def test_write_once_uses_exclusive_creation_and_preserves_first_bytes(
    tmp_path: Path,
) -> None:
    target = tmp_path / "nested" / "evidence.json"
    payload = b'{"first":true}\n'
    digest = write_once_v1(target, payload)
    assert digest == hashlib.sha256(payload).hexdigest()
    assert target.read_bytes() == payload
    with pytest.raises(ContractValidationError, match="already exists"):
        write_once_v1(target, b'{"second":true}\n')
    assert target.read_bytes() == payload


def test_replay_execution_and_lock_require_three_way_determinism() -> None:
    execution = OpenRouterLiveSafetyReplayExecutionV1(
        source_artifact_id="szorlivesafetyartifactv1_" + "a" * 64,
        source_artifact_sha256="b" * 64,
        recomputed_artifact_id="szorlivesafetyartifactv1_" + "a" * 64,
        recomputed_artifact_sha256="b" * 64,
        semantic_equality=True,
        artifact_id_equality=True,
        byte_identity=True,
    )
    execution_bytes = render_openrouter_live_safety_replay_execution_v1(execution)
    assert execution_bytes.endswith(b"\n")
    lock = OpenRouterLiveSafetyReplayLockV1(
        artifact_id=execution.source_artifact_id,
        artifact_sha256=execution.source_artifact_sha256,
        replay_execution_id=execution.execution_id,
        replay_execution_sha256=hashlib.sha256(execution_bytes).hexdigest(),
        semantic_equality=True,
        artifact_id_equality=True,
        byte_identity=True,
    )
    assert render_openrouter_live_safety_replay_lock_v1(lock).endswith(b"\n")
    with pytest.raises(ValidationError, match="requires semantic, ID and byte"):
        OpenRouterLiveSafetyReplayLockV1(
            artifact_id=execution.source_artifact_id,
            artifact_sha256=execution.source_artifact_sha256,
            replay_execution_id=execution.execution_id,
            replay_execution_sha256=hashlib.sha256(execution_bytes).hexdigest(),
            semantic_equality=True,
            artifact_id_equality=True,
            byte_identity=False,
        )


def test_authoritative_paths_are_additive_and_exact() -> None:
    expected_prefix = (
        "docs/branches/feature-socrates-zero-openrouter-live-safety-closure-v1/"
        "artifacts/"
    )
    paths = (
        OPENROUTER_LIVE_SAFETY_ARTIFACT_RELATIVE_PATH_V1,
        OPENROUTER_LIVE_SAFETY_REPLAY_EXECUTION_RELATIVE_PATH_V1,
        OPENROUTER_LIVE_SAFETY_REPLAY_LOCK_RELATIVE_PATH_V1,
    )
    assert len(set(paths)) == 3
    assert all(path.startswith(expected_prefix) for path in paths)
    assert all("prelive-integration-v1" not in path for path in paths)


def test_builder_and_replay_wiring_require_tripwire_and_three_equalities() -> None:
    builder_source = inspect.getsource(build_openrouter_live_safety_artifact_v1)
    replay_source = inspect.getsource(replay_openrouter_live_safety_v1)
    assert builder_source.index(
        "require_clean_acquisition_boundary_tripwire_v0()"
    ) < builder_source.index("evaluate_openrouter_live_safety_v1")
    assert "_BackgroundStartTripwireV1" in builder_source
    assert "semantic_equality=source == recomputed" in replay_source
    assert "artifact_id_equality=source.artifact_id == recomputed.artifact_id" in (
        replay_source
    )
    assert "byte_identity=source_bytes == recomputed_bytes" in replay_source


def test_no_aggregate_or_replay_runs_at_module_import() -> None:
    tree = ast.parse(
        (RUNTIME_DIR / "openrouter_live_safety_evaluation_v1.py").read_text(
            encoding="utf-8"
        )
    )
    forbidden = {
        "build_openrouter_live_safety_artifact_v1",
        "evaluate_openrouter_live_safety_v1",
        "replay_openrouter_live_safety_v1",
    }
    top_level_calls = {
        node.func.id
        for statement in tree.body
        for node in ast.walk(statement)
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }
    assert top_level_calls.isdisjoint(forbidden)


def test_s7a_modules_are_import_inert_and_do_not_start_background_work(
    tmp_path: Path,
) -> None:
    from backend.dialogues.socrates_zero import acquisition_tripwires

    before = acquisition_tripwires.active_acquisition_boundary_tripwire_v0().snapshot()
    installed_authorization = OpenRouterOneCallAuthorizationV1
    installed_preflight_result = OpenRouterOneLiveCallPreflightResultV1
    probe_names = []
    thread_starts = []
    process_starts = []

    def refuse_thread(*_args, **_kwargs):
        thread_starts.append(True)
        raise AssertionError("import attempted a background thread")

    def refuse_process(*_args, **_kwargs):
        process_starts.append(True)
        raise AssertionError("import attempted a background process")

    try:
        with patch.object(threading.Thread, "start", refuse_thread), patch.object(
            multiprocessing.process.BaseProcess,
            "start",
            refuse_process,
        ):
            for name in S7A_MODULES:
                probe_name = f"backend.dialogues.socrates_zero._s7a_probe_{name[:-3]}"
                spec = importlib.util.spec_from_file_location(
                    probe_name, RUNTIME_DIR / name
                )
                assert spec is not None and spec.loader is not None
                module = importlib.util.module_from_spec(spec)
                sys.modules[probe_name] = module
                probe_names.append(probe_name)
                spec.loader.exec_module(module)
    finally:
        for probe_name in probe_names:
            sys.modules.pop(probe_name, None)
    after = acquisition_tripwires.active_acquisition_boundary_tripwire_v0().assert_clean()
    assert before.total_forbidden_attempts == after.total_forbidden_attempts == 0
    assert thread_starts == [] and process_starts == []
    assert list(tmp_path.iterdir()) == []
    assert OpenRouterOneCallAuthorizationV1 is installed_authorization
    assert OpenRouterOneLiveCallPreflightResultV1 is installed_preflight_result


def test_consumption_refuses_a_self_consistent_forged_authorization_and_result(
    tmp_path: Path,
) -> None:
    fixture = _fixture_v1(ROOT)
    sibling = _fixture_v1(ROOT, request_usd="0.000001000001")
    preflight = _authorized_preflight_v1(fixture, tmp_path)
    authorization = preflight.authorization
    assert authorization is not None

    forged_payload = authorization.model_dump(mode="python")
    forged_payload["price_policy_id"] = sibling.policy.price_policy_id
    forged_payload["authorization_id"] = None
    forged_authorization = OpenRouterOneCallAuthorizationV1.model_validate(
        forged_payload
    )
    forged_result = OpenRouterOneLiveCallPreflightResultV1(
        preflight_execution_id=preflight.preflight_execution_id,
        mode=preflight.mode,
        verdict=preflight.verdict,
        authorization=forged_authorization,
    )
    with pytest.raises(ContractValidationError):
        _consume_authorized_preflight_v1(
            forged_result,
            fixture=fixture,
            claim_directory=tmp_path,
            rendered_request=fixture.request,
            transport_policy=fixture.transport,
        )
    assert list(tmp_path.iterdir()) == []


def test_authorization_identity_has_no_credential_material_field() -> None:
    names = set(OpenRouterOneCallAuthorizationV1.model_fields)
    assert all("credential" not in name for name in names)
