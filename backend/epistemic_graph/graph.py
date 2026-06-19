from __future__ import annotations

from typing import Dict, List, Optional

from .cbe_engine import CurrentBestExplanationEngine
from .contradiction_engine import ContradictionGraphEngine
from .models import Claim, ClaimStatus, Contradiction, CurrentBestExplanation, EpistemicEvent, Evidence
from .revision_engine import ClaimRevisionEngine


class EpistemicGraph:
    def __init__(self, question: str = "") -> None:
        self.question = question
        self.claims: Dict[str, Claim] = {}
        self.evidence: Dict[str, Evidence] = {}
        self.contradictions: Dict[str, Contradiction] = {}
        self.epistemic_events: List[EpistemicEvent] = []

    def add_claim(self, text: str | Claim, author_model: str | None = None, confidence: float = 0.5) -> Claim:
        claim = text if isinstance(text, Claim) else Claim(text=text, author_model=author_model or "unknown", confidence=confidence)
        self.claims[claim.claim_id] = claim
        self._event("claim_added", f"Claim {claim.claim_id} added.", claim.author_model, claim.claim_id)
        return claim

    def add_evidence(self, claim_id: str, text: str, source: str = "", quality: float = 0.0) -> Evidence:
        if claim_id not in self.claims:
            raise KeyError(f"Unknown claim_id: {claim_id}")
        ev = Evidence(text=text, source=source, quality=quality, supports_claim_id=claim_id)
        self.evidence[ev.evidence_id] = ev
        claim = self.claims[claim_id]
        if ev.evidence_id not in claim.evidence_ids:
            claim.evidence_ids.append(ev.evidence_id)
        if quality > 0:
            claim.status = ClaimStatus.SUPPORTED
            claim.confidence = max(claim.confidence, min(1.0, 0.5 + quality / 2))
        claim.touch()
        self._event("evidence_added", f"Evidence {ev.evidence_id} attached to {claim_id}.", "system", claim_id)
        return ev

    def add_contradiction(self, claim_a: str, claim_b: str, reason: str = "") -> Contradiction:
        if claim_a not in self.claims or claim_b not in self.claims:
            raise KeyError("Both claims must exist before linking a contradiction.")
        con = Contradiction(claim_a=claim_a, claim_b=claim_b, reason=reason)
        self.contradictions[con.contradiction_id] = con
        for left, right in ((claim_a, claim_b), (claim_b, claim_a)):
            claim = self.claims[left]
            if right not in claim.contradicts:
                claim.contradicts.append(right)
            claim.status = ClaimStatus.CONTRADICTED
            claim.touch()
        self._event("contradiction_added", f"Contradiction {con.contradiction_id} linked claims.", "system")
        return con

    def revise_claim(self, claim_id: str, new_text: str, actor: str) -> Claim:
        if claim_id not in self.claims:
            raise KeyError(f"Unknown claim_id: {claim_id}")
        revised = ClaimRevisionEngine().revise(self.claims[claim_id], new_text, actor)
        self.claims[revised.claim_id] = revised
        self._event("claim_revised", f"Claim {claim_id} revised into {revised.claim_id}.", actor, revised.claim_id)
        return revised

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        return self.claims.get(claim_id)

    def list_claims(self) -> List[Claim]:
        return list(self.claims.values())

    def get_active_claims(self) -> List[Claim]:
        return [c for c in self.claims.values() if c.status not in {ClaimStatus.REJECTED, ClaimStatus.REVISED}]

    def detect_contradictions(self) -> List[Contradiction]:
        detected = ContradictionGraphEngine().detect(self.claims.values())
        for con in detected:
            if con.contradiction_id not in self.contradictions:
                self.add_contradiction(con.claim_a, con.claim_b, con.reason)
        return list(self.contradictions.values())

    def build_current_best_explanation(self) -> CurrentBestExplanation:
        return CurrentBestExplanationEngine().build(
            self.question,
            self.claims.values(),
            self.contradictions.values(),
            open_questions=[self.question] if self.question else [],
        )

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "claims": [c.to_dict() for c in self.claims.values()],
            "evidence": [e.to_dict() for e in self.evidence.values()],
            "contradictions": [c.to_dict() for c in self.contradictions.values()],
            "epistemic_events": [e.to_dict() for e in self.epistemic_events],
            "current_best_explanation": self.build_current_best_explanation().to_dict(),
        }

    def _event(self, event_type: str, description: str, actor: str = "system", claim_id: str | None = None) -> None:
        self.epistemic_events.append(EpistemicEvent(event_type=event_type, description=description, actor=actor, claim_id=claim_id))

