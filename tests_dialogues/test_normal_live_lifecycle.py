"""Offline authority/lifecycle tests for the browser Normal Live bridge."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import AgentState, AgentTask
from backend.dialogues.provider_registry import ScriptedMockProvider
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    SocratesLiveOpenRouterAdapter,
)
from socrates.runtime import prepare
from socrates.source_authorization import (
    NormalLiveSourceAuthorizationError,
    VerifiedNormalLiveSourceAuthorizationV1,
)


SECRET_CANARIES = (
    "sk-or-v1-THIS-MUST-NEVER-REACH-BROWSER",
    "Authorization: Bearer THIS-MUST-NOT-LEAK",
    r"C:\private\secret\path",
)
SECRET_QUESTION = "\n".join(SECRET_CANARIES)


def _receipt(seed: str = "a") -> VerifiedNormalLiveSourceAuthorizationV1:
    return VerifiedNormalLiveSourceAuthorizationV1(
        authorization_id="normallivesourceauthv1_" + seed * 64,
        source_set_digest=seed * 64,
        authorized_implementation_commit_sha=seed * 40,
        authorized_implementation_tree_sha=seed * 40,
        runtime_identity="normal-socrates-browser-runtime/v1",
    )


class _Clock:
    def __init__(self, value: float = 100.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


class _FakeCompletion:
    http_status = 200
    completed = True
    failure_class = None
    retry_count = 0


class _FakeDispatchResult:
    def __init__(self, raw_response_body: bytes) -> None:
        self.raw_response_body = raw_response_body
        self.response_headers = (
            ("Content-Type", "application/json"),
            ("X-Test-Private-Debug", SECRET_CANARIES[0]),
        )
        self.completion = _FakeCompletion()
        self.registration = None
        self.dispatched_body = b""


class _DeterministicWireTransport:
    """Synchronous wire stub backed by the repository's scripted provider."""

    _provider_display = {
        "openai/gpt-5-mini": "OpenAI",
        "google/gemini-3.7-flash": "Google",
        "openai/gpt-4.1-mini": "Azure",
    }

    def __init__(self) -> None:
        self.calls = 0
        self.scripted = ScriptedMockProvider("normal_live_wire_fixture")

    @staticmethod
    def _complete_without_yield(coroutine) -> str:
        iterator = coroutine.__await__()
        try:
            yielded = next(iterator)
        except StopIteration as completed:
            return completed.value
        coroutine.close()
        raise AssertionError(f"offline scripted provider unexpectedly yielded {yielded!r}")

    def __call__(self, **kwargs):
        self.calls += 1
        body = json.loads(kwargs["body_bytes"].decode("utf-8"))
        user_content = body["messages"][-1]["content"]
        projected = json.loads(user_content.split("\n", 1)[1])
        task = AgentTask.model_validate(projected["task"])
        state = AgentState.model_validate(projected["agent_state"])
        content = self._complete_without_yield(
            self.scripted._produce_raw_text(task, state)
        )
        model = body["model"]
        response = {
            "id": f"offline-normal-{self.calls}",
            "model": model,
            "provider": self._provider_display[model],
            "object": "chat.completion",
            "created": 1,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": content},
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
                "cost": "0",
            },
            "private_debug": {
                "raw_response": SECRET_QUESTION,
                "exception_message": " ".join(SECRET_CANARIES),
            },
        }
        return _FakeDispatchResult(
            json.dumps(response, separators=(",", ":")).encode("utf-8")
        )


def _preflight(run_id: str = "normal-live-store-test"):
    return prepare(
        "What should the live council examine?",
        standing_cap_usd="1000",
        now=datetime(2026, 9, 1, tzinfo=timezone.utc),
        run_id=run_id,
    )


def test_preflight_store_is_bounded_ttl_and_one_use() -> None:
    from backend.dialogues.normal_live import (
        NormalLivePreflightConflictError,
        NormalLivePreflightExpiredError,
        NormalLivePreflightStore,
        make_normal_live_preflight_binding,
    )

    async def exercise() -> None:
        clock = _Clock()
        store = NormalLivePreflightStore(
            max_entries=2,
            ttl_seconds=10,
            monotonic_clock=clock,
        )
        first_preflight = _preflight()
        binding = make_normal_live_preflight_binding(first_preflight, _receipt())
        first = await store.create(first_preflight, binding)
        assert first.state == "pending"
        assert first.preflight.question == first_preflight.question
        assert first.binding == binding
        consumed = await store.consume(first.preflight_id, binding)
        assert consumed.state == "consumed"
        with pytest.raises(NormalLivePreflightConflictError):
            await store.consume(first.preflight_id, binding)

        expiring_preflight = _preflight("normal-live-store-expiry")
        expiring_binding = make_normal_live_preflight_binding(
            expiring_preflight, _receipt()
        )
        expiring = await store.create(expiring_preflight, expiring_binding)
        clock.value += 11
        with pytest.raises(NormalLivePreflightExpiredError):
            await store.inspect_pending(expiring.preflight_id)

    asyncio.run(exercise())


def test_preflight_store_cancel_and_concurrent_confirm_are_atomic() -> None:
    from backend.dialogues.normal_live import (
        NormalLivePreflightConflictError,
        NormalLivePreflightStore,
        make_normal_live_preflight_binding,
    )

    async def exercise() -> None:
        store = NormalLivePreflightStore(max_entries=4, ttl_seconds=30)
        cancelled_preflight = _preflight("normal-live-store-cancel")
        cancelled_binding = make_normal_live_preflight_binding(
            cancelled_preflight, _receipt()
        )
        cancelled = await store.create(cancelled_preflight, cancelled_binding)
        await store.cancel(cancelled.preflight_id)
        with pytest.raises(NormalLivePreflightConflictError):
            await store.consume(cancelled.preflight_id, cancelled_binding)

        racing_preflight = _preflight("normal-live-store-race")
        racing_binding = make_normal_live_preflight_binding(
            racing_preflight, _receipt()
        )
        racing = await store.create(racing_preflight, racing_binding)

        async def confirm():
            try:
                await store.consume(racing.preflight_id, racing_binding)
                return "started"
            except NormalLivePreflightConflictError:
                return "blocked"

        outcomes = await asyncio.gather(confirm(), confirm())
        assert sorted(outcomes) == ["blocked", "started"]

        cancel_racing_preflight = _preflight("normal-live-cancel-confirm-race")
        cancel_racing_binding = make_normal_live_preflight_binding(
            cancel_racing_preflight, _receipt()
        )
        cancel_racing = await store.create(
            cancel_racing_preflight, cancel_racing_binding
        )

        async def consume_or_block():
            try:
                result = await store.consume(
                    cancel_racing.preflight_id, cancel_racing_binding
                )
                return result.state
            except NormalLivePreflightConflictError:
                return "blocked"

        async def cancel_or_block():
            try:
                result = await store.cancel(cancel_racing.preflight_id)
                return result.state
            except NormalLivePreflightConflictError:
                return "blocked"

        transition_outcomes = await asyncio.gather(
            consume_or_block(), cancel_or_block()
        )
        assert transition_outcomes.count("blocked") == 1
        assert set(transition_outcomes) in (
            {"blocked", "consumed"},
            {"blocked", "cancelled"},
        )
        assert store.records[cancel_racing.preflight_id].state in {
            "consumed",
            "cancelled",
        }

    asyncio.run(exercise())


def test_manager_simultaneous_confirm_starts_exactly_one_task(
    tmp_path: Path,
) -> None:
    from backend.dialogues.normal_live import (
        NormalLiveCouncilManager,
        NormalLivePreflightConflictError,
    )

    manager = NormalLiveCouncilManager(
        source_verifier=lambda: _receipt(),
        run_root=tmp_path / "runs",
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    executions = 0
    release = asyncio.Event()

    async def fake_execute(run, _record):
        nonlocal executions
        executions += 1
        run.status = "running"
        await release.wait()
        run.status = "failed"
        run.emit(
            "run.failed",
            {"status": "failed", "message": "Test-only terminal event."},
            terminal=True,
        )

    manager._execute = fake_execute

    async def exercise() -> None:
        public = await manager.create_preflight("Confirm this preflight once.")

        async def confirm():
            try:
                return await manager.start_run(public["preflight_id"])
            except NormalLivePreflightConflictError:
                return None

        outcomes = await asyncio.gather(confirm(), confirm())
        started = [run for run in outcomes if run is not None]
        assert len(started) == 1
        assert executions == 1
        release.set()
        assert started[0].task is not None
        await started[0].task

    asyncio.run(exercise())
    assert len(manager.runs) == 1


def test_start_and_shutdown_race_cannot_hang_or_enter_execution(tmp_path: Path) -> None:
    from backend.dialogues.normal_live import (
        NormalLiveCapacityError,
        NormalLiveCouncilManager,
    )

    manager = NormalLiveCouncilManager(
        source_verifier=lambda: _receipt(),
        run_root=tmp_path / "runs",
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    manager._execute = AsyncMock(
        side_effect=AssertionError("cancelled launch must not enter execution")
    )

    async def exercise() -> None:
        public = await manager.create_preflight("Exercise the shutdown race.")
        starting = asyncio.create_task(manager.start_run(public["preflight_id"]))
        stopping = asyncio.create_task(manager.shutdown())
        outcomes = await asyncio.wait_for(
            asyncio.gather(starting, stopping, return_exceptions=True),
            timeout=1,
        )
        assert isinstance(outcomes[0], NormalLiveCapacityError)
        assert outcomes[1] is None
        assert manager._execute.await_count == 0
        assert manager.preflight_store.records[public["preflight_id"]].state == (
            "consumed"
        )
        runs = tuple(manager.runs.values())
        assert len(runs) == 1
        assert runs[0].status == "failed"
        assert [event["type"] for event in runs[0].events] == ["run.failed"]

    asyncio.run(exercise())


def test_binding_detects_plan_source_question_topology_and_limit_drift() -> None:
    from backend.dialogues.normal_live import make_normal_live_preflight_binding
    from socrates.runtime import NormalIntegrityError

    preflight = _preflight("normal-live-binding")
    original = make_normal_live_preflight_binding(preflight, _receipt("a"))
    assert original.question_sha256 == preflight.question_sha256
    assert original.maximum_calls == preflight.call_plan.maximum_call_count
    assert original.maximum_spend_picodollars == preflight.cost.maximum_cost_picodollars
    assert len(original.private_topology) == 3
    assert make_normal_live_preflight_binding(preflight, _receipt("b")) != original

    changed_question = _preflight("normal-live-binding")
    changed_question = replace(
        changed_question,
        question="A different server-owned question.",
        question_sha256=(
            __import__("hashlib").sha256(
                b"A different server-owned question."
            ).hexdigest()
        ),
        question_utf8_bytes=len(b"A different server-owned question."),
    )
    assert make_normal_live_preflight_binding(
        changed_question, _receipt("a")
    ) != original

    drifted_plan = replace(
        preflight,
        call_plan=replace(
            preflight.call_plan,
            agent_to_seat=tuple(reversed(preflight.call_plan.agent_to_seat)),
        ),
    )
    drifted_topology = replace(
        preflight,
        call_plan=replace(
            preflight.call_plan,
            seats=tuple(reversed(preflight.call_plan.seats)),
        ),
    )
    drifted_limit = replace(
        preflight,
        standing_cap_picodollars=preflight.standing_cap_picodollars + 1,
    )
    for drifted in (drifted_plan, drifted_topology):
        with pytest.raises(NormalIntegrityError):
            make_normal_live_preflight_binding(drifted, _receipt("a"))
    assert make_normal_live_preflight_binding(
        drifted_limit, _receipt("a")
    ) != original


def test_manager_verifies_source_before_canonical_prepare(monkeypatch, tmp_path: Path) -> None:
    import backend.dialogues.normal_live as normal_live

    calls: list[str] = []

    def absent_source():
        calls.append("source")
        raise NormalLiveSourceAuthorizationError(
            "manifest_absent " + " ".join(SECRET_CANARIES)
        )

    def forbidden_prepare(*_args, **_kwargs):
        calls.append("prepare")
        raise AssertionError("prepare must remain unreachable")

    monkeypatch.setattr(normal_live.normal_runtime, "prepare", forbidden_prepare)
    manager = normal_live.NormalLiveCouncilManager(
        source_verifier=absent_source,
        run_root=tmp_path / "runs",
    )
    with pytest.raises(normal_live.NormalLiveUnavailableError) as refused:
        asyncio.run(manager.create_preflight("Do not construct providers."))
    assert calls == ["source"]
    for canary in SECRET_CANARIES:
        assert canary not in str(refused.value)
    assert not (tmp_path / "runs").exists()


def test_manager_preflight_is_exact_safe_projection_of_canonical_plan(tmp_path: Path) -> None:
    from backend.dialogues.normal_live import NormalLiveCouncilManager

    manager = NormalLiveCouncilManager(
        source_verifier=lambda: _receipt(),
        run_root=tmp_path / "runs",
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    public = asyncio.run(manager.create_preflight(SECRET_QUESTION))
    assert set(public) == {
        "preflight_id",
        "question",
        "run_mode",
        "seats",
        "provider_count",
        "base_calls",
        "retry_calls",
        "maximum_calls",
        "maximum_cost_usd",
        "confirmation_required",
        "source_authorization_status",
    }
    assert public["run_mode"] == "normal_live"
    assert public["confirmation_required"] is True
    assert public["source_authorization_status"] == "authorized"
    assert public["provider_count"] == len(public["seats"]) == 3
    assert public["seats"] == [
        {"seat_id": "agent_0", "alias": "Aletheia"},
        {"seat_id": "agent_1", "alias": "Logos"},
        {"seat_id": "agent_2", "alias": "Praxis"},
    ]
    assert public["maximum_calls"] == public["base_calls"] + public["retry_calls"]
    assert isinstance(public["maximum_cost_usd"], str)
    serialized = json.dumps(public).lower()
    for canary in SECRET_CANARIES:
        assert canary.lower() not in serialized
    for forbidden in (
        "provider_id",
        "model_id",
        "policy_key",
        "source_set_digest",
        "authorization_id",
        "commit",
        "tree",
        "artifact",
        "alpha",
        "beta",
        "gamma",
    ):
        assert forbidden not in serialized


def test_manager_reverifies_source_and_refuses_stale_preflight(tmp_path: Path) -> None:
    from backend.dialogues.normal_live import (
        NormalLiveCouncilManager,
        NormalLivePreflightConflictError,
    )

    receipts = iter((_receipt("a"), _receipt("b")))
    manager = NormalLiveCouncilManager(
        source_verifier=lambda: next(receipts),
        run_root=tmp_path / "runs",
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    public = asyncio.run(manager.create_preflight("Will stale authority fail?"))
    with pytest.raises(NormalLivePreflightConflictError):
        asyncio.run(manager.start_run(public["preflight_id"]))
    assert manager.runs == {}
    assert not (tmp_path / "runs").exists()


def test_run_capacity_is_checked_before_confirmation_is_consumed(tmp_path: Path) -> None:
    from backend.dialogues.council_live import LocalCouncilRun
    from backend.dialogues.normal_live import (
        NormalLiveCapacityError,
        NormalLiveCouncilManager,
    )

    manager = NormalLiveCouncilManager(
        source_verifier=lambda: _receipt(),
        transport=lambda **_kwargs: pytest.fail("transport must remain unreachable"),
        run_root=tmp_path / "runs",
        max_retained_runs=1,
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    active = LocalCouncilRun("ced_" + "f" * 24, "Already running")
    active.status = "running"
    manager._runs[active.run_id] = active
    public = asyncio.run(manager.create_preflight("Do not burn this confirmation."))

    with pytest.raises(NormalLiveCapacityError):
        asyncio.run(manager.start_run(public["preflight_id"]))

    pending = asyncio.run(
        manager.preflight_store.inspect_pending(public["preflight_id"])
    )
    assert pending.state == "pending"
    asyncio.run(manager.cancel_preflight(public["preflight_id"]))
    assert not (tmp_path / "runs").exists()


def test_third_source_check_blocks_before_runtime_or_transport(tmp_path: Path, monkeypatch) -> None:
    import backend.dialogues.normal_live as normal_live

    checks: list[str] = []
    receipts = iter((_receipt("a"), _receipt("a"), _receipt("b")))

    def verifier():
        checks.append("source")
        return next(receipts)

    def forbidden_runtime(*_args, **_kwargs):
        raise AssertionError("runtime construction must remain unreachable")

    monkeypatch.setattr(normal_live.normal_runtime, "_build_live_runtime", forbidden_runtime)
    manager = normal_live.NormalLiveCouncilManager(
        source_verifier=verifier,
        transport=lambda **_kwargs: pytest.fail("transport must remain unreachable"),
        run_root=tmp_path / "runs" / "normal",
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    async def exercise():
        public = await manager.create_preflight("Recheck immediately before runtime.")
        run = await manager.start_run(public["preflight_id"])
        assert run.task is not None
        await run.task
        return public, run

    public, run = asyncio.run(exercise())
    assert checks == ["source", "source", "source"]
    assert run.status == "failed"
    assert manager.preflight_store.records[public["preflight_id"]].state == "consumed"
    run_directory = tmp_path / "runs" / "normal" / run.run_id
    assert (run_directory / "plan.json").is_file()
    result = json.loads((run_directory / "result.json").read_text(encoding="utf-8"))
    assert result["status"] == "execution_error"
    assert result["actual_accounting"]["calls_consumed"] == 0


def test_cancelled_preflight_never_creates_run_runtime_or_artifact(tmp_path: Path) -> None:
    from backend.dialogues.normal_live import (
        NormalLiveCouncilManager,
        NormalLivePreflightConflictError,
    )

    manager = NormalLiveCouncilManager(
        source_verifier=lambda: _receipt(),
        transport=lambda **_kwargs: pytest.fail("transport must remain unreachable"),
        run_root=tmp_path / "runs",
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    public = asyncio.run(manager.create_preflight("Cancel before execution."))
    asyncio.run(manager.cancel_preflight(public["preflight_id"]))
    with pytest.raises(NormalLivePreflightConflictError):
        asyncio.run(manager.start_run(public["preflight_id"]))
    assert manager.runs == {}
    assert not (tmp_path / "runs").exists()


def test_confirmed_test_transport_uses_real_three_adapters_canonical_ced_and_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 as adapter_module
    from backend.dialogues.normal_live import NormalLiveCouncilManager
    from socrates import runtime as normal_runtime

    transport = _DeterministicWireTransport()
    repository_root = Path(__file__).resolve().parents[1]
    runtime_json_reads: set[str] = set()
    real_read_text = Path.read_text
    real_read_bytes = Path.read_bytes

    def remember_json(path: Path) -> None:
        if path.suffix.lower() != ".json":
            return
        try:
            relative = path.resolve(strict=False).relative_to(repository_root)
        except (OSError, ValueError):
            return
        runtime_json_reads.add(relative.as_posix())

    def tracked_read_text(path: Path, *args, **kwargs):
        remember_json(path)
        return real_read_text(path, *args, **kwargs)

    def tracked_read_bytes(path: Path, *args, **kwargs):
        remember_json(path)
        return real_read_bytes(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked_read_text)
    monkeypatch.setattr(Path, "read_bytes", tracked_read_bytes)
    execute_calls = 0
    canonical_calls = 0
    real_execute = normal_runtime.execute
    real_canonical = CEDOrchestrator.run_registry_session

    async def counted_execute(*args, **kwargs):
        nonlocal execute_calls
        execute_calls += 1
        return await real_execute(*args, **kwargs)

    async def counted_canonical(self, *args, **kwargs):
        nonlocal canonical_calls
        canonical_calls += 1
        return await real_canonical(self, *args, **kwargs)

    def forbidden_external_dispatcher():
        raise AssertionError("external transport must remain unreachable")

    monkeypatch.setattr(normal_runtime, "execute", counted_execute)
    monkeypatch.setattr(CEDOrchestrator, "run_registry_session", counted_canonical)
    monkeypatch.setattr(
        adapter_module, "_default_dispatcher_v1", forbidden_external_dispatcher
    )
    manager = NormalLiveCouncilManager(
        source_verifier=lambda: _receipt(),
        transport=transport,
        run_root=tmp_path / "runs" / "normal",
        utc_clock=lambda: datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    async def exercise():
        public = await manager.create_preflight(SECRET_QUESTION)
        run = await manager.start_run(public["preflight_id"])
        assert run.task is not None
        await run.task
        return public, run

    public, run = asyncio.run(exercise())
    assert execute_calls == 1
    assert canonical_calls == 1
    assert transport.calls > 0
    assert transport.calls <= public["maximum_calls"]
    assert run.ced is not None
    assert isinstance(run.ced, CEDOrchestrator)
    adapters = run.ced.registry.all_adapters()
    assert len(adapters) == 3
    assert all(type(adapter) is SocratesLiveOpenRouterAdapter for adapter in adapters)
    dynamic_runtime_inputs = {
        "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs/hard_logic_live_test_collection_v1.json",
        "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs/q1_gemini_3_7_flash_endpoints_v1.json",
        "docs/branches/feature-socrates-zero-openrouter-one-live-shadow-v1/evidence/s7c_model_endpoints_response_v1.json",
    }
    assert dynamic_runtime_inputs <= runtime_json_reads
    from socrates.source_authorization import NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1

    assert runtime_json_reads <= set(NORMAL_LIVE_RUNTIME_SOURCE_PATHS_V1)
    assert run.status in {"completed", "blocked"}
    event_types = [event["type"] for event in run.events]
    assert event_types[0] == "run.started"
    assert "phase.started" in event_types
    assert "move.accepted" in event_types
    assert "ratification.completed" in event_types
    assert event_types[-1] == "run.completed"

    run_directory = tmp_path / "runs" / "normal" / run.run_id
    assert (run_directory / "plan.json").is_file()
    assert (run_directory / "result.json").is_file()
    assert (run_directory / "claims").is_dir()
    assert list((run_directory / "claims").iterdir())
    public_serialized = json.dumps(run.public_snapshot(), ensure_ascii=False).lower()
    event_serialized = json.dumps(run.events, ensure_ascii=False).lower()
    for canary in SECRET_CANARIES:
        assert canary.lower() not in public_serialized
        assert canary.lower() not in event_serialized
    for forbidden in (
        "provider_id",
        "model_id",
        "policy_key",
        "authorization_id",
        "source_set_digest",
        "artifact_path",
        "raw_text",
        "score_breakdown",
    ):
        assert forbidden not in public_serialized

    assert run.state is not None
    roles_by_agent: dict[str, set[str]] = {}
    for row in run.state.role_history:
        roles_by_agent.setdefault(row["agent_id"], set()).add(row["role"])
    assert any(len(roles) > 1 for roles in roles_by_agent.values())
    snapshots = [
        event["data"]["commitments"]
        for event in run.events
        if event["type"] == "commitments.snapshot"
    ]
    assert snapshots
    assert snapshots[-1] == run.public_snapshot()["commitments"]

    artifact = json.loads((run_directory / "result.json").read_text(encoding="utf-8"))
    completed = next(
        event for event in reversed(run.events) if event["type"] == "run.completed"
    )
    assert artifact["role_history"] == run.state.role_history
    assert artifact["governing"]["outcome"] == completed["data"]["final"]["outcome"]
    assert artifact["ratification"]["status"] == run.public_snapshot()["ratification"]["status"]
    artifact_text = json.dumps(artifact, ensure_ascii=False).lower()
    for canary in SECRET_CANARIES:
        assert canary.lower() not in artifact_text
