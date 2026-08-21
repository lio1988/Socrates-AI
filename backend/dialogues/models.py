"""
Socratic Dialogues Orchestration System — Pydantic Models (V1)

All session state is CED-owned. Agents never hold a reference to SessionState
or to any scorecard. They receive an AgentTask and return an AgentMove — that
is the full extent of their I/O contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces the deprecated naive utcnow)."""
    return datetime.now(timezone.utc)


# ── Enumerations ──────────────────────────────────────────────────────────────

class AgentRole(str, Enum):
    SOCRATES               = "socrates"
    ELENCHUS_CRITIC        = "elenchus_critic"
    EMPIRICIST             = "empiricist"
    MAIEUTIC_RECONSTRUCTOR = "maieutic_reconstructor"
    SYNTHESIZER            = "synthesizer"
    REFLECTOR              = "reflector"
    FINAL_EVALUATOR        = "final_evaluator"


class DialogPhase(str, Enum):
    OPENING          = "opening"
    INITIAL_RESPONSE = "initial_response"
    ELENCHUS         = "elenchus"
    REFLECTION       = "reflection"
    RECONSTRUCTION   = "reconstruction"
    SYNTHESIS        = "synthesis"
    RATIFICATION     = "ratification"
    COMPLETE         = "complete"


class EpistemicMarker(str, Enum):
    ESTABLISHED_FACT    = "established_fact"
    LOGICAL_INFERENCE   = "logical_inference"
    REASONABLE_HYPOTHESIS = "reasonable_hypothesis"
    OPEN_UNCERTAINTY    = "open_uncertainty"
    UNSUBSTANTIATED_CLAIM = "unsubstantiated_claim"


class EpistemicStatus(str, Enum):
    WELL_SUPPORTED = "well_supported"
    CONTESTED      = "contested"
    UNCERTAIN      = "uncertain"
    SPECULATIVE    = "speculative"


# ── Phase 4: scoring / section / ratification enums ───────────────────────────

class PenaltyFlag(str, Enum):
    UNSUPPORTED_CLAIM  = "unsupported_claim"
    OVERCONFIDENCE     = "overconfidence"
    VAGUE              = "vague"
    LOGICAL_GAP        = "logical_gap"
    IRRELEVANT         = "irrelevant"
    RHETORICAL_FLUFF   = "rhetorical_fluff"
    UNFAIR_ATTACK      = "unfair_attack"
    MISSED_UNCERTAINTY = "missed_uncertainty"
    SCHEMA_VIOLATION   = "schema_violation"


class ProviderStatus(str, Enum):
    OK           = "ok"
    DEGRADED     = "degraded"
    FALLBACK     = "fallback"
    ERROR        = "error"
    TIMEOUT      = "timeout"
    UNAVAILABLE  = "unavailable"
    # Phase 8A provider-adapter statuses
    MISSING_KEY  = "missing_key"
    INVALID_JSON = "invalid_json"
    SCHEMA_ERROR = "schema_error"
    RATE_LIMITED = "rate_limited"
    DISABLED     = "disabled"


# ── Phase 7: epistemic sync gate / leaderboard status ─────────────────────────

class LeaderboardStatus(str, Enum):
    COMPLETE    = "complete"
    PARTIAL     = "partial"
    UNAVAILABLE = "unavailable"
    DISABLED    = "disabled"
    FAILED      = "failed"        # peer scoring ran but produced no valid scores


class SyncGateStatus(str, Enum):
    COMPLETE    = "complete"
    PARTIAL     = "partial"
    TIMEOUT     = "timeout"
    UNAVAILABLE = "unavailable"
    DISABLED    = "disabled"
    FAILED      = "failed"        # peer scoring failed (no valid peer scores)


class ShadowScoringMode(str, Enum):
    """How much shadow scoring to run (cost control for real providers later)."""
    ALL_PHASES     = "all_phases"      # score every phase in SCORED_PHASES (default)
    SYNTHESIS_ONLY = "synthesis_only"  # score only the synthesis drafts
    SAMPLED        = "sampled"         # deterministic reduced: opening + synthesis
    OFF            = "off"             # no shadow scoring; leaderboard = disabled


class SectionName(str, Enum):
    CORE_ANSWER         = "core_answer"
    CRUCIAL_STRESS_TEST = "crucial_stress_test"
    BLIND_SPOTS         = "blind_spots"
    NUANCE              = "nuance"
    FINAL_VERDICT       = "final_verdict"


class RatificationDecision(str, Enum):
    APPROVE            = "approve"
    BLOCKING_OBJECTION = "blocking_objection"


class ObjectionSeverity(str, Enum):
    NONE     = "none"
    MINOR    = "minor"
    MAJOR    = "major"
    CRITICAL = "critical"


# Canonical section order used for assembly + display.
SECTION_ORDER: List[SectionName] = [
    SectionName.CORE_ANSWER,
    SectionName.CRUCIAL_STRESS_TEST,
    SectionName.BLIND_SPOTS,
    SectionName.NUANCE,
    SectionName.FINAL_VERDICT,
]

# Phase 4 ratification policy.
MAX_RATIFICATION_ROUNDS = 2

# Phase 7 epistemic sync gate policy.
MAX_LEADERBOARD_HARVEST_TIMEOUT = 4.0
LEADERBOARD_INTERPRETATION_WARNING = "Scores are peer-evaluation signals, not proof of truth."


# ── Task / Move ───────────────────────────────────────────────────────────────

class TaskKind(str, Enum):
    """
    Explicit, deterministic identity of an agent task within a phase. Used (with
    slot_index / attempt_index) to derive reproducible move ids that do NOT
    depend on runtime completion order.
    """
    SOCRATIC_QUESTION       = "socratic_question"
    INITIAL_RESPONSE        = "initial_response"
    ELENCHUS_OBJECTION      = "elenchus_objection"
    REFLECTION_REVISION     = "reflection_revision"
    RECONSTRUCTION_PROPOSAL = "reconstruction_proposal"
    SYNTHESIS_DRAFT         = "synthesis_draft"
    RATIFICATION_INITIAL    = "ratification_initial"
    RATIFICATION_REVISION   = "ratification_revision"
    RATIFICATION_FINAL      = "ratification_final"
    COUNCIL_RATIFICATION    = "council_ratification"   # Phase 8C.1 per-provider verdict
    MOVE_SCORE              = "move_score"              # Phase 8C.2 registry peer move scoring
    SECTION_SCORE           = "section_score"           # Phase 8C.2 registry peer section scoring
    LESSON_DISTILLATION     = "lesson_distillation"     # Phase 13D AI-authored lesson
    PROCESS_REVIEW          = "process_review"          # Phase 13D AI meta-reflection on the dialogue
    LESSON_RELEVANCE        = "lesson_relevance"        # Phase 14 AI lesson retrieval
    LESSON_CONSOLIDATION    = "lesson_consolidation"    # Phase 15 memory consolidation ("sleep")
    TREE_REVISION           = "tree_revision"           # Deliberation-tree draft revision (search)
    OBJECTION_VERIFICATION  = "objection_verification"  # H3 mid-session check of one objection


class AgentTask(BaseModel):
    """
    Instruction packet sent from CED to an agent.
    The agent never stores this — it is consumed, acted on, and discarded.
    """
    task_id:       str = Field(default_factory=lambda: _uid("task_"))
    session_id:    str
    agent_id:      str
    role:          AgentRole
    phase:         DialogPhase
    question:      str
    context:       Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    round_number:  int = 0
    # Deterministic task identity (CED-owned routing; not scoring/leaderboard data).
    task_kind:     Optional[TaskKind] = None
    slot_index:    int = 0
    attempt_index: int = 0


class AgentState(BaseModel):
    """
    CED-owned view of one agent within a session.
    primary_role: deterministic assignment made at session creation.
    assigned_role: current phase override (e.g. REFLECTOR, FINAL_EVALUATOR).
    """
    agent_id:      str
    primary_role:  AgentRole
    assigned_role: AgentRole
    round_number:  int = 0
    has_submitted: bool = False


class AgentMove(BaseModel):
    """Structured output produced by an agent in response to an AgentTask."""
    move_id:          str = Field(default_factory=lambda: _uid("move_"))
    task_id:          str
    agent_id:         str
    role:             AgentRole
    phase:            DialogPhase
    content:          Dict[str, Any]
    confidence:       float = Field(ge=0.0, le=1.0, default=0.7)
    epistemic_markers: List[EpistemicMarker] = Field(default_factory=list)
    # Deterministic task identity copied from the AgentTask (CED-owned audit).
    task_kind:        Optional[TaskKind] = None
    slot_index:       int = 0
    attempt_index:    int = 0
    # Registry mode: which provider PRODUCED this move (for provider-level
    # no-self-scoring). None in the legacy self.agents path.
    provider_id:      Optional[str] = None
    timestamp:        datetime = Field(default_factory=_utcnow)


# ── Phase 8A: provider adapter contract (no real API calls yet) ───────────────

class ProviderResponse(BaseModel):
    """
    One provider adapter's response to a single agent task. CED-owned routing
    record — provider internals here are never inserted into AgentState or shown
    to agents. A failed provider carries status + error metadata, NOT a fake move.
    """
    provider_id:      str
    agent_id:         Optional[str] = None
    status:           ProviderStatus
    raw_text:         Optional[str] = None
    parsed_move:      Optional[AgentMove] = None
    error_message:    Optional[str] = None
    latency_ms:       Optional[float] = None
    retry_count:      int = 0
    repair_attempted: bool = False
    repair_succeeded: bool = False

    @property
    def ok(self) -> bool:
        return self.status == ProviderStatus.OK and self.parsed_move is not None


class CouncilRoundResult(BaseModel):
    """Outcome of gathering provider responses for one council round (CED-owned)."""
    responses:            List[ProviderResponse] = Field(default_factory=list)
    ok_provider_ids:      List[str] = Field(default_factory=list)
    failed_provider_ids:  List[str] = Field(default_factory=list)
    proceed:              bool = False
    warning:              Optional[str] = None


class TaskLogEntry(BaseModel):
    """
    CED-owned trace of a dispatched agent task (Phase 8C). Never inserted into
    AgentState and never sent to agents. Contains identity + a stable
    context_hash — NOT raw prompts/keys/secrets (full text is debug-only, off by
    default).
    """
    task_id:         str
    move_id:         Optional[str] = None
    session_id:      str
    phase:           DialogPhase
    round_index:     int = 0
    agent_id:        str
    assigned_role:   AgentRole
    task_kind:       Optional[TaskKind] = None
    slot_index:      int = 0
    attempt_index:   int = 0
    schema_name:     str = ""
    context_hash:    str = ""
    provider_id:     Optional[str] = None
    provider_status: Optional[ProviderStatus] = None
    debug_context:   Optional[Dict[str, Any]] = None   # debug-only; off by default
    created_at:      datetime = Field(default_factory=_utcnow)


# ── Scoring (shadow — never shown to agents) ──────────────────────────────────

# Dimension weights for the weighted overall. Must sum to 1.0 (unit-tested).
SCORE_WEIGHTS: Dict[str, float] = {
    "epistemic_value":      0.30,
    "logical_rigor":        0.20,
    "factual_grounding":    0.15,
    "constructive_impact":  0.10,
    "intellectual_honesty": 0.10,
    "clarity_precision":    0.10,
    "grounded_creativity":  0.05,
}


class ScoreBreakdown(BaseModel):
    """
    Multi-dimensional score, every dimension on a 0–10 scale.
    weighted_overall() collapses the seven dimensions; the weights sum to 1.0.
    """
    epistemic_value:      float = Field(ge=0.0, le=10.0)
    logical_rigor:        float = Field(ge=0.0, le=10.0)
    factual_grounding:    float = Field(ge=0.0, le=10.0)
    constructive_impact:  float = Field(ge=0.0, le=10.0)
    intellectual_honesty: float = Field(ge=0.0, le=10.0)
    clarity_precision:    float = Field(ge=0.0, le=10.0)
    grounded_creativity:  float = Field(ge=0.0, le=10.0)

    def weighted_overall(self) -> float:
        return (
            self.epistemic_value      * 0.30
            + self.logical_rigor      * 0.20
            + self.factual_grounding  * 0.15
            + self.constructive_impact * 0.10
            + self.intellectual_honesty * 0.10
            + self.clarity_precision  * 0.10
            + self.grounded_creativity * 0.05
        )


class MicroScore(BaseModel):
    """
    One voter's move-level shadow score. CED-owned; never shown to agents.
    Self-scoring is rejected (author_agent_id must differ from voter_agent_id).
    overall_score defaults to score_breakdown.weighted_overall() (0–10 scale).
    """
    session_id:       str
    output_id:        str                 # the scored AgentMove.move_id
    phase:            DialogPhase
    rubric_name:      Optional[str] = None  # phase-specific rubric (CED-owned)
    author_agent_id:  str
    voter_agent_id:   str
    provider_id:      Optional[str] = None  # registry provider that produced this score
    score_breakdown:  ScoreBreakdown
    overall_score:    Optional[float] = Field(default=None, ge=0.0, le=10.0)
    confidence:       float = Field(ge=0.0, le=1.0, default=0.7)
    justification:    str = ""
    penalty_flags:    List[PenaltyFlag] = Field(default_factory=list)
    provider_status:  ProviderStatus = ProviderStatus.OK
    created_at:       datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def _check_and_fill(self) -> "MicroScore":
        if self.author_agent_id == self.voter_agent_id:
            raise ValueError(
                f"Self-scoring is not allowed (agent '{self.author_agent_id}' "
                "cannot score its own output)."
            )
        if self.overall_score is None:
            self.overall_score = self.score_breakdown.weighted_overall()
        return self


class SectionScore(BaseModel):
    """
    One voter's score for ONE section of ONE draft. CED-owned.
    Self-scoring rejected; all scores on 0–10 scale.
    """
    score_id:         str = Field(default_factory=lambda: _uid("sc_"))
    session_id:       str
    section_name:     SectionName
    draft_id:         str
    author_agent_id:  str
    voter_agent_id:   str
    provider_id:      Optional[str] = None  # registry provider that produced this score
    score_breakdown:  ScoreBreakdown
    overall_score:    Optional[float] = Field(default=None, ge=0.0, le=10.0)
    confidence:       float = Field(ge=0.0, le=1.0, default=0.7)
    justification:    str = ""
    penalty_flags:    List[PenaltyFlag] = Field(default_factory=list)
    provider_status:  ProviderStatus = ProviderStatus.OK

    @model_validator(mode="after")
    def _check_and_fill(self) -> "SectionScore":
        if self.author_agent_id == self.voter_agent_id:
            raise ValueError(
                f"Self-scoring is not allowed (agent '{self.author_agent_id}' "
                "cannot score its own draft)."
            )
        if self.overall_score is None:
            self.overall_score = self.score_breakdown.weighted_overall()
        return self


class DraftScorecard(BaseModel):
    """
    One voter's scorecard for ONE draft, holding up to five SectionScores.
    CED-owned; never exposed to agents. Sections that could not be scored are
    recorded in missing_sections rather than silently dropped.
    """
    scorecard_id:       str = Field(default_factory=lambda: _uid("card_"))
    session_id:         str
    draft_id:           str
    author_agent_id:    str
    voter_agent_id:     str
    section_scores:     List[SectionScore] = Field(default_factory=list)
    missing_sections:   List[SectionName] = Field(default_factory=list)
    blocking_objection: Optional[str] = None
    provider_status:    ProviderStatus = ProviderStatus.OK

    @model_validator(mode="after")
    def _reject_self_scoring(self) -> "DraftScorecard":
        if self.author_agent_id == self.voter_agent_id:
            raise ValueError(
                f"Self-scoring is not allowed (agent '{self.author_agent_id}' "
                "cannot score its own draft)."
            )
        return self

    def score_for_section(self, section: SectionName) -> Optional[SectionScore]:
        return next((s for s in self.section_scores if s.section_name == section), None)


# ── Draft / Assembly ──────────────────────────────────────────────────────────

class SectionDraft(BaseModel):
    """
    One synthesizer's full 5-section draft answer. The five section fields are
    the locked structure; the rest is CED-owned routing metadata.
    """
    draft_id:           str = Field(default_factory=lambda: _uid("draft_"))
    session_id:         str
    author_agent_id:    str
    move_id:            str
    provider_id:        Optional[str] = None   # registry provider that produced the draft
    core_answer:         str
    crucial_stress_test: str
    blind_spots:         str
    nuance:              str
    final_verdict:       str

    def section_text(self, section: SectionName) -> str:
        return getattr(self, section.value)

    def sections(self) -> Dict[SectionName, str]:
        return {s: getattr(self, s.value) for s in SECTION_ORDER}


class AssembledSection(BaseModel):
    """One section selected mechanically (blind) as the best across all drafts."""
    section_name:             SectionName
    selected_draft_id:        str
    selected_author_agent_id: str
    content:                  str
    average_score:            float           # 0–10 scale
    score_count:              int = 0
    variance:                 float = 0.0
    unresolved:               bool = False


class AssembledAnswer(BaseModel):
    """Complete answer assembled from the best draft per section."""
    answer_id:           str = Field(default_factory=lambda: _uid("ans_"))
    session_id:          str
    sections:            List[AssembledSection] = Field(default_factory=list)
    assembly_method:     str = "blind_section_highest_average"
    unresolved_sections: List[SectionName] = Field(default_factory=list)
    assembled_at:        datetime = Field(default_factory=_utcnow)

    def section(self, name: SectionName) -> Optional[AssembledSection]:
        return next((s for s in self.sections if s.section_name == name), None)

    def full_text(self) -> str:
        ordered = [s for name in SECTION_ORDER
                   for s in self.sections if s.section_name == name]
        parts = []
        for s in ordered:
            heading = s.section_name.value.replace("_", " ").title()
            body = s.content if not s.unresolved else "(unresolved — no acceptable draft)"
            parts.append(f"## {heading}\n{body}")
        return "\n\n".join(parts)


# ── Ratification ──────────────────────────────────────────────────────────────

class RatificationVote(BaseModel):
    """Final Evaluator's structured verdict on the assembled answer (single-evaluator path)."""
    voter_agent_id: str
    decision:       RatificationDecision
    severity:       ObjectionSeverity = ObjectionSeverity.NONE
    target_section: Optional[SectionName] = None
    reason:         str = ""

    def is_critical_block(self) -> bool:
        """Only a BLOCKING_OBJECTION at CRITICAL severity blocks."""
        return (
            self.decision == RatificationDecision.BLOCKING_OBJECTION
            and self.severity == ObjectionSeverity.CRITICAL
        )


# ── Phase 8C.1: Socratic Council Ratification (council-level, not a monarchy) ──

class FinalSynthesisMode(str, Enum):
    """How the final answer is ratified. Only council_ratification is implemented
    in V1; the others are RESERVED for V2/V3 (no logic added now)."""
    COUNCIL_RATIFICATION = "council_ratification"
    CANDIDATE_TOURNAMENT = "candidate_tournament"   # reserved (future V2/V3)
    HYBRID               = "hybrid"                 # reserved (future V2/V3)


class CouncilVerdict(str, Enum):
    ACCEPT             = "accept"
    ACCEPT_WITH_CAVEAT = "accept_with_caveat"
    BLOCKING_OBJECTION = "blocking_objection"


class CouncilRatificationStatus(str, Enum):
    RATIFIED                   = "ratified"
    RATIFIED_WITH_CAVEATS      = "ratified_with_caveats"
    REPAIR_REQUIRED            = "repair_required"          # ≥1 valid critical block
    RATIFICATION_FAILED        = "ratification_failed"      # no valid verdicts
    RATIFICATION_QUORUM_FAILED = "ratification_quorum_failed"


class RatificationVerdict(BaseModel):
    """
    One participating agent/provider's independent verdict on the final synthesis.
    CED-owned; attributed to the voter that raised it. CED only checks structural
    schema validity — it never judges whether the verdict is philosophically right.
    """
    ratification_id: str = Field(default_factory=lambda: _uid("rat_"))
    session_id:      str
    agent_id:        str
    provider_id:     Optional[str] = None
    verdict:         CouncilVerdict
    rationale:       str = ""
    confidence:      float = Field(ge=0.0, le=1.0, default=0.7)
    caveat:          Optional[str] = None
    blocking_objection: Optional[str] = None
    target_section:  Optional[SectionName] = None
    severity:        ObjectionSeverity = ObjectionSeverity.NONE
    required_fix:    Optional[str] = None
    provider_status: ProviderStatus = ProviderStatus.OK
    task_id:         Optional[str] = None
    move_id:         Optional[str] = None

    def is_schema_valid_critical_block(self) -> bool:
        """
        STRUCTURAL check only (no semantic judgement): a blocking objection that
        is critically severe and carries a target_section, a rationale and a
        required_fix. CED does not assess whether the objection is 'correct'.
        """
        return (
            self.verdict == CouncilVerdict.BLOCKING_OBJECTION
            and self.severity == ObjectionSeverity.CRITICAL
            and self.target_section is not None
            and bool(self.rationale.strip())
            and bool((self.required_fix or "").strip())
        )

    def is_caveat(self) -> bool:
        """A non-blocking concern: an explicit caveat, or a non-critical objection."""
        if self.verdict == CouncilVerdict.ACCEPT_WITH_CAVEAT:
            return True
        if self.verdict == CouncilVerdict.BLOCKING_OBJECTION and not self.is_schema_valid_critical_block():
            return True
        return False


class CouncilRatification(BaseModel):
    """CED-owned outcome of a council ratification round (mechanical aggregation)."""
    session_id:           str
    status:               CouncilRatificationStatus
    verdicts:             List[RatificationVerdict] = Field(default_factory=list)
    valid_verdicts:       int = 0
    invalid_verdicts:     int = 0
    quorum:               int = 0
    caveat_count:         int = 0
    critical_block_count: int = 0
    target_sections:      List[SectionName] = Field(default_factory=list)
    failed_providers:     List[str] = Field(default_factory=list)
    timed_out_providers:  List[str] = Field(default_factory=list)
    rounds:               int = 1

    def is_ratified(self) -> bool:
        return self.status in (
            CouncilRatificationStatus.RATIFIED,
            CouncilRatificationStatus.RATIFIED_WITH_CAVEATS,
        )


# ── Phase 7: epistemic sync gate + CED-owned leaderboard ──────────────────────

class ShadowScoreHarvest(BaseModel):
    """
    Result of the bounded final harvest of shadow-scoring tasks (the sync gate).
    CED-owned audit record — never shown to agents.
    """
    session_id:      str
    scores_expected: int = 0
    scores_collected: int = 0
    coverage_ratio:  float = 0.0
    status:          SyncGateStatus = SyncGateStatus.UNAVAILABLE
    timed_out_tasks: List[str] = Field(default_factory=list)
    failed_tasks:    List[str] = Field(default_factory=list)


class EpistemicLeaderboard(BaseModel):
    """
    CED-owned aggregate analytics over shadow scores. Must NOT be inserted into
    AgentState and must NOT be shown to agents. Aggregates only — no raw
    MicroScore / SectionScore objects, no raw justifications (unless debug).
    """
    session_id:                str
    leaderboard_status:        LeaderboardStatus = LeaderboardStatus.UNAVAILABLE
    scores_expected:           int = 0
    scores_collected:          int = 0
    coverage_ratio:            float = 0.0
    average_scores_by_agent:   Dict[str, float] = Field(default_factory=dict)
    cumulative_scores_by_agent: Dict[str, float] = Field(default_factory=dict)
    scores_by_phase:           Dict[str, Dict[str, float]] = Field(default_factory=dict)
    top_contributors:          List[str] = Field(default_factory=list)
    notable_events:            List[str] = Field(default_factory=list)
    interpretation_warning:    str = LEADERBOARD_INTERPRETATION_WARNING


# ── Final Response ────────────────────────────────────────────────────────────

class FinalResponse(BaseModel):
    """
    What the end-user / developer receives after the Council completes.

    Phase 7 separates the assembled synthesis, the ratification outcome, the
    CED-owned audit summary, and the CED-owned leaderboard. The pre-Phase-7
    fields (answer/ratified/...) are retained for backward compatibility.
    Raw MicroScore / SectionScore objects are never exposed here.
    """
    response_id:         str = Field(default_factory=lambda: _uid("resp_"))
    session_id:          str
    question:            str

    # Phase 7 contract — clearly separated parts.
    synthesis:           Optional[AssembledAnswer] = None
    ratification_status: str = ""           # "ratified" | "blocked" | "unresolved"
    audit_summary:       Dict[str, Any] = Field(default_factory=dict)
    socratic_leaderboard: Optional[EpistemicLeaderboard] = None

    # Retained (backward compatible) fields.
    answer:              str = ""
    ratified:            bool = False
    blocking_objections: List[str] = Field(default_factory=list)
    unresolved_sections: List[SectionName] = Field(default_factory=list)
    ratification_votes:  List[RatificationVote] = Field(default_factory=list)
    # LEGACY, retained for compatibility and audit. Produced by a mean-quality
    # threshold (>= 7.5 -> well_supported) and NON-GOVERNING after H7. Read
    # governing_epistemic_status instead.
    # LEGACY, retained for compatibility and audit. Produced by a mean-quality
    # threshold (>= 7.5 -> well_supported) and NON-GOVERNING after H7. Read
    # governing_epistemic_status instead.
    epistemic_status:    EpistemicStatus = EpistemicStatus.UNCERTAIN
    # H7 authority migration: the governing epistemic state, decided from
    # records by the hybrid core. None on paths that do not run the core.
    governing_epistemic_status: Optional[str] = None
    #: The frozen release decision. The single release authority.
    release_decision:    Optional[str] = None
    # H7 authority migration: the governing epistemic state, decided from
    # records by the hybrid core. None on paths that do not run the core.
    governing_epistemic_status: Optional[str] = None
    #: The frozen release decision. The single release authority.
    release_decision:    Optional[str] = None
    council_summary:     Dict[str, Any] = Field(default_factory=dict)
    created_at:          datetime = Field(default_factory=_utcnow)


# ── Session State (CED-owned) ─────────────────────────────────────────────────

class SessionState(BaseModel):
    """
    Complete CED-owned state for one dialogue session.
    Agents never hold a reference to this object.
    """
    session_id:       str = Field(default_factory=lambda: _uid("sess_"))
    question:         str
    phase:            DialogPhase = DialogPhase.OPENING
    round_number:     int = 0
    agent_states:     Dict[str, AgentState] = Field(default_factory=dict)
    moves:            List[AgentMove] = Field(default_factory=list)
    # Phase 4 scoring is CED-owned and lives only here, never on AgentState.
    micro_scores:     List[MicroScore] = Field(default_factory=list)      # move-level (VALID peer scores only)
    # Peer scoring tasks that failed/were invalid — recorded, NEVER fabricated as scores.
    failed_score_tasks: List[str] = Field(default_factory=list)
    section_scores_failed: List[str] = Field(default_factory=list)
    section_drafts:   List[SectionDraft] = Field(default_factory=list)    # 5-section drafts
    draft_scorecards: List[DraftScorecard] = Field(default_factory=list)  # section-level
    # Phase 7 CED-owned audit analytics (never on AgentState, never to agents).
    shadow_harvest:      Optional[ShadowScoreHarvest] = None
    epistemic_leaderboard: Optional[EpistemicLeaderboard] = None
    # Phase 8B registry-backed council rounds (CED-owned audit; never to agents).
    registry_rounds:  List[CouncilRoundResult] = Field(default_factory=list)
    # Phase 8C CED-owned task trace (never on AgentState, never to agents).
    task_log:         List[TaskLogEntry] = Field(default_factory=list)
    # Phase 8C.1 council ratification outcome (CED-owned audit; never to agents).
    council_ratification: Optional["CouncilRatification"] = None
    assembled_answer: Optional[AssembledAnswer] = None
    final_response:   Optional[FinalResponse] = None
    phase_history:    List[DialogPhase] = Field(default_factory=list)
    # Per-phase deterministic role assignments, recorded by the CED as each phase
    # runs. Each entry: {"phase", "round_index", "agent_id", "role"}.
    role_history:     List[Dict[str, Any]] = Field(default_factory=list)
    created_at:       datetime = Field(default_factory=_utcnow)
    updated_at:       datetime = Field(default_factory=_utcnow)

    def moves_for_phase(self, phase: DialogPhase) -> List[AgentMove]:
        return [m for m in self.moves if m.phase == phase]

    def micro_scores_for_move(self, move_id: str) -> List["MicroScore"]:
        return [ms for ms in self.micro_scores if ms.output_id == move_id]

    def section_scores_for(self, section: "SectionName") -> List["SectionScore"]:
        """Every voter's SectionScore for one section, across all drafts."""
        return [
            ss
            for card in self.draft_scorecards
            for ss in card.section_scores
            if ss.section_name == section
        ]

    def record_role_assignment(
        self,
        phase: DialogPhase,
        round_index: int,
        assignment: Dict[str, "AgentRole"],
    ) -> None:
        """Append one role_history record per (agent_id, role) for this phase."""
        for agent_id, role in assignment.items():
            self.role_history.append({
                "phase": phase.value,
                "round_index": round_index,
                "agent_id": agent_id,
                "role": role.value if isinstance(role, AgentRole) else str(role),
            })
        self.updated_at = _utcnow()

    def roles_for_phase_history(self, phase: DialogPhase) -> List[Dict[str, Any]]:
        """All role_history records for a given phase, in recorded order."""
        return [r for r in self.role_history if r["phase"] == phase.value]

    def advance_phase(self, new_phase: DialogPhase) -> None:
        # Record the phase we are leaving, skipping no-op re-entries (e.g. the
        # initial OPENING default → OPENING) so phase_history stays clean.
        if self.phase != new_phase:
            self.phase_history.append(self.phase)
        self.phase = new_phase
        self.updated_at = _utcnow()
