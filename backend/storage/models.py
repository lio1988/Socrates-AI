"""Data models and enumerations for Socrates AI (extracted from main.py).

Pydantic request/response and domain models, plus the rule-tagged enums.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Literal, Tuple

from pydantic import BaseModel, Field, validator


class DialogModeEnum(str, Enum):
    SOCRATIC  = "socratic"
    DEBATE    = "debate"
    CONSENSUS = "consensus"


class DialogSpeedEnum(str, Enum):
    VERY_SLOW = "very_slow"
    SLOW      = "slow"
    NORMAL    = "normal"
    FAST      = "fast"
    VERY_FAST = "very_fast"


class SummaryModeEnum(str, Enum):
    NONE  = "none"
    EVERY = "every"
    HALF  = "half"


class ClaimStatus(str, Enum):
    """Rule 6 — Fact Verification statuses"""
    VERIFIED     = "verified"
    LIKELY       = "likely"
    UNVERIFIED   = "unverified"
    CONTRADICTED = "contradicted"


class EdgeType(str, Enum):
    """Rule 7 — Contradiction Graph edge types"""
    SUPPORTS     = "supports"
    CONTRADICTS  = "contradicts"
    DEPENDS_ON   = "depends_on"
    REFINES      = "refines"


class ComplexityLevel(str, Enum):
    """Rule 10 — Adaptive reasoning depth"""
    SIMPLE       = "simple"
    MODERATE     = "moderate"
    COMPLEX      = "complex"
    VERY_COMPLEX = "very_complex"


class ConsensusItemType(str, Enum):
    """Rule 9 — Consensus Memory item types"""
    CONCLUSION   = "conclusion"
    OPEN_QUESTION = "open_question"
    DISAGREEMENT = "disagreement"


class Domain(str, Enum):
    """Rule 12 — Domain-based synthesis model selection"""
    SOFTWARE    = "software"
    MATHEMATICS = "mathematics"
    CREATIVE    = "creative"
    SCIENCE     = "science"
    PHILOSOPHY  = "philosophy"
    LAW         = "law"
    ETHICS      = "ethics"
    GENERAL     = "general"


# ============================================================================
# SECTION 2: DATA MODELS
# ============================================================================

# ── Rule 6: Fact Claims ─────────────────────────────────────────────────────

class Claim(BaseModel):
    """A verifiable factual claim with full provenance (Rule 6)"""
    claim_id:   str        = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    text:       str
    evidence:   str        = ""
    confidence: float      = Field(ge=0.0, le=1.0, default=0.5)
    source:     str        # model_id that made the claim
    status:     ClaimStatus = ClaimStatus.UNVERIFIED
    round:      int
    timestamp:  str        = Field(default_factory=lambda: datetime.now().isoformat())


# ── Rule 7: Contradiction Graph ─────────────────────────────────────────────

class ContradictionEdge(BaseModel):
    """Edge in the Contradiction Graph (Rule 7)"""
    edge_id:          str      = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_claim_id:  str
    target_claim_id:  str
    edge_type:        EdgeType
    explanation:      str
    detected_by:      str      # model_id that detected the edge
    detected_in_round: int


class ContradictionGraphData(BaseModel):
    """Full Contradiction Graph preserving reasoning history (Rule 7)"""
    nodes: List[Claim]              = []
    edges: List[ContradictionEdge]  = []


# ── Rule 8: Knowledge Graph ─────────────────────────────────────────────────

class KnowledgeConcept(BaseModel):
    """A validated concept in the Knowledge Graph (Rule 8)"""
    concept_id:     str   = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    label:          str
    definition:     str
    confidence:     float = Field(ge=0.0, le=1.0)
    source_model:   str
    validated:      bool  = False   # MUST be True before entering long-term memory
    round_added:    int
    # Rule 8 enforcement: opinions and unverified drafts are rejected
    is_opinion:     bool  = False
    is_hallucination_risk: bool = False


class KnowledgeRelation(BaseModel):
    """A relation between two validated concepts (Rule 8)"""
    from_concept_id: str
    to_concept_id:   str
    relation_type:   str
    strength:        float = Field(ge=0.0, le=1.0)


class KnowledgeGraphData(BaseModel):
    """Knowledge Graph — only validated knowledge (Rule 8)"""
    concepts:  List[KnowledgeConcept]  = []
    relations: List[KnowledgeRelation] = []

    def add_concept(self, concept: KnowledgeConcept) -> bool:
        """
        Rule 8 enforcement: reject unvalidated, opinionated, or risky concepts.
        Returns True if added, False if rejected.
        """
        if not concept.validated:
            return False
        if concept.is_opinion or concept.is_hallucination_risk:
            return False
        self.concepts.append(concept)
        return True


# ── Rule 9: Consensus Memory ─────────────────────────────────────────────────

class ConsensusItem(BaseModel):
    """A single item in Consensus Memory (Rule 9)"""
    item_id:       str              = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type:          ConsensusItemType
    content:       str
    evidence:      List[str]        = []
    confidence:    float            = Field(ge=0.0, le=1.0)
    models_agreed: List[str]        = []
    round:         int
    timestamp:     str              = Field(default_factory=lambda: datetime.now().isoformat())


class ConsensusMemoryData(BaseModel):
    """
    Consensus Memory stores only:
    - Verified conclusions
    - Open questions
    - Remaining disagreements
    NOT complete conversations (Rule 9)
    """
    verified_conclusions:   List[ConsensusItem] = []
    open_questions:         List[ConsensusItem] = []
    remaining_disagreements: List[ConsensusItem] = []

    @property
    def total_items(self) -> int:
        return (len(self.verified_conclusions) +
                len(self.open_questions) +
                len(self.remaining_disagreements))


# ── Rule 3: Elenchus ────────────────────────────────────────────────────────


# ── v10.2: Provider runtime transparency ─────────────────────────────────────

class ProviderRuntimeStatus(BaseModel):
    """Runtime visibility for provider calls. Never stores API keys."""
    provider_name: str
    configured: bool = False
    real_api_call: Optional[bool] = None
    fallback_used: Optional[bool] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    latency_ms: Optional[int] = None


class ElenchusResult(BaseModel):
    """Result of a mandatory Elenchus (falsification) phase (Rule 3)"""
    elenchus_id:             str  = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    round:                   int
    target_claim_summary:    str
    challenger_model:        str  # Rule 1: rotates
    challenged_assumptions:  List[str] = []
    logic_gaps:              List[str] = []
    evidence_issues:         List[str] = []
    conclusion_issues:       List[str] = []
    falsification_successful: bool     = False
    # Rule 3: If successful, original answer MUST be revised
    revision_required:       bool     = False
    revision_submitted:      bool     = False
    # v10.2: human-useful Elenchus explanation and claim target clarity.
    target_claim_id:         Optional[str] = None
    target_claim_text:       str = ""
    target_is_epistemic_claim: Optional[bool] = None
    outcome:                 str = "not_refuted_yet"
    reason:                  str = ""
    remaining_uncertainty:   str = ""
    next_socratic_question:  str = ""
    evidence_needed:         List[str] = []
    falsification_status:    str = "not_refuted_yet"
    provider_status:         Optional[ProviderRuntimeStatus] = None
    timestamp:               str      = Field(default_factory=lambda: datetime.now().isoformat())


# ── Rule 5: Reflection ──────────────────────────────────────────────────────

class ReflectionStep(BaseModel):
    """
    Per-agent reflection before final submission (Rule 5):
    Initial reasoning → Self-criticism → Revision → Final reasoning
    """
    reflection_id:    str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    model_id:         str
    round:            int
    initial_reasoning: str
    self_criticism:   str
    revision:         str
    final_reasoning:  str
    improved:         bool = False  # Did reflection change the answer?
    timestamp:        str  = Field(default_factory=lambda: datetime.now().isoformat())


# ── Rule 10: Complexity Assessment ──────────────────────────────────────────

class ComplexityAssessment(BaseModel):
    """Drives adaptive reasoning depth (Rule 10)"""
    level:                        ComplexityLevel
    score:                        float = Field(ge=0.0, le=1.0)
    recommended_rounds:           int
    recommended_reflection_interval: int
    requires_fact_verification:   bool
    requires_elenchus:            bool
    estimated_socratic_cycles:    int
    domain:                       Domain
    reasoning:                    str


# ── Rule 12+13: Synthesis ───────────────────────────────────────────────────

class SynthesisResult(BaseModel):
    """
    Dynamic synthesis with full explainability (Rules 12 + 13)
    Rule 13: Must include reasoning, evidence, uncertainty, confidence, alternatives
    Rule 12: Model selected by domain
    """
    selected_model:        str
    domain:                Domain
    domain_selection_reason: str
    reasoning_summary:     str
    supporting_evidence:   List[str]
    remaining_uncertainty: str
    confidence_score:      float = Field(ge=0.0, le=1.0)
    # Rule 13: Never hide disagreement
    alternative_viewpoints: List[str]
    hidden_disagreements:  List[str]  = []  # Always exposed, never hidden
    final_answer:          str
    # Rule 4: Certify this emerged from dialogue, not authority
    emerged_from_dialogue: bool = True
    claims_referenced:     List[str] = []  # IDs from Claim store
    timestamp:             str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Rule 14: Evolution Log ──────────────────────────────────────────────────

class EvolutionEntry(BaseModel):
    """
    Tracks improvements to routing, prompts, discussion order (Rule 14).
    Changes to stored knowledge require explicit reasoning.
    """
    entry_id:    str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    component:   str  # "routing" | "prompt" | "discussion_order" | "reasoning_policy"
    change:      str
    reason:      str
    round:       int
    timestamp:   str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Request / Response Models ────────────────────────────────────────────────

class DialogStartRequest(BaseModel):
    topic:        str             = Field(..., min_length=1, max_length=500)
    rounds:       int             = Field(default=8, ge=2, le=20)
    mode:         DialogModeEnum  = DialogModeEnum.SOCRATIC
    speed:        DialogSpeedEnum = DialogSpeedEnum.NORMAL
    summary_mode: SummaryModeEnum = SummaryModeEnum.EVERY
    # Rule 10: allow override, but never go below complexity minimum
    force_min_rounds: bool = False


class DialogTurnResponse(BaseModel):
    round:      int
    model_id:   str
    content:    str
    is_socratic: bool
    is_elenchus: bool = False
    is_reflection: bool = False
    timestamp:  str
    provider_status: Optional[ProviderRuntimeStatus] = None


class SocraticRotationInfo(BaseModel):
    """Rule 1: Full rotation history — proves no permanent authority"""
    rotation_order:       List[str]
    current_socrates:     str
    next_socrates:        str
    rounds_as_socrates:   Dict[str, int]


class DialogStatusResponse(BaseModel):
    session_id:         str
    topic:              str
    rounds_planned:     int
    rounds_completed:   int
    mode:               str
    status:             str
    complexity:         Optional[ComplexityAssessment]
    convergence_score:  float
    consensus_stable:   bool
    socratic_rotation:  Optional[SocraticRotationInfo]
    history:            List[DialogTurnResponse]
    scores:             dict
    constitution_violations: List[str]


class InjectQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)

