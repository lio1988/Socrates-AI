"""Read-only canonical CED/Hybrid projection into SocratesZero SearchState."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_epistemic import (
    ClaimRecord,
    ContradictionRecord,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    HybridEpistemicState,
    ObjectionRecord,
    ObjectionState,
    VerificationClass,
    verify_task_internal,
)
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    DialogPhase,
    ProviderStatus,
    TaskKind,
    TaskLogEntry,
)
from backend.dialogues.provider_registry import CouncilProviderRegistry, ScriptedMockProvider
from backend.dialogues.providers import FakeProvider
from backend.dialogues.socratic import (
    AporiaRecord,
    CommitmentStatus,
    commitments_from_move,
)
from backend.dialogues.socrates_zero import (
    BudgetUsage,
    ContractValidationError,
    SearchBudget,
    TerminalStatus,
    project_search_state,
)


QUESTION = "Evidence A is supplied. Which claim survives examination?"


def _budget() -> SearchBudget:
    return SearchBudget(
        max_nodes=8,
        max_expansions=4,
        max_model_calls=4,
        max_tool_calls=2,
        max_tokens=4000,
        max_cost_microusd=100_000,
        max_wall_time_ms=20_000,
        max_depth=3,
    )


def _ced():
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(4):
        registry.register(ScriptedMockProvider(f"seat{index}"))
    ced = CEDOrchestrator(
        [SocraticAgent(f"agent_{index}", provider) for index in range(4)],
        provider,
        registry=registry,
    )
    state = ced.create_session(QUESTION, session_id="projection-session")
    return ced, state


def _record_move(state, spec, move_id, content):
    move = AgentMove(
        move_id=move_id,
        task_id=f"random-{move_id}",
        agent_id=spec.agent_id,
        role=spec.role,
        phase=spec.phase,
        content=content,
        task_kind=spec.task_kind,
        slot_index=spec.slot_index,
    )
    state.moves.append(move)
    state.task_log.append(
        TaskLogEntry(
            task_id=move.task_id,
            move_id=move.move_id,
            session_id=state.session_id,
            phase=spec.phase,
            round_index=spec.round_number,
            agent_id=spec.agent_id,
            assigned_role=spec.role,
            task_kind=spec.task_kind,
            slot_index=spec.slot_index,
            provider_id="volatile-route",
            provider_status=ProviderStatus.OK,
        )
    )
    return move


def _source_fixture():
    ced, state = _ced()
    opening = ced.canonical_registry_task_specs(state, DialogPhase.OPENING)[0]
    _record_move(
        state,
        opening,
        "move_opening",
        {"question": "Which premise is load-bearing?", "operator": "clarify"},
    )
    initial = ced.canonical_registry_task_specs(state, DialogPhase.INITIAL_RESPONSE)[0]
    move = _record_move(
        state,
        initial,
        "move_initial",
        {"commitments": ["Claim A survives the supplied evidence."]},
    )
    state.record_role_assignment(
        DialogPhase.OPENING,
        0,
        {opening.agent_id: opening.role},
    )
    state.record_role_assignment(
        DialogPhase.INITIAL_RESPONSE,
        0,
        {initial.agent_id: initial.role},
    )
    commitments = commitments_from_move(
        move.move_id,
        0,
        move.content,
        provider_id="volatile-route",
        model_id="vendor/exact-model-v1",
    )
    commitment = commitments[0]
    aporia = AporiaRecord(
        previous_commitment_id=commitment.commitment_id,
        conflicting_commitment_id=commitment.commitment_id,
        resulting_status=CommitmentStatus.SUSPENDED,
        remaining_question="What would disconfirm Claim A?",
        cycle=0,
    )

    hybrid = HybridEpistemicState(state.session_id, state.question)
    hybrid.add_claim(
        ClaimRecord(
            claim_id="claim_a",
            text="Claim A survives the supplied evidence.",
            section="core_answer",
            verification_class=VerificationClass.TASK_INTERNAL,
        )
    )
    hybrid.add_evidence(
        EvidenceRecord(
            evidence_id="evidence_a",
            claim_id="claim_a",
            stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.SUPPLIED_TASK_MATERIAL,
            source_identity="task",
            content="Evidence A is supplied.",
            known_at="volatile timestamp",
            provenance="task",
        )
    )
    hybrid.add_objection(
        ObjectionRecord(
            objection_id="objection_a",
            target_claim_id="claim_a",
            text="The inference may be incomplete.",
            state=ObjectionState.RAISED,
        )
    )
    next_task = ced.canonical_registry_task_specs(state, DialogPhase.ELENCHUS)[0]
    return state, next_task, commitments, (aporia,), hybrid


def _project(source=None):
    state, task, commitments, aporia, hybrid = source or _source_fixture()
    return project_search_state(
        state,
        task,
        budget=_budget(),
        budget_usage=BudgetUsage(nodes=1, max_depth_observed=0),
        commitments=commitments,
        aporia_records=aporia,
        hybrid_state=hybrid,
    )


def test_projection_is_side_effect_free_and_populates_only_canonical_records():
    source = _source_fixture()
    state, _task, commitments, aporia, hybrid = source
    before_state = state.model_dump(mode="json")
    before_commitments = [record.to_dict() for record in commitments]
    before_aporia = [record.to_dict() for record in aporia]
    before_hybrid = deepcopy(hybrid.__dict__)

    projected = _project(source)

    assert state.model_dump(mode="json") == before_state
    assert [record.to_dict() for record in commitments] == before_commitments
    assert [record.to_dict() for record in aporia] == before_aporia
    assert hybrid.__dict__ == before_hybrid
    assert {item.artifact_id for item in projected.active_claims} == {
        commitments[0].commitment_id,
        "claim_a",
    }
    assert {item.artifact_id for item in projected.evidence} == {"evidence_a"}
    assert {item.artifact_id for item in projected.unresolved_questions} == {
        aporia[0].aporia_id,
        "objection_a",
    }
    assert projected.provider_receipts == ()


def test_volatile_runtime_fields_do_not_change_projected_semantic_identity():
    source = _source_fixture()
    first = _project(source)
    changed = deepcopy(source)
    state = changed[0]
    state.session_id = "different-audit-session"
    state.created_at += timedelta(days=1)
    state.updated_at += timedelta(days=2)
    for move in state.moves:
        move.task_id = f"different-{move.task_id}"
        move.timestamp += timedelta(hours=1)
    for row in state.task_log:
        row.task_id = f"different-{row.task_id}"
        row.session_id = state.session_id
        row.provider_id = "different-route"
        row.created_at += timedelta(hours=2)
    changed[4].session_id = state.session_id

    second = _project(changed)

    assert first.state_id == second.state_id
    assert first.session_id != second.session_id


def test_meaningful_contradiction_verification_and_target_changes_change_identity():
    source = _source_fixture()
    original = _project(source)

    with_contradiction = deepcopy(source)
    with_contradiction[4].add_claim(
        ClaimRecord(claim_id="claim_b", text="Claim B", section="nuance")
    )
    with_contradiction[4].add_contradiction(
        ContradictionRecord(
            contradiction_id="contradiction_ab",
            claim_id_a="claim_a",
            claim_id_b="claim_b",
        )
    )
    assert _project(with_contradiction).state_id != original.state_id

    with_verification = deepcopy(source)
    verification = verify_task_internal(
        claim_id="claim_a",
        objection_id=None,
        task_text=QUESTION,
        cited_spans=(("Evidence A is supplied.", 0),),
        condition_tested="is the cited material present?",
        holds=True,
        rationale="deterministic citation check",
    )
    with_verification[4].add_verification(verification)
    assert _project(with_verification).state_id != original.state_id

    retargeted = deepcopy(source)
    retargeted[4].add_claim(ClaimRecord(claim_id="claim_b", text="Claim B"))
    current = retargeted[4].objections["objection_a"]
    retargeted[4].objections["objection_a"] = current.model_copy(
        update={"target_claim_id": "claim_b"}
    )
    assert _project(retargeted).state_id != original.state_id


def test_move_content_digest_is_part_of_state_identity_but_timestamp_is_not():
    source = _source_fixture()
    first = _project(source)
    changed = deepcopy(source)
    changed[0].moves[0].content["question"] = "A materially different question?"
    second = _project(changed)
    assert first.state_id != second.state_id


def test_hybrid_mapping_insertion_order_does_not_change_identity():
    source = _source_fixture()
    source[4].add_claim(ClaimRecord(claim_id="claim_b", text="Claim B"))
    source[4].add_evidence(
        EvidenceRecord(
            evidence_id="evidence_b",
            claim_id="claim_b",
            stance=EvidenceStance.WEAK,
            source_type=EvidenceSourceType.HUMAN_PROVIDED,
            source_identity="operator",
            content="bounded observation",
        )
    )
    first = _project(source)
    reordered = deepcopy(source)
    reordered[4].claims = dict(reversed(tuple(reordered[4].claims.items())))
    reordered[4].evidence = dict(reversed(tuple(reordered[4].evidence.items())))
    second = _project(reordered)
    assert first.state_id == second.state_id


def test_terminal_state_is_derived_from_canonical_final_state():
    source = list(_source_fixture())
    source[0].phase = DialogPhase.COMPLETE
    source[1] = None
    projected = _project(tuple(source))
    assert projected.terminal_status is TerminalStatus.BLOCKED


@pytest.mark.parametrize(
    "break_source,match",
    [
        (
            lambda source: source.__setitem__(
                1, replace(source[1], agent_id="missing")
            ),
            "active agent",
        ),
        (lambda source: setattr(source[4], "task_text", "different"), "task text"),
        (
            lambda source: setattr(
                source[2][0], "source_move_id", "unknown-move"
            ),
            "unknown source move",
        ),
    ],
)
def test_invalid_source_state_fails_closed(break_source, match):
    source = list(_source_fixture())
    break_source(source)
    with pytest.raises(ContractValidationError, match=match):
        _project(tuple(source))
