"""Pre-search freeze tests; these execute no BestOfN strategy."""

from __future__ import annotations

from collections import Counter
import hashlib

from backend.dialogues.ced_search_value_v1_bestofn_cases import (
    FROZEN_VALUE_V1_BESTOFN_CASE_SET,
    VALUE_V1_BESTOFN_CASE_SET_VERSION,
    VALUE_V1_BESTOFN_HARNESS_VERSION,
    ValueV1BestOfNCaseMode,
    frozen_bestofn_case_set_canonical_json,
    validate_root_legality,
)
from backend.dialogues.ced_search_value_v1_evaluation_cases import (
    build_canonical_state,
)


def test_secondary_ids_counts_and_modes_are_frozen_after_primary_pass():
    case_set = FROZEN_VALUE_V1_BESTOFN_CASE_SET
    assert case_set.case_set_id == VALUE_V1_BESTOFN_CASE_SET_VERSION \
        == "socrateszero-value-v1-bestofn-case-set/v0"
    assert VALUE_V1_BESTOFN_HARNESS_VERSION \
        == "socrateszero-value-v1-bestofn-harness/v0"
    assert len(case_set.cases) == 11
    counts = Counter(item.mode for item in case_set.cases)
    assert counts[ValueV1BestOfNCaseMode.ORDERED_SELECTION] == 7
    assert counts[ValueV1BestOfNCaseMode.GUARDRAIL_TIE] == 4


def test_every_secondary_root_has_exactly_four_real_constitutional_actions():
    for case in FROZEN_VALUE_V1_BESTOFN_CASE_SET.cases:
        assert len(validate_root_legality(case)) == 4


def test_every_secondary_successor_recipe_replays_from_real_canonical_sources():
    state_ids = set()
    for case in FROZEN_VALUE_V1_BESTOFN_CASE_SET.cases:
        for blueprint in case.candidates:
            assert "support_state" not in blueprint.model_dump(mode="json")
            state = build_canonical_state(blueprint).projected
            assert state.state_id not in state_ids
            state_ids.add(state.state_id)
    assert len(state_ids) == 44


def test_secondary_state_ids_are_neutral_and_labels_are_evaluator_only():
    forbidden = {"winner", "optimal", "better", "tie", "left", "right"}
    for case in FROZEN_VALUE_V1_BESTOFN_CASE_SET.cases:
        for blueprint in (case.root, *case.candidates):
            assert all(token not in blueprint.blueprint_id for token in forbidden)
        if case.mode is ValueV1BestOfNCaseMode.GUARDRAIL_TIE:
            assert case.optimal_candidate_slot is None


def test_secondary_case_set_has_deterministic_digest_and_sha_lock():
    case_set = FROZEN_VALUE_V1_BESTOFN_CASE_SET
    rendered = frozen_bestofn_case_set_canonical_json().encode("utf-8")
    assert case_set.case_set_digest == (
        "szvaluev1bestofncases_"
        "22a0659a07be21d83c17d566c6fe5e3fe66c6fea6830b79a2535495b0090d667"
    )
    assert hashlib.sha256(rendered).hexdigest() == (
        "e18aa8ff8ac371fd5857dbc7b7c47058eac223bf76194acbef7c685252ed5f53"
    )
