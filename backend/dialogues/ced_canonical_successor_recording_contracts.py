"""Frozen capture-authority contracts for Phase 8 recorded observations.

These contracts record what the canonical offline CED path actually dispatched
and received.  They do not execute a provider, parse output, decide acceptance,
or construct a successor.  A manifest entry binds one immutable capture receipt
to one exact :class:`RecordedCanonicalObservation`; replay callers cannot mint a
different task/provider/root identity from the same raw bytes and retain
manifest membership.
"""

from __future__ import annotations

import hashlib
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ced_canonical_successor_contracts import (
    CanonicalTaskIdentity,
    ObservationTransportStatus,
    RecordedCanonicalObservation,
    RecordedHistoricalUsage,
    RecordedObservationProvenance,
)
from .models import ProviderStatus
from .socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)


CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID = (
    "ced-canonical-successor-recording/v0"
)
CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION = (
    "ced-canonical-successor-capture-manifest/v0"
)
CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_ENTRY_SCHEMA_VERSION = (
    "ced-canonical-successor-capture-manifest-entry/v0"
)

_HEX64_PATTERN = r"^[0-9a-f]{64}$"


class _FrozenRecordingContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    return value


class CanonicalObservationCaptureReceipt(_FrozenRecordingContract):
    """Semantic receipt for one observation seen on the canonical CED path."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID
    ] = CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID
    capture_receipt_id: Optional[str] = None

    source_capsule_id: str
    source_execution_id: str
    source_configuration_digest: str = Field(pattern=_HEX64_PATTERN)
    source_normalized_semantic_digest: str = Field(pattern=_HEX64_PATTERN)
    source_search_state_v1_id: str
    action_id: str
    task_identity: CanonicalTaskIdentity

    provider_id: str
    configured_model_id: str
    actual_model_id: str
    model_config_digest: str = Field(pattern=_HEX64_PATTERN)
    provider_status: ProviderStatus
    transport_status: ObservationTransportStatus
    raw_output_digest: str = Field(pattern=_HEX64_PATTERN)

    historical_usage: RecordedHistoricalUsage
    provenance: RecordedObservationProvenance
    offline_fixture_dispatches: Literal[1] = 1
    live_calls: Literal[0] = 0
    tool_calls: Literal[0] = 0

    # The production task ID proves that an actual task was observed, but it is
    # random provenance and therefore excluded from semantic receipt identity.
    source_task_id: Optional[str] = None

    _nonblank_fields = field_validator(
        "source_capsule_id",
        "source_execution_id",
        "source_search_state_v1_id",
        "action_id",
        "provider_id",
        "configured_model_id",
        "actual_model_id",
    )(_nonblank)

    @model_validator(mode="after")
    def validate_links_and_identify(self) -> "CanonicalObservationCaptureReceipt":
        if self.model_config_digest != self.task_identity.model_config_digest:
            raise ContractValidationError(
                "capture receipt task/provider configuration identities differ"
            )
        expected = stable_contract_id("cedcapture", self.identity_payload())
        if self.capture_receipt_id is not None and self.capture_receipt_id != expected:
            raise ContractValidationError(
                "capture_receipt_id does not match recorded capture semantics"
            )
        object.__setattr__(self, "capture_receipt_id", expected)
        return self

    def identity_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "source_capsule_id": self.source_capsule_id,
            "source_execution_id": self.source_execution_id,
            "source_configuration_digest": self.source_configuration_digest,
            "source_normalized_semantic_digest": (
                self.source_normalized_semantic_digest
            ),
            "source_search_state_v1_id": self.source_search_state_v1_id,
            "action_id": self.action_id,
            "task_identity": self.task_identity.identity_payload(),
            "provider_id": self.provider_id,
            "configured_model_id": self.configured_model_id,
            "actual_model_id": self.actual_model_id,
            "model_config_digest": self.model_config_digest,
            "provider_status": self.provider_status.value,
            "transport_status": self.transport_status.value,
            "raw_output_digest": self.raw_output_digest,
            "historical_usage": self.historical_usage.identity_payload(),
            "provenance": self.provenance.identity_payload(),
            "offline_fixture_dispatches": self.offline_fixture_dispatches,
            "live_calls": self.live_calls,
            "tool_calls": self.tool_calls,
        }


class CanonicalRecordedObservationManifestEntry(_FrozenRecordingContract):
    """One exact capture receipt and its only authorized observation bytes."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_ENTRY_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_ENTRY_SCHEMA_VERSION
    entry_id: Optional[str] = None
    capture_receipt: CanonicalObservationCaptureReceipt
    observation: RecordedCanonicalObservation
    observation_canonical_sha256: Optional[str] = Field(
        default=None, pattern=_HEX64_PATTERN
    )

    @model_validator(mode="after")
    def validate_links_and_identify(
        self,
    ) -> "CanonicalRecordedObservationManifestEntry":
        capture = self.capture_receipt
        observation = self.observation
        linked = (
            observation.capture_receipt_id == capture.capture_receipt_id
            and observation.source_capsule_id == capture.source_capsule_id
            and observation.source_execution_id == capture.source_execution_id
            and observation.source_configuration_digest
            == capture.source_configuration_digest
            and observation.action_id == capture.action_id
            and observation.task_identity == capture.task_identity
            and observation.provider_id == capture.provider_id
            and observation.configured_model_id == capture.configured_model_id
            and observation.actual_model_id == capture.actual_model_id
            and observation.model_config_digest == capture.model_config_digest
            and observation.transport_status is capture.transport_status
            and observation.raw_output_digest == capture.raw_output_digest
            and observation.historical_usage == capture.historical_usage
            and observation.provenance == capture.provenance
            and observation.source_task_id == capture.source_task_id
        )
        if not linked:
            raise ContractValidationError(
                "manifest observation does not match its canonical capture receipt"
            )
        digest = hashlib.sha256(
            canonical_json(observation.model_dump(mode="json")).encode("utf-8")
        ).hexdigest()
        if (
            self.observation_canonical_sha256 is not None
            and self.observation_canonical_sha256 != digest
        ):
            raise ContractValidationError(
                "manifest observation canonical SHA-256 does not match"
            )
        object.__setattr__(self, "observation_canonical_sha256", digest)
        expected = stable_contract_id(
            "cedcaptureentry",
            {
                "schema_version": self.schema_version,
                "capture_receipt_id": capture.capture_receipt_id,
                "observation_id": observation.observation_id,
                "observation_canonical_sha256": digest,
            },
        )
        if self.entry_id is not None and self.entry_id != expected:
            raise ContractValidationError("manifest entry ID does not match")
        object.__setattr__(self, "entry_id", expected)
        return self


class CanonicalRecordedObservationManifest(_FrozenRecordingContract):
    """Frozen capture authority used by the Phase 8 replay boundary."""

    schema_version: Literal[
        CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION
    ] = CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION
    manifest_id: Optional[str] = None
    entries: Tuple[CanonicalRecordedObservationManifestEntry, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "CanonicalRecordedObservationManifest":
        ordered = tuple(
            sorted(self.entries, key=lambda item: item.capture_receipt.capture_receipt_id or "")
        )
        if not ordered:
            raise ContractValidationError("capture manifest must not be empty")
        receipt_ids = [item.capture_receipt.capture_receipt_id for item in ordered]
        observation_ids = [item.observation.observation_id for item in ordered]
        if len(set(receipt_ids)) != len(ordered):
            raise ContractValidationError("capture receipt IDs must be unique")
        if len(set(observation_ids)) != len(ordered):
            raise ContractValidationError("captured observation IDs must be unique")
        object.__setattr__(self, "entries", ordered)
        expected = stable_contract_id(
            "cedcapturemanifest",
            {
                "schema_version": self.schema_version,
                "entry_ids": [item.entry_id for item in ordered],
            },
        )
        if self.manifest_id is not None and self.manifest_id != expected:
            raise ContractValidationError("capture manifest ID does not match")
        object.__setattr__(self, "manifest_id", expected)
        return self

    def entry_for_receipt(
        self, capture_receipt_id: str
    ) -> CanonicalRecordedObservationManifestEntry:
        try:
            return next(
                item
                for item in self.entries
                if item.capture_receipt.capture_receipt_id == capture_receipt_id
            )
        except StopIteration as exc:
            raise KeyError(capture_receipt_id) from exc


__all__ = [
    "CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_ENTRY_SCHEMA_VERSION",
    "CANONICAL_SUCCESSOR_CAPTURE_MANIFEST_SCHEMA_VERSION",
    "CANONICAL_SUCCESSOR_RECORDING_CONTRACT_ID",
    "CanonicalObservationCaptureReceipt",
    "CanonicalRecordedObservationManifest",
    "CanonicalRecordedObservationManifestEntry",
]
