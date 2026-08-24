"""Deterministic model-free policy priors over Phase-2 legal actions."""

from __future__ import annotations

import asyncio
import hashlib
import math

import pytest

from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
from backend.dialogues.socrates_zero import (
    ActionKind,
    ActionTargetKind,
    BudgetUsage,
    CEDSearchConstitution,
    ContractValidationError,
    HEURISTIC_POLICY_MIN_PROBABILITY,
    HeuristicPolicyPrior,
    LegalAction,
    MoveHistoryRef,
    PolicyPrior,
    SearchBudget,
    SearchState,
    SemanticArtifactRef,
    TerminalStatus,
    UniformPolicyPrior,
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _artifact(artifact_id: str) -> SemanticArtifactRef:
    return SemanticArtifactRef(
        artifact_id=artifact_id,
        semantic_digest=_digest(artifact_id),
    )


def _move(
    move_id: str,
    phase: DialogPhase,
    task_kind: TaskKind,
    *,
    round_index: int = 0,
) -> MoveHistoryRef:
    role = {
        TaskKind.INITIAL_RESPONSE: AgentRole.SYNTHESIZER,
        TaskKind.SOCRATIC_QUESTION: AgentRole.SOCRATES,
    }[task_kind]
    return MoveHistoryRef(
        move_id=move_id,
        semantic_digest=_digest(f"content:{move_id}"),
        phase=phase.value,
        round_index=round_index,
        agent_id=f"agent:{move_id}",
        role=role.value,
        task_kind=task_kind.value,
    )


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


def _state(kind: TaskKind | str, phase: DialogPhase, **overrides) -> SearchState:
    data = {
        "task_kind": kind.value if isinstance(kind, TaskKind) else kind,
        "question": "Which claim survives examination?",
        "phase": phase.value,
        "budget": _budget(),
        "budget_usage": BudgetUsage(nodes=1),
    }
    data.update(overrides)
    return SearchState(**data)


def _elenchus_state(**overrides) -> SearchState:
    data = {
        "active_claims": (_artifact("claim_b"), _artifact("claim_a")),
        "move_history": (
            _move(
                "initial",
                DialogPhase.INITIAL_RESPONSE,
                TaskKind.INITIAL_RESPONSE,
            ),
        ),
    }
    data.update(overrides)
    return _state(TaskKind.ELENCHUS_OBJECTION, DialogPhase.ELENCHUS, **data)


def _reflection_state(**overrides) -> SearchState:
    data = {
        "round_number": 1,
        "active_claims": (_artifact("claim_a"),),
        "move_history": (
            _move(
                "followup",
                DialogPhase.ELENCHUS,
                TaskKind.SOCRATIC_QUESTION,
                round_index=1,
            ),
        ),
    }
    data.update(overrides)
    return _state(TaskKind.REFLECTION_REVISION, DialogPhase.REFLECTION, **data)


def _legal(state: SearchState):
    return CEDSearchConstitution().legal_actions(state)


def _priors(policy, state: SearchState, actions):
    return asyncio.run(policy.priors(state, actions))


def _by_kind(priors, actions):
    kind_by_id = {action.action_id: action.kind for action in actions}
    return {kind_by_id[item.action_id]: item.probability for item in priors}


def test_policy_implementations_use_the_canonical_contract_and_named_versions():
    heuristic = HeuristicPolicyPrior()
    uniform = UniformPolicyPrior()

    assert isinstance(heuristic, PolicyPrior)
    assert isinstance(uniform, PolicyPrior)
    assert heuristic.version == "heuristic-policy-prior/v0"
    assert uniform.version == "uniform-policy-prior/v0"
    assert HEURISTIC_POLICY_MIN_PROBABILITY == 1e-6


def test_uniform_prior_is_canonical_normalized_and_exactly_supported():
    state = _elenchus_state()
    legal = _legal(state)
    result = _priors(UniformPolicyPrior(), state, tuple(reversed(legal)))

    assert tuple(item.action_id for item in result) == tuple(
        action.action_id for action in legal
    )
    assert {item.action_id for item in result} == {
        action.action_id for action in legal
    }
    assert all(item.probability == pytest.approx(1 / len(legal)) for item in result)
    assert math.fsum(item.probability for item in result) == pytest.approx(1.0)


def test_heuristic_prior_is_deterministic_finite_normalized_floored_and_pure():
    state = _elenchus_state(
        contradictions=(_artifact("contradiction_a"),),
        unresolved_questions=(_artifact("objection_a"),),
    )
    legal = _legal(state)
    state_before = state.model_dump(mode="json")
    actions_before = tuple(action.model_dump(mode="json") for action in legal)
    policy = HeuristicPolicyPrior()

    first = _priors(policy, state, legal)
    second = _priors(policy, state, tuple(reversed(legal)))

    assert first == second
    assert tuple(item.action_id for item in first) == tuple(
        action.action_id for action in legal
    )
    assert all(math.isfinite(item.probability) for item in first)
    assert all(
        item.probability >= HEURISTIC_POLICY_MIN_PROBABILITY for item in first
    )
    assert math.fsum(item.probability for item in first) == pytest.approx(
        1.0, abs=1e-12
    )
    assert state.model_dump(mode="json") == state_before
    assert tuple(action.model_dump(mode="json") for action in legal) == actions_before


def test_policy_does_not_manufacture_actions_and_handles_zero_or_one_action():
    state = _elenchus_state()
    legal = _legal(state)
    selected_subset = (legal[0],)

    assert _priors(HeuristicPolicyPrior(), state, ()) == ()
    singleton = _priors(HeuristicPolicyPrior(), state, selected_subset)
    assert len(singleton) == 1
    assert singleton[0].action_id == selected_subset[0].action_id
    assert singleton[0].probability == 1.0

    terminal = _state(
        "terminal",
        DialogPhase.COMPLETE,
        terminal_status=TerminalStatus.ANSWER_READY,
    )
    stop = _legal(terminal)
    assert len(stop) == 1 and stop[0].kind is ActionKind.STOP
    assert _priors(HeuristicPolicyPrior(), terminal, stop)[0].probability == 1.0


def test_policy_never_calls_constitution_to_redecide_legality(monkeypatch):
    state = _elenchus_state()
    legal = _legal(state)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Policy must not call Constitution.legal_actions")

    monkeypatch.setattr(CEDSearchConstitution, "legal_actions", forbidden)
    assert _priors(HeuristicPolicyPrior(), state, legal)
    assert _priors(UniformPolicyPrior(), state, legal)


@pytest.mark.parametrize("policy", [HeuristicPolicyPrior(), UniformPolicyPrior()])
def test_policy_fails_closed_on_duplicate_or_unresolvable_actions(policy):
    state = _elenchus_state()
    legal = _legal(state)
    with pytest.raises(ContractValidationError, match="duplicate"):
        _priors(policy, state, (legal[0], legal[0]))

    missing = LegalAction(
        kind=ActionKind.CHALLENGE_CLAIM,
        target_kind=ActionTargetKind.CLAIM,
        target_id="missing_claim",
    )
    with pytest.raises(ContractValidationError, match="unknown claim"):
        _priors(policy, state, (missing,))

    with pytest.raises(ContractValidationError, match="LegalAction"):
        _priors(policy, state, ({"kind": "stop"},))


@pytest.mark.parametrize(
    "delta,match",
    [(float("nan"), "finite"), (float("inf"), "finite"), (-2.0, "positive")],
)
def test_heuristic_fails_closed_on_invalid_internal_weight(delta, match):
    class BrokenHeuristic(HeuristicPolicyPrior):
        contradiction_adjustments = {ActionKind.RUN_ELENCHUS: delta}

    state = _elenchus_state(contradictions=(_artifact("contradiction_a"),))
    with pytest.raises(ContractValidationError, match=match):
        _priors(BrokenHeuristic(), state, _legal(state))


def test_unresolved_contradiction_modestly_boosts_elenchus_with_neutral_control():
    neutral = _elenchus_state()
    contradicted = _elenchus_state(
        contradictions=(_artifact("contradiction_a"),)
    )
    policy = HeuristicPolicyPrior()
    legal = _legal(neutral)
    neutral_by_kind = _by_kind(_priors(policy, neutral, legal), legal)
    contradicted_by_kind = _by_kind(_priors(policy, contradicted, legal), legal)

    assert (
        contradicted_by_kind[ActionKind.RUN_ELENCHUS]
        > neutral_by_kind[ActionKind.RUN_ELENCHUS]
    )
    neutral_codes = {
        adjustment.reason_code
        for audit in policy.evaluate(neutral, legal)
        for adjustment in audit.adjustments
    }
    contradicted_codes = {
        adjustment.reason_code
        for audit in policy.evaluate(contradicted, legal)
        for adjustment in audit.adjustments
    }
    assert "unresolved_contradiction" not in neutral_codes
    assert "unresolved_contradiction" in contradicted_codes


def test_unresolved_question_boosts_reflection_with_neutral_control():
    neutral = _reflection_state()
    unresolved = _reflection_state(
        unresolved_questions=(_artifact("objection_a"),)
    )
    policy = HeuristicPolicyPrior()
    legal = _legal(neutral)
    neutral_by_kind = _by_kind(_priors(policy, neutral, legal), legal)
    unresolved_by_kind = _by_kind(_priors(policy, unresolved, legal), legal)

    assert (
        unresolved_by_kind[ActionKind.REFLECT]
        > neutral_by_kind[ActionKind.REFLECT]
    )
    neutral_reflect = next(
        audit
        for audit in policy.evaluate(neutral, legal)
        if audit.action_kind is ActionKind.REFLECT
    )
    unresolved_reflect = next(
        audit
        for audit in policy.evaluate(unresolved, legal)
        if audit.action_kind is ActionKind.REFLECT
    )
    assert neutral_reflect.adjustments == ()
    assert [item.reason_code for item in unresolved_reflect.adjustments] == [
        "unresolved_question"
    ]


def test_canonical_claim_target_adjustment_is_scoped_to_targeted_actions():
    state = _elenchus_state()
    audits = HeuristicPolicyPrior().evaluate(state, _legal(state))
    challenge_audits = [
        audit for audit in audits if audit.action_kind is ActionKind.CHALLENGE_CLAIM
    ]
    generic = next(
        audit for audit in audits if audit.action_kind is ActionKind.RUN_ELENCHUS
    )

    assert challenge_audits
    assert all(
        [item.reason_code for item in audit.adjustments]
        == ["canonical_claim_target"]
        for audit in challenge_audits
    )
    assert generic.adjustments == ()
