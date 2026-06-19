from __future__ import annotations

from typing import Iterable, List

from .models import Claim, ClaimStatus, Contradiction, CurrentBestExplanation


class CurrentBestExplanationEngine:
    def build(
        self,
        question: str,
        claims: Iterable[Claim],
        contradictions: Iterable[Contradiction],
        open_questions: List[str] | None = None,
    ) -> CurrentBestExplanation:
        active = [c for c in claims if c.status not in {ClaimStatus.REJECTED, ClaimStatus.REVISED}]
        strongest = sorted(
            active,
            key=lambda c: (
                c.status in {ClaimStatus.SUPPORTED, ClaimStatus.INTEGRATED},
                c.confidence,
                len(c.evidence_ids),
            ),
            reverse=True,
        )
        unresolved = [c for c in contradictions if not c.resolved]
        if strongest:
            claim_texts = "; ".join(c.text for c in strongest[:3])
            text = f"Provisional answer to '{question}': {claim_texts}"
            confidence = max(0.0, strongest[0].confidence - 0.05 * len(unresolved))
            based_on = [c.claim_id for c in strongest[:3]]
        else:
            text = f"No supported explanation is available yet for '{question}'."
            confidence = 0.0
            based_on = []
        return CurrentBestExplanation(
            text=text,
            based_on_claims=based_on,
            open_questions=open_questions or [],
            unresolved_contradictions=[c.contradiction_id for c in unresolved],
            confidence=confidence,
            provisional=True,
        )

