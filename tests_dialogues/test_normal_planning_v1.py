"""Offline contract tests for the ordinary Normal Socrates call planner."""

from __future__ import annotations

import pytest

from backend.dialogues.models import TaskKind
from socrates.planning import (
    DEFAULT_NORMAL_SEATS,
    GPT5_INITIAL_RESPONSE_OUTPUT_TOKENS,
    NormalPlanningError,
    NormalSeat,
    REVISION_OUTPUT_TOKENS,
    derive_normal_call_plan,
    price_normal_call_plan,
)


def test_default_topology_is_exactly_three_model_distinct_one_to_one_seats() -> None:
    plan = derive_normal_call_plan(session_id="normal-topology-proof")

    assert [seat.alias for seat in plan.seats] == ["Alpha", "Beta", "Gamma"]
    assert len({seat.provider_id for seat in plan.seats}) == 3
    assert len({seat.model_id for seat in plan.seats}) == 3
    assert [seat.provider_id for seat in plan.seats] == [
        "worker_alpha",
        "worker_beta",
        "worker_gamma",
    ]
    assert [seat.policy_key for seat in plan.seats] == [
        "gpt_5_mini",
        "gemini_3_7_flash_standard",
        "gpt_4_1_mini",
    ]
    assert plan.agent_to_seat == (
        ("agent_0", "Alpha"),
        ("agent_1", "Beta"),
        ("agent_2", "Gamma"),
    )


def test_current_full_ced_plan_derives_base_retry_and_maximum_calls() -> None:
    plan = derive_normal_call_plan(session_id="normal-current-call-proof")

    assert plan.stage_counts() == {
        "deliberation": 20,
        "governing_objection_verification": 14,
        "mid_round_objection_ruling": 8,
        "move_score": 40,
        "ratification": 3,
        "same_seat_phase_retry": 20,
        "section_score": 30,
    }
    assert plan.base_call_count == 115
    assert plan.retry_call_count == 20
    assert plan.maximum_call_count == 135
    assert plan.maximum_call_count != 235


def test_one_cycle_early_stop_is_a_separate_authorized_execution_branch() -> None:
    early = derive_normal_call_plan(
        session_id="normal-early-stop-proof",
        max_socratic_followups=2,
        completed_socratic_cycles=1,
    )
    maximum = derive_normal_call_plan(
        session_id="normal-early-stop-proof",
        max_socratic_followups=2,
        completed_socratic_cycles=2,
    )

    assert (
        early.base_call_count,
        early.retry_call_count,
        early.maximum_call_count,
    ) == (89, 14, 103)
    assert early.maximum_call_count < maximum.maximum_call_count
    assert {
        call.round_index
        for call in early.base_calls
        if call.task_kind in {
            TaskKind.RECONSTRUCTION_PROPOSAL,
            TaskKind.SYNTHESIS_DRAFT,
        }
    } == {0}
    assert {
        call.round_index
        for call in maximum.base_calls
        if call.task_kind in {
            TaskKind.RECONSTRUCTION_PROPOSAL,
            TaskKind.SYNTHESIS_DRAFT,
        }
    } == {1}


def test_normal_planning_refuses_runner_up_reratification() -> None:
    with pytest.raises(NormalPlanningError, match="ratification_repair='block'"):
        derive_normal_call_plan(ratification_repair="runner_up")


def test_deliberation_kinds_come_from_the_current_canonical_phase_specs() -> None:
    plan = derive_normal_call_plan(session_id="normal-task-spec-proof")
    deliberation = [call for call in plan.base_calls if call.stage == "deliberation"]
    counts = {
        kind: sum(call.task_kind is kind for call in deliberation)
        for kind in (
            TaskKind.SOCRATIC_QUESTION,
            TaskKind.INITIAL_RESPONSE,
            TaskKind.ELENCHUS_OBJECTION,
            TaskKind.REFLECTION_REVISION,
            TaskKind.RECONSTRUCTION_PROPOSAL,
            TaskKind.SYNTHESIS_DRAFT,
        )
    }

    assert counts == {
        TaskKind.SOCRATIC_QUESTION: 3,
        TaskKind.INITIAL_RESPONSE: 3,
        TaskKind.ELENCHUS_OBJECTION: 4,
        TaskKind.REFLECTION_REVISION: 6,
        TaskKind.RECONSTRUCTION_PROPOSAL: 1,
        TaskKind.SYNTHESIS_DRAFT: 3,
    }


def test_every_legal_retry_is_once_at_the_original_logical_and_physical_seat() -> None:
    plan = derive_normal_call_plan(session_id="normal-same-seat-proof")
    originals = [call for call in plan.base_calls if call.stage == "deliberation"]

    assert len(plan.retry_calls) == len(originals)
    for original, retry in zip(originals, plan.retry_calls):
        assert retry.attempt_index == 1
        assert original.attempt_index == 0
        assert retry.logical_agent_id == original.logical_agent_id
        assert retry.role is original.role
        assert retry.seat_alias == original.seat_alias
        assert retry.provider_id == original.provider_id
        assert retry.model_id == original.model_id
        assert retry.task_kind is original.task_kind
        assert retry.phase is original.phase
        assert retry.round_index == original.round_index
        assert retry.slot_index == original.slot_index
        assert retry.output_limit_tokens == original.output_limit_tokens


def test_gpt5_initial_response_uses_14k_for_original_and_same_seat_retry() -> None:
    alpha = DEFAULT_NORMAL_SEATS[0]
    assert alpha.output_limit_for(TaskKind.INITIAL_RESPONSE) == (
        GPT5_INITIAL_RESPONSE_OUTPUT_TOKENS
    )
    assert alpha.output_limit_for(TaskKind.ELENCHUS_OBJECTION) == REVISION_OUTPUT_TOKENS

    plan = derive_normal_call_plan(session_id="normal-gpt5-tier-proof")
    alpha_initial = [
        call for call in plan.base_calls + plan.retry_calls
        if call.seat_alias == "Alpha" and call.task_kind is TaskKind.INITIAL_RESPONSE
    ]
    assert [(call.attempt_index, call.output_limit_tokens) for call in alpha_initial] == [
        (0, 14_000),
        (1, 14_000),
    ]


@pytest.mark.parametrize("session_id", ["normal-role-a", "normal-role-b", "normal-role-c"])
def test_role_rotation_may_move_task_tiers_but_never_changes_call_ceiling(
    session_id: str,
) -> None:
    plan = derive_normal_call_plan(session_id=session_id)
    assert (plan.base_call_count, plan.retry_call_count, plan.maximum_call_count) == (
        115,
        20,
        135,
    )
    assert sum(
        count
        for counts in plan.calls_by_seat_and_output_limit().values()
        for count in counts.values()
    ) == 135


def test_preflight_payload_exposes_separate_base_retry_and_maximum_allocations() -> None:
    payload = derive_normal_call_plan(session_id="normal-preflight-proof").to_preflight_dict()

    assert payload["base_calls"] == 115
    assert payload["same_seat_retry_calls"] == 20
    assert payload["maximum_calls"] == 135
    allocations = payload["calls_by_seat_and_output_limit"]
    assert allocations["base"]["Alpha"]["14000"] == 1
    assert allocations["same_seat_retry"]["Alpha"]["14000"] == 1
    assert allocations["maximum"]["Alpha"]["14000"] == 2


def test_cost_preflight_prices_every_seat_tier_including_retry_headroom() -> None:
    plan = derive_normal_call_plan(session_id="normal-price-proof")
    maximum = plan.calls_by_seat_and_output_limit()
    prices = {
        seat.alias: {limit: 100 + limit for limit in maximum[seat.alias]}
        for seat in plan.seats
    }

    priced = price_normal_call_plan(plan, prices)
    expected = sum(
        count * prices[alias][limit]
        for alias, counts in maximum.items()
        for limit, count in counts.items()
    )
    assert priced.maximum_cost_picodollars == expected
    assert priced.maximum_cost_picodollars == (
        priced.base_cost_picodollars + priced.retry_cost_picodollars
    )
    assert sum(allocation.maximum_count for allocation in priced.allocations) == 135


def test_cost_preflight_fails_closed_when_one_reachable_tier_is_unpriced() -> None:
    plan = derive_normal_call_plan(session_id="normal-price-refusal-proof")
    maximum = plan.calls_by_seat_and_output_limit()
    prices = {
        seat.alias: {limit: 1 for limit in maximum[seat.alias]}
        for seat in plan.seats
    }
    del prices["Alpha"][14_000]

    with pytest.raises(NormalPlanningError, match="14000"):
        price_normal_call_plan(plan, prices)


def test_non_distinct_or_non_one_to_one_topology_is_refused() -> None:
    duplicate_model = NormalSeat(
        alias="Delta",
        provider_id="normal_delta",
        model_id=DEFAULT_NORMAL_SEATS[0].model_id,
        policy_key="duplicate_model_probe",
    )
    with pytest.raises(NormalPlanningError, match="model ids must be unique"):
        derive_normal_call_plan(
            seats=(DEFAULT_NORMAL_SEATS[0], DEFAULT_NORMAL_SEATS[1], duplicate_model)
        )
    with pytest.raises(NormalPlanningError, match="one logical agent per seat"):
        derive_normal_call_plan(logical_agent_ids=("agent_0", "agent_1"))
