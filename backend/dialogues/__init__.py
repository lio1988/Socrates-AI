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
    TaskKind,
    TaskLogEntry,
    DialogPhase,
    EpistemicMarker,
    EpistemicStatus,
    PenaltyFlag,
    ProviderStatus,
    LeaderboardStatus,
    SyncGateStatus,
    ShadowScoringMode,
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
    FinalSynthesisMode,
    CouncilVerdict,
    CouncilRatificationStatus,
    RatificationVerdict,
    CouncilRatification,
    ShadowScoreHarvest,
    EpistemicLeaderboard,
    ProviderResponse,
    CouncilRoundResult,
    FinalResponse,
    SessionState,
    SECTION_ORDER,
    SCORE_WEIGHTS,
    MAX_RATIFICATION_ROUNDS,
    MAX_LEADERBOARD_HARVEST_TIMEOUT,
    LEADERBOARD_INTERPRETATION_WARNING,
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
from .topic import Topic, classify_topic
from .provider_registry import (
    CouncilProviderRegistry,
    LLMProviderAdapter,
    BaseProviderAdapter,
    parse_and_validate_move,
    is_placeholder_key,
    AlwaysOKProvider,
    TimeoutProvider,
    InvalidJSONProvider,
    SchemaErrorProvider,
    RateLimitedProvider,
    MissingKeyProvider,
    ScriptedMockProvider,
    TimeoutScriptedProvider,
    CaveatRatifierProvider,
    BlockingObjectionProvider,
    MINIMUM_PROVIDERS,
    QUORUM_FOR_ASSEMBLY,
    PROVIDER_TIMEOUT_SECONDS,
)
from .ced import CEDOrchestrator
from .conversation import (
    ConversationManager,
    ConversationSession,
    ConversationTurn,
    PublicEpistemicMemory,
    HiddenCedTrace,
    ChatResponse,
    build_full_brief,
    save_conversation_json,
    load_conversation_json,
)
from .live_providers import (
    LiveAnthropicAdapter,
    build_council,
    build_council_registry,
)
from .nvidia_nim_provider import (
    LiveNvidiaNIMAdapter,
    NvidiaNIMRequest,
    CannedNvidiaNIMTransport,
    nvidia_chat_envelope,
)
from .learning_foundation import (
    SocratesPrinciple,
    SocratesConstitution,
    TrainingEligibility,
    LearningTrace,
    LearningDataset,
    LearningUse,
    LearningSignalKind,
    PreferenceExample,
    EvalExample,
    EvalVerifierType,
    assess_training_eligibility,
    build_preference_example,
    sanitize_public_payload,
    jsonl,
)
from .self_improvement import (
    SeatHealthTracker,
    EpistemicLessonStore,
    Lesson,
    ProcessLesson,
    TopicSkillTracker,
    CalibrationLedger,
    extract_lesson,
    distill_lesson_with_council,
    review_process_with_council,
    rank_lessons_with_council,
)
from .living_system import (
    OpenQuestionLedger,
    OpenQuestion,
    consolidate_lessons,
    compute_vitals,
    run_inquiry_cycle,
)

__all__ = [
    "AgentRole", "AgentTask", "AgentState", "AgentMove",
    "TaskKind", "TaskLogEntry",
    "DialogPhase", "EpistemicMarker", "EpistemicStatus",
    "PenaltyFlag", "ProviderStatus", "LeaderboardStatus", "SyncGateStatus",
    "ShadowScoringMode",
    "SectionName", "RatificationDecision", "ObjectionSeverity",
    "ScoreBreakdown", "MicroScore", "SectionScore", "DraftScorecard",
    "SectionDraft", "AssembledSection", "AssembledAnswer",
    "RatificationVote", "ShadowScoreHarvest", "EpistemicLeaderboard",
    "FinalSynthesisMode", "CouncilVerdict", "CouncilRatificationStatus",
    "RatificationVerdict", "CouncilRatification",
    "ProviderResponse", "CouncilRoundResult",
    "CouncilProviderRegistry", "LLMProviderAdapter", "BaseProviderAdapter",
    "parse_and_validate_move", "is_placeholder_key",
    "AlwaysOKProvider", "TimeoutProvider", "InvalidJSONProvider",
    "SchemaErrorProvider", "RateLimitedProvider", "MissingKeyProvider",
    "ScriptedMockProvider", "TimeoutScriptedProvider",
    "CaveatRatifierProvider", "BlockingObjectionProvider",
    "MINIMUM_PROVIDERS", "QUORUM_FOR_ASSEMBLY", "PROVIDER_TIMEOUT_SECONDS",
    "FinalResponse", "SessionState",
    "SECTION_ORDER", "SCORE_WEIGHTS", "MAX_RATIFICATION_ROUNDS",
    "MAX_LEADERBOARD_HARVEST_TIMEOUT", "LEADERBOARD_INTERPRETATION_WARNING",
    "LLMProvider", "FakeProvider", "AnthropicProvider",
    "OpenAIProvider", "LocalProvider", "ProviderRegistry",
    "SocraticAgent", "CORE_AGENT_PROMPT",
    "assign_primary_roles", "socrates_for_session",
    "Topic", "classify_topic",
    "CEDOrchestrator",
    "ConversationManager", "ConversationSession", "ConversationTurn",
    "PublicEpistemicMemory", "HiddenCedTrace", "ChatResponse",
    "build_full_brief", "save_conversation_json", "load_conversation_json",
    "LiveAnthropicAdapter", "LiveNvidiaNIMAdapter", "NvidiaNIMRequest",
    "CannedNvidiaNIMTransport", "nvidia_chat_envelope",
    "SocratesPrinciple", "SocratesConstitution", "TrainingEligibility",
    "LearningTrace", "LearningDataset", "LearningUse", "LearningSignalKind",
    "PreferenceExample", "EvalExample", "EvalVerifierType",
    "assess_training_eligibility", "build_preference_example",
    "sanitize_public_payload", "jsonl",
    "build_council", "build_council_registry",
    "SeatHealthTracker", "EpistemicLessonStore", "Lesson", "ProcessLesson",
    "TopicSkillTracker", "CalibrationLedger",
    "extract_lesson", "distill_lesson_with_council", "review_process_with_council",
    "rank_lessons_with_council",
    "OpenQuestionLedger", "OpenQuestion", "consolidate_lessons", "compute_vitals",
    "run_inquiry_cycle",
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
