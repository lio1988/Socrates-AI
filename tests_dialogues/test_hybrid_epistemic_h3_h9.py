"""H3..H9 adversarial regression matrix for the governing epistemic core.

Every case here is a failure the system actually produced, or an invariant whose
violation would recreate one. The two frozen known-failure fixtures supply the
benchmark text, so the anchoring in CASE 1 is against the real task.

All offline: no provider, no network, no key.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from backend.dialogues.hybrid_epistemic import (
    ClaimBallot,
    ClaimRecord,
    ContradictionRecord,
    ContradictionState,
    EvidenceApplicability,
    EvidenceCarry,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    HybridEpistemicObserver,
    HybridEpistemicState,
    MalformedVerification,
    ObjectionRecord,
    ObjectionState,
    ObjectionTransitionError,
    RatificationDisposition,
    ReleaseDecision,
    RevisionRecord,
    SupportState,
    VerificationClass,
    VerificationRecord,
    VerificationMethod,
    VerificationResult,
    external_evidence_required,
    freeze_release,
    stable_id,
    verify_task_internal,
)
from backend.dialogues.hybrid_shadow import HybridEpistemicLedger

_FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "known_failures"


def _benchmark_task() -> str:
    """The frozen logic benchmark, verbatim from the known-failure fixture."""
    data = json.loads(
        (_FIXTURES / "current_canonical_repeat_003.json").read_text(encoding="utf-8"))
    return data["benchmark"]["question_verbatim"]


def _span(task: str, needle: str):
    offset = task.index(needle)
    return (needle, offset)


def _state(task: str | None = None) -> HybridEpistemicState:
    return HybridEpistemicState("regress", task if task is not None else _benchmark_task())


def _claim(state, cid, text, vclass=VerificationClass.TASK_INTERNAL):
    return state.add_claim(ClaimRecord(claim_id=cid, text=text,
                                       verification_class=vclass))


# ══ CASE 1 — the logic puzzle ════════════════════════════════════════════════
#
# Ground truth: Anna, Ben, Clara, David. The frozen failure was a false
# counterexample destroying that correct answer through persuasion.

def test_case1_benchmark_constraints_are_present_verbatim():
    task = _benchmark_task()
    assert "Anna presents before Ben" in task
    assert "Clara presents immediately before David" in task
    assert "Ben does not present last" in task


def test_case1_false_counterexample_is_rejected_and_leaves_the_claim_standing():
    """C-D-A-B does not refute A-B-C-D: it puts Ben last, violating constraint 3."""
    task = _benchmark_task()
    state = _state(task)
    _claim(state, "c_abcd", "The unique order is Anna, Ben, Clara, David.")

    objection = state.add_objection(ObjectionRecord(
        objection_id="o_false", target_claim_id="c_abcd",
        text="C-D-A-B also satisfies every constraint, so the order is not unique."))
    state.transition_objection("o_false", ObjectionState.PENDING_VERIFICATION)

    # The check that the frozen elenchus never performed.
    check = state.add_verification(verify_task_internal(
        claim_id="c_abcd", objection_id="o_false", task_text=task,
        cited_spans=[_span(task, "Ben does not present last")],
        condition_tested="does C-D-A-B satisfy 'Ben does not present last'?",
        holds=False,
        rationale="In C-D-A-B Ben occupies position 4, so constraint 3 is violated.",
    ))
    state.transition_objection("o_false", ObjectionState.REJECTED,
                               verification_id=check.verification_id)

    assessment = state.assess_claim("c_abcd")
    assert state.objections["o_false"].state is ObjectionState.REJECTED
    assert state.objections["o_false"].is_destructive is False
    assert assessment.support_state is not SupportState.FALSIFIED
    assert assessment.eligible_for_assembly is True
    assert "o_false" not in assessment.falsifying_record_ids


def test_case1_valid_counterexample_still_falsifies():
    """The protection must not become immunity."""
    task = _benchmark_task()
    state = _state(task)
    _claim(state, "c_cdab", "The unique order is Clara, David, Anna, Ben.")
    state.add_objection(ObjectionRecord(
        objection_id="o_true", target_claim_id="c_cdab",
        text="C-D-A-B puts Ben last, which constraint 3 forbids."))
    state.transition_objection("o_true", ObjectionState.PENDING_VERIFICATION)
    check = state.add_verification(verify_task_internal(
        claim_id="c_cdab", objection_id="o_true", task_text=task,
        cited_spans=[_span(task, "Ben does not present last")],
        condition_tested="does the claimed order place Ben last?",
        holds=True,
        rationale="Clara, David, Anna, Ben places Ben in position 4.",
    ))
    state.transition_objection("o_true", ObjectionState.VALIDATED,
                               verification_id=check.verification_id)

    assessment = state.assess_claim("c_cdab")
    assert assessment.support_state is SupportState.FALSIFIED
    assert assessment.eligible_for_assembly is False
    assert "o_true" in assessment.falsifying_record_ids


def test_case1_an_unverified_objection_has_no_destructive_force():
    """RAISED persuasion is recorded and powerless. This is the frozen failure."""
    state = _state()
    _claim(state, "c_abcd", "The unique order is Anna, Ben, Clara, David.")
    state.add_objection(ObjectionRecord(
        objection_id="o_raw", target_claim_id="c_abcd",
        text="I am confident several orders work."))
    assessment = state.assess_claim("c_abcd")
    assert assessment.support_state is not SupportState.FALSIFIED
    assert assessment.falsifying_record_ids == []
    assert "o_raw" in assessment.unresolved_record_ids
    assert assessment.eligible_for_assembly is True


def test_case1_an_objection_cannot_be_validated_without_a_verification():
    state = _state()
    _claim(state, "c_abcd", "The unique order is Anna, Ben, Clara, David.")
    state.add_objection(ObjectionRecord(objection_id="o", target_claim_id="c_abcd",
                                        text="wrong"))
    state.transition_objection("o", ObjectionState.PENDING_VERIFICATION)
    with pytest.raises(ObjectionTransitionError):
        state.transition_objection("o", ObjectionState.VALIDATED)


def test_case1_scores_consensus_and_ratification_cannot_override_a_constraint_failure():
    """Everything the frozen failure used to release a wrong answer, refused."""
    task = _benchmark_task()
    state = _state(task)
    _claim(state, "c_bad", "The order is Clara, David, Anna, Ben.")
    state.add_objection(ObjectionRecord(objection_id="o", target_claim_id="c_bad",
                                        text="Ben is last."))
    state.transition_objection("o", ObjectionState.PENDING_VERIFICATION)
    check = state.add_verification(verify_task_internal(
        claim_id="c_bad", objection_id="o", task_text=task,
        cited_spans=[_span(task, "Ben does not present last")],
        condition_tested="is Ben last?", holds=True, rationale="position 4"))
    state.transition_objection("o", ObjectionState.VALIDATED,
                               verification_id=check.verification_id)

    # A unanimous, enthusiastic, top-scoring council.
    ballots = [ClaimBallot(ballot_id=f"b{i}", claim_id="c_bad",
                           ratifier_provider_id=f"seat{i}",
                           disposition=RatificationDisposition.ACCEPT,
                           rationale="Reads well.") for i in range(5)]
    release = freeze_release(state, assembled_claim_ids=["c_bad"], ballots=ballots,
                             quality_mean=9.9, legacy_epistemic_status="well_supported")

    assert release.release_decision is ReleaseDecision.BLOCKED
    assert "falsified" in release.blocked_reason
    assert release.unanchored_ballots == 5      # counted, and powerless
    assert release.quality_mean == 9.9          # reported, and powerless
    assert release.legacy_epistemic_status == "well_supported"


def test_case1_assembly_cannot_combine_validated_contradictory_claims():
    task = _benchmark_task()
    state = _state(task)
    _claim(state, "c_a", "The unique order is Anna, Ben, Clara, David.")
    _claim(state, "c_b", "There are several valid orders.")
    state.add_contradiction(ContradictionRecord(
        contradiction_id="x", claim_id_a="c_a", claim_id_b="c_b",
        detector="test"))
    check = state.add_verification(verify_task_internal(
        claim_id="c_a", objection_id=None, task_text=task,
        cited_spans=[_span(task, "Determine the unique presentation order")],
        condition_tested="are uniqueness and multiplicity jointly assertable?",
        holds=True, rationale="The task asks for a unique order; both cannot hold."))
    state.validate_contradiction("x", verification_id=check.verification_id)

    release = freeze_release(state, assembled_claim_ids=["c_a", "c_b"])
    assert release.release_decision is ReleaseDecision.BLOCKED
    assert "validated contradiction" in release.blocked_reason


# ══ CASE 2 — false premise / SPE ═════════════════════════════════════════════

SPE_TASK = ("The Stanford Prison Experiment demonstrated that ordinary people "
            "become cruel when placed in positions of institutional power.")


def test_case2_polished_high_quality_reasoning_creates_no_support():
    state = HybridEpistemicState("spe", SPE_TASK)
    state.add_claim(ClaimRecord(
        claim_id="c_spe", text="The SPE established that power corrupts.",
        verification_class=VerificationClass.EXTERNAL_EVIDENCE))
    state.add_verification(external_evidence_required(
        "c_spe", "Nothing in the task settles what the SPE established."))

    release = freeze_release(state, assembled_claim_ids=["c_spe"],
                             quality_mean=9.8,
                             legacy_epistemic_status="well_supported")
    assessment = state.assess_claim("c_spe")
    assert assessment.support_state is SupportState.EXTERNAL_EVIDENCE_REQUIRED
    assert assessment.basis_record_ids == []
    assert release.release_decision is ReleaseDecision.RELEASE_UNRESOLVED
    assert release.quality_mean == 9.8


def test_case2_a_model_assertion_is_not_external_evidence():
    """The circularity the whole migration exists to refuse."""
    state = HybridEpistemicState("spe", SPE_TASK)
    state.add_claim(ClaimRecord(claim_id="c_spe", text="The SPE established it.",
                                verification_class=VerificationClass.EXTERNAL_EVIDENCE))
    state.add_evidence(EvidenceRecord(
        evidence_id="e_vote", claim_id="c_spe", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.MODEL_ASSERTION,
        source_identity="openai/gpt-4.1-mini",
        content="Yes, this is true."))
    assessment = state.assess_claim("c_spe")
    assert state.evidence["e_vote"].admissible is False
    assert assessment.basis_record_ids == []
    assert assessment.support_state is not SupportState.SUPPORTED


def test_case2_external_verification_refuses_to_rest_on_a_model_assertion():
    state = HybridEpistemicState("spe", SPE_TASK)
    state.add_claim(ClaimRecord(claim_id="c_spe", text="x",
                                verification_class=VerificationClass.EXTERNAL_EVIDENCE))
    state.add_evidence(EvidenceRecord(
        evidence_id="e_vote", claim_id="c_spe", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.MODEL_ASSERTION, source_identity="a-model"))
    with pytest.raises(MalformedVerification, match="not external evidence"):
        state.add_verification(VerificationRecord(
            verification_id="v", claim_id="c_spe",
            verification_class=VerificationClass.EXTERNAL_EVIDENCE,
            method=VerificationMethod.EXTERNAL_SOURCE,
            evidence_ids=["e_vote"], result=VerificationResult.VERIFIED))


# ══ CASE 3 — revision ════════════════════════════════════════════════════════

def test_case3_stale_evidence_does_not_survive_a_semantic_revision():
    """The frozen `revised_claim_retains_semantically_stale_evidence`."""
    state = _state()
    _claim(state, "c_old", "The order is Clara, David, Anna, Ben.")
    _claim(state, "c_new", "The order is Anna, Ben, Clara, David.")
    state.add_evidence(EvidenceRecord(
        evidence_id="e_stale", claim_id="c_old", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.SUPPLIED_TASK_MATERIAL,
        source_identity="task", content="reasoning that supported the old order"))

    state.revise(RevisionRecord(
        revision_id="r1", from_claim_id="c_old", to_claim_id="c_new",
        reason="constraint 3 violated",
        evidence_disposition=[EvidenceCarry(evidence_id="e_stale",
                                            applicability=EvidenceApplicability.STALE,
                                            rationale="supported the superseded order")]))

    assert state.evidence["e_stale"].claim_id == "c_old"       # did not move
    assert state.assess_claim("c_new").basis_record_ids == []
    assert state.claims["c_old"].superseded_by == "c_new"
    assert state.assess_claim("c_old").eligible_for_assembly is False


def test_case3_unclassified_evidence_is_not_carried_and_is_recorded():
    state = _state()
    _claim(state, "c_old", "old")
    _claim(state, "c_new", "new")
    state.add_evidence(EvidenceRecord(
        evidence_id="e", claim_id="c_old", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.SUPPLIED_TASK_MATERIAL, source_identity="task"))
    state.revise(RevisionRecord(revision_id="r", from_claim_id="c_old",
                                to_claim_id="c_new"))
    assert state.evidence["e"].claim_id == "c_old"
    assert any(t["kind"] == "evidence_unclassified" for t in state.transitions)


def test_case3_revalidated_evidence_may_carry_across():
    state = _state()
    _claim(state, "c_old", "old")
    _claim(state, "c_new", "new")
    state.add_evidence(EvidenceRecord(
        evidence_id="e", claim_id="c_old", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.DETERMINISTIC_COMPUTATION,
        source_identity="checker"))
    state.revise(RevisionRecord(
        revision_id="r", from_claim_id="c_old", to_claim_id="c_new",
        evidence_disposition=[EvidenceCarry(
            evidence_id="e", applicability=EvidenceApplicability.REVALIDATED,
            rationale="re-checked against the revised claim")]))
    assert state.evidence["e"].claim_id == "c_new"
    assert "e" in state.assess_claim("c_new").basis_record_ids


# ══ CASE 4 — contradiction ═══════════════════════════════════════════════════

def test_case4_candidate_contradictions_penalise_nothing():
    """`contradiction_edges_are_excessively_noisy` must cost a correct claim nothing."""
    state = _state()
    _claim(state, "c_a", "A")
    _claim(state, "c_b", "B")
    for i in range(20):
        state.add_contradiction(ContradictionRecord(
            contradiction_id=f"x{i}", claim_id_a="c_a", claim_id_b="c_b",
            detector="noisy regex"))
    assessment = state.assess_claim("c_a")
    assert assessment.support_state is not SupportState.FALSIFIED
    assert assessment.eligible_for_assembly is True
    assert state.incompatible_pairs(["c_a", "c_b"]) == []
    release = freeze_release(state, assembled_claim_ids=["c_a", "c_b"])
    assert release.release_decision is not ReleaseDecision.BLOCKED


def test_case4_a_contradiction_is_validated_only_by_a_verified_record():
    state = _state()
    _claim(state, "c_a", "A")
    _claim(state, "c_b", "B")
    state.add_contradiction(ContradictionRecord(contradiction_id="x", claim_id_a="c_a",
                                                claim_id_b="c_b"))
    task = state.task_text
    inconclusive = state.add_verification(verify_task_internal(
        claim_id="c_a", objection_id=None, task_text=task,
        cited_spans=[_span(task, "Ben does not present last")],
        condition_tested="do these conflict?", holds=None,
        rationale="cannot be determined from the supplied constraints"))
    with pytest.raises(ObjectionTransitionError):
        state.validate_contradiction("x", verification_id=inconclusive.verification_id)


# ══ CASE 5 — consensus cascade ═══════════════════════════════════════════════

def test_case5_agreement_creates_no_evidence_at_any_scale():
    state = _state()
    _claim(state, "c", "a false claim everyone liked")
    for i in range(25):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"e{i}", claim_id="c", stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.MODEL_ASSERTION,
            source_identity=f"seat{i}", content="I agree."))
    assessment = state.assess_claim("c")
    assert assessment.basis_record_ids == []
    assert assessment.support_state is SupportState.UNSUPPORTED


def test_case5_an_inconsistent_ballot_is_detected_mechanically():
    """A ratifier citing a falsified check and voting accept."""
    task = _benchmark_task()
    state = _state(task)
    _claim(state, "c", "The order is Clara, David, Anna, Ben.")
    check = state.add_verification(verify_task_internal(
        claim_id="c", objection_id=None, task_text=task,
        cited_spans=[_span(task, "Ben does not present last")],
        condition_tested="constraint 3", holds=False,
        rationale="Ben is last in the claimed order"))
    ballots = [ClaimBallot(ballot_id="b1", claim_id="c", ratifier_provider_id="seat0",
                           disposition=RatificationDisposition.ACCEPT,
                           checked_verification_ids=[check.verification_id])]
    release = freeze_release(state, assembled_claim_ids=["c"], ballots=ballots)
    assert release.inconsistent_ballots == ["b1"]
    assert release.anchored_ballots == 1


# ══ CASE 6 — low quality, real support ═══════════════════════════════════════

def test_case6_a_badly_written_but_supported_claim_keeps_its_support():
    state = _state()
    _claim(state, "c", "ben not last so abcd. thats it")
    state.add_evidence(EvidenceRecord(
        evidence_id="e", claim_id="c", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.DETERMINISTIC_COMPUTATION,
        source_identity="constraint checker",
        content="Exhaustive enumeration leaves exactly one order."))
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=2.1)
    assert state.assess_claim("c").support_state is SupportState.SUPPORTED
    assert release.release_decision is ReleaseDecision.RELEASE_SUPPORTED
    assert release.quality_mean == 2.1          # low, and irrelevant to the decision


def test_case6_weak_evidence_never_becomes_a_basis():
    state = _state()
    _claim(state, "c", "x")
    state.add_evidence(EvidenceRecord(
        evidence_id="e", claim_id="c", stance=EvidenceStance.WEAK,
        source_type=EvidenceSourceType.EXTERNAL_SOURCE, source_identity="source"))
    assert state.assess_claim("c").basis_record_ids == []


# ══ CASE 7 — malformed / fail-closed ═════════════════════════════════════════

def test_case7_a_citation_absent_from_the_task_is_refused():
    task = _benchmark_task()
    state = _state(task)
    _claim(state, "c", "x")
    with pytest.raises(MalformedVerification, match="not present at offset"):
        state.add_verification(VerificationRecord(
            verification_id="v", claim_id="c",
            verification_class=VerificationClass.TASK_INTERNAL,
            method=VerificationMethod.TASK_INTERNAL_CHECK,
            authoritative_inputs=[{"text": "Ben must present last", "offset": 0}],
            condition_tested="fabricated", result=VerificationResult.FALSIFIED))


def test_case7_a_correct_citation_at_a_wrong_offset_is_refused():
    task = _benchmark_task()
    state = _state(task)
    _claim(state, "c", "x")
    real = task.index("Ben does not present last")
    with pytest.raises(MalformedVerification, match="not present at offset"):
        state.add_verification(VerificationRecord(
            verification_id="v", claim_id="c",
            verification_class=VerificationClass.TASK_INTERNAL,
            method=VerificationMethod.TASK_INTERNAL_CHECK,
            authoritative_inputs=[{"text": "Ben does not present last",
                                   "offset": real + 5}],
            condition_tested="c3", result=VerificationResult.FALSIFIED))


def test_case7_an_illegal_method_for_the_class_is_refused():
    state = _state()
    _claim(state, "c", "x")
    with pytest.raises(MalformedVerification, match="not legal"):
        state.add_verification(VerificationRecord(
            verification_id="v", claim_id="c",
            verification_class=VerificationClass.TASK_INTERNAL,
            method=VerificationMethod.EXTERNAL_SOURCE,
            result=VerificationResult.VERIFIED))


def test_case7_an_incomplete_check_becomes_inconclusive_not_a_guess():
    task = _benchmark_task()
    record = verify_task_internal(
        claim_id="c", objection_id=None, task_text=task,
        cited_spans=[_span(task, "Anna presents before Ben")],
        condition_tested="unresolvable here", holds=None,
        rationale="the supplied constraints do not settle it")
    assert record.result is VerificationResult.INCONCLUSIVE


# ══ CASE 8 — replay ══════════════════════════════════════════════════════════

def _build_replayable(task):
    state = HybridEpistemicState("replay", task)
    state.add_claim(ClaimRecord(claim_id="c", text="Anna, Ben, Clara, David"))
    state.add_evidence(EvidenceRecord(
        evidence_id="e", claim_id="c", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.DETERMINISTIC_COMPUTATION,
        source_identity="checker"))
    state.add_objection(ObjectionRecord(objection_id="o", target_claim_id="c",
                                        text="C-D-A-B works too"))
    state.transition_objection("o", ObjectionState.PENDING_VERIFICATION)
    check = state.add_verification(verify_task_internal(
        claim_id="c", objection_id="o", task_text=task,
        cited_spans=[_span(task, "Ben does not present last")],
        condition_tested="c3", holds=False, rationale="Ben last"))
    state.transition_objection("o", ObjectionState.REJECTED,
                               verification_id=check.verification_id)
    return state


def test_case8_identical_records_reproduce_the_identical_governing_state():
    task = _benchmark_task()
    a = freeze_release(_build_replayable(task), assembled_claim_ids=["c"])
    b = freeze_release(_build_replayable(task), assembled_claim_ids=["c"])
    assert a.frozen_digest == b.frozen_digest
    assert a.model_dump(mode="json") == b.model_dump(mode="json")
    assert a.release_decision is ReleaseDecision.RELEASE_SUPPORTED


def test_case8_a_changed_basis_changes_the_frozen_digest():
    task = _benchmark_task()
    base = freeze_release(_build_replayable(task), assembled_claim_ids=["c"])
    altered = _build_replayable(task)
    altered.add_evidence(EvidenceRecord(
        evidence_id="e2", claim_id="c", stance=EvidenceStance.SUPPORTING,
        source_type=EvidenceSourceType.TOOL_RECEIPT, source_identity="tool"))
    assert freeze_release(altered, assembled_claim_ids=["c"]).frozen_digest \
        != base.frozen_digest


def test_case8_ledger_projection_is_idempotent_and_replayable():
    task = _benchmark_task()
    state = _build_replayable(task)
    release = freeze_release(state, assembled_claim_ids=["c"])
    ledger = HybridEpistemicLedger()
    observer = HybridEpistemicObserver(ledger)
    first = observer.capture(state, release)
    second = observer.capture(state, release)
    assert [r.record_id for r in first] == [r.record_id for r in second]
    assert ledger.replay("replay") == ledger.records("replay")


# ══ invariants that must be structurally impossible ══════════════════════════

def test_no_numeric_epistemic_ranker_in_the_governing_core():
    banned = {"support_index", "epistemic_score", "truth_score", "support_score",
              "epistemic_rank", "cbe_score"}
    from backend.dialogues.hybrid_epistemic import ClaimAssessment, FrozenRelease
    for model in (ClaimAssessment, FrozenRelease):
        assert not (set(model.model_fields) & banned)


def test_release_never_reports_supported_without_a_basis():
    state = _state()
    _claim(state, "c", "x")
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=10.0)
    assert release.basis_record_ids == []
    assert release.release_decision is not ReleaseDecision.RELEASE_SUPPORTED
