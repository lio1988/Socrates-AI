"""Claim-directed verification, and the two identity bugs that preceded it.

Before this the governing layer was a constant. Every verification the canonical
path produced was aimed at an objection, and an objection check can only ever
take support away, so no live session could reach any state but `unresolved` —
however checkable its question was.

The gate here is deliberately the same one that guards destruction: two
independent verifiers, unanimous, citing the same passage. The tests that matter
most are the ones proving what it still refuses — a lone seat, a council that
merely agrees, a verdict reached by citing different material.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_epistemic import (
    REQUIRED_CORROBORATION,
    ClaimRecord,
    HybridEpistemicState,
    ObjectionRecord,
    SupportState,
    VerificationClass,
    VerificationResult,
    VerificationVerdict,
    apply_claim_verification,
    corroborated_claim_result,
    parse_claim_verification_response,
    verify_task_internal,
)
from backend.dialogues.models import (
    AgentState, AgentTask, RatificationDecision, RatificationVote,
    ObjectionSeverity, ShadowScoringMode, TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider

TASK = ("Four researchers present once each. Anna presents before Ben. "
        "Clara presents immediately before David. Ben does not present last.")
C3 = "Ben does not present last"
C1 = "Anna presents before Ben"


def _state():
    state = HybridEpistemicState("cv", TASK)
    state.add_claim(ClaimRecord(claim_id="c", text="The order is A-B-C-D.",
                                section="core_answer",
                                verification_class=VerificationClass.TASK_INTERNAL))
    return state


def _record(seat, *, holds, span=C3):
    """A claim-directed check: objection_id is None, which is what makes it one."""
    return verify_task_internal(
        claim_id="c", objection_id=None, task_text=TASK,
        cited_spans=[(span, TASK.index(span))],
        condition_tested="does the task settle the claimed order?",
        holds=holds, rationale="read against the quoted constraint",
        verifier_provider_id=seat)


# ── the gate refuses ─────────────────────────────────────────────────────────

def test_one_seat_saying_verified_is_never_support():
    """The whole reason the gate sits before storage rather than after."""
    result, verdict, reason = corroborated_claim_result([_record("s0", holds=True)])
    assert result is None
    assert verdict is VerificationVerdict.UNCORROBORATED
    assert str(REQUIRED_CORROBORATION) in reason


def test_the_same_seat_twice_is_not_two_verifiers():
    result, verdict, _ = corroborated_claim_result([_record("s0", holds=True),
                                                    _record("s0", holds=True)])
    assert result is None
    assert verdict is VerificationVerdict.UNCORROBORATED


def test_disagreement_settles_nothing_and_never_becomes_a_majority():
    result, verdict, _ = corroborated_claim_result([
        _record("s0", holds=True), _record("s1", holds=True),
        _record("s2", holds=False)])
    assert result is None                       # 2-1 does not carry
    assert verdict is VerificationVerdict.CONFLICTING


def test_agreeing_while_citing_different_material_settles_nothing():
    result, verdict, reason = corroborated_claim_result([
        _record("s0", holds=True, span=C3), _record("s1", holds=True, span=C1)])
    assert result is None
    assert verdict is VerificationVerdict.NO_ANCHOR_AGREEMENT
    assert "different material" in reason


def test_no_records_settles_nothing():
    result, verdict, _ = corroborated_claim_result([])
    assert result is None
    assert verdict is VerificationVerdict.NO_RECORDS


# ── the gate allows ──────────────────────────────────────────────────────────

def test_two_independent_verifiers_on_one_passage_establish_the_claim():
    result, verdict, _ = corroborated_claim_result([_record("s0", holds=True),
                                                    _record("s1", holds=True)])
    assert result is VerificationResult.VERIFIED
    assert verdict is VerificationVerdict.CORROBORATED_VALID


def test_two_independent_verifiers_can_also_contradict_the_claim():
    result, verdict, _ = corroborated_claim_result([_record("s0", holds=False),
                                                    _record("s1", holds=False)])
    assert result is VerificationResult.FALSIFIED
    assert verdict is VerificationVerdict.CORROBORATED_INVALID


def test_the_anchor_rule_carries_over_to_claim_checks():
    """Endpoint differences are the same passage here too."""
    result, verdict, _ = corroborated_claim_result([
        _record("s0", holds=True, span="Ben does not present last"),
        _record("s1", holds=True, span="Ben does not present las")])
    assert result is VerificationResult.VERIFIED
    assert verdict is VerificationVerdict.CORROBORATED_VALID


# ── applying a result to the state ───────────────────────────────────────────

def test_a_corroborated_check_becomes_the_claims_basis():
    state = _state()
    verdict, _ = apply_claim_verification(state, "c", [_record("s0", holds=True),
                                                       _record("s1", holds=True)])
    assert verdict is VerificationVerdict.CORROBORATED_VALID
    assessment = state.assess_claim("c")
    assert assessment.support_state is SupportState.SUPPORTED
    assert len(assessment.basis_record_ids) >= 1


def test_a_corroborated_contradiction_falsifies_the_claim():
    state = _state()
    verdict, _ = apply_claim_verification(state, "c", [_record("s0", holds=False),
                                                       _record("s1", holds=False)])
    assert verdict is VerificationVerdict.CORROBORATED_INVALID
    assert state.assess_claim("c").support_state is SupportState.FALSIFIED


def test_an_uncorroborated_check_is_never_stored_as_a_basis():
    """The dangerous case: one seat's VERIFIED must not reach assess_claim."""
    state = _state()
    apply_claim_verification(state, "c", [_record("s0", holds=True)])
    assessment = state.assess_claim("c")
    assert assessment.support_state is SupportState.UNRESOLVED
    assert assessment.basis_record_ids == []
    stored = list(state.verifications.values())
    assert all(r.result is not VerificationResult.VERIFIED for r in stored)


def test_a_failed_check_leaves_unresolved_rather_than_unsupported():
    """Checked and unsettled is not the same as never checked."""
    state = _state()
    apply_claim_verification(state, "c", [_record("s0", holds=True),
                                          _record("s1", holds=False)])
    assessment = state.assess_claim("c")
    assert assessment.support_state is SupportState.UNRESOLVED
    assert assessment.support_state is not SupportState.UNSUPPORTED


def test_nothing_usable_coming_back_is_not_recorded_as_an_examination():
    """Never checked is not the same as checked and unsettled.

    Storing an inconclusive record here would claim the council examined the
    claim when no seat produced anything, and the claim would read UNRESOLVED
    on the strength of a check that never happened.
    """
    state = _state()
    verdict, _ = apply_claim_verification(state, "c", [])
    assert verdict is VerificationVerdict.NO_RECORDS
    assert state.verifications == {}
    assert state.assess_claim("c").support_state is SupportState.UNSUPPORTED


def test_an_objection_scoped_record_is_not_a_check_of_the_claim():
    """The distinction that made the layer a constant, now explicit."""
    state = _state()
    state.add_objection(ObjectionRecord(objection_id="o", target_claim_id="c",
                                        text="a doubt"))
    objection_check = verify_task_internal(
        claim_id="c", objection_id="o", task_text=TASK,
        cited_spans=[(C3, TASK.index(C3))], condition_tested="does it hold?",
        holds=True, rationale="checked", verifier_provider_id="s0")
    verdict, _ = apply_claim_verification(state, "c", [objection_check,
                                                       objection_check])
    assert verdict is VerificationVerdict.NO_RECORDS
    assert state.assess_claim("c").support_state is not SupportState.SUPPORTED


def test_the_verdict_is_recorded_in_the_transition_log():
    state = _state()
    apply_claim_verification(state, "c", [_record("s0", holds=True),
                                          _record("s1", holds=True)])
    kinds = [t for t in state.transitions if t.get("kind") == "claim_verification"]
    assert len(kinds) == 1
    assert kinds[0]["verdict"] == VerificationVerdict.CORROBORATED_VALID.value


# ── parsing a verifier's answer ──────────────────────────────────────────────

def _content(*, contradicted=False, established=True, span=C3):
    return {"cited_spans": [span],
            "condition_tested": "does the task settle the claimed order?",
            "claim_contradicted_by_task": contradicted,
            "claim_established_by_task": established,
            "rationale": "the quoted constraint decides it"}


def _parse(content, seat="s0"):
    return parse_claim_verification_response(
        content, task_text=TASK, claim_id="c", verifier_provider_id=seat)


def test_established_and_uncontradicted_reads_as_verified():
    record = _parse(_content())
    assert record is not None
    assert record.result is VerificationResult.VERIFIED
    assert record.objection_id is None


def test_contradicted_reads_as_falsified_whatever_else_was_said():
    record = _parse(_content(contradicted=True, established=True))
    assert record.result is VerificationResult.FALSIFIED


def test_neither_contradicted_nor_established_is_inconclusive():
    """A true claim that the task does not settle. The common, correct answer."""
    record = _parse(_content(contradicted=False, established=False))
    assert record.result is VerificationResult.INCONCLUSIVE


def test_an_undecided_verifier_is_inconclusive_not_a_guess():
    record = _parse(_content(contradicted=None, established=None))
    assert record.result is VerificationResult.INCONCLUSIVE


def test_a_fabricated_citation_produces_no_record():
    assert _parse(_content(span="Ben must present last")) is None


def test_a_missing_citation_produces_no_record():
    content = _content()
    content["cited_spans"] = []
    assert _parse(content) is None


def test_a_non_boolean_answer_produces_no_record():
    content = _content()
    content["claim_established_by_task"] = "probably"
    assert _parse(content) is None


def test_inconclusive_records_cannot_corroborate_anything():
    """Two seats politely undecided is not two seats agreeing."""
    a = _parse(_content(established=False), seat="s0")
    b = _parse(_content(established=False), seat="s1")
    result, verdict, _ = corroborated_claim_result([a, b])
    assert result is None
    assert verdict is VerificationVerdict.NO_RECORDS


# ── inside a canonical session ───────────────────────────────────────────────

class ClaimVerifyingMock(ScriptedMockProvider):
    """A seat that also answers claim-verification tasks.

    `established`/`contradicted` are what this seat reports; `span` lets a test
    make two seats agree while reading different material.
    """

    def __init__(self, provider_id, *, established=True, contradicted=False,
                 span=C3, fabricate=False):
        super().__init__(provider_id)
        self._established = established
        self._contradicted = contradicted
        self._span = span
        self._fabricate = fabricate

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is not TaskKind.CLAIM_VERIFICATION:
            return await super()._produce_raw_text(task, agent_state)
        span = "Ben must present last" if self._fabricate else self._span
        return json.dumps({"content": {
            "cited_spans": [span],
            "condition_tested": "does the task settle the claim?",
            "claim_contradicted_by_task": self._contradicted,
            "claim_established_by_task": self._established,
            "rationale": "read against the quoted constraint"},
            "confidence": 0.8})


def _run(seats, session_id):
    provider = FakeProvider()
    agents = [SocraticAgent(f"agent_{i}", provider) for i in range(4)]
    registry = CouncilProviderRegistry()
    for seat in seats:
        registry.register(seat)
    ced = CEDOrchestrator(agents, provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    final = asyncio.run(ced.run_registry_session(TASK, session_id=session_id))
    return ced, final


def _claim_verdicts(final):
    return final.audit_summary["governing_release"].get("claim_verdicts", {})


def test_a_session_can_now_reach_a_state_other_than_unresolved():
    """The point of the whole exercise."""
    seats = [ClaimVerifyingMock(f"seat{i}") for i in range(3)]
    _ced, final = _run(seats, "cv_supported")
    assert set(_claim_verdicts(final).values()) == {
        VerificationVerdict.CORROBORATED_VALID.value}
    governing = final.audit_summary["governing_release"]
    assert governing["basis_record_ids"], "a corroborated check must be a basis"


def test_a_council_that_only_agrees_establishes_nothing():
    """THE invariant. Unanimity about the answer is not evidence for it.

    Every seat says the claim is fine and none says the task establishes it.
    That is agreement, and agreement is exactly what must not become support.
    """
    seats = [ClaimVerifyingMock(f"seat{i}", established=False) for i in range(3)]
    _ced, final = _run(seats, "cv_agreement")
    governing = final.audit_summary["governing_release"]
    assert governing["basis_record_ids"] == []
    assert final.governing_epistemic_status != SupportState.SUPPORTED.value


def test_seats_agreeing_by_reading_different_passages_establish_nothing():
    seats = [ClaimVerifyingMock("seat0", span=C3),
             ClaimVerifyingMock("seat1", span=C1),
             ClaimVerifyingMock("seat2", span="Clara presents immediately before David")]
    _ced, final = _run(seats, "cv_anchors")
    assert set(_claim_verdicts(final).values()) == {
        VerificationVerdict.NO_ANCHOR_AGREEMENT.value}
    assert final.audit_summary["governing_release"]["basis_record_ids"] == []


def test_fabricated_citations_establish_nothing():
    seats = [ClaimVerifyingMock(f"seat{i}", fabricate=True) for i in range(3)]
    _ced, final = _run(seats, "cv_fabricated")
    assert set(_claim_verdicts(final).values()) == {
        VerificationVerdict.NO_RECORDS.value}
    assert final.audit_summary["governing_release"]["basis_record_ids"] == []


def test_plain_seats_leave_the_claim_where_it_was():
    """The pre-wiring behaviour, still the safe default."""
    seats = [ScriptedMockProvider(f"seat{i}") for i in range(3)]
    _ced, final = _run(seats, "cv_plain")
    assert final.governing_epistemic_status == SupportState.UNRESOLVED.value
    assert final.audit_summary["governing_release"]["basis_record_ids"] == []


def test_the_governing_status_now_varies_with_the_records():
    a = _run([ClaimVerifyingMock(f"a{i}") for i in range(3)], "cv_var_a")[1]
    b = _run([ClaimVerifyingMock(f"b{i}", established=False) for i in range(3)],
             "cv_var_b")[1]
    assert a.audit_summary["governing_release"]["basis_record_ids"] != \
        b.audit_summary["governing_release"]["basis_record_ids"]


def test_replay_reproduces_the_same_claim_verdict():
    a = _run([ClaimVerifyingMock(f"seat{i}") for i in range(3)], "cv_replay")[1]
    b = _run([ClaimVerifyingMock(f"seat{i}") for i in range(3)], "cv_replay")[1]
    assert _claim_verdicts(a) == _claim_verdicts(b)
    assert a.governing_epistemic_status == b.governing_epistemic_status


# ── the two identity bugs in the projection ──────────────────────────────────

def test_an_objection_is_attributed_to_the_seat_that_raised_it():
    """`raised_by` held an agent_id while peer filtering compares provider_ids.

    They never matched, so the no-self-verification rule excluded nobody and a
    seat could corroborate its own objection.
    """
    seats = [ScriptedMockProvider(f"seat{i}") for i in range(4)]
    ced, final = _run(seats, "cv_identity")
    core = ced.project_governing_state(ced.get_session("cv_identity"), final)
    seat_ids = {s.provider_id for s in seats}
    assert core.objections, "elenchus moves should project as objections"
    for objection in core.objections.values():
        assert objection.raised_by in seat_ids
        peers = [s for s in seat_ids if s != objection.raised_by]
        assert len(peers) == len(seat_ids) - 1, "the raiser must be excluded"


def test_a_critical_ratification_vote_projects_without_crashing():
    """The loop called three names RatificationVote does not have.

    While `ratification_votes` stayed empty the dead code was invisible; the
    first populated vote turned the AttributeError into a silently unavailable
    governing layer.
    """
    seats = [ScriptedMockProvider(f"seat{i}") for i in range(3)]
    ced, final = _run(seats, "cv_votes")
    final.ratification_votes = [
        RatificationVote(voter_agent_id="agent_1",
                         decision=RatificationDecision.BLOCKING_OBJECTION,
                         severity=ObjectionSeverity.CRITICAL,
                         reason="the core answer contradicts the second constraint"),
        RatificationVote(voter_agent_id="agent_2",
                         decision=RatificationDecision.APPROVE,
                         severity=ObjectionSeverity.NONE, reason="fine"),
    ]
    core = ced.project_governing_state(ced.get_session("cv_votes"), final)
    texts = [o.text for o in core.objections.values()]
    assert "the core answer contradicts the second constraint" in texts
    assert "fine" not in texts               # only a critical block projects
