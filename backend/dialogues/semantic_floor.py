"""Deterministic semantic contribution floor for CED move content.

A move contract that constrains strings only by "non-empty" accepts a model that
cannot meet it: every required field gets one letter and the move is valid. That
is not hypothetical. Four open-weight seats across two size classes did exactly
this on live runs, returning ``{"question": "M"}`` and
``{"commitments": ["S", "R", "T"]}``, and CED recorded them as accepted moves —
which made `ced_move_accepted` useless as evidence of contribution.

This module answers one narrow question: could this string carry a proposition
at all? It never judges whether the proposition is true, relevant or good. That
remains CED's job, and no judge model is involved anywhere here.

The floor is a small combination of structural checks rather than one length
rule, because a length rule alone admits ``"AAAAAAAAAAAAAAAAAAAAAAAAAAAA"``.

Fields are **allowlisted**. A field not named below is never checked, so
identifier-carrying fields (``commitment_id``, ``ref_id``,
``commitments_retained``) cannot be broken by tightening this file.
"""

from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, Mapping

#: A proposition needs room to exist.
SUBSTANTIVE_MIN_CHARS = 24
#: Enough separate words for a subject and a predicate.
SUBSTANTIVE_MIN_WORDS = 4
#: Repetition is not content: "the the the the" must not pass.
SUBSTANTIVE_MIN_DISTINCT_WORDS = 4
#: Words long enough to be more than articles and connectives.
SUBSTANTIVE_MIN_CONTENT_WORDS = 3
#: Character variety defeats padding one letter out to length.
SUBSTANTIVE_MIN_DISTINCT_LETTERS = 8

#: A cited span is quoted from the task, not authored, so it may be short.
#: "Managers voluntarily apply" is a real citation; "M" is not.
QUOTED_SPAN_MIN_CHARS = 8
QUOTED_SPAN_MIN_WORDS = 2
QUOTED_SPAN_MIN_DISTINCT_LETTERS = 6

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

#: Operators and step references carry the proposition in a formal derivation.
#: Counting only alphabetic words made "(5) not-Fair; (6) not-Fair -> Abolish"
#: look like three-word repetition, so the floor discarded exactly the dense,
#: symbolic reasoning this research line is trying to elicit. These tokens count
#: toward *distinctness* only; the prose requirements below are untouched, so a
#: string of bare symbols still fails for want of content words.
_FORMAL_TOKEN_RE = re.compile(
    r"<->|->|=>|\|-|[¬∧∨→←↔⊃⊢⊨∀∃≠≤≥≡∈∉∪∩⊂⊆∴∵±×÷√∑∏]|\d+",
    re.UNICODE,
)


def _distinct_semantic_units(text: str, words):
    """Distinct meaning-bearing units: words plus formal tokens."""

    units = {w.lower() for w in words}
    units.update(_FORMAL_TOKEN_RE.findall(text))
    return units


class SemanticFloorError(ValueError):
    """Content satisfied the schema without carrying a proposition."""


def _fail(field: str, reason: str, value: str) -> "SemanticFloorError":
    return SemanticFloorError(
        f"semantic contribution floor: {field}: {reason} "
        f"(received {value.strip()[:60]!r})"
    )


def assert_substantive(value: str, field: str = "content") -> str:
    """Reject text that fits the schema without asserting anything."""

    if not isinstance(value, str):
        raise _fail(field, "must be text", str(value))
    text = value.strip()
    if len(text) < SUBSTANTIVE_MIN_CHARS:
        raise _fail(field, f"needs at least {SUBSTANTIVE_MIN_CHARS} characters", value)
    words = _WORD_RE.findall(text)
    if len(words) < SUBSTANTIVE_MIN_WORDS:
        raise _fail(field, f"needs at least {SUBSTANTIVE_MIN_WORDS} words", value)
    if len(_distinct_semantic_units(text, words)) < SUBSTANTIVE_MIN_DISTINCT_WORDS:
        raise _fail(
            field,
            f"needs at least {SUBSTANTIVE_MIN_DISTINCT_WORDS} distinct words or "
            "formal tokens",
            value,
        )
    if sum(1 for w in words if len(w) >= 3) < SUBSTANTIVE_MIN_CONTENT_WORDS:
        raise _fail(
            field,
            f"needs at least {SUBSTANTIVE_MIN_CONTENT_WORDS} words of three or "
            "more letters",
            value,
        )
    if len({c.lower() for c in text if c.isalpha()}) < SUBSTANTIVE_MIN_DISTINCT_LETTERS:
        raise _fail(
            field,
            f"needs at least {SUBSTANTIVE_MIN_DISTINCT_LETTERS} distinct letters; "
            "repeated padding is not content",
            value,
        )
    return value


def assert_interrogative(value: str, field: str = "question") -> str:
    """A Socratic question must be substantive and must actually ask."""

    assert_substantive(value, field)
    if "?" not in value:
        raise _fail(field, "a question must contain '?'", value)
    return value


def assert_quoted_span(value: str, field: str = "cited_spans") -> str:
    """Reject a degenerate citation without demanding a full proposition."""

    if not isinstance(value, str):
        raise _fail(field, "must be text", str(value))
    text = value.strip()
    if len(text) < QUOTED_SPAN_MIN_CHARS:
        raise _fail(
            field, f"a cited span needs at least {QUOTED_SPAN_MIN_CHARS} characters",
            value,
        )
    words = _WORD_RE.findall(text)
    if len({w.lower() for w in words}) < QUOTED_SPAN_MIN_WORDS:
        raise _fail(
            field,
            f"a cited span needs at least {QUOTED_SPAN_MIN_WORDS} distinct words",
            value,
        )
    if len({c.lower() for c in text if c.isalpha()}) < QUOTED_SPAN_MIN_DISTINCT_LETTERS:
        raise _fail(
            field,
            f"a cited span needs at least {QUOTED_SPAN_MIN_DISTINCT_LETTERS} "
            "distinct letters",
            value,
        )
    return value


# -- Which fields carry a proposition ------------------------------------------
#
# Allowlists, deliberately. Anything absent is never checked, so a field that
# names something rather than asserting it is safe by construction:
# ``commitment_id``, ``ref_id``, ``status``, ``target_section``, and the
# ``commitments_retained`` / ``commitments_withdrawn`` id lists.

INTERROGATIVE_FIELDS: FrozenSet[str] = frozenset({"question", "remaining_question"})

PROPOSITION_FIELDS: FrozenSet[str] = frozenset(
    {
        "critique_summary",
        "synthesis_draft",
        "stronger_position",
        "core_answer",
        "crucial_stress_test",
        "blind_spots",
        "nuance",
        "final_verdict",
        "rationale",
        "caveat",
        "required_fix",
        "condition_tested",
        "answer_to_socratic_question",
        "remaining_uncertainty",
        "revised_position",
        "what_changed",
        "pending_on",
        "new_claim",
    }
)

PROPOSITION_LIST_FIELDS: FrozenSet[str] = frozenset(
    {
        "contradictions",
        "weak_assumptions",
        "logic_gaps",
        "documentation_gaps",
        "commitments",
        "key_insights",
        "unresolved_tensions",
        "new_commitments",
        "integrated_critiques",
        "remaining_weaknesses",
    }
)

QUOTED_SPAN_LIST_FIELDS: FrozenSet[str] = frozenset({"cited_spans"})

#: Object-valued fields, mapped to the keys inside them that carry propositions.
NESTED_PROPOSITION_FIELDS: Mapping[str, FrozenSet[str]] = {
    "factual_claims": frozenset({"claim", "notes"}),
    "commitments_revised": frozenset({"new_claim"}),
    "commitments_suspended": frozenset({"pending_on"}),
}


def assert_move_content_floor(content: Any) -> None:
    """Apply the floor to every proposition-bearing field present in content.

    Silent on anything it does not recognise: numeric scoring payloads, enum
    slots, identifier fields and any future field all pass untouched. Raises
    :class:`SemanticFloorError` on the first violation.
    """

    if not isinstance(content, dict):
        return
    for field, value in content.items():
        if field in INTERROGATIVE_FIELDS:
            assert_interrogative(value, field)
        elif field in PROPOSITION_FIELDS:
            assert_substantive(value, field)
        elif field in PROPOSITION_LIST_FIELDS:
            if isinstance(value, list):
                for item in value:
                    assert_substantive(item, field)
        elif field in QUOTED_SPAN_LIST_FIELDS:
            if isinstance(value, list):
                for item in value:
                    assert_quoted_span(item, field)
        elif field in NESTED_PROPOSITION_FIELDS:
            inner_keys = NESTED_PROPOSITION_FIELDS[field]
            items = value if isinstance(value, list) else [value]
            for item in items:
                if not isinstance(item, dict):
                    continue
                for inner in inner_keys:
                    if inner in item:
                        assert_substantive(item[inner], f"{field}.{inner}")


__all__ = [
    "SemanticFloorError",
    "assert_interrogative",
    "assert_move_content_floor",
    "assert_quoted_span",
    "assert_substantive",
    "INTERROGATIVE_FIELDS",
    "PROPOSITION_FIELDS",
    "PROPOSITION_LIST_FIELDS",
    "QUOTED_SPAN_LIST_FIELDS",
    "NESTED_PROPOSITION_FIELDS",
    "SUBSTANTIVE_MIN_CHARS",
    "QUOTED_SPAN_MIN_CHARS",
]
