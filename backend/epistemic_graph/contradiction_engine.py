from __future__ import annotations

import re
from typing import Iterable, List, Tuple

from .models import Claim, Contradiction


class ContradictionGraphEngine:
    """Deterministic v0 contradiction detector.

    It deliberately avoids embeddings and external model calls so tests remain
    stable. It catches explicit negation/opposition patterns only.
    """

    NEGATION_PATTERNS: Tuple[Tuple[str, str], ...] = (
        (r"\bis\b", r"\bis not\b"),
        (r"\bare\b", r"\bare not\b"),
        (r"\bcan\b", r"\bcannot\b"),
        (r"\bdoes\b", r"\bdoes not\b"),
        (r"\bshould\b", r"\bshould not\b"),
        (r"\btrue\b", r"\bfalse\b"),
        (r"\bprocess\b", r"\bfinal answer\b"),
    )

    def detect(self, claims: Iterable[Claim]) -> List[Contradiction]:
        result: List[Contradiction] = []
        ordered = list(claims)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                reason = self.explain_if_contradiction(a.text, b.text)
                if reason:
                    result.append(Contradiction(a.claim_id, b.claim_id, reason=reason))
        return result

    def explain_if_contradiction(self, text_a: str, text_b: str) -> str:
        a = self._normalize(text_a)
        b = self._normalize(text_b)
        for positive, negative in self.NEGATION_PATTERNS:
            if re.search(positive, a) and re.search(negative, b):
                return f"Explicit opposition: '{positive}' vs '{negative}'."
            if re.search(negative, a) and re.search(positive, b):
                return f"Explicit opposition: '{negative}' vs '{positive}'."
        if a.startswith("not ") and a[4:] in b:
            return "One claim directly negates the other."
        if b.startswith("not ") and b[4:] in a:
            return "One claim directly negates the other."
        return ""

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().replace("n't", " not").split())

