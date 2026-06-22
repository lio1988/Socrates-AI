"""
Socratic Dialogues Orchestration System — Pydantic Models (V1)

All session state is CED-owned. Agents never hold a reference to SessionState
or to any scorecard. They receive an AgentTask and return an AgentMove — that
is the full extent of their I/O contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


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
    OK          = "ok"
    DEGRADED    = "degraded"
    FALLBACK    = "fallback"
    ERROR       = "error"
    UNAVAILABLE = "unavailable"


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


# ── Task / Move ───────────────────────────────────────────────────────────────

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
    timestamp:        datetime = Field(default_factory=datetime.utcnow)


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
    author_agent_id:  str
    voter_agent_id:   str
    score_breakdown:  ScoreBreakdown
    overall_score:    Optional[float] = Field(default=None, ge=0.0, le=10.0)
    confidence:       float = Field(ge=0.0, le=1.0, default=0.7)
    justification:    str = ""
    penalty_flags:    List[PenaltyFlag] = Field(default_factory=list)
    provider_status:  ProviderStatus = ProviderStatus.OK
    created_at:       datetime = Field(default_factory=datetime.utcnow)

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
    assembled_at:        datetime = Field(default_factory=datetime.utcnow)

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
    """Final Evaluator's structured verdict on the assembled answer."""
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


# ── Final Response ────────────────────────────────────────────────────────────

class FinalResponse(BaseModel):
    """What the end-user receives after the Council completes ratification."""
    response_id:         str = Field(default_factory=lambda: _uid("resp_"))
    session_id:          str
    question:            str
    answer:              str
    ratified:            bool
    blocking_objections: List[str] = Field(default_factory=list)
    unresolved_sections: List[SectionName] = Field(default_factory=list)
    ratification_votes:  List[RatificationVote] = Field(default_factory=list)
    epistemic_status:    EpistemicStatus = EpistemicStatus.UNCERTAIN
    council_summary:     Dict[str, Any] = Field(default_factory=dict)
    created_at:          datetime = Field(default_factory=datetime.utcnow)


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
    micro_scores:     List[MicroScore] = Field(default_factory=list)      # move-level
    section_drafts:   List[SectionDraft] = Field(default_factory=list)    # 5-section drafts
    draft_scorecards: List[DraftScorecard] = Field(default_factory=list)  # section-level
    assembled_answer: Optional[AssembledAnswer] = None
    final_response:   Optional[FinalResponse] = None
    phase_history:    List[DialogPhase] = Field(default_factory=list)
    # Per-phase deterministic role assignments, recorded by the CED as each phase
    # runs. Each entry: {"phase", "round_index", "agent_id", "role"}.
    role_history:     List[Dict[str, Any]] = Field(default_factory=list)
    created_at:       datetime = Field(default_factory=datetime.utcnow)
    updated_at:       datetime = Field(default_factory=datetime.utcnow)

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
        self.updated_at = datetime.utcnow()

    def roles_for_phase_history(self, phase: DialogPhase) -> List[Dict[str, Any]]:
        """All role_history records for a given phase, in recorded order."""
        return [r for r in self.role_history if r["phase"] == phase.value]

    def advance_phase(self, new_phase: DialogPhase) -> None:
        # Record the phase we are leaving, skipping no-op re-entries (e.g. the
        # initial OPENING default → OPENING) so phase_history stays clean.
        if self.phase != new_phase:
            self.phase_history.append(self.phase)
        self.phase = new_phase
        self.updated_at = datetime.utcnow()
