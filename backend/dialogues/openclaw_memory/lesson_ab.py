"""
OpenClaw Memory Lessons — lesson effectiveness A/B harness (Goal 6.1).

Matched-pair experiment per question:
  control   = fresh council without the candidate lessons
  treatment = identically built council with the candidate lessons
  same question + same session id on separate orchestrators

A lesson is not "helpful" merely because the mean score rose. Coverage and
harm are first-class:
  - a treatment with more unresolved sections is a regression
  - any ratification regression is a veto
  - the tested sample must meet ``min_tested``
  - the per-question harm rate must stay within ``max_harm_rate``

The harness only reports. A human controls lifecycle promotion.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

AB_SCHEMA_VERSION = "lesson_ab_v1"


def _default_council_factory(openclaw_lessons):
    from backend.dialogues.live_providers import build_council
    from backend.dialogues.models import ShadowScoringMode
    return build_council(
        council_size=2,
        shadow_scoring_mode=ShadowScoringMode.OFF,
        openclaw_lessons=openclaw_lessons,
    )


def _arm_outcome(ced, session_id: str, final) -> Dict[str, Any]:
    state = ced.get_session(session_id)
    assembled = state.assembled_answer
    resolved = (
        [section for section in assembled.sections if not section.unresolved]
        if assembled is not None else []
    )
    mean_score = (
        sum(section.average_score for section in resolved) / len(resolved)
        if resolved else None
    )
    openclaw = (final.audit_summary or {}).get("openclaw_lessons") or {}
    return {
        "ratified": bool(final.ratified),
        "mean_section_score": (
            round(mean_score, 4) if mean_score is not None else None),
        "resolved_sections": len(resolved),
        "unresolved_sections": (
            len(assembled.sections) - len(resolved)
            if assembled is not None else 0),
        "lessons_selected": int(openclaw.get("selected_count", 0)),
        "lesson_ids": list(openclaw.get("selected", []) or []),
    }


async def run_lesson_ab(
    questions: Sequence[str],
    lessons: Sequence[Any],
    *,
    council_factory: Optional[Callable[..., Tuple[Any, str]]] = None,
    min_delta: float = 0.0,
    min_tested: int = 1,
    max_harm_rate: float = 0.0,
) -> Dict[str, Any]:
    """Run a matched-pair lesson experiment and return an auditable report.

    ``helped`` requires all of:
      - at least ``min_tested`` valid questions
      - mean score delta greater than ``min_delta``
      - no ratification regression
      - no unresolved-section regression
      - per-question negative-delta rate <= ``max_harm_rate``

    Invalid/no-injection rows never enter the denominator.
    """
    if not lessons:
        raise ValueError("run_lesson_ab needs at least one lesson to test")
    if min_tested < 1:
        raise ValueError("min_tested must be >= 1")
    if not 0.0 <= float(max_harm_rate) <= 1.0:
        raise ValueError("max_harm_rate must be between 0 and 1")

    factory = council_factory or _default_council_factory

    rows: List[Dict[str, Any]] = []
    deltas: List[float] = []
    untested = invalid = 0
    ratification_gains = ratification_regressions = 0
    unresolved_gains = unresolved_regressions = 0

    for question_index, question in enumerate(questions):
        session_id = f"lesson_ab_q{question_index}"

        ced_control, _ = factory(openclaw_lessons=None)
        final_control = await ced_control.run_registry_session(
            question, session_id=session_id)

        ced_treatment, _ = factory(openclaw_lessons=list(lessons))
        final_treatment = await ced_treatment.run_registry_session(
            question, session_id=session_id)

        control = _arm_outcome(ced_control, session_id, final_control)
        treatment = _arm_outcome(ced_treatment, session_id, final_treatment)
        row: Dict[str, Any] = {
            "question": question,
            "session_id": session_id,
            "control": control,
            "treatment": treatment,
        }

        if (control["mean_section_score"] is None
                or treatment["mean_section_score"] is None):
            row.update({"valid": False, "reason": "no_assembly"})
            invalid += 1
        elif treatment["lessons_selected"] == 0:
            row.update({"valid": False, "reason": "no_lessons_selected"})
            untested += 1
        else:
            score_delta = (
                treatment["mean_section_score"]
                - control["mean_section_score"])
            unresolved_delta = (
                treatment["unresolved_sections"]
                - control["unresolved_sections"])
            row.update({
                "valid": True,
                "score_delta": round(score_delta, 4),
                "unresolved_delta": unresolved_delta,
            })
            deltas.append(score_delta)

            if treatment["ratified"] and not control["ratified"]:
                ratification_gains += 1
            elif control["ratified"] and not treatment["ratified"]:
                ratification_regressions += 1

            if unresolved_delta < 0:
                unresolved_gains += 1
            elif unresolved_delta > 0:
                unresolved_regressions += 1

        rows.append(row)

    tested = len(deltas)
    mean_delta = (sum(deltas) / tested) if tested else 0.0
    sorted_deltas = sorted(deltas)
    if not sorted_deltas:
        median_delta = 0.0
    elif tested % 2:
        median_delta = sorted_deltas[tested // 2]
    else:
        middle = tested // 2
        median_delta = (
            sorted_deltas[middle - 1] + sorted_deltas[middle]) / 2.0

    improved = sum(1 for delta in deltas if delta > 0)
    worsened = sum(1 for delta in deltas if delta < 0)
    unchanged = tested - improved - worsened
    harm_rate = (worsened / tested) if tested else 0.0

    helped = (
        tested >= min_tested
        and mean_delta > min_delta
        and ratification_regressions == 0
        and unresolved_regressions == 0
        and harm_rate <= float(max_harm_rate)
    )

    if tested == 0:
        verdict = "untested"
    elif helped:
        verdict = "helped"
    elif (
        mean_delta < 0
        or ratification_regressions > 0
        or unresolved_regressions > 0
        or harm_rate > float(max_harm_rate)
    ):
        verdict = "harmed"
    else:
        verdict = "no_effect"

    return {
        "schema_version": AB_SCHEMA_VERSION,
        "lesson_ids": [
            getattr(lesson, "lesson_id", str(lesson)) for lesson in lessons],
        "min_delta": float(min_delta),
        "min_tested": int(min_tested),
        "max_harm_rate": float(max_harm_rate),
        "questions": rows,
        "tested": tested,
        "untested": untested,
        "invalid": invalid,
        "mean_score_delta": round(mean_delta, 4),
        "median_score_delta": round(median_delta, 4),
        "improved": improved,
        "worsened": worsened,
        "unchanged": unchanged,
        "harm_rate": round(harm_rate, 4),
        "ratification_gains": ratification_gains,
        "ratification_regressions": ratification_regressions,
        "unresolved_gains": unresolved_gains,
        "unresolved_regressions": unresolved_regressions,
        "helped": helped,
        "verdict": verdict,
        "note": (
            "The harness reports; a human moves the lesson through its "
            "lifecycle (proposed -> tested -> verified -> stable)."),
    }
