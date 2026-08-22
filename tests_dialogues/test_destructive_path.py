"""The red brake: a false conclusion, refuted by computation, blocked at release.

Three live runs proved the positive arm — correct answer, deterministic receipt,
admissible basis, SUPPORTED, RELEASE_SUPPORTED. The council was right all three
times, so the arm that matters more was never exercised: can this layer stop a
wrong answer that every model believes?

Waiting for the council to slip is not an experiment. If it answers correctly we
learn nothing. So the false conclusion is supplied deliberately and put through
the same machinery the live path uses — task parsing, the checker, receipt
creation, evidence ingestion, assess_claim, freeze_release. Nothing is mocked;
the checker discovers the violated constraint itself.

The near-miss is chosen to be hard: it satisfies four of five constraints and
fails only the negative one.

All offline: scripted providers, no network, no key.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.hybrid_epistemic import (
    ClaimRecord,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    HybridEpistemicState,
    ObjectionRecord,
    ObjectionScope,
    ObjectionState,
    ReleaseDecision,
    SupportState,
    VerificationClass,
    freeze_release,
    verify_task_internal,
)
from backend.dialogues.models import (
    AgentState, AgentTask, ObjectionSeverity, RatificationDecision,
    RatificationVote, ShadowScoringMode, TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry, ScriptedMockProvider,
)
from backend.dialogues.providers import FakeProvider
from backend.dialogues.task_checker import (
    AUTHORITY_CLASS,
    CheckerStatus,
    NotApplicableReason,
    evaluate_candidate,
    model_task,
    receipt_refutation,
    receipt_support,
)

TASK = ("Six analysts — Anna, Ben, Clara, David, Elena, and Farid — occupy six "
        "consecutive positions, one per position. "
        "Clara is first. "
        "Anna is immediately before Elena. "
        "Ben is not immediately before Anna. "
        "Elena is last. "
        "Farid is before Ben.")

TRUE_ORDER = ("Clara", "Farid", "Ben", "David", "Anna", "Elena")
FALSE_ORDER = ("Clara", "Farid", "David", "Ben", "Anna", "Elena")

TRUE_ANSWER = "The unique order is Clara, Farid, Ben, David, Anna, Elena."
FALSE_ANSWER = "The unique order is Clara, Farid, David, Ben, Anna, Elena."

#: The one constraint the near-miss breaks. Everything else it satisfies.
BROKEN = "Ben not immediately before Anna"


# ══ the task reduces, and the ground truth is what we think it is ════════════

def test_the_task_reduces_to_one_solution():
    model, reason = model_task(TASK)
    assert model is not None, reason
    assert model.entities == ("Anna", "Ben", "Clara", "David", "Elena", "Farid")
    assert model.constraint_names == (
        "Clara first", "Anna immediately before Elena", BROKEN,
        "Elena last", "Farid before Ben")
    assert model.solutions == (TRUE_ORDER,)


def test_the_false_candidate_is_a_near_miss_not_an_obvious_error():
    """Four of five constraints hold. Only the negative one fails."""
    receipt = evaluate_candidate(TASK, FALSE_ANSWER)
    assert len(receipt.satisfied_constraints) == 4
    assert receipt.violated_constraints == (BROKEN,)


# ══ CONTROLLED NEGATIVE: the checker refutes it ══════════════════════════════

def test_the_checker_discovers_the_violation_itself():
    receipt = evaluate_candidate(TASK, FALSE_ANSWER)
    assert receipt.result is CheckerStatus.INVALID
    assert receipt.candidate_checked == "Clara, Farid, David, Ben, Anna, Elena"
    assert BROKEN in receipt.violated_constraints
    assert receipt.deterministic is True
    assert receipt.authority_class == AUTHORITY_CLASS
    assert receipt.candidate_is_invalid is True
    assert receipt.candidate_is_valid is False


def test_an_invalid_receipt_can_never_create_support():
    receipt = evaluate_candidate(TASK, FALSE_ANSWER)
    assert receipt.establishes_the_candidate is False
    assert receipt_support(receipt, "c") is None


def _falsified_state(text=FALSE_ANSWER, claim_id="final_verdict"):
    """Run the false conclusion through the real ingestion path."""
    state = HybridEpistemicState("neg", TASK)
    state.add_claim(ClaimRecord(claim_id=claim_id, text=text,
                                section="final_verdict",
                                verification_class=VerificationClass.TASK_INTERNAL))
    receipt = evaluate_candidate(TASK, text)
    refutation = receipt_refutation(receipt, claim_id, TASK)
    if refutation is not None:
        state.add_verification(refutation)
    return state, receipt


def test_the_governing_claim_becomes_falsified():
    state, _ = _falsified_state()
    assert state.assess_claim("final_verdict").support_state is SupportState.FALSIFIED


def test_the_release_is_blocked_and_says_why():
    state, _ = _falsified_state()
    release = freeze_release(state, assembled_claim_ids=["final_verdict"],
                             quality_mean=10.0,
                             legacy_epistemic_status="well_supported")
    assert release.release_decision is ReleaseDecision.BLOCKED
    assert "falsified" in release.blocked_reason
    assert release.basis_record_ids == []


def test_invalid_is_not_softened_into_unresolved():
    """A conclusive refutation of the exact governing proposition is conclusive."""
    state, _ = _falsified_state()
    assessment = state.assess_claim("final_verdict")
    assert assessment.support_state is SupportState.FALSIFIED
    assert assessment.support_state is not SupportState.UNRESOLVED
    assert assessment.eligible_for_assembly is False


# ══ POSITIVE CONTROL: only the candidate changes ═════════════════════════════

def test_the_true_candidate_is_supported_and_released():
    state = HybridEpistemicState("pos", TASK)
    state.add_claim(ClaimRecord(claim_id="final_verdict", text=TRUE_ANSWER,
                                section="final_verdict",
                                verification_class=VerificationClass.TASK_INTERNAL))
    receipt = evaluate_candidate(TASK, TRUE_ANSWER)
    assert receipt.result is CheckerStatus.VALID
    assert receipt.candidate_is_unique is True
    state.add_evidence(receipt_support(receipt, "final_verdict"))

    assert state.assess_claim("final_verdict").support_state is SupportState.SUPPORTED
    release = freeze_release(state, assembled_claim_ids=["final_verdict"],
                             quality_mean=1.0)
    assert release.release_decision is ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids


def test_the_two_controls_differ_only_in_the_candidate():
    """Same task, same path, same everything but six names in an order."""
    def outcome(answer):
        state = HybridEpistemicState("ab", TASK)
        state.add_claim(ClaimRecord(claim_id="final_verdict", text=answer,
                                    section="final_verdict",
                                    verification_class=VerificationClass.TASK_INTERNAL))
        receipt = evaluate_candidate(TASK, answer)
        support = receipt_support(receipt, "final_verdict")
        refutation = receipt_refutation(receipt, "final_verdict", TASK)
        if support is not None:
            state.add_evidence(support)
        if refutation is not None:
            state.add_verification(refutation)
        return freeze_release(state, assembled_claim_ids=["final_verdict"],
                              quality_mean=10.0).release_decision

    assert outcome(TRUE_ANSWER) is ReleaseDecision.RELEASE_SUPPORTED
    assert outcome(FALSE_ANSWER) is ReleaseDecision.BLOCKED


# ══ AUTHORITY: nothing a council can do overrides the computation ════════════

def _state_with_false_claim():
    state, _ = _falsified_state()
    return state


@pytest.mark.parametrize("seats", [2, 4])
def test_1_unanimous_models_supporting_the_false_candidate_change_nothing(seats):
    state = _state_with_false_claim()
    for i in range(seats):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"m{i}", claim_id="final_verdict",
            stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.CORROBORATED_MODEL_INTERPRETATION,
            source_identity=f"seat{i}", content="we all read it this way"))
    assert state.assess_claim("final_verdict").support_state is SupportState.FALSIFIED
    release = freeze_release(state, assembled_claim_ids=["final_verdict"])
    assert release.release_decision is ReleaseDecision.BLOCKED
    assert release.basis_record_ids == []


def test_2_ratification_accepting_the_false_candidate_changes_nothing():
    state = _state_with_false_claim()
    release = freeze_release(state, assembled_claim_ids=["final_verdict"],
                             legacy_epistemic_status="well_supported")
    assert release.release_decision is ReleaseDecision.BLOCKED
    assert release.legacy_epistemic_status == "well_supported"   # recorded, inert


def test_3_a_perfect_quality_mean_changes_nothing():
    state = _state_with_false_claim()
    release = freeze_release(state, assembled_claim_ids=["final_verdict"],
                             quality_mean=10.0,
                             legacy_epistemic_status="well_supported")
    assert release.quality_mean == 10.0
    assert release.release_decision is ReleaseDecision.BLOCKED


def test_4_seat_verifications_cannot_overturn_a_deterministic_invalid():
    """Four seats verifying the false claim, all well formed, all anchored."""
    state = _state_with_false_claim()
    for i in range(4):
        state.add_verification(verify_task_internal(
            claim_id="final_verdict", objection_id=None, task_text=TASK,
            cited_spans=[("Clara is first", TASK.index("Clara is first"))],
            condition_tested="does the task establish this order?", holds=True,
            rationale="it does", verifier_provider_id=f"seat{i}"))
    assert state.assess_claim("final_verdict").support_state is SupportState.FALSIFIED
    assert freeze_release(
        state, assembled_claim_ids=["final_verdict"]
    ).release_decision is ReleaseDecision.BLOCKED


def test_5_models_cannot_manufacture_a_valid_without_a_receipt():
    """The positive direction of the same firewall."""
    state = HybridEpistemicState("no_receipt", TASK)
    state.add_claim(ClaimRecord(claim_id="final_verdict", text=TRUE_ANSWER,
                                section="final_verdict",
                                verification_class=VerificationClass.TASK_INTERNAL))
    for i in range(4):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"m{i}", claim_id="final_verdict",
            stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.MODEL_ASSERTION,
            source_identity=f"seat{i}", content="correct"))
        state.add_verification(verify_task_internal(
            claim_id="final_verdict", objection_id=None, task_text=TASK,
            cited_spans=[("Elena is last", TASK.index("Elena is last"))],
            condition_tested="established?", holds=True, rationale="yes",
            verifier_provider_id=f"seat{i}"))
    assessment = state.assess_claim("final_verdict")
    assert assessment.basis_record_ids == []
    assert assessment.support_state is not SupportState.SUPPORTED


def test_6_invalid_and_not_applicable_remain_distinct():
    invalid = evaluate_candidate(TASK, FALSE_ANSWER)
    declined = evaluate_candidate(TASK, "Clara, Farid, David, Ben, Anna, Elena")
    assert invalid.result is CheckerStatus.INVALID
    assert declined.result is CheckerStatus.NOT_APPLICABLE
    assert declined.reason == NotApplicableReason.NO_CANDIDATE.value
    # Only one of them refutes anything.
    assert receipt_refutation(invalid, "c", TASK) is not None
    assert receipt_refutation(declined, "c", TASK) is None


def test_7_the_violated_constraint_survives_the_audit_and_a_replay():
    a = evaluate_candidate(TASK, FALSE_ANSWER)
    b = evaluate_candidate(TASK, FALSE_ANSWER)
    assert a.digest() == b.digest()
    wire = json.loads(json.dumps(a.to_dict()))
    assert wire["violated_constraints"] == [BROKEN]
    assert wire["result"] == CheckerStatus.INVALID.value
    assert wire["authority_class"] == AUTHORITY_CLASS

    record = receipt_refutation(a, "final_verdict", TASK)
    assert BROKEN in record.rationale
    assert record.verifier_provider_id is None       # nothing read it
    # The record carries the whole receipt, so the refutation is replayable
    # from the stored verification alone.
    embedded = json.loads(record.rationale[record.rationale.index("{"):])
    assert embedded["violated_constraints"] == [BROKEN]
    assert embedded["authority_class"] == AUTHORITY_CLASS


# ══ the same thing through a whole session ═══════════════════════════════════

class FalseAnswerCouncil(ScriptedMockProvider):
    """A council that is confident, unanimous, and wrong."""

    def __init__(self, provider_id, *, answer=FALSE_ANSWER):
        super().__init__(provider_id)
        self._answer = answer

    def _ratification_verdict(self, task):
        return {"verdict": "accept", "confidence": 0.99,
                "rationale": "The derivation is airtight and we all agree."}

    async def _produce_raw_text(self, task: AgentTask, agent_state: AgentState) -> str:
        if task.task_kind is TaskKind.SYNTHESIS_DRAFT:
            return json.dumps({"content": {
                "core_answer": self._answer,
                "crucial_stress_test": "We tested every alternative and found none.",
                "blind_spots": "None material.",
                "nuance": "The constraints are unambiguous.",
                "final_verdict": self._answer}, "confidence": 0.99})
        return await super()._produce_raw_text(task, agent_state)


def _session(answer, session_id):
    provider = FakeProvider()
    registry = CouncilProviderRegistry()
    for i in range(4):
        registry.register(FalseAnswerCouncil(f"seat{i}", answer=answer))
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                          provider, registry=registry,
                          shadow_scoring_mode=ShadowScoringMode.ALL_PHASES)
    return asyncio.run(ced.run_registry_session(TASK, session_id=session_id))


def test_a_whole_session_asserting_the_false_order_is_blocked():
    """Every seat says it, ratification accepts it, and it does not get out."""
    final = _session(FALSE_ANSWER, "neg_session")
    governing = final.audit_summary["governing_release"]
    assert final.governing_epistemic_status == SupportState.FALSIFIED.value
    assert final.release_decision == ReleaseDecision.BLOCKED.value
    assert "falsified" in governing["blocked_reason"]
    assert governing["basis_record_ids"] == []
    checks = governing["deterministic_checks"]
    results = {e["result"] for e in checks["claims"].values()}
    assert CheckerStatus.INVALID.value in results


def test_the_same_session_with_the_true_order_is_released():
    final = _session(TRUE_ANSWER, "pos_session")
    assert final.governing_epistemic_status == SupportState.SUPPORTED.value
    assert final.release_decision == ReleaseDecision.RELEASE_SUPPORTED.value
    assert final.audit_summary["governing_release"]["basis_record_ids"]


def test_the_legacy_layer_is_happy_with_the_false_answer_and_does_not_govern():
    """The whole reason the governing layer exists, in one assertion."""
    final = _session(FALSE_ANSWER, "neg_legacy")
    assert final.ratified is True                      # the council approved it
    assert final.release_decision == ReleaseDecision.BLOCKED.value
    assert final.audit_summary["legacy_epistemic_status_authority"] == \
        "legacy_non_governing"
