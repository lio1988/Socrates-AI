"""Bounded deterministic PUCT over real one-ply successor observations."""

from __future__ import annotations

import asyncio
import hashlib
import math

import pytest
from pydantic import ValidationError

from backend.dialogues.socrates_zero import (
    PUCT_AUDIT_VERSION,
    PUCT_CONFIG_VERSION,
    PUCT_DEFAULT_C,
    PUCT_MAX_C,
    PUCT_MAX_SAFE_RELATIVE_DEPTH_V0,
    PUCT_STRATEGY_VERSION,
    ActionKind,
    ActionParameter,
    ActionPrior,
    ActionSuccessor,
    BudgetExceeded,
    BudgetUsage,
    ContractValidationError,
    HeuristicValueEstimator,
    LegalAction,
    NeutralValueEstimator,
    ObservationRef,
    PUCTConfig,
    PUCTEdge,
    PUCTNode,
    PUCTSearchReceipt,
    PUCTStrategy,
    PolicyContextEntry,
    SearchBudget,
    SearchState,
    SearchStrategy,
    SearchTerminationReason,
    SemanticArtifactRef,
    SuccessorStateEvaluator,
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _budget(*, simulations: int = 4, **updates) -> SearchBudget:
    data = {
        "max_nodes": 1 + simulations,
        "max_expansions": simulations,
        "max_model_calls": simulations,
        "max_tool_calls": 0,
        "max_tokens": simulations * 100,
        "max_cost_microusd": simulations * 1000,
        "max_wall_time_ms": simulations * 10,
        "max_depth": 1,
    }
    data.update(updates)
    return SearchBudget(**data)


def _state(*, simulations: int = 4, **updates) -> SearchState:
    data = {
        "task_kind": "elenchus_objection",
        "question": "Which observed branch deserves bounded search?",
        "phase": "elenchus",
        "budget": _budget(simulations=simulations),
        "budget_usage": BudgetUsage(nodes=1),
    }
    data.update(updates)
    return SearchState(**data)


def _action(label: str) -> LegalAction:
    return LegalAction(
        kind=ActionKind.PROPOSE_CLAIM,
        parameters=(ActionParameter(name="branch", value=label),),
    )


class _Constitution:
    def __init__(self, actions) -> None:
        self.actions = tuple(actions)
        self.legal_inputs = []
        self.validated = []

    def legal_actions(self, state):
        self.legal_inputs.append((state.state_id, state.depth))
        return self.actions

    def validate_action(self, state, action):
        if action.action_id not in {candidate.action_id for candidate in self.actions}:
            raise ContractValidationError("not hard-legal")
        self.validated.append((state.state_id, action.action_id))


class _Generator:
    def __init__(self, outputs=None) -> None:
        self.outputs = outputs
        self.calls = []

    async def generate(self, state, *, hard_legal_actions, limit):
        hard = tuple(hard_legal_actions)
        self.calls.append((state.state_id, hard, limit))
        return self.outputs if self.outputs is not None else tuple(reversed(hard))


class _Policy:
    name = "fixture_policy_prior"
    version = "fixture-policy/v0"

    def __init__(self, probabilities=None, outputs=None) -> None:
        self.probabilities = probabilities or {}
        self.outputs = outputs
        self.calls = []

    async def priors(self, state, legal_actions):
        actions = tuple(legal_actions)
        self.calls.append((state.state_id, actions))
        if self.outputs is not None:
            return self.outputs
        return tuple(
            ActionPrior(
                action_id=action.action_id,
                probability=self.probabilities[action.action_id],
            )
            for action in reversed(actions)
        )


class _Value:
    name = "fixture_value_estimator"
    version = "fixture-value/v0"

    def __init__(self, values, *, root_value=0.0) -> None:
        self.values = dict(values)
        self.root_value = root_value
        self.calls = []

    async def estimate(self, state):
        self.calls.append((state.state_id, state.depth))
        marker = next(
            (item for item in state.policy_context if item.name == "candidate_action"),
            None,
        )
        if marker is None:
            return self.root_value
        return self.values[marker.semantic_digest]


class _Successors:
    name = "fixture_successor_evaluator"
    version = "fixture-successor/v0"

    def __init__(
        self,
        *,
        transform=None,
        terminal_actions=(),
        shared_state=False,
        artifact_by_action=None,
        fail=None,
    ) -> None:
        self.transform = transform
        self.terminal_actions = set(terminal_actions)
        self.shared_state = shared_state
        self.artifact_by_action = artifact_by_action or {}
        self.fail = fail
        self.calls = []

    async def evaluate_successor(
        self,
        state,
        action,
        *,
        budget,
        aggregate_usage,
    ):
        self.calls.append((state, action, aggregate_usage))
        if self.fail is not None:
            raise self.fail
        delta = BudgetUsage(
            nodes=1,
            expansions=1,
            model_calls=1,
            tokens=100,
            cost_microusd=1000,
            wall_time_ms=10,
            max_depth_observed=state.depth + 1,
        )
        # The experimental seam owns reservation for dimensions whose next
        # delta the strategy cannot know before invoking it.
        budget.enforce(aggregate_usage.plus(delta))
        marker = "shared" if self.shared_state else action.action_id
        data = state.model_dump(mode="python", exclude={"state_id"})
        data.update(
            {
                "parent_state_id": state.state_id,
                "policy_context": (
                    PolicyContextEntry(
                        name="candidate_action",
                        semantic_digest=_digest(marker),
                    ),
                ),
                "provider_receipts": (
                    ObservationRef(
                        record_id=f"provider:{marker}",
                        semantic_digest=_digest(f"observation:{marker}"),
                    ),
                ),
                "budget_usage": state.budget_usage.plus(delta),
                "depth": state.depth + 1,
            }
        )
        artifact = self.artifact_by_action.get(action.action_id)
        if artifact is not None:
            data["contradictions"] = (artifact,)
        if action.action_id in self.terminal_actions:
            data.update(phase="complete", terminal_status="answer_ready")
        result = ActionSuccessor(
            action_id=action.action_id,
            state=SearchState(**data),
            usage_delta=delta,
        )
        return self.transform(result) if self.transform is not None else result


class _Unused:
    def legal_actions(self, *args, **kwargs):
        raise AssertionError("constitution must not be called")

    def validate_action(self, *args, **kwargs):
        raise AssertionError("constitution must not validate")

    async def generate(self, *args, **kwargs):
        raise AssertionError("generator must not be called")

    async def priors(self, *args, **kwargs):
        raise AssertionError("policy must not be called")

    async def evaluate_successor(self, *args, **kwargs):
        raise AssertionError("successor evaluator must not be called")


def _two_ply_successor(outcome):
    delta = outcome.usage_delta.model_copy(update={"max_depth_observed": 2})
    data = outcome.state.model_dump(mode="python", exclude={"state_id"})
    data.update(
        depth=2,
        budget_usage=outcome.state.budget_usage.model_copy(
            update={"max_depth_observed": 2}
        ),
    )
    return ActionSuccessor(
        action_id=outcome.action_id,
        state=SearchState(**data),
        usage_delta=delta,
    )


def _run(
    *,
    state,
    actions,
    probabilities,
    values,
    successors=None,
    constitution=None,
    generator=None,
    policy=None,
    value=None,
    budget=None,
    config=None,
    rich=True,
):
    successors = successors or _Successors()
    strategy = PUCTStrategy(successors, config=config)
    coroutine = strategy.evaluate if rich else strategy.search
    return asyncio.run(
        coroutine(
            state,
            constitution=constitution or _Constitution(actions),
            action_generator=generator or _Generator(),
            policy_prior=policy or _Policy(probabilities),
            value_estimator=value
            or _Value({_digest(action_id): item for action_id, item in values.items()}),
            budget=budget or state.budget,
        )
    )


def test_puct_contract_versions_default_math_and_strategy_protocol():
    evaluator = _Successors()
    strategy = PUCTStrategy(evaluator)

    assert isinstance(evaluator, SuccessorStateEvaluator)
    assert isinstance(strategy, SearchStrategy)
    assert PUCT_STRATEGY_VERSION == "puct-strategy/v0"
    assert PUCT_CONFIG_VERSION == "puct-config/v0"
    assert PUCT_AUDIT_VERSION == "puct-search-receipt/v0"
    assert PUCT_DEFAULT_C == 1.0
    assert PUCT_MAX_SAFE_RELATIVE_DEPTH_V0 == 1
    assert strategy.config == PUCTConfig(c_puct=1.0)


@pytest.mark.parametrize(
    "value", [0.0, -1.0, math.nan, math.inf, -math.inf, 100.01, True]
)
def test_c_puct_rejects_disabled_nonfinite_or_out_of_range_values(value):
    with pytest.raises((ValidationError, ContractValidationError)):
        PUCTConfig(c_puct=value)
    assert PUCT_MAX_C == 100.0


def test_strategy_rejects_noncanonical_or_forged_config():
    with pytest.raises(ContractValidationError, match="PUCTConfig"):
        PUCTStrategy(_Successors(), config={"c_puct": 1.0})

    forged = PUCTConfig().model_copy(update={"config_id": "forged"})
    with pytest.raises(ContractValidationError, match="valid config"):
        PUCTStrategy(_Successors(), config=forged)


def test_tiny_budget_follows_misleading_policy_but_sufficient_budget_overrides_it():
    action_a, action_b = _action("A"), _action("B")
    actions = (action_a, action_b)
    probabilities = {action_a.action_id: 0.75, action_b.action_id: 0.25}
    values = {action_a.action_id: -0.8, action_b.action_id: 0.8}

    tiny = _run(
        state=_state(simulations=1),
        actions=actions,
        probabilities=probabilities,
        values=values,
    )
    sufficient = _run(
        state=_state(simulations=2),
        actions=actions,
        probabilities=probabilities,
        values=values,
    )

    assert tiny.result.selected_action == action_a
    assert [item.selected_action_id for item in tiny.puct_receipt.simulations] == [
        action_a.action_id
    ]
    assert sufficient.result.selected_action == action_b
    assert [
        item.selected_action_id for item in sufficient.puct_receipt.simulations
    ] == [action_a.action_id, action_b.action_id]
    assert {item.action_id: item.mean_value for item in sufficient.result.action_statistics} == {
        action_a.action_id: -0.8,
        action_b.action_id: 0.8,
    }


def test_policy_correct_tree_remains_on_good_high_prior_branch():
    action_a, action_b = _action("A"), _action("B")
    result = _run(
        state=_state(simulations=6),
        actions=(action_a, action_b),
        probabilities={action_a.action_id: 0.7, action_b.action_id: 0.3},
        values={action_a.action_id: 0.7, action_b.action_id: 0.1},
    )

    visits = {item.action_id: item.visit_count for item in result.result.action_statistics}
    assert result.result.selected_action == action_a
    assert visits[action_a.action_id] > visits[action_b.action_id]


def test_changing_c_puct_predictably_changes_exploration():
    action_a, action_b, action_c = _action("A"), _action("B"), _action("C")
    actions = (action_a, action_b, action_c)
    probabilities = {
        action_a.action_id: 0.55,
        action_b.action_id: 0.35,
        action_c.action_id: 0.10,
    }
    values = {
        action_a.action_id: 0.3,
        action_b.action_id: 0.0,
        action_c.action_id: 0.0,
    }

    exploit = _run(
        state=_state(simulations=2),
        actions=actions,
        probabilities=probabilities,
        values=values,
        config=PUCTConfig(c_puct=0.1),
    )
    explore = _run(
        state=_state(simulations=2),
        actions=actions,
        probabilities=probabilities,
        values=values,
        config=PUCTConfig(c_puct=10.0),
    )

    assert [item.selected_action_id for item in exploit.puct_receipt.simulations] == [
        action_a.action_id,
        action_a.action_id,
    ]
    assert [item.selected_action_id for item in explore.puct_receipt.simulations] == [
        action_a.action_id,
        action_b.action_id,
    ]


def test_exact_backup_statistics_use_same_orientation_without_discount_or_sign_flip():
    action_a, action_b = _action("A"), _action("B")
    evaluation = _run(
        state=_state(simulations=3),
        actions=(action_a, action_b),
        probabilities={action_a.action_id: 0.75, action_b.action_id: 0.25},
        values={action_a.action_id: -0.8, action_b.action_id: 0.8},
    )
    receipt = evaluation.puct_receipt
    root = next(node for node in receipt.nodes if node.parent_edge_id is None)
    edge_by_action = {edge.action_id: edge for edge in receipt.edges}
    leaves = tuple(item.leaf_value for item in receipt.simulations)

    assert leaves == (-0.8, 0.8, 0.8)
    assert root.visit_count == 3
    assert root.value_sum == pytest.approx(0.8)
    assert root.mean_value == pytest.approx(0.8 / 3.0)
    assert edge_by_action[action_a.action_id].value_sum == -0.8
    assert edge_by_action[action_a.action_id].mean_q == -0.8
    assert edge_by_action[action_b.action_id].value_sum == 1.6
    assert edge_by_action[action_b.action_id].mean_q == 0.8


def test_full_legal_edge_registration_is_independent_of_budget_and_zero_prior():
    actions = (_action("A"), _action("B"), _action("C"))
    state = _state(simulations=0)
    generator = _Generator()
    evaluation = _run(
        state=state,
        actions=actions,
        probabilities={
            actions[0].action_id: 1.0,
            actions[1].action_id: 0.0,
            actions[2].action_id: 0.0,
        },
        values={action.action_id: 0.0 for action in actions},
        generator=generator,
    )

    assert generator.calls == [(state.state_id, actions, len(actions))]
    assert {edge.action_id for edge in evaluation.puct_receipt.edges} == {
        action.action_id for action in actions
    }
    assert all(edge.visit_count == 0 for edge in evaluation.puct_receipt.edges)
    assert evaluation.result.selected_action is None
    assert evaluation.result.receipt.termination_reason is SearchTerminationReason.BUDGET_EXHAUSTED


def test_budget_stops_at_exact_structural_limit_without_plus_one_call():
    actions = (_action("A"), _action("B"))
    state = _state(simulations=3)
    evaluator = _Successors()
    evaluation = _run(
        state=state,
        actions=actions,
        probabilities={action.action_id: 0.5 for action in actions},
        values={action.action_id: 0.0 for action in actions},
        successors=evaluator,
    )

    assert len(evaluator.calls) == 3
    assert evaluation.result.receipt.usage == BudgetUsage(
        nodes=4,
        expansions=3,
        model_calls=3,
        tokens=300,
        cost_microusd=3000,
        wall_time_ms=30,
        max_depth_observed=1,
    )
    assert evaluation.puct_receipt.usage == evaluation.result.receipt.usage
    assert evaluation.result.receipt.termination_reason is SearchTerminationReason.BUDGET_EXHAUSTED


@pytest.mark.parametrize(
    "limit_update",
    [
        {"max_nodes": 3},
        {"max_expansions": 2},
        {"max_depth": 0},
    ],
)
def test_each_structural_budget_dimension_is_checked_before_successor_work(limit_update):
    actions = (_action("A"), _action("B"))
    budget = _budget(simulations=4, **limit_update)
    state = _state(simulations=4, budget=budget)
    evaluator = _Successors()
    evaluation = _run(
        state=state,
        actions=actions,
        probabilities={action.action_id: 0.5 for action in actions},
        values={action.action_id: 0.0 for action in actions},
        successors=evaluator,
    )

    expected = 0 if limit_update == {"max_depth": 0} else 2
    assert len(evaluator.calls) == expected
    assert len(evaluation.puct_receipt.simulations) == expected


def test_aggregate_usage_is_passed_before_each_real_observation():
    actions = (_action("A"), _action("B"))
    state = _state(simulations=3)
    evaluator = _Successors()
    _run(
        state=state,
        actions=actions,
        probabilities={action.action_id: 0.5 for action in actions},
        values={action.action_id: 0.0 for action in actions},
        successors=evaluator,
    )

    assert [call[2].nodes for call in evaluator.calls] == [1, 2, 3]
    assert [call[2].model_calls for call in evaluator.calls] == [0, 1, 2]


def test_evaluator_that_exceeds_nonstructural_budget_fails_closed():
    actions = (_action("A"),)
    budget = _budget(simulations=1, max_model_calls=0)
    state = _state(simulations=1, budget=budget)

    with pytest.raises(BudgetExceeded, match="model_calls"):
        _run(
            state=state,
            actions=actions,
            probabilities={actions[0].action_id: 1.0},
            values={actions[0].action_id: 0.0},
        )


def test_terminal_root_has_no_expansion_successor_or_fabricated_stop_selection():
    state = _state(
        simulations=2,
        phase="complete",
        terminal_status="answer_ready",
    )
    stop = LegalAction(kind=ActionKind.STOP)
    constitution = _Constitution((stop,))
    value = _Value({}, root_value=0.4)
    evaluation = asyncio.run(
        PUCTStrategy(_Unused()).evaluate(
            state,
            constitution=constitution,
            action_generator=_Unused(),
            policy_prior=_Policy({}),
            value_estimator=value,
            budget=state.budget,
        )
    )

    assert evaluation.result.selected_action is None
    assert evaluation.result.estimated_value == 0.4
    assert evaluation.result.action_statistics == ()
    assert evaluation.puct_receipt.edges == ()
    assert evaluation.puct_receipt.expanded_state_ids == ()
    assert evaluation.puct_receipt.root_value == 0.4
    assert evaluation.result.receipt.termination_reason is SearchTerminationReason.TERMINAL_STATE


def test_terminal_child_is_evaluated_once_per_selected_root_visit_but_never_expanded():
    action = _action("terminal")
    state = _state(simulations=2, budget=_budget(simulations=2, max_depth=4))
    evaluator = _Successors(terminal_actions=(action.action_id,))
    constitution = _Constitution((action,))
    evaluation = _run(
        state=state,
        actions=(action,),
        probabilities={action.action_id: 1.0},
        values={action.action_id: 0.5},
        successors=evaluator,
        constitution=constitution,
    )

    assert len(evaluator.calls) == 2
    assert all(call[0].state_id == state.state_id for call in evaluator.calls)
    assert constitution.legal_inputs == [(state.state_id, 0)]
    child_nodes = [node for node in evaluation.puct_receipt.nodes if node.parent_edge_id]
    assert child_nodes and all(node.terminal and not node.expanded for node in child_nodes)


def test_max_depth_larger_than_one_never_enables_fake_recursive_evaluation():
    actions = (_action("A"), _action("B"))
    budget = _budget(simulations=4, max_depth=9)
    state = _state(simulations=4, budget=budget)
    evaluator = _Successors()
    constitution = _Constitution(actions)
    evaluation = _run(
        state=state,
        actions=actions,
        probabilities={action.action_id: 0.5 for action in actions},
        values={action.action_id: 0.0 for action in actions},
        successors=evaluator,
        constitution=constitution,
    )

    assert {call[0].depth for call in evaluator.calls} == {0}
    assert {call[0].state_id for call in evaluator.calls} == {state.state_id}
    assert {item.successor_state_id for item in evaluation.puct_receipt.simulations}
    assert constitution.legal_inputs == [(state.state_id, 0)]
    assert evaluation.puct_receipt.maximum_safe_relative_depth == 1
    assert evaluation.result.receipt.usage.max_depth_observed == 1


@pytest.mark.parametrize(
    "transform,match",
    [
        (
            lambda outcome: outcome.model_copy(
                update={"action_id": LegalAction(kind=ActionKind.STOP).action_id}
            ),
            "action ID",
        ),
        (
            lambda outcome: outcome.model_copy(
                update={
                    "state": outcome.state.model_copy(
                        update={"parent_state_id": "wrong-parent"}
                    )
                }
            ),
            "parent",
        ),
        (
            _two_ply_successor,
            "one real ply",
        ),
        (
            lambda outcome: outcome.model_copy(
                update={"usage_delta": BudgetUsage(nodes=1, max_depth_observed=1)}
            ),
            "node and one expansion",
        ),
        (lambda outcome: "not-a-successor", "ActionSuccessor"),
    ],
)
def test_malformed_successor_fails_closed_before_value_or_continuation(transform, match):
    action = _action("A")
    value = _Value({_digest(action.action_id): 1.0})
    with pytest.raises(ContractValidationError, match=match):
        _run(
            state=_state(
                simulations=1,
                budget=_budget(simulations=1, max_depth=3),
            ),
            actions=(action,),
            probabilities={action.action_id: 1.0},
            values={action.action_id: 1.0},
            successors=_Successors(transform=transform),
            value=value,
        )
    assert value.calls == []


def test_successor_exception_invalidates_entire_search_without_synthetic_penalty():
    action = _action("A")
    evaluator = _Successors(fail=RuntimeError("transition failed"))

    with pytest.raises(RuntimeError, match="transition failed"):
        _run(
            state=_state(simulations=1),
            actions=(action,),
            probabilities={action.action_id: 1.0},
            values={action.action_id: -1.0},
            successors=evaluator,
        )
    assert len(evaluator.calls) == 1


@pytest.mark.parametrize("case", ["outside", "missing", "duplicate", "type"])
def test_expansion_edges_are_exactly_the_unique_full_hard_legal_set(case):
    actions = (_action("A"), _action("B"))
    if case == "outside":
        outputs = (actions[0], _action("C"))
    elif case == "missing":
        outputs = actions[:1]
    elif case == "duplicate":
        outputs = (actions[0], actions[0])
    else:
        outputs = ("not-an-action", "not-an-action")

    with pytest.raises(ContractValidationError):
        _run(
            state=_state(simulations=1),
            actions=actions,
            probabilities={action.action_id: 0.5 for action in actions},
            values={action.action_id: 0.0 for action in actions},
            generator=_Generator(outputs=outputs),
        )


def test_policy_cannot_insert_illegal_action_or_delete_legal_edge():
    actions = (_action("A"), _action("B"))
    illegal = _action("illegal")
    outputs = (
        ActionPrior(action_id=actions[0].action_id, probability=0.5),
        ActionPrior(action_id=illegal.action_id, probability=0.5),
    )

    with pytest.raises(ContractValidationError, match="every generated action"):
        _run(
            state=_state(simulations=1),
            actions=actions,
            probabilities={},
            values={action.action_id: 0.0 for action in actions},
            policy=_Policy(outputs=outputs),
        )


@pytest.mark.parametrize("leaf_value", [math.nan, math.inf, -1.01, 1.01, "0.5", True])
def test_leaf_value_must_be_finite_numeric_and_bounded(leaf_value):
    action = _action("A")
    with pytest.raises(ContractValidationError, match="leaf Value"):
        _run(
            state=_state(simulations=1),
            actions=(action,),
            probabilities={action.action_id: 1.0},
            values={action.action_id: leaf_value},
        )


def test_root_and_sibling_inputs_remain_immutable_and_isolated():
    actions = (_action("A"), _action("B"))
    state = _state(simulations=2)
    before = state.model_dump(mode="json")
    evaluator = _Successors()
    _run(
        state=state,
        actions=actions,
        probabilities={actions[0].action_id: 0.75, actions[1].action_id: 0.25},
        values={actions[0].action_id: -0.8, actions[1].action_id: 0.8},
        successors=evaluator,
    )

    assert state.model_dump(mode="json") == before
    assert all(call[0] is state or call[0] == state for call in evaluator.calls)
    assert evaluator.calls[0][0].state_id == evaluator.calls[1][0].state_id


def test_identical_successor_state_ids_keep_path_local_nodes_and_edge_statistics():
    actions = (_action("A"), _action("B"))
    shared_digest = _digest("shared")
    evaluation = _run(
        state=_state(simulations=2),
        actions=actions,
        probabilities={actions[0].action_id: 0.75, actions[1].action_id: 0.25},
        values={"shared": -0.8},
        successors=_Successors(shared_state=True),
        value=_Value({shared_digest: -0.8}),
    )
    receipt = evaluation.puct_receipt
    children = tuple(node for node in receipt.nodes if node.parent_edge_id is not None)

    assert len({node.node_id for node in children}) == 2
    assert len({node.state_id for node in children}) == 1
    assert receipt.duplicate_state_ids == (children[0].state_id,)
    assert len([edge for edge in receipt.edges if edge.visit_count == 1]) == 2


def test_semantic_replay_is_identical_including_tree_and_receipt_hash():
    actions = (_action("A"), _action("B"), _action("C"))
    state = _state(simulations=5)
    probabilities = {
        actions[0].action_id: 0.6,
        actions[1].action_id: 0.3,
        actions[2].action_id: 0.1,
    }
    values = {
        actions[0].action_id: -0.2,
        actions[1].action_id: 0.4,
        actions[2].action_id: 0.0,
    }

    first = _run(
        state=state,
        actions=actions,
        probabilities=probabilities,
        values=values,
    )
    second = _run(
        state=state,
        actions=tuple(reversed(actions)),
        probabilities=probabilities,
        values=values,
        generator=_Generator(outputs=tuple(reversed(actions))),
    )

    assert first == second
    assert first.result.receipt.receipt_id == second.result.receipt.receipt_id
    assert first.puct_receipt.receipt_id == second.puct_receipt.receipt_id


def test_equal_values_use_deterministic_prior_then_action_id_root_ties():
    actions = (_action("A"), _action("B"))
    probabilities = {action.action_id: 0.5 for action in actions}
    evaluation = _run(
        state=_state(simulations=2),
        actions=tuple(reversed(actions)),
        probabilities=probabilities,
        values={action.action_id: 0.0 for action in actions},
    )

    assert evaluation.result.selected_action.action_id == min(
        action.action_id for action in actions
    )


def test_root_value_is_not_used_as_action_q_when_observations_exist():
    actions = (_action("A"), _action("B"))
    value = _Value(
        {
            _digest(actions[0].action_id): -0.4,
            _digest(actions[1].action_id): 0.6,
        },
        root_value=1.0,
    )
    evaluation = _run(
        state=_state(simulations=2),
        actions=actions,
        probabilities={actions[0].action_id: 0.75, actions[1].action_id: 0.25},
        values={},
        value=value,
    )

    assert all(depth == 1 for _, depth in value.calls)
    assert evaluation.puct_receipt.root_value is None
    assert evaluation.result.estimated_value == 0.6


def test_neutral_and_heuristic_value_estimators_share_engine_and_produce_auditable_difference():
    action_clean, action_contradiction = _action("clean"), _action("contradiction")
    actions = (action_clean, action_contradiction)
    contradiction = SemanticArtifactRef(
        artifact_id="contradiction_a",
        semantic_digest=_digest("contradiction_a"),
    )
    evaluator = _Successors(
        artifact_by_action={action_contradiction.action_id: contradiction}
    )
    probabilities = {
        action_clean.action_id: 0.4,
        action_contradiction.action_id: 0.6,
    }

    neutral = _run(
        state=_state(simulations=2),
        actions=actions,
        probabilities=probabilities,
        values={},
        successors=evaluator,
        value=NeutralValueEstimator(),
    )
    heuristic = _run(
        state=_state(simulations=2),
        actions=actions,
        probabilities=probabilities,
        values={},
        successors=_Successors(
            artifact_by_action={action_contradiction.action_id: contradiction}
        ),
        value=HeuristicValueEstimator(),
    )

    assert neutral.result.selected_action == action_contradiction
    assert heuristic.result.selected_action == action_clean
    assert neutral.puct_receipt.value_estimator_id.endswith(
        "neutral-value-estimator/v0"
    )
    assert heuristic.puct_receipt.value_estimator_id.endswith(
        "heuristic-value-estimator/v0"
    )


def test_search_method_returns_canonical_result_while_evaluate_adds_rich_receipt():
    action = _action("A")
    state = _state(simulations=1)
    rich = _run(
        state=state,
        actions=(action,),
        probabilities={action.action_id: 1.0},
        values={action.action_id: 0.2},
    )
    canonical = _run(
        state=state,
        actions=(action,),
        probabilities={action.action_id: 1.0},
        values={action.action_id: 0.2},
        rich=False,
    )

    assert canonical == rich.result
    assert isinstance(rich.puct_receipt, PUCTSearchReceipt)
    assert rich.puct_receipt.search_receipt_id == canonical.receipt.receipt_id
    assert rich.puct_receipt.policy_estimator_id.endswith("fixture-policy/v0")
    assert rich.puct_receipt.value_estimator_id.endswith("fixture-value/v0")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: PUCTNode(
            node_id="node",
            state_id="state",
            terminal=False,
            expanded=False,
            visit_count=1,
            value_sum=0.5,
            mean_value=0.0,
        ),
        lambda: PUCTNode(
            node_id="node",
            state_id="state",
            terminal=True,
            expanded=True,
            visit_count=0,
            value_sum=0.0,
            mean_value=0.0,
            child_edge_ids=("edge",),
        ),
        lambda: PUCTEdge(
            edge_id="edge",
            parent_node_id="root",
            action_id="action",
            prior=0.5,
            visit_count=1,
            value_sum=0.5,
            mean_q=0.5,
        ),
        lambda: PUCTEdge(
            edge_id="edge",
            parent_node_id="root",
            action_id="action",
            prior=0.5,
            visit_count=0,
            value_sum=math.nan,
            mean_q=0.0,
        ),
    ],
)
def test_public_tree_contracts_reject_impossible_or_nonfinite_statistics(factory):
    with pytest.raises((ValidationError, ContractValidationError)):
        factory()


def test_puct_receipt_identity_and_failure_fields_are_fail_closed():
    action = _action("A")
    evaluation = _run(
        state=_state(simulations=1),
        actions=(action,),
        probabilities={action.action_id: 1.0},
        values={action.action_id: 0.2},
    )
    payload = evaluation.puct_receipt.model_dump(mode="python")
    payload["receipt_id"] = "forged"
    with pytest.raises((ValidationError, ContractValidationError), match="receipt_id"):
        PUCTSearchReceipt(**payload)

    payload = evaluation.puct_receipt.model_dump(
        mode="python", exclude={"receipt_id"}
    )
    payload["failed_action_ids"] = (action.action_id,)
    with pytest.raises(
        (ValidationError, ContractValidationError), match="entire search"
    ):
        PUCTSearchReceipt(**payload)


def test_invalid_root_or_budget_fails_before_dependencies():
    state = _state(simulations=1)
    strategy = PUCTStrategy(_Unused())
    forged = state.model_copy(update={"state_id": "forged"})

    with pytest.raises(ContractValidationError, match="valid SearchState"):
        asyncio.run(
            strategy.search(
                forged,
                constitution=_Unused(),
                action_generator=_Unused(),
                policy_prior=_Unused(),
                value_estimator=_Unused(),
                budget=state.budget,
            )
        )
    with pytest.raises(ContractValidationError, match="budget must equal"):
        asyncio.run(
            strategy.search(
                state,
                constitution=_Unused(),
                action_generator=_Unused(),
                policy_prior=_Unused(),
                value_estimator=_Unused(),
                budget=_budget(simulations=2),
            )
        )
