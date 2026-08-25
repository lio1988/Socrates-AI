"""Contract, safety, and reward-farming tests for HeuristicValueEstimator v1."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import math

import pytest

from backend.dialogues.ced_search_observability_v1 import (
    CanonicalClaimAssessmentView,
    SearchStateV1,
)
from backend.dialogues.ced_search_value_v1 import HeuristicValueEstimatorV1
from backend.dialogues.ced_search_value_v1_contracts import (
    HEURISTIC_VALUE_ESTIMATOR_V1_VERSION,
    HEURISTIC_VALUE_RULES_V1,
    VALUE_V1_BASE,
    VALUE_V1_MAX,
    VALUE_V1_MIN,
)
from backend.dialogues.ced_search_value_v1_evaluation_cases import (
    CanonicalClaimBlueprint,
    CanonicalStateBlueprint,
    FROZEN_VALUE_V1_EVALUATION_CASE_SET,
    ValueV1TerminalRecipe,
    build_canonical_state,
)
from backend.dialogues.hybrid_epistemic import SupportState
from backend.dialogues.socrates_zero import (
    ContractValidationError,
    PolicyContextEntry,
    SearchState,
    TerminalStatus,
)


def _claim(**kwargs) -> CanonicalClaimBlueprint:
    return CanonicalClaimBlueprint(**kwargs)


def _projected(token: str, *, claims=None, **kwargs) -> SearchStateV1:
    blueprint = CanonicalStateBlueprint(
        blueprint_id=f"unit-{token}",
        claims=claims or (_claim(),),
        **kwargs,
    )
    return build_canonical_state(blueprint).projected


def _value(state: SearchStateV1) -> float:
    return HeuristicValueEstimatorV1().evaluate(state).bounded_value


def test_v1_contract_id_base_range_and_async_protocol_shape():
    estimator = HeuristicValueEstimatorV1()
    state = _projected("contract")
    assert estimator.version == HEURISTIC_VALUE_ESTIMATOR_V1_VERSION \
        == "heuristic-value-estimator/v1"
    assert estimator.base_value == VALUE_V1_BASE == 0.0
    assert VALUE_V1_MIN == -1.0
    assert VALUE_V1_MAX == 1.0
    assert asyncio.run(estimator.estimate(state)) == estimator.evaluate(state).bounded_value


@pytest.mark.parametrize(
    "token,claim,expected,reason",
    [
        ("supported", _claim(supporting_evidence_count=1), 0.0, None),
        ("unsupported", _claim(), -0.05, "active_claim_unsupported"),
        ("unresolved", _claim(inconclusive_count=1), -0.08, "active_claim_unresolved"),
        (
            "external",
            _claim(external_evidence_required=True),
            -0.12,
            "active_claim_external_evidence_required",
        ),
        ("falsified", _claim(falsified_count=1), -0.20, "active_claim_falsified"),
    ],
)
def test_exact_claim_rule_mapping_is_penalty_only(token, claim, expected, reason):
    audit = HeuristicValueEstimatorV1().evaluate(
        _projected(token, claims=(claim,))
    )
    assert audit.bounded_value == expected
    assert audit.raw_value == expected
    assert all(component.contribution <= 0.0 for component in audit.components)
    if reason is None:
        assert audit.components == ()
        assert audit.reason_code == "active_claim_supported_no_bonus"
    else:
        assert [(item.reason_code, item.contribution) for item in audit.components] \
            == [(reason, expected)]


def test_worst_active_claim_is_scored_once_by_penalty_not_enum_or_iteration_order():
    claims = (
        _claim(supporting_evidence_count=1),
        _claim(),
        _claim(external_evidence_required=True),
        _claim(inconclusive_count=1),
        _claim(falsified_count=1),
    )
    state = _projected("worst", claims=claims)
    audit = HeuristicValueEstimatorV1().evaluate(state)
    assert audit.selected_worst_support_state is SupportState.FALSIFIED
    assert audit.bounded_value == -0.20
    assert len(audit.components) == 1

    reordered = state.model_copy(
        update={"claim_assessments": tuple(reversed(state.claim_assessments))}
    )
    assert HeuristicValueEstimatorV1().evaluate(reordered).bounded_value == -0.20


def test_equal_worst_claims_choose_lowest_canonical_claim_id_for_audit_only():
    state = _projected(
        "equal-worst",
        claims=(_claim(inconclusive_count=1), _claim(open_objection_count=1)),
    )
    audit = HeuristicValueEstimatorV1().evaluate(state)
    expected_claim = min(item.claim_id for item in state.claim_assessments)
    assert audit.bounded_value == -0.08
    assert audit.source_claim_id == expected_claim


def test_socratic_remainder_is_one_state_level_component_after_objection_subtraction():
    supported = (_claim(supporting_evidence_count=1),)
    no_remainder = _projected("remainder-none", claims=supported)
    one_remainder = _projected(
        "remainder-one", claims=supported, aporia_count=1
    )
    two_remainders = _projected(
        "remainder-two", claims=supported, aporia_count=2
    )
    objection_only = _projected(
        "remainder-objection", claims=(_claim(open_objection_count=1),)
    )
    assert _value(no_remainder) == 0.0
    assert _value(one_remainder) == -0.05
    assert _value(two_remainders) == -0.05
    objection_audit = HeuristicValueEstimatorV1().evaluate(objection_only)
    assert objection_audit.bounded_value == -0.08
    assert "socratic_remainder_open" not in {
        item.reason_code for item in objection_audit.components
    }


@pytest.mark.parametrize(
    "terminal,expected",
    [
        (ValueV1TerminalRecipe.BLOCKED, -0.20),
        (ValueV1TerminalRecipe.BUDGET_EXHAUSTED, -0.10),
    ],
)
def test_terminal_firewall_suppresses_claim_and_lifecycle_stacking(terminal, expected):
    state = _projected(
        f"terminal-{terminal.value}",
        claims=(
            _claim(falsified_count=1),
            _claim(external_evidence_required=True),
            _claim(open_objection_count=1),
        ),
        aporia_count=1,
        terminal=terminal,
    )
    audit = HeuristicValueEstimatorV1().evaluate(state)
    assert audit.bounded_value == expected
    assert len(audit.components) == 1
    assert audit.terminal_suppression_status is True
    assert audit.selected_worst_support_state is None
    assert audit.suppressed_sources


@pytest.mark.parametrize(
    "status",
    [TerminalStatus.ANSWER_READY, TerminalStatus.ABSTAINED],
)
def test_answer_ready_and_abstained_remain_neutral_terminal_audits(status):
    blocked = _projected(
        f"neutral-terminal-{status.value}",
        claims=(_claim(falsified_count=1),),
        terminal=ValueV1TerminalRecipe.BLOCKED,
    )
    base_payload = blocked.base_state.model_dump(mode="python", exclude={"state_id"})
    base_payload["terminal_status"] = status
    base = SearchState(**base_payload)
    state = SearchStateV1(
        base_state=base,
        evidence=blocked.evidence,
        verifications=blocked.verifications,
        claim_assessments=blocked.claim_assessments,
        objections=blocked.objections,
        contradictions=blocked.contradictions,
    )
    audit = HeuristicValueEstimatorV1().evaluate(state)
    assert audit.bounded_value == 0.0
    assert audit.components == ()
    assert audit.terminal_suppression_status is True


def test_claim_splitting_supported_inflation_and_record_inflation_cannot_farm_value():
    one_unsupported = _projected("split-one")
    three_unsupported = _projected(
        "split-three", claims=(_claim(), _claim(), _claim())
    )
    unsupported_plus_supported = _projected(
        "supported-inflation",
        claims=(
            _claim(),
            _claim(supporting_evidence_count=1),
            _claim(deterministic_verified_count=1),
        ),
    )
    one_supported_record = _projected(
        "records-one", claims=(_claim(supporting_evidence_count=1),)
    )
    many_supported_records = _projected(
        "records-many",
        claims=(
            _claim(
                supporting_evidence_count=4,
                deterministic_verified_count=4,
                rejected_objection_count=4,
            ),
        ),
    )
    assert _value(one_unsupported) == _value(three_unsupported) == -0.05
    assert _value(unsupported_plus_supported) == -0.05
    assert _value(one_supported_record) == _value(many_supported_records) == 0.0


def test_open_record_counts_do_not_stack_and_closure_never_creates_positive_value():
    one_open = _projected(
        "open-one", claims=(_claim(open_objection_count=1),)
    )
    four_open = _projected(
        "open-four", claims=(_claim(open_objection_count=4),)
    )
    rejected = _projected(
        "closed-rejected", claims=(_claim(rejected_objection_count=3),)
    )
    no_record = _projected("closed-none")
    assert _value(one_open) == _value(four_open) == -0.08
    assert _value(rejected) == _value(no_record) == -0.05
    assert _value(rejected) <= 0.0


def test_receipt_links_governing_assessment_and_suppresses_all_related_sources():
    state = _projected(
        "receipt",
        claims=(
            _claim(
                supporting_evidence_count=2,
                inconclusive_count=1,
                rejected_objection_count=1,
            ),
        ),
    )
    audit = HeuristicValueEstimatorV1().evaluate(state)
    assert audit.source_claim_assessment_id.startswith("claim-assessment:")
    assert audit.source_claim_assessment_digest is not None
    assert len(audit.source_claim_assessment_digest) == 64
    assert len(audit.receipt_hash) == 64
    assert audit.reason_code == "active_claim_unresolved"
    canonical_ids = {
        item.source_record_id for collection in (
            state.evidence,
            state.verifications,
            state.objections,
            state.contradictions,
        ) for item in collection
    }
    assert {item.source_record_id for item in audit.suppressed_sources} \
        <= canonical_ids
    assert audit.suppressed_sources


def test_receipt_and_value_are_deterministic_and_canonical_order_independent():
    state = _projected(
        "deterministic",
        claims=(
            _claim(open_objection_count=2),
            _claim(inconclusive_count=1),
        ),
    )
    estimator = HeuristicValueEstimatorV1()
    first = estimator.evaluate(state)
    second = estimator.evaluate(state)
    assert first == second
    assert first.receipt_hash == second.receipt_hash
    assert math.isfinite(first.raw_value)
    assert VALUE_V1_MIN <= first.bounded_value <= VALUE_V1_MAX


def test_temporal_prefix_forbidden_metadata_and_future_outcomes_do_not_enter_value():
    prefix = _projected("prefix")
    future_supported = _projected(
        "future-supported", claims=(_claim(supporting_evidence_count=1),)
    )
    future_falsified = _projected(
        "future-falsified", claims=(_claim(falsified_count=1),)
    )
    assert HeuristicValueEstimatorV1().evaluate(prefix) \
        == HeuristicValueEstimatorV1().evaluate(prefix)
    assert _value(future_supported) != _value(future_falsified)

    equivalence = next(
        pair for pair in FROZEN_VALUE_V1_EVALUATION_CASE_SET.pairs
        if pair.pair_name == "canonical-v1-pair-031"
    ).estimator_view()
    assert _value(equivalence.left_state) == _value(equivalence.right_state)

    base_payload = prefix.base_state.model_dump(mode="python", exclude={"state_id"})
    base_payload["question"] = "Different non-authoritative evaluation prose."
    base_payload["policy_context"] = (
        PolicyContextEntry(name="consensus-score-marker", semantic_digest="a" * 64),
    )
    changed_base = SearchState(**base_payload)
    changed = SearchStateV1(
        base_state=changed_base,
        evidence=prefix.evidence,
        verifications=prefix.verifications,
        claim_assessments=prefix.claim_assessments,
        objections=prefix.objections,
        contradictions=prefix.contradictions,
    )
    assert _value(changed) == _value(prefix)


def test_evaluation_is_pure_and_cannot_mutate_ced_hybrid_or_projected_state():
    blueprint = CanonicalStateBlueprint(
        blueprint_id="unit-authority",
        claims=(_claim(open_objection_count=1),),
        aporia_count=1,
    )
    built = build_canonical_state(blueprint)
    state_before = built.session_state.model_dump(mode="json")
    hybrid_before = deepcopy(built.hybrid_state.__dict__)
    projected_before = built.projected.model_dump(mode="json")
    HeuristicValueEstimatorV1().evaluate(built.projected)
    assert built.session_state.model_dump(mode="json") == state_before
    assert built.hybrid_state.__dict__ == hybrid_before
    assert built.projected.model_dump(mode="json") == projected_before


def test_estimator_rejects_v0_input_duplicate_assessment_and_invalid_support_state():
    estimator = HeuristicValueEstimatorV1()
    valid = _projected("malformed")
    with pytest.raises(ContractValidationError, match="SearchState v1"):
        estimator.evaluate(valid.base_state)  # type: ignore[arg-type]

    duplicated = SearchStateV1.model_construct(
        **{
            **valid.__dict__,
            "claim_assessments": (
                valid.claim_assessments[0],
                valid.claim_assessments[0],
            ),
        }
    )
    with pytest.raises(ContractValidationError, match="valid SearchState v1"):
        estimator.evaluate(duplicated)

    invalid_assessment = CanonicalClaimAssessmentView.model_construct(
        **{
            **valid.claim_assessments[0].__dict__,
            "support_state": "invented",
        }
    )
    invalid = SearchStateV1.model_construct(
        **{**valid.__dict__, "claim_assessments": (invalid_assessment,)}
    )
    with pytest.warns(UserWarning, match="Pydantic serializer warnings"):
        with pytest.raises(ContractValidationError, match="valid SearchState v1"):
            estimator.evaluate(invalid)


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_estimator_fails_closed_on_cross_claim_source_ownership_and_nonfinite_rules(
    invalid,
):
    state = _projected(
        "ownership",
        claims=(_claim(supporting_evidence_count=1), _claim()),
    )
    first, second = state.claim_assessments
    evidence_id = state.evidence[0].source_record_id
    forged_second = CanonicalClaimAssessmentView(
        claim_id=second.claim_id,
        support_state=SupportState.SUPPORTED,
        basis_record_ids=(evidence_id,),
        eligible_for_assembly=True,
    )
    forged = SearchStateV1(
        base_state=state.base_state,
        evidence=state.evidence,
        verifications=state.verifications,
        claim_assessments=(first, forged_second),
        objections=state.objections,
        contradictions=state.contradictions,
    )
    with pytest.raises(ContractValidationError, match="source ownership"):
        HeuristicValueEstimatorV1().evaluate(forged)

    class NonFiniteEstimator(HeuristicValueEstimatorV1):
        rules = {**HEURISTIC_VALUE_RULES_V1, "active_claim_unsupported": invalid}

    with pytest.raises(ContractValidationError, match="finite"):
        NonFiniteEstimator().evaluate(_projected("nonfinite"))


def test_estimator_refuses_positive_or_unapproved_rule_families():
    class PositiveEstimator(HeuristicValueEstimatorV1):
        rules = {**HEURISTIC_VALUE_RULES_V1, "active_claim_unsupported": 0.01}

    class ExpandedEstimator(HeuristicValueEstimatorV1):
        rules = {**HEURISTIC_VALUE_RULES_V1, "closure_bonus": 0.0}

    state = _projected("rule-firewall")
    with pytest.raises(ContractValidationError, match="positive"):
        PositiveEstimator().evaluate(state)
    with pytest.raises(ContractValidationError, match="families"):
        ExpandedEstimator().evaluate(state)


def test_worst_state_monotonicity_only_for_comparable_canonical_states():
    supported = _value(
        _projected("monotonic-supported", claims=(_claim(supporting_evidence_count=1),))
    )
    unsupported = _value(_projected("monotonic-unsupported"))
    unresolved = _value(
        _projected("monotonic-unresolved", claims=(_claim(inconclusive_count=1),))
    )
    external = _value(
        _projected(
            "monotonic-external",
            claims=(_claim(external_evidence_required=True),),
        )
    )
    falsified = _value(
        _projected("monotonic-falsified", claims=(_claim(falsified_count=1),))
    )
    assert supported > unsupported > unresolved > external > falsified
