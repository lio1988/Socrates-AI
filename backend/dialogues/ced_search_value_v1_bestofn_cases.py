"""Frozen secondary BestOfN quartets, defined before search execution."""

from __future__ import annotations

from collections import Counter
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import model_validator

from .ced_search_value_v1_evaluation_cases import (
    CanonicalClaimBlueprint,
    CanonicalStateBlueprint,
    FROZEN_VALUE_V1_EVALUATION_CASE_SET,
    ValueV1EvaluationCategory,
    ValueV1EvaluationSplit,
    ValueV1PairExpectation,
    build_canonical_state,
)
from .socrates_zero.constitution import CEDSearchConstitution
from .socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)
from .socrates_zero.evaluation import _FrozenEvaluationContract


VALUE_V1_BESTOFN_CASE_SET_VERSION = (
    "socrateszero-value-v1-bestofn-case-set/v0"
)
VALUE_V1_BESTOFN_HARNESS_VERSION = "socrateszero-value-v1-bestofn-harness/v0"
VALUE_V1_BESTOFN_CASE_VERSION = "socrateszero-value-v1-bestofn-case/v0"


class ValueV1BestOfNCaseMode(str, Enum):
    ORDERED_SELECTION = "ordered_selection"
    GUARDRAIL_TIE = "guardrail_tie"


class ValueV1BestOfNCase(_FrozenEvaluationContract):
    schema_version: Literal[
        VALUE_V1_BESTOFN_CASE_VERSION
    ] = VALUE_V1_BESTOFN_CASE_VERSION
    case_id: Optional[str] = None
    case_name: str
    mode: ValueV1BestOfNCaseMode
    source_pair_id: str
    category: ValueV1EvaluationCategory
    root: CanonicalStateBlueprint
    candidates: Tuple[CanonicalStateBlueprint, ...]
    optimal_candidate_slot: Optional[int] = None

    @model_validator(mode="after")
    def validate_and_identify(self) -> "ValueV1BestOfNCase":
        if not self.case_name.strip():
            raise ContractValidationError("BestOfN case name cannot be blank")
        if len(self.candidates) != 4:
            raise ContractValidationError("BestOfN case requires four candidates")
        ids = {self.root.blueprint_id} | {
            item.blueprint_id for item in self.candidates
        }
        if len(ids) != 5:
            raise ContractValidationError("BestOfN state blueprint IDs must be unique")
        if self.mode is ValueV1BestOfNCaseMode.ORDERED_SELECTION:
            if self.optimal_candidate_slot not in range(4):
                raise ContractValidationError("ordered case requires an optimal slot")
        elif self.optimal_candidate_slot is not None:
            raise ContractValidationError("guardrail case cannot name a winner")
        expected = stable_contract_id(
            "szvaluev1bestofncase",
            self.model_dump(mode="json", exclude={"case_id"}),
        )
        if self.case_id is not None and self.case_id != expected:
            raise ContractValidationError("BestOfN case ID does not match semantics")
        object.__setattr__(self, "case_id", expected)
        return self


class ValueV1BestOfNCaseSet(_FrozenEvaluationContract):
    case_set_id: Literal[
        VALUE_V1_BESTOFN_CASE_SET_VERSION
    ] = VALUE_V1_BESTOFN_CASE_SET_VERSION
    case_set_digest: Optional[str] = None
    cases: Tuple[ValueV1BestOfNCase, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "ValueV1BestOfNCaseSet":
        if len(self.cases) != 11:
            raise ContractValidationError("secondary case set requires 11 cases")
        if len({item.case_id for item in self.cases}) != 11:
            raise ContractValidationError("secondary case IDs must be unique")
        counts = Counter(item.mode for item in self.cases)
        if counts[ValueV1BestOfNCaseMode.ORDERED_SELECTION] != 7:
            raise ContractValidationError("secondary set requires seven ordered cases")
        if counts[ValueV1BestOfNCaseMode.GUARDRAIL_TIE] != 4:
            raise ContractValidationError("secondary set requires four guardrails")
        ordered = tuple(sorted(self.cases, key=lambda item: item.case_name))
        object.__setattr__(self, "cases", ordered)
        expected = stable_contract_id(
            "szvaluev1bestofncases",
            {
                "case_set_id": self.case_set_id,
                "case_ids": [item.case_id for item in ordered],
            },
        )
        if self.case_set_digest is not None and self.case_set_digest != expected:
            raise ContractValidationError("secondary case-set digest mismatch")
        object.__setattr__(self, "case_set_digest", expected)
        return self


def _clone(
    source: CanonicalStateBlueprint, *, case_number: int, slot: int
) -> CanonicalStateBlueprint:
    return source.model_copy(
        update={"blueprint_id": f"bestofn-state-{case_number:02d}-{slot}"}
    )


def _root(case_number: int) -> CanonicalStateBlueprint:
    return CanonicalStateBlueprint(
        blueprint_id=f"bestofn-root-{case_number:02d}",
        claims=(
            CanonicalClaimBlueprint(),
            CanonicalClaimBlueprint(),
            CanonicalClaimBlueprint(),
        ),
        aporia_count=1,
    )


def _control(case_number: int, slot: int) -> CanonicalStateBlueprint:
    return CanonicalStateBlueprint(
        blueprint_id=f"bestofn-state-{case_number:02d}-{slot}",
        claims=(CanonicalClaimBlueprint(falsified_count=1),),
    )


_PRIMARY_HOLDOUT = {
    item.pair_name: item
    for item in FROZEN_VALUE_V1_EVALUATION_CASE_SET.for_split(
        ValueV1EvaluationSplit.HOLDOUT
    )
}
_ORDERED_PRIMARY = tuple(
    sorted(
        (
            item for item in _PRIMARY_HOLDOUT.values()
            if item.expectation is not ValueV1PairExpectation.REQUIRED_TIE
        ),
        key=lambda item: item.pair_name,
    )
)


def _ordered_case(case_number: int, pair) -> ValueV1BestOfNCase:
    candidates = (
        _clone(pair.left, case_number=case_number, slot=0),
        _control(case_number, 1),
        _clone(pair.right, case_number=case_number, slot=2),
        _control(case_number, 3),
    )
    optimal_slot = (
        0
        if pair.expectation is ValueV1PairExpectation.LEFT_BETTER
        else 2
    )
    return ValueV1BestOfNCase(
        case_name=f"bestofn-case-{case_number:02d}",
        mode=ValueV1BestOfNCaseMode.ORDERED_SELECTION,
        source_pair_id=pair.pair_id,
        category=pair.category,
        root=_root(case_number),
        candidates=candidates,
        optimal_candidate_slot=optimal_slot,
    )


_GUARDRAIL_SOURCES = (
    _PRIMARY_HOLDOUT["canonical-v1-pair-013"],
    _PRIMARY_HOLDOUT["canonical-v1-pair-018"],
    _PRIMARY_HOLDOUT["canonical-v1-pair-033"],
    _PRIMARY_HOLDOUT["canonical-v1-pair-043"],
)


def _guardrail_case(case_number: int, pair) -> ValueV1BestOfNCase:
    candidates = (
        _clone(pair.left, case_number=case_number, slot=0),
        _clone(pair.right, case_number=case_number, slot=1),
        _clone(pair.left, case_number=case_number, slot=2),
        _clone(pair.right, case_number=case_number, slot=3),
    )
    return ValueV1BestOfNCase(
        case_name=f"bestofn-case-{case_number:02d}",
        mode=ValueV1BestOfNCaseMode.GUARDRAIL_TIE,
        source_pair_id=pair.pair_id,
        category=pair.category,
        root=_root(case_number),
        candidates=candidates,
    )


_CASES = tuple(
    _ordered_case(index, pair)
    for index, pair in enumerate(_ORDERED_PRIMARY, start=1)
) + tuple(
    _guardrail_case(index, pair)
    for index, pair in enumerate(_GUARDRAIL_SOURCES, start=8)
)


FROZEN_VALUE_V1_BESTOFN_CASE_SET = ValueV1BestOfNCaseSet(cases=_CASES)


def frozen_bestofn_case_set_canonical_json() -> str:
    return canonical_json(
        FROZEN_VALUE_V1_BESTOFN_CASE_SET.model_dump(mode="json")
    )


def validate_root_legality(case: ValueV1BestOfNCase) -> Tuple[str, ...]:
    root = build_canonical_state(case.root).projected.base_state
    actions = CEDSearchConstitution().legal_actions(root)
    if len(actions) != 4:
        raise ContractValidationError(
            "secondary canonical root must expose exactly four legal actions"
        )
    return tuple(action.action_id for action in actions)


__all__ = [
    "FROZEN_VALUE_V1_BESTOFN_CASE_SET",
    "VALUE_V1_BESTOFN_CASE_SET_VERSION",
    "VALUE_V1_BESTOFN_HARNESS_VERSION",
    "ValueV1BestOfNCase",
    "ValueV1BestOfNCaseMode",
    "ValueV1BestOfNCaseSet",
    "frozen_bestofn_case_set_canonical_json",
    "validate_root_legality",
]
