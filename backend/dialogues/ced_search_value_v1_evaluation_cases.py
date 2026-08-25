"""Pre-registered canonical state-pair cases for the Value-v1 experiment.

Ground truth is evaluator-only.  Every state is reconstructed from real
``SessionState`` and ``HybridEpistemicState`` records and projected through
``ced-search-state-projection/v1``.  No SearchState-v1 observation is authored
directly and this module executes no Value estimator.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ced import CanonicalTaskSpec
from .ced_search_observability_v1 import SearchStateV1
from .ced_search_projection_v1 import project_search_state_v1
from .hybrid_epistemic import (
    ClaimRecord,
    ContradictionRecord,
    EvidenceRecord,
    EvidenceSourceType,
    EvidenceStance,
    HybridEpistemicState,
    ObjectionRecord,
    ObjectionScope,
    ObjectionState,
    ObjectionTargetProvenance,
    UNMAPPED_TARGET,
    VerificationClass,
    external_evidence_required,
    verify_task_internal,
)
from .models import (
    AgentMove,
    AgentRole,
    AgentState,
    DialogPhase,
    ProviderStatus,
    SessionState,
    TaskKind,
    TaskLogEntry,
)
from .socratic import AporiaRecord, CommitmentRecord, CommitmentStatus
from .socrates_zero.contracts import (
    BudgetUsage,
    ContractValidationError,
    SearchBudget,
    canonical_json,
    stable_contract_id,
)


VALUE_V1_EVAL_CASE_SET_VERSION = "socrateszero-value-v1-eval-case-set/v1"
VALUE_V1_EVAL_HARNESS_VERSION = "socrateszero-value-v1-eval-harness/v0"
VALUE_V1_EVAL_PAIR_SCHEMA_VERSION = "socrateszero-value-v1-eval-pair/v0"
VALUE_V1_EVAL_CASE_SET_DIGEST_PREFIX = "szvaluev1cases"

VALUE_V1_HOLDOUT_ORDERED_ACCURACY_THRESHOLD = 0.80
VALUE_V1_HOLDOUT_IMPROVEMENT_THRESHOLD = 0.20
VALUE_V1_NONTERMINAL_ORDERED_ACCURACY_THRESHOLD = 0.80
VALUE_V1_NONTERMINAL_IMPROVEMENT_THRESHOLD = 0.20
VALUE_V1_REQUIRED_TIE_ACCURACY_THRESHOLD = 1.0
VALUE_V1_SECONDARY_IMPROVEMENT_THRESHOLD = 0.10

_QUESTION = (
    "Canonical fixture evidence is supplied. Which current claim is more ready?"
)
_CITATION = "Canonical fixture evidence is supplied."
_AGENT_ID = "canonical-evaluation-agent"
_BUDGET = SearchBudget(
    max_nodes=8,
    max_expansions=4,
    max_model_calls=4,
    max_tool_calls=2,
    max_tokens=4000,
    max_cost_microusd=100_000,
    max_wall_time_ms=20_000,
    max_depth=1,
)


class _FrozenEvaluationModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ValueV1EvaluationSplit(str, Enum):
    DEVELOPMENT = "development"
    HOLDOUT = "holdout"


class ValueV1EvaluationCategory(str, Enum):
    USEFUL_SUPPORT_STATE = "useful_support_state"
    IRRELEVANT_V1_SIGNAL = "irrelevant_v1_signal"
    MISLEADING_LIFECYCLE_CLOSURE = "misleading_lifecycle_closure"
    DUPLICATE_DERIVED_SIGNAL = "duplicate_derived_signal"
    TERMINAL_SUPPORT_ONLY = "terminal_support_only"
    INTERMEDIATE_ASSESSMENT = "intermediate_assessment"
    V0_V1_EQUIVALENCE = "v0_v1_equivalence"
    RESOLUTION_REMOVES_PENALTY = "resolution_removes_penalty"
    COUNT_INFLATION = "count_inflation"


class ValueV1PairExpectation(str, Enum):
    LEFT_BETTER = "left_better"
    RIGHT_BETTER = "right_better"
    REQUIRED_TIE = "required_tie"


class ValueV1TerminalRecipe(str, Enum):
    NONTERMINAL = "nonterminal"
    BLOCKED = "blocked"
    BUDGET_EXHAUSTED = "budget_exhausted"


class CanonicalClaimBlueprint(_FrozenEvaluationModel):
    """Record recipe; never a direct SupportState assignment."""

    supporting_evidence_count: int = Field(default=0, ge=0, le=4)
    weak_evidence_count: int = Field(default=0, ge=0, le=4)
    model_assertion_count: int = Field(default=0, ge=0, le=4)
    deterministic_verified_count: int = Field(default=0, ge=0, le=4)
    model_verified_count: int = Field(default=0, ge=0, le=4)
    inconclusive_count: int = Field(default=0, ge=0, le=4)
    falsified_count: int = Field(default=0, ge=0, le=1)
    external_evidence_required: bool = False
    open_objection_count: int = Field(default=0, ge=0, le=4)
    rejected_objection_count: int = Field(default=0, ge=0, le=4)


class CanonicalStateBlueprint(_FrozenEvaluationModel):
    """Evaluator-independent source recipe with neutral deterministic IDs."""

    blueprint_id: str
    claims: Tuple[CanonicalClaimBlueprint, ...]
    aporia_count: int = Field(default=0, ge=0, le=2)
    candidate_contradiction_count: int = Field(default=0, ge=0, le=2)
    dismissed_contradiction_count: int = Field(default=0, ge=0, le=2)
    validated_contradiction_count: int = Field(default=0, ge=0, le=1)
    unmapped_open_objection_count: int = Field(default=0, ge=0, le=3)
    terminal: ValueV1TerminalRecipe = ValueV1TerminalRecipe.NONTERMINAL

    @model_validator(mode="after")
    def validate_recipe(self) -> "CanonicalStateBlueprint":
        if not self.blueprint_id.strip():
            raise ContractValidationError("state blueprint ID cannot be blank")
        if not self.claims:
            raise ContractValidationError("canonical state recipe requires a claim")
        contradiction_count = (
            self.candidate_contradiction_count
            + self.dismissed_contradiction_count
            + self.validated_contradiction_count
        )
        if contradiction_count and len(self.claims) < 2:
            raise ContractValidationError(
                "canonical contradiction recipes require two claims"
            )
        return self


class ValueV1StatePairView(_FrozenEvaluationModel):
    """Only lawful estimator-facing states; contains no ordering label."""

    left_state: SearchStateV1
    right_state: SearchStateV1


class ValueV1EvaluationPair(_FrozenEvaluationModel):
    schema_version: Literal[
        VALUE_V1_EVAL_PAIR_SCHEMA_VERSION
    ] = VALUE_V1_EVAL_PAIR_SCHEMA_VERSION
    pair_id: Optional[str] = None
    pair_name: str
    category: ValueV1EvaluationCategory
    split: ValueV1EvaluationSplit
    left: CanonicalStateBlueprint
    right: CanonicalStateBlueprint
    expectation: ValueV1PairExpectation
    ranking_regret_weight: float = Field(default=1.0, gt=0.0, le=2.0)

    @model_validator(mode="after")
    def identify(self) -> "ValueV1EvaluationPair":
        if not self.pair_name.strip():
            raise ContractValidationError("evaluation pair name cannot be blank")
        if self.left.blueprint_id == self.right.blueprint_id:
            raise ContractValidationError("pair states require distinct neutral IDs")
        expected = stable_contract_id(
            "szvaluev1pair",
            self.model_dump(mode="json", exclude={"pair_id"}),
        )
        if self.pair_id is not None and self.pair_id != expected:
            raise ContractValidationError("pair ID does not match frozen semantics")
        object.__setattr__(self, "pair_id", expected)
        return self

    def estimator_view(self) -> ValueV1StatePairView:
        return ValueV1StatePairView(
            left_state=build_canonical_state(self.left).projected,
            right_state=build_canonical_state(self.right).projected,
        )


class ValueV1EvaluationCaseSet(_FrozenEvaluationModel):
    case_set_id: Literal[
        VALUE_V1_EVAL_CASE_SET_VERSION
    ] = VALUE_V1_EVAL_CASE_SET_VERSION
    case_set_digest: Optional[str] = None
    pairs: Tuple[ValueV1EvaluationPair, ...]

    @model_validator(mode="after")
    def validate_balance_and_identify(self) -> "ValueV1EvaluationCaseSet":
        if len(self.pairs) != 45:
            raise ContractValidationError("Value-v1 case set requires 45 pairs")
        if len({pair.pair_id for pair in self.pairs}) != 45:
            raise ContractValidationError("Value-v1 pair IDs must be unique")
        if len({pair.pair_name for pair in self.pairs}) != 45:
            raise ContractValidationError("Value-v1 pair names must be unique")
        if len({pair.left.blueprint_id for pair in self.pairs}) != 45 \
                or len({pair.right.blueprint_id for pair in self.pairs}) != 45:
            raise ContractValidationError("state blueprint IDs must be unique per side")
        counts = Counter((pair.category, pair.split) for pair in self.pairs)
        for category in ValueV1EvaluationCategory:
            if counts[(category, ValueV1EvaluationSplit.DEVELOPMENT)] != 2:
                raise ContractValidationError(
                    f"{category.value} requires two development pairs"
                )
            if counts[(category, ValueV1EvaluationSplit.HOLDOUT)] != 3:
                raise ContractValidationError(
                    f"{category.value} requires three holdout pairs"
                )
        ordered = tuple(sorted(self.pairs, key=lambda item: item.pair_name))
        object.__setattr__(self, "pairs", ordered)
        expected = stable_contract_id(
            VALUE_V1_EVAL_CASE_SET_DIGEST_PREFIX,
            {
                "case_set_id": self.case_set_id,
                "pair_ids": [pair.pair_id for pair in ordered],
            },
        )
        if self.case_set_digest is not None and self.case_set_digest != expected:
            raise ContractValidationError("case-set digest does not match pairs")
        object.__setattr__(self, "case_set_digest", expected)
        return self

    def for_split(
        self, split: ValueV1EvaluationSplit
    ) -> Tuple[ValueV1EvaluationPair, ...]:
        return tuple(pair for pair in self.pairs if pair.split is split)


@dataclass(frozen=True)
class BuiltCanonicalValueV1State:
    session_state: SessionState
    task: Optional[CanonicalTaskSpec]
    commitments: Tuple[CommitmentRecord, ...]
    aporia_records: Tuple[AporiaRecord, ...]
    hybrid_state: HybridEpistemicState
    projected: SearchStateV1


def _add_check(
    hybrid: HybridEpistemicState,
    *,
    claim_id: str,
    token: str,
    counter: int,
    holds: Optional[bool],
    objection_id: Optional[str] = None,
    model_produced: bool = False,
):
    record = verify_task_internal(
        claim_id=claim_id,
        objection_id=objection_id,
        task_text=_QUESTION,
        cited_spans=((_CITATION, 0),),
        condition_tested=f"canonical condition {token} {counter}",
        holds=holds,
        rationale="bounded canonical fixture check",
        verifier_provider_id="model-route" if model_produced else None,
        verifier_model_id="vendor/model" if model_produced else None,
    )
    return hybrid.add_verification(record)


def _source_for_blueprint(blueprint: CanonicalStateBlueprint):
    token = blueprint.blueprint_id
    state = SessionState(
        session_id=f"session-{token}",
        question=_QUESTION,
        phase=(
            DialogPhase.COMPLETE
            if blueprint.terminal is ValueV1TerminalRecipe.BLOCKED
            else DialogPhase.ELENCHUS
        ),
        agent_states={
            _AGENT_ID: AgentState(
                agent_id=_AGENT_ID,
                primary_role=AgentRole.ELENCHUS_CRITIC,
                assigned_role=AgentRole.ELENCHUS_CRITIC,
            )
        },
    )
    task = None
    if state.phase is not DialogPhase.COMPLETE:
        task = CanonicalTaskSpec(
            phase=DialogPhase.ELENCHUS,
            round_number=0,
            slot_index=0,
            agent_id=_AGENT_ID,
            role=AgentRole.ELENCHUS_CRITIC,
            task_kind=TaskKind.ELENCHUS_OBJECTION,
        )

    hybrid = HybridEpistemicState(state.session_id, state.question)
    claim_ids = []
    for claim_index, recipe in enumerate(blueprint.claims):
        claim_id = f"claim-{token}-{claim_index}"
        claim_ids.append(claim_id)
        verification_class = (
            VerificationClass.EXTERNAL_EVIDENCE
            if recipe.external_evidence_required
            else VerificationClass.TASK_INTERNAL
        )
        hybrid.add_claim(
            ClaimRecord(
                claim_id=claim_id,
                text=f"Canonical claim {token} {claim_index}",
                verification_class=verification_class,
            )
        )
        for counter in range(recipe.supporting_evidence_count):
            hybrid.add_evidence(
                EvidenceRecord(
                    evidence_id=f"evidence-{token}-{claim_index}-support-{counter}",
                    claim_id=claim_id,
                    stance=EvidenceStance.SUPPORTING,
                    source_type=EvidenceSourceType.DETERMINISTIC_COMPUTATION,
                    source_identity="canonical-evaluator-fixture",
                    content="Current canonical support record.",
                )
            )
        for counter in range(recipe.weak_evidence_count):
            hybrid.add_evidence(
                EvidenceRecord(
                    evidence_id=f"evidence-{token}-{claim_index}-weak-{counter}",
                    claim_id=claim_id,
                    stance=EvidenceStance.WEAK,
                    source_type=EvidenceSourceType.HUMAN_PROVIDED,
                    source_identity="canonical-operator-fixture",
                    content="Current weak record.",
                )
            )
        for counter in range(recipe.model_assertion_count):
            hybrid.add_evidence(
                EvidenceRecord(
                    evidence_id=f"evidence-{token}-{claim_index}-model-{counter}",
                    claim_id=claim_id,
                    stance=EvidenceStance.SUPPORTING,
                    source_type=EvidenceSourceType.MODEL_ASSERTION,
                    source_identity="model-route",
                    content="Non-authoritative model assertion.",
                )
            )
        for counter in range(recipe.deterministic_verified_count):
            _add_check(
                hybrid,
                claim_id=claim_id,
                token=f"{token}-deterministic",
                counter=counter,
                holds=True,
            )
        for counter in range(recipe.model_verified_count):
            _add_check(
                hybrid,
                claim_id=claim_id,
                token=f"{token}-model",
                counter=counter,
                holds=True,
                model_produced=True,
            )
        for counter in range(recipe.inconclusive_count):
            _add_check(
                hybrid,
                claim_id=claim_id,
                token=f"{token}-inconclusive",
                counter=counter,
                holds=None,
            )
        for counter in range(recipe.falsified_count):
            _add_check(
                hybrid,
                claim_id=claim_id,
                token=f"{token}-falsified",
                counter=counter,
                holds=False,
            )
        if recipe.external_evidence_required:
            hybrid.add_verification(
                external_evidence_required(
                    claim_id, "No canonical external evidence substrate is present."
                )
            )
        for counter in range(recipe.open_objection_count):
            hybrid.add_objection(
                ObjectionRecord(
                    objection_id=f"objection-{token}-{claim_index}-open-{counter}",
                    target_claim_id=claim_id,
                    text="Current canonical objection.",
                )
            )
        for counter in range(recipe.rejected_objection_count):
            objection = hybrid.add_objection(
                ObjectionRecord(
                    objection_id=f"objection-{token}-{claim_index}-rejected-{counter}",
                    target_claim_id=claim_id,
                    text="Canonical objection submitted for checking.",
                )
            )
            hybrid.transition_objection(
                objection.objection_id, ObjectionState.PENDING_VERIFICATION
            )
            check = _add_check(
                hybrid,
                claim_id=claim_id,
                objection_id=objection.objection_id,
                token=f"{token}-rejected-objection",
                counter=counter,
                holds=False,
            )
            hybrid.transition_objection(
                objection.objection_id,
                ObjectionState.REJECTED,
                verification_id=check.verification_id,
            )

    for counter in range(blueprint.unmapped_open_objection_count):
        hybrid.add_objection(
            ObjectionRecord(
                objection_id=f"objection-{token}-unmapped-{counter}",
                target_claim_id=UNMAPPED_TARGET,
                text="Canonical objection with no established claim target.",
                target_provenance=ObjectionTargetProvenance.UNMAPPED,
            )
        )

    contradiction_index = 0
    for kind, count in (
        ("candidate", blueprint.candidate_contradiction_count),
        ("dismissed", blueprint.dismissed_contradiction_count),
        ("validated", blueprint.validated_contradiction_count),
    ):
        for _ in range(count):
            contradiction_id = f"contradiction-{token}-{contradiction_index}"
            contradiction_index += 1
            hybrid.add_contradiction(
                ContradictionRecord(
                    contradiction_id=contradiction_id,
                    claim_id_a=claim_ids[0],
                    claim_id_b=claim_ids[1],
                )
            )
            if kind == "dismissed":
                hybrid.dismiss_contradiction(
                    contradiction_id, "Canonical check dismissed the candidate."
                )
            elif kind == "validated":
                check = _add_check(
                    hybrid,
                    claim_id=claim_ids[0],
                    token=f"{token}-validated-contradiction",
                    counter=contradiction_index,
                    holds=True,
                )
                hybrid.validate_contradiction(
                    contradiction_id, verification_id=check.verification_id
                )

    commitments = []
    aporia_records = []
    if blueprint.aporia_count:
        move_id = f"move-{token}"
        task_id = f"task-{token}"
        state.moves.append(
            AgentMove(
                move_id=move_id,
                task_id=task_id,
                agent_id=_AGENT_ID,
                role=AgentRole.ELENCHUS_CRITIC,
                phase=DialogPhase.INITIAL_RESPONSE,
                content={"commitments": ["Canonical current-state commitment."]},
                task_kind=TaskKind.INITIAL_RESPONSE,
            )
        )
        state.task_log.append(
            TaskLogEntry(
                task_id=task_id,
                move_id=move_id,
                session_id=state.session_id,
                phase=DialogPhase.INITIAL_RESPONSE,
                agent_id=_AGENT_ID,
                assigned_role=AgentRole.ELENCHUS_CRITIC,
                task_kind=TaskKind.INITIAL_RESPONSE,
                provider_status=ProviderStatus.OK,
            )
        )
        for counter in range(blueprint.aporia_count):
            commitment = CommitmentRecord(
                commitment_id=f"commitment-{token}-{counter}",
                source_move_id=move_id,
                cycle=counter,
                claim="Canonical current-state commitment.",
                status=CommitmentStatus.SUSPENDED,
            )
            commitments.append(commitment)
            aporia_records.append(
                AporiaRecord(
                    previous_commitment_id=commitment.commitment_id,
                    conflicting_commitment_id=commitment.commitment_id,
                    resulting_status=CommitmentStatus.SUSPENDED,
                    remaining_question="Which canonical premise remains open?",
                    cycle=counter,
                )
            )

    usage = BudgetUsage(
        nodes=(
            _BUDGET.max_nodes + 1
            if blueprint.terminal is ValueV1TerminalRecipe.BUDGET_EXHAUSTED
            else 1
        )
    )
    return state, task, tuple(commitments), tuple(aporia_records), hybrid, usage


def build_canonical_state(
    blueprint: CanonicalStateBlueprint,
) -> BuiltCanonicalValueV1State:
    """Execute the real canonical source -> projection chain, without Value."""

    state, task, commitments, aporia, hybrid, usage = _source_for_blueprint(
        blueprint
    )
    projected = project_search_state_v1(
        state,
        task,
        budget=_BUDGET,
        budget_usage=usage,
        commitments=commitments,
        aporia_records=aporia,
        hybrid_state=hybrid,
    )
    return BuiltCanonicalValueV1State(
        session_state=state,
        task=task,
        commitments=commitments,
        aporia_records=aporia,
        hybrid_state=hybrid,
        projected=projected,
    )


def _claim(**kwargs) -> CanonicalClaimBlueprint:
    return CanonicalClaimBlueprint(**kwargs)


def _state(
    ordinal: int,
    slot: int,
    *,
    claims: Tuple[CanonicalClaimBlueprint, ...] = (CanonicalClaimBlueprint(),),
    **kwargs,
) -> CanonicalStateBlueprint:
    return CanonicalStateBlueprint(
        blueprint_id=f"canonical-v1-state-{ordinal:03d}-{slot}",
        claims=claims,
        **kwargs,
    )


def _pair(
    ordinal: int,
    category: ValueV1EvaluationCategory,
    category_index: int,
    expectation: ValueV1PairExpectation,
    *,
    left: dict,
    right: dict,
) -> ValueV1EvaluationPair:
    split = (
        ValueV1EvaluationSplit.DEVELOPMENT
        if category_index < 2
        else ValueV1EvaluationSplit.HOLDOUT
    )
    return ValueV1EvaluationPair(
        pair_name=f"canonical-v1-pair-{ordinal:03d}",
        category=category,
        split=split,
        left=_state(ordinal, 0, **left),
        right=_state(ordinal, 1, **right),
        expectation=expectation,
    )


_U = ValueV1EvaluationCategory.USEFUL_SUPPORT_STATE
_I = ValueV1EvaluationCategory.IRRELEVANT_V1_SIGNAL
_C = ValueV1EvaluationCategory.MISLEADING_LIFECYCLE_CLOSURE
_D = ValueV1EvaluationCategory.DUPLICATE_DERIVED_SIGNAL
_T = ValueV1EvaluationCategory.TERMINAL_SUPPORT_ONLY
_M = ValueV1EvaluationCategory.INTERMEDIATE_ASSESSMENT
_E = ValueV1EvaluationCategory.V0_V1_EQUIVALENCE
_R = ValueV1EvaluationCategory.RESOLUTION_REMOVES_PENALTY
_N = ValueV1EvaluationCategory.COUNT_INFLATION
_L = ValueV1PairExpectation.LEFT_BETTER
_B = ValueV1PairExpectation.RIGHT_BETTER
_Q = ValueV1PairExpectation.REQUIRED_TIE


# V1 recovery lineage: frozen after estimator semantics were already committed,
# and before any Value result on these state identities or any holdout run.
_FROZEN_PAIRS = (
    # 1. Canonical support-state distinctions that should help.
    _pair(1, _U, 0, _L, left={"claims": (_claim(supporting_evidence_count=1),)}, right={}),
    _pair(2, _U, 1, _B, left={"claims": (_claim(external_evidence_required=True),)}, right={"claims": (_claim(supporting_evidence_count=1),)}),
    _pair(3, _U, 2, _L, left={"claims": (_claim(deterministic_verified_count=1),)}, right={}),
    _pair(4, _U, 3, _B, left={"claims": (_claim(inconclusive_count=1),)}, right={"claims": (_claim(supporting_evidence_count=1),)}),
    _pair(5, _U, 4, _B, left={"claims": (_claim(falsified_count=1),)}, right={"claims": (_claim(external_evidence_required=True),)}),
    # 2. V1 signals irrelevant to ranking.
    _pair(6, _I, 0, _Q, left={"claims": (_claim(weak_evidence_count=1),)}, right={}),
    _pair(7, _I, 1, _Q, left={"claims": (_claim(), _claim()), "candidate_contradiction_count": 1}, right={"claims": (_claim(), _claim())}),
    _pair(8, _I, 2, _Q, left={"claims": (_claim(model_assertion_count=2),)}, right={}),
    _pair(9, _I, 3, _Q, left={"claims": (_claim(model_verified_count=1),)}, right={}),
    _pair(10, _I, 4, _Q, left={"unmapped_open_objection_count": 1}, right={}),
    # 3. Misleading lifecycle closure.
    _pair(11, _C, 0, _Q, left={"claims": (_claim(), _claim()), "dismissed_contradiction_count": 1}, right={"claims": (_claim(), _claim())}),
    _pair(12, _C, 1, _Q, left={"claims": (_claim(rejected_objection_count=1),)}, right={}),
    _pair(13, _C, 2, _Q, left={"claims": (_claim(supporting_evidence_count=1), _claim()), "dismissed_contradiction_count": 1}, right={"claims": (_claim(supporting_evidence_count=1), _claim())}),
    _pair(14, _C, 3, _Q, left={"claims": (_claim(supporting_evidence_count=1, rejected_objection_count=1),)}, right={"claims": (_claim(supporting_evidence_count=1),)}),
    _pair(15, _C, 4, _Q, left={"claims": (_claim(rejected_objection_count=3),)}, right={}),
    # 4. Duplicate or derived representations of one governing state.
    _pair(16, _D, 0, _Q, left={"claims": (_claim(supporting_evidence_count=1),)}, right={"claims": (_claim(supporting_evidence_count=3),)}),
    _pair(17, _D, 1, _Q, left={"claims": (_claim(supporting_evidence_count=1),)}, right={"claims": (_claim(supporting_evidence_count=1, deterministic_verified_count=1),)}),
    _pair(18, _D, 2, _Q, left={"claims": (_claim(deterministic_verified_count=1),)}, right={"claims": (_claim(deterministic_verified_count=3),)}),
    _pair(19, _D, 3, _Q, left={"claims": (_claim(open_objection_count=1),)}, right={"claims": (_claim(open_objection_count=3),)}),
    _pair(20, _D, 4, _Q, left={"claims": (_claim(), _claim()), "validated_contradiction_count": 1}, right={"claims": (_claim(supporting_evidence_count=2), _claim()), "validated_contradiction_count": 1}),
    # 5. Terminal support is a firewall control, never a ranking shortcut.
    _pair(21, _T, 0, _Q, left={"claims": (_claim(supporting_evidence_count=1),), "terminal": ValueV1TerminalRecipe.BLOCKED}, right={"terminal": ValueV1TerminalRecipe.BLOCKED}),
    _pair(22, _T, 1, _Q, left={"claims": (_claim(supporting_evidence_count=1),), "terminal": ValueV1TerminalRecipe.BUDGET_EXHAUSTED}, right={"claims": (_claim(external_evidence_required=True),), "terminal": ValueV1TerminalRecipe.BUDGET_EXHAUSTED}),
    _pair(23, _T, 2, _Q, left={"claims": (_claim(falsified_count=1),), "terminal": ValueV1TerminalRecipe.BLOCKED}, right={"claims": (_claim(supporting_evidence_count=1),), "terminal": ValueV1TerminalRecipe.BLOCKED}),
    _pair(24, _T, 3, _Q, left={"claims": (_claim(open_objection_count=1),), "terminal": ValueV1TerminalRecipe.BLOCKED}, right={"terminal": ValueV1TerminalRecipe.BLOCKED}),
    _pair(25, _T, 4, _Q, left={"claims": (_claim(inconclusive_count=1),), "terminal": ValueV1TerminalRecipe.BUDGET_EXHAUSTED}, right={"claims": (_claim(supporting_evidence_count=1),), "terminal": ValueV1TerminalRecipe.BUDGET_EXHAUSTED}),
    # 6. Intermediate verification and governing-assessment states.
    _pair(26, _M, 0, _L, left={"claims": (_claim(supporting_evidence_count=1),)}, right={}),
    _pair(27, _M, 1, _B, left={"claims": (_claim(external_evidence_required=True),)}, right={"claims": (_claim(supporting_evidence_count=1),)}),
    _pair(28, _M, 2, _B, left={"claims": (_claim(open_objection_count=1),)}, right={}),
    _pair(29, _M, 3, _B, left={"claims": (_claim(falsified_count=1),)}, right={"claims": (_claim(inconclusive_count=1),)}),
    _pair(30, _M, 4, _B, left={"claims": (_claim(external_evidence_required=True),)}, right={}),
    # 7. States where v0 and v1 should remain equivalent.
    _pair(31, _E, 0, _Q, left={}, right={}),
    _pair(32, _E, 1, _Q, left={"claims": (_claim(supporting_evidence_count=1),)}, right={"claims": (_claim(deterministic_verified_count=1),)}),
    _pair(33, _E, 2, _Q, left={"claims": (_claim(model_verified_count=2),)}, right={"claims": (_claim(model_verified_count=1),)}),
    _pair(34, _E, 3, _Q, left={"claims": (_claim(supporting_evidence_count=1), _claim(supporting_evidence_count=1))}, right={"claims": (_claim(supporting_evidence_count=1),)}),
    _pair(35, _E, 4, _Q, left={"aporia_count": 1}, right={"aporia_count": 1}),
    # 8. Resolution may remove a penalty but may never create a bonus.
    _pair(36, _R, 0, _B, left={"claims": (_claim(open_objection_count=1),)}, right={"claims": (_claim(rejected_objection_count=1),)}),
    _pair(37, _R, 1, _Q, left={}, right={"claims": (_claim(rejected_objection_count=1),)}),
    _pair(38, _R, 2, _B, left={"claims": (_claim(open_objection_count=1),)}, right={"claims": (_claim(rejected_objection_count=1),)}),
    _pair(39, _R, 3, _Q, left={}, right={"claims": (_claim(rejected_objection_count=2),)}),
    _pair(40, _R, 4, _Q, left={"claims": (_claim(), _claim())}, right={"claims": (_claim(), _claim()), "dismissed_contradiction_count": 1}),
    # 9. Evidence, verification, claim, and lifecycle count inflation.
    _pair(41, _N, 0, _Q, left={"claims": (_claim(supporting_evidence_count=1),)}, right={"claims": (_claim(supporting_evidence_count=4),)}),
    _pair(42, _N, 1, _Q, left={"claims": (_claim(supporting_evidence_count=1),)}, right={"claims": (_claim(supporting_evidence_count=1), _claim(supporting_evidence_count=1), _claim(supporting_evidence_count=1))}),
    _pair(43, _N, 2, _Q, left={"claims": (_claim(open_objection_count=1),)}, right={"claims": (_claim(open_objection_count=4),)}),
    _pair(44, _N, 3, _Q, left={}, right={"claims": (_claim(), _claim(supporting_evidence_count=1), _claim(supporting_evidence_count=1), _claim(supporting_evidence_count=1))}),
    _pair(45, _N, 4, _Q, left={"claims": (_claim(deterministic_verified_count=1),)}, right={"claims": (_claim(deterministic_verified_count=4),)}),
)


FROZEN_VALUE_V1_EVALUATION_CASE_SET = ValueV1EvaluationCaseSet(
    pairs=_FROZEN_PAIRS
)


def frozen_case_set_canonical_json() -> str:
    """Canonical serialization used for the pre-result freeze digest."""

    return canonical_json(
        FROZEN_VALUE_V1_EVALUATION_CASE_SET.model_dump(mode="json")
    )


__all__ = [
    "BuiltCanonicalValueV1State",
    "CanonicalClaimBlueprint",
    "CanonicalStateBlueprint",
    "FROZEN_VALUE_V1_EVALUATION_CASE_SET",
    "VALUE_V1_EVAL_CASE_SET_VERSION",
    "VALUE_V1_EVAL_HARNESS_VERSION",
    "VALUE_V1_HOLDOUT_IMPROVEMENT_THRESHOLD",
    "VALUE_V1_HOLDOUT_ORDERED_ACCURACY_THRESHOLD",
    "VALUE_V1_NONTERMINAL_IMPROVEMENT_THRESHOLD",
    "VALUE_V1_NONTERMINAL_ORDERED_ACCURACY_THRESHOLD",
    "VALUE_V1_REQUIRED_TIE_ACCURACY_THRESHOLD",
    "VALUE_V1_SECONDARY_IMPROVEMENT_THRESHOLD",
    "ValueV1EvaluationCaseSet",
    "ValueV1EvaluationCategory",
    "ValueV1EvaluationPair",
    "ValueV1EvaluationSplit",
    "ValueV1PairExpectation",
    "ValueV1StatePairView",
    "ValueV1TerminalRecipe",
    "build_canonical_state",
    "frozen_case_set_canonical_json",
]
