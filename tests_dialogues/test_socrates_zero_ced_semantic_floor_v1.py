"""The CED acceptance contract must reject schema-valid, contribution-free moves.

Every MUST-REJECT fixture below is a verbatim body a live model actually
returned and CED actually accepted, taken from
`runs/q1_lowcost_heterogeneous_ced_v1.json` and
`runs/q1_condition_c_four_seat_v1.json`. They are kept as fixtures rather than
deleted, because they are the only direct evidence of the failure this floor
exists to close.

The MUST-ACCEPT fixtures are also real: substantive moves from the same runs and
from the ratified two-seat council. A floor that rejected those would be a
regression of a different kind.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
    SUBSTANTIVE_MIN_CHARS_V1,
    assert_interrogative_text_v1,
    assert_substantive_text_v1,
)
from backend.dialogues.socrates_zero.contracts import ContractValidationError

# --------------------------------------------------------------------------
# Verbatim placeholder values observed live, one per accepted move.
# --------------------------------------------------------------------------

OBSERVED_PLACEHOLDER_VALUES_V1 = [
    pytest.param("M", id="llama-4-scout-question"),
    pytest.param("W", id="llama-4-scout-question-2"),
    pytest.param("A", id="llama-4-scout-stronger-position"),
    pytest.param("S", id="maverick-commitment-S"),
    pytest.param("R", id="maverick-commitment-R"),
    pytest.param("T", id="maverick-commitment-T"),
    pytest.param("I", id="maverick-critique-summary"),
    pytest.param("N", id="qwen3-32b-documentation-gap"),
    pytest.param("1", id="qwen3-32b-commitment-digit"),
    pytest.param("O", id="qwen3-235b-key-insight"),
]

#: Ways a model could pad past a bare length rule.  A `minLength` alone admits
#: every one of these, which is why the floor is a combination.
PADDING_EVASIONS_V1 = [
    pytest.param("A" * 40, id="single-letter-padded"),
    pytest.param("ab " * 20, id="two-letter-word-repeated"),
    pytest.param("the the the the the the the the", id="one-word-repeated"),
    pytest.param("a b c d e f g h i j k l m n o p", id="single-letters-spaced"),
    pytest.param("1. 2. 3. 4. 5. 6. 7. 8. 9. 10.", id="bare-enumerators"),
    pytest.param("... --- ... --- ... --- ... ---", id="punctuation-only"),
    pytest.param("M, M, M, M, M, M, M, M, M, M, M", id="placeholder-list-flattened"),
]

#: Verbatim substantive values from accepted moves that must keep passing.
OBSERVED_SUBSTANTIVE_VALUES_V1 = [
    pytest.param(
        "The six statements are jointly inconsistent (they force a direct "
        "contradiction about Mira approving S).",
        id="gpt-5-mini-commitment",
    ),
    pytest.param(
        "Anyone who filed a formal exception did not chair the final review; "
        "by contraposition, Mira did not file a formal exception.",
        id="derivation-step",
    ),
    pytest.param(
        "The minimal inconsistent subset is the entire set of six statements "
        "{1,2,3,4,5,6}.",
        id="minimal-subset-claim",
    ),
    pytest.param(
        "Precise formalization convention for the English quantifier phrase "
        "'Anyone ...' (universal by material implication, or weaker).",
        id="documentation-gap",
    ),
]


@pytest.mark.parametrize("value", OBSERVED_PLACEHOLDER_VALUES_V1)
def test_observed_placeholder_is_rejected(value: str) -> None:
    with pytest.raises(ContractValidationError):
        assert_substantive_text_v1(value)


@pytest.mark.parametrize("value", PADDING_EVASIONS_V1)
def test_padding_cannot_buy_acceptance(value: str) -> None:
    assert len(value) >= SUBSTANTIVE_MIN_CHARS_V1, "fixture must clear the length rule"
    with pytest.raises(ContractValidationError):
        assert_substantive_text_v1(value)


@pytest.mark.parametrize("value", OBSERVED_SUBSTANTIVE_VALUES_V1)
def test_real_content_still_passes(value: str) -> None:
    assert assert_substantive_text_v1(value) == value


def test_question_must_actually_ask() -> None:
    statement = "The six statements are jointly inconsistent under classical logic."
    assert_substantive_text_v1(statement)
    with pytest.raises(ContractValidationError):
        assert_interrogative_text_v1(statement)


def test_real_socratic_question_passes() -> None:
    question = (
        "Before we formalize the six premises, can the council commit to reading "
        "'anyone who X' as a universal material implication?"
    )
    assert assert_interrogative_text_v1(question) == question


# --------------------------------------------------------------------------
# The same fixtures through the actual move contract, not just the primitive.
# --------------------------------------------------------------------------


def _socratic_opening_task():
    """The module's own representative task, so the fixture cannot drift."""
    from backend.dialogues.models import DialogPhase, TaskKind
    from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
        _representative_tasks_v1,
    )

    for task in _representative_tasks_v1():
        if (
            task.task_kind is TaskKind.SOCRATIC_QUESTION
            and task.phase is DialogPhase.OPENING
        ):
            return task
    raise AssertionError("no representative Socratic opening task")


def test_llama_scout_opening_move_is_rejected_by_the_contract() -> None:
    """`{"question": "M"}` was accepted live; it must not be any more."""
    from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
        validate_ced_structured_output_v1,
    )

    body = json.dumps(
        {
            "confidence": 0.6,
            "content": {
                "epistemic_marker": "open_uncertainty",
                "operator": "clarify",
                "question": "M",
            },
        }
    )
    # Either gate may fire first: the declared `minLength` on the wire type, or
    # the floor validator behind it. Both are the floor doing its job, and the
    # adapter already surfaces both as a rejected move. What must not happen is
    # the move being accepted, or being rejected for some unrelated reason.
    with pytest.raises((ContractValidationError, ValidationError)) as caught:
        validate_ced_structured_output_v1(_socratic_opening_task(), body)
    message = str(caught.value)
    assert "question" in message
    assert (
        "semantic contribution floor" in message
        or "at least 24 characters" in message
    )


def test_substantive_opening_move_is_still_accepted() -> None:
    from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
        validate_ced_structured_output_v1,
    )

    body = json.dumps(
        {
            "confidence": 0.6,
            "content": {
                "epistemic_marker": "reasonable_hypothesis",
                "operator": "clarify",
                "question": (
                    "Can the council commit to reading each 'anyone who' clause "
                    "as a universal material implication?"
                ),
            },
        }
    )
    assert validate_ced_structured_output_v1(_socratic_opening_task(), body) is not None


def test_padded_question_is_rejected_by_the_floor_not_by_length() -> None:
    """A 40-character single letter clears `minLength` and must still fail."""
    from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
        validate_ced_structured_output_v1,
    )

    body = json.dumps(
        {
            "confidence": 0.6,
            "content": {
                "epistemic_marker": "open_uncertainty",
                "operator": "clarify",
                "question": "A" * 40 + "?",
            },
        }
    )
    with pytest.raises((ContractValidationError, ValidationError)) as caught:
        validate_ced_structured_output_v1(_socratic_opening_task(), body)
    assert "semantic contribution floor" in str(caught.value)


def test_qwen_commitment_list_is_rejected_by_the_contract() -> None:
    """`{"commitments": ["M", "1", "2", ...]}` was accepted live."""
    from backend.dialogues.models import DialogPhase, TaskKind
    from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
        _representative_tasks_v1,
        validate_ced_structured_output_v1,
    )

    task = next(
        t
        for t in _representative_tasks_v1()
        if t.task_kind is TaskKind.INITIAL_RESPONSE
    )
    body = json.dumps(
        {
            "confidence": 0.95,
            "content": {
                "commitments": ["M", "1", "2", "4", "5", "6"],
                "key_insights": ["M", "1", "2", "4", "5", "6"],
                "synthesis_draft": "M",
                "unresolved_tensions": ["M"],
                "epistemic_marker": "established_fact",
            },
        }
    )
    with pytest.raises((ContractValidationError, ValidationError)):
        validate_ced_structured_output_v1(task, body)


# --------------------------------------------------------------------------
# Where the floor is enforced.
#
# `parse_and_validate_move` deliberately accepts content the provider schema
# rejects — `test_provider_schema_and_ced_acceptance_remain_separate_measurements`
# pins that separation, and an empty question is caught downstream by
# `validate_socratic_content` instead.  Both of those live in files under the
# canonical-successor blob lock, so the floor is enforced in the live adapter,
# which is where `ced_move_accepted` is decided for these runs.
# --------------------------------------------------------------------------


def test_parser_separation_is_left_intact() -> None:
    """The floor must not be smuggled into the shared parser."""
    from backend.dialogues.models import ProviderStatus
    from backend.dialogues.provider_registry import parse_and_validate_move

    _move, status, _err = parse_and_validate_move(
        json.dumps(
            {
                "confidence": 0.9,
                "content": {
                    "question": "M",
                    "operator": "clarify",
                    "epistemic_marker": "open_uncertainty",
                },
            }
        ),
        _socratic_opening_task(),
    )
    assert status is ProviderStatus.OK


def test_adapter_rejects_a_placeholder_move() -> None:
    """`{"question": "M"}` must never reach the council through the adapter."""
    from backend.dialogues.semantic_floor import (
        SemanticFloorError,
        assert_move_content_floor,
    )

    with pytest.raises(SemanticFloorError):
        assert_move_content_floor(
            {
                "question": "M",
                "operator": "clarify",
                "epistemic_marker": "open_uncertainty",
            }
        )


def test_adapter_floor_is_wired_into_the_acceptance_decision() -> None:
    """The live adapter must consult the floor before reporting acceptance."""
    import inspect

    from backend.dialogues.socrates_zero import (
        openrouter_live_session_adapter_v1 as adapter,
    )

    source = inspect.getsource(adapter)
    assert "assert_move_content_floor" in source
    # It must run where acceptance is decided, not merely as recorded evidence.
    decision = source.split("accepted = status is ProviderStatus.OK", 1)[1]
    assert "assert_move_content_floor" in decision
    assert "accepted = False" in decision


def test_placeholder_commitment_list_is_rejected_by_the_floor() -> None:
    from backend.dialogues.semantic_floor import (
        SemanticFloorError,
        assert_move_content_floor,
    )

    with pytest.raises(SemanticFloorError):
        assert_move_content_floor(
            {
                "commitments": ["M", "1", "2", "4", "5", "6"],
                "synthesis_draft": "M",
                "epistemic_marker": "established_fact",
            }
        )


def test_identifier_fields_are_never_held_to_the_floor() -> None:
    """`commitments_retained` carries ids like "c1"; tightening must not break it."""
    from backend.dialogues.semantic_floor import assert_move_content_floor

    assert_move_content_floor(
        {
            "commitments_retained": ["c1", "c2"],
            "commitments_withdrawn": ["c3"],
            "epistemic_marker": "logical_inference",
        }
    )


def test_numeric_scoring_payloads_pass_untouched() -> None:
    from backend.dialogues.semantic_floor import assert_move_content_floor

    assert_move_content_floor(
        {"logical_rigor": 3, "intellectual_honesty": 1, "clarity_precision": 0}
    )


def test_substantive_move_content_passes_the_floor() -> None:
    from backend.dialogues.semantic_floor import assert_move_content_floor

    assert_move_content_floor(
        {
            "question": (
                "Can the council commit to reading each 'anyone who' clause as a "
                "universal material implication?"
            ),
            "operator": "clarify",
            "epistemic_marker": "reasonable_hypothesis",
        }
    )
