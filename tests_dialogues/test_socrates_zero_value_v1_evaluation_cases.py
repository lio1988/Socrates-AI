"""Pre-result chronology and leakage gates for the frozen Value-v1 cases."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
from pathlib import Path

from backend.dialogues.ced_search_projection_v1 import project_search_state_v1
from backend.dialogues.ced_search_value_v1_evaluation_cases import (
    FROZEN_VALUE_V1_EVALUATION_CASE_SET,
    VALUE_V1_EVAL_CASE_SET_VERSION,
    VALUE_V1_EVAL_HARNESS_VERSION,
    VALUE_V1_HOLDOUT_IMPROVEMENT_THRESHOLD,
    VALUE_V1_HOLDOUT_ORDERED_ACCURACY_THRESHOLD,
    VALUE_V1_NONTERMINAL_IMPROVEMENT_THRESHOLD,
    VALUE_V1_NONTERMINAL_ORDERED_ACCURACY_THRESHOLD,
    VALUE_V1_REQUIRED_TIE_ACCURACY_THRESHOLD,
    VALUE_V1_SECONDARY_IMPROVEMENT_THRESHOLD,
    ValueV1EvaluationCategory,
    ValueV1EvaluationSplit,
    ValueV1PairExpectation,
    build_canonical_state,
    frozen_case_set_canonical_json,
)
from backend.dialogues.hybrid_epistemic import SupportState
from backend.dialogues.socrates_zero import TerminalStatus


_CASE_SET_DIGEST = (
    "szvaluev1cases_"
    "5fad13cb294223cf76bcc7783bed1a5ac0bed56b22b4f5aa6ba73edaefbd18e3"
)
_CASE_SET_SHA256 = (
    "22122913601c9fc39265fbdc44a3f3cec02030333c7317e971db42fb3a436afd"
)
_PHASE5_SHA256 = (
    "21aa870a790f80186c0cd2b66878fa0d6344399fdf9e5386e399c7032569886c"
)


def test_frozen_ids_thresholds_and_exact_balanced_split():
    case_set = FROZEN_VALUE_V1_EVALUATION_CASE_SET
    assert case_set.case_set_id == VALUE_V1_EVAL_CASE_SET_VERSION \
        == "socrateszero-value-v1-eval-case-set/v1"
    assert VALUE_V1_EVAL_HARNESS_VERSION \
        == "socrateszero-value-v1-eval-harness/v0"
    assert len(case_set.pairs) == 45
    assert len(case_set.for_split(ValueV1EvaluationSplit.DEVELOPMENT)) == 18
    assert len(case_set.for_split(ValueV1EvaluationSplit.HOLDOUT)) == 27
    counts = Counter((pair.category, pair.split) for pair in case_set.pairs)
    assert set(ValueV1EvaluationCategory) == {
        ValueV1EvaluationCategory.USEFUL_SUPPORT_STATE,
        ValueV1EvaluationCategory.IRRELEVANT_V1_SIGNAL,
        ValueV1EvaluationCategory.MISLEADING_LIFECYCLE_CLOSURE,
        ValueV1EvaluationCategory.DUPLICATE_DERIVED_SIGNAL,
        ValueV1EvaluationCategory.TERMINAL_SUPPORT_ONLY,
        ValueV1EvaluationCategory.INTERMEDIATE_ASSESSMENT,
        ValueV1EvaluationCategory.V0_V1_EQUIVALENCE,
        ValueV1EvaluationCategory.RESOLUTION_REMOVES_PENALTY,
        ValueV1EvaluationCategory.COUNT_INFLATION,
    }
    for category in ValueV1EvaluationCategory:
        assert counts[(category, ValueV1EvaluationSplit.DEVELOPMENT)] == 2
        assert counts[(category, ValueV1EvaluationSplit.HOLDOUT)] == 3
    assert VALUE_V1_HOLDOUT_ORDERED_ACCURACY_THRESHOLD == 0.80
    assert VALUE_V1_HOLDOUT_IMPROVEMENT_THRESHOLD == 0.20
    assert VALUE_V1_NONTERMINAL_ORDERED_ACCURACY_THRESHOLD == 0.80
    assert VALUE_V1_NONTERMINAL_IMPROVEMENT_THRESHOLD == 0.20
    assert VALUE_V1_REQUIRED_TIE_ACCURACY_THRESHOLD == 1.0
    assert VALUE_V1_SECONDARY_IMPROVEMENT_THRESHOLD == 0.10


def test_case_set_semantics_have_pre_result_digest_and_canonical_sha_lock():
    case_set = FROZEN_VALUE_V1_EVALUATION_CASE_SET
    assert case_set.case_set_digest == _CASE_SET_DIGEST
    rendered = frozen_case_set_canonical_json().encode("utf-8")
    assert hashlib.sha256(rendered).hexdigest() == _CASE_SET_SHA256


def test_every_case_builds_real_sources_then_replays_through_projection_v1():
    state_ids = set()
    for pair in FROZEN_VALUE_V1_EVALUATION_CASE_SET.pairs:
        for blueprint in (pair.left, pair.right):
            assert "support_state" not in blueprint.model_dump(mode="json")
            built = build_canonical_state(blueprint)
            replay = project_search_state_v1(
                built.session_state,
                built.task,
                budget=built.projected.base_state.budget,
                budget_usage=built.projected.base_state.budget_usage,
                commitments=built.commitments,
                aporia_records=built.aporia_records,
                hybrid_state=built.hybrid_state,
            )
            assert replay == built.projected
            assert replay.state_id not in state_ids
            state_ids.add(replay.state_id)
    assert len(state_ids) == 90


def test_ground_truth_is_absent_from_estimator_view_and_canonical_id_inputs():
    forbidden_tokens = {
        "left", "right", "better", "winner", "tie", "development", "holdout"
    }
    for pair in FROZEN_VALUE_V1_EVALUATION_CASE_SET.pairs:
        view = pair.estimator_view()
        assert set(type(view).model_fields) == {"left_state", "right_state"}
        assert not hasattr(view, "expectation")
        for blueprint in (pair.left, pair.right):
            lowered = blueprint.blueprint_id.lower()
            assert all(token not in lowered for token in forbidden_tokens)


def test_adversarial_label_flip_cannot_change_state_or_record_identities():
    pair = next(
        item for item in FROZEN_VALUE_V1_EVALUATION_CASE_SET.pairs
        if item.expectation is ValueV1PairExpectation.LEFT_BETTER
    )
    original = pair.estimator_view()
    relabeled = pair.model_copy(
        update={"expectation": ValueV1PairExpectation.RIGHT_BETTER}
    ).estimator_view()
    assert original == relabeled
    assert original.left_state.state_id == relabeled.left_state.state_id
    assert original.right_state.state_id == relabeled.right_state.state_id


def test_development_and_holdout_are_separate_and_nonterminal_dominates_holdout():
    case_set = FROZEN_VALUE_V1_EVALUATION_CASE_SET
    development = case_set.for_split(ValueV1EvaluationSplit.DEVELOPMENT)
    holdout = case_set.for_split(ValueV1EvaluationSplit.HOLDOUT)
    assert {pair.pair_id for pair in development}.isdisjoint(
        pair.pair_id for pair in holdout
    )
    nonterminal_pairs = 0
    for pair in holdout:
        view = pair.estimator_view()
        if (
            view.left_state.base_state.terminal_status
            is TerminalStatus.NON_TERMINAL
            and view.right_state.base_state.terminal_status
            is TerminalStatus.NON_TERMINAL
        ):
            nonterminal_pairs += 1
    assert nonterminal_pairs == 24


def test_blueprints_derive_expected_governing_states_without_manual_assignment():
    pairs = FROZEN_VALUE_V1_EVALUATION_CASE_SET.pairs
    first = next(
        pair for pair in pairs if pair.pair_name == "canonical-v1-pair-001"
    )
    first_view = first.estimator_view()
    assert first_view.left_state.claim_assessments[0].support_state \
        is SupportState.SUPPORTED
    assert first_view.right_state.claim_assessments[0].support_state \
        is SupportState.UNSUPPORTED
    fifth = next(
        pair for pair in pairs if pair.pair_name == "canonical-v1-pair-005"
    )
    fifth_view = fifth.estimator_view()
    assert fifth_view.left_state.claim_assessments[0].support_state \
        is SupportState.FALSIFIED
    assert fifth_view.right_state.claim_assessments[0].support_state \
        is SupportState.EXTERNAL_EVIDENCE_REQUIRED


def test_case_construction_and_projection_do_not_mutate_authoritative_sources():
    pair = FROZEN_VALUE_V1_EVALUATION_CASE_SET.pairs[0]
    built = build_canonical_state(pair.left)
    state_before = built.session_state.model_dump(mode="json")
    commitments_before = [item.to_dict() for item in built.commitments]
    aporia_before = [item.to_dict() for item in built.aporia_records]
    hybrid_before = deepcopy(built.hybrid_state.__dict__)
    pair.estimator_view()
    assert built.session_state.model_dump(mode="json") == state_before
    assert [item.to_dict() for item in built.commitments] == commitments_before
    assert [item.to_dict() for item in built.aporia_records] == aporia_before
    assert built.hybrid_state.__dict__ == hybrid_before


def test_phase5_artifact_remains_sealed_before_any_value_v1_result():
    path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "branches"
        / "feature-socrates-zero-search-v0"
        / "artifacts"
        / "socrateszero_search_kernel_benchmark_v0.json"
    )
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(normalized).hexdigest() == _PHASE5_SHA256
