"""Canonical execution restoration regressions.

These tests cover only three existing contracts:
  * one logical agent stays bound to one provider/model seat within a session;
  * provider model metadata remains exact;
  * parsed AgentMove confidence remains the typed downstream confidence source.

They do not change scoring, ratification, epistemic-status, or prompt semantics.
"""

import asyncio
import json
from collections import defaultdict

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    AgentRole,
    AgentTask,
    AssembledAnswer,
    AssembledSection,
    DialogPhase,
    ProviderResponse,
    ProviderStatus,
    SectionDraft,
    SectionName,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    BaseProviderAdapter,
    CouncilProviderRegistry,
    ScriptedMockProvider,
    parse_and_validate_move,
)
from backend.dialogues.providers import FakeProvider


Q = "Is knowledge merely justified true belief?"
DELIBERATION_KINDS = {
    TaskKind.SOCRATIC_QUESTION,
    TaskKind.INITIAL_RESPONSE,
    TaskKind.ELENCHUS_OBJECTION,
    TaskKind.REFLECTION_REVISION,
    TaskKind.RECONSTRUCTION_PROPOSAL,
    TaskKind.SYNTHESIS_DRAFT,
}


class ModelSeatProvider(ScriptedMockProvider):
    """Scripted transport with the canonical provider ``model`` metadata."""

    def __init__(self, provider_id: str, model: str) -> None:
        super().__init__(provider_id)
        self.model = model


def _council() -> CEDOrchestrator:
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(3)]
    registry = CouncilProviderRegistry()
    for i, model in enumerate(("vendor/model-a", "vendor/model-b", "vendor/model-c")):
        registry.register(ModelSeatProvider(f"seat_{i}", model))
    return CEDOrchestrator(agents, provider, registry=registry, assembly_fallback=True)


def _deliberation_route(ced: CEDOrchestrator, session_id: str):
    state = ced.get_session(session_id)
    return [
        (entry.phase.value, entry.agent_id, entry.provider_id, entry.assigned_role.value,
         entry.task_kind.value)
        for entry in state.task_log
        if entry.task_kind in DELIBERATION_KINDS and entry.attempt_index == 0
    ]


def test_logical_agent_stays_on_one_provider_model_across_phases():
    ced = _council()
    asyncio.run(ced.run_registry_session(Q, session_id="stable-seat-binding"))
    state = ced.get_session("stable-seat-binding")

    providers_by_agent = defaultdict(set)
    for _, agent_id, provider_id, _, _ in _deliberation_route(ced, state.session_id):
        providers_by_agent[agent_id].add(provider_id)

    assert set(providers_by_agent) == set(state.agent_states)
    assert all(len(provider_ids) == 1 for provider_ids in providers_by_agent.values())

    model_by_provider = {a.provider_id: a.model for a in ced.registry.all_adapters()}
    models_by_agent = {
        agent_id: {model_by_provider[provider_id] for provider_id in provider_ids}
        for agent_id, provider_ids in providers_by_agent.items()
    }
    assert all(len(model_ids) == 1 for model_ids in models_by_agent.values())
    assert {next(iter(v)) for v in models_by_agent.values()} == {
        "vendor/model-a", "vendor/model-b", "vendor/model-c",
    }


def test_roles_rotate_over_stable_agent_provider_bindings():
    ced = _council()
    asyncio.run(ced.run_registry_session(Q, session_id="stable-role-rotation"))
    state = ced.get_session("stable-role-rotation")

    providers_by_agent = defaultdict(set)
    for _, agent_id, provider_id, _, _ in _deliberation_route(ced, state.session_id):
        providers_by_agent[agent_id].add(provider_id)
    roles_by_agent = defaultdict(set)
    for record in state.role_history:
        roles_by_agent[record["agent_id"]].add(record["role"])

    assert all(len(provider_ids) == 1 for provider_ids in providers_by_agent.values())
    assert any(len(roles) > 1 for roles in roles_by_agent.values())

    single_slot = {
        entry.phase: entry.provider_id
        for entry in state.task_log
        if entry.task_kind in {TaskKind.SOCRATIC_QUESTION, TaskKind.RECONSTRUCTION_PROPOSAL}
        and entry.attempt_index == 0
    }
    # These phases are assigned to different logical agents for a three-seat council;
    # routing must therefore not silently restart from provider slot zero.
    assert single_slot[DialogPhase.OPENING] != single_slot[DialogPhase.RECONSTRUCTION]


def test_stable_agent_provider_routing_is_deterministic():
    routes = []
    for _ in range(2):
        ced = _council()
        asyncio.run(ced.run_registry_session(Q, session_id="deterministic-seat-binding"))
        routes.append(_deliberation_route(ced, "deterministic-seat-binding"))
    assert routes[0] == routes[1]


def test_socrates_rotates_across_physical_model_seats_between_sessions():
    opening_providers = set()
    for i in range(12):
        ced = _council()
        session_id = f"physical-role-rotation-{i}"
        state = ced.create_session(Q, session_id=session_id)
        asyncio.run(ced._run_registry_phase(state, DialogPhase.OPENING, 5.0))
        opening = next(
            entry for entry in state.task_log
            if entry.task_kind == TaskKind.SOCRATIC_QUESTION
        )
        opening_providers.add(opening.provider_id)
    assert opening_providers == {"seat_0", "seat_1", "seat_2"}


class FixedConfidenceProvider(BaseProviderAdapter):
    provider_name = "Fixed Confidence"

    def __init__(self, provider_id: str, confidence: float) -> None:
        super().__init__(api_key="sk-fake-confidence")
        self.provider_id = provider_id
        self.confidence = confidence
        self.model = "mock-confidence"

    async def _produce_raw_text(self, task, agent_state):
        dimensions = {
            "epistemic_value": 8,
            "logical_rigor": 8,
            "factual_grounding": 8,
            "constructive_impact": 8,
            "intellectual_honesty": 8,
            "clarity_precision": 8,
            "grounded_creativity": 8,
        }
        return json.dumps({"content": dimensions, "confidence": self.confidence})


def _parsed_response(task: AgentTask, content: dict, confidence: float) -> ProviderResponse:
    move, status, error = parse_and_validate_move(
        json.dumps({"content": content, "confidence": confidence}), task,
    )
    assert status == ProviderStatus.OK and error is None and move is not None
    return ProviderResponse(
        provider_id=task.agent_id,
        agent_id=task.agent_id,
        status=ProviderStatus.OK,
        parsed_move=move,
    )


@pytest.mark.parametrize("confidence", [0.13, 0.91])
def test_move_score_uses_typed_parsed_move_confidence(confidence):
    ced = _council()
    state = ced.create_session(Q, session_id=f"move-confidence-{confidence}")
    candidate_task = AgentTask(
        session_id=state.session_id,
        agent_id="agent_0",
        role=AgentRole.SYNTHESIZER,
        phase=DialogPhase.SYNTHESIS,
        question=Q,
        task_kind=TaskKind.SYNTHESIS_DRAFT,
    )
    candidate = _parsed_response(candidate_task, {"text": "candidate"}, 0.5).parsed_move
    score_task = ced._build_move_score_task(
        state, candidate, "seat_1", DialogPhase.SYNTHESIS, 0,
    )
    score_response = _parsed_response(score_task, {
        "epistemic_value": 8,
        "logical_rigor": 8,
        "factual_grounding": 8,
        "constructive_impact": 8,
        "intellectual_honesty": 8,
        "clarity_precision": 8,
        "grounded_creativity": 8,
    }, confidence)

    score = ced._microscore_from_response(
        state, candidate, "seat_1", DialogPhase.SYNTHESIS, score_response,
    )
    assert score.confidence == pytest.approx(confidence)


@pytest.mark.parametrize("confidence", [0.13, 0.91])
def test_section_score_uses_typed_parsed_move_confidence(confidence):
    provider = FakeProvider()
    agents = [SocraticAgent("agent_0", provider), SocraticAgent("agent_1", provider)]
    registry = CouncilProviderRegistry()
    registry.register(ModelSeatProvider("producer", "vendor/producer"))
    registry.register(FixedConfidenceProvider("voter", confidence))
    ced = CEDOrchestrator(agents, provider, registry=registry)
    state = ced.create_session(Q, session_id=f"section-confidence-{confidence}")
    state.section_drafts = [SectionDraft(
        draft_id="draft_confidence",
        session_id=state.session_id,
        author_agent_id="agent_0",
        move_id="move_confidence",
        provider_id="producer",
        core_answer="core",
        crucial_stress_test="stress",
        blind_spots="blind",
        nuance="nuance",
        final_verdict="verdict",
    )]

    cards = asyncio.run(ced.score_section_drafts_with_registry(state, 5.0))
    scores = [score for card in cards for score in card.section_scores]
    assert len(scores) == 5
    assert all(score.confidence == pytest.approx(confidence) for score in scores)


@pytest.mark.parametrize("confidence", [0.13, 0.91])
def test_ratification_uses_typed_parsed_move_confidence(confidence):
    ced = _council()
    state = ced.create_session(Q, session_id=f"ratification-confidence-{confidence}")
    state.assembled_answer = AssembledAnswer(
        session_id=state.session_id,
        sections=[AssembledSection(
            section_name=SectionName.CORE_ANSWER,
            selected_draft_id="draft",
            selected_author_agent_id="agent_0",
            content="answer",
            average_score=8.0,
        )],
    )
    task = AgentTask(
        session_id=state.session_id,
        agent_id="seat_1",
        role=AgentRole.FINAL_EVALUATOR,
        phase=DialogPhase.RATIFICATION,
        question=Q,
        task_kind=TaskKind.COUNCIL_RATIFICATION,
    )
    response = _parsed_response(
        task, {"verdict": "accept", "rationale": "meets the existing bar"}, confidence,
    )

    verdict = ced._parse_verdict(response, task)
    assert verdict.confidence == pytest.approx(confidence)
