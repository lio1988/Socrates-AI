"""BYOK: one council run funded by the user's own OpenRouter credential.

This module owns exactly three things that Normal Live does not: a run-scoped
credential boundary, a bounded preview rate limiter, and the manager that binds
one confirmed preflight to one user credential.

Everything else is deliberately borrowed rather than reimplemented. Planning and
cost arithmetic stay in ``socrates.runtime``; preflight retention, expiry and
one-use consumption stay in ``normal_live``; the canonical council stays in
``CEDOrchestrator``; the transport, its dispatch latch and its single
``Authorization`` injection site stay in ``openrouter_one_live_shadow_v1``. A
second planner or a second transport would be a second place that can authorize
a charge, and one is already hard enough to audit.

Why this lives in its own module rather than beside ``NormalLiveCouncilManager``:
the two managers differ in exactly one respect, and it is the one that matters.
Operator Normal Live reads the process credential; BYOK never can. Keeping them
in one file would put both credential sources one editing mistake apart.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Optional

from backend.dialogues.council_live import (
    LocalCouncilRun,
    observe_public_council,
    project_normal_render,
    project_public_seat_identities,
    project_public_text,
)
from backend.dialogues.normal_live import (
    DEFAULT_MAX_PREFLIGHTS,
    DEFAULT_MAX_RETAINED_NORMAL_RUNS,
    DEFAULT_PREFLIGHT_TTL_SECONDS,
    NormalLiveCapacityError,
    NormalLiveCostBlockedError,
    NormalLiveError,
    NormalLivePreflightConflictError,
    NormalLivePreflightStore,
    NormalLiveUnavailableError,
    StoredNormalLivePreflight,
    make_normal_live_preflight_binding,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    dispatch_openrouter_one_live_inference_with_credential_v1,
    validate_bearer_credential_v1,
)
from socrates import runtime as normal_runtime
from socrates.source_authorization import (
    VerifiedNormalLiveSourceAuthorizationV1,
    verify_production_normal_live_source_authorization_v1,
)


BYOK_RUN_MODE = "byok_live"

#: Single-process public-preview protection. These are server constants, never
#: browser input. They are not a substitute for a shared limiter: a second
#: application worker has its own copy of every counter below, so the public
#: preview must run one worker until an external limiter exists.
DEFAULT_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT = 1
DEFAULT_MAX_ACTIVE_BYOK_RUNS_GLOBAL = 2
DEFAULT_MAX_BYOK_PREFLIGHTS_PER_CLIENT = 10
DEFAULT_BYOK_PREFLIGHT_WINDOW_SECONDS = 600.0
DEFAULT_MAX_BYOK_EXECUTIONS_PER_CLIENT = 4
DEFAULT_BYOK_EXECUTION_WINDOW_SECONDS = 3600.0
#: Distinct client identities the limiter will track before it starts evicting
#: the least recently seen. Without a bound this is a memory-growth surface an
#: anonymous caller controls.
DEFAULT_MAX_TRACKED_BYOK_CLIENTS = 4096


class ByokLiveError(NormalLiveError):
    """Base for BYOK-specific failures."""


class ByokCredentialRejectedError(ByokLiveError):
    """The supplied credential failed local validation, or was absent.

    Carries no fragment of the value and no length, because an error is a public
    surface and a length is a distinguisher.
    """

    def __init__(self) -> None:
        super().__init__("The supplied OpenRouter key was rejected.")


class ByokRateLimitedError(ByokLiveError):
    """A bounded preview limit was reached."""

    def __init__(self, retry_after_seconds: int = 60) -> None:
        super().__init__("Capacity for this preview was temporarily reached.")
        self.retry_after_seconds = max(1, int(retry_after_seconds))


# ------------------------------------------------------- credential boundary --


class ReleasedCredentialError(ByokLiveError):
    """The run tried to use a credential after its terminal release."""

    def __init__(self) -> None:
        super().__init__("The run credential has already been released.")


class RunScopedCredential:
    """One user credential, bound to one run, redacted everywhere but the socket.

    What this class actually guarantees, stated exactly because the honest scope
    is narrower than the phrase "secure memory" suggests: the value cannot be
    reached by accident. It is not an attribute anyone can print, it has no
    ``repr`` that discloses it, it refuses to be copied, pickled or serialized,
    and reading it requires calling :meth:`reveal` by name.

    What it does not guarantee, and must never be claimed to: that CPython has
    overwritten every immutable copy of the string. Releasing drops this
    object's reference and the interpreter reclaims the object when nothing else
    holds it. That is best effort, and it is the truthful description.
    """

    __slots__ = ("_value", "_released")

    def __init__(self, value: str) -> None:
        # Validated here so a malformed credential can never reach a header, and
        # so the rejection happens before anything is bound to a run.
        self._value = validate_bearer_credential_v1(value)
        self._released = False

    def reveal(self) -> str:
        """Return the credential. The only way out, and deliberately named."""
        if self._released:
            raise ReleasedCredentialError()
        return self._value

    def release(self) -> None:
        """Terminal. Idempotent, so every cleanup path may call it."""
        self._released = True
        self._value = ""

    @property
    def released(self) -> bool:
        return self._released

    def __repr__(self) -> str:
        state = "released" if self._released else "held"
        return f"<RunScopedCredential {state}>"

    __str__ = __repr__

    def __format__(self, _spec: str) -> str:
        return repr(self)

    # Copying, pickling and JSON are all ways a secret escapes a process by
    # accident. Each one fails loudly instead.
    def __reduce__(self):
        raise TypeError("a run-scoped credential cannot be serialized")

    def __copy__(self):
        raise TypeError("a run-scoped credential cannot be copied")

    def __deepcopy__(self, _memo):
        raise TypeError("a run-scoped credential cannot be copied")

    def __getstate__(self):
        raise TypeError("a run-scoped credential cannot be serialized")


def make_byok_dispatch_v1(
    credential: RunScopedCredential,
    *,
    transport: Optional[Callable[..., Any]] = None,
) -> Callable[..., Any]:
    """Bind one credential to one run's dispatches.

    The credential lives in this closure and nowhere else: not in the adapter,
    not in the ledger, not in the run model, not in a module-level store. When
    the run's ``finally`` releases it, every later call through this closure
    raises rather than reaching the network.
    """

    def dispatch(
        *,
        body_bytes: bytes,
        semantic_headers: Any,
        bounded_timeout_seconds: int,
        process_dispatch_limit: int = 1,
    ) -> Any:
        secret = credential.reveal()
        if transport is not None:
            return transport(
                bearer_credential=secret,
                body_bytes=body_bytes,
                semantic_headers=semantic_headers,
                bounded_timeout_seconds=bounded_timeout_seconds,
                process_dispatch_limit=process_dispatch_limit,
            )
        return dispatch_openrouter_one_live_inference_with_credential_v1(
            bearer_credential=secret,
            body_bytes=body_bytes,
            semantic_headers=semantic_headers,
            bounded_timeout_seconds=bounded_timeout_seconds,
            process_dispatch_limit=process_dispatch_limit,
        )

    return dispatch


# ------------------------------------------------------------ rate limiting --


class ByokRateLimiter:
    """Bounded, in-memory, single-process preview protection.

    Deliberately not a queue. A queue would hold a user's credential while they
    wait, and waiting is the one thing a credential must not do.
    """

    def __init__(
        self,
        *,
        max_active_per_client: int = DEFAULT_MAX_ACTIVE_BYOK_RUNS_PER_CLIENT,
        max_active_global: int = DEFAULT_MAX_ACTIVE_BYOK_RUNS_GLOBAL,
        max_preflights_per_client: int = DEFAULT_MAX_BYOK_PREFLIGHTS_PER_CLIENT,
        preflight_window_seconds: float = DEFAULT_BYOK_PREFLIGHT_WINDOW_SECONDS,
        max_executions_per_client: int = DEFAULT_MAX_BYOK_EXECUTIONS_PER_CLIENT,
        execution_window_seconds: float = DEFAULT_BYOK_EXECUTION_WINDOW_SECONDS,
        max_tracked_clients: int = DEFAULT_MAX_TRACKED_BYOK_CLIENTS,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_active_per_client = int(max_active_per_client)
        self._max_active_global = int(max_active_global)
        self._max_preflights = int(max_preflights_per_client)
        self._preflight_window = float(preflight_window_seconds)
        self._max_executions = int(max_executions_per_client)
        self._execution_window = float(execution_window_seconds)
        self._max_tracked = int(max_tracked_clients)
        self._clock = monotonic_clock
        self._preflights: Dict[str, Deque[float]] = {}
        self._executions: Dict[str, Deque[float]] = {}
        self._active: Dict[str, int] = {}

    # No credential is ever an argument here, and no key material is stored: a
    # rate-limit record outlives the run it describes.
    def _prune(self, marks: Deque[float], window: float, now: float) -> None:
        while marks and (now - marks[0]) > window:
            marks.popleft()

    def _evict_if_needed(self, table: Dict[str, Deque[float]]) -> None:
        while len(table) > self._max_tracked:
            table.pop(next(iter(table)), None)

    def check_preflight(self, client: str) -> None:
        now = self._clock()
        marks = self._preflights.setdefault(client, deque())
        self._prune(marks, self._preflight_window, now)
        if len(marks) >= self._max_preflights:
            oldest = marks[0]
            raise ByokRateLimitedError(
                int(self._preflight_window - (now - oldest)) + 1
            )
        marks.append(now)
        self._evict_if_needed(self._preflights)

    def check_execution(self, client: str) -> None:
        now = self._clock()
        if sum(self._active.values()) >= self._max_active_global:
            raise ByokRateLimitedError(60)
        if self._active.get(client, 0) >= self._max_active_per_client:
            raise ByokRateLimitedError(60)
        marks = self._executions.setdefault(client, deque())
        self._prune(marks, self._execution_window, now)
        if len(marks) >= self._max_executions:
            oldest = marks[0]
            raise ByokRateLimitedError(
                int(self._execution_window - (now - oldest)) + 1
            )
        marks.append(now)
        self._evict_if_needed(self._executions)

    def enter_run(self, client: str) -> None:
        self._active[client] = self._active.get(client, 0) + 1

    def exit_run(self, client: str) -> None:
        remaining = self._active.get(client, 0) - 1
        if remaining > 0:
            self._active[client] = remaining
        else:
            self._active.pop(client, None)

    @property
    def active_total(self) -> int:
        return sum(self._active.values())


# ----------------------------------------------------------------- manager ---


class ByokLiveCouncilManager:
    """One confirmed preflight, one user credential, one canonical council."""

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
        rate_limiter: Optional[ByokRateLimiter] = None,
    ) -> None:
        if type(max_retained_runs) is not int or max_retained_runs <= 0:
            raise ValueError("max_retained_runs must be a positive integer")
        self._source_verifier = source_verifier
        #: Test transport. It receives ``bearer_credential`` exactly as the real
        #: transport does, so an offline test can assert whose key was used.
        self._transport = transport
        self._run_root = Path(run_root)
        self._utc_clock = utc_clock
        self._store = NormalLivePreflightStore(
            max_entries=max_preflights,
            ttl_seconds=preflight_ttl_seconds,
            monotonic_clock=monotonic_clock,
            utc_clock=utc_clock,
        )
        self._runs: Dict[str, LocalCouncilRun] = {}
        self._runs_lock = asyncio.Lock()
        self._max_retained_runs = max_retained_runs
        self._limiter = rate_limiter or ByokRateLimiter(
            monotonic_clock=monotonic_clock
        )
        self._closing = False

    @property
    def preflight_store(self) -> NormalLivePreflightStore:
        return self._store

    @property
    def rate_limiter(self) -> ByokRateLimiter:
        return self._limiter

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
    def _public_preflight(record: StoredNormalLivePreflight) -> Dict[str, Any]:
        preflight = record.preflight
        logical_seat_ids = tuple(
            agent_id for agent_id, _private_seat in preflight.call_plan.agent_to_seat
        )
        seats = project_public_seat_identities(logical_seat_ids)
        if len(seats) != len(preflight.call_plan.seats):
            raise NormalLivePreflightConflictError()
        return {
            "preflight_id": record.preflight_id,
            "question_sha256": preflight.question_sha256,
            "question": project_public_text(preflight.question, limit=8_000),
            "run_mode": BYOK_RUN_MODE,
            "seats": seats,
            "provider_count": len(preflight.call_plan.seats),
            "base_calls": preflight.call_plan.base_call_count,
            "retry_calls": preflight.call_plan.retry_call_count,
            "maximum_calls": preflight.call_plan.maximum_call_count,
            "maximum_cost_usd": normal_runtime.picodollars_to_usd_text(
                preflight.cost.maximum_cost_picodollars
            ),
            "confirmation_required": True,
            "credential_required": True,
            "source_authorization_status": "authorized",
            "validity_seconds": record.validity_seconds,
            "expires_at_utc": record.expires_at_utc,
        }

    async def create_preflight(
        self, question: str, *, client: str = "local"
    ) -> Dict[str, Any]:
        """Plan a run. The credential is not an input here and never will be."""
        self._limiter.check_preflight(client)
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

    def _revalidate_binding(self, record: StoredNormalLivePreflight):
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

    async def start_run(
        self,
        preflight_id: str,
        credential_value: str,
        *,
        client: str = "local",
    ) -> LocalCouncilRun:
        """Consume one preflight and bind one credential to one run.

        The credential is validated and wrapped before the preflight is consumed,
        so a rejected key cannot burn a one-use capability.
        """
        try:
            credential = RunScopedCredential(credential_value)
        except Exception:
            raise ByokCredentialRejectedError() from None

        try:
            self._limiter.check_execution(client)
        except Exception:
            credential.release()
            raise

        try:
            record = await self._store.inspect_pending(preflight_id)
        except Exception:
            credential.release()
            raise

        async with self._runs_lock:
            if self._closing:
                credential.release()
                raise NormalLiveCapacityError()
            try:
                self._trim_terminal_runs()
                run_id = record.preflight.run_id
                if run_id in self._runs:
                    raise NormalLivePreflightConflictError()
                run = LocalCouncilRun(run_id, record.preflight.question)
                run.provider_mode = BYOK_RUN_MODE
                binding = self._revalidate_binding(record)
                consumed = await self._store.consume(preflight_id, binding)
            except Exception:
                credential.release()
                raise
            self._runs[run_id] = run
            self._limiter.enter_run(client)
            entered_execution = asyncio.Event()

            async def launch() -> None:
                entered_execution.set()
                try:
                    await self._execute(run, consumed, credential)
                finally:
                    self._limiter.exit_run(client)

            run.task = asyncio.create_task(launch())
            run.task.add_done_callback(lambda _task: entered_execution.set())
        await entered_execution.wait()
        if run.task.cancelled():
            credential.release()
            run.status = "failed"
            if not run._store.terminal:
                run.emit(
                    "run.failed",
                    {
                        "status": "failed",
                        "message": "BYOK council stopped during server shutdown.",
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
        credential: RunScopedCredential,
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
                "run_mode": BYOK_RUN_MODE,
            },
        )

        def pre_runtime_guard() -> None:
            try:
                fresh = self._verify_source()
                fresh_binding = make_normal_live_preflight_binding(
                    record.preflight, fresh
                )
            except Exception:
                raise normal_runtime.NormalAuthorizationError(
                    "BYOK source authorization changed before execution"
                ) from None
            if fresh_binding != record.binding:
                raise normal_runtime.NormalAuthorizationError(
                    "BYOK source authorization changed before execution"
                )

        dispatch = make_byok_dispatch_v1(credential, transport=self._transport)

        def runtime_factory(prepared, run_directory, progress):
            # The only difference from operator Normal Live in the entire path.
            return normal_runtime._build_live_runtime(
                prepared,
                run_directory,
                progress,
                confirmed=True,
                dispatch=dispatch,
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
                        "message": "BYOK council could not be completed.",
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
                    "message": "BYOK council stopped during server shutdown.",
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
                    "message": "BYOK council could not be completed.",
                },
                terminal=True,
            )
        finally:
            # Every terminal path, including cancellation and an exception on
            # the way to one. After this the run's dispatch closure can only
            # raise, so a late retry cannot reach the network with this key.
            credential.release()

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
    "BYOK_RUN_MODE",
    "ByokCredentialRejectedError",
    "ByokLiveCouncilManager",
    "ByokLiveError",
    "ByokRateLimitedError",
    "ByokRateLimiter",
    "ReleasedCredentialError",
    "RunScopedCredential",
    "make_byok_dispatch_v1",
]
