"""Offline integration tests for the ordinary Normal Socrates runtime boundary."""

from __future__ import annotations

import asyncio
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import socrates.__main__ as normal_cli
from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    AgentRole,
    AgentState,
    AgentTask,
    DialogPhase,
    ShadowScoringMode,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    FakeProvider,
    ScriptedMockProvider,
)
from backend.dialogues.reasoning_prompts import build_reasoning_system_prompt
from backend.dialogues.socrates_zero.contracts import ContractValidationError
from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
    validate_ced_structured_output_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    build_turn_user_content_v1,
    safe_public_exception_code_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterDynamicTurnRequestV1,
    render_dynamic_turn_v1,
)
from scripts.question_bundles_v1 import load_bundle_v1
from socrates import runtime as normal_runtime
from socrates.rendering import NormalRenderResult
from socrates.runtime import (
    NORMAL_PROMPT_BUDGET_TOKENS,
    NormalAuthorizationError,
    NormalIntegrityError,
    NormalRunCollisionError,
    NormalRuntime,
    _build_live_runtime,
    execute,
    prepare,
    validate_preflight,
)


_RAW_SECRET = "FAKE-NOT-A-REAL-RAW-PROVIDER-SECRET"
_DEBUG_SECRET = "FAKE-NOT-A-REAL-DEBUG-CONTEXT-SECRET"

_ARTIFACT_KEYS = {
    "schema_version",
    "run_id",
    "session_id",
    "question_sha256",
    "question_utf8_bytes",
    "status",
    "error_code",
    "requested_topology",
    "served_models",
    "logical_agent_to_seat",
    "plan",
    "authorization_bounds",
    "actual_accounting",
    "turns",
    "task_log",
    "role_history",
    "phase_retries",
    "actual_same_seat_retries",
    "terminal_lost_voices",
    "ratification",
    "governing",
    "public",
    "internal_candidate",
}
_TURN_KEYS = {
    "turn_id",
    "role_seat",
    "dialogue_phase",
    "task_kind",
    "model",
    "provider_selector",
    "http_status",
    "transport_completed",
    "retry_count",
    "prompt_tokens",
    "completion_tokens",
    "observed_cost_picodollars",
    "actual_served_model",
    "provider_display_name",
    "returned_model_binding_ok",
    "returned_provider_binding_ok",
    "provider_structured_output_valid",
    "provider_structured_output_error",
    "ced_move_accepted",
    "ced_rejection_reason",
    "failure_class",
    "attempt_index",
    "attempt_failure_class",
    "objection_rulings_in_context",
}
_TASK_LOG_KEYS = {
    "task_id",
    "move_id",
    "session_id",
    "phase",
    "round_index",
    "agent_id",
    "assigned_role",
    "task_kind",
    "slot_index",
    "attempt_index",
    "schema_name",
    "context_hash",
    "provider_id",
    "provider_status",
}


class _CountingScriptedMockProvider(ScriptedMockProvider):
    """The repository fake plus a bounded call counter and hostile debug row."""

    def __init__(self, provider_id: str, model_id: str, alias: str) -> None:
        super().__init__(provider_id=provider_id, model_id=model_id)
        self.alias = alias
        self.normal_calls_consumed = 0
        self.seen_tasks: list[AgentTask] = []

    async def generate_agent_move(
        self, task: AgentTask, agent_state: AgentState
    ):
        self.normal_calls_consumed += 1
        self.seen_tasks.append(task)
        return await super().generate_agent_move(task, agent_state)

    def observability_rows(self):
        # The Normal artifact boundary must select safe fields, not serialize a
        # provider row wholesale.  These deliberately hostile values exercise
        # that projection without ever representing a real credential.
        return ({
            "turn_id": f"offline-{self.provider_id}",
            "role_seat": self.alias,
            "dialogue_phase": "offline_test",
            "task_kind": "offline_test",
            "model": self.model_id,
            "actual_served_model": self.model_id,
            "transport_completed": True,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "raw_text": _RAW_SECRET,
            "debug_context": {
                "Authorization": f"Bearer {_DEBUG_SECRET}",
            },
        },)


class _CountingCanonicalCED(CEDOrchestrator):
    """Count entry into, while retaining, the real canonical implementation."""

    canonical_run_calls = 0

    async def run_registry_session(
        self, question: str, session_id: str, timeout_seconds: float = 120.0
    ):
        self.canonical_run_calls += 1
        return await super().run_registry_session(
            question,
            session_id=session_id,
            timeout_seconds=timeout_seconds,
        )


class _ScriptedRuntimeFactory:
    def __init__(self) -> None:
        self.calls = 0
        self.runtime: NormalRuntime | None = None

    def __call__(self, preflight, _run_directory: Path, _progress) -> NormalRuntime:
        self.calls += 1
        registry = CouncilProviderRegistry(provider_timeout_seconds=5.0)
        adapters = tuple(
            _CountingScriptedMockProvider(
                provider_id=seat.provider_id,
                model_id=seat.model_id,
                alias=seat.alias,
            )
            for seat in preflight.call_plan.seats
        )
        for adapter in adapters:
            registry.register(adapter)
        fake = FakeProvider()
        ced = _CountingCanonicalCED(
            [SocraticAgent(f"agent_{index}", fake) for index in range(3)],
            fake,
            registry=registry,
            shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
            assembly_fallback=False,
            phase_retry=True,
            max_socratic_followups=2,
            ratification_repair="block",
            tree_expansions=0,
            ai_learning=False,
        )
        ced.mid_round_objection_rulings_v1 = True
        self.runtime = NormalRuntime(ced=ced, adapters=adapters)
        return self.runtime


def _run(coro):
    return asyncio.run(coro)


def _render_for_guard(adapter, task: AgentTask, agent_state: AgentState):
    policy = adapter._execution_policy_for_task(task)
    turn = OpenRouterDynamicTurnRequestV1(
        system_prompt=build_reasoning_system_prompt(
            task.role,
            task.phase,
            task.task_kind,
            model=None,
        ),
        user_content=build_turn_user_content_v1(
            task,
            agent_state,
            outbound_task_state_projector=(
                adapter._outbound_task_state_projector
            ),
        ),
        role_seat=task.role.value,
        dialogue_id=task.session_id,
        turn_id=task.task_id,
        dialogue_phase=task.phase.value,
    )
    return render_dynamic_turn_v1(
        policy,
        adapter.profile,
        turn,
        response_format_override=adapter._response_format_factory(task),
    )


def test_prepare_accepts_an_arbitrary_question_and_only_computes_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    question = "  Τι κάνει μια εξήγηση πραγματικά καλή; \U0001f9ed  "
    runtime_calls = 0

    def unexpected_runtime(*_args: Any, **_kwargs: Any):
        nonlocal runtime_calls
        runtime_calls += 1
        raise AssertionError("prepare constructed an execution runtime")

    monkeypatch.setattr(normal_runtime, "_build_live_runtime", unexpected_runtime)
    monkeypatch.setattr(normal_runtime, "DEFAULT_RUN_ROOT", tmp_path / "runs")
    preflight = prepare(
        question,
        standing_cap_usd="1000",
        run_id="normal-arbitrary-question",
        now=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
    )

    assert preflight.question == question
    assert preflight.question_sha256 == hashlib.sha256(
        question.encode("utf-8")
    ).hexdigest()
    assert preflight.question_utf8_bytes == len(question.encode("utf-8"))
    assert preflight.run_id == preflight.session_id == "normal-arbitrary-question"
    assert preflight.created_at_utc == "2026-08-30T12:00:00Z"
    assert runtime_calls == 0
    assert not normal_runtime.DEFAULT_RUN_ROOT.exists()
    assert list(tmp_path.iterdir()) == []


def test_exact_question_text_changes_the_bound_identity() -> None:
    first = prepare(
        "What follows?",
        standing_cap_usd="1000",
        run_id="normal-exact-question-identity",
    )
    second = prepare(
        "What follows? ",
        standing_cap_usd="1000",
        run_id="normal-exact-question-identity",
    )

    assert first.question == "What follows?"
    assert second.question == "What follows? "
    assert first.question_sha256 != second.question_sha256
    assert first.question_utf8_bytes + 1 == second.question_utf8_bytes


def test_persisted_plan_binds_question_by_digest_without_storing_raw_text() -> None:
    question = (
        "Authorization: Basic FAKE-NOT-A-REAL-AUTH-VALUE\n"
        "AWS_SECRET_ACCESS_KEY=FAKE-NOT-A-REAL-SECRET"
    )
    preflight = prepare(
        question,
        standing_cap_usd="1000",
        run_id="normal-question-digest-only",
    )

    encoded = json.dumps(preflight.plan_record(), sort_keys=True)
    assert "question" not in preflight.plan_record()
    assert "FAKE-NOT-A-REAL-AUTH-VALUE" not in encoded
    assert "FAKE-NOT-A-REAL-SECRET" not in encoded
    assert preflight.question_sha256 == hashlib.sha256(
        question.encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    ("standing_cap_usd", "confirmed", "message"),
    [
        ("0.000001", True, "exceeds configured maximum"),
        ("1000", False, "was not confirmed"),
    ],
)
def test_cap_block_and_unconfirmed_execution_are_side_effect_free(
    tmp_path: Path,
    standing_cap_usd: str,
    confirmed: bool,
    message: str,
) -> None:
    preflight = prepare(
        "A question whose execution is not authorized",
        standing_cap_usd=standing_cap_usd,
        run_id=f"normal-no-execute-{confirmed}",
    )
    factory_calls = 0

    def unexpected_factory(*_args: Any, **_kwargs: Any):
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("authorization gate called the runtime factory")

    run_root = tmp_path / "runs"
    with pytest.raises(NormalAuthorizationError, match=message):
        _run(execute(
            preflight,
            confirmed=confirmed,
            runtime_factory=unexpected_factory,
            run_root=run_root,
        ))

    assert factory_calls == 0
    assert not run_root.exists()


def test_write_once_run_collision_happens_before_factory_and_preserves_artifact(
    tmp_path: Path,
) -> None:
    preflight = prepare(
        "Do not overwrite the first run",
        standing_cap_usd="1000",
        run_id="normal-write-once-collision",
    )
    existing = tmp_path / "runs" / preflight.run_id
    existing.mkdir(parents=True)
    first_artifact = existing / "result.json"
    original = b'{"first":"immutable"}\n'
    first_artifact.write_bytes(original)
    factory_calls = 0

    def unexpected_factory(*_args: Any, **_kwargs: Any):
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("collision called the runtime factory")

    with pytest.raises(NormalRunCollisionError, match=preflight.run_id):
        _run(execute(
            preflight,
            confirmed=True,
            runtime_factory=unexpected_factory,
            run_root=tmp_path / "runs",
        ))

    assert factory_calls == 0
    assert first_artifact.read_bytes() == original
    assert sorted(path.name for path in existing.iterdir()) == ["result.json"]


def test_redirected_run_root_is_refused_before_runtime_factory(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    redirected = tmp_path / "redirected"
    try:
        redirected.symlink_to(actual, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {type(exc).__name__}")

    preflight = prepare(
        "Do not follow a redirected artifact root",
        standing_cap_usd="1000",
        run_id="normal-redirected-root",
    )
    factory_calls = 0

    def unexpected_factory(*_args: Any, **_kwargs: Any):
        nonlocal factory_calls
        factory_calls += 1
        raise AssertionError("redirected root called runtime factory")

    with pytest.raises(NormalIntegrityError, match="redirected"):
        _run(execute(
            preflight,
            confirmed=True,
            runtime_factory=unexpected_factory,
            run_root=redirected,
        ))

    assert factory_calls == 0
    assert list(actual.iterdir()) == []


def test_live_runtime_construction_is_exact_strict_offline_and_fully_authorized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = prepare(
        "Inspect the strict Normal runtime without dispatching it",
        standing_cap_usd="1000",
        run_id="normal-strict-runtime",
    )
    dispatch_calls = 0

    def forbidden_dispatch(*_args: Any, **_kwargs: Any):
        nonlocal dispatch_calls
        dispatch_calls += 1
        raise AssertionError("runtime construction dispatched a provider request")

    monkeypatch.setenv(
        "OPENROUTER_API_KEY", "FAKE-NOT-A-REAL-CREDENTIAL-MUST-NOT-BE-READ"
    )
    run_directory = tmp_path / "not-created-by-construction"
    runtime = _build_live_runtime(
        preflight,
        run_directory,
        confirmed=True,
        dispatch=forbidden_dispatch,
    )

    expected = (
        ("Alpha", "worker_alpha", "openai/gpt-5-mini", "openai/flex", "max_tokens"),
        (
            "Beta",
            "worker_beta",
            "google/gemini-3.7-flash",
            "google-vertex/global",
            "max_tokens",
        ),
        (
            "Gamma",
            "worker_gamma",
            "openai/gpt-4.1-mini",
            "azure/swedencentral",
            "max_completion_tokens",
        ),
    )
    assert tuple(
        (
            adapter.worker_alias,
            adapter.provider_id,
            adapter.model_id,
            adapter.policy.provider_only[0],
            adapter.profile.output_limit_parameter,
        )
        for adapter in runtime.adapters
    ) == expected
    assert [agent.agent_id for agent in runtime.ced.agents] == [
        "agent_0",
        "agent_1",
        "agent_2",
    ]
    assert tuple(runtime.ced.registry.available_adapters()) == runtime.adapters
    assert all(adapter.ledger is runtime.ledger for adapter in runtime.adapters)
    assert all(adapter.api_key is None for adapter in runtime.adapters)
    assert all(adapter._dispatch is forbidden_dispatch for adapter in runtime.adapters)
    assert all(adapter.policy.allow_fallbacks is False for adapter in runtime.adapters)
    assert all(adapter.policy.require_parameters is True for adapter in runtime.adapters)
    assert all(adapter.policy.stream is False for adapter in runtime.adapters)
    assert all(adapter.policy.maximum_local_dispatches == 1 for adapter in runtime.adapters)
    assert all(adapter.policy.automatic_retries == 0 for adapter in runtime.adapters)
    assert all(adapter.ced_parse_repair_attempts == 0 for adapter in runtime.adapters)
    assert all(adapter.expose_model_identity_to_worker is False for adapter in runtime.adapters)
    assert all(adapter.max_input_tokens == NORMAL_PROMPT_BUDGET_TOKENS for adapter in runtime.adapters)
    assert dispatch_calls == 0
    assert not run_directory.exists()

    initial_tasks = tuple(
        AgentTask(
            task_id=f"strict-initial-{index}",
            session_id=preflight.session_id,
            agent_id=f"agent_{index}",
            role=AgentRole.EMPIRICIST,
            phase=DialogPhase.INITIAL_RESPONSE,
            question=preflight.question,
            task_kind=TaskKind.INITIAL_RESPONSE,
        )
        for index in range(3)
    )
    assert tuple(
        adapter._task_execution_policy_factory(task).output_limit_tokens
        for adapter, task in zip(runtime.adapters, initial_tasks, strict=True)
    ) == (14_000, 8_192, 8_192)

    authorization = runtime.authorization
    assert authorization is not None
    assert authorization.model == "multi-model"
    assert authorization.provider_selector == "multi-endpoint"
    assert authorization.session_id == preflight.session_id
    assert authorization.maximum_calls == 135
    assert authorization.maximum_calls == preflight.call_plan.maximum_call_count
    assert authorization.maximum_total_spend_picodollars == (
        preflight.cost.maximum_cost_picodollars
    )
    assert authorization.maximum_per_call_spend_picodollars == (
        preflight.maximum_per_call_picodollars
    )
    assert authorization.policy_id.startswith("normal-policy-set-sha256-")
    assert authorization.profile_id.startswith("normal-profile-set-sha256-")
    assert authorization.policy_id != runtime.adapters[0].policy.policy_id
    assert authorization.profile_id != runtime.adapters[0].profile.profile_id

    ced = runtime.ced
    assert ced.shadow_scoring_mode is ShadowScoringMode.ALL_PHASES
    assert ced.assembly_fallback is False
    assert ced.phase_retry is True
    assert ced.max_socratic_followups == 2
    assert ced.ratification_repair == "block"
    assert ced.tree_expansions == 0
    assert ced.ai_learning is False
    assert ced.mid_round_objection_rulings_v1 is True


def test_private_runtime_builder_rechecks_cap_and_explicit_confirmation(
    tmp_path: Path,
) -> None:
    admitted = prepare(
        "Builder confirmation gate",
        standing_cap_usd="1000",
        run_id="normal-builder-confirmation",
    )
    with pytest.raises(NormalAuthorizationError, match="not confirmed"):
        _build_live_runtime(admitted, tmp_path / "unconfirmed")

    blocked = prepare(
        "Builder cap gate",
        standing_cap_usd="0.000001",
        run_id="normal-builder-cap",
    )
    with pytest.raises(NormalAuthorizationError, match="exceeds configured"):
        _build_live_runtime(
            blocked,
            tmp_path / "over-cap",
            confirmed=True,
        )
    assert list(tmp_path.iterdir()) == []


def test_predispatch_guard_rejects_an_ordinary_task_outside_the_plan(
    tmp_path: Path,
) -> None:
    preflight = prepare(
        "Guard membership proof",
        standing_cap_usd="1000",
        run_id="normal-guard-membership",
    )
    runtime = _build_live_runtime(
        preflight,
        tmp_path / "unused",
        confirmed=True,
        dispatch=lambda **_kwargs: None,
    )
    adapter = runtime.adapters[0]
    task = AgentTask(
        task_id="invented-task-not-in-plan",
        session_id=preflight.session_id,
        agent_id="agent_0",
        role=AgentRole.EMPIRICIST,
        phase=DialogPhase.INITIAL_RESPONSE,
        question=preflight.question,
        task_kind=TaskKind.INITIAL_RESPONSE,
        attempt_index=0,
        round_number=99,
        slot_index=99,
    )
    agent_state = AgentState(
        agent_id="agent_0",
        primary_role=AgentRole.EMPIRICIST,
        assigned_role=AgentRole.EMPIRICIST,
    )
    rendered = _render_for_guard(adapter, task, agent_state)

    with pytest.raises(ContractValidationError, match="authorized"):
        adapter._pre_dispatch_guard(task, rendered)


def test_predispatch_retry_requires_its_same_slot_original_first(
    tmp_path: Path,
) -> None:
    preflight = prepare(
        "Retry ordering proof",
        standing_cap_usd="1000",
        run_id="normal-retry-ordering",
    )
    runtime = _build_live_runtime(
        preflight,
        tmp_path / "unused",
        confirmed=True,
        dispatch=lambda **_kwargs: None,
    )
    planned = next(
        call
        for call in preflight.call_plan.base_calls
        if call.seat_alias == "Alpha"
        and call.task_kind is TaskKind.INITIAL_RESPONSE
    )
    adapter = runtime.adapters[0]
    agent_state = AgentState(
        agent_id=planned.logical_agent_id,
        primary_role=planned.role,
        assigned_role=planned.role,
    )

    def task_for(attempt_index: int) -> AgentTask:
        return AgentTask(
            task_id=f"normal-retry-order-{attempt_index}",
            session_id=preflight.session_id,
            agent_id=planned.logical_agent_id,
            role=planned.role,
            phase=planned.phase,
            question=preflight.question,
            task_kind=planned.task_kind,
            round_number=planned.round_index,
            slot_index=planned.slot_index,
            attempt_index=attempt_index,
        )

    retry = task_for(1)
    with pytest.raises(ContractValidationError, match="same-slot original"):
        adapter._pre_dispatch_guard(
            retry,
            _render_for_guard(adapter, retry, agent_state),
        )

    original = task_for(0)
    adapter._pre_dispatch_guard(
        original,
        _render_for_guard(adapter, original, agent_state),
    )
    adapter._pre_dispatch_guard(
        retry,
        _render_for_guard(adapter, retry, agent_state),
    )


def test_predispatch_quota_consumption_is_atomic_across_threads() -> None:
    preflight = prepare(
        "Concurrent quota proof",
        standing_cap_usd="1000",
        run_id="normal-concurrent-quota",
    )
    planned = next(
        call
        for call in preflight.call_plan.base_calls
        if call.seat_alias == "Alpha"
        and call.task_kind is TaskKind.INITIAL_RESPONSE
    )
    dispatch_plan = normal_runtime._NormalDispatchPlanAuthorization(
        normal_runtime._normal_execution_branch_plans(preflight.session_id)
    )
    task = AgentTask(
        task_id="normal-concurrent-quota-task",
        session_id=preflight.session_id,
        agent_id=planned.logical_agent_id,
        role=planned.role,
        phase=planned.phase,
        question=preflight.question,
        task_kind=planned.task_kind,
        round_number=planned.round_index,
        slot_index=planned.slot_index,
        attempt_index=0,
    )
    worker_count = 32
    barrier = threading.Barrier(worker_count)
    result_lock = threading.Lock()
    successes = 0
    failures: list[Exception] = []

    def consume_once() -> None:
        nonlocal successes
        barrier.wait()
        try:
            dispatch_plan.consume("Alpha", task)
        except Exception as exc:
            with result_lock:
                failures.append(exc)
        else:
            with result_lock:
                successes += 1

    workers = [threading.Thread(target=consume_once) for _ in range(worker_count)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    assert not any(worker.is_alive() for worker in workers)
    assert successes == 1
    assert len(failures) == worker_count - 1
    assert all(isinstance(exc, ContractValidationError) for exc in failures)


def test_authorization_binding_identity_changes_with_any_constituent() -> None:
    first = normal_runtime._normal_binding_set_id(
        "policy",
        ({"seat": "Alpha", "policy_id": "policy-a"},),
    )
    changed = normal_runtime._normal_binding_set_id(
        "policy",
        ({"seat": "Alpha", "policy_id": "policy-b"},),
    )

    assert first != changed


def test_each_terminal_lost_slot_keeps_only_its_own_first_provider() -> None:
    losses = normal_runtime._terminal_lost_voices((
        {
            "phase": "initial_response",
            "failed_slots": [0, 1],
            "first_failed_providers": ["worker_alpha", "worker_beta"],
            "voice_lost_slots": [0, 1],
        },
    ))

    assert losses == (
        {
            "phase": "initial_response",
            "slot_index": 0,
            "first_failed_providers": ["worker_alpha"],
        },
        {
            "phase": "initial_response",
            "slot_index": 1,
            "first_failed_providers": ["worker_beta"],
        },
    )


def test_debug_predispatch_environment_is_rejected_before_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCRATES_DEBUG_PREDISPATCH", "1")

    with pytest.raises(NormalIntegrityError, match="debug output"):
        prepare(
            "Debug output must stay disabled",
            standing_cap_usd="1000",
            run_id="normal-debug-refusal",
        )


def test_unknown_lab_seat_environment_cannot_break_normal_import() -> None:
    environment = os.environ.copy()
    environment["SOCRATES_COUNCIL_SEATS"] = "stale-unknown-lab-selection"
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from socrates.runtime import prepare; "
                "p=prepare('isolation', standing_cap_usd='1000', "
                "run_id='normal-invalid-env-proof'); "
                "print(','.join(s.model_id for s in p.call_plan.seats))"
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == (
        "openai/gpt-5-mini,google/gemini-3.7-flash,openai/gpt-4.1-mini"
    )


def test_preflight_exposes_full_canonical_retry_and_cost_flags() -> None:
    preflight = prepare(
        "Show the complete Normal plan",
        standing_cap_usd="1000",
        run_id="normal-plan-flags",
    )
    record = preflight.plan_record()

    assert record["full_canonical_council"] is True
    assert record["admitted_by_standing_cap"] is True
    assert record["prompt_budget_tokens"] == NORMAL_PROMPT_BUDGET_TOKENS
    assert record["call_plan"]["max_socratic_followups"] == 2
    assert record["call_plan"]["completed_socratic_cycles"] == 2
    assert record["call_plan"]["base_calls"] == 115
    assert record["call_plan"]["same_seat_retry_calls"] == 20
    assert record["call_plan"]["maximum_calls"] == 135
    assert record["call_plan"]["logical_agent_to_seat"] == {
        "agent_0": "Alpha",
        "agent_1": "Beta",
        "agent_2": "Gamma",
    }
    assert record["cost"]["maximum_picodollars"] == (
        record["cost"]["base_picodollars"]
        + record["cost"]["same_seat_retry_picodollars"]
    )


def test_high_level_execute_uses_real_canonical_three_seat_council_and_safe_artifact(
    tmp_path: Path,
) -> None:
    question = "How should confidence change when independent evidence conflicts?"
    preflight = prepare(
        question,
        standing_cap_usd="1000",
        run_id="normal-scripted-full-council",
    )
    factory = _ScriptedRuntimeFactory()

    result = _run(execute(
        preflight,
        confirmed=True,
        runtime_factory=factory,
        run_root=tmp_path / "runs",
    ))

    assert factory.calls == 1
    assert factory.runtime is not None
    assert isinstance(factory.runtime.ced, _CountingCanonicalCED)
    assert factory.runtime.ced.canonical_run_calls == 1
    adapters = factory.runtime.adapters
    assert len(adapters) == 3
    assert [adapter.normal_calls_consumed for adapter in adapters] == [
        len(adapter.seen_tasks) for adapter in adapters
    ]
    assert all(adapter.normal_calls_consumed > 0 for adapter in adapters)
    actual_calls = sum(adapter.normal_calls_consumed for adapter in adapters)
    assert 0 < actual_calls <= preflight.call_plan.base_call_count
    actual_dispatches = Counter(
        (adapter.alias, normal_runtime._task_dispatch_key(task))
        for adapter in adapters
        for task in adapter.seen_tasks
    )
    branch_dispatches = tuple(
        Counter(
            (call.seat_alias, normal_runtime._planned_dispatch_key(call))
            for call in branch.base_calls + branch.retry_calls
        )
        for branch in normal_runtime._normal_execution_branch_plans(
            preflight.session_id
        )
    )
    assert any(
        all(count <= branch[key] for key, count in actual_dispatches.items())
        for branch in branch_dispatches
    )
    assert result.accounting.calls_consumed == actual_calls
    assert result.maximum_calls == 135
    assert result.error_code is None
    assert result.artifact_path.exists()
    assert result.artifact_path.parent.name == preflight.run_id

    encoded = result.artifact_path.read_bytes()
    payload = json.loads(encoded)
    assert hashlib.sha256(encoded).hexdigest() == result.artifact_sha256
    assert set(payload) == _ARTIFACT_KEYS
    assert "question" not in payload
    assert payload["question_sha256"] == preflight.question_sha256
    assert payload["plan"]["maximum_calls"] == 135
    assert payload["logical_agent_to_seat"] == {
        "agent_0": "Alpha",
        "agent_1": "Beta",
        "agent_2": "Gamma",
    }
    assert len(payload["turns"]) == 3
    assert all(set(row) == _TURN_KEYS for row in payload["turns"])
    assert payload["task_log"]
    assert all(set(row) == _TASK_LOG_KEYS for row in payload["task_log"])
    assert {row["phase"] for row in payload["task_log"]} >= {
        "opening",
        "initial_response",
        "elenchus",
        "reflection",
        "reconstruction",
        "synthesis",
    }
    # End to end, in a result.json actually written to disk: the governing
    # audit carries the records an offline reader needs, and still carries no
    # quality-plane field.
    governing_audit = payload["governing"]["audit"]
    assert {
        "objections",
        "objection_verdicts",
        "deterministic_checks",
    } <= set(governing_audit)
    assert "quality_mean" not in governing_audit
    assert "legacy_epistemic_status" not in governing_audit

    artifact_text = encoded.decode("utf-8")
    assert "raw_text" not in artifact_text
    assert "debug_context" not in artifact_text
    assert "Authorization" not in artifact_text
    assert _RAW_SECRET not in artifact_text
    assert _DEBUG_SECRET not in artifact_text


def test_cli_yes_path_runs_real_execute_through_the_canonical_fake_council(
    tmp_path: Path,
) -> None:
    responses = iter(
        [
            "How should a difficult claim be examined?",
            "YES",
        ]
    )
    output: list[str] = []
    factory = _ScriptedRuntimeFactory()

    exit_code = normal_cli.main(
        [],
        input_fn=lambda _prompt: next(responses),
        output_fn=output.append,
        runtime_factory=factory,
        run_root=tmp_path / "cli-runs",
    )

    assert exit_code == 0
    assert factory.calls == 1
    assert factory.runtime is not None
    assert isinstance(factory.runtime.ced, _CountingCanonicalCED)
    assert factory.runtime.ced.canonical_run_calls == 1
    assert len(factory.runtime.adapters) == 3
    assert all(
        adapter.normal_calls_consumed > 0 for adapter in factory.runtime.adapters
    )
    rendered_output = "\n".join(output)
    assert "FULL council: YES" in rendered_output
    assert "[Governing release]" in rendered_output
    assert "SOCRATES:" in rendered_output
    assert f"Artifact: {tmp_path / 'cli-runs'}" in rendered_output


def test_normal_arbitrary_question_is_not_admitted_by_benchmark_bundle_loader() -> None:
    arbitrary_question = "ordinary_question_not_in_benchmarks"

    preflight = prepare(
        arbitrary_question,
        standing_cap_usd="1000",
        run_id="normal-not-a-benchmark",
    )
    assert preflight.question == arbitrary_question

    with pytest.raises(ContractValidationError, match="no pinned question bundle"):
        load_bundle_v1(arbitrary_question)


def test_public_preflight_validator_preserves_the_canonical_integrity_gate() -> None:
    preflight = prepare(
        "Validate this immutable plan.",
        standing_cap_usd="1000",
        run_id="normal-public-validation-seam",
    )
    assert validate_preflight(preflight) is None
    with pytest.raises(NormalIntegrityError):
        validate_preflight(
            preflight.__class__(
                **{
                    **preflight.__dict__,
                    "question_sha256": "0" * 64,
                }
            )
        )


def test_execute_runs_guard_before_runtime_construction_and_observer_only_around_ced(
    tmp_path: Path,
    monkeypatch,
) -> None:
    preflight = prepare(
        "Observe the same canonical session without changing it.",
        standing_cap_usd="1000",
        run_id="normal-observer-runtime-seams",
    )
    scripted = _ScriptedRuntimeFactory()
    order: list[str] = []

    def guard() -> None:
        order.append("guard")

    def factory(*args, **kwargs):
        assert order == ["guard"]
        order.append("runtime")
        return scripted(*args, **kwargs)

    original = _CountingCanonicalCED.run_registry_session

    async def observed_run(ced, *args, **kwargs):
        assert getattr(ced, "_normal_test_observer_active", False) is True
        order.append("canonical")
        return await original(ced, *args, **kwargs)

    monkeypatch.setattr(_CountingCanonicalCED, "run_registry_session", observed_run)

    @contextmanager
    def observer(ced):
        assert order == ["guard", "runtime"]
        order.append("observer.enter")
        ced._normal_test_observer_active = True
        try:
            yield
        finally:
            ced._normal_test_observer_active = False
            order.append("observer.exit")

    result = _run(
        execute(
            preflight,
            confirmed=True,
            runtime_factory=factory,
            run_root=tmp_path / "runs",
            pre_runtime_guard=guard,
            observer_factory=observer,
        )
    )

    assert result.error_code is None
    assert order == [
        "guard",
        "runtime",
        "observer.enter",
        "canonical",
        "observer.exit",
    ]


def test_execute_guard_failure_prevents_runtime_construction(tmp_path: Path) -> None:
    preflight = prepare(
        "Refuse stale authority before provider construction.",
        standing_cap_usd="1000",
        run_id="normal-stale-authority-guard",
    )
    calls = 0

    def forbidden_runtime(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("runtime construction must remain unreachable")

    def stale_guard() -> None:
        raise NormalAuthorizationError("stale test authority")

    result = _run(
        execute(
            preflight,
            confirmed=True,
            runtime_factory=forbidden_runtime,
            run_root=tmp_path / "runs",
            pre_runtime_guard=stale_guard,
        )
    )
    assert calls == 0
    assert result.error_code is not None


@pytest.mark.parametrize("persist_cancellation_result", (False, True))
def test_execute_cancellation_default_is_unchanged_and_browser_can_persist(
    tmp_path: Path,
    monkeypatch,
    persist_cancellation_result: bool,
) -> None:
    preflight = prepare(
        "Finalize canonical provenance if server shutdown cancels execution.",
        standing_cap_usd="1000",
        run_id=(
            "normal-cancelled-persisted"
            if persist_cancellation_result
            else "normal-cancelled-default"
        ),
    )
    factory = _ScriptedRuntimeFactory()

    async def exercise() -> None:
        entered = asyncio.Event()
        never = asyncio.Event()

        async def blocked_run(self, *_args, **_kwargs):
            entered.set()
            await never.wait()

        monkeypatch.setattr(
            _CountingCanonicalCED,
            "run_registry_session",
            blocked_run,
        )
        task = asyncio.create_task(
            execute(
                preflight,
                confirmed=True,
                runtime_factory=factory,
                run_root=tmp_path / "runs",
                persist_cancellation_result=persist_cancellation_result,
            )
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    _run(exercise())
    run_directory = tmp_path / "runs" / preflight.run_id
    assert (run_directory / "plan.json").is_file()
    artifact_path = run_directory / "result.json"
    assert artifact_path.is_file() is persist_cancellation_result
    if not persist_cancellation_result:
        return
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["status"] == "execution_error"
    assert artifact["error_code"]
    assert factory.runtime is not None
    assert all(
        adapter.normal_calls_consumed == 0
        for adapter in factory.runtime.adapters
    )


def test_governing_audit_projection_keeps_objection_and_check_records() -> None:
    """The projector must not drop the three records CED already built.

    A frozen run reported two unresolved objection ids and one unresolved claim,
    and carried nothing saying which claim either objection targeted, what
    verdict ended them there, or whether the deterministic checker applied at
    all. `_apply_governing_release` built every one of those fields and the
    allow-list here dropped them, so the only way to ask why a release was
    unresolved was to re-read the source and guess. Offline is the only way a
    frozen run is ever audited.

    Scope: this covers objection and deterministic-check records only. An
    unresolved id may also name an evidence, verification or contradiction
    record, and none of those are projected yet.
    """
    objections = [
        {
            "objection_id": "obj_1",
            "target_claim_id": "claim_a",
            "target_section": "core_answer",
            "scope": "justification",
            "targeting_provenance": "declared_identifier",
            "state": "inconclusive",
            "raised_by": "worker_alpha",
            "raised_by_model_id": "vendor/model-a",
        },
    ]
    final = SimpleNamespace(
        audit_summary={
            "governing_release": {
                "available": True,
                "release_decision": "release_unresolved",
                "governing_epistemic_status": "unresolved",
                "claim_states": {"claim_a": "unresolved"},
                "basis_record_ids": [],
                "unresolved_record_ids": ["obj_1"],
                "objections": objections,
                "objection_verdicts": {"obj_1": "uncorroborated"},
                "deterministic_checks": {
                    "applicable": False,
                    "reason": "no_roster",
                },
                "blocked_reason": "",
                "frozen_digest": "0" * 64,
                # Built by the projection and deliberately not carried: the
                # quality plane governs nothing and must not travel as if it did.
                "quality_mean": 7.61,
                "legacy_epistemic_status": "well_supported",
            },
        },
    )
    render = NormalRenderResult(
        outcome="release_unresolved",
        release_decision="release_unresolved",
        governing_epistemic_status="unresolved",
        public_answer="Answer",
        notice="WARNING",
        candidate_authorized=True,
        candidate="Candidate",
    )

    audit = normal_runtime._governing_record(final, render)["audit"]

    assert audit["objections"] == objections
    assert audit["objection_verdicts"] == {"obj_1": "uncorroborated"}
    assert audit["deterministic_checks"]["reason"] == "no_roster"
    # An unresolved id that names an objection now resolves to a record carrying
    # its target and to the verdict that left it there. Ids naming evidence,
    # verification or contradiction records still resolve to nothing, so this is
    # deliberately not asserted over the whole list.
    projected = {row["objection_id"] for row in audit["objections"]}
    assert "obj_1" in audit["unresolved_record_ids"]
    assert "obj_1" in projected
    assert "obj_1" in audit["objection_verdicts"]
    # The quality plane still does not travel with the governing record.
    assert "quality_mean" not in audit
    assert "legacy_epistemic_status" not in audit


def test_turn_projection_keeps_the_codes_that_say_why_a_seat_failed() -> None:
    """`provider_structured_output_valid: false` alone names no cause.

    Across two live runs one served model was 0/11 on `socratic_question` and
    `objection_verification` and 46/46 on every other task kind — deterministic,
    not flaky — and the artifact carried nothing to say what failed. The adapter
    already computes both codes; only this projection dropped them.
    """
    row = {
        "turn_id": "t1",
        "provider_structured_output_valid": False,
        "provider_structured_output_error": "structured_output:ValidationError:literal_error=1",
        "ced_move_accepted": False,
        "ced_rejection_reason": "ced_schema_error:validation_failed",
        "unexpected_field": "must not be projected",
    }
    projected = normal_runtime._project_turn_row(row)

    assert projected["provider_structured_output_error"] == (
        "structured_output:ValidationError:literal_error=1"
    )
    assert projected["ced_rejection_reason"] == "ced_schema_error:validation_failed"
    assert "unexpected_field" not in projected
    # A row without them projects None rather than raising.
    assert normal_runtime._project_turn_row(
        {"turn_id": "t2"}
    )["provider_structured_output_error"] is None


def test_a_const_violation_is_reported_as_literal_error() -> None:
    """The retained code has to discriminate, not merely exist.

    `socratic_question` pins `introduces_new_proposition` to `const: false`, and
    that class of constraint — a non-string const — is the one structural
    feature present in both failing schemas and absent from every passing one.
    A seat that returns `true` there must surface as `literal_error`, so the
    next live run answers the question from the artifact instead of a re-read
    of the source.
    """
    task = AgentTask(
        task_id="t",
        session_id="s",
        agent_id="a",
        role=AgentRole.SOCRATES,
        phase=DialogPhase.ELENCHUS,
        question="q",
        task_kind=TaskKind.SOCRATIC_QUESTION,
    )
    payload = {
        "content": {
            "question": "What exactly grounds the claim that the rule applies here?",
            "operator": "request_grounds",
            "grounded_in": [{"ref_type": "commitment", "ref_id": "cmt_1"}],
            "introduces_new_proposition": True,      # schema pins this to False
            "inquiry_state": "continue_inquiry",
            "aporia": None,
            "epistemic_marker": "open_uncertainty",
        },
        "confidence": 0.5,
    }
    with pytest.raises(Exception) as caught:
        validate_ced_structured_output_v1(task, json.dumps(payload))
    code = safe_public_exception_code_v1(caught.value, context="structured_output")

    assert code.startswith("structured_output:ValidationError:")
    assert "literal_error" in code
    # Closed vocabulary: no provider prose, no field paths, no input values.
    assert "introduces_new_proposition" not in code
    assert "True" not in code
