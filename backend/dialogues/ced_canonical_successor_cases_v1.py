"""Authoritative recorded-observation corpus v1 for Phase 8 parity.

Each case owns an exact manifest-anchored observation captured while the real
offline CED path was executing. ``materialize`` only round-trips and verifies
that immutable observation against a pending transition; it cannot stamp or
rewrite task, root, provider, model, or configuration metadata. Expected
successor truth is held exclusively in evaluator-side reference records.
"""

from __future__ import annotations

import hashlib
from enum import Enum
from typing import Dict, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ced_canonical_successor import (
    CANONICAL_PROCESSOR_IDS,
    CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID,
)
from .ced_canonical_successor_contracts import (
    CanonicalRejectionReason,
    CanonicalTransitionStatus,
    PendingCanonicalTransition,
    RecordedCanonicalObservation,
    validate_recorded_observation_compatibility,
)
from .ced_canonical_successor_manifest import (
    FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST,
    verify_authoritative_recorded_observation,
)
from .ced_canonical_successor_recording_contracts import (
    CanonicalRecordedObservationManifestEntry,
)
from .socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)


CANONICAL_SUCCESSOR_CORPUS_VERSION = (
    "ced-canonical-successor-parity-corpus/v1"
)
RECORDED_OBSERVATION_CASE_SCHEMA_VERSION = (
    "ced-canonical-successor-parity-case/v1"
)
CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION = (
    "ced-canonical-successor-reference/v1"
)
CANONICAL_SUCCESSOR_REFERENCE_FIELD_SCHEMA_VERSION = (
    "ced-canonical-successor-reference-field/v1"
)

FROZEN_PARITY_FIELD_NAMES = (
    "aporia",
    "budget",
    "commitments",
    "normalized_semantics",
    "phase_dispatch",
    "phase_role_cursor",
    "provider_bindings",
    "registry_retry",
    "registry_rounds",
    "search_state_v1",
    "session_state",
    "socratic_audit",
    "task_log",
)

_HEX64_PATTERN = r"^[0-9a-f]{64}$"


class RecordedObservationFixtureRole(str, Enum):
    ACCEPTED_REFERENCE = "accepted_reference"
    CONTENT_CONTRACT_REFERENCE = "content_contract_reference"
    INJECTION_FIREWALL_REFERENCE = "injection_firewall_reference"
    INVALID_JSON_REFERENCE = "invalid_json_reference"
    SCHEMA_ERROR_REFERENCE = "schema_error_reference"


class _FrozenCorpusV1Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


class CanonicalSuccessorReferenceField(_FrozenCorpusV1Contract):
    schema_version: Literal[
        CANONICAL_SUCCESSOR_REFERENCE_FIELD_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_REFERENCE_FIELD_SCHEMA_VERSION
    name: str
    semantic_digest: str = Field(pattern=_HEX64_PATTERN)

    _name_nonblank = field_validator("name")(_nonblank)


class CanonicalSuccessorReferenceRecord(_FrozenCorpusV1Contract):
    """Evaluator-only immutable content references for one canonical successor."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION
    reference_id: Optional[str] = None
    capture_receipt_id: str
    observation_id: str
    source_capsule_id: str
    source_execution_id: str
    source_normalized_semantic_digest: str = Field(pattern=_HEX64_PATTERN)
    action_id: str
    task_identity_id: str
    status: CanonicalTransitionStatus
    canonical_rejection_reason: Optional[CanonicalRejectionReason] = None
    accepted_move_id: Optional[str] = None
    successor_semantic_digest: str = Field(pattern=_HEX64_PATTERN)
    successor_search_state_v1_id: str
    successor_search_state_v1_digest: str = Field(pattern=_HEX64_PATTERN)
    parity_field_digests: Tuple[CanonicalSuccessorReferenceField, ...]
    parity_definition_id: Literal[
        CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID
    ] = CANONICAL_SUCCESSOR_PARITY_DEFINITION_ID
    canonical_processor_ids: Tuple[str, ...] = CANONICAL_PROCESSOR_IDS
    offline_fixture_dispatches: Literal[1] = 1

    _nonblank_fields = field_validator(
        "capture_receipt_id",
        "observation_id",
        "source_capsule_id",
        "source_execution_id",
        "action_id",
        "task_identity_id",
        "successor_search_state_v1_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "CanonicalSuccessorReferenceRecord":
        fields = tuple(sorted(self.parity_field_digests, key=lambda item: item.name))
        if tuple(item.name for item in fields) != FROZEN_PARITY_FIELD_NAMES:
            raise ContractValidationError(
                "reference record does not contain the exact frozen parity field set"
            )
        object.__setattr__(self, "parity_field_digests", fields)
        processors = tuple(sorted(self.canonical_processor_ids))
        if processors != tuple(sorted(CANONICAL_PROCESSOR_IDS)):
            raise ContractValidationError("reference canonical processor set changed")
        object.__setattr__(self, "canonical_processor_ids", processors)
        if self.status is CanonicalTransitionStatus.APPLIED_ACCEPTED:
            if self.accepted_move_id is None or self.canonical_rejection_reason is not None:
                raise ContractValidationError(
                    "accepted reference requires one move ID and no rejection reason"
                )
        elif self.status is CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION:
            if self.accepted_move_id is not None or self.canonical_rejection_reason is None:
                raise ContractValidationError(
                    "canonical-rejection reference requires a reason and no move ID"
                )
        else:
            raise ContractValidationError(
                "authoritative corpus references must be applied canonical outcomes"
            )
        expected = stable_contract_id(
            "cedsuccessorref",
            self.model_dump(mode="json", exclude={"reference_id"}),
        )
        if self.reference_id is not None and self.reference_id != expected:
            raise ContractValidationError("reference_id does not match frozen truth")
        object.__setattr__(self, "reference_id", expected)
        return self

    def field_digest(self, name: str) -> str:
        try:
            return next(
                item.semantic_digest
                for item in self.parity_field_digests
                if item.name == name
            )
        except StopIteration as exc:
            raise KeyError(name) from exc


def canonical_successor_reference_field_payloads(
    semantic_payload: Mapping[str, object],
) -> Dict[str, object]:
    """Project the predeclared evaluator-side parity fields.

    This is a read-only comparison projection over the canonical CED semantic
    snapshot. It does not interpret transition validity or acceptance; those
    decisions remain entirely CED-owned.
    """

    try:
        session_state = semantic_payload["session_state"]
        side_ledgers = semantic_payload["side_ledgers"]
        if not isinstance(session_state, Mapping) or not isinstance(
            side_ledgers, Mapping
        ):
            raise TypeError
        payloads: Dict[str, object] = {
            "aporia": side_ledgers["aporia"],
            "budget": {
                "budget": semantic_payload["budget"],
                "budget_usage": semantic_payload["budget_usage"],
                "depth": semantic_payload["depth"],
            },
            "commitments": side_ledgers["commitment"],
            "normalized_semantics": semantic_payload,
            "phase_dispatch": side_ledgers["phase_dispatch"],
            "phase_role_cursor": {
                "phase": session_state["phase"],
                "round_number": session_state["round_number"],
                "agent_states": session_state["agent_states"],
                "phase_history": session_state["phase_history"],
                "role_history": session_state["role_history"],
            },
            "provider_bindings": semantic_payload["provider_bindings"],
            "registry_retry": side_ledgers["registry_retry"],
            "registry_rounds": session_state["registry_rounds"],
            "search_state_v1": semantic_payload["search_state_v1"],
            "session_state": session_state,
            "socratic_audit": side_ledgers["socratic_audit"],
            "task_log": session_state["task_log"],
        }
    except (KeyError, TypeError) as exc:
        raise ContractValidationError(
            "canonical semantic snapshot is incomplete for frozen parity"
        ) from exc
    if tuple(sorted(payloads)) != FROZEN_PARITY_FIELD_NAMES:
        raise ContractValidationError("frozen parity field projection changed")
    return payloads


def canonical_successor_reference_field_digests(
    semantic_payload: Mapping[str, object],
) -> Tuple[CanonicalSuccessorReferenceField, ...]:
    """Hash the exact frozen evaluator-side parity field projection."""

    return tuple(
        CanonicalSuccessorReferenceField(
            name=name,
            semantic_digest=hashlib.sha256(
                canonical_json(payload).encode("utf-8")
            ).hexdigest(),
        )
        for name, payload in sorted(
            canonical_successor_reference_field_payloads(
                semantic_payload
            ).items()
        )
    )


class AuthoritativeRecordedObservationCase(_FrozenCorpusV1Contract):
    """One fixed root profile, captured observation, and evaluator reference."""

    schema_version: Literal[
        RECORDED_OBSERVATION_CASE_SCHEMA_VERSION
    ] = RECORDED_OBSERVATION_CASE_SCHEMA_VERSION
    case_id: Optional[str] = None
    case_name: str
    fixture_role: RecordedObservationFixtureRole
    recorded_question: str
    recorded_session_id: str
    manifest_entry: CanonicalRecordedObservationManifestEntry
    reference: CanonicalSuccessorReferenceRecord

    _nonblank_fields = field_validator(
        "case_name", "recorded_question", "recorded_session_id"
    )(_nonblank)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AuthoritativeRecordedObservationCase":
        capture = self.manifest_entry.capture_receipt
        observation = self.manifest_entry.observation
        reference = self.reference
        if not verify_authoritative_recorded_observation(observation):
            raise ContractValidationError(
                "case observation is absent from the frozen capture manifest"
            )
        if (
            reference.capture_receipt_id != capture.capture_receipt_id
            or reference.observation_id != observation.observation_id
            or reference.source_capsule_id != capture.source_capsule_id
            or reference.source_execution_id != capture.source_execution_id
            or reference.source_normalized_semantic_digest
            != capture.source_normalized_semantic_digest
            or reference.action_id != capture.action_id
            or reference.task_identity_id != capture.task_identity.task_identity_id
        ):
            raise ContractValidationError(
                "evaluator reference does not link the exact captured observation"
            )
        expected_outcome = {
            RecordedObservationFixtureRole.ACCEPTED_REFERENCE: (
                CanonicalTransitionStatus.APPLIED_ACCEPTED,
                None,
            ),
            RecordedObservationFixtureRole.CONTENT_CONTRACT_REFERENCE: (
                CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                CanonicalRejectionReason.SOCRATIC_CONTENT_REJECTED,
            ),
            RecordedObservationFixtureRole.INJECTION_FIREWALL_REFERENCE: (
                CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                CanonicalRejectionReason.ANSWER_INJECTION_REJECTED,
            ),
            RecordedObservationFixtureRole.INVALID_JSON_REFERENCE: (
                CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                CanonicalRejectionReason.PARSER_REJECTED,
            ),
            RecordedObservationFixtureRole.SCHEMA_ERROR_REFERENCE: (
                CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                CanonicalRejectionReason.SCHEMA_REJECTED,
            ),
        }[self.fixture_role]
        if (
            reference.status,
            reference.canonical_rejection_reason,
        ) != expected_outcome:
            raise ContractValidationError(
                "fixture role does not match frozen CED reference outcome"
            )
        expected = stable_contract_id(
            "cedobscasev1",
            {
                "schema_version": self.schema_version,
                "case_name": self.case_name,
                "fixture_role": self.fixture_role.value,
                "recorded_question": self.recorded_question,
                "recorded_session_id": self.recorded_session_id,
                "manifest_entry_id": self.manifest_entry.entry_id,
                "reference_id": reference.reference_id,
            },
        )
        if self.case_id is not None and self.case_id != expected:
            raise ContractValidationError("case_id does not match frozen v1 lineage")
        object.__setattr__(self, "case_id", expected)
        return self

    @property
    def observation(self) -> RecordedCanonicalObservation:
        return self.manifest_entry.observation

    @property
    def raw_text(self) -> Optional[str]:
        return self.observation.raw_text

    def materialize(
        self,
        pending: PendingCanonicalTransition,
    ) -> RecordedCanonicalObservation:
        """Verify and expose the already-captured observation without rebinding."""

        observation = RecordedCanonicalObservation.model_validate_json(
            self.observation.model_dump_json()
        )
        if not verify_authoritative_recorded_observation(observation):
            raise ContractValidationError(
                "recorded observation lost frozen manifest membership"
            )
        validate_recorded_observation_compatibility(pending, observation)
        return observation


class AuthoritativeRecordedObservationCorpusV1(_FrozenCorpusV1Contract):
    corpus_version: Literal[
        CANONICAL_SUCCESSOR_CORPUS_VERSION
    ] = CANONICAL_SUCCESSOR_CORPUS_VERSION
    corpus_id: Optional[str] = None
    capture_manifest_id: str
    cases: Tuple[AuthoritativeRecordedObservationCase, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "AuthoritativeRecordedObservationCorpusV1":
        if (
            self.capture_manifest_id
            != FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST.manifest_id
        ):
            raise ContractValidationError("corpus capture manifest ID changed")
        ordered = tuple(sorted(self.cases, key=lambda item: item.case_name))
        if len(ordered) != 5:
            raise ContractValidationError("authoritative v1 corpus requires five cases")
        if {item.fixture_role for item in ordered} != set(RecordedObservationFixtureRole):
            raise ContractValidationError(
                "authoritative v1 corpus requires every frozen fixture role"
            )
        if len({item.case_id for item in ordered}) != len(ordered):
            raise ContractValidationError("authoritative case IDs must be unique")
        if len({item.observation.observation_id for item in ordered}) != len(ordered):
            raise ContractValidationError("authoritative observations must be unique")
        object.__setattr__(self, "cases", ordered)
        expected = stable_contract_id(
            "cedobscorpus",
            {
                "corpus_version": self.corpus_version,
                "capture_manifest_id": self.capture_manifest_id,
                "case_ids": [item.case_id for item in ordered],
                "reference_ids": [item.reference.reference_id for item in ordered],
            },
        )
        if self.corpus_id is not None and self.corpus_id != expected:
            raise ContractValidationError("corpus_id does not match v1 case lineage")
        object.__setattr__(self, "corpus_id", expected)
        return self

    def case(self, case_name: str) -> AuthoritativeRecordedObservationCase:
        try:
            return next(item for item in self.cases if item.case_name == case_name)
        except StopIteration as exc:
            raise KeyError(case_name) from exc


def _manifest_entry(capture_receipt_id: str) -> CanonicalRecordedObservationManifestEntry:
    return FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST.entry_for_receipt(
        capture_receipt_id
    )


def _reference(
    *,
    capture_receipt_id: str,
    status: CanonicalTransitionStatus,
    rejection: Optional[CanonicalRejectionReason],
    move_id: Optional[str],
    successor_semantic_digest: str,
    search_state_v1_id: str,
    search_state_v1_digest: str,
    fields: dict[str, str],
) -> CanonicalSuccessorReferenceRecord:
    entry = _manifest_entry(capture_receipt_id)
    capture = entry.capture_receipt
    return CanonicalSuccessorReferenceRecord(
        capture_receipt_id=capture_receipt_id,
        observation_id=entry.observation.observation_id,
        source_capsule_id=capture.source_capsule_id,
        source_execution_id=capture.source_execution_id,
        source_normalized_semantic_digest=capture.source_normalized_semantic_digest,
        action_id=capture.action_id,
        task_identity_id=capture.task_identity.task_identity_id,
        status=status,
        canonical_rejection_reason=rejection,
        accepted_move_id=move_id,
        successor_semantic_digest=successor_semantic_digest,
        successor_search_state_v1_id=search_state_v1_id,
        successor_search_state_v1_digest=search_state_v1_digest,
        parity_field_digests=tuple(
            CanonicalSuccessorReferenceField(name=name, semantic_digest=digest)
            for name, digest in fields.items()
        ),
    )


def _case(
    *,
    name: str,
    role: RecordedObservationFixtureRole,
    question: str,
    capture_receipt_id: str,
    reference: CanonicalSuccessorReferenceRecord,
) -> AuthoritativeRecordedObservationCase:
    return AuthoritativeRecordedObservationCase(
        case_name=name,
        fixture_role=role,
        recorded_question=question,
        recorded_session_id=f"phase8-recorded-{name}",
        manifest_entry=_manifest_entry(capture_receipt_id),
        reference=reference,
    )


_COMMON_EMPTY = "57c23369bc6a51e4158c1e112d3a1ceeb4776451c781573f96ce5f1acab23ff6"
_COMMON_COMMITMENTS = "3dc7cefcfa5749c30cea8875c9e2707bae647e1f1aa6ead57345672eb9e5ccb2"
_COMMON_BUDGET = "2b6053ada822bc09f562961820088c0ec96a8bcd408c6d86b4e774deb2c01acb"
_COMMON_BINDINGS = "48a66e399cff98f8c7488f83d7113ecac1c7a5b696020d83cdf571e6460d708f"


FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1 = (
    AuthoritativeRecordedObservationCorpusV1(
        capture_manifest_id=(
            FROZEN_CANONICAL_RECORDED_OBSERVATION_MANIFEST.manifest_id or ""
        ),
        cases=(
            _case(
                name="opening-scripted-mock",
                role=RecordedObservationFixtureRole.ACCEPTED_REFERENCE,
                question="Is knowledge merely justified true belief?",
                capture_receipt_id="cedcapture_0533bc778cec56100a695953033e041ba4d6aa52f214c0ec36f3f03f93d28c80",
                reference=_reference(
                    capture_receipt_id="cedcapture_0533bc778cec56100a695953033e041ba4d6aa52f214c0ec36f3f03f93d28c80",
                    status=CanonicalTransitionStatus.APPLIED_ACCEPTED,
                    rejection=None,
                    move_id="move_a0ac20327a5c",
                    successor_semantic_digest="2ad8e495b2764b90c54600ffefb4cfd1ff33bbcbdc2cc496ced3d48d5ac9d735",
                    search_state_v1_id="szstatev1_f22fe026c83d0ed3fb3a1647e097f01afe0744423a8d5b11e7f06438f2c58f31",
                    search_state_v1_digest="c943a6faaa1477d15341de68735668c240b009ca901459ccc6128bb38f5bb8e6",
                    fields={
                        "aporia": _COMMON_EMPTY,
                        "budget": _COMMON_BUDGET,
                        "commitments": _COMMON_COMMITMENTS,
                        "normalized_semantics": "2ad8e495b2764b90c54600ffefb4cfd1ff33bbcbdc2cc496ced3d48d5ac9d735",
                        "phase_dispatch": "481a0b0db866071e1113ba3b3bc8d4b34654965c2b13ece2e7e96aa1136081da",
                        "phase_role_cursor": "ad37022fa30bd58f7754092d529480d5c828a784550b8845cfb6995393501a86",
                        "provider_bindings": _COMMON_BINDINGS,
                        "registry_retry": _COMMON_EMPTY,
                        "registry_rounds": "e540db96c24e774f6f6e1e7a72fa94f3be3672a161319ec034dcd84195054b7c",
                        "search_state_v1": "c943a6faaa1477d15341de68735668c240b009ca901459ccc6128bb38f5bb8e6",
                        "session_state": "2c88c55351f31c83aae01a7c2e567c85c48d43b6b48418db9518cf3c80654901",
                        "socratic_audit": "0f70b2052e87fef0f09f1e9f7b63354754351fff178e24c2f991b6b07d906605",
                        "task_log": "78029ce0c2d87a4919ff13255d24655f29c5fddff31b1909e4a8b29f57124620",
                    },
                ),
            ),
            _case(
                name="opening-empty-question",
                role=RecordedObservationFixtureRole.CONTENT_CONTRACT_REFERENCE,
                question="What is knowledge?",
                capture_receipt_id="cedcapture_da0031c4af533d398ee24fffadac817aa29a587270d674164a0a4e016ee9f19b",
                reference=_reference(
                    capture_receipt_id="cedcapture_da0031c4af533d398ee24fffadac817aa29a587270d674164a0a4e016ee9f19b",
                    status=CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                    rejection=CanonicalRejectionReason.SOCRATIC_CONTENT_REJECTED,
                    move_id=None,
                    successor_semantic_digest="00dc58e10a92fd0aee48e4ee8619860f80987b03e99830944088cf9025438136",
                    search_state_v1_id="szstatev1_3f726c2d418f4fdb31abd576a1be97d4c3da9db9a635283f029999cd74b776aa",
                    search_state_v1_digest="7b21fd88bd824f36773085fc78465ef9acd94dfc00398685f8a8509029cf3e98",
                    fields={
                        "aporia": _COMMON_EMPTY,
                        "budget": _COMMON_BUDGET,
                        "commitments": _COMMON_COMMITMENTS,
                        "normalized_semantics": "00dc58e10a92fd0aee48e4ee8619860f80987b03e99830944088cf9025438136",
                        "phase_dispatch": "5f6adce2229ae94729e84f9673d943be7b1faf3a2825687f430d72884bceb928",
                        "phase_role_cursor": "fb3b0fe652d54300fd528e589b59715517f87fe2e05230d4764a6efdff742183",
                        "provider_bindings": _COMMON_BINDINGS,
                        "registry_retry": _COMMON_EMPTY,
                        "registry_rounds": "c86b49cd253b1a03576ab8cd28ab056ff87578d4e09c3090b864311b4c43227b",
                        "search_state_v1": "7b21fd88bd824f36773085fc78465ef9acd94dfc00398685f8a8509029cf3e98",
                        "session_state": "3912756ebf3deaf85b5e9b34bbe2771d3737c0e9a65540546891583fffaf54ba",
                        "socratic_audit": "d52a5f1e604cdeece2cd7325e4e777e6d7f9038781f5001fbcf422f4c61493d8",
                        "task_log": "2cf2c973c8b0fe3dfa26aa8d4b735b0bd8afa3d8a650b931d818d682f39e60af",
                    },
                ),
            ),
            _case(
                name="opening-injection-question",
                role=RecordedObservationFixtureRole.INJECTION_FIREWALL_REFERENCE,
                question=(
                    "Six analysts — Anna, Ben, Clara, David, Elena, and Farid — "
                    "occupy six consecutive positions, one per position. Clara is "
                    "first. Anna is immediately before Elena. Ben is not immediately "
                    "before Anna. Elena is last. Farid is before Ben."
                ),
                capture_receipt_id="cedcapture_ab1938fa95e2e37c4a6095c62babd4176619aa8b881476af868358703ef4c41a",
                reference=_reference(
                    capture_receipt_id="cedcapture_ab1938fa95e2e37c4a6095c62babd4176619aa8b881476af868358703ef4c41a",
                    status=CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                    rejection=CanonicalRejectionReason.ANSWER_INJECTION_REJECTED,
                    move_id=None,
                    successor_semantic_digest="1538370eed4eb415092ecb21df11223ffe620878c50567280421e43eba4212ad",
                    search_state_v1_id="szstatev1_d64432536756d60bb5be82f74533a8d57e9098c8704427c740c9ac5338a655bb",
                    search_state_v1_digest="ab8317ca230aaf6107d21775b682b456b2a2fa07bba440fe6fb1478e3f15cf3e",
                    fields={
                        "aporia": _COMMON_EMPTY,
                        "budget": _COMMON_BUDGET,
                        "commitments": _COMMON_COMMITMENTS,
                        "normalized_semantics": "1538370eed4eb415092ecb21df11223ffe620878c50567280421e43eba4212ad",
                        "phase_dispatch": "5f6adce2229ae94729e84f9673d943be7b1faf3a2825687f430d72884bceb928",
                        "phase_role_cursor": "fb3b0fe652d54300fd528e589b59715517f87fe2e05230d4764a6efdff742183",
                        "provider_bindings": _COMMON_BINDINGS,
                        "registry_retry": _COMMON_EMPTY,
                        "registry_rounds": "388babdf9aa69e711de3112d3c63e2d6c562b627048c4865b980479027e8b353",
                        "search_state_v1": "ab8317ca230aaf6107d21775b682b456b2a2fa07bba440fe6fb1478e3f15cf3e",
                        "session_state": "2fa7d4b5141f028725bbc6ff8e2b7396a45943d9ca5440609b5c3fc4644e4a71",
                        "socratic_audit": "75b173f28a1548fc9a048ffba4ab77b34d894bf06928d8ea882cd00a8b6b86ce",
                        "task_log": "c864ef89c5a071a8f23804f96d747150cb8983fa5aefe97de09e4814cf48e8d5",
                    },
                ),
            ),
            _case(
                name="opening-invalid-json",
                role=RecordedObservationFixtureRole.INVALID_JSON_REFERENCE,
                question="Q?",
                capture_receipt_id="cedcapture_20f0f52e08bef675f27b8aeaabdf28e32384a5c579565df830dc6800a73abcb3",
                reference=_reference(
                    capture_receipt_id="cedcapture_20f0f52e08bef675f27b8aeaabdf28e32384a5c579565df830dc6800a73abcb3",
                    status=CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                    rejection=CanonicalRejectionReason.PARSER_REJECTED,
                    move_id=None,
                    successor_semantic_digest="fb156e9de538a6b50bf667ecdc13c74b75cf18ebb5523c7abf09d371c2fbec10",
                    search_state_v1_id="szstatev1_e48963abd8dad277b73893924e7126f4736c4d574ca3f4ccc67479a48562c7b4",
                    search_state_v1_digest="212a114c538a71e9c6c84c264f497bf42292d04e9ff79e7a67edb2c79c4749f9",
                    fields={
                        "aporia": _COMMON_EMPTY,
                        "budget": _COMMON_BUDGET,
                        "commitments": _COMMON_COMMITMENTS,
                        "normalized_semantics": "fb156e9de538a6b50bf667ecdc13c74b75cf18ebb5523c7abf09d371c2fbec10",
                        "phase_dispatch": "1b12b955a3d88305de6a0e9309bc9920787d6e434852cc2885464a8d934e9051",
                        "phase_role_cursor": "ad37022fa30bd58f7754092d529480d5c828a784550b8845cfb6995393501a86",
                        "provider_bindings": _COMMON_BINDINGS,
                        "registry_retry": _COMMON_EMPTY,
                        "registry_rounds": "6f185e7144f6554a83ef692cc38d70649d6161e1214736546ee79983efcf4d04",
                        "search_state_v1": "212a114c538a71e9c6c84c264f497bf42292d04e9ff79e7a67edb2c79c4749f9",
                        "session_state": "77d7e566e9b547e91a4a5e3608d8413340022c8ece234a03b706add5eb4ea1e9",
                        "socratic_audit": _COMMON_EMPTY,
                        "task_log": "7f7eba795b2bd830ece01dd3a0121f5aaebf53152af44ff07f89b22a8fe7f9d8",
                    },
                ),
            ),
            _case(
                name="opening-schema-error",
                role=RecordedObservationFixtureRole.SCHEMA_ERROR_REFERENCE,
                question="Q?",
                capture_receipt_id="cedcapture_949b1b3ba7446437fc118c48788a090518d9d9fb405c0e4a281e1edd70a6a58c",
                reference=_reference(
                    capture_receipt_id="cedcapture_949b1b3ba7446437fc118c48788a090518d9d9fb405c0e4a281e1edd70a6a58c",
                    status=CanonicalTransitionStatus.APPLIED_CANONICAL_REJECTION,
                    rejection=CanonicalRejectionReason.SCHEMA_REJECTED,
                    move_id=None,
                    successor_semantic_digest="b47bf900e7f88ccc71d50e63ff97de84bec9636301fa5c6b52ba685df0b1b92c",
                    search_state_v1_id="szstatev1_956448fc4409beca61b99a4ef4a838d063949ed1d2314acf0fb67283c9d52e31",
                    search_state_v1_digest="fc7025849d061ac21c57773e18b29834217e495122e522bf86c059d114408b05",
                    fields={
                        "aporia": _COMMON_EMPTY,
                        "budget": _COMMON_BUDGET,
                        "commitments": _COMMON_COMMITMENTS,
                        "normalized_semantics": "b47bf900e7f88ccc71d50e63ff97de84bec9636301fa5c6b52ba685df0b1b92c",
                        "phase_dispatch": "428695fedf9ca2d35a4e0020a5203437c7dd5cbaeb9ecc92ad01ef38a760590a",
                        "phase_role_cursor": "fb3b0fe652d54300fd528e589b59715517f87fe2e05230d4764a6efdff742183",
                        "provider_bindings": _COMMON_BINDINGS,
                        "registry_retry": _COMMON_EMPTY,
                        "registry_rounds": "a7d53816c6d372e57cce93a51b645d3044f175957c7a2ba46f6af93df91f3999",
                        "search_state_v1": "fc7025849d061ac21c57773e18b29834217e495122e522bf86c059d114408b05",
                        "session_state": "c30ac38d451948a3239d5ff87c06c59aa213048fa7635b7e5dea55b233a9862a",
                        "socratic_audit": _COMMON_EMPTY,
                        "task_log": "0bb6e6e174e58993f5eadfd90ba8325a713eefee82950ac1b41408fe6f1b818b",
                    },
                ),
            ),
        ),
    )
)


def frozen_corpus_v1_canonical_json() -> str:
    return canonical_json(
        FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1.model_dump(mode="json")
    )


def frozen_corpus_v1_canonical_sha256() -> str:
    return hashlib.sha256(
        frozen_corpus_v1_canonical_json().encode("utf-8")
    ).hexdigest()


__all__ = [
    "CANONICAL_SUCCESSOR_CORPUS_VERSION",
    "CANONICAL_SUCCESSOR_REFERENCE_FIELD_SCHEMA_VERSION",
    "CANONICAL_SUCCESSOR_REFERENCE_SCHEMA_VERSION",
    "FROZEN_CANONICAL_SUCCESSOR_OBSERVATION_CORPUS_V1",
    "FROZEN_PARITY_FIELD_NAMES",
    "RECORDED_OBSERVATION_CASE_SCHEMA_VERSION",
    "AuthoritativeRecordedObservationCase",
    "AuthoritativeRecordedObservationCorpusV1",
    "CanonicalSuccessorReferenceField",
    "CanonicalSuccessorReferenceRecord",
    "RecordedObservationFixtureRole",
    "canonical_successor_reference_field_digests",
    "canonical_successor_reference_field_payloads",
    "frozen_corpus_v1_canonical_json",
    "frozen_corpus_v1_canonical_sha256",
]
