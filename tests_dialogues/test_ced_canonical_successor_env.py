"""Adversarial locks for the Phase 8 isolated canonical successor environment."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from collections import defaultdict
from typing import Any, Callable

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.ced_canonical_successor import (
    CanonicalSuccessorEnvironmentV0,
    CanonicalSuccessorUnavailable,
    canonical_capsule_semantic_snapshot,
)
from backend.dialogues.ced_canonical_successor_cases_v1 import (
    FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1,
    canonical_successor_reference_field_digests,
)
from backend.dialogues.ced_canonical_successor_contracts import (
    CanonicalRejectionReason,
    CanonicalTransitionStatus,
    NewExecutionUsage,
    ObservationTransportStatus,
    SuccessorUnavailableReason,
)
from backend.dialogues.ced_canonical_successor_recording_fixtures import (
    CANONICAL_RECORDING_AGENT_IDS,
    CANONICAL_RECORDING_PROVIDER_MODELS,
    CanonicalSuccessorRecordingProvider,
    build_canonical_recording_root,
)
from backend.dialogues.models import TaskKind
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.socrates_zero.contracts import (
    ActionKind,
    BudgetUsage,
    LegalAction,
    SearchBudget,
    canonical_json,
)


class CountingScriptedProvider(ScriptedMockProvider):
    """A normal offline seat with an explicit dispatch tripwire."""

    def __init__(
        self,
        provider_id: str,
        *,
        model_id: str,
        raw_text: str | None = None,
    ) -> None:
        super().__init__(provider_id, model_id=model_id)
        self.generate_calls = 0
        self.raw_text = raw_text

    async def generate_agent_move(self, task, agent_state):
        self.generate_calls += 1
        return await super().generate_agent_move(task, agent_state)

    async def _produce_raw_text(self, task, agent_state) -> str:
        if self.raw_text is not None:
            assert task.task_kind is TaskKind.SOCRATIC_QUESTION
            return self.raw_text
        return await super()._produce_raw_text(task, agent_state)


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


def _build_ced(
    question: str,
    *,
    session_id: str,
    raw_text: str | None = None,
    phase_retry: bool = False,
) -> tuple[CEDOrchestrator, Any, list[CountingScriptedProvider]]:
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    adapters: list[CountingScriptedProvider] = []
    for index in range(2):
        provider_id = f"phase8-seat-{index}"
        model_id = f"phase8-model/{index}"
        adapter = CountingScriptedProvider(
            provider_id,
            model_id=model_id,
            raw_text=raw_text,
        )
        adapters.append(adapter)
        registry.register(adapter)
    ced = CEDOrchestrator(
        [SocraticAgent(f"phase8-agent-{index}", provider) for index in range(4)],
        provider,
        registry=registry,
        phase_retry=phase_retry,
    )
    state = ced.create_session(question, session_id=session_id)
    return ced, state, adapters


def _build_recorded_case(case_name: str):
    blueprint = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(case_name)
    return build_canonical_recording_root(
        question=blueprint.recorded_question,
        raw_text=blueprint.raw_text,
        session_id=blueprint.recorded_session_id,
    )


def _build_recording_variant(
    case_name: str,
    *,
    agent_ids: tuple[str, ...] = CANONICAL_RECORDING_AGENT_IDS,
    provider_models: tuple[tuple[str, str], ...] = (
        CANONICAL_RECORDING_PROVIDER_MODELS
    ),
    quorum_for_assembly: int | None = None,
):
    """Build a legitimate offline root with one controlled identity mismatch."""

    case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(case_name)
    provider = FakeProvider()
    registry_kwargs = (
        {}
        if quorum_for_assembly is None
        else {"quorum_for_assembly": quorum_for_assembly}
    )
    registry = CouncilProviderRegistry(**registry_kwargs)
    adapters = tuple(
        CanonicalSuccessorRecordingProvider(
            provider_id,
            model_id=model_id,
            recorded_raw_text=case.raw_text or "",
        )
        for provider_id, model_id in provider_models
    )
    for adapter in adapters:
        registry.register(adapter)
    ced = CEDOrchestrator(
        [SocraticAgent(agent_id, provider) for agent_id in agent_ids],
        provider,
        registry=registry,
        phase_retry=False,
    )
    state = ced.create_session(
        case.recorded_question,
        session_id=case.recorded_session_id,
    )
    return ced, state, adapters


def _source_snapshot(ced: CEDOrchestrator, state: Any) -> dict[str, Any]:
    """Exact mutable target surface, with process-local adapter identity retained."""

    session_id = state.session_id
    ledger_names = (
        "_session_lessons",
        "_phase_retries",
        "_phase_dispatch",
        "_commitments",
        "_aporia",
        "_socratic_audit_rows",
        "_cycle_log",
        "_tree_audits",
        "_injected_lessons",
        "_hybrid_shadow_diagnostics",
    )
    return {
        "state": state.model_dump(mode="json"),
        "target_ledgers": {
            name: copy.deepcopy(getattr(ced, name).get(session_id, "__absent__"))
            for name in ledger_names
        },
        "registry_last_failed": tuple(ced.registry._last_failed),
        "registry_adapter_ids": tuple(
            id(adapter) for adapter in ced.registry.all_adapters()
        ),
        "adapter_order": tuple(
            (adapter.provider_id, id(adapter))
            for adapter in ced._session_adapter_orders.get(session_id, ())
        ),
        "adapter_bindings": tuple(
            sorted(
                (agent_id, adapter.provider_id, id(adapter))
                for agent_id, adapter in ced._session_adapter_bindings.get(
                    session_id, {}
                ).items()
            )
        ),
        "provider_calls": tuple(
            getattr(adapter, "generate_calls", None)
            for adapter in ced.registry.all_adapters()
        ),
    }


def _capture_and_prepare(
    env: CanonicalSuccessorEnvironmentV0,
    ced: CEDOrchestrator,
    state: Any,
    *,
    budget: SearchBudget | None = None,
    usage: BudgetUsage | None = None,
):
    budget = budget or _budget()
    usage = usage or BudgetUsage(nodes=1)
    capsule = env.capture_capsule(
        ced,
        state,
        budget=budget,
        budget_usage=usage,
    )
    action = LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION)
    pending = env.prepare_transition(capsule, action, budget)
    return capsule, pending


def _case_observation(pending, case_name: str):
    return FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        case_name
    ).materialize(pending)


def _replace_observation(observation, **updates):
    payload = observation.model_dump(mode="python")
    payload.update(updates)
    payload["observation_id"] = None
    if "raw_text" in updates or "transport_status" in updates:
        payload["raw_output_digest"] = None
    return type(observation).model_validate(payload)


def _unavailable_reason(call: Callable[[], Any]) -> SuccessorUnavailableReason:
    with pytest.raises(CanonicalSuccessorUnavailable) as captured:
        call()
    return captured.value.reason


def _unavailable_result_reason(call: Callable[[], Any]) -> SuccessorUnavailableReason:
    result = call()
    assert result.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    assert result.successor_capsule is None
    assert result.successor_search_state_v1 is None
    assert result.receipt.new_execution_usage == NewExecutionUsage.not_applied()
    assert result.receipt.unavailable_reason is not None
    return result.receipt.unavailable_reason


def test_capture_is_detached_and_does_not_mutate_source_or_dispatch() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, adapters = _build_ced(
        "Is knowledge merely justified true belief?",
        session_id="phase8-capture-isolation",
    )
    before = _source_snapshot(ced, state)

    capsule, pending = _capture_and_prepare(env, ced, state)

    assert _source_snapshot(ced, state) == before
    assert all(adapter.generate_calls == 0 for adapter in adapters)
    assert isinstance(capsule.source_snapshot_json, str)
    assert pending.source_capsule == capsule
    assert pending.source_capsule_id == capsule.capsule_id
    assert pending.root_state_v1_id == capsule.search_state_v1_id
    assert pending.expected_model_id


@pytest.mark.parametrize(
    "invalidator",
    (
        lambda ced, state: setattr(state, "round_number", 1),
        lambda ced, state: setattr(ced, "phase_retry", True),
        lambda ced, state: setattr(
            ced.registry.all_adapters()[0], "is_fake", False
        ),
    ),
    ids=(
        "nonzero-opening-round",
        "phase-retry-needs-second-observation",
        "non-offline-adapter",
    ),
)
def test_capture_rejects_noncanonical_or_multi_observation_roots(invalidator) -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_ced("Q?", session_id="phase8-invalid-root")
    invalidator(ced, state)
    before = _source_snapshot(ced, state)

    reason = _unavailable_reason(
        lambda: env.capture_capsule(
            ced,
            state,
            budget=_budget(),
            budget_usage=BudgetUsage(nodes=1),
        )
    )

    assert reason is SuccessorUnavailableReason.INVALID_ROOT
    assert _source_snapshot(ced, state) == before


def test_capture_reports_existing_usage_beyond_budget_as_budget_exhausted() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_ced("Q?", session_id="phase8-root-budget")

    reason = _unavailable_reason(
        lambda: env.capture_capsule(
            ced,
            state,
            budget=_budget(max_nodes=1),
            budget_usage=BudgetUsage(nodes=2),
        )
    )

    assert reason is SuccessorUnavailableReason.BUDGET_EXHAUSTED


def test_prepare_distinguishes_unsupported_family_from_illegal_action() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_ced("Q?", session_id="phase8-action-failures")
    capsule = env.capture_capsule(
        ced,
        state,
        budget=_budget(),
        budget_usage=BudgetUsage(nodes=1),
    )
    unsupported = LegalAction(kind=ActionKind.RUN_ELENCHUS)
    illegal = LegalAction(
        kind=ActionKind.ASK_SOCRATIC_QUESTION,
        required_capabilities=("unavailable-capability",),
    )

    assert _unavailable_reason(
        lambda: env.prepare_transition(capsule, unsupported, capsule.budget)
    ) is SuccessorUnavailableReason.UNSUPPORTED_ACTION_FAMILY
    assert _unavailable_reason(
        lambda: env.prepare_transition(capsule, illegal, capsule.budget)
    ) is SuccessorUnavailableReason.ILLEGAL_ACTION


def test_prepare_fails_before_application_when_budget_cannot_reserve_transition() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    budget = _budget(max_nodes=1, max_expansions=0)
    usage = BudgetUsage(nodes=1)
    ced, state, _ = _build_ced("Q?", session_id="phase8-budget-exhausted")
    capsule = env.capture_capsule(
        ced,
        state,
        budget=budget,
        budget_usage=usage,
    )

    reason = _unavailable_reason(
        lambda: env.prepare_transition(
            capsule,
            LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
            budget,
        )
    )

    assert reason is SuccessorUnavailableReason.BUDGET_EXHAUSTED
    assert capsule.budget_usage == usage


def test_missing_forged_and_future_observations_fail_without_mutation() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    capsule, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")
    before = _source_snapshot(ced, state)

    assert _unavailable_result_reason(
        lambda: env.apply_observation(pending, None)
    ) is SuccessorUnavailableReason.MISSING_OBSERVATION

    assert _unavailable_result_reason(
        lambda: env.apply_observation(
            pending,
            {"capture_receipt_id": observation.capture_receipt_id},
        )
    ) is SuccessorUnavailableReason.INVALID_OBSERVATION

    forged = observation.model_copy(update={"observation_id": "forged"})
    assert _unavailable_result_reason(
        lambda: env.apply_observation(pending, forged)
    ) is SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY

    forged_mapping = observation.model_dump(mode="python")
    forged_mapping["observation_id"] = "forged-mapping"
    forged_result = env.apply_observation(pending, forged_mapping)
    assert (
        forged_result.receipt.unavailable_reason
        is SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY
    )
    assert forged_result.receipt.recorded_historical_usage is None

    raw_with_future_label = json.dumps(
        {
            "content": {
                "question": "Which assumption is doing the decisive work?",
                "operator": "expose_premise",
                "epistemic_marker": "open_uncertainty",
            },
            "confidence": 0.7,
            "reward": 1,
        }
    )
    future = _replace_observation(
        observation,
        raw_text=raw_with_future_label,
    )
    assert _unavailable_result_reason(
        lambda: env.apply_observation(pending, future)
    ) is SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN

    assert _source_snapshot(ced, state) == before
    assert capsule == pending.source_capsule


def test_caller_rebinding_fails_manifest_firewall_end_to_end() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    source_ced, source_state, _ = _build_recorded_case("opening-scripted-mock")
    _, source_pending = _capture_and_prepare(env, source_ced, source_state)
    original = _case_observation(source_pending, "opening-scripted-mock")
    other_ced, other_state, other_adapters = _build_recorded_case(
        "opening-empty-question"
    )
    other_before = _source_snapshot(other_ced, other_state)
    _, other_pending = _capture_and_prepare(env, other_ced, other_state)
    rebound_payload = original.model_dump(mode="python")
    rebound_payload.update(
        observation_id=None,
        source_capsule_id=other_pending.source_capsule_id,
        source_execution_id=other_pending.source_capsule.source_execution_id,
        source_configuration_digest=(
            other_pending.source_capsule.configuration_digest
        ),
        action_id=other_pending.selected_action.action_id,
        task_identity=other_pending.canonical_task,
        provider_id=other_pending.expected_provider_id,
        configured_model_id=other_pending.expected_model_id,
        actual_model_id=other_pending.expected_model_id,
        model_config_digest=other_pending.canonical_task.model_config_digest,
    )
    rebound = type(original).model_validate(rebound_payload)

    result = env.apply_observation(other_pending, rebound)

    assert rebound.raw_text == original.raw_text
    assert rebound.observation_id != original.observation_id
    assert result.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    assert (
        result.receipt.unavailable_reason
        is SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY
    )
    assert result.successor_capsule is None
    assert result.successor_search_state_v1 is None
    assert result.receipt.recorded_historical_usage is None
    assert _source_snapshot(other_ced, other_state) == other_before
    assert all(adapter.generate_calls == 0 for adapter in other_adapters)


def test_same_binding_and_raw_on_a_different_canonical_question_fails_closed() -> None:
    """One changed root question/context cannot borrow an accepted observation."""

    env = CanonicalSuccessorEnvironmentV0()
    accepted = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-scripted-mock"
    )
    context_variant = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-injection-question"
    ).recorded_question
    ced, state, adapters = build_canonical_recording_root(
        question=context_variant,
        raw_text=accepted.raw_text or "",
        session_id=accepted.recorded_session_id,
    )
    before = _source_snapshot(ced, state)
    _, pending = _capture_and_prepare(env, ced, state)
    observation = accepted.observation

    assert state.session_id == accepted.recorded_session_id
    assert state.question != accepted.recorded_question
    assert observation.raw_text == accepted.raw_text
    assert observation.action_id == pending.selected_action.action_id
    assert observation.provider_id == pending.expected_provider_id
    assert observation.configured_model_id == pending.expected_model_id
    assert observation.actual_model_id == pending.expected_model_id
    assert observation.model_config_digest == pending.canonical_task.model_config_digest
    assert (
        observation.source_configuration_digest
        == pending.source_capsule.configuration_digest
    )
    for field in (
        "phase",
        "round_number",
        "slot_index",
        "attempt_index",
        "agent_id",
        "role",
        "task_kind",
        "model_config_digest",
    ):
        assert getattr(observation.task_identity, field) == getattr(
            pending.canonical_task, field
        )
    assert (
        observation.task_identity.source_session_semantic_id
        != pending.canonical_task.source_session_semantic_id
    )
    assert (
        observation.task_identity.context_digest
        != pending.canonical_task.context_digest
    )
    assert (
        observation.task_identity.request_semantic_digest
        != pending.canonical_task.request_semantic_digest
    )

    result = env.apply_observation(pending, observation)

    assert result.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    assert (
        result.receipt.unavailable_reason
        is SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH
    )
    assert result.successor_capsule is None
    assert result.successor_search_state_v1 is None
    assert result.receipt.new_execution_usage == NewExecutionUsage.not_applied()
    assert _source_snapshot(ced, state) == before
    assert all(adapter.generate_calls == 0 for adapter in adapters)


@pytest.mark.parametrize(
    ("probe", "expected_reason"),
    (
        ("root", SuccessorUnavailableReason.ROOT_CONTEXT_MISMATCH),
        ("task", SuccessorUnavailableReason.OBSERVATION_TASK_MISMATCH),
        ("provider", SuccessorUnavailableReason.OBSERVATION_PROVIDER_MISMATCH),
        ("model", SuccessorUnavailableReason.OBSERVATION_MODEL_MISMATCH),
        ("config", SuccessorUnavailableReason.OBSERVATION_CONFIG_MISMATCH),
    ),
)
def test_authoritative_observation_identity_mismatches_are_distinct(
    probe: str,
    expected_reason: SuccessorUnavailableReason,
) -> None:
    """Probe compatibility with one exact manifest observation, never a relabel."""

    env = CanonicalSuccessorEnvironmentV0()
    case = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-scripted-mock"
    )
    observation = case.observation

    if probe == "root":
        ced, state, adapters = _build_recorded_case("opening-empty-question")
    elif probe == "task":
        ced, state, adapters = _build_recording_variant(
            "opening-scripted-mock",
            agent_ids=tuple(f"phase8-task-variant-{index}" for index in range(4)),
        )
    elif probe == "provider":
        ced, state, adapters = _build_recorded_case("opening-scripted-mock")
        active_agent_id = observation.task_identity.agent_id
        current = ced._session_adapter_bindings[state.session_id][active_agent_id]
        replacement = next(adapter for adapter in adapters if adapter is not current)
        # The public roster/task context is unchanged; only the legitimate
        # session-stable provider binding for this canonical seat differs.
        ced._session_adapter_bindings[state.session_id][active_agent_id] = replacement
    elif probe == "model":
        ced, state, adapters = _build_recording_variant(
            "opening-scripted-mock",
            provider_models=tuple(
                (provider_id, f"{model_id}-variant")
                for provider_id, model_id in CANONICAL_RECORDING_PROVIDER_MODELS
            ),
        )
    else:
        assert probe == "config"
        ced, state, adapters = _build_recording_variant(
            "opening-scripted-mock",
            quorum_for_assembly=7,
        )

    before = _source_snapshot(ced, state)
    _, pending = _capture_and_prepare(env, ced, state)

    result = env.apply_observation(pending, observation)

    assert result.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    assert result.receipt.unavailable_reason is expected_reason
    assert result.receipt.observation_id == observation.observation_id
    assert result.receipt.recorded_historical_usage == observation.historical_usage
    assert result.receipt.new_execution_usage == NewExecutionUsage.not_applied()
    assert _source_snapshot(ced, state) == before
    assert all(adapter.generate_calls == 0 for adapter in adapters)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("future_state", {"phase": "synthesis"}),
        ("reward", 1),
        ("benchmark_label", "accepted"),
    ),
)
def test_model_copy_cannot_hide_future_labels_from_serialization(field, value) -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")
    poisoned = observation.model_copy(update={field: value})

    assert _unavailable_result_reason(
        lambda: env.apply_observation(pending, poisoned)
    ) is SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN


def test_nested_model_copy_cannot_hide_future_labels() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")
    provenance = observation.provenance.model_copy(update={"reward": 1})
    poisoned = observation.model_copy(update={"provenance": provenance})

    assert _unavailable_result_reason(
        lambda: env.apply_observation(pending, poisoned)
    ) is SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN


@pytest.mark.parametrize(
    "field",
    (
        "successor_capsule",
        "successor_search_state_v1",
        "expected_move_id",
        "ground_truth",
        "terminal_status",
        "transition_receipt",
        "arbitrary_side_channel",
    ),
)
def test_structured_raw_envelope_rejects_future_or_unknown_side_channels(field) -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")
    payload = json.loads(observation.raw_text)
    payload[field] = {"invented": True}
    poisoned = _replace_observation(
        observation,
        raw_text=json.dumps(payload, sort_keys=True),
    )

    assert _unavailable_result_reason(
        lambda: env.apply_observation(pending, poisoned)
    ) is SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN


def test_mapping_observation_rejects_nested_future_control_fields() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")
    poisoned = observation.model_dump(mode="python")
    poisoned["provenance"]["reward"] = 1

    assert _unavailable_result_reason(
        lambda: env.apply_observation(pending, poisoned)
    ) is SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN


def test_apply_rederives_pending_and_rejects_a_self_consistent_forged_root() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    capsule_payload = pending.source_capsule.model_dump(mode="python")
    capsule_payload.update(
        normalized_semantic_digest="0" * 64,
        capsule_id=None,
        branch_id=None,
        source_execution_id=None,
    )
    forged_capsule = type(pending.source_capsule).model_validate(capsule_payload)
    pending_payload = pending.model_dump(mode="python")
    pending_payload.update(
        source_capsule=forged_capsule,
        source_capsule_id=forged_capsule.capsule_id,
        source_branch_id=forged_capsule.branch_id,
        transition_id=None,
        replay_task_id=None,
    )
    forged_pending = type(pending).model_validate(pending_payload)
    observation = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(
        "opening-scripted-mock"
    ).observation

    assert _unavailable_reason(
        lambda: env.apply_observation(forged_pending, observation)
    ) is SuccessorUnavailableReason.INVALID_ROOT


def test_successor_capsule_cannot_be_stripped_into_a_second_v0_transition() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")
    first = env.apply_observation(pending, observation)
    successor = first.successor_capsule
    assert successor is not None
    pending_payload = pending.model_dump(mode="python")
    pending_payload.update(
        source_capsule=successor,
        source_capsule_id=successor.capsule_id,
        source_branch_id=successor.branch_id,
        root_state_v1_id=successor.search_state_v1_id,
        budget_before=successor.budget_usage,
        transition_id=None,
        replay_task_id=None,
    )
    forged_second = type(pending).model_validate(pending_payload)

    assert _unavailable_reason(
        lambda: env.apply_observation(forged_second, observation)
    ) is SuccessorUnavailableReason.INVALID_ROOT


def test_unmanifested_transport_relabel_fails_before_canonical_processing() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    delivered = _case_observation(pending, "opening-scripted-mock")
    refused = _replace_observation(
        delivered,
        transport_status=ObservationTransportStatus.REFUSED,
        transport_error_code="provider_refused",
        raw_text=None,
    )

    result = env.apply_observation(pending, refused)

    assert result.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    assert (
        result.receipt.unavailable_reason
        is SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY
    )
    assert result.receipt.recorded_historical_usage is None
    assert result.receipt.new_execution_usage == NewExecutionUsage.not_applied()


def test_manifest_authorized_transport_without_canonical_equivalent_is_rejected(
    monkeypatch,
) -> None:
    """Inject manifest authorization only to exercise the transport boundary."""

    env = CanonicalSuccessorEnvironmentV0()
    ced, state, adapters = _build_recorded_case("opening-scripted-mock")
    source_before = _source_snapshot(ced, state)
    _, pending = _capture_and_prepare(env, ced, state)
    delivered = _case_observation(pending, "opening-scripted-mock")
    refused = _replace_observation(
        delivered,
        transport_status=ObservationTransportStatus.REFUSED,
        transport_error_code="provider_refused",
        raw_text=None,
    )
    monkeypatch.setattr(
        "backend.dialogues.ced_canonical_successor."
        "verify_authoritative_recorded_observation",
        lambda candidate: candidate == refused,
    )

    result = env.apply_observation(pending, refused)

    assert result.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    assert (
        result.receipt.unavailable_reason
        is SuccessorUnavailableReason.CANONICAL_PROCESSING_REJECTED
    )
    assert result.receipt.recorded_historical_usage == refused.historical_usage
    assert result.receipt.new_execution_usage == NewExecutionUsage.not_applied()
    assert result.successor_capsule is None
    assert result.successor_search_state_v1 is None
    assert _source_snapshot(ced, state) == source_before
    assert all(adapter.generate_calls == 0 for adapter in adapters)


def test_apply_delegates_once_to_canonical_helpers_and_never_dispatches_provider(
    monkeypatch,
) -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, adapters = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")
    calls: dict[str, list[int]] = defaultdict(list)

    for name in (
        "_prepare_registry_phase",
        "_build_registry_phase_task",
        "_apply_registry_response",
        "_effective_registry_quorum",
        "_finalize_registry_phase",
    ):
        original = getattr(CEDOrchestrator, name)

        def wrapper(self, *args, __name=name, __original=original, **kwargs):
            calls[__name].append(id(self))
            return __original(self, *args, **kwargs)

        monkeypatch.setattr(CEDOrchestrator, name, wrapper)

    async def forbidden_dispatch(*args, **kwargs):
        raise AssertionError("recorded-observation replay dispatched a provider")

    monkeypatch.setattr(CouncilProviderRegistry, "run_adapter", forbidden_dispatch)

    result = env.apply_observation(pending, observation)

    assert result.status is CanonicalTransitionStatus.APPLIED_ACCEPTED
    assert set(calls) == {
        "_prepare_registry_phase",
        "_build_registry_phase_task",
        "_apply_registry_response",
        "_effective_registry_quorum",
        "_finalize_registry_phase",
    }
    assert {name: len(seen) for name, seen in calls.items()} == {
        "_prepare_registry_phase": 1,
        "_build_registry_phase_task": 2,
        "_apply_registry_response": 1,
        "_effective_registry_quorum": 1,
        "_finalize_registry_phase": 1,
    }
    execution_ced_ids = {
        calls[name][0]
        for name in (
            "_prepare_registry_phase",
            "_apply_registry_response",
            "_effective_registry_quorum",
            "_finalize_registry_phase",
        )
    }
    assert len(execution_ced_ids) == 1
    execution_ced_id = next(iter(execution_ced_ids))
    assert execution_ced_id in calls["_build_registry_phase_task"]
    assert id(ced) not in set().union(*map(set, calls.values()))
    assert all(adapter.generate_calls == 0 for adapter in adapters)


def test_canonical_processing_exception_fails_closed_without_a_successor(
    monkeypatch,
) -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, adapters = _build_recorded_case("opening-scripted-mock")
    source_before = _source_snapshot(ced, state)
    _, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")

    def reject_processing(*args, **kwargs):
        raise RuntimeError("injected canonical processor failure")

    monkeypatch.setattr(
        CEDOrchestrator,
        "_apply_registry_response",
        reject_processing,
    )

    result = env.apply_observation(pending, observation)

    assert result.status is CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE
    assert (
        result.receipt.unavailable_reason
        is SuccessorUnavailableReason.CANONICAL_PROCESSING_REJECTED
    )
    assert result.successor_capsule is None
    assert result.successor_search_state_v1 is None
    assert result.receipt.new_execution_usage == pending.reserved_usage
    assert result.receipt.recorded_historical_usage == observation.historical_usage
    assert _source_snapshot(ced, state) == source_before
    assert all(adapter.generate_calls == 0 for adapter in adapters)


@pytest.mark.parametrize(
    ("case_name", "expected_status", "expected_rejection"),
    (
        (
            "opening-scripted-mock",
            CanonicalTransitionStatus.APPLIED_ACCEPTED,
            None,
        ),
        (
            "opening-empty-question",
            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
            CanonicalRejectionReason.SOCRATIC_CONTENT_REJECTED,
        ),
        (
            "opening-injection-question",
            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
            CanonicalRejectionReason.ANSWER_INJECTION_REJECTED,
        ),
        (
            "opening-invalid-json",
            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
            CanonicalRejectionReason.PARSER_REJECTED,
        ),
        (
            "opening-schema-error",
            CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
            CanonicalRejectionReason.SCHEMA_REJECTED,
        ),
    ),
)
def test_frozen_observations_match_canonical_transition_and_search_state_v1(
    case_name,
    expected_status,
    expected_rejection,
) -> None:
    env = CanonicalSuccessorEnvironmentV0()
    blueprint = FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.case(case_name)
    budget = _budget()
    usage = BudgetUsage(nodes=1)
    source_ced, source_state, source_adapters = _build_recorded_case(case_name)
    source_before = _source_snapshot(source_ced, source_state)
    _, pending = _capture_and_prepare(
        env,
        source_ced,
        source_state,
        budget=budget,
        usage=usage,
    )
    observation = blueprint.materialize(pending)

    result = env.apply_observation(pending, observation)
    reference = blueprint.reference

    assert result.status is expected_status
    assert result.status is reference.status
    assert result.receipt.canonical_rejection_reason is expected_rejection
    assert (
        result.receipt.canonical_rejection_reason
        is reference.canonical_rejection_reason
    )
    assert (
        result.successor_capsule.normalized_semantic_digest
        == reference.successor_semantic_digest
    )
    assert (
        result.successor_search_state_v1.state_id
        == reference.successor_search_state_v1_id
    )
    assert (
        result.successor_capsule.search_state_v1_id
        == reference.successor_search_state_v1_id
    )
    semantic_payload, rebuilt_projection = canonical_capsule_semantic_snapshot(
        result.successor_capsule
    )
    assert rebuilt_projection == result.successor_search_state_v1
    assert (
        canonical_successor_reference_field_digests(semantic_payload)
        == reference.parity_field_digests
    )
    projected_digest = hashlib.sha256(
        canonical_json(
            result.successor_search_state_v1.model_dump(mode="json")
        ).encode("utf-8")
    ).hexdigest()
    assert projected_digest == reference.successor_search_state_v1_digest
    if expected_status is CanonicalTransitionStatus.APPLIED_ACCEPTED:
        assert result.receipt.resulting_move_id == reference.accepted_move_id
        assert (
            result.successor_search_state_v1.base_state.move_history[0].move_id
            == reference.accepted_move_id
        )
    else:
        assert reference.accepted_move_id is None
        assert result.receipt.resulting_move_id is None

    assert _source_snapshot(source_ced, source_state) == source_before
    assert all(adapter.generate_calls == 0 for adapter in source_adapters)
    assert result.receipt.source_state_hash == pending.source_capsule.normalized_semantic_digest
    assert (
        result.receipt.successor_state_hash
        == result.successor_capsule.normalized_semantic_digest
    )
    assert result.receipt.observation_id == observation.observation_id
    assert result.receipt.recorded_historical_usage == observation.historical_usage
    assert result.receipt.new_execution_usage == NewExecutionUsage()
    assert result.receipt.canonical_processor_ids == pending.canonical_processor_ids


def test_replay_is_idempotent_and_an_unmanifested_sibling_is_fail_closed() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    source_before = _source_snapshot(ced, state)
    capsule, pending = _capture_and_prepare(env, ced, state)
    observation_a = _case_observation(pending, "opening-scripted-mock")
    observation_b = _replace_observation(
        observation_a,
        raw_text=json.dumps(
            {
                "content": {
                    "question": (
                        "Which unstated premise would have to hold for the "
                        "conclusion to follow?"
                    ),
                    "operator": "expose_premise",
                    "epistemic_marker": "open_uncertainty",
                },
                "confidence": 0.7,
            }
        ),
    )

    result_a_first = env.apply_observation(pending, observation_a)
    result_a_frozen = result_a_first.model_dump_json()
    unavailable_b_first = env.apply_observation(pending, observation_b)
    unavailable_b_second = env.apply_observation(pending, observation_b)
    result_a_second = env.apply_observation(pending, observation_a)

    assert _source_snapshot(ced, state) == source_before
    assert capsule.model_dump_json() == pending.source_capsule.model_dump_json()
    assert result_a_first.model_dump_json() == result_a_frozen
    assert result_a_first.result_id == result_a_second.result_id
    assert result_a_first.receipt.receipt_id == result_a_second.receipt.receipt_id
    assert result_a_first.successor_capsule.normalized_semantic_digest == (
        result_a_second.successor_capsule.normalized_semantic_digest
    )
    assert result_a_first.successor_search_state_v1 == (
        result_a_second.successor_search_state_v1
    )
    assert unavailable_b_first == unavailable_b_second
    assert (
        unavailable_b_first.receipt.unavailable_reason
        is SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY
    )
    assert unavailable_b_first.successor_capsule is None
    assert unavailable_b_first.successor_search_state_v1 is None
    assert result_a_first.model_dump_json() == result_a_frozen


def test_apply_cannot_mutate_an_unrelated_production_ced_or_registry_failure_state() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    source_ced, source_state, _ = _build_recorded_case("opening-invalid-json")
    production_ced, production_state, _ = _build_ced(
        "A separate production-shaped root",
        session_id="phase8-production",
    )
    _, pending = _capture_and_prepare(env, source_ced, source_state)
    source_ced.registry._last_failed = ["source-sentinel"]
    production_ced.registry._last_failed = ["production-sentinel"]
    source_before = _source_snapshot(source_ced, source_state)
    production_before = _source_snapshot(production_ced, production_state)
    observation = _case_observation(pending, "opening-invalid-json")

    result = env.apply_observation(pending, observation)

    assert result.status is CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION
    assert _source_snapshot(source_ced, source_state) == source_before
    assert _source_snapshot(production_ced, production_state) == production_before
    assert source_ced.registry._last_failed == ["source-sentinel"]
    assert production_ced.registry._last_failed == ["production-sentinel"]
    assert result.receipt.source_unchanged is True
    assert result.receipt.sibling_branches_unchanged is True
    assert result.receipt.production_unchanged is True


def test_receipt_separates_recorded_usage_from_zero_call_replay_usage() -> None:
    env = CanonicalSuccessorEnvironmentV0()
    ced, state, _ = _build_recorded_case("opening-scripted-mock")
    _, pending = _capture_and_prepare(env, ced, state)
    observation = _case_observation(pending, "opening-scripted-mock")

    result = env.apply_observation(pending, observation)
    receipt = result.receipt

    assert receipt.new_execution_usage == NewExecutionUsage()
    assert receipt.new_execution_usage.budget_delta == BudgetUsage(
        nodes=1,
        expansions=1,
        max_depth_observed=1,
    )
    assert receipt.new_execution_usage.budget_delta.model_calls == 0
    assert receipt.new_execution_usage.budget_delta.tool_calls == 0
    assert receipt.new_execution_usage.budget_delta.tokens == 0
    assert receipt.new_execution_usage.budget_delta.cost_microusd == 0
    assert receipt.recorded_historical_usage == observation.historical_usage
    assert receipt.budget_before == pending.budget_before
    assert receipt.budget_after == pending.budget_before.plus(
        receipt.new_execution_usage.budget_delta
    )
    assert receipt.receipt_id == f"cedreceipt_{receipt.receipt_hash}"
    assert receipt.canonical_processor_ids == pending.canonical_processor_ids


def test_environment_source_contains_no_duplicate_ced_transition_authority() -> None:
    module = inspect.getmodule(CanonicalSuccessorEnvironmentV0)
    assert module is not None
    tree = ast.parse(inspect.getsource(module))
    identifiers = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    forbidden_identifiers = {
        "validate_socratic_content",
        "check_answer_injection",
        "aporia_from_content",
        "commitments_from_move",
        "commitment_events_from_reflection",
        "_PHASE_ROLE_SLOTS",
        "SOCRATIC_CYCLE_PHASES",
        "assign_roles_for_phase",
        "_deterministic_move_id",
        "_screen_socratic_move",
        "_record_task_log",
        "finalize_round",
        "generate_agent_move",
        "run_adapter",
    }
    direct_calls = {
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }

    assert not (forbidden_identifiers & identifiers)
    assert not {
        call
        for call in direct_calls
        if call.endswith("moves.append") or call.endswith("task_log.append")
    }
