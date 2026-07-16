"""
Council Live View Foundation — closed event taxonomy + typed stream contract.

The taxonomy is CLOSED: exactly these dotted names, nothing else. Adding an
event type is a contract change (new payload model + registry entry + tests),
never an ad-hoc string.

Stream contract (session/run sequencing, audited):

- Every event belongs to exactly ONE stream — the unit of sequencing.
- ``session.created`` is **session-scoped**: it carries NO run_id (typed
  ``None``, never a sentinel string) and sequences on the session stream
  ``session:<session_id>``. Future session-level events join that stream.
- Every other event type is **run-scoped**: ``run_id`` is required, non-empty,
  and sentinel spellings ("none", "null", …) are rejected as a contract
  violation. Run-scoped events sequence on ``run:<run_id>``.
- ``stream_id`` is DERIVED (``session:…`` / ``run:…``), never caller-asserted,
  so an event can never claim membership in a stream its ids do not define.
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet


class CedEventType(str, Enum):
    """Closed dotted taxonomy — exact names, per the audited contract."""
    SESSION_CREATED            = "session.created"
    RUN_STARTED                = "run.started"
    ROLE_ASSIGNED              = "role.assigned"
    PHASE_STARTED              = "phase.started"
    TASK_CREATED               = "task.created"
    PROVIDER_REQUESTED         = "provider.requested"
    PROVIDER_COMPLETED         = "provider.completed"
    PROVIDER_FAILED            = "provider.failed"
    MOVE_VALIDATED             = "move.validated"
    DRAFT_CREATED              = "draft.created"
    PEER_SCORE_REQUESTED       = "peer_score.requested"
    PEER_SCORE_COMPLETED       = "peer_score.completed"
    PEER_SCORE_MISSING         = "peer_score.missing"
    QUORUM_EVALUATED           = "quorum.evaluated"
    SECTION_WINNER_SELECTED    = "section_winner.selected"
    ASSEMBLY_COMPLETED         = "assembly.completed"
    BLOCKING_OBJECTION_RAISED  = "blocking_objection.raised"
    RATIFICATION_VOTE_RECORDED = "ratification_vote.recorded"
    RUNNER_UP_REPLACED         = "runner_up.replaced"
    SECTION_UNRESOLVED         = "section.unresolved"
    ANSWER_WITHHELD            = "answer.withheld"
    RUN_COMPLETED              = "run.completed"


#: Event types that sequence on the SESSION stream and must carry run_id=None.
SESSION_SCOPED_TYPES: FrozenSet[CedEventType] = frozenset({
    CedEventType.SESSION_CREATED,
})

#: Event types whose envelope MUST carry phase + round_index.
PHASE_REQUIRED_TYPES: FrozenSet[CedEventType] = frozenset({
    CedEventType.ROLE_ASSIGNED,
    CedEventType.PHASE_STARTED,
})

#: Sentinel spellings that are NEVER a valid run_id (typed-stream rule:
#: absence is expressed as None on a session-scoped event, not as a string).
FORBIDDEN_RUN_ID_SENTINELS: FrozenSet[str] = frozenset({
    "", "none", "null", "nil", "n/a", "na", "undefined",
})


def session_stream_id(session_id: str) -> str:
    """Typed stream id for session-scoped sequencing."""
    return f"session:{session_id}"


def run_stream_id(run_id: str) -> str:
    """Typed stream id for run-scoped sequencing."""
    return f"run:{run_id}"
