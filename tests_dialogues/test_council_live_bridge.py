"""Offline authority and public-projection tests for the V0.2 council bridge."""

from __future__ import annotations

import asyncio
import json

import pytest

import backend.dialogues.council_live as council_live_module
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.council_live import (
    PUBLIC_EVENT_SCHEMA,
    LocalCouncilManager,
    project_commitments,
    project_final,
    project_public_move,
)
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    DialogPhase,
    ProviderResponse,
    ProviderStatus,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.socratic import CommitmentRecord, CommitmentStatus
from socrates.rendering import render_normal_response


SECRET = "sk-or-v1-THIS-MUST-NEVER-REACH-BROWSER"
PRIVATE_KEYS = {
    "api_key",
    "audit_summary",
    "authorization",
    "authority",
    "candidate",
    "context",
    "context_hash",
    "debug_context",
    "error_message",
    "failure_class",
    "leaderboard",
    "model_id",
    "output_schema",
    "provider_id",
    "ratification_votes",
    "raw_text",
    "schema_name",
    "score_breakdown",
    "source_move_id",
    "task_log",
}


@pytest.fixture(scope="module")
def canonical_run():
    manager = LocalCouncilManager()
    return asyncio.run(
        manager.run_to_completion(
            "Should a hospital use an AI triage assistant?",
            run_id="ced_ui_v02_projection_test",
        )
    )


def test_default_manager_runs_real_canonical_ced_offline(canonical_run):
    assert canonical_run.provider_mode == "mock"
    assert canonical_run.ced is not None
    assert isinstance(canonical_run.ced, CEDOrchestrator)
    assert canonical_run.state.question == canonical_run.question
    assert canonical_run.state.phase is DialogPhase.COMPLETE
    assert canonical_run.ced.registry.all_adapters()
    assert all(
        isinstance(adapter, ScriptedMockProvider) and adapter.is_fake is True
        for adapter in canonical_run.ced.registry.all_adapters()
    )


def test_public_events_are_monotonic_and_versioned(canonical_run):
    sequences = [event["sequence"] for event in canonical_run.events]
    assert sequences == list(range(len(sequences)))
    assert all(event["schema_version"] == PUBLIC_EVENT_SCHEMA for event in canonical_run.events)
    assert canonical_run.events[0]["type"] == "run.started"
    assert canonical_run.events[-1]["type"] == "run.completed"


def test_actual_ced_phases_and_roles_reach_projection(canonical_run):
    phase_events = [
        event for event in canonical_run.events if event["type"] == "phase.started"
    ]
    assert [event["data"]["phase"]["id"] for event in phase_events] == [
        phase.value for phase in canonical_run.state.phase_history
    ]
    projected = [
        (event["data"]["phase"]["id"], seat["seat_id"], seat["role"])
        for event in phase_events[:-1]
        for seat in event["data"]["seats"]
        if seat["role"] is not None
    ]
    canonical = [
        (row["phase"], row["agent_id"], row["role"])
        for row in canonical_run.state.role_history
    ]
    assert projected == canonical


def test_only_accepted_canonical_moves_become_contributions(canonical_run):
    accepted = [event["data"]["move"] for event in canonical_run.events
                if event["type"] == "move.accepted"]
    assert [move["move_id"] for move in accepted] == [
        move.move_id for move in canonical_run.state.moves
    ]
    assert all(move["status"] == "accepted" for move in accepted)


def test_empty_canonical_commitment_ledger_is_not_fabricated(canonical_run):
    snapshots = [event["data"] for event in canonical_run.events
                 if event["type"] == "commitments.snapshot"]
    assert snapshots
    assert snapshots[-1]["commitments"] == []
    assert canonical_run.ced.commitment_ledger(canonical_run.state) == []


def test_commitment_projection_keeps_history_and_derives_current_server_side():
    original = CommitmentRecord(
        commitment_id="cmt_original",
        source_move_id="move_a",
        cycle=0,
        claim="The initial claim.",
        status=CommitmentStatus.ASSERTED,
        provider_id="private_provider",
        model_id="private_model",
    )
    revision = CommitmentRecord(
        commitment_id="cmt_revision",
        source_move_id="move_b",
        cycle=1,
        claim="The revised claim.",
        status=CommitmentStatus.REVISED,
        target_commitment_id="cmt_original",
        provider_id="private_provider",
        model_id="private_model",
    )
    projected = project_commitments([original, revision])
    assert [item["commitment_id"] for item in projected] == [
        "cmt_original", "cmt_revision"
    ]
    assert projected[0]["is_current"] is False
    assert projected[1]["is_current"] is True
    serialized = json.dumps(projected)
    assert "private_provider" not in serialized
    assert "private_model" not in serialized


def test_final_projection_uses_normal_governing_renderer(canonical_run):
    final_event = canonical_run.events[-1]["data"]["final"]
    rendered = render_normal_response(canonical_run.final)
    assert final_event["outcome"] == rendered.outcome
    assert final_event["release_decision"] == rendered.release_decision
    assert final_event["governing_status"] == rendered.governing_epistemic_status
    assert final_event["notice"] == rendered.notice
    assert final_event["answer_released"] == rendered.candidate_authorized
    assert final_event["public_answer"] == rendered.public_answer


def test_blocked_final_never_projects_the_internal_candidate(canonical_run):
    blocked = canonical_run.final.model_copy(deep=True)
    blocked.answer = f"private candidate {SECRET}"
    blocked.release_decision = "blocked"
    blocked.governing_epistemic_status = "falsified"
    blocked.audit_summary["governing_release"] = {
        "available": True,
        "release_decision": "blocked",
        "governing_epistemic_status": "falsified",
    }
    projected = project_final(blocked)
    assert projected["outcome"] == "blocked"
    assert projected["answer_released"] is False
    assert projected["public_answer"] == ""
    assert projected["sections"] == []
    assert SECRET not in json.dumps(projected)


def test_secret_path_chain_of_thought_and_private_fields_are_scrubbed():
    move = AgentMove(
        task_id="private_task",
        agent_id="agent_0",
        role=AgentRole.SOCRATES,
        phase=DialogPhase.OPENING,
        task_kind=TaskKind.SOCRATIC_QUESTION,
        content={
            "question": f"What follows from {SECRET} at C:\\private\\run.json?",
            "api_key": SECRET,
            "chain_of_thought": "private scratchpad",
            "raw_provider_response": {"Authorization": f"Bearer {SECRET}"},
        },
    )
    projected = project_public_move(move)
    serialized = json.dumps(projected, ensure_ascii=False).lower()
    assert SECRET.lower() not in serialized
    assert "c:\\private\\run.json" not in serialized
    assert "api_key" not in serialized
    assert "chain_of_thought" not in serialized
    assert "raw_provider_response" not in serialized
    assert "provider_id" not in serialized
    assert "task_id" not in serialized
    assert projected["role"] == "socrates"
    assert projected["phase"] == "opening"
    assert projected["confidence"] == 0.7
    assert "What follows from" in projected["display_text"]
    assert "[REDACTED" in projected["display_text"]


def test_nested_private_values_inside_allowed_move_fields_are_not_projected():
    private_value = "PRIVATE-NESTED-VALUE-CANARY"
    move = AgentMove(
        task_id="nested_private_task",
        agent_id="agent_0",
        role=AgentRole.EMPIRICIST,
        phase=DialogPhase.INITIAL_RESPONSE,
        task_kind=TaskKind.INITIAL_RESPONSE,
        content={
            "factual_claims": [
                {
                    "claim": "A public factual claim.",
                    "status": "unverified",
                    "notes": "A public qualification.",
                    "raw_text": private_value,
                    "provider_id": "private-provider-canary",
                    "model_id": "private-model-canary",
                    "Authorization": "Basic RkFLRS1QUklWQVRFLUNBTkFSWQ==",
                    "path": r"C:\private\nested.json",
                    ".env": "OPENROUTER_API_KEY=private-env-canary",
                }
            ]
        },
    )
    projected = project_public_move(move)
    serialized = json.dumps(projected, ensure_ascii=False).lower()
    assert "a public factual claim" in serialized
    assert "unverified" in serialized
    assert "a public qualification" in serialized
    for forbidden in (
        private_value.lower(),
        "private-provider-canary",
        "private-model-canary",
        "rklrrs1quklwqvrflunbtkfswq==",
        "nested.json",
        "private-env-canary",
    ):
        assert forbidden not in serialized


class RejectInitialProvider(ScriptedMockProvider):
    async def generate_agent_move(self, task, agent_state):
        if task.task_kind is TaskKind.INITIAL_RESPONSE:
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.SCHEMA_ERROR,
                raw_text=SECRET,
                error_message=f"private failure {SECRET}",
            )
        return await super().generate_agent_move(task, agent_state)


class CommitmentMockProvider(ScriptedMockProvider):
    async def _produce_raw_text(self, task, agent_state):
        raw = await super()._produce_raw_text(task, agent_state)
        if task.task_kind is not TaskKind.INITIAL_RESPONSE:
            return raw
        payload = json.loads(raw)
        payload["content"]["commitments"] = [
            {"claim": f"Public canonical commitment from {task.agent_id}."}
        ]
        return json.dumps(payload)


def _rejecting_ced_factory():
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    # agent_0 is Socrates and is excluded from INITIAL_RESPONSE.  Bind the
    # rejecting adapter to agent_1 so this fixture exercises a real rejection.
    registry.register(ScriptedMockProvider("mock_seat0"))
    registry.register(RejectInitialProvider("rejecting_seat"))
    registry.register(ScriptedMockProvider("mock_seat2"))
    registry.register(ScriptedMockProvider("mock_seat3"))
    agents = [SocraticAgent(f"agent_{index}", provider) for index in range(4)]
    ced = CEDOrchestrator(
        agents,
        provider,
        registry=registry,
        assembly_fallback=True,
        phase_retry=False,
        ratification_repair="block",
    )
    return ced, "mock"


def _commitment_ced_factory():
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for index in range(4):
        registry.register(CommitmentMockProvider(f"commitment_seat{index}"))
    agents = [SocraticAgent(f"agent_{index}", provider) for index in range(4)]
    return CEDOrchestrator(
        agents,
        provider,
        registry=registry,
        assembly_fallback=True,
        phase_retry=False,
        ratification_repair="block",
    ), "mock"


def test_rejected_candidate_is_operational_event_never_contribution():
    manager = LocalCouncilManager(ced_factory=_rejecting_ced_factory)
    run = asyncio.run(
        manager.run_to_completion(
            "Does this rejected candidate stay private?",
            run_id="ced_ui_v02_rejection_test",
        )
    )
    rejected = [event for event in run.events if event["type"] == "operation.rejected"]
    accepted = [event["data"]["move"]["move_id"] for event in run.events
                if event["type"] == "move.accepted"]
    assert rejected
    assert accepted == [move.move_id for move in run.state.moves]
    serialized = json.dumps(run.public_snapshot(), ensure_ascii=False).lower()
    assert SECRET.lower() not in serialized
    assert "raw_text" not in serialized
    assert "error_message" not in serialized


def test_actual_canonical_commitment_harvest_reaches_public_snapshot():
    manager = LocalCouncilManager(ced_factory=_commitment_ced_factory)
    run = asyncio.run(manager.run_to_completion(
        "Which commitments survive?", run_id="ced_ui_v02_commitment_test"
    ))
    canonical = run.ced.commitment_ledger(run.state)
    assert canonical
    assert run.public_snapshot()["commitments"] == project_commitments(canonical)
    assert all(item["claim"].startswith("Public canonical commitment")
               for item in run.public_snapshot()["commitments"])


def test_ratification_projection_matches_canonical_result(canonical_run):
    projected = [event["data"]["ratification"] for event in canonical_run.events
                 if event["type"] == "ratification.completed"][-1]
    canonical = canonical_run.state.council_ratification
    assert projected == {
        "status": canonical.status.value,
        "valid_verdicts": canonical.valid_verdicts,
        "quorum": canonical.quorum,
        "caveat_count": canonical.caveat_count,
        "critical_block_count": canonical.critical_block_count,
    }


def test_public_snapshot_contains_no_private_contract_keys(canonical_run):
    def object_keys(value):
        if isinstance(value, dict):
            return {str(key).lower() for key in value} | {
                nested for item in value.values() for nested in object_keys(item)
            }
        if isinstance(value, list):
            return {nested for item in value for nested in object_keys(item)}
        return set()

    keys = object_keys(canonical_run.public_snapshot())
    for key in PRIVATE_KEYS:
        assert key not in keys


def test_returned_events_and_snapshots_are_detached_copies(canonical_run):
    events = canonical_run.events
    snapshot = canonical_run.public_snapshot()
    events[0]["data"]["question"] = "mutated"
    snapshot["contributions"].clear()
    assert canonical_run.events[0]["data"]["question"] == canonical_run.question
    assert canonical_run.public_snapshot()["contributions"]


def test_each_sse_subscriber_gets_an_independent_complete_replay(canonical_run):
    async def collect():
        async def one():
            return [event async for event in canonical_run.subscribe(-1)]
        return await asyncio.gather(one(), one())

    first, second = asyncio.run(collect())
    assert first == canonical_run.events
    assert second == canonical_run.events


def test_sse_does_not_drop_events_appended_while_replay_is_yielding():
    async def exercise():
        run = council_live_module.LocalCouncilRun("replay-race", "Question?")
        run.emit("run.started", {"status": "running"})
        subscription = run.subscribe(-1)
        first = await anext(subscription)
        run.emit("phase.started", {"phase": "opening"})
        run.emit(
            "run.failed",
            {"status": "failed", "message": "Safe terminal."},
            terminal=True,
        )
        remaining = [event async for event in subscription]
        return first, remaining

    first, remaining = asyncio.run(exercise())
    assert first["type"] == "run.started"
    assert [event["type"] for event in remaining] == [
        "phase.started",
        "run.failed",
    ]
    assert [event["sequence"] for event in [first, *remaining]] == [0, 1, 2]


def test_future_sse_cursor_closes_on_terminal_for_live_and_completed_runs():
    async def exercise_live():
        run = council_live_module.LocalCouncilRun("future-live", "Question?")
        subscription = run.subscribe(99)
        pending = asyncio.create_task(anext(subscription, None))
        await asyncio.sleep(0)
        run.emit(
            "run.failed",
            {"status": "failed", "message": "Safe terminal."},
            terminal=True,
        )
        return await asyncio.wait_for(pending, timeout=1)

    async def exercise_completed():
        run = council_live_module.LocalCouncilRun("future-complete", "Question?")
        run.emit(
            "run.failed",
            {"status": "failed", "message": "Safe terminal."},
            terminal=True,
        )
        return await asyncio.wait_for(anext(run.subscribe(99), None), timeout=1)

    assert asyncio.run(exercise_live()) is None
    assert asyncio.run(exercise_completed()) is None


def test_observer_projection_failure_cannot_change_canonical_result(monkeypatch):
    def broken_projector(_move):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(council_live_module, "project_public_move", broken_projector)
    run = asyncio.run(LocalCouncilManager().run_to_completion(
        "Does observability remain subordinate?",
        run_id="ced_ui_observer_isolation_test",
    ))
    assert run.state.phase is DialogPhase.COMPLETE
    assert run.final is not None
    assert run.status == "completed"
    assert not [event for event in run.events if event["type"] == "move.accepted"]
    assert run.events[-1]["type"] == "run.completed"
    assert SECRET not in json.dumps(run.public_snapshot())


def test_internal_failure_becomes_one_sanitized_terminal_event():
    def broken_factory():
        raise RuntimeError(f"private backend failure {SECRET} at C:\\private\\trace.txt")

    run = asyncio.run(LocalCouncilManager(ced_factory=broken_factory).run_to_completion(
        "Fail safely?", run_id="ced_ui_failure_sanitization_test"
    ))
    assert run.status == "failed"
    assert [event["type"] for event in run.events] == ["run.failed"]
    serialized = json.dumps(run.public_snapshot(), ensure_ascii=False)
    assert SECRET not in serialized
    assert "private backend failure" not in serialized
    assert "trace.txt" not in serialized


def test_duplicate_explicit_run_id_fails_without_replacing_the_first_run():
    async def exercise():
        manager = LocalCouncilManager()
        first = await manager.run_to_completion("First?", run_id="ced_ui_unique_test")
        with pytest.raises(ValueError, match="already exists"):
            await manager.run_to_completion("Second?", run_id="ced_ui_unique_test")
        return manager, first

    manager, first = asyncio.run(exercise())
    assert manager.get_run("ced_ui_unique_test") is first


def test_two_canonical_runs_are_isolated_and_sequence_independent():
    async def exercise():
        manager = LocalCouncilManager()
        first, second = await asyncio.gather(
            manager.run_to_completion("Question one?", run_id="ced_ui_parallel_one"),
            manager.run_to_completion("Question two?", run_id="ced_ui_parallel_two"),
        )
        return first, second

    first, second = asyncio.run(exercise())
    assert first.ced is not second.ced
    assert first.state is not second.state
    assert first.question != second.question
    assert first.events[0]["sequence"] == second.events[0]["sequence"] == 0
    assert {event["run_id"] for event in first.events} == {first.run_id}
    assert {event["run_id"] for event in second.events} == {second.run_id}


def test_process_environment_cannot_enable_live_providers_or_leak(monkeypatch):
    monkeypatch.setenv("CED_ENABLE_LIVE_PROVIDERS", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    run = asyncio.run(LocalCouncilManager().run_to_completion(
        "Does env={} keep this offline?", run_id="ced_ui_env_isolation_test"
    ))
    assert run.provider_mode == "mock"
    assert all(adapter.is_fake is True for adapter in run.ced.registry.all_adapters())
    assert SECRET not in json.dumps(run.public_snapshot(), ensure_ascii=False)
