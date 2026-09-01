"""Thin, fail-closed browser lifecycle over the existing Normal runtime.

This module owns only preflight retention, explicit one-use confirmation, and
public observation.  Planning, cost authorization, adapter construction,
canonical CED execution, governing release, and artifacts remain owned by
``socrates.runtime``.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import secrets
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Literal, Optional

from backend.dialogues.council_live import (
    LocalCouncilRun,
    observe_public_council,
    project_normal_render,
    project_public_seat_identities,
    project_public_text,
)
from backend.dialogues.socrates_zero.contracts import canonical_json
from socrates import runtime as normal_runtime
from socrates.runtime import NormalPreflight
from socrates.source_authorization import (
    VerifiedNormalLiveSourceAuthorizationV1,
    verify_production_normal_live_source_authorization_v1,
)


PREFLIGHT_ID_PREFIX = "nlpf_"
DEFAULT_PREFLIGHT_TTL_SECONDS = 300.0
DEFAULT_MAX_PREFLIGHTS = 32
DEFAULT_MAX_RETAINED_NORMAL_RUNS = 32


class NormalLiveError(RuntimeError):
    """Base class whose text is safe but deliberately nonspecific."""


class NormalLiveUnavailableError(NormalLiveError):
    def __init__(self) -> None:
        super().__init__("Normal Live is not yet authorized for this build.")


class NormalLiveCapacityError(NormalLiveError):
    def __init__(self) -> None:
        super().__init__("Normal Live is temporarily unavailable.")


class NormalLiveCostBlockedError(NormalLiveError):
    def __init__(self) -> None:
        super().__init__("Normal Live exceeds the configured spending limit.")


class NormalLivePreflightNotFoundError(NormalLiveError):
    def __init__(self) -> None:
        super().__init__("Normal Live preflight was not found.")


class NormalLivePreflightExpiredError(NormalLiveError):
    def __init__(self) -> None:
        super().__init__("Normal Live preflight has expired.")


class NormalLivePreflightConflictError(NormalLiveError):
    def __init__(self) -> None:
        super().__init__("Normal Live preflight is no longer usable.")


@dataclass(frozen=True)
class NormalLivePreflightBinding:
    question_sha256: str
    plan_digest: str
    source_receipt: VerifiedNormalLiveSourceAuthorizationV1
    private_topology: tuple[tuple[str, str, str, str], ...]
    maximum_calls: int
    maximum_spend_picodollars: int


@dataclass(frozen=True)
class StoredNormalLivePreflight:
    preflight_id: str
    preflight: NormalPreflight
    binding: NormalLivePreflightBinding
    created_monotonic: float
    expires_monotonic: float
    state: Literal["pending", "consumed", "cancelled", "expired"] = "pending"


def make_normal_live_preflight_binding(
    preflight: NormalPreflight,
    source_receipt: VerifiedNormalLiveSourceAuthorizationV1,
) -> NormalLivePreflightBinding:
    """Recompute all execution-authority fields from trusted server objects."""

    normal_runtime.validate_preflight(preflight)
    if type(source_receipt) is not VerifiedNormalLiveSourceAuthorizationV1:
        raise NormalLiveUnavailableError()
    plan_digest = hashlib.sha256(
        canonical_json(preflight.plan_record()).encode("utf-8")
    ).hexdigest()
    return NormalLivePreflightBinding(
        question_sha256=preflight.question_sha256,
        plan_digest=plan_digest,
        source_receipt=source_receipt,
        private_topology=tuple(
            (seat.alias, seat.provider_id, seat.model_id, seat.policy_key)
            for seat in preflight.call_plan.seats
        ),
        maximum_calls=preflight.call_plan.maximum_call_count,
        maximum_spend_picodollars=preflight.cost.maximum_cost_picodollars,
    )


class NormalLivePreflightStore:
    """Bounded TTL store with an atomic one-use confirmation transition."""

    def __init__(
        self,
        *,
        max_entries: int = DEFAULT_MAX_PREFLIGHTS,
        ttl_seconds: float = DEFAULT_PREFLIGHT_TTL_SECONDS,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if type(max_entries) is not int or max_entries <= 0:
            raise ValueError("max_entries must be a positive integer")
        if (
            not isinstance(ttl_seconds, (int, float))
            or isinstance(ttl_seconds, bool)
            or not math.isfinite(float(ttl_seconds))
            or float(ttl_seconds) <= 0
        ):
            raise ValueError("ttl_seconds must be finite and positive")
        self._max_entries = max_entries
        self._ttl_seconds = float(ttl_seconds)
        self._clock = monotonic_clock
        self._records: Dict[str, StoredNormalLivePreflight] = {}
        self._lock = asyncio.Lock()

    @property
    def records(self) -> Dict[str, StoredNormalLivePreflight]:
        return dict(self._records)

    def _now(self) -> float:
        value = float(self._clock())
        if not math.isfinite(value):
            raise NormalLiveCapacityError()
        return value

    def _transition_expired(self, now: float) -> None:
        for preflight_id, record in tuple(self._records.items()):
            if record.state == "pending" and now >= record.expires_monotonic:
                self._records[preflight_id] = replace(record, state="expired")

    def _make_room(self) -> None:
        excess = len(self._records) - self._max_entries + 1
        if excess <= 0:
            return
        terminal_ids = [
            preflight_id
            for preflight_id, record in self._records.items()
            if record.state != "pending"
        ]
        for preflight_id in terminal_ids[:excess]:
            self._records.pop(preflight_id, None)
        if len(self._records) >= self._max_entries:
            raise NormalLiveCapacityError()

    def _pending(
        self, preflight_id: str, now: float
    ) -> StoredNormalLivePreflight:
        record = self._records.get(preflight_id)
        if record is None:
            raise NormalLivePreflightNotFoundError()
        if record.state == "pending" and now >= record.expires_monotonic:
            record = replace(record, state="expired")
            self._records[preflight_id] = record
        if record.state == "expired":
            raise NormalLivePreflightExpiredError()
        if record.state != "pending":
            raise NormalLivePreflightConflictError()
        return record

    async def create(
        self,
        preflight: NormalPreflight,
        binding: NormalLivePreflightBinding,
    ) -> StoredNormalLivePreflight:
        if type(preflight) is not NormalPreflight:
            raise NormalLivePreflightConflictError()
        if type(binding) is not NormalLivePreflightBinding:
            raise NormalLivePreflightConflictError()
        async with self._lock:
            now = self._now()
            self._transition_expired(now)
            self._make_room()
            while True:
                preflight_id = PREFLIGHT_ID_PREFIX + secrets.token_hex(18)
                if preflight_id not in self._records:
                    break
            record = StoredNormalLivePreflight(
                preflight_id=preflight_id,
                preflight=preflight,
                binding=binding,
                created_monotonic=now,
                expires_monotonic=now + self._ttl_seconds,
            )
            self._records[preflight_id] = record
            return record

    async def inspect_pending(self, preflight_id: str) -> StoredNormalLivePreflight:
        async with self._lock:
            return self._pending(preflight_id, self._now())

    async def consume(
        self,
        preflight_id: str,
        current_binding: NormalLivePreflightBinding,
    ) -> StoredNormalLivePreflight:
        async with self._lock:
            record = self._pending(preflight_id, self._now())
            if type(current_binding) is not NormalLivePreflightBinding:
                raise NormalLivePreflightConflictError()
            if current_binding != record.binding:
                raise NormalLivePreflightConflictError()
            consumed = replace(record, state="consumed")
            self._records[preflight_id] = consumed
            return consumed

    async def cancel(self, preflight_id: str) -> StoredNormalLivePreflight:
        async with self._lock:
            record = self._pending(preflight_id, self._now())
            cancelled = replace(record, state="cancelled")
            self._records[preflight_id] = cancelled
            return cancelled


class NormalLiveCouncilManager:
    """Server-owned bridge from confirmed browser preflight to Normal execute."""

    def __init__(
        self,
        *,
        source_verifier: Callable[
            [], VerifiedNormalLiveSourceAuthorizationV1
        ] = verify_production_normal_live_source_authorization_v1,
        transport: Optional[Callable[..., Any]] = None,
        run_root: Path = normal_runtime.DEFAULT_RUN_ROOT,
        monotonic_clock: Callable[[], float] = time.monotonic,
        utc_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        preflight_ttl_seconds: float = DEFAULT_PREFLIGHT_TTL_SECONDS,
        max_preflights: int = DEFAULT_MAX_PREFLIGHTS,
        max_retained_runs: int = DEFAULT_MAX_RETAINED_NORMAL_RUNS,
    ) -> None:
        if type(max_retained_runs) is not int or max_retained_runs <= 0:
            raise ValueError("max_retained_runs must be a positive integer")
        self._source_verifier = source_verifier
        self._transport = transport
        self._run_root = Path(run_root)
        self._utc_clock = utc_clock
        self._store = NormalLivePreflightStore(
            max_entries=max_preflights,
            ttl_seconds=preflight_ttl_seconds,
            monotonic_clock=monotonic_clock,
        )
        self._runs: Dict[str, LocalCouncilRun] = {}
        self._runs_lock = asyncio.Lock()
        self._max_retained_runs = max_retained_runs
        self._closing = False

    @property
    def preflight_store(self) -> NormalLivePreflightStore:
        return self._store

    @property
    def runs(self) -> Dict[str, LocalCouncilRun]:
        return dict(self._runs)

    def get_run(self, run_id: str) -> Optional[LocalCouncilRun]:
        return self._runs.get(run_id)

    def _verify_source(self) -> VerifiedNormalLiveSourceAuthorizationV1:
        try:
            receipt = self._source_verifier()
        except Exception:
            raise NormalLiveUnavailableError() from None
        if type(receipt) is not VerifiedNormalLiveSourceAuthorizationV1:
            raise NormalLiveUnavailableError()
        return receipt

    @staticmethod
    def _public_preflight(
        record: StoredNormalLivePreflight,
    ) -> Dict[str, Any]:
        preflight = record.preflight
        logical_seat_ids = tuple(
            agent_id for agent_id, _private_seat in preflight.call_plan.agent_to_seat
        )
        seats = project_public_seat_identities(logical_seat_ids)
        if len(seats) != len(preflight.call_plan.seats):
            raise NormalLivePreflightConflictError()
        return {
            "preflight_id": record.preflight_id,
            "question": project_public_text(preflight.question, limit=8_000),
            "run_mode": "normal_live",
            "seats": seats,
            "provider_count": len(preflight.call_plan.seats),
            "base_calls": preflight.call_plan.base_call_count,
            "retry_calls": preflight.call_plan.retry_call_count,
            "maximum_calls": preflight.call_plan.maximum_call_count,
            "maximum_cost_usd": normal_runtime.picodollars_to_usd_text(
                preflight.cost.maximum_cost_picodollars
            ),
            "confirmation_required": True,
            "source_authorization_status": "authorized",
        }

    async def create_preflight(self, question: str) -> Dict[str, Any]:
        receipt = self._verify_source()
        try:
            preflight = normal_runtime.prepare(question, now=self._utc_clock())
            normal_runtime.validate_preflight(preflight)
        except Exception:
            raise NormalLivePreflightConflictError() from None
        if not preflight.admitted_by_standing_cap:
            raise NormalLiveCostBlockedError()
        binding = make_normal_live_preflight_binding(preflight, receipt)
        record = await self._store.create(preflight, binding)
        return self._public_preflight(record)

    def _revalidate_binding(
        self, record: StoredNormalLivePreflight
    ) -> NormalLivePreflightBinding:
        try:
            receipt = self._verify_source()
            binding = make_normal_live_preflight_binding(record.preflight, receipt)
        except Exception:
            raise NormalLivePreflightConflictError() from None
        if binding != record.binding:
            raise NormalLivePreflightConflictError()
        return binding

    def _trim_terminal_runs(self) -> None:
        excess = len(self._runs) - self._max_retained_runs + 1
        if excess <= 0:
            return
        terminal = [
            run_id
            for run_id, run in self._runs.items()
            if run.status in {"completed", "blocked", "failed"}
        ]
        for run_id in terminal[:excess]:
            self._runs.pop(run_id, None)
        if len(self._runs) >= self._max_retained_runs:
            raise NormalLiveCapacityError()

    async def start_run(self, preflight_id: str) -> LocalCouncilRun:
        record = await self._store.inspect_pending(preflight_id)
        async with self._runs_lock:
            if self._closing:
                raise NormalLiveCapacityError()
            self._trim_terminal_runs()
            run_id = record.preflight.run_id
            if run_id in self._runs:
                raise NormalLivePreflightConflictError()
            run = LocalCouncilRun(run_id, record.preflight.question)
            run.provider_mode = "normal_live"
            binding = self._revalidate_binding(record)
            consumed = await self._store.consume(preflight_id, binding)
            self._runs[run_id] = run
            entered_execution = asyncio.Event()

            async def launch() -> None:
                entered_execution.set()
                await self._execute(run, consumed)

            run.task = asyncio.create_task(launch())
            run.task.add_done_callback(lambda _task: entered_execution.set())
        await entered_execution.wait()
        if run.task.cancelled():
            run.status = "failed"
            if not run._store.terminal:
                run.emit(
                    "run.failed",
                    {
                        "status": "failed",
                        "message": (
                            "Normal Live council stopped during server shutdown."
                        ),
                    },
                    terminal=True,
                )
            raise NormalLiveCapacityError()
        return run

    async def cancel_preflight(self, preflight_id: str) -> None:
        await self._store.cancel(preflight_id)

    async def _execute(
        self,
        run: LocalCouncilRun,
        record: StoredNormalLivePreflight,
    ) -> None:
        preflight = record.preflight
        logical_seat_ids = tuple(
            agent_id for agent_id, _private_seat in preflight.call_plan.agent_to_seat
        )
        public_seats = project_public_seat_identities(logical_seat_ids)
        run.status = "running"
        run.emit(
            "run.started",
            {
                "status": "running",
                "question": project_public_text(preflight.question, limit=8_000),
                "council_size": len(public_seats),
                "seats": public_seats,
                "run_mode": "normal_live",
            },
        )

        def pre_runtime_guard() -> None:
            fresh = self._verify_source()
            if fresh != record.binding.source_receipt:
                raise normal_runtime.NormalAuthorizationError(
                    "Normal Live source authorization changed before execution"
                )

        runtime_factory = None
        if self._transport is not None:
            transport = self._transport

            def runtime_factory(prepared, run_directory, progress):
                return normal_runtime._build_live_runtime(
                    prepared,
                    run_directory,
                    progress,
                    confirmed=True,
                    dispatch=transport,
                )

        try:
            result = await normal_runtime.execute(
                preflight,
                confirmed=True,
                runtime_factory=runtime_factory,
                run_root=self._run_root,
                pre_runtime_guard=pre_runtime_guard,
                observer_factory=lambda ced: observe_public_council(run, ced),
                persist_cancellation_result=True,
            )
            if result.error_code is not None:
                run.status = "failed"
                run.emit(
                    "run.failed",
                    {
                        "status": "failed",
                        "message": "Normal Live council could not be completed.",
                    },
                    terminal=True,
                )
                return
            if run.ced is not None:
                try:
                    run.state = run.ced.get_session(preflight.session_id)
                except KeyError:
                    run.state = None
            public_final = project_normal_render(result.render)
            run.status = "completed" if public_final["answer_released"] else "blocked"
            run.emit(
                "run.completed",
                {"status": run.status, "final": public_final},
                terminal=True,
            )
        except asyncio.CancelledError:
            run.status = "failed"
            run.emit(
                "run.failed",
                {
                    "status": "failed",
                    "message": "Normal Live council stopped during server shutdown.",
                },
                terminal=True,
            )
            raise
        except Exception:
            run.status = "failed"
            run.emit(
                "run.failed",
                {
                    "status": "failed",
                    "message": "Normal Live council could not be completed.",
                },
                terminal=True,
            )

    async def shutdown(self) -> None:
        async with self._runs_lock:
            self._closing = True
            tasks = [
                run.task
                for run in self._runs.values()
                if run.task is not None and not run.task.done()
            ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


__all__ = [
    "NormalLiveCapacityError",
    "NormalLiveCostBlockedError",
    "NormalLiveCouncilManager",
    "NormalLiveError",
    "NormalLivePreflightBinding",
    "NormalLivePreflightConflictError",
    "NormalLivePreflightExpiredError",
    "NormalLivePreflightNotFoundError",
    "NormalLivePreflightStore",
    "NormalLiveUnavailableError",
    "StoredNormalLivePreflight",
    "make_normal_live_preflight_binding",
]
