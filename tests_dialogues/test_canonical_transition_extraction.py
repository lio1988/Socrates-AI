"""Focused locks for the behavior-preserving registry transition extraction."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    DialogPhase,
    ProviderStatus,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.socratic import MaieuticOperator


QUESTION = "Is knowledge merely justified true belief?"


def _ced(provider_type=ScriptedMockProvider) -> CEDOrchestrator:
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(2):
        registry.register(provider_type(f"seat{index}"))
    return CEDOrchestrator(
        [SocraticAgent(f"agent_{index}", provider) for index in range(4)],
        provider,
        registry=registry,
    )


def _capture_extracted_calls(ced: CEDOrchestrator):
    prepared_specs = []
    built_tasks = []
    applications = []
    finalized = []

    original_prepare = ced._prepare_registry_phase
    original_build = ced._build_registry_phase_task
    original_apply = ced._apply_registry_response
    original_finalize = ced._finalize_registry_phase

    def prepare(*args, **kwargs):
        specs = original_prepare(*args, **kwargs)
        prepared_specs.append(specs)
        return specs

    def build(*args, **kwargs):
        task = original_build(*args, **kwargs)
        built_tasks.append(task)
        return task

    def apply(*args, **kwargs):
        application = original_apply(*args, **kwargs)
        applications.append(application)
        return application

    def finalize(*args, **kwargs):
        result = original_finalize(*args, **kwargs)
        finalized.append(result)
        return result

    return (
        prepared_specs,
        built_tasks,
        applications,
        finalized,
        prepare,
        build,
        apply,
        finalize,
    )


def test_production_registry_phase_delegates_to_all_extracted_helpers():
    ced = _ced()
    state = ced.create_session(QUESTION, session_id="extraction-accepted")
    spec = ced.canonical_registry_task_specs(state, DialogPhase.OPENING)[0]
    captured = _capture_extracted_calls(ced)
    (
        prepared,
        built,
        applications,
        finalized,
        prepare,
        build,
        apply,
        finalize,
    ) = captured

    with (
        patch.object(ced, "_prepare_registry_phase", side_effect=prepare) as prepare_spy,
        patch.object(ced, "_build_registry_phase_task", side_effect=build) as build_spy,
        patch.object(ced, "_apply_registry_response", side_effect=apply) as apply_spy,
        patch.object(ced, "_finalize_registry_phase", side_effect=finalize) as finalize_spy,
    ):
        result = asyncio.run(
            ced._run_registry_phase(state, DialogPhase.OPENING, 5.0)
        )

    assert (
        prepare_spy.call_count
        == build_spy.call_count
        == apply_spy.call_count
        == finalize_spy.call_count
        == 1
    )
    assert prepared == [(spec,)]
    assert len(built) == len(applications) == len(finalized) == 1
    task = built[0]
    assert (
        task.agent_id,
        task.role,
        task.phase,
        task.task_kind,
        task.slot_index,
        task.attempt_index,
    ) == (
        spec.agent_id,
        spec.role,
        DialogPhase.OPENING,
        spec.task_kind,
        spec.slot_index,
        0,
    )

    application = applications[0]
    assert application.provider_status is ProviderStatus.OK
    assert application.provider_ok is True
    assert application.accepted_move_id == state.moves[0].move_id
    assert application.canonical_rejection_reason is None
    assert application.dispatch_recorded is True

    assert result is finalized[0]
    assert result is state.registry_rounds[-1]
    assert result.proceed is True
    assert state.task_log[0].move_id == state.moves[0].move_id
    assert ced._phase_dispatch[state.session_id] == [{
        "phase": DialogPhase.OPENING.value,
        "slots": [{
            "slot_index": 0,
            "logical_agent_id": spec.agent_id,
            "assigned_role": spec.role.value,
            "provider_id": state.moves[0].provider_id,
            "model_id": f"mock/{state.moves[0].provider_id}",
            "attempt_index": 0,
            "retry": False,
            "ok": True,
        }],
    }]


class EmptyOpeningProvider(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind is TaskKind.SOCRATIC_QUESTION:
            return json.dumps({
                "content": {
                    "question": "",
                    "operator": MaieuticOperator.CLARIFY.value,
                    "epistemic_marker": "open_uncertainty",
                },
                "confidence": 0.7,
            })
        return await super()._produce_raw_text(task, agent_state)


def test_extracted_application_preserves_provider_ok_canonical_rejection():
    ced = _ced(EmptyOpeningProvider)
    state = ced.create_session(QUESTION, session_id="extraction-rejected")
    captured = _capture_extracted_calls(ced)
    _, _, applications, finalized, prepare, build, apply, finalize = captured

    with (
        patch.object(ced, "_prepare_registry_phase", side_effect=prepare),
        patch.object(ced, "_build_registry_phase_task", side_effect=build),
        patch.object(ced, "_apply_registry_response", side_effect=apply),
        patch.object(ced, "_finalize_registry_phase", side_effect=finalize),
    ):
        result = asyncio.run(
            ced._run_registry_phase(state, DialogPhase.OPENING, 5.0)
        )

    assert len(applications) == len(finalized) == 1
    application = applications[0]
    assert application.provider_status is ProviderStatus.OK
    assert application.provider_ok is True
    assert application.accepted_move_id is None
    assert "question must be non-empty" in application.canonical_rejection_reason
    assert application.dispatch_recorded is False

    # Existing semantics: provider quorum succeeds, but CED gives the refused
    # question no public identity and records no accepted dispatch slot.
    assert result.proceed is True
    assert state.moves == []
    assert len(state.task_log) == 1
    assert state.task_log[0].provider_status is ProviderStatus.OK
    assert state.task_log[0].move_id is None
    assert ced._phase_dispatch[state.session_id] == [{
        "phase": DialogPhase.OPENING.value,
        "slots": [],
    }]
    assert ced._socratic_audit_rows[state.session_id][0][
        "content_contract_accepted"
    ] is False


class InvalidOpeningProvider(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state):
        if task.task_kind is TaskKind.SOCRATIC_QUESTION:
            return "<<< not valid json >>>"
        return await super()._produce_raw_text(task, agent_state)


def test_extracted_application_preserves_provider_failure_without_fabrication():
    ced = _ced(InvalidOpeningProvider)
    state = ced.create_session(QUESTION, session_id="extraction-provider-failure")
    captured = _capture_extracted_calls(ced)
    _, _, applications, _, prepare, build, apply, finalize = captured

    with (
        patch.object(ced, "_prepare_registry_phase", side_effect=prepare),
        patch.object(ced, "_build_registry_phase_task", side_effect=build),
        patch.object(ced, "_apply_registry_response", side_effect=apply),
        patch.object(ced, "_finalize_registry_phase", side_effect=finalize),
    ):
        result = asyncio.run(
            ced._run_registry_phase(state, DialogPhase.OPENING, 5.0)
        )

    assert len(applications) == 1
    application = applications[0]
    assert application.provider_status is ProviderStatus.INVALID_JSON
    assert application.provider_ok is False
    assert application.accepted_move_id is None
    assert application.canonical_rejection_reason is None
    assert application.dispatch_recorded is True

    assert result.proceed is False
    assert state.moves == []
    assert len(state.task_log) == 1
    assert state.task_log[0].provider_status is ProviderStatus.INVALID_JSON
    assert state.task_log[0].move_id is None
    assert ced._phase_dispatch[state.session_id][0]["slots"][0]["ok"] is False
