"""
Council Live View Foundation — the explicit event contract matrix.

One row per event type (hardening rounds 1–2, review findings 6/R2-1/R2-5):

    event type
    → required envelope fields (beyond the always-required core)
    → required payload fields
    → optional payload fields
    → idempotency identity fields  (EXECUTABLE — see below)
    → receipt rule                 (required / optional_pending_integration /
                                    none)
    → public/redacted projection rule

The matrix is ENFORCED three ways:
- at runtime: ``events._contract_check`` reads ``required_envelope`` and the
  receipt rule for every draft and sealed event, and VERIFIES that the
  event's ``idempotency_key`` equals the contract-derived key
  (``events.derive_event_idempotency_key``) — a caller-supplied wrong key is
  rejected (round 2, finding 1: identity is executable, not descriptive);
- in tests: a 22/22 test asserts each payload model's required/optional
  fields equal this matrix exactly, plus 22/22 identity-derivation tests;
- the registry itself is exposed as an immutable ``MappingProxyType`` view —
  runtime validation behavior cannot be changed by mutating it (round 2,
  finding 6).

Identity semantics (round 2, finding 1):
- identity fields may live on the envelope (session_id, run_id, phase,
  round_index) or in the payload (task_id, move_id, …);
- provider events include ``attempt_index`` — a bounded retry is a NEW
  canonical attempt, never a conflict with the first one;
- ratification votes are identified per (ratification_id, voter_id) and
  blocking objections per (ratification_id, provider_id) — two voters can
  never collide, and a re-emission by the same voter with different content
  is a conflict;
- ratification-repair re-votes (Phase 19) produce NEW RatificationVerdicts
  with NEW ratification_ids — they are new canonical events by construction,
  never conflicts with round-1 votes; runner-up replacements carry the
  repair ``round`` in their identity for the same reason.

Receipt rule (round 2, finding 5): ``receipt_ref`` is a typed reference to an
immutable receipt — format ``sha256:<64 hex>`` (the receipt digest under
which the AtomicReceiptStore record is addressable). Format is verifiable
without store access; content verification happens at projection-integration
time. ``required`` = the event may not exist without one
(provider.completed — the immutable-provider-receipt invariant).
``optional_pending_integration`` = the parent architecture links these events
to receipts, but the current runtime does not yet mint them
(provider.failed, ratification_vote.recorded, blocking_objection.raised) —
the matrix says so honestly instead of claiming full parity. ``none`` = the
event carries NO receipt_ref (present value is a contract violation).

Changing a row here is a versioned contract change, never a convenience edit.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Dict, Literal, Mapping, Tuple

from .taxonomy import CedEventType

ProjectionRule = Literal["public", "derived", "redacted_until_reveal"]
ReceiptRule = Literal["required", "optional_pending_integration", "none"]


@dataclass(frozen=True)
class EventContract:
    required_envelope:    Tuple[str, ...]
    required_payload:     Tuple[str, ...]
    optional_payload:     Tuple[str, ...]
    idempotency_identity: Tuple[str, ...]
    receipt:              ReceiptRule
    projection:           ProjectionRule


_CONTRACT_MATRIX: Dict[CedEventType, EventContract] = {
    CedEventType.SESSION_CREATED: EventContract(
        required_envelope=(),
        required_payload=("question",),
        optional_payload=(),
        idempotency_identity=("session_id",),
        receipt="none",
        projection="public",
    ),
    CedEventType.RUN_STARTED: EventContract(
        required_envelope=(),
        required_payload=(),
        optional_payload=(),
        idempotency_identity=("run_id",),
        receipt="none",
        projection="public",
    ),
    CedEventType.ROLE_ASSIGNED: EventContract(
        required_envelope=("phase", "round_index"),
        required_payload=("agent_id", "role"),
        optional_payload=(),
        idempotency_identity=("run_id", "phase", "round_index", "agent_id"),
        receipt="none",
        projection="public",
    ),
    CedEventType.PHASE_STARTED: EventContract(
        required_envelope=("phase", "round_index"),
        required_payload=(),
        optional_payload=(),
        idempotency_identity=("run_id", "phase", "round_index"),
        receipt="none",
        projection="public",
    ),
    CedEventType.TASK_CREATED: EventContract(
        required_envelope=(),
        required_payload=("task_id", "task_kind", "agent_id", "slot_index",
                          "attempt_index", "schema_name", "context_hash"),
        optional_payload=(),
        idempotency_identity=("task_id",),
        receipt="none",
        projection="derived",
    ),
    CedEventType.PROVIDER_REQUESTED: EventContract(
        required_envelope=(),
        required_payload=("task_id", "provider_id", "requested_model",
                          "attempt_index"),
        optional_payload=(),
        idempotency_identity=("task_id", "provider_id", "attempt_index"),
        receipt="none",
        projection="derived",
    ),
    CedEventType.PROVIDER_COMPLETED: EventContract(
        required_envelope=("receipt_ref",),
        required_payload=("task_id", "provider_id", "returned_model",
                          "latency_ms", "attempt_index"),
        optional_payload=("token_usage",),
        idempotency_identity=("task_id", "provider_id", "attempt_index"),
        receipt="required",
        projection="public",
    ),
    CedEventType.PROVIDER_FAILED: EventContract(
        required_envelope=(),
        required_payload=("task_id", "provider_id", "status",
                          "failure_category", "attempt_index"),
        optional_payload=(),
        idempotency_identity=("task_id", "provider_id", "attempt_index"),
        receipt="optional_pending_integration",
        projection="public",
    ),
    CedEventType.MOVE_VALIDATED: EventContract(
        required_envelope=("phase", "round_index"),
        required_payload=("move_id", "task_id", "agent_id", "role",
                          "confidence", "raw_digest", "validated_digest"),
        optional_payload=(),
        idempotency_identity=("move_id",),
        receipt="none",
        projection="public",
    ),
    CedEventType.DRAFT_CREATED: EventContract(
        required_envelope=(),
        required_payload=("draft_id", "author_agent_id", "move_id",
                          "sections_present"),
        optional_payload=(),
        idempotency_identity=("draft_id",),
        receipt="none",
        projection="public",
    ),
    CedEventType.PEER_SCORE_REQUESTED: EventContract(
        required_envelope=(),
        required_payload=("score_task_id", "target_id", "voter_id"),
        optional_payload=(),
        idempotency_identity=("score_task_id",),
        receipt="none",
        projection="derived",
    ),
    CedEventType.PEER_SCORE_COMPLETED: EventContract(
        required_envelope=(),
        required_payload=("score_task_id", "score_id", "voter_id",
                          "scored_kind", "overall_score", "penalty_flags"),
        optional_payload=("section", "draft_id"),
        idempotency_identity=("score_task_id",),
        receipt="none",
        projection="redacted_until_reveal",
    ),
    CedEventType.PEER_SCORE_MISSING: EventContract(
        required_envelope=(),
        required_payload=("score_task_id", "reason"),
        optional_payload=(),
        idempotency_identity=("score_task_id",),
        receipt="none",
        projection="public",
    ),
    CedEventType.QUORUM_EVALUATED: EventContract(
        required_envelope=(),
        required_payload=("scope", "expected", "valid", "status"),
        optional_payload=(),
        idempotency_identity=("run_id", "scope"),
        receipt="none",
        projection="public",
    ),
    CedEventType.SECTION_WINNER_SELECTED: EventContract(
        required_envelope=(),
        required_payload=("section", "unresolved"),
        optional_payload=("selected_draft_id", "average_score", "score_count",
                          "variance", "corroboration_count",
                          "assembly_flags"),
        idempotency_identity=("run_id", "section"),
        receipt="none",
        projection="public",
    ),
    CedEventType.ASSEMBLY_COMPLETED: EventContract(
        required_envelope=(),
        required_payload=("answer_id", "sections", "unresolved_sections"),
        optional_payload=("fragmentation", "single_source", "thin_sections",
                          "flags_by_section"),
        idempotency_identity=("answer_id",),
        receipt="none",
        projection="public",
    ),
    CedEventType.BLOCKING_OBJECTION_RAISED: EventContract(
        required_envelope=(),
        required_payload=("ratification_id", "provider_id", "target_section",
                          "severity", "required_fix"),
        optional_payload=(),
        idempotency_identity=("ratification_id", "provider_id"),
        receipt="optional_pending_integration",
        projection="public",
    ),
    CedEventType.RATIFICATION_VOTE_RECORDED: EventContract(
        required_envelope=(),
        required_payload=("ratification_id", "voter_id", "verdict"),
        optional_payload=("caveat", "target_section", "provider_id"),
        idempotency_identity=("ratification_id", "voter_id"),
        receipt="optional_pending_integration",
        projection="public",
    ),
    CedEventType.RUNNER_UP_REPLACED: EventContract(
        required_envelope=(),
        required_payload=("section", "from_draft", "to_draft", "via",
                          "round"),
        optional_payload=(),
        idempotency_identity=("run_id", "section", "round"),
        receipt="none",
        projection="public",
    ),
    CedEventType.SECTION_UNRESOLVED: EventContract(
        required_envelope=(),
        required_payload=("section", "reason"),
        optional_payload=(),
        idempotency_identity=("run_id", "section"),
        receipt="none",
        projection="public",
    ),
    CedEventType.ANSWER_WITHHELD: EventContract(
        required_envelope=(),
        required_payload=("reason", "status"),
        optional_payload=(),
        idempotency_identity=("run_id",),
        receipt="none",
        projection="public",
    ),
    CedEventType.RUN_COMPLETED: EventContract(
        required_envelope=(),
        required_payload=("ratification_status",),
        optional_payload=("leaderboard_status",),
        idempotency_identity=("run_id",),
        receipt="none",
        projection="public",
    ),
}

# Import-time completeness guard: exactly one row per event type.
_missing = set(CedEventType) - set(_CONTRACT_MATRIX)
_extra = set(_CONTRACT_MATRIX) - set(CedEventType)
if _missing or _extra:  # pragma: no cover — construction-time invariant
    raise RuntimeError(
        f"CONTRACT_MATRIX incomplete: missing={_missing} extra={_extra}"
    )

#: Immutable public view (round 2, finding 6): the matrix cannot be mutated
#: to weaken runtime validation. EventContract rows are frozen dataclasses.
CONTRACT_MATRIX: Mapping[CedEventType, EventContract] = MappingProxyType(
    _CONTRACT_MATRIX
)
