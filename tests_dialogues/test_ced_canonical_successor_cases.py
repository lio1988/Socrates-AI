"""Pre-result locks for invalidated v0 and authoritative Phase 8 corpus v1."""

from __future__ import annotations

import asyncio
import hashlib

import pytest

from backend.dialogues.ced_canonical_successor import (
    CanonicalSuccessorEnvironmentV0,
    canonical_transition_outcome,
    canonical_transition_semantic_snapshot,
)
from backend.dialogues.ced_canonical_successor_cases import (
    INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_CANONICAL_SHA256,
    INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_ID,
    INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_REASON,
    INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_STATUS,
)
from backend.dialogues.ced_canonical_successor_cases_v1 import (
    CANONICAL_SUCCESSOR_CORPUS_VERSION,
    FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1,
    FROZEN_PARITY_FIELD_NAMES,
    RECORDED_OBSERVATION_CASE_SCHEMA_VERSION,
    RecordedObservationFixtureRole,
    canonical_successor_reference_field_digests,
    frozen_corpus_v1_canonical_sha256,
)
from backend.dialogues.ced_canonical_successor_contracts import (
    FORBIDDEN_RECORDED_OBSERVATION_FIELDS,
    HistoricalUsageKnowledge,
    ObservationCaptureKind,
    RecordedCanonicalObservation,
    RecordedObservationCompatibilityError,
    SuccessorUnavailableReason,
)
from backend.dialogues.ced_canonical_successor_manifest import (
    CANONICAL_SUCCESSOR_CAPTURE_SOURCE_REVISION,
    FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST,
    verify_authoritative_recorded_observation,
)
from backend.dialogues.ced_canonical_successor_recording import (
    capture_canonical_opening_observation,
)
from backend.dialogues.ced_canonical_successor_recording_fixtures import (
    build_canonical_recording_root,
)
from backend.dialogues.provider_registry import (
    InvalidJSONProvider,
    SchemaErrorProvider,
    ScriptedMockProvider,
)
from backend.dialogues.socrates_zero.contracts import (
    ActionKind,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    SearchBudget,
    canonical_json,
)
from tests_dialogues.test_socratic_acceptance_contract import EmptySocrates
from tests_dialogues.test_socratic_firewall import Injecting


_CORPUS_ID = (
    "cedobscorpus_b5ebe4b46d2b3ae4fed3faded341c8a2d8ff5f5f254531f000e479bf66b7f8b7"
)
_CORPUS_SHA256 = (
    "06c5eda5ee8c71992cb8b7427794f6d5ab6e44b4f92f0d6f71f4366d5729427c"
)
_MANIFEST_ID = (
    "cedcapturemanifest_ab3391e6fa324dec6ca2d8937ba09bdb7100c373fb7e7c38bb6be53bb0c86a60"
)
_CASE_IDS = {
    "opening-empty-question": "cedobscasev1_10d9781cb3a252ecd759449885081e8a6670996e5fdf7435f5242872c5218905",
    "opening-injection-question": "cedobscasev1_bcd6517311b1a76644b3e533bfb5ca576e7afb84d3a3e05505f59db7c28c2ac6",
    "opening-invalid-json": "cedobscasev1_e5ad44bc15348ea9f82d406afc785c9a70dab9b98582644c585c0216641b901c",
    "opening-schema-error": "cedobscasev1_eba36c3c48cb05f8f7b63b66945ca91a5853da3feeb1bc35d44a0fefda4f0cf3",
    "opening-scripted-mock": "cedobscasev1_7a7cefff8d5cb30ff35e70342016304a7c98835e7c575e2a39b07a4afdc4144a",
}
_DONOR_FACTORIES = {
    "opening-scripted-mock": lambda: ScriptedMockProvider("donor"),
    "opening-empty-question": lambda: EmptySocrates("donor"),
    "opening-injection-question": lambda: Injecting("donor"),
    "opening-invalid-json": InvalidJSONProvider,
    "opening-schema-error": SchemaErrorProvider,
}


def _budget() -> SearchBudget:
    return SearchBudget(
        max_nodes=4,
        max_expansions=3,
        max_model_calls=0,
        max_tool_calls=0,
        max_tokens=0,
        max_cost_microusd=0,
        max_wall_time_ms=0,
        max_depth=1,
    )


def _pending(case_name: str):
    case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(case_name)
    ced, state, adapters = build_canonical_recording_root(
        question=case.recorded_question,
        raw_text=case.raw_text or "",
        session_id=case.recorded_session_id,
    )
    budget = _budget()
    env = CanonicalSuccessorEnvironmentV0()
    capsule = env.capture_capsule(
        ced,
        state,
        budget=budget,
        budget_usage=BudgetUsage(nodes=1),
    )
    pending = env.prepare_transition(
        capsule,
        LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
        budget,
    )
    return ced, state, adapters, pending


def test_old_v0_lineage_is_explicitly_preserved_and_invalidated() -> None:
    assert INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_ID == (
        "cedobscorpus_99a8090204758b4085f6f937d0e36ab77f6fe4f79f3c66ab8416b05c49bfb8e0"
    )
    assert INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_CANONICAL_SHA256 == (
        "a6453fe7fe5bdabaa3258612c040ddc0e93c31214838405fa21afc373194cd8d"
    )
    assert INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_STATUS == (
        "INVALIDATED / SUPERSEDED FOR AUTHORITATIVE PHASE-8 PARITY"
    )
    assert "rebound" in INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_REASON


def test_v1_corpus_manifest_membership_and_byte_lock_are_frozen() -> None:
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1
    manifest = FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST
    assert corpus.corpus_version == CANONICAL_SUCCESSOR_CORPUS_VERSION \
        == "ced-canonical-successor-parity-corpus/v1"
    assert corpus.corpus_id == _CORPUS_ID
    assert corpus.capture_manifest_id == manifest.manifest_id == _MANIFEST_ID
    assert frozen_corpus_v1_canonical_sha256() == _CORPUS_SHA256
    assert tuple(case.case_name for case in corpus.cases) == tuple(sorted(_CASE_IDS))
    assert {case.case_id for case in corpus.cases} == set(_CASE_IDS.values())
    assert {case.fixture_role for case in corpus.cases} == set(
        RecordedObservationFixtureRole
    )
    assert len(manifest.entries) == len(corpus.cases) == 5
    assert all(
        case.schema_version == RECORDED_OBSERVATION_CASE_SCHEMA_VERSION
        and verify_authoritative_recorded_observation(case.observation)
        and tuple(item.name for item in case.reference.parity_field_digests)
        == FROZEN_PARITY_FIELD_NAMES
        for case in corpus.cases
    )


def test_every_frozen_record_recaptures_from_the_actual_canonical_path() -> None:
    for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases:
        donor = _DONOR_FACTORIES[case.case_name]()
        donor_tasks = []
        donor_raw_outputs = []

        async def produce_from_unchanged_donor(task, agent_state):
            donor_tasks.append(task)
            raw_text = await donor._produce_raw_text(task, agent_state)
            donor_raw_outputs.append(raw_text)
            return raw_text

        ced, state, adapters = build_canonical_recording_root(
            question=case.recorded_question,
            raw_text=case.raw_text or "",
            session_id=case.recorded_session_id,
            raw_observation_producer=produce_from_unchanged_donor,
        )
        capture = asyncio.run(
            capture_canonical_opening_observation(
                ced,
                state,
                action=LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
                budget=_budget(),
                budget_usage=BudgetUsage(nodes=1),
                historical_usage=case.observation.historical_usage,
                provenance=case.observation.provenance,
            )
        )
        assert CANONICAL_SUCCESSOR_CAPTURE_SOURCE_REVISION \
            == "4a3ad5cd4b3f3db4b86e13e7b4597ab07a0c893d"
        assert capture.capture_receipt == case.manifest_entry.capture_receipt
        assert capture.observation == case.observation
        assert capture.source_task.task_id
        assert donor_tasks == [capture.source_task]
        assert donor_raw_outputs == [case.raw_text]
        assert capture.provider_response.raw_text == case.raw_text
        assert sum(item.generate_calls for item in adapters) == 1
        reference = case.reference
        status, rejection = canonical_transition_outcome(
            capture.canonical_application
        )
        successor_usage = BudgetUsage(nodes=1).plus(
            BudgetUsage(nodes=1, expansions=1, max_depth_observed=1)
        )
        semantic, projection = canonical_transition_semantic_snapshot(
            capture.authoritative_ced,
            capture.authoritative_state,
            task=capture.task_spec,
            budget=_budget(),
            budget_usage=successor_usage,
            depth=1,
        )
        semantic_digest = hashlib.sha256(
            canonical_json(semantic).encode("utf-8")
        ).hexdigest()
        projection_digest = hashlib.sha256(
            canonical_json(projection.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()
        assert status is reference.status
        assert rejection is reference.canonical_rejection_reason
        assert (
            capture.canonical_application.accepted_move_id
            == reference.accepted_move_id
        )
        assert semantic_digest == reference.successor_semantic_digest
        assert projection.state_id == reference.successor_search_state_v1_id
        assert projection_digest == reference.successor_search_state_v1_digest
        assert (
            canonical_successor_reference_field_digests(semantic)
            == reference.parity_field_digests
        )
        assert (
            capture.offline_fixture_dispatches
            == reference.offline_fixture_dispatches
            == 1
        )


def test_materialize_only_validates_and_exposes_the_captured_observation() -> None:
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1
    before = corpus.model_dump(mode="json")
    forward = {}
    for case in corpus.cases:
        _, _, adapters, pending = _pending(case.case_name)
        observation = case.materialize(pending)
        assert observation == case.observation
        assert observation is not case.observation
        assert verify_authoritative_recorded_observation(observation)
        assert sum(item.generate_calls for item in adapters) == 0
        forward[case.case_name] = observation.observation_id
    reverse = {
        case.case_name: case.materialize(_pending(case.case_name)[3]).observation_id
        for case in reversed(corpus.cases)
    }
    assert forward == reverse
    assert corpus.model_dump(mode="json") == before


def test_materialize_refuses_same_raw_observation_on_another_root() -> None:
    accepted = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-scripted-mock"
    )
    other_pending = _pending("opening-empty-question")[3]
    with pytest.raises(RecordedObservationCompatibilityError) as error:
        accepted.materialize(other_pending)
    assert error.value.reason is SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH


def test_caller_cannot_rebind_raw_bytes_and_keep_manifest_membership() -> None:
    accepted = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-scripted-mock"
    )
    other_pending = _pending("opening-empty-question")[3]
    original = accepted.observation
    rebound = RecordedCanonicalObservation(
        capture_receipt_id=original.capture_receipt_id,
        source_capsule_id=other_pending.source_capsule_id,
        source_execution_id=other_pending.source_capsule.source_execution_id,
        source_configuration_digest=other_pending.source_capsule.configuration_digest,
        action_id=other_pending.selected_action.action_id,
        task_identity=other_pending.canonical_task,
        provider_id=other_pending.expected_provider_id,
        configured_model_id=other_pending.expected_model_id,
        actual_model_id=other_pending.expected_model_id,
        model_config_digest=other_pending.canonical_task.model_config_digest,
        transport_status=original.transport_status,
        raw_text=original.raw_text,
        historical_usage=original.historical_usage,
        provenance=original.provenance,
    )
    assert rebound.raw_text == original.raw_text
    assert rebound.observation_id != original.observation_id
    assert not verify_authoritative_recorded_observation(rebound)


def test_transition_observation_contains_no_reference_truth_or_case_labels() -> None:
    for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases:
        dumped = case.observation.model_dump(mode="json")
        assert "fixture_role" not in dumped
        assert "recorded_question" not in dumped
        assert "reference" not in dumped
        assert "accepted_move_id" not in dumped
        assert "canonical_rejection_reason" not in dumped
        assert not (FORBIDDEN_RECORDED_OBSERVATION_FIELDS & set(dumped))
        assert case.observation.capture_id is None
        assert case.observation.source_task_id is None
        assert case.observation.recorded_response_id is None


def test_historical_usage_and_capture_kind_remain_truthful() -> None:
    for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.cases:
        usage = case.observation.historical_usage
        assert usage.knowledge is HistoricalUsageKnowledge.PARTIAL
        assert (
            usage.model_calls,
            usage.tool_calls,
            usage.tokens,
            usage.cost_microusd,
            usage.wall_time_ms,
            usage.observation_acquisitions,
        ) == (0, 0, 0, 0, None, 1)
        assert case.observation.provenance.capture_kind \
            is ObservationCaptureKind.CANONICAL_RECORDED_TRANSITION


def test_invalidated_v0_materialization_cannot_be_promoted() -> None:
    from backend.dialogues.ced_canonical_successor_cases import (
        FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS,
    )

    old_case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS.cases[0]
    with pytest.raises(ContractValidationError, match="INVALIDATED / SUPERSEDED"):
        old_case.materialize(_pending("opening-empty-question")[3])
