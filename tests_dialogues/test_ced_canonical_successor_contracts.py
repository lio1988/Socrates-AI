from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from backend.dialogues.ced_canonical_successor_contracts import (
    CanonicalBranchCapsule,
    CanonicalRejectionReason,
    CanonicalTaskIdentity,
    CanonicalTransitionReceipt,
    CanonicalTransitionResult,
    CanonicalTransitionStatus,
    HistoricalUsageKnowledge,
    LegalActionValidationStatus,
    NewExecutionUsage,
    ObservationCaptureKind,
    ObservationTransportStatus,
    PendingCanonicalTransition,
    ProviderBindingIdentity,
    RecordedCanonicalObservation,
    RecordedHistoricalUsage,
    RecordedObservationCompatibilityError,
    RecordedObservationProvenance,
    SuccessorUnavailableReason,
    validate_recorded_observation_compatibility,
)
from backend.dialogues.ced_search_observability_v1 import SearchStateV1
from backend.dialogues.models import AgentRole, DialogPhase, TaskKind
from backend.dialogues.socrates_zero.contracts import (
    ActionKind,
    BudgetUsage,
    LegalAction,
    SearchBudget,
    SearchState,
    canonical_json,
)


_TASK_DIGEST = "1" * 64
_CONTEXT_DIGEST = "2" * 64
_REQUEST_DIGEST = "3" * 64
_MODEL_CONFIG_DIGEST = "4" * 64
_SEMANTIC_DIGEST = "5" * 64
_CONFIGURATION_DIGEST = "6" * 64
_ARTIFACT_DIGEST = "7" * 64


def _budget(**updates: int) -> SearchBudget:
    values = {
        "max_nodes": 4,
        "max_expansions": 3,
        "max_model_calls": 0,
        "max_tool_calls": 0,
        "max_tokens": 0,
        "max_cost_microusd": 0,
        "max_wall_time_ms": 0,
        "max_depth": 1,
    }
    values.update(updates)
    return SearchBudget(**values)


def _task(**updates: Any) -> CanonicalTaskIdentity:
    values = {
        "phase": DialogPhase.OPENING,
        "round_number": 0,
        "slot_index": 0,
        "attempt_index": 0,
        "agent_id": "agent-socrates",
        "role": AgentRole.SOCRATES,
        "task_kind": TaskKind.SOCRATIC_QUESTION,
        "task_semantic_digest": _TASK_DIGEST,
        "context_digest": _CONTEXT_DIGEST,
        "request_semantic_digest": _REQUEST_DIGEST,
        "model_config_digest": _MODEL_CONFIG_DIGEST,
    }
    values.update(updates)
    return CanonicalTaskIdentity(**values)


def _action() -> LegalAction:
    return LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION)


def _binding() -> ProviderBindingIdentity:
    return ProviderBindingIdentity(
        agent_id="agent-socrates",
        provider_id="scripted-provider",
        model_id="fixture-model-v1",
        model_config_digest=_MODEL_CONFIG_DIGEST,
    )


def _capsule(**updates: Any) -> CanonicalBranchCapsule:
    values = {
        "session_id": "session-canonical-1",
        "search_state_v1_id": "szstatev1_root",
        "source_snapshot_json": canonical_json(
            {"session_id": "session-canonical-1", "task_id": "task-random-a"}
        ),
        "normalized_semantic_digest": _SEMANTIC_DIGEST,
        "configuration_digest": _CONFIGURATION_DIGEST,
        "canonical_task": _task(),
        "provider_bindings": (_binding(),),
        "budget": _budget(),
        "budget_usage": BudgetUsage(nodes=1),
    }
    values.update(updates)
    return CanonicalBranchCapsule(**values)


def _pending(**updates: Any) -> PendingCanonicalTransition:
    capsule = updates.pop("capsule", _capsule())
    action = updates.pop("selected_action", _action())
    values = {
        "source_capsule_id": capsule.capsule_id,
        "source_branch_id": capsule.branch_id,
        "root_state_v1_id": capsule.search_state_v1_id,
        "selected_action": action,
        "complete_legal_action_ids": (action.action_id,),
        "canonical_task": capsule.canonical_task,
        "expected_provider_id": "scripted-provider",
        "expected_model_id": "fixture-model-v1",
        "budget": capsule.budget,
        "budget_before": capsule.budget_usage,
        "canonical_processor_ids": (
            "ced.parse_and_validate_move/v0",
            "ced.apply_opening_response/v0",
        ),
    }
    values.update(updates)
    return PendingCanonicalTransition(**values)


def _historical(
    knowledge: HistoricalUsageKnowledge = HistoricalUsageKnowledge.COMPLETE,
    **updates: Any,
) -> RecordedHistoricalUsage:
    values: dict[str, Any] = {"knowledge": knowledge}
    if knowledge is HistoricalUsageKnowledge.COMPLETE:
        values.update(
            model_calls=0,
            tool_calls=0,
            tokens=0,
            cost_microusd=0,
            wall_time_ms=0,
        )
    values.update(updates)
    return RecordedHistoricalUsage(**values)


def _provenance(**updates: Any) -> RecordedObservationProvenance:
    values = {
        "capture_kind": ObservationCaptureKind.OFFLINE_FIXTURE,
        "source_artifact_id": "opening-accepted-v0",
        "source_artifact_digest": _ARTIFACT_DIGEST,
        "source_revision": "phase8-corpus/v0",
    }
    values.update(updates)
    return RecordedObservationProvenance(**values)


def _observation(
    pending: PendingCanonicalTransition | None = None,
    **updates: Any,
) -> RecordedCanonicalObservation:
    pending = pending or _pending()
    task = pending.canonical_task
    values = {
        "capture_id": None,
        "source_task_id": None,
        "recorded_response_id": None,
        "recorded_request_digest": None,
        "action_id": pending.selected_action.action_id,
        "phase": task.phase,
        "round_number": task.round_number,
        "slot_index": task.slot_index,
        "attempt_index": task.attempt_index,
        "agent_id": task.agent_id,
        "role": task.role,
        "task_kind": task.task_kind,
        "task_semantic_digest": task.task_semantic_digest,
        "request_semantic_digest": task.request_semantic_digest,
        "provider_id": pending.expected_provider_id,
        "configured_model_id": pending.expected_model_id,
        "actual_model_id": pending.expected_model_id,
        "model_config_digest": task.model_config_digest,
        "transport_status": ObservationTransportStatus.DELIVERED,
        "raw_text": '{"content":"What assumption carries the conclusion?"}',
        "historical_usage": _historical(),
        "provenance": _provenance(),
    }
    values.update(updates)
    return RecordedCanonicalObservation(**values)


def _replace(model: Any, **updates: Any) -> Any:
    values = model.model_dump(mode="python")
    values.update(updates)
    return type(model).model_validate(values)


def _state_v1(budget: SearchBudget, usage: BudgetUsage) -> SearchStateV1:
    return SearchStateV1(
        base_state=SearchState(
            task_kind=TaskKind.SOCRATIC_QUESTION.value,
            question="Which assumption is load-bearing?",
            phase=DialogPhase.OPENING.value,
            round_number=0,
            active_agent_id="agent-socrates",
            active_role=AgentRole.SOCRATES.value,
            active_slot_index=0,
            active_attempt_index=0,
            budget=budget,
            budget_usage=usage,
            depth=1,
        )
    )


def _successor_capsule(
    root: CanonicalBranchCapsule,
    pending: PendingCanonicalTransition,
    observation: RecordedCanonicalObservation,
    state: SearchStateV1,
) -> CanonicalBranchCapsule:
    return _capsule(
        search_state_v1_id=state.state_id,
        source_snapshot_json=canonical_json(
            {"session_id": root.session_id, "moves": ["move-canonical-opening"]}
        ),
        normalized_semantic_digest="8" * 64,
        budget_usage=pending.budget_before.plus(
            pending.reserved_usage.budget_delta
        ),
        parent_branch_id=root.branch_id,
        produced_by_transition_id=pending.transition_id,
        produced_by_observation_id=observation.observation_id,
    )


def _accepted_receipt(
    root: CanonicalBranchCapsule,
    pending: PendingCanonicalTransition,
    observation: RecordedCanonicalObservation,
    successor: CanonicalBranchCapsule,
) -> CanonicalTransitionReceipt:
    return CanonicalTransitionReceipt(
        transition_id=pending.transition_id,
        root_capsule_id=root.capsule_id,
        root_branch_id=root.branch_id,
        root_state_v1_id=root.search_state_v1_id,
        branch_id=successor.branch_id,
        action_id=pending.selected_action.action_id,
        observation_id=observation.observation_id,
        observation_digest=observation.raw_output_digest,
        status=CanonicalTransitionStatus.APPLIED_ACCEPTED,
        legal_action_validation=LegalActionValidationStatus.PASSED,
        resulting_move_id="move-canonical-opening",
        source_state_hash=root.normalized_semantic_digest,
        successor_state_hash=successor.normalized_semantic_digest,
        successor_state_v1_id=successor.search_state_v1_id,
        canonical_processor_ids=pending.canonical_processor_ids,
        budget=pending.budget,
        budget_before=pending.budget_before,
        new_execution_usage=pending.reserved_usage,
        budget_after=pending.budget_before.plus(
            pending.reserved_usage.budget_delta
        ),
        recorded_historical_usage=observation.historical_usage,
    )


def test_capsule_is_deeply_frozen_canonical_and_semantically_identified() -> None:
    capsule = _capsule()
    same_semantics = _capsule(
        source_snapshot_json=canonical_json(
            {"session_id": "session-canonical-1", "task_id": "task-random-b"}
        )
    )

    assert capsule.source_snapshot_digest != same_semantics.source_snapshot_digest
    assert capsule.source_execution_id == same_semantics.source_execution_id
    assert capsule.capsule_id == same_semantics.capsule_id
    assert capsule.branch_id == same_semantics.branch_id
    assert isinstance(capsule.source_snapshot_json, str)
    with pytest.raises(ValidationError):
        capsule.session_id = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="canonical JSON encoding"):
        _capsule(source_snapshot_json='{ "session_id": "session-canonical-1" }')
    with pytest.raises(ValidationError, match="capsule_id"):
        _replace(capsule, capsule_id="forged")


def test_capsule_identity_changes_for_move_relevant_session_or_semantics() -> None:
    capsule = _capsule()
    other_session = _capsule(session_id="session-canonical-2")
    other_semantics = _capsule(normalized_semantic_digest="9" * 64)

    assert other_session.capsule_id != capsule.capsule_id
    assert other_semantics.capsule_id != capsule.capsule_id


def test_pending_freezes_exact_supported_family_and_one_offline_reservation() -> None:
    pending = _pending(
        canonical_processor_ids=(
            "ced.apply_opening_response/v0",
            "ced.parse_and_validate_move/v0",
        )
    )

    assert pending.pending_id == pending.transition_id
    assert pending.complete_legal_action_ids == (pending.selected_action.action_id,)
    assert pending.canonical_processor_ids == (
        "ced.apply_opening_response/v0",
        "ced.parse_and_validate_move/v0",
    )
    assert pending.reserved_usage.budget_delta == BudgetUsage(
        nodes=1, expansions=1, max_depth_observed=1
    )
    assert pending.reserved_usage.budget_delta.model_calls == 0
    assert pending.reserved_usage.budget_delta.tool_calls == 0
    assert pending.reserved_usage.budget_delta.tokens == 0
    assert pending.reserved_usage.budget_delta.cost_microusd == 0

    with pytest.raises(ValidationError, match="complete hard-legal set"):
        _pending(complete_legal_action_ids=("different-action",))
    with pytest.raises(ValidationError, match="opening/Socrates"):
        _pending(canonical_task=_task(round_number=1))
    with pytest.raises(ValidationError, match="reserve one successor"):
        _pending(reserved_usage=NewExecutionUsage.not_applied())


def test_pending_fails_closed_when_the_one_transition_exceeds_budget() -> None:
    capsule = _capsule(
        budget=_budget(max_nodes=1, max_expansions=0),
        budget_usage=BudgetUsage(nodes=1),
    )
    with pytest.raises(ValidationError, match="search budget exceeded"):
        _pending(capsule=capsule)


def test_new_execution_usage_accepts_only_zero_or_exact_one_transition() -> None:
    assert not NewExecutionUsage.not_applied().applied
    assert NewExecutionUsage().applied
    with pytest.raises(ValidationError, match="exactly one offline successor"):
        NewExecutionUsage(
            budget_delta=BudgetUsage(
                nodes=1,
                expansions=1,
                model_calls=1,
                max_depth_observed=1,
            )
        )
    with pytest.raises(ValidationError):
        NewExecutionUsage(observation_applications=True)


def test_historical_usage_preserves_complete_partial_and_unknown_truth() -> None:
    complete = _historical()
    partial = _historical(
        HistoricalUsageKnowledge.PARTIAL,
        model_calls=0,
    )
    unavailable = _historical(HistoricalUsageKnowledge.UNAVAILABLE)

    assert complete.model_calls == 0
    assert partial.model_calls == 0 and partial.tokens is None
    assert unavailable.model_calls is None and unavailable.tokens is None
    with pytest.raises(ValidationError, match="requires every measured"):
        _historical(HistoricalUsageKnowledge.COMPLETE, tokens=None)
    with pytest.raises(ValidationError, match="keep every measured value unknown"):
        _historical(HistoricalUsageKnowledge.UNAVAILABLE, model_calls=0)
    with pytest.raises(ValidationError, match="both known and unknown"):
        _historical(HistoricalUsageKnowledge.PARTIAL)


def test_observation_identity_excludes_unavailable_or_volatile_audit_ids() -> None:
    observation = _observation()
    recaptured = _replace(
        observation,
        observation_id=None,
        capture_id="capture-new",
        source_task_id="task-random-new",
        recorded_response_id="response-random-new",
        recorded_request_digest="a" * 64,
    )
    changed_raw = _replace(
        observation,
        observation_id=None,
        raw_output_digest=None,
        raw_text="different raw output",
    )

    assert observation.capture_id is None
    assert observation.source_task_id is None
    assert observation.observation_id == recaptured.observation_id
    assert observation.observation_id != changed_raw.observation_id


def test_observation_transport_shape_and_digest_are_fail_closed() -> None:
    delivered = _observation(raw_text="")
    failed = _observation(
        transport_status=ObservationTransportStatus.TIMEOUT,
        transport_error_code="provider_timeout",
        raw_text=None,
        actual_model_id=None,
    )

    assert delivered.raw_output_digest is not None
    assert failed.raw_output_digest is not None
    with pytest.raises(ValidationError, match="requires exact raw_text"):
        _observation(raw_text=None)
    with pytest.raises(ValidationError, match="cannot contain raw_text"):
        _observation(
            transport_status=ObservationTransportStatus.ERROR,
            transport_error_code="error",
        )
    with pytest.raises(ValidationError, match="raw_output_digest"):
        _observation(raw_output_digest="0" * 64)


def test_observation_future_label_firewall_does_not_scan_opaque_raw_prose() -> None:
    raw = (
        'Ordinary text may literally discuss future_state, reward, '
        'benchmark_label, or resulting_move_id.'
    )
    assert _observation(raw_text=raw).raw_text == raw

    envelope = _observation().model_dump(mode="python")
    envelope["reward"] = 1
    with pytest.raises(ValidationError, match="forbidden future/control fields"):
        RecordedCanonicalObservation.model_validate(envelope)
    envelope = _observation().model_dump(mode="python")
    envelope["unrecognized_control"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RecordedCanonicalObservation.model_validate(envelope)


def test_observation_compatibility_uses_semantics_not_random_audit_ids() -> None:
    pending = _pending()
    observation = _observation(
        pending,
        capture_id="capture-a",
        source_task_id="unrelated-random-task-id",
    )
    validate_recorded_observation_compatibility(pending, observation)

    wrong_task = _replace(
        observation,
        observation_id=None,
        task_semantic_digest="a" * 64,
    )
    with pytest.raises(RecordedObservationCompatibilityError) as task_error:
        validate_recorded_observation_compatibility(pending, wrong_task)
    assert (
        task_error.value.reason
        is SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH
    )

    wrong_provider = _replace(
        observation,
        observation_id=None,
        provider_id="different-provider",
    )
    with pytest.raises(RecordedObservationCompatibilityError) as provider_error:
        validate_recorded_observation_compatibility(pending, wrong_provider)
    assert (
        provider_error.value.reason
        is SuccessorUnavailableReason.OBSERVATION_PROVIDER_MISMATCH
    )


def test_applied_accepted_receipt_and_result_link_every_successor_identity() -> None:
    root = _capsule()
    pending = _pending(capsule=root)
    observation = _observation(pending)
    after = pending.budget_before.plus(pending.reserved_usage.budget_delta)
    state = _state_v1(pending.budget, after)
    successor = _successor_capsule(root, pending, observation, state)
    receipt = _accepted_receipt(root, pending, observation, successor)
    result = CanonicalTransitionResult(
        transition_id=pending.transition_id,
        status=CanonicalTransitionStatus.APPLIED_ACCEPTED,
        receipt=receipt,
        successor_capsule=successor,
        successor_search_state_v1=state,
    )

    assert receipt.resulting_move_id == "move-canonical-opening"
    assert receipt.receipt_id == f"cedreceipt_{receipt.receipt_hash}"
    assert result.result_id is not None
    with pytest.raises(ValidationError, match="budget_after"):
        _replace(receipt, receipt_id=None, receipt_hash=None, budget_after=BudgetUsage())
    with pytest.raises(ValidationError, match="receipt semantic-state hashes"):
        bad_receipt = _replace(
            receipt,
            receipt_id=None,
            receipt_hash=None,
            successor_state_hash="0" * 64,
        )
        CanonicalTransitionResult(
            transition_id=pending.transition_id,
            status=CanonicalTransitionStatus.APPLIED_ACCEPTED,
            receipt=bad_receipt,
            successor_capsule=successor,
            successor_search_state_v1=state,
        )


def test_canonical_rejection_is_applied_successor_but_has_no_move() -> None:
    root = _capsule()
    pending = _pending(capsule=root)
    observation = _observation(pending, raw_text="{}")
    after = pending.budget_before.plus(pending.reserved_usage.budget_delta)
    state = _state_v1(pending.budget, after)
    successor = _successor_capsule(root, pending, observation, state)
    receipt = CanonicalTransitionReceipt(
        transition_id=pending.transition_id,
        root_capsule_id=root.capsule_id,
        root_branch_id=root.branch_id,
        root_state_v1_id=root.search_state_v1_id,
        branch_id=successor.branch_id,
        action_id=pending.selected_action.action_id,
        observation_id=observation.observation_id,
        observation_digest=observation.raw_output_digest,
        status=CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        legal_action_validation=LegalActionValidationStatus.PASSED,
        canonical_rejection_reason=CanonicalRejectionReason.SCHEMA_REJECTED,
        source_state_hash=root.normalized_semantic_digest,
        successor_state_hash=successor.normalized_semantic_digest,
        successor_state_v1_id=successor.search_state_v1_id,
        canonical_processor_ids=pending.canonical_processor_ids,
        budget=pending.budget,
        budget_before=pending.budget_before,
        new_execution_usage=pending.reserved_usage,
        budget_after=after,
        recorded_historical_usage=observation.historical_usage,
    )
    result = CanonicalTransitionResult(
        transition_id=pending.transition_id,
        status=CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        receipt=receipt,
        successor_capsule=successor,
        successor_search_state_v1=state,
    )

    assert result.successor_capsule is not None
    assert receipt.resulting_move_id is None
    with pytest.raises(ValidationError, match="cannot contain an accepted move_id"):
        _replace(
            receipt,
            receipt_id=None,
            receipt_hash=None,
            resulting_move_id="branch-derived-move",
        )


def test_successor_unavailable_never_contains_a_successor_or_fabricated_usage() -> None:
    root = _capsule()
    pending = _pending(capsule=root)
    zero = NewExecutionUsage.not_applied()
    receipt = CanonicalTransitionReceipt(
        transition_id=pending.transition_id,
        root_capsule_id=root.capsule_id,
        root_branch_id=root.branch_id,
        root_state_v1_id=root.search_state_v1_id,
        action_id=pending.selected_action.action_id,
        status=CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
        legal_action_validation=LegalActionValidationStatus.PASSED,
        unavailable_reason=SuccessorUnavailableReason.MISSING_OBSERVATION,
        source_state_hash=root.normalized_semantic_digest,
        canonical_processor_ids=pending.canonical_processor_ids,
        budget=pending.budget,
        budget_before=pending.budget_before,
        new_execution_usage=zero,
        budget_after=pending.budget_before,
    )
    result = CanonicalTransitionResult(
        transition_id=pending.transition_id,
        status=CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
        receipt=receipt,
    )

    assert result.successor_capsule is None
    assert receipt.observation_id is None
    assert receipt.recorded_historical_usage is None
    assert receipt.new_execution_usage.budget_delta == BudgetUsage()
    with pytest.raises(ValidationError, match="cannot create a branch"):
        _replace(
            receipt,
            receipt_id=None,
            receipt_hash=None,
            branch_id="invented-successor",
        )


def test_branch_lineage_changes_without_contaminating_canonical_move_identity() -> None:
    root = _capsule()
    pending = _pending(capsule=root)
    observation_a = _observation(pending, raw_text="first raw observation")
    observation_b = _observation(pending, raw_text="second raw observation")
    after = pending.budget_before.plus(pending.reserved_usage.budget_delta)
    state = _state_v1(pending.budget, after)
    successor_a = _successor_capsule(root, pending, observation_a, state)
    successor_b = _successor_capsule(root, pending, observation_b, state)
    receipt_a = _accepted_receipt(root, pending, observation_a, successor_a)
    receipt_b = _accepted_receipt(root, pending, observation_b, successor_b)

    assert successor_a.capsule_id == successor_b.capsule_id
    assert successor_a.branch_id != successor_b.branch_id
    assert receipt_a.resulting_move_id == receipt_b.resulting_move_id
    assert receipt_a.receipt_id != receipt_b.receipt_id
