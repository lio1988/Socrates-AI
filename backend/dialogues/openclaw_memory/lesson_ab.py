"""
OpenClaw Memory Lessons — lesson effectiveness A/B harness (Goal 6.1).

Closes the LESSON POISONING gap: until now the lifecycle gated lessons on the
way IN (repeated-only proposals, human curation) but no instrument measured
whether a lesson actually HELPS once it is injected. A bad lesson that passed
the curator would degrade the council invisibly.

Mechanism — a matched-pair experiment per question:

    control   arm: a fresh council WITHOUT the lessons
    treatment arm: an identically-built council WITH the lessons
    SAME question, SAME session id (separate orchestrators), so the ONLY
    difference between the arms is the injected lessons.

Outcomes compared are mechanical council facts: ratification, the mean
peer-score of the assembled sections, and unresolved-section counts. A
treatment arm in which retrieval selected ZERO lessons is counted as
UNTESTED (it cannot show an effect either way) and excluded from deltas.

This implements the lifecycle's missing middle step:

    proposed -> TESTED (this harness) -> verified -> stable

Honesty rules:
  - The harness REPORTS; a human moves the lesson through its lifecycle —
    the same never-auto-promote symmetry as the proposer, the arena, and
    the identity gates.
  - A question where either arm produced no assembled answer is INVALID
    (not a win or loss for the lessons).
  - `helped` requires a positive mean score delta AND zero ratification
    regressions over at least one tested question.

No network, no keys. Live effect requires live providers; with deterministic
mocks the harness verifies mechanics (and rigged test providers verify the
full injection->effect->measurement pipeline).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

AB_SCHEMA_VERSION = "lesson_ab_v0"


def _default_council_factory(openclaw_lessons):
    """Fresh default council (mock unless live-gated). Lazy import keeps this
    module import-clean inside the openclaw_memory package."""
    from backend.dialogues.live_providers import build_council
    from backend.dialogues.models import ShadowScoringMode
    return build_council(council_size=2,
                         shadow_scoring_mode=ShadowScoringMode.OFF,
                         openclaw_lessons=openclaw_lessons)


def _arm_outcome(ced, session_id: str, final) -> Dict[str, Any]:
    """Mechanical outcome facts of one finished arm."""
    state = ced.get_session(session_id)
    assembled = state.assembled_answer
    resolved = ([s for s in assembled.sections if not s.unresolved]
                if assembled is not None else [])
    mean_score = (sum(s.average_score for s in resolved) / len(resolved)
                  if resolved else None)
    openclaw = (final.audit_summary or {}).get("openclaw_lessons") or {}
    return {
        "ratified": bool(final.ratified),
        "mean_section_score": (round(mean_score, 4)
                               if mean_score is not None else None),
        "resolved_sections": len(resolved),
        "unresolved_sections": (len(assembled.sections) - len(resolved)
                                if assembled is not None else 0),
        "lessons_selected": int(openclaw.get("selected_count", 0)),
    }


async def run_lesson_ab(
    questions: Sequence[str],
    lessons: Sequence[Any],
    *,
    council_factory: Optional[Callable[..., Tuple[Any, str]]] = None,
    min_delta: float = 0.0,
) -> Dict[str, Any]:
    """Run the matched-pair lesson experiment and return the mechanical report.

    ``council_factory(openclaw_lessons=...)`` must return ``(ced, mode)``
    (default: ``build_council`` with a 2-seat council). Each question runs the
    control arm (lessons=None) and the treatment arm (lessons=list) on
    separate orchestrators with the SAME session id, so deterministic
    providers make the lessons the only difference.
    """
    if not lessons:
        raise ValueError("run_lesson_ab needs at least one lesson to test")
    factory = council_factory or _default_council_factory

    rows: List[Dict[str, Any]] = []
    deltas: List[float] = []
    untested = invalid = 0
    ratification_gains = ratification_regressions = 0

    for qi, question in enumerate(questions):
        sid = f"lesson_ab_q{qi}"
        ced_control, _ = factory(openclaw_lessons=None)
        final_control = await ced_control.run_registry_session(
            question, session_id=sid)
        ced_treatment, _ = factory(openclaw_lessons=list(lessons))
        final_treatment = await ced_treatment.run_registry_session(
            question, session_id=sid)

        control = _arm_outcome(ced_control, sid, final_control)
        treatment = _arm_outcome(ced_treatment, sid, final_treatment)
        row: Dict[str, Any] = {"question": question, "session_id": sid,
                               "control": control, "treatment": treatment}

        if (control["mean_section_score"] is None
                or treatment["mean_section_score"] is None):
            row.update({"valid": False, "reason": "no_assembly"})
            invalid += 1
        elif treatment["lessons_selected"] == 0:
            # Retrieval picked nothing for this question: the arms are
            # trivially identical — no effect could have been shown.
            row.update({"valid": False, "reason": "no_lessons_selected"})
            untested += 1
        else:
            delta = (treatment["mean_section_score"]
                     - control["mean_section_score"])
            row.update({"valid": True, "score_delta": round(delta, 4)})
            deltas.append(delta)
            if treatment["ratified"] and not control["ratified"]:
                ratification_gains += 1
            elif control["ratified"] and not treatment["ratified"]:
                ratification_regressions += 1
        rows.append(row)

    tested = len(deltas)
    mean_delta = (sum(deltas) / tested) if tested else 0.0
    improved = sum(1 for d in deltas if d > 0)
    worsened = sum(1 for d in deltas if d < 0)
    helped = (tested >= 1
              and mean_delta > min_delta
              and ratification_regressions == 0)
    if tested == 0:
        verdict = "untested"
    elif helped:
        verdict = "helped"
    elif mean_delta < 0 or ratification_regressions > 0:
        verdict = "harmed"
    else:
        verdict = "no_effect"

    return {
        "schema_version": AB_SCHEMA_VERSION,
        "lesson_ids": [getattr(lesson, "lesson_id", str(lesson))
                       for lesson in lessons],
        "min_delta": float(min_delta),
        "questions": rows,
        "tested": tested,
        "untested": untested,
        "invalid": invalid,
        "mean_score_delta": round(mean_delta, 4),
        "improved": improved,
        "worsened": worsened,
        "unchanged": tested - improved - worsened,
        "ratification_gains": ratification_gains,
        "ratification_regressions": ratification_regressions,
        "helped": helped,
        "verdict": verdict,
        "note": "The harness reports; a human moves the lesson through its "
                "lifecycle (proposed -> tested -> verified -> stable).",
    }
