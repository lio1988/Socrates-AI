"""Deterministic runtime-inert strategy baselines.

Strategies may select from a CED-owned hard-legal set.  They do not execute the
selection, mutate CED state, manufacture successor states, or grant epistemic
status.  Greedy v0 is deliberately one-step: Policy ranks actions and Value
evaluates the current root state only. Best-of-N consumes explicit successors
from an injected evaluator; the strategy never manufactures them.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Iterable, Tuple

from pydantic import ValidationError

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
)


GREEDY_STRATEGY_VERSION = "greedy-strategy/v0"
BEST_OF_N_STRATEGY_VERSION = "best-of-n-strategy/v0"
BEST_OF_N_CANDIDATE_COUNT_V0 = 4
_PROBABILITY_TOLERANCE = 1e-12


def _validated_state(state: SearchState) -> SearchState:
    if not isinstance(state, SearchState):
        raise ContractValidationError("strategy requires a SearchState")
    try:
        validated = SearchState.model_validate(state.model_dump(mode="python"))
    except (ValidationError, ContractValidationError, TypeError, ValueError) as exc:
        raise ContractValidationError("strategy requires a valid SearchState") from exc
    complete = validated.phase == "complete"
    if validated.terminal_status in {
        TerminalStatus.ANSWER_READY,
        TerminalStatus.ABSTAINED,
        TerminalStatus.BLOCKED,
    } and not complete:
        raise ContractValidationError(
            f"{validated.terminal_status.value} terminal state must be in complete phase"
        )
    if complete and validated.terminal_status is TerminalStatus.NON_TERMINAL:
        raise ContractValidationError("complete state cannot be non-terminal")
    return validated


def _actions(values: Iterable[LegalAction], *, owner: str) -> Tuple[LegalAction, ...]:
    try:
        actions = tuple(values)
    except TypeError as exc:
        raise ContractValidationError(f"{owner} actions must be iterable") from exc
    if any(not isinstance(action, LegalAction) for action in actions):
        raise ContractValidationError(f"{owner} actions must contain only LegalAction values")
    action_ids = tuple(action.action_id for action in actions)
    if len(set(action_ids)) != len(action_ids):
        raise ContractValidationError(f"{owner} actions contain duplicate IDs")
    return actions


def _validated_priors(
    values: Iterable[ActionPrior],
    *,
    candidate_ids: Tuple[str, ...],
) -> Tuple[ActionPrior, ...]:
    try:
        priors = tuple(values)
    except TypeError as exc:
        raise ContractValidationError("policy priors must be iterable") from exc
    if any(not isinstance(prior, ActionPrior) for prior in priors):
        raise ContractValidationError("policy output must contain only ActionPrior values")
    prior_ids = tuple(prior.action_id for prior in priors)
    if len(set(prior_ids)) != len(prior_ids):
        raise ContractValidationError("policy output contains duplicate action IDs")
    if set(prior_ids) != set(candidate_ids) or len(prior_ids) != len(candidate_ids):
        raise ContractValidationError(
            "policy output must map exactly one prior to every generated action"
        )
    probabilities = tuple(prior.probability for prior in priors)
    if any(not math.isfinite(probability) for probability in probabilities):
        raise ContractValidationError("policy probability must be finite")
    if any(probability < 0.0 or probability > 1.0 for probability in probabilities):
        raise ContractValidationError("policy probability must be inside [0,1]")
    if not math.isclose(
        math.fsum(probabilities),
        1.0,
        rel_tol=0.0,
        abs_tol=_PROBABILITY_TOLERANCE,
    ):
        raise ContractValidationError("policy probabilities must sum to 1")
    return priors


async def _root_value(value_estimator, state: SearchState) -> float:
    value = await value_estimator.estimate(state)
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ContractValidationError("estimated value must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ContractValidationError("estimated value must be finite")
    if numeric < -1.0 or numeric > 1.0:
        raise ContractValidationError("estimated value must be inside [-1,+1]")
    return numeric


def _result(
    *,
    strategy_name: str,
    strategy_version: str,
    state: SearchState,
    budget: SearchBudget,
    selected_action: LegalAction | None,
    estimated_value: float,
    priors: Tuple[ActionPrior, ...],
    termination_reason: SearchTerminationReason,
) -> SearchResult:
    receipt = SearchReceipt(
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        initial_state_id=state.state_id,
        selected_action_id=(selected_action.action_id if selected_action else None),
        visited_state_ids=(state.state_id,),
        budget=budget,
        usage=state.budget_usage,
        termination_reason=termination_reason,
    )
    return SearchResult(
        initial_state_id=state.state_id,
        selected_action=selected_action,
        estimated_value=estimated_value,
        action_statistics=tuple(
            ActionStatistics(
                action_id=prior.action_id,
                prior=prior.probability,
                visit_count=0,
                mean_value=0.0,
            )
            for prior in sorted(priors, key=lambda item: item.action_id)
        ),
        receipt=receipt,
    )


class GreedyStrategy:
    """Choose the highest Policy prior across the complete hard-legal set.

    Equal priors use stable action-ID order.  Root Value is reported separately;
    it is never treated as an action-conditioned Q value.  No action is executed.
    """

    name = "greedy_strategy"
    version = GREEDY_STRATEGY_VERSION

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
        state = _validated_state(initial_state)
        if budget != state.budget:
            raise ContractValidationError(
                "greedy strategy budget must equal the projected state's hard budget"
            )
        budget.enforce(state.budget_usage)

        hard_legal = _actions(
            constitution.legal_actions(state),
            owner="hard-legal",
        )
        if not hard_legal:
            return _result(
                strategy_name=self.name,
                strategy_version=self.version,
                state=state,
                budget=budget,
                selected_action=None,
                estimated_value=await _root_value(value_estimator, state),
                priors=(),
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
            raise ContractValidationError(
                "generated action falls outside the hard-legal set"
            )
        if set(generated_ids) != set(hard_ids) or len(generated_ids) != len(hard_ids):
            raise ContractValidationError(
                "greedy strategy requires the full hard-legal set"
            )
        for action in generated:
            constitution.validate_action(state, action)

        priors = _validated_priors(
            await policy_prior.priors(state, generated),
            candidate_ids=generated_ids,
        )
        probability_by_id = {
            prior.action_id: prior.probability for prior in priors
        }
        selected = min(
            generated,
            key=lambda action: (
                -probability_by_id[action.action_id],
                action.action_id,
            ),
        )
        return _result(
            strategy_name=self.name,
            strategy_version=self.version,
            state=state,
            budget=budget,
            selected_action=selected,
            estimated_value=await _root_value(value_estimator, state),
            priors=priors,
            termination_reason=SearchTerminationReason.COMPLETED,
        )


def _validated_successor(
    value: ActionSuccessor,
    *,
    root: SearchState,
    action: LegalAction,
    budget: SearchBudget,
) -> ActionSuccessor:
    if not isinstance(value, ActionSuccessor):
        raise ContractValidationError(
            "successor evaluator must return an ActionSuccessor"
        )
    if value.action_id != action.action_id:
        raise ContractValidationError("successor action ID does not match candidate")
    successor = _validated_state(value.state)
    if successor.parent_state_id != root.state_id:
        raise ContractValidationError("successor parent must be the initial state")
    if successor.budget != budget:
        raise ContractValidationError("successor budget must equal the search budget")
    if successor.depth != root.depth + 1:
        raise ContractValidationError("successor must be exactly one search ply deeper")

    delta = value.usage_delta
    if delta.nodes != 1 or delta.expansions != 1:
        raise ContractValidationError(
            "each Best-of-N successor must consume one node and one expansion"
        )
    if delta.max_depth_observed != successor.depth:
        raise ContractValidationError(
            "successor usage must record its exact observed depth"
        )
    expected_path_usage = root.budget_usage.plus(delta)
    if successor.budget_usage != expected_path_usage:
        raise ContractValidationError(
            "successor state usage does not match its branch-local usage delta"
        )
    budget.enforce(expected_path_usage)
    return ActionSuccessor(
        action_id=value.action_id,
        state=successor,
        usage_delta=delta,
    )


class BestOfNStrategy:
    """Evaluate at most four explicit one-ply successors and select the best.

    Successor Value is the primary ordering signal.  Equal Values use Policy
    prior and then stable action-ID order.  The injected evaluator owns no CED
    execution authority and must return immutable states plus exact usage.
    """

    name = "best_of_n_strategy"
    version = BEST_OF_N_STRATEGY_VERSION
    candidate_count = BEST_OF_N_CANDIDATE_COUNT_V0

    def __init__(self, successor_evaluator) -> None:
        if not callable(getattr(successor_evaluator, "evaluate_successor", None)):
            raise ContractValidationError(
                "Best-of-N requires a SuccessorStateEvaluator"
            )
        self._successor_evaluator = successor_evaluator

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
        state = _validated_state(initial_state)
        if budget != state.budget:
            raise ContractValidationError(
                "Best-of-N budget must equal the projected state's hard budget"
            )
        budget.enforce(state.budget_usage)

        hard_legal = _actions(
            constitution.legal_actions(state),
            owner="hard-legal",
        )
        if state.terminal_status is not TerminalStatus.NON_TERMINAL:
            if len(hard_legal) != 1 or hard_legal[0].kind is not ActionKind.STOP:
                raise ContractValidationError(
                    "terminal Best-of-N state requires exactly one hard-legal Stop"
                )
            selected = hard_legal[0]
            constitution.validate_action(state, selected)
            return _result(
                strategy_name=self.name,
                strategy_version=self.version,
                state=state,
                budget=budget,
                selected_action=selected,
                estimated_value=await _root_value(value_estimator, state),
                priors=(ActionPrior(action_id=selected.action_id, probability=1.0),),
                termination_reason=SearchTerminationReason.TERMINAL_STATE,
            )
        if not hard_legal:
            return _result(
                strategy_name=self.name,
                strategy_version=self.version,
                state=state,
                budget=budget,
                selected_action=None,
                estimated_value=await _root_value(value_estimator, state),
                priors=(),
                termination_reason=SearchTerminationReason.NO_LEGAL_ACTIONS,
            )

        remaining_nodes = budget.max_nodes - state.budget_usage.nodes
        remaining_expansions = (
            budget.max_expansions - state.budget_usage.expansions
        )
        depth_available = state.depth < budget.max_depth
        limit = (
            min(
                self.candidate_count,
                len(hard_legal),
                max(0, remaining_nodes),
                max(0, remaining_expansions),
            )
            if depth_available
            else 0
        )
        if limit == 0:
            return _result(
                strategy_name=self.name,
                strategy_version=self.version,
                state=state,
                budget=budget,
                selected_action=None,
                estimated_value=await _root_value(value_estimator, state),
                priors=(),
                termination_reason=SearchTerminationReason.BUDGET_EXHAUSTED,
            )

        generated = _actions(
            await action_generator.generate(
                state,
                hard_legal_actions=hard_legal,
                limit=limit,
            ),
            owner="generated",
        )
        hard_ids = {action.action_id for action in hard_legal}
        generated_ids = tuple(action.action_id for action in generated)
        if set(generated_ids) - hard_ids:
            raise ContractValidationError(
                "generated Best-of-N candidate falls outside the hard-legal set"
            )
        if len(generated) != limit:
            raise ContractValidationError(
                "action generator must return exactly the requested candidate count"
            )
        for action in generated:
            constitution.validate_action(state, action)

        priors = _validated_priors(
            await policy_prior.priors(state, generated),
            candidate_ids=generated_ids,
        )
        probability_by_id = {
            prior.action_id: prior.probability for prior in priors
        }

        aggregate_usage = state.budget_usage
        evaluated = []
        for action in sorted(generated, key=lambda item: item.action_id):
            outcome = _validated_successor(
                await self._successor_evaluator.evaluate_successor(
                    state,
                    action,
                    budget=budget,
                    aggregate_usage=aggregate_usage,
                ),
                root=state,
                action=action,
                budget=budget,
            )
            aggregate_usage = aggregate_usage.plus(outcome.usage_delta)
            budget.enforce(aggregate_usage)
            estimated_value = await _root_value(value_estimator, outcome.state)
            evaluated.append((action, outcome, estimated_value))

        selected_action, selected_outcome, selected_value = min(
            evaluated,
            key=lambda item: (
                -item[2],
                -probability_by_id[item[0].action_id],
                item[0].action_id,
            ),
        )
        provider_receipt_ids = tuple(
            sorted(
                {
                    receipt.record_id
                    for _, outcome, _ in evaluated
                    for receipt in outcome.state.provider_receipts
                }
            )
        )
        verification_result_ids = tuple(
            sorted(
                {
                    result.record_id
                    for _, outcome, _ in evaluated
                    for result in outcome.state.verification_results
                }
            )
        )
        receipt = SearchReceipt(
            strategy_name=self.name,
            strategy_version=self.version,
            initial_state_id=state.state_id,
            final_state_id=selected_outcome.state.state_id,
            selected_action_id=selected_action.action_id,
            visited_state_ids=(state.state_id,) + tuple(
                outcome.state.state_id for _, outcome, _ in evaluated
            ),
            expanded_action_ids=tuple(
                action.action_id for action, _, _ in evaluated
            ),
            provider_receipt_ids=provider_receipt_ids,
            verification_result_ids=verification_result_ids,
            budget=budget,
            usage=aggregate_usage,
            termination_reason=SearchTerminationReason.COMPLETED,
        )
        return SearchResult(
            initial_state_id=state.state_id,
            final_state_id=selected_outcome.state.state_id,
            selected_action=selected_action,
            estimated_value=selected_value,
            action_statistics=tuple(
                ActionStatistics(
                    action_id=action.action_id,
                    prior=probability_by_id[action.action_id],
                    visit_count=1,
                    mean_value=value,
                )
                for action, _, value in evaluated
            ),
            receipt=receipt,
        )


__all__ = [
    "BEST_OF_N_CANDIDATE_COUNT_V0",
    "BEST_OF_N_STRATEGY_VERSION",
    "GREEDY_STRATEGY_VERSION",
    "BestOfNStrategy",
    "GreedyStrategy",
]
