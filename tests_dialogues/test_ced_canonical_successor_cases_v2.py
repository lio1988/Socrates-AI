"""Focused pre-result locks for Phase 8R successor case contracts v2.

The tests in this module are static/data-contract checks.  They do not build or
run the authoritative aggregate, dispatch a provider, or apply a CED move.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.dialogues.ced_canonical_successor_cases_v1 import (
    FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1,
    frozen_corpus_v1_canonical_sha256,
)
from backend.dialogues.ced_canonical_successor_cases_v2 import (
    CASE_SET_SCHEMA_V2,
    COMPATIBILITY_DIAGNOSTICS_SCHEMA_V1,
    EXPECTED_GUARD_IDS,
    EXPECTED_V1_CORPUS_ID,
    EXPECTED_V1_CORPUS_SHA256,
    EXPECTED_V1_REFERENCE_LINKS,
    FAILURE_PRECEDENCE_SCHEMA_V1,
    FAILURE_TAXONOMY_SCHEMA_V1,
    FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1,
    FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1,
    FROZEN_CANONICAL_FAILURE_TAXONOMY_V1,
    FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2,
    FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2,
    FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1,
    FROZEN_CANONICAL_SUCCESSOR_PROBES_V2,
    FROZEN_CANONICAL_VALIDATION_ORDER_V2,
    ORTHOGONAL_PROBE_IDS,
    PARITY_CORPUS_SCHEMA_V2,
    PRECEDENCE_PROBE_IDS,
    PROBE_DESIGN_SCHEMA_V1,
    UNAVAILABLE_PROBE_SCHEMA_V2,
    VALIDATION_ORDER_SCHEMA_V1,
    CanonicalSuccessorParityCaseSetV2,
    CanonicalSuccessorParityCorpusV2,
    CanonicalSuccessorProbeV2,
    CanonicalValidationOrder,
    CompatibilityDiagnosticsContract,
    FailureLayer,
    FailurePrecedenceContract,
    FailurePrecedenceModel,
    FailureTaxonomyContract,
    GuardEvaluationState,
    InvariantState,
    ObservationSubmissionState,
    ProbeClass,
    ProbeDesignContract,
    ProbeInvariantVector,
    ProbeLiteralMutation,
    frozen_corpus_v2_canonical_sha256,
)
from backend.dialogues.ced_canonical_successor_contracts import (
    SuccessorUnavailableReason,
)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SUCCESSOR_SOURCE = (
    _REPO_ROOT / "backend" / "dialogues" / "ced_canonical_successor.py"
)
_CONTRACTS_SOURCE = (
    _REPO_ROOT
    / "backend"
    / "dialogues"
    / "ced_canonical_successor_contracts.py"
)

_EXPECTED_V1_CASE_AND_REFERENCE_IDS = {
    "opening-empty-question": (
        "cedobscasev1_10d9781cb3a252ecd759449885081e8a6670996e5fdf7435f5242872c5218905",
        "cedsuccessorref_85abdbfec328b39cc43630a8cea70ca2696843cfed9e4e6d5ff9b13599072ef2",
    ),
    "opening-injection-question": (
        "cedobscasev1_bcd6517311b1a76644b3e533bfb5ca576e7afb84d3a3e05505f59db7c28c2ac6",
        "cedsuccessorref_33244c4894345a37f56088c6149f8262fbf2e146ccc3b3231ec1aa2535e43e61",
    ),
    "opening-invalid-json": (
        "cedobscasev1_e5ad44bc15348ea9f82d406afc785c9a70dab9b98582644c585c0216641b901c",
        "cedsuccessorref_128626044b00732b181d9658ecd5b4ea8b3a4e0855fc32c214109495e4b91f8f",
    ),
    "opening-schema-error": (
        "cedobscasev1_eba36c3c48cb05f8f7b63b66945ca91a5853da3feeb1bc35d44a0fefda4f0cf3",
        "cedsuccessorref_aa10387f33f114023cc263c2a8ba7cd721c9d46ebe860a63a61a1299de71e3d2",
    ),
    "opening-scripted-mock": (
        "cedobscasev1_7a7cefff8d5cb30ff35e70342016304a7c98835e7c575e2a39b07a4afdc4144a",
        "cedsuccessorref_6efccf0d4a43b1c96845eb71d57fd6fb5f6e5d6b43154e3f49cdaad6832dcc44",
    ),
}

_EXPECTED_GUARDS = (
    "C1",
    "P8",
    "A3",
    "A5",
    "A5",
    "A9",
    "A8",
    "A11",
    "A12",
    "A4",
    "P9",
    "P7",
    "A8",
    "A8",
    "A9",
    "A5",
    "P8",
    "A7",
)

_EXPECTED_REASONS = (
    SuccessorUnavailableReason.INVALID_ROOT,
    SuccessorUnavailableReason.ILLEGAL_ACTION,
    SuccessorUnavailableReason.MISSING_OBSERVATION,
    SuccessorUnavailableReason.INVALID_OBSERVATION,
    SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
    SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH,
    SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
    SuccessorUnavailableReason.OBSERVATION_MODEL_MISMATCH,
    SuccessorUnavailableReason.OBSERVATION_CONFIG_MISMATCH,
    SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN,
    SuccessorUnavailableReason.BUDGET_EXHAUSTED,
    SuccessorUnavailableReason.UNSUPPORTED_ACTION_FAMILY,
    SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
    SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH,
    SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH,
    SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
    SuccessorUnavailableReason.ILLEGAL_ACTION,
    SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
)

_EXPECTED_DIAGNOSTIC_MISMATCH_FIELDS = {
    "p8v2-o01-invalid-root-registration": ((), ()),
    "p8v2-o02-illegal-action-capability": (("required_capabilities",), ()),
    "p8v2-o03-missing-observation": ((), ()),
    "p8v2-o04-invalid-observation-schema": ((), ()),
    "p8v2-o05-tampered-raw-digest": (("raw_output_digest",), ()),
    "p8v2-o06-wrong-task-agent": (
        ("agent_id", "task_semantic_digest"),
        (
            "source_capsule_id",
            "source_configuration_digest",
            "source_execution_id",
        ),
    ),
    "p8v2-o07-wrong-root-question": (
        ("request_semantic_digest", "source_session_semantic_id"),
        ("source_capsule_id", "source_execution_id", "task_semantic_digest"),
    ),
    "p8v2-o08-wrong-exact-model": (
        ("actual_model_id", "configured_model_id"),
        (
            "model_config_digest",
            "source_capsule_id",
            "source_configuration_digest",
            "source_execution_id",
            "task_model_config_digest",
        ),
    ),
    "p8v2-o09-wrong-runtime-timeout": (
        ("source_configuration_digest",),
        ("source_capsule_id", "source_execution_id"),
    ),
    "p8v2-o10-future-label": (("reward",), ()),
    "p8v2-o11-budget-exhausted": (("max_nodes",), ()),
    "p8v2-p01-unsupported-family-vs-legality": (
        ("action_family",),
        ("not_in_legal_set",),
    ),
    "p8v2-p02-provider-roster-context": (
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
    "p8v2-p03-root-plus-provider": (
        (
            "context_digest",
            "request_semantic_digest",
            "source_session_semantic_id",
        ),
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

_EXPECTED_PROBE_FINGERPRINTS = {
    "p8v2-o01-invalid-root-registration": "29155a104236c5d5f3d11ff5d404d70cddab37efe1e2b677263a7299b37537fe",
    "p8v2-o02-illegal-action-capability": "7cb275980a51adfb09bb48c6a7fa4766320e5bbd03e48bc17a2b69464a4bad1b",
    "p8v2-o03-missing-observation": "22e9cc7c34f693f96871a03dd48f5f789bf09c26f9f367a2aa92395d77c3bec5",
    "p8v2-o04-invalid-observation-schema": "54711ac1efec9408d696e122ef79c1310aaf30b5b002494a80e123e4d1d8964f",
    "p8v2-o05-tampered-raw-digest": "93500fa5d1f8d76a6fb824590bf0dd557b6c54ace6d12e33fc0b34894b97e5f4",
    "p8v2-o06-wrong-task-agent": "dafc8c0cae120f7f8353ef566e2c9060fd348d7f5b9a9bbcd967e9b1df940e20",
    "p8v2-o07-wrong-root-question": "644fbb6c3be82720215fdfcd9d36141d8368fd5e0db30705d2c612a588a28e27",
    "p8v2-o08-wrong-exact-model": "d3af214134abef2320af1fa696c0386734cd6c9f252144585f04de438b683a14",
    "p8v2-o09-wrong-runtime-timeout": "aac76d506841fc44f35f86db37ec45ba11580cb15be0c5ab4b78f85448fd8329",
    "p8v2-o10-future-label": "93b3ea24355502e2596e0b182f272f0f028019e4f77dac88f001ae94020eef40",
    "p8v2-o11-budget-exhausted": "ceb7d64e3ca54797c2de737dba457066a15004b388481db32612cfb02e584a0d",
    "p8v2-p01-unsupported-family-vs-legality": "42464f2e5227bdbafc617f45168bdbf681952ff017443bec9ac6912c1ee68374",
    "p8v2-p02-provider-roster-context": "4392d052bf43a69593185af7482bc59d9fc45083c4b954e930cae1348d16f3e3",
    "p8v2-p03-root-plus-provider": "694b55219d1576f480c056deb5ec534a174d790c8a48ca510b19b60691d68fe7",
    "p8v2-p04-task-plus-model": "1c3ab60b4407bdb551f257f8b01e49bd506abb4a6342f04153b7cb00e7487811",
    "p8v2-p05-context-plus-tampered-digest": "0029393aa355cc3b25684058c9dcaa736cca2d5b9cbdd106be212008e7342b53",
    "p8v2-p06-illegal-plus-incompatible-observation": "457382922082d3d9c26a3fb116870bdaa1d297a394c75d2b4c9214c6233798b5",
    "p8v2-p07-caller-rebinding-vs-manifest": "d5c2e08b898cde4ab040d91e4b837b5454789b24615b74265a4bbea48270e71f",
}

_EXPECTED_CONTENT_IDS = {
    "validation_order_id": "cedvalidationorder_2bbd60972e07a9afdc3ca6f2dd344cd891f39dab6f9edb4e92c4ba0552203a54",
    "taxonomy_id": "cedfailuretaxonomy_73bef28686e43b201cafb33fcc536d19a863bd0773592db8aa6867b5a1189cf7",
    "precedence_id": "cedfailureprecedence_4d75632cc9dac55daf59a87142dbd918e6c6573e48afec32f2225db10eaf7d7f",
    "diagnostics_id": "cedcompatdiagnostics_b577167b4199464b250328b58dbc248194076a3f1a9370f8cf28022d56ebd44f",
    "probe_design_id": "cedprobedesign_fd7d21658acea185d164ccb32c726b498c0f7a3aa476b4c1698c82a1847f9e2f",
    "probe_design_fingerprint": "fd7d21658acea185d164ccb32c726b498c0f7a3aa476b4c1698c82a1847f9e2f",
    "case_set_id": "cedparitycasesetv2_3706cb242dd60070acec46d00def5389c62fb90f869d98d932649fe023dc1233",
    "corpus_id": "cedparitycorpusv2_9d7d8563b931f1206c2e685c51d62dfa66b7a5ae66a40254fb63477f9c15524d",
    "corpus_sha256": "9d7d8563b931f1206c2e685c51d62dfa66b7a5ae66a40254fb63477f9c15524d",
}

_EXPECTED_LITERAL_MUTATIONS = {
    "p8v2-o01-invalid-root-registration": (
        ("root.object_registration", "registered_canonical_object", "detached_deep_copy"),
    ),
    "p8v2-o02-illegal-action-capability": (
        ("action.required_capabilities", [], ["not-present-in-root"]),
    ),
    "p8v2-o03-missing-observation": (
        ("observation", "exact_manifest_observation", None),
    ),
    "p8v2-o04-invalid-observation-schema": (
        (
            "observation",
            "exact_manifest_observation",
            {"schema_version": "ced-recorded-observation/v1"},
        ),
    ),
    "p8v2-o05-tampered-raw-digest": (
        (
            "observation.raw_output_digest",
            "912c229dca5ecb8d0ad0736b5e5241dae6e5a3a6ddf9151e323d1bc321d24f62",
            "f" * 64,
        ),
    ),
    "p8v2-o06-wrong-task-agent": (
        ("root.active_agent_id", "phase8-recorded-agent-1", "phase8-recorded-agent-1-v2"),
    ),
    "p8v2-o07-wrong-root-question": (
        (
            "root.question",
            "Is knowledge merely justified true belief?",
            "What is knowledge?",
        ),
    ),
    "p8v2-o08-wrong-exact-model": (
        (
            "root.active_model_id",
            "phase8-recorded-model/1",
            "phase8-recorded-model/1-v2-orthogonal",
        ),
    ),
    "p8v2-o09-wrong-runtime-timeout": (
        ("runtime.provider_timeout_seconds", 30.0, 31.0),
    ),
    "p8v2-o10-future-label": (("observation.reward", None, 1),),
    "p8v2-o11-budget-exhausted": (("budget.max_nodes", 4, 1),),
    "p8v2-p01-unsupported-family-vs-legality": (
        ("action.action_family", "OPENING", "RUN_ELENCHUS"),
    ),
    "p8v2-p02-provider-roster-context": (
        (
            "root.provider_catalog[0].provider_id",
            "phase8-recorded-seat-0",
            "phase8-wrong-seat-0",
        ),
        (
            "root.provider_catalog[1].provider_id",
            "phase8-recorded-seat-1",
            "phase8-wrong-seat-1",
        ),
    ),
    "p8v2-p03-root-plus-provider": (
        (
            "root.question",
            "Is knowledge merely justified true belief?",
            "What is knowledge?",
        ),
        (
            "root.provider_catalog[0].provider_id",
            "phase8-recorded-seat-0",
            "phase8-wrong-seat-0",
        ),
        (
            "root.provider_catalog[1].provider_id",
            "phase8-recorded-seat-1",
            "phase8-wrong-seat-1",
        ),
    ),
    "p8v2-p04-task-plus-model": (
        ("root.active_agent_id", "phase8-recorded-agent-1", "phase8-recorded-agent-1-v2"),
        (
            "root.active_model_id",
            "phase8-recorded-model/1",
            "phase8-recorded-model/1-v2-orthogonal",
        ),
    ),
    "p8v2-p05-context-plus-tampered-digest": (
        (
            "root.question",
            "Is knowledge merely justified true belief?",
            "What is knowledge?",
        ),
        (
            "observation.raw_output_digest",
            "912c229dca5ecb8d0ad0736b5e5241dae6e5a3a6ddf9151e323d1bc321d24f62",
            "f" * 64,
        ),
    ),
    "p8v2-p06-illegal-plus-incompatible-observation": (
        (
            "root.question",
            "Is knowledge merely justified true belief?",
            "What is knowledge?",
        ),
        ("action.required_capabilities", [], ["not-present-in-root"]),
    ),
    "p8v2-p07-caller-rebinding-vs-manifest": (
        ("caller.binding_case", "opening-scripted-mock", "opening-empty-question"),
    ),
}


def _probe_by_id(probe_id: str) -> CanonicalSuccessorProbeV2:
    return next(
        probe
        for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
        if probe.probe_id == probe_id
    )


def _mutation_values(probe: CanonicalSuccessorProbeV2):
    return tuple(
        (
            mutation.path,
            json.loads(mutation.before_json),
            json.loads(mutation.after_json),
        )
        for mutation in probe.literal_mutations
    )


def _vector_symbols(probe_id: str) -> str:
    symbols = {
        InvariantState.PRESERVED: "P",
        InvariantState.INTENTIONALLY_CHANGED: "I",
        InvariantState.DEPENDENTLY_CHANGED: "D",
        InvariantState.NOT_APPLICABLE: "N",
    }
    vector = _probe_by_id(probe_id).invariant_vector
    return "".join(
        symbols[getattr(vector, field)] for field in ProbeInvariantVector.model_fields
    )


def _assert_text_order(text: str, anchors: tuple[str, ...]) -> None:
    offsets = tuple(text.index(anchor) for anchor in anchors)
    assert offsets == tuple(sorted(offsets))
    assert len(offsets) == len(set(offsets))


def test_semantic_schema_versions_are_exact_and_bound_to_frozen_contracts() -> None:
    assert (
        FAILURE_TAXONOMY_SCHEMA_V1,
        FAILURE_PRECEDENCE_SCHEMA_V1,
        PROBE_DESIGN_SCHEMA_V1,
        COMPATIBILITY_DIAGNOSTICS_SCHEMA_V1,
        UNAVAILABLE_PROBE_SCHEMA_V2,
        CASE_SET_SCHEMA_V2,
        PARITY_CORPUS_SCHEMA_V2,
        VALIDATION_ORDER_SCHEMA_V1,
    ) == (
        "ced-canonical-transition-failure-taxonomy/v1",
        "ced-canonical-transition-failure-precedence/v1",
        "ced-canonical-successor-probe-design/v1",
        "ced-canonical-successor-compatibility-diagnostics/v1",
        "ced-canonical-successor-unavailable-probe/v2",
        "ced-canonical-successor-parity-case-set/v2",
        "ced-canonical-successor-parity-corpus/v2",
        "ced-canonical-successor-validation-order/v1",
    )
    assert FROZEN_CANONICAL_FAILURE_TAXONOMY_V1.schema_version == FAILURE_TAXONOMY_SCHEMA_V1
    assert FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1.schema_version == FAILURE_PRECEDENCE_SCHEMA_V1
    assert FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1.schema_version == PROBE_DESIGN_SCHEMA_V1
    assert FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1.schema_version == COMPATIBILITY_DIAGNOSTICS_SCHEMA_V1
    assert FROZEN_CANONICAL_VALIDATION_ORDER_V2.schema_version == VALIDATION_ORDER_SCHEMA_V1
    assert FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2.schema_version == CASE_SET_SCHEMA_V2
    assert FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2.schema_version == PARITY_CORPUS_SCHEMA_V2
    assert {
        probe.schema_version for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
    } == {UNAVAILABLE_PROBE_SCHEMA_V2}


def test_validation_order_is_exactly_c1_through_a22_with_real_source_anchors() -> None:
    order = FROZEN_CANONICAL_VALIDATION_ORDER_V2
    assert len(order.steps) == 44
    assert tuple(step.guard_id for step in order.steps) == EXPECTED_GUARD_IDS
    assert tuple(step.order_index for step in order.steps) == tuple(range(1, 45))
    assert EXPECTED_GUARD_IDS == (
        *(f"C{index}" for index in range(1, 12)),
        *(f"P{index}" for index in range(1, 11)),
        *(f"A{index}" for index in range(1, 15)),
        "A15a",
        "A15b",
        *(f"A{index}" for index in range(16, 23)),
    )
    by_id = {step.guard_id: step for step in order.steps}
    assert {by_id[f"C{index}"].source_ref for index in range(1, 12)} == {
        "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.capture_capsule"
    }
    assert {by_id[f"P{index}"].source_ref for index in range(1, 11)} == {
        "ced_canonical_successor.py:CanonicalSuccessorEnvironmentV0.prepare_transition"
    }
    assert by_id["A3"].source_ref.endswith("._validated_observation")
    assert by_id["A7"].source_ref.endswith(".apply_observation")
    assert {
        by_id[f"A{index}"].source_ref for index in range(8, 14)
    } == {
        "ced_canonical_successor_contracts.py:validate_recorded_observation_compatibility"
    }
    assert by_id["A15a"].source_ref == "ced_canonical_successor.py:_rehydrate"
    assert by_id["A15b"].source_ref.endswith(".apply_observation")
    assert by_id["A16"].source_ref == "provider_registry.py:parse_and_validate_move"
    assert by_id["A17"].source_ref == "ced.py:CEDOrchestrator._screen_socratic_move"
    assert by_id["A18"].source_ref == "ced.py:CEDOrchestrator._apply_registry_response"
    assert by_id["A19"].source_ref == "ced.py:CEDOrchestrator._finalize_registry_phase"
    assert by_id["A20"].source_ref == "ced_canonical_successor.py:canonical_transition_outcome"
    assert by_id["C2"].failure_result == "BUDGET_EXHAUSTED"
    assert by_id["P7"].failure_result == "UNSUPPORTED_ACTION_FAMILY"
    assert by_id["P8"].failure_result == "ILLEGAL_ACTION"
    assert by_id["A13"].failure_result == "ROOT_CONTEXT_MISMATCH"
    assert by_id["A14"].failure_result == "CANONICAL_PROCESSING_REJECTED"
    assert by_id["A15a"].failure_result == "REHYDRATION_CONTRACT_ERROR_PROPAGATES"


def test_source_order_anchors_remain_monotonic_in_runtime_source() -> None:
    successor = _SUCCESSOR_SOURCE.read_text(encoding="utf-8")
    prepare = successor[successor.index("    def prepare_transition(") :]
    _assert_text_order(
        prepare,
        (
            "self._validate_capsule(capsule)",
            "if budget != capsule.budget:",
            "LegalAction.model_validate_json(action.model_dump_json())",
            "if action.kind is not ActionKind.ASK_SOCRATIC_QUESTION:",
            "legal = tuple(self._constitution.legal_actions",
            "self._constitution.validate_action",
            "binding = next(",
            "budget.enforce(",
            "return PendingCanonicalTransition(",
        ),
    )
    normalize_start = successor.index("    def _validated_observation(")
    normalize_end = successor.index("    def apply_observation(", normalize_start)
    normalize = successor[normalize_start:normalize_end]
    _assert_text_order(
        normalize,
        (
            "if value is None:",
            "if isinstance(value, BaseModel):",
            "raw_mapping = value if isinstance(value, Mapping) else None",
            "try:",
            "except ValidationError:",
            "return observation, None",
        ),
    )
    apply = successor[successor.index("    def apply_observation(") :]
    _assert_text_order(
        apply,
        (
            "pending transition contains non-contract fields",
            "replayed_pending = self.prepare_transition(",
            "validated, invalid_reason = self._validated_observation(observation)",
            "_structured_future_fields(validated.raw_text)",
            "verify_authoritative_recorded_observation(validated)",
            "validate_recorded_observation_compatibility(pending, validated)",
            "validated.transport_status is ObservationTransportStatus.REFUSED",
            "ced, state = _rehydrate(pending.source_capsule)",
            "move, status, error = parse_and_validate_move(",
            "application = ced._apply_registry_response(",
            "ced._finalize_registry_phase(",
            "status, rejection = canonical_transition_outcome(application)",
            "if successor_configuration_digest !=",
        ),
    )
    contracts = _CONTRACTS_SOURCE.read_text(encoding="utf-8")
    compatibility = contracts[
        contracts.index("def validate_recorded_observation_compatibility(") :
        contracts.index("class CanonicalTransitionReceipt", contracts.index("def validate_recorded_observation_compatibility("))
    ]
    _assert_text_order(
        compatibility,
        (
            "root_values = {",
            "task_values = {",
            "if observation.provider_id != pending.expected_provider_id:",
            "model_mismatches = []",
            "config_mismatches = []",
            "lineage_mismatches = []",
        ),
    )


def test_probe_membership_counts_human_ids_and_fingerprints_are_exact() -> None:
    probes = FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
    design = FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1
    case_set = FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2
    corpus = FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2
    assert len(ORTHOGONAL_PROBE_IDS) == 11
    assert len(PRECEDENCE_PROBE_IDS) == 7
    assert len(probes) == 18
    assert tuple(probe.probe_id for probe in probes) == (
        ORTHOGONAL_PROBE_IDS + PRECEDENCE_PROBE_IDS
    )
    assert tuple(probe.probe_class for probe in probes[:11]) == (
        ProbeClass.ORTHOGONAL,
    ) * 11
    assert tuple(probe.probe_class for probe in probes[11:]) == (
        ProbeClass.PRECEDENCE,
    ) * 7
    assert design.orthogonal_probe_ids == ORTHOGONAL_PROBE_IDS
    assert design.precedence_probe_ids == PRECEDENCE_PROBE_IDS
    assert case_set.positive_reference_count == 5
    assert case_set.orthogonal_probe_count == 11
    assert case_set.precedence_probe_count == 7
    assert case_set.total_case_count == 23
    assert corpus.total_membership == 23
    assert corpus.human_probe_ids == case_set.human_probe_ids
    assert corpus.probe_fingerprints == case_set.probe_fingerprints
    assert len(set(case_set.probe_fingerprints)) == 18
    assert {
        probe.probe_id: probe.probe_fingerprint for probe in probes
    } == _EXPECTED_PROBE_FINGERPRINTS
    assert all(
        probe.probe_fingerprint != probe.probe_id
        and len(probe.probe_fingerprint or "") == 64
        for probe in probes
    )


def test_probe_guards_reasons_literals_and_unreachable_checks_are_exact() -> None:
    probes = FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
    assert tuple(probe.expected_guard_id for probe in probes) == _EXPECTED_GUARDS
    assert tuple(probe.expected_primary_reason for probe in probes) == _EXPECTED_REASONS
    assert {
        probe.probe_id: (
            probe.expected_primary_mismatch_fields,
            probe.advisory_or_dominated_mismatch_fields,
        )
        for probe in probes
    } == _EXPECTED_DIAGNOSTIC_MISMATCH_FIELDS
    assert set(_EXPECTED_LITERAL_MUTATIONS) == {probe.probe_id for probe in probes}
    for probe in probes:
        assert _mutation_values(probe) == _EXPECTED_LITERAL_MUTATIONS[probe.probe_id]
        target_index = EXPECTED_GUARD_IDS.index(probe.expected_guard_id)
        states = tuple(item.state for item in probe.guard_evaluations)
        assert tuple(item.guard_id for item in probe.guard_evaluations) == EXPECTED_GUARD_IDS
        assert states[target_index] is GuardEvaluationState.EVALUATED_FAILED
        assert all(
            state is GuardEvaluationState.EVALUATED_PASSED
            for state in states[:target_index]
        )
        assert probe.unreachable_guard_ids == EXPECTED_GUARD_IDS[target_index + 1 :]
        assert all(
            state
            in {
                GuardEvaluationState.NOT_EVALUATED,
                GuardEvaluationState.NOT_CONSTRUCTED,
            }
            for state in states[target_index + 1 :]
        )
        assert probe.canonical_parser_reached is False
        assert probe.ced_application_reached is False
    assert json.loads(
        _probe_by_id("p8v2-o05-tampered-raw-digest")
        .literal_mutations[0]
        .before_json
    ) == FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-scripted-mock"
    ).observation.raw_output_digest
    assert _probe_by_id("p8v2-o03-missing-observation").observation_submission \
        is ObservationSubmissionState.NOT_SUBMITTED
    assert _probe_by_id(
        "p8v2-p06-illegal-plus-incompatible-observation"
    ).observation_submission is ObservationSubmissionState.NOT_SUBMITTED
    assert _probe_by_id(
        "p8v2-p07-caller-rebinding-vs-manifest"
    ).structured_future_scan_reached is True


def test_exact_fifteen_field_invariant_vectors_lock_critical_dependencies() -> None:
    assert tuple(ProbeInvariantVector.model_fields) == (
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
    expected = {
        "p8v2-o01-invalid-root-registration": "INNPPPPPPPPPNPP",
        "p8v2-o02-illegal-action-capability": "PPNPPPIPPPPPPPP",
        "p8v2-o03-missing-observation": "PPPPPPPINPPPPPP",
        "p8v2-o04-invalid-observation-schema": "PPPPPPPNIPPPPPP",
        "p8v2-o05-tampered-raw-digest": "PPPPPPPIPPPPPPP",
        "p8v2-o06-wrong-task-agent": "DDDIPPPPPPPDDPP",
        "p8v2-o07-wrong-root-question": "IDDDPPPPPPPPDPP",
        "p8v2-o08-wrong-exact-model": "DDDDPPPPPPIDDPP",
        "p8v2-o09-wrong-runtime-timeout": "DDDPPPPPPPPIDPP",
        "p8v2-o10-future-label": "PPPPPPPPPPPPPIP",
        "p8v2-o11-budget-exhausted": "DDNPPPPPPPPPDPI",
        "p8v2-p01-unsupported-family-vs-legality": "PPNPPPIPPPPPPPP",
        "p8v2-p02-provider-roster-context": "DDDDDIPPPDPDDPP",
        "p8v2-p03-root-plus-provider": "IDDDDIPPPDPDDPP",
        "p8v2-p04-task-plus-model": "DDDIPPPPPPIDDPP",
        "p8v2-p05-context-plus-tampered-digest": "IDDDPPPIPPPPDPP",
        "p8v2-p06-illegal-plus-incompatible-observation": "IDNDPPIPPPPPDPP",
        "p8v2-p07-caller-rebinding-vs-manifest": "IIIIPPPIPIIDIPP",
    }
    assert {probe.probe_id for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2} \
        == set(expected)
    assert {
        probe_id: _vector_symbols(probe_id) for probe_id in expected
    } == expected
    assert all(
        sum(
            getattr(probe.invariant_vector, field)
            is InvariantState.INTENTIONALLY_CHANGED
            for field in ProbeInvariantVector.model_fields
        )
        == 1
        for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2[:11]
    )
    diagnostics = FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1
    assert diagnostics.task_semantic_guard_fields == (
        "phase",
        "round_number",
        "slot_index",
        "attempt_index",
        "agent_id",
        "role",
        "task_kind",
        "task_semantic_digest",
    )
    assert diagnostics.root_context_guard_fields == (
        "source_session_semantic_id",
        "context_digest",
        "request_semantic_digest",
    )


def test_four_layer_taxonomy_and_model_a_precedence_preserve_ced_ownership() -> None:
    taxonomy = FROZEN_CANONICAL_FAILURE_TAXONOMY_V1
    precedence = FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1
    entries = {entry.code: entry for entry in taxonomy.entries}
    assert {entry.layer for entry in taxonomy.entries} == set(FailureLayer)
    assert {
        code for code, entry in entries.items() if entry.layer is FailureLayer.PREPARATION
    } == {
        "INVALID_ROOT",
        "ILLEGAL_ACTION",
        "UNSUPPORTED_ACTION_FAMILY",
        "BUDGET_EXHAUSTED",
    }
    assert {
        code
        for code, entry in entries.items()
        if entry.layer is FailureLayer.OBSERVATION_BINDING
    } == {
        "MISSING_OBSERVATION",
        "INVALID_OBSERVATION",
        "INVALID_OBSERVATION_IDENTITY",
        "FUTURE_LABEL_FORBIDDEN",
        "ROOT_CONTEXT_MISMATCH",
        "OBSERVATION_TASK_MISMATCH",
        "OBSERVATION_PROVIDER_MISMATCH",
        "OBSERVATION_MODEL_MISMATCH",
        "OBSERVATION_CONFIG_MISMATCH",
    }
    assert entries["BUDGET_EXHAUSTED"].governing_guard_ids == ("C2", "P9")
    assert entries["ILLEGAL_ACTION"].governing_guard_ids == ("P6", "P8")
    assert entries["UNSUPPORTED_ACTION_FAMILY"].governing_guard_ids == ("P7",)
    assert entries["ROOT_CONTEXT_MISMATCH"].governing_guard_ids == ("A8", "A13")
    assert entries["CANONICAL_PROCESSING_REJECTED"].governing_guard_ids == (
        "A14",
        "A15b",
        "A19",
        "A21",
    )
    assert all(
        entry.owner == "CED canonical parser and application"
        for entry in taxonomy.entries
        if entry.layer is FailureLayer.APPLIED
    )
    assert precedence.selected_model is FailurePrecedenceModel.FIRST_CANONICAL_GUARD_WINS
    assert precedence.runtime_semantic_change_required is False
    assert precedence.compatibility_guard_order == (
        "A8",
        "A9",
        "A10",
        "A11",
        "A12",
        "A13",
    )
    assert "first failing canonical guard" in precedence.primary_rule.lower()
    assert "cannot replace" in precedence.advisory_rule.lower()


def test_private_provider_mismatch_is_defined_but_excluded_from_probe_corpus() -> None:
    taxonomy = {
        entry.code: entry for entry in FROZEN_CANONICAL_FAILURE_TAXONOMY_V1.entries
    }
    provider = taxonomy["OBSERVATION_PROVIDER_MISMATCH"]
    assert provider.governing_guard_ids == ("A10",)
    assert provider.independently_reachable is False
    assert FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1.provider_mismatch_probe_excluded
    assert all(
        probe.expected_primary_reason
        is not SuccessorUnavailableReason.OBSERVATION_PROVIDER_MISMATCH
        for probe in FROZEN_CANONICAL_SUCCESSOR_PROBES_V2
    )
    diagnostics = FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1
    assert "private expected provider binding" in diagnostics.provider_mismatch_reachability
    assert "excluded from the orthogonal corpus" in diagnostics.provider_mismatch_reachability
    assert "may call json.loads" in diagnostics.parser_boundary
    assert "never passed to canonical parse_and_validate_move" in diagnostics.parser_boundary


def test_v2_references_exact_frozen_v1_ids_and_sha_without_copying_payloads() -> None:
    v1 = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1
    case_set = FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2
    corpus = FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2
    assert EXPECTED_V1_CORPUS_ID == (
        "cedobscorpus_b5ebe4b46d2b3ae4fed3faded341c8a2d8ff5f5f254531f000e479bf66b7f8b7"
    )
    assert EXPECTED_V1_CORPUS_SHA256 == (
        "06c5eda5ee8c71992cb8b7427794f6d5ab6e44b4f92f0d6f71f4366d5729427c"
    )
    assert v1.corpus_id == case_set.predecessor_corpus_id == corpus.predecessor_corpus_id
    assert frozen_corpus_v1_canonical_sha256() \
        == case_set.predecessor_canonical_sha256 \
        == corpus.predecessor_canonical_sha256 \
        == EXPECTED_V1_CORPUS_SHA256
    assert case_set.positive_case_references == EXPECTED_V1_REFERENCE_LINKS
    assert corpus.frozen_v1_references == EXPECTED_V1_REFERENCE_LINKS
    assert len(case_set.positive_case_references) == 5
    assert {
        link.case_name: (link.case_id, link.reference_id)
        for link in case_set.positive_case_references
    } == _EXPECTED_V1_CASE_AND_REFERENCE_IDS
    assert {
        case.case_name: (case.case_id, case.reference.reference_id)
        for case in v1.cases
    } == _EXPECTED_V1_CASE_AND_REFERENCE_IDS
    assert all(
        tuple(type(link).model_fields) == ("case_name", "case_id", "reference_id")
        and not hasattr(link, "observation")
        and not hasattr(link, "manifest_entry")
        for link in case_set.positive_case_references
    )
    reference_only_json = corpus.model_dump_json()
    assert "recorded_question" not in reference_only_json
    assert "raw_text" not in reference_only_json
    assert "manifest_entry" not in reference_only_json
    assert "observation_id" not in reference_only_json


def test_derived_semantic_ids_round_trip_and_tampering_is_refused() -> None:
    validation_order = FROZEN_CANONICAL_VALIDATION_ORDER_V2
    taxonomy = FROZEN_CANONICAL_FAILURE_TAXONOMY_V1
    precedence = FROZEN_CANONICAL_FAILURE_PRECEDENCE_V1
    diagnostics = FROZEN_CANONICAL_COMPATIBILITY_DIAGNOSTICS_V1
    design = FROZEN_CANONICAL_SUCCESSOR_PROBE_DESIGN_V1
    case_set = FROZEN_CANONICAL_SUCCESSOR_PARITY_CASE_SET_V2
    corpus = FROZEN_CANONICAL_SUCCESSOR_PARITY_CORPUS_V2
    assert CanonicalValidationOrder.model_validate(
        validation_order.model_dump(mode="json")
    ) == validation_order
    assert FailureTaxonomyContract.model_validate(
        taxonomy.model_dump(mode="json")
    ) == taxonomy
    assert FailurePrecedenceContract.model_validate(
        precedence.model_dump(mode="json")
    ) == precedence
    assert CompatibilityDiagnosticsContract.model_validate(
        diagnostics.model_dump(mode="json")
    ) == diagnostics
    assert ProbeDesignContract.model_validate(design.model_dump(mode="json")) == design
    assert CanonicalSuccessorParityCaseSetV2.model_validate(
        case_set.model_dump(mode="json")
    ) == case_set
    assert CanonicalSuccessorParityCorpusV2.model_validate(
        corpus.model_dump(mode="json")
    ) == corpus
    assert validation_order.validation_order_id.startswith("cedvalidationorder_")
    assert taxonomy.taxonomy_id.startswith("cedfailuretaxonomy_")
    assert precedence.precedence_id.startswith("cedfailureprecedence_")
    assert diagnostics.diagnostics_id.startswith("cedcompatdiagnostics_")
    assert design.probe_design_id.startswith("cedprobedesign_")
    assert case_set.case_set_id.startswith("cedparitycasesetv2_")
    assert corpus.corpus_id.startswith("cedparitycorpusv2_")
    assert {
        "validation_order_id": validation_order.validation_order_id,
        "taxonomy_id": taxonomy.taxonomy_id,
        "precedence_id": precedence.precedence_id,
        "diagnostics_id": diagnostics.diagnostics_id,
        "probe_design_id": design.probe_design_id,
        "probe_design_fingerprint": design.probe_design_fingerprint,
        "case_set_id": case_set.case_set_id,
        "corpus_id": corpus.corpus_id,
        "corpus_sha256": frozen_corpus_v2_canonical_sha256(),
    } == _EXPECTED_CONTENT_IDS
    assert corpus.corpus_id.removeprefix("cedparitycorpusv2_") \
        == frozen_corpus_v2_canonical_sha256()

    probe_payload = FROZEN_CANONICAL_SUCCESSOR_PROBES_V2[0].model_dump(mode="json")
    probe_payload["probe_fingerprint"] = "0" * 64
    with pytest.raises(ValidationError, match="probe_fingerprint"):
        CanonicalSuccessorProbeV2.model_validate(probe_payload)

    order_payload = validation_order.model_dump(mode="json")
    order_payload["steps"][0], order_payload["steps"][1] = (
        order_payload["steps"][1],
        order_payload["steps"][0],
    )
    with pytest.raises(ValidationError, match="canonical validation order"):
        CanonicalValidationOrder.model_validate(order_payload)

    case_set_payload = case_set.model_dump(mode="json")
    case_set_payload["predecessor_canonical_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="exact v1 SHA"):
        CanonicalSuccessorParityCaseSetV2.model_validate(case_set_payload)

    corpus_payload = corpus.model_dump(mode="json")
    corpus_payload["human_probe_ids"][0] = "p8v2-o99-invented"
    with pytest.raises(ValidationError, match="human probe membership"):
        CanonicalSuccessorParityCorpusV2.model_validate(corpus_payload)

    with pytest.raises(ValidationError, match="canonical JSON"):
        ProbeLiteralMutation(
            path="x",
            before_json='{ "b": 1, "a": 2 }',
            after_json="null",
        )

    with pytest.raises(ValidationError, match="frozen"):
        corpus.total_membership = 24
