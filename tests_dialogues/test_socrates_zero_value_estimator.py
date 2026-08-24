"""Leakage-safe deterministic state-value baselines for SocratesZero."""

from __future__ import annotations

import asyncio
import hashlib
import math

import pytest

from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
from backend.dialogues.socrates_zero import (
    BudgetUsage,
    CEDSearchConstitution,
    ContractValidationError,
    HEURISTIC_VALUE_ESTIMATOR_VERSION,
    HEURISTIC_VALUE_RULES_V0,
    HeuristicPolicyPrior,
    HeuristicValueEstimator,
    MoveHistoryRef,
    NEUTRAL_VALUE_ESTIMATOR_VERSION,
    NeutralValueEstimator,
    ObservationRef,
    PolicyContextEntry,
    SearchBudget,
    SearchState,
    SemanticArtifactRef,
    TerminalStatus,
    UniformPolicyPrior,
    ValueEstimator,
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _artifact(artifact_id: str) -> SemanticArtifactRef:
    return SemanticArtifactRef(
        artifact_id=artifact_id,
        semantic_digest=_digest(artifact_id),
    )


def _observation(
    record_id: str,
    *,
    semantic: str = "opaque verification outcome",
    provider_id: str | None = None,
    model_id: str | None = None,
) -> ObservationRef:
    return ObservationRef(
        record_id=record_id,
        semantic_digest=_digest(semantic),
        provider_id=provider_id,
        model_id=model_id,
    )


def _move(move_id: str, *, semantic: str = "public move") -> MoveHistoryRef:
    return MoveHistoryRef(
        move_id=move_id,
        semantic_digest=_digest(semantic),
        phase=DialogPhase.ELENCHUS.value,
        round_index=0,
        agent_id="agent_a",
        role=AgentRole.ELENCHUS_CRITIC.value,
        task_kind=TaskKind.ELENCHUS_OBJECTION.value,
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


def _state(**overrides) -> SearchState:
    data = {
        "task_kind": TaskKind.ELENCHUS_OBJECTION.value,
        "question": "Which claim survives examination?",
        "phase": DialogPhase.ELENCHUS.value,
        "budget": _budget(),
        "budget_usage": BudgetUsage(nodes=1),
    }
    data.update(overrides)
    return SearchState(**data)


def _replace(state: SearchState, **updates) -> SearchState:
    data = state.model_dump(exclude={"state_id"})
    data.update(updates)
    return SearchState(**data)


def _estimate(estimator, state: SearchState) -> float:
    return asyncio.run(estimator.estimate(state))


def _component(audit, reason_code: str):
    return next(item for item in audit.components if item.reason_code == reason_code)


def test_estimators_use_canonical_contract_named_versions_and_range():
    neutral = NeutralValueEstimator()
    heuristic = HeuristicValueEstimator()
    state = _state()

    assert isinstance(neutral, ValueEstimator)
    assert isinstance(heuristic, ValueEstimator)
    assert neutral.version == "neutral-value-estimator/v0"
    assert heuristic.version == "heuristic-value-estimator/v0"
    assert NEUTRAL_VALUE_ESTIMATOR_VERSION == neutral.version
    assert HEURISTIC_VALUE_ESTIMATOR_VERSION == heuristic.version
    assert _estimate(neutral, state) == 0.0
    assert -1.0 <= _estimate(heuristic, state) <= 1.0


def test_same_state_produces_same_finite_value_and_audit_without_mutation():
    state = _state(
        contradictions=(_artifact("contradiction_a"),),
        unresolved_questions=(_artifact("objection_a"),),
    )
    before = state.model_dump(mode="json")
    estimator = HeuristicValueEstimator()

    first = estimator.evaluate(state)
    second = estimator.evaluate(state)

    assert first == second
    assert first.audit_id == second.audit_id
    assert math.isfinite(first.bounded_value)
    assert -1.0 <= first.bounded_value <= 1.0
    assert _estimate(estimator, state) == first.bounded_value
    assert state.model_dump(mode="json") == before


def test_unresolved_contradiction_is_monotone_capped_and_auditable():
    estimator = HeuristicValueEstimator()
    neutral = _state()
    one = _state(contradictions=(_artifact("c1"),))
    boundary = _state(
        contradictions=tuple(_artifact(f"c{index}") for index in range(20))
    )

    assert _estimate(estimator, one) <= _estimate(estimator, neutral)
    assert _estimate(estimator, boundary) <= _estimate(estimator, one)
    assert _estimate(estimator, neutral) == 0.0
    assert _estimate(estimator, one) == pytest.approx(-0.08)
    assert _estimate(estimator, boundary) == pytest.approx(-0.24)

    component = _component(estimator.evaluate(one), "unresolved_contradiction")
    assert component.contribution == pytest.approx(-0.08)
    assert component.canonical_refs == ("c1",)


def test_unresolved_question_is_monotone_capped_and_auditable():
    estimator = HeuristicValueEstimator()
    neutral = _state()
    one = _state(unresolved_questions=(_artifact("q1"),))
    boundary = _state(
        unresolved_questions=tuple(_artifact(f"q{index}") for index in range(20))
    )

    assert _estimate(estimator, one) <= _estimate(estimator, neutral)
    assert _estimate(estimator, boundary) <= _estimate(estimator, one)
    assert _estimate(estimator, one) == pytest.approx(-0.05)
    assert _estimate(estimator, boundary) == pytest.approx(-0.20)

    component = _component(estimator.evaluate(one), "unresolved_question")
    assert component.contribution == pytest.approx(-0.05)
    assert component.canonical_refs == ("q1",)


def test_terminal_semantics_do_not_confuse_completion_with_truth():
    estimator = HeuristicValueEstimator()
    answer_ready = _state(
        task_kind="terminal",
        phase=DialogPhase.COMPLETE.value,
        terminal_status=TerminalStatus.ANSWER_READY,
        verification_results=(_observation("verified_fixture"),),
    )
    abstained = _state(
        task_kind="terminal",
        phase=DialogPhase.COMPLETE.value,
        terminal_status=TerminalStatus.ABSTAINED,
    )
    blocked = _state(
        task_kind="terminal",
        phase=DialogPhase.COMPLETE.value,
        terminal_status=TerminalStatus.BLOCKED,
    )
    unresolved = _replace(
        blocked,
        unresolved_questions=(_artifact("unresolved_at_terminal"),),
    )
    budget_exhausted = _state(
        terminal_status=TerminalStatus.BUDGET_EXHAUSTED,
        budget_usage=BudgetUsage(nodes=9),
    )

    assert _estimate(estimator, answer_ready) == 0.0
    assert _component(
        estimator.evaluate(answer_ready), "answer_ready_is_not_verification"
    ).contribution == 0.0
    assert _estimate(estimator, abstained) == 0.0
    assert _component(
        estimator.evaluate(abstained), "epistemic_abstention"
    ).contribution == 0.0
    assert _estimate(estimator, blocked) == pytest.approx(-0.20)
    assert _estimate(estimator, unresolved) < _estimate(estimator, blocked)
    assert _estimate(estimator, budget_exhausted) == pytest.approx(-0.10)


def test_opaque_verification_cannot_create_optimism_or_override_blocking():
    estimator = HeuristicValueEstimator()
    blocked = _state(
        task_kind="terminal",
        phase=DialogPhase.COMPLETE.value,
        terminal_status=TerminalStatus.BLOCKED,
    )
    with_failed_fixture = _replace(
        blocked,
        verification_results=(
            _observation(
                "failed_verification",
                semantic="fixture says falsified but SearchState exposes only digest",
                provider_id="provider_a",
                model_id="model/a",
            ),
        ),
        evidence=tuple(_artifact(f"e{index}") for index in range(8)),
        candidate_answers=(_artifact("polished_answer"),),
    )

    assert _estimate(estimator, with_failed_fixture) == _estimate(estimator, blocked)
    assert _estimate(estimator, with_failed_fixture) < 0.0


@pytest.mark.parametrize(
    "updates",
    [
        {"question": "A much longer and more eloquent question with confidence."},
        {
            "policy_context": (
                PolicyContextEntry(
                    name="consensus_and_peer_score",
                    semantic_digest=_digest("unanimous; score=10"),
                ),
            )
        },
        {"move_history": (_move("move_a", semantic="established_fact; confidence=1"),)},
        {
            "verification_results": (
                _observation(
                    "verification_a",
                    provider_id="prestigious_provider",
                    model_id="prestigious/model",
                ),
            )
        },
        {"evidence": tuple(_artifact(f"citation_{index}") for index in range(12))},
        {"candidate_answers": (_artifact("elegant_final_answer"),)},
        {"active_agent_id": "different_agent", "active_role": "synthesizer"},
    ],
)
def test_forbidden_metadata_and_prose_do_not_change_value(updates):
    estimator = HeuristicValueEstimator()
    base = _state()
    changed = _replace(base, **updates)

    assert base.state_id != changed.state_id
    assert _estimate(estimator, changed) == _estimate(estimator, base)


def test_same_current_state_with_different_fixture_futures_has_same_value():
    current = _state(
        contradictions=(_artifact("c1"),),
        unresolved_questions=(_artifact("q1"),),
    )
    successful_future_fixture = {
        "current_state": current,
        "future_gold_label": "correct",
        "future_reward": 1.0,
        "future_answer": "A",
    }
    failed_future_fixture = {
        "current_state": _replace(current),
        "future_gold_label": "incorrect",
        "future_reward": -1.0,
        "future_answer": "B",
    }

    estimator = HeuristicValueEstimator()
    first = estimator.evaluate(successful_future_fixture["current_state"])
    second = estimator.evaluate(failed_future_fixture["current_state"])

    assert successful_future_fixture["current_state"].state_id == (
        failed_future_fixture["current_state"].state_id
    )
    assert first == second


def test_value_never_calls_policy_or_constitution(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Value must not call Policy or Constitution")

    monkeypatch.setattr(HeuristicPolicyPrior, "priors", forbidden)
    monkeypatch.setattr(UniformPolicyPrior, "priors", forbidden)
    monkeypatch.setattr(CEDSearchConstitution, "legal_actions", forbidden)

    state = _state(contradictions=(_artifact("c1"),))
    assert _estimate(NeutralValueEstimator(), state) == 0.0
    assert _estimate(HeuristicValueEstimator(), state) < 0.0


@pytest.mark.parametrize(
    "state,match",
    [
        (
            _state(terminal_status=TerminalStatus.ANSWER_READY),
            "answer_ready.*complete",
        ),
        (
            _state(
                task_kind="terminal",
                phase=DialogPhase.COMPLETE.value,
                terminal_status=TerminalStatus.NON_TERMINAL,
            ),
            "complete.*non-terminal",
        ),
    ],
)
def test_structurally_invalid_terminal_state_fails_closed(state, match):
    with pytest.raises(ContractValidationError, match=match):
        _estimate(HeuristicValueEstimator(), state)


def test_invalid_or_forged_search_state_fails_closed():
    estimator = HeuristicValueEstimator()
    with pytest.raises(ContractValidationError, match="SearchState"):
        _estimate(estimator, {"phase": "elenchus"})

    valid = _state()
    forged = valid.model_copy(update={"state_id": "forged"})
    with pytest.raises(ContractValidationError, match="valid SearchState"):
        _estimate(estimator, forged)


@pytest.mark.parametrize("coefficient", [float("nan"), float("inf")])
def test_nonfinite_v0_coefficient_fails_closed(coefficient):
    class BrokenEstimator(HeuristicValueEstimator):
        unresolved_contradiction_per_record = coefficient

    state = _state(contradictions=(_artifact("c1"),))
    with pytest.raises(ContractValidationError, match="finite"):
        _estimate(BrokenEstimator(), state)


def test_v0_rule_table_is_explicit_conservative_and_versioned():
    assert HEURISTIC_VALUE_RULES_V0 == {
        "unresolved_contradiction_per_record": -0.08,
        "unresolved_contradiction_floor": -0.24,
        "unresolved_question_per_record": -0.05,
        "unresolved_question_floor": -0.20,
        "terminal_blocked": -0.20,
        "terminal_budget_exhausted": -0.10,
    }
    assert all(math.isfinite(value) for value in HEURISTIC_VALUE_RULES_V0.values())
    assert all(value <= 0.0 for value in HEURISTIC_VALUE_RULES_V0.values())
