"""Focused proof that Phase 8 recording observes the canonical CED path."""

from __future__ import annotations

import asyncio
import hashlib

import pytest

import backend.dialogues.ced_canonical_successor_recording as recording_module
from backend.dialogues.ced_canonical_successor import (
    canonical_runtime_fingerprint,
    canonical_task_semantic_identity,
)
from backend.dialogues.ced_canonical_successor_contracts import (
    ObservationCaptureKind,
    ObservationTransportStatus,
    RecordedObservationProvenance,
)
from backend.dialogues.ced_canonical_successor_recording import (
    capture_canonical_opening_observation,
    offline_fixture_historical_usage,
)
from backend.dialogues.ced_canonical_successor_recording_fixtures import (
    build_canonical_recording_root,
)
from backend.dialogues.models import DialogPhase, ProviderStatus
from backend.dialogues.socrates_zero.contracts import (
    ActionKind,
    BudgetUsage,
    LegalAction,
    SearchBudget,
    canonical_json,
)


RAW = (
    '{"content": {"question": "What assumption makes justified true belief '
    'seem sufficient for knowledge?", "operator": "expose_premise", '
    '"epistemic_marker": "open_uncertainty"}, "confidence": 0.7}'
)


def _budget() -> SearchBudget:
    return SearchBudget(
        max_nodes=4,
        max_expansions=3,
        max_model_calls=0,
        max_tool_calls=0,
        max_tokens=0,
        max_cost_microusd=0,
        max_wall_time_ms=0,
        max_depth=1,
    )


def test_recorder_observes_actual_task_and_response_without_owning_transition() -> None:
    ced, state, adapters = build_canonical_recording_root(
        question="Is knowledge justified true belief?",
        raw_text=RAW,
        session_id="phase8-recording-contract-test",
    )
    source_payload = {
        "fixture": "CanonicalSuccessorRecordingProvider",
        "raw_text": RAW,
    }
    provenance = RecordedObservationProvenance(
        capture_kind=ObservationCaptureKind.CANONICAL_RECORDED_TRANSITION,
        source_artifact_id="tests::phase8-recording-contract-test",
        source_artifact_digest=hashlib.sha256(
            canonical_json(source_payload).encode("utf-8")
        ).hexdigest(),
        source_revision="working-recording-contract-test",
    )
    before = canonical_runtime_fingerprint(ced)
    capture = asyncio.run(
        capture_canonical_opening_observation(
            ced,
            state,
            action=LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
            budget=_budget(),
            budget_usage=BudgetUsage(nodes=1),
            historical_usage=offline_fixture_historical_usage(),
            provenance=provenance,
        )
    )

    assert capture.source_runtime_fingerprint == before
    assert sum(item.generate_calls for item in adapters) == 1
    assert capture.offline_fixture_dispatches == 1
    assert capture.source_task.task_id
    assert capture.source_task.phase is DialogPhase.OPENING
    assert capture.provider_response.status is ProviderStatus.OK
    assert capture.provider_response.raw_text == RAW
    assert capture.canonical_application.accepted_move_id == state.moves[0].move_id
    assert capture.canonical_round_result is state.registry_rounds[0]
    assert capture.capture_receipt.source_task_id is None
    assert capture.observation.source_task_id is None
    assert capture.observation.transport_status is ObservationTransportStatus.DELIVERED
    assert capture.observation.capture_receipt_id \
        == capture.capture_receipt.capture_receipt_id
    assert capture.observation.task_identity == capture.source_capsule.canonical_task
    assert capture.observation.task_identity == canonical_task_semantic_identity(
        capture.source_task,
        model_config_digest=capture.observation.model_config_digest,
    )
    assert capture.observation.provider_id == capture.capture_receipt.provider_id
    assert capture.observation.actual_model_id \
        == capture.capture_receipt.actual_model_id
    assert capture.observation.raw_output_digest \
        == capture.capture_receipt.raw_output_digest
    serialized = capture.observation.model_dump(mode="json")
    assert "expected_successor" not in serialized
    assert "accepted" not in serialized
    assert "resulting_move_id" not in serialized


def test_recorder_refuses_observed_task_semantic_drift(monkeypatch) -> None:
    ced, state, _ = build_canonical_recording_root(
        question="Is knowledge justified true belief?",
        raw_text=RAW,
        session_id="phase8-recording-task-drift-test",
    )
    original_identity = recording_module.canonical_task_semantic_identity

    def drifted_identity(task, *, model_config_digest):
        identity = original_identity(
            task,
            model_config_digest=model_config_digest,
        )
        return identity.model_copy(update={"task_semantic_digest": "0" * 64})

    monkeypatch.setattr(
        recording_module,
        "canonical_task_semantic_identity",
        drifted_identity,
    )
    provenance = RecordedObservationProvenance(
        capture_kind=ObservationCaptureKind.CANONICAL_RECORDED_TRANSITION,
        source_artifact_id="tests::phase8-recording-task-drift-test",
        source_artifact_digest=hashlib.sha256(RAW.encode("utf-8")).hexdigest(),
        source_revision="working-recording-task-drift-test",
    )

    with pytest.raises(ValueError, match="observed canonical task differs"):
        asyncio.run(
            capture_canonical_opening_observation(
                ced,
                state,
                action=LegalAction(kind=ActionKind.ASK_SOCRATIC_QUESTION),
                budget=_budget(),
                budget_usage=BudgetUsage(nodes=1),
                historical_usage=offline_fixture_historical_usage(),
                provenance=provenance,
            )
        )
