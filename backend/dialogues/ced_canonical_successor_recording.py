"""Deterministic offline acquisition profile for the frozen Phase 8 corpus.

This module is test/evaluation infrastructure only.  It creates an ordinary
CED opening root whose fake adapters return one exact pre-recorded raw output
when the authoritative reference path dispatches them.  The successor
environment never imports this module and never dispatches these adapters.
"""

from __future__ import annotations

from typing import Optional, Tuple

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


class CanonicalSuccessorRecordingProvider(ScriptedMockProvider):
    """Fake canonical adapter that emits one already-frozen raw observation."""

    def __init__(
        self,
        provider_id: str,
        *,
        model_id: str,
        recorded_raw_text: str,
    ) -> None:
        super().__init__(provider_id, model_id=model_id)
        self.recorded_raw_text = recorded_raw_text
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
        return self.recorded_raw_text


def build_canonical_recording_root(
    *,
    question: str,
    raw_text: str,
    session_id: str,
) -> Tuple[
    CEDOrchestrator,
    SessionState,
    Tuple[CanonicalSuccessorRecordingProvider, ...],
]:
    """Build the exact fixed root used for capture and later parity replay."""

    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    adapters = tuple(
        CanonicalSuccessorRecordingProvider(
            provider_id,
            model_id=model_id,
            recorded_raw_text=raw_text,
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
    "CanonicalSuccessorRecordingProvider",
    "build_canonical_recording_root",
]
