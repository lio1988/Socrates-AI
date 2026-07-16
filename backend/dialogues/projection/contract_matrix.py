"""
Council Live View Foundation — the explicit event contract matrix.

One row per event type (hardening round 1, review finding 6):

    event type
    → required envelope fields (beyond the always-required core)
    → required payload fields
    → optional payload fields
    → idempotency identity fields (descriptive: what §9.2 col 7 keys on)
    → receipt requirement (envelope receipt_ref MUST be present)
    → public/redacted projection rule

The matrix is ENFORCED twice:
- at runtime: ``events._contract_check`` reads ``required_envelope`` and
  ``receipt_required`` for every draft and sealed event;
- in tests: a 22/22 test asserts each payload model's required/optional
  fields equal this matrix exactly, so model and matrix can never drift.

Changing a row here is a versioned contract change, never a convenience edit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal, Tuple

from .taxonomy import CedEventType

ProjectionRule = Literal["public", "derived", "redacted_until_reveal"]


@dataclass(frozen=True)
class EventContract:
    required_envelope:    Tuple[str, ...]
    required_payload:     Tuple[str, ...]
    optional_payload:     Tuple[str, ...]
    idempotency_identity: Tuple[str, ...]
    receipt_required:     bool
    projection:           ProjectionRule


CONTRACT_MATRIX: Dict[CedEventType, EventContract] = {
    CedEventType.SESSION_CREATED: EventContract(
        required_envelope=(),
        required_payload=("question",),
        optional_payload=(),
        idempotency_identity=("session_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.RUN_STARTED: EventContract(
        required_envelope=(),
        required_payload=(),
        optional_payload=(),
        idempotency_identity=("run_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.ROLE_ASSIGNED: EventContract(
        required_envelope=("phase", "round_index"),
        required_payload=("agent_id", "role"),
        optional_payload=(),
        idempotency_identity=("run_id", "phase", "round_index", "agent_id"),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.PHASE_STARTED: EventContract(
        required_envelope=("phase", "round_index"),
        required_payload=(),
        optional_payload=(),
        idempotency_identity=("run_id", "phase", "round_index"),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.TASK_CREATED: EventContract(
        required_envelope=(),
        required_payload=("task_id", "task_kind", "agent_id", "slot_index",
                          "attempt_index", "schema_name", "context_hash"),
        optional_payload=(),
        idempotency_identity=("task_id",),
        receipt_required=False,
        projection="derived",
    ),
    CedEventType.PROVIDER_REQUESTED: EventContract(
        required_envelope=(),
        required_payload=("task_id", "provider_id", "requested_model"),
        optional_payload=(),
        idempotency_identity=("task_id", "provider_id", "attempt_index"),
        receipt_required=False,
        projection="derived",
    ),
    CedEventType.PROVIDER_COMPLETED: EventContract(
        required_envelope=("receipt_ref",),
        required_payload=("task_id", "provider_id", "returned_model",
                          "latency_ms"),
        optional_payload=("token_usage",),
        idempotency_identity=("task_id", "provider_id", "attempt_index"),
        receipt_required=True,
        projection="public",
    ),
    CedEventType.PROVIDER_FAILED: EventContract(
        required_envelope=(),
        required_payload=("task_id", "provider_id", "status",
                          "failure_category"),
        optional_payload=(),
        idempotency_identity=("task_id", "provider_id", "attempt_index"),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.MOVE_VALIDATED: EventContract(
        required_envelope=("phase", "round_index"),
        required_payload=("move_id", "task_id", "agent_id", "role",
                          "confidence", "raw_digest", "validated_digest"),
        optional_payload=(),
        idempotency_identity=("move_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.DRAFT_CREATED: EventContract(
        required_envelope=(),
        required_payload=("draft_id", "author_agent_id", "move_id",
                          "sections_present"),
        optional_payload=(),
        idempotency_identity=("draft_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.PEER_SCORE_REQUESTED: EventContract(
        required_envelope=(),
        required_payload=("score_task_id", "target_id", "voter_id"),
        optional_payload=(),
        idempotency_identity=("score_task_id",),
        receipt_required=False,
        projection="derived",
    ),
    CedEventType.PEER_SCORE_COMPLETED: EventContract(
        required_envelope=(),
        required_payload=("score_task_id", "score_id", "voter_id",
                          "scored_kind", "overall_score", "penalty_flags"),
        optional_payload=("section", "draft_id"),
        idempotency_identity=("score_task_id",),
        receipt_required=False,
        projection="redacted_until_reveal",
    ),
    CedEventType.PEER_SCORE_MISSING: EventContract(
        required_envelope=(),
        required_payload=("score_task_id", "reason"),
        optional_payload=(),
        idempotency_identity=("score_task_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.QUORUM_EVALUATED: EventContract(
        required_envelope=(),
        required_payload=("scope", "expected", "valid", "status"),
        optional_payload=(),
        idempotency_identity=("run_id", "scope"),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.SECTION_WINNER_SELECTED: EventContract(
        required_envelope=(),
        required_payload=("section", "unresolved"),
        optional_payload=("selected_draft_id", "average_score", "score_count",
                          "variance", "corroboration_count"),
        idempotency_identity=("run_id", "section"),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.ASSEMBLY_COMPLETED: EventContract(
        required_envelope=(),
        required_payload=("answer_id", "sections", "unresolved_sections"),
        optional_payload=("fragmentation", "single_source", "thin_sections"),
        idempotency_identity=("answer_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.BLOCKING_OBJECTION_RAISED: EventContract(
        required_envelope=(),
        required_payload=("ratification_id", "provider_id", "target_section",
                          "severity", "required_fix"),
        optional_payload=(),
        idempotency_identity=("ratification_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.RATIFICATION_VOTE_RECORDED: EventContract(
        required_envelope=(),
        required_payload=("ratification_id", "verdict"),
        optional_payload=("caveat", "target_section"),
        idempotency_identity=("ratification_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.RUNNER_UP_REPLACED: EventContract(
        required_envelope=(),
        required_payload=("section", "from_draft", "to_draft", "via",
                          "round"),
        optional_payload=(),
        idempotency_identity=("run_id", "section", "round"),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.SECTION_UNRESOLVED: EventContract(
        required_envelope=(),
        required_payload=("section", "reason"),
        optional_payload=(),
        idempotency_identity=("run_id", "section"),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.ANSWER_WITHHELD: EventContract(
        required_envelope=(),
        required_payload=("reason", "status"),
        optional_payload=(),
        idempotency_identity=("run_id",),
        receipt_required=False,
        projection="public",
    ),
    CedEventType.RUN_COMPLETED: EventContract(
        required_envelope=(),
        required_payload=("ratification_status",),
        optional_payload=("leaderboard_status",),
        idempotency_identity=("run_id",),
        receipt_required=False,
        projection="public",
    ),
}

# Import-time completeness guard: exactly one row per event type.
_missing = set(CedEventType) - set(CONTRACT_MATRIX)
_extra = set(CONTRACT_MATRIX) - set(CedEventType)
if _missing or _extra:  # pragma: no cover — construction-time invariant
    raise RuntimeError(
        f"CONTRACT_MATRIX incomplete: missing={_missing} extra={_extra}"
    )
