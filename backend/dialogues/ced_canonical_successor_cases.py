"""Frozen recorded-observation blueprints for the Phase 8 parity corpus.

The corpus retains exact raw outputs and enough harness-only provenance to
reconstruct each recorded opening root.  It deliberately contains no parsed
move, acceptance label inside an observation, successor state, move identity,
reward, or other future-derived truth.  ``materialize`` binds a blueprint to a
previously validated pending transition; canonical CED processing remains the
only source of an outcome.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ced_canonical_successor_contracts import (
    HistoricalUsageKnowledge,
    ObservationCaptureKind,
    ObservationTransportStatus,
    PendingCanonicalTransition,
    RecordedCanonicalObservation,
    RecordedHistoricalUsage,
    RecordedObservationProvenance,
)
from .socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)


CANONICAL_SUCCESSOR_CORPUS_VERSION = (
    "ced-canonical-successor-parity-corpus/v0"
)
RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION = (
    "ced-recorded-observation-blueprint/v0"
)


class RecordedObservationFixtureRole(str, Enum):
    """Evaluator-side route labels; never copied into an observation."""

    ACCEPTED_REFERENCE = "accepted_reference"
    CONTENT_CONTRACT_REFERENCE = "content_contract_reference"
    INJECTION_FIREWALL_REFERENCE = "injection_firewall_reference"
    INVALID_JSON_REFERENCE = "invalid_json_reference"
    SCHEMA_ERROR_REFERENCE = "schema_error_reference"


class _FrozenCorpusContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


class RecordedObservationBlueprint(_FrozenCorpusContract):
    """Root-independent exact fixture output plus harness-only root metadata."""

    schema_version: Literal[
        RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION
    ] = RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION
    case_id: Optional[str] = None
    case_name: str
    fixture_role: RecordedObservationFixtureRole

    # Harness-only input used to build the same root request.  The observation
    # receives only the normalized task/request digests from ``pending``.
    recorded_question: str

    source_artifact_id: str
    source_artifact_digest: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    capture_kind: ObservationCaptureKind
    transport_status: ObservationTransportStatus
    transport_error_code: Optional[str] = None
    raw_text: Optional[str] = None
    historical_usage: RecordedHistoricalUsage

    _nonblank_fields = field_validator(
        "case_name", "recorded_question", "source_artifact_id"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "RecordedObservationBlueprint":
        # The v0 corpus consists only of exact raw outputs that were delivered
        # by deterministic offline fixtures. Transport failures belong to the
        # environment failure matrix, not this raw-observation corpus.
        if self.transport_status is not ObservationTransportStatus.DELIVERED:
            raise ContractValidationError(
                "the v0 frozen corpus requires delivered raw observations"
            )
        if self.raw_text is None:
            raise ContractValidationError(
                "a delivered corpus blueprint requires exact raw_text"
            )
        if self.transport_error_code is not None:
            raise ContractValidationError(
                "a delivered corpus blueprint cannot contain a transport error"
            )

        expected_source_digest = hashlib.sha256(
            canonical_json(self.source_semantic_payload()).encode("utf-8")
        ).hexdigest()
        if (
            self.source_artifact_digest is not None
            and self.source_artifact_digest != expected_source_digest
        ):
            raise ContractValidationError(
                "source_artifact_digest does not match the frozen fixture payload"
            )
        object.__setattr__(
            self, "source_artifact_digest", expected_source_digest
        )

        expected_case_id = stable_contract_id(
            "cedobscase",
            {
                "schema_version": self.schema_version,
                "case_name": self.case_name,
                "fixture_role": self.fixture_role.value,
                "source_artifact_digest": expected_source_digest,
            },
        )
        if self.case_id is not None and self.case_id != expected_case_id:
            raise ContractValidationError(
                "case_id does not match frozen corpus semantics"
            )
        object.__setattr__(self, "case_id", expected_case_id)
        return self

    def source_semantic_payload(self) -> dict[str, object]:
        """Exact source payload; excludes evaluator-side outcome routing."""

        return {
            "schema_version": self.schema_version,
            "recorded_question": self.recorded_question,
            "source_artifact_id": self.source_artifact_id,
            "capture_kind": self.capture_kind.value,
            "transport_status": self.transport_status.value,
            "transport_error_code": self.transport_error_code,
            "raw_text": self.raw_text,
            "historical_usage": self.historical_usage.identity_payload(),
        }

    def materialize(
        self,
        pending: PendingCanonicalTransition,
        *,
        capture_id: Optional[str] = None,
        source_task_id: Optional[str] = None,
        recorded_response_id: Optional[str] = None,
        recorded_request_digest: Optional[str] = None,
    ) -> RecordedCanonicalObservation:
        """Bind raw fixture truth to one validated pending task.

        Audit-only IDs default to ``None`` because the existing donors did not
        durably preserve their random runtime identifiers.  Inventing them
        would weaken rather than improve provenance.
        """

        task = pending.canonical_task
        assert self.source_artifact_digest is not None
        return RecordedCanonicalObservation(
            capture_id=capture_id,
            source_task_id=source_task_id,
            recorded_response_id=recorded_response_id,
            recorded_request_digest=recorded_request_digest,
            action_id=pending.selected_action.action_id,
            phase=task.phase,
            round_number=task.round_number,
            slot_index=task.slot_index,
            attempt_index=task.attempt_index,
            agent_id=task.agent_id,
            role=task.role,
            task_kind=task.task_kind,
            task_semantic_digest=task.task_semantic_digest,
            request_semantic_digest=task.request_semantic_digest,
            provider_id=pending.expected_provider_id,
            configured_model_id=pending.expected_model_id,
            actual_model_id=pending.expected_model_id,
            model_config_digest=task.model_config_digest,
            transport_status=self.transport_status,
            transport_error_code=self.transport_error_code,
            raw_text=self.raw_text,
            historical_usage=self.historical_usage,
            provenance=RecordedObservationProvenance(
                capture_kind=self.capture_kind,
                source_artifact_id=self.source_artifact_id,
                source_artifact_digest=self.source_artifact_digest,
                source_revision=CANONICAL_SUCCESSOR_CORPUS_VERSION,
            ),
        )


class RecordedObservationCorpus(_FrozenCorpusContract):
    """The complete pre-result frozen v0 observation corpus."""

    corpus_version: Literal[
        CANONICAL_SUCCESSOR_CORPUS_VERSION
    ] = CANONICAL_SUCCESSOR_CORPUS_VERSION
    corpus_id: Optional[str] = None
    cases: Tuple[RecordedObservationBlueprint, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "RecordedObservationCorpus":
        ordered = tuple(sorted(self.cases, key=lambda item: item.case_name))
        if len(ordered) != 5:
            raise ContractValidationError(
                "the v0 recorded-observation corpus requires exactly five cases"
            )
        if len({case.case_id for case in ordered}) != len(ordered):
            raise ContractValidationError("corpus case IDs must be unique")
        if len({case.case_name for case in ordered}) != len(ordered):
            raise ContractValidationError("corpus case names must be unique")
        if {case.fixture_role for case in ordered} != set(
            RecordedObservationFixtureRole
        ):
            raise ContractValidationError(
                "the v0 corpus requires one case for every frozen fixture role"
            )
        object.__setattr__(self, "cases", ordered)

        expected = stable_contract_id(
            "cedobscorpus",
            {
                "corpus_version": self.corpus_version,
                "case_ids": [case.case_id for case in ordered],
            },
        )
        if self.corpus_id is not None and self.corpus_id != expected:
            raise ContractValidationError(
                "corpus_id does not match the frozen case set"
            )
        object.__setattr__(self, "corpus_id", expected)
        return self

    def case(self, case_name: str) -> RecordedObservationBlueprint:
        try:
            return next(item for item in self.cases if item.case_name == case_name)
        except StopIteration as exc:
            raise KeyError(case_name) from exc


_OFFLINE_FIXTURE_USAGE = RecordedHistoricalUsage(
    knowledge=HistoricalUsageKnowledge.PARTIAL,
    model_calls=0,
    tool_calls=0,
    tokens=0,
    cost_microusd=0,
    wall_time_ms=None,
    observation_acquisitions=1,
)


FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS = RecordedObservationCorpus(
    cases=(
        RecordedObservationBlueprint(
            case_name="opening-scripted-mock",
            fixture_role=RecordedObservationFixtureRole.ACCEPTED_REFERENCE,
            recorded_question="Is knowledge merely justified true belief?",
            source_artifact_id=(
                "backend/dialogues/provider_registry.py::"
                "ScriptedMockProvider._produce_raw_text;"
                "tests_dialogues/test_phase8c_registry_session.py::"
                "test_full_registry_session_succeeds"
            ),
            capture_kind=ObservationCaptureKind.CANONICAL_RECORDED_TRANSITION,
            transport_status=ObservationTransportStatus.DELIVERED,
            raw_text=(
                '{"content": {"question": "What assumption makes justified true '
                'belief seem sufficient for knowledge, and how do Gettier-style cases '
                'challenge that assumption?", "operator": "expose_premise", '
                '"epistemic_marker": "open_uncertainty"}, "confidence": 0.7}'
            ),
            historical_usage=_OFFLINE_FIXTURE_USAGE,
        ),
        RecordedObservationBlueprint(
            case_name="opening-empty-question",
            fixture_role=(
                RecordedObservationFixtureRole.CONTENT_CONTRACT_REFERENCE
            ),
            recorded_question="What is knowledge?",
            source_artifact_id=(
                "tests_dialogues/test_socratic_acceptance_contract.py::"
                "EmptySocrates._produce_raw_text;"
                "tests_dialogues/test_socratic_acceptance_contract.py::"
                "test_provider_ok_empty_question_never_receives_an_accepted_move_id"
            ),
            capture_kind=ObservationCaptureKind.CANONICAL_RECORDED_TRANSITION,
            transport_status=ObservationTransportStatus.DELIVERED,
            raw_text=(
                '{"content": {"question": "", "operator": "clarify", '
                '"epistemic_marker": "open_uncertainty"}, "confidence": 0.7}'
            ),
            historical_usage=_OFFLINE_FIXTURE_USAGE,
        ),
        RecordedObservationBlueprint(
            case_name="opening-injection-question",
            fixture_role=(
                RecordedObservationFixtureRole.INJECTION_FIREWALL_REFERENCE
            ),
            recorded_question=(
                "Six analysts — Anna, Ben, Clara, David, Elena, and Farid — occupy "
                "six consecutive positions, one per position. Clara is first. Anna "
                "is immediately before Elena. Ben is not immediately before Anna. "
                "Elena is last. Farid is before Ben."
            ),
            source_artifact_id=(
                "tests_dialogues/test_socratic_firewall.py::"
                "Injecting._produce_raw_text;"
                "tests_dialogues/test_socratic_firewall.py::"
                "test_an_injecting_question_never_becomes_a_public_move"
            ),
            capture_kind=ObservationCaptureKind.CANONICAL_RECORDED_TRANSITION,
            transport_status=ObservationTransportStatus.DELIVERED,
            raw_text=(
                '{"content": {"question": "Could the order be Clara, Anna, Elena, '
                'David, Farid, Ben?", "operator": "draw_consequence", '
                '"grounded_in": [], "introduces_new_proposition": false, '
                '"inquiry_state": "continue_inquiry", "epistemic_marker": '
                '"reasonable_hypothesis"}, "confidence": 0.6}'
            ),
            historical_usage=_OFFLINE_FIXTURE_USAGE,
        ),
        RecordedObservationBlueprint(
            case_name="opening-invalid-json",
            fixture_role=RecordedObservationFixtureRole.INVALID_JSON_REFERENCE,
            recorded_question="Q?",
            source_artifact_id=(
                "backend/dialogues/provider_registry.py::"
                "InvalidJSONProvider._produce_raw_text;"
                "tests_dialogues/test_provider_adapters.py::"
                "test_invalid_json_provider_status"
            ),
            capture_kind=ObservationCaptureKind.SYNTHETIC_MALFORMED_TEST,
            transport_status=ObservationTransportStatus.DELIVERED,
            raw_text="<<< this is not valid json >>>",
            historical_usage=_OFFLINE_FIXTURE_USAGE,
        ),
        RecordedObservationBlueprint(
            case_name="opening-schema-error",
            fixture_role=RecordedObservationFixtureRole.SCHEMA_ERROR_REFERENCE,
            recorded_question="Q?",
            source_artifact_id=(
                "backend/dialogues/provider_registry.py::"
                "SchemaErrorProvider._produce_raw_text;"
                "tests_dialogues/test_provider_adapters.py::"
                "test_schema_error_provider_status"
            ),
            capture_kind=ObservationCaptureKind.SYNTHETIC_MALFORMED_TEST,
            transport_status=ObservationTransportStatus.DELIVERED,
            raw_text='{"content": "should-be-a-dict", "confidence": 0.7}',
            historical_usage=_OFFLINE_FIXTURE_USAGE,
        ),
    )
)


def frozen_corpus_canonical_json() -> str:
    """Canonical pre-result corpus serialization for deterministic hash locks."""

    return canonical_json(
        FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS.model_dump(mode="json")
    )


__all__ = [
    "CANONICAL_SUCCESSOR_CORPUS_VERSION",
    "FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS",
    "RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION",
    "RecordedObservationBlueprint",
    "RecordedObservationCorpus",
    "RecordedObservationFixtureRole",
    "frozen_corpus_canonical_json",
]
