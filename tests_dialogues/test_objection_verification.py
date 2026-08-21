"""Mid-session objection verification, and the gate that guards it.

This is the only path where a model's reading can destroy a correct claim: a
VALIDATED objection falsifies, and deterministic code proves a citation exists
but not that it was read correctly. So the gate is stricter than the release
gate needed to be — independent corroboration, unanimity, and agreement on the
same cited span.

All offline: no provider, no network, no key.
"""

from __future__ import annotations

import pytest

from backend.dialogues.hybrid_epistemic import (
    REQUIRED_CORROBORATION,
    ClaimRecord,
    HybridEpistemicState,
    ObjectionRecord,
    ObjectionState,
    SupportState,
    VerificationClass,
    VerificationResult,
    VerificationVerdict,
    apply_verification,
    corroborated_verdict,
    parse_verification_response,
    verify_task_internal,
)

TASK = ("Four researchers present once each. Anna presents before Ben. "
        "Clara presents immediately before David. Ben does not present last.")
C3 = "Ben does not present last"
C1 = "Anna presents before Ben"


def _state():
    state = HybridEpistemicState("verif", TASK)
    state.add_claim(ClaimRecord(claim_id="c", text="The order is A-B-C-D.",
                                verification_class=VerificationClass.TASK_INTERNAL))
    state.add_objection(ObjectionRecord(objection_id="o", target_claim_id="c",
                                        text="C-D-A-B works too"))
    return state


def _record(verifier, *, holds, span=C3, condition="does the order put Ben last?"):
    return verify_task_internal(
        claim_id="c", objection_id="o", task_text=TASK,
        cited_spans=[(span, TASK.index(span))],
        condition_tested=condition, holds=holds,
        rationale="checked against the cited constraint",
        verifier_provider_id=verifier)


# ── the gate ─────────────────────────────────────────────────────────────────

def test_a_single_record_never_validates_an_objection():
    """One well-cited but possibly misread check must not destroy a claim."""
    target, verdict, reason = corroborated_verdict([_record("seat0", holds=True)])
    assert target is None
    assert verdict is VerificationVerdict.UNCORROBORATED
    assert str(REQUIRED_CORROBORATION) in reason


def test_two_independent_agreeing_verifiers_validate():
    target, verdict, _ = corroborated_verdict([_record("seat0", holds=True),
                                               _record("seat1", holds=True)])
    assert target is ObjectionState.VALIDATED
    assert verdict is VerificationVerdict.CORROBORATED_VALID


def test_two_independent_agreeing_verifiers_reject():
    target, verdict, _ = corroborated_verdict([_record("seat0", holds=False),
                                               _record("seat1", holds=False)])
    assert target is ObjectionState.REJECTED
    assert verdict is VerificationVerdict.CORROBORATED_INVALID


def test_the_same_verifier_twice_is_not_corroboration():
    target, verdict, _ = corroborated_verdict([_record("seat0", holds=True),
                                               _record("seat0", holds=True)])
    assert target is None
    assert verdict is VerificationVerdict.UNCORROBORATED


def test_disagreement_is_inconclusive_and_never_a_majority():
    records = [_record("seat0", holds=True), _record("seat1", holds=True),
               _record("seat2", holds=False)]
    target, verdict, _ = corroborated_verdict(records)
    assert target is None                       # 2-1 does not carry
    assert verdict is VerificationVerdict.CONFLICTING


def test_agreeing_on_a_verdict_while_citing_different_material_is_inconclusive():
    """Same answer by different routes is not corroboration."""
    target, verdict, reason = corroborated_verdict([
        _record("seat0", holds=True, span=C3),
        _record("seat1", holds=True, span=C1),
    ])
    assert target is None
    assert verdict is VerificationVerdict.NO_ANCHOR_AGREEMENT
    assert "different material" in reason


def test_no_records_leaves_the_objection_alone():
    target, verdict, _ = corroborated_verdict([])
    assert target is None
    assert verdict is VerificationVerdict.NO_RECORDS


# ── applying a verdict to the state ──────────────────────────────────────────

def test_corroborated_rejection_leaves_the_claim_standing():
    """The frozen failure, inverted: a false counterexample is refused."""
    state = _state()
    verdict, _ = apply_verification(state, "o", [_record("seat0", holds=False),
                                                 _record("seat1", holds=False)])
    assert verdict is VerificationVerdict.CORROBORATED_INVALID
    assert state.objections["o"].state is ObjectionState.REJECTED
    assessment = state.assess_claim("c")
    assert assessment.support_state is not SupportState.FALSIFIED
    assert assessment.eligible_for_assembly is True


def test_corroborated_validation_falsifies_the_claim():
    state = _state()
    verdict, _ = apply_verification(state, "o", [_record("seat0", holds=True),
                                                 _record("seat1", holds=True)])
    assert verdict is VerificationVerdict.CORROBORATED_VALID
    assert state.objections["o"].state is ObjectionState.VALIDATED
    assert state.assess_claim("c").support_state is SupportState.FALSIFIED


def test_an_uncorroborated_check_leaves_the_objection_inconclusive():
    state = _state()
    verdict, _ = apply_verification(state, "o", [_record("seat0", holds=True)])
    assert verdict is VerificationVerdict.UNCORROBORATED
    assert state.objections["o"].state is ObjectionState.INCONCLUSIVE
    assert state.objections["o"].is_destructive is False
    assert state.assess_claim("c").support_state is SupportState.UNRESOLVED


# ── parsing a verifier's output ──────────────────────────────────────────────

def _content(span=C3, holds=True, condition="is Ben last?"):
    return {"cited_spans": [{"text": span, "offset": TASK.index(span)}],
            "condition_tested": condition, "objection_holds": holds,
            "rationale": "position 4"}


def test_a_well_formed_response_becomes_a_record():
    record = parse_verification_response(
        _content(), task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    assert record is not None
    assert record.verifier_provider_id == "seat0"
    assert record.authoritative_inputs[0].text == C3


def test_a_fabricated_citation_produces_no_record_at_all():
    """Refused outright rather than downgraded into a weaker signal."""
    bad = {"cited_spans": [{"text": "Ben must present last", "offset": 0}],
           "condition_tested": "invented", "objection_holds": True}
    assert parse_verification_response(
        bad, task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0") is None


def test_a_correct_citation_with_a_wrong_offset_is_resolved_by_search():
    """The Level-3 live failure, no longer fatal.

    A verifier quoted the task correctly and reported offset 134 for text at 89.
    Asking a model for a character offset asks it to do the one thing it is
    worst at, and discarding a sound check over it helps nobody. The model
    quotes; the protocol locates. Any supplied offset is ignored.
    """
    supplied = {"cited_spans": [{"text": C3, "offset": TASK.index(C3) + 47}],
                "condition_tested": "c3", "objection_holds": True}
    record = parse_verification_response(
        supplied, task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    assert record is not None
    assert record.authoritative_inputs[0].offset == TASK.index(C3)


def test_a_span_needs_no_offset_at_all():
    for span in ({"text": C3}, C3):
        record = parse_verification_response(
            {"cited_spans": [span], "condition_tested": "c3",
             "objection_holds": False},
            task_text=TASK, claim_id="c", objection_id="o",
            verifier_provider_id="seat0")
        assert record is not None
        assert record.authoritative_inputs[0].offset == TASK.index(C3)


def test_whitespace_differences_do_not_break_a_faithful_quotation():
    """A model re-typing a line across a wrap is still quoting faithfully."""
    record = parse_verification_response(
        {"cited_spans": ["Ben  does   not  present last"],
         "condition_tested": "c3", "objection_holds": False},
        task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    assert record is not None
    assert record.authoritative_inputs[0].offset == TASK.index(C3)


@pytest.mark.parametrize("content", [
    None, "a string", 42, {},
    {"cited_spans": [], "condition_tested": "x", "objection_holds": True},
    {"cited_spans": [{"text": C3, "offset": 0}], "condition_tested": "",
     "objection_holds": True},
    {"cited_spans": [{"text": C3, "offset": 0}], "condition_tested": "x",
     "objection_holds": "maybe"},
])
def test_malformed_responses_contribute_nothing(content):
    assert parse_verification_response(
        content, task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0") is None


def test_an_undecidable_check_parses_as_inconclusive_and_cannot_corroborate():
    record = parse_verification_response(
        _content(holds=None), task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    assert record is not None
    target, verdict, _ = corroborated_verdict([record, record])
    assert target is None
    assert verdict is VerificationVerdict.NO_RECORDS


# ── the risk this gate exists to bound ───────────────────────────────────────

def test_one_misreading_verifier_cannot_destroy_a_correct_claim():
    """The named risk: a real citation, a wrong reading, a correct claim.

    Alone it cannot validate. It needs an independent verifier to agree on the
    same span, and if a second verifier reads the span correctly the result is
    CONFLICTING rather than a majority verdict.
    """
    state = _state()
    misreader = _record("seat0", holds=True)          # says the objection holds
    correct = _record("seat1", holds=False)           # says it does not
    verdict, _ = apply_verification(state, "o", [misreader, correct])
    assert verdict is VerificationVerdict.CONFLICTING
    assert state.objections["o"].state is ObjectionState.INCONCLUSIVE
    assert state.assess_claim("c").support_state is not SupportState.FALSIFIED


# ── the Level-3 live outputs, replayed ───────────────────────────────────────

#: The Level-3 task, verbatim.
LEVEL3_TASK = """Four people — Anna, Ben, Clara, and David — must present one at a time.

Constraints:

* Anna presents before Ben.
* Clara presents immediately before David.
* Ben is not last.

Question:
Determine the unique presentation order and explain why it is unique."""

#: What the six live verifiers actually produced: (seat, quoted, offset, holds).
LEVEL3_VERIFIER_OUTPUTS = [
    ("seat1", "the claim that the unique presentation order", 0, True),
    ("seat0", "The claim that the unique presentation order", 0, True),
    ("seat2", "Anna presents before Ben.", 134, False),
    ("seat2", "The reasoning provided does not systematical", 56, True),
    ("seat1", "The assumption that there is a unique presen", 0, True),
    ("seat0", "The assumption that there is a unique presen", 0, True),
]


def _replay_level3():
    records = []
    for seat, text, offset, holds in LEVEL3_VERIFIER_OUTPUTS:
        record = parse_verification_response(
            {"cited_spans": [{"text": text, "offset": offset}],
             "condition_tested": "live", "objection_holds": holds,
             "rationale": "live"},
            task_text=LEVEL3_TASK, claim_id="c", objection_id="o",
            verifier_provider_id=seat)
        records.append((seat, holds, record))
    return records


def test_the_sound_live_check_is_rescued_by_offset_resolution():
    """One verifier quoted the task correctly at the wrong offset. It now counts."""
    rescued = [(s, r) for s, _h, r in _replay_level3() if r is not None]
    assert len(rescued) == 1
    seat, record = rescued[0]
    assert seat == "seat2"
    assert record.authoritative_inputs[0].text == "Anna presents before Ben."
    assert record.authoritative_inputs[0].offset == LEVEL3_TASK.index(
        "Anna presents before Ben.")


def test_the_five_unsound_live_checks_are_still_refused():
    """They quoted the objection or their own prose. None becomes a record."""
    refused = [(s, h) for s, h, r in _replay_level3() if r is None]
    assert len(refused) == 5
    # And every one of them claimed the objection HELD, which would have
    # destroyed a correct answer under any majority rule.
    assert all(holds for _seat, holds in refused)


def test_the_replayed_live_run_still_destroys_nothing():
    records = [r for _s, _h, r in _replay_level3() if r is not None]
    target, verdict, _reason = corroborated_verdict(records)
    assert target is None
    assert verdict is VerificationVerdict.UNCORROBORATED


# ── partial citation resolution ──────────────────────────────────────────────

def test_a_mostly_sound_citation_list_survives_one_bad_span():
    """The second live run: six real quotations, one mangled em-dash.

    Discarding the whole check for a transcription artifact helps nobody, and a
    dropped span can never become a shared anchor, so padding with fabrications
    buys a verifier nothing.
    """
    record = parse_verification_response(
        {"cited_spans": [C3, "Four people —6 mangled dash", C1],
         "condition_tested": "c3", "objection_holds": False,
         "rationale": "x"},
        task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    assert record is not None
    assert [s.text for s in record.authoritative_inputs] == [C3, C1]
    assert record.unresolved_citations == 1


def test_a_verifier_whose_every_citation_is_invented_still_produces_nothing():
    record = parse_verification_response(
        {"cited_spans": ["Ben must present last", "Anna presents after Ben"],
         "condition_tested": "invented", "objection_holds": True},
        task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    assert record is None


def test_dropped_spans_cannot_become_shared_anchors():
    """Two verifiers agreeing only through fabricated spans corroborate nothing."""
    a = parse_verification_response(
        {"cited_spans": [C3, "invented alpha"], "condition_tested": "x",
         "objection_holds": True, "rationale": "r"},
        task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    b = parse_verification_response(
        {"cited_spans": [C1, "invented alpha"], "condition_tested": "x",
         "objection_holds": True, "rationale": "r"},
        task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat1")
    assert a.unresolved_citations == b.unresolved_citations == 1
    target, verdict, _ = corroborated_verdict([a, b])
    assert target is None
    assert verdict is VerificationVerdict.NO_ANCHOR_AGREEMENT


# ── objections that are not about the task ───────────────────────────────────

def test_a_methodological_objection_needs_no_citation():
    """"The enumeration was not systematic" says nothing the task can settle.

    Demanding a task citation for it invites a fabricated one, or discards a
    verifier for answering honestly. Four of six live verifiers were refused
    this way.
    """
    record = parse_verification_response(
        {"objection_concerns_the_task": False, "cited_spans": [],
         "condition_tested": "whether the objection concerns the task",
         "objection_holds": None,
         "rationale": "It criticises how the answer was derived."},
        task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    assert record is not None
    assert record.result is VerificationResult.NOT_APPLICABLE
    assert record.authoritative_inputs == []
    assert record.method is None


def test_not_applicable_records_never_validate_or_reject():
    records = [
        parse_verification_response(
            {"objection_concerns_the_task": False, "cited_spans": [],
             "condition_tested": "x", "objection_holds": None, "rationale": "r"},
            task_text=TASK, claim_id="c", objection_id="o",
            verifier_provider_id=seat)
        for seat in ("seat0", "seat1", "seat2")
    ]
    target, verdict, reason = corroborated_verdict(records)
    assert target is None
    assert verdict is VerificationVerdict.NOT_TASK_CHECKABLE
    assert "no claim the task can settle" in reason


def test_a_not_applicable_record_cannot_corroborate_a_real_check():
    """Mixing "not about the task" with a real check is not agreement."""
    real = _record("seat0", holds=True)
    not_applicable = parse_verification_response(
        {"objection_concerns_the_task": False, "cited_spans": [],
         "condition_tested": "x", "objection_holds": None, "rationale": "r"},
        task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat1")
    target, verdict, _ = corroborated_verdict([real, not_applicable])
    assert target is None
    assert verdict is VerificationVerdict.UNCORROBORATED


def test_the_applicability_flag_does_not_excuse_a_fabricated_citation():
    """Claiming the objection IS about the task still requires a real quote."""
    record = parse_verification_response(
        {"objection_concerns_the_task": True,
         "cited_spans": ["Ben must present last"],
         "condition_tested": "invented", "objection_holds": True,
         "rationale": "r"},
        task_text=TASK, claim_id="c", objection_id="o",
        verifier_provider_id="seat0")
    assert record is None


def test_an_objection_declared_not_task_checkable_stays_unresolved():
    state = _state()
    records = [
        parse_verification_response(
            {"objection_concerns_the_task": False, "cited_spans": [],
             "condition_tested": "x", "objection_holds": None, "rationale": "r"},
            task_text=TASK, claim_id="c", objection_id="o",
            verifier_provider_id=seat)
        for seat in ("seat0", "seat1")
    ]
    verdict, _ = apply_verification(state, "o", records)
    assert verdict is VerificationVerdict.NOT_TASK_CHECKABLE
    assert state.objections["o"].state is ObjectionState.INCONCLUSIVE
    assert state.objections["o"].is_destructive is False
    assert state.assess_claim("c").support_state is SupportState.UNRESOLVED
