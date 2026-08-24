"""Bounded deterministic one-real-ply PUCT for SocratesZero research.

PUCT v0 allocates repeated, serial successor observations across the complete
CED-owned hard-legal root edge set.  Every visit is backed by a fresh call to
the injected experimental successor evaluator; cached Values never create
compute-free pseudo-visits.  The current successor protocol does not establish
safe recursive transition semantics, so v0 never evaluates from a child state.

The selected action is advisory and runtime-inert.  This module imports no CED
orchestrator, provider, tool, neural runtime, or production execution path.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from numbers import Real
from typing import Dict, Iterable, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import (
    ActionKind,
    ActionPrior,
    ActionStatistics,
    ActionSuccessor,
    BudgetUsage,
    ContractValidationError,
    LegalAction,
    SearchBudget,
    SearchConstitution,
    SearchReceipt,
    SearchResult,
    SearchState,
    SearchTerminationReason,
    TerminalStatus,
    stable_contract_id,
)
from .strategy import _actions, _root_value, _validated_priors, _validated_state


PUCT_STRATEGY_VERSION = "puct-strategy/v0"
PUCT_CONFIG_VERSION = "puct-config/v0"
PUCT_AUDIT_VERSION = "puct-search-receipt/v0"
PUCT_DEFAULT_C = 1.0
PUCT_MAX_C = 100.0
PUCT_MAX_SAFE_RELATIVE_DEPTH_V0 = 1

PUCT_SELECTION_TIE_BREAK = (
    "puct_score_desc",
    "policy_prior_desc",
    "action_id_asc",
)
PUCT_ROOT_TIE_BREAK = (
    "visit_count_desc",
    "mean_q_desc",
    "policy_prior_desc",
    "action_id_asc",
)


class _FrozenPUCTContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


def _finite_unit_value(value: float, *, owner: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ContractValidationError(f"{owner} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ContractValidationError(f"{owner} must be finite")
    if numeric < -1.0 or numeric > 1.0:
        raise ContractValidationError(f"{owner} must be inside [-1,+1]")
    return numeric


def _mean(values: Iterable[float]) -> float:
    items = tuple(values)
    return math.fsum(items) / len(items) if items else 0.0


def _component_id(component: object) -> str:
    """Return a bounded deterministic dependency identity for the audit.

    Canonical Policy/Value implementations expose name and version.  Test or
    research fixtures that implement only the Protocol retain a stable source
    identity based on their type; that fallback is not promoted to a canonical
    semantic version.
    """

    name = getattr(component, "name", None)
    version = getattr(component, "version", None)
    if (
        isinstance(name, str)
        and name.strip()
        and isinstance(version, str)
        and version.strip()
    ):
        return f"{name}@{version}"
    cls = component.__class__
    return f"{cls.__module__}.{cls.__qualname__}"


class PUCTConfig(_FrozenPUCTContract):
    """Immutable v0 search math configuration.

    The finite ``(0, 100]`` interval prevents disabled exploration and absurd
    floating-point scale.  The canonical default is intentionally untuned.
    """

    schema_version: Literal[PUCT_CONFIG_VERSION] = PUCT_CONFIG_VERSION
    config_id: Optional[str] = None
    c_puct: float = Field(default=PUCT_DEFAULT_C, gt=0.0, le=PUCT_MAX_C)

    @field_validator("c_puct", mode="before")
    @classmethod
    def reject_boolean_c_puct(cls, value):
        if isinstance(value, bool):
            raise ValueError("c_puct must be numeric, not boolean")
        return value

    @model_validator(mode="after")
    def validate_and_identify(self) -> "PUCTConfig":
        if not math.isfinite(self.c_puct):
            raise ContractValidationError("c_puct must be finite")
        expected = stable_contract_id(
            "szpuctconfig",
            {
                "schema_version": self.schema_version,
                "c_puct": self.c_puct,
            },
        )
        if self.config_id is not None and self.config_id != expected:
            raise ContractValidationError("config_id does not match PUCT config")
        object.__setattr__(self, "config_id", expected)
        return self


class PUCTNode(_FrozenPUCTContract):
    """Bounded public snapshot of one path-local search node."""

    node_id: str
    state_id: str
    parent_edge_id: Optional[str] = None
    terminal: bool
    expanded: bool
    visit_count: int = Field(ge=0)
    value_sum: float
    mean_value: float = Field(ge=-1.0, le=1.0)
    child_edge_ids: Tuple[str, ...] = ()

    _nonblank_ids = field_validator("node_id", "state_id")(_nonblank)

    @model_validator(mode="after")
    def validate_statistics(self) -> "PUCTNode":
        if not math.isfinite(self.value_sum) or not math.isfinite(self.mean_value):
            raise ContractValidationError("PUCT node values must be finite")
        expected_mean = self.value_sum / self.visit_count if self.visit_count else 0.0
        if not math.isclose(
            self.mean_value, expected_mean, rel_tol=0.0, abs_tol=1e-12
        ):
            raise ContractValidationError("PUCT node mean does not match its visits")
        if self.terminal and (self.expanded or self.child_edge_ids):
            raise ContractValidationError("terminal PUCT node cannot be expanded")
        if not self.expanded and self.child_edge_ids:
            raise ContractValidationError("unexpanded PUCT node cannot own child edges")
        if len(set(self.child_edge_ids)) != len(self.child_edge_ids):
            raise ContractValidationError("PUCT node child edge IDs must be unique")
        return self


class PUCTEdge(_FrozenPUCTContract):
    """Root-edge P/Q/N statistics backed only by real observations."""

    edge_id: str
    parent_node_id: str
    action_id: str
    prior: float = Field(ge=0.0, le=1.0)
    visit_count: int = Field(ge=0)
    value_sum: float
    mean_q: float = Field(ge=-1.0, le=1.0)
    successor_node_ids: Tuple[str, ...] = ()
    successor_state_ids: Tuple[str, ...] = ()

    _nonblank_ids = field_validator(
        "edge_id", "parent_node_id", "action_id"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_statistics(self) -> "PUCTEdge":
        if not math.isfinite(self.prior):
            raise ContractValidationError("PUCT edge prior must be finite")
        if not math.isfinite(self.value_sum) or not math.isfinite(self.mean_q):
            raise ContractValidationError("PUCT edge values must be finite")
        if len(self.successor_node_ids) != self.visit_count:
            raise ContractValidationError("every PUCT edge visit needs a path-local node")
        if len(self.successor_state_ids) != self.visit_count:
            raise ContractValidationError("every PUCT edge visit needs a successor state")
        expected_mean = self.value_sum / self.visit_count if self.visit_count else 0.0
        if not math.isclose(self.mean_q, expected_mean, rel_tol=0.0, abs_tol=1e-12):
            raise ContractValidationError("PUCT edge Q does not match its visits")
        return self


class PUCTSimulation(_FrozenPUCTContract):
    """Public facts for one serial selection/observation/evaluation/backup."""

    simulation_index: int = Field(ge=1)
    selected_edge_id: str
    selected_action_id: str
    parent_visit_count_before: int = Field(ge=0)
    edge_visit_count_before: int = Field(ge=0)
    edge_q_before: float = Field(ge=-1.0, le=1.0)
    prior: float = Field(ge=0.0, le=1.0)
    puct_score: float
    successor_node_id: str
    successor_state_id: str
    leaf_value: float = Field(ge=-1.0, le=1.0)
    usage_before: BudgetUsage
    usage_delta: BudgetUsage
    usage_after: BudgetUsage

    _nonblank_ids = field_validator(
        "selected_edge_id",
        "selected_action_id",
        "successor_node_id",
        "successor_state_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_observation(self) -> "PUCTSimulation":
        for value in (self.edge_q_before, self.prior, self.puct_score, self.leaf_value):
            if not math.isfinite(value):
                raise ContractValidationError("PUCT simulation values must be finite")
        if self.usage_before.plus(self.usage_delta) != self.usage_after:
            raise ContractValidationError("PUCT simulation usage is not additive")
        return self


class PUCTSearchReceipt(_FrozenPUCTContract):
    """Rich bounded PUCT audit companion to the frozen SearchReceipt v0."""

    schema_version: Literal[PUCT_AUDIT_VERSION] = PUCT_AUDIT_VERSION
    receipt_id: Optional[str] = None
    search_receipt_id: str
    strategy_id: Literal[PUCT_STRATEGY_VERSION] = PUCT_STRATEGY_VERSION
    config: PUCTConfig
    root_state_id: str
    policy_estimator_id: str
    value_estimator_id: str
    successor_evaluator_id: str
    maximum_safe_relative_depth: Literal[1] = PUCT_MAX_SAFE_RELATIVE_DEPTH_V0
    initial_usage: BudgetUsage
    budget: SearchBudget
    usage: BudgetUsage
    expanded_state_ids: Tuple[str, ...] = ()
    nodes: Tuple[PUCTNode, ...] = ()
    edges: Tuple[PUCTEdge, ...] = ()
    simulations: Tuple[PUCTSimulation, ...] = ()
    duplicate_state_ids: Tuple[str, ...] = ()
    failed_action_ids: Tuple[str, ...] = ()
    pruned_action_ids: Tuple[str, ...] = ()
    selection_tie_break: Tuple[str, ...] = PUCT_SELECTION_TIE_BREAK
    root_tie_break: Tuple[str, ...] = PUCT_ROOT_TIE_BREAK
    root_value: Optional[float] = Field(default=None, ge=-1.0, le=1.0)
    selected_action_id: Optional[str] = None
    termination_reason: SearchTerminationReason

    _nonblank_fields = field_validator(
        "search_receipt_id",
        "root_state_id",
        "policy_estimator_id",
        "value_estimator_id",
        "successor_evaluator_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_tree_and_identify(self) -> "PUCTSearchReceipt":
        if self.failed_action_ids or self.pruned_action_ids:
            raise ContractValidationError(
                "PUCT v0 fails the entire search; completed receipts cannot hide failures"
            )
        if self.selection_tie_break != PUCT_SELECTION_TIE_BREAK:
            raise ContractValidationError("PUCT selection tie-break is frozen in v0")
        if self.root_tie_break != PUCT_ROOT_TIE_BREAK:
            raise ContractValidationError("PUCT root tie-break is frozen in v0")
        if self.root_value is not None and not math.isfinite(self.root_value):
            raise ContractValidationError("PUCT root Value must be finite")
        self.budget.enforce(self.usage)

        node_by_id = {node.node_id: node for node in self.nodes}
        edge_by_id = {edge.edge_id: edge for edge in self.edges}
        if len(node_by_id) != len(self.nodes) or len(edge_by_id) != len(self.edges):
            raise ContractValidationError("PUCT node and edge IDs must be unique")
        roots = tuple(node for node in self.nodes if node.parent_edge_id is None)
        if len(roots) != 1 or roots[0].state_id != self.root_state_id:
            raise ContractValidationError("PUCT receipt requires exactly one root node")
        root = roots[0]
        if tuple(sorted(root.child_edge_ids)) != tuple(sorted(edge_by_id)):
            raise ContractValidationError("root child edges do not match receipt edges")
        if any(edge.parent_node_id != root.node_id for edge in self.edges):
            raise ContractValidationError("PUCT v0 edges must be owned by the root")
        if any(
            node is not root and node.parent_edge_id not in edge_by_id
            for node in self.nodes
        ):
            raise ContractValidationError("PUCT child node has an unknown parent edge")

        expected_indices = tuple(range(1, len(self.simulations) + 1))
        if tuple(item.simulation_index for item in self.simulations) != expected_indices:
            raise ContractValidationError("PUCT simulation indices must be contiguous")
        if self.simulations:
            if self.simulations[0].usage_before != self.initial_usage:
                raise ContractValidationError("first PUCT simulation usage is not initial usage")
            for previous, current in zip(self.simulations, self.simulations[1:]):
                if previous.usage_after != current.usage_before:
                    raise ContractValidationError("PUCT simulation usage is not monotone")
            if self.simulations[-1].usage_after != self.usage:
                raise ContractValidationError("final PUCT simulation usage differs from receipt")
        elif self.usage != self.initial_usage:
            raise ContractValidationError("zero-simulation PUCT cannot consume hidden usage")

        leaf_values = tuple(item.leaf_value for item in self.simulations)
        if root.visit_count != len(self.simulations):
            raise ContractValidationError("root visits must equal completed simulations")
        if not math.isclose(root.value_sum, math.fsum(leaf_values), abs_tol=1e-12):
            raise ContractValidationError("root backup sum does not match leaf Values")

        simulation_by_edge: Dict[str, list[PUCTSimulation]] = {
            edge_id: [] for edge_id in edge_by_id
        }
        for simulation in self.simulations:
            if simulation.selected_edge_id not in edge_by_id:
                raise ContractValidationError("simulation selected an unknown edge")
            edge = edge_by_id[simulation.selected_edge_id]
            if simulation.selected_action_id != edge.action_id:
                raise ContractValidationError("simulation action differs from selected edge")
            if simulation.successor_node_id not in node_by_id:
                raise ContractValidationError("simulation successor node is absent")
            child = node_by_id[simulation.successor_node_id]
            if child.parent_edge_id != edge.edge_id:
                raise ContractValidationError("simulation child uses the wrong parent edge")
            if child.state_id != simulation.successor_state_id:
                raise ContractValidationError("simulation child state ID differs")
            simulation_by_edge[edge.edge_id].append(simulation)

        for edge in self.edges:
            observations = simulation_by_edge[edge.edge_id]
            values = tuple(item.leaf_value for item in observations)
            if edge.visit_count != len(observations):
                raise ContractValidationError("edge visits differ from simulations")
            if not math.isclose(edge.value_sum, math.fsum(values), abs_tol=1e-12):
                raise ContractValidationError("edge backup sum differs from leaf Values")
            if tuple(item.successor_node_id for item in observations) != edge.successor_node_ids:
                raise ContractValidationError("edge successor node order differs")
            if tuple(item.successor_state_id for item in observations) != edge.successor_state_ids:
                raise ContractValidationError("edge successor state order differs")
            if edge.visit_count > root.visit_count:
                raise ContractValidationError("edge visits cannot exceed root visits")

        expected_duplicates = tuple(
            sorted(
                state_id
                for state_id, count in Counter(
                    node.state_id for node in self.nodes
                ).items()
                if count > 1
            )
        )
        if self.duplicate_state_ids != expected_duplicates:
            raise ContractValidationError("duplicate state diagnostics are incomplete")
        expected_expanded = (self.root_state_id,) if root.expanded else ()
        if self.expanded_state_ids != expected_expanded:
            raise ContractValidationError("expanded state diagnostics differ from the tree")
        if self.selected_action_id is not None and self.selected_action_id not in {
            edge.action_id for edge in self.edges
        }:
            raise ContractValidationError("selected PUCT action is not a root edge")

        expected = stable_contract_id("szpuctreceipt", self.identity_payload())
        if self.receipt_id is not None and self.receipt_id != expected:
            raise ContractValidationError("receipt_id does not match PUCT audit")
        object.__setattr__(self, "receipt_id", expected)
        return self

    def identity_payload(self) -> Dict[str, object]:
        return self.model_dump(mode="json", exclude={"receipt_id"})


class PUCTEvaluation(_FrozenPUCTContract):
    """Canonical SearchResult plus the explicit PUCT-only companion receipt."""

    result: SearchResult
    puct_receipt: PUCTSearchReceipt

    @model_validator(mode="after")
    def validate_links(self) -> "PUCTEvaluation":
        if self.result.receipt.receipt_id != self.puct_receipt.search_receipt_id:
            raise ContractValidationError("PUCT and canonical receipts are not linked")
        if self.result.initial_state_id != self.puct_receipt.root_state_id:
            raise ContractValidationError("PUCT evaluation roots differ")
        selected_id = (
            self.result.selected_action.action_id
            if self.result.selected_action is not None
            else None
        )
        if selected_id != self.puct_receipt.selected_action_id:
            raise ContractValidationError("PUCT evaluation selections differ")
        if self.result.receipt.usage != self.puct_receipt.usage:
            raise ContractValidationError("PUCT evaluation usage differs")
        return self


@dataclass
class _EdgeAccumulator:
    action: LegalAction
    prior: float
    edge_id: str
    values: list[float] = field(default_factory=list)
    successor_node_ids: list[str] = field(default_factory=list)
    successor_state_ids: list[str] = field(default_factory=list)

    @property
    def visit_count(self) -> int:
        return len(self.values)

    @property
    def mean_q(self) -> float:
        return _mean(self.values)


def _puct_score(edge: _EdgeAccumulator, root_visits: int, c_puct: float) -> float:
    # max(1, N) makes the first selection explicitly prior-ordered rather than
    # relying on every score accidentally initializing to zero.
    return edge.mean_q + (
        c_puct
        * edge.prior
        * math.sqrt(max(1, root_visits))
        / (1 + edge.visit_count)
    )


def _select_edge(
    edges: Tuple[_EdgeAccumulator, ...], root_visits: int, c_puct: float
) -> Tuple[_EdgeAccumulator, float]:
    scored = tuple((edge, _puct_score(edge, root_visits, c_puct)) for edge in edges)
    edge, score = min(
        scored,
        key=lambda item: (-item[1], -item[0].prior, item[0].action.action_id),
    )
    return edge, score


def _validated_successor(
    value: ActionSuccessor,
    *,
    root: SearchState,
    action: LegalAction,
    budget: SearchBudget,
) -> ActionSuccessor:
    if not isinstance(value, ActionSuccessor):
        raise ContractValidationError("successor evaluator must return an ActionSuccessor")
    if value.action_id != action.action_id:
        raise ContractValidationError("successor action ID does not match selected edge")
    successor = _validated_state(value.state)
    if successor.parent_state_id != root.state_id:
        raise ContractValidationError("PUCT successor parent must be the root state")
    if successor.budget != budget:
        raise ContractValidationError("PUCT successor budget must equal search budget")
    if successor.depth != root.depth + PUCT_MAX_SAFE_RELATIVE_DEPTH_V0:
        raise ContractValidationError("PUCT v0 successor must be exactly one real ply deep")

    delta = value.usage_delta
    if delta.nodes != 1 or delta.expansions != 1:
        raise ContractValidationError(
            "each PUCT successor observation must consume one node and one expansion"
        )
    if delta.max_depth_observed != successor.depth:
        raise ContractValidationError("PUCT successor usage must record exact depth")
    expected_path_usage = root.budget_usage.plus(delta)
    if successor.budget_usage != expected_path_usage:
        raise ContractValidationError(
            "PUCT successor state usage differs from branch-local usage"
        )
    budget.enforce(expected_path_usage)
    return ActionSuccessor(
        action_id=value.action_id,
        state=successor,
        usage_delta=delta,
    )


def _structural_capacity(
    *, root: SearchState, aggregate_usage: BudgetUsage, budget: SearchBudget
) -> bool:
    if root.depth + PUCT_MAX_SAFE_RELATIVE_DEPTH_V0 > budget.max_depth:
        return False
    proposed = aggregate_usage.plus(
        BudgetUsage(
            nodes=1,
            expansions=1,
            max_depth_observed=root.depth + PUCT_MAX_SAFE_RELATIVE_DEPTH_V0,
        )
    )
    return budget.allows(proposed)


class PUCTStrategy:
    """Allocate a hard budget across real one-ply successor observations.

    Q is the undiscounted, same-orientation mean of observed leaf V values.
    There is no adversarial sign alternation.  Repeated visits perform repeated
    evaluator calls and consume repeated usage.  Child states are never used as
    evaluator inputs because the experimental seam lacks recursive guarantees.
    """

    name = "puct_strategy"
    version = PUCT_STRATEGY_VERSION

    def __init__(
        self,
        successor_evaluator,
        *,
        config: Optional[PUCTConfig] = None,
    ) -> None:
        if not callable(getattr(successor_evaluator, "evaluate_successor", None)):
            raise ContractValidationError("PUCT requires a SuccessorStateEvaluator")
        self._successor_evaluator = successor_evaluator
        if config is None:
            self.config = PUCTConfig()
        elif not isinstance(config, PUCTConfig):
            raise ContractValidationError("PUCT config must be a PUCTConfig")
        else:
            try:
                self.config = PUCTConfig.model_validate(
                    config.model_dump(mode="python")
                )
            except (TypeError, ValueError) as exc:
                raise ContractValidationError("PUCT requires a valid config") from exc

    async def search(
        self,
        initial_state: SearchState,
        *,
        constitution: SearchConstitution,
        action_generator,
        policy_prior,
        value_estimator,
        budget: SearchBudget,
    ) -> SearchResult:
        return (
            await self.evaluate(
                initial_state,
                constitution=constitution,
                action_generator=action_generator,
                policy_prior=policy_prior,
                value_estimator=value_estimator,
                budget=budget,
            )
        ).result

    async def evaluate(
        self,
        initial_state: SearchState,
        *,
        constitution: SearchConstitution,
        action_generator,
        policy_prior,
        value_estimator,
        budget: SearchBudget,
    ) -> PUCTEvaluation:
        state = _validated_state(initial_state)
        if budget != state.budget:
            raise ContractValidationError(
                "PUCT budget must equal the projected state's hard budget"
            )
        budget.enforce(state.budget_usage)

        hard_legal = _actions(constitution.legal_actions(state), owner="hard-legal")
        if state.terminal_status is not TerminalStatus.NON_TERMINAL:
            if len(hard_legal) != 1 or hard_legal[0].kind is not ActionKind.STOP:
                raise ContractValidationError(
                    "terminal PUCT state requires exactly one hard-legal Stop"
                )
            constitution.validate_action(state, hard_legal[0])
            root_value = await _root_value(value_estimator, state)
            return self._empty_evaluation(
                state=state,
                budget=budget,
                policy_prior=policy_prior,
                value_estimator=value_estimator,
                root_value=root_value,
                termination_reason=SearchTerminationReason.TERMINAL_STATE,
            )
        if not hard_legal:
            root_value = await _root_value(value_estimator, state)
            return self._empty_evaluation(
                state=state,
                budget=budget,
                policy_prior=policy_prior,
                value_estimator=value_estimator,
                root_value=root_value,
                termination_reason=SearchTerminationReason.NO_LEGAL_ACTIONS,
            )

        generated = _actions(
            await action_generator.generate(
                state,
                hard_legal_actions=hard_legal,
                limit=len(hard_legal),
            ),
            owner="generated",
        )
        hard_ids = tuple(action.action_id for action in hard_legal)
        generated_ids = tuple(action.action_id for action in generated)
        if set(generated_ids) - set(hard_ids):
            raise ContractValidationError("generated PUCT action is not hard-legal")
        if set(generated_ids) != set(hard_ids) or len(generated_ids) != len(hard_ids):
            raise ContractValidationError("PUCT expansion requires the full hard-legal set")
        for action in generated:
            constitution.validate_action(state, action)

        priors = _validated_priors(
            await policy_prior.priors(state, generated),
            candidate_ids=generated_ids,
        )
        prior_by_id = {item.action_id: item.probability for item in priors}

        root_node_id = stable_contract_id(
            "szpuctnode",
            {
                "root_state_id": state.state_id,
                "config_id": self.config.config_id,
                "path": (),
            },
        )
        edges = tuple(
            _EdgeAccumulator(
                action=action,
                prior=prior_by_id[action.action_id],
                edge_id=stable_contract_id(
                    "szpuctedge",
                    {
                        "root_node_id": root_node_id,
                        "action_id": action.action_id,
                    },
                ),
            )
            for action in sorted(generated, key=lambda item: item.action_id)
        )

        aggregate_usage = state.budget_usage
        simulations: list[PUCTSimulation] = []
        child_nodes: list[PUCTNode] = []
        provider_receipt_ids: set[str] = set()
        verification_result_ids: set[str] = set()
        while _structural_capacity(
            root=state,
            aggregate_usage=aggregate_usage,
            budget=budget,
        ):
            root_visits = len(simulations)
            edge, score = _select_edge(edges, root_visits, self.config.c_puct)
            usage_before = aggregate_usage
            outcome = _validated_successor(
                await self._successor_evaluator.evaluate_successor(
                    state,
                    edge.action,
                    budget=budget,
                    aggregate_usage=aggregate_usage,
                ),
                root=state,
                action=edge.action,
                budget=budget,
            )
            aggregate_usage = aggregate_usage.plus(outcome.usage_delta)
            budget.enforce(aggregate_usage)
            leaf_value = _finite_unit_value(
                await value_estimator.estimate(outcome.state),
                owner="PUCT leaf Value",
            )

            simulation_index = root_visits + 1
            successor_node_id = stable_contract_id(
                "szpuctnode",
                {
                    "root_state_id": state.state_id,
                    "config_id": self.config.config_id,
                    "simulation_index": simulation_index,
                    "action_id": edge.action.action_id,
                    "successor_state_id": outcome.state.state_id,
                },
            )
            child_nodes.append(
                PUCTNode(
                    node_id=successor_node_id,
                    state_id=outcome.state.state_id,
                    parent_edge_id=edge.edge_id,
                    terminal=(
                        outcome.state.terminal_status is not TerminalStatus.NON_TERMINAL
                    ),
                    expanded=False,
                    visit_count=1,
                    value_sum=leaf_value,
                    mean_value=leaf_value,
                )
            )
            simulations.append(
                PUCTSimulation(
                    simulation_index=simulation_index,
                    selected_edge_id=edge.edge_id,
                    selected_action_id=edge.action.action_id,
                    parent_visit_count_before=root_visits,
                    edge_visit_count_before=edge.visit_count,
                    edge_q_before=edge.mean_q,
                    prior=edge.prior,
                    puct_score=score,
                    successor_node_id=successor_node_id,
                    successor_state_id=outcome.state.state_id,
                    leaf_value=leaf_value,
                    usage_before=usage_before,
                    usage_delta=outcome.usage_delta,
                    usage_after=aggregate_usage,
                )
            )
            edge.values.append(leaf_value)
            edge.successor_node_ids.append(successor_node_id)
            edge.successor_state_ids.append(outcome.state.state_id)
            provider_receipt_ids.update(
                receipt.record_id for receipt in outcome.state.provider_receipts
            )
            verification_result_ids.update(
                result.record_id for result in outcome.state.verification_results
            )

        if simulations:
            selected_edge = min(
                edges,
                key=lambda item: (
                    -item.visit_count,
                    -item.mean_q,
                    -item.prior,
                    item.action.action_id,
                ),
            )
            selected_action: Optional[LegalAction] = selected_edge.action
            estimated_value = selected_edge.mean_q
            root_value: Optional[float] = None
        else:
            selected_action = None
            estimated_value = await _root_value(value_estimator, state)
            root_value = estimated_value

        termination_reason = SearchTerminationReason.BUDGET_EXHAUSTED
        search_receipt = SearchReceipt(
            strategy_name=self.name,
            strategy_version=self.version,
            initial_state_id=state.state_id,
            selected_action_id=(selected_action.action_id if selected_action else None),
            visited_state_ids=(state.state_id,)
            + tuple(item.successor_state_id for item in simulations),
            expanded_action_ids=tuple(item.selected_action_id for item in simulations),
            provider_receipt_ids=tuple(sorted(provider_receipt_ids)),
            verification_result_ids=tuple(sorted(verification_result_ids)),
            budget=budget,
            usage=aggregate_usage,
            termination_reason=termination_reason,
        )
        result = SearchResult(
            initial_state_id=state.state_id,
            selected_action=selected_action,
            estimated_value=estimated_value,
            action_statistics=tuple(
                ActionStatistics(
                    action_id=edge.action.action_id,
                    prior=edge.prior,
                    visit_count=edge.visit_count,
                    mean_value=edge.mean_q,
                )
                for edge in edges
            ),
            receipt=search_receipt,
        )
        return self._evaluation_with_tree(
            result=result,
            state=state,
            policy_prior=policy_prior,
            value_estimator=value_estimator,
            root_node_id=root_node_id,
            root_value=root_value,
            edges=edges,
            child_nodes=tuple(child_nodes),
            simulations=tuple(simulations),
        )

    def _empty_evaluation(
        self,
        *,
        state: SearchState,
        budget: SearchBudget,
        policy_prior,
        value_estimator,
        root_value: float,
        termination_reason: SearchTerminationReason,
    ) -> PUCTEvaluation:
        search_receipt = SearchReceipt(
            strategy_name=self.name,
            strategy_version=self.version,
            initial_state_id=state.state_id,
            visited_state_ids=(state.state_id,),
            budget=budget,
            usage=state.budget_usage,
            termination_reason=termination_reason,
        )
        result = SearchResult(
            initial_state_id=state.state_id,
            selected_action=None,
            estimated_value=root_value,
            receipt=search_receipt,
        )
        root_node_id = stable_contract_id(
            "szpuctnode",
            {
                "root_state_id": state.state_id,
                "config_id": self.config.config_id,
                "path": (),
            },
        )
        audit = PUCTSearchReceipt(
            search_receipt_id=search_receipt.receipt_id,
            config=self.config,
            root_state_id=state.state_id,
            policy_estimator_id=_component_id(policy_prior),
            value_estimator_id=_component_id(value_estimator),
            successor_evaluator_id=_component_id(self._successor_evaluator),
            initial_usage=state.budget_usage,
            budget=budget,
            usage=state.budget_usage,
            nodes=(
                PUCTNode(
                    node_id=root_node_id,
                    state_id=state.state_id,
                    terminal=(
                        state.terminal_status is not TerminalStatus.NON_TERMINAL
                    ),
                    expanded=False,
                    visit_count=0,
                    value_sum=0.0,
                    mean_value=0.0,
                ),
            ),
            root_value=root_value,
            termination_reason=termination_reason,
        )
        return PUCTEvaluation(result=result, puct_receipt=audit)

    def _evaluation_with_tree(
        self,
        *,
        result: SearchResult,
        state: SearchState,
        policy_prior,
        value_estimator,
        root_node_id: str,
        root_value: Optional[float],
        edges: Tuple[_EdgeAccumulator, ...],
        child_nodes: Tuple[PUCTNode, ...],
        simulations: Tuple[PUCTSimulation, ...],
    ) -> PUCTEvaluation:
        edge_snapshots = tuple(
            PUCTEdge(
                edge_id=edge.edge_id,
                parent_node_id=root_node_id,
                action_id=edge.action.action_id,
                prior=edge.prior,
                visit_count=edge.visit_count,
                value_sum=math.fsum(edge.values),
                mean_q=edge.mean_q,
                successor_node_ids=tuple(edge.successor_node_ids),
                successor_state_ids=tuple(edge.successor_state_ids),
            )
            for edge in edges
        )
        root_values = tuple(item.leaf_value for item in simulations)
        root_node = PUCTNode(
            node_id=root_node_id,
            state_id=state.state_id,
            terminal=False,
            expanded=True,
            visit_count=len(simulations),
            value_sum=math.fsum(root_values),
            mean_value=_mean(root_values),
            child_edge_ids=tuple(edge.edge_id for edge in edges),
        )
        all_nodes = (root_node,) + child_nodes
        duplicate_state_ids = tuple(
            sorted(
                state_id
                for state_id, count in Counter(
                    node.state_id for node in all_nodes
                ).items()
                if count > 1
            )
        )
        audit = PUCTSearchReceipt(
            search_receipt_id=result.receipt.receipt_id,
            config=self.config,
            root_state_id=state.state_id,
            policy_estimator_id=_component_id(policy_prior),
            value_estimator_id=_component_id(value_estimator),
            successor_evaluator_id=_component_id(self._successor_evaluator),
            initial_usage=state.budget_usage,
            budget=result.receipt.budget,
            usage=result.receipt.usage,
            expanded_state_ids=(state.state_id,),
            nodes=all_nodes,
            edges=edge_snapshots,
            simulations=simulations,
            duplicate_state_ids=duplicate_state_ids,
            root_value=root_value,
            selected_action_id=(
                result.selected_action.action_id
                if result.selected_action is not None
                else None
            ),
            termination_reason=result.receipt.termination_reason,
        )
        return PUCTEvaluation(result=result, puct_receipt=audit)


__all__ = [
    "PUCT_AUDIT_VERSION",
    "PUCT_CONFIG_VERSION",
    "PUCT_DEFAULT_C",
    "PUCT_MAX_C",
    "PUCT_MAX_SAFE_RELATIVE_DEPTH_V0",
    "PUCT_ROOT_TIE_BREAK",
    "PUCT_SELECTION_TIE_BREAK",
    "PUCT_STRATEGY_VERSION",
    "PUCTConfig",
    "PUCTEdge",
    "PUCTEvaluation",
    "PUCTNode",
    "PUCTSearchReceipt",
    "PUCTSimulation",
    "PUCTStrategy",
]
