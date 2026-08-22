"""The maieutic loop: commitment, examination, question, reflection, repeat.

The design drifted once. A previous version required the opening question to
name a complete rival ordering, and four live runs duly handed the council a
six-name permutation before any agent had spoken. That is answer injection
wearing a question mark, and the correction is not a softer prompt — it is that
Socrates owns the question and never the answer.

Reflection sits inside the cycle. A second question asked before anyone has
answered the first is not a dialogue, it is two monologues.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import (
    SOCRATIC_CYCLE_PHASES, CEDOrchestrator, rubric_for, rubric_for_move,
)
from backend.dialogues.models import (
    AgentRole, AgentState, AgentTask, DialogPhase, ShadowScoringMode, TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.reasoning_prompts import (
    ROLE_REASONING, SOCRATIC_AIM_CONSTRAINT, SOCRATIC_AIM_OPEN,
    SOCRATIC_FOLLOWUP_MANDATE, SOCRATIC_OPENING_MANDATE,
)
from backend.dialogues.socratic import (
    CommitmentStatus, InquiryState, MaieuticOperator, live_commitments,
)

PUZZLE = ("Six analysts — Anna, Ben, Clara, David, Elena, and Farid — occupy six "
          "consecutive positions, one per position. Clara is first. Anna is "
          "immediately before Elena. Ben is not immediately before Anna. Elena "
          "is last. Farid is before Ben. Determine the unique order.")
ESSAY = "Is consensus among AI models a reliable signal of truth?"

C1 = "Clara occupies position one."
C2 = "Elena occupies position six."


class Maieutic(ScriptedMockProvider):
    """A council that plays the protocol: commits, examines, asks, revises."""

    def __init__(self, provider_id, *, keep_going=True, question=None,
                 grounded=True, revise=True):
        super().__init__(provider_id)
        self._keep_going = keep_going
        self._question = question
        self._grounded = grounded
        self._revise = revise

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is TaskKind.SOCRATIC_QUESTION:
            if task.phase is DialogPhase.OPENING:
                return json.dumps({"content": {
                    "question": "Which stated constraints fix a position outright?",
                    "operator": MaieuticOperator.ELICIT_COMMITMENT.value,
                    "epistemic_marker": "hypothesis"}, "confidence": 0.6})
            refs = []
            if self._grounded:
                for row in task.context.get("public_commitments") or []:
                    refs.append({"ref_type": "commitment",
                                 "ref_id": row["commitment_id"]})
                    break
            return json.dumps({"content": {
                "question": self._question or
                "You have fixed two positions — what does that leave open?",
                "operator": MaieuticOperator.DRAW_CONSEQUENCE.value,
                "grounded_in": refs,
                "introduces_new_proposition": False,
                "inquiry_state": (InquiryState.CONTINUE_INQUIRY.value
                                  if self._keep_going
                                  else InquiryState.READY_FOR_RECONSTRUCTION.value),
                "epistemic_marker": "hypothesis"}, "confidence": 0.6})

        if task.task_kind is TaskKind.INITIAL_RESPONSE:
            return json.dumps({"content": {
                "analysis": "Two positions are fixed by the stated rules.",
                "commitments": [C1, C2],
                "epistemic_marker": "hypothesis"}, "confidence": 0.7})

        if task.task_kind is TaskKind.REFLECTION_REVISION:
            live = task.context.get("current_public_commitments") or []
            content = {
                "revised_position": "The fixed positions still hold.",
                "answer_to_socratic_question":
                    "It leaves the middle four positions to be determined.",
                "commitments_retained": [live[0]["commitment_id"]] if live else [],
                "new_commitments": (["The middle four remain to be assigned."]
                                    if self._revise else []),
                "epistemic_marker": "hypothesis"}
            if self._revise and len(live) > 1:
                content["commitments_withdrawn"] = [live[1]["commitment_id"]]
            return json.dumps({"content": content, "confidence": 0.7})

        return await super()._produce_raw_text(task, agent_state)


def _council(seats=4, *, cls=Maieutic, max_followups=2, **kwargs):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(seats):
        registry.register(cls(f"seat{i}", **kwargs) if cls is Maieutic
                          else cls(f"seat{i}"))
    return CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                           provider, registry=registry,
                           shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
                           max_socratic_followups=max_followups)


def _run(ced, session_id, question=PUZZLE):
    return asyncio.run(ced.run_registry_session(question, session_id=session_id))


# ══ the opening asks, it does not propose ════════════════════════════════════

def test_no_mandate_asks_for_a_candidate_answer():
    """The drift, named in the tests so it cannot come back quietly."""
    for mandate in (SOCRATIC_OPENING_MANDATE, SOCRATIC_AIM_CONSTRAINT,
                    SOCRATIC_AIM_OPEN, SOCRATIC_FOLLOWUP_MANDATE):
        assert "rival_candidate" not in mandate
        assert "near miss" not in mandate.lower()
    assert "Do NOT propose a candidate answer" in SOCRATIC_OPENING_MANDATE


def test_the_constraint_aim_elicits_rather_than_proposes():
    assert "no hidden premise to expose" in SOCRATIC_AIM_CONSTRAINT
    assert "Let the council do the fixing" in SOCRATIC_AIM_CONSTRAINT


def test_no_mandate_names_the_live_puzzle():
    for mandate in (SOCRATIC_OPENING_MANDATE, SOCRATIC_AIM_CONSTRAINT,
                    SOCRATIC_AIM_OPEN, SOCRATIC_FOLLOWUP_MANDATE):
        for name in ("Anna", "Ben", "Clara", "David", "Elena", "Farid"):
            assert name not in mandate


def test_the_role_line_forbids_proposing():
    line = ROLE_REASONING[AgentRole.SOCRATES]
    assert "never answer it" in line
    assert "do not propose" in line.lower()


# ══ commitments: declared, append-only, source-grounded ══════════════════════

def test_initial_responses_become_public_commitments():
    ced = _council()
    _run(ced, "commit")
    ledger = ced.commitment_ledger(ced.get_session("commit"))
    assert ledger, "the council declared commitments"
    for record in ledger:
        assert record.source_move_id
        assert record.is_authoritative
        assert record.provider_id


def test_a_reflection_extends_the_history_and_never_edits_it():
    ced = _council()
    _run(ced, "append")
    ledger = ced.commitment_ledger(ced.get_session("append"))
    asserted = [c for c in ledger if c.status is CommitmentStatus.ASSERTED]
    events = [c for c in ledger if c.status is not CommitmentStatus.ASSERTED]
    assert asserted and events, "both the positions and the changes are recorded"
    # Every event points back at a record that is still present, unmodified.
    ids = {c.commitment_id for c in ledger}
    for event in events:
        assert event.target_commitment_id in ids


def test_a_withdrawn_commitment_stays_in_the_history():
    ced = _council()
    _run(ced, "withdraw")
    ledger = ced.commitment_ledger(ced.get_session("withdraw"))
    withdrawn = [c for c in ledger if c.status is CommitmentStatus.WITHDRAWN]
    if not withdrawn:
        pytest.skip("this council withdrew nothing")
    target = withdrawn[0].target_commitment_id
    assert any(c.commitment_id == target for c in ledger), "the record survives"
    assert target not in {c.commitment_id for c in live_commitments(ledger)}


def test_commitments_are_never_inferred_from_prose():
    """A council that declares nothing commits to nothing."""
    ced = _council(cls=ScriptedMockProvider)
    _run(ced, "silent")
    assert ced.commitment_ledger(ced.get_session("silent")) == []


# ══ the loop ═════════════════════════════════════════════════════════════════

def test_reflection_happens_inside_every_cycle():
    """Two questions with no answer between them is two monologues."""
    ced = _council()
    _run(ced, "loop")
    state = ced.get_session("loop")
    order = [m.phase.value for m in state.moves
             if m.phase in SOCRATIC_CYCLE_PHASES or m.role is AgentRole.SOCRATES]
    # Every Socratic follow-up is preceded by a reflection, except the first.
    followups = [i for i, m in enumerate(state.moves)
                 if m.role is AgentRole.SOCRATES and m.phase is DialogPhase.ELENCHUS]
    reflections = [i for i, m in enumerate(state.moves)
                   if m.phase is DialogPhase.REFLECTION]
    for later in followups[1:]:
        assert any(r < later for r in reflections), order


def test_the_follow_up_is_asked_after_the_critics_have_spoken():
    ced = _council()
    _run(ced, "waves")
    state = ced.get_session("waves")
    elenchus = [m for m in state.moves if m.phase is DialogPhase.ELENCHUS]
    # Per cycle, not globally: with two cycles the moves interleave as
    # critic, critic, question, critic, critic, question.
    seen_critics = 0
    questions = 0
    for move in elenchus:
        if move.role is AgentRole.SOCRATES:
            assert seen_critics > 0, "a question must see this cycle's objections"
            questions += 1
            seen_critics = 0
        else:
            seen_critics += 1
    assert questions >= 1


def test_a_later_question_sees_the_commitment_changes_of_the_earlier_cycle():
    ced = _council()
    _run(ced, "sees")
    state = ced.get_session("sees")
    ledger = ced.commitment_ledger(state)
    later = [c for c in ledger if c.cycle > 0]
    assert later, "a second cycle produced new commitment events"


def test_ced_enforces_the_bound_however_often_socrates_asks_to_continue():
    ced = _council(max_followups=1, keep_going=True)
    _run(ced, "bound")
    state = ced.get_session("bound")
    followups = [m for m in state.moves
                 if m.role is AgentRole.SOCRATES and m.phase is DialogPhase.ELENCHUS]
    assert len(followups) == 1


def test_ready_for_reconstruction_stops_the_cycle_early():
    ced = _council(max_followups=3, keep_going=False)
    _run(ced, "ready")
    state = ced.get_session("ready")
    followups = [m for m in state.moves
                 if m.role is AgentRole.SOCRATES and m.phase is DialogPhase.ELENCHUS]
    assert len(followups) == 1
    allowed, why = ced.another_socratic_cycle(state)
    assert allowed is False
    assert "ready_for_reconstruction" in why


def test_the_cycle_decision_is_recorded_with_its_reason():
    ced = _council(max_followups=1)
    _run(ced, "cyclelog")
    log = ced._cycle_log["cyclelog"]
    assert log and any(entry["continue"] is False for entry in log)
    assert all("reason" in entry for entry in log)


# ══ reflection receives a question, not a critique ═══════════════════════════

def test_reflection_receives_the_question_separately_from_the_critiques():
    ced = _council()
    _run(ced, "sep")
    state = ced.get_session("sep")
    ctx = ced._registry_phase_context(state, DialogPhase.REFLECTION, "a0")
    assert ctx["socratic_question_to_answer"]
    assert ctx["current_public_commitments"]
    for critique in ctx["critiques_from_council"]:
        assert critique["role"] != AgentRole.SOCRATES.value


def test_a_socratic_question_is_never_listed_as_a_critique():
    ced = _council()
    _run(ced, "notcrit")
    state = ced.get_session("notcrit")
    question = ced._latest_socratic_question(state)
    blob = json.dumps(ced._public_critiques(state), default=str)
    assert question and question not in blob


# ══ scoring firewall ═════════════════════════════════════════════════════════

def test_a_socratic_move_is_judged_as_a_question_wherever_it_is_asked():
    """Inside ELENCHUS the phase rubric would score it on 'strongest criticism'."""
    ced = _council()
    _run(ced, "rubric")
    state = ced.get_session("rubric")
    for move in state.moves:
        if move.role is not AgentRole.SOCRATES:
            continue
        assert rubric_for_move(move, move.phase)[0] == "question_quality"
    assert rubric_for(DialogPhase.ELENCHUS)[0] == "objection_quality"


def test_every_socratic_micro_score_uses_the_question_rubric():
    ced = _council()
    _run(ced, "scored")
    state = ced.get_session("scored")
    socratic_ids = {m.move_id for m in state.moves if m.role is AgentRole.SOCRATES}
    scored = [ms for ms in state.micro_scores if ms.output_id in socratic_ids]
    assert scored, "Socratic moves are still scored"
    assert {ms.rubric_name for ms in scored} == {"question_quality"}
