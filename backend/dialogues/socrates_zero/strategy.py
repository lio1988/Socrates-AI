"""Deterministic runtime-inert strategy baselines.

Strategies may select from a CED-owned hard-legal set.  They do not execute the
selection, mutate CED state, manufacture successor states, or grant epistemic
status.  Greedy v0 is deliberately one-step: Policy ranks actions and Value
evaluates the current root state only.
"""

from __future__ import annotations

import math
from numbers import Real
from typing import Iterable, Tuple

from pydantic import ValidationError

from .contracts import (
    ActionPrior,
    ActionStatistics,
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


__all__ = [
    "GREEDY_STRATEGY_VERSION",
    "GreedyStrategy",
]
