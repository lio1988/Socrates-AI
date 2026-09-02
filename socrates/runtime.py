"""Normal Socrates preflight, strict runtime construction, and safe artifacts.

This module is deliberately a thin boundary around the repository's canonical
``CEDOrchestrator.run_registry_session`` path.  It owns ordinary-user identity,
cost authorization, progress, strict adapter construction, and selective
projection only; it contains no dialogue or release decision logic.

Importing it performs no credential read and no network request.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import uuid
from collections import Counter
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Lock
from typing import Any, Callable, ContextManager, Dict, Mapping, Optional, Sequence, Tuple

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    AgentState,
    AgentTask,
    DialogPhase,
    ShadowScoringMode,
    TaskKind,
)
from backend.dialogues.provider_registry import CouncilProviderRegistry, FakeProvider
from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
    ced_structured_response_format_v1,
    validate_ced_structured_output_v1,
)
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    SocratesLiveOpenRouterAdapter,
    safe_public_exception_code_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    PICODOLLARS_PER_USD,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterRenderedTurnV1,
    OpenRouterSessionLedgerV1,
    conservative_turn_cost_bound_v1,
)
from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
    REDUCED_SEED_V1,
    make_worker_payload_projector_v1,
)
from backend.dialogues.socrates_zero.openrouter_request_bounds_v1 import (
    EstimatorUnsupportedError,
    RequestBoundError,
    assert_request_within_bounds_v1,
    measure_request_v1,
)
from scripts import run_multimodel_q1_ced_v1 as current_policy
from scripts import run_multimodel_q1_v1 as current_topology

from .planning import (
    DEFAULT_NORMAL_SEATS,
    NormalCallPlan,
    NormalCostPreflight,
    NormalPlanningError,
    SYNTHESIS_OUTPUT_TOKENS,
    derive_normal_call_plan,
    price_normal_call_plan,
)
from .rendering import (
    NormalRenderResult,
    render_normal_response,
)


NORMAL_PREFLIGHT_SCHEMA_VERSION = "normal-socrates-preflight/v1"
NORMAL_RESULT_SCHEMA_VERSION = "normal-socrates-result/v1"
NORMAL_REFUSAL_SCHEMA_VERSION = "normal-socrates-request-refusal/v1"
DEFAULT_STANDING_CAP_USD = "25.00"
STANDING_CAP_ENVIRONMENT_VARIABLE = "SOCRATES_MAX_RUN_USD"
PREDISPATCH_DEBUG_ENVIRONMENT_VARIABLE = "SOCRATES_DEBUG_PREDISPATCH"
NORMAL_PROMPT_BUDGET_TOKENS = (
    current_policy.EXPERIMENT_PROMPT_BUDGET_TOKENS_V1
)
NORMAL_MAX_SOCRATIC_FOLLOWUPS = 2
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = REPOSITORY_ROOT / "runs" / "normal"

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_ORDINARY_TASK_KINDS = frozenset(
    {
        TaskKind.SOCRATIC_QUESTION,
        TaskKind.INITIAL_RESPONSE,
        TaskKind.ELENCHUS_OBJECTION,
        TaskKind.REFLECTION_REVISION,
        TaskKind.RECONSTRUCTION_PROPOSAL,
        TaskKind.SYNTHESIS_DRAFT,
    }
)
_PROVIDER_OWNED_TASK_KINDS = frozenset(
    {
        TaskKind.MOVE_SCORE,
        TaskKind.SECTION_SCORE,
        TaskKind.COUNCIL_RATIFICATION,
    }
)


class NormalSocratesError(RuntimeError):
    """Base error for the Normal user boundary."""


class NormalAuthorizationError(NormalSocratesError):
    """Execution was not confirmed or exceeds the standing cost cap."""


class NormalIntegrityError(NormalSocratesError):
    """An immutable preflight or current policy no longer agrees."""


class NormalRunCollisionError(NormalSocratesError):
    """The automatically selected write-once run identity already exists."""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def picodollars_to_usd_text(value: int) -> str:
    """Render an exact integer picodollar amount without binary rounding."""

    return format(Decimal(value) / Decimal(PICODOLLARS_PER_USD), "f")


def _parse_standing_cap_picodollars(value: Any) -> int:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError, ValueError) as exc:
        raise NormalAuthorizationError(
            f"{STANDING_CAP_ENVIRONMENT_VARIABLE} must be a positive USD amount"
        ) from exc
    if not amount.is_finite() or amount <= 0:
        raise NormalAuthorizationError(
            f"{STANDING_CAP_ENVIRONMENT_VARIABLE} must be a positive USD amount"
        )
    picodollars = amount * Decimal(PICODOLLARS_PER_USD)
    if picodollars != picodollars.to_integral_value():
        raise NormalAuthorizationError(
            f"{STANDING_CAP_ENVIRONMENT_VARIABLE} has more than 12 decimal places"
        )
    return int(picodollars)


def _new_run_id(
    *,
    question_sha256: str,
    now: Optional[datetime] = None,
    random_id: Optional[str] = None,
) -> str:
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise NormalIntegrityError("Normal run identity requires a timezone-aware clock")
    stamp = instant.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    entropy = random_id or uuid.uuid4().hex
    return f"normal_{stamp}_{question_sha256[:12]}_{entropy}"


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or _RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise NormalIntegrityError("Normal run identity is not a safe path component")


def _current_per_call_bounds(
    plan: NormalCallPlan,
) -> Tuple[Dict[str, Dict[int, int]], int]:
    """Price every reachable seat/tier from the retained current policies."""

    policy_keys = tuple(seat.policy_key for seat in plan.seats)
    current_policy.assert_output_budgets_fit_v1(policy_keys)
    bounds: Dict[str, Dict[int, int]] = {}
    maximum_per_call = 0
    allocation = plan.calls_by_seat_and_output_limit(include_retries=True)
    for seat in plan.seats:
        family = current_policy.build_seat_policy_family_v1(seat.policy_key)
        seat_bounds: Dict[int, int] = {}
        for output_limit in allocation[seat.alias]:
            try:
                policy = family[output_limit]
            except KeyError as exc:
                raise NormalPlanningError(
                    f"{seat.alias}: current policy does not declare {output_limit} tokens"
                ) from exc
            if policy.automatic_retries != 0:
                raise NormalPlanningError(
                    f"{seat.alias}: provider transport retries must remain disabled"
                )
            bound = conservative_turn_cost_bound_v1(
                policy, NORMAL_PROMPT_BUDGET_TOKENS
            )
            seat_bounds[output_limit] = bound
            maximum_per_call = max(maximum_per_call, bound)
        bounds[seat.alias] = seat_bounds
    return bounds, maximum_per_call


def _normal_binding_set_id(
    kind: str, bindings: Sequence[Mapping[str, Any]]
) -> str:
    """Content-bind a heterogeneous authorization field to every exact seat."""

    if kind not in {"policy", "profile"} or not bindings:
        raise NormalIntegrityError("Normal authorization binding set is invalid")
    payload = canonical_json(
        {
            "schema_version": "normal-socrates-binding-set/v1",
            "kind": kind,
            "bindings": list(bindings),
        }
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"normal-{kind}-set-sha256-{digest}"


def _normal_authorization_binding_ids(
    plan: NormalCallPlan,
) -> Tuple[str, str]:
    allocation = plan.calls_by_seat_and_output_limit(include_retries=True)
    policy_bindings = []
    profile_bindings = []
    for seat in plan.seats:
        profile = current_topology.load_profile_v1(seat.policy_key)
        profile_bindings.append(
            {
                "seat_alias": seat.alias,
                "provider_id": seat.provider_id,
                "model_id": seat.model_id,
                "profile_id": profile.profile_id,
            }
        )
        family = current_policy.build_seat_policy_family_v1(seat.policy_key)
        for output_limit in sorted(allocation[seat.alias]):
            policy = family[output_limit]
            policy_bindings.append(
                {
                    "seat_alias": seat.alias,
                    "model_id": seat.model_id,
                    "output_limit_tokens": output_limit,
                    "policy_id": policy.policy_id,
                }
            )
    return (
        _normal_binding_set_id("policy", policy_bindings),
        _normal_binding_set_id("profile", profile_bindings),
    )


def _normal_execution_branch_plans(session_id: str) -> Tuple[NormalCallPlan, ...]:
    """Enumerate every legal early-stop depth of the two-cycle Normal CED."""

    return tuple(
        derive_normal_call_plan(
            session_id=session_id,
            max_socratic_followups=NORMAL_MAX_SOCRATIC_FOLLOWUPS,
            completed_socratic_cycles=completed_cycles,
        )
        for completed_cycles in range(1, NORMAL_MAX_SOCRATIC_FOLLOWUPS + 1)
    )


def _assert_maximum_branch_authorizes_all_paths(
    maximum_plan: NormalCallPlan,
    maximum_cost: NormalCostPreflight,
    maximum_per_call_picodollars: int,
) -> Tuple[NormalCallPlan, ...]:
    branches = _normal_execution_branch_plans(maximum_plan.session_id)
    if not branches or branches[-1] != maximum_plan:
        raise NormalPlanningError("Normal maximum-cycle plan is not canonical")
    for branch in branches:
        bounds, branch_maximum_per_call = _current_per_call_bounds(branch)
        branch_cost = price_normal_call_plan(branch, bounds)
        if branch.maximum_call_count > maximum_plan.maximum_call_count:
            raise NormalPlanningError("Normal early-stop branch exceeds call ceiling")
        if branch_cost.maximum_cost_picodollars > (
            maximum_cost.maximum_cost_picodollars
        ):
            raise NormalPlanningError(
                "Normal early-stop branch exceeds the authorized cost ceiling"
            )
        if branch_maximum_per_call > maximum_per_call_picodollars:
            raise NormalPlanningError(
                "Normal early-stop branch exceeds the per-call cost ceiling"
            )
    return branches


@dataclass(frozen=True)
class NormalPreflight:
    """Immutable no-network identity, call plan, price, and standing cap."""

    schema_version: str
    run_id: str
    session_id: str
    created_at_utc: str
    question: str = field(repr=False)
    question_sha256: str
    question_utf8_bytes: int
    call_plan: NormalCallPlan
    cost: NormalCostPreflight
    maximum_per_call_picodollars: int
    standing_cap_picodollars: int

    @property
    def admitted_by_standing_cap(self) -> bool:
        return self.cost.maximum_cost_picodollars <= self.standing_cap_picodollars

    def plan_record(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "created_at_utc": self.created_at_utc,
            "question_sha256": self.question_sha256,
            "question_utf8_bytes": self.question_utf8_bytes,
            "full_canonical_council": True,
            "call_plan": self.call_plan.to_preflight_dict(),
            "cost": _cost_record(self.cost),
            "maximum_per_call_picodollars": self.maximum_per_call_picodollars,
            "maximum_per_call_usd": picodollars_to_usd_text(
                self.maximum_per_call_picodollars
            ),
            "standing_cap_picodollars": self.standing_cap_picodollars,
            "standing_cap_usd": picodollars_to_usd_text(
                self.standing_cap_picodollars
            ),
            "admitted_by_standing_cap": self.admitted_by_standing_cap,
            "prompt_budget_tokens": NORMAL_PROMPT_BUDGET_TOKENS,
        }


def prepare(
    question: str,
    *,
    standing_cap_usd: Optional[Any] = None,
    environment: Optional[Mapping[str, str]] = None,
    now: Optional[datetime] = None,
    run_id: Optional[str] = None,
) -> NormalPreflight:
    """Prepare an arbitrary question without credentials, adapters, or network.

    ``run_id`` and ``now`` are deterministic test seams.  The interactive CLI
    never accepts a path or run identity from its user.
    """

    if not isinstance(question, str) or not question.strip():
        raise NormalIntegrityError("Ask Socrates a nonblank question")
    digest = _sha256_text(question)
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise NormalIntegrityError("Normal preflight requires a timezone-aware clock")
    chosen_run_id = run_id or _new_run_id(question_sha256=digest, now=instant)
    _validate_run_id(chosen_run_id)
    env = os.environ if environment is None else environment
    if env.get(PREDISPATCH_DEBUG_ENVIRONMENT_VARIABLE):
        raise NormalIntegrityError(
            "Normal Socrates requires pre-dispatch debug output to be disabled"
        )
    cap_text = (
        standing_cap_usd
        if standing_cap_usd is not None
        else env.get(STANDING_CAP_ENVIRONMENT_VARIABLE, DEFAULT_STANDING_CAP_USD)
    )
    standing_cap = _parse_standing_cap_picodollars(cap_text)
    plan = derive_normal_call_plan(session_id=chosen_run_id)
    bounds, maximum_per_call = _current_per_call_bounds(plan)
    cost = price_normal_call_plan(plan, bounds)
    _assert_maximum_branch_authorizes_all_paths(plan, cost, maximum_per_call)
    created = instant.astimezone(timezone.utc)
    return NormalPreflight(
        schema_version=NORMAL_PREFLIGHT_SCHEMA_VERSION,
        run_id=chosen_run_id,
        session_id=chosen_run_id,
        created_at_utc=created.isoformat().replace("+00:00", "Z"),
        question=question,
        question_sha256=digest,
        question_utf8_bytes=len(question.encode("utf-8")),
        call_plan=plan,
        cost=cost,
        maximum_per_call_picodollars=maximum_per_call,
        standing_cap_picodollars=standing_cap,
    )


def _validate_preflight(preflight: NormalPreflight) -> None:
    if type(preflight) is not NormalPreflight:
        raise NormalIntegrityError("execute requires an exact NormalPreflight")
    if preflight.schema_version != NORMAL_PREFLIGHT_SCHEMA_VERSION:
        raise NormalIntegrityError("Normal preflight schema drifted")
    _validate_run_id(preflight.run_id)
    if preflight.session_id != preflight.run_id:
        raise NormalIntegrityError("Normal run/session identity drifted")
    if not isinstance(preflight.question, str) or not preflight.question.strip():
        raise NormalIntegrityError("Normal question is blank")
    if (
        type(preflight.standing_cap_picodollars) is not int
        or preflight.standing_cap_picodollars <= 0
    ):
        raise NormalIntegrityError("Normal standing cap is invalid")
    if _sha256_text(preflight.question) != preflight.question_sha256:
        raise NormalIntegrityError("Normal question digest drifted")
    if len(preflight.question.encode("utf-8")) != preflight.question_utf8_bytes:
        raise NormalIntegrityError("Normal question byte length drifted")
    fresh_plan = derive_normal_call_plan(session_id=preflight.session_id)
    if fresh_plan != preflight.call_plan:
        raise NormalIntegrityError("Normal call plan no longer matches current CED")
    bounds, maximum_per_call = _current_per_call_bounds(fresh_plan)
    fresh_cost = price_normal_call_plan(fresh_plan, bounds)
    if fresh_cost != preflight.cost or maximum_per_call != (
        preflight.maximum_per_call_picodollars
    ):
        raise NormalIntegrityError("Normal cost authorization drifted")
    _assert_maximum_branch_authorizes_all_paths(
        fresh_plan,
        fresh_cost,
        maximum_per_call,
    )


def validate_preflight(preflight: NormalPreflight) -> None:
    """Apply the canonical immutable-plan integrity gate without execution."""

    _validate_preflight(preflight)


@dataclass(frozen=True)
class NormalAccounting:
    calls_consumed: int = 0
    observed_picodollars: int = 0
    settled_picodollars: int = 0
    unsettled_reserved_picodollars: int = 0
    committed_picodollars: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    fatal_failure_code: Optional[str] = None


@dataclass
class NormalRuntime:
    """The minimal execution surface returned by an injected runtime factory."""

    ced: CEDOrchestrator
    adapters: Tuple[Any, ...]
    ledger: Optional[OpenRouterSessionLedgerV1] = None
    authorization: Optional[OpenRouterLiveTestSessionAuthorizationV1] = None
    progress_reporter: Optional[Any] = field(default=None, repr=False)

    def safe_turn_rows(self) -> Tuple[Dict[str, Any], ...]:
        rows = []
        for adapter in self.adapters:
            observer = getattr(adapter, "observability_rows", None)
            if not callable(observer):
                continue
            for row in observer():
                rows.append(_project_turn_row(row))
        return tuple(rows)

    def accounting(self) -> NormalAccounting:
        turns = self.safe_turn_rows()
        prompt_tokens = sum(
            int(row.get("prompt_tokens") or 0) for row in turns
        )
        completion_tokens = sum(
            int(row.get("completion_tokens") or 0) for row in turns
        )
        if self.ledger is not None:
            fatal = (
                "session_fatal"
                if self.ledger.fatal_failure is not None
                else None
            )
            return NormalAccounting(
                calls_consumed=self.ledger.calls_consumed,
                observed_picodollars=self.ledger.observed_picodollars,
                settled_picodollars=self.ledger.settled_picodollars,
                unsettled_reserved_picodollars=(
                    self.ledger.unsettled_reserved_picodollars
                ),
                committed_picodollars=self.ledger.committed_picodollars,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                fatal_failure_code=fatal,
            )
        calls = sum(
            int(getattr(adapter, "normal_calls_consumed", 0) or 0)
            for adapter in self.adapters
        )
        return NormalAccounting(
            calls_consumed=calls or len(turns),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


ProgressCallback = Callable[[str], None]
RuntimeFactory = Callable[
    [NormalPreflight, Path, Optional[ProgressCallback]], NormalRuntime
]
PreRuntimeGuard = Callable[[], None]
ObserverFactory = Callable[[CEDOrchestrator], ContextManager[None]]


class _ProgressReporter:
    def __init__(self, callback: Optional[ProgressCallback]) -> None:
        self._callback = callback
        self._seen: set[str] = set()

    def emit(self, label: str) -> None:
        if self._callback is not None and label not in self._seen:
            self._seen.add(label)
            self._callback(label)

    def observe(self, task: AgentTask) -> None:
        kind = task.task_kind
        if kind in (TaskKind.MOVE_SCORE, TaskKind.SECTION_SCORE):
            self.emit("Scoring")
        elif kind is TaskKind.COUNCIL_RATIFICATION:
            self.emit("Ratification")
        elif kind is TaskKind.OBJECTION_VERIFICATION:
            if task.task_id.startswith("verify_"):
                self.emit("Governing release")
            elif task.task_id.startswith("rule_"):
                self.emit(f"Objection review {task.round_number + 1}")
        elif task.phase is DialogPhase.OPENING:
            self.emit("Opening")
        elif task.phase is DialogPhase.INITIAL_RESPONSE:
            self.emit("Initial responses")
        elif task.phase is DialogPhase.ELENCHUS:
            if kind is TaskKind.SOCRATIC_QUESTION:
                self.emit(f"Socratic follow-up {task.round_number + 1}")
            else:
                self.emit(f"Elenchus {task.round_number + 1}")
        elif task.phase is DialogPhase.REFLECTION:
            self.emit(f"Reflection {task.round_number + 1}")
        elif task.phase is DialogPhase.RECONSTRUCTION:
            self.emit("Reconstruction")
        elif task.phase is DialogPhase.SYNTHESIS:
            self.emit("Synthesis")


class _ProgressRegistry(CouncilProviderRegistry):
    def __init__(self, reporter: _ProgressReporter) -> None:
        super().__init__(provider_timeout_seconds=125.0)
        self._normal_reporter = reporter

    async def run_adapter(
        self,
        adapter: Any,
        task: AgentTask,
        agent_state: AgentState,
        timeout_seconds: Optional[float] = None,
    ) -> Any:
        self._normal_reporter.observe(task)
        return await super().run_adapter(
            adapter, task, agent_state, timeout_seconds
        )


def _normal_refusal_receipt(
    *,
    run_directory: Path,
    seat_key: str,
    task: AgentTask,
    rendered: OpenRouterRenderedTurnV1,
    measurement: Optional[Mapping[str, Any]],
    reason: str,
) -> None:
    """Persist bounded refusal metadata without prompt or provider text."""

    receipt = {
        "schema_version": NORMAL_REFUSAL_SCHEMA_VERSION,
        "seat": seat_key,
        "session_id": task.session_id,
        "task_id_sha256": _sha256_text(task.task_id),
        "task_kind": task.task_kind.value if task.task_kind else None,
        "phase": task.phase.value,
        "attempt_index": task.attempt_index,
        "canonical_body_sha256": rendered.body_sha256,
        "measurement": dict(measurement or {}),
        "reason": reason,
    }
    refusal_dir = run_directory / "turn_receipts"
    refusal_dir.mkdir(parents=True, exist_ok=True)
    target = refusal_dir / (
        f"refusal_{seat_key}_{rendered.body_sha256[:16]}_"
        f"{_sha256_text(task.task_id)[:12]}.json"
    )
    try:
        _write_once_json(target, receipt)
    except FileExistsError:
        pass


def _planned_dispatch_key(call: Any) -> Tuple[Any, ...]:
    if call.stage in {"deliberation", "same_seat_phase_retry"}:
        return (
            "ordinary",
            call.stage,
            call.task_kind,
            call.logical_agent_id,
            call.role,
            call.phase,
            call.round_index,
            call.slot_index,
            call.attempt_index,
        )
    return ("evaluator", call.stage, call.task_kind, call.role, call.phase)


def _task_dispatch_key(task: AgentTask) -> Tuple[Any, ...]:
    if task.task_kind in _ORDINARY_TASK_KINDS:
        stage = (
            "deliberation"
            if task.attempt_index == 0
            else "same_seat_phase_retry"
        )
        return (
            "ordinary",
            stage,
            task.task_kind,
            task.agent_id,
            task.role,
            task.phase,
            task.round_number,
            task.slot_index,
            task.attempt_index,
        )
    if task.task_kind is TaskKind.MOVE_SCORE:
        stage = "move_score"
    elif task.task_kind is TaskKind.SECTION_SCORE:
        stage = "section_score"
    elif task.task_kind is TaskKind.COUNCIL_RATIFICATION:
        stage = "ratification"
    elif (
        task.task_kind is TaskKind.OBJECTION_VERIFICATION
        and task.task_id.startswith("rule_")
    ):
        stage = "mid_round_objection_ruling"
    elif (
        task.task_kind is TaskKind.OBJECTION_VERIFICATION
        and task.task_id.startswith("verify_")
    ):
        stage = "governing_objection_verification"
    else:
        raise ContractValidationError(
            "Normal task is not represented by the authorized plan"
        )
    return ("evaluator", stage, task.task_kind, task.role, task.phase)


class _NormalDispatchPlanAuthorization:
    """Shared branch-aware quota consumed synchronously before every POST."""

    def __init__(self, branches: Sequence[NormalCallPlan]) -> None:
        if not branches:
            raise NormalIntegrityError("Normal dispatch plan has no legal branch")
        self._remaining = [
            Counter(
                (call.seat_alias, _planned_dispatch_key(call))
                for call in branch.base_calls + branch.retry_calls
            )
            for branch in branches
        ]
        self._consumed_dispatches: Counter[Any] = Counter()
        self._lock = Lock()

    def consume(self, seat_alias: str, task: AgentTask) -> None:
        with self._lock:
            self._consume_locked(seat_alias, task)

    def _consume_locked(self, seat_alias: str, task: AgentTask) -> None:
        key = (seat_alias, _task_dispatch_key(task))
        if task.task_kind in _ORDINARY_TASK_KINDS and task.attempt_index == 1:
            original = (
                seat_alias,
                (
                    "ordinary",
                    "deliberation",
                    task.task_kind,
                    task.agent_id,
                    task.role,
                    task.phase,
                    task.round_number,
                    task.slot_index,
                    0,
                ),
            )
            if self._consumed_dispatches[original] <= (
                self._consumed_dispatches[key]
            ):
                raise ContractValidationError(
                    "Normal retry has no consumed same-slot original"
                )
        next_remaining = []
        for branch in self._remaining:
            if branch[key] <= 0:
                continue
            after = branch.copy()
            after[key] -= 1
            next_remaining.append(after)
        if not next_remaining:
            raise ContractValidationError(
                "Normal task exceeds every authorized execution branch"
            )
        self._remaining = next_remaining
        self._consumed_dispatches[key] += 1


def _normal_predispatch_guard(
    *,
    preflight: NormalPreflight,
    run_directory: Path,
    seat_index: int,
    reporter: _ProgressReporter,
    dispatch_plan: _NormalDispatchPlanAuthorization,
) -> Callable[[Optional[AgentTask], OpenRouterRenderedTurnV1], None]:
    seat = preflight.call_plan.seats[seat_index]
    spec = current_topology.FAMILIES_V1[seat.policy_key]
    expected_provider_id = seat.provider_id
    expected_agent_id = next(
        agent_id
        for agent_id, alias in preflight.call_plan.agent_to_seat
        if alias == seat.alias
    )
    expected_provider = {
        "allow_fallbacks": False,
        "max_price": {
            "completion": spec["completion_ceiling"],
            "prompt": spec["prompt_ceiling"],
            "request": "0",
        },
        "only": [spec["selector"]],
        "order": [spec["selector"]],
        "require_parameters": True,
    }
    def guard(
        task: Optional[AgentTask], rendered: OpenRouterRenderedTurnV1
    ) -> None:
        if type(task) is not AgentTask:
            raise ContractValidationError("Normal CED pre-dispatch task is required")
        if task.session_id != preflight.session_id or task.question != (
            preflight.question
        ):
            raise ContractValidationError("Normal task identity drifted")
        if task.task_kind in _ORDINARY_TASK_KINDS:
            if task.attempt_index not in (0, 1):
                raise ContractValidationError(
                    "Normal deliberation admits only attempts 0 and 1"
                )
            if task.agent_id != expected_agent_id:
                raise ContractValidationError(
                    f"{seat.policy_key}: task is not bound to {expected_agent_id}"
                )
        elif task.task_kind in _PROVIDER_OWNED_TASK_KINDS:
            if task.attempt_index != 0 or task.agent_id != expected_provider_id:
                raise ContractValidationError(
                    f"{seat.policy_key}: evaluator task is not provider-owned"
                )
        elif task.task_kind is TaskKind.OBJECTION_VERIFICATION:
            if task.attempt_index != 0:
                raise ContractValidationError(
                    "Normal objection verification cannot be retried"
                )
            if task.task_id.startswith("rule_") and task.agent_id != expected_agent_id:
                raise ContractValidationError(
                    f"{seat.policy_key}: ruling task is not seat-owner bound"
                )
            if not task.task_id.startswith(("rule_", "verify_")):
                raise ContractValidationError(
                    "Normal objection-verification identity is not canonical"
                )
        else:
            raise ContractValidationError("Normal task kind is not reachable")

        if type(rendered) is not OpenRouterRenderedTurnV1:
            raise ContractValidationError("Normal exact rendered turn is required")
        if task.task_kind is None:
            raise ContractValidationError("Normal task kind is required")
        expected_limit = seat.output_limit_for(task.task_kind)
        expected_policy = current_policy.build_seat_policy_v1(
            seat.policy_key, expected_limit
        )
        expected_profile = current_topology.load_profile_v1(seat.policy_key)
        if rendered.policy_id != expected_policy.policy_id:
            raise ContractValidationError("Normal rendered policy identity drifted")
        if rendered.profile_id != expected_profile.profile_id:
            raise ContractValidationError("Normal rendered profile identity drifted")
        try:
            body = json.loads(rendered.canonical_body_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ContractValidationError("Normal rendered body is invalid JSON") from exc
        if not isinstance(body, dict) or rendered.canonical_body_json != canonical_json(body):
            raise ContractValidationError("Normal rendered body is not canonical")
        expected_output_field = spec["output_field"]
        expected_keys = {
            "messages",
            "model",
            "provider",
            "response_format",
            "seed",
            "stream",
            expected_output_field,
        }
        if set(body) != expected_keys:
            raise ContractValidationError("Normal rendered body field set drifted")
        if body.get("model") != seat.model_id:
            raise ContractValidationError("Normal rendered exact model drifted")
        current_policy.assert_exact_seat_output_parameter_v1(
            seat.policy_key, body, expected_limit
        )
        if body.get("seed") != REDUCED_SEED_V1:
            raise ContractValidationError("Normal rendered seed drifted")
        if body.get("provider") != expected_provider:
            raise ContractValidationError("Normal rendered provider controls drifted")
        if body.get("stream") is not False:
            raise ContractValidationError("Normal rendered stream control drifted")
        if body.get("response_format") != ced_structured_response_format_v1(task):
            raise ContractValidationError("Normal response schema drifted")
        for forbidden in current_policy.FORBIDDEN_WIRE_PARAMETERS_V1:
            if forbidden in body:
                raise ContractValidationError(
                    f"Normal forbidden parameter emitted: {forbidden}"
                )

        measurement_record: Optional[Mapping[str, Any]] = None
        try:
            measurement = measure_request_v1(
                body,
                reserved_output_tokens=expected_limit,
                context_window_tokens=(
                    current_policy.SEAT_CONTEXT_WINDOW_TOKENS_V1[seat.policy_key]
                ),
                provider_selector=spec["selector"],
            )
            measurement_record = measurement.as_record()
            assert_request_within_bounds_v1(
                measurement,
                max_prompt_tokens=NORMAL_PROMPT_BUDGET_TOKENS,
            )
        except (EstimatorUnsupportedError, RequestBoundError) as exc:
            _normal_refusal_receipt(
                run_directory=run_directory,
                seat_key=seat.policy_key,
                task=task,
                rendered=rendered,
                measurement=measurement_record,
                reason=type(exc).__name__,
            )
            raise ContractValidationError(
                f"{seat.policy_key}: Normal request exceeded its local bound"
            ) from exc
        dispatch_plan.consume(seat.alias, task)
        reporter.observe(task)

    return guard


def _normal_task_policy_factory(
    seat: Any,
    family: Mapping[int, Any],
) -> Callable[[AgentTask], Any]:
    """Select only the current seat/task tier from its frozen policy family."""

    def select(task: AgentTask) -> Any:
        if type(task) is not AgentTask or task.task_kind is None:
            raise ContractValidationError("Normal CED task kind is required")
        output_limit = seat.output_limit_for(task.task_kind)
        try:
            return family[output_limit]
        except KeyError as exc:
            raise ContractValidationError(
                f"{seat.policy_key}: no policy for {output_limit} output tokens"
            ) from exc

    return select


def _require_execution_authorization(
    preflight: NormalPreflight, *, confirmed: bool
) -> None:
    if not preflight.admitted_by_standing_cap:
        raise NormalAuthorizationError(
            "Normal Socrates is blocked: conservative maximum $"
            f"{picodollars_to_usd_text(preflight.cost.maximum_cost_picodollars)} "
            "exceeds configured maximum $"
            f"{picodollars_to_usd_text(preflight.standing_cap_picodollars)}"
        )
    if confirmed is not True:
        raise NormalAuthorizationError("Normal Socrates execution was not confirmed")


def _build_live_runtime(
    preflight: NormalPreflight,
    run_directory: Path,
    progress: Optional[ProgressCallback] = None,
    *,
    confirmed: bool = False,
    dispatch: Optional[Callable[..., Any]] = None,
) -> NormalRuntime:
    """Construct the exact live runtime only behind an explicit authorization.

    This is intentionally private.  Ordinary callers use :func:`execute` or
    :func:`run`; the explicit flag exists only for focused offline construction
    tests and still enforces the standing cap.
    """

    _validate_preflight(preflight)
    _require_execution_authorization(preflight, confirmed=confirmed)
    if os.environ.get(PREDISPATCH_DEBUG_ENVIRONMENT_VARIABLE):
        raise NormalIntegrityError(
            "Normal Socrates requires pre-dispatch debug output to be disabled"
        )
    seats = preflight.call_plan.seats
    if tuple(seats) != DEFAULT_NORMAL_SEATS:
        raise NormalIntegrityError("Normal live topology differs from trusted default")
    if len(seats) != 3 or len({seat.model_id for seat in seats}) != 3:
        raise NormalIntegrityError("Normal live council is not three-model distinct")

    policy_set_id, profile_set_id = _normal_authorization_binding_ids(
        preflight.call_plan
    )
    authorization = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement=(
            "Normal Socrates full canonical three-model council; exact arbitrary "
            f"question SHA-256 {preflight.question_sha256}; one same-seat retry "
            "per rejected deliberation slot; no fallback, substitution, benchmark, "
            "baseline, answer key, or adapter retry."
        ),
        policy_id=policy_set_id,
        profile_id=profile_set_id,
        model="multi-model",
        provider_selector="multi-endpoint",
        maximum_calls=preflight.call_plan.maximum_call_count,
        maximum_total_spend_picodollars=(
            preflight.cost.maximum_cost_picodollars
        ),
        maximum_per_call_spend_picodollars=(
            preflight.maximum_per_call_picodollars
        ),
        session_id=preflight.session_id,
    )
    ledger = OpenRouterSessionLedgerV1(authorization)
    reporter = _ProgressReporter(progress)
    dispatch_plan = _NormalDispatchPlanAuthorization(
        _normal_execution_branch_plans(preflight.session_id)
    )
    adapters = []
    for index, seat in enumerate(seats):
        spec = current_topology.FAMILIES_V1[seat.policy_key]
        family = current_policy.build_seat_policy_family_v1(seat.policy_key)
        adapters.append(
            SocratesLiveOpenRouterAdapter(
                provider_id=seat.provider_id,
                policy=family[SYNTHESIS_OUTPUT_TOKENS],
                profile=current_topology.load_profile_v1(seat.policy_key),
                ledger=ledger,
                claim_directory=run_directory / "claims",
                max_input_tokens=NORMAL_PROMPT_BUDGET_TOKENS,
                dispatch=dispatch,
                response_format_factory=ced_structured_response_format_v1,
                structured_output_validator=validate_ced_structured_output_v1,
                task_execution_policy_factory=_normal_task_policy_factory(
                    seat, family
                ),
                outbound_task_state_projector=make_worker_payload_projector_v1(),
                pre_dispatch_guard=_normal_predispatch_guard(
                    preflight=preflight,
                    run_directory=run_directory,
                    seat_index=index,
                    reporter=reporter,
                    dispatch_plan=dispatch_plan,
                ),
                worker_alias=seat.alias,
                expose_model_identity_to_worker=False,
                expected_returned_models=(seat.model_id,),
                expected_provider_display_names=spec["provider_display"],
                ced_parse_repair_attempts=0,
            )
        )

    registry = _ProgressRegistry(reporter)
    for adapter in adapters:
        registry.register(adapter)
    fake = FakeProvider()
    agents = [SocraticAgent(f"agent_{index}", fake) for index in range(3)]
    ced = CEDOrchestrator(
        agents,
        fake,
        registry=registry,
        shadow_scoring_mode=ShadowScoringMode.ALL_PHASES,
        assembly_fallback=False,
        phase_retry=True,
        max_socratic_followups=NORMAL_MAX_SOCRATIC_FOLLOWUPS,
        ratification_repair="block",
        tree_expansions=0,
        ai_learning=False,
    )
    ced.mid_round_objection_rulings_v1 = True
    return NormalRuntime(
        ced=ced,
        adapters=tuple(adapters),
        ledger=ledger,
        authorization=authorization,
        progress_reporter=reporter,
    )


@dataclass(frozen=True)
class NormalResult:
    schema_version: str
    run_id: str
    session_id: str
    question_sha256: str
    status: str
    render: NormalRenderResult
    model_topology: Tuple[Dict[str, str], ...]
    logical_agent_to_seat: Tuple[Tuple[str, str], ...]
    base_calls: int
    maximum_retry_calls: int
    maximum_calls: int
    accounting: NormalAccounting
    actual_same_seat_retries: int
    terminal_lost_voices: Tuple[Dict[str, Any], ...]
    ratified: bool
    ratification_status: str
    artifact_path: Path
    artifact_sha256: str
    error_code: Optional[str] = None

    @property
    def public_answer(self) -> str:
        return self.render.public_answer


def _cost_record(cost: NormalCostPreflight) -> Dict[str, Any]:
    return {
        "base_picodollars": cost.base_cost_picodollars,
        "base_usd": picodollars_to_usd_text(cost.base_cost_picodollars),
        "same_seat_retry_picodollars": cost.retry_cost_picodollars,
        "same_seat_retry_usd": picodollars_to_usd_text(
            cost.retry_cost_picodollars
        ),
        "maximum_picodollars": cost.maximum_cost_picodollars,
        "maximum_usd": picodollars_to_usd_text(cost.maximum_cost_picodollars),
        "allocations": [
            {
                "seat_alias": row.seat_alias,
                "output_limit_tokens": row.output_limit_tokens,
                "base_count": row.base_count,
                "retry_count": row.retry_count,
                "maximum_count": row.maximum_count,
                "per_call_bound_picodollars": row.per_call_bound_picodollars,
                "maximum_cost_picodollars": row.maximum_cost_picodollars,
            }
            for row in cost.allocations
        ],
    }


def _write_once_json(path: Path, payload: Mapping[str, Any]) -> str:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return hashlib.sha256(encoded).hexdigest()


def _claim_run_directory(root: Path, run_id: str) -> Path:
    _validate_run_id(run_id)
    lexical_root = Path(os.path.abspath(os.fspath(root)))

    def normalized(path: Path) -> str:
        return os.path.normcase(os.path.normpath(os.fspath(path)))

    def redirected(path: Path) -> bool:
        if path.is_symlink():
            return True
        is_junction = getattr(os.path, "isjunction", None)
        return bool(is_junction(path)) if callable(is_junction) else False

    if (
        normalized(lexical_root.resolve(strict=False))
        != normalized(lexical_root)
        or (lexical_root.exists() and redirected(lexical_root))
    ):
        raise NormalIntegrityError("Normal run root is redirected")
    lexical_root.mkdir(parents=True, exist_ok=True)
    if (
        redirected(lexical_root)
        or normalized(lexical_root.resolve(strict=True))
        != normalized(lexical_root)
    ):
        raise NormalIntegrityError("Normal run root is redirected")
    target = (lexical_root / run_id).resolve(strict=False)
    if normalized(target.parent) != normalized(lexical_root):
        raise NormalIntegrityError("Normal run path escaped its trusted root")
    try:
        target.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise NormalRunCollisionError(
            f"Normal run identity already exists: {run_id}"
        ) from exc
    return target


def _project_turn_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = (
        "turn_id",
        "role_seat",
        "dialogue_phase",
        "task_kind",
        "model",
        "provider_selector",
        "http_status",
        "transport_completed",
        "retry_count",
        "prompt_tokens",
        "completion_tokens",
        "observed_cost_picodollars",
        "actual_served_model",
        "provider_display_name",
        "returned_model_binding_ok",
        "returned_provider_binding_ok",
        "provider_structured_output_valid",
        # A bare False says a seat failed and nothing else. Across two live
        # runs one model was 0/11 on two task kinds and 46/46 on the rest,
        # which is a deterministic incompatibility rather than flakiness, and
        # the artifact carried nothing to say with what. The adapter already
        # computes both codes below over closed vocabularies — pydantic error
        # types by count, and a fixed rejection table — so neither carries
        # provider prose, messages, locations or input values.
        "provider_structured_output_error",
        "ced_move_accepted",
        "ced_rejection_reason",
        "failure_class",
        "attempt_index",
        "attempt_failure_class",
        "objection_rulings_in_context",
    )
    return {name: row.get(name) for name in allowed}


def _project_task_log(state: Any) -> Tuple[Dict[str, Any], ...]:
    rows = []
    for entry in getattr(state, "task_log", ()):
        rows.append(
            {
                "task_id": entry.task_id,
                "move_id": entry.move_id,
                "session_id": entry.session_id,
                "phase": entry.phase.value,
                "round_index": entry.round_index,
                "agent_id": entry.agent_id,
                "assigned_role": entry.assigned_role.value,
                "task_kind": entry.task_kind.value if entry.task_kind else None,
                "slot_index": entry.slot_index,
                "attempt_index": entry.attempt_index,
                "schema_name": entry.schema_name,
                "context_hash": entry.context_hash,
                "provider_id": entry.provider_id,
                "provider_status": (
                    entry.provider_status.value if entry.provider_status else None
                ),
            }
        )
    return tuple(rows)


def _project_role_history(state: Any) -> Tuple[Dict[str, Any], ...]:
    allowed = ("phase", "round_index", "agent_id", "role")
    return tuple(
        {name: row.get(name) for name in allowed}
        for row in getattr(state, "role_history", ())
        if isinstance(row, Mapping)
    )


def _project_phase_retries(final: Any) -> Tuple[Dict[str, Any], ...]:
    rows = final.audit_summary.get("phase_retries", []) if final is not None else []
    allowed = (
        "phase",
        "failed_slots",
        "reasked_same_seat_slots",
        "voice_lost_slots",
        "quorum_held_but_a_voice_was_lost",
        "first_failed_providers",
        "retry_ok_providers",
        "rescued",
    )
    return tuple(
        {name: row.get(name) for name in allowed}
        for row in rows
        if isinstance(row, Mapping)
    )


def _terminal_lost_voices(
    phase_retries: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, Any], ...]:
    losses = []
    for row in phase_retries:
        failed_slots = list(row.get("failed_slots") or [])
        failed_providers = list(row.get("first_failed_providers") or [])
        provider_by_slot: Dict[Any, str] = {}
        for index, failed_slot in enumerate(failed_slots):
            if index >= len(failed_providers):
                break
            provider = failed_providers[index]
            if isinstance(provider, str) and provider:
                provider_by_slot.setdefault(failed_slot, provider)
        for slot in row.get("voice_lost_slots") or []:
            provider = provider_by_slot.get(slot)
            losses.append(
                {
                    "phase": row.get("phase"),
                    "slot_index": slot,
                    "first_failed_providers": (
                        [provider] if provider is not None else []
                    ),
                }
            )
    return tuple(losses)


def _actual_same_seat_retries(
    phase_retries: Sequence[Mapping[str, Any]],
) -> int:
    return sum(len(row.get("reasked_same_seat_slots") or []) for row in phase_retries)


def _ratification_record(final: Any) -> Dict[str, Any]:
    if final is None:
        return {"ratified": False, "status": "unavailable"}
    audit = final.audit_summary.get("council_ratification", {})
    allowed = (
        "status",
        "valid_verdicts",
        "invalid_verdicts",
        "quorum",
        "caveat_count",
        "critical_block_count",
        "target_sections",
        "failed_providers",
        "timed_out_providers",
        "verdicts",
    )
    return {
        "ratified": bool(final.ratified),
        "status": str(final.ratification_status or ""),
        "audit": {
            name: audit.get(name) for name in allowed
        } if isinstance(audit, Mapping) else {},
    }


def _governing_record(final: Any, render: NormalRenderResult) -> Dict[str, Any]:
    audit = (
        final.audit_summary.get("governing_release", {})
        if final is not None
        else {}
    )
    allowed = (
        "available",
        "release_decision",
        "governing_epistemic_status",
        "claim_states",
        "basis_record_ids",
        "unresolved_record_ids",
        # The three below name what the id lists above rest on. Without them a
        # frozen run reports that two objections are unresolved and one claim is
        # unresolved with it, and nothing on disk says which claim either
        # objection targeted, what verdict ended them there, or whether the
        # deterministic checker ever applied. That is not enough to audit the
        # release offline, which is the only way it is ever audited.
        "objections",
        "objection_verdicts",
        "deterministic_checks",
        "blocked_reason",
        "frozen_digest",
    )
    return {
        "outcome": render.outcome,
        "release_decision": render.release_decision,
        "governing_epistemic_status": render.governing_epistemic_status,
        "candidate_authorized_for_public_display": render.candidate_authorized,
        "audit": {
            name: audit.get(name) for name in allowed
        } if isinstance(audit, Mapping) else {},
    }


def _artifact_payload(
    *,
    preflight: NormalPreflight,
    final: Any,
    state: Any,
    runtime: Optional[NormalRuntime],
    render: NormalRenderResult,
    accounting: NormalAccounting,
    error_code: Optional[str],
) -> Dict[str, Any]:
    retries = _project_phase_retries(final)
    turns = runtime.safe_turn_rows() if runtime is not None else ()
    served_models = sorted(
        {
            str(row["actual_served_model"])
            for row in turns
            if row.get("actual_served_model")
        }
    )
    return {
        "schema_version": NORMAL_RESULT_SCHEMA_VERSION,
        "run_id": preflight.run_id,
        "session_id": preflight.session_id,
        "question_sha256": preflight.question_sha256,
        "question_utf8_bytes": preflight.question_utf8_bytes,
        "status": render.outcome if error_code is None else "execution_error",
        "error_code": error_code,
        "requested_topology": preflight.call_plan.to_preflight_dict()["topology"],
        "served_models": served_models,
        "logical_agent_to_seat": dict(preflight.call_plan.agent_to_seat),
        "plan": preflight.call_plan.to_preflight_dict(),
        "authorization_bounds": {
            "cost": _cost_record(preflight.cost),
            "standing_cap_picodollars": preflight.standing_cap_picodollars,
            "standing_cap_usd": picodollars_to_usd_text(
                preflight.standing_cap_picodollars
            ),
            "maximum_per_call_picodollars": (
                preflight.maximum_per_call_picodollars
            ),
        },
        "actual_accounting": {
            "calls_consumed": accounting.calls_consumed,
            "prompt_tokens": accounting.prompt_tokens,
            "completion_tokens": accounting.completion_tokens,
            "observed_picodollars": accounting.observed_picodollars,
            "settled_picodollars": accounting.settled_picodollars,
            "unsettled_reserved_picodollars": (
                accounting.unsettled_reserved_picodollars
            ),
            "committed_picodollars": accounting.committed_picodollars,
            "fatal_failure_code": accounting.fatal_failure_code,
        },
        "turns": list(turns),
        "task_log": list(_project_task_log(state)) if state is not None else [],
        "role_history": (
            list(_project_role_history(state)) if state is not None else []
        ),
        "phase_retries": list(retries),
        "actual_same_seat_retries": _actual_same_seat_retries(retries),
        "terminal_lost_voices": list(_terminal_lost_voices(retries)),
        "ratification": _ratification_record(final),
        "governing": _governing_record(final, render),
        "public": {
            "notice": render.notice,
            "answer": render.public_answer,
            "candidate_authorized": render.candidate_authorized,
        },
        "internal_candidate": {
            "answer": render.candidate,
            "authorized_for_public_display": render.candidate_authorized,
        },
    }


def _unavailable_render() -> NormalRenderResult:
    return NormalRenderResult(
        outcome="unavailable",
        release_decision=None,
        governing_epistemic_status=None,
        public_answer="",
        notice=(
            "Governing release is unavailable; no candidate is presented as "
            "an authorized public answer."
        ),
        candidate_authorized=False,
        candidate="",
    )


async def execute(
    preflight: NormalPreflight,
    *,
    confirmed: bool,
    runtime_factory: Optional[RuntimeFactory] = None,
    run_root: Path = DEFAULT_RUN_ROOT,
    progress: Optional[ProgressCallback] = None,
    pre_runtime_guard: Optional[PreRuntimeGuard] = None,
    observer_factory: Optional[ObserverFactory] = None,
    persist_cancellation_result: bool = False,
) -> NormalResult:
    """Execute one confirmed full canonical council and write a safe artifact."""

    _validate_preflight(preflight)
    _require_execution_authorization(preflight, confirmed=confirmed)

    run_directory = _claim_run_directory(run_root, preflight.run_id)
    _write_once_json(run_directory / "plan.json", preflight.plan_record())
    runtime: Optional[NormalRuntime] = None
    final: Any = None
    state: Any = None
    error_code: Optional[str] = None
    cancelled: Optional[asyncio.CancelledError] = None
    try:
        if pre_runtime_guard is not None:
            pre_runtime_guard()
        if runtime_factory is None:
            runtime = _build_live_runtime(
                preflight,
                run_directory,
                progress,
                confirmed=True,
            )
        else:
            runtime = runtime_factory(preflight, run_directory, progress)
        if type(runtime) is not NormalRuntime:
            raise NormalIntegrityError(
                "Normal runtime factory returned an unsupported boundary"
            )
        observer = (
            observer_factory(runtime.ced)
            if observer_factory is not None
            else nullcontext()
        )
        with observer:
            final = await runtime.ced.run_registry_session(
                preflight.question,
                session_id=preflight.session_id,
            )
        state = runtime.ced.get_session(preflight.session_id)
    except asyncio.CancelledError as exc:
        if not persist_cancellation_result:
            raise
        cancelled = exc
        error_code = safe_public_exception_code_v1(
            exc, context="orchestration"
        )
        if runtime is not None:
            try:
                state = runtime.ced.get_session(preflight.session_id)
            except KeyError:
                state = None
    except Exception as exc:
        error_code = safe_public_exception_code_v1(
            exc, context="orchestration"
        )
        if runtime is not None:
            try:
                state = runtime.ced.get_session(preflight.session_id)
            except KeyError:
                state = None

    if runtime is not None and runtime.progress_reporter is not None:
        runtime.progress_reporter.emit("Governing release")
    elif progress is not None:
        progress("Governing release")
    render = render_normal_response(final) if final is not None else _unavailable_render()
    accounting = runtime.accounting() if runtime is not None else NormalAccounting()
    payload = _artifact_payload(
        preflight=preflight,
        final=final,
        state=state,
        runtime=runtime,
        render=render,
        accounting=accounting,
        error_code=error_code,
    )
    artifact_path = run_directory / "result.json"
    artifact_sha256 = _write_once_json(artifact_path, payload)
    retries = _project_phase_retries(final)
    ratified = bool(getattr(final, "ratified", False))
    ratification_status = str(getattr(final, "ratification_status", "") or "")
    result = NormalResult(
        schema_version=NORMAL_RESULT_SCHEMA_VERSION,
        run_id=preflight.run_id,
        session_id=preflight.session_id,
        question_sha256=preflight.question_sha256,
        status=payload["status"],
        render=render,
        model_topology=tuple(
            {
                "alias": seat.alias,
                "provider_id": seat.provider_id,
                "model_id": seat.model_id,
                "policy_key": seat.policy_key,
            }
            for seat in preflight.call_plan.seats
        ),
        logical_agent_to_seat=preflight.call_plan.agent_to_seat,
        base_calls=preflight.call_plan.base_call_count,
        maximum_retry_calls=preflight.call_plan.retry_call_count,
        maximum_calls=preflight.call_plan.maximum_call_count,
        accounting=accounting,
        actual_same_seat_retries=_actual_same_seat_retries(retries),
        terminal_lost_voices=_terminal_lost_voices(retries),
        ratified=ratified,
        ratification_status=ratification_status,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        error_code=error_code,
    )
    if cancelled is not None:
        raise cancelled
    return result


def run(
    question: str,
    *,
    confirmed: bool,
    standing_cap_usd: Optional[Any] = None,
    runtime_factory: Optional[RuntimeFactory] = None,
    run_root: Path = DEFAULT_RUN_ROOT,
    progress: Optional[ProgressCallback] = None,
) -> NormalResult:
    """Synchronous high-level API for callers that already own confirmation."""

    preflight = prepare(question, standing_cap_usd=standing_cap_usd)
    return asyncio.run(
        execute(
            preflight,
            confirmed=confirmed,
            runtime_factory=runtime_factory,
            run_root=run_root,
            progress=progress,
        )
    )


__all__ = [
    "DEFAULT_RUN_ROOT",
    "DEFAULT_STANDING_CAP_USD",
    "NORMAL_PROMPT_BUDGET_TOKENS",
    "NormalAccounting",
    "NormalAuthorizationError",
    "NormalIntegrityError",
    "NormalPreflight",
    "NormalResult",
    "NormalRunCollisionError",
    "NormalRuntime",
    "NormalSocratesError",
    "ObserverFactory",
    "PreRuntimeGuard",
    "STANDING_CAP_ENVIRONMENT_VARIABLE",
    "execute",
    "picodollars_to_usd_text",
    "prepare",
    "run",
    "validate_preflight",
]
