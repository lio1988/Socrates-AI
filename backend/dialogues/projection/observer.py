"""
Council Live View — the CED → EventLedger observer bridge (Slice 1).

This is the ONLY projection module that CED imports. It stays inert with
respect to the execution layer: it imports **only** projection siblings
(`events`, `ledger`) and nothing from `ced.py`, providers, the registry, or
`models`. CED passes primitives (strings/ints) into `build_draft` at the emit
sites, so the observer never needs a domain type.

Design (reviewed, Slice 1):
- Dependency-injected: the caller constructs the observer around its own
  `EventLedger` and passes it to `CEDOrchestrator(event_observer=...)`. Default
  is `None` (disabled) — the single flag.
- Failures are recorded on a **bounded diagnostic side channel on the
  observer** — never on `SessionState` / `FinalResponse` / `audit_summary`.
  That is the whole point: a raising ledger must leave the canonical
  `FinalResponse` byte-identical (the golden invariant), so the failure record
  must live entirely off `FinalResponse`. The history is a bounded deque
  (oldest records drop first); `total_failure_count` / `dropped_failure_count`
  keep the loss visible.
- `run_id` for the projection is a pure function of `session_id`
  (`derive_projection_run_id`): today's CED has no native run/attempt concept —
  each full `run_session()` / `run_registry_session()` builds one
  `SessionState` keyed by `session_id`. Same `session_id` ⇒ same run stream
  (retries/replays dedupe or conflict honestly on the ledger); a new logical
  execution means a new `session_id`.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Deque, Tuple

from .events import CedEpistemicEvent, CedEventDraft, canonical_identity_digest
from .ledger import EventLedger

#: Bound on the diagnostic failure message (no raw exception object is kept;
#: the text is truncated, not redacted).
_MAX_MESSAGE_CHARS = 256

#: Bound on the retained failure HISTORY: a long-lived observer must not grow
#: without limit. Oldest records drop first; the counters keep loss visible.
_MAX_FAILURE_RECORDS = 256


def derive_projection_run_id(session_id: str) -> str:
    """Deterministic projection run id for ONE logical CED execution.

    Pure function of `session_id` (canonical JSON digest, versioned). No uuid,
    no timestamp, no invocation counter, no execution-mode suffix, no mutable
    run registry — so legacy and registry runs of the same `session_id` are the
    same logical run, and if they ever recorded contradictory facts the ledger
    conflicts fail-closed on the observer side channel rather than presenting
    two independent runs.
    """
    return "run_" + canonical_identity_digest(
        ["ced_projection_run_v1", session_id]
    )


@dataclass(frozen=True)
class ObserverFailure:
    """A bounded diagnostic record of one emit failure. No raw exception
    object is kept; the message is truncated, not redacted."""
    event_type: str
    error_type: str
    message: str


class CedEventObserver:
    """Bridge between CED emit sites and the append-only `EventLedger`.

    Owns the ledger reference and the bounded failure side channel.
    Thread-safe.
    """

    def __init__(self, ledger: EventLedger) -> None:
        self.ledger = ledger
        self._failures: Deque[ObserverFailure] = deque(
            maxlen=_MAX_FAILURE_RECORDS)
        self._total_failure_count = 0
        self._lock = threading.Lock()

    def append(self, draft: CedEventDraft) -> CedEpistemicEvent:
        """Append a draft to the ledger and return the sealed event. The
        sealed event is ignored by CED (no feedback into execution)."""
        return self.ledger.append(draft)

    def record_failure(
        self, event_type: str, error_type: str, message: str
    ) -> None:
        """Record a bounded diagnostic failure. Never touches CED state.
        History is capped at `_MAX_FAILURE_RECORDS` (oldest drop first);
        `total_failure_count` keeps counting past the cap."""
        failure = ObserverFailure(
            event_type=str(event_type),
            error_type=str(error_type),
            message=str(message)[:_MAX_MESSAGE_CHARS],
        )
        with self._lock:
            self._total_failure_count += 1
            self._failures.append(failure)

    @property
    def failures(self) -> Tuple[ObserverFailure, ...]:
        """Immutable snapshot of the RETAINED failures (most recent
        `_MAX_FAILURE_RECORDS`)."""
        with self._lock:
            return tuple(self._failures)

    @property
    def total_failure_count(self) -> int:
        """Every failure ever recorded, including dropped ones."""
        with self._lock:
            return self._total_failure_count

    @property
    def dropped_failure_count(self) -> int:
        """How many old failure records the bounded history has discarded."""
        with self._lock:
            return max(0, self._total_failure_count - len(self._failures))
