"""
Claim — the central living object of Socrates AI.

The system is claim-centric, not agent-centric. Agents are tools that produce,
challenge and revise claims. A Claim is not a string: it carries its evidence,
contradictions, dependencies and a full revision history, and it enforces its
own lifecycle rules.

Key invariant enforced here (directive §5 + §18):
    A claim may NOT be promoted to KNOWLEDGE unless it has survived at least one
    challenge and reached VERIFIED. The `has_been_challenged` guard makes the
    "HYPOTHESIS -> KNOWLEDGE" shortcut impossible even if some caller tried to
    force it through intermediate states without a real Elenchus.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .epistemic_state import (
    EpistemicState,
    assert_transition,
    IllegalTransition,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str = "claim") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class EvidenceStance(str, Enum):
    """Deterministic stance of a piece of evidence toward a claim.

    SUPPORTING     - backs the claim.
    CONTRADICTING  - undermines the claim.
    WEAK           - relevant but insufficient/inconclusive; does NOT strongly
                     support and does NOT contradict. WEAK evidence must never,
                     on its own, make a claim WELL_SUPPORTED.
    """

    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    WEAK = "weak"


@dataclass
class Evidence:
    evidence_id: str
    summary: str
    source: Optional[str] = None
    quality: float = 0.0          # 0..1, set by the verifier (LEGACY field)
    supports: bool = True         # LEGACY compatibility flag (supports vs. undermines)
    created_at: datetime = field(default_factory=_now)
    # ---- Evidence Layer v0.1 (all optional; fully backward compatible) -------
    # `stance` supersedes `supports` when set (see evidence_scoring.effective_stance).
    stance: Optional[EvidenceStance] = None
    # `strength` optionally overrides `quality` for the audit layer; defaults to quality.
    strength: Optional[float] = None
    source_label: str = "fixture:unspecified"   # provenance label, NOT a verified source
    source_type: str = "testimonial"            # empirical|testimonial|formal|statistical|anecdotal
    verifiable: bool = False                    # v0.1 is fixtures-only -> always False


@dataclass
class RevisionEntry:
    timestamp: datetime
    from_state: Optional[EpistemicState]
    to_state: EpistemicState
    actor: str                    # which agent / engine caused the change
    reason: str
    confidence_before: float
    confidence_after: float


@dataclass
class Claim:
    text: str
    author_model: str
    claim_id: str = field(default_factory=_new_id)
    state: EpistemicState = EpistemicState.HYPOTHESIS
    confidence: float = 0.5
    evidence: List[Evidence] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)   # claim_ids
    dependencies: List[str] = field(default_factory=list)      # claim_ids
    revision_history: List[RevisionEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    # process flags used by the Knowledge Emergence Engine
    has_been_challenged: bool = False
    independent_reviews: int = 0
    stability_under_challenge: int = 0

    # ---- lifecycle -------------------------------------------------------

    def transition(self, to: EpistemicState, actor: str, reason: str) -> None:
        """Move the claim to a new state, validating the transition and
        logging it to revision_history."""
        assert_transition(self.state, to)

        # Hard guard: promotion to KNOWLEDGE requires prior challenge.
        if to == EpistemicState.KNOWLEDGE and not self.has_been_challenged:
            raise IllegalTransition(
                "A claim cannot become KNOWLEDGE without surviving challenge."
            )

        prev = self.state
        self.revision_history.append(
            RevisionEntry(
                timestamp=_now(),
                from_state=prev,
                to_state=to,
                actor=actor,
                reason=reason,
                confidence_before=self.confidence,
                confidence_after=self.confidence,
            )
        )
        self.state = to
        if to == EpistemicState.CHALLENGED:
            self.has_been_challenged = True
        self.updated_at = _now()

    def adjust_confidence(self, new_confidence: float, actor: str, reason: str) -> None:
        new_confidence = max(0.0, min(1.0, new_confidence))
        self.revision_history.append(
            RevisionEntry(
                timestamp=_now(),
                from_state=self.state,
                to_state=self.state,
                actor=actor,
                reason=reason,
                confidence_before=self.confidence,
                confidence_after=new_confidence,
            )
        )
        self.confidence = new_confidence
        self.updated_at = _now()

    def add_evidence(self, ev: Evidence) -> None:
        self.evidence.append(ev)
        self.updated_at = _now()

    def add_contradiction(self, other_claim_id: str) -> None:
        if other_claim_id not in self.contradictions:
            self.contradictions.append(other_claim_id)
            self.updated_at = _now()

    # ---- derived metrics -------------------------------------------------

    @property
    def evidence_quality(self) -> float:
        supporting = [e.quality for e in self.evidence if e.supports]
        if not supporting:
            return 0.0
        return sum(supporting) / len(supporting)

    @property
    def is_active(self) -> bool:
        from .epistemic_state import ACTIVE_STATES
        return self.state in ACTIVE_STATES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "author_model": self.author_model,
            "state": self.state.value,
            "confidence": round(self.confidence, 3),
            "evidence_quality": round(self.evidence_quality, 3),
            "evidence": [
                {
                    "evidence_id": e.evidence_id,
                    "summary": e.summary,
                    "source": e.source,
                    "quality": e.quality,
                    "supports": e.supports,
                }
                for e in self.evidence
            ],
            "contradictions": self.contradictions,
            "dependencies": self.dependencies,
            "has_been_challenged": self.has_been_challenged,
            "independent_reviews": self.independent_reviews,
            "stability_under_challenge": self.stability_under_challenge,
            "revision_count": len(self.revision_history),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
