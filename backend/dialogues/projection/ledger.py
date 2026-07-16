"""
Council Live View Foundation — append-only in-memory Event Ledger (audited).

Guarantees, each locked by tests:

- **Sequence starts at 1**, monotonic and gap-free PER STREAM (typed
  ``session:<id>`` / ``run:<id>`` streams — see taxonomy.py). Sequence is
  assigned only at append; callers can never claim one.
- **Idempotent vs conflicting appends**:
    same stream + same idempotency_key + same semantic content
        → return the EXISTING sealed event; no new sequence consumed
    same stream + same idempotency_key + DIFFERENT semantic content
        → raise CedEventConflictError; no mutation; no sequence consumed
  Semantic content = canonical sorted UTF-8 JSON excluding event_id
  (sequence / emitted_at are structurally absent from drafts).
- **Failed append consumes no sequence**: validation, revalidation, digest
  computation and the conflict check all happen BEFORE a sequence is
  assigned; a raising append leaves the stream exactly as it was.
- **Immutable returned history**: reads return fresh tuples of frozen models.
- **Cross-stream isolation**: one stream's events are never visible through
  another stream's reads; the same idempotency_key in two different streams
  is two distinct facts.
- **No global singleton**: the ledger is instance-scoped; this module defines
  no shared instance. **No callbacks/subscribers**: appending triggers no
  user code. **No lock-held external execution**: the only injected callable
  (the clock) runs OUTSIDE the internal lock; under the lock there are only
  pure dict operations and internal model construction.
- **Deterministic injected clock**: ``EventLedger(clock=...)`` makes
  emitted_at reproducible in tests. (Event ids are caller/draft-side, so id
  determinism is injected at draft construction.)

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
    """Same stream + same idempotency_key + DIFFERENT semantic content."""


class EventLedger:
    """In-memory, append-only, per-stream event log with idempotent appends."""

    def __init__(self, clock: Optional[Callable[[], datetime]] = None) -> None:
        self._clock: Callable[[], datetime] = clock or _utcnow
        self._lock = threading.Lock()
        self._events_by_stream: Dict[str, List[CedEpistemicEvent]] = {}
        # stream_id -> idempotency_key -> (index, semantic_digest)
        self._index_by_key: Dict[str, Dict[str, Tuple[int, str]]] = {}

    # ── write path ────────────────────────────────────────────────────────

    def append(self, draft: CedEventDraft) -> CedEpistemicEvent:
        """
        Seal and append a draft. Idempotent on identical semantic content;
        conflicting content under a reused key raises CedEventConflictError.
        A raising append consumes no sequence and mutates nothing.
        """
        # Re-validate defensively (closes any post-construction payload-dict
        # mutation hole) — OUTSIDE the lock, like every non-pure step.
        draft = CedEventDraft.model_validate(
            {**draft.model_dump(), "event_type": draft.event_type}
        )
        digest = semantic_digest(draft)
        emitted_at = self._clock()          # injected callable: never under lock
        stream = draft.stream_id

        with self._lock:
            events = self._events_by_stream.setdefault(stream, [])
            key_index = self._index_by_key.setdefault(stream, {})

            hit = key_index.get(draft.idempotency_key)
            if hit is not None:
                existing_index, existing_digest = hit
                if existing_digest == digest:
                    return events[existing_index]      # idempotent duplicate
                raise CedEventConflictError(
                    f"idempotency_key {draft.idempotency_key!r} already bound "
                    f"to different semantic content on stream {stream!r} — "
                    "refusing to record a contradictory fact"
                )

            sealed = CedEpistemicEvent(
                **{**draft.model_dump(), "event_type": draft.event_type},
                sequence=len(events) + 1,               # sequences start at 1
                emitted_at=emitted_at,
            )
            events.append(sealed)
            key_index[draft.idempotency_key] = (len(events) - 1, digest)
            return sealed

    # ── read path (immutable results; fresh tuples of frozen models) ─────

    def stream_ids(self) -> Tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._events_by_stream.keys()))

    def event_count(self, stream_id: str) -> int:
        with self._lock:
            return len(self._events_by_stream.get(stream_id, []))

    def events_for_stream(self, stream_id: str) -> Tuple[CedEpistemicEvent, ...]:
        """All events for one stream, in sequence order."""
        with self._lock:
            return tuple(self._events_by_stream.get(stream_id, []))

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
        return tuple(selected)

    def find_by_idempotency_key(
        self, stream_id: str, idempotency_key: str
    ) -> Optional[CedEpistemicEvent]:
        with self._lock:
            hit = self._index_by_key.get(stream_id, {}).get(idempotency_key)
            if hit is None:
                return None
            return self._events_by_stream[stream_id][hit[0]]
