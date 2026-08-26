"""Sealed one-shot canned adapter for the OpenRouter acquisition experiment.

The adapter is intentionally incapable of live execution.  Its only dispatch
target is the exact in-process canned transport defined here, and authoritative
entry requires the repository acquisition boundary tripwire to be active and
clean.  Retained raw JSON bytes are the response-metadata authority; separately
supplied canned identity, control, and usage fields are only cross-checks.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import weakref
from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional, Tuple

from .acquisition_tripwires import (
    require_clean_acquisition_boundary_tripwire_v0,
)
from .contracts import canonical_json
from .openrouter_acquisition_contracts import (
    OPENROUTER_ACQUISITION_ADAPTER_ID,
    OPENROUTER_CANNED_CANCELLATION_GRACE_MS,
    OPENROUTER_CANNED_CLEANUP_ROUNDS,
    OPENROUTER_MODEL_ID,
    OPENROUTER_PROVIDER_ID,
    OpenRouterAttemptOutcome,
    OpenRouterAttemptReceipt,
    OpenRouterCapabilitySnapshot,
    OpenRouterCannedResponseEnvelope,
    OpenRouterEvidenceState,
    OpenRouterIdentityEvidence,
    OpenRouterPreparedBody,
    OpenRouterRawResponseEvidence,
    OpenRouterTransportMode,
    OpenRouterTransportStatus,
    OpenRouterUsageCompleteness,
    OpenRouterUsageEvidence,
)


OPENROUTER_CANNED_TRANSPORT_ID = (
    "socrateszero-openrouter-acquisition-canned-transport/v0"
)

_CANNED_RESPONSE_KEYS = frozenset(
    {
        "id",
        "provider",
        "model",
        "configuration_digest",
        "choices",
        "fallback_used",
        "explicit_retry_count",
        "adapter_retry_count",
        "sdk_internal_retry_count",
        "hidden_transport_retry_count",
        "stream_used",
        "tool_calls",
        "usage",
    }
)
_USAGE_KEYS = frozenset({"input_tokens", "output_tokens", "total_tokens"})
_HEX_DIGITS = frozenset("0123456789abcdef")


class OpenRouterAcquisitionFailureCode(str, Enum):
    CANNED_TRANSPORT_ERROR = "CANNED_TRANSPORT_ERROR"
    TRANSPORT_TIMEOUT = "TRANSPORT_TIMEOUT"
    CANNED_INVOCATION_COUNT_MISMATCH = "CANNED_INVOCATION_COUNT_MISMATCH"
    WORKER_NOT_TERMINATED = "WORKER_NOT_TERMINATED"
    LATE_MUTATION_DETECTED = "LATE_MUTATION_DETECTED"
    MISSING_RAW_RESPONSE = "MISSING_RAW_RESPONSE"
    RAW_DIGEST_OR_LENGTH_MISMATCH = "RAW_DIGEST_OR_LENGTH_MISMATCH"
    MALFORMED_RESPONSE_ENVELOPE = "MALFORMED_RESPONSE_ENVELOPE"
    ACTUAL_PROVIDER_MISMATCH = "ACTUAL_PROVIDER_MISMATCH"
    ACTUAL_MODEL_MISSING = "ACTUAL_MODEL_MISSING"
    ACTUAL_MODEL_MISMATCH = "ACTUAL_MODEL_MISMATCH"
    ACTUAL_CONFIGURATION_MISMATCH = "ACTUAL_CONFIGURATION_MISMATCH"
    FALLBACK_ACTIVATED = "FALLBACK_ACTIVATED"
    RETRY_ACTIVATED = "RETRY_ACTIVATED"
    STREAMING_RESPONSE_DETECTED = "STREAMING_RESPONSE_DETECTED"
    TOOL_ACTIVATED = "TOOL_ACTIVATED"
    USAGE_INCOMPLETE = "USAGE_INCOMPLETE"
    USAGE_INCONSISTENT = "USAGE_INCONSISTENT"
    REPORTED_USAGE_EXCEEDS_BOUND = "REPORTED_USAGE_EXCEEDS_BOUND"
    RECEIPT_MISMATCH = "RECEIPT_MISMATCH"


class OpenRouterCannedInvocationOutcome(str, Enum):
    RETURNED = "RETURNED"
    RAISED = "RAISED"
    CANCELLED = "CANCELLED"
    FORCED_CLEANUP = "FORCED_CLEANUP"


class OpenRouterAcquisitionAdapterError(RuntimeError):
    """Raised when an authoritative adapter entry cannot be constructed safely."""


class _OpenRouterCannedTransportError(OpenRouterAcquisitionAdapterError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _is_typed_code(value: object) -> bool:
    return (
        type(value) is str
        and bool(value)
        and value[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        and all(character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in value)
    )


def _is_hex64(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in _HEX_DIGITS for character in value)
    )


@dataclass(frozen=True)
class OpenRouterCannedTransportDirectiveV0:
    """Exactly one deterministic canned outcome owned by the sealed transport."""

    envelope: Optional[OpenRouterCannedResponseEnvelope] = None
    error_code: Optional[str] = None
    wait_for_timeout: bool = False
    resist_initial_cancellation: bool = False
    cooperative_yields: int = 0
    attempt_late_mutation: bool = False

    def __post_init__(self) -> None:
        if self.envelope is not None and type(self.envelope) is not OpenRouterCannedResponseEnvelope:
            raise TypeError("canned envelope must use the exact frozen contract type")
        if self.error_code is not None and not _is_typed_code(self.error_code):
            raise ValueError("canned error must be a typed uppercase code")
        if type(self.wait_for_timeout) is not bool:
            raise TypeError("wait_for_timeout must be an exact boolean")
        if type(self.resist_initial_cancellation) is not bool:
            raise TypeError("resist_initial_cancellation must be an exact boolean")
        if type(self.cooperative_yields) is not int or self.cooperative_yields < 0:
            raise ValueError("cooperative_yields must be a nonnegative exact integer")
        if type(self.attempt_late_mutation) is not bool:
            raise TypeError("attempt_late_mutation must be an exact boolean")
        selected = int(self.envelope is not None)
        selected += int(self.error_code is not None)
        selected += int(self.wait_for_timeout)
        if selected != 1:
            raise ValueError("exactly one canned transport outcome is required")
        if self.resist_initial_cancellation and not self.wait_for_timeout:
            raise ValueError("cancellation resistance requires the timeout outcome")
        if (self.cooperative_yields or self.attempt_late_mutation) and self.envelope is None:
            raise ValueError("delay and late-mutation probes require a returned envelope")


@dataclass(frozen=True)
class OpenRouterCannedInvocationRecordV0:
    ordinal: int
    transport_attempt_id: str
    received_body_bytes: bytes
    received_body_sha256: str
    received_body_byte_length: int
    outcome: OpenRouterCannedInvocationOutcome
    cancellation_acknowledged: bool
    worker_terminated: bool
    cancellation_requests: int = 0
    forced_cleanup: bool = False

    def __post_init__(self) -> None:
        if self.ordinal != 1:
            raise ValueError("the one-shot canned invocation ordinal must be one")
        if type(self.transport_attempt_id) is not str or not self.transport_attempt_id:
            raise ValueError("transport_attempt_id must be nonblank")
        if type(self.received_body_bytes) is not bytes:
            raise TypeError("received body must be immutable exact bytes")
        if self.received_body_byte_length != len(self.received_body_bytes):
            raise ValueError("received body length does not match exact bytes")
        if self.received_body_sha256 != hashlib.sha256(self.received_body_bytes).hexdigest():
            raise ValueError("received body digest does not match exact bytes")
        if type(self.cancellation_acknowledged) is not bool:
            raise TypeError("cancellation acknowledgement must be exact boolean")
        if type(self.worker_terminated) is not bool:
            raise TypeError("worker termination must be exact boolean")
        if type(self.cancellation_requests) is not int or self.cancellation_requests < 0:
            raise ValueError("cancellation request count must be a nonnegative integer")
        if type(self.forced_cleanup) is not bool:
            raise TypeError("forced cleanup must be exact boolean")


def _directive_payload(
    directive: OpenRouterCannedTransportDirectiveV0,
) -> dict[str, object]:
    return {
        "envelope": (
            directive.envelope.model_dump(mode="json")
            if directive.envelope is not None
            else None
        ),
        "error_code": directive.error_code,
        "wait_for_timeout": directive.wait_for_timeout,
        "resist_initial_cancellation": directive.resist_initial_cancellation,
        "cooperative_yields": directive.cooperative_yields,
        "attempt_late_mutation": directive.attempt_late_mutation,
    }


def _directive_fingerprint(
    directive: OpenRouterCannedTransportDirectiveV0,
) -> str:
    return hashlib.sha256(
        canonical_json(_directive_payload(directive)).encode("utf-8")
    ).hexdigest()


class OpenRouterCannedTransportV0:
    """Exact-type, one-use, in-process transport with no external seams."""

    implementation_id = OPENROUTER_CANNED_TRANSPORT_ID

    def __setattr__(self, name: str, value: object) -> None:
        try:
            sealed = object.__getattribute__(self, "_sealed")
        except AttributeError:
            sealed = False
        if sealed:
            raise AttributeError("OpenRouter canned transport construction is sealed")
        object.__setattr__(self, name, value)

    def __init__(self, directive: OpenRouterCannedTransportDirectiveV0) -> None:
        if type(directive) is not OpenRouterCannedTransportDirectiveV0:
            raise TypeError("transport requires the exact canned directive type")
        object.__setattr__(self, "_sealed", False)
        self._directive = directive
        self._started = False
        self._records: Tuple[OpenRouterCannedInvocationRecordV0, ...] = ()
        self._construction_fingerprint = _directive_fingerprint(directive)
        object.__setattr__(self, "_sealed", True)
        _register_transport_seal(self)

    @property
    def invocation_count(self) -> int:
        return int(object.__getattribute__(self, "_started"))

    @property
    def invocation_records(self) -> Tuple[OpenRouterCannedInvocationRecordV0, ...]:
        return object.__getattribute__(self, "_records")

    def _finish(
        self,
        *,
        transport_attempt_id: str,
        body_bytes: bytes,
        outcome: OpenRouterCannedInvocationOutcome,
        cancellation_acknowledged: bool,
        cancellation_requests: int = 0,
        forced_cleanup: bool = False,
    ) -> None:
        if object.__getattribute__(self, "_records"):
            raise OpenRouterAcquisitionAdapterError(
                "one-shot canned transport already has a terminal record"
            )
        record = OpenRouterCannedInvocationRecordV0(
            ordinal=1,
            transport_attempt_id=transport_attempt_id,
            received_body_bytes=body_bytes,
            received_body_sha256=hashlib.sha256(body_bytes).hexdigest(),
            received_body_byte_length=len(body_bytes),
            outcome=outcome,
            cancellation_acknowledged=cancellation_acknowledged,
            worker_terminated=True,
            cancellation_requests=cancellation_requests,
            forced_cleanup=forced_cleanup,
        )
        object.__setattr__(self, "_records", (record,))

    async def invoke(
        self,
        prepared_body_bytes: bytes,
        transport_attempt_id: str,
    ) -> OpenRouterCannedResponseEnvelope:
        if type(prepared_body_bytes) is not bytes:
            raise TypeError("prepared body must be passed as exact immutable bytes")
        if type(transport_attempt_id) is not str or not transport_attempt_id:
            raise ValueError("transport attempt identity must be nonblank")
        if object.__getattribute__(self, "_started"):
            raise OpenRouterAcquisitionAdapterError(
                "one-shot canned transport cannot be invoked twice"
            )
        object.__setattr__(self, "_started", True)
        directive = object.__getattribute__(self, "_directive")
        if directive.envelope is not None:
            try:
                for _yield_index in range(directive.cooperative_yields):
                    await asyncio.sleep(0)
            except asyncio.CancelledError:
                _SEALED_TRANSPORT_FINISH(
                    self,
                    transport_attempt_id=transport_attempt_id,
                    body_bytes=prepared_body_bytes,
                    outcome=OpenRouterCannedInvocationOutcome.CANCELLED,
                    cancellation_acknowledged=True,
                    cancellation_requests=1,
                )
                raise
            _SEALED_TRANSPORT_FINISH(
                self,
                transport_attempt_id=transport_attempt_id,
                body_bytes=prepared_body_bytes,
                outcome=OpenRouterCannedInvocationOutcome.RETURNED,
                cancellation_acknowledged=False,
            )
            if directive.attempt_late_mutation:
                asyncio.create_task(
                    _attempt_sealed_late_mutation(self),
                    name="socrates-zero-openrouter-canned-late-mutation-1",
                )
            return directive.envelope
        if directive.error_code is not None:
            _SEALED_TRANSPORT_FINISH(
                self,
                transport_attempt_id=transport_attempt_id,
                body_bytes=prepared_body_bytes,
                outcome=OpenRouterCannedInvocationOutcome.RAISED,
                cancellation_acknowledged=False,
            )
            raise _OpenRouterCannedTransportError(directive.error_code)

        blocker = asyncio.Event()
        cancellation_requests = 0
        while True:
            try:
                await blocker.wait()
            except asyncio.CancelledError:
                cancellation_requests += 1
                if directive.resist_initial_cancellation and cancellation_requests == 1:
                    continue
                forced = cancellation_requests > 1
                _SEALED_TRANSPORT_FINISH(
                    self,
                    transport_attempt_id=transport_attempt_id,
                    body_bytes=prepared_body_bytes,
                    outcome=(
                        OpenRouterCannedInvocationOutcome.FORCED_CLEANUP
                        if forced
                        else OpenRouterCannedInvocationOutcome.CANCELLED
                    ),
                    cancellation_acknowledged=True,
                    cancellation_requests=cancellation_requests,
                    forced_cleanup=forced,
                )
                raise


_SEALED_TRANSPORT_INVOKE = OpenRouterCannedTransportV0.__dict__["invoke"]
_SEALED_TRANSPORT_FINISH = OpenRouterCannedTransportV0.__dict__["_finish"]
_SEALED_TRANSPORT_SETATTR = OpenRouterCannedTransportV0.__dict__["__setattr__"]
_SEALED_TRANSPORT_INVOCATION_COUNT = OpenRouterCannedTransportV0.__dict__[
    "invocation_count"
]
_SEALED_TRANSPORT_INVOCATION_RECORDS = OpenRouterCannedTransportV0.__dict__[
    "invocation_records"
]
_TRANSPORT_INSTANCE_KEYS = frozenset(
    {
        "_construction_fingerprint",
        "_directive",
        "_records",
        "_sealed",
        "_started",
    }
)


@dataclass(frozen=True)
class _TransportExternalSeal:
    transport_ref: weakref.ReferenceType[OpenRouterCannedTransportV0]
    construction_fingerprint: str
    directive_identity: int
    initial_records_identity: int
    late_mutation_attempts: int = 0


_TRANSPORT_SEALS: dict[int, _TransportExternalSeal] = {}


def _register_transport_seal(transport: OpenRouterCannedTransportV0) -> None:
    state = object.__getattribute__(transport, "__dict__")
    _TRANSPORT_SEALS[id(transport)] = _TransportExternalSeal(
        transport_ref=weakref.ref(transport),
        construction_fingerprint=state["_construction_fingerprint"],
        directive_identity=id(state["_directive"]),
        initial_records_identity=id(state["_records"]),
    )


def _late_mutation_attempt_count(transport: OpenRouterCannedTransportV0) -> int:
    seal = _TRANSPORT_SEALS.get(id(transport))
    if seal is None or seal.transport_ref() is not transport:
        raise OpenRouterAcquisitionAdapterError("canned transport external seal is absent")
    return seal.late_mutation_attempts


def _record_blocked_late_mutation(transport: OpenRouterCannedTransportV0) -> None:
    seal = _TRANSPORT_SEALS.get(id(transport))
    if seal is None or seal.transport_ref() is not transport:
        raise OpenRouterAcquisitionAdapterError("canned transport external seal is absent")
    _TRANSPORT_SEALS[id(transport)] = replace(
        seal,
        late_mutation_attempts=seal.late_mutation_attempts + 1,
    )


async def _attempt_sealed_late_mutation(
    transport: OpenRouterCannedTransportV0,
) -> None:
    """Exercise the real seal after return without retaining a background task."""

    try:
        transport._records = ()  # type: ignore[attr-defined]
    except AttributeError:
        _record_blocked_late_mutation(transport)
        return
    raise OpenRouterAcquisitionAdapterError("late mutation unexpectedly bypassed seal")


def _transport_state_is_valid(
    transport: OpenRouterCannedTransportV0,
    *,
    require_unused: bool,
) -> bool:
    try:
        if type(transport) is not OpenRouterCannedTransportV0:
            return False
        class_state = OpenRouterCannedTransportV0.__dict__
        if any(
            (
                class_state.get("invoke") is not _SEALED_TRANSPORT_INVOKE,
                class_state.get("_finish") is not _SEALED_TRANSPORT_FINISH,
                class_state.get("__setattr__") is not _SEALED_TRANSPORT_SETATTR,
                class_state.get("invocation_count")
                is not _SEALED_TRANSPORT_INVOCATION_COUNT,
                class_state.get("invocation_records")
                is not _SEALED_TRANSPORT_INVOCATION_RECORDS,
                class_state.get("implementation_id")
                != OPENROUTER_CANNED_TRANSPORT_ID,
            )
        ):
            return False
        state = object.__getattribute__(transport, "__dict__")
        if type(state) is not dict or frozenset(state) != _TRANSPORT_INSTANCE_KEYS:
            return False
        if type(state["_sealed"]) is not bool or state["_sealed"] is not True:
            return False
        if type(state["_directive"]) is not OpenRouterCannedTransportDirectiveV0:
            return False
        if type(state["_started"]) is not bool:
            return False
        if type(state["_records"]) is not tuple or any(
            type(record) is not OpenRouterCannedInvocationRecordV0
            for record in state["_records"]
        ):
            return False
        if len(state["_records"]) > 1:
            return False
        seal = _TRANSPORT_SEALS.get(id(transport))
        if (
            seal is None
            or seal.transport_ref() is not transport
            or seal.construction_fingerprint != state["_construction_fingerprint"]
            or seal.directive_identity != id(state["_directive"])
        ):
            return False
        if require_unused and (
            state["_started"]
            or state["_records"]
            or seal.initial_records_identity != id(state["_records"])
        ):
            return False
        if state["_records"] and not state["_started"]:
            return False
        fingerprint = state["_construction_fingerprint"]
        return (
            _is_hex64(fingerprint)
            and fingerprint == _directive_fingerprint(state["_directive"])
        )
    except Exception:
        return False


@dataclass(frozen=True)
class OpenRouterAcquisitionAdapterResultV0:
    attempt_receipt: OpenRouterAttemptReceipt
    invocation_record: Optional[OpenRouterCannedInvocationRecordV0]
    admission_status: str = "UNADMITTED"
    governance_status: str = "NON_GOVERNING"
    ced_application_count: int = 0
    live_authorization_allowed: bool = False

    def __post_init__(self) -> None:
        if type(self.attempt_receipt) is not OpenRouterAttemptReceipt:
            raise TypeError("adapter result requires the exact attempt receipt type")
        if self.invocation_record is not None and type(
            self.invocation_record
        ) is not OpenRouterCannedInvocationRecordV0:
            raise TypeError("adapter result requires the exact invocation record type")
        if self.admission_status != "UNADMITTED":
            raise ValueError("adapter result is always unadmitted")
        if self.governance_status != "NON_GOVERNING":
            raise ValueError("adapter result is always non-governing")
        if type(self.ced_application_count) is not int or self.ced_application_count != 0:
            raise ValueError("adapter result cannot apply an observation to CED")
        if type(self.live_authorization_allowed) is not bool or self.live_authorization_allowed:
            raise ValueError("adapter result cannot authorize live execution")

    @property
    def receipt(self) -> OpenRouterAttemptReceipt:
        return self.attempt_receipt

    @property
    def outcome(self) -> OpenRouterAttemptOutcome:
        return self.attempt_receipt.outcome

    @property
    def failure_code(self) -> Optional[OpenRouterAcquisitionFailureCode]:
        code = self.attempt_receipt.failure_code
        return OpenRouterAcquisitionFailureCode(code) if code is not None else None


@dataclass(frozen=True)
class _DerivedDeliveredResponse:
    envelope: OpenRouterCannedResponseEnvelope
    raw_response: OpenRouterRawResponseEvidence
    identity_evidence: OpenRouterIdentityEvidence
    usage_evidence: OpenRouterUsageEvidence


class _ResponseRejected(Exception):
    def __init__(
        self,
        code: OpenRouterAcquisitionFailureCode,
        *,
        raw_response: Optional[OpenRouterRawResponseEvidence] = None,
        identity_evidence: Optional[OpenRouterIdentityEvidence] = None,
        usage_evidence: Optional[OpenRouterUsageEvidence] = None,
    ) -> None:
        self.code = code
        self.raw_response = raw_response
        self.identity_evidence = identity_evidence
        self.usage_evidence = usage_evidence
        super().__init__(code.value)


def _safe_identifier(value: object) -> bool:
    if type(value) is not str or not value.strip():
        return False
    lowered = value.lower()
    return not any(
        marker in lowered
        for marker in ("authorization", "api_key", "apikey", "bearer ", "sk-")
    )


def _validate_authoritative_inputs(
    *,
    semantic_request_id: str,
    transport_attempt_id: str,
    prepared_body: OpenRouterPreparedBody,
    capability_snapshot: OpenRouterCapabilitySnapshot,
    transport: OpenRouterCannedTransportV0,
) -> bytes:
    if not _safe_identifier(semantic_request_id):
        raise OpenRouterAcquisitionAdapterError("semantic request identity is invalid")
    if not _safe_identifier(transport_attempt_id):
        raise OpenRouterAcquisitionAdapterError("transport attempt identity is invalid")
    if type(prepared_body) is not OpenRouterPreparedBody:
        raise OpenRouterAcquisitionAdapterError("prepared body type is not exact")
    if type(capability_snapshot) is not OpenRouterCapabilitySnapshot:
        raise OpenRouterAcquisitionAdapterError("capability snapshot type is not exact")
    try:
        rebuilt_body = OpenRouterPreparedBody.model_validate(
            prepared_body.model_dump(mode="json")
        )
        rebuilt_capability = OpenRouterCapabilitySnapshot.model_validate(
            capability_snapshot.model_dump(mode="json")
        )
    except Exception as exc:
        raise OpenRouterAcquisitionAdapterError(
            "frozen request or capability contract is invalid"
        ) from exc
    if rebuilt_body != prepared_body or rebuilt_capability != capability_snapshot:
        raise OpenRouterAcquisitionAdapterError(
            "frozen request or capability contract changed after construction"
        )
    if capability_snapshot.prepared_body_id != prepared_body.prepared_body_id:
        raise OpenRouterAcquisitionAdapterError("capability/body identity does not match")
    if (
        capability_snapshot.endpoint_policy.endpoint_policy_id
        != prepared_body.endpoint_policy_id
        or capability_snapshot.route_policy.route_policy_id
        != prepared_body.route_policy_id
        or capability_snapshot.control_policy.control_policy_id
        != prepared_body.control_policy_id
    ):
        raise OpenRouterAcquisitionAdapterError("prepared body policy links do not match")
    policy = capability_snapshot.transport_policy
    if (
        policy.mode is not OpenRouterTransportMode.CANNED_ONLY
        or policy.max_canned_transport_invocations != 1
        or policy.external_network_allowed
        or policy.credential_access_allowed
        or policy.provider_sdk_allowed
        or policy.model_execution_allowed
    ):
        raise OpenRouterAcquisitionAdapterError("transport policy is not sealed canned-only")
    if not _transport_state_is_valid(transport, require_unused=True):
        raise OpenRouterAcquisitionAdapterError("canned transport seal is invalid or consumed")
    body_bytes = prepared_body.body_bytes
    if (
        type(body_bytes) is not bytes
        or len(body_bytes) != prepared_body.byte_length
        or hashlib.sha256(body_bytes).hexdigest() != prepared_body.sha256
    ):
        raise OpenRouterAcquisitionAdapterError("prepared body bytes do not match evidence")
    return body_bytes


def _reject(
    code: OpenRouterAcquisitionFailureCode,
    *,
    raw_response: Optional[OpenRouterRawResponseEvidence] = None,
    identity_evidence: Optional[OpenRouterIdentityEvidence] = None,
    usage_evidence: Optional[OpenRouterUsageEvidence] = None,
) -> None:
    raise _ResponseRejected(
        code,
        raw_response=raw_response,
        identity_evidence=identity_evidence,
        usage_evidence=usage_evidence,
    )


def _derive_delivered_response(
    returned: object,
    *,
    transport_attempt_id: str,
    prepared_body: OpenRouterPreparedBody,
    capability_snapshot: OpenRouterCapabilitySnapshot,
) -> _DerivedDeliveredResponse:
    if type(returned) is not OpenRouterCannedResponseEnvelope:
        _reject(OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE)
    assert isinstance(returned, OpenRouterCannedResponseEnvelope)
    if returned.transport_status is not OpenRouterTransportStatus.DELIVERED:
        _reject(OpenRouterAcquisitionFailureCode.CANNED_TRANSPORT_ERROR)
    if returned.raw_response is None:
        _reject(OpenRouterAcquisitionFailureCode.MISSING_RAW_RESPONSE)
    side_raw = returned.raw_response
    if type(side_raw) is not OpenRouterRawResponseEvidence:
        _reject(OpenRouterAcquisitionFailureCode.RAW_DIGEST_OR_LENGTH_MISMATCH)
    if side_raw.raw_response_base64 is None:
        _reject(OpenRouterAcquisitionFailureCode.MISSING_RAW_RESPONSE)
    try:
        raw_response = OpenRouterRawResponseEvidence(
            evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            transport_status=OpenRouterTransportStatus.DELIVERED,
            raw_response_base64=side_raw.raw_response_base64,
        )
    except Exception:
        _reject(OpenRouterAcquisitionFailureCode.RAW_DIGEST_OR_LENGTH_MISMATCH)
    assert raw_response is not None
    if raw_response != side_raw:
        _reject(
            OpenRouterAcquisitionFailureCode.RAW_DIGEST_OR_LENGTH_MISMATCH,
            raw_response=raw_response,
        )
    raw_bytes = raw_response.raw_bytes
    if raw_bytes is None:
        _reject(OpenRouterAcquisitionFailureCode.MISSING_RAW_RESPONSE)
    try:
        raw_text = raw_bytes.decode("utf-8")
        parsed = json.loads(raw_text)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        _reject(
            OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            raw_response=raw_response,
        )
    if (
        not isinstance(parsed, dict)
        or canonical_json(parsed) != raw_text
        or set(parsed) != _CANNED_RESPONSE_KEYS
    ):
        _reject(
            OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            raw_response=raw_response,
        )
    response_id = parsed.get("id")
    choices = parsed.get("choices")
    if type(response_id) is not str or not response_id.strip():
        _reject(
            OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            raw_response=raw_response,
        )
    if not isinstance(choices, list) or len(choices) != 1:
        _reject(
            OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            raw_response=raw_response,
        )
    choice = choices[0]
    if not isinstance(choice, dict) or set(choice) != {"finish_reason", "message"}:
        _reject(
            OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            raw_response=raw_response,
        )
    message = choice.get("message")
    if (
        choice.get("finish_reason") != "stop"
        or not isinstance(message, dict)
        or set(message) != {"role", "content"}
        or message.get("role") != "assistant"
        or type(message.get("content")) is not str
    ):
        _reject(
            OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            raw_response=raw_response,
        )

    actual_router = parsed.get("provider")
    actual_model = parsed.get("model")
    actual_configuration = parsed.get("configuration_digest")
    if type(actual_router) is not str or actual_router != OPENROUTER_PROVIDER_ID:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_PROVIDER_MISMATCH,
            raw_response=raw_response,
        )
    if actual_model is None or actual_model == "":
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_MODEL_MISSING,
            raw_response=raw_response,
        )
    if type(actual_model) is not str or actual_model != OPENROUTER_MODEL_ID:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_MODEL_MISMATCH,
            raw_response=raw_response,
        )
    requested_configuration = (
        capability_snapshot.control_policy.control_policy_id or ""
    ).split("_", 1)[-1]
    if (
        not _is_hex64(actual_configuration)
        or actual_configuration != requested_configuration
    ):
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH,
            raw_response=raw_response,
        )
    try:
        identity_evidence = OpenRouterIdentityEvidence(
            evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            requested_configuration_digest=requested_configuration,
            actual_router_id=actual_router,
            actual_model_id=actual_model,
            actual_configuration_digest=actual_configuration,
            router_identity_match=True,
            model_identity_match=True,
            configuration_identity_match=True,
            identity_match=True,
            exact_router_model_configuration_verified=True,
        )
    except Exception:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH,
            raw_response=raw_response,
        )
    assert identity_evidence is not None
    side_identity = returned.identity_evidence
    if side_identity is None:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_MODEL_MISSING,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    if side_identity.actual_router_id != actual_router:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_PROVIDER_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    if side_identity.actual_model_id != actual_model:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_MODEL_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    if side_identity.actual_configuration_digest != actual_configuration:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    if returned.actual_router_id != actual_router:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_PROVIDER_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    if returned.actual_model_id != actual_model:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_MODEL_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    if returned.actual_configuration_digest != actual_configuration:
        _reject(
            OpenRouterAcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    if side_identity != identity_evidence:
        _reject(
            OpenRouterAcquisitionFailureCode.RECEIPT_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )

    fallback = parsed.get("fallback_used")
    if type(fallback) is not bool or fallback or returned.fallback_used is not False:
        _reject(
            OpenRouterAcquisitionFailureCode.FALLBACK_ACTIVATED,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    retry_values = (
        parsed.get("explicit_retry_count"),
        parsed.get("adapter_retry_count"),
        parsed.get("hidden_transport_retry_count"),
    )
    side_retry_values = (
        returned.explicit_retry_count,
        returned.adapter_retry_count,
        returned.hidden_transport_retry_count,
    )
    if (
        any(type(value) is not int or value != 0 for value in retry_values)
        or side_retry_values != (0, 0, 0)
        or parsed.get("sdk_internal_retry_count") is not None
        or returned.sdk_internal_retry_state is not OpenRouterEvidenceState.NOT_APPLICABLE
        or returned.sdk_internal_retry_count is not None
    ):
        _reject(
            OpenRouterAcquisitionFailureCode.RETRY_ACTIVATED,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    streamed = parsed.get("stream_used")
    if type(streamed) is not bool or streamed or returned.stream_used is not False:
        _reject(
            OpenRouterAcquisitionFailureCode.STREAMING_RESPONSE_DETECTED,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    tool_calls = parsed.get("tool_calls")
    if type(tool_calls) is not int or tool_calls != 0 or returned.tool_calls != 0:
        _reject(
            OpenRouterAcquisitionFailureCode.TOOL_ACTIVATED,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )

    raw_usage = parsed.get("usage")
    if not isinstance(raw_usage, dict) or set(raw_usage) != _USAGE_KEYS:
        _reject(
            OpenRouterAcquisitionFailureCode.USAGE_INCOMPLETE,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    if any(type(value) is not int or value < 0 for value in raw_usage.values()):
        _reject(
            OpenRouterAcquisitionFailureCode.USAGE_INCOMPLETE,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    input_tokens = raw_usage["input_tokens"]
    output_tokens = raw_usage["output_tokens"]
    total_tokens = raw_usage["total_tokens"]
    if total_tokens != input_tokens + output_tokens:
        _reject(
            OpenRouterAcquisitionFailureCode.USAGE_INCONSISTENT,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    token_policy = capability_snapshot.token_policy
    if (
        input_tokens > token_policy.payload_input_token_upper_bound
        or output_tokens > token_policy.max_output_tokens
    ):
        _reject(
            OpenRouterAcquisitionFailureCode.REPORTED_USAGE_EXCEEDS_BOUND,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    try:
        usage_evidence = OpenRouterUsageEvidence(
            evidence_state=OpenRouterEvidenceState.SYNTHETIC_ONLY,
            token_completeness=OpenRouterUsageCompleteness.COMPLETE,
            token_policy=token_policy,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    except Exception:
        _reject(
            OpenRouterAcquisitionFailureCode.USAGE_INCONSISTENT,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
        )
    assert usage_evidence is not None
    side_usage = returned.usage_evidence
    if side_usage is None:
        _reject(
            OpenRouterAcquisitionFailureCode.USAGE_INCOMPLETE,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    if (
        side_usage.input_tokens,
        side_usage.output_tokens,
        side_usage.total_tokens,
    ) != (input_tokens, output_tokens, total_tokens):
        _reject(
            OpenRouterAcquisitionFailureCode.USAGE_INCONSISTENT,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    if side_usage != usage_evidence:
        _reject(
            OpenRouterAcquisitionFailureCode.RECEIPT_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )

    if returned.transport_attempt_id != transport_attempt_id:
        _reject(
            OpenRouterAcquisitionFailureCode.RECEIPT_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    if returned.prepared_body_id != prepared_body.prepared_body_id:
        _reject(
            OpenRouterAcquisitionFailureCode.RECEIPT_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    if returned.canned_transport_invocations != 1:
        _reject(
            OpenRouterAcquisitionFailureCode.CANNED_INVOCATION_COUNT_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    if returned.worker_terminated is not True:
        _reject(
            OpenRouterAcquisitionFailureCode.WORKER_NOT_TERMINATED,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    if returned.timeout_fired or returned.cancellation_requested:
        _reject(
            OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    try:
        rebuilt_envelope = OpenRouterCannedResponseEnvelope(
            transport_attempt_id=transport_attempt_id,
            prepared_body_id=prepared_body.prepared_body_id or "",
            transport_status=OpenRouterTransportStatus.DELIVERED,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
            timeout_fired=False,
            cancellation_requested=False,
        )
    except Exception:
        _reject(
            OpenRouterAcquisitionFailureCode.MALFORMED_RESPONSE_ENVELOPE,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    assert rebuilt_envelope is not None
    if rebuilt_envelope != returned:
        _reject(
            OpenRouterAcquisitionFailureCode.RECEIPT_MISMATCH,
            raw_response=raw_response,
            identity_evidence=identity_evidence,
            usage_evidence=usage_evidence,
        )
    return _DerivedDeliveredResponse(
        envelope=rebuilt_envelope,
        raw_response=raw_response,
        identity_evidence=identity_evidence,
        usage_evidence=usage_evidence,
    )


async def _terminate_worker(task: asyncio.Task[object]) -> None:
    grace_seconds = OPENROUTER_CANNED_CANCELLATION_GRACE_MS / 1000.0
    for _round in range(OPENROUTER_CANNED_CLEANUP_ROUNDS):
        task.cancel()
        done, _pending = await asyncio.wait((task,), timeout=grace_seconds)
        if done:
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            return
    raise OpenRouterAcquisitionAdapterError(
        "sealed canned worker resisted every bounded cancellation round"
    )


async def _invoke_one_shot(
    *,
    transport: OpenRouterCannedTransportV0,
    body_bytes: bytes,
    transport_attempt_id: str,
    timeout_ms: int,
) -> tuple[Optional[OpenRouterCannedResponseEnvelope], bool]:
    task = asyncio.create_task(
        _SEALED_TRANSPORT_INVOKE(transport, body_bytes, transport_attempt_id),
        name="socrates-zero-openrouter-canned-acquisition-1",
    )
    try:
        await asyncio.sleep(0)
        done, _pending = await asyncio.wait((task,), timeout=timeout_ms / 1000.0)
        if not done:
            await _terminate_worker(task)
            return None, True
        return task.result(), False
    except asyncio.CancelledError:
        if not task.done():
            await _terminate_worker(task)
        raise


def _terminal_record(
    transport: OpenRouterCannedTransportV0,
    *,
    body_bytes: bytes,
    transport_attempt_id: str,
) -> OpenRouterCannedInvocationRecordV0:
    if not _transport_state_is_valid(transport, require_unused=False):
        raise OpenRouterAcquisitionAdapterError("canned transport seal changed during dispatch")
    state = object.__getattribute__(transport, "__dict__")
    records = state["_records"]
    if not state["_started"] or len(records) != 1:
        raise OpenRouterAcquisitionAdapterError("one-shot invocation has no terminal record")
    record = records[0]
    if (
        record.ordinal != 1
        or record.transport_attempt_id != transport_attempt_id
        or record.received_body_bytes != body_bytes
        or record.received_body_sha256 != hashlib.sha256(body_bytes).hexdigest()
        or record.received_body_byte_length != len(body_bytes)
        or not record.worker_terminated
    ):
        raise OpenRouterAcquisitionAdapterError("terminal invocation record is inconsistent")
    return record


def _build_success_receipt(
    *,
    semantic_request_id: str,
    prepared_body: OpenRouterPreparedBody,
    capability_snapshot: OpenRouterCapabilitySnapshot,
    derived: _DerivedDeliveredResponse,
) -> OpenRouterAttemptReceipt:
    return OpenRouterAttemptReceipt(
        outcome=OpenRouterAttemptOutcome.CANNED_OBSERVATION_CAPTURED,
        semantic_request_id=semantic_request_id,
        capability_snapshot=capability_snapshot,
        prepared_body=prepared_body,
        canned_response_envelope=derived.envelope,
        raw_response=derived.raw_response,
        identity_evidence=derived.identity_evidence,
        usage_evidence=derived.usage_evidence,
        canned_transport_invocations=1,
        application_fallback_used=False,
        explicit_retry_count=0,
        adapter_retry_count=0,
        hidden_transport_retry_count=0,
        stream_used=False,
        tool_calls=0,
    )


def _build_failure_result(
    *,
    code: OpenRouterAcquisitionFailureCode,
    semantic_request_id: str,
    prepared_body: OpenRouterPreparedBody,
    capability_snapshot: OpenRouterCapabilitySnapshot,
    invocation_record: OpenRouterCannedInvocationRecordV0,
    envelope: Optional[OpenRouterCannedResponseEnvelope] = None,
    raw_response: Optional[OpenRouterRawResponseEvidence] = None,
    identity_evidence: Optional[OpenRouterIdentityEvidence] = None,
    usage_evidence: Optional[OpenRouterUsageEvidence] = None,
) -> OpenRouterAcquisitionAdapterResultV0:
    receipt = OpenRouterAttemptReceipt(
        outcome=OpenRouterAttemptOutcome.FAILED_CLOSED,
        semantic_request_id=semantic_request_id,
        capability_snapshot=capability_snapshot,
        prepared_body=prepared_body,
        canned_response_envelope=envelope,
        raw_response=raw_response,
        identity_evidence=identity_evidence,
        usage_evidence=usage_evidence,
        canned_transport_invocations=1,
        application_fallback_used=False,
        explicit_retry_count=0,
        adapter_retry_count=0,
        hidden_transport_retry_count=0,
        stream_used=False,
        tool_calls=0,
        failure_code=code.value,
    )
    return OpenRouterAcquisitionAdapterResultV0(
        attempt_receipt=receipt,
        invocation_record=invocation_record,
    )


async def acquire_openrouter_canned_v0(
    *,
    semantic_request_id: str,
    transport_attempt_id: str,
    prepared_body: OpenRouterPreparedBody,
    capability_snapshot: OpenRouterCapabilitySnapshot,
    transport: OpenRouterCannedTransportV0,
) -> OpenRouterAcquisitionAdapterResultV0:
    """Run one experimental harness attempt under an active clean tripwire.

    This low-level entry is not production activation: no production module
    imports it, and an inactive tripwire rejects it before dispatch.  The
    production-shaped facade below remains disabled unless a caller explicitly
    enables one canned-only instance.
    """

    require_clean_acquisition_boundary_tripwire_v0()
    body_bytes = _validate_authoritative_inputs(
        semantic_request_id=semantic_request_id,
        transport_attempt_id=transport_attempt_id,
        prepared_body=prepared_body,
        capability_snapshot=capability_snapshot,
        transport=transport,
    )
    late_mutation_attempts_before = _late_mutation_attempt_count(transport)
    try:
        try:
            returned, timed_out = await _invoke_one_shot(
                transport=transport,
                body_bytes=body_bytes,
                transport_attempt_id=transport_attempt_id,
                timeout_ms=capability_snapshot.transport_policy.total_timeout_ms,
            )
        except _OpenRouterCannedTransportError:
            record = _terminal_record(
                transport,
                body_bytes=body_bytes,
                transport_attempt_id=transport_attempt_id,
            )
            return _build_failure_result(
                code=OpenRouterAcquisitionFailureCode.CANNED_TRANSPORT_ERROR,
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                invocation_record=record,
            )
        except OpenRouterAcquisitionAdapterError:
            if object.__getattribute__(transport, "_started"):
                record = _terminal_record(
                    transport,
                    body_bytes=body_bytes,
                    transport_attempt_id=transport_attempt_id,
                )
                return _build_failure_result(
                    code=OpenRouterAcquisitionFailureCode.CANNED_TRANSPORT_ERROR,
                    semantic_request_id=semantic_request_id,
                    prepared_body=prepared_body,
                    capability_snapshot=capability_snapshot,
                    invocation_record=record,
                )
            raise
        except Exception:
            record = _terminal_record(
                transport,
                body_bytes=body_bytes,
                transport_attempt_id=transport_attempt_id,
            )
            return _build_failure_result(
                code=OpenRouterAcquisitionFailureCode.CANNED_TRANSPORT_ERROR,
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                invocation_record=record,
            )

        record = _terminal_record(
            transport,
            body_bytes=body_bytes,
            transport_attempt_id=transport_attempt_id,
        )
        # Every returned-envelope path, including an early parse/identity/usage
        # failure, crosses this barrier before returning.  A sealed late-effect
        # probe has no opportunity to survive until event-loop shutdown.
        await asyncio.sleep(0)
        post_return_late_mutation = (
            _late_mutation_attempt_count(transport)
            != late_mutation_attempts_before
        )
        if timed_out:
            timeout_envelope = OpenRouterCannedResponseEnvelope(
                transport_attempt_id=transport_attempt_id,
                prepared_body_id=prepared_body.prepared_body_id or "",
                transport_status=OpenRouterTransportStatus.TIMEOUT,
                timeout_fired=True,
                cancellation_requested=True,
                transport_error_code="CANNED_TIMEOUT",
            )
            return _build_failure_result(
                code=OpenRouterAcquisitionFailureCode.TRANSPORT_TIMEOUT,
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                invocation_record=record,
                envelope=timeout_envelope,
            )
        if returned is None:
            return _build_failure_result(
                code=OpenRouterAcquisitionFailureCode.CANNED_TRANSPORT_ERROR,
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                invocation_record=record,
            )
        if returned.transport_status is not OpenRouterTransportStatus.DELIVERED:
            try:
                failed_envelope = OpenRouterCannedResponseEnvelope.model_validate(
                    returned.model_dump(mode="json")
                )
            except Exception:
                failed_envelope = None
            return _build_failure_result(
                code=(
                    OpenRouterAcquisitionFailureCode.TRANSPORT_TIMEOUT
                    if returned.transport_status is OpenRouterTransportStatus.TIMEOUT
                    else OpenRouterAcquisitionFailureCode.CANNED_TRANSPORT_ERROR
                ),
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                invocation_record=record,
                envelope=failed_envelope,
            )
        try:
            derived = _derive_delivered_response(
                returned,
                transport_attempt_id=transport_attempt_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
            )
        except _ResponseRejected as rejected:
            return _build_failure_result(
                code=(
                    OpenRouterAcquisitionFailureCode.LATE_MUTATION_DETECTED
                    if post_return_late_mutation
                    else rejected.code
                ),
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                invocation_record=record,
                raw_response=rejected.raw_response,
                identity_evidence=rejected.identity_evidence,
                usage_evidence=rejected.usage_evidence,
            )
        frozen_record = record
        try:
            receipt = _build_success_receipt(
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                derived=derived,
            )
            rebuilt_receipt = OpenRouterAttemptReceipt.model_validate(
                receipt.model_dump(mode="json")
            )
            if rebuilt_receipt != receipt:
                raise OpenRouterAcquisitionAdapterError("receipt round-trip changed")
        except Exception:
            return _build_failure_result(
                code=OpenRouterAcquisitionFailureCode.RECEIPT_MISMATCH,
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                invocation_record=frozen_record,
                raw_response=derived.raw_response,
                identity_evidence=derived.identity_evidence,
                usage_evidence=derived.usage_evidence,
            )
        # Give a returned worker exactly one scheduling boundary in which to
        # expose a prohibited post-return mutation attempt, then freeze state.
        await asyncio.sleep(0)
        try:
            current_record = _terminal_record(
                transport,
                body_bytes=body_bytes,
                transport_attempt_id=transport_attempt_id,
            )
        except OpenRouterAcquisitionAdapterError:
            current_record = None
        late_mutation_detected = (
            _late_mutation_attempt_count(transport)
            != late_mutation_attempts_before
            or current_record != frozen_record
        )
        if late_mutation_detected:
            return _build_failure_result(
                code=OpenRouterAcquisitionFailureCode.LATE_MUTATION_DETECTED,
                semantic_request_id=semantic_request_id,
                prepared_body=prepared_body,
                capability_snapshot=capability_snapshot,
                invocation_record=frozen_record,
                raw_response=derived.raw_response,
                identity_evidence=derived.identity_evidence,
                usage_evidence=derived.usage_evidence,
            )
        return OpenRouterAcquisitionAdapterResultV0(
            attempt_receipt=receipt,
            invocation_record=frozen_record,
        )
    finally:
        require_clean_acquisition_boundary_tripwire_v0()


class OpenRouterAcquisitionAdapterV0:
    """Default-disabled, non-governing facade over the sealed canned entry."""

    adapter_id = OPENROUTER_ACQUISITION_ADAPTER_ID

    def __init_subclass__(cls, **_kwargs: object) -> None:
        raise TypeError("OpenRouterAcquisitionAdapterV0 is sealed")

    def __setattr__(self, name: str, value: object) -> None:
        try:
            sealed = object.__getattribute__(self, "_sealed")
        except AttributeError:
            sealed = False
        if sealed:
            raise AttributeError("OpenRouter acquisition adapter facade is sealed")
        object.__setattr__(self, name, value)

    def __init__(self, *, canned_execution_enabled: bool = False) -> None:
        if type(canned_execution_enabled) is not bool:
            raise TypeError("canned_execution_enabled must be an exact boolean")
        object.__setattr__(self, "_sealed", False)
        self._canned_execution_enabled = canned_execution_enabled
        self._consumed = False
        object.__setattr__(self, "_sealed", True)

    @property
    def canned_execution_enabled(self) -> bool:
        return object.__getattribute__(self, "_canned_execution_enabled")

    @property
    def admission_status(self) -> str:
        return "UNADMITTED"

    @property
    def governance_status(self) -> str:
        return "NON_GOVERNING"

    @property
    def ced_application_count(self) -> int:
        return 0

    @property
    def live_authorization_allowed(self) -> bool:
        return False

    async def acquire_canned(
        self,
        *,
        semantic_request_id: str,
        transport_attempt_id: str,
        prepared_body: OpenRouterPreparedBody,
        capability_snapshot: OpenRouterCapabilitySnapshot,
        transport: OpenRouterCannedTransportV0,
    ) -> OpenRouterAcquisitionAdapterResultV0:
        if type(self) is not OpenRouterAcquisitionAdapterV0:
            raise OpenRouterAcquisitionAdapterError("adapter facade type is not exact")
        if not object.__getattribute__(self, "_canned_execution_enabled"):
            raise OpenRouterAcquisitionAdapterError(
                "canned acquisition adapter is disabled by default"
            )
        if object.__getattribute__(self, "_consumed"):
            raise OpenRouterAcquisitionAdapterError(
                "one-shot acquisition adapter facade is already consumed"
            )
        object.__setattr__(self, "_consumed", True)
        return await acquire_openrouter_canned_v0(
            semantic_request_id=semantic_request_id,
            transport_attempt_id=transport_attempt_id,
            prepared_body=prepared_body,
            capability_snapshot=capability_snapshot,
            transport=transport,
        )


__all__ = [
    "OPENROUTER_CANNED_TRANSPORT_ID",
    "OpenRouterAcquisitionAdapterV0",
    "OpenRouterAcquisitionAdapterError",
    "OpenRouterAcquisitionAdapterResultV0",
    "OpenRouterAcquisitionFailureCode",
    "OpenRouterCannedInvocationOutcome",
    "OpenRouterCannedInvocationRecordV0",
    "OpenRouterCannedTransportDirectiveV0",
    "OpenRouterCannedTransportV0",
    "acquire_openrouter_canned_v0",
]
