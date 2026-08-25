"""Frozen, non-authoritative isolation evidence for acquisition-contract v0.

The acquisition experiment has no production-session reference and no mutation
authority.  Its three isolation scopes are therefore evidenced honestly as an
immutable source-input snapshot, a test-owned sibling sentinel, and a detached
production sentinel.  These payloads are data only; importing this module does
not inspect a runtime, provider, credential, network, CED, or production path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Tuple

from .contracts import canonical_json


ACQUISITION_ISOLATION_EVIDENCE_SCHEMA_V0 = (
    "socrateszero-acquisition-isolation-evidence/v0"
)

SOURCE_ISOLATION_SUBJECT_ID_V0 = (
    "socrateszero-acquisition-source-input-snapshot/v0"
)
SIBLING_ISOLATION_SUBJECT_ID_V0 = (
    "socrateszero-acquisition-sibling-sentinel/v0"
)
PRODUCTION_ISOLATION_SUBJECT_ID_V0 = (
    "socrateszero-acquisition-detached-production-sentinel/v0"
)

SOURCE_ISOLATION_EVIDENCE_MODE_V0 = "IMMUTABLE_SOURCE_INPUT"
SIBLING_ISOLATION_EVIDENCE_MODE_V0 = "TEST_OWNED_SIBLING_SENTINEL"
PRODUCTION_ISOLATION_EVIDENCE_MODE_V0 = "DETACHED_PRODUCTION_SENTINEL"

_SOURCE_CAPSULE_ID = (
    "cedcapsule_a5499733b7b7561d971034d9d65741b1ab76e32c11abf7651a838ad6be6cbd50"
)
_SOURCE_EXECUTION_ID = (
    "cedexecution_c90d438f2737bcbe3aff9a349412a18671ac88bbf1c4afc743f854b9b09312f6"
)
_ROOT_STATE_V1_ID = (
    "szstatev1_a17ce47c27894a3aac4095d0c08da107142a54d2b773c10104fde2b250c2f20e"
)
_PENDING_TRANSITION_ID = (
    "cedpending_3111a26bb87ea7b0fe5a1658ffc86a6313fa66b4ac2f167095c0393bea85c31a"
)
_CANONICAL_TASK_ID = (
    "cedtasksemantic_b5ace018c4bb1369d62bb5004a99edcd8945e4dd0eef1e206570c96b1d71017a"
)
_ACTION_ID = (
    "szaction_e2f2e183f281d8741db89061d679f535042fc35ff9e25dcfb313a7796e232421"
)
_PROVIDER_VISIBLE_REQUEST_SHA256 = (
    "e75582c3a6d50a27efaf6676cbcc7d3bbad4a3635568ec194345c1becd67d8c7"
)
_FROZEN_CORE_BLOB_LOCK_ID_V2 = (
    "cedcorebloblockv2_"
    "2cfc46afcf7afca20b4eb537d626296e11c8b85e885f5caa78d7322e0eb0a957"
)
_FROZEN_PHASE8_V2_ARTIFACT_SHA256 = (
    "8b6d2dd8f347d1dffc60e8a67e7a9bc0652bb2acdcd31c81ec9800ba76f78fdc"
)


@dataclass(frozen=True)
class AcquisitionIsolationEvidenceDefinitionV0:
    """One immutable declaration of what an isolation digest represents."""

    scope: str
    subject_id: str
    evidence_mode: str
    payload_json: str
    runtime_digest: str


def _definition(
    scope: str,
    subject_id: str,
    evidence_mode: str,
    payload: object,
) -> AcquisitionIsolationEvidenceDefinitionV0:
    payload_json = canonical_json(payload)
    return AcquisitionIsolationEvidenceDefinitionV0(
        scope=scope,
        subject_id=subject_id,
        evidence_mode=evidence_mode,
        payload_json=payload_json,
        runtime_digest=hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
    )


FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0: Tuple[
    AcquisitionIsolationEvidenceDefinitionV0, ...
] = (
    _definition(
        "source",
        SOURCE_ISOLATION_SUBJECT_ID_V0,
        SOURCE_ISOLATION_EVIDENCE_MODE_V0,
        {
            "action_id": _ACTION_ID,
            "canonical_task_identity_id": _CANONICAL_TASK_ID,
            "evidence_mode": SOURCE_ISOLATION_EVIDENCE_MODE_V0,
            "pending_transition_id": _PENDING_TRANSITION_ID,
            "root_state_v1_id": _ROOT_STATE_V1_ID,
            "schema_version": ACQUISITION_ISOLATION_EVIDENCE_SCHEMA_V0,
            "scope": "SOURCE",
            "source_capsule_id": _SOURCE_CAPSULE_ID,
            "source_execution_id": _SOURCE_EXECUTION_ID,
        },
    ),
    _definition(
        "sibling",
        SIBLING_ISOLATION_SUBJECT_ID_V0,
        SIBLING_ISOLATION_EVIDENCE_MODE_V0,
        {
            "cross_response_visibility": False,
            "evidence_mode": SIBLING_ISOLATION_EVIDENCE_MODE_V0,
            "independent_attempt_ledgers": True,
            "independent_transport_state": True,
            "provider_visible_request_sha256": _PROVIDER_VISIBLE_REQUEST_SHA256,
            "schema_version": ACQUISITION_ISOLATION_EVIDENCE_SCHEMA_V0,
            "scope": "SIBLING",
            "subject_id": SIBLING_ISOLATION_SUBJECT_ID_V0,
        },
    ),
    _definition(
        "production",
        PRODUCTION_ISOLATION_SUBJECT_ID_V0,
        PRODUCTION_ISOLATION_EVIDENCE_MODE_V0,
        {
            "evidence_mode": PRODUCTION_ISOLATION_EVIDENCE_MODE_V0,
            "frozen_core_blob_lock_id": _FROZEN_CORE_BLOB_LOCK_ID_V2,
            "frozen_phase8_v2_artifact_sha256": (
                _FROZEN_PHASE8_V2_ARTIFACT_SHA256
            ),
            "production_authority": "NONE",
            "production_runtime_attached": False,
            "schema_version": ACQUISITION_ISOLATION_EVIDENCE_SCHEMA_V0,
            "scope": "PRODUCTION",
            "subject_id": PRODUCTION_ISOLATION_SUBJECT_ID_V0,
        },
    ),
)


def acquisition_isolation_evidence_v0(
    scope: str,
) -> AcquisitionIsolationEvidenceDefinitionV0:
    for item in FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0:
        if item.scope == scope:
            return item
    raise KeyError(scope)


def acquisition_isolation_mutation_digest_v0(scope: str) -> str:
    """Hash the declared payload plus one explicit evaluator-side mutation."""

    definition = acquisition_isolation_evidence_v0(scope)
    payload = json.loads(definition.payload_json)
    payload["probe_mutation"] = {
        "field": "runtime_digest",
        "scope": scope.upper(),
        "state": "INTENTIONALLY_CHANGED",
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


FROZEN_ACQUISITION_ISOLATION_SUBJECT_IDS_V0: Tuple[Tuple[str, str], ...] = tuple(
    (item.scope, item.subject_id)
    for item in FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0
)
FROZEN_ACQUISITION_ISOLATION_EVIDENCE_MODES_V0: Tuple[
    Tuple[str, str], ...
] = tuple(
    (item.scope, item.evidence_mode)
    for item in FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0
)
FROZEN_ACQUISITION_ISOLATION_PAYLOADS_JSON_V0: Tuple[
    Tuple[str, str], ...
] = tuple(
    (item.scope, item.payload_json)
    for item in FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0
)
FROZEN_ACQUISITION_ISOLATION_RUNTIME_DIGESTS_V0: Tuple[
    Tuple[str, str], ...
] = tuple(
    (item.scope, item.runtime_digest)
    for item in FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0
)


__all__ = [
    "ACQUISITION_ISOLATION_EVIDENCE_SCHEMA_V0",
    "AcquisitionIsolationEvidenceDefinitionV0",
    "FROZEN_ACQUISITION_ISOLATION_EVIDENCE_MODES_V0",
    "FROZEN_ACQUISITION_ISOLATION_EVIDENCE_V0",
    "FROZEN_ACQUISITION_ISOLATION_PAYLOADS_JSON_V0",
    "FROZEN_ACQUISITION_ISOLATION_RUNTIME_DIGESTS_V0",
    "FROZEN_ACQUISITION_ISOLATION_SUBJECT_IDS_V0",
    "PRODUCTION_ISOLATION_EVIDENCE_MODE_V0",
    "PRODUCTION_ISOLATION_SUBJECT_ID_V0",
    "SIBLING_ISOLATION_EVIDENCE_MODE_V0",
    "SIBLING_ISOLATION_SUBJECT_ID_V0",
    "SOURCE_ISOLATION_EVIDENCE_MODE_V0",
    "SOURCE_ISOLATION_SUBJECT_ID_V0",
    "acquisition_isolation_evidence_v0",
    "acquisition_isolation_mutation_digest_v0",
]
