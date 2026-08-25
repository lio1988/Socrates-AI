"""Observe one real offline canonical CED transition for Phase 8 recording.

The recorder never calls an adapter. It attaches a temporary observer to the
CED-owned response-application seam and then asks the ordinary
``_run_registry_phase`` path to execute. The actual ``AgentTask`` and
``ProviderResponse`` seen on that path become an immutable capture receipt and
recorded observation. Parsing, firewall decisions, move identity, TaskLog, and
successor mutation remain wholly CED-owned.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Optional

from .ced import (
    CEDOrchestrator,
    CanonicalRegistryResponseApplication,
    CanonicalTaskSpec,
)
from .ced_canonical_successor import (
    CanonicalSuccessorEnvironmentV0,
    canonical_runtime_fingerprint,
    canonical_task_semantic_identity,
)
from .ced_canonical_successor_contracts import (
    CanonicalBranchCapsule,
    HistoricalUsageKnowledge,
    ObservationTransportStatus,
    PendingCanonicalTransition,
    RecordedCanonicalObservation,
    RecordedHistoricalUsage,
    RecordedObservationProvenance,
)
from .ced_canonical_successor_recording_contracts import (
    CanonicalObservationCaptureReceipt,
)
from .models import (
    AgentTask,
    CouncilRoundResult,
    DialogPhase,
    ProviderResponse,
    ProviderStatus,
    SessionState,
)
from .socrates_zero.contracts import (
    BudgetUsage,
    LegalAction,
    SearchBudget,
    canonical_json,
)


@dataclass(frozen=True)
class CanonicalRecordedTransitionCapture:
    """Ephemeral output of one observed canonical acquisition run.

    Only ``capture_receipt`` and ``observation`` enter the transition-facing
    lineage. The authoritative CED/state and application outcome are returned
    so a separate evaluator-side freezer can record the reference successor.
    """

    source_capsule: CanonicalBranchCapsule
    pending_transition: PendingCanonicalTransition
    capture_receipt: CanonicalObservationCaptureReceipt
    observation: RecordedCanonicalObservation
    task_spec: CanonicalTaskSpec
    source_task: AgentTask
    provider_response: ProviderResponse
    canonical_application: CanonicalRegistryResponseApplication
    canonical_round_result: CouncilRoundResult
    authoritative_ced: CEDOrchestrator
    authoritative_state: SessionState
    source_runtime_fingerprint: str
    offline_fixture_dispatches: int


def offline_fixture_historical_usage() -> RecordedHistoricalUsage:
    """Truthful acquisition ledger for one deterministic in-process fixture."""

    return RecordedHistoricalUsage(
        knowledge=HistoricalUsageKnowledge.PARTIAL,
        model_calls=0,
        tool_calls=0,
        tokens=0,
        cost_microusd=0,
        wall_time_ms=None,
        observation_acquisitions=1,
    )


def _transport_identity(response: ProviderResponse) -> ObservationTransportStatus:
    if response.raw_text is not None:
        return ObservationTransportStatus.DELIVERED
    mapping = {
        ProviderStatus.TIMEOUT: ObservationTransportStatus.TIMEOUT,
        ProviderStatus.RATE_LIMITED: ObservationTransportStatus.RATE_LIMITED,
        ProviderStatus.ERROR: ObservationTransportStatus.ERROR,
        ProviderStatus.UNAVAILABLE: ObservationTransportStatus.UNAVAILABLE,
        ProviderStatus.MISSING_KEY: ObservationTransportStatus.UNAVAILABLE,
        ProviderStatus.DISABLED: ObservationTransportStatus.UNAVAILABLE,
    }
    try:
        return mapping[response.status]
    except KeyError as exc:
        raise ValueError(
            f"provider status {response.status.value!r} has no recording transport identity"
        ) from exc


def _raw_output_digest(
    response: ProviderResponse,
    transport: ObservationTransportStatus,
) -> str:
    if transport is ObservationTransportStatus.DELIVERED:
        assert response.raw_text is not None
        return hashlib.sha256(response.raw_text.encode("utf-8")).hexdigest()
    return hashlib.sha256(
        canonical_json(
            {
                "transport_status": transport.value,
                "transport_error_code": response.error_message
                or response.status.value,
            }
        ).encode("utf-8")
    ).hexdigest()


async def capture_canonical_opening_observation(
    ced: CEDOrchestrator,
    state: SessionState,
    *,
    action: LegalAction,
    budget: SearchBudget,
    budget_usage: Optional[BudgetUsage],
    historical_usage: RecordedHistoricalUsage,
    provenance: RecordedObservationProvenance,
    timeout_seconds: float = 5.0,
) -> CanonicalRecordedTransitionCapture:
    """Capture the exact task/response from one canonical offline opening run."""

    env = CanonicalSuccessorEnvironmentV0()
    usage = budget_usage or BudgetUsage()
    capsule = env.capture_capsule(ced, state, budget=budget, budget_usage=usage)
    pending = env.prepare_transition(capsule, action, budget)
    source_fingerprint = canonical_runtime_fingerprint(ced)
    specs = ced.canonical_registry_task_specs(state, DialogPhase.OPENING)
    if len(specs) != 1:
        raise ValueError("authoritative opening capture requires exactly one task")

    observed: list[
        tuple[
            AgentTask,
            ProviderResponse,
            CanonicalRegistryResponseApplication,
        ]
    ] = []
    original_apply = ced._apply_registry_response

    def observe_application(
        observed_state: SessionState,
        phase: DialogPhase,
        task: AgentTask,
        response: ProviderResponse,
        dispatch,
    ) -> CanonicalRegistryResponseApplication:
        # Snapshot actual dispatch inputs before CED gives an accepted parsed
        # move its deterministic public identity.
        captured_task = AgentTask.model_validate_json(task.model_dump_json())
        captured_response = ProviderResponse.model_validate_json(
            response.model_dump_json()
        )
        application = original_apply(
            observed_state,
            phase,
            task,
            response,
            dispatch,
        )
        observed.append((captured_task, captured_response, application))
        return application

    ced._apply_registry_response = observe_application  # type: ignore[method-assign]
    try:
        round_result = await ced._run_registry_phase(
            state,
            DialogPhase.OPENING,
            timeout_seconds,
        )
    finally:
        ced._apply_registry_response = original_apply  # type: ignore[method-assign]

    if len(observed) != 1:
        raise ValueError(
            "authoritative opening capture must observe exactly one canonical response"
        )
    task, response, application = observed[0]
    active_binding = next(
        item for item in capsule.provider_bindings if item.agent_id == task.agent_id
    )
    if (
        task.agent_id != pending.canonical_task.agent_id
        or response.provider_id != active_binding.provider_id
        or active_binding.provider_id != pending.expected_provider_id
    ):
        raise ValueError(
            "observed canonical provider route differs from the pending task"
        )
    actual_model_id = ced.registry.authoritative_model_id(response.provider_id)
    if actual_model_id is None or actual_model_id != active_binding.model_id:
        raise ValueError("observed provider lacks the exact captured model identity")
    observed_task_identity = canonical_task_semantic_identity(
        task,
        model_config_digest=active_binding.model_config_digest,
    )
    if observed_task_identity != capsule.canonical_task:
        raise ValueError(
            "observed canonical task differs from the captured semantic identity"
        )

    transport = _transport_identity(response)
    raw_digest = _raw_output_digest(response, transport)
    receipt = CanonicalObservationCaptureReceipt(
        source_capsule_id=capsule.capsule_id,
        source_execution_id=capsule.source_execution_id,
        source_configuration_digest=capsule.configuration_digest,
        source_normalized_semantic_digest=capsule.normalized_semantic_digest,
        source_search_state_v1_id=capsule.search_state_v1_id,
        action_id=action.action_id,
        task_identity=capsule.canonical_task,
        provider_id=response.provider_id,
        configured_model_id=active_binding.model_id,
        actual_model_id=actual_model_id,
        model_config_digest=active_binding.model_config_digest,
        provider_status=response.status,
        transport_status=transport,
        raw_output_digest=raw_digest,
        historical_usage=historical_usage,
        provenance=provenance,
        # Random production task_id was observed in ``source_task`` above but
        # is provenance-only and intentionally omitted from the semantic/frozen
        # capture so independent recapture remains byte-stable.
        source_task_id=None,
    )
    observation = RecordedCanonicalObservation(
        capture_receipt_id=receipt.capture_receipt_id,
        source_capsule_id=receipt.source_capsule_id,
        source_execution_id=receipt.source_execution_id,
        source_configuration_digest=receipt.source_configuration_digest,
        source_task_id=receipt.source_task_id,
        action_id=receipt.action_id,
        task_identity=receipt.task_identity,
        provider_id=receipt.provider_id,
        configured_model_id=receipt.configured_model_id,
        actual_model_id=receipt.actual_model_id,
        model_config_digest=receipt.model_config_digest,
        transport_status=receipt.transport_status,
        transport_error_code=(
            None
            if transport is ObservationTransportStatus.DELIVERED
            else response.error_message or response.status.value
        ),
        raw_text=response.raw_text,
        raw_output_digest=receipt.raw_output_digest,
        historical_usage=receipt.historical_usage,
        provenance=receipt.provenance,
    )
    return CanonicalRecordedTransitionCapture(
        source_capsule=capsule,
        pending_transition=pending,
        capture_receipt=receipt,
        observation=observation,
        task_spec=specs[0],
        source_task=task,
        provider_response=response,
        canonical_application=application,
        canonical_round_result=round_result,
        authoritative_ced=ced,
        authoritative_state=state,
        source_runtime_fingerprint=source_fingerprint,
        offline_fixture_dispatches=1,
    )


__all__ = [
    "CanonicalRecordedTransitionCapture",
    "capture_canonical_opening_observation",
    "offline_fixture_historical_usage",
]
