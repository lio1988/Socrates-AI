"""Anchor equivalence: same source, same version, materially overlapping span.

Two verifiers in live run 3 quoted the same sentence, one with the closing full
stop and one without. Exact identity called those different anchors. They are
not: they observe the same passage.

Text similarity has no authority here. The rule compares source identity,
source version and character intervals, and nothing else — identical wording
elsewhere, in another document, or against another version stays distinct.

Agreement on an anchor means verifiers read the same material. It never means
their reading was right, and it never decides what a sustained objection damages.

All offline: pure functions, no provider, no network.
"""

from __future__ import annotations

import pytest

from backend.dialogues.hybrid_epistemic import (
    MATERIAL_OVERLAP_RATIO,
    AnchorSpan,
    ClaimRecord,
    HybridEpistemicState,
    ObjectionRecord,
    ObjectionScope,
    ObjectionState,
    SupportState,
    VerificationClass,
    VerificationVerdict,
    anchors_equivalent,
    apply_verification,
    corroborated_verdict,
    source_digest,
    verify_task_internal,
)

TASK = ("Four people must present one at a time. Anna presents before Ben. "
        "Clara presents immediately before David. Ben is not last.")
C3 = "Ben is not last."
DIGEST = source_digest(TASK)


def _span(text, offset, *, source_id="task", digest=DIGEST):
    return AnchorSpan(text=text, offset=offset, source_id=source_id,
                      source_digest=digest)


# ── 1-3, 8: equivalent ───────────────────────────────────────────────────────

def test_1_punctuation_only_containment_is_equivalent():
    """The frozen run-3 pair."""
    assert anchors_equivalent(_span("Ben is not last.", 160),
                              _span("Ben is not last", 160)) is True


def test_2_a_one_character_endpoint_difference_is_equivalent():
    assert anchors_equivalent(_span("Clara presents immediately", 10),
                              _span("lara presents immediately", 11)) is True


def test_3_an_identical_span_is_equivalent_to_itself():
    span = _span(C3, 160)
    assert anchors_equivalent(span, span) is True


def test_8_strong_containment_is_equivalent():
    long_span = _span("A" * 50, 100)
    inner = _span("B" * 45, 103)          # 45 of 45 inside the longer span
    assert anchors_equivalent(long_span, inner) is True


# ── 4-7: not equivalent ──────────────────────────────────────────────────────

def test_4_the_same_text_at_a_different_offset_is_not_equivalent():
    """A phrase repeated in a document is two passages, not one."""
    assert anchors_equivalent(_span(C3, 160), _span(C3, 400)) is False


def test_5_the_same_offsets_under_a_different_digest_are_not_equivalent():
    """A quotation that matched an earlier revision does not observe this one."""
    assert anchors_equivalent(_span(C3, 160),
                              _span(C3, 160, digest="a-different-version")) is False


def test_6_the_same_offsets_in_a_different_document_are_not_equivalent():
    assert anchors_equivalent(_span(C3, 160),
                              _span(C3, 160, source_id="other_document")) is False


def test_7_small_incidental_overlap_is_not_equivalent():
    """One shared character between two long passages merges nothing."""
    a = _span("x" * 100, 100)             # [100, 200)
    b = _span("y" * 100, 199)             # [199, 299) - overlaps by 1
    assert anchors_equivalent(a, b) is False


@pytest.mark.parametrize("shorter_len,overlap,expected", [
    (10, 10, True),                        # full containment
    (10, 8, True),                         # exactly at the threshold
    (10, 7, False),                        # just under it
    (100, 1, False),                       # incidental
])
def test_the_threshold_is_measured_against_the_shorter_span(
        shorter_len, overlap, expected):
    long_span = _span("L" * 200, 0)
    start = overlap and (overlap - shorter_len) or 0
    short = _span("S" * shorter_len, max(0, 200 - overlap))
    assert anchors_equivalent(long_span, short) is expected
    assert MATERIAL_OVERLAP_RATIO == 0.8


def test_non_overlapping_spans_are_never_equivalent():
    assert anchors_equivalent(_span("a" * 10, 0), _span("b" * 10, 50)) is False


# ── 9-11: equivalence does not decide effect ─────────────────────────────────

def _state():
    state = HybridEpistemicState("anchor", TASK)
    state.add_claim(ClaimRecord(claim_id="c", text="The order is A-B-C-D.",
                                verification_class=VerificationClass.TASK_INTERNAL))
    state.add_objection(ObjectionRecord(objection_id="o", target_claim_id="c",
                                        text="uniqueness was not established"))
    return state


def _record(seat, *, holds, text=C3, scope=ObjectionScope.JUSTIFICATION):
    return verify_task_internal(
        claim_id="c", objection_id="o", task_text=TASK,
        cited_spans=[(text, TASK.index(text))],
        condition_tested="was uniqueness established?", holds=holds,
        rationale="checked the cited passage", verifier_provider_id=seat,
        objection_scope=scope)


def test_9_equivalent_anchors_with_a_justification_objection_do_not_falsify():
    """MANDATORY: the frozen run-3 near-miss, end to end.

    Two verifiers now agree on the anchor, and the objection they sustain is
    aimed at the reasoning. The claim loses its support and keeps its truth.
    """
    state = _state()
    a = _record("seat0", holds=True, text="Ben is not last.")
    b = _record("seat1", holds=True, text="Ben is not last")
    assert anchors_equivalent(a.authoritative_inputs[0],
                              b.authoritative_inputs[0]) is True

    verdict, reason = apply_verification(state, "o", [a, b])
    assert verdict is VerificationVerdict.CORROBORATED_VALID
    assert "not refuted" in reason
    objection = state.objections["o"]
    assert objection.state is ObjectionState.VALIDATED
    assert objection.is_destructive is False
    assessment = state.assess_claim("c")
    assert assessment.support_state is SupportState.UNRESOLVED
    assert assessment.support_state is not SupportState.FALSIFIED
    assert assessment.falsifying_record_ids == []


def test_10_equivalent_anchors_with_a_conclusion_counterexample_may_falsify():
    state = _state()
    verdict, reason = apply_verification(state, "o", [
        _record("seat0", holds=True, text="Ben is not last.",
                scope=ObjectionScope.CONCLUSION),
        _record("seat1", holds=True, text="Ben is not last",
                scope=ObjectionScope.CONCLUSION),
    ])
    assert verdict is VerificationVerdict.CORROBORATED_VALID
    assert "refutes the claim" in reason
    assert state.objections["o"].is_destructive is True
    assert state.assess_claim("c").support_state is SupportState.FALSIFIED


def test_11_five_of_six_agreeing_on_an_anchor_does_not_create_falsification():
    """Anchor agreement is agreement on material, not on interpretation."""
    state = _state()
    records = [_record(f"seat{i}", holds=True, text="Ben is not last.")
               for i in range(5)]
    records.append(_record("seat5", holds=True, text="Ben is not last"))
    verdict, _ = apply_verification(state, "o", records)
    assert verdict is VerificationVerdict.CORROBORATED_VALID
    # Six verifiers, one anchor, and still no refutation: the objection is
    # aimed at the justification.
    assert state.assess_claim("c").support_state is not SupportState.FALSIFIED


def test_anchor_agreement_alone_never_reaches_a_verdict():
    """Verifiers reading the same passage to opposite conclusions stay split."""
    state = _state()
    verdict, _ = apply_verification(state, "o", [
        _record("seat0", holds=True, text="Ben is not last."),
        _record("seat1", holds=False, text="Ben is not last"),
    ])
    assert verdict is VerificationVerdict.CONFLICTING
    assert state.objections["o"].state is ObjectionState.INCONCLUSIVE


def test_agreement_on_different_passages_is_still_not_corroboration():
    """The rule loosened endpoints, not the requirement to read the same thing."""
    state = _state()
    verdict, _ = apply_verification(state, "o", [
        _record("seat0", holds=True, text="Ben is not last."),
        _record("seat1", holds=True, text="Anna presents before Ben."),
    ])
    assert verdict is VerificationVerdict.NO_ANCHOR_AGREEMENT


# ── 12: determinism ──────────────────────────────────────────────────────────

def test_12_equivalence_is_a_pure_deterministic_function():
    a = _span("Ben is not last.", 160)
    b = _span("Ben is not last", 160)
    results = {anchors_equivalent(a, b) for _ in range(50)}
    assert results == {True}
    assert source_digest(TASK) == source_digest(TASK)
    assert source_digest(TASK) != source_digest(TASK + " ")


def test_12_replay_reproduces_the_same_corroboration_outcome():
    def build():
        return [_record("seat0", holds=True, text="Ben is not last."),
                _record("seat1", holds=True, text="Ben is not last")]

    first = corroborated_verdict(build())
    second = corroborated_verdict(build())
    assert first == second


def test_every_span_carries_its_source_identity_and_version():
    record = _record("seat0", holds=True)
    span = record.authoritative_inputs[0]
    assert span.source_id == "task"
    assert span.source_digest == source_digest(TASK)
    assert span.end == span.offset + len(span.text)
