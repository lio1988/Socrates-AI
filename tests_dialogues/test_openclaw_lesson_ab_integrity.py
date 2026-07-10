"""Adversarial integrity tests for Lesson A/B arm comparison."""

import asyncio

from backend.dialogues.openclaw_memory import run_lesson_ab


class FakeCED:
    def __init__(self, arm):
        self.arm = arm

    async def run_registry_session(self, question, session_id):
        return object()


def _base_outcome(*, score, selected, ratified=True, resolved=5, unresolved=0):
    return {
        "ratified": ratified,
        "mean_section_score": score,
        "resolved_sections": resolved,
        "unresolved_sections": unresolved,
        "has_assembly": score is not None and resolved > 0,
        "lessons_selected": selected,
        "lesson_ids": ["LESSON-X"] if selected else [],
        "available_providers": ["seat0", "seat1"],
        "unavailable_providers": [],
    }


def test_treatment_assembly_collapse_is_catastrophic_harm(monkeypatch):
    import backend.dialogues.openclaw_memory.lesson_ab as module

    def factory(openclaw_lessons):
        arm = "treatment" if openclaw_lessons is not None else "control"
        return FakeCED(arm), "mock"

    def outcome(ced, session_id, final):
        if ced.arm == "control":
            return _base_outcome(score=8.0, selected=0)
        return _base_outcome(
            score=None,
            selected=1,
            ratified=False,
            resolved=0,
            unresolved=5,
        )

    monkeypatch.setattr(module, "_arm_outcome", outcome)
    report = asyncio.run(run_lesson_ab(
        ["q"], [object()], council_factory=factory))

    assert report["catastrophic_regressions"] == 1
    assert report["tested"] == 0
    assert report["harm_rate"] == 1.0
    assert report["helped"] is False
    assert report["verdict"] == "harmed"
    assert report["questions"][0]["reason"] == "treatment_no_assembly"


def test_arm_order_is_counterbalanced_across_questions(monkeypatch):
    import backend.dialogues.openclaw_memory.lesson_ab as module

    calls = []

    def factory(openclaw_lessons):
        arm = "treatment" if openclaw_lessons is not None else "control"
        calls.append(arm)
        return FakeCED(arm), "mock"

    def outcome(ced, session_id, final):
        return _base_outcome(
            score=6.0 if ced.arm == "treatment" else 5.0,
            selected=1 if ced.arm == "treatment" else 0,
        )

    monkeypatch.setattr(module, "_arm_outcome", outcome)
    report = asyncio.run(run_lesson_ab(
        ["q0", "q1"], [object()], council_factory=factory))

    assert calls == ["control", "treatment", "treatment", "control"]
    assert report["questions"][0]["arm_order"] == ["control", "treatment"]
    assert report["questions"][1]["arm_order"] == ["treatment", "control"]
    assert report["tested"] == 2
    assert report["verdict"] == "helped"


def test_execution_mode_mismatch_is_invalid_not_evidence(monkeypatch):
    import backend.dialogues.openclaw_memory.lesson_ab as module

    def factory(openclaw_lessons):
        arm = "treatment" if openclaw_lessons is not None else "control"
        mode = "live" if arm == "treatment" else "mock"
        return FakeCED(arm), mode

    def outcome(ced, session_id, final):
        return _base_outcome(
            score=6.0 if ced.arm == "treatment" else 5.0,
            selected=1 if ced.arm == "treatment" else 0,
        )

    monkeypatch.setattr(module, "_arm_outcome", outcome)
    report = asyncio.run(run_lesson_ab(
        ["q"], [object()], council_factory=factory))

    assert report["configuration_mismatches"] == 1
    assert report["invalid"] == 1
    assert report["tested"] == 0
    assert report["helped"] is False
    assert report["verdict"] == "untested"
    assert report["questions"][0]["reason"] == "execution_mode_mismatch"
