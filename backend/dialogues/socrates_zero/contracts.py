"""Runtime-inert SocratesZero search contracts.

This module defines data and interface boundaries only.  It imports no CED
orchestrator, provider, tool, neural runtime, or legacy epistemic graph.  Search
is advisory: an implementation may choose only from a CED-supplied hard legal
set and the CED must validate the chosen action again before execution.

The contracts intentionally retain audit references separately from semantic
identity.  Random task/session ids, parent ids, timestamps, latency, provider
route ids, and response ids therefore cannot change ``SearchState.state_id``.
Exact known model identity and immutable observation digests do change it.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import (
    ClassVar,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
    runtime_checkable,
)

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SEARCH_CONTRACT_SCHEMA_VERSION = "socrates.zero.search-contracts/v0"

JsonScalar = Union[str, int, float, bool, None]


def canonical_json(value: object) -> str:
    """Canonical JSON used only for deterministic contract identity."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def stable_contract_id(prefix: str, value: object) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest}"


class ContractValidationError(ValueError):
    """A search contract would weaken deterministic protocol validation."""


class BudgetExceeded(ContractValidationError):
    """A proposed usage exceeds at least one hard search limit."""

    def __init__(self, violations: Sequence[str]) -> None:
        self.violations = tuple(violations)
        super().__init__("search budget exceeded: " + ", ".join(self.violations))


class _FrozenContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


class TerminalStatus(str, Enum):
    NON_TERMINAL = "non_terminal"
    ANSWER_READY = "answer_ready"
    ABSTAINED = "abstained"
    BLOCKED = "blocked"
    BUDGET_EXHAUSTED = "budget_exhausted"


class SearchTerminationReason(str, Enum):
    COMPLETED = "completed"
    TERMINAL_STATE = "terminal_state"
    NO_LEGAL_ACTIONS = "no_legal_actions"
    BUDGET_EXHAUSTED = "budget_exhausted"
    BASELINE_SELECTED = "baseline_selected"
    FAILED_CLOSED = "failed_closed"


class ActionKind(str, Enum):
    ASK_SOCRATIC_QUESTION = "ask_socratic_question"
    RUN_ELENCHUS = "run_elenchus"
    REFLECT = "reflect"
    RECONSTRUCT = "reconstruct"
    RATIFY = "ratify"
    DEFINE_TERM = "define_term"
    PROPOSE_CLAIM = "propose_claim"
    CHALLENGE_CLAIM = "challenge_claim"
    FALSIFY_CLAIM = "falsify_claim"
    DEFEND_CLAIM = "defend_claim"
    REQUEST_PRIMARY_SOURCE = "request_primary_source"
    REQUEST_INDEPENDENT_SOURCE = "request_independent_source"
    SEEK_EVIDENCE = "seek_evidence"
    VERIFY_EVIDENCE = "verify_evidence"
    VERIFY_CLAIM = "verify_claim"
    VERIFY_CALCULATION = "verify_calculation"
    RECALCULATE = "recalculate"
    GENERATE_COUNTEREXAMPLE = "generate_counterexample"
    EXPLORE_ALTERNATIVE_HYPOTHESIS = "explore_alternative_hypothesis"
    INVESTIGATE_CONTRADICTION = "investigate_contradiction"
    RESOLVE_CONTRADICTION = "resolve_contradiction"
    CHECK_SOURCE_INDEPENDENCE = "check_source_independence"
    CHECK_TEMPORAL_VALIDITY = "check_temporal_validity"
    CALL_INDEPENDENT_PEER = "call_independent_peer"
    REQUEST_SPECIALIST = "request_specialist"
    SYNTHESIZE_PARTIAL = "synthesize_partial"
    SYNTHESIZE_FINAL = "synthesize_final"
    ABSTAIN = "abstain"
    STOP = "stop"


class ActionTargetKind(str, Enum):
    CLAIM = "claim"
    EVIDENCE = "evidence"
    CONTRADICTION = "contradiction"
    UNRESOLVED_QUESTION = "unresolved_question"
    HYPOTHESIS = "hypothesis"
    CANDIDATE_ANSWER = "candidate_answer"


class SemanticArtifactRef(_FrozenContract):
    """Immutable reference to content held by a governing repository contract."""

    artifact_id: str
    semantic_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    _artifact_id_nonblank = field_validator("artifact_id")(_nonblank)

    def identity_payload(self) -> Dict[str, str]:
        return {"artifact_id": self.artifact_id, "digest": self.semantic_digest}


class ObservationRef(_FrozenContract):
    """Observed result with audit metadata separated from semantic identity.

    ``record_id`` and ``provider_id`` can be volatile process identifiers and
    are excluded from state identity.  The content digest and exact actual
    model identity are included.  Unknown model identity remains ``None`` and
    contributes no false source independence.
    """

    record_id: str
    semantic_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_id: Optional[str] = None
    model_id: Optional[str] = None

    _record_id_nonblank = field_validator("record_id")(_nonblank)

    def identity_payload(self) -> Dict[str, Optional[str]]:
        return {"digest": self.semantic_digest, "model_id": self.model_id}


class RoleHistoryRef(_FrozenContract):
    phase: str
    round_index: int = Field(ge=0)
    agent_id: str
    role: str

    _nonblank_fields = field_validator("phase", "agent_id", "role")(_nonblank)


class MoveHistoryRef(_FrozenContract):
    """Relevant accepted-move identity; random task IDs are deliberately absent."""

    move_id: str
    semantic_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    phase: str
    round_index: int = Field(ge=0)
    agent_id: str
    role: str
    task_kind: Optional[str] = None
    slot_index: int = Field(default=0, ge=0)
    attempt_index: int = Field(default=0, ge=0)

    _nonblank_fields = field_validator(
        "move_id", "phase", "agent_id", "role"
    )(_nonblank)


class PolicyContextEntry(_FrozenContract):
    """Versioned policy input represented by an immutable semantic digest."""

    name: str
    semantic_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    _name_nonblank = field_validator("name")(_nonblank)


class BudgetUsage(_FrozenContract):
    """Monotone counters. Cost is integer micro-USD; time is milliseconds."""

    nodes: int = Field(default=0, ge=0)
    expansions: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    cost_microusd: int = Field(default=0, ge=0)
    wall_time_ms: int = Field(default=0, ge=0)
    max_depth_observed: int = Field(default=0, ge=0)

    def plus(self, delta: "BudgetUsage") -> "BudgetUsage":
        """Return a new usage snapshot; never mutate or decrement counters."""
        return BudgetUsage(
            nodes=self.nodes + delta.nodes,
            expansions=self.expansions + delta.expansions,
            model_calls=self.model_calls + delta.model_calls,
            tool_calls=self.tool_calls + delta.tool_calls,
            tokens=self.tokens + delta.tokens,
            cost_microusd=self.cost_microusd + delta.cost_microusd,
            wall_time_ms=self.wall_time_ms + delta.wall_time_ms,
            max_depth_observed=max(
                self.max_depth_observed, delta.max_depth_observed
            ),
        )


class SearchBudget(_FrozenContract):
    """Hard deterministic ceilings owned by CED/infrastructure, not policy."""

    max_nodes: int = Field(ge=1)
    max_expansions: int = Field(ge=0)
    max_model_calls: int = Field(ge=0)
    max_tool_calls: int = Field(ge=0)
    max_tokens: int = Field(ge=0)
    max_cost_microusd: int = Field(ge=0)
    max_wall_time_ms: int = Field(ge=0)
    max_depth: int = Field(ge=0)

    _LIMITS: ClassVar[Tuple[Tuple[str, str], ...]] = (
        ("nodes", "max_nodes"),
        ("expansions", "max_expansions"),
        ("model_calls", "max_model_calls"),
        ("tool_calls", "max_tool_calls"),
        ("tokens", "max_tokens"),
        ("cost_microusd", "max_cost_microusd"),
        ("wall_time_ms", "max_wall_time_ms"),
        ("max_depth_observed", "max_depth"),
    )

    def violations(self, usage: BudgetUsage) -> Tuple[str, ...]:
        violations: List[str] = []
        for usage_name, limit_name in self._LIMITS:
            actual = getattr(usage, usage_name)
            limit = getattr(self, limit_name)
            if actual > limit:
                violations.append(f"{usage_name}={actual}>{limit_name}={limit}")
        return tuple(violations)

    def allows(self, usage: BudgetUsage) -> bool:
        return not self.violations(usage)

    def enforce(self, usage: BudgetUsage) -> None:
        violations = self.violations(usage)
        if violations:
            raise BudgetExceeded(violations)


class SearchState(_FrozenContract):
    """Conservative immutable projection of CED/Hybrid public state.

    Collections of artifacts are canonical sets. Role and move histories are
    ordered protocol history. No text-similarity equivalence or lossy merge is
    performed.
    """

    schema_version: Literal[
        SEARCH_CONTRACT_SCHEMA_VERSION
    ] = SEARCH_CONTRACT_SCHEMA_VERSION
    state_id: Optional[str] = None

    # Audit/navigation only; excluded from semantic identity.
    parent_state_id: Optional[str] = None
    session_id: Optional[str] = None
    task_id: Optional[str] = None

    task_kind: str
    question: str
    phase: str
    round_number: int = Field(default=0, ge=0)
    active_agent_id: Optional[str] = None
    active_role: Optional[str] = None
    active_slot_index: int = Field(default=0, ge=0)
    active_attempt_index: int = Field(default=0, ge=0)

    active_claims: Tuple[SemanticArtifactRef, ...] = ()
    evidence: Tuple[SemanticArtifactRef, ...] = ()
    contradictions: Tuple[SemanticArtifactRef, ...] = ()
    unresolved_questions: Tuple[SemanticArtifactRef, ...] = ()
    candidate_hypotheses: Tuple[SemanticArtifactRef, ...] = ()
    candidate_answers: Tuple[SemanticArtifactRef, ...] = ()

    role_history: Tuple[RoleHistoryRef, ...] = ()
    move_history: Tuple[MoveHistoryRef, ...] = ()
    provider_receipts: Tuple[ObservationRef, ...] = ()
    verification_results: Tuple[ObservationRef, ...] = ()
    epistemic_graph_ref: Optional[SemanticArtifactRef] = None
    policy_context: Tuple[PolicyContextEntry, ...] = ()

    budget: SearchBudget
    budget_usage: BudgetUsage
    depth: int = Field(default=0, ge=0)
    terminal_status: TerminalStatus = TerminalStatus.NON_TERMINAL

    _ARTIFACT_FIELDS: ClassVar[Tuple[str, ...]] = (
        "active_claims",
        "evidence",
        "contradictions",
        "unresolved_questions",
        "candidate_hypotheses",
        "candidate_answers",
    )
    _OBSERVATION_FIELDS: ClassVar[Tuple[str, ...]] = (
        "provider_receipts",
        "verification_results",
    )

    _nonblank_fields = field_validator("task_kind", "question", "phase")(_nonblank)

    @staticmethod
    def _canonical_artifacts(
        values: Iterable[SemanticArtifactRef], field_name: str
    ) -> Tuple[SemanticArtifactRef, ...]:
        ordered = tuple(sorted(values, key=lambda item: item.artifact_id))
        seen: Dict[str, str] = {}
        for item in ordered:
            previous = seen.get(item.artifact_id)
            if previous is not None:
                detail = "conflicting digest" if previous != item.semantic_digest else "duplicate"
                raise ContractValidationError(
                    f"{field_name} contains {detail} for {item.artifact_id}"
                )
            seen[item.artifact_id] = item.semantic_digest
        return ordered

    @staticmethod
    def _canonical_observations(
        values: Iterable[ObservationRef], field_name: str
    ) -> Tuple[ObservationRef, ...]:
        ordered = tuple(
            sorted(
                values,
                key=lambda item: (
                    item.semantic_digest,
                    item.model_id or "",
                    item.record_id,
                ),
            )
        )
        seen: Dict[str, Tuple[str, Optional[str]]] = {}
        for item in ordered:
            content = (item.semantic_digest, item.model_id)
            previous = seen.get(item.record_id)
            if previous is not None:
                detail = "conflicting content" if previous != content else "duplicate"
                raise ContractValidationError(
                    f"{field_name} contains {detail} for {item.record_id}"
                )
            seen[item.record_id] = content
        return ordered

    @model_validator(mode="after")
    def canonicalize_and_identify(self) -> "SearchState":
        if (self.active_agent_id is None) != (self.active_role is None):
            raise ContractValidationError(
                "active_agent_id and active_role must both be present or absent"
            )
        if self.active_agent_id is not None:
            _nonblank(self.active_agent_id)
            _nonblank(self.active_role or "")
        for field_name in self._ARTIFACT_FIELDS:
            canonical = self._canonical_artifacts(getattr(self, field_name), field_name)
            object.__setattr__(self, field_name, canonical)
        for field_name in self._OBSERVATION_FIELDS:
            canonical = self._canonical_observations(
                getattr(self, field_name), field_name
            )
            object.__setattr__(self, field_name, canonical)

        context = tuple(sorted(self.policy_context, key=lambda item: item.name))
        if len({item.name for item in context}) != len(context):
            raise ContractValidationError("policy_context names must be unique")
        object.__setattr__(self, "policy_context", context)

        if self.budget_usage.max_depth_observed < self.depth:
            raise ContractValidationError(
                "max_depth_observed cannot be less than the current state depth"
            )
        violations = self.budget.violations(self.budget_usage)
        if violations and self.terminal_status is not TerminalStatus.BUDGET_EXHAUSTED:
            raise ContractValidationError(
                "an over-budget state must be terminal_status=budget_exhausted"
            )

        expected = stable_contract_id("szstate", self.identity_payload())
        if self.state_id is not None and self.state_id != expected:
            raise ContractValidationError("state_id does not match semantic content")
        object.__setattr__(self, "state_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        artifacts = {
            name: [item.identity_payload() for item in getattr(self, name)]
            for name in self._ARTIFACT_FIELDS
        }
        observations = {
            name: [item.identity_payload() for item in getattr(self, name)]
            for name in self._OBSERVATION_FIELDS
        }
        return {
            "schema_version": self.schema_version,
            "task_kind": self.task_kind,
            "question": self.question,
            "phase": self.phase,
            "round_number": self.round_number,
            "active_agent_id": self.active_agent_id,
            "active_role": self.active_role,
            "active_slot_index": self.active_slot_index,
            "active_attempt_index": self.active_attempt_index,
            **artifacts,
            "role_history": [item.model_dump(mode="json") for item in self.role_history],
            "move_history": [item.model_dump(mode="json") for item in self.move_history],
            **observations,
            "epistemic_graph": (
                self.epistemic_graph_ref.identity_payload()
                if self.epistemic_graph_ref is not None
                else None
            ),
            "policy_context": [
                item.model_dump(mode="json") for item in self.policy_context
            ],
            "budget": self.budget.model_dump(mode="json"),
            "budget_usage": self.budget_usage.model_dump(mode="json"),
            "depth": self.depth,
            "terminal_status": self.terminal_status.value,
        }

    def target_ids(self, kind: ActionTargetKind) -> Tuple[str, ...]:
        field_by_kind = {
            ActionTargetKind.CLAIM: "active_claims",
            ActionTargetKind.EVIDENCE: "evidence",
            ActionTargetKind.CONTRADICTION: "contradictions",
            ActionTargetKind.UNRESOLVED_QUESTION: "unresolved_questions",
            ActionTargetKind.HYPOTHESIS: "candidate_hypotheses",
            ActionTargetKind.CANDIDATE_ANSWER: "candidate_answers",
        }
        return tuple(
            item.artifact_id for item in getattr(self, field_by_kind[kind])
        )


class ActionParameter(_FrozenContract):
    name: str
    value: JsonScalar

    _name_nonblank = field_validator("name")(_nonblank)

    @field_validator("value")
    @classmethod
    def finite_number(cls, value: JsonScalar) -> JsonScalar:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric action parameters must be finite")
        return value


class LegalAction(_FrozenContract):
    """Typed macro-action. It is a proposal, never an observation or evidence."""

    schema_version: Literal[
        SEARCH_CONTRACT_SCHEMA_VERSION
    ] = SEARCH_CONTRACT_SCHEMA_VERSION
    action_id: Optional[str] = None
    kind: ActionKind
    target_kind: Optional[ActionTargetKind] = None
    target_id: Optional[str] = None
    parameters: Tuple[ActionParameter, ...] = ()
    required_capabilities: Tuple[str, ...] = ()

    _REQUIRED_TARGET: ClassVar[Dict[ActionKind, ActionTargetKind]] = {
        ActionKind.CHALLENGE_CLAIM: ActionTargetKind.CLAIM,
        ActionKind.FALSIFY_CLAIM: ActionTargetKind.CLAIM,
        ActionKind.DEFEND_CLAIM: ActionTargetKind.CLAIM,
        ActionKind.VERIFY_CLAIM: ActionTargetKind.CLAIM,
        ActionKind.GENERATE_COUNTEREXAMPLE: ActionTargetKind.CLAIM,
        ActionKind.VERIFY_EVIDENCE: ActionTargetKind.EVIDENCE,
        ActionKind.CHECK_SOURCE_INDEPENDENCE: ActionTargetKind.EVIDENCE,
        ActionKind.CHECK_TEMPORAL_VALIDITY: ActionTargetKind.EVIDENCE,
        ActionKind.INVESTIGATE_CONTRADICTION: ActionTargetKind.CONTRADICTION,
        ActionKind.RESOLVE_CONTRADICTION: ActionTargetKind.CONTRADICTION,
    }

    @model_validator(mode="after")
    def validate_shape_and_identify(self) -> "LegalAction":
        if (self.target_kind is None) != (self.target_id is None):
            raise ContractValidationError(
                "target_kind and target_id must either both be present or both be absent"
            )
        if self.target_id is not None and not self.target_id.strip():
            raise ContractValidationError("target_id must not be blank")

        required = self._REQUIRED_TARGET.get(self.kind)
        if required is not None and self.target_kind is not required:
            raise ContractValidationError(
                f"{self.kind.value} requires a {required.value} target"
            )
        if self.kind in (ActionKind.STOP, ActionKind.ABSTAIN) and self.target_id is not None:
            raise ContractValidationError(f"{self.kind.value} cannot have a target")

        parameters = tuple(sorted(self.parameters, key=lambda item: item.name))
        if len({item.name for item in parameters}) != len(parameters):
            raise ContractValidationError("action parameter names must be unique")
        capabilities = tuple(sorted(set(self.required_capabilities)))
        if any(not value.strip() for value in capabilities):
            raise ContractValidationError("required capabilities must not be blank")
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "required_capabilities", capabilities)

        expected = stable_contract_id("szaction", self.identity_payload())
        if self.action_id is not None and self.action_id != expected:
            raise ContractValidationError("action_id does not match action content")
        object.__setattr__(self, "action_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind.value,
            "target_kind": self.target_kind.value if self.target_kind else None,
            "target_id": self.target_id,
            "parameters": [item.model_dump(mode="json") for item in self.parameters],
            "required_capabilities": list(self.required_capabilities),
        }


def validate_action_references(state: SearchState, action: LegalAction) -> None:
    """Fail closed if an action targets an artifact absent from the snapshot."""
    if action.target_kind is None:
        return
    if action.target_id not in state.target_ids(action.target_kind):
        raise ContractValidationError(
            f"unknown {action.target_kind.value} target {action.target_id!r}"
        )


class ActionPrior(_FrozenContract):
    action_id: str
    probability: float = Field(ge=0.0, le=1.0)

    _action_id_nonblank = field_validator("action_id")(_nonblank)


class ActionStatistics(_FrozenContract):
    action_id: str
    prior: float = Field(ge=0.0, le=1.0)
    visit_count: int = Field(ge=0)
    mean_value: float = Field(ge=-1.0, le=1.0)

    _action_id_nonblank = field_validator("action_id")(_nonblank)


class ActionSuccessor(_FrozenContract):
    """One action-linked successor plus its exact branch-local usage delta.

    The state remains only an experimental observation supplied by an injected
    evaluator.  This record does not execute the action or make the successor
    governing CED state. Additive counters in ``usage_delta`` are local to this
    branch; ``max_depth_observed`` is the absolute depth reached, matching
    ``BudgetUsage.plus`` semantics.
    """

    action_id: str
    state: SearchState
    usage_delta: BudgetUsage

    _action_id_nonblank = field_validator("action_id")(_nonblank)


class SearchReceipt(_FrozenContract):
    """Audit receipt containing bounded public facts, never hidden reasoning."""

    schema_version: Literal[
        SEARCH_CONTRACT_SCHEMA_VERSION
    ] = SEARCH_CONTRACT_SCHEMA_VERSION
    receipt_id: Optional[str] = None
    strategy_name: str
    strategy_version: str
    initial_state_id: str
    final_state_id: Optional[str] = None
    selected_action_id: Optional[str] = None
    visited_state_ids: Tuple[str, ...] = ()
    expanded_action_ids: Tuple[str, ...] = ()
    provider_receipt_ids: Tuple[str, ...] = ()
    verification_result_ids: Tuple[str, ...] = ()
    budget: SearchBudget
    usage: BudgetUsage
    budget_violations: Tuple[str, ...] = ()
    termination_reason: SearchTerminationReason
    deterministic_seed: Optional[int] = Field(default=None, ge=0)

    _nonblank_fields = field_validator(
        "strategy_name", "strategy_version", "initial_state_id"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "SearchReceipt":
        expected_violations = self.budget.violations(self.usage)
        supplied = tuple(sorted(set(self.budget_violations)))
        if supplied and supplied != tuple(sorted(expected_violations)):
            raise ContractValidationError(
                "budget_violations do not match measured usage"
            )
        object.__setattr__(self, "budget_violations", expected_violations)

        if expected_violations and self.termination_reason not in (
            SearchTerminationReason.BUDGET_EXHAUSTED,
            SearchTerminationReason.FAILED_CLOSED,
        ):
            raise ContractValidationError(
                "an over-budget receipt must terminate budget_exhausted or failed_closed"
            )

        expected = stable_contract_id("szreceipt", self.identity_payload())
        if self.receipt_id is not None and self.receipt_id != expected:
            raise ContractValidationError("receipt_id does not match receipt content")
        object.__setattr__(self, "receipt_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "initial_state_id": self.initial_state_id,
            "final_state_id": self.final_state_id,
            "selected_action_id": self.selected_action_id,
            "visited_state_ids": list(self.visited_state_ids),
            "expanded_action_ids": list(self.expanded_action_ids),
            "provider_receipt_ids": list(self.provider_receipt_ids),
            "verification_result_ids": list(self.verification_result_ids),
            "budget": self.budget.model_dump(mode="json"),
            "usage": self.usage.model_dump(mode="json"),
            "budget_violations": list(self.budget_violations),
            "termination_reason": self.termination_reason.value,
            "deterministic_seed": self.deterministic_seed,
        }


class SearchResult(_FrozenContract):
    initial_state_id: str
    final_state_id: Optional[str] = None
    selected_action: Optional[LegalAction] = None
    estimated_value: float = Field(ge=-1.0, le=1.0)
    action_statistics: Tuple[ActionStatistics, ...] = ()
    receipt: SearchReceipt

    _initial_state_nonblank = field_validator("initial_state_id")(_nonblank)

    @model_validator(mode="after")
    def validate_receipt_links(self) -> "SearchResult":
        if self.receipt.initial_state_id != self.initial_state_id:
            raise ContractValidationError("result and receipt initial states differ")
        if self.receipt.final_state_id != self.final_state_id:
            raise ContractValidationError("result and receipt final states differ")
        selected_id = self.selected_action.action_id if self.selected_action else None
        if self.receipt.selected_action_id != selected_id:
            raise ContractValidationError("result and receipt selected actions differ")

        stats = tuple(sorted(self.action_statistics, key=lambda item: item.action_id))
        if len({item.action_id for item in stats}) != len(stats):
            raise ContractValidationError("action statistics IDs must be unique")
        object.__setattr__(self, "action_statistics", stats)
        return self


@runtime_checkable
class SearchConstitution(Protocol):
    """Hard legal-action owner. Policy and search have no override."""

    def legal_actions(self, state: SearchState) -> Tuple[LegalAction, ...]: ...

    def validate_action(self, state: SearchState, action: LegalAction) -> None: ...


@runtime_checkable
class ActionGenerator(Protocol):
    async def generate(
        self,
        state: SearchState,
        *,
        hard_legal_actions: Sequence[LegalAction],
        limit: int,
    ) -> Tuple[LegalAction, ...]: ...


@runtime_checkable
class SuccessorStateEvaluator(Protocol):
    """Injected experimental transition seam with no production authority.

    ``aggregate_usage`` is the compute already consumed across sibling
    candidates, so an implementation can reserve resources before evaluating
    the next branch.
    """

    async def evaluate_successor(
        self,
        state: SearchState,
        action: LegalAction,
        *,
        budget: SearchBudget,
        aggregate_usage: BudgetUsage,
    ) -> ActionSuccessor: ...


@runtime_checkable
class PolicyPrior(Protocol):
    async def priors(
        self, state: SearchState, legal_actions: Sequence[LegalAction]
    ) -> Tuple[ActionPrior, ...]: ...


@runtime_checkable
class ValueEstimator(Protocol):
    async def estimate(self, state: SearchState) -> float: ...


@runtime_checkable
class SearchStrategy(Protocol):
    name: str
    version: str

    async def search(
        self,
        initial_state: SearchState,
        *,
        constitution: SearchConstitution,
        action_generator: ActionGenerator,
        policy_prior: PolicyPrior,
        value_estimator: ValueEstimator,
        budget: SearchBudget,
    ) -> SearchResult: ...


__all__ = [
    "SEARCH_CONTRACT_SCHEMA_VERSION",
    "ActionGenerator",
    "ActionKind",
    "ActionParameter",
    "ActionPrior",
    "ActionStatistics",
    "ActionSuccessor",
    "ActionTargetKind",
    "BudgetExceeded",
    "BudgetUsage",
    "ContractValidationError",
    "LegalAction",
    "MoveHistoryRef",
    "ObservationRef",
    "PolicyContextEntry",
    "PolicyPrior",
    "RoleHistoryRef",
    "SearchBudget",
    "SearchConstitution",
    "SearchReceipt",
    "SearchResult",
    "SearchState",
    "SearchStrategy",
    "SearchTerminationReason",
    "SemanticArtifactRef",
    "SuccessorStateEvaluator",
    "TerminalStatus",
    "ValueEstimator",
    "canonical_json",
    "stable_contract_id",
    "validate_action_references",
]
