"""Invalidated Phase 8 v0 recorded-observation corpus lineage.

The committed v0 lineage is preserved for history and low-level processing
tests only. It is explicitly invalid for authoritative Phase 8 parity because
its original ``materialize`` implementation rebound raw provider output to
caller-created task/provider metadata. Authoritative v1 cases live in
``ced_canonical_successor_cases_v1``.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ced_canonical_successor_contracts import (
    CanonicalTaskIdentity,
    HistoricalUsageKnowledge,
    ObservationCaptureKind,
    ObservationTransportStatus,
    PendingCanonicalTransition,
    RecordedCanonicalObservation,
    RecordedHistoricalUsage,
    RecordedObservationProvenance,
    validate_recorded_observation_compatibility,
)
from .models import AgentRole, DialogPhase, TaskKind
from .socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)


CANONICAL_SUCCESSOR_CORPUS_VERSION = (
    "ced-canonical-successor-parity-corpus/v0"
)
INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_ID = (
    "cedobscorpus_99a8090204758b4085f6f937d0e36ab77f6fe4f79f3c66ab8416b05c49bfb8e0"
)
INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_CANONICAL_SHA256 = (
    "a6453fe7fe5bdabaa3258612c040ddc0e93c31214838405fa21afc373194cd8d"
)
INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_STATUS = (
    "INVALIDATED / SUPERSEDED FOR AUTHORITATIVE PHASE-8 PARITY"
)
INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_REASON = (
    "Raw provider output was rebound to caller-created task/provider metadata "
    "instead of retaining the exact semantic identity of the original canonical "
    "observation."
)
RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION = (
    "ced-recorded-observation-blueprint/v0"
)
CANONICAL_SUCCESSOR_CAPTURE_REVISION = (
    "3acd99497af22ad5104c9350b7690e0b9a8dfd39"
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
    """Exact raw output and the immutable canonical request that acquired it."""

    schema_version: Literal[
        RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION
    ] = RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION
    case_id: Optional[str] = None
    case_name: str
    fixture_role: RecordedObservationFixtureRole

    # Harness-only root data. The complete request/provider identity below is
    # frozen from an actual canonical offline capture and is never rebound.
    recorded_question: str
    recorded_session_id: str
    recorded_action_id: str
    recorded_task: CanonicalTaskIdentity
    recorded_provider_id: str
    recorded_configured_model_id: str
    recorded_actual_model_id: str

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
        "case_name",
        "recorded_question",
        "recorded_session_id",
        "recorded_action_id",
        "recorded_provider_id",
        "recorded_configured_model_id",
        "recorded_actual_model_id",
        "source_artifact_id",
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
        task = self.recorded_task
        if (
            task.phase is not DialogPhase.OPENING
            or task.round_number != 0
            or task.slot_index != 0
            or task.attempt_index != 0
            or task.role is not AgentRole.SOCRATES
            or task.task_kind is not TaskKind.SOCRATIC_QUESTION
        ):
            raise ContractValidationError(
                "the v0 corpus requires an exact canonical opening Socratic task"
            )
        if self.recorded_configured_model_id != self.recorded_actual_model_id:
            raise ContractValidationError(
                "the delivered offline capture requires exact configured/actual model parity"
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
            "recorded_session_id": self.recorded_session_id,
            "recorded_action_id": self.recorded_action_id,
            "recorded_task": self.recorded_task.identity_payload(),
            "recorded_provider_id": self.recorded_provider_id,
            "recorded_configured_model_id": self.recorded_configured_model_id,
            "recorded_actual_model_id": self.recorded_actual_model_id,
            "source_artifact_id": self.source_artifact_id,
            "source_revision": CANONICAL_SUCCESSOR_CAPTURE_REVISION,
            "capture_kind": self.capture_kind.value,
            "transport_status": self.transport_status.value,
            "transport_error_code": self.transport_error_code,
            "raw_text": self.raw_text,
            "historical_usage": self.historical_usage.identity_payload(),
        }

    def materialize(
        self,
        pending: PendingCanonicalTransition,
    ) -> RecordedCanonicalObservation:
        """Refuse promotion of the scientifically invalidated v0 lineage."""

        raise ContractValidationError(
            INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_STATUS
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

_RECORDED_ACTION_ID = (
    "szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421"
)


def _recorded_task(
    *,
    agent_id: str,
    task_semantic_digest: str,
    context_digest: str,
    request_semantic_digest: str,
    model_config_digest: str,
) -> CanonicalTaskIdentity:
    return CanonicalTaskIdentity(
        source_session_semantic_id=stable_contract_id(
            "invalidatedsourcesession",
            {
                "agent_id": agent_id,
                "task_semantic_digest": task_semantic_digest,
            },
        ),
        phase=DialogPhase.OPENING,
        round_number=0,
        slot_index=0,
        attempt_index=0,
        agent_id=agent_id,
        role=AgentRole.SOCRATES,
        task_kind=TaskKind.SOCRATIC_QUESTION,
        task_semantic_digest=task_semantic_digest,
        context_digest=context_digest,
        request_semantic_digest=request_semantic_digest,
        model_config_digest=model_config_digest,
    )


FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS = RecordedObservationCorpus(
    cases=(
        RecordedObservationBlueprint(
            case_name="opening-scripted-mock",
            fixture_role=RecordedObservationFixtureRole.ACCEPTED_REFERENCE,
            recorded_question="Is knowledge merely justified true belief?",
            recorded_session_id="phase8-recorded-opening-scripted-mock",
            recorded_action_id=_RECORDED_ACTION_ID,
            recorded_task=_recorded_task(
                agent_id="phase8-recorded-agent-1",
                task_semantic_digest=(
                    "1abbf7300703a36a7849a3b6dea82e9ffeb3134295ad68127523b08f714f5898"
                ),
                context_digest=(
                    "c7e105c1b837c31640516f7243e42662c8a377f0be8cc806c6dfb4c6627312f7"
                ),
                request_semantic_digest=(
                    "bcec1aeb613f44c61843979e2469e0b003587650dcc648af39d2b292d1332e93"
                ),
                model_config_digest=(
                    "412c2296bb32b6f6359af3eea819f8940a0a62a0057225955888644ea65eadcc"
                ),
            ),
            recorded_provider_id="phase8-recorded-seat-1",
            recorded_configured_model_id="phase8-recorded-model/1",
            recorded_actual_model_id="phase8-recorded-model/1",
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
            recorded_session_id="phase8-recorded-opening-empty-question",
            recorded_action_id=_RECORDED_ACTION_ID,
            recorded_task=_recorded_task(
                agent_id="phase8-recorded-agent-0",
                task_semantic_digest=(
                    "1dc32e986118ede060df30390e37fc309bb046a2faa84c106417a87681f577a6"
                ),
                context_digest=(
                    "c7e105c1b837c31640516f7243e42662c8a377f0be8cc806c6dfb4c6627312f7"
                ),
                request_semantic_digest=(
                    "01087e3506613fac89e4e1ab4905293f7ec54518bf723d070f8b8e67077761d8"
                ),
                model_config_digest=(
                    "773b173a47dae0c64f7d2b19efa6b575c5ece84a3c940857db1d2c9e20c9b90c"
                ),
            ),
            recorded_provider_id="phase8-recorded-seat-0",
            recorded_configured_model_id="phase8-recorded-model/0",
            recorded_actual_model_id="phase8-recorded-model/0",
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
            recorded_session_id="phase8-recorded-opening-injection-question",
            recorded_action_id=_RECORDED_ACTION_ID,
            recorded_task=_recorded_task(
                agent_id="phase8-recorded-agent-0",
                task_semantic_digest=(
                    "29ede9e4bb5ec48bcf76ae3890f10e8cd3d094f27be6fd688ad5421a3248ad9c"
                ),
                context_digest=(
                    "a967affed98c5005207b9fc0767c87b219d7e7114e9b8912da979ebd40bf497e"
                ),
                request_semantic_digest=(
                    "53f471f624d1639460791b042e0a4f6720fc8ea2866b597c91aa4aecc72c7ed6"
                ),
                model_config_digest=(
                    "773b173a47dae0c64f7d2b19efa6b575c5ece84a3c940857db1d2c9e20c9b90c"
                ),
            ),
            recorded_provider_id="phase8-recorded-seat-0",
            recorded_configured_model_id="phase8-recorded-model/0",
            recorded_actual_model_id="phase8-recorded-model/0",
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
            recorded_session_id="phase8-recorded-opening-invalid-json",
            recorded_action_id=_RECORDED_ACTION_ID,
            recorded_task=_recorded_task(
                agent_id="phase8-recorded-agent-1",
                task_semantic_digest=(
                    "37ee909044127cdd76b77df3ed8099c5498c2bb580fb9e25371491671a880774"
                ),
                context_digest=(
                    "c7e105c1b837c31640516f7243e42662c8a377f0be8cc806c6dfb4c6627312f7"
                ),
                request_semantic_digest=(
                    "8df788475297d9bb0cf69a1f8e57294ee1fe9544e9eb12a8fc2574a3e838d266"
                ),
                model_config_digest=(
                    "412c2296bb32b6f6359af3eea819f8940a0a62a0057225955888644ea65eadcc"
                ),
            ),
            recorded_provider_id="phase8-recorded-seat-1",
            recorded_configured_model_id="phase8-recorded-model/1",
            recorded_actual_model_id="phase8-recorded-model/1",
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
            recorded_session_id="phase8-recorded-opening-schema-error",
            recorded_action_id=_RECORDED_ACTION_ID,
            recorded_task=_recorded_task(
                agent_id="phase8-recorded-agent-0",
                task_semantic_digest=(
                    "7d9e907db1eaf201d17068645c624ec51450ec4f60d63d7dc38129948b94914f"
                ),
                context_digest=(
                    "c7e105c1b837c31640516f7243e42662c8a377f0be8cc806c6dfb4c6627312f7"
                ),
                request_semantic_digest=(
                    "8df788475297d9bb0cf69a1f8e57294ee1fe9544e9eb12a8fc2574a3e838d266"
                ),
                model_config_digest=(
                    "773b173a47dae0c64f7d2b19efa6b575c5ece84a3c940857db1d2c9e20c9b90c"
                ),
            ),
            recorded_provider_id="phase8-recorded-seat-0",
            recorded_configured_model_id="phase8-recorded-model/0",
            recorded_actual_model_id="phase8-recorded-model/0",
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
    "CANONICAL_SUCCESSOR_CAPTURE_REVISION",
    "CANONICAL_SUCCESSOR_CORPUS_VERSION",
    "FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS",
    "INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_CANONICAL_SHA256",
    "INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_ID",
    "INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_REASON",
    "INVALIDATED_CANONICAL_SUCCESSOR_CORPUS_V0_STATUS",
    "RECORDED_OBSERVATION_BLUEPRINT_SCHEMA_VERSION",
    "RecordedObservationBlueprint",
    "RecordedObservationCorpus",
    "RecordedObservationFixtureRole",
    "frozen_corpus_canonical_json",
]
