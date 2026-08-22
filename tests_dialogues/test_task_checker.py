"""The deterministic task checker, and the hole it was built to replace.

`SUPPORTED` had no honest route. Objection checks can only take support away,
and the attempt to let claim checks add it laundered a model's reading through a
citation — two seats agreeing became support, which is "quality 7.5 → truth" at
a different resolution.

This checker has no model in the loop. It parses the task, enumerates, and
refuses anything its grammar does not fully cover. Most of these tests are about
the refusing: a checker that silently drops a constraint it could not read would
report a uniqueness that does not hold, and manufacture exactly the false
support the whole design exists to prevent.

All offline: pure functions, no provider, no network.
"""

from __future__ import annotations

import pytest

from backend.dialogues.hybrid_epistemic import (
    ADMISSIBLE_EVIDENCE_SOURCES,
    ClaimRecord,
    EvidenceSourceType,
    HybridEpistemicState,
    ReleaseDecision,
    SupportState,
    VerificationClass,
    VerificationResult,
    freeze_release,
    verify_task_internal,
)
from backend.dialogues.task_checker import (
    CHECKER_IDENTITY,
    MAX_ENTITIES,
    check_ordering_task,
    deterministic_refutation,
    deterministic_support,
    order_asserted_by,
)

BENCHMARK = """Four people — Anna, Ben, Clara, and David — must present one at a time.

Constraints:

* Anna presents before Ben.
* Clara presents immediately before David.
* Ben is not last.

Question:
Determine the unique presentation order and explain why it is unique."""

TRUTH = ("Anna", "Ben", "Clara", "David")
PROSE = ("Four researchers — Anna, Ben, Clara, and David — present once each. "
         "Anna presents before Ben. Clara presents immediately before David. "
         "Ben does not present last.")


# ── it reads the tasks it claims to read ─────────────────────────────────────

def test_the_frozen_benchmark_yields_the_known_ground_truth():
    check = check_ordering_task(BENCHMARK)
    assert check is not None
    assert check.roster == TRUTH
    assert len(check.rules) == 3
    assert check.valid_orders == (TRUTH,)
    assert check.determines_a_unique_order is True


def test_the_same_task_in_prose_reads_identically():
    """Bullets are formatting, not meaning."""
    assert check_ordering_task(PROSE).valid_orders == \
        check_ordering_task(BENCHMARK).valid_orders


@pytest.mark.parametrize("constraint,expected_first", [
    ("Ben presents immediately after Anna.", "Anna"),
    ("Ben presents after Anna.", "Anna"),
])
def test_after_forms_are_read_as_their_before_equivalents(constraint, expected_first):
    task = ("Three people — Anna, Ben, and Clara — present. "
            f"{constraint} Clara is last.")
    check = check_ordering_task(task)
    assert check is not None
    assert all(order[0] == expected_first for order in check.valid_orders)


def test_absolute_position_constraints_are_read():
    task = ("Three people — Anna, Ben, and Clara — present. "
            "Anna is first. Clara is last.")
    assert check_ordering_task(task).valid_orders == (("Anna", "Ben", "Clara"),)


def test_every_cited_constraint_is_verbatim_in_the_task():
    check = check_ordering_task(BENCHMARK)
    for text, offset in check.spans:
        assert BENCHMARK[offset:offset + len(text)] == text


# ── it refuses everything else ───────────────────────────────────────────────

def test_a_sentence_about_the_entities_it_cannot_parse_aborts_the_check():
    """THE safety property. A dropped constraint invents uniqueness."""
    task = ("Four people — Anna, Ben, Clara, and David — present. "
            "Anna presents before Ben. "
            "Clara sits closer to the window than David.")
    assert check_ordering_task(task) is None


def test_a_task_with_no_explicit_roster_is_refused():
    assert check_ordering_task("Someone presents before someone else.") is None


def test_a_stated_count_disagreeing_with_the_list_is_refused():
    """Either the list or the count was misread, and guessing which is worse."""
    task = ("Five people — Anna, Ben, Clara, and David — present. "
            "Anna presents before Ben.")
    assert check_ordering_task(task) is None


def test_a_repeated_name_is_refused():
    task = ("Four people — Anna, Ben, Anna, and David — present. "
            "Anna presents before Ben.")
    assert check_ordering_task(task) is None


def test_a_roster_larger_than_the_enumeration_budget_is_refused():
    names = ", ".join(f"Person{i}" for i in range(MAX_ENTITIES + 1))
    task = f"Many people — {names}, and Extra — present. Extra is last."
    assert check_ordering_task(task) is None


def test_a_task_with_a_roster_and_no_constraints_is_refused():
    assert check_ordering_task("Anna, Ben, Clara, and David will present.") is None


def test_an_essay_question_is_refused():
    """Nothing here fits, and nothing is the right answer."""
    assert check_ordering_task(
        "Is consensus among AI models a reliable signal of truth?") is None


# ── it reports non-uniqueness honestly ───────────────────────────────────────

def test_an_underconstrained_task_determines_nothing():
    task = ("Four people — Anna, Ben, Clara, and David — present. "
            "Anna presents before Ben.")
    check = check_ordering_task(task)
    assert len(check.valid_orders) > 1
    assert check.determines_a_unique_order is False
    assert check.unique_order is None


def test_a_contradictory_task_has_no_valid_order():
    task = ("Three people — Anna, Ben, and Clara — present. "
            "Anna presents before Ben. Ben presents before Anna.")
    check = check_ordering_task(task)
    assert check.valid_orders == ()
    assert check.determines_a_unique_order is False


# ── reading a claim ──────────────────────────────────────────────────────────

def test_a_claim_stating_the_order_is_read():
    assert order_asserted_by("The unique order is Anna, Ben, Clara, David.",
                             TRUTH, BENCHMARK) == TRUTH


def test_a_claim_that_merely_quotes_the_task_asserts_nothing():
    """Echoing the question is not answering it.

    The mock council opens every section by quoting the prompt, and the roster
    there happens to be listed in the answer's order. Reading that as an
    assertion would hand out support for repetition.
    """
    echo = ("On «Four people — Anna, Ben, Clara, and David — must present one "
            "at a time» the council observes...")
    assert order_asserted_by(echo, TRUTH, BENCHMARK) is None


def test_a_claim_stating_two_different_orders_asserts_neither():
    text = "It is Anna, Ben, Clara, David — not Clara, David, Anna, Ben."
    assert order_asserted_by(text, TRUTH, BENCHMARK) is None


def test_a_claim_with_no_complete_order_asserts_none():
    assert order_asserted_by("Anna goes before Ben, which is all we know.",
                             TRUTH, BENCHMARK) is None


# ── the records it emits ─────────────────────────────────────────────────────

def _check():
    return check_ordering_task(BENCHMARK)


def test_support_is_emitted_only_when_the_claim_states_the_computed_order():
    good = deterministic_support(_check(), "c",
                                 "The unique order is Anna, Ben, Clara, David.",
                                 BENCHMARK)
    assert good is not None
    bad = deterministic_support(_check(), "c",
                                "The order is Clara, David, Anna, Ben.", BENCHMARK)
    assert bad is None


def test_the_support_record_is_admissible_and_not_attributed_to_a_model():
    record = deterministic_support(_check(), "c",
                                   "The unique order is Anna, Ben, Clara, David.",
                                   BENCHMARK)
    assert record.source_type is EvidenceSourceType.DETERMINISTIC_COMPUTATION
    assert record.source_type in ADMISSIBLE_EVIDENCE_SOURCES
    assert record.admissible is True
    assert record.source_identity == CHECKER_IDENTITY
    assert "seat" not in record.source_identity


def test_no_support_when_the_task_determines_nothing():
    task = ("Four people — Anna, Ben, Clara, and David — present. "
            "Anna presents before Ben.")
    check = check_ordering_task(task)
    assert deterministic_support(check, "c", "The order is Anna, Ben, Clara, David.",
                                 task) is None


def test_a_refutation_is_emitted_for_a_different_complete_order():
    record = deterministic_refutation(_check(), "c",
                                      "The order is Clara, David, Anna, Ben.",
                                      BENCHMARK)
    assert record is not None
    assert record.result is VerificationResult.FALSIFIED
    assert record.verifier_provider_id is None      # nothing read this
    assert record.provenance == "deterministic_computation"


def test_no_refutation_for_the_correct_order():
    assert deterministic_refutation(_check(), "c",
                                    "The unique order is Anna, Ben, Clara, David.",
                                    BENCHMARK) is None


def test_the_checker_is_a_pure_deterministic_function():
    first = check_ordering_task(BENCHMARK)
    for _ in range(20):
        again = check_ordering_task(BENCHMARK)
        assert again.valid_orders == first.valid_orders
        assert again.rules == first.rules


# ── the closed hole ──────────────────────────────────────────────────────────

def _state(text="The unique order is Anna, Ben, Clara, David."):
    state = HybridEpistemicState("chk", BENCHMARK)
    state.add_claim(ClaimRecord(claim_id="c", text=text, section="core_answer",
                                verification_class=VerificationClass.TASK_INTERNAL))
    return state


def test_a_model_attributed_check_cannot_create_support():
    """The f8144cd bug, pinned. Two seats plus one quote is not truth.

    Both records are VERIFIED, both cite the task verbatim, both are perfectly
    well formed. Neither reaches the basis, because a model read them.
    """
    state = _state()
    for seat in ("seat0", "seat1"):
        state.add_verification(verify_task_internal(
            claim_id="c", objection_id=None, task_text=BENCHMARK,
            cited_spans=[("Ben is not last", BENCHMARK.index("Ben is not last"))],
            condition_tested="does the task establish the order?", holds=True,
            rationale="it does", verifier_provider_id=seat))
    assessment = state.assess_claim("c")
    assert assessment.basis_record_ids == []
    assert assessment.support_state is not SupportState.SUPPORTED


def test_a_computed_check_does_create_support():
    """The same state, the same claim, evidence that no model produced."""
    state = _state()
    state.add_evidence(deterministic_support(_check(), "c", state.claims["c"].text,
                                             BENCHMARK))
    assessment = state.assess_claim("c")
    assert assessment.basis_record_ids != []
    assert assessment.support_state is SupportState.SUPPORTED


def test_the_computed_support_survives_to_the_release():
    state = _state()
    state.add_evidence(deterministic_support(_check(), "c", state.claims["c"].text,
                                             BENCHMARK))
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=1.0)
    assert release.release_decision is ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids


def test_a_computed_refutation_falsifies_and_blocks_the_release():
    state = _state("The order is Clara, David, Anna, Ben.")
    state.add_verification(deterministic_refutation(
        _check(), "c", state.claims["c"].text, BENCHMARK))
    assert state.assess_claim("c").support_state is SupportState.FALSIFIED
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=10.0)
    assert release.release_decision is ReleaseDecision.BLOCKED


def test_the_orchestrator_runs_the_checker_over_a_projected_core():
    """The CED wiring, end to end and free: no adapters, no model calls."""
    import asyncio

    from backend.dialogues.agent import SocraticAgent
    from backend.dialogues.ced import CEDOrchestrator
    from backend.dialogues.providers import FakeProvider

    provider = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                          provider)
    core = _state()
    core.add_claim(ClaimRecord(claim_id="wrong",
                               text="Alternatively the order is Clara, David, Anna, Ben.",
                               section="crucial_stress_test",
                               verification_class=VerificationClass.TASK_INTERNAL))
    outcomes = ced.apply_deterministic_checks(core)

    assert outcomes["c"] == "supported_by_computation"
    assert outcomes["wrong"] == "refuted_by_computation"
    assert core.assess_claim("c").support_state is SupportState.SUPPORTED
    assert core.assess_claim("wrong").support_state is SupportState.FALSIFIED


def test_the_orchestrator_reports_nothing_on_a_task_it_cannot_read():
    from backend.dialogues.agent import SocraticAgent
    from backend.dialogues.ced import CEDOrchestrator
    from backend.dialogues.providers import FakeProvider

    provider = FakeProvider()
    ced = CEDOrchestrator([SocraticAgent(f"a{i}", provider) for i in range(4)],
                          provider)
    core = HybridEpistemicState("essay", "Is consensus a signal of truth?")
    core.add_claim(ClaimRecord(claim_id="c", text="Sometimes.",
                               section="core_answer"))
    assert ced.apply_deterministic_checks(core) == {}
    assert core.assess_claim("c").support_state is not SupportState.SUPPORTED


def test_high_quality_still_cannot_reach_supported_without_the_checker():
    """The law, restated at the boundary the checker sits on."""
    state = _state()
    release = freeze_release(state, assembled_claim_ids=["c"], quality_mean=9.9,
                             legacy_epistemic_status="well_supported")
    assert release.release_decision is not ReleaseDecision.RELEASE_SUPPORTED
    assert release.basis_record_ids == []
