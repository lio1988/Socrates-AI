"""Phase-1 SocratesZero contracts are strict, deterministic and runtime-inert."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.dialogues.hybrid_authority import AuthorityClass, authority_of
from backend.dialogues.socrates_zero import (
    SOCRATES_ZERO_DEFAULT_ENABLED,
    ActionKind,
    ActionParameter,
    ActionStatistics,
    ActionTargetKind,
    BudgetExceeded,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    ObservationRef,
    PolicyContextEntry,
    SearchBudget,
    SearchReceipt,
    SearchResult,
    SearchState,
    SearchTerminationReason,
    SemanticArtifactRef,
    TerminalStatus,
    validate_action_references,
)


def _digest(char: str) -> str:
    return char * 64


def _artifact(artifact_id: str, char: str) -> SemanticArtifactRef:
    return SemanticArtifactRef(artifact_id=artifact_id, semantic_digest=_digest(char))


def _budget(**overrides) -> SearchBudget:
    data = {
        "max_nodes": 8,
        "max_expansions": 4,
        "max_model_calls": 3,
        "max_tool_calls": 2,
        "max_tokens": 5000,
        "max_cost_microusd": 250_000,
        "max_wall_time_ms": 30_000,
        "max_depth": 3,
    }
    data.update(overrides)
    return SearchBudget(**data)


def _state(**overrides) -> SearchState:
    data = {
        "session_id": "random-session-a",
        "task_id": "random-task-a",
        "parent_state_id": "random-parent-a",
        "task_kind": "epistemic_deliberation",
        "question": "Which claim survives the governed checks?",
        "phase": "elenchus",
        "active_claims": (_artifact("claim_b", "b"), _artifact("claim_a", "a")),
        "evidence": (_artifact("evidence_1", "c"),),
        "contradictions": (_artifact("contradiction_1", "d"),),
        "provider_receipts": (
            ObservationRef(
                record_id="random-response-a",
                semantic_digest=_digest("e"),
                provider_id="route-a",
                model_id="vendor/exact-model-v1",
            ),
        ),
        "verification_results": (
            ObservationRef(
                record_id="verification-a",
                semantic_digest=_digest("f"),
                provider_id="checker-route-a",
                model_id=None,
            ),
        ),
        "policy_context": (
            PolicyContextEntry(name="constitution", semantic_digest=_digest("1")),
            PolicyContextEntry(name="policy", semantic_digest=_digest("2")),
        ),
        "budget": _budget(),
        "budget_usage": BudgetUsage(nodes=2, expansions=1, max_depth_observed=1),
        "depth": 1,
        "terminal_status": TerminalStatus.NON_TERMINAL,
    }
    data.update(overrides)
    return SearchState(**data)


def test_package_is_disabled_by_default_and_classified_as_search_only():
    assert SOCRATES_ZERO_DEFAULT_ENABLED is False
    assert authority_of("SocratesZero search contracts") is AuthorityClass.SEARCH


def test_state_identity_excludes_volatile_audit_and_route_metadata():
    first = _state()
    second = _state(
        session_id="random-session-b",
        task_id="random-task-b",
        parent_state_id="random-parent-b",
        provider_receipts=(
            ObservationRef(
                record_id="random-response-b",
                semantic_digest=_digest("e"),
                provider_id="different-route",
                model_id="vendor/exact-model-v1",
            ),
        ),
        verification_results=(
            ObservationRef(
                record_id="verification-b",
                semantic_digest=_digest("f"),
                provider_id="different-checker-route",
                model_id=None,
            ),
        ),
    )
    assert first.state_id == second.state_id


def test_state_identity_is_order_independent_for_semantic_sets():
    first = _state()
    second = _state(
        active_claims=tuple(reversed(first.active_claims)),
        policy_context=tuple(reversed(first.policy_context)),
    )
    assert first.active_claims == second.active_claims
    assert first.state_id == second.state_id


@pytest.mark.parametrize(
    "change",
    [
        {"question": "A different task"},
        {"active_claims": (_artifact("claim_a", "9"),)},
        {
            "provider_receipts": (
                ObservationRef(
                    record_id="same-audit-ref",
                    semantic_digest=_digest("e"),
                    model_id="vendor/exact-model-v2",
                ),
            )
        },
        {"budget": _budget(max_nodes=9)},
        {"budget_usage": BudgetUsage(nodes=3, expansions=1, max_depth_observed=1)},
        {
            "depth": 2,
            "budget_usage": BudgetUsage(
                nodes=2, expansions=1, max_depth_observed=2
            ),
        },
        {"terminal_status": TerminalStatus.ANSWER_READY},
    ],
)
def test_state_identity_changes_for_semantic_or_legality_relevant_state(change):
    assert _state().state_id != _state(**change).state_id


def test_state_rejects_wrong_identity_duplicate_artifacts_and_extra_fields():
    original = _state()
    with pytest.raises(ValidationError, match="state_id"):
        _state(state_id="szstate_wrong")
    with pytest.raises(ValidationError, match="duplicate"):
        _state(active_claims=(original.active_claims[0], original.active_claims[0]))
    with pytest.raises(ValidationError, match="Extra inputs"):
        SearchState(**original.model_dump(), timestamp="volatile")


def test_state_budget_and_depth_consistency_fail_closed():
    with pytest.raises(ValidationError, match="max_depth_observed"):
        _state(depth=2)

    over = BudgetUsage(nodes=9, expansions=1, max_depth_observed=1)
    with pytest.raises(ValidationError, match="over-budget state"):
        _state(budget_usage=over)

    exhausted = _state(
        budget_usage=over,
        terminal_status=TerminalStatus.BUDGET_EXHAUSTED,
    )
    assert exhausted.terminal_status is TerminalStatus.BUDGET_EXHAUSTED


def test_state_round_trip_preserves_full_deterministic_identity_and_is_frozen():
    original = _state()
    restored = SearchState.model_validate_json(original.model_dump_json())
    assert restored == original
    with pytest.raises(ValidationError):
        original.depth = 99


def test_legal_action_has_order_independent_full_identity():
    first = LegalAction(
        kind=ActionKind.CHALLENGE_CLAIM,
        target_kind=ActionTargetKind.CLAIM,
        target_id="claim_a",
        parameters=(
            ActionParameter(name="scope", value="central"),
            ActionParameter(name="severity", value=2),
        ),
        required_capabilities=("structured_output", "verification"),
    )
    second = LegalAction(
        kind=ActionKind.CHALLENGE_CLAIM,
        target_kind=ActionTargetKind.CLAIM,
        target_id="claim_a",
        parameters=tuple(reversed(first.parameters)),
        required_capabilities=tuple(reversed(first.required_capabilities)),
    )
    assert first.action_id == second.action_id
    assert len(first.action_id.removeprefix("szaction_")) == 64


def test_legal_action_shape_and_state_reference_validation_fail_closed():
    with pytest.raises(ValidationError, match="requires a claim target"):
        LegalAction(kind=ActionKind.CHALLENGE_CLAIM)
    with pytest.raises(ValidationError, match="cannot have a target"):
        LegalAction(
            kind=ActionKind.STOP,
            target_kind=ActionTargetKind.CLAIM,
            target_id="claim_a",
        )

    known = LegalAction(
        kind=ActionKind.VERIFY_CLAIM,
        target_kind=ActionTargetKind.CLAIM,
        target_id="claim_a",
    )
    validate_action_references(_state(), known)

    unknown = LegalAction(
        kind=ActionKind.VERIFY_CLAIM,
        target_kind=ActionTargetKind.CLAIM,
        target_id="claim_missing",
    )
    with pytest.raises(ContractValidationError, match="unknown claim target"):
        validate_action_references(_state(), unknown)


def test_action_cannot_smuggle_an_observation_or_evidence_payload():
    with pytest.raises(ValidationError, match="Extra inputs"):
        LegalAction(
            kind=ActionKind.SEEK_EVIDENCE,
            evidence={"claim": "fabricated observation"},
        )


def test_budget_accepts_exact_limit_and_rejects_next_unit():
    budget = _budget()
    exact = BudgetUsage(
        nodes=8,
        expansions=4,
        model_calls=3,
        tool_calls=2,
        tokens=5000,
        cost_microusd=250_000,
        wall_time_ms=30_000,
        max_depth_observed=3,
    )
    budget.enforce(exact)
    assert budget.allows(exact)

    over = exact.model_copy(update={"model_calls": 4})
    assert not budget.allows(over)
    with pytest.raises(BudgetExceeded) as exc:
        budget.enforce(over)
    assert exc.value.violations == ("model_calls=4>max_model_calls=3",)


def test_receipt_records_overrun_and_requires_fail_closed_termination():
    budget = _budget(max_model_calls=1)
    over = BudgetUsage(nodes=2, model_calls=2)
    with pytest.raises(ValidationError, match="over-budget receipt"):
        SearchReceipt(
            strategy_name="test",
            strategy_version="v0",
            initial_state_id=_state().state_id,
            budget=budget,
            usage=over,
            termination_reason=SearchTerminationReason.COMPLETED,
        )

    receipt = SearchReceipt(
        strategy_name="test",
        strategy_version="v0",
        initial_state_id=_state().state_id,
        budget=budget,
        usage=over,
        termination_reason=SearchTerminationReason.BUDGET_EXHAUSTED,
    )
    assert receipt.budget_violations == (
        "model_calls=2>max_model_calls=1",
    )


def test_result_and_receipt_links_are_schema_checked():
    state = _state()
    action = LegalAction(kind=ActionKind.STOP)
    receipt = SearchReceipt(
        strategy_name="baseline",
        strategy_version="v0",
        initial_state_id=state.state_id,
        selected_action_id=action.action_id,
        budget=_budget(),
        usage=state.budget_usage,
        termination_reason=SearchTerminationReason.BASELINE_SELECTED,
    )
    result = SearchResult(
        initial_state_id=state.state_id,
        selected_action=action,
        estimated_value=0.0,
        action_statistics=(
            ActionStatistics(
                action_id=action.action_id,
                prior=1.0,
                visit_count=1,
                mean_value=0.0,
            ),
        ),
        receipt=receipt,
    )
    assert result.receipt.receipt_id.startswith("szreceipt_")

    bad = deepcopy(receipt.model_dump())
    bad["selected_action_id"] = None
    bad["receipt_id"] = None
    mismatched_receipt = SearchReceipt(**bad)
    with pytest.raises(ValidationError, match="selected actions differ"):
        SearchResult(
            initial_state_id=state.state_id,
            selected_action=action,
            estimated_value=0.0,
            receipt=mismatched_receipt,
        )
