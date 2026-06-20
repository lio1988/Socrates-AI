"""Evidence-Constrained CBE Composer (Evidence Layer v0.1).

NON-MUTATING. Takes the *raw* Current Best Explanation (exactly what the
existing Socrates/CBE system produced) plus the per-claim evidence audit, and
produces a final, user-facing answer whose *presentation* is constrained by
evidence status. It does NOT change the raw CBE, claim ranking, confidence math,
or any claim/graph state.

    raw_cbe                -> what the system says
    evidence_status(claim) -> what the evidence layer says
    FinalEpistemicAnswer   -> how each claim is ALLOWED to appear

Presentation rules:
    WELL_SUPPORTED   -> eligible for primary_answer
    WEAKLY_SUPPORTED -> tentative / low-confidence only (speculative bucket)
    MISSING          -> hypothesis / open-question / speculative only
    CONTESTED        -> only with an explicit caveat (contested bucket)
    REFUTED          -> never primary; only under refuted_claims

If no claim is WELL_SUPPORTED, the composer refuses to invent a primary answer
and returns a humble no-CBE message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from backend.epistemic.claim import Claim
from backend.epistemic.evidence_scoring import (
    EvidenceStatus,
    evidence_status,
    evidence_summary,
)

NO_SUPPORTED_ANSWER = (
    "No sufficiently supported Current Best Explanation is available from the "
    "current evidence."
)

_AUDIT_NOTE = (
    "Evidence status reflects scripted fixtures only and is a regression signal, "
    "not a truth guarantee."
)


@dataclass
class FinalEpistemicAnswer:
    primary_answer: str
    confidence_label: str
    supported_claims: List[Dict] = field(default_factory=list)
    contested_claims: List[Dict] = field(default_factory=list)
    speculative_claims: List[Dict] = field(default_factory=list)
    refuted_claims: List[Dict] = field(default_factory=list)
    missing_evidence: List[Dict] = field(default_factory=list)
    evidence_summary: Dict = field(default_factory=dict)
    what_would_change_the_answer: List[str] = field(default_factory=list)
    note: str = _AUDIT_NOTE

    def to_dict(self) -> Dict:
        return {
            "primary_answer": self.primary_answer,
            "confidence_label": self.confidence_label,
            "supported_claims": self.supported_claims,
            "contested_claims": self.contested_claims,
            "speculative_claims": self.speculative_claims,
            "refuted_claims": self.refuted_claims,
            "missing_evidence": self.missing_evidence,
            "evidence_summary": self.evidence_summary,
            "what_would_change_the_answer": self.what_would_change_the_answer,
            "note": self.note,
        }


def _ranked_claim_ids(raw_cbe: Dict) -> List[str]:
    """Ordered claim_ids from the raw CBE (ranked first, then strongest),
    de-duplicated, preserving the raw system's ordering."""
    ordered: List[str] = []
    seen = set()
    for key in ("ranked_claims", "strongest_claims"):
        for row in raw_cbe.get(key, []) or []:
            cid = row.get("claim_id") if isinstance(row, dict) else None
            if cid and cid not in seen:
                seen.add(cid)
                ordered.append(cid)
    return ordered


def _claim_brief(claim: Claim, status: EvidenceStatus) -> Dict:
    return {
        "claim_id": claim.claim_id,
        "text": claim.text,
        "evidence_status": status.value,
        "evidence": evidence_summary(claim),
    }


def compose_final_epistemic_answer(
    raw_cbe: Dict, claims_by_id: Dict[str, Claim]
) -> FinalEpistemicAnswer:
    """Compose the evidence-constrained final answer. Pure / non-mutating."""
    # Only describe claims that the raw CBE actually surfaced.
    cbe_ids = [cid for cid in _ranked_claim_ids(raw_cbe) if cid in claims_by_id]

    supported: List[Dict] = []
    contested: List[Dict] = []
    speculative: List[Dict] = []
    refuted: List[Dict] = []
    missing: List[Dict] = []
    status_by_id: Dict[str, EvidenceStatus] = {}

    for cid in cbe_ids:
        claim = claims_by_id[cid]
        status = evidence_status(claim)
        status_by_id[cid] = status
        brief = _claim_brief(claim, status)
        if status == EvidenceStatus.WELL_SUPPORTED:
            supported.append(brief)
        elif status == EvidenceStatus.CONTESTED:
            contested.append(brief)
        elif status == EvidenceStatus.REFUTED:
            refuted.append(brief)
        elif status == EvidenceStatus.MISSING:
            missing.append(brief)
        else:  # WEAKLY_SUPPORTED
            speculative.append(brief)

    # primary_answer: the raw system's best claim that is ALSO well-supported.
    # A REFUTED/CONTESTED/MISSING/WEAK claim can NEVER become the primary answer.
    primary_answer = NO_SUPPORTED_ANSWER
    confidence_label = "insufficient_evidence"
    for cid in cbe_ids:
        if status_by_id.get(cid) == EvidenceStatus.WELL_SUPPORTED:
            claim = claims_by_id[cid]
            primary_answer = claim.text
            bal = evidence_summary(claim)["balance"]
            strong = bal["support_mass"] >= 0.8 and bal["support_quality"] >= 0.8
            confidence_label = "well_supported" if strong else "supported"
            break

    summary = {
        "counts": {
            "supported": len(supported),
            "contested": len(contested),
            "speculative": len(speculative),
            "refuted": len(refuted),
            "missing_evidence": len(missing),
        },
        "has_primary": primary_answer != NO_SUPPORTED_ANSWER,
        "note": _AUDIT_NOTE,
    }

    changes: List[str] = []
    if primary_answer == NO_SUPPORTED_ANSWER:
        changes.append(
            "Strong, uncontested supporting evidence for any candidate claim "
            "would enable a primary answer."
        )
    else:
        changes.append(
            "New contradicting evidence against the primary claim would weaken "
            "or retract it."
        )
    if contested:
        changes.append(
            "Resolving the contradiction on contested claim(s) would change "
            "their standing."
        )
    if refuted:
        changes.append(
            "Refuting the contradicting evidence on refuted claim(s) could "
            "restore them."
        )
    if missing or speculative:
        changes.append(
            "Adding strong independent supporting evidence would upgrade "
            "speculative/unsupported claim(s)."
        )

    return FinalEpistemicAnswer(
        primary_answer=primary_answer,
        confidence_label=confidence_label,
        supported_claims=supported,
        contested_claims=contested,
        speculative_claims=speculative,
        refuted_claims=refuted,
        missing_evidence=missing,
        evidence_summary=summary,
        what_would_change_the_answer=changes,
    )
