"""Deterministic offline provider profile used to acquire Phase 8 captures.

The fixtures emit raw bytes only.  They do not create observation records,
successors, or expected results; the ordinary canonical CED path dispatches
them exactly as it dispatches any other registered adapter.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Optional, Tuple

from .agent import SocraticAgent
from .ced import CEDOrchestrator
from .models import AgentState, AgentTask, SessionState, TaskKind
from .provider_registry import CouncilProviderRegistry, ScriptedMockProvider
from .providers import FakeProvider


CANONICAL_RECORDING_AGENT_IDS = tuple(
    f"phase8-recorded-agent-{index}" for index in range(4)
)
CANONICAL_RECORDING_PROVIDER_MODELS = (
    ("phase8-recorded-seat-0", "phase8-recorded-model/0"),
    ("phase8-recorded-seat-1", "phase8-recorded-model/1"),
)

CanonicalRawObservationProducer = Callable[[AgentTask, AgentState], Awaitable[str]]


class CanonicalSuccessorRecordingProvider(ScriptedMockProvider):
    """Committed fake adapter that emits one configured raw observation."""

    def __init__(
        self,
        provider_id: str,
        *,
        model_id: str,
        recorded_raw_text: str,
        raw_observation_producer: Optional[CanonicalRawObservationProducer] = None,
    ) -> None:
        super().__init__(provider_id, model_id=model_id)
        self.recorded_raw_text = recorded_raw_text
        self.raw_observation_producer = raw_observation_producer
        self.generate_calls = 0

    async def generate_agent_move(self, task, agent_state):
        self.generate_calls += 1
        return await super().generate_agent_move(task, agent_state)

    async def _produce_raw_text(
        self,
        task: AgentTask,
        agent_state: AgentState,
    ) -> str:
        if task.task_kind is not TaskKind.SOCRATIC_QUESTION:
            return await super()._produce_raw_text(task, agent_state)
        if self.raw_observation_producer is not None:
            return await self.raw_observation_producer(task, agent_state)
        return self.recorded_raw_text


def build_canonical_recording_root(
    *,
    question: str,
    raw_text: str,
    session_id: str,
    raw_observation_producer: Optional[CanonicalRawObservationProducer] = None,
) -> Tuple[
    CEDOrchestrator,
    SessionState,
    Tuple[CanonicalSuccessorRecordingProvider, ...],
]:
    """Build the fixed offline root used for capture and replay reconstruction."""

    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    adapters = tuple(
        CanonicalSuccessorRecordingProvider(
            provider_id,
            model_id=model_id,
            recorded_raw_text=raw_text,
            raw_observation_producer=raw_observation_producer,
        )
        for provider_id, model_id in CANONICAL_RECORDING_PROVIDER_MODELS
    )
    for adapter in adapters:
        registry.register(adapter)
    ced = CEDOrchestrator(
        [SocraticAgent(agent_id, provider) for agent_id in CANONICAL_RECORDING_AGENT_IDS],
        provider,
        registry=registry,
        phase_retry=False,
    )
    state = ced.create_session(question, session_id=session_id)
    return ced, state, adapters


__all__ = [
    "CANONICAL_RECORDING_AGENT_IDS",
    "CANONICAL_RECORDING_PROVIDER_MODELS",
    "CanonicalRawObservationProducer",
    "CanonicalSuccessorRecordingProvider",
    "build_canonical_recording_root",
]
