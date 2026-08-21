"""Integrity tests for the two frozen, offline architectural failure fixtures.

The fixtures preserve observed evidence only. They make no provider calls and
contain no proposed Hybrid behavior.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "known_failures"
FIXTURE_SCHEMA = "socrates_known_failure_fixture_v1"
GROUND_TRUTH = ["Anna", "Ben", "Clara", "David"]
QUESTION = """Four researchers — Anna, Ben, Clara, and David — each present exactly once,
in positions 1 through 4.

The following statements are all true:

1. Anna presents before Ben.
2. Clara presents immediately before David.
3. Ben does not present last.

Determine the unique presentation order.

Do not guess. Enumerate or logically eliminate the possible orders, verify
that the final order satisfies every constraint, and state whether the
information is sufficient to determine a unique solution. If it is not
sufficient, explicitly say so and list all valid orders."""


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _valid_orders() -> list[list[str]]:
    valid = []
    for order in itertools.permutations(("Anna", "Ben", "Clara", "David")):
        positions = {name: index for index, name in enumerate(order)}
        if not positions["Anna"] < positions["Ben"]:
            continue
        if positions["David"] != positions["Clara"] + 1:
            continue
        if positions["Ben"] == 3:
            continue
        valid.append(list(order))
    return valid


def test_fixture_ground_truth_is_objective_and_identical():
    assert _valid_orders() == [GROUND_TRUTH]
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        assert fixture["schema_version"] == FIXTURE_SCHEMA
        assert fixture["benchmark"]["question_verbatim"] == QUESTION
        assert fixture["benchmark"]["ground_truth"] == {
            "unique": True,
            "valid_orders": [GROUND_TRUTH],
        }
        assert fixture["offline_replay"]["provider_calls"] == 0
        assert fixture["offline_replay"]["network_required"] is False
        assert fixture["source"]["raw_provider_transcript_complete"] is False
        assert fixture["unavailable_material"]


def test_current_canonical_fixture_preserves_consensus_failure_chain():
    fixture = _load("current_canonical_repeat_003.json")
    observed = fixture["observed"]

    assert observed["initial_correct_candidate"]["present"] is True
    assert observed["initial_correct_candidate"]["semantic_answer"] == GROUND_TRUTH
    assert observed["initially_correct_agent_abandoned_correct_position"] is True
    assert observed["reflection_reinforced_false_consensus"] is True
    assert observed["incorrect_reasoning_received_high_scores"] is True
    assert observed["ratification"]["verdicts"] == ["accept"] * 3
    assert observed["ratification"]["status"] == "ratified"
    assert observed["epistemic_status"] == "well_supported"
    assert observed["final_answer"]["objective_correctness"] == "false"
    assert observed["final_answer"]["verbatim_text"] is None
    assert observed["score_values"] is None


def test_historical_fixture_preserves_cbe_and_renderer_failure_chain():
    fixture = _load("historical_challenger_live_001.json")
    observed = fixture["observed"]
    selected = observed["cbe_selection"]

    assert observed["provider_calls"]["successful"] == 36
    assert observed["provider_calls"]["failed"] == 0
    assert observed["graph"]["cbe_confidence"] == 0.0
    assert observed["correct_initial_claim"]["semantic_answer"] == GROUND_TRUTH
    assert selected[0]["objective_correctness"] == "false"
    assert selected[1]["semantic_answer"] == GROUND_TRUTH
    assert selected[1]["objective_correctness"] == "true"
    assert observed["selected_claims_materially_compatible"] is False
    assert observed["renderer_combined_selected_claims"] is True
    assert observed["final_answer"]["internally_contradictory"] is True
    assert observed["final_answer"]["objective_correctness"] == "false"
