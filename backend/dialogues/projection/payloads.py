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

Hardening round 1 (review findings 6 + 9):
- fields now match the parent mapping §9.2 exactly — see
  ``contract_matrix.CONTRACT_MATRIX`` (a 22/22 test enforces agreement);
- closed vocabularies: sections/roles/verdicts/penalty flags/status words are
  Literals, never free non-empty strings;
- semantic coherence validators: quorum ``valid <= expected``; a COMPLETED
  peer score must actually carry a score (missing scores are the separate
  ``peer_score.missing`` event); an unresolved section winner carries no
  selection data (and a resolved one must); assembly section refs must agree
  with ``unresolved_sections``.

Naming: ``PAYLOAD_SCHEMA == "<event_type>.payload"``. Versions move per
payload model, independently of the envelope's ``schema_version``. The
registry ``PAYLOAD_MODELS`` is COMPLETE over the closed taxonomy — an
import-time guard (and a test) enforces it.
"""

from __future__ import annotations

from typing import ClassVar, Dict, List, Literal, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .taxonomy import (
    CedEventType,
    FailureCategoryLiteral,
    LeaderboardStatusLiteral,
    PenaltyFlagLiteral,
    ProviderFailureStatusLiteral,
    QuorumStatusLiteral,
    RatificationStatusLiteral,
    RoleLiteral,
    ScoredKindLiteral,
    SectionLiteral,
    VerdictLiteral,
    ViaLiteral,
    WithheldStatusLiteral,
)


_HEX64 = r"^[0-9a-f]{64}$"

#: Locked: the blocking-objection event exists only at critical severity —
#: CED raises it solely for a schema-valid CRITICAL block.
VerdictSeverity = Literal["critical"]


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
    role:     RoleLiteral


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
    status:           ProviderFailureStatusLiteral
    failure_category: FailureCategoryLiteral


class MoveValidatedPayload(BasePayload):
    """§9.3: raw vs validated digests are SPLIT and both required.
    Envelope phase/round_index are also required for this event (matrix)."""
    PAYLOAD_SCHEMA: ClassVar[str] = "move.validated.payload"
    move_id:          str = Field(min_length=1)
    task_id:          str = Field(min_length=1)
    agent_id:         str = Field(min_length=1)
    role:             RoleLiteral
    confidence:       float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    raw_digest:       str = Field(pattern=_HEX64)
    validated_digest: str = Field(pattern=_HEX64)


class DraftCreatedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "draft.created.payload"
    draft_id:         str = Field(min_length=1)
    author_agent_id:  str = Field(min_length=1)
    move_id:          str = Field(min_length=1)
    # Parent mapping: "section names present" — the locked sections this
    # draft actually filled.
    sections_present: List[SectionLiteral] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_sections(self) -> "DraftCreatedPayload":
        if len(self.sections_present) != len(set(self.sections_present)):
            raise ValueError("sections_present must not contain duplicates")
        return self


class PeerScoreRequestedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "peer_score.requested.payload"
    score_task_id: str = Field(min_length=1)
    target_id:     str = Field(min_length=1)
    voter_id:      str = Field(min_length=1)


class PeerScoreCompletedPayload(BasePayload):
    """
    A COMPLETED peer score must carry an actual score — a missing/failed
    score is the separate ``peer_score.missing`` event (coherence, finding 9).
    Section-scored entries must name section+draft; move-scored must not.
    """
    PAYLOAD_SCHEMA: ClassVar[str] = "peer_score.completed.payload"
    score_task_id: str = Field(min_length=1)
    score_id:      str = Field(min_length=1)
    voter_id:      str = Field(min_length=1)
    scored_kind:   ScoredKindLiteral
    overall_score: float = Field(ge=0.0, le=10.0, allow_inf_nan=False)
    penalty_flags: List[PenaltyFlagLiteral]
    section:       Optional[SectionLiteral] = None
    draft_id:      Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _coherent_target(self) -> "PeerScoreCompletedPayload":
        if len(self.penalty_flags) != len(set(self.penalty_flags)):
            raise ValueError("penalty_flags must not contain duplicates")
        if self.scored_kind == "section":
            if self.section is None or self.draft_id is None:
                raise ValueError(
                    "section-scored peer score requires section and draft_id"
                )
        else:
            if self.section is not None or self.draft_id is not None:
                raise ValueError(
                    "move-scored peer score must not carry section/draft_id"
                )
        return self


class PeerScoreMissingPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "peer_score.missing.payload"
    score_task_id: str = Field(min_length=1)
    reason:        str = Field(min_length=1)


class QuorumEvaluatedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "quorum.evaluated.payload"
    scope:    str = Field(min_length=1)
    expected: int = Field(ge=0)
    valid:    int = Field(ge=0)
    status:   QuorumStatusLiteral

    @model_validator(mode="after")
    def _coherent_counts(self) -> "QuorumEvaluatedPayload":
        if self.valid > self.expected:
            raise ValueError(
                f"quorum valid ({self.valid}) cannot exceed expected "
                f"({self.expected})"
            )
        return self


class SectionWinnerSelectedPayload(BasePayload):
    """
    Coherence (finding 9): a RESOLVED winner must carry selection data; an
    UNRESOLVED one must carry none — there is no winner to describe.
    """
    PAYLOAD_SCHEMA: ClassVar[str] = "section_winner.selected.payload"
    section:             SectionLiteral
    unresolved:          bool
    selected_draft_id:   Optional[str] = Field(default=None, min_length=1)
    average_score:       Optional[float] = Field(
        default=None, ge=0.0, le=10.0, allow_inf_nan=False)
    score_count:         Optional[int] = Field(default=None, ge=0)
    variance:            Optional[float] = Field(
        default=None, ge=0.0, allow_inf_nan=False)
    corroboration_count: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _coherent_selection(self) -> "SectionWinnerSelectedPayload":
        selection = (self.selected_draft_id, self.average_score,
                     self.score_count, self.variance,
                     self.corroboration_count)
        if self.unresolved:
            if any(v is not None for v in selection):
                raise ValueError(
                    "unresolved section winner must not carry selection data"
                )
        else:
            if (self.selected_draft_id is None or self.average_score is None
                    or self.score_count is None):
                raise ValueError(
                    "resolved section winner requires selected_draft_id, "
                    "average_score and score_count"
                )
        return self


class AssemblySectionRef(BaseModel):
    """One assembled section reference inside assembly.completed."""
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    section:           SectionLiteral
    selected_draft_id: Optional[str] = Field(default=None, min_length=1)
    unresolved:        bool

    @model_validator(mode="after")
    def _coherent(self) -> "AssemblySectionRef":
        if self.unresolved and self.selected_draft_id is not None:
            raise ValueError("unresolved section carries no selected draft")
        if not self.unresolved and self.selected_draft_id is None:
            raise ValueError("resolved section requires selected_draft_id")
        return self


class AssemblyCompletedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "assembly.completed.payload"
    answer_id:           str = Field(min_length=1)
    sections:            List[AssemblySectionRef] = Field(min_length=1)
    unresolved_sections: List[SectionLiteral]
    fragmentation:       Optional[float] = Field(
        default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    single_source:       Optional[bool] = None
    thin_sections:       Optional[List[SectionLiteral]] = None

    @model_validator(mode="after")
    def _coherent_sections(self) -> "AssemblyCompletedPayload":
        names = [ref.section for ref in self.sections]
        if len(names) != len(set(names)):
            raise ValueError("assembly sections must not repeat a section")
        flagged = {ref.section for ref in self.sections if ref.unresolved}
        declared = set(self.unresolved_sections)
        if len(self.unresolved_sections) != len(declared):
            raise ValueError("unresolved_sections must not contain duplicates")
        if flagged != declared:
            raise ValueError(
                "unresolved_sections must equal the section refs flagged "
                f"unresolved (refs={sorted(flagged)}, "
                f"declared={sorted(declared)})"
            )
        if self.thin_sections is not None:
            if not set(self.thin_sections) <= set(names):
                raise ValueError(
                    "thin_sections must reference assembled sections"
                )
        return self


class BlockingObjectionRaisedPayload(BasePayload):
    """Raised only for a schema-valid CRITICAL block — severity is locked."""
    PAYLOAD_SCHEMA: ClassVar[str] = "blocking_objection.raised.payload"
    ratification_id: str = Field(min_length=1)
    provider_id:     str = Field(min_length=1)
    target_section:  SectionLiteral
    severity:        VerdictSeverity
    required_fix:    str = Field(min_length=1)


class RatificationVoteRecordedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "ratification_vote.recorded.payload"
    ratification_id: str = Field(min_length=1)
    verdict:         VerdictLiteral
    caveat:          Optional[str] = Field(default=None, min_length=1)
    target_section:  Optional[SectionLiteral] = None


class RunnerUpReplacedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "runner_up.replaced.payload"
    section:    SectionLiteral
    from_draft: str = Field(min_length=1)
    to_draft:   str = Field(min_length=1)
    via:        ViaLiteral
    round:      int = Field(ge=0)

    @model_validator(mode="after")
    def _coherent(self) -> "RunnerUpReplacedPayload":
        if self.from_draft == self.to_draft:
            raise ValueError("runner-up replacement must change the draft")
        return self


class SectionUnresolvedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "section.unresolved.payload"
    section: SectionLiteral
    reason:  str = Field(min_length=1)


class AnswerWithheldPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "answer.withheld.payload"
    reason: str = Field(min_length=1)
    status: WithheldStatusLiteral


class RunCompletedPayload(BasePayload):
    PAYLOAD_SCHEMA: ClassVar[str] = "run.completed.payload"
    ratification_status: RatificationStatusLiteral
    leaderboard_status:  Optional[LeaderboardStatusLiteral] = None


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
