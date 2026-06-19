"""Deterministic structured epistemic parser for CED Graph v2.

The parser is intentionally local, dependency-free, and deterministic. It turns a
single agent answer into a structured epistemic analysis that can be written into
the live graph without relying on another model call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re


@dataclass
class ParsedEpistemicAnswer:
    main_claims: list[str] = field(default_factory=list)
    supporting_evidence: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    objections: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    revision_suggestions: list[str] = field(default_factory=list)
    uncertainty_level: str = "medium"
    uncertainty_score: float = 0.5

    def to_dict(self) -> dict:
        return {
            "main_claims": list(self.main_claims),
            "supporting_evidence": list(self.supporting_evidence),
            "assumptions": list(self.assumptions),
            "objections": list(self.objections),
            "contradictions": list(self.contradictions),
            "revision_suggestions": list(self.revision_suggestions),
            "uncertainty_level": self.uncertainty_level,
            "uncertainty_score": self.uncertainty_score,
        }


class StructuredEpistemicParser:
    """Rule-based parser for claim/evidence/assumption/objection structure."""

    VERSION = "v2"

    EVIDENCE_MARKERS = (
        "because",
        "according to",
        "evidence",
        "for example",
        "for instance",
        "data",
        "study",
        "source",
        "observed",
        "since ",
        "therefore",
        "as shown",
        "research",
    )

    ASSUMPTION_MARKERS = (
        "assuming",
        "assumption",
        "if we assume",
        "provided that",
        "depends on",
        "requires that",
        "presupposes",
        "given that",
    )

    OBJECTION_MARKERS = (
        "however",
        "but ",
        "although",
        "objection",
        "counter",
        "challenge",
        "weakness",
        "risk",
        "problem",
        "on the other hand",
    )

    CONTRADICTION_MARKERS = (
        "contradict",
        "inconsistent",
        "cannot both",
        "mutually exclusive",
        "conflicts with",
        "false",
        "incorrect",
        "wrong",
        "disagree",
        "not true",
    )

    REVISION_MARKERS = (
        "revise",
        "revision",
        "update",
        "refine",
        "correct",
        "change this claim",
        "should change",
        "should be changed",
        "should be revised",
        "new evidence",
        "further evidence",
    )

    UNCERTAINTY_HIGH = (
        "maybe",
        "uncertain",
        "unknown",
        "not sure",
        "unclear",
        "might",
        "could",
        "possibly",
        "seems",
        "appears",
        "probably",
    )

    UNCERTAINTY_LOW = (
        "certainly",
        "definitely",
        "clearly",
        "necessarily",
        "must",
        "proven",
    )

    CLAIM_VERBS = (
        " is ",
        " are ",
        " means ",
        " shows ",
        " implies ",
        " suggests ",
        " requires ",
        " becomes ",
        " remains ",
    )

    def parse(self, text: str) -> ParsedEpistemicAnswer:
        sentences = list(self._sentences(text))
        lower_text = self._normalize(text)

        parsed = ParsedEpistemicAnswer(
            main_claims=self._main_claims(sentences),
            supporting_evidence=self._pick(sentences, self.EVIDENCE_MARKERS),
            assumptions=self._pick(sentences, self.ASSUMPTION_MARKERS),
            objections=self._pick(sentences, self.OBJECTION_MARKERS),
            contradictions=self._pick(sentences, self.CONTRADICTION_MARKERS),
            revision_suggestions=self._pick(sentences, self.REVISION_MARKERS),
        )

        parsed.uncertainty_level, parsed.uncertainty_score = self._uncertainty(lower_text)

        return parsed

    def _sentences(self, text: str) -> list[str]:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return []
        parts = re.split(r"(?<=[.!?;])\s+", cleaned)
        return [part.strip()[:420] for part in parts if len(part.strip()) >= 12]

    def _main_claims(self, sentences: list[str]) -> list[str]:
        claims: list[str] = []
        for sentence in sentences:
            lower = f" {sentence.lower()} "
            if any(verb in lower for verb in self.CLAIM_VERBS):
                claims.append(sentence)
            if len(claims) >= 3:
                break

        if not claims and sentences:
            claims.append(sentences[0])

        return claims

    def _pick(self, sentences: list[str], markers: tuple[str, ...], limit: int = 3) -> list[str]:
        picked: list[str] = []
        for sentence in sentences:
            lower = self._normalize(sentence)
            if any(marker in lower for marker in markers):
                picked.append(sentence)
            if len(picked) >= limit:
                break
        return picked

    def _uncertainty(self, lower_text: str) -> tuple[str, float]:
        high_hits = sum(1 for marker in self.UNCERTAINTY_HIGH if marker in lower_text)
        low_hits = sum(1 for marker in self.UNCERTAINTY_LOW if marker in lower_text)

        if high_hits > 0:
            return "high", min(0.95, 0.65 + 0.1 * high_hits)
        if low_hits > 0:
            return "low", max(0.05, 0.25 - 0.05 * low_hits)
        return "medium", 0.5

    def _normalize(self, text: str) -> str:
        return " ".join(text.lower().replace("n't", " not").split())
