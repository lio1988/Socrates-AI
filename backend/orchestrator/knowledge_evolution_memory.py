"""
CED Graph v5 — Knowledge Evolution Memory / Claim Lineage
=========================================================

A persistent, graph-native, deterministic memory of how claims evolve over
time. A claim is not a static string: the system preserves historical text
versions, revisions, superseded versions, and an ordered lineage of events.

This module is purely additive. It records lineage *alongside* the existing
v0-v4 epistemics; it never changes claim states, scores, graph structure, or
which claim_ids the Current Best Explanation references.

Lineage event types
-------------------
created · challenged · revised · supported_after_revision · superseded ·
rejected · used_in_current_best_explanation
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

# --- event type constants ---------------------------------------------------
EVENT_CREATED = "created"
EVENT_CHALLENGED = "challenged"
EVENT_REVISED = "revised"
EVENT_SUPPORTED_AFTER_REVISION = "supported_after_revision"
EVENT_SUPERSEDED = "superseded"
EVENT_REJECTED = "rejected"
EVENT_USED_IN_CBE = "used_in_current_best_explanation"

ALLOWED_EVENT_TYPES = frozenset({
    EVENT_CREATED,
    EVENT_CHALLENGED,
    EVENT_REVISED,
    EVENT_SUPPORTED_AFTER_REVISION,
    EVENT_SUPERSEDED,
    EVENT_REJECTED,
    EVENT_USED_IN_CBE,
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class LineageEvent:
    """A single, immutable point in a claim's history."""
    event_id: str
    claim_id: str
    event_type: str
    actor: str
    reason: str
    text_snapshot: str
    confidence_snapshot: float
    state_snapshot: str
    timestamp: str
    sequence: int
    parent_claim_id: Optional[str] = None
    previous_claim_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class KnowledgeEvolutionMemory:
    """Ordered, deterministic lineage store for claims.

    Determinism: events are appended in call order and carry a monotonically
    increasing ``sequence``; ordering never depends on dict iteration or wall
    clock. Timestamps are recorded for display only.
    """

    def __init__(self) -> None:
        self.events: List[LineageEvent] = []                       # global ordered log
        self.events_by_claim: Dict[str, List[LineageEvent]] = {}    # per-claim ordered
        self.lineage_id_by_claim: Dict[str, str] = {}
        # historical (pre-revision) text versions, oldest first
        self.text_history_by_claim: Dict[str, List[str]] = {}
        self._seq = 0

    # --- lineage identity --------------------------------------------------
    def lineage_id(self, claim_id: str) -> str:
        if claim_id not in self.lineage_id_by_claim:
            self.lineage_id_by_claim[claim_id] = _new_id("lineage")
        return self.lineage_id_by_claim[claim_id]

    # --- recording ---------------------------------------------------------
    def record(
        self,
        claim_id: str,
        event_type: str,
        *,
        actor: str,
        reason: str,
        text_snapshot: str,
        confidence_snapshot: float,
        state_snapshot: str,
        parent_claim_id: Optional[str] = None,
        previous_claim_id: Optional[str] = None,
    ) -> LineageEvent:
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"Unknown lineage event type: {event_type!r}")
        self.lineage_id(claim_id)  # ensure a stable lineage id exists
        self._seq += 1
        event = LineageEvent(
            event_id=_new_id("evt"),
            claim_id=claim_id,
            event_type=event_type,
            actor=actor,
            reason=reason,
            text_snapshot=text_snapshot,
            confidence_snapshot=round(float(confidence_snapshot), 3),
            state_snapshot=state_snapshot,
            timestamp=_now_iso(),
            sequence=self._seq,
            parent_claim_id=parent_claim_id,
            previous_claim_id=previous_claim_id,
        )
        self.events.append(event)
        self.events_by_claim.setdefault(claim_id, []).append(event)
        return event

    def add_text_version(self, claim_id: str, text: str) -> None:
        """Preserve a historical (pre-revision) text snapshot."""
        self.text_history_by_claim.setdefault(claim_id, []).append(text)

    # --- queries -----------------------------------------------------------
    def lineage_for(self, claim_id: str) -> List[LineageEvent]:
        return list(self.events_by_claim.get(claim_id, []))

    def event_count(self, claim_id: str) -> int:
        return len(self.events_by_claim.get(claim_id, []))

    def event_types(self, claim_id: str) -> List[str]:
        return [e.event_type for e in self.events_by_claim.get(claim_id, [])]

    def previous_text_snapshot(self, claim_id: str) -> Optional[str]:
        history = self.text_history_by_claim.get(claim_id, [])
        return history[-1] if history else None

    def text_versions(self, claim_id: str) -> List[str]:
        return list(self.text_history_by_claim.get(claim_id, []))

    def latest_revision_actor(self, claim_id: str) -> Optional[str]:
        for event in reversed(self.events_by_claim.get(claim_id, [])):
            if event.event_type in (EVENT_REVISED, EVENT_SUPPORTED_AFTER_REVISION):
                return event.actor
        return None

    def has_event(self, claim_id: str, event_type: str) -> bool:
        return any(e.event_type == event_type
                   for e in self.events_by_claim.get(claim_id, []))

    # --- summaries ---------------------------------------------------------
    def lineage_summary(self, claim_id: str) -> dict:
        events = self.events_by_claim.get(claim_id, [])
        return {
            "claim_id": claim_id,
            "lineage_id": self.lineage_id_by_claim.get(claim_id),
            "lineage_event_count": len(events),
            "event_types": [e.event_type for e in events],
            "previous_text_snapshot": self.previous_text_snapshot(claim_id),
            "text_versions": self.text_versions(claim_id),
            "latest_revision_actor": self.latest_revision_actor(claim_id),
            "used_in_current_best_explanation": self.has_event(
                claim_id, EVENT_USED_IN_CBE),
            "events": [e.to_dict() for e in events],
        }

    def to_dict(self) -> dict:
        return {
            "memory_version": "v5",
            "event_count": len(self.events),
            "claims_tracked": len(self.events_by_claim),
            "events": [e.to_dict() for e in self.events],
            "lineage_by_claim": {
                cid: self.lineage_summary(cid) for cid in self.events_by_claim
            },
        }


def ensure_knowledge_evolution_memory(session) -> KnowledgeEvolutionMemory:
    """Attach a KnowledgeEvolutionMemory to a session if not already present."""
    memory = getattr(session, "knowledge_evolution_memory", None)
    if memory is None:
        memory = KnowledgeEvolutionMemory()
        session.knowledge_evolution_memory = memory
    return memory


def sync_lineage_payload(graph, claim_id: str, memory: KnowledgeEvolutionMemory) -> None:
    """Mirror lineage metadata onto the claim's graph node payload."""
    node = graph.nodes.get(claim_id)
    if node is None:
        return
    payload = dict(node.payload or {})
    payload.update({
        "lineage_id": memory.lineage_id_by_claim.get(claim_id),
        "lineage_event_count": memory.event_count(claim_id),
        "previous_text_snapshot": memory.previous_text_snapshot(claim_id),
        "latest_revision_actor": memory.latest_revision_actor(claim_id),
        # cross-claim supersession is optional in v5; keys present for forward
        # compatibility, populated only if a genuine supersede is recorded.
        "supersedes": payload.get("supersedes"),
        "superseded_by": payload.get("superseded_by"),
    })
    node.payload = payload
