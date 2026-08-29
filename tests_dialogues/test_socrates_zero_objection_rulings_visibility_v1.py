"""Objection rulings must reach the room, and nothing else may ride along.

Measured over three ratified councils, 80% of calls and about 60% of generated
tokens are evaluator output no seat ever sees. Nearly all of it is quality
scores, and those must stay hidden: a seat that can see what the scorer rewards
optimises for the scorer rather than for the argument.

Nine outputs per run are not scores. They are objection verifications, deciding
whether an objection a seat raised holds against the task text, and carrying
condition_tested, objection_holds, rationale and cited_spans. Withholding those
cost the Q4 council directly - the seats circled one specification gap for six
rounds while six reasoned rulings on that exact gap were produced and discarded,
two of them contradicting each other on whether the task settled the question.

These tests fix both halves: the rulings become visible to deliberation, and
scores stay out of them.
"""

from __future__ import annotations

import pytest

from backend.dialogues.models import AgentRole, AgentTask, DialogPhase, TaskKind
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    OBJECTION_RULING_CONTEXT_KEY_V1,
    OBJECTION_RULING_FIELDS_V1,
    _record_objection_ruling_v1,
    _with_objection_rulings_v1,
    recorded_objection_rulings_v1,
    reset_objection_rulings_v1,
)

SESSION_V1 = "rulings-visibility-test"

# Taken verbatim from the Q4 council: two rulings on the same specification gap
# that reach opposite conclusions. Neither reached the dialogue.
RULING_HOLDS_V1 = {
    "condition_tested": (
        "Whether allowing randomized tie-breaking is consistent with the task "
        "requirement that the published rule deterministically name a single "
        "winner for every profile."
    ),
    "objection_holds": True,
    "objection_targets": "claim_4",
    "rationale": (
        "The original task explicitly requires a rule that for every profile "
        "names exactly one winner, never a tie. A randomized device yields a "
        "lottery over winners, so the objection is correct."
    ),
    "cited_spans": ["names exactly one winner, never a tie"],
}
RULING_IRRELEVANT_V1 = {
    "condition_tested": "Whether the task permits randomized mechanisms.",
    "objection_holds": False,
    "objection_targets": "claim_4",
    "rationale": (
        "Those statements fix a deterministic, single-winner interpretation and "
        "thereby exclude randomized tie-breaking; the objection is irrelevant to "
        "the task as written."
    ),
    "cited_spans": ["names a single winner"],
}


def _task(kind: TaskKind, objection: str = "obj_1") -> AgentTask:
    return AgentTask(
        task_id="task_1",
        session_id=SESSION_V1,
        agent_id="agent_1",
        role=AgentRole.ELENCHUS_CRITIC,
        phase=DialogPhase.ELENCHUS,
        question="Assess this argument.",
        context={"dialogue_so_far": []},
        output_schema={"_role": "__objection_verification__", "_objection": objection},
        task_kind=kind,
    )


@pytest.fixture(autouse=True)
def _clean():
    reset_objection_rulings_v1(SESSION_V1)
    yield
    reset_objection_rulings_v1(SESSION_V1)


def test_a_ruling_is_recorded_with_its_objection_id():
    _record_objection_ruling_v1(_task(TaskKind.OBJECTION_VERIFICATION), RULING_HOLDS_V1)
    recorded = recorded_objection_rulings_v1(SESSION_V1)
    assert len(recorded) == 1
    assert recorded[0]["objection_id"] == "obj_1"
    assert recorded[0]["objection_holds"] is True
    assert "randomized" in recorded[0]["rationale"]


def test_contradicting_rulings_are_both_kept():
    """The disagreement is the finding; collapsing it would hide the problem."""

    _record_objection_ruling_v1(_task(TaskKind.OBJECTION_VERIFICATION), RULING_HOLDS_V1)
    _record_objection_ruling_v1(
        _task(TaskKind.OBJECTION_VERIFICATION, "obj_1"), RULING_IRRELEVANT_V1
    )
    verdicts = [row["objection_holds"] for row in recorded_objection_rulings_v1(SESSION_V1)]
    assert verdicts == [True, False]


def test_deliberation_task_sees_prior_rulings():
    _record_objection_ruling_v1(_task(TaskKind.OBJECTION_VERIFICATION), RULING_HOLDS_V1)
    original = _task(TaskKind.ELENCHUS_OBJECTION)
    augmented = _with_objection_rulings_v1(original)
    assert augmented is not original, "the task must be replaced, never mutated"
    rulings = augmented.context[OBJECTION_RULING_CONTEXT_KEY_V1]
    assert len(rulings) == 1
    assert rulings[0]["condition_tested"].startswith("Whether allowing randomized")
    assert original.context.get(OBJECTION_RULING_CONTEXT_KEY_V1) is None


@pytest.mark.parametrize(
    "kind",
    (TaskKind.OBJECTION_VERIFICATION, TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE),
)
def test_evaluators_never_see_rulings(kind):
    """A verifier fed its own prior verdicts stops being an independent check."""

    _record_objection_ruling_v1(_task(TaskKind.OBJECTION_VERIFICATION), RULING_HOLDS_V1)
    task = _task(kind)
    assert _with_objection_rulings_v1(task) is task


def test_no_score_field_can_ride_along():
    """The allowlist is the guarantee: only these five fields are ever carried."""

    contaminated = dict(RULING_HOLDS_V1)
    contaminated.update(
        {
            "logical_rigor": 9,
            "epistemic_value": 8,
            "intellectual_honesty": 7,
            "verdict": "accept",
            "score": 46,
        }
    )
    _record_objection_ruling_v1(_task(TaskKind.OBJECTION_VERIFICATION), contaminated)
    carried = set(recorded_objection_rulings_v1(SESSION_V1)[0])
    assert carried == set(OBJECTION_RULING_FIELDS_V1) | {"objection_id"}
    for leaked in ("logical_rigor", "epistemic_value", "verdict", "score"):
        assert leaked not in carried


def test_a_ruling_without_a_rationale_is_not_recorded():
    """A bare verdict carries no reason, so it is not dialectical material."""

    _record_objection_ruling_v1(
        _task(TaskKind.OBJECTION_VERIFICATION), {"objection_holds": True}
    )
    assert recorded_objection_rulings_v1(SESSION_V1) == ()


def test_a_task_without_rulings_is_returned_unchanged():
    task = _task(TaskKind.ELENCHUS_OBJECTION)
    assert _with_objection_rulings_v1(task) is task


def test_injection_is_idempotent():
    _record_objection_ruling_v1(_task(TaskKind.OBJECTION_VERIFICATION), RULING_HOLDS_V1)
    once = _with_objection_rulings_v1(_task(TaskKind.ELENCHUS_OBJECTION))
    twice = _with_objection_rulings_v1(once)
    assert twice is once


def test_sessions_do_not_bleed_into_each_other():
    _record_objection_ruling_v1(_task(TaskKind.OBJECTION_VERIFICATION), RULING_HOLDS_V1)
    other = _task(TaskKind.ELENCHUS_OBJECTION).model_copy(update={"session_id": "another-run"})
    assert _with_objection_rulings_v1(other) is other


# --------------------------------------------------------------------------
# Three failures, three different things.
#
# A first failure may be simple misunderstanding, so the same seat is asked
# again - which is the elenchus, not an evasion of it: nothing is discarded,
# every attempt stays in the record, and a seat that answers differently the
# second time has shown its first answer was opinion. A second failure, after
# being asked again, is no longer not knowing, so the question passes to another
# seat. A third is neither, and the council stops asking and records the fact
# about that seat rather than absorbing it as an unlucky round.
#
# Collapsing the three into one name would discard the only signal that
# separates a seat that could not answer from one that would not.
# --------------------------------------------------------------------------

from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (  # noqa: E402
    ATTEMPT_FAILURE_CLASSES_V1,
    attempt_failure_class_v1,
)


@pytest.mark.parametrize(
    "attempt,expected",
    [(0, "ignorance"), (1, "betrayal"), (2, "non_conformance")],
)
def test_each_attempt_names_its_own_kind_of_failure(attempt, expected):
    assert attempt_failure_class_v1(attempt) == expected


def test_the_three_are_distinct():
    assert len(set(ATTEMPT_FAILURE_CLASSES_V1)) == 3


def test_beyond_the_third_stays_non_conformance():
    """Nothing softer is available once a seat has refused three times."""

    assert attempt_failure_class_v1(3) == "non_conformance"
    assert attempt_failure_class_v1(9) == "non_conformance"


@pytest.mark.parametrize("bad", [None, -1, "1", 1.0])
def test_an_unusable_attempt_index_is_not_guessed_at(bad):
    assert attempt_failure_class_v1(bad) is None
