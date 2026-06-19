from __future__ import annotations

from .models import Claim, ClaimStatus


class ClaimRevisionEngine:
    def revise(self, original: Claim, new_text: str, actor: str) -> Claim:
        original.status = ClaimStatus.REVISED
        original.touch()
        revised = Claim(
            text=new_text,
            author_model=actor,
            status=ClaimStatus.SUPPORTED,
            confidence=min(1.0, original.confidence + 0.1),
            evidence_ids=list(original.evidence_ids),
            contradicts=list(original.contradicts),
            supports=list(original.supports),
            revision_of=original.claim_id,
        )
        return revised

