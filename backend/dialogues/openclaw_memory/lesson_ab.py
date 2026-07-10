"""
OpenClaw Memory Lessons — lesson effectiveness A/B harness (Goal 6.1).

Each question runs two fresh, matched councils:
  control   = without candidate lessons
  treatment = with candidate lessons

Evidence rules:
  - same question and session id, separate orchestrators
  - arm execution order is counterbalanced across questions
  - execution mode and configured available-provider set must match
  - no-injection treatment rows are UNTESTED
  - treatment assembly collapse after real injection is catastrophic HARM,
    not an INVALID row that disappears from the verdict
  - positive mean alone is insufficient: ratification, coverage, sample size,
    and per-question harm veto false improvement

The harness reports; a human controls lifecycle promotion.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

AB_SCHEMA_VERSION = "lesson_ab_v2"


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
    audit = final.audit_summary or {}
    openclaw = audit.get("openclaw_lessons") or {}
    provider_status = audit.get("provider_status_summary") or {}
    return {
        "ratified": bool(final.ratified),
        "mean_section_score": (
            round(mean_score, 4) if mean_score is not None else None),
        "resolved_sections": len(resolved),
        "unresolved_sections": (
            len(assembled.sections) - len(resolved)
            if assembled is not None else 0),
        "has_assembly": assembled is not None and bool(resolved),
        "lessons_selected": int(openclaw.get("selected_count", 0)),
        "lesson_ids": list(openclaw.get("selected", []) or []),
        "available_providers": sorted(
            str(provider_id)
            for provider_id in provider_status.get("available_providers", [])
        ),
        "unavailable_providers": sorted(
            str(provider_id)
            for provider_id in provider_status.get("unavailable_providers", [])
        ),
    }


async def _execute_arm(factory, lessons, question: str, session_id: str):
    ced, mode = factory(openclaw_lessons=lessons)
    final = await ced.run_registry_session(question, session_id=session_id)
    return ced, str(mode), final


def _configuration_mismatch(
    control_mode: str,
    treatment_mode: str,
    control: Dict[str, Any],
    treatment: Dict[str, Any],
) -> Optional[str]:
    if control_mode != treatment_mode:
        return "execution_mode_mismatch"
    control_available = control.get("available_providers")
    treatment_available = treatment.get("available_providers")
    if (
        control_available is not None
        and treatment_available is not None
        and control_available != treatment_available
    ):
        return "available_provider_set_mismatch"
    return None


async def run_lesson_ab(
    questions: Sequence[str],
    lessons: Sequence[Any],
    *,
    council_factory: Optional[Callable[..., Tuple[Any, str]]] = None,
    min_delta: float = 0.0,
    min_tested: int = 1,
    max_harm_rate: float = 0.0,
    counterbalance: bool = True,
) -> Dict[str, Any]:
    """Run a conservative matched-pair lesson experiment.

    ``helped`` requires:
      - enough comparable score rows
      - positive mean delta above threshold
      - no ratification regression
      - no unresolved-section regression
      - no catastrophic treatment collapse
      - harm rate within the configured bound

    Operationally incomparable arms are invalid, never forced into a verdict.
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
    catastrophic_regressions = 0
    configuration_mismatches = 0

    for question_index, question in enumerate(questions):
        session_id = f"lesson_ab_q{question_index}"
        treatment_first = bool(counterbalance and question_index % 2 == 1)
        arm_order = ["treatment", "control"] if treatment_first \
            else ["control", "treatment"]

        results: Dict[str, Tuple[Any, str, Any]] = {}
        for arm in arm_order:
            arm_lessons = list(lessons) if arm == "treatment" else None
            results[arm] = await _execute_arm(
                factory, arm_lessons, question, session_id)

        ced_control, control_mode, final_control = results["control"]
        ced_treatment, treatment_mode, final_treatment = results["treatment"]
        control = _arm_outcome(ced_control, session_id, final_control)
        treatment = _arm_outcome(ced_treatment, session_id, final_treatment)

        row: Dict[str, Any] = {
            "question": question,
            "session_id": session_id,
            "arm_order": arm_order,
            "control_mode": control_mode,
            "treatment_mode": treatment_mode,
            "control": control,
            "treatment": treatment,
        }

        mismatch = _configuration_mismatch(
            control_mode, treatment_mode, control, treatment)
        if mismatch:
            row.update({"valid": False, "reason": mismatch})
            invalid += 1
            configuration_mismatches += 1
            rows.append(row)
            continue

        if treatment["lessons_selected"] == 0:
            row.update({"valid": False, "reason": "no_lessons_selected"})
            untested += 1
            rows.append(row)
            continue

        control_has = bool(control.get("has_assembly",
                                       control["mean_section_score"] is not None))
        treatment_has = bool(treatment.get(
            "has_assembly", treatment["mean_section_score"] is not None))

        if control_has and not treatment_has:
            row.update({
                "valid": True,
                "reason": "treatment_no_assembly",
                "catastrophic_regression": True,
            })
            catastrophic_regressions += 1
            if control["ratified"] and not treatment["ratified"]:
                ratification_regressions += 1
            rows.append(row)
            continue

        if not control_has and treatment_has:
            row.update({
                "valid": False,
                "reason": "control_no_assembly",
            })
            invalid += 1
            rows.append(row)
            continue

        if not control_has and not treatment_has:
            row.update({
                "valid": False,
                "reason": "neither_arm_assembled",
            })
            invalid += 1
            rows.append(row)
            continue

        score_delta = (
            treatment["mean_section_score"] - control["mean_section_score"])
        unresolved_delta = (
            treatment["unresolved_sections"] - control["unresolved_sections"])
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
    harm_denominator = tested + catastrophic_regressions
    harm_rate = (
        (worsened + catastrophic_regressions) / harm_denominator
        if harm_denominator else 0.0
    )

    helped = (
        tested >= min_tested
        and mean_delta > min_delta
        and ratification_regressions == 0
        and unresolved_regressions == 0
        and catastrophic_regressions == 0
        and harm_rate <= float(max_harm_rate)
    )

    if catastrophic_regressions > 0:
        verdict = "harmed"
    elif tested == 0:
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
        "counterbalance": bool(counterbalance),
        "questions": rows,
        "tested": tested,
        "untested": untested,
        "invalid": invalid,
        "configuration_mismatches": configuration_mismatches,
        "catastrophic_regressions": catastrophic_regressions,
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
