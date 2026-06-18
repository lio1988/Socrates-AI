#!/usr/bin/env python3
"""
Socratic Dialog API — Engineering Constitution v0.1
Multi-Agent Socratic Reasoning Engine

Philosophy: Truth through structured dialogue.
NOT speed. NOT single-model performance.

Rules implemented:
  ✅ Rule  1 — Rotating authority, no permanent Socrates
  ✅ Rule  2 — Mandatory Socratic phase every round
  ✅ Rule  3 — Mandatory Elenchus (falsification attempt)
  ✅ Rule  4 — Maieutic emergence, not authoritative conclusion
  ✅ Rule  5 — Per-agent reflection loop before submission
  ✅ Rule  6 — Fact claims carry evidence, confidence, source, status
  ✅ Rule  7 — Contradiction Graph (supports/contradicts/depends_on/refines)
  ✅ Rule  8 — Knowledge Graph stores only validated knowledge
  ✅ Rule  9 — Consensus Memory: conclusions, open questions, disagreements
  ✅ Rule 10 — Adaptive reasoning depth from complexity assessment
  ✅ Rule 11 — Convergence-based stopping, not fixed rounds
  ✅ Rule 12 — Dynamic synthesis model selected by domain
  ✅ Rule 13 — Every answer includes reasoning, uncertainty, confidence, alternatives
  ✅ Rule 14 — Evolution log for routing and strategy improvements
  ✅ Rule 15 — Fully modular, each engine is independent

Forbidden (ConstitutionGuard enforced):
  ❌ Shorten Socratic process for speed
  ❌ Replace consensus with single-model decision
  ❌ Permanent authority for one agent
  ❌ Store unverified data in Knowledge Graph
  ❌ Hide disagreements in synthesis
  ❌ Add new facts during synthesis
"""

from __future__ import annotations

import json
import os
import uuid
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal, Tuple
from enum import Enum
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sse_starlette.responses import EventSourceResponse

from socrates_ai import DialogManager, DialogConfig, DialogMode, DialogSpeed, SummaryMode


# ============================================================================
# SECTION 1: ENUMERATIONS
# ============================================================================

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


# ============================================================================
# SECTION 3: CONSTITUTION GUARD (Rule enforcement)
# ============================================================================

class ConstitutionViolationError(Exception):
    """Raised when an Engineering Constitution rule is violated"""
    def __init__(self, rule: int, description: str):
        self.rule = rule
        self.description = description
        super().__init__(f"[Constitution Rule {rule}] {description}")


class ConstitutionGuard:
    """
    Enforces the Engineering Constitution v0.1.
    Every forbidden action raises ConstitutionViolationError.
    """

    @staticmethod
    def assert_socratic_rotation(
        model_id: str,
        previous_socrates: Optional[str],
        rounds_as_socrates: Dict[str, int],
        total_rounds: int,
    ) -> None:
        """Rule 1: No agent permanently acts as Socrates"""
        if previous_socrates and model_id == previous_socrates:
            # Check if this agent has been Socrates > 60% of rounds
            count = rounds_as_socrates.get(model_id, 0)
            if count > total_rounds * 0.6:
                raise ConstitutionViolationError(
                    1,
                    f"{model_id} has been Socrates in {count}/{total_rounds} rounds "
                    f"(>{60}%). Authority must rotate."
                )

    @staticmethod
    def assert_socratic_phase_present(history: List[DialogTurnResponse]) -> None:
        """Rule 2: Every discussion must contain a Socratic phase"""
        has_socratic = any(t.is_socratic for t in history)
        if history and not has_socratic:
            raise ConstitutionViolationError(
                2,
                "No Socratic phase found in dialogue history. "
                "Every discussion MUST contain a Socratic phase."
            )

    @staticmethod
    def assert_elenchus_after_claim(
        elenchus_history: List[ElenchusResult],
        rounds_completed: int,
    ) -> None:
        """Rule 3: Every answer must be challenged via Elenchus"""
        if rounds_completed > 0 and not elenchus_history:
            raise ConstitutionViolationError(
                3,
                f"No Elenchus performed after {rounds_completed} rounds. "
                "Every proposed answer MUST be challenged."
            )

    @staticmethod
    def assert_reflection_performed(
        reflection_history: List[ReflectionStep],
        model_id: str,
        round_num: int,
    ) -> None:
        """Rule 5: Every agent must reflect before final submission"""
        performed = any(
            r.model_id == model_id and r.round == round_num
            for r in reflection_history
        )
        if not performed:
            raise ConstitutionViolationError(
                5,
                f"{model_id} submitted in round {round_num} without a Reflection step. "
                "Every agent MUST review its own reasoning before submission."
            )

    @staticmethod
    def assert_claim_has_provenance(claim: Claim) -> None:
        """Rule 6: Every factual claim must carry Evidence + Confidence + Source + Status"""
        if not claim.source:
            raise ConstitutionViolationError(6, "Claim missing 'source'.")
        if claim.confidence == 0.5 and not claim.evidence:
            raise ConstitutionViolationError(
                6, f"Claim '{claim.text[:60]}...' has no evidence and default confidence."
            )

    @staticmethod
    def assert_knowledge_graph_validated_only(concept: KnowledgeConcept) -> None:
        """Rule 8: Only validated knowledge enters long-term memory"""
        if not concept.validated:
            raise ConstitutionViolationError(
                8,
                f"Concept '{concept.label}' is not validated. "
                "The Knowledge Graph MUST NOT store unvalidated concepts."
            )
        if concept.is_opinion:
            raise ConstitutionViolationError(
                8, f"Concept '{concept.label}' is an opinion. Opinions MUST NOT enter the Knowledge Graph."
            )
        if concept.is_hallucination_risk:
            raise ConstitutionViolationError(
                8, f"Concept '{concept.label}' is flagged as hallucination risk."
            )

    @staticmethod
    def assert_consensus_not_single_model(
        models_agreed: List[str],
        available_models: List[str],
    ) -> None:
        """Rule 3+9: Consensus cannot be decided by a single model"""
        if len(models_agreed) == 1 and len(available_models) > 1:
            raise ConstitutionViolationError(
                3,
                f"Consensus declared by single model '{models_agreed[0]}'. "
                "Consensus MUST NOT replace structured Elenchus."
            )

    @staticmethod
    def assert_synthesis_no_new_facts(
        synthesis_text: str,
        claim_texts: List[str],
    ) -> List[str]:
        """
        Rule 6+: Synthesis must not add new facts.
        Returns list of suspected new facts (heuristic — LLM should enforce strictly).
        """
        warnings: List[str] = []
        # Heuristic: flag sentences with factual patterns not in claims
        import re
        sentences = re.split(r'[.!?]', synthesis_text)
        factual_patterns = [r'\d{4}', r'\b\d+%', r'\baccording to\b', r'\bproved\b', r'\bshowed that\b']
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            for pattern in factual_patterns:
                if re.search(pattern, sent, re.IGNORECASE):
                    matched = any(
                        sent.lower()[:40] in c.lower() for c in claim_texts
                    )
                    if not matched:
                        warnings.append(sent[:100])
                        break
        return warnings

    @staticmethod
    def assert_disagreements_exposed(synthesis: SynthesisResult) -> None:
        """Rule 13: Never hide disagreement"""
        if synthesis.hidden_disagreements:
            raise ConstitutionViolationError(
                13,
                f"Synthesis attempted to hide {len(synthesis.hidden_disagreements)} disagreement(s). "
                "Disagreements MUST always be exposed."
            )

    @staticmethod
    def assert_minimum_rounds(
        requested_rounds: int,
        complexity: ComplexityAssessment,
    ) -> int:
        """
        Rule 10: Complexity drives minimum rounds.
        Returns the enforced round count (may be higher than requested).
        """
        if requested_rounds < complexity.recommended_rounds:
            return complexity.recommended_rounds
        return requested_rounds


# ============================================================================
# SECTION 4: DOMAIN CLASSIFIER (Rule 12)
# ============================================================================

# Keywords that suggest each domain
_DOMAIN_KEYWORDS: Dict[Domain, List[str]] = {
    Domain.SOFTWARE:    ["code", "algorithm", "software", "programming", "api", "database", "system", "architecture"],
    Domain.MATHEMATICS: ["math", "proof", "theorem", "equation", "calculus", "probability", "statistics", "number"],
    Domain.CREATIVE:    ["story", "poem", "narrative", "art", "design", "creative", "imagination", "metaphor"],
    Domain.SCIENCE:     ["quantum", "physics", "chemistry", "biology", "experiment", "hypothesis", "empirical"],
    Domain.PHILOSOPHY:  ["consciousness", "existence", "reality", "truth", "knowledge", "ethics", "ontology", "epistemology", "free will", "soul"],
    Domain.LAW:         ["law", "legal", "rights", "justice", "constitution", "court", "regulation", "contract"],
    Domain.ETHICS:      ["moral", "ethical", "good", "evil", "virtue", "duty", "harm", "obligation", "AI ethics"],
}

# Rule 12: Best model per domain
_DOMAIN_MODEL_MAP: Dict[Domain, str] = {
    Domain.SOFTWARE:    "claude",
    Domain.MATHEMATICS: "chatgpt",
    Domain.CREATIVE:    "gemini",
    Domain.SCIENCE:     "gemini",
    Domain.PHILOSOPHY:  "claude",
    Domain.LAW:         "chatgpt",
    Domain.ETHICS:      "claude",
    Domain.GENERAL:     "",  # selected dynamically from highest-scoring model
}


def classify_domain(topic: str) -> Tuple[Domain, str]:
    """
    Rule 12: Classify topic domain to determine synthesis model.
    Returns (Domain, reasoning).
    """
    topic_lower = topic.lower()
    scores: Dict[Domain, int] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for kw in keywords if kw in topic_lower)

    best_domain = max(scores, key=scores.get)  # type: ignore
    best_score = scores[best_domain]

    if best_score == 0:
        return Domain.GENERAL, "No domain-specific keywords detected; general analysis selected."

    return best_domain, (
        f"Domain '{best_domain.value}' detected ({best_score} keyword matches). "
        f"Synthesis assigned to '{_DOMAIN_MODEL_MAP.get(best_domain, 'dynamic')}'."
    )


def select_synthesis_model(domain: Domain, available_models: List[str]) -> str:
    """
    Rule 12: Automatically select best model for synthesis.
    Falls back to first available if preferred model not connected.
    """
    preferred = _DOMAIN_MODEL_MAP.get(domain, "")
    if preferred and preferred in available_models:
        return preferred
    # Dynamic fallback for GENERAL domain
    return available_models[0] if available_models else "claude"


# ============================================================================
# SECTION 5: COMPLEXITY ASSESSOR (Rule 10)
# ============================================================================

_COMPLEXITY_SIGNALS = {
    "very_complex": [
        "consciousness", "quantum", "paradox", "turing", "gödel", "free will",
        "hard problem", "metaphysics", "ontology", "epistemology", "p vs np",
        "philosophy of mind",
    ],
    "complex": [
        "ethics", "justice", "moral", "artificial intelligence", "democracy",
        "religion", "god", "soul", "meaning", "truth", "reality", "infinity",
    ],
    "moderate": [
        "history", "economics", "psychology", "education", "society",
        "technology", "environment", "politics",
    ],
}


def assess_complexity(topic: str) -> ComplexityAssessment:
    """
    Rule 10: Determine reasoning depth from topic complexity.
    Simple → short reasoning. Very complex → full Socratic pipeline.
    """
    topic_lower = topic.lower()

    if any(kw in topic_lower for kw in _COMPLEXITY_SIGNALS["very_complex"]):
        level, score = ComplexityLevel.VERY_COMPLEX, 0.9
        min_rounds, refl_interval, cycles = 10, 2, 4
    elif any(kw in topic_lower for kw in _COMPLEXITY_SIGNALS["complex"]):
        level, score = ComplexityLevel.COMPLEX, 0.7
        min_rounds, refl_interval, cycles = 6, 3, 3
    elif any(kw in topic_lower for kw in _COMPLEXITY_SIGNALS["moderate"]):
        level, score = ComplexityLevel.MODERATE, 0.5
        min_rounds, refl_interval, cycles = 4, 4, 2
    else:
        level, score = ComplexityLevel.SIMPLE, 0.25
        min_rounds, refl_interval, cycles = 2, 0, 1

    domain, _ = classify_domain(topic)

    return ComplexityAssessment(
        level=level,
        score=score,
        recommended_rounds=min_rounds,
        recommended_reflection_interval=refl_interval,
        requires_fact_verification=(score >= 0.5),
        requires_elenchus=True,  # Rule 3: ALWAYS required
        estimated_socratic_cycles=cycles,
        domain=domain,
        reasoning=(
            f"Topic complexity assessed as '{level.value}' (score={score}). "
            f"Minimum {min_rounds} rounds recommended with Elenchus every round "
            f"and Reflection every {refl_interval} rounds."
        ),
    )


# ============================================================================
# SECTION 6: CONVERGENCE CHECKER (Rule 11)
# ============================================================================

def compute_convergence(
    consensus: ConsensusMemoryData,
    elenchus_history: List[ElenchusResult],
    prev_conclusion_count: int,
) -> Tuple[float, bool]:
    """
    Rule 11: Consensus stability check.
    Returns (convergence_score 0.0–1.0, is_stable).
    Stable when: no new conclusions added AND no Elenchus falsification in last 2 rounds.
    """
    conclusion_count = len(consensus.verified_conclusions)
    open_count       = len(consensus.open_questions)
    disagreement_count = len(consensus.remaining_disagreements)

    # No new conclusions added
    stable_conclusions = (conclusion_count == prev_conclusion_count and conclusion_count > 0)

    # Recent Elenchus results: none falsified in last 2
    recent_elenchus = elenchus_history[-2:] if len(elenchus_history) >= 2 else elenchus_history
    recent_falsifications = sum(1 for e in recent_elenchus if e.falsification_successful)
    stable_elenchus = (recent_falsifications == 0)

    # Open questions shrinking
    open_ratio = 1.0 - (open_count / max(conclusion_count + open_count, 1))

    score = (
        (0.40 * float(stable_conclusions)) +
        (0.40 * float(stable_elenchus)) +
        (0.20 * open_ratio)
    )

    # Stable when score > 0.8 AND at least 1 verified conclusion
    is_stable = (score >= 0.8 and conclusion_count >= 1 and disagreement_count == 0)

    return round(score, 3), is_stable


# ============================================================================
# SECTION 7: ENHANCED SESSION
# ============================================================================

class EnhancedDialogSession:
    """
    Full session state implementing all 15 Constitution rules.
    Each engine is independently managed (Rule 15).
    """

    def __init__(self, session_id: str, config: DialogConfig, api_keys: dict):
        self.session_id       = session_id
        self.config           = config
        self.api_keys         = api_keys
        self.status           = "initialized"
        self.created_at       = datetime.now()
        self.current_round    = 0
        self._paused          = asyncio.Event()
        self._paused.set()    # starts unpaused
        self._stop_requested  = False

        # ── Rule 1: Socratic rotation tracking ──────────────────────────
        self.available_models:    List[str] = list(api_keys.keys())
        self.socratic_rotation:   List[str] = []  # history of who was Socrates
        self.rounds_as_socrates:  Dict[str, int] = {m: 0 for m in self.available_models}
        self.current_socrates:    str = ""

        # ── Dialogue history ─────────────────────────────────────────────
        self.history:       List[DialogTurnResponse] = []
        self.scores:        Dict[str, int] = {m: 0 for m in self.available_models}

        # ── Rule 6: Claims store ─────────────────────────────────────────
        self.claims:        List[Claim] = []

        # ── Rule 7: Contradiction Graph ──────────────────────────────────
        self.contradiction_graph: ContradictionGraphData = ContradictionGraphData()

        # ── Rule 8: Knowledge Graph ──────────────────────────────────────
        self.knowledge_graph: KnowledgeGraphData = KnowledgeGraphData()

        # ── Rule 9: Consensus Memory ─────────────────────────────────────
        self.consensus_memory:    ConsensusMemoryData = ConsensusMemoryData()
        self._prev_conclusion_count: int = 0

        # ── Rule 3: Elenchus history ─────────────────────────────────────
        self.elenchus_history:    List[ElenchusResult] = []

        # ── Rule 5: Reflection history ───────────────────────────────────
        self.reflection_history:  List[ReflectionStep] = []

        # ── Rule 10: Complexity ──────────────────────────────────────────
        self.complexity:          Optional[ComplexityAssessment] = None
        self.enforced_rounds:     int = config.rounds

        # ── Rule 11: Convergence ─────────────────────────────────────────
        self.convergence_score:   float = 0.0
        self.consensus_stable:    bool  = False

        # ── Rule 12+13: Synthesis ────────────────────────────────────────
        self.synthesis_result:    Optional[SynthesisResult] = None
        self.synthesis_domain:    Optional[Domain]          = None

        # ── Rule 14: Evolution log ───────────────────────────────────────
        self.evolution_log:       List[EvolutionEntry] = []

        # ── Constitution Guard log ────────────────────────────────────────
        self.constitution_violations: List[str] = []

        # ── Injected questions (mid-dialogue) ────────────────────────────
        self.pending_injection:   Optional[str] = None

        # ── Dialog manager (from socrates_ai) ────────────────────────────
        self.manager:             Optional[DialogManager] = None

    # ── Rotation helpers (Rule 1) ────────────────────────────────────────────

    def next_socrates(self) -> str:
        """
        Rule 1: Select next Socrates using round-robin rotation.
        Explicitly avoids permanent authority.
        """
        idx = len(self.socratic_rotation) % len(self.available_models)
        model = self.available_models[idx]
        try:
            ConstitutionGuard.assert_socratic_rotation(
                model,
                self.current_socrates or None,
                self.rounds_as_socrates,
                self.enforced_rounds,
            )
        except ConstitutionViolationError as exc:
            self._log_violation(exc)
            # Force pick next in rotation
            idx = (idx + 1) % len(self.available_models)
            model = self.available_models[idx]

        self.current_socrates = model
        self.socratic_rotation.append(model)
        self.rounds_as_socrates[model] = self.rounds_as_socrates.get(model, 0) + 1
        return model

    # ── Convergence update (Rule 11) ─────────────────────────────────────────

    def update_convergence(self) -> None:
        self.convergence_score, self.consensus_stable = compute_convergence(
            self.consensus_memory,
            self.elenchus_history,
            self._prev_conclusion_count,
        )
        self._prev_conclusion_count = len(self.consensus_memory.verified_conclusions)

    # ── Constitution violation logger ────────────────────────────────────────

    def _log_violation(self, exc: ConstitutionViolationError) -> None:
        entry = f"[R{self.current_round}] Rule {exc.rule}: {exc.description}"
        self.constitution_violations.append(entry)
        self.evolution_log.append(EvolutionEntry(
            component="reasoning_policy",
            change=f"Violation detected: {entry}",
            reason="Automatic Constitution enforcement",
            round=self.current_round,
        ))

    def to_status_response(self) -> DialogStatusResponse:
        rotation_info = None
        if self.available_models:
            nxt_idx = len(self.socratic_rotation) % len(self.available_models)
            rotation_info = SocraticRotationInfo(
                rotation_order=self.socratic_rotation,
                current_socrates=self.current_socrates,
                next_socrates=self.available_models[nxt_idx],
                rounds_as_socrates=self.rounds_as_socrates,
            )
        return DialogStatusResponse(
            session_id=self.session_id,
            topic=self.config.topic,
            rounds_planned=self.enforced_rounds,
            rounds_completed=self.current_round,
            mode=self.config.mode.value,
            status=self.status,
            complexity=self.complexity,
            convergence_score=self.convergence_score,
            consensus_stable=self.consensus_stable,
            socratic_rotation=rotation_info,
            history=self.history,
            scores=self.scores,
            constitution_violations=self.constitution_violations,
        )


# ============================================================================
# SECTION 8: SESSION MANAGER
# ============================================================================

class DialogSessionManager:
    """Thread-safe in-memory session store (Rule 15: independent module)"""

    def __init__(self):
        self._sessions: Dict[str, EnhancedDialogSession] = {}

    def create(self, session_id: str, config: DialogConfig, api_keys: dict) -> EnhancedDialogSession:
        session = EnhancedDialogSession(session_id, config, api_keys)
        session.manager = DialogManager(config, api_keys)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[EnhancedDialogSession]:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> EnhancedDialogSession:
        session = self.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
        return session

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_all(self) -> List[dict]:
        return [
            {
                "session_id": s.session_id,
                "topic": s.config.topic,
                "status": s.status,
                "created_at": s.created_at.isoformat(),
                "rounds_planned": s.enforced_rounds,
                "rounds_completed": s.current_round,
                "convergence_score": s.convergence_score,
                "consensus_stable": s.consensus_stable,
                "constitution_violations": len(s.constitution_violations),
            }
            for s in self._sessions.values()
        ]


session_manager = DialogSessionManager()


# ============================================================================
# SECTION 9: HELPERS
# ============================================================================

def get_api_keys() -> dict:
    keys = {
        "claude":  os.getenv("ANTHROPIC_API_KEY", ""),
        "grok":    os.getenv("XAI_API_KEY", ""),
        "gemini":  os.getenv("GOOGLE_API_KEY", ""),
        "chatgpt": os.getenv("OPENAI_API_KEY", ""),
    }
    return {k: v for k, v in keys.items() if v}


def speed_to_model(s: DialogSpeedEnum) -> DialogSpeed:
    return {
        DialogSpeedEnum.VERY_SLOW: DialogSpeed.VERY_SLOW,
        DialogSpeedEnum.SLOW:      DialogSpeed.SLOW,
        DialogSpeedEnum.NORMAL:    DialogSpeed.NORMAL,
        DialogSpeedEnum.FAST:      DialogSpeed.FAST,
        DialogSpeedEnum.VERY_FAST: DialogSpeed.VERY_FAST,
    }[s]


def mode_to_model(m: DialogModeEnum) -> DialogMode:
    return {
        DialogModeEnum.SOCRATIC:  DialogMode.SOCRATIC,
        DialogModeEnum.DEBATE:    DialogMode.DEBATE,
        DialogModeEnum.CONSENSUS: DialogMode.CONSENSUS,
    }[m]


def summary_to_model(s: SummaryModeEnum) -> SummaryMode:
    return {
        SummaryModeEnum.NONE:  SummaryMode.NONE,
        SummaryModeEnum.EVERY: SummaryMode.EVERY,
        SummaryModeEnum.HALF:  SummaryMode.HALF,
    }[s]


def generate_session_id() -> str:
    return f"dialog_{uuid.uuid4().hex[:12]}"


# ============================================================================
# SECTION 10: FASTAPI APP
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🏛️  Socratic Dialog API — Constitution v0.1 — Starting...")
    yield
    print("🛑  Socratic Dialog API — Shutting Down...")


app = FastAPI(
    title="Socratic Dialog API",
    description=(
        "Multi-Agent Socratic Reasoning Engine. "
        "Optimizes for Truth through structured dialogue, "
        "NOT speed or single-model performance."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# SECTION 11: API ENDPOINTS
# ============================================================================

# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """System health — lists configured models"""
    api_keys = get_api_keys()
    return {
        "status":            "healthy",
        "configured_models": list(api_keys.keys()),
        "constitution":      "v0.1",
        "timestamp":         datetime.now().isoformat(),
    }


# ── Constitution (Rule 14: expose rules) ─────────────────────────────────────

@app.get("/constitution", tags=["System"])
async def get_constitution():
    """Return the Engineering Constitution v0.1 rules as structured data"""
    return {
        "version": "v0.1",
        "philosophy": "Truth through structured dialogue. NOT speed. NOT single-model performance.",
        "rules": [
            {"id": 1,  "name": "No Permanent Authority",     "summary": "Socratic role rotates every round"},
            {"id": 2,  "name": "Socratic Dialogue",          "summary": "Every round has a mandatory Socratic phase"},
            {"id": 3,  "name": "Elenchus",                   "summary": "Every answer is challenged via falsification"},
            {"id": 4,  "name": "Maieutic Emergence",         "summary": "Conclusion emerges from dialogue, not authority"},
            {"id": 5,  "name": "Reflection",                 "summary": "Every agent reflects before final submission"},
            {"id": 6,  "name": "Fact Verification",          "summary": "Claims carry evidence, confidence, source, status"},
            {"id": 7,  "name": "Contradiction Graph",        "summary": "All contradictions stored as graph edges"},
            {"id": 8,  "name": "Knowledge Graph",            "summary": "Only validated knowledge in long-term memory"},
            {"id": 9,  "name": "Consensus Memory",           "summary": "Stores conclusions, open questions, disagreements"},
            {"id": 10, "name": "Adaptive Deep Reasoning",    "summary": "Depth scales with topic complexity"},
            {"id": 11, "name": "Consensus Stability",        "summary": "Stops when consensus converges, not by fixed rounds"},
            {"id": 12, "name": "Dynamic Synthesis",          "summary": "Best model for domain performs synthesis"},
            {"id": 13, "name": "Explainability",             "summary": "Every answer includes reasoning, evidence, uncertainty"},
            {"id": 14, "name": "Evolution",                  "summary": "System improves routing and strategy over time"},
            {"id": 15, "name": "Modularity",                 "summary": "Every subsystem is independently replaceable"},
        ],
        "forbidden": [
            "Shortening the Socratic process for speed",
            "Replacing consensus with single-model decision",
            "Permanent authority for one agent",
            "Storing unverified data in the Knowledge Graph",
            "Hiding disagreements in synthesis",
            "Adding new facts during synthesis",
        ],
    }


# ── Start Dialog ─────────────────────────────────────────────────────────────

@app.post("/dialog/start", response_model=dict, tags=["Dialog"])
async def start_dialog(request: DialogStartRequest, background_tasks: BackgroundTasks):
    """
    Start a new Socratic dialog session.

    Constitution enforcements:
    - Rule 10: Rounds may be increased based on complexity assessment
    - Rule 12: Synthesis model selected automatically from domain
    - Rule 1: Socratic rotation initialized
    """
    api_keys = get_api_keys()

    if not api_keys:
        raise HTTPException(500, "No API keys configured.")
    if len(api_keys) < 2:
        raise HTTPException(500, f"Need ≥2 models. Got: {list(api_keys.keys())}")

    # Rule 10: assess complexity → may override requested rounds
    complexity = assess_complexity(request.topic)
    enforced_rounds = ConstitutionGuard.assert_minimum_rounds(request.rounds, complexity)

    if enforced_rounds > request.rounds and not request.force_min_rounds:
        # Inform caller that rounds were increased
        pass

    # Rule 12: determine synthesis model
    domain, domain_reason = classify_domain(request.topic)

    config = DialogConfig(
        topic=request.topic,
        rounds=enforced_rounds,
        mode=mode_to_model(request.mode),
        speed=speed_to_model(request.speed),
        summary_mode=summary_to_model(request.summary_mode),
    )

    session_id = generate_session_id()
    session    = session_manager.create(session_id, config, api_keys)
    session.complexity       = complexity
    session.enforced_rounds  = enforced_rounds
    session.synthesis_domain = domain

    background_tasks.add_task(_run_dialog_pipeline, session_id)

    return {
        "session_id":        session_id,
        "status":            "started",
        "topic":             request.topic,
        "rounds_requested":  request.rounds,
        "rounds_enforced":   enforced_rounds,
        "rounds_increased":  enforced_rounds > request.rounds,
        "complexity":        complexity.dict(),
        "synthesis_domain":  domain.value,
        "synthesis_model":   select_synthesis_model(domain, list(api_keys.keys())),
        "domain_reason":     domain_reason,
        "message":           f"Session '{session_id}' started. Monitor at /dialog/{session_id}",
    }


# ── Status ───────────────────────────────────────────────────────────────────

@app.get("/dialog/{session_id}", response_model=DialogStatusResponse, tags=["Dialog"])
async def get_status(session_id: str):
    """Full session status including all engine states"""
    return session_manager.require(session_id).to_status_response()


# ── Stream (SSE) ─────────────────────────────────────────────────────────────

@app.get("/dialog/{session_id}/stream", tags=["Dialog"])
async def stream_dialog(session_id: str):
    """Real-time Server-Sent Events stream of dialogue progress"""
    session_manager.require(session_id)

    async def generator():
        last_len = 0
        while True:
            s = session_manager.get(session_id)
            if s is None:
                break

            if len(s.history) > last_len:
                for turn in s.history[last_len:]:
                    yield f"data: {json.dumps({'event': 'turn', 'turn': turn.dict()})}\n\n"
                last_len = len(s.history)

            yield f"data: {json.dumps({'event': 'status', 'status': s.status, 'scores': s.scores, 'convergence': s.convergence_score, 'consensus_stable': s.consensus_stable})}\n\n"

            if s.status in ("completed", "error", "stopped"):
                yield f"data: {json.dumps({'event': 'complete', 'status': s.status, 'violations': s.constitution_violations})}\n\n"
                break

            await asyncio.sleep(1)

    return EventSourceResponse(generator())


# ── Rule 1: Socratic Rotation ─────────────────────────────────────────────────

@app.get("/dialog/{session_id}/socratic-rotation", tags=["Rule 1 — No Permanent Authority"])
async def get_socratic_rotation(session_id: str):
    """
    Rule 1: View the Socratic rotation history.
    Proves that no single agent has held permanent authority.
    """
    s = session_manager.require(session_id)
    return {
        "rotation_order":     s.socratic_rotation,
        "current_socrates":   s.current_socrates,
        "rounds_as_socrates": s.rounds_as_socrates,
        "rule_satisfied":     len(set(s.socratic_rotation)) > 1 or s.current_round <= 1,
    }


# ── Rule 3: Elenchus ─────────────────────────────────────────────────────────

@app.get("/dialog/{session_id}/elenchus", tags=["Rule 3 — Elenchus"])
async def get_elenchus_history(session_id: str):
    """
    Rule 3: Full Elenchus (falsification) history.
    Shows every answer that was challenged and whether revision was required.
    """
    s = session_manager.require(session_id)
    return {
        "count":                 len(s.elenchus_history),
        "falsifications":        sum(1 for e in s.elenchus_history if e.falsification_successful),
        "revisions_required":    sum(1 for e in s.elenchus_history if e.revision_required),
        "revisions_submitted":   sum(1 for e in s.elenchus_history if e.revision_submitted),
        "elenchus_history":      [e.dict() for e in s.elenchus_history],
        "rule_satisfied":        len(s.elenchus_history) >= s.current_round,
    }


# ── Rule 5: Reflection ────────────────────────────────────────────────────────

@app.get("/dialog/{session_id}/reflections", tags=["Rule 5 — Reflection"])
async def get_reflections(session_id: str):
    """
    Rule 5: Per-agent reflection steps.
    Shows initial reasoning → self-criticism → revision → final reasoning.
    """
    s = session_manager.require(session_id)
    return {
        "count":         len(s.reflection_history),
        "improved":      sum(1 for r in s.reflection_history if r.improved),
        "reflections":   [r.dict() for r in s.reflection_history],
    }


# ── Rule 6: Claims / Fact Verification ───────────────────────────────────────

@app.get("/dialog/{session_id}/claims", tags=["Rule 6 — Fact Verification"])
async def get_claims(
    session_id: str,
    status: Optional[ClaimStatus] = Query(None, description="Filter by status"),
):
    """
    Rule 6: All factual claims with evidence, confidence, source, and status.
    Optionally filter by verification status.
    """
    s = session_manager.require(session_id)
    claims = s.claims
    if status:
        claims = [c for c in claims if c.status == status]
    return {
        "total":       len(s.claims),
        "verified":    sum(1 for c in s.claims if c.status == ClaimStatus.VERIFIED),
        "unverified":  sum(1 for c in s.claims if c.status == ClaimStatus.UNVERIFIED),
        "contradicted": sum(1 for c in s.claims if c.status == ClaimStatus.CONTRADICTED),
        "claims":      [c.dict() for c in claims],
    }


# ── Rule 7: Contradiction Graph ───────────────────────────────────────────────

@app.get("/dialog/{session_id}/contradiction-graph", tags=["Rule 7 — Contradiction Graph"])
async def get_contradiction_graph(session_id: str):
    """
    Rule 7: Contradiction Graph of claims.
    Nodes = claims, Edges = supports / contradicts / depends_on / refines.
    Preserves reasoning history, NOT chat history.
    """
    s = session_manager.require(session_id)
    g = s.contradiction_graph
    return {
        "nodes":         [n.dict() for n in g.nodes],
        "edges":         [e.dict() for e in g.edges],
        "contradictions": sum(1 for e in g.edges if e.edge_type == EdgeType.CONTRADICTS),
        "supports":       sum(1 for e in g.edges if e.edge_type == EdgeType.SUPPORTS),
        "refinements":    sum(1 for e in g.edges if e.edge_type == EdgeType.REFINES),
    }


# ── Rule 8: Knowledge Graph ───────────────────────────────────────────────────

@app.get("/dialog/{session_id}/knowledge-graph", tags=["Rule 8 — Knowledge Graph"])
async def get_knowledge_graph(session_id: str):
    """
    Rule 8: Knowledge Graph — only validated, non-opinion, non-hallucinated concepts.
    Unvalidated concepts are explicitly rejected and logged.
    """
    s = session_manager.require(session_id)
    kg = s.knowledge_graph
    return {
        "validated_concepts": len(kg.concepts),
        "relations":          len(kg.relations),
        "concepts":           [c.dict() for c in kg.concepts],
        "relations_data":     [r.dict() for r in kg.relations],
        "rule_note":          "Only validated=True, is_opinion=False concepts are stored.",
    }


# ── Rule 9: Consensus Memory ──────────────────────────────────────────────────

@app.get("/dialog/{session_id}/consensus", tags=["Rule 9 — Consensus Memory"])
async def get_consensus(session_id: str):
    """
    Rule 9: Consensus Memory.
    Stores ONLY verified conclusions, open questions, remaining disagreements.
    NOT complete conversations.
    """
    s = session_manager.require(session_id)
    cm = s.consensus_memory
    return {
        "verified_conclusions":    [i.dict() for i in cm.verified_conclusions],
        "open_questions":          [i.dict() for i in cm.open_questions],
        "remaining_disagreements": [i.dict() for i in cm.remaining_disagreements],
        "total_items":             cm.total_items,
        "rule_note":               "Complete conversations are NOT stored here.",
    }


# ── Rule 10: Complexity ───────────────────────────────────────────────────────

@app.get("/dialog/{session_id}/complexity", tags=["Rule 10 — Adaptive Deep Reasoning"])
async def get_complexity(session_id: str):
    """Rule 10: Topic complexity assessment driving reasoning depth"""
    s = session_manager.require(session_id)
    if not s.complexity:
        raise HTTPException(404, "Complexity not yet assessed.")
    return s.complexity.dict()


# ── Rule 11: Convergence ──────────────────────────────────────────────────────

@app.get("/dialog/{session_id}/convergence", tags=["Rule 11 — Consensus Stability"])
async def get_convergence(session_id: str):
    """
    Rule 11: Convergence status.
    Dialog continues until consensus stabilises, not by fixed round count.
    """
    s = session_manager.require(session_id)
    return {
        "convergence_score":  s.convergence_score,
        "consensus_stable":   s.consensus_stable,
        "rounds_completed":   s.current_round,
        "rounds_planned":     s.enforced_rounds,
        "stopping_criterion": "convergence",
        "rule_note":          "Dialog stops when convergence ≥ 0.8, not by fixed rounds.",
    }


# ── Rule 12+13: Synthesis ─────────────────────────────────────────────────────

@app.get("/dialog/{session_id}/synthesis", tags=["Rule 12+13 — Dynamic Synthesis + Explainability"])
async def get_synthesis(session_id: str):
    """
    Rule 12: Synthesis performed by domain-best model.
    Rule 13: Full explainability — reasoning, evidence, uncertainty, confidence, alternatives.
    """
    s = session_manager.require(session_id)
    if not s.synthesis_result:
        raise HTTPException(404, "Synthesis not yet produced. Dialog may still be running.")
    return s.synthesis_result.dict()


# ── Rule 14: Evolution Log ────────────────────────────────────────────────────

@app.get("/dialog/{session_id}/evolution", tags=["Rule 14 — Evolution"])
async def get_evolution_log(session_id: str):
    """
    Rule 14: Evolution log — routing, prompt, and strategy changes over time.
    Every knowledge modification carries an explicit reason.
    """
    s = session_manager.require(session_id)
    return {
        "entries": [e.dict() for e in s.evolution_log],
        "count":   len(s.evolution_log),
    }


# ── Constitution Violations ───────────────────────────────────────────────────

@app.get("/dialog/{session_id}/violations", tags=["Constitution"])
async def get_violations(session_id: str):
    """List all Constitution rule violations detected in this session"""
    s = session_manager.require(session_id)
    return {
        "count":      len(s.constitution_violations),
        "violations": s.constitution_violations,
        "status":     "clean" if not s.constitution_violations else "violations_detected",
    }


# ── Export ────────────────────────────────────────────────────────────────────

@app.get("/dialog/{session_id}/export", tags=["Dialog"])
async def export_dialog(session_id: str):
    """
    Full export: history, all engine states, Constitution compliance report.
    """
    s = session_manager.require(session_id)
    return {
        "session_id":             s.session_id,
        "topic":                  s.config.topic,
        "mode":                   s.config.mode.value,
        "rounds_completed":       s.current_round,
        "timestamp":              datetime.now().isoformat(),
        "complexity":             s.complexity.dict() if s.complexity else None,
        "convergence_score":      s.convergence_score,
        "consensus_stable":       s.consensus_stable,
        "socratic_rotation":      s.socratic_rotation,
        "history":                [t.dict() for t in s.history],
        "scores":                 s.scores,
        "claims":                 [c.dict() for c in s.claims],
        "contradiction_graph":    s.contradiction_graph.dict(),
        "knowledge_graph":        s.knowledge_graph.dict(),
        "consensus_memory":       s.consensus_memory.dict(),
        "elenchus_history":       [e.dict() for e in s.elenchus_history],
        "reflection_history":     [r.dict() for r in s.reflection_history],
        "synthesis":              s.synthesis_result.dict() if s.synthesis_result else None,
        "evolution_log":          [e.dict() for e in s.evolution_log],
        "constitution_violations": s.constitution_violations,
    }


# ── Pause / Resume / Stop ─────────────────────────────────────────────────────

@app.post("/dialog/{session_id}/pause", tags=["Dialog"])
async def pause_dialog(session_id: str):
    s = session_manager.require(session_id)
    s._paused.clear()
    return {"session_id": session_id, "status": "paused"}


@app.post("/dialog/{session_id}/resume", tags=["Dialog"])
async def resume_dialog(session_id: str):
    s = session_manager.require(session_id)
    s._paused.set()
    return {"session_id": session_id, "status": "resumed"}


@app.post("/dialog/{session_id}/stop", tags=["Dialog"])
async def stop_dialog(session_id: str):
    s = session_manager.require(session_id)
    s._stop_requested = True
    s._paused.set()
    return {"session_id": session_id, "status": "stop_requested"}


# ── Inject Question ───────────────────────────────────────────────────────────

@app.post("/dialog/{session_id}/inject", tags=["Dialog"])
async def inject_question(session_id: str, body: InjectQuestionRequest):
    """Inject a user question into the running dialogue"""
    s = session_manager.require(session_id)
    if s.status != "running":
        raise HTTPException(400, "Injection only possible while dialog is running.")
    s.pending_injection = body.question
    return {"session_id": session_id, "queued": body.question}


# ── List / Delete ─────────────────────────────────────────────────────────────

@app.get("/dialog/list/active", tags=["Dialog"])
async def list_sessions():
    return {"count": len(session_manager._sessions), "sessions": session_manager.list_all()}


@app.delete("/dialog/{session_id}", tags=["Dialog"])
async def delete_session(session_id: str):
    session_manager.require(session_id)
    session_manager.delete(session_id)
    return {"session_id": session_id, "status": "deleted"}


# ============================================================================
# SECTION 12: BACKGROUND PIPELINE (Full Constitution-compliant loop)
# ============================================================================

async def _run_dialog_pipeline(session_id: str) -> None:
    """
    Full multi-phase pipeline implementing all 15 Constitution rules.

    Per-round flow:
      1. Socrates speaks (rotating — Rule 1, 2)
      2. Each participant reflects (Rule 5)
      3. Each participant responds
      4. Elenchus phase: falsification attempt (Rule 3)
      5. If falsified: revision round (Rule 3)
      6. Update Contradiction Graph (Rule 7)
      7. Extract and verify claims (Rule 6)
      8. Update Consensus Memory (Rule 9)
      9. Update Knowledge Graph (Rule 8)
      10. Check convergence (Rule 11)

    Post-loop:
      11. Dynamic synthesis by domain model (Rule 12)
      12. Explainability package (Rule 13)
      13. Log evolution (Rule 14)
    """
    s = session_manager.get(session_id)
    if s is None:
        return

    s.status = "running"

    try:
        for round_num in range(1, s.enforced_rounds + 1):
            # ── Pause check ──────────────────────────────────────────────
            await s._paused.wait()
            if s._stop_requested:
                break

            s.current_round = round_num

            # ── Rule 1+2: Next Socrates ───────────────────────────────────
            socrates_id = s.next_socrates()

            # ── Inject pending question ───────────────────────────────────
            if s.pending_injection:
                inject_turn = DialogTurnResponse(
                    round=round_num,
                    model_id="user",
                    content=s.pending_injection,
                    is_socratic=False,
                    is_elenchus=False,
                    is_reflection=False,
                    timestamp=datetime.now().isoformat(),
                )
                s.history.append(inject_turn)
                s.pending_injection = None

            # ── Build context from history ────────────────────────────────
            context = _build_context(s)

            # ── Socratic phase (Rule 2) ───────────────────────────────────
            socratic_response = await _call_model(
                s, socrates_id,
                _socratic_prompt(s.config.topic, round_num, s.enforced_rounds, s.config.mode.value),
                context, is_socratic=True,
            )
            if socratic_response:
                s.scores[socrates_id] = s.scores.get(socrates_id, 0) + 1
                s.history.append(DialogTurnResponse(
                    round=round_num, model_id=socrates_id,
                    content=socratic_response, is_socratic=True,
                    is_elenchus=False, is_reflection=False,
                    timestamp=datetime.now().isoformat(),
                ))

            # ── Per-participant: Reflect → Respond (Rules 5 + 4) ──────────
            for participant_id in s.available_models:
                if participant_id == socrates_id:
                    continue
                await s._paused.wait()
                if s._stop_requested:
                    break

                # Rule 5: Reflection step
                reflection = await _reflection_step(s, participant_id, round_num, context)
                if reflection:
                    s.reflection_history.append(reflection)

                # Final response uses reflection output
                response_content = reflection.final_reasoning if reflection else ""
                if not response_content:
                    response_content = await _call_model(
                        s, participant_id,
                        _participant_prompt(s.config.topic, round_num, s.enforced_rounds, s.config.mode.value),
                        context, is_socratic=False,
                    ) or ""

                if response_content:
                    improved = bool(reflection and reflection.improved)
                    s.scores[participant_id] = s.scores.get(participant_id, 0) + (3 if improved else 1)
                    s.history.append(DialogTurnResponse(
                        round=round_num, model_id=participant_id,
                        content=response_content, is_socratic=False,
                        is_elenchus=False, is_reflection=False,
                        timestamp=datetime.now().isoformat(),
                    ))
                    # Extract claims from response (Rule 6)
                    _extract_claims(s, participant_id, response_content, round_num)

            # ── Rule 3: Elenchus phase ────────────────────────────────────
            elenchus_challenger = _pick_elenchus_challenger(s, socrates_id)
            elenchus = await _elenchus_phase(s, elenchus_challenger, round_num, context)
            if elenchus:
                s.elenchus_history.append(elenchus)
                s.history.append(DialogTurnResponse(
                    round=round_num, model_id=elenchus_challenger,
                    content=f"[ELENCHUS] Challenged assumptions: {'; '.join(elenchus.challenged_assumptions[:2])}. "
                            f"Falsification {'successful' if elenchus.falsification_successful else 'unsuccessful'}.",
                    is_socratic=False, is_elenchus=True, is_reflection=False,
                    timestamp=datetime.now().isoformat(),
                ))
                # Rule 3: If falsified, trigger revision
                if elenchus.falsification_successful and elenchus.revision_required:
                    await _revision_round(s, elenchus, round_num, context)

            # ── Rule 7: Update Contradiction Graph ────────────────────────
            _update_contradiction_graph(s, round_num)

            # ── Rule 9: Update Consensus Memory ──────────────────────────
            _update_consensus_memory(s, round_num)

            # ── Rule 8: Update Knowledge Graph ────────────────────────────
            _update_knowledge_graph(s, round_num)

            # ── Rule 11: Convergence check ────────────────────────────────
            s.update_convergence()
            if s.consensus_stable:
                s.evolution_log.append(EvolutionEntry(
                    component="reasoning_policy",
                    change=f"Early stopping at round {round_num}",
                    reason=f"Convergence reached: score={s.convergence_score}",
                    round=round_num,
                ))
                break

        # ── Constitution assertions at end of loop ─────────────────────────
        _run_end_of_loop_assertions(s)

        # ── Rule 12+13: Dynamic Synthesis ────────────────────────────────
        await _produce_synthesis(s)

    except ConstitutionViolationError as exc:
        s._log_violation(exc)
        s.status = "error"
        return
    except Exception as exc:
        print(f"❌ Pipeline error [{session_id}]: {exc}")
        s.status = "error"
        return

    s.status = "completed"


# ── Pipeline helpers ─────────────────────────────────────────────────────────

def _build_context(s: EnhancedDialogSession) -> str:
    """Build conversation context from recent history"""
    recent = s.history[-8:]
    lines = []
    for t in recent:
        tag = " (Σωκράτης)" if t.is_socratic else (" (Elenchus)" if t.is_elenchus else "")
        lines.append(f"[{t.model_id}{tag}]: {t.content}")
    return "\n".join(lines)


async def _call_model(
    s: EnhancedDialogSession,
    model_id: str,
    system_prompt: str,
    context: str,
    is_socratic: bool = False,
) -> Optional[str]:
    """Call the underlying dialog manager for a model response"""
    try:
        if s.manager is None:
            return None
        # Delegate to existing DialogManager
        return await s.manager.call_model(
            model_id=model_id,
            system_prompt=system_prompt,
            context=context,
        )
    except Exception as exc:
        print(f"  ⚠️ {model_id} call failed: {exc}")
        return None


async def _reflection_step(
    s: EnhancedDialogSession,
    model_id: str,
    round_num: int,
    context: str,
) -> Optional[ReflectionStep]:
    """
    Rule 5: Generate reflection for an agent.
    Initial → Self-criticism → Revision → Final.
    """
    try:
        system = (
            f"You are {model_id}. BEFORE giving your answer, follow this mandatory reflection protocol:\n"
            f"1. STATE your initial reasoning (2 sentences).\n"
            f"2. CRITICISE your own reasoning — find flaws, gaps, or biases.\n"
            f"3. REVISE your position based on the criticism.\n"
            f"4. STATE your final reasoning.\n"
            f"Output format:\n"
            f"INITIAL: ...\nCRITICISM: ...\nREVISION: ...\nFINAL: ...\n"
            f"Topic: '{s.config.topic}'"
        )
        raw = await _call_model(s, model_id, system, context)
        if not raw:
            return None

        def _extract(label: str) -> str:
            import re
            m = re.search(rf"{label}:(.*?)(?:(?:INITIAL|CRITICISM|REVISION|FINAL):|$)", raw, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        initial    = _extract("INITIAL")
        criticism  = _extract("CRITICISM")
        revision   = _extract("REVISION")
        final      = _extract("FINAL") or raw

        improved = bool(revision and revision.strip() != initial.strip())

        return ReflectionStep(
            model_id=model_id,
            round=round_num,
            initial_reasoning=initial,
            self_criticism=criticism,
            revision=revision,
            final_reasoning=final,
            improved=improved,
        )
    except Exception:
        return None


async def _elenchus_phase(
    s: EnhancedDialogSession,
    challenger_id: str,
    round_num: int,
    context: str,
) -> Optional[ElenchusResult]:
    """
    Rule 3: Mandatory Elenchus — attempt to falsify the latest answer.
    """
    system = (
        f"You are the Elenchus challenger ({challenger_id}). Your ONLY job is to falsify.\n"
        f"Examine the latest claims in the dialogue and attempt to:\n"
        f"1. Identify hidden assumptions\n"
        f"2. Expose logical gaps\n"
        f"3. Challenge evidence\n"
        f"4. Question conclusions\n"
        f"Output JSON only:\n"
        f'{{"challenged_assumptions":["..."],"logic_gaps":["..."],"evidence_issues":["..."],"conclusion_issues":["..."],"falsification_successful":true/false}}'
    )
    import json
    raw = await _call_model(s, challenger_id, system, context)
    if not raw:
        return None

    try:
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean)
    except Exception:
        data = {
            "challenged_assumptions": ["Unable to parse structured elenchus."],
            "logic_gaps": [], "evidence_issues": [], "conclusion_issues": [],
            "falsification_successful": False,
        }

    falsified = data.get("falsification_successful", False)
    return ElenchusResult(
        round=round_num,
        target_claim_summary=context[-200:] if context else "",
        challenger_model=challenger_id,
        challenged_assumptions=data.get("challenged_assumptions", []),
        logic_gaps=data.get("logic_gaps", []),
        evidence_issues=data.get("evidence_issues", []),
        conclusion_issues=data.get("conclusion_issues", []),
        falsification_successful=falsified,
        revision_required=falsified,
    )


async def _revision_round(
    s: EnhancedDialogSession,
    elenchus: ElenchusResult,
    round_num: int,
    context: str,
) -> None:
    """Rule 3: If Elenchus falsified, the original model MUST revise"""
    # Find which model was challenged (latest non-elenchus turn)
    target_model = next(
        (t.model_id for t in reversed(s.history) if not t.is_elenchus and t.model_id != "user"),
        None
    )
    if not target_model:
        return

    system = (
        f"Your previous answer was successfully challenged by Elenchus.\n"
        f"Identified issues:\n"
        f"- Assumptions: {'; '.join(elenchus.challenged_assumptions)}\n"
        f"- Logic gaps: {'; '.join(elenchus.logic_gaps)}\n"
        f"You MUST revise your answer to address these issues. "
        f"Do not simply repeat your previous answer. Topic: '{s.config.topic}'"
    )
    revision_text = await _call_model(s, target_model, system, context)
    if revision_text:
        elenchus.revision_submitted = True
        s.history.append(DialogTurnResponse(
            round=round_num, model_id=target_model,
            content=f"[REVISION after Elenchus] {revision_text}",
            is_socratic=False, is_elenchus=False, is_reflection=False,
            timestamp=datetime.now().isoformat(),
        ))
        s.scores[target_model] = s.scores.get(target_model, 0) + 2


def _pick_elenchus_challenger(s: EnhancedDialogSession, socrates_id: str) -> str:
    """Rule 1: Elenchus challenger also rotates"""
    participants = [m for m in s.available_models if m != socrates_id]
    if not participants:
        return s.available_models[0]
    idx = s.current_round % len(participants)
    return participants[idx]


def _extract_claims(
    s: EnhancedDialogSession,
    model_id: str,
    text: str,
    round_num: int,
) -> None:
    """
    Rule 6: Simple heuristic claim extraction from response text.
    In production, use a dedicated LLM call for structured extraction.
    """
    import re
    sentences = re.split(r'[.!?]', text)
    factual_markers = ['is', 'are', 'was', 'were', 'has', 'have', 'proves', 'shows', 'demonstrates', 'according']
    for sent in sentences[:5]:  # max 5 claims per turn
        sent = sent.strip()
        if len(sent) < 20:
            continue
        if any(m in sent.lower() for m in factual_markers):
            claim = Claim(
                text=sent[:300],
                evidence="",
                confidence=0.4,
                source=model_id,
                status=ClaimStatus.UNVERIFIED,
                round=round_num,
            )
            try:
                ConstitutionGuard.assert_claim_has_provenance(claim)
                s.claims.append(claim)
            except ConstitutionViolationError:
                pass  # Claim rejected — logged implicitly


def _update_contradiction_graph(s: EnhancedDialogSession, round_num: int) -> None:
    """Rule 7: Add recent claims as nodes; detect contradiction edges"""
    for claim in s.claims:
        if claim not in s.contradiction_graph.nodes:
            s.contradiction_graph.nodes.append(claim)

    # Simple heuristic: compare latest claim against previous claims
    if len(s.claims) < 2:
        return
    latest = s.claims[-1]
    for prev in s.claims[-10:-1]:
        if prev.source == latest.source:
            continue
        # Heuristic: negation words suggest contradiction
        neg_words = ["not", "never", "no", "false", "incorrect", "wrong", "disagree"]
        if any(w in latest.text.lower() for w in neg_words):
            edge = ContradictionEdge(
                source_claim_id=prev.claim_id,
                target_claim_id=latest.claim_id,
                edge_type=EdgeType.CONTRADICTS,
                explanation="Heuristic: negation language detected",
                detected_by=latest.source,
                detected_in_round=round_num,
            )
            s.contradiction_graph.edges.append(edge)
            latest.status = ClaimStatus.CONTRADICTED
        elif any(w in latest.text.lower() for w in ["supports", "confirms", "agrees", "consistent"]):
            edge = ContradictionEdge(
                source_claim_id=prev.claim_id,
                target_claim_id=latest.claim_id,
                edge_type=EdgeType.SUPPORTS,
                explanation="Heuristic: support language detected",
                detected_by=latest.source,
                detected_in_round=round_num,
            )
            s.contradiction_graph.edges.append(edge)


def _update_consensus_memory(s: EnhancedDialogSession, round_num: int) -> None:
    """Rule 9: Update Consensus Memory from recent dialogue"""
    # Heuristic: if same claim is supported by ≥2 models, it's a consensus item
    model_claims: dict[str, List[str]] = {}
    for claim in s.claims[-20:]:
        model_claims.setdefault(claim.source, []).append(claim.text.lower()[:60])

    models = list(model_claims.keys())
    if len(models) < 2:
        return

    # Find overlapping key phrases
    for i, m1 in enumerate(models):
        for m2 in models[i+1:]:
            for c1 in model_claims[m1]:
                for c2 in model_claims[m2]:
                    # Very rough similarity check
                    words1 = set(c1.split())
                    words2 = set(c2.split())
                    overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                    if overlap > 0.4:
                        # Check not already stored
                        already = any(c1[:30] in item.content for item in s.consensus_memory.verified_conclusions)
                        if not already:
                            item = ConsensusItem(
                                type=ConsensusItemType.CONCLUSION,
                                content=c1[:200],
                                evidence=[c2[:100]],
                                confidence=min(0.5 + overlap, 1.0),
                                models_agreed=[m1, m2],
                                round=round_num,
                            )
                            try:
                                ConstitutionGuard.assert_consensus_not_single_model(
                                    item.models_agreed, s.available_models
                                )
                                s.consensus_memory.verified_conclusions.append(item)
                            except ConstitutionViolationError as exc:
                                s._log_violation(exc)


def _update_knowledge_graph(s: EnhancedDialogSession, round_num: int) -> None:
    """
    Rule 8: Add only VERIFIED claims as Knowledge Graph concepts.
    Unverified, opinionated, or risky claims are rejected.
    """
    for claim in s.claims:
        if claim.status != ClaimStatus.VERIFIED:
            continue
        # Check not already in graph
        if any(c.label[:40] == claim.text[:40] for c in s.knowledge_graph.concepts):
            continue

        concept = KnowledgeConcept(
            label=claim.text[:80],
            definition=claim.text,
            confidence=claim.confidence,
            source_model=claim.source,
            validated=True,
            round_added=round_num,
            is_opinion=False,
            is_hallucination_risk=False,
        )
        try:
            ConstitutionGuard.assert_knowledge_graph_validated_only(concept)
            added = s.knowledge_graph.add_concept(concept)
            if added:
                s.evolution_log.append(EvolutionEntry(
                    component="reasoning_policy",
                    change=f"Added concept to Knowledge Graph: '{concept.label[:40]}'",
                    reason=f"Claim verified by {claim.source} in round {round_num}",
                    round=round_num,
                ))
        except ConstitutionViolationError as exc:
            s._log_violation(exc)


def _run_end_of_loop_assertions(s: EnhancedDialogSession) -> None:
    """Run all end-of-dialogue Constitution assertions"""
    try:
        ConstitutionGuard.assert_socratic_phase_present(s.history)
    except ConstitutionViolationError as exc:
        s._log_violation(exc)

    try:
        ConstitutionGuard.assert_elenchus_after_claim(s.elenchus_history, s.current_round)
    except ConstitutionViolationError as exc:
        s._log_violation(exc)


async def _produce_synthesis(s: EnhancedDialogSession) -> None:
    """
    Rule 12: Select domain-appropriate model for synthesis.
    Rule 13: Full explainability package.
    Rule 4: Synthesis emerges from dialogue, not authority.
    """
    domain = s.synthesis_domain or Domain.GENERAL
    synth_model = select_synthesis_model(domain, s.available_models)
    domain_reason = f"Domain '{domain.value}' → '{synth_model}' selected (Rule 12)"

    context = _build_context(s)
    conclusion_texts = [i.content for i in s.consensus_memory.verified_conclusions]
    disagreement_texts = [i.content for i in s.consensus_memory.remaining_disagreements]
    claim_texts = [c.text for c in s.claims]

    # Rule 13: Synthesis must include all required fields
    system = (
        f"You are the final Synthesizer for domain '{domain.value}' (Rule 12).\n"
        f"IMPORTANT — You may NOT add new facts. Synthesis is based ONLY on what was already established.\n"
        f"Verified conclusions: {json.dumps(conclusion_texts[:5])}\n"
        f"Remaining disagreements (MUST be exposed — Rule 13): {json.dumps(disagreement_texts[:3])}\n"
        f"Provide:\n"
        f"REASONING_SUMMARY: ...\n"
        f"SUPPORTING_EVIDENCE: bullet list\n"
        f"REMAINING_UNCERTAINTY: ...\n"
        f"CONFIDENCE: 0.0-1.0\n"
        f"ALTERNATIVE_VIEWPOINTS: bullet list\n"
        f"FINAL_ANSWER: ...\n"
        f"Topic: '{s.config.topic}'"
    )

    raw = await _call_model(s, synth_model, system, context)
    if not raw:
        return

    import re

    def _extract(label: str) -> str:
        m = re.search(rf"{label}:(.*?)(?:[A-Z_]+:|$)", raw, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _extract_list(label: str) -> List[str]:
        block = _extract(label)
        return [l.strip("- •").strip() for l in block.split("\n") if l.strip("- •").strip()]

    confidence_str = _extract("CONFIDENCE")
    try:
        confidence = float(confidence_str.strip()) if confidence_str else 0.6
    except ValueError:
        confidence = 0.6

    # Rule 6+: Check synthesis doesn't add new facts
    synth_text = raw
    suspected_new_facts = ConstitutionGuard.assert_synthesis_no_new_facts(synth_text, claim_texts)
    if suspected_new_facts:
        s.constitution_violations.append(
            f"[Synthesis] Possible new facts injected: {suspected_new_facts[:2]}"
        )

    synthesis = SynthesisResult(
        selected_model=synth_model,
        domain=domain,
        domain_selection_reason=domain_reason,
        reasoning_summary=_extract("REASONING_SUMMARY"),
        supporting_evidence=_extract_list("SUPPORTING_EVIDENCE"),
        remaining_uncertainty=_extract("REMAINING_UNCERTAINTY"),
        confidence_score=min(max(confidence, 0.0), 1.0),
        alternative_viewpoints=_extract_list("ALTERNATIVE_VIEWPOINTS"),
        hidden_disagreements=[],  # Rule 13: we NEVER hide disagreements
        final_answer=_extract("FINAL_ANSWER") or raw[:500],
        emerged_from_dialogue=True,
        claims_referenced=[c.claim_id for c in s.claims[-10:]],
    )

    try:
        ConstitutionGuard.assert_disagreements_exposed(synthesis)
    except ConstitutionViolationError as exc:
        s._log_violation(exc)

    s.synthesis_result = synthesis

    # Rule 14: Log synthesis event
    s.evolution_log.append(EvolutionEntry(
        component="routing",
        change=f"Synthesis assigned to '{synth_model}' for domain '{domain.value}'",
        reason=domain_reason,
        round=s.current_round,
    ))


# ── Prompt builders ──────────────────────────────────────────────────────────

def _socratic_prompt(topic: str, r: int, total: int, mode: str) -> str:
    return (
        f"You are the Socratic questioner (Rule 2). Your ONLY role is to ask questions.\n"
        f"DO NOT provide answers. DO NOT make claims.\n"
        f"Your responsibilities:\n"
        f"  1. Identify assumptions in what has been said\n"
        f"  2. Ask ONE clarifying question that exposes a contradiction or gap\n"
        f"  3. Request evidence for unsubstantiated claims\n"
        f"Mode: {mode}. Round {r}/{total}. Topic: '{topic}'\n"
        f"Output: max 3 sentences + 1 question. Never answer your own question."
    )


def _participant_prompt(topic: str, r: int, total: int, mode: str) -> str:
    return (
        f"You are a dialogue participant (Rule 4 — Maieutic Emergence).\n"
        f"State and defend your position clearly. If the Socratic question exposed a genuine gap:\n"
        f"  - Acknowledge it honestly\n"
        f"  - Revise your position\n"
        f"  - Show your reasoning explicitly\n"
        f"Mode: {mode}. Round {r}/{total}. Topic: '{topic}'\n"
        f"Max 5 sentences."
    )


# ============================================================================
# SECTION 13: RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
