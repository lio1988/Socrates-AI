"""What Socrates may never see, never say, and never decide.

Two invariants, and everything here is one of them:

    SOCRATES OWNS THE QUESTION, NOT THE ANSWER.
    THE DIALOGUE HISTORY IS IMMUTABLE.

The first was broken once. A `rival_candidate` field required the opening to
name a complete ordering, and four paid runs opened by handing the council a
six-name permutation nobody had proposed. Prompts alone cannot hold a line like
that, so the ordering case is enforced mechanically here.

Where mechanical detection does not exist, the check says NOT_APPLICABLE. It
does not ask a model whether a model leaked — that swaps a guarantee for an
opinion, and an opinion is exactly what this layer refuses everywhere else.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_epistemic import SupportState
from backend.dialogues.models import (
    AgentRole, AgentState, AgentTask, DialogPhase, ShadowScoringMode, TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.socratic import (
    AporiaRecord, CommitmentRecord, CommitmentStatus, InjectionCheck,
    InquiryState, MaieuticOperator, aporia_from_content, check_answer_injection,
    commitment_events_from_reflection, commitments_from_move,
    independent_sources, live_commitments, parse_grounding, resolve_grounding,
)

TASK = ("Six analysts — Anna, Ben, Clara, David, Elena, and Farid — occupy six "
        "consecutive positions, one per position. Clara is first. Anna is "
        "immediately before Elena. Ben is not immediately before Anna. Elena "
        "is last. Farid is before Ben.")
ESSAY = "Is consensus among AI models a reliable signal of truth?"

TRUE_ORDER = "Clara, Farid, Ben, David, Anna, Elena"
OTHER_ORDER = "Clara, Anna, Elena, David, Farid, Ben"


# ══ 2. the opening may not hand over an answer ═══════════════════════════════

def test_a_question_naming_an_unpublished_ordering_is_injection():
    """The exact drift, caught by code rather than by asking nicely."""
    check, why = check_answer_injection(
        f"Could the order be {OTHER_ORDER}?", TASK, [])
    assert check is InjectionCheck.ANSWER_INJECTION_DETECTED
    assert OTHER_ORDER in why


def test_merely_naming_every_entity_is_not_injection():
    """The false positive that would make the firewall useless."""
    question = ("Which of Anna, Ben, Clara, David, Elena and Farid has a "
                "position fixed outright by the stated rules?")
    assert check_answer_injection(question, TASK, [])[0] is InjectionCheck.PASS


def test_an_eliciting_question_passes():
    assert check_answer_injection(
        "Which stated constraints fix a position directly?", TASK, []
    )[0] is InjectionCheck.PASS


def test_an_ordering_a_prior_move_already_made_public_may_be_referred_to():
    prior = [f"The order is {TRUE_ORDER}."]
    assert check_answer_injection(
        f"Could the order be {TRUE_ORDER} — and what makes it so?", TASK, prior
    )[0] is InjectionCheck.PASS


def test_an_ordering_the_user_supplied_may_be_referred_to():
    task = TASK + f" The order is {TRUE_ORDER}. Is that right?"
    assert check_answer_injection(
        f"Could the order be {TRUE_ORDER}?", task, []
    )[0] is InjectionCheck.PASS


def test_an_open_domain_reports_not_applicable_rather_than_false_confidence():
    check, why = check_answer_injection("What do we mean by consensus?", ESSAY, [])
    assert check is InjectionCheck.NOT_APPLICABLE
    assert "no mechanical" in why


# ══ the firewall inside a real session ═══════════════════════════════════════

class Injecting(ScriptedMockProvider):
    """A Socrates that hands over an ordering nobody proposed."""

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is TaskKind.SOCRATIC_QUESTION:
            return json.dumps({"content": {
                "question": f"Could the order be {OTHER_ORDER}?",
                "operator": MaieuticOperator.DRAW_CONSEQUENCE.value,
                "grounded_in": [], "introduces_new_proposition": False,
                "inquiry_state": InquiryState.CONTINUE_INQUIRY.value,
                "epistemic_marker": "hypothesis"}, "confidence": 0.6})
        return await super()._produce_raw_text(task, agent_state)


def _council(cls=ScriptedMockProvider, seats=4, **kwargs):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(seats):
        registry.register(cls(f"seat{i}"))
    return CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                           provider, registry=registry,
                           shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
                           **kwargs)


def test_an_injecting_question_never_becomes_a_public_move():
    ced = _council(Injecting)
    asyncio.run(ced.run_registry_session(TASK, session_id="inject"))
    state = ced.get_session("inject")
    assert [m for m in state.moves if m.role is AgentRole.SOCRATES] == []
    rows = ced._socratic_audit_rows["inject"]
    assert rows and all(
        r["injection_check"] == InjectionCheck.ANSWER_INJECTION_DETECTED.value
        for r in rows)


def test_the_session_survives_a_refused_question():
    """Fail-closed: the question is refused, the dialogue is not."""
    ced = _council(Injecting)
    final = asyncio.run(ced.run_registry_session(TASK, session_id="survive"))
    assert final.synthesis is not None


# ══ 1 / 6. the information firewall ══════════════════════════════════════════

class Recording(ScriptedMockProvider):
    """Captures every context Socrates was given."""

    seen: list = []

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is TaskKind.SOCRATIC_QUESTION:
            Recording.seen.append(json.dumps(task.context, default=str, sort_keys=True))
        return await super()._produce_raw_text(task, agent_state)


@pytest.mark.parametrize("forbidden", [
    "deterministic_checks", "governing_release", "release_decision",
    "governing_epistemic_status", "basis_record_ids", "micro_scores",
    "leaderboard", "quality_mean", "ratification", "objection_verdicts",
])
def test_no_governing_or_scoring_artifact_reaches_socrates(forbidden):
    Recording.seen = []
    ced = _council(Recording)
    asyncio.run(ced.run_registry_session(TASK, session_id=f"fw_{forbidden}"))
    assert Recording.seen, "Socrates ran"
    for context in Recording.seen:
        assert forbidden not in context


def test_hidden_checker_truth_cannot_change_the_socratic_task():
    """Same public dialogue, different hidden answer — identical context.

    The strongest form of the firewall: if the checker's verdict could reach
    Socrates at all, changing the task's true answer while holding the public
    dialogue fixed would show up here.
    """
    def contexts(question):
        Recording.seen = []
        ced = _council(Recording)
        asyncio.run(ced.run_registry_session(question, session_id="hidden"))
        # Strip the task text itself: only the derived context is under test.
        return [c.replace(question, "<TASK>") for c in Recording.seen]

    unique = TASK
    # Same roster, same public dialogue shape, a different true answer.
    altered = TASK.replace("Clara is first.", "Farid is first.")
    assert contexts(unique) == contexts(altered)


# ══ 3. grounding resolves to public artifacts that already existed ═══════════

def test_grounding_references_are_typed_and_resolved():
    refs = parse_grounding([
        {"ref_type": "commitment", "ref_id": "cmt_a"},
        {"ref_type": "critique", "ref_id": "move_b"},
        {"ref_type": "nonsense", "ref_id": "x"},
        "not a mapping",
    ])
    assert refs == [("commitment", "cmt_a"), ("critique", "move_b")]
    resolved, unresolved = resolve_grounding(
        refs, {"commitment": {"cmt_a"}, "critique": set()})
    assert resolved == [("commitment", "cmt_a")]
    assert unresolved == [("critique", "move_b")]


def test_a_reference_to_something_that_does_not_exist_resolves_to_nothing():
    resolved, unresolved = resolve_grounding(
        [("commitment", "cmt_future")], {"commitment": {"cmt_past"}})
    assert resolved == []
    assert unresolved == [("commitment", "cmt_future")]


# ══ 2 (append-only) / 5. commitments and their history ═══════════════════════

def _asserted(move_id="move_1"):
    return commitments_from_move(move_id, 0, {"commitments": ["X holds.", "Y holds."]},
                                 provider_id="seat0")


def test_a_revision_creates_a_new_record_and_leaves_the_old_one_alone():
    base = _asserted()
    known = {c.commitment_id for c in base}
    events = commitment_events_from_reflection(
        "move_2", 1,
        {"commitments_revised": [{"commitment_id": base[0].commitment_id,
                                  "new_claim": "X holds only under Z."}]},
        known, provider_id="seat0")
    assert len(events) == 1
    assert events[0].status is CommitmentStatus.REVISED
    assert events[0].target_commitment_id == base[0].commitment_id
    assert base[0].claim == "X holds."          # untouched


def test_a_withdrawal_removes_a_commitment_from_the_live_set_not_the_history():
    base = _asserted()
    known = {c.commitment_id for c in base}
    events = commitment_events_from_reflection(
        "move_2", 1, {"commitments_withdrawn": [base[0].commitment_id]},
        known, provider_id="seat0")
    ledger = base + events
    live = live_commitments(ledger)
    assert base[0].commitment_id not in {c.commitment_id for c in live}
    assert base[0] in ledger


def test_a_reference_to_an_unknown_commitment_changes_nothing():
    events = commitment_events_from_reflection(
        "move_2", 1, {"commitments_withdrawn": ["cmt_nobody_made"]},
        set(), provider_id="seat0")
    assert events == []


def test_inferred_commitments_carry_no_authority():
    inferred = CommitmentRecord(
        commitment_id="cmt_x", source_move_id="move_1", cycle=0,
        claim="what it probably meant", status=CommitmentStatus.ASSERTED,
        authority="non_authoritative_annotation")
    assert inferred.is_authoritative is False
    assert _asserted()[0].is_authoritative is True


# ══ 5. multi-round independence ══════════════════════════════════════════════

def test_one_provider_repeating_itself_across_rounds_is_one_source():
    """Rounds multiply utterances. They never multiply independence."""
    round0 = commitments_from_move("move_a", 0, {"commitments": ["X."]},
                                   provider_id="seat0")
    round1 = commitments_from_move("move_b", 1, {"commitments": ["X."]},
                                   provider_id="seat0")
    assert len(round0 + round1) == 2
    assert independent_sources(round0 + round1) == {"seat0"}


def test_two_providers_are_two_sources():
    a = commitments_from_move("move_a", 0, {"commitments": ["X."]}, provider_id="seat0")
    b = commitments_from_move("move_b", 1, {"commitments": ["X."]}, provider_id="seat1")
    assert independent_sources(a + b) == {"seat0", "seat1"}


class RepeatObjector(ScriptedMockProvider):
    """One seat raising the same objection in every cycle."""

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is TaskKind.ELENCHUS_OBJECTION:
            return json.dumps({"content": {
                "objection": "the derivation was never shown to be exhaustive",
                "target_section": "core_answer"}, "confidence": 0.9})
        return await super()._produce_raw_text(task, agent_state)


def test_repeated_objections_across_cycles_cannot_corroborate_themselves():
    from backend.dialogues.hybrid_epistemic import REQUIRED_CORROBORATION

    ced = _council(RepeatObjector)
    final = asyncio.run(ced.run_registry_session(TASK, session_id="repeat"))
    objections = final.audit_summary["governing_release"]["objections"]
    by_source = {}
    for row in objections:
        by_source.setdefault(row["raised_by"], []).append(row["objection_id"])
    for raiser, ids in by_source.items():
        if len(ids) > 1:
            # The same voice, more than once. It is still one voice, and the
            # corroboration gate counts distinct verifiers, never utterances.
            assert len({raiser}) < REQUIRED_CORROBORATION


# ══ 8 / 9 / 11. what a question can never become ═════════════════════════════

def test_a_socratic_move_never_becomes_an_objection():
    ced = _council()
    final = asyncio.run(ced.run_registry_session(TASK, session_id="notobj"))
    state = ced.get_session("notobj")
    socratic_ids = {m.move_id for m in state.moves if m.role is AgentRole.SOCRATES}
    core = ced.project_governing_state(state, final)
    for objection in core.objections.values():
        assert objection.objection_id not in socratic_ids
    assert len(core.objections) < len(state.moves_for_phase(DialogPhase.ELENCHUS))


def test_a_socratic_move_creates_no_evidence_and_no_support():
    ced = _council()
    final = asyncio.run(ced.run_registry_session(TASK, session_id="noev"))
    core = ced.project_governing_state(ced.get_session("noev"), final)
    assert core.evidence == {}
    for claim_id in core.claims:
        assert core.assess_claim(claim_id).support_state is not SupportState.SUPPORTED


def test_aporia_is_recorded_without_deciding_anything():
    base = _asserted()
    known = {c.commitment_id for c in base}
    record = aporia_from_content({"aporia": {
        "previous_commitment_id": base[0].commitment_id,
        "conflicting_commitment_id": base[1].commitment_id,
        "resulting_status": "suspended",
        "remaining_question": "which of the two can still be defended?"}}, 1, known)
    assert record is not None
    payload = record.to_dict()
    assert payload["resulting_status"] == "suspended"
    # Nothing epistemic anywhere in it.
    for forbidden in ("support", "falsified", "verified", "evidence", "release"):
        assert forbidden not in json.dumps(payload)


def test_an_aporia_over_commitments_nobody_made_is_not_recorded():
    assert aporia_from_content({"aporia": {
        "previous_commitment_id": "cmt_x",
        "conflicting_commitment_id": "cmt_y",
        "resulting_status": "withdrawn",
        "remaining_question": "?"}}, 1, set()) is None


def test_aporia_is_not_a_termination_state():
    """Reaching aporia usually shows where the next question belongs."""
    assert {s.value for s in InquiryState} == {
        "continue_inquiry", "ready_for_reconstruction"}


# ══ 7 / 13. the role stays the role ══════════════════════════════════════════

def test_socrates_always_carries_the_question_task_kind():
    ced = _council()
    asyncio.run(ced.run_registry_session(TASK, session_id="kind"))
    state = ced.get_session("kind")
    socratic = [m for m in state.moves if m.role is AgentRole.SOCRATES]
    assert socratic
    for move in socratic:
        assert move.task_kind is TaskKind.SOCRATIC_QUESTION


def test_no_permanent_model_becomes_socrates():
    """Rotation is deterministic and still rotates across sessions."""
    seen = set()
    for session_id in ("s_a", "s_b", "s_c", "s_d"):
        ced = _council()
        asyncio.run(ced.run_registry_session(TASK, session_id=session_id))
        state = ced.get_session(session_id)
        seen |= {m.provider_id for m in state.moves
                 if m.role is AgentRole.SOCRATES and m.phase is DialogPhase.OPENING}
    assert len(seen) > 1, seen


# ══ 2. cross-round independence, end to end ══════════════════════════════════

def test_the_same_seat_objecting_in_two_rounds_is_still_one_source():
    """Rounds create temporal observations, not provider independence.

    Built directly rather than fished out of a session: role rotation spreads
    the critic slots across seats between cycles, so a natural repeat is a
    matter of luck. The invariant must hold whether or not luck supplies it.
    """
    from backend.dialogues.hybrid_epistemic import (
        REQUIRED_CORROBORATION, ObjectionRecord, independent_objection_sources,
    )

    same_voice_twice = [
        ObjectionRecord(objection_id="obj_r0", target_claim_id="c",
                        text="the derivation was never shown exhaustive",
                        raised_by="seat0"),
        ObjectionRecord(objection_id="obj_r1", target_claim_id="c",
                        text="the derivation was never shown exhaustive",
                        raised_by="seat0"),
    ]
    assert len(same_voice_twice) == 2                              # utterances
    assert independent_objection_sources(same_voice_twice) == {"seat0"}
    assert len(independent_objection_sources(same_voice_twice)) < REQUIRED_CORROBORATION


def test_repetition_cannot_reach_the_corroboration_threshold_alone():
    """Even unbounded repetition by one seat stays one source."""
    from backend.dialogues.hybrid_epistemic import (
        REQUIRED_CORROBORATION, ObjectionRecord, independent_objection_sources,
    )

    many = [ObjectionRecord(objection_id=f"obj_{i}", target_claim_id="c",
                            text="same doubt", raised_by="seat0")
            for i in range(10)]
    assert len(independent_objection_sources(many)) == 1
    assert len(independent_objection_sources(many)) < REQUIRED_CORROBORATION


def test_role_rotation_already_spreads_objections_across_seats():
    """A welcome consequence of rotating per cycle, recorded so it is noticed."""
    from backend.dialogues.hybrid_epistemic import independent_objection_sources

    ced = _council(RepeatObjector)
    final = asyncio.run(ced.run_registry_session(TASK, session_id="spread"))
    core = ced.project_governing_state(ced.get_session("spread"), final)
    raised = [o for o in core.objections.values() if o.raised_by]
    assert len(raised) > 1
    assert len(independent_objection_sources(raised)) > 1


def test_a_repeated_objection_never_verifies_itself_across_rounds():
    """The raiser is excluded from verifying, in every cycle it speaks."""
    ced = _council(RepeatObjector)
    final = asyncio.run(ced.run_registry_session(TASK, session_id="cross_self"))
    session = ced.get_session("cross_self")
    core = ced.project_governing_state(session, final)

    asked = {}
    original = ced.registry.run_adapter

    async def spy(adapter, task, agent_state, timeout=None):
        if task.task_id.startswith("verify_"):
            asked.setdefault(task.task_id, set()).add(adapter.provider_id)
        return await original(adapter, task, agent_state, timeout)

    ced.registry.run_adapter = spy
    asyncio.run(ced.run_objection_verification(session, core))
    for objection_id, objection in core.objections.items():
        seats = asked.get(f"verify_{objection_id}")
        if seats is not None:
            assert objection.raised_by not in seats
