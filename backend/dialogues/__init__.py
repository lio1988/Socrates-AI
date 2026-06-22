"""
Socratic Dialogues Orchestration System (V1)

Public surface:
  - CEDOrchestrator  — drives the full pipeline
  - SocraticAgent    — stateless reasoning agent
  - FakeProvider     — deterministic provider for testing
  - ProviderRegistry — holds the four provider slots
  - All Pydantic models from .models
"""

from .models import (
    AgentRole,
    AgentTask,
    AgentState,
    AgentMove,
    DialogPhase,
    EpistemicMarker,
    EpistemicStatus,
    PenaltyFlag,
    ProviderStatus,
    SectionName,
    RatificationDecision,
    ObjectionSeverity,
    ScoreBreakdown,
    MicroScore,
    SectionScore,
    DraftScorecard,
    SectionDraft,
    AssembledSection,
    AssembledAnswer,
    RatificationVote,
    FinalResponse,
    SessionState,
    SECTION_ORDER,
    SCORE_WEIGHTS,
    MAX_RATIFICATION_ROUNDS,
)
from .providers import (
    LLMProvider,
    FakeProvider,
    AnthropicProvider,
    OpenAIProvider,
    LocalProvider,
    ProviderRegistry,
)
from .agent import SocraticAgent, CORE_AGENT_PROMPT
from .role_assignment import assign_primary_roles, socrates_for_session
from .ced import CEDOrchestrator

__all__ = [
    "AgentRole", "AgentTask", "AgentState", "AgentMove",
    "DialogPhase", "EpistemicMarker", "EpistemicStatus",
    "PenaltyFlag", "ProviderStatus", "SectionName",
    "RatificationDecision", "ObjectionSeverity",
    "ScoreBreakdown", "MicroScore", "SectionScore", "DraftScorecard",
    "SectionDraft", "AssembledSection", "AssembledAnswer",
    "RatificationVote", "FinalResponse", "SessionState",
    "SECTION_ORDER", "SCORE_WEIGHTS", "MAX_RATIFICATION_ROUNDS",
    "LLMProvider", "FakeProvider", "AnthropicProvider",
    "OpenAIProvider", "LocalProvider", "ProviderRegistry",
    "SocraticAgent", "CORE_AGENT_PROMPT",
    "assign_primary_roles", "socrates_for_session",
    "CEDOrchestrator",
    "run_demo", "build_demo_orchestrator",
]


def __getattr__(name: str):
    """
    Lazily expose the demo helpers without importing the demo module at package
    import time. This keeps `from backend.dialogues import run_demo` working while
    avoiding the double-import RuntimeWarning when running
    `python -m backend.dialogues.demo`.
    """
    if name in ("run_demo", "build_demo_orchestrator"):
        from . import demo
        return getattr(demo, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
