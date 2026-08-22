"""Socratic Question Policy v1: the question form the task actually admits.

Four paid runs, all on finite constraint puzzles, produced these openings:

    "What assumptions are we making about the relationships ..."
    "What is the significance of the order in which the analysts present?"  (x2)
    "What assumptions are we making about the positions of A..."

None of them could change the answer. In a puzzle whose rules are printed there
is no hidden assumption to expose, and the role directive asked for exactly that,
so the model manufactured ambiguity that was not there. The directive was
producing what it asked for; the ask was wrong for the task class.

That is upstream of the failure we could not close. A vague opening produces a
critique of the reasoning; a critique of the reasoning has nothing in the task to
quote; the verifier returns nothing usable. Four runs, no corroborated objection.

The regime is decided by the same reducer the checker uses — no model judges it,
and no solution or solution count is ever passed to the council.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    AgentRole, AgentState, AgentTask, DialogPhase, ShadowScoringMode, TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.reasoning_prompts import (
    ROLE_REASONING, SOCRATIC_MANDATE_CONSTRAINT, SOCRATIC_MANDATE_OPEN,
    marker_is_contracted,
)

PUZZLE = ("Six analysts — Anna, Ben, Clara, David, Elena, and Farid — occupy six "
          "consecutive positions, one per position. Clara is first. Anna is "
          "immediately before Elena. Ben is not immediately before Anna. Elena "
          "is last. Farid is before Ben. Determine the unique order.")
ESSAY = "Is consensus among AI models a reliable signal of truth?"

TRUE_ORDER = "Clara, Farid, Ben, David, Anna, Elena"
NEAR_MISS = "Clara, Farid, David, Ben, Anna, Elena"     # breaks exactly one rule


def _ced(seats=3):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(seats):
        registry.register(ScriptedMockProvider(f"seat{i}"))
    return CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                           provider, registry=registry,
                           shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)


def _mandate(question, session_id="m"):
    ced = _ced()
    state = ced.create_session(question, session_id=session_id)
    ctx = ced._registry_phase_context(state, DialogPhase.OPENING, "a0")
    return ctx["socratic_question_mandate"]


# ══ the regime is chosen by the reducer, not by a model ══════════════════════

def test_a_constraint_task_gets_the_constraint_mandate():
    ced = _ced()
    state = ced.create_session(PUZZLE, session_id="reg_c")
    assert ced._socratic_regime(state) == "finite_constraint"
    assert _mandate(PUZZLE, "man_c") is SOCRATIC_MANDATE_CONSTRAINT


def test_an_open_question_gets_the_elenchus_mandate():
    ced = _ced()
    state = ced.create_session(ESSAY, session_id="reg_o")
    assert ced._socratic_regime(state) == "open"
    assert _mandate(ESSAY, "man_o") is SOCRATIC_MANDATE_OPEN


def test_a_task_the_reducer_cannot_read_falls_back_to_open():
    """Fail-open here is safe: elenchus is the right default for anything else."""
    half = ("Four people — Anna, Ben, Clara, and David — present. "
            "Anna sits closer to the window than Ben.")
    assert _mandate(half, "man_h") is SOCRATIC_MANDATE_OPEN


def test_the_regime_is_deterministic():
    ced = _ced()
    state = ced.create_session(PUZZLE, session_id="det")
    assert {ced._socratic_regime(state) for _ in range(20)} == {"finite_constraint"}


# ══ what the mandates may and may not contain ════════════════════════════════

def test_neither_mandate_leaks_a_solution_or_a_solution_count():
    """The orchestrator picks the question's shape. It hands over no answer."""
    for mandate in (SOCRATIC_MANDATE_CONSTRAINT, SOCRATIC_MANDATE_OPEN):
        lowered = mandate.lower()
        assert "unique solution" not in lowered
        assert "exactly one solution" not in lowered
        assert "the answer is" not in lowered
        for name in ("Anna", "Ben", "Clara", "David", "Elena", "Farid"):
            assert name not in mandate, f"{name} leaks the live puzzle's roster"


def test_the_constraint_mandate_forbids_manufacturing_an_assumption():
    """The exact failure mode, named in the text so it cannot drift back."""
    assert "no hidden premise to expose" in SOCRATIC_MANDATE_CONSTRAINT
    assert "what are we assuming?" in SOCRATIC_MANDATE_CONSTRAINT


def test_both_mandates_name_the_epistemic_marker_as_a_required_field():
    """The marker is contracted for this kind, and a field list that omits it
    silently loses it — the synthesis regression, which cost 0/8 markers."""
    assert marker_is_contracted(TaskKind.SOCRATIC_QUESTION)
    for mandate in (SOCRATIC_MANDATE_CONSTRAINT, SOCRATIC_MANDATE_OPEN):
        assert '"epistemic_marker"' in mandate


def test_both_mandates_require_the_question_field_downstream_depends_on():
    """`_socratic_opening` reads content["question"]; two phases consume it."""
    for mandate in (SOCRATIC_MANDATE_CONSTRAINT, SOCRATIC_MANDATE_OPEN):
        assert '"question"' in mandate


def test_the_role_line_no_longer_prescribes_a_single_question_shape():
    line = ROLE_REASONING[AgentRole.SOCRATES]
    assert "hidden assumption or ambiguity whose resolution" not in line
    assert "depends on the task" in line


# ══ the opening still flows where it always did ══════════════════════════════

class NamedRival(ScriptedMockProvider):
    """A Socrates that follows the constraint mandate."""

    def __init__(self, provider_id, *, rival=NEAR_MISS, question=None):
        super().__init__(provider_id)
        self._rival = rival
        self._question = question

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is not TaskKind.SOCRATIC_QUESTION:
            return await super()._produce_raw_text(task, agent_state)
        content = {"question": self._question or
                   f"Could the order be {self._rival} — and if not, which rule rules it out?",
                   "discriminating_rule": "Ben is not immediately before Anna",
                   "epistemic_marker": "hypothesis"}
        if self._rival is not None:
            content["rival_candidate"] = self._rival
        return json.dumps({"content": content, "confidence": 0.6})


def _run(seats, session_id, question=PUZZLE):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for seat in seats:
        registry.register(seat)
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                          provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(question, session_id=session_id))
    return ced, final


def test_the_opening_question_still_reaches_the_phases_that_consume_it():
    ced, _final = _run([NamedRival(f"seat{i}") for i in range(3)], "flow")
    state = ced.get_session("flow")
    assert NEAR_MISS in ced._socratic_opening(state)
    for phase in (DialogPhase.INITIAL_RESPONSE, DialogPhase.ELENCHUS):
        ctx = ced._registry_phase_context(state, phase, "a0")
        assert NEAR_MISS in ctx["socratic_opening_question"]


# ══ the audit: did the question do its job? ══════════════════════════════════

def test_a_named_near_miss_is_recorded_as_one():
    _ced_, final = _run([NamedRival(f"seat{i}") for i in range(3)], "audit_near")
    audit = final.audit_summary["socratic_opening"]
    assert audit["regime"] == "finite_constraint"
    assert audit["rival_candidate"] == NEAR_MISS
    assert audit["rival_checker_result"] == "invalid"
    assert audit["rival_violated"] == ["Ben not immediately before Anna"]
    assert audit["rival_is_a_near_miss"] is True


def test_a_rival_that_is_actually_the_answer_is_not_a_near_miss():
    """Handing the council the solution is not the Socratic move."""
    seats = [NamedRival(f"seat{i}", rival=TRUE_ORDER) for i in range(3)]
    _ced_, final = _run(seats, "audit_true")
    audit = final.audit_summary["socratic_opening"]
    assert audit["rival_checker_result"] == "valid"
    assert audit["rival_is_a_near_miss"] is False


def test_an_opening_with_no_rival_is_recorded_as_such():
    seats = [NamedRival(f"seat{i}", rival=None,
                        question="What are we assuming about the positions?")
             for i in range(3)]
    _ced_, final = _run(seats, "audit_none")
    audit = final.audit_summary["socratic_opening"]
    assert audit["rival_candidate"] is None
    assert "rival_checker_result" not in audit


def test_the_four_openings_we_actually_paid_for_all_score_as_no_rival():
    """The before side of the measurement, replayed through the audit."""
    for i, question in enumerate([
        "What assumptions are we making about the relationships between them?",
        "What is the significance of the order in which the analysts present?",
    ]):
        seats = [NamedRival(f"seat{j}", rival=None, question=question)
                 for j in range(3)]
        _ced_, final = _run(seats, f"before_{i}")
        audit = final.audit_summary["socratic_opening"]
        assert audit["regime"] == "finite_constraint"
        assert audit["rival_candidate"] is None, question


def test_an_open_task_audit_reports_whether_the_branches_discriminate():
    class Branching(ScriptedMockProvider):
        def __init__(self, provider_id, *, same):
            super().__init__(provider_id)
            self._same = same

        async def _produce_raw_text(self, task, agent_state):
            if task.task_kind is not TaskKind.SOCRATIC_QUESTION:
                return await super()._produce_raw_text(task, agent_state)
            other = "consensus is a signal" if self._same else "consensus is noise"
            return json.dumps({"content": {
                "question": "Does agreement between models share a cause?",
                "if_answered_one_way": "consensus is a signal",
                "if_answered_another_way": other,
                "epistemic_marker": "hypothesis"}, "confidence": 0.6})

    _c1, discriminating = _run([Branching(f"s{i}", same=False) for i in range(3)],
                               "br_ok", question=ESSAY)
    _c2, decorative = _run([Branching(f"s{i}", same=True) for i in range(3)],
                           "br_no", question=ESSAY)
    assert discriminating.audit_summary["socratic_opening"]["branches_discriminate"] is True
    assert decorative.audit_summary["socratic_opening"]["branches_discriminate"] is False


# ══ the probe is observability and nothing else ══════════════════════════════

def test_the_rival_probe_never_reaches_a_claim_or_the_release():
    """A model's guess is a guess. Checking it must not make it evidence."""
    a = _run([NamedRival(f"seat{i}") for i in range(3)], "probe_a")[1]
    b = _run([NamedRival(f"seat{i}", rival=None) for i in range(3)], "probe_b")[1]

    for final in (a, b):
        governing = final.audit_summary["governing_release"]
        assert "rival_candidate" not in json.dumps(governing)
    # The opening differs; the governing verdict does not move because of it.
    assert a.governing_epistemic_status == b.governing_epistemic_status
    assert a.release_decision == b.release_decision


def test_the_council_is_never_told_the_probe_result():
    ced, _final = _run([NamedRival(f"seat{i}") for i in range(3)], "no_leak")
    state = ced.get_session("no_leak")
    for phase in (DialogPhase.INITIAL_RESPONSE, DialogPhase.ELENCHUS,
                  DialogPhase.REFLECTION, DialogPhase.SYNTHESIS):
        blob = json.dumps(ced._registry_phase_context(state, phase, "a0"),
                          default=str)
        assert "rival_checker_result" not in blob
        assert "rival_is_a_near_miss" not in blob


# ══ the loop: he asks again, having read the answer ══════════════════════════

FOLLOWUP = "You asserted uniqueness — which stated rule eliminates the rival?"


class LoopingSocrates(ScriptedMockProvider):
    """Answers the opening as Socrates, and the follow-up as Socrates."""

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is not TaskKind.SOCRATIC_QUESTION:
            return await super()._produce_raw_text(task, agent_state)
        if task.phase is DialogPhase.ELENCHUS:
            return json.dumps({"content": {
                "question": FOLLOWUP,
                "answers_engaged": "they claimed a unique order without ruling out rivals",
                "opening_answered": True,
                "epistemic_marker": "hypothesis"}, "confidence": 0.6})
        return json.dumps({"content": {
            "question": "Could the order be X — and if not, which rule rules it out?",
            "rival_candidate": NEAR_MISS,
            "discriminating_rule": "Ben is not immediately before Anna",
            "epistemic_marker": "hypothesis"}, "confidence": 0.6})


def _loop_run(session_id, question=PUZZLE):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(4):
        registry.register(LoopingSocrates(f"seat{i}"))
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                          provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    return ced, asyncio.run(ced.run_registry_session(question, session_id=session_id))


def test_socrates_asks_a_second_time_after_the_answers_arrive():
    """The elenchus is a loop; we had implemented its first move and stopped."""
    ced, _final = _loop_run("loop_two")
    asked = ced.socratic_questions(ced.get_session("loop_two"))
    assert [q["phase"] for q in asked] == ["opening", "elenchus"]
    assert asked[1]["question"] == FOLLOWUP


def test_the_follow_up_is_a_question_task_not_an_objection_task():
    """Given the phase's kind he would receive the objection contract, and the
    questioner would become an objector."""
    ced, _final = _loop_run("loop_kind")
    state = ced.get_session("loop_kind")
    socratic = [m for m in state.moves_for_phase(DialogPhase.ELENCHUS)
                if m.role is AgentRole.SOCRATES]
    assert len(socratic) == 1
    assert socratic[0].task_kind is TaskKind.SOCRATIC_QUESTION


def test_the_follow_up_sees_the_opening_and_the_answers():
    ced, _final = _loop_run("loop_ctx")
    state = ced.get_session("loop_ctx")
    socrates = next(a for a, r in ced._registry_phase_assignment(
        state, DialogPhase.ELENCHUS).items() if r is AgentRole.SOCRATES)
    ctx = ced._registry_phase_context(state, DialogPhase.ELENCHUS, socrates)
    assert "socratic_followup_mandate" in ctx
    assert ctx["socratic_opening_question"]
    assert ctx["initial_responses"], "he must see what he provoked"
    # The critic's escalation mandates are written for an attacker.
    assert "devils_advocate_mandate" not in ctx
    assert "low_diversity_alert" not in ctx


def test_asking_is_not_objecting():
    """A question in the elenchus phase must not project as an objection."""
    ced, final = _loop_run("loop_obj")
    state = ced.get_session("loop_obj")
    elenchus_moves = state.moves_for_phase(DialogPhase.ELENCHUS)
    objections = final.audit_summary["governing_release"]["objections"]
    assert len(elenchus_moves) > len(objections)
    assert all(FOLLOWUP not in o["text"] if "text" in o else True for o in objections)


def test_every_later_phase_sees_both_questions():
    ced, _final = _loop_run("loop_flow")
    state = ced.get_session("loop_flow")
    for phase in (DialogPhase.REFLECTION, DialogPhase.RECONSTRUCTION,
                  DialogPhase.SYNTHESIS):
        asked = ced._registry_phase_context(state, phase, "a0").get(
            "socratic_questions_so_far") or []
        assert len(asked) == 2, phase


def test_the_opening_context_does_not_carry_questions_that_do_not_exist_yet():
    ced, _final = _loop_run("loop_open")
    state = ced.get_session("loop_open")
    ctx = ced._registry_phase_context(state, DialogPhase.OPENING, "a0")
    assert "socratic_questions_so_far" not in ctx


def test_the_critics_still_get_their_own_contract():
    """Socrates rejoining must not take the elenchus away from the elenchus."""
    ced, _final = _loop_run("loop_critics")
    state = ced.get_session("loop_critics")
    roles = {r for r in ced._registry_phase_assignment(
        state, DialogPhase.ELENCHUS).values()}
    assert AgentRole.ELENCHUS_CRITIC in roles
    assert AgentRole.EMPIRICIST in roles
    assert AgentRole.SOCRATES in roles
