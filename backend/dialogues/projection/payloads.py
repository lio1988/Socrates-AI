"""
Council Live View Foundation — strict typed payload models (one per event).

Required-key validation is NOT enough (audit finding). Every event type maps
to exactly one strict, frozen, versioned Pydantic payload model:

- unknown payload field      → reject (``extra="forbid"``)
- wrong payload field type   → reject (``strict=True``; no lax coercion)
- wrong event/payload pairing→ reject (envelope ``payload_schema`` must equal
                               the registered model's ``PAYLOAD_SCHEMA``)
- wrong payload version      → reject (envelope ``payload_version`` must equal
                               the registered model's ``PAYLOAD_VERSION``)
- NaN / Infinity             → reject (``allow_inf_nan=False`` on every float,
                               plus the envelope's canonical-JSON check)

Naming: ``PAYLOAD_SCHEMA == "<event_type>.payload"`` — e.g. the payload of
``role.assigned`` is ``role.assigned.payload`` v1. Versions move per payload
model, independently of the envelope's ``schema_version``.

The registry ``PAYLOAD_MODELS`` is COMPLETE over the closed taxonomy — an
import-time guard (and a test) enforces it.
"""

from __future__ import annotations

from typing import ClassVar, Dict, List, Optional, Type

from pydantic import BaseModel, ConfigDict, Field

from .taxonomy import CedEventType


_HEX64 = r"^[0-9a-f]{64}$"


class BasePayload(BaseModel):
    """Strict, frozen base for all event payloads."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    PAYLOAD_SCHEMA:  ClassVar[str]
    PAYLOAD_VERSION: ClassVar[int] = 1


class SessionCreatedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "session.created.payload"
    question: str = Field(min_length=1)


class RunStartedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "run.started.payload"
    # Intentionally empty: run identity lives on the envelope. Strict model
    # still rejects any stray field.


class RoleAssignedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "role.assigned.payload"
    agent_id: str = Field(min_length=1)
    role:     str = Field(min_length=1)


class PhaseStartedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "phase.started.payload"
    # Phase identity lives on the envelope (phase + round_index).


class TaskCreatedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "task.created.payload"
    task_id:       str = Field(min_length=1)
    task_kind:     str = Field(min_length=1)
    agent_id:      str = Field(min_length=1)
    slot_index:    int = Field(ge=0)
    attempt_index: int = Field(ge=0)
    schema_name:   str = Field(min_length=1)
    context_hash:  str = Field(min_length=1)


class ProviderRequestedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "provider.requested.payload"
    task_id:         str = Field(min_length=1)
    provider_id:     str = Field(min_length=1)
    requested_model: str = Field(min_length=1)


class ProviderCompletedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "provider.completed.payload"
    task_id:        str = Field(min_length=1)
    provider_id:    str = Field(min_length=1)
    returned_model: str = Field(min_length=1)
    latency_ms:     float = Field(ge=0.0, allow_inf_nan=False)
    token_usage:    Optional[Dict[str, int]] = None


class ProviderFailedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "provider.failed.payload"
    task_id:          str = Field(min_length=1)
    provider_id:      str = Field(min_length=1)
    status:           str = Field(min_length=1)
    failure_category: str = Field(min_length=1)


class MoveValidatedPayload(BasePayload):
    """§9.3: raw vs validated digests are SPLIT and both required."""
    PAYLOAD_SCHEMA: ClassVar[str] = "move.validated.payload"
    move_id:          str = Field(min_length=1)
    task_id:          str = Field(min_length=1)
    agent_id:         str = Field(min_length=1)
    role:             str = Field(min_length=1)
    confidence:       float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    raw_digest:       str = Field(pattern=_HEX64)
    validated_digest: str = Field(pattern=_HEX64)


class DraftCreatedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "draft.created.payload"
    draft_id:        str = Field(min_length=1)
    author_agent_id: str = Field(min_length=1)
    move_id:         str = Field(min_length=1)


class PeerScoreRequestedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "peer_score.requested.payload"
    score_task_id: str = Field(min_length=1)
    target_id:     str = Field(min_length=1)
    voter_id:      str = Field(min_length=1)


class PeerScoreCompletedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "peer_score.completed.payload"
    score_task_id: str = Field(min_length=1)
    voter_id:      str = Field(min_length=1)
    overall_score: Optional[float] = Field(
        default=None, ge=0.0, le=10.0, allow_inf_nan=False)


class PeerScoreMissingPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "peer_score.missing.payload"
    score_task_id: str = Field(min_length=1)
    reason:        str = Field(min_length=1)


class QuorumEvaluatedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "quorum.evaluated.payload"
    scope:    str = Field(min_length=1)
    expected: int = Field(ge=0)
    valid:    int = Field(ge=0)
    status:   str = Field(min_length=1)


class SectionWinnerSelectedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "section_winner.selected.payload"
    section:            str = Field(min_length=1)
    selected_draft_id:  str = Field(min_length=1)
    average_score:      float = Field(ge=0.0, le=10.0, allow_inf_nan=False)
    score_count:        int = Field(ge=0)
    unresolved:         bool
    variance:           Optional[float] = Field(
        default=None, ge=0.0, allow_inf_nan=False)
    corroboration_count: Optional[int] = Field(default=None, ge=0)


class AssemblyCompletedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "assembly.completed.payload"
    answer_id:           str = Field(min_length=1)
    unresolved_sections: List[str]
    fragmentation:       Optional[float] = Field(
        default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    single_source:       Optional[bool] = None


class BlockingObjectionRaisedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "blocking_objection.raised.payload"
    ratification_id: str = Field(min_length=1)
    target_section:  str = Field(min_length=1)
    severity:        str = Field(min_length=1)
    required_fix:    str = Field(min_length=1)


class RatificationVoteRecordedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "ratification_vote.recorded.payload"
    ratification_id: str = Field(min_length=1)
    verdict:         str = Field(min_length=1)
    caveat:          Optional[str] = None
    target_section:  Optional[str] = None


class RunnerUpReplacedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "runner_up.replaced.payload"
    section:    str = Field(min_length=1)
    from_draft: str = Field(min_length=1)
    to_draft:   str = Field(min_length=1)
    round:      int = Field(ge=0)


class SectionUnresolvedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "section.unresolved.payload"
    section: str = Field(min_length=1)
    reason:  str = Field(min_length=1)


class AnswerWithheldPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "answer.withheld.payload"
    reason: str = Field(min_length=1)
    status: str = Field(min_length=1)


class RunCompletedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "run.completed.payload"
    ratification_status: str = Field(min_length=1)
    leaderboard_status:  Optional[str] = None


PAYLOAD_MODELS: Dict[CedEventType, Type[BasePayload]] = {
    CedEventType.SESSION_CREATED:            SessionCreatedPayload,
    CedEventType.RUN_STARTED:                RunStartedPayload,
    CedEventType.ROLE_ASSIGNED:              RoleAssignedPayload,
    CedEventType.PHASE_STARTED:              PhaseStartedPayload,
    CedEventType.TASK_CREATED:               TaskCreatedPayload,
    CedEventType.PROVIDER_REQUESTED:         ProviderRequestedPayload,
    CedEventType.PROVIDER_COMPLETED:         ProviderCompletedPayload,
    CedEventType.PROVIDER_FAILED:            ProviderFailedPayload,
    CedEventType.MOVE_VALIDATED:             MoveValidatedPayload,
    CedEventType.DRAFT_CREATED:              DraftCreatedPayload,
    CedEventType.PEER_SCORE_REQUESTED:       PeerScoreRequestedPayload,
    CedEventType.PEER_SCORE_COMPLETED:       PeerScoreCompletedPayload,
    CedEventType.PEER_SCORE_MISSING:         PeerScoreMissingPayload,
    CedEventType.QUORUM_EVALUATED:           QuorumEvaluatedPayload,
    CedEventType.SECTION_WINNER_SELECTED:    SectionWinnerSelectedPayload,
    CedEventType.ASSEMBLY_COMPLETED:         AssemblyCompletedPayload,
    CedEventType.BLOCKING_OBJECTION_RAISED:  BlockingObjectionRaisedPayload,
    CedEventType.RATIFICATION_VOTE_RECORDED: RatificationVoteRecordedPayload,
    CedEventType.RUNNER_UP_REPLACED:         RunnerUpReplacedPayload,
    CedEventType.SECTION_UNRESOLVED:         SectionUnresolvedPayload,
    CedEventType.ANSWER_WITHHELD:            AnswerWithheldPayload,
    CedEventType.RUN_COMPLETED:              RunCompletedPayload,
}

# Import-time completeness guard: the registry must cover the closed taxonomy
# exactly — no orphan event type, no orphan payload model.
_missing = set(CedEventType) - set(PAYLOAD_MODELS)
_extra = set(PAYLOAD_MODELS) - set(CedEventType)
if _missing or _extra:  # pragma: no cover — construction-time invariant
    raise RuntimeError(
        f"PAYLOAD_MODELS registry incomplete: missing={_missing} extra={_extra}"
    )
for _et, _model in PAYLOAD_MODELS.items():
    if _model.PAYLOAD_SCHEMA != f"{_et.value}.payload":  # pragma: no cover
        raise RuntimeError(
            f"payload schema name mismatch for {_et.value}: "
            f"{_model.PAYLOAD_SCHEMA}"
        )
