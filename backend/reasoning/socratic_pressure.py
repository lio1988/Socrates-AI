"""
CED Graph v10.1 — Socratic Pressure & Scope Narrowing Engine.

Pure, deterministic, offline. No API calls, no LLM calls, no randomness.

This engine makes Socrates progressively stricter across rounds against vague,
abstract, generic answers. It does not insult the user or any model; it raises
the intellectual bar. A response is only acceptable as strong knowledge when it
has all six pillars:

    1. a direct answer
    2. a narrowed scope
    3. an operational criterion
    4. a practical example
    5. a strongest objection
    6. an uncertainty boundary
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List


PRESSURE_VERSION = "v10.1"

# Pressure escalates with the round number.
PRESSURE_ORDER = ("mild", "focused", "firm", "strict", "final_gate")

# --- marker vocabularies (lowercase) ---------------------------------------
VAGUE_PHRASES = (
    "it depends", "complex", "dynamic process", "multifaceted", "various factors",
    "in some sense", "arguably", "generally speaking", "context-dependent",
    "context dependent", "a lot of factors", "many factors", "hard to say",
    "it's complicated", "it is complicated", "on many levels", "holistic",
)

EXAMPLE_MARKERS = (
    "for example", "for instance", "e.g.", "e.g", "such as", "consider the case",
    "imagine", "in practice", "real-world", "real world", "use case",
    "application", "παράδειγμα", "π.χ", "take the case", "case where",
)

OPERATIONAL_MARKERS = (
    "we treat", "we consider", "we count", "counts as", "count as", "if and only if",
    "iff", "criterion", "survives", "survive", "test for", "measured by",
    "defined as", "we accept", "we reject", "passes", "verified", "operational",
    "the rule is", "we say", "qualifies as", "threshold",
)

NARROW_MARKERS = (
    "only when", "specifically", "in particular", "the case where", "counts as",
    "we treat", "if and only if", "iff", "under the condition", "restricted to",
    "narrow", "precisely", "in the sense that", "limited to", "the question of whether",
)

BROAD_MARKERS = (
    "everything", "always", "in general", "broadly", "all of", "universally",
    "in every case", "for all", "anything", "everyone", "no matter what",
)

OBJECTION_MARKERS = (
    "strongest objection", "objection", "however", "but ", "on the other hand",
    "critics", "one might argue", "one could argue", "counterargument",
    "could be challenged", "fails when", "unless", "the problem is",
    "a weakness is", "the risk is", "you might object",
)

UNCERTAINTY_MARKERS = (
    "uncertain", "uncertainty", "unknown", "may ", "might ", "could change",
    "would change", "depends on", "provisional", "revisable", "tentative",
    "not certain", "what could change", "limits", "boundary", "open question",
    "we don't know", "we do not know", "remains unclear", "overturn", "could be wrong",
)


# --- low-level helpers ------------------------------------------------------

def normalize_answer_text(text: str) -> str:
    """Lowercase and collapse whitespace. Deterministic."""
    return " ".join((text or "").split()).strip().lower()


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?;])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _marker_count(text: str, markers) -> int:
    return sum(text.count(m) for m in markers)


def _has_marker(text: str, markers) -> bool:
    return _marker_count(text, markers) > 0


def _has_example(text: str) -> bool:
    return _has_marker(text, EXAMPLE_MARKERS)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


# --- scoring functions ------------------------------------------------------
# Convention: every "*_score" is in [0, 1] and HIGHER IS BETTER, EXCEPT
# vagueness_score where HIGHER IS MORE VAGUE (i.e. higher pressure / worse).

def score_vagueness(text: str) -> float:
    """Higher = more vague/abstract = more Socratic pressure."""
    norm = normalize_answer_text(text)
    if not norm:
        return 1.0  # empty answers are maximally vague / unusable
    vague_hits = _marker_count(norm, VAGUE_PHRASES)
    score = min(0.6, 0.2 * vague_hits)
    if not _has_example(norm):
        score += 0.2
    if not _has_marker(norm, OPERATIONAL_MARKERS):
        score += 0.2
    return round(_clamp(score), 3)


def score_directness(question: str, answer: str) -> float:
    """Higher = more directly addresses the question."""
    q = normalize_answer_text(question)
    a = normalize_answer_text(answer)
    if not a:
        return 0.0
    q_terms = {w for w in re.findall(r"[a-zα-ω]+", q) if len(w) > 3}
    a_terms = set(re.findall(r"[a-zα-ω]+", a))
    overlap = (len(q_terms & a_terms) / len(q_terms)) if q_terms else 0.0
    score = 0.5 * overlap
    first = _sentences(a)[0] if _sentences(a) else a
    if any(first.startswith(p) for p in ("well", "it depends", "arguably", "generally speaking")):
        score -= 0.1
    if re.search(r"\b(is|are|means|no,|yes,|we treat|we define|i claim)\b", a):
        score += 0.3
    if _has_marker(a, OPERATIONAL_MARKERS) or _has_example(a):
        score += 0.2
    return round(_clamp(score), 3)


def score_scope_fit(question: str, answer: str) -> float:
    """Higher = narrows the question into an answerable scope."""
    a = normalize_answer_text(answer)
    if not a:
        return 0.0
    score = min(0.6, 0.2 * _marker_count(a, NARROW_MARKERS))
    score -= min(0.3, 0.15 * _marker_count(a, BROAD_MARKERS))
    if _has_example(a):
        score += 0.2
    return round(_clamp(score), 3)


def score_operational_clarity(answer: str) -> float:
    """Higher = provides a working criterion, not just an abstraction."""
    a = normalize_answer_text(answer)
    if not a:
        return 0.0
    score = min(0.8, 0.3 * _marker_count(a, OPERATIONAL_MARKERS))
    if re.search(r"\bwhen\b[^.]*\b(surviv|pass|confirm|hold|true|false)", a):
        score += 0.2
    return round(_clamp(score), 3)


def score_practical_grounding(answer: str) -> float:
    """Higher = concrete example / use case / real-world application."""
    a = normalize_answer_text(answer)
    if not a:
        return 0.0
    score = 0.0
    if _has_example(a):
        score += 0.5
    score += min(0.3, 0.15 * _marker_count(a, EXAMPLE_MARKERS))
    if re.search(r"\d", a):
        score += 0.1
    if len(_sentences(a)) >= 2 and _has_example(a):
        score += 0.1
    return round(_clamp(score), 3)


def score_objection_strength(answer: str) -> float:
    """Higher = a real strongest objection; weak/empty objections score low."""
    a = normalize_answer_text(answer)
    if not a:
        return 0.0
    score = min(0.7, 0.3 * _marker_count(a, OBJECTION_MARKERS))
    if re.search(r"objection\b[^.]*\b(is|that|because)\b", a) or "on the other hand" in a:
        score += 0.3
    return round(_clamp(score), 3)


def score_uncertainty_calibration(answer: str) -> float:
    """Higher = states what is known, what is uncertain, and what could change."""
    a = normalize_answer_text(answer)
    if not a:
        return 0.0
    score = min(0.7, 0.3 * _marker_count(a, UNCERTAINTY_MARKERS))
    if re.search(r"could change|would change|overturn|if .*(then|appears|emerges)", a):
        score += 0.3
    return round(_clamp(score), 3)


# --- aggregation ------------------------------------------------------------

def _all_scores(question: str, answer: str) -> Dict[str, float]:
    return {
        "vagueness": score_vagueness(answer),
        "directness": score_directness(question, answer),
        "scope_fit": score_scope_fit(question, answer),
        "operational_clarity": score_operational_clarity(answer),
        "practical_grounding": score_practical_grounding(answer),
        "objection_strength": score_objection_strength(answer),
        "uncertainty_calibration": score_uncertainty_calibration(answer),
    }


def compute_pressure_level(round_number, scores: Dict[str, float] | None = None) -> str:
    """Pressure increases with round number. Scores may only escalate, never relax."""
    try:
        raw = int(round_number)
    except (TypeError, ValueError):
        raw = 1
    rank = max(1, raw)
    if rank >= 5:
        return "final_gate"
    level = PRESSURE_ORDER[rank - 1]
    # A very vague answer can push the stance one notch firmer (never softer).
    if scores and scores.get("vagueness", 0.0) >= 0.6:
        idx = min(len(PRESSURE_ORDER) - 1, PRESSURE_ORDER.index(level) + 1)
        level = PRESSURE_ORDER[idx]
    return level


def identify_required_repairs(scores: Dict[str, float]) -> List[str]:
    repairs: List[str] = []
    if scores["directness"] < 0.5:
        repairs.append("provide_direct_answer")
    if scores["scope_fit"] < 0.5:
        repairs.append("narrow_scope")
    if scores["operational_clarity"] < 0.5:
        repairs.append("define_operational_criterion")
    if scores["practical_grounding"] < 0.5:
        repairs.append("add_practical_example")
    if scores["objection_strength"] < 0.5:
        repairs.append("add_strongest_objection")
    if scores["uncertainty_calibration"] < 0.5:
        repairs.append("state_uncertainty")
    if scores["vagueness"] >= 0.5 and "define_operational_criterion" not in repairs:
        repairs.append("define_operational_criterion")
    return repairs


def _weaknesses(scores: Dict[str, float]) -> List[str]:
    out: List[str] = []
    if scores["vagueness"] >= 0.5:
        out.append("Answer is too vague or abstract.")
    if scores["directness"] < 0.5:
        out.append("Answer does not directly address the question.")
    if scores["scope_fit"] < 0.5:
        out.append("Scope is too broad; the question was not narrowed.")
    if scores["operational_clarity"] < 0.5:
        out.append("No working/operational criterion was given.")
    if scores["practical_grounding"] < 0.5:
        out.append("No concrete example or real-world grounding.")
    if scores["objection_strength"] < 0.5:
        out.append("No strong objection or counterargument was raised.")
    if scores["uncertainty_calibration"] < 0.5:
        out.append("Uncertainty and what could change are not stated.")
    return out


def build_socratic_challenge(question: str, answer: str,
                             scores: Dict[str, float], round_number) -> str:
    """Produce the next Socratic challenge. Stricter by round, never insulting."""
    level = compute_pressure_level(round_number, scores)
    repairs = identify_required_repairs(scores)

    prefix = {
        "mild": "Let's clarify before going further: ",
        "focused": "Be more precise here: ",
        "firm": "This still isn't sharp enough. ",
        "strict": "I can't accept this as knowledge yet. ",
        "final_gate": "Final gate before this counts as knowledge. ",
    }[level]

    demand_map = {
        "provide_direct_answer": "state a direct answer to the question instead of talking around it",
        "narrow_scope": "narrow the question to a scope you can actually answer",
        "define_operational_criterion": "give a working criterion — when exactly does this hold?",
        "add_practical_example": "ground it in one concrete example",
        "add_strongest_objection": "state the strongest objection against your own answer",
        "state_uncertainty": "say what is uncertain and what could change the conclusion",
    }
    targets = [demand_map[r] for r in repairs if r in demand_map]

    if not targets:
        body = ("Defend why this should count as knowledge: what evidence, objection, "
                "and revision has it already survived?")
    else:
        # Later rounds demand more repairs at once.
        demand_count = {"mild": 1, "focused": 1, "firm": 2, "strict": 3}.get(level, len(targets))
        chosen = targets[:max(1, demand_count)]
        body = "You must " + "; ".join(chosen) + "."

    return prefix + body


# --- report -----------------------------------------------------------------

@dataclass
class SocraticPressureReport:
    pressure_version: str
    round_number: int
    pressure_level: str
    vagueness_score: float
    directness_score: float
    scope_fit_score: float
    operational_clarity_score: float
    practical_grounding_score: float
    objection_strength_score: float
    uncertainty_calibration_score: float
    weaknesses: List[str]
    required_repairs: List[str]
    next_socratic_challenge: str
    can_accept_answer: bool = False

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def should_accept_answer(report: SocraticPressureReport) -> bool:
    """An answer is acceptable only if it is non-vague and has all six pillars.

    The vagueness tolerance tightens at later rounds, and a missing objection /
    operational criterion / practical grounding blocks acceptance — especially at
    the later, stricter rounds.
    """
    if report.vagueness_score >= 0.6:
        return False
    pillars = (
        report.directness_score >= 0.5,
        report.scope_fit_score >= 0.5,
        report.operational_clarity_score >= 0.5,
        report.practical_grounding_score >= 0.5,
        report.objection_strength_score >= 0.5,
        report.uncertainty_calibration_score >= 0.5,
    )
    if not all(pillars):
        return False
    order = PRESSURE_ORDER.index(report.pressure_level)
    max_vagueness = 0.4 if order < 3 else 0.3  # strict / final_gate are tighter
    return report.vagueness_score < max_vagueness


def evaluate_answer_pressure(question: str, answer: str, round_number) -> SocraticPressureReport:
    """Main public function: evaluate an answer under Socratic pressure."""
    scores = _all_scores(question, answer)
    level = compute_pressure_level(round_number, scores)
    try:
        rnd = int(round_number)
    except (TypeError, ValueError):
        rnd = 1

    report = SocraticPressureReport(
        pressure_version=PRESSURE_VERSION,
        round_number=rnd,
        pressure_level=level,
        vagueness_score=scores["vagueness"],
        directness_score=scores["directness"],
        scope_fit_score=scores["scope_fit"],
        operational_clarity_score=scores["operational_clarity"],
        practical_grounding_score=scores["practical_grounding"],
        objection_strength_score=scores["objection_strength"],
        uncertainty_calibration_score=scores["uncertainty_calibration"],
        weaknesses=_weaknesses(scores),
        required_repairs=identify_required_repairs(scores),
        next_socratic_challenge=build_socratic_challenge(question, answer, scores, round_number),
    )
    report.can_accept_answer = should_accept_answer(report)
    return report
