"""Offline call planning for the ordinary three-seat Socrates council.

The planner asks the canonical :class:`CEDOrchestrator` for its deliberation
task specifications and then accounts for the evaluator paths executed by
``run_registry_session``.  It reuses the retained topology and task-tier
declarations from the strict live modules, but never invokes their benchmark
entry points, reads a credential, or dispatches a provider request.

``base_calls`` is a conservative structural ceiling with phase retry disabled:
it assumes every deliberation slot eventually supplies one accepted move, every
synthesis draft supplies all five sections, every eligible objection is mapped,
and every seat participates in the one fail-closed ratification round.
``retry_calls``
is the separate headroom for the one currently legal same-seat CED retry.  A
successful retry replaces a failed original move, so it does not create an
additional move-score or section-score fan-out.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Sequence, Tuple

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import (
    CEDOrchestrator,
    REGISTRY_SESSION_PHASES,
    SOCRATIC_CYCLE_PHASES,
)
from backend.dialogues.hybrid_epistemic import REQUIRED_CORROBORATION
from backend.dialogues.models import (
    AgentMove,
    AgentRole,
    DialogPhase,
    SECTION_ORDER,
    ShadowScoringMode,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    FakeProvider,
    ScriptedMockProvider,
)
from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
    WORKER_PROVIDER_IDS_V1,
)
# The retained Q1 topology module owns the current endpoint/model declarations,
# but its experiment selector raises ``SystemExit`` for an unknown lab-only
# environment value at import time.  Normal does not consume that selector.  If
# and only if that exact stale-value failure occurs, load the declarations under
# ``default`` and immediately restore the caller's environment.  Valid lab
# selections remain untouched, and Normal still selects the explicit default
# set below rather than the module's experiment-selected set.
try:
    _current_topology = importlib.import_module("scripts.run_multimodel_q1_v1")
except SystemExit as exc:
    _seat_environment_name = "SOCRATES_COUNCIL_SEATS"
    _seat_environment_value = os.environ.get(_seat_environment_name)
    if (
        not isinstance(exc.code, str)
        or not exc.code.startswith("unknown council seat set ")
        or _seat_environment_value is None
    ):
        raise
    os.environ[_seat_environment_name] = "default"
    try:
        _current_topology = importlib.import_module(
            "scripts.run_multimodel_q1_v1"
        )
    finally:
        os.environ[_seat_environment_name] = _seat_environment_value

COUNCIL_SEAT_SETS_V1 = _current_topology.COUNCIL_SEAT_SETS_V1
FAMILIES_V1 = _current_topology.FAMILIES_V1

from scripts.run_multimodel_q1_ced_v1 import (  # noqa: E402
    GPT5_MINI_INITIAL_RESPONSE_OUTPUT_TOKENS_V1,
)
from scripts.run_socrates_live_v1 import (
    NORMAL_OUTPUT_LIMIT_BY_TASK_KIND_V1,
    REVISION_OUTPUT_TOKENS_V1,
    SHORT_OUTPUT_TOKENS_V1,
    SYNTHESIS_OUTPUT_TOKENS_V1,
)


SHORT_OUTPUT_TOKENS = SHORT_OUTPUT_TOKENS_V1
REVISION_OUTPUT_TOKENS = REVISION_OUTPUT_TOKENS_V1
GPT5_INITIAL_RESPONSE_OUTPUT_TOKENS = (
    GPT5_MINI_INITIAL_RESPONSE_OUTPUT_TOKENS_V1
)
SYNTHESIS_OUTPUT_TOKENS = SYNTHESIS_OUTPUT_TOKENS_V1

GPT5_MINI_MODEL_ID = FAMILIES_V1["gpt_5_mini"]["model"]

_COMMON_OUTPUT_LIMITS: Tuple[Tuple[TaskKind, int], ...] = tuple(
    NORMAL_OUTPUT_LIMIT_BY_TASK_KIND_V1.items()
)


class NormalPlanningError(ValueError):
    """The executable CED shape cannot be conservatively planned."""


@dataclass(frozen=True)
class NormalSeat:
    """One physical, model-pinned council seat and its output-tier exceptions."""

    alias: str
    provider_id: str
    model_id: str
    policy_key: str
    task_output_overrides: Tuple[Tuple[TaskKind, int], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.alias.strip()
            or not self.provider_id.strip()
            or not self.model_id.strip()
            or not self.policy_key.strip()
        ):
            raise NormalPlanningError("normal seat identity fields must be nonblank")
        kinds = [kind for kind, _limit in self.task_output_overrides]
        if len(kinds) != len(set(kinds)):
            raise NormalPlanningError(f"duplicate output override on seat {self.alias!r}")
        if any(type(limit) is not int or limit <= 0 for _kind, limit in self.task_output_overrides):
            raise NormalPlanningError(f"invalid output override on seat {self.alias!r}")

    def output_limit_for(self, task_kind: TaskKind) -> int:
        overrides = dict(self.task_output_overrides)
        if task_kind in overrides:
            return overrides[task_kind]
        try:
            return dict(_COMMON_OUTPUT_LIMITS)[task_kind]
        except KeyError as exc:
            raise NormalPlanningError(
                f"no Normal output tier for task kind {task_kind.value!r}"
            ) from exc


def _trusted_output_limit(policy_key: str, task_kind: TaskKind) -> int:
    """Apply the two retained GPT-5 exceptions over the shared task tiers.

    The values come from the current strict-policy modules.  Keeping the tiny
    selector here prevents the experiment-only ``SOCRATES_COUNCIL_SEATS``
    environment switch from changing Normal's explicit default topology.
    """

    if (
        policy_key == "gpt_5_mini"
        and task_kind is TaskKind.INITIAL_RESPONSE
    ):
        return GPT5_MINI_INITIAL_RESPONSE_OUTPUT_TOKENS_V1
    if (
        policy_key == "gpt_5_mini"
        and task_kind is TaskKind.ELENCHUS_OBJECTION
    ):
        return REVISION_OUTPUT_TOKENS_V1
    try:
        return dict(_COMMON_OUTPUT_LIMITS)[task_kind]
    except KeyError as exc:
        raise NormalPlanningError(
            f"no trusted output policy for task kind {task_kind.value!r}"
        ) from exc


def _build_default_normal_seats() -> Tuple[NormalSeat, ...]:
    """Derive the Normal topology and task tiers from the trusted live policy."""

    topology = tuple(COUNCIL_SEAT_SETS_V1["default"])
    provider_ids = tuple(WORKER_PROVIDER_IDS_V1[: len(topology)])
    if len(topology) != 3 or len(provider_ids) != len(topology):
        raise NormalPlanningError("trusted Normal topology is not exactly three seats")

    seats = []
    common = dict(_COMMON_OUTPUT_LIMITS)
    for (alias, policy_key), provider_id in zip(
        topology, provider_ids, strict=True
    ):
        family = FAMILIES_V1[policy_key]
        overrides = []
        for task_kind, common_limit in _COMMON_OUTPUT_LIMITS:
            trusted_limit = _trusted_output_limit(policy_key, task_kind)
            if trusted_limit != common_limit:
                overrides.append((task_kind, trusted_limit))
        seat = NormalSeat(
            alias=alias,
            provider_id=provider_id,
            model_id=family["model"],
            policy_key=policy_key,
            task_output_overrides=tuple(overrides),
        )
        for task_kind in common:
            if seat.output_limit_for(task_kind) != _trusted_output_limit(
                policy_key, task_kind
            ):
                raise NormalPlanningError(
                    f"Normal output policy drifted for {alias} / {task_kind.value}"
                )
        seats.append(seat)
    return tuple(seats)


DEFAULT_NORMAL_SEATS: Tuple[NormalSeat, ...] = _build_default_normal_seats()


@dataclass(frozen=True)
class PlannedCall:
    """One provider dispatch in a conservative Normal call allocation."""

    stage: str
    task_kind: TaskKind
    seat_alias: str
    provider_id: str
    model_id: str
    output_limit_tokens: int
    logical_agent_id: Optional[str]
    role: AgentRole
    phase: DialogPhase
    round_index: int
    slot_index: Optional[int]
    attempt_index: int = 0
    conditional_reason: Optional[str] = None


@dataclass(frozen=True)
class NormalCallPlan:
    """Immutable call allocation suitable for a separate cost preflight."""

    session_id: str
    max_socratic_followups: int
    completed_socratic_cycles: int
    seats: Tuple[NormalSeat, ...]
    agent_to_seat: Tuple[Tuple[str, str], ...]
    base_calls: Tuple[PlannedCall, ...]
    retry_calls: Tuple[PlannedCall, ...]
    boundary_notes: Tuple[str, ...]

    @property
    def base_call_count(self) -> int:
        return len(self.base_calls)

    @property
    def retry_call_count(self) -> int:
        return len(self.retry_calls)

    @property
    def maximum_call_count(self) -> int:
        return self.base_call_count + self.retry_call_count

    def stage_counts(self, *, include_retries: bool = True) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        calls = self.base_calls + (self.retry_calls if include_retries else ())
        for call in calls:
            counts[call.stage] = counts.get(call.stage, 0) + 1
        return dict(sorted(counts.items()))

    def calls_by_seat_and_output_limit(
        self, *, include_retries: bool = True
    ) -> Dict[str, Dict[int, int]]:
        counts: Dict[str, Dict[int, int]] = {seat.alias: {} for seat in self.seats}
        calls = self.base_calls + (self.retry_calls if include_retries else ())
        for call in calls:
            by_limit = counts[call.seat_alias]
            by_limit[call.output_limit_tokens] = (
                by_limit.get(call.output_limit_tokens, 0) + 1
            )
        return {
            alias: dict(sorted(by_limit.items()))
            for alias, by_limit in counts.items()
        }

    def to_preflight_dict(self) -> Dict[str, object]:
        base = self.calls_by_seat_and_output_limit(include_retries=False)
        maximum = self.calls_by_seat_and_output_limit(include_retries=True)
        retry: Dict[str, Dict[int, int]] = {seat.alias: {} for seat in self.seats}
        for call in self.retry_calls:
            by_limit = retry[call.seat_alias]
            by_limit[call.output_limit_tokens] = by_limit.get(call.output_limit_tokens, 0) + 1

        def json_limits(value: Mapping[str, Mapping[int, int]]) -> Dict[str, Dict[str, int]]:
            return {
                alias: {str(limit): count for limit, count in sorted(counts.items())}
                for alias, counts in value.items()
            }

        return {
            "schema_version": "normal-socrates-call-plan/v1",
            "session_id": self.session_id,
            "max_socratic_followups": self.max_socratic_followups,
            "completed_socratic_cycles": self.completed_socratic_cycles,
            "topology": [
                {
                    "alias": seat.alias,
                    "provider_id": seat.provider_id,
                    "model_id": seat.model_id,
                    "policy_key": seat.policy_key,
                }
                for seat in self.seats
            ],
            "logical_agent_to_seat": dict(self.agent_to_seat),
            "base_calls": self.base_call_count,
            "same_seat_retry_calls": self.retry_call_count,
            "maximum_calls": self.maximum_call_count,
            "stage_calls": self.stage_counts(),
            "calls_by_seat_and_output_limit": {
                "base": json_limits(base),
                "same_seat_retry": json_limits(retry),
                "maximum": json_limits(maximum),
            },
            "output_limit_by_seat_and_task_kind": {
                seat.alias: {
                    kind.value: seat.output_limit_for(kind)
                    for kind, _limit in _COMMON_OUTPUT_LIMITS
                }
                for seat in self.seats
            },
            "boundary_notes": list(self.boundary_notes),
        }


@dataclass(frozen=True)
class CostAllocation:
    seat_alias: str
    output_limit_tokens: int
    base_count: int
    retry_count: int
    maximum_count: int
    per_call_bound_picodollars: int
    maximum_cost_picodollars: int


@dataclass(frozen=True)
class NormalCostPreflight:
    base_cost_picodollars: int
    retry_cost_picodollars: int
    maximum_cost_picodollars: int
    allocations: Tuple[CostAllocation, ...]


def price_normal_call_plan(
    plan: NormalCallPlan,
    per_call_bound_picodollars: Mapping[str, Mapping[int, int]],
) -> NormalCostPreflight:
    """Multiply the plan by caller-supplied, seat/tier-specific price bounds."""

    base = plan.calls_by_seat_and_output_limit(include_retries=False)
    maximum = plan.calls_by_seat_and_output_limit(include_retries=True)
    allocations = []
    base_total = 0
    retry_total = 0
    for seat in plan.seats:
        limits = sorted(set(base[seat.alias]) | set(maximum[seat.alias]))
        seat_prices = per_call_bound_picodollars.get(seat.alias)
        if seat_prices is None:
            raise NormalPlanningError(f"missing price bounds for seat {seat.alias!r}")
        for limit in limits:
            price = seat_prices.get(limit)
            if type(price) is not int or price < 0:
                raise NormalPlanningError(
                    f"missing or invalid price bound for {seat.alias!r} at {limit} tokens"
                )
            base_count = base[seat.alias].get(limit, 0)
            maximum_count = maximum[seat.alias].get(limit, 0)
            retry_count = maximum_count - base_count
            base_cost = base_count * price
            retry_cost = retry_count * price
            base_total += base_cost
            retry_total += retry_cost
            allocations.append(CostAllocation(
                seat_alias=seat.alias,
                output_limit_tokens=limit,
                base_count=base_count,
                retry_count=retry_count,
                maximum_count=maximum_count,
                per_call_bound_picodollars=price,
                maximum_cost_picodollars=base_cost + retry_cost,
            ))
    return NormalCostPreflight(
        base_cost_picodollars=base_total,
        retry_cost_picodollars=retry_total,
        maximum_cost_picodollars=base_total + retry_total,
        allocations=tuple(allocations),
    )


def _validate_topology(seats: Sequence[NormalSeat], agent_ids: Sequence[str]) -> None:
    if len(seats) < REQUIRED_CORROBORATION + 1:
        raise NormalPlanningError(
            "Normal governing verification requires three model-distinct seats"
        )
    if len(seats) != len(agent_ids):
        raise NormalPlanningError("Normal planning requires one logical agent per seat")
    for label, values in (
        ("seat alias", [seat.alias for seat in seats]),
        ("provider id", [seat.provider_id for seat in seats]),
        ("model id", [seat.model_id for seat in seats]),
        ("logical agent id", list(agent_ids)),
    ):
        if len(values) != len(set(values)):
            raise NormalPlanningError(f"Normal {label}s must be unique")


def derive_normal_call_plan(
    *,
    session_id: str = "normal-socrates-plan-v1",
    seats: Sequence[NormalSeat] = DEFAULT_NORMAL_SEATS,
    logical_agent_ids: Optional[Sequence[str]] = None,
    max_socratic_followups: int = 2,
    completed_socratic_cycles: Optional[int] = None,
    phase_retry: bool = True,
    ratification_repair: str = "block",
    mid_round_objection_rulings: bool = True,
) -> NormalCallPlan:
    """Derive the current full-CED structural call ceiling without dispatching.

    Role holders and ordinary task kinds come directly from
    ``canonical_registry_task_specs`` for ``session_id``.  Evaluator fan-outs
    mirror the explicit loops in ``run_registry_session`` and fail closed if the
    surrounding canonical phase shape changes.
    """

    if not isinstance(session_id, str) or not session_id.strip():
        raise NormalPlanningError("normal planning session_id must be nonblank")
    seats = tuple(seats)
    agent_ids = tuple(logical_agent_ids or (
        f"agent_{index}" for index in range(len(seats))
    ))
    _validate_topology(seats, agent_ids)
    if type(max_socratic_followups) is not int or max_socratic_followups < 1:
        raise NormalPlanningError("Normal planning requires at least one Socratic follow-up")
    completed_cycles = (
        max_socratic_followups
        if completed_socratic_cycles is None
        else completed_socratic_cycles
    )
    if (
        type(completed_cycles) is not int
        or completed_cycles < 1
        or completed_cycles > max_socratic_followups
    ):
        raise NormalPlanningError(
            "completed Socratic cycles must be within the configured maximum"
        )
    if ratification_repair != "block":
        raise NormalPlanningError(
            "Normal execution requires fail-closed ratification_repair='block'"
        )
    expected_phases = (
        DialogPhase.OPENING,
        DialogPhase.INITIAL_RESPONSE,
        DialogPhase.ELENCHUS,
        DialogPhase.REFLECTION,
        DialogPhase.RECONSTRUCTION,
        DialogPhase.SYNTHESIS,
    )
    if tuple(REGISTRY_SESSION_PHASES) != expected_phases:
        raise NormalPlanningError("canonical registry phase shape changed")
    if tuple(SOCRATIC_CYCLE_PHASES) != (
        DialogPhase.ELENCHUS,
        DialogPhase.REFLECTION,
    ):
        raise NormalPlanningError("canonical Socratic cycle shape changed")

    registry = CouncilProviderRegistry()
    for seat in seats:
        registry.register(ScriptedMockProvider(
            provider_id=seat.provider_id,
            model_id=seat.model_id,
        ))
    fake = FakeProvider()
    agents = [SocraticAgent(agent_id, fake) for agent_id in agent_ids]
    ced = CEDOrchestrator(
        agents,
        fake,
        registry=registry,
        shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
        assembly_fallback=False,
        ai_learning=False,
        ratification_repair=ratification_repair,
        phase_retry=phase_retry,
        max_socratic_followups=max_socratic_followups,
        tree_expansions=0,
    )
    state = ced.create_session("Normal offline call-plan proof", session_id=session_id)

    # There is no public binding-plan accessor yet.  Resolve the exact frozen
    # CED mapping without running an adapter, then make that boundary explicit in
    # the returned plan rather than silently reconstructing it by seat order.
    ced._bind_session_adapters(state)
    bindings = ced._session_adapter_bindings.get(state.session_id, {})
    seats_by_provider = {seat.provider_id: seat for seat in seats}
    agent_to_seat: Dict[str, NormalSeat] = {}
    for agent_id in agent_ids:
        adapter = bindings.get(agent_id)
        if adapter is None or adapter.provider_id not in seats_by_provider:
            raise NormalPlanningError("canonical session binding could not be derived")
        agent_to_seat[agent_id] = seats_by_provider[adapter.provider_id]
    if len({seat.alias for seat in agent_to_seat.values()}) != len(seats):
        raise NormalPlanningError("canonical binding is not one logical agent per seat")

    base_calls = []

    def append_call(
        *, stage: str, task_kind: TaskKind, seat: NormalSeat,
        logical_agent_id: Optional[str], phase: DialogPhase, round_index: int,
        role: AgentRole = AgentRole.FINAL_EVALUATOR,
        slot_index: Optional[int] = None,
        attempt_index: int = 0, conditional_reason: Optional[str] = None,
    ) -> None:
        base_calls.append(PlannedCall(
            stage=stage,
            task_kind=task_kind,
            seat_alias=seat.alias,
            provider_id=seat.provider_id,
            model_id=seat.model_id,
            output_limit_tokens=seat.output_limit_for(task_kind),
            logical_agent_id=logical_agent_id,
            role=role,
            phase=phase,
            round_index=round_index,
            slot_index=slot_index,
            attempt_index=attempt_index,
            conditional_reason=conditional_reason,
        ))

    def append_specs(phase: DialogPhase, round_index: int):
        specs = ced.canonical_registry_task_specs(
            state, phase, round_index=round_index
        )
        for spec in specs:
            append_call(
                stage="deliberation",
                task_kind=spec.task_kind,
                seat=agent_to_seat[spec.agent_id],
                logical_agent_id=spec.agent_id,
                role=spec.role,
                phase=spec.phase,
                round_index=round_index,
                slot_index=spec.slot_index,
            )
        return specs

    append_specs(DialogPhase.OPENING, 0)
    initial_specs = append_specs(DialogPhase.INITIAL_RESPONSE, 0)
    if {spec.agent_id for spec in initial_specs} != set(agent_ids):
        raise NormalPlanningError("current initial-response phase is not full-council")
    for spec in initial_specs:
        seat = agent_to_seat[spec.agent_id]
        state.moves.append(AgentMove(
            task_id=f"normal_plan_initial_{spec.slot_index}",
            agent_id=spec.agent_id,
            role=spec.role,
            phase=DialogPhase.INITIAL_RESPONSE,
            content={"commitments": [f"normal plan claim {spec.slot_index}"]},
            task_kind=TaskKind.INITIAL_RESPONSE,
            provider_id=seat.provider_id,
        ))
    for round_index in range(completed_cycles):
        append_specs(DialogPhase.ELENCHUS, round_index)
        append_specs(DialogPhase.REFLECTION, round_index)
    final_round = completed_cycles - 1
    append_specs(DialogPhase.RECONSTRUCTION, final_round)
    append_specs(DialogPhase.SYNTHESIS, final_round)

    deliberation = tuple(base_calls)
    retry_calls = tuple(
        PlannedCall(
            stage="same_seat_phase_retry",
            task_kind=call.task_kind,
            seat_alias=call.seat_alias,
            provider_id=call.provider_id,
            model_id=call.model_id,
            output_limit_tokens=call.output_limit_tokens,
            logical_agent_id=call.logical_agent_id,
            role=call.role,
            phase=call.phase,
            round_index=call.round_index,
            slot_index=call.slot_index,
            attempt_index=1,
            conditional_reason="original deliberation slot was canonically rejected",
        )
        for call in deliberation
    ) if phase_retry else ()

    seats_by_alias = {seat.alias: seat for seat in seats}
    agent_by_seat = {seat.alias: agent_id for agent_id, seat in agent_to_seat.items()}

    def peer_seats(producer: NormalSeat) -> Tuple[NormalSeat, ...]:
        return tuple(seat for seat in seats if seat.provider_id != producer.provider_id)

    def model_distinct_peers(producer: NormalSeat) -> Tuple[NormalSeat, ...]:
        return tuple(seat for seat in seats if seat.model_id != producer.model_id)

    # Move scoring: one accepted move at most per canonical deliberation slot,
    # even when the accepted move comes from attempt 1.
    for call in deliberation:
        producer = seats_by_alias[call.seat_alias]
        for voter in peer_seats(producer):
            append_call(
                stage="move_score",
                task_kind=TaskKind.MOVE_SCORE,
                seat=voter,
                logical_agent_id=None,
                phase=call.phase,
                round_index=call.round_index,
                conditional_reason="deliberation slot supplied an accepted move",
            )

    synthesis_calls = [
        call for call in deliberation if call.task_kind is TaskKind.SYNTHESIS_DRAFT
    ]
    for call in synthesis_calls:
        producer = seats_by_alias[call.seat_alias]
        for voter in peer_seats(producer):
            for _section in SECTION_ORDER:
                append_call(
                    stage="section_score",
                    task_kind=TaskKind.SECTION_SCORE,
                    seat=voter,
                    logical_agent_id=None,
                    phase=DialogPhase.SYNTHESIS,
                    round_index=call.round_index,
                    conditional_reason="synthesis draft supplied a nonempty section",
                )

    objection_calls = [
        call for call in deliberation
        if call.task_kind is TaskKind.ELENCHUS_OBJECTION
    ]
    if mid_round_objection_rulings:
        for call in objection_calls:
            raiser = seats_by_alias[call.seat_alias]
            for voter in model_distinct_peers(raiser):
                append_call(
                    stage="mid_round_objection_ruling",
                    task_kind=TaskKind.OBJECTION_VERIFICATION,
                    seat=voter,
                    logical_agent_id=agent_by_seat[voter.alias],
                    phase=DialogPhase.ELENCHUS,
                    round_index=call.round_index,
                    conditional_reason="accepted elenchus move stated a ruleable objection",
                )

    ratification_rounds = 1
    for round_index in range(ratification_rounds):
        for seat in seats:
            append_call(
                stage="ratification",
                task_kind=TaskKind.COUNCIL_RATIFICATION,
                seat=seat,
                logical_agent_id=None,
                phase=DialogPhase.RATIFICATION,
                round_index=round_index,
                conditional_reason=None,
            )

    # Governing verification may see every mapped elenchus objection plus one
    # final-round critical objection from every ratifier.  Earlier repair-round
    # objections are not projected by the current final-response path.
    governing_raisers = [seats_by_alias[call.seat_alias] for call in objection_calls]
    governing_raisers.extend(seats)
    for raiser in governing_raisers:
        peers = model_distinct_peers(raiser)
        if len(peers) < REQUIRED_CORROBORATION:
            continue
        for verifier in peers:
            append_call(
                stage="governing_objection_verification",
                task_kind=TaskKind.OBJECTION_VERIFICATION,
                seat=verifier,
                logical_agent_id=None,
                phase=DialogPhase.ELENCHUS,
                round_index=final_round,
                conditional_reason="objection was explicitly mapped to an assembled claim",
            )

    return NormalCallPlan(
        session_id=session_id,
        max_socratic_followups=max_socratic_followups,
        completed_socratic_cycles=completed_cycles,
        seats=seats,
        agent_to_seat=tuple(
            (agent_id, agent_to_seat[agent_id].alias) for agent_id in agent_ids
        ),
        base_calls=tuple(base_calls),
        retry_calls=retry_calls,
        boundary_notes=(
            "CED exposes ordinary task specs but not a public evaluator dry-run plan; "
            "evaluator cardinalities mirror the current explicit registry loops.",
            "The base ceiling assumes accepted moves, five nonempty synthesis sections, "
            "all eligible mapped objections, and one fail-closed ratification round.",
            "Provider-transport retries are excluded; the live execution policies must "
            "retain zero automatic retries.",
            "The production authorization validates every legal one- or two-cycle "
            "early-stop branch against this maximum-cycle call and cost ceiling.",
        ),
    )


__all__ = [
    "DEFAULT_NORMAL_SEATS",
    "GPT5_INITIAL_RESPONSE_OUTPUT_TOKENS",
    "GPT5_MINI_MODEL_ID",
    "NormalCallPlan",
    "NormalCostPreflight",
    "NormalPlanningError",
    "NormalSeat",
    "PlannedCall",
    "REVISION_OUTPUT_TOKENS",
    "SHORT_OUTPUT_TOKENS",
    "SYNTHESIS_OUTPUT_TOKENS",
    "derive_normal_call_plan",
    "price_normal_call_plan",
]
