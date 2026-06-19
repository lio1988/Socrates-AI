"""
CED Graph v10 — Socratic Pressure & Practical Answer Quality.

This module does not create new epistemic claims. It pressure-tests an existing
Current Best Explanation and renders it into a practical answer contract:
clear answer, plain explanation, example, objection, uncertainty, and next step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List


QUALITY_VERSION = "v10"

ABSTRACT_MARKERS = (
    "abstract", "dynamic", "emergent", "emergence", "holistic", "framework",
    "paradigm", "process", "epistemic", "ontology", "dialectic", "truth",
    "knowledge", "complex", "multi-layer", "meta", "conceptual",
)

PRACTICAL_MARKERS = (
    "for example", "example", "e.g.", "e.g", "π.χ", "παράδειγμα",
    "when ", "if ", "use ", "check ", "test ", "measure ", "compare ",
)

UNCERTAINTY_MARKERS = (
    "uncertain", "uncertainty", "may", "might", "could", "depends",
    "not final", "current", "tentative", "provisional", "revisable",
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _clean(text: str, limit: int = 420) -> str:
    return " ".join((text or "").split())[:limit]


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?;])\s+", _clean(text, 1200))
    return [p.strip() for p in parts if p.strip()]


def _marker_count(text: str, markers: tuple[str, ...]) -> int:
    lower = (text or "").lower()
    return sum(lower.count(marker) for marker in markers)


def _has_marker(text: str, markers: tuple[str, ...]) -> bool:
    return _marker_count(text, markers) > 0


def socratic_pressure_level(round_number: int | None) -> Dict[str, Any]:
    """Return deterministic pressure instructions for a Socratic round.

    The pressure is aimed at vague answers, not at the user.
    """
    try:
        raw = int(round_number or 1)
    except (TypeError, ValueError):
        raw = 1
    level = max(1, min(5, raw))
    ladder = {
        1: ("understand", "Restate the claim and identify its main assertion."),
        2: ("clarify", "Ask what exactly would make the claim true or false."),
        3: ("challenge", "Attack vague language and unsupported assumptions."),
        4: ("concretize", "Demand a concrete example, counterexample, and practical test."),
        5: ("compress", "Force a direct answer, strongest objection, uncertainty, and next step."),
    }
    stance, instruction = ladder[level]
    return {
        "round": raw,
        "pressure_level": level,
        "pressure_score": round(level / 5, 2),
        "stance": stance,
        "instruction": instruction,
        "targets": [
            "vague claims",
            "unsupported certainty",
            "missing examples",
            "hidden assumptions",
            "unclear practical value",
        ],
    }


@dataclass
class AnswerQualityEvaluation:
    score: float
    level: str
    contract_passed: bool
    contract: Dict[str, bool]
    missing_requirements: List[str]
    penalties: Dict[str, float]
    practical_answer: Dict[str, Any]
    socratic_pressure: Dict[str, Any]
    quality_version: str = QUALITY_VERSION
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality_version": self.quality_version,
            "score": round(self.score, 3),
            "level": self.level,
            "contract_passed": self.contract_passed,
            "contract": self.contract,
            "missing_requirements": self.missing_requirements,
            "penalties": self.penalties,
            "reasons": self.reasons,
        }


class AnswerQualityEngine:
    """Pressure-test a CBE and build a practical user-facing answer skeleton."""

    REQUIRED_CONTRACT_KEYS = (
        "has_direct_answer",
        "has_plain_explanation",
        "has_practical_example",
        "has_strongest_objection",
        "has_uncertainty",
        "has_next_steps",
        "not_over_abstract",
    )

    def evaluate(self, question: str, graph, cbe) -> AnswerQualityEvaluation:
        strongest = list(getattr(cbe, "strongest_claims", []) or [])
        unresolved = list(getattr(cbe, "unresolved_disagreements", []) or [])
        rejected = list(getattr(cbe, "rejected_hypotheses", []) or [])
        confidence = float(getattr(cbe, "confidence", 0.0) or 0.0)

        selected_texts = [_clean(row.get("text", "")) for row in strongest if isinstance(row, dict)]
        all_text = " ".join(selected_texts)
        top_text = selected_texts[0] if selected_texts else ""

        direct_answer = self._direct_answer(top_text)
        plain_explanation = self._plain_explanation(top_text, strongest)
        practical_example = self._practical_example(top_text)
        strongest_objection = self._strongest_objection(unresolved, rejected, top_text)
        uncertainty = self._uncertainty(confidence, unresolved)
        next_steps = self._next_steps()

        abstraction_penalty = self.abstraction_penalty(all_text)
        practicality = self.practicality_score(all_text)

        contract = {
            "has_direct_answer": bool(direct_answer),
            "has_plain_explanation": bool(plain_explanation),
            "has_practical_example": bool(practical_example),
            "has_strongest_objection": bool(strongest_objection),
            "has_uncertainty": bool(uncertainty),
            "has_next_steps": len(next_steps) >= 2,
            "not_over_abstract": abstraction_penalty < 0.30,
        }
        missing = [key for key in self.REQUIRED_CONTRACT_KEYS if not contract[key]]

        weights = {
            "has_direct_answer": 0.18,
            "has_plain_explanation": 0.15,
            "has_practical_example": 0.18,
            "has_strongest_objection": 0.15,
            "has_uncertainty": 0.14,
            "has_next_steps": 0.14,
            "not_over_abstract": 0.06,
        }
        base = sum(weight for key, weight in weights.items() if contract[key])
        score = _clamp(base + (0.10 * practicality) - abstraction_penalty)
        level = self._level(score)
        contract_passed = not missing and score >= 0.65

        practical_answer = {
            "direct_answer": direct_answer,
            "plain_explanation": plain_explanation,
            "practical_example": practical_example,
            "strongest_objection": strongest_objection,
            "uncertainty": uncertainty,
            "next_steps": next_steps,
            "scope": self._scope(question),
            "source_claim_ids": [
                row.get("claim_id") for row in strongest
                if isinstance(row, dict) and row.get("claim_id")
            ],
            "note": "This is a practical rendering of existing graph claims, not a new factual claim.",
        }

        pressure = {
            "quality_version": QUALITY_VERSION,
            "purpose": "Increase pressure on vague answers until the answer becomes usable.",
            "escalation_plan": [socratic_pressure_level(i) for i in range(1, 6)],
            "current_pressure": socratic_pressure_level(5),
            "must_not_accept": [
                "abstract synthesis without example",
                "confidence without uncertainty",
                "agreement without strongest objection",
                "answer without next step",
            ],
        }

        reasons = []
        if abstraction_penalty:
            reasons.append(f"abstraction_penalty:-{round(abstraction_penalty, 3)}")
        if practicality:
            reasons.append(f"practicality:+{round(practicality, 3)}")
        if missing:
            reasons.append("missing:" + ",".join(missing))
        reasons.append("answer_quality_contract:passed" if contract_passed else "answer_quality_contract:needs_revision")

        return AnswerQualityEvaluation(
            score=score,
            level=level,
            contract_passed=contract_passed,
            contract=contract,
            missing_requirements=missing,
            penalties={
                "abstraction_penalty": round(abstraction_penalty, 3),
                "low_practicality_penalty": round(max(0.0, 0.25 - practicality), 3),
            },
            practical_answer=practical_answer,
            socratic_pressure=pressure,
            reasons=reasons,
        )

    def abstraction_penalty(self, text: str) -> float:
        if not text:
            return 0.20
        hits = _marker_count(text, ABSTRACT_MARKERS)
        practical_hits = _marker_count(text, PRACTICAL_MARKERS)
        sentence_count = max(1, len(_sentences(text)))
        raw = min(0.35, (0.035 * hits) / sentence_count)
        relief = min(0.16, 0.04 * practical_hits)
        return round(max(0.0, raw - relief), 3)

    def practicality_score(self, text: str) -> float:
        if not text:
            return 0.0
        score = 0.0
        lower = text.lower()
        if _has_marker(lower, PRACTICAL_MARKERS):
            score += 0.35
        if re.search(r"\b(first|second|third|step|check|test|compare|measure|example)\b", lower):
            score += 0.25
        if re.search(r"\d", text):
            score += 0.10
        if len(_sentences(text)) >= 2:
            score += 0.10
        if _has_marker(lower, UNCERTAINTY_MARKERS):
            score += 0.10
        return round(_clamp(score), 3)

    def _direct_answer(self, top_text: str) -> str:
        if not top_text:
            return "No direct answer can be produced because no selected claim exists yet."
        sentences = _sentences(top_text)
        first_sentence = sentences[0] if sentences else top_text
        return _clean(first_sentence, 260)

    def _plain_explanation(self, top_text: str, strongest: List[Dict[str, Any]]) -> str:
        if not top_text:
            return "The system has not selected a claim strong enough to explain yet."
        sentences = _sentences(top_text)
        if len(sentences) >= 2:
            return _clean(" ".join(sentences[:2]), 360)
        claim_count = len(strongest)
        return _clean(
            f"The current graph prefers this claim among {claim_count} selected candidate(s) because it survived the current scoring and challenge process: {top_text}",
            420,
        )

    def _practical_example(self, top_text: str) -> str:
        if not top_text:
            return "Example: take one claim, ask what evidence supports it, what would contradict it, and what revision would improve it."
        if _has_marker(top_text, PRACTICAL_MARKERS):
            return _clean(top_text, 360)
        return _clean(
            "Practical test: apply the selected claim to one concrete case, then ask what evidence supports it, what objection weakens it, and what would make you revise it.",
            360,
        )

    def _strongest_objection(
        self,
        unresolved: List[Dict[str, Any]],
        rejected: List[Dict[str, Any]],
        top_text: str,
    ) -> str:
        if unresolved:
            row = unresolved[0]
            return _clean(f"Unresolved objection: {row.get('text', '')}", 360)
        if rejected:
            row = rejected[0]
            return _clean(f"Rejected competing hypothesis to keep in mind: {row.get('text', '')}", 360)
        if top_text:
            return "The strongest objection is that the selected claim may still be too broad unless it is tied to evidence, a concrete example, and a condition that could change it."
        return "No objection can be ranked yet because the graph has no selected claim."

    def _uncertainty(self, confidence: float, unresolved: List[Dict[str, Any]]) -> str:
        disagreement = len(unresolved)
        if confidence >= 0.75 and disagreement == 0:
            return "Confidence is high within the current graph, but it remains revisable if stronger evidence or objections appear."
        if confidence >= 0.45:
            return "Confidence is moderate: the answer is useful now, but unresolved objections or limited evidence may still change it."
        return "Confidence is low: treat this as a tentative answer until more evidence, examples, and objections are processed."

    def _next_steps(self) -> List[str]:
        return [
            "Test the answer on one concrete example.",
            "Ask what evidence would strengthen or weaken the selected claim.",
            "Check the strongest objection before treating the answer as reliable.",
        ]

    def _scope(self, question: str) -> Dict[str, str]:
        return {
            "answerable_question": _clean(question, 260),
            "narrowing_rule": "Use only existing graph claims; separate answer, example, objection, uncertainty, and next action.",
        }

    def _level(self, score: float) -> str:
        if score >= 0.80:
            return "strong"
        if score >= 0.65:
            return "usable"
        if score >= 0.45:
            return "weak"
        return "not_useful_yet"
