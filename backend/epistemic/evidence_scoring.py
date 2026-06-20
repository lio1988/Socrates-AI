"""Evidence Audit Layer (v0.1) -- a *shadow*, read-only scoring pass over the
evidence attached to a Claim.

This layer NEVER mutates claims, NEVER changes ``Claim.evidence_quality`` (which
remains the legacy mean of supporting qualities), and NEVER drives knowledge
promotion. It answers a *different* question from the core engine:

    "Given the evidence attached to this claim, how is the claim ALLOWED to
     appear in the final user-facing answer?"

Two quantities are computed **separately** and must not be conflated:

  * quality - the mean strength of the evidence of a given stance.
  * mass    - a saturating ("noisy-OR") accumulation of evidence strengths.

IMPORTANT (honest framing):
    ``evidence_mass`` is a deterministic *fixture coverage heuristic*. It is NOT
    a probability of truth and it does NOT assume real-world source
    independence. A high mass only means "several/strong fixtures of this stance
    are attached" -- nothing about whether the claim is actually true.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from backend.epistemic.claim import Claim, Evidence, EvidenceStance


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def effective_stance(ev: Evidence) -> EvidenceStance:
    """Stance wins if explicitly set; otherwise fall back to the legacy
    ``supports`` flag (True -> SUPPORTING, False -> CONTRADICTING).

    All Evidence Layer code MUST use this rather than reading ``supports``
    directly."""
    if ev.stance is not None:
        return ev.stance
    return EvidenceStance.SUPPORTING if ev.supports else EvidenceStance.CONTRADICTING


def _strength(ev: Evidence) -> float:
    """Per-evidence strength: ``strength`` overrides ``quality`` when set."""
    val = ev.strength if ev.strength is not None else ev.quality
    return _clamp01(val)


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def saturating_mass(values: List[float]) -> float:
    """Noisy-OR accumulation of strengths in ``[0, 1]``.

    This is NOT a plain sum and NOT a probability of truth -- it is a
    deterministic fixture-coverage heuristic (see module docstring). Two pieces
    at 0.9 and 0.85 give ~0.985, not 1.75 and not a mean of 0.875.
    """
    mass = 0.0
    for v in values:
        v = _clamp01(v)
        mass = 1.0 - ((1.0 - mass) * (1.0 - v))
    return _clamp01(mass)


class EvidenceStatus(str, Enum):
    MISSING = "MISSING"
    WELL_SUPPORTED = "WELL_SUPPORTED"
    CONTESTED = "CONTESTED"
    REFUTED = "REFUTED"
    WEAKLY_SUPPORTED = "WEAKLY_SUPPORTED"


# Thresholds for WELL_SUPPORTED. Both quality AND mass must clear the bar, and
# there must be no contradicting mass at all.
WELL_SUPPORTED_QUALITY = 0.6
WELL_SUPPORTED_MASS = 0.6


@dataclass
class EvidenceBalance:
    support_quality: float
    contra_quality: float
    weak_quality: float
    support_mass: float
    contra_mass: float
    weak_mass: float
    counts: Dict[str, int]

    def to_dict(self) -> Dict:
        return {
            "support_quality": round(self.support_quality, 4),
            "contra_quality": round(self.contra_quality, 4),
            "weak_quality": round(self.weak_quality, 4),
            "support_mass": round(self.support_mass, 4),
            "contra_mass": round(self.contra_mass, 4),
            "weak_mass": round(self.weak_mass, 4),
            "counts": dict(self.counts),
        }


def evidence_balance(claim: Claim) -> EvidenceBalance:
    """Separate *quality* (mean strength) from *mass* (saturating coverage) per
    stance. Read-only; does not mutate the claim."""
    support: List[float] = []
    contra: List[float] = []
    weak: List[float] = []
    for ev in claim.evidence:
        st = effective_stance(ev)
        s = _strength(ev)
        if st == EvidenceStance.SUPPORTING:
            support.append(s)
        elif st == EvidenceStance.CONTRADICTING:
            contra.append(s)
        else:
            weak.append(s)
    return EvidenceBalance(
        support_quality=_mean(support),
        contra_quality=_mean(contra),
        weak_quality=_mean(weak),
        support_mass=saturating_mass(support),
        contra_mass=saturating_mass(contra),
        weak_mass=saturating_mass(weak),
        counts={
            "supporting": len(support),
            "contradicting": len(contra),
            "weak": len(weak),
        },
    )


def evidence_status(claim: Claim) -> EvidenceStatus:
    """Deterministic status from the balance. Read-only.

    Order matters: MISSING first; contradiction-aware statuses (REFUTED /
    CONTESTED) before WELL_SUPPORTED; and WELL_SUPPORTED only when there is no
    contradicting mass at all.
    """
    b = evidence_balance(claim)
    sm, cm, wm = b.support_mass, b.contra_mass, b.weak_mass
    sq, cq = b.support_quality, b.contra_quality

    if sm == 0.0 and cm == 0.0 and wm == 0.0:
        return EvidenceStatus.MISSING
    if cm > 0.0 and sm == 0.0:
        return EvidenceStatus.REFUTED
    if cm > 0.0 and sm > 0.0:
        # Both stances present. Contradiction dominates -> REFUTED, else CONTESTED.
        if cm >= sm and cq >= sq:
            return EvidenceStatus.REFUTED
        return EvidenceStatus.CONTESTED
    # No contradicting mass beyond this point.
    if sm > 0.0 and sq >= WELL_SUPPORTED_QUALITY and sm >= WELL_SUPPORTED_MASS:
        return EvidenceStatus.WELL_SUPPORTED
    return EvidenceStatus.WEAKLY_SUPPORTED


_MASS_NOTE = (
    "evidence_mass is a deterministic fixture-coverage heuristic, not a "
    "probability of truth; it does not assume source independence."
)


def evidence_summary(claim: Claim) -> Dict:
    """Compact, JSON-friendly audit summary for one claim. Read-only."""
    b = evidence_balance(claim)
    status = evidence_status(claim)
    return {
        "claim_id": claim.claim_id,
        "status": status.value,
        "balance": b.to_dict(),
        "sources": [ev.source_label for ev in claim.evidence],
        "note": _MASS_NOTE,
    }
