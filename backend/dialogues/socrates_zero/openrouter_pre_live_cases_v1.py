"""Frozen offline case set for OpenRouter pre-live integration v1.

Two complete sibling chains exist, A and B, so cross-request substitution can be
attacked directly: every mix of A's request with B's transport, A's transport
with B's response, A's response with B's mapping, and A's chain with B's
authorization must fail closed.

Request digests are frozen literals rather than rendered at import time, which
keeps the module import-inert.  A test re-renders the real request from the
repository and requires it to equal chain A, so the literals are bound to reality
rather than trusted.

Response bodies reuse the S5 wire shapes, which are themselves derived from the
retained official snapshots.  No new wire semantics are invented here.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_pre_live_integration_v1 import (
    OpenRouterIntegrationFailureCodeV1,
    OpenRouterTransportCompletionStateV1,
    OpenRouterTransportExecutionRecordV1,
    OpenRouterTransportRegistrationStateV1,
)
from .openrouter_pre_live_safety_v1 import (
    OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1,
    OPENROUTER_SEALED_REQUEST_BODY_BYTES_V1,
    OpenRouterBoundStatusV1,
    OpenRouterCredentialPresenceAttestationV1,
    OpenRouterInputBoundBasisV1,
    OpenRouterInputBoundEvidenceV1,
    OpenRouterOperatorCeilingV1,
    OpenRouterOutputBoundEvidenceV1,
    OpenRouterPreflightFailureCodeV1,
    OpenRouterPricingSourceV1,
    OpenRouterTrustedPricingRecordV1,
)
from .openrouter_route_controls_contracts import OpenRouterRequestIntentReceiptV1

OPENROUTER_INTEGRATION_CASE_SCHEMA_V1 = (
    "socrateszero-openrouter-integration-case/v1"
)
OPENROUTER_INTEGRATION_CASE_SET_SCHEMA_V1 = (
    "socrateszero-openrouter-integration-case-set/v1"
)

# --- Chain A: the real rendered request, pinned as literals (verified by test).
_A_BODY_SHA = "35a119b1e35f9f8ce05baf57009d787358bf086aaae4055ef56fcfedade514a1"
_A_BODY_LEN = 447
_A_HEADERS_SHA = "1c688da6c6494631d6922fcb89a56b126e0900327dd865c2483d84f3c9f58149"
_A_HEADERS_LEN = 98
_A_ROUTE_INTENT_ID = (
    "szorrouteintent_d26fcc19fd146c37ce7d3181055cdd447eab91dc2295319a31a3e81c52362c8b"
)
_A_POLICY_ID = (
    "szorroutecontrolsv1_67a0a4b9ca91805fd62ee30e89afdfe5c88c912b4db904311b966bc82708b036"
)
_A_CONTRACT_ID = (
    "szorrouteintentcontractv1_"
    "7bd1e67cad72f21127369f68e5aa9ecacb4752a8f7a275d2db7b3826f3b1e932"
)

# --- Chain B: a sibling request that differs in its rendered bytes.
_B_BODY_SHA = "b" * 64
_B_BODY_LEN = 461
_B_HEADERS_SHA = "c" * 64
_B_HEADERS_LEN = 104
_B_ROUTE_INTENT_ID = "szorrouteintent_" + "d" * 64


def _intent(
    body_sha: str,
    body_len: int,
    headers_sha: str,
    headers_len: int,
    route_intent_id: str,
) -> OpenRouterRequestIntentReceiptV1:
    return OpenRouterRequestIntentReceiptV1(
        route_control_policy_id=_A_POLICY_ID,
        route_intent_contract_id=_A_CONTRACT_ID,
        route_intent_id=route_intent_id,
        body_sha256=body_sha,
        body_length=body_len,
        semantic_headers_sha256=headers_sha,
        semantic_headers_length=headers_len,
    )


INTENT_A = _intent(
    _A_BODY_SHA, _A_BODY_LEN, _A_HEADERS_SHA, _A_HEADERS_LEN, _A_ROUTE_INTENT_ID
)
INTENT_B = _intent(
    _B_BODY_SHA, _B_BODY_LEN, _B_HEADERS_SHA, _B_HEADERS_LEN, _B_ROUTE_INTENT_ID
)


# ------------------------------------------------------------ response bodies


_SCAFFOLD_CHOICES = [
    {"index": 0, "message": {"role": "assistant", "content": "scaffolding"}}
]


def _metadata(**overrides) -> dict:
    base = {
        "requested": "openai/gpt-4.1-mini",
        "strategy": "direct",
        "region": "iad",
        "summary": "available=1, selected=Azure",
        "attempt": 1,
        "is_byok": False,
        "endpoints": {
            "total": 1,
            "available": [
                {"provider": "Azure", "model": "openai/gpt-4.1-mini", "selected": True}
            ],
        },
    }
    base.update(overrides)
    return base


def _success(metadata=None, model="openai/gpt-4.1-mini", **extra) -> bytes:
    body = {"id": "gen-scaffold", "model": model, "choices": _SCAFFOLD_CHOICES}
    if metadata is not None:
        body["openrouter_metadata"] = metadata
    body.update(extra)
    return json.dumps(body).encode("utf-8")


def _error(metadata=None, code: int = 404) -> bytes:
    body = {"error": {"code": code, "message": "scaffolding error"}}
    if metadata is not None:
        body["openrouter_metadata"] = metadata
    return json.dumps(body).encode("utf-8")


RESPONSE_A = _success(_metadata())
RESPONSE_B = _success(_metadata(summary="sibling chain B"), model="openai/gpt-4.1-mini")
HEADERS_A = (("X-Generation-Id", "gen-a"), ("X-OpenRouter-Cache-Status", "MISS"))
HEADERS_B = (("X-Generation-Id", "gen-b"), ("X-OpenRouter-Cache-Status", "MISS"))


class OpenRouterIntegrationCaseKindV1(str, Enum):
    POSITIVE = "POSITIVE"
    ADVERSARIAL = "ADVERSARIAL"


class OpenRouterIntegrationExpectedOutcomeV1(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class _FrozenCaseContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterIntegrationCaseV1(_FrozenCaseContractV1):
    """One frozen integration case.

    ``mapping_body``/``mapping_headers`` normally equal the observation, and
    differ only where a case deliberately pairs a mapping with a sibling
    response.
    """

    schema_version: Literal[
        OPENROUTER_INTEGRATION_CASE_SCHEMA_V1
    ] = OPENROUTER_INTEGRATION_CASE_SCHEMA_V1
    case_id: str
    kind: OpenRouterIntegrationCaseKindV1
    description: str
    intent: OpenRouterRequestIntentReceiptV1
    transport: OpenRouterTransportExecutionRecordV1
    observation_body: bytes
    observation_headers: Tuple[Tuple[str, str], ...]
    mapping_body: bytes
    mapping_headers: Tuple[Tuple[str, str], ...]
    expected_outcome: OpenRouterIntegrationExpectedOutcomeV1
    expected_failure_code: Optional[OpenRouterIntegrationFailureCodeV1] = None
    expected_fields: Tuple[Tuple[str, str], ...] = ()
    case_fingerprint: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterIntegrationCaseV1":
        accepted = (
            self.expected_outcome is OpenRouterIntegrationExpectedOutcomeV1.ACCEPTED
        )
        if accepted != (self.expected_failure_code is None):
            raise ContractValidationError(
                "expected outcome disagrees with the predeclared failure code"
            )
        expected = stable_contract_id(
            "szorintegrationcasev1",
            {
                "case_id": self.case_id,
                "kind": self.kind.value,
                "intent_receipt_id": self.intent.receipt_id,
                "transport_record_id": self.transport.record_id,
                "observation_body_hex": self.observation_body.hex(),
                "observation_headers": [list(p) for p in self.observation_headers],
                "mapping_body_hex": self.mapping_body.hex(),
                "mapping_headers": [list(p) for p in self.mapping_headers],
                "expected_outcome": self.expected_outcome.value,
                "expected_failure_code": (
                    self.expected_failure_code.value
                    if self.expected_failure_code
                    else None
                ),
                "expected_fields": [list(p) for p in self.expected_fields],
            },
        )
        if self.case_fingerprint not in (None, expected):
            raise ContractValidationError("integration case fingerprint mismatch")
        object.__setattr__(self, "case_fingerprint", expected)
        return self


class OpenRouterIntegrationCaseSetV1(_FrozenCaseContractV1):
    schema_version: Literal[
        OPENROUTER_INTEGRATION_CASE_SET_SCHEMA_V1
    ] = OPENROUTER_INTEGRATION_CASE_SET_SCHEMA_V1
    cases: Tuple[OpenRouterIntegrationCaseV1, ...]
    case_set_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterIntegrationCaseSetV1":
        ids = [case.case_id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ContractValidationError("integration case IDs must be unique")
        if ids != sorted(ids):
            raise ContractValidationError("integration cases must be in stable order")
        expected = stable_contract_id(
            "szorintegrationcasesetv1",
            [case.case_fingerprint for case in self.cases],
        )
        if self.case_set_id not in (None, expected):
            raise ContractValidationError("integration case-set ID mismatch")
        object.__setattr__(self, "case_set_id", expected)
        return self


# ------------------------------------------------------------ transport helper


def _sha(value: bytes) -> str:
    import hashlib

    return hashlib.sha256(value).hexdigest()


def _header_evidence(headers: Tuple[Tuple[str, str], ...]) -> Tuple[str, int]:
    import hashlib

    payload = canonical_json([[name, value] for name, value in headers])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest(), len(headers)


def _transport(
    intent: OpenRouterRequestIntentReceiptV1,
    response_body: Optional[bytes],
    response_headers: Tuple[Tuple[str, str], ...] = (),
    *,
    registration: OpenRouterTransportRegistrationStateV1 = (
        OpenRouterTransportRegistrationStateV1.REGISTERED
    ),
    dispatches: int = 1,
    completion: OpenRouterTransportCompletionStateV1 = (
        OpenRouterTransportCompletionStateV1.COMPLETED
    ),
    registered_body_sha: Optional[str] = None,
    registered_body_len: Optional[int] = None,
    registered_headers_sha: Optional[str] = None,
    registered_headers_len: Optional[int] = None,
    timeout_fired: bool = False,
    worker_terminated: bool = False,
) -> OpenRouterTransportExecutionRecordV1:
    if response_body is None:
        response_sha = response_len = header_sha = header_count = None
        present = False
    else:
        response_sha, response_len = _sha(response_body), len(response_body)
        header_sha, header_count = _header_evidence(response_headers)
        present = True
    return OpenRouterTransportExecutionRecordV1(
        registration_state=registration,
        registered_body_sha256=(
            registered_body_sha
            if registered_body_sha is not None
            else (intent.body_sha256 if registration.value == "REGISTERED" else None)
        ),
        registered_body_length=(
            registered_body_len
            if registered_body_len is not None
            else (intent.body_length if registration.value == "REGISTERED" else None)
        ),
        registered_semantic_headers_sha256=(
            registered_headers_sha
            if registered_headers_sha is not None
            else (
                intent.semantic_headers_sha256
                if registration.value == "REGISTERED"
                else None
            )
        ),
        registered_semantic_headers_length=(
            registered_headers_len
            if registered_headers_len is not None
            else (
                intent.semantic_headers_length
                if registration.value == "REGISTERED"
                else None
            )
        ),
        local_dispatch_count=dispatches,
        completion_state=completion,
        response_present=present,
        response_body_sha256=response_sha,
        response_body_length=response_len,
        response_header_evidence_sha256=header_sha,
        response_header_count=header_count,
        timeout_fired=timeout_fired,
        worker_terminated=worker_terminated,
    )


def _expect(**fields) -> Tuple[Tuple[str, str], ...]:
    return tuple((k, canonical_json(v)) for k, v in sorted(fields.items()))


def _positive(
    case_id: str,
    description: str,
    body: bytes,
    headers: Tuple[Tuple[str, str], ...],
    **expected,
) -> OpenRouterIntegrationCaseV1:
    return OpenRouterIntegrationCaseV1(
        case_id=case_id,
        kind=OpenRouterIntegrationCaseKindV1.POSITIVE,
        description=description,
        intent=INTENT_A,
        transport=_transport(INTENT_A, body, headers),
        observation_body=body,
        observation_headers=headers,
        mapping_body=body,
        mapping_headers=headers,
        expected_outcome=OpenRouterIntegrationExpectedOutcomeV1.ACCEPTED,
        expected_fields=_expect(**expected),
    )


_F = OpenRouterIntegrationFailureCodeV1

_POSITIVE: Tuple[OpenRouterIntegrationCaseV1, ...] = (
    _positive(
        "orintegv1-p01-success-chain",
        "Exact request, one dispatch, success response, mapping bound.",
        RESPONSE_A,
        HEADERS_A,
        model_conformance="MATCH",
        actual_served_model="openai/gpt-4.1-mini",
        cache_conformance="CONSISTENT_WITH_DISABLED_INTENT",
        local_dispatch_count=1,
    ),
    _positive(
        "orintegv1-p02-documented-error-chain",
        "Documented error envelope with partial metadata still binds causally.",
        _error(
            {
                "requested": "openai/gpt-4.1-mini",
                "strategy": "direct",
                "attempt": 0,
                "endpoints": {"total": 1, "available": []},
            }
        ),
        HEADERS_A,
        model_conformance="UNAVAILABLE",
        actual_served_model=None,
        actual_served_model_status="ABSENT_FROM_OBSERVATION",
    ),
    _positive(
        "orintegv1-p03-cache-hit-chain",
        "Cache HIT: header authority, metadata absent as documented.",
        _success(),
        (
            ("X-OpenRouter-Cache-Status", "HIT"),
            ("X-OpenRouter-Cache-Age", "12"),
            ("X-Generation-Id", "gen-hit"),
        ),
        cache_conformance="ANOMALOUS_HIT_UNDER_DISABLED_INTENT",
        response_cache_status="HIT",
    ),
    _positive(
        "orintegv1-p04-cache-miss-chain",
        "Cache MISS is consistent with the pinned disabled cache intent.",
        RESPONSE_A,
        HEADERS_A,
        cache_conformance="CONSISTENT_WITH_DISABLED_INTENT",
        response_cache_status="MISS",
    ),
    _positive(
        "orintegv1-p05-no-cache-header-chain",
        "No cache header at all leaves cache authority absent.",
        RESPONSE_A,
        (("X-Generation-Id", "gen-a"),),
        cache_conformance="NO_RESPONSE_AUTHORITY",
        response_cache_status=None,
    ),
    _positive(
        "orintegv1-p06-provider-display-label-preserved",
        "Provider evidence stays a display label and never becomes a slug.",
        RESPONSE_A,
        HEADERS_A,
        response_provider_display_names=["Azure"],
        requested_exact_endpoint_selector="azure/swedencentral",
    ),
    _positive(
        "orintegv1-p07-attempts-absent",
        "attempts absent is preserved, never synthesized.",
        RESPONSE_A,
        HEADERS_A,
        response_attempts_presence="ABSENT",
    ),
    _positive(
        "orintegv1-p08-attempts-present-empty",
        "An empty attempts array is distinct from an absent one.",
        _success(_metadata(attempts=[])),
        HEADERS_A,
        response_attempts_presence="PRESENT_EMPTY",
    ),
    _positive(
        "orintegv1-p09-attempts-present-with-entries",
        "Server-reported attempts never imply local retries.",
        _success(
            _metadata(
                attempt=2,
                attempts=[
                    {"provider": "OpenAI", "model": "openai/gpt-4.1-mini", "status": 503},
                    {"provider": "Azure", "model": "openai/gpt-4.1-mini", "status": 200},
                ],
            )
        ),
        HEADERS_A,
        response_attempts_presence="PRESENT_WITH_ENTRIES",
        response_attempt=2,
        local_dispatch_count=1,
    ),
    _positive(
        "orintegv1-p10-exact-endpoint-remains-unavailable",
        "Exact endpoint response identity survives integration unchanged.",
        RESPONSE_A,
        HEADERS_A,
        exact_endpoint_response_identity=None,
        exact_endpoint_response_identity_status=(
            "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"
        ),
    ),
    _positive(
        "orintegv1-p11-actual-model-mismatch-still-binds",
        "A served-model mismatch is real evidence: causally valid, policy FAIL.",
        _success(_metadata(), model="anthropic/claude-sonnet-4"),
        HEADERS_A,
        model_conformance="MISMATCH",
        actual_served_model="anthropic/claude-sonnet-4",
        requested_model="openai/gpt-4.1-mini",
    ),
    _positive(
        "orintegv1-p12-sibling-chain-b-binds-independently",
        "Chain B is a complete valid chain of its own.",
        RESPONSE_B,
        HEADERS_B,
        local_dispatch_count=1,
    ),
)
# Chain B's positive case must use intent B throughout.
_POSITIVE = _POSITIVE[:-1] + (
    OpenRouterIntegrationCaseV1(
        case_id="orintegv1-p12-sibling-chain-b-binds-independently",
        kind=OpenRouterIntegrationCaseKindV1.POSITIVE,
        description="Chain B is a complete valid chain of its own.",
        intent=INTENT_B,
        transport=_transport(INTENT_B, RESPONSE_B, HEADERS_B),
        observation_body=RESPONSE_B,
        observation_headers=HEADERS_B,
        mapping_body=RESPONSE_B,
        mapping_headers=HEADERS_B,
        expected_outcome=OpenRouterIntegrationExpectedOutcomeV1.ACCEPTED,
        expected_fields=_expect(local_dispatch_count=1),
    ),
)


def _adv(
    case_id: str,
    description: str,
    code: OpenRouterIntegrationFailureCodeV1,
    *,
    intent: OpenRouterRequestIntentReceiptV1 = INTENT_A,
    transport: Optional[OpenRouterTransportExecutionRecordV1] = None,
    observation_body: bytes = RESPONSE_A,
    observation_headers: Tuple[Tuple[str, str], ...] = HEADERS_A,
    mapping_body: Optional[bytes] = None,
    mapping_headers: Optional[Tuple[Tuple[str, str], ...]] = None,
) -> OpenRouterIntegrationCaseV1:
    return OpenRouterIntegrationCaseV1(
        case_id=case_id,
        kind=OpenRouterIntegrationCaseKindV1.ADVERSARIAL,
        description=description,
        intent=intent,
        transport=(
            transport
            if transport is not None
            else _transport(intent, observation_body, observation_headers)
        ),
        observation_body=observation_body,
        observation_headers=observation_headers,
        mapping_body=mapping_body if mapping_body is not None else observation_body,
        mapping_headers=(
            mapping_headers if mapping_headers is not None else observation_headers
        ),
        expected_outcome=OpenRouterIntegrationExpectedOutcomeV1.REJECTED,
        expected_failure_code=code,
    )


_ADVERSARIAL: Tuple[OpenRouterIntegrationCaseV1, ...] = (
    _adv(
        "orintegv1-x01-transport-not-registered",
        "Transport was never registered for dispatch.",
        _F.TRANSPORT_NOT_REGISTERED,
        transport=_transport(
            INTENT_A,
            RESPONSE_A,
            HEADERS_A,
            registration=OpenRouterTransportRegistrationStateV1.UNREGISTERED,
        ),
    ),
    _adv(
        "orintegv1-x02-registered-body-digest-mismatch",
        "Registered body digest differs from the intended request body.",
        _F.REGISTERED_BODY_MISMATCH,
        transport=_transport(
            INTENT_A, RESPONSE_A, HEADERS_A, registered_body_sha="0" * 64
        ),
    ),
    _adv(
        "orintegv1-x03-registered-body-length-mismatch",
        "Registered body length differs after a post-render mutation.",
        _F.REGISTERED_BODY_MISMATCH,
        transport=_transport(
            INTENT_A, RESPONSE_A, HEADERS_A, registered_body_len=_A_BODY_LEN + 1
        ),
    ),
    _adv(
        "orintegv1-x04-registered-headers-mismatch",
        "Registered semantic headers differ from the intended headers.",
        _F.REGISTERED_HEADERS_MISMATCH,
        transport=_transport(
            INTENT_A, RESPONSE_A, HEADERS_A, registered_headers_sha="0" * 64
        ),
    ),
    _adv(
        "orintegv1-x05-sibling-request-paired-to-transport",
        "Substitution matrix: request B paired with transport registered for A.",
        _F.REGISTERED_BODY_MISMATCH,
        intent=INTENT_B,
        transport=_transport(INTENT_A, RESPONSE_A, HEADERS_A),
    ),
    _adv(
        "orintegv1-x06-sibling-transport-paired-to-request",
        "Substitution matrix: request A paired with transport registered for B.",
        _F.REGISTERED_BODY_MISMATCH,
        intent=INTENT_A,
        transport=_transport(INTENT_B, RESPONSE_B, HEADERS_B),
    ),
    _adv(
        "orintegv1-x07-dispatch-count-zero",
        "Nothing was dispatched, so nothing can be bound.",
        _F.DISPATCH_COUNT_INVALID,
        transport=_transport(INTENT_A, RESPONSE_A, HEADERS_A, dispatches=0),
    ),
    _adv(
        "orintegv1-x08-dispatch-count-two",
        "A local retry breaks the one-shot rule.",
        _F.DISPATCH_COUNT_INVALID,
        transport=_transport(INTENT_A, RESPONSE_A, HEADERS_A, dispatches=2),
    ),
    _adv(
        "orintegv1-x09-transport-pending",
        "No mapping may be authoritative before transport completion.",
        _F.TRANSPORT_NOT_COMPLETE,
        transport=_transport(
            INTENT_A,
            RESPONSE_A,
            HEADERS_A,
            completion=OpenRouterTransportCompletionStateV1.PENDING,
        ),
    ),
    _adv(
        "orintegv1-x10-transport-timed-out",
        "A timed-out transport is not a completed one.",
        _F.TRANSPORT_NOT_COMPLETE,
        transport=_transport(
            INTENT_A,
            RESPONSE_A,
            HEADERS_A,
            completion=OpenRouterTransportCompletionStateV1.TIMED_OUT,
            timeout_fired=True,
            worker_terminated=True,
        ),
    ),
    _adv(
        "orintegv1-x11-transport-failed",
        "A failed transport is not a completed one.",
        _F.TRANSPORT_NOT_COMPLETE,
        transport=_transport(
            INTENT_A,
            RESPONSE_A,
            HEADERS_A,
            completion=OpenRouterTransportCompletionStateV1.FAILED,
        ),
    ),
    _adv(
        "orintegv1-x12-response-absent",
        "A completed transport with no response cannot bind.",
        _F.RESPONSE_ABSENT,
        transport=_transport(INTENT_A, None),
    ),
    _adv(
        "orintegv1-x13-response-body-swapped",
        "The observation is not the response this transport received.",
        _F.RESPONSE_BODY_BINDING_MISMATCH,
        transport=_transport(INTENT_A, RESPONSE_B, HEADERS_A),
        observation_body=RESPONSE_A,
        observation_headers=HEADERS_A,
    ),
    _adv(
        "orintegv1-x14-response-headers-swapped",
        "Response header evidence does not match the transport's headers.",
        _F.RESPONSE_HEADER_BINDING_MISMATCH,
        transport=_transport(INTENT_A, RESPONSE_A, HEADERS_B),
        observation_body=RESPONSE_A,
        observation_headers=HEADERS_A,
    ),
    _adv(
        "orintegv1-x15-sibling-response-observation",
        "Substitution matrix: transport A with response B's observation.",
        _F.RESPONSE_BODY_BINDING_MISMATCH,
        transport=_transport(INTENT_A, RESPONSE_A, HEADERS_A),
        observation_body=RESPONSE_B,
        observation_headers=HEADERS_B,
    ),
    _adv(
        "orintegv1-x16-mapping-from-sibling-observation",
        "Substitution matrix: response A bound, mapping taken from response B.",
        _F.MAPPING_OBSERVATION_MISMATCH,
        observation_body=RESPONSE_A,
        observation_headers=HEADERS_A,
        mapping_body=RESPONSE_B,
        mapping_headers=HEADERS_B,
    ),
    _adv(
        "orintegv1-x17-mapping-header-provenance-mismatch",
        "Mapping made from the same body but different header evidence.",
        _F.MAPPING_OBSERVATION_MISMATCH,
        observation_body=RESPONSE_A,
        observation_headers=HEADERS_A,
        mapping_body=RESPONSE_A,
        mapping_headers=HEADERS_B,
    ),
    _adv(
        "orintegv1-x18-whitespace-variant-observation",
        "A whitespace variant is different wire evidence, so it cannot bind.",
        _F.RESPONSE_BODY_BINDING_MISMATCH,
        transport=_transport(INTENT_A, RESPONSE_A, HEADERS_A),
        observation_body=json.dumps(
            json.loads(RESPONSE_A.decode("utf-8")), indent=2
        ).encode("utf-8"),
        observation_headers=HEADERS_A,
    ),
)

FROZEN_OPENROUTER_INTEGRATION_CASES_V1: Tuple[OpenRouterIntegrationCaseV1, ...] = tuple(
    sorted(_POSITIVE + _ADVERSARIAL, key=lambda case: case.case_id)
)
FROZEN_OPENROUTER_INTEGRATION_CASE_SET_V1 = OpenRouterIntegrationCaseSetV1(
    cases=FROZEN_OPENROUTER_INTEGRATION_CASES_V1
)
OPENROUTER_INTEGRATION_CASE_SET_ID_V1 = (
    FROZEN_OPENROUTER_INTEGRATION_CASE_SET_V1.case_set_id
)


# ------------------------------------------------------- preflight case family


OPENROUTER_PREFLIGHT_CASE_SCHEMA_V1 = "socrateszero-openrouter-preflight-case/v1"

#: A synthetic preflight execution identity.  Structural freshness, not a clock.
PREFLIGHT_EXECUTION_ID = "szorpreflightexec_offline_s6_reference"

#: The honest current state of P17: no pinned tokenizer is available in this
#: repository, so no input token bound exists.  The byte cap sits beside it and
#: is never presented as a token bound.
INPUT_BOUND_UNESTABLISHED = OpenRouterInputBoundEvidenceV1(
    status=OpenRouterBoundStatusV1.NOT_ESTABLISHED,
    basis=OpenRouterInputBoundBasisV1.NO_PINNED_TOKENIZER_AVAILABLE,
    request_body_byte_cap=OPENROUTER_SEALED_REQUEST_BODY_BYTES_V1,
    bound_request_body_sha256=_A_BODY_SHA,
)

#: A hypothetical established input bound, used only to exercise the guards
#: downstream of P17.  It is not a claim that P17 is established.
INPUT_BOUND_HYPOTHETICAL = OpenRouterInputBoundEvidenceV1(
    status=OpenRouterBoundStatusV1.ESTABLISHED,
    basis=OpenRouterInputBoundBasisV1.PINNED_OFFICIAL_TOKENIZER,
    max_input_tokens=512,
    request_body_byte_cap=OPENROUTER_SEALED_REQUEST_BODY_BYTES_V1,
    bound_request_body_sha256=_A_BODY_SHA,
    chat_framing_overhead_bounded=True,
)

OUTPUT_BOUND_ESTABLISHED = OpenRouterOutputBoundEvidenceV1(
    status=OpenRouterBoundStatusV1.ESTABLISHED,
    max_output_tokens=OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1,
    bound_request_body_sha256=_A_BODY_SHA,
)
OUTPUT_BOUND_MISSING = OpenRouterOutputBoundEvidenceV1(
    status=OpenRouterBoundStatusV1.NOT_ESTABLISHED,
    bound_request_body_sha256=_A_BODY_SHA,
)

PRICING_TRUSTED = OpenRouterTrustedPricingRecordV1(
    source=OpenRouterPricingSourceV1.FIRST_PARTY_MODEL_ENDPOINTS,
    source_evidence_sha256="a" * 64,
    preflight_execution_id=PREFLIGHT_EXECUTION_ID,
    model_id="openai/gpt-4.1-mini",
    endpoint_scope="azure/swedencentral",
    prompt_price_usd="0.0000004",
    completion_price_usd="0.0000016",
)
PRICING_UNTRUSTED_SOURCE = OpenRouterTrustedPricingRecordV1(
    source=OpenRouterPricingSourceV1.UNTRUSTED,
    source_evidence_sha256="a" * 64,
    preflight_execution_id=PREFLIGHT_EXECUTION_ID,
    model_id="openai/gpt-4.1-mini",
    prompt_price_usd="0.0000004",
    completion_price_usd="0.0000016",
)
PRICING_WRONG_MODEL = OpenRouterTrustedPricingRecordV1(
    source=OpenRouterPricingSourceV1.FIRST_PARTY_MODEL_ENDPOINTS,
    source_evidence_sha256="a" * 64,
    preflight_execution_id=PREFLIGHT_EXECUTION_ID,
    model_id="anthropic/claude-sonnet-4",
    prompt_price_usd="0.0000004",
    completion_price_usd="0.0000016",
)
PRICING_STALE = OpenRouterTrustedPricingRecordV1(
    source=OpenRouterPricingSourceV1.FIRST_PARTY_MODEL_ENDPOINTS,
    source_evidence_sha256="a" * 64,
    preflight_execution_id="szorpreflightexec_some_earlier_execution",
    model_id="openai/gpt-4.1-mini",
    prompt_price_usd="0.0000004",
    completion_price_usd="0.0000016",
)

CREDENTIAL_PRESENT = OpenRouterCredentialPresenceAttestationV1(
    credential_present=True, credential_variable_name="OPENROUTER_API_KEY"
)
CREDENTIAL_ABSENT = OpenRouterCredentialPresenceAttestationV1(
    credential_present=False, credential_variable_name="OPENROUTER_API_KEY"
)

#: Generous enough for the hypothetical bound.  The operator authorizes the real
#: value before S7; S6 does not pick a monetary figure.
CEILING_AUTHORIZED = OpenRouterOperatorCeilingV1(
    authorized=True, max_spend_picodollars=10**9
)
CEILING_TOO_LOW = OpenRouterOperatorCeilingV1(authorized=True, max_spend_picodollars=1)
CEILING_UNAUTHORIZED = OpenRouterOperatorCeilingV1(authorized=False)


class OpenRouterPreflightCaseV1(_FrozenCaseContractV1):
    """One frozen preflight case, evaluated entirely offline."""

    schema_version: Literal[
        OPENROUTER_PREFLIGHT_CASE_SCHEMA_V1
    ] = OPENROUTER_PREFLIGHT_CASE_SCHEMA_V1
    case_id: str
    description: str
    use_frozen_safety_contract: bool = True
    transport_ready: bool = True
    credential_present: bool = True
    request_intent_receipt_id_override: Optional[str] = None
    request_body_sha_override: Optional[str] = None
    input_bound_established: bool = True
    output_bound_established: bool = True
    pricing_variant: str = "TRUSTED"
    ceiling_variant: str = "AUTHORIZED"
    replay_consumed: bool = False
    expected_verdict: str
    expected_failure_code: Optional[OpenRouterPreflightFailureCodeV1] = None
    case_fingerprint: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterPreflightCaseV1":
        authorized = self.expected_verdict == "AUTHORIZED_FOR_ONE_CALL"
        if authorized != (self.expected_failure_code is None):
            raise ContractValidationError(
                "preflight expectation disagrees with its failure code"
            )
        expected = stable_contract_id(
            "szorpreflightcasev1",
            self.model_dump(mode="json", exclude={"case_fingerprint"}),
        )
        if self.case_fingerprint not in (None, expected):
            raise ContractValidationError("preflight case fingerprint mismatch")
        object.__setattr__(self, "case_fingerprint", expected)
        return self


_P = OpenRouterPreflightFailureCodeV1

FROZEN_OPENROUTER_PREFLIGHT_CASES_V1: Tuple[OpenRouterPreflightCaseV1, ...] = tuple(
    sorted(
        (
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-p01-all-preconditions-satisfied",
                description=(
                    "With every precondition hypothetically satisfied, exactly one "
                    "dispatch is authorized."
                ),
                expected_verdict="AUTHORIZED_FOR_ONE_CALL",
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x01-safety-contract-mismatch",
                description="A substituted structural safety contract is refused.",
                use_frozen_safety_contract=False,
                expected_verdict="REFUSED",
                expected_failure_code=_P.SAFETY_CONTRACT_MISMATCH,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x02-transport-not-ready",
                description="Transport is not ready for a bounded dispatch.",
                transport_ready=False,
                expected_verdict="REFUSED",
                expected_failure_code=_P.TRANSPORT_NOT_READY,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x03-credential-attestation-missing",
                description="No credential presence attestation, so no dispatch.",
                credential_present=False,
                expected_verdict="REFUSED",
                expected_failure_code=_P.CREDENTIAL_ATTESTATION_MISSING,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x04-request-intent-mismatch",
                description="The authorized request intent is not the one presented.",
                request_intent_receipt_id_override=(
                    "szorrouteintentreceiptv1_" + "0" * 64
                ),
                expected_verdict="REFUSED",
                expected_failure_code=_P.REQUEST_INTENT_MISMATCH,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x05-input-bound-evidence-wrong-request",
                description="Input bound evidence was computed for another request.",
                request_body_sha_override="9" * 64,
                expected_verdict="REFUSED",
                expected_failure_code=_P.REQUEST_INTENT_MISMATCH,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x06-input-bound-not-established",
                description=(
                    "The real current state: no pinned tokenizer, so no input bound."
                ),
                input_bound_established=False,
                expected_verdict="REFUSED",
                expected_failure_code=_P.INPUT_BOUND_NOT_ESTABLISHED,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x07-output-bound-not-established",
                description="Without an output cap the output cost is unbounded.",
                output_bound_established=False,
                expected_verdict="REFUSED",
                expected_failure_code=_P.OUTPUT_BOUND_NOT_ESTABLISHED,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x08-pricing-absent",
                description="No pricing record at all.",
                pricing_variant="ABSENT",
                expected_verdict="REFUSED",
                expected_failure_code=_P.PRICING_NOT_ESTABLISHED,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x09-pricing-source-untrusted",
                description="Only first-party pricing surfaces are acceptable.",
                pricing_variant="UNTRUSTED",
                expected_verdict="REFUSED",
                expected_failure_code=_P.PRICING_SOURCE_UNTRUSTED,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x10-pricing-model-mismatch",
                description="A price for a different model prices nothing here.",
                pricing_variant="WRONG_MODEL",
                expected_verdict="REFUSED",
                expected_failure_code=_P.PRICING_MODEL_MISMATCH,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x11-pricing-not-jit-fresh",
                description="A price from an earlier preflight execution is not fresh.",
                pricing_variant="STALE",
                expected_verdict="REFUSED",
                expected_failure_code=_P.PRICING_NOT_JIT_FRESH,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x12-operator-ceiling-unauthorized",
                description="No operator spend ceiling has been authorized.",
                ceiling_variant="UNAUTHORIZED",
                expected_verdict="REFUSED",
                expected_failure_code=_P.COST_EXCEEDS_OPERATOR_CEILING,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x13-cost-exceeds-operator-ceiling",
                description="Worst-case cost is above what the operator allowed.",
                ceiling_variant="TOO_LOW",
                expected_verdict="REFUSED",
                expected_failure_code=_P.COST_EXCEEDS_OPERATOR_CEILING,
            ),
            OpenRouterPreflightCaseV1(
                case_id="orpreflightv1-x14-authorization-already-consumed",
                description="A one-call authorization cannot be spent twice.",
                replay_consumed=True,
                expected_verdict="REFUSED",
                expected_failure_code=_P.AUTHORIZATION_ALREADY_CONSUMED,
            ),
        ),
        key=lambda case: case.case_id,
    )
)

OPENROUTER_PREFLIGHT_CASE_SET_ID_V1 = stable_contract_id(
    "szorpreflightcasesetv1",
    [case.case_fingerprint for case in FROZEN_OPENROUTER_PREFLIGHT_CASES_V1],
)


__all__ = [
    "CEILING_AUTHORIZED",
    "CEILING_TOO_LOW",
    "CEILING_UNAUTHORIZED",
    "CREDENTIAL_ABSENT",
    "CREDENTIAL_PRESENT",
    "FROZEN_OPENROUTER_PREFLIGHT_CASES_V1",
    "INPUT_BOUND_HYPOTHETICAL",
    "INPUT_BOUND_UNESTABLISHED",
    "OPENROUTER_PREFLIGHT_CASE_SCHEMA_V1",
    "OPENROUTER_PREFLIGHT_CASE_SET_ID_V1",
    "OUTPUT_BOUND_ESTABLISHED",
    "OUTPUT_BOUND_MISSING",
    "OpenRouterPreflightCaseV1",
    "PREFLIGHT_EXECUTION_ID",
    "PRICING_STALE",
    "PRICING_TRUSTED",
    "PRICING_UNTRUSTED_SOURCE",
    "PRICING_WRONG_MODEL",
    "FROZEN_OPENROUTER_INTEGRATION_CASES_V1",
    "FROZEN_OPENROUTER_INTEGRATION_CASE_SET_V1",
    "HEADERS_A",
    "HEADERS_B",
    "INTENT_A",
    "INTENT_B",
    "OPENROUTER_INTEGRATION_CASE_SCHEMA_V1",
    "OPENROUTER_INTEGRATION_CASE_SET_ID_V1",
    "OPENROUTER_INTEGRATION_CASE_SET_SCHEMA_V1",
    "OpenRouterIntegrationCaseKindV1",
    "OpenRouterIntegrationCaseSetV1",
    "OpenRouterIntegrationCaseV1",
    "OpenRouterIntegrationExpectedOutcomeV1",
    "RESPONSE_A",
    "RESPONSE_B",
]
