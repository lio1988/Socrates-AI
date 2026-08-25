"""Pre-result locks for the Phase 8 recorded-observation corpus."""

from __future__ import annotations

import asyncio
import hashlib

from backend.dialogues.ced_canonical_successor_cases import (
    CANONICAL_SUCCESSOR_CORPUS_VERSION,
    FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS,
    RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION,
    RecordedObservationFixtureRole,
    frozen_corpus_canonical_json,
)
from backend.dialogues.ced_canonical_successor_contracts import (
    FORBIDDEN_RECORDED_OBSERVATION_FIELDS,
    CanonicalTaskIdentity,
    HistoricalUsageKnowledge,
    ObservationCaptureKind,
    PendingCanonicalTransition,
    validate_recorded_observation_compatibility,
)
from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    ProviderStatus,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    InvalidJSONProvider,
    SchemaErrorProvider,
    ScriptedMockProvider,
)
from backend.dialogues.socrates_zero.contracts import (
    ActionKind,
    BudgetUsage,
    LegalAction,
    SearchBudget,
)
from tests_dialogues.test_phase8c_registry_session import Q as GETTIER_QUESTION
from tests_dialogues.test_provider_adapters import _task as provider_fixture_task
from tests_dialogues.test_socratic_acceptance_contract import EmptySocrates
from tests_dialogues.test_socratic_firewall import Injecting, TASK as ORDERING_TASK


_CORPUS_ID = (
    "cedobscorpus_"
    "99a8090204758b4085f6f937d0e36ab77f6fe4f79f3c66ab8416b05c49bfb8e0"
)
_CORPUS_SHA256 = (
    "a6453fe7fe5bdabaa3258612c040ddc0e93c31214838405fa21afc373194cd8d"
)
_CASE_IDS = {
    "opening-empty-question": (
        "cedobscase_"
        "3d38a99392382b995f1581dd787e222585e2761f883c021f79a4216b65095855"
    ),
    "opening-injection-question": (
        "cedobscase_"
        "bd3fa1c8905f3d070b9c198a9a7adc3833e8f9a1b0ad2802f62d537263f7f893"
    ),
    "opening-invalid-json": (
        "cedobscase_"
        "a5a1e28f0c0ee35a3b576fa1101e7b286928a6958d0fe519ea020c5c01b6e2d6"
    ),
    "opening-schema-error": (
        "cedobscase_"
        "681027a1ffb0cec07643a6d99a31fa5d4c076feb9ca02f417510b731c01465f7"
    ),
    "opening-scripted-mock": (
        "cedobscase_"
        "c06708a4115205eefa5d072588528082621a3588781ddb51a087bd7d0c6e9bab"
    ),
}


def _pending() -> PendingCanonicalTransition:
    action = LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION)
    task = CanonicalTaskIdentity(
        phase=DialogPhase.OPENING,
        round_number=0,
        slot_index=0,
        attempt_index=0,
        agent_id="phase8-corpus-agent",
        role=AgentRole.SOCRATES,
        task_kind=TaskKind.SOCRATIC_QUESTION,
        task_semantic_digest="1" * 64,
        context_digest="2" * 64,
        request_semantic_digest="3" * 64,
        model_config_digest="4" * 64,
    )
    return PendingCanonicalTransition(
        source_capsule_id="phase8-corpus-capsule",
        source_branch_id="phase8-corpus-branch",
        root_state_v1_id="phase8-corpus-root-state",
        selected_action=action,
        complete_legal_action_ids=(action.action_id,),
        canonical_task=task,
        expected_provider_id="phase8-corpus-provider",
        expected_model_id="mock/phase8-corpus-provider",
        budget=SearchBudget(
            max_nodes=2,
            max_expansions=1,
            max_model_calls=0,
            max_tool_calls=0,
            max_tokens=0,
            max_cost_microusd=0,
            max_wall_time_ms=0,
            max_depth=1,
        ),
        budget_before=BudgetUsage(nodes=1),
        canonical_processor_ids=(
            "CEDOrchestrator._apply_registry_response",
            "CEDOrchestrator._finalize_registry_phase",
        ),
    )


def _capture_raw(case_name: str):
    case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS.case(case_name)
    providers = {
        "opening-scripted-mock": ScriptedMockProvider("phase8-fixture"),
        "opening-empty-question": EmptySocrates("phase8-fixture"),
        "opening-injection-question": Injecting("phase8-fixture"),
        "opening-invalid-json": InvalidJSONProvider(),
        "opening-schema-error": SchemaErrorProvider(),
    }
    provider = providers[case_name]
    assert provider.is_fake is True
    task = AgentTask(
        session_id="phase8-corpus-capture",
        agent_id="phase8-corpus-agent",
        role=AgentRole.SOCRATES,
        phase=DialogPhase.OPENING,
        question=case.recorded_question,
        task_kind=TaskKind.SOCRATIC_QUESTION,
        slot_index=0,
        attempt_index=0,
    )
    state = AgentState(
        agent_id=task.agent_id,
        primary_role=AgentRole.SOCRATES,
        assigned_role=AgentRole.SOCRATES,
    )
    return asyncio.run(provider.generate_agent_move(task, state))


def test_corpus_version_identity_order_and_exact_frozen_roles():
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS
    assert corpus.corpus_version == CANONICAL_SUCCESSOR_CORPUS_VERSION \
        == "ced-canonical-successor-parity-corpus/v0"
    assert corpus.corpus_id == _CORPUS_ID
    assert len(corpus.cases) == 5
    assert tuple(case.case_name for case in corpus.cases) == tuple(
        sorted(_CASE_IDS)
    )
    assert {case.case_id for case in corpus.cases} == set(_CASE_IDS.values())
    assert {case.fixture_role for case in corpus.cases} == set(
        RecordedObservationFixtureRole
    )
    assert all(
        case.schema_version == RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION
        for case in corpus.cases
    )


def test_corpus_has_a_pre_result_canonical_byte_lock():
    rendered = frozen_corpus_canonical_json()
    assert hashlib.sha256(rendered.encode("utf-8")).hexdigest() == _CORPUS_SHA256


def test_harness_roots_are_the_exact_existing_fixture_questions():
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS
    assert corpus.case("opening-scripted-mock").recorded_question == GETTIER_QUESTION
    assert corpus.case("opening-empty-question").recorded_question \
        == "What is knowledge?"
    assert corpus.case("opening-injection-question").recorded_question \
        == ORDERING_TASK
    assert corpus.case("opening-invalid-json").recorded_question \
        == provider_fixture_task().question == "Q?"
    assert corpus.case("opening-schema-error").recorded_question == "Q?"


def test_exact_raw_text_is_reproducible_from_existing_offline_donors():
    expected_statuses = {
        "opening-scripted-mock": ProviderStatus.OK,
        "opening-empty-question": ProviderStatus.OK,
        "opening-injection-question": ProviderStatus.OK,
        "opening-invalid-json": ProviderStatus.INVALID_JSON,
        "opening-schema-error": ProviderStatus.SCHEMA_ERROR,
    }
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS
    for case in corpus.cases:
        response = _capture_raw(case.case_name)
        assert response.raw_text == case.raw_text
        assert response.status is expected_statuses[case.case_name]


def test_historical_unknowns_are_never_coerced_to_zero():
    for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS.cases:
        usage = case.historical_usage
        assert usage.knowledge is HistoricalUsageKnowledge.PARTIAL
        assert (
            usage.model_calls,
            usage.tool_calls,
            usage.tokens,
            usage.cost_microusd,
            usage.wall_time_ms,
            usage.observation_acquisitions,
        ) == (0, 0, 0, 0, None, 1)


def test_materialization_binds_only_pending_semantics_and_real_raw_truth():
    pending = _pending()
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS
    observations = tuple(case.materialize(pending) for case in corpus.cases)

    assert len({item.observation_id for item in observations}) == len(observations)
    for case, observation in zip(corpus.cases, observations):
        validate_recorded_observation_compatibility(pending, observation)
        assert observation.raw_text == case.raw_text
        assert observation.provenance.source_artifact_digest \
            == case.source_artifact_digest
        assert observation.provenance.source_revision \
            == CANONICAL_SUCCESSOR_CORPUS_VERSION
        assert observation.capture_id is None
        assert observation.source_task_id is None
        assert observation.recorded_response_id is None
        assert observation.recorded_request_digest is None


def test_evaluator_role_and_root_question_never_enter_observation_schema():
    pending = _pending()
    for case in FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS.cases:
        source_payload = case.source_semantic_payload()
        assert "fixture_role" not in source_payload
        observation = case.materialize(pending)
        dumped = observation.model_dump(mode="json")
        assert "fixture_role" not in dumped
        assert "recorded_question" not in dumped
        assert not (FORBIDDEN_RECORDED_OBSERVATION_FIELDS & set(dumped))


def test_unavailable_random_capture_ids_are_not_fabricated_or_semantic():
    case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS.cases[0]
    pending = _pending()
    without_audit_ids = case.materialize(pending)
    with_audit_ids = case.materialize(
        pending,
        capture_id="audit-capture-only",
        source_task_id="audit-task-only",
        recorded_response_id="audit-response-only",
        recorded_request_digest="5" * 64,
    )
    assert without_audit_ids.observation_id == with_audit_ids.observation_id
    assert without_audit_ids.identity_payload() == with_audit_ids.identity_payload()
    assert without_audit_ids.model_dump(mode="json") != with_audit_ids.model_dump(
        mode="json"
    )


def test_materialization_is_order_independent_and_does_not_mutate_blueprints():
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS
    pending = _pending()
    before = corpus.model_dump(mode="json")
    forward = {
        case.case_name: case.materialize(pending).observation_id
        for case in corpus.cases
    }
    reverse = {
        case.case_name: case.materialize(pending).observation_id
        for case in reversed(corpus.cases)
    }
    assert forward == reverse
    assert corpus.model_dump(mode="json") == before


def test_only_malformed_parser_cases_are_explicitly_synthetic():
    corpus = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS
    synthetic = {
        case.case_name
        for case in corpus.cases
        if case.capture_kind is ObservationCaptureKind.SYNTHETIC_MALFORMED_TEST
    }
    assert synthetic == {"opening-invalid-json", "opening-schema-error"}
    assert all(
        case.capture_kind is ObservationCaptureKind.CANONICAL_RECORDED_TRANSITION
        for case in corpus.cases
        if case.case_name not in synthetic
    )
