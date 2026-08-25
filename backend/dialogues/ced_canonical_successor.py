"""CED-owned, isolated, one-transition recorded-observation replay.

This experimental module acquires no observation and dispatches no provider.
It rehydrates a detached branch, asks the existing CED for the canonical
opening task, parses one externally recorded raw response with the existing
parser, and delegates every state mutation to the shared CED registry seam.

The supported surface is intentionally one action family only:
``ASK_SOCRATIC_QUESTION`` for the round-zero OPENING Socrates slot.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ValidationError

from .agent import SocraticAgent
from .ced import (
    CEDOrchestrator,
    CanonicalRegistryApplicationOutcome,
    CanonicalRegistryResponseApplication,
    CanonicalTaskSpec,
)
from .ced_canonical_successor_contracts import (
    CANONICAL_SUCCESSOR_ENV_ID,
    FORBIDDEN_RECORDED_OBSERVATION_FIELDS,
    CanonicalBranchCapsule,
    CanonicalRejectionReason,
    CanonicalSideLedgerKind,
    CanonicalTaskIdentity,
    CanonicalTransitionReceipt,
    CanonicalTransitionResult,
    CanonicalTransitionStatus,
    FutureLabelForbiddenError,
    LegalActionValidationStatus,
    NewExecutionUsage,
    ObservationTransportStatus,
    PendingCanonicalTransition,
    ProviderBindingIdentity,
    RECORDED_SOCRATIC_CONTENT_FIELDS,
    RECORDED_SOCRATIC_ENVELOPE_FIELDS,
    RecordedCanonicalObservation,
    RecordedObservationCompatibilityError,
    SideLedgerDigest,
    SuccessorUnavailableReason,
    validate_recorded_observation_compatibility,
)
from .ced_canonical_successor_manifest import (
    verify_authoritative_recorded_observation,
)
from .ced_search_projection_v1 import project_search_state_v1
from .models import (
    AgentTask,
    DialogPhase,
    FinalSynthesisMode,
    ProviderResponse,
    ProviderStatus,
    SessionState,
    ShadowScoringMode,
)
from .provider_registry import (
    CouncilProviderRegistry,
    parse_and_validate_move,
)
from .providers import FakeProvider
from .socratic import (
    AporiaRecord,
    CommitmentRecord,
    CommitmentStatus,
)
from .socrates_zero.constitution import CEDSearchConstitution
from .socrates_zero.contracts import (
    ActionKind,
    BudgetExceeded,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    SearchBudget,
    canonical_json,
    stable_contract_id,
)


CANONICAL_PROCESSOR_IDS = (
    "CEDOrchestrator._apply_registry_response",
    "CEDOrchestrator._build_registry_phase_task",
    "CEDOrchestrator._effective_registry_quorum",
    "CEDOrchestrator._finalize_registry_phase",
    "CEDOrchestrator._prepare_registry_phase",
    "provider_registry.parse_and_validate_move",
)
CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID = (
    "ced-canonical-successor-semantic-parity/v0"
)

_MODEL_CONFIGURATION_VERSION = "ced-recorded-observation-model-config/v0"


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_copy(value: object) -> object:
    return json.loads(canonical_json(value))


class CanonicalSuccessorUnavailable(ContractValidationError):
    """Fail-closed precondition or integrity failure with a frozen reason."""

    def __init__(self, reason: SuccessorUnavailableReason, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason.value}: {detail}")


class _RecordedObservationOnlyAdapter:
    """Fresh metadata-only seat; accidental dispatch is a hard test failure."""

    is_fake = True

    def __init__(
        self,
        *,
        provider_id: str,
        provider_name: str,
        exact_model_id: str,
        display_model: Optional[str],
        model_config_digest: str,
        source_adapter_type: str,
    ) -> None:
        self.provider_id = provider_id
        self.provider_name = provider_name
        self.model_id = exact_model_id
        self.model_config_digest = model_config_digest
        self.source_adapter_type = source_adapter_type
        self.enabled = True
        if display_model is not None:
            # CED roster semantics distinguish an absent `.model` (displayed as
            # "mock") from an explicit exact model string.
            self.model = display_model

    def authoritative_model_id(self) -> str:
        return self.model_id

    def is_available(self) -> bool:
        return True

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
        raise AssertionError(
            "canonical successor replay must never dispatch a provider"
        )


def _adapter_catalog_entry(adapter: object, exact_model_id: str) -> Dict[str, object]:
    display_model = getattr(adapter, "model", None)
    if display_model is not None:
        display_model = str(display_model)
    payload = {
        "provider_id": str(getattr(adapter, "provider_id", "")),
        "provider_name": str(getattr(adapter, "provider_name", "")),
        "exact_model_id": exact_model_id,
        "display_model": display_model,
        "source_adapter_type": getattr(
            adapter,
            "source_adapter_type",
            f"{type(adapter).__module__}.{type(adapter).__qualname__}",
        ),
        "model_configuration_version": _MODEL_CONFIGURATION_VERSION,
    }
    return {**payload, "model_config_digest": _digest(payload)}


def _serialize_side_ledgers(
    ced: CEDOrchestrator,
    session_id: str,
) -> Dict[str, Dict[str, object]]:
    def entry(store: Mapping[str, object], items: object) -> Dict[str, object]:
        return {
            "present": session_id in store,
            "items": _json_copy(items),
        }

    commitments = [
        item.to_dict() for item in ced._commitments.get(session_id, [])
    ]
    aporia = [item.to_dict() for item in ced._aporia.get(session_id, [])]
    return {
        CanonicalSideLedgerKind.COMMITMENT.value: entry(
            ced._commitments, commitments
        ),
        CanonicalSideLedgerKind.APORIA.value: entry(ced._aporia, aporia),
        CanonicalSideLedgerKind.SOCRATIC_AUDIT.value: entry(
            ced._socratic_audit_rows,
            ced._socratic_audit_rows.get(session_id, []),
        ),
        CanonicalSideLedgerKind.PHASE_DISPATCH.value: entry(
            ced._phase_dispatch,
            ced._phase_dispatch.get(session_id, []),
        ),
        CanonicalSideLedgerKind.REGISTRY_RETRY.value: entry(
            ced._phase_retries,
            ced._phase_retries.get(session_id, []),
        ),
        CanonicalSideLedgerKind.CYCLE.value: entry(
            ced._cycle_log,
            ced._cycle_log.get(session_id, []),
        ),
    }


def _side_ledger_digests(
    side_ledgers: Mapping[str, object],
) -> Tuple[SideLedgerDigest, ...]:
    return tuple(
        SideLedgerDigest(
            name=CanonicalSideLedgerKind(name),
            semantic_digest=_digest(value),
        )
        for name, value in sorted(side_ledgers.items())
    )


def _capture_runtime_configuration(
    ced: CEDOrchestrator,
    state: SessionState,
) -> Tuple[Dict[str, object], Tuple[ProviderBindingIdentity, ...]]:
    if ced.registry is None:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "a canonical provider registry is required",
        )
    if ced.phase_retry:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "v0 requires phase_retry=False because one observation cannot satisfy a retry",
        )
    optional_components = {
        "lesson_store": ced.lesson_store,
        "seat_health": ced.seat_health,
        "topic_skill": ced.topic_skill,
        "open_questions": ced.open_questions,
        "calibration": ced.calibration,
        "training_corpus": ced.training_corpus,
        "openclaw_lessons": ced.openclaw_lessons,
        "trace_capturer": ced.trace_capturer,
        "hybrid_shadow": ced.hybrid_shadow,
    }
    enabled = sorted(name for name, value in optional_components.items() if value is not None)
    if enabled or ced.ai_learning or ced.tree_expansions or ced.debug_task_log:
        detail = enabled + [
            name
            for name, active in (
                ("ai_learning", ced.ai_learning),
                ("tree_expansions", bool(ced.tree_expansions)),
                ("debug_task_log", ced.debug_task_log),
            )
            if active
        ]
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "v0 root enables unsupported mutable context: " + ", ".join(detail),
        )

    adapters = ced.registry.all_adapters()
    if not adapters:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "provider catalog is empty",
        )
    if any(getattr(adapter, "is_fake", False) is not True for adapter in adapters):
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "v0 accepts only explicit offline fixture adapters",
        )
    provider_ids = [str(getattr(item, "provider_id", "")) for item in adapters]
    if any(not value for value in provider_ids) or len(set(provider_ids)) != len(
        provider_ids
    ):
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "provider catalog IDs must be nonblank and unique",
        )
    available = ced.registry.available_adapters()
    if [id(item) for item in available] != [id(item) for item in adapters]:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "every v0 provider descriptor must be available in registration order",
        )

    catalog = []
    for adapter in adapters:
        exact = ced.registry.authoritative_model_id(adapter.provider_id)
        if exact is None:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                f"provider {adapter.provider_id!r} lacks exact actual model identity",
            )
        catalog.append(_adapter_catalog_entry(adapter, exact))
    by_provider = {str(item["provider_id"]): item for item in catalog}

    sid = state.session_id
    if sid not in ced._session_adapter_orders or sid not in ced._session_adapter_bindings:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "session has no pre-existing canonical adapter binding",
        )
    order = ced._session_adapter_orders[sid]
    bindings = ced._session_adapter_bindings[sid]
    if [item.provider_id for item in order] != provider_ids:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "session adapter order differs from the fixed provider catalog",
        )
    agent_ids = tuple(sorted(state.agent_states))
    if tuple(sorted(bindings)) != agent_ids:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "session adapter bindings do not cover the canonical agents exactly",
        )

    binding_payload = {
        agent_id: bindings[agent_id].provider_id for agent_id in agent_ids
    }
    provider_bindings = tuple(
        ProviderBindingIdentity(
            agent_id=agent_id,
            provider_id=provider_id,
            model_id=str(by_provider[provider_id]["exact_model_id"]),
            model_config_digest=str(
                by_provider[provider_id]["model_config_digest"]
            ),
        )
        for agent_id, provider_id in binding_payload.items()
    )
    config = {
        "env_id": CANONICAL_SUCCESSOR_ENV_ID,
        "agent_ids": list(agent_ids),
        "provider_catalog": catalog,
        "adapter_order": provider_ids,
        "agent_bindings": binding_payload,
        "registry": {
            "minimum_providers": ced.registry.minimum_providers,
            "quorum_for_assembly": ced.registry.quorum_for_assembly,
            "provider_timeout_seconds": ced.registry.provider_timeout_seconds,
            "allow_fake_provider_in_dev": ced.registry.allow_fake_provider_in_dev,
        },
        "ced": {
            "shadow_scoring_mode": ced.shadow_scoring_mode.value,
            "final_synthesis_mode": ced.final_synthesis_mode.value,
            "assembly_fallback": ced.assembly_fallback,
            "ratification_repair": ced.ratification_repair,
            "phase_retry": False,
            "max_socratic_followups": ced.max_socratic_followups,
            "score_weighting": ced.score_weighting,
            "cohesion_margin": ced.cohesion_margin,
            "tree_expansions": 0,
            "tree_exploration": ced.tree_exploration,
        },
    }
    return config, provider_bindings


def _structural_snapshot(
    ced: CEDOrchestrator,
    state: SessionState,
) -> Tuple[Dict[str, object], Tuple[ProviderBindingIdentity, ...]]:
    config, bindings = _capture_runtime_configuration(ced, state)
    registry = ced.registry
    assert registry is not None
    return (
        {
            "session_state": state.model_dump(mode="json"),
            "side_ledgers": _serialize_side_ledgers(ced, state.session_id),
            "registry_last_failed": list(registry._last_failed),
            "runtime_configuration": config,
        },
        bindings,
    )


def canonical_runtime_fingerprint(ced: CEDOrchestrator) -> str:
    """Exact fingerprint of relevant CED runtime state for isolation proofs."""

    sessions = {
        sid: state.model_dump(mode="json")
        for sid, state in sorted(ced._sessions.items())
    }
    commitments = {
        sid: [item.to_dict() for item in rows]
        for sid, rows in sorted(ced._commitments.items())
    }
    aporia = {
        sid: [item.to_dict() for item in rows]
        for sid, rows in sorted(ced._aporia.items())
    }
    simple_stores = {
        name: _json_copy(getattr(ced, name))
        for name in (
            "_phase_retries",
            "_phase_dispatch",
            "_socratic_audit_rows",
            "_cycle_log",
            "_session_lessons",
            "_session_outcomes",
            "_tree_audits",
            "_injected_lessons",
            "_hybrid_shadow_diagnostics",
        )
    }
    bindings = {
        sid: {
            agent_id: adapter.provider_id
            for agent_id, adapter in sorted(rows.items())
        }
        for sid, rows in sorted(ced._session_adapter_bindings.items())
    }
    orders = {
        sid: [adapter.provider_id for adapter in rows]
        for sid, rows in sorted(ced._session_adapter_orders.items())
    }
    registry_last_failed = (
        list(ced.registry._last_failed) if ced.registry is not None else None
    )
    return _digest(
        {
            "sessions": sessions,
            "commitments": commitments,
            "aporia": aporia,
            "stores": simple_stores,
            "bindings": bindings,
            "orders": orders,
            "registry_last_failed": registry_last_failed,
            "cohesion_overrides": ced._cohesion_overrides,
        }
    )


def _restore_side_ledgers(
    ced: CEDOrchestrator,
    session_id: str,
    payload: Mapping[str, Mapping[str, object]],
) -> None:
    def rows(kind: CanonicalSideLedgerKind) -> Sequence[Mapping[str, object]]:
        value = payload[kind.value]
        raw = value.get("items", [])
        if not isinstance(raw, list):
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                f"{kind.value} side ledger is not a list",
            )
        return raw

    commitment_rows = rows(CanonicalSideLedgerKind.COMMITMENT)
    aporia_rows = rows(CanonicalSideLedgerKind.APORIA)
    stores: Tuple[Tuple[CanonicalSideLedgerKind, Dict[str, object], object], ...] = (
        (CanonicalSideLedgerKind.COMMITMENT, ced._commitments, [
            CommitmentRecord(
                commitment_id=str(item["commitment_id"]),
                source_move_id=str(item["source_move_id"]),
                cycle=int(item["cycle"]),
                claim=str(item["claim"]),
                status=CommitmentStatus(str(item["status"])),
                target_commitment_id=item.get("target_commitment_id"),
                provider_id=item.get("provider_id"),
                model_id=item.get("model_id"),
                authority=str(item.get("authority", "public_move")),
            )
            for item in commitment_rows
        ]),
        (CanonicalSideLedgerKind.APORIA, ced._aporia, [
            AporiaRecord(
                previous_commitment_id=str(item["previous_commitment_id"]),
                conflicting_commitment_id=str(item["conflicting_commitment_id"]),
                resulting_status=CommitmentStatus(str(item["resulting_status"])),
                remaining_question=str(item["remaining_question"]),
                cycle=int(item["cycle"]),
            )
            for item in aporia_rows
        ]),
        (
            CanonicalSideLedgerKind.SOCRATIC_AUDIT,
            ced._socratic_audit_rows,
            list(rows(CanonicalSideLedgerKind.SOCRATIC_AUDIT)),
        ),
        (
            CanonicalSideLedgerKind.PHASE_DISPATCH,
            ced._phase_dispatch,
            list(rows(CanonicalSideLedgerKind.PHASE_DISPATCH)),
        ),
        (
            CanonicalSideLedgerKind.REGISTRY_RETRY,
            ced._phase_retries,
            list(rows(CanonicalSideLedgerKind.REGISTRY_RETRY)),
        ),
        (
            CanonicalSideLedgerKind.CYCLE,
            ced._cycle_log,
            list(rows(CanonicalSideLedgerKind.CYCLE)),
        ),
    )
    for kind, store, restored in stores:
        if bool(payload[kind.value].get("present", False)):
            store[session_id] = restored


def _rehydrate_snapshot(
    *,
    source_snapshot_json: str,
    configuration_digest: str,
    session_id: str,
) -> Tuple[CEDOrchestrator, SessionState]:
    try:
        snapshot = json.loads(source_snapshot_json)
        config = snapshot["runtime_configuration"]
        registry_config = config["registry"]
        ced_config = config["ced"]
        catalog = config["provider_catalog"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "capsule runtime snapshot is incomplete",
        ) from exc
    if _digest(config) != configuration_digest:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "capsule configuration digest mismatch",
        )

    registry = CouncilProviderRegistry(**registry_config)
    descriptors: Dict[str, _RecordedObservationOnlyAdapter] = {}
    for item in catalog:
        adapter = _RecordedObservationOnlyAdapter(
            provider_id=str(item["provider_id"]),
            provider_name=str(item["provider_name"]),
            exact_model_id=str(item["exact_model_id"]),
            display_model=item.get("display_model"),
            model_config_digest=str(item["model_config_digest"]),
            source_adapter_type=str(item["source_adapter_type"]),
        )
        descriptors[adapter.provider_id] = adapter
        registry.register(adapter)

    provider = FakeProvider()
    agents = [
        SocraticAgent(str(agent_id), provider) for agent_id in config["agent_ids"]
    ]
    ced = CEDOrchestrator(
        agents,
        provider,
        registry=registry,
        shadow_scoring_mode=ShadowScoringMode(ced_config["shadow_scoring_mode"]),
        final_synthesis_mode=FinalSynthesisMode(ced_config["final_synthesis_mode"]),
        assembly_fallback=bool(ced_config["assembly_fallback"]),
        ratification_repair=str(ced_config["ratification_repair"]),
        phase_retry=False,
        max_socratic_followups=int(ced_config["max_socratic_followups"]),
        score_weighting=str(ced_config["score_weighting"]),
        cohesion_margin=float(ced_config["cohesion_margin"]),
        tree_expansions=0,
        tree_exploration=float(ced_config["tree_exploration"]),
    )
    try:
        state = SessionState.model_validate(snapshot["session_state"])
    except (KeyError, ValidationError) as exc:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "capsule SessionState cannot be rehydrated",
        ) from exc
    if state.session_id != session_id:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "capsule session identity mismatch",
        )
    sid = state.session_id
    ced._sessions[sid] = state
    try:
        order = [descriptors[item] for item in config["adapter_order"]]
        binding = {
            str(agent_id): descriptors[provider_id]
            for agent_id, provider_id in config["agent_bindings"].items()
        }
    except KeyError as exc:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "capsule names an unknown provider binding",
        ) from exc
    ced._session_adapter_orders[sid] = order
    ced._session_adapter_bindings[sid] = binding
    _restore_side_ledgers(ced, sid, snapshot["side_ledgers"])
    registry._last_failed = list(snapshot.get("registry_last_failed", []))
    return ced, state


def _rehydrate(capsule: CanonicalBranchCapsule) -> Tuple[CEDOrchestrator, SessionState]:
    return _rehydrate_snapshot(
        source_snapshot_json=capsule.source_snapshot_json,
        configuration_digest=capsule.configuration_digest,
        session_id=capsule.session_id,
    )


def _move_semantics(move: object, *, include_move_id: bool = True) -> Dict[str, object]:
    return {
        "move_id": getattr(move, "move_id", None) if include_move_id else None,
        "agent_id": getattr(move, "agent_id", None),
        "role": getattr(getattr(move, "role", None), "value", None),
        "phase": getattr(getattr(move, "phase", None), "value", None),
        "content": _json_copy(getattr(move, "content", {})),
        "confidence": getattr(move, "confidence", None),
        "epistemic_markers": [
            item.value for item in getattr(move, "epistemic_markers", [])
        ],
        "task_kind": getattr(getattr(move, "task_kind", None), "value", None),
        "slot_index": getattr(move, "slot_index", None),
        "attempt_index": getattr(move, "attempt_index", None),
        "provider_id": getattr(move, "provider_id", None),
    }


def _state_semantics(state: SessionState) -> Dict[str, object]:
    accepted_move_ids = {move.move_id for move in state.moves}
    rounds = []
    for result in state.registry_rounds:
        responses = []
        for response in result.responses:
            parsed = response.parsed_move
            responses.append({
                "provider_id": response.provider_id,
                "agent_id": response.agent_id,
                "status": response.status.value,
                "raw_text": response.raw_text,
                "parsed_move": (
                    _move_semantics(
                        parsed,
                        include_move_id=parsed.move_id in accepted_move_ids,
                    )
                    if parsed is not None
                    else None
                ),
                "error_message": response.error_message,
                "retry_count": response.retry_count,
                "repair_attempted": response.repair_attempted,
                "repair_succeeded": response.repair_succeeded,
            })
        rounds.append({
            "responses": responses,
            "ok_provider_ids": list(result.ok_provider_ids),
            "failed_provider_ids": list(result.failed_provider_ids),
            "proceed": result.proceed,
            "warning": result.warning,
        })
    task_log = [
        {
            "move_id": item.move_id,
            "session_id": item.session_id,
            "phase": item.phase.value,
            "round_index": item.round_index,
            "agent_id": item.agent_id,
            "assigned_role": item.assigned_role.value,
            "task_kind": item.task_kind.value if item.task_kind else None,
            "slot_index": item.slot_index,
            "attempt_index": item.attempt_index,
            "schema_name": item.schema_name,
            "context_hash": item.context_hash,
            "provider_id": item.provider_id,
            "provider_status": (
                item.provider_status.value if item.provider_status else None
            ),
            "debug_context": _json_copy(item.debug_context),
        }
        for item in state.task_log
    ]
    return {
        "session_id": state.session_id,
        "question": state.question,
        "phase": state.phase.value,
        "round_number": state.round_number,
        "agent_states": {
            key: value.model_dump(mode="json")
            for key, value in sorted(state.agent_states.items())
        },
        "moves": [_move_semantics(item) for item in state.moves],
        "micro_scores": [item.model_dump(mode="json") for item in state.micro_scores],
        "failed_score_tasks": list(state.failed_score_tasks),
        "section_scores_failed": list(state.section_scores_failed),
        "section_drafts": [item.model_dump(mode="json") for item in state.section_drafts],
        "draft_scorecards": [
            item.model_dump(mode="json") for item in state.draft_scorecards
        ],
        "shadow_harvest": (
            state.shadow_harvest.model_dump(mode="json")
            if state.shadow_harvest is not None
            else None
        ),
        "epistemic_leaderboard": (
            state.epistemic_leaderboard.model_dump(mode="json")
            if state.epistemic_leaderboard is not None
            else None
        ),
        "registry_rounds": rounds,
        "task_log": task_log,
        "council_ratification": (
            state.council_ratification.model_dump(mode="json")
            if state.council_ratification is not None
            else None
        ),
        "assembled_answer": (
            state.assembled_answer.model_dump(mode="json")
            if state.assembled_answer is not None
            else None
        ),
        "final_response": (
            state.final_response.model_dump(mode="json")
            if state.final_response is not None
            else None
        ),
        "phase_history": [item.value for item in state.phase_history],
        "role_history": _json_copy(state.role_history),
    }


def _binding_semantics(
    ced: CEDOrchestrator,
    state: SessionState,
) -> Dict[str, object]:
    if ced.registry is None:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "canonical semantic snapshot requires a provider registry",
        )
    bindings = ced._session_adapter_bindings.get(state.session_id, {})
    normalized = {}
    for agent_id, adapter in sorted(bindings.items()):
        exact_model_id = ced.registry.authoritative_model_id(adapter.provider_id)
        if exact_model_id is None:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                f"provider {adapter.provider_id!r} lacks exact model identity",
            )
        catalog = _adapter_catalog_entry(adapter, exact_model_id)
        normalized[agent_id] = {
            "provider_id": adapter.provider_id,
            "model_id": exact_model_id,
            "display_model": catalog["display_model"],
            "model_config_digest": catalog["model_config_digest"],
        }
    return normalized


def canonical_transition_semantic_snapshot(
    ced: CEDOrchestrator,
    state: SessionState,
    *,
    task: CanonicalTaskSpec,
    budget: SearchBudget,
    budget_usage: BudgetUsage,
    depth: int,
) -> Tuple[Dict[str, object], object]:
    """Predeclared normalized parity payload plus the canonical v1 projection."""

    commitments = tuple(ced._commitments.get(state.session_id, ()))
    aporia = tuple(ced._aporia.get(state.session_id, ()))
    projection = project_search_state_v1(
        state,
        task,
        budget=budget,
        budget_usage=budget_usage,
        commitments=commitments,
        aporia_records=aporia,
        hybrid_state=None,
        depth=depth,
    )
    payload = {
        "equivalence": CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID,
        "session_state": _state_semantics(state),
        "side_ledgers": _serialize_side_ledgers(ced, state.session_id),
        "registry_last_failed": list(ced.registry._last_failed),
        "provider_bindings": _binding_semantics(ced, state),
        "budget": budget.model_dump(mode="json"),
        "budget_usage": budget_usage.model_dump(mode="json"),
        "depth": depth,
        "search_state_v1": projection.model_dump(mode="json"),
    }
    return payload, projection


def canonical_capsule_semantic_snapshot(
    capsule: CanonicalBranchCapsule,
) -> Tuple[Dict[str, object], object]:
    """Rebuild a capsule's read-only canonical semantic parity snapshot.

    This performs no provider dispatch and makes no transition decision.  It is
    the evaluator-facing inverse of capsule capture: a fresh branch-local CED is
    rehydrated, the already-frozen canonical task coordinates are restored, and
    the existing semantic projection is required to reproduce the capsule's
    own identities exactly.
    """

    try:
        validated = CanonicalBranchCapsule.model_validate_json(
            capsule.model_dump_json()
        )
    except (AttributeError, ValidationError) as exc:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "capsule identity or schema is invalid",
        ) from exc
    ced, state = _rehydrate(validated)
    task = validated.canonical_task
    spec = CanonicalTaskSpec(
        phase=task.phase,
        round_number=task.round_number,
        slot_index=task.slot_index,
        agent_id=task.agent_id,
        role=task.role,
        task_kind=task.task_kind,
    )
    depth = 0 if validated.parent_branch_id is None else 1
    semantic, projected = canonical_transition_semantic_snapshot(
        ced,
        state,
        task=spec,
        budget=validated.budget,
        budget_usage=validated.budget_usage,
        depth=depth,
    )
    if (
        _digest(semantic) != validated.normalized_semantic_digest
        or projected.state_id != validated.search_state_v1_id
    ):
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "capsule semantic snapshot does not reproduce its frozen identity",
        )
    return semantic, projected


def canonical_transition_outcome(
    application: CanonicalRegistryResponseApplication,
) -> Tuple[CanonicalTransitionStatus, Optional[CanonicalRejectionReason]]:
    """Project a CED-owned application outcome into the transition contract."""

    if application.outcome is CanonicalRegistryApplicationOutcome.ACCEPTED:
        return CanonicalTransitionStatus.APPLIED_ACCEPTED, None
    if application.canonical_rejection_kind is None:
        raise ValueError("CED canonical rejection omitted its rejection kind")
    return (
        CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
        CanonicalRejectionReason(application.canonical_rejection_kind),
    )


def canonical_task_semantic_identity(
    task: AgentTask,
    *,
    model_config_digest: str,
) -> CanonicalTaskIdentity:
    semantic = {
        "session_id": task.session_id,
        "agent_id": task.agent_id,
        "role": task.role.value,
        "phase": task.phase.value,
        "question": task.question,
        "context": task.context,
        "output_schema": task.output_schema,
        "round_number": task.round_number,
        "task_kind": task.task_kind.value if task.task_kind else None,
        "slot_index": task.slot_index,
        "attempt_index": task.attempt_index,
    }
    request = {
        "question": task.question,
        "context": task.context,
        "output_schema": task.output_schema,
    }
    return CanonicalTaskIdentity(
        source_session_semantic_id=stable_contract_id(
            "cedsourcesession",
            {
                "session_id": task.session_id,
                "question": task.question,
            },
        ),
        phase=task.phase,
        round_number=task.round_number,
        slot_index=task.slot_index,
        attempt_index=task.attempt_index,
        agent_id=task.agent_id,
        role=task.role,
        task_kind=task.task_kind,
        task_semantic_digest=_digest(semantic),
        context_digest=_digest(task.context),
        request_semantic_digest=_digest(request),
        model_config_digest=model_config_digest,
    )


def _validate_pristine_opening_root(
    ced: CEDOrchestrator,
    state: SessionState,
) -> CanonicalTaskSpec:
    occupied = (
        state.moves,
        state.micro_scores,
        state.failed_score_tasks,
        state.section_scores_failed,
        state.section_drafts,
        state.draft_scorecards,
        state.registry_rounds,
        state.task_log,
        state.phase_history,
        state.role_history,
    )
    if (
        state.phase is not DialogPhase.OPENING
        or state.round_number != 0
        or any(occupied)
        or state.shadow_harvest is not None
        or state.epistemic_leaderboard is not None
        or state.council_ratification is not None
        or state.assembled_answer is not None
        or state.final_response is not None
    ):
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "v0 requires a pristine round-zero OPENING SessionState",
        )
    if any(
        value.round_number != 0
        or value.has_submitted
        or value.assigned_role is not value.primary_role
        for value in state.agent_states.values()
    ):
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "v0 agent state is not pristine",
        )
    side = _serialize_side_ledgers(ced, state.session_id)
    if any(value["items"] for value in side.values()):
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "v0 opening root has non-empty CED side ledgers",
        )
    if ced.registry._last_failed:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "v0 opening root carries prior registry failure state",
        )
    specs = ced.canonical_registry_task_specs(state, DialogPhase.OPENING)
    if len(specs) != 1:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.INVALID_ROOT,
            "canonical opening does not contain exactly one task",
        )
    return specs[0]


def _forbidden_fields_in_structure(value: object) -> Tuple[str, ...]:
    found = set()

    def visit(item: object) -> None:
        if isinstance(item, Mapping):
            found.update(FORBIDDEN_RECORDED_OBSERVATION_FIELDS & set(item))
            for nested in item.values():
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return tuple(sorted(found))


def _structured_future_fields(raw_text: str) -> Tuple[str, ...]:
    try:
        value = json.loads(raw_text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ()
    found = set(_forbidden_fields_in_structure(value))
    if isinstance(value, Mapping):
        found.update(set(value) - RECORDED_SOCRATIC_ENVELOPE_FIELDS)
        content = value.get("content")
        if isinstance(content, Mapping):
            found.update(set(content) - RECORDED_SOCRATIC_CONTENT_FIELDS)
    return tuple(sorted(found))


def _stored_contract_extras(value: BaseModel) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Expose ``model_copy(update=...)`` extras that normal serialization drops."""

    unexpected = set()
    forbidden = set()
    visited = set()

    def scan_extra_payload(item: object) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                name = str(key)
                if name in FORBIDDEN_RECORDED_OBSERVATION_FIELDS:
                    forbidden.add(name)
                scan_extra_payload(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                scan_extra_payload(nested)
        elif isinstance(item, BaseModel):
            visit_model(item)

    def visit_model(item: BaseModel) -> None:
        marker = id(item)
        if marker in visited:
            return
        visited.add(marker)
        declared = set(type(item).model_fields)
        stored = dict(getattr(item, "__dict__", {}))
        pydantic_extra = getattr(item, "__pydantic_extra__", None)
        if isinstance(pydantic_extra, Mapping):
            stored.update(pydantic_extra)
        for name in sorted(set(stored) - declared):
            unexpected.add(name)
            if name in FORBIDDEN_RECORDED_OBSERVATION_FIELDS:
                forbidden.add(name)
            scan_extra_payload(stored[name])
        for name in declared:
            nested = getattr(item, name, None)
            if isinstance(nested, BaseModel):
                visit_model(nested)
            elif isinstance(nested, (list, tuple)):
                for child in nested:
                    if isinstance(child, BaseModel):
                        visit_model(child)

    visit_model(value)
    return tuple(sorted(unexpected)), tuple(sorted(forbidden))


def _transport_provider_status(status: ObservationTransportStatus) -> ProviderStatus:
    if status is ObservationTransportStatus.REFUSED:
        raise CanonicalSuccessorUnavailable(
            SuccessorUnavailableReason.CANONICAL_PROCESSING_REJECTED,
            "v0 has no canonical ProviderStatus equivalent for refused transport",
        )
    return {
        ObservationTransportStatus.TIMEOUT: ProviderStatus.TIMEOUT,
        ObservationTransportStatus.RATE_LIMITED: ProviderStatus.RATE_LIMITED,
        ObservationTransportStatus.ERROR: ProviderStatus.ERROR,
        ObservationTransportStatus.UNAVAILABLE: ProviderStatus.UNAVAILABLE,
    }[status]


class CanonicalSuccessorEnvironmentV0:
    """Stateless one-transition façade over branch-local canonical CED objects."""

    env_id = CANONICAL_SUCCESSOR_ENV_ID

    def __init__(self) -> None:
        self._constitution = CEDSearchConstitution()

    def capture_capsule(
        self,
        ced: CEDOrchestrator,
        state: SessionState,
        *,
        budget: SearchBudget,
        budget_usage: Optional[BudgetUsage] = None,
    ) -> CanonicalBranchCapsule:
        """Detach a validated pristine opening without mutating the source CED."""

        usage = budget_usage or BudgetUsage()
        before = canonical_runtime_fingerprint(ced)
        if ced._sessions.get(state.session_id) is not state:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "SessionState is not the registered canonical source object",
            )
        try:
            budget.enforce(usage)
        except BudgetExceeded as exc:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.BUDGET_EXHAUSTED,
                str(exc),
            ) from exc
        snapshot, bindings = _structural_snapshot(ced, state)
        snapshot_json = canonical_json(snapshot)

        # All canonical reads occur on a fresh rehydration, never on production.
        clone, clone_state = _rehydrate_snapshot(
            source_snapshot_json=snapshot_json,
            configuration_digest=_digest(snapshot["runtime_configuration"]),
            session_id=state.session_id,
        )
        spec = _validate_pristine_opening_root(clone, clone_state)
        active_binding = next(
            item for item in bindings if item.agent_id == spec.agent_id
        )
        task = clone._build_registry_phase_task(
            clone_state, DialogPhase.OPENING, spec, 0
        )
        task_identity = canonical_task_semantic_identity(
            task, model_config_digest=active_binding.model_config_digest
        )
        semantic_payload, projection = canonical_transition_semantic_snapshot(
            clone,
            clone_state,
            task=spec,
            budget=budget,
            budget_usage=usage,
            depth=0,
        )
        legal = self._constitution.legal_actions(projection.base_state)
        if len(legal) != 1 or legal[0].kind is not ActionKind.ASK_SOCRATIC_QUESTION:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "canonical hard-legal root is not the sole opening Socratic action",
            )
        capsule = CanonicalBranchCapsule(
            session_id=state.session_id,
            search_state_v1_id=projection.state_id,
            source_snapshot_json=snapshot_json,
            normalized_semantic_digest=_digest(semantic_payload),
            configuration_digest=_digest(snapshot["runtime_configuration"]),
            canonical_task=task_identity,
            provider_bindings=bindings,
            side_ledgers=_side_ledger_digests(snapshot["side_ledgers"]),
            budget=budget,
            budget_usage=usage,
        )
        if canonical_runtime_fingerprint(ced) != before:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "capsule capture changed the source CED",
            )
        return capsule

    def _validate_capsule(
        self, capsule: CanonicalBranchCapsule
    ) -> Tuple[CanonicalBranchCapsule, CEDOrchestrator, SessionState, CanonicalTaskSpec, object]:
        try:
            capsule = CanonicalBranchCapsule.model_validate_json(
                capsule.model_dump_json()
            )
        except (AttributeError, ValidationError) as exc:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "capsule identity or schema is invalid",
            ) from exc
        if capsule.parent_branch_id is not None:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "v0 accepts a root capsule, not a successor capsule",
            )
        ced, state = _rehydrate(capsule)
        spec = _validate_pristine_opening_root(ced, state)
        binding = next(
            (item for item in capsule.provider_bindings if item.agent_id == spec.agent_id),
            None,
        )
        if binding is None:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "active opening agent has no capsule provider binding",
            )
        task = ced._build_registry_phase_task(state, DialogPhase.OPENING, spec, 0)
        if canonical_task_semantic_identity(\
                task, model_config_digest=binding.model_config_digest) \
                != capsule.canonical_task:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "capsule task semantics do not replay canonically",
            )
        semantic, projection = canonical_transition_semantic_snapshot(
            ced,
            state,
            task=spec,
            budget=capsule.budget,
            budget_usage=capsule.budget_usage,
            depth=0,
        )
        if (
            projection.state_id != capsule.search_state_v1_id
            or _digest(semantic) != capsule.normalized_semantic_digest
        ):
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "capsule semantic root or SearchState-v1 identity diverged",
            )
        snapshot = json.loads(capsule.source_snapshot_json)
        if _side_ledger_digests(snapshot["side_ledgers"]) != capsule.side_ledgers:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "capsule side-ledger integrity mismatch",
            )
        return capsule, ced, state, spec, projection

    def prepare_transition(
        self,
        capsule: CanonicalBranchCapsule,
        action: LegalAction,
        budget: SearchBudget,
    ) -> PendingCanonicalTransition:
        """Validate legality and reserve exactly one offline successor evaluation."""

        capsule, _, _, _, projection = self._validate_capsule(capsule)
        if budget != capsule.budget:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "prepare budget differs from the budget frozen in the root",
            )
        try:
            action = LegalAction.model_validate_json(action.model_dump_json())
        except (AttributeError, ValidationError) as exc:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.ILLEGAL_ACTION,
                "legal-action identity or schema is invalid",
            ) from exc
        if action.kind is not ActionKind.ASK_SOCRATIC_QUESTION:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.UNSUPPORTED_ACTION_FAMILY,
                f"v0 does not support {action.kind.value}",
            )
        legal = tuple(self._constitution.legal_actions(projection.base_state))
        try:
            self._constitution.validate_action(projection.base_state, action)
        except ContractValidationError as exc:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.ILLEGAL_ACTION,
                str(exc),
            ) from exc
        binding = next(
            item
            for item in capsule.provider_bindings
            if item.agent_id == capsule.canonical_task.agent_id
        )
        try:
            budget.enforce(
                capsule.budget_usage.plus(NewExecutionUsage().budget_delta)
            )
        except BudgetExceeded as exc:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.BUDGET_EXHAUSTED,
                str(exc),
            ) from exc
        try:
            return PendingCanonicalTransition(
                source_capsule=capsule,
                source_capsule_id=capsule.capsule_id,
                source_branch_id=capsule.branch_id,
                root_state_v1_id=capsule.search_state_v1_id,
                selected_action=action,
                complete_legal_action_ids=tuple(item.action_id for item in legal),
                canonical_task=capsule.canonical_task,
                expected_provider_id=binding.provider_id,
                expected_model_id=binding.model_id,
                budget=budget,
                budget_before=capsule.budget_usage,
                canonical_processor_ids=CANONICAL_PROCESSOR_IDS,
            )
        except (ValidationError, ContractValidationError) as exc:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "pending transition contract rejected canonical inputs",
            ) from exc

    @staticmethod
    def _unavailable_result(
        pending: PendingCanonicalTransition,
        reason: SuccessorUnavailableReason,
        observation: Optional[RecordedCanonicalObservation],
        *,
        legal_status: LegalActionValidationStatus = LegalActionValidationStatus.PASSED,
        usage: Optional[NewExecutionUsage] = None,
    ) -> CanonicalTransitionResult:
        execution = usage or NewExecutionUsage.not_applied()
        after = pending.budget_before.plus(execution.budget_delta)
        receipt = CanonicalTransitionReceipt(
            transition_id=pending.transition_id,
            root_capsule_id=pending.source_capsule_id,
            root_branch_id=pending.source_branch_id,
            root_state_v1_id=pending.root_state_v1_id,
            action_id=pending.selected_action.action_id,
            observation_id=(observation.observation_id if observation else None),
            observation_digest=(
                observation.raw_output_digest if observation else None
            ),
            status=CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
            legal_action_validation=legal_status,
            unavailable_reason=reason,
            source_state_hash=pending.source_capsule.normalized_semantic_digest,
            canonical_processor_ids=pending.canonical_processor_ids,
            budget=pending.budget,
            budget_before=pending.budget_before,
            new_execution_usage=execution,
            budget_after=after,
            recorded_historical_usage=(
                observation.historical_usage if observation else None
            ),
        )
        return CanonicalTransitionResult(
            transition_id=pending.transition_id,
            status=CanonicalTransitionStatus.SUCCESSOR_UNAVAILABLE,
            receipt=receipt,
        )

    @staticmethod
    def _validated_observation(
        value: object,
    ) -> Tuple[Optional[RecordedCanonicalObservation], Optional[SuccessorUnavailableReason]]:
        if value is None:
            return None, SuccessorUnavailableReason.MISSING_OBSERVATION
        if isinstance(value, BaseModel):
            unexpected, forbidden = _stored_contract_extras(value)
            if forbidden:
                return None, SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN
            if unexpected:
                return None, SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY
        raw_mapping = value if isinstance(value, Mapping) else None
        if raw_mapping is not None:
            forbidden = _forbidden_fields_in_structure(raw_mapping)
            if forbidden:
                return None, SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN
        try:
            if isinstance(value, RecordedCanonicalObservation):
                observation = RecordedCanonicalObservation.model_validate_json(
                    value.model_dump_json()
                )
            else:
                observation = RecordedCanonicalObservation.model_validate(value)
        except ValidationError:
            # An already-instantiated frozen contract can fail round-trip only
            # when its stored identity was tampered with (for example through
            # Pydantic's low-level ``model_copy(update=...)`` escape hatch).
            # Never clear and re-mint that identity on the caller's behalf.
            if isinstance(value, RecordedCanonicalObservation):
                return None, SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY
            if isinstance(value, Mapping) and value.get("observation_id"):
                return None, SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY
            return None, SuccessorUnavailableReason.INVALID_OBSERVATION
        return observation, None

    def apply_observation(
        self,
        pending: PendingCanonicalTransition,
        observation: object,
    ) -> CanonicalTransitionResult:
        """Apply one external recorded observation through canonical CED rules."""

        if isinstance(pending, BaseModel):
            unexpected, _ = _stored_contract_extras(pending)
            if unexpected:
                raise CanonicalSuccessorUnavailable(
                    SuccessorUnavailableReason.INVALID_ROOT,
                    "pending transition contains non-contract fields",
                )
        try:
            pending = PendingCanonicalTransition.model_validate_json(
                pending.model_dump_json()
            )
        except (AttributeError, ValidationError) as exc:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "pending transition identity or embedded capsule is invalid",
            ) from exc
        replayed_pending = self.prepare_transition(
            pending.source_capsule,
            pending.selected_action,
            pending.budget,
        )
        if replayed_pending != pending:
            raise CanonicalSuccessorUnavailable(
                SuccessorUnavailableReason.INVALID_ROOT,
                "pending transition does not replay from its canonical root",
            )
        validated, invalid_reason = self._validated_observation(observation)
        if invalid_reason is not None:
            return self._unavailable_result(pending, invalid_reason, validated)
        assert validated is not None
        if (
            validated.raw_text is not None
            and (future := _structured_future_fields(validated.raw_text))
        ):
            return self._unavailable_result(
                pending,
                SuccessorUnavailableReason.FUTURE_LABEL_FORBIDDEN,
                validated,
            )
        if not verify_authoritative_recorded_observation(validated):
            return self._unavailable_result(
                pending,
                SuccessorUnavailableReason.INVALID_OBSERVATION_IDENTITY,
                None,
            )
        try:
            validate_recorded_observation_compatibility(pending, validated)
        except RecordedObservationCompatibilityError as exc:
            return self._unavailable_result(pending, exc.reason, validated)
        if validated.transport_status is ObservationTransportStatus.REFUSED:
            return self._unavailable_result(
                pending,
                SuccessorUnavailableReason.CANONICAL_PROCESSING_REJECTED,
                validated,
            )

        ced, state = _rehydrate(pending.source_capsule)
        try:
            specs = ced._prepare_registry_phase(state, DialogPhase.OPENING)
            if len(specs) != 1:
                raise RuntimeError("canonical opening no longer contains one task")
            spec = specs[0]
            task = ced._build_registry_phase_task(
                state, DialogPhase.OPENING, spec, 0
            ).model_copy(update={"task_id": pending.replay_task_id})
            if canonical_task_semantic_identity(
                task,
                model_config_digest=pending.canonical_task.model_config_digest,
            ) != pending.canonical_task:
                raise RuntimeError("prepared task diverged from pending semantics")

            if validated.transport_status is ObservationTransportStatus.DELIVERED:
                meta: Dict[str, Any] = {}
                move, status, error = parse_and_validate_move(
                    validated.raw_text,
                    task,
                    meta=meta,
                )
                response = ProviderResponse(
                    provider_id=validated.provider_id,
                    agent_id=task.agent_id,
                    status=status,
                    raw_text=validated.raw_text,
                    parsed_move=move,
                    error_message=error,
                    retry_count=0,
                    repair_attempted=bool(meta.get("repair_attempted", False)),
                    repair_succeeded=bool(meta.get("repair_succeeded", False)),
                )
            else:
                response = ProviderResponse(
                    provider_id=validated.provider_id,
                    agent_id=task.agent_id,
                    status=_transport_provider_status(validated.transport_status),
                    error_message=validated.transport_error_code,
                )
            dispatch: list[Dict[str, Any]] = []
            application = ced._apply_registry_response(
                state,
                DialogPhase.OPENING,
                task,
                response,
                dispatch,
            )
            ced._finalize_registry_phase(
                state,
                DialogPhase.OPENING,
                [response],
                dispatch,
                ced._effective_registry_quorum(len(specs)),
            )
        except Exception:
            return self._unavailable_result(
                pending,
                SuccessorUnavailableReason.CANONICAL_PROCESSING_REJECTED,
                validated,
                usage=pending.reserved_usage,
            )

        status, rejection = canonical_transition_outcome(application)

        after = pending.budget_before.plus(pending.reserved_usage.budget_delta)
        semantic, projected = canonical_transition_semantic_snapshot(
            ced,
            state,
            task=spec,
            budget=pending.budget,
            budget_usage=after,
            depth=1,
        )
        successor_snapshot, _ = _structural_snapshot(ced, state)
        successor_configuration_digest = _digest(
            successor_snapshot["runtime_configuration"]
        )
        if successor_configuration_digest != (
            pending.source_capsule.configuration_digest
        ):
            return self._unavailable_result(
                pending,
                SuccessorUnavailableReason.CANONICAL_PROCESSING_REJECTED,
                validated,
                usage=pending.reserved_usage,
            )
        successor = CanonicalBranchCapsule(
            session_id=state.session_id,
            search_state_v1_id=projected.state_id,
            source_snapshot_json=canonical_json(successor_snapshot),
            normalized_semantic_digest=_digest(semantic),
            configuration_digest=successor_configuration_digest,
            canonical_task=pending.canonical_task,
            provider_bindings=pending.source_capsule.provider_bindings,
            side_ledgers=_side_ledger_digests(successor_snapshot["side_ledgers"]),
            budget=pending.budget,
            budget_usage=after,
            parent_branch_id=pending.source_branch_id,
            produced_by_transition_id=pending.transition_id,
            produced_by_observation_id=validated.observation_id,
        )
        receipt = CanonicalTransitionReceipt(
            transition_id=pending.transition_id,
            root_capsule_id=pending.source_capsule_id,
            root_branch_id=pending.source_branch_id,
            root_state_v1_id=pending.root_state_v1_id,
            branch_id=successor.branch_id,
            action_id=pending.selected_action.action_id,
            observation_id=validated.observation_id,
            observation_digest=validated.raw_output_digest,
            status=status,
            legal_action_validation=LegalActionValidationStatus.PASSED,
            canonical_rejection_reason=rejection,
            resulting_move_id=application.accepted_move_id,
            source_state_hash=pending.source_capsule.normalized_semantic_digest,
            successor_state_hash=successor.normalized_semantic_digest,
            successor_state_v1_id=projected.state_id,
            canonical_processor_ids=pending.canonical_processor_ids,
            budget=pending.budget,
            budget_before=pending.budget_before,
            new_execution_usage=pending.reserved_usage,
            budget_after=after,
            recorded_historical_usage=validated.historical_usage,
        )
        return CanonicalTransitionResult(
            transition_id=pending.transition_id,
            status=status,
            receipt=receipt,
            successor_capsule=successor,
            successor_search_state_v1=projected,
        )


__all__ = [
    "CANONICAL_PROCESSOR_IDS",
    "CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID",
    "CanonicalSuccessorEnvironmentV0",
    "CanonicalSuccessorUnavailable",
    "canonical_capsule_semantic_snapshot",
    "canonical_runtime_fingerprint",
    "canonical_task_semantic_identity",
    "canonical_transition_semantic_snapshot",
    "canonical_transition_outcome",
]
