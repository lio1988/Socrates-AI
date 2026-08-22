"""The deterministic checker: what it computes, and what it refuses to.

`SUPPORTED` has one route and it does not involve asking a model. An earlier
attempt let two seats citing the same quote create support; it was reverted,
because "quality 7.5 -> truth" and "two seats plus one quote -> truth" are the
same mistake at different resolutions.

Most of what follows tests refusal rather than computation. A checker that
half-reads a task, drops a constraint it could not parse, and reports a
uniqueness that does not hold would manufacture exactly the false support the
design exists to prevent — so ambiguity, unparseable constraints, oversized
rosters and bare entity lists all have to fail closed, loudly, and distinctly
from "false".

All offline: pure functions, no provider, no network, no key.
"""

from __future__ import annotations

import json

import pytest

from backend.dialogues.hybrid_epistemic import (
    ADMISSIBLE_EVIDENCE_SOURCES,
    ClaimRecord,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    HybridEpistemicState,
    ReleaseDecision,
    SupportState,
    VerificationClass,
    freeze_release,
    verify_task_internal,
)
from backend.dialogues.task_checker import (
    AUTHORITY_CLASS,
    CHECKER_ID,
    CHECKER_VERSION,
    MAX_ENTITIES,
    CheckerReceipt,
    CheckerStatus,
    NotApplicableReason,
    ProblemClass,
    candidate_order,
    evaluate_candidate,
    evaluate_statement,
    model_task,
    receipt_refutation,
    receipt_support,
)

BENCHMARK = """Four people — Anna, Ben, Clara, and David — must present one at a time.

Constraints:

* Anna presents before Ben.
* Clara presents immediately before David.
* Ben is not last.

Question:
Determine the unique presentation order and explain why it is unique."""

TRUTH = ("Anna", "Ben", "Clara", "David")

#: Same roster, one constraint dropped: three satisfying orders instead of one.
LOOSE = ("Four people — Anna, Ben, Clara, and David — present. "
         "Anna presents before Ben. Clara presents immediately before David.")


def _reason(receipt) -> str:
    return receipt.reason


# ══ A. an entity list is not an ordering ═════════════════════════════════════

def test_A_a_bare_list_of_names_is_not_an_ordering():
    """THE false positive. Entity extraction is not relation extraction.

    "Anna, Ben, Clara, David" names four people. Reading it as
    Anna < Ben < Clara < David would hand support to any text that lists the
    roster — including the task's own roster sentence, and including every
    section of a council answer that opens by quoting the prompt.
    """
    receipt = evaluate_candidate(BENCHMARK, "Anna, Ben, Clara, David")
    assert receipt.result is CheckerStatus.NOT_APPLICABLE
    assert _reason(receipt) == NotApplicableReason.NO_CANDIDATE.value
    assert receipt.candidate_is_valid is None
    assert receipt_support(receipt, "c") is None


def test_A_quoting_the_tasks_own_roster_sentence_is_not_an_ordering():
    echo = ("On «Four people — Anna, Ben, Clara, and David — must present one "
            "at a time» the council observes a great deal.")
    receipt = evaluate_candidate(BENCHMARK, echo)
    assert receipt.result is CheckerStatus.NOT_APPLICABLE
    assert receipt_support(receipt, "c") is None


def test_A_names_in_prose_without_an_ordering_frame_are_not_an_ordering():
    prose = ("Anna raised the objection, Ben and Clara agreed, and David "
             "abstained from the vote.")
    assert candidate_order(prose, TRUTH)[0] is None


@pytest.mark.parametrize("frame", [
    "The order is Anna, Ben, Clara, David.",
    "The unique presentation order is Anna, Ben, Clara, David.",
    "Could the order be Anna, Ben, Clara, David?",
    "The sequence is Anna, then Ben, then Clara, then David.",
    "The final arrangement: Anna, Ben, Clara, David.",
    "Schedule = Anna > Ben > Clara > David.".replace(">", "-"),
])
def test_A_an_explicit_ordering_frame_is_recognised(frame):
    assert candidate_order(frame, TRUTH)[0] == TRUTH


def test_A_two_different_proposed_orders_are_ambiguous_not_a_pick():
    text = "The order is Anna, Ben, Clara, David. Or the order is Clara, David, Anna, Ben."
    order, reason = candidate_order(text, TRUTH)
    assert order is None
    assert reason is NotApplicableReason.AMBIGUOUS_CANDIDATE


# ══ B. an explicit candidate is evaluated ════════════════════════════════════

def test_B_an_explicit_candidate_question_is_evaluated():
    receipt = evaluate_candidate(
        BENCHMARK, "Could the order be Anna, Ben, Clara, David?")
    assert receipt.result is CheckerStatus.VALID
    assert receipt.candidate_checked == "Anna, Ben, Clara, David"
    assert receipt.problem_class == ProblemClass.FINITE_ORDERING.value
    assert receipt.normalized_entities == TRUTH
    assert receipt.normalized_constraints == (
        "Anna before Ben", "Clara immediately before David", "Ben not last")


# ══ C. INVALID names the constraint it broke ═════════════════════════════════

def test_C_a_violated_constraint_is_reported_exactly():
    receipt = evaluate_candidate(BENCHMARK, "The order is Clara, David, Anna, Ben.")
    assert receipt.result is CheckerStatus.INVALID
    assert receipt.candidate_is_invalid is True
    assert receipt.violated_constraints == ("Ben not last",)
    assert set(receipt.satisfied_constraints) == {
        "Anna before Ben", "Clara immediately before David"}


def test_C_invalid_is_never_confused_with_not_applicable():
    """The distinction that matters most: 'false' and 'unrepresentable'."""
    invalid = evaluate_candidate(BENCHMARK, "The order is Clara, David, Anna, Ben.")
    declined = evaluate_candidate(BENCHMARK, "Anna, Ben, Clara, David")
    assert invalid.result is CheckerStatus.INVALID
    assert declined.result is CheckerStatus.NOT_APPLICABLE
    assert invalid.result is not declined.result
    assert invalid.reason is None and declined.reason is not None


# ══ D. VALID produces a full receipt ═════════════════════════════════════════

def test_D_a_satisfying_candidate_produces_a_complete_receipt():
    receipt = evaluate_candidate(
        BENCHMARK, "The unique order is Anna, Ben, Clara, David.")
    assert receipt.result is CheckerStatus.VALID
    assert receipt.violated_constraints == ()
    assert len(receipt.satisfied_constraints) == 3
    assert receipt.deterministic is True
    assert receipt.authority_class == AUTHORITY_CLASS
    assert receipt.checker_id == CHECKER_ID
    assert receipt.checker_version == CHECKER_VERSION
    assert receipt.input_digest


def test_D_the_receipt_carries_every_required_field():
    receipt = evaluate_candidate(
        BENCHMARK, "The unique order is Anna, Ben, Clara, David.")
    required = {"checker_id", "checker_version", "problem_class",
                "normalized_entities", "normalized_constraints",
                "candidate_checked", "result", "violated_constraints",
                "satisfied_constraints", "input_digest", "deterministic",
                "authority_class"}
    assert required <= set(receipt.to_dict())


# ══ E. never report unique from one satisfying example ═══════════════════════

def test_E_a_valid_candidate_under_multiple_solutions_is_not_unique():
    model, _ = model_task(LOOSE)
    assert len(model.solutions) == 3
    receipt = evaluate_candidate(LOOSE, "The order is Anna, Ben, Clara, David.")
    assert receipt.result is CheckerStatus.VALID
    assert receipt.candidate_is_unique is False
    assert receipt.solution_count == 3


def test_E_a_non_unique_valid_candidate_creates_no_support():
    """Consistent with the task is not established by it."""
    receipt = evaluate_candidate(LOOSE, "The order is Anna, Ben, Clara, David.")
    assert receipt.establishes_the_candidate is False
    assert receipt_support(receipt, "c") is None


# ══ F. must-be-true is checked against ALL assignments ═══════════════════════

def test_F_must_hold_requires_every_satisfying_assignment():
    receipt = evaluate_statement(LOOSE, "Clara presents before David")
    assert receipt.statement_must_hold is True
    assert receipt.solution_count == 3


def test_F_a_statement_true_in_some_assignments_does_not_must_hold():
    """Two of three orders start with Anna. That is not 'must'."""
    receipt = evaluate_statement(LOOSE, "Anna is first")
    assert receipt.statement_could_hold is True
    assert receipt.statement_must_hold is False


def test_F_only_a_must_hold_statement_creates_support():
    assert receipt_support(evaluate_statement(LOOSE, "Clara presents before David"),
                           "c") is not None
    assert receipt_support(evaluate_statement(LOOSE, "Anna is first"), "c") is None


# ══ G. could-be-true needs one satisfying assignment ═════════════════════════

def test_G_could_hold_needs_at_least_one_assignment():
    receipt = evaluate_statement(LOOSE, "Anna is first")
    assert receipt.statement_could_hold is True
    assert receipt.result is CheckerStatus.VALID


def test_G_a_statement_no_assignment_satisfies_is_invalid():
    receipt = evaluate_statement(LOOSE, "Ben is first")
    assert receipt.statement_could_hold is False
    assert receipt.result is CheckerStatus.INVALID


# ══ H. ambiguity fails closed ════════════════════════════════════════════════

def test_H_a_conditional_constraint_is_an_ambiguous_parse():
    task = ("Four people — Anna, Ben, Clara, and David — present. "
            "Anna presents before Ben. "
            "Clara presents immediately before David, unless Ben is first.")
    receipt = evaluate_candidate(task, "The order is Anna, Ben, Clara, David.")
    assert receipt.result is CheckerStatus.NOT_APPLICABLE
    assert _reason(receipt) == NotApplicableReason.AMBIGUOUS_PARSE.value
    assert receipt_support(receipt, "c") is None


@pytest.mark.parametrize("constraint", [
    "Anna presents before Ben or Clara.",
    "Anna probably presents before Ben.",
    "Anna might present before Ben.",
    "Anna usually presents before Ben.",
])
def test_H_hedged_and_disjunctive_constraints_are_ambiguous(constraint):
    task = f"Four people — Anna, Ben, Clara, and David — present. {constraint}"
    receipt = evaluate_candidate(task, "The order is Anna, Ben, Clara, David.")
    assert receipt.result is CheckerStatus.NOT_APPLICABLE
    assert _reason(receipt) == NotApplicableReason.AMBIGUOUS_PARSE.value


def test_H_a_sentence_about_the_entities_it_cannot_read_aborts_the_check():
    """A dropped constraint would report a uniqueness that does not hold."""
    task = ("Four people — Anna, Ben, Clara, and David — present. "
            "Anna presents before Ben. Clara sits closer to the window than David.")
    receipt = evaluate_candidate(task, "The order is Anna, Ben, Clara, David.")
    assert _reason(receipt) == NotApplicableReason.UNPARSEABLE_CONSTRAINT.value


@pytest.mark.parametrize("task,expected", [
    ("Someone presents before someone else.", NotApplicableReason.NO_ROSTER),
    ("Five people — Anna, Ben, Clara, and David — present. Anna presents before Ben.",
     NotApplicableReason.COUNT_MISMATCH),
    ("Four people — Anna, Ben, Anna, and David — present. Anna presents before Ben.",
     NotApplicableReason.DUPLICATE_ENTITY),
    ("Anna, Ben, Clara, and David will present.", NotApplicableReason.NO_CONSTRAINTS),
    ("Is consensus among AI models a reliable signal of truth?",
     NotApplicableReason.NO_ROSTER),
])
def test_H_every_unsafe_reduction_declines_with_its_own_reason(task, expected):
    model, reason = model_task(task)
    assert model is None
    assert reason is expected


def test_H_a_roster_beyond_the_enumeration_budget_is_resource_bound():
    pool = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf",
            "Hotel", "India"]
    assert len(pool) > MAX_ENTITIES
    names = ", ".join(pool[:-1])
    task = f"Many people — {names}, and {pool[-1]} — present. {pool[-1]} is last."
    model, reason = model_task(task)
    assert model is None
    assert reason is NotApplicableReason.RESOURCE_BOUND


def test_H_out_of_class_questions_are_declined_not_answered():
    """Causal, legal, scientific and semantic questions have no finite form."""
    for question in (
        "Increasing advertising will substantially increase attendance. "
        "Which of Alpha, Beta, Gamma, and Delta is assumed?",
        "Whether the contract binds Alpha, Beta, Gamma, and Delta is disputed.",
    ):
        model, reason = model_task(question)
        assert model is None, reason


# ══ I. model consensus creates nothing ═══════════════════════════════════════

def _state(text="The unique order is Anna, Ben, Clara, David."):
    state = HybridEpistemicState("chk", BENCHMARK)
    state.add_claim(ClaimRecord(claim_id="c", text=text, section="core_answer",
                                verification_class=VerificationClass.TASK_INTERNAL))
    return state


@pytest.mark.parametrize("seats", [2, 4])
def test_I_unanimous_models_asserting_a_false_inference_create_no_basis(seats):
    """Two agree, four agree. Neither is evidence; agreement scales the claim."""
    state = _state("The unique order is Clara, David, Anna, Ben.")
    for i in range(seats):
        state.add_verification(verify_task_internal(
            claim_id="c", objection_id=None, task_text=BENCHMARK,
            cited_spans=[("Ben is not last", BENCHMARK.index("Ben is not last"))],
            condition_tested="does the task establish this order?", holds=True,
            rationale="we all read it that way", verifier_provider_id=f"seat{i}"))
    assessment = state.assess_claim("c")
    assert assessment.basis_record_ids == []
    assert assessment.support_state is not SupportState.SUPPORTED


@pytest.mark.parametrize("source", [
    EvidenceSourceType.MODEL_ASSERTION,
    EvidenceSourceType.MODEL_INTERPRETATION,
    EvidenceSourceType.CORROBORATED_MODEL_INTERPRETATION,
])
def test_I_every_model_flavoured_evidence_class_is_refused(source):
    state = _state()
    for i in range(4):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"e{i}", claim_id="c", stance=EvidenceStance.SUPPORTING,
            source_type=source, source_identity=f"seat{i}",
            content="the task establishes it"))
    assert state.assess_claim("c").basis_record_ids == []


# ══ 7. the authority firewall, enumerated ════════════════════════════════════

def test_the_admissible_set_is_exactly_the_non_model_sources():
    model_flavoured = {EvidenceSourceType.MODEL_ASSERTION,
                       EvidenceSourceType.MODEL_INTERPRETATION,
                       EvidenceSourceType.CORROBORATED_MODEL_INTERPRETATION}
    assert set(ADMISSIBLE_EVIDENCE_SOURCES) == set(EvidenceSourceType) - model_flavoured
    assert not (model_flavoured & set(ADMISSIBLE_EVIDENCE_SOURCES))


def test_nothing_a_council_produces_can_reach_the_governing_basis():
    """Every channel the user named, in one state, all at maximum.

    Model assertions, model interpretations, corroborated interpretations,
    unanimous seat verifications, a perfect quality mean and a legacy status of
    well_supported. The basis stays empty because none of them is evidence.
    """
    state = _state()
    for i in range(4):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"assert{i}", claim_id="c",
            stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.MODEL_ASSERTION,
            source_identity=f"seat{i}", content="I agree"))
        state.add_evidence(EvidenceRecord(
            evidence_id=f"interp{i}", claim_id="c",
            stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.CORROBORATED_MODEL_INTERPRETATION,
            source_identity=f"seat{i}", content="we all read it this way"))
        state.add_verification(verify_task_internal(
            claim_id="c", objection_id=None, task_text=BENCHMARK,
            cited_spans=[("Ben is not last", BENCHMARK.index("Ben is not last"))],
            condition_tested="established?", holds=True, rationale="yes",
            verifier_provider_id=f"seat{i}"))

    assert state.assess_claim("c").basis_record_ids == []
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=10.0,
                             legacy_epistemic_status="well_supported")
    assert release.basis_record_ids == []
    assert release.release_decision is not ReleaseDecision.RELEASE_SUPPORTED


# ══ J. the receipt survives serialization and replay ═════════════════════════

def test_J_a_receipt_round_trips_with_the_same_digest_and_authority():
    first = evaluate_candidate(BENCHMARK,
                               "The unique order is Anna, Ben, Clara, David.")
    replay = evaluate_candidate(BENCHMARK,
                                "The unique order is Anna, Ben, Clara, David.")
    assert first.digest() == replay.digest()
    assert first.to_dict() == replay.to_dict()

    wire = json.loads(json.dumps(first.to_dict()))
    assert wire["authority_class"] == AUTHORITY_CLASS
    assert wire["deterministic"] is True
    rebuilt = CheckerReceipt(
        result=CheckerStatus(wire["result"]),
        problem_class=wire["problem_class"],
        normalized_entities=tuple(wire["normalized_entities"]),
        normalized_constraints=tuple(wire["normalized_constraints"]),
        cited_spans=tuple(wire["cited_spans"]),
        candidate_checked=wire["candidate_checked"],
        violated_constraints=tuple(wire["violated_constraints"]),
        satisfied_constraints=tuple(wire["satisfied_constraints"]),
        input_digest=wire["input_digest"], reason=wire["reason"],
        solution_count=wire["solution_count"],
        candidate_is_valid=wire["candidate_is_valid"],
        candidate_is_invalid=wire["candidate_is_invalid"],
        candidate_is_unique=wire["candidate_is_unique"],
        statement_must_hold=wire["statement_must_hold"],
        statement_could_hold=wire["statement_could_hold"])
    assert rebuilt.digest() == first.digest()


def test_J_a_different_task_yields_a_different_digest():
    a = evaluate_candidate(BENCHMARK, "The order is Anna, Ben, Clara, David.")
    b = evaluate_candidate(LOOSE, "The order is Anna, Ben, Clara, David.")
    assert a.input_digest != b.input_digest
    assert a.digest() != b.digest()


def test_J_the_checker_is_pure_over_repeated_calls():
    reference = evaluate_candidate(BENCHMARK, "The order is Anna, Ben, Clara, David.")
    for _ in range(25):
        assert evaluate_candidate(
            BENCHMARK, "The order is Anna, Ben, Clara, David.").digest() == \
            reference.digest()


# ══ K/L. the governing release ═══════════════════════════════════════════════

def test_K_a_deterministic_receipt_is_accepted_as_a_governing_basis():
    state = _state()
    receipt = evaluate_candidate(BENCHMARK, state.claims["c"].text)
    state.add_evidence(receipt_support(receipt, "c"))
    assert state.assess_claim("c").support_state is SupportState.SUPPORTED
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=1.0)
    assert release.release_decision is ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids


def test_K_the_support_record_is_admissible_and_carries_its_receipt():
    receipt = evaluate_candidate(BENCHMARK,
                                 "The unique order is Anna, Ben, Clara, David.")
    record = receipt_support(receipt, "c")
    assert record.source_type is EvidenceSourceType.DETERMINISTIC_COMPUTATION
    assert record.admissible is True
    assert record.source_identity == f"{CHECKER_ID}/{CHECKER_VERSION}"
    assert record.receipt_ref == receipt.digest()
    assert json.loads(record.content)["authority_class"] == AUTHORITY_CLASS


def test_K_a_computed_refutation_falsifies_and_blocks_the_release():
    state = _state("The order is Clara, David, Anna, Ben.")
    receipt = evaluate_candidate(BENCHMARK, state.claims["c"].text)
    state.add_verification(receipt_refutation(receipt, "c", BENCHMARK))
    assert state.assess_claim("c").support_state is SupportState.FALSIFIED
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=10.0)
    assert release.release_decision is ReleaseDecision.BLOCKED


def test_L_only_model_interpretation_leaves_the_release_without_support():
    state = _state()
    for i in range(4):
        state.add_evidence(EvidenceRecord(
            evidence_id=f"e{i}", claim_id="c", stance=EvidenceStance.SUPPORTING,
            source_type=EvidenceSourceType.MODEL_INTERPRETATION,
            source_identity=f"seat{i}", content="reads correct to me"))
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=9.9,
                             legacy_epistemic_status="well_supported")
    assert release.release_decision is not ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids == []


# ══ the orchestrator wiring ══════════════════════════════════════════════════

def _ced():
    from backend.dialogues.agent import SocraticAgent
    from backend.dialogues.ced import CEDOrchestrator
    from backend.dialogues.providers import FakeProvider

    provider = FakeProvider()
    return CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                           provider)


def test_the_orchestrator_supports_a_correct_claim_and_refutes_a_wrong_one():
    core = _state()
    core.add_claim(ClaimRecord(
        claim_id="wrong", section="crucial_stress_test",
        text="Alternatively the order is Clara, David, Anna, Ben.",
        verification_class=VerificationClass.TASK_INTERNAL))
    summary = _ced().apply_deterministic_checks(core)

    assert summary["applicable"] is True
    assert summary["problem_class"] == ProblemClass.FINITE_ORDERING.value
    assert summary["solution_count"] == 1
    assert summary["claims"]["c"]["result"] == CheckerStatus.VALID.value
    assert summary["claims"]["wrong"]["result"] == CheckerStatus.INVALID.value
    assert core.assess_claim("c").support_state is SupportState.SUPPORTED
    assert core.assess_claim("wrong").support_state is SupportState.FALSIFIED


def test_the_orchestrator_declines_a_task_it_cannot_represent():
    core = HybridEpistemicState("essay", "Is consensus a signal of truth?")
    core.add_claim(ClaimRecord(claim_id="c", text="Sometimes.",
                               section="core_answer"))
    summary = _ced().apply_deterministic_checks(core)
    assert summary == {"applicable": False,
                       "reason": NotApplicableReason.NO_ROSTER.value}
    assert core.assess_claim("c").support_state is not SupportState.SUPPORTED


def test_the_orchestrator_creates_nothing_from_a_claim_that_only_echoes():
    core = HybridEpistemicState("echo", BENCHMARK)
    core.add_claim(ClaimRecord(
        claim_id="c", section="core_answer",
        text="On «Four people — Anna, Ben, Clara, and David — must present» we note much.",
        verification_class=VerificationClass.TASK_INTERNAL))
    summary = _ced().apply_deterministic_checks(core)
    assert summary["claims"]["c"]["result"] == CheckerStatus.NOT_APPLICABLE.value
    assert summary["claims"]["c"]["reason"] == NotApplicableReason.NO_CANDIDATE.value
    assert core.assess_claim("c").basis_record_ids == []


# ══ the copula forms ═════════════════════════════════════════════════════════

FIVE = ("Five analysts—Anna, Ben, Clara, David, and Elena—must be assigned to "
        "five consecutive presentation positions, one analyst per position. The "
        "following rules apply: David is first. Elena is last. Anna is "
        "immediately before Ben. Clara is after Ben. Determine the unique "
        "ordering of all five analysts.")


@pytest.mark.parametrize("constraint,expected", [
    ("Anna is before Ben", "Anna before Ben"),
    ("Anna is after Ben", "Ben before Anna"),
    ("Anna is immediately before Ben", "Anna immediately before Ben"),
    ("Anna is immediately after Ben", "Ben immediately before Anna"),
    ("Anna presents before Ben", "Anna before Ben"),
    ("Anna comes before Ben", "Anna before Ben"),
])
def test_the_copula_states_the_same_relation_as_a_domain_verb(constraint, expected):
    """"Anna is before Ben" was refused as unparseable. It is a synonym."""
    task = f"Three people — Anna, Ben, and Clara — present. {constraint}. Clara is last."
    model, reason = model_task(task)
    assert model is not None, reason
    assert expected in model.constraint_names


def test_immediately_before_does_not_also_match_the_plain_form():
    """Anchoring end to end is what keeps one sentence to one reading."""
    task = ("Three people — Anna, Ben, and Clara — present. "
            "Anna is immediately before Ben. Clara is last.")
    model, reason = model_task(task)
    assert model is not None, reason
    assert model.constraint_names == ("Anna immediately before Ben", "Clara last")


@pytest.mark.parametrize("constraint,expected", [
    ("Anna is not before Ben", "Anna not before Ben"),
    ("Anna is not after Ben", "Ben not before Anna"),
    ("Anna is not immediately before Ben", "Anna not immediately before Ben"),
    ("Anna is not immediately after Ben", "Ben not immediately before Anna"),
])
def test_an_exclusion_is_read_as_the_relation_it_excludes(constraint, expected):
    """Negated relations were refused as unparseable; they are single-reading.

    Added for the controlled negative control, where the one constraint the
    false candidate breaks is a negative one. Positions are distinct and totally
    ordered, so "not before" is "after" and needs no extra machinery.
    """
    task = f"Three people — Anna, Ben, and Clara — present. {constraint}. Clara is last."
    model, reason = model_task(task)
    assert model is not None, reason
    assert expected in model.constraint_names


def test_a_negation_the_grammar_does_not_cover_is_still_refused():
    """Fail-closed did not move: only the listed exclusions were added."""
    task = ("Three people — Anna, Ben, and Clara — present. "
            "Anna is not adjacent to Ben. Clara is last.")
    model, reason = model_task(task)
    assert model is None
    assert reason is NotApplicableReason.UNPARSEABLE_CONSTRAINT


def test_the_five_analyst_task_resolves_to_one_order():
    model, reason = model_task(FIVE)
    assert model is not None, reason
    assert model.entities == ("Anna", "Ben", "Clara", "David", "Elena")
    assert model.constraint_names == (
        "David first", "Elena last", "Anna immediately before Ben",
        "Ben before Clara")
    assert model.solutions == (("David", "Anna", "Ben", "Clara", "Elena"),)


def test_the_five_analyst_task_grades_a_candidate_three_ways():
    truth = evaluate_candidate(
        FIVE, "The unique order is David, Anna, Ben, Clara, Elena.")
    assert truth.result is CheckerStatus.VALID
    assert truth.candidate_is_unique is True
    assert receipt_support(truth, "c") is not None

    wrong = evaluate_candidate(
        FIVE, "The unique order is David, Clara, Anna, Ben, Elena.")
    assert wrong.result is CheckerStatus.INVALID
    assert wrong.violated_constraints == ("Ben before Clara",)

    template = evaluate_candidate(
        FIVE, "The unique order is NAME, NAME, NAME, NAME, NAME.")
    assert template.result is CheckerStatus.NOT_APPLICABLE
    assert template.reason == NotApplicableReason.NO_CANDIDATE.value
