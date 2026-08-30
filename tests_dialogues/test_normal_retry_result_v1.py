"""Offline Normal-boundary proofs for same-seat retry and lost-voice output.

These tests deliberately use the real canonical registry session.  Only the
provider transport is replaced by three model-distinct scripted mocks, so the
retry records, move acceptance, quorum, final projection, and write-once result
artifact all come from the production-shaped Normal path without credentials or
network access.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, MutableMapping, Tuple, Type

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator, REGISTRY_SESSION_PHASES
from backend.dialogues.models import (
    DialogPhase,
    ProviderResponse,
    ProviderStatus,
    ShadowScoringMode,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    FakeProvider,
    ScriptedMockProvider,
)
from socrates.runtime import NormalRuntime, execute, prepare


QUESTION = "How should a city decide whether to pedestrianize its center?"


class _SelectiveInitialFailureProvider(ScriptedMockProvider):
    """Record every dispatch and fail selected initial-response attempts."""

    MODEL_ID = "offline/abstract"

    def __init__(
        self,
        provider_id: str,
        *,
        failed_attempts: FrozenSet[int] = frozenset(),
    ) -> None:
        super().__init__(provider_id=provider_id, model_id=self.MODEL_ID)
        self.failed_attempts = failed_attempts
        self.dispatches: List[Dict[str, Any]] = []

    async def generate_agent_move(self, task, agent_state) -> ProviderResponse:
        should_fail = (
            task.task_kind is TaskKind.INITIAL_RESPONSE
            and task.attempt_index in self.failed_attempts
        )
        self.dispatches.append(
            {
                "provider_id": self.provider_id,
                "model_id": self.model_id,
                "agent_id": task.agent_id,
                "task_id": task.task_id,
                "task_kind": task.task_kind,
                "phase": task.phase,
                "slot_index": task.slot_index,
                "attempt_index": task.attempt_index,
                "failed": should_fail,
            }
        )
        if should_fail:
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.TIMEOUT,
                raw_text="",
                parsed_move=None,
                error_message="offline deliberate silence",
            )
        return await super().generate_agent_move(task, agent_state)


class _AlphaProvider(_SelectiveInitialFailureProvider):
    MODEL_ID = "offline/model-alpha"


class _BetaProvider(_SelectiveInitialFailureProvider):
    MODEL_ID = "offline/model-beta"


class _GammaProvider(_SelectiveInitialFailureProvider):
    MODEL_ID = "offline/model-gamma"


_PROVIDER_CLASSES: Tuple[Type[_SelectiveInitialFailureProvider], ...] = (
    _AlphaProvider,
    _BetaProvider,
    _GammaProvider,
)


def _runtime_factory(
    *,
    failing_alias: str,
    failed_attempts: FrozenSet[int],
    capture: MutableMapping[str, Any],
):
    def factory(preflight, _run_directory: Path, _progress) -> NormalRuntime:
        registry = CouncilProviderRegistry()
        adapters = []
        for provider_type, seat in zip(
            _PROVIDER_CLASSES, preflight.call_plan.seats, strict=True
        ):
            adapter = provider_type(
                seat.provider_id,
                failed_attempts=(
                    failed_attempts if seat.alias == failing_alias else frozenset()
                ),
            )
            registry.register(adapter)
            adapters.append(adapter)

        fake = FakeProvider()
        agents = [
            SocraticAgent(agent_id, fake)
            for agent_id, _seat_alias in preflight.call_plan.agent_to_seat
        ]
        ced = CEDOrchestrator(
            agents,
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
        runtime = NormalRuntime(ced=ced, adapters=tuple(adapters))
        capture["runtime"] = runtime
        return runtime

    return factory


def _assert_exact_normal_runtime(runtime: NormalRuntime) -> None:
    ced = runtime.ced
    assert len(ced.agents) == 3
    assert len(runtime.adapters) == 3
    assert len({type(adapter) for adapter in runtime.adapters}) == 3
    assert all(
        isinstance(adapter, ScriptedMockProvider) for adapter in runtime.adapters
    )
    assert len({adapter.model_id for adapter in runtime.adapters}) == 3
    assert ced.shadow_scoring_mode is ShadowScoringMode.ALL_PHASES
    assert ced.assembly_fallback is False
    assert ced.phase_retry is True
    assert ced.max_socratic_followups == 2
    assert ced.ratification_repair == "block"
    assert ced.tree_expansions == 0
    assert ced.ai_learning is False
    assert ced.mid_round_objection_rulings_v1 is True


def _initial_dispatches(adapter: _SelectiveInitialFailureProvider):
    return [
        row
        for row in adapter.dispatches
        if row["task_kind"] is TaskKind.INITIAL_RESPONSE
    ]


def _initial_task_log(state, *, agent_id: str):
    return [
        row
        for row in state.task_log
        if row.agent_id == agent_id
        and row.task_kind is TaskKind.INITIAL_RESPONSE
    ]


def _artifact(result) -> Dict[str, Any]:
    return json.loads(result.artifact_path.read_text(encoding="utf-8"))


def test_normal_retry_recovers_at_the_same_model_distinct_seat(tmp_path):
    preflight = prepare(
        QUESTION,
        standing_cap_usd="100",
        run_id="normal_retry_recovers_v1",
    )
    capture: Dict[str, Any] = {}

    result = asyncio.run(
        execute(
            preflight,
            confirmed=True,
            runtime_factory=_runtime_factory(
                failing_alias="Beta",
                failed_attempts=frozenset({0}),
                capture=capture,
            ),
            run_root=tmp_path,
        )
    )

    runtime = capture["runtime"]
    _assert_exact_normal_runtime(runtime)
    assert result.error_code is None
    assert result.actual_same_seat_retries == 1
    assert result.terminal_lost_voices == ()

    beta = runtime.adapters[1]
    dispatches = _initial_dispatches(beta)
    assert [row["attempt_index"] for row in dispatches] == [0, 1]
    assert [row["failed"] for row in dispatches] == [True, False]
    assert {row["provider_id"] for row in dispatches} == {"worker_beta"}
    assert {row["model_id"] for row in dispatches} == {"offline/model-beta"}
    assert len({row["agent_id"] for row in dispatches}) == 1
    retried_agent = dispatches[0]["agent_id"]
    assert dict(preflight.call_plan.agent_to_seat)[retried_agent] == "Beta"

    state = runtime.ced.get_session(preflight.session_id)
    task_rows = _initial_task_log(state, agent_id=retried_agent)
    assert [row.attempt_index for row in task_rows] == [0, 1]
    assert task_rows[0].provider_id == task_rows[1].provider_id == "worker_beta"
    assert task_rows[0].provider_status is ProviderStatus.TIMEOUT
    assert task_rows[0].move_id is None
    assert task_rows[1].provider_status is ProviderStatus.OK
    assert task_rows[1].move_id is not None
    accepted = [
        move
        for move in state.moves
        if move.agent_id == retried_agent
        and move.task_kind is TaskKind.INITIAL_RESPONSE
    ]
    assert len(accepted) == 1
    assert accepted[0].attempt_index == 1

    payload = _artifact(result)
    assert payload["actual_same_seat_retries"] == 1
    assert payload["terminal_lost_voices"] == []
    retry_record = next(
        row for row in payload["phase_retries"]
        if row["phase"] == DialogPhase.INITIAL_RESPONSE.value
    )
    assert retry_record["reasked_same_seat_slots"] == [dispatches[0]["slot_index"]]
    assert retry_record["retry_ok_providers"] == ["worker_beta"]
    assert retry_record["voice_lost_slots"] == []


def test_normal_second_failure_is_one_visible_terminal_lost_voice(tmp_path):
    preflight = prepare(
        QUESTION,
        standing_cap_usd="100",
        run_id="normal_retry_lost_voice_v1",
    )
    capture: Dict[str, Any] = {}

    result = asyncio.run(
        execute(
            preflight,
            confirmed=True,
            runtime_factory=_runtime_factory(
                failing_alias="Beta",
                failed_attempts=frozenset({0, 1}),
                capture=capture,
            ),
            run_root=tmp_path,
        )
    )

    runtime = capture["runtime"]
    _assert_exact_normal_runtime(runtime)
    assert result.error_code is None
    assert result.actual_same_seat_retries == 1
    assert len(result.terminal_lost_voices) == 1

    beta = runtime.adapters[1]
    dispatches = _initial_dispatches(beta)
    assert [row["attempt_index"] for row in dispatches] == [0, 1]
    assert all(row["failed"] for row in dispatches)
    assert {row["provider_id"] for row in dispatches} == {"worker_beta"}
    assert {row["model_id"] for row in dispatches} == {"offline/model-beta"}
    assert len({row["agent_id"] for row in dispatches}) == 1
    lost_agent = dispatches[0]["agent_id"]
    assert dict(preflight.call_plan.agent_to_seat)[lost_agent] == "Beta"

    state = runtime.ced.get_session(preflight.session_id)
    assert {move.phase for move in state.moves} == set(REGISTRY_SESSION_PHASES)
    task_rows = _initial_task_log(state, agent_id=lost_agent)
    assert [row.attempt_index for row in task_rows] == [0, 1]
    assert all(row.provider_id == "worker_beta" for row in task_rows)
    assert all(row.provider_status is ProviderStatus.TIMEOUT for row in task_rows)
    assert all(row.move_id is None for row in task_rows)
    assert not any(
        move.agent_id == lost_agent
        and move.task_kind is TaskKind.INITIAL_RESPONSE
        for move in state.moves
    ), "failed provider responses must not fabricate an initial-response move"

    loss = result.terminal_lost_voices[0]
    assert loss["phase"] == DialogPhase.INITIAL_RESPONSE.value
    assert loss["slot_index"] == dispatches[0]["slot_index"]
    assert loss["first_failed_providers"] == ["worker_beta"]

    payload = _artifact(result)
    assert payload["actual_same_seat_retries"] == 1
    assert payload["terminal_lost_voices"] == [loss]
    retry_record = next(
        row for row in payload["phase_retries"]
        if row["phase"] == DialogPhase.INITIAL_RESPONSE.value
    )
    assert retry_record["voice_lost_slots"] == [loss["slot_index"]]
    assert retry_record["quorum_held_but_a_voice_was_lost"] is True
    artifact_failures = [
        row
        for row in payload["task_log"]
        if row["agent_id"] == lost_agent
        and row["task_kind"] == TaskKind.INITIAL_RESPONSE.value
    ]
    assert [row["attempt_index"] for row in artifact_failures] == [0, 1]
    assert all(row["move_id"] is None for row in artifact_failures)
    assert all(row["provider_status"] == ProviderStatus.TIMEOUT.value
               for row in artifact_failures)
