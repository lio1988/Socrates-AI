"""
Council Live View Foundation — append-only in-memory Event Ledger (hardened).

Guarantees, each locked by tests:

- **Sequence starts at 1**, monotonic and gap-free PER STREAM (typed
  ``session:<id>`` / ``run:<id>`` streams — see taxonomy.py). Sequence is
  assigned only at append; callers can never claim one.
- **Idempotent vs conflicting appends**:
    same stream + same idempotency_key + same semantic content
        → return the existing sealed fact; no new sequence consumed
    same stream + same idempotency_key + DIFFERENT semantic content
        → raise CedEventConflictError; no mutation; no sequence consumed
  Semantic content = canonical sorted UTF-8 JSON excluding event_id
  (sequence / emitted_at are structurally absent from drafts).
- **Failure atomicity (hardening round 1, finding 4)**: the duplicate/conflict
  check happens BEFORE the clock is called, so an exact duplicate is returned
  even if the clock is broken; a clock failure or sealed-validation failure
  on a new event leaves NO empty stream, NO index entry, NO consumed
  sequence — internal maps are only created after the sealed event has been
  successfully constructed.
- **Concurrency-safe**: check → clock (outside lock) → re-check under the
  lock → construct → append atomically. Two racing identical appends publish
  exactly one event; racing conflicting appends yield one winner and one
  CedEventConflictError.
- **Deep immutability (hardening round 1, finding 2)**: the ledger stores its
  own deep copies and every read/append returns fresh deep copies — mutating
  a returned event's payload (or the original draft) can never change ledger
  history. Reads return fresh tuples of frozen models.
- **Cross-stream isolation**: one stream's events are never visible through
  another stream's reads; the same idempotency_key in two different streams
  is two distinct facts.
- **No global singleton**: the ledger is instance-scoped; this module defines
  no shared instance. **No callbacks/subscribers**: appending triggers no
  user code. **No lock-held external execution**: the only injected callable
  (the clock) runs OUTSIDE the internal lock; under the lock there are only
  pure dict operations and internal model construction.
- **Deterministic injected clock**: ``EventLedger(clock=...)`` makes
  emitted_at reproducible in tests. The clock MUST return timezone-aware UTC
  datetimes — the sealed-event contract rejects naive or non-UTC values.

The ledger records; it never decides. It knows nothing about roles, scores,
or ratification semantics.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from .events import CedEpistemicEvent, CedEventDraft, _utcnow, semantic_digest
from .taxonomy import run_stream_id, session_stream_id


class CedEventConflictError(RuntimeError):
    """Same stream + same idempotency_key + DIFFERENT semantic content,
    or a reused event_id claiming a different canonical fact."""


class CedCausalityError(RuntimeError):
    """causal_parent_id violates the v1 causality policy (see append())."""


class EventLedger:
    """In-memory, append-only, per-stream event log with idempotent appends.

    Round 2 additions (finding 2):
    - GLOBAL event_id uniqueness: a reused event_id claiming a different
      canonical fact is a conflict (idempotent replay of the same fact keeps
      returning the original event regardless of the replay draft's own
      event_id — key-based dedupe wins first).
    - v1 causality policy, LOCKED: a non-None causal_parent_id must reference
      an event that ALREADY exists in this ledger (globally — cross
      session/run stream parents are explicitly allowed, e.g. session.created
      → run.started); self-parenting is refused. Deeper semantic causality
      (type-level parent/child rules) is deferred to the emission slice.
    """

    def __init__(self, clock: Optional[Callable[[], datetime]] = None) -> None:
        self._clock: Callable[[], datetime] = clock or _utcnow
        self._lock = threading.Lock()
        self._events_by_stream: Dict[str, List[CedEpistemicEvent]] = {}
        # stream_id -> idempotency_key -> (index, semantic_digest)
        self._index_by_key: Dict[str, Dict[str, Tuple[int, str]]] = {}
        # event_id -> (stream_id, index)  — GLOBAL uniqueness (round 2)
        self._event_id_index: Dict[str, Tuple[str, int]] = {}

    # ── internal helpers (call under lock) ────────────────────────────────

    def _existing(
        self, stream: str, key: str, digest: str
    ) -> Optional[CedEpistemicEvent]:
        """Return the existing event for (stream, key) or raise on conflict.
        Pure lookup: creates nothing."""
        key_index = self._index_by_key.get(stream)
        if not key_index:
            return None
        hit = key_index.get(key)
        if hit is None:
            return None
        existing_index, existing_digest = hit
        if existing_digest == digest:
            return self._events_by_stream[stream][existing_index]
        raise CedEventConflictError(
            f"idempotency_key {key!r} already bound to different semantic "
            f"content on stream {stream!r} — refusing to record a "
            "contradictory fact"
        )

    def _preflight(
        self, draft: CedEventDraft, stream: str, digest: str
    ) -> Optional[CedEpistemicEvent]:
        """
        ALL contract checks for an append, under the lock (round 3,
        finding 4): duplicate/conflict, global event_id uniqueness, and the
        v1 causality policy. Runs BEFORE the clock on the first pass so a
        broken clock can never mask the real contract error, and again after
        the clock for races. Pure: mutates nothing.
        """
        existing = self._existing(stream, draft.idempotency_key, digest)
        if existing is not None:
            return existing

        # Global event_id uniqueness: reaching here means this is NOT an
        # idempotent replay, so a known event_id is a different fact trying
        # to reuse an identity.
        if draft.event_id in self._event_id_index:
            raise CedEventConflictError(
                f"event_id {draft.event_id!r} is already bound to a "
                "different canonical fact — event ids are globally "
                "unique (causal references would become ambiguous)"
            )

        # v1 causality policy: parent must already exist; self-parent is
        # refused; cross-STREAM links are allowed only WITHIN one session
        # (session:<S> → run-of-<S>); cross-session links are refused —
        # conversation lineage needs an explicit contract later.
        if draft.causal_parent_id is not None:
            if draft.causal_parent_id == draft.event_id:
                raise CedCausalityError(
                    "an event cannot be its own causal parent"
                )
            location = self._event_id_index.get(draft.causal_parent_id)
            if location is None:
                raise CedCausalityError(
                    f"causal_parent_id {draft.causal_parent_id!r} does "
                    "not reference any recorded event — parents must "
                    "exist before their children"
                )
            parent_stream, parent_index = location
            parent = self._events_by_stream[parent_stream][parent_index]
            if parent.session_id != draft.session_id:
                raise CedCausalityError(
                    "cross-session causal links are refused in v1 — the "
                    f"parent belongs to session {parent.session_id!r}, "
                    f"this event to {draft.session_id!r}; cross-session "
                    "lineage requires an explicit future contract"
                )
        return None

    # ── write path ────────────────────────────────────────────────────────

    def append(self, draft: CedEventDraft) -> CedEpistemicEvent:
        """
        Seal and append a draft. Idempotent on identical semantic content;
        conflicting content under a reused key raises CedEventConflictError.
        A raising append consumes no sequence and mutates nothing — not even
        an empty stream entry.
        """
        # Re-validate defensively (closes any post-construction payload-dict
        # mutation hole) — OUTSIDE the lock, like every non-pure step.
        draft = CedEventDraft.model_validate(draft.model_dump())
        digest = semantic_digest(draft)
        stream = draft.stream_id
        key = draft.idempotency_key

        # First pass: EVERY contract check runs BEFORE the clock (round 3,
        # finding 4) — an exact duplicate returns, and an invalid event_id /
        # causality error surfaces as ITSELF, never masked by a broken clock.
        with self._lock:
            existing = self._preflight(draft, stream, digest)
        if existing is not None:
            return existing.model_copy(deep=True)

        # Only a genuinely valid new fact consumes a clock reading. The
        # injected callable runs outside the lock. If it raises, nothing was
        # mutated.
        emitted_at = self._clock()

        with self._lock:
            # Repeat ALL checks under the lock: another thread may have
            # appended while we were reading the clock.
            existing = self._preflight(draft, stream, digest)
            if existing is not None:
                return existing.model_copy(deep=True)

            events = self._events_by_stream.get(stream)
            next_sequence = (len(events) if events is not None else 0) + 1

            # Construct BEFORE mutating any ledger structure: a validation
            # failure here (e.g. a naive/non-UTC clock) leaves no empty
            # stream and no index entry.
            sealed = CedEpistemicEvent(
                **draft.model_dump(),
                sequence=next_sequence,
                emitted_at=emitted_at,
            )

            if events is None:
                events = []
                self._events_by_stream[stream] = events
                self._index_by_key[stream] = {}
            events.append(sealed)
            self._index_by_key[stream][key] = (len(events) - 1, digest)
            self._event_id_index[draft.event_id] = (stream, len(events) - 1)

        return sealed.model_copy(deep=True)

    # ── read path (fresh deep copies in fresh tuples, every call) ─────────

    def stream_ids(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._events_by_stream.keys()))

    def event_count(self, stream_id: str) -> int:
        with self._lock:
            return len(self._events_by_stream.get(stream_id, []))

    def events_for_stream(self, stream_id: str) -> Tuple[CedEpistemicEvent, ...]:
        """All events for one stream, in sequence order."""
        with self._lock:
            stored = list(self._events_by_stream.get(stream_id, []))
        return tuple(e.model_copy(deep=True) for e in stored)

    def events_for_run(self, run_id: str) -> Tuple[CedEpistemicEvent, ...]:
        return self.events_for_stream(run_stream_id(run_id))

    def events_for_session(self, session_id: str) -> Tuple[CedEpistemicEvent, ...]:
        return self.events_for_stream(session_stream_id(session_id))

    def events_since(
        self,
        stream_id: str,
        after_sequence: int = 0,
        limit: Optional[int] = None,
    ) -> Tuple[CedEpistemicEvent, ...]:
        """
        Bounded replay (Last-Event-ID semantics): events with
        sequence > after_sequence. The default 0 replays from the start,
        because sequences start at 1.
        """
        with self._lock:
            events = self._events_by_stream.get(stream_id, [])
            selected = [e for e in events if e.sequence > after_sequence]
        if limit is not None:
            selected = selected[: max(0, limit)]
        return tuple(e.model_copy(deep=True) for e in selected)

    def find_by_idempotency_key(
        self, stream_id: str, idempotency_key: str
    ) -> Optional[CedEpistemicEvent]:
        with self._lock:
            hit = self._index_by_key.get(stream_id, {}).get(idempotency_key)
            if hit is None:
                return None
            stored = self._events_by_stream[stream_id][hit[0]]
        return stored.model_copy(deep=True)

    def find_by_event_id(self, event_id: str) -> Optional[CedEpistemicEvent]:
        """Global event lookup (event ids are globally unique)."""
        with self._lock:
            hit = self._event_id_index.get(event_id)
            if hit is None:
                return None
            stream_id, index = hit
            stored = self._events_by_stream[stream_id][index]
        return stored.model_copy(deep=True)
