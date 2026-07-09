"""
OpenClaw Memory Lessons — lesson retriever (Goal 3).

Selects the *few* memory lessons relevant to the current task, so an otherwise
stateless agent can receive focused behavioral guidance — never a full memory
dump, never raw scores, never leaderboard data.

The retriever is a small, fully mechanical relevance scorer. It combines five
independent, auditable signals into a relevance score and returns the top-k:

  1. previous failure tags  (strongest — we KNOW this went wrong before)
  2. rotating role          (e.g. empiricist -> unsupported-claim lessons)
  3. dialogue phase         (e.g. synthesis -> synthesis-quality lessons)
  4. task kind              (e.g. synthesis_draft -> synthesis-quality lessons)
  5. task-text keywords     (curated trigger terms per lesson type)

The mappings below are explicit and reference the real CED enum *values*
(AgentRole / DialogPhase / TaskKind / PenaltyFlag) plus the design-doc role
names from AGENT_PROMPT_BASE.md, so both naming schemes work. Everything is
deterministic: output order is (score desc, lesson_id asc).

Invariants:
  - no provider calls, no API keys, no network
  - no epistemic peer scores or leaderboard data are read or returned
  - result is capped (default 5); an irrelevant query returns nothing rather
    than padding with unrelated lessons
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from .lesson_loader import MemoryLesson, load_stable_lessons

# ── Signal weights (module constants for auditability) ────────────────────────
WEIGHT_FAILURE_TAG: float = 5.0
WEIGHT_ROLE: float = 3.0
WEIGHT_PHASE: float = 2.5
WEIGHT_TASK_KIND: float = 2.5
WEIGHT_KEYWORD: float = 1.0
MAX_KEYWORD_CONTRIBUTION: float = 4.0
DEFAULT_MAX_LESSONS: int = 5

# ── Explicit enum-value -> lesson_type mappings ───────────────────────────────
# AgentRole values + design-doc (AGENT_PROMPT_BASE.md) role names.
ROLE_LESSON_TYPES: dict[str, tuple[str, ...]] = {
    # code enum (backend.dialogues.models.AgentRole)
    "socrates": ("uncertainty_control", "contradiction_detection"),
    "elenchus_critic": ("contradiction_detection", "unsupported_claim"),
    "empiricist": ("unsupported_claim", "contradiction_detection", "uncertainty_control"),
    "maieutic_reconstructor": ("synthesis_quality", "uncertainty_control"),
    "synthesizer": ("synthesis_quality",),
    "reflector": ("uncertainty_control", "unsupported_claim"),
    "final_evaluator": ("ratification_quality",),
    # design-doc / prompt role names
    "thesis_builder": ("unsupported_claim", "uncertainty_control"),
    "evidence_verifier": ("unsupported_claim", "contradiction_detection"),
    "alternative_framer": ("contradiction_detection",),
    "reconstructor": ("synthesis_quality",),
    "ratification_reviewer": ("ratification_quality",),
}

# DialogPhase values.
PHASE_LESSON_TYPES: dict[str, tuple[str, ...]] = {
    "opening": ("uncertainty_control",),
    "initial_response": ("unsupported_claim",),
    "elenchus": ("contradiction_detection", "unsupported_claim"),
    "reflection": ("uncertainty_control",),
    "reconstruction": ("synthesis_quality",),
    "synthesis": ("synthesis_quality",),
    "ratification": ("ratification_quality",),
    # "complete": no lessons
}

# TaskKind values.
TASK_KIND_LESSON_TYPES: dict[str, tuple[str, ...]] = {
    "socratic_question": ("uncertainty_control", "contradiction_detection"),
    "initial_response": ("unsupported_claim",),
    "elenchus_objection": ("contradiction_detection", "unsupported_claim"),
    "reflection_revision": ("uncertainty_control",),
    "reconstruction_proposal": ("synthesis_quality",),
    "synthesis_draft": ("synthesis_quality",),
    "ratification_initial": ("ratification_quality",),
    "ratification_revision": ("ratification_quality",),
    "ratification_final": ("ratification_quality",),
    "council_ratification": ("ratification_quality",),
    "move_score": ("unsupported_claim",),
    "section_score": ("unsupported_claim",),
    "lesson_distillation": ("memory_usage",),
    "process_review": ("memory_usage",),
    "lesson_relevance": ("memory_usage",),
    "lesson_consolidation": ("memory_usage",),
}

# PenaltyFlag values -> the lesson type that addresses that failure.
FAILURE_TAG_LESSON_TYPES: dict[str, tuple[str, ...]] = {
    "unsupported_claim": ("unsupported_claim",),
    "overconfidence": ("uncertainty_control",),
    "missed_uncertainty": ("uncertainty_control",),
    "logical_gap": ("contradiction_detection",),
    "vague": ("exact_output",),
    "rhetorical_fluff": ("exact_output",),
    "schema_violation": ("exact_output",),
    # "irrelevant", "unfair_attack": no clean behavioral-lesson mapping
}

# Curated keyword triggers per lesson type. Morphological variants are listed
# explicitly so matching can stay precise (word-boundary), not fuzzy.
LESSON_TYPE_TRIGGERS: dict[str, tuple[str, ...]] = {
    "exact_output": (
        "exact", "exactly", "verbatim", "token", "letter", "number", "numeric",
        "one word", "single word", "multiple choice", "yes or no", "yes/no",
        "terse", "precise", "precisely", "format", "only",
    ),
    "unsupported_claim": (
        "evidence", "unsupported", "cite", "citation", "source", "sources",
        "grounded", "grounding", "support", "supported", "factual", "fact",
    ),
    "uncertainty_control": (
        "uncertain", "uncertainty", "confidence", "confident", "overconfident",
        "unknown", "insufficient", "ambiguous", "ambiguity", "unclear", "incomplete",
    ),
    "contradiction_detection": (
        "contradiction", "contradict", "contradicts", "conflict", "conflicting",
        "inconsistent", "inconsistency", "disagree", "disagreement", "tension",
    ),
    "synthesis_quality": (
        "synthesis", "synthesize", "synthesise", "assemble", "assembly",
        "section", "sections", "draft", "drafts", "combine", "merge", "compose",
    ),
    "ratification_quality": (
        "ratify", "ratification", "review", "approve", "block", "blocking",
        "objection", "objections", "verdict",
    ),
    "role_rotation": (
        "role", "roles", "rotate", "rotation", "assign", "builder", "critic", "verifier",
    ),
    "memory_usage": (
        "memory", "lesson", "lessons", "retrieval", "retrieve", "recall", "remember",
    ),
    "prompt_patch": (
        "prompt", "patch", "rewrite", "instruction", "template",
    ),
    "provider_behavior": (
        "provider", "model", "api", "timeout", "rate limit",
    ),
}


@dataclass(frozen=True)
class RetrievedLesson:
    """A lesson selected for a task, with its relevance score and match reasons."""

    lesson: MemoryLesson
    score: float
    reasons: tuple[str, ...]

    @property
    def lesson_id(self) -> str:
        return self.lesson.lesson_id

    def to_record(self) -> dict:
        record = self.lesson.to_record()
        record["relevance_score"] = self.score
        record["match_reasons"] = list(self.reasons)
        return record


def _norm(value) -> str:
    """Normalize an enum member or string to its lowercase value string."""
    return str(getattr(value, "value", value)).strip().lower()


def _lesson_trigger_terms(lesson: MemoryLesson) -> tuple[str, ...]:
    terms = set(LESSON_TYPE_TRIGGERS.get(lesson.lesson_type, ()))
    terms.update(phrase.lower() for phrase in lesson.use_when if phrase)
    return tuple(sorted(terms))


def _term_in_text(term: str, text: str) -> bool:
    return re.search(r"\b" + re.escape(term) + r"\b", text) is not None


def score_lesson(
    lesson: MemoryLesson,
    *,
    task_text: str = "",
    phase=None,
    role=None,
    task_kind=None,
    failure_tags: Iterable = (),
) -> tuple[float, list[str]]:
    """Return ``(relevance_score, reasons)`` for one lesson against a task."""
    lesson_type = lesson.lesson_type
    score = 0.0
    reasons: list[str] = []

    for tag in failure_tags:
        norm_tag = _norm(tag)
        if lesson_type in FAILURE_TAG_LESSON_TYPES.get(norm_tag, ()):
            score += WEIGHT_FAILURE_TAG
            reasons.append(f"failure:{norm_tag}->{lesson_type}")

    if role is not None:
        norm_role = _norm(role)
        if lesson_type in ROLE_LESSON_TYPES.get(norm_role, ()):
            score += WEIGHT_ROLE
            reasons.append(f"role:{norm_role}->{lesson_type}")

    if phase is not None:
        norm_phase = _norm(phase)
        if lesson_type in PHASE_LESSON_TYPES.get(norm_phase, ()):
            score += WEIGHT_PHASE
            reasons.append(f"phase:{norm_phase}->{lesson_type}")

    if task_kind is not None:
        norm_kind = _norm(task_kind)
        if lesson_type in TASK_KIND_LESSON_TYPES.get(norm_kind, ()):
            score += WEIGHT_TASK_KIND
            reasons.append(f"task_kind:{norm_kind}->{lesson_type}")

    if task_text:
        text = task_text.lower()
        matched = [term for term in _lesson_trigger_terms(lesson) if _term_in_text(term, text)]
        if matched:
            score += min(len(matched) * WEIGHT_KEYWORD, MAX_KEYWORD_CONTRIBUTION)
            reasons.append("keywords:" + ",".join(matched[:5]))

    return score, reasons


def retrieve_lessons(
    lessons: Sequence[MemoryLesson],
    *,
    task_text: str = "",
    phase=None,
    role=None,
    task_kind=None,
    failure_tags: Iterable = (),
    max_lessons: int = DEFAULT_MAX_LESSONS,
) -> list[RetrievedLesson]:
    """Rank ``lessons`` by relevance and return the top ``max_lessons``.

    Only lessons with a positive score are returned (no unrelated padding).
    Deterministic order: highest score first, ties broken by lesson id.
    """
    if max_lessons <= 0:
        raise ValueError("max_lessons must be positive")

    scored: list[RetrievedLesson] = []
    for lesson in lessons:
        score, reasons = score_lesson(
            lesson,
            task_text=task_text,
            phase=phase,
            role=role,
            task_kind=task_kind,
            failure_tags=failure_tags,
        )
        if score > 0:
            scored.append(RetrievedLesson(lesson=lesson, score=score, reasons=tuple(reasons)))

    scored.sort(key=lambda item: (-item.score, item.lesson.lesson_id))
    return scored[:max_lessons]


def retrieve_for_task(
    *,
    task_text: str = "",
    phase=None,
    role=None,
    task_kind=None,
    failure_tags: Iterable = (),
    max_lessons: int = DEFAULT_MAX_LESSONS,
    lessons: Optional[Sequence[MemoryLesson]] = None,
) -> list[RetrievedLesson]:
    """Retrieve relevant lessons, defaulting to the stable/verified pool.

    High-stakes rule: only ``stable`` / ``verified`` lessons influence runs
    unless the caller passes an explicit ``lessons`` pool.
    """
    pool = lessons if lessons is not None else load_stable_lessons()
    return retrieve_lessons(
        pool,
        task_text=task_text,
        phase=phase,
        role=role,
        task_kind=task_kind,
        failure_tags=failure_tags,
        max_lessons=max_lessons,
    )
