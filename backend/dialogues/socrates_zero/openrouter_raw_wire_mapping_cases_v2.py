"""Frozen offline case set for OpenRouter raw wire-mapping v2.

Every fixture body is constructed here from the documented schemas and examples
in the retained v2r1 official source snapshots.  Nothing is copied from the
historical Route Controls canned response, and no expectation is inherited from a
predecessor case set: expectations are evaluator-side and stated as the exact
normalized fields the official evidence authorizes.

Where a fixture needs filler payload content that no conclusion depends on - the
body of a chat completion, an opaque guardrail payload - the case is marked
``scaffolding`` so a reader can see that the science does not rest on that value.

The module is import-inert.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_raw_wire_mapping_v2 import OpenRouterWireFailureCodeV2

OPENROUTER_WIRE_CASE_SCHEMA_V2 = "socrateszero-openrouter-raw-wire-case/v2"
OPENROUTER_WIRE_CASE_SET_SCHEMA_V2 = "socrateszero-openrouter-raw-wire-case-set/v2"


class OpenRouterWireCaseKindV2(str, Enum):
    POSITIVE = "POSITIVE"
    ADVERSARIAL = "ADVERSARIAL"


class OpenRouterWireExpectedOutcomeV2(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class _FrozenCaseContractV2(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterWireCaseV2(_FrozenCaseContractV2):
    """One frozen wire case.

    ``expected_fields`` holds canonical-JSON encodings of the normalized values
    the case must produce, so an expectation cannot drift into a free-text
    assertion.  ``authorizing_evidence`` names the retained relationships and
    schemas that make the case legitimate.
    """

    schema_version: Literal[
        OPENROUTER_WIRE_CASE_SCHEMA_V2
    ] = OPENROUTER_WIRE_CASE_SCHEMA_V2
    case_id: str
    kind: OpenRouterWireCaseKindV2
    description: str
    raw_body: bytes
    headers: Tuple[Tuple[str, str], ...] = ()
    expected_outcome: OpenRouterWireExpectedOutcomeV2
    expected_failure_code: Optional[OpenRouterWireFailureCodeV2] = None
    expected_fields: Tuple[Tuple[str, str], ...] = ()
    authorizing_evidence: Tuple[str, ...] = ()
    scaffolding: bool = False
    case_fingerprint: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterWireCaseV2":
        accepted = self.expected_outcome is OpenRouterWireExpectedOutcomeV2.ACCEPTED
        if accepted and self.expected_failure_code is not None:
            raise ContractValidationError(
                "an accepted case must not predeclare a failure code"
            )
        if not accepted and self.expected_failure_code is None:
            raise ContractValidationError(
                "a rejected case must predeclare its first failing guard"
            )
        if not accepted and self.expected_fields:
            raise ContractValidationError(
                "a rejected case produces no normalized fields to expect"
            )
        if not self.authorizing_evidence:
            raise ContractValidationError(
                "every case must name the evidence that authorizes it"
            )
        expected = stable_contract_id(
            "szorwirecasev2",
            {
                "schema_version": self.schema_version,
                "case_id": self.case_id,
                "kind": self.kind.value,
                "raw_body_hex": self.raw_body.hex(),
                "headers": [list(pair) for pair in self.headers],
                "expected_outcome": self.expected_outcome.value,
                "expected_failure_code": (
                    self.expected_failure_code.value
                    if self.expected_failure_code
                    else None
                ),
                "expected_fields": [list(pair) for pair in self.expected_fields],
            },
        )
        if self.case_fingerprint not in (None, expected):
            raise ContractValidationError("wire case fingerprint mismatch")
        object.__setattr__(self, "case_fingerprint", expected)
        return self


class OpenRouterWireCaseSetV2(_FrozenCaseContractV2):
    schema_version: Literal[
        OPENROUTER_WIRE_CASE_SET_SCHEMA_V2
    ] = OPENROUTER_WIRE_CASE_SET_SCHEMA_V2
    cases: Tuple[OpenRouterWireCaseV2, ...]
    case_set_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterWireCaseSetV2":
        ids = [case.case_id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ContractValidationError("wire case IDs must be unique")
        if ids != sorted(ids):
            raise ContractValidationError("wire cases must be in stable ID order")
        expected = stable_contract_id(
            "szorwirecasesetv2",
            [case.case_fingerprint for case in self.cases],
        )
        if self.case_set_id not in (None, expected):
            raise ContractValidationError("wire case-set ID mismatch")
        object.__setattr__(self, "case_set_id", expected)
        return self


# ------------------------------------------------------------ body builders --

#: Filler completion payload.  Scaffolding: no conclusion depends on its content.
_SCAFFOLD_CHOICES = [
    {
        "index": 0,
        "message": {"role": "assistant", "content": "scaffolding"},
        "finish_reason": "stop",
    }
]

_EV_SUCCESS = "relationship:SUCCESS_ENVELOPE_PLACEMENT"
_EV_ERROR = "relationship:ERROR_ENVELOPE_PLACEMENT"
_EV_CACHE_ABSENCE = "relationship:CACHE_METADATA_ABSENCE"
_EV_CACHE_ATTEST = "relationship:CACHE_ATTESTATION"
_EV_ATTEMPT = "relationship:ATTEMPT_SEMANTICS"
_EV_ATTEMPTS = "relationship:ATTEMPTS_LIST_SEMANTICS"
_EV_ENDPOINTS = "relationship:ENDPOINT_COLLECTION"
_EV_PROVIDER = "relationship:PROVIDER_GRANULARITY"
_EV_SERVED = "relationship:SERVED_MODEL_PRECEDENCE"
_EV_ACTUAL = "relationship:ACTUAL_SERVED_MODEL_IDENTITY"
_EV_STRATEGY = "relationship:STRATEGY_SEMANTICS"
_EV_PIPELINE = "relationship:PIPELINE_SEMANTICS"
_EV_ADDITIVE = "relationship:UNKNOWN_ADDITIVE_FIELD_POLICY"
_EV_EXACT = "relationship:EXACT_ENDPOINT_RESPONSE_IDENTITY"
_EV_OPENAPI = "source:openapi.yaml#components.schemas.OpenRouterMetadata"
_EV_STRATEGY_ENUM = "source:openapi.yaml#components.schemas.RoutingStrategy"
_EV_STAGE_ENUM = "source:openapi.yaml#components.schemas.PipelineStageType"
_EV_ERROR_SCHEMA = "source:openapi.yaml#error-schemas.openrouter_metadata"
_EV_CACHE_DOC = "source:response-caching.mdx#response-headers"
_EV_META_DOC = "source:router-metadata.mdx"


def _metadata(**overrides: Any) -> Dict[str, Any]:
    """A documented, complete success-shaped metadata object."""
    base: Dict[str, Any] = {
        "requested": "openai/gpt-4.1-mini",
        "strategy": "direct",
        "region": "iad",
        "summary": "available=1, selected=Azure",
        "attempt": 1,
        "is_byok": False,
        "endpoints": {
            "total": 1,
            "available": [
                {
                    "provider": "Azure",
                    "model": "openai/gpt-4.1-mini",
                    "selected": True,
                }
            ],
        },
    }
    base.update(overrides)
    return base


def _success_body(metadata: Optional[Dict[str, Any]] = None, **extra: Any) -> bytes:
    body: Dict[str, Any] = {
        "id": "gen-scaffold",
        "model": "openai/gpt-4.1-mini",
        "object": "chat.completion",
        "choices": _SCAFFOLD_CHOICES,
    }
    if metadata is not None:
        body["openrouter_metadata"] = metadata
    body.update(extra)
    return json.dumps(body).encode("utf-8")


def _error_body(metadata: Optional[Dict[str, Any]] = None, code: int = 404) -> bytes:
    body: Dict[str, Any] = {
        "error": {"code": code, "message": "scaffolding error message"},
    }
    if metadata is not None:
        body["openrouter_metadata"] = metadata
    return json.dumps(body).encode("utf-8")


def _expect(**fields: Any) -> Tuple[Tuple[str, str], ...]:
    return tuple(
        (name, canonical_json(value)) for name, value in sorted(fields.items())
    )


_HIT_HEADERS = (
    ("X-OpenRouter-Cache-Status", "HIT"),
    ("X-OpenRouter-Cache-Age", "12"),
    ("X-OpenRouter-Cache-TTL", "288"),
    ("X-OpenRouter-Cache-Source-Id", "gen-abc123"),
    ("X-Generation-Id", "gen-def456"),
)
_MISS_HEADERS = (
    ("X-OpenRouter-Cache-Status", "MISS"),
    ("X-OpenRouter-Cache-TTL", "300"),
    ("X-Generation-Id", "gen-abc123"),
)

_POSITIVE: Tuple[OpenRouterWireCaseV2, ...] = (
    OpenRouterWireCaseV2(
        case_id="orwirev2-p01-success-with-metadata",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description="Opt-in success carries router metadata at the top level.",
        raw_body=_success_body(_metadata()),
        headers=(("X-Generation-Id", "gen-abc123"),),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            envelope_kind="SUCCESS",
            actual_served_model="openai/gpt-4.1-mini",
            actual_served_model_status="ESTABLISHED",
            router_metadata_presence="PRESENT",
            routing_strategy="direct",
            attempt=1,
            exact_endpoint_response_identity=None,
        ),
        authorizing_evidence=(_EV_SUCCESS, _EV_OPENAPI, _EV_SERVED),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p02-error-with-partial-metadata",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "Documented 404 example: metadata is a sibling of error and omits "
            "region/summary/is_byok, which the loose error-schema binding allows."
        ),
        raw_body=_error_body(
            {
                "requested": "openai/gpt-4o-mini",
                "strategy": "direct",
                "attempt": 0,
                "endpoints": {
                    "total": 1,
                    "available": [
                        {
                            "provider": "OpenAI",
                            "model": "openai/gpt-4o-mini",
                            "selected": False,
                        }
                    ],
                },
            }
        ),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            envelope_kind="ERROR",
            actual_served_model=None,
            actual_served_model_status="ABSENT_FROM_OBSERVATION",
            router_metadata_presence="PRESENT",
            attempt=0,
            region_presence="ABSENT",
        ),
        authorizing_evidence=(_EV_ERROR, _EV_ERROR_SCHEMA, _EV_ATTEMPT, _EV_META_DOC),
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p03-error-without-metadata",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description="Documented 500 class: metadata omitted by design.",
        raw_body=_error_body(code=500),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            envelope_kind="ERROR",
            router_metadata_presence="ABSENT",
            cache_status_presence="ABSENT",
        ),
        authorizing_evidence=(_EV_ERROR, _EV_META_DOC),
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p04-cache-hit-header-authority",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "Cache HIT: authority is the header; metadata is absent as documented."
        ),
        raw_body=_success_body(),
        headers=_HIT_HEADERS,
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            envelope_kind="SUCCESS",
            cache_status="HIT",
            cache_status_presence="PRESENT",
            cache_age_seconds=12,
            cache_source_generation_id="gen-abc123",
            generation_id="gen-def456",
            router_metadata_presence="ABSENT",
        ),
        authorizing_evidence=(_EV_CACHE_ATTEST, _EV_CACHE_ABSENCE, _EV_CACHE_DOC),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p05-cache-miss-with-metadata",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description="Cache MISS carries full TTL and may carry metadata.",
        raw_body=_success_body(_metadata()),
        headers=_MISS_HEADERS,
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            cache_status="MISS",
            cache_ttl_seconds=300,
            cache_age_seconds=None,
            router_metadata_presence="PRESENT",
        ),
        authorizing_evidence=(_EV_CACHE_ATTEST, _EV_CACHE_DOC),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p06-requested-distinct-from-actual",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "Model fallback: requested and actual served model differ and are "
            "mapped to separate authorities."
        ),
        raw_body=_success_body(
            _metadata(requested="openai/gpt-4o", strategy="fallback"),
            model="anthropic/claude-sonnet-4",
        ),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            actual_served_model="anthropic/claude-sonnet-4",
            requested_model="openai/gpt-4o",
            routing_strategy="fallback",
        ),
        authorizing_evidence=(_EV_ACTUAL, _EV_SERVED, _EV_STRATEGY),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p07-attempts-absent",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description="attempts is optional; absence is preserved, not synthesized.",
        raw_body=_success_body(_metadata()),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(attempts_presence="ABSENT", attempts=[]),
        authorizing_evidence=(_EV_ATTEMPTS, _EV_OPENAPI),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p08-attempts-present-empty",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description="An empty attempts array is distinct from an absent one.",
        raw_body=_success_body(_metadata(attempts=[])),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(attempts_presence="PRESENT_EMPTY", attempts=[]),
        authorizing_evidence=(_EV_ATTEMPTS, _EV_OPENAPI),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p09-attempts-present-with-entries",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "Typed attempt records at documented granularity. Multiple attempts "
            "are attempts, never evidence of a fallback policy."
        ),
        raw_body=_success_body(
            _metadata(
                attempt=2,
                attempts=[
                    {
                        "provider": "OpenAI",
                        "model": "openai/gpt-4.1-mini",
                        "status": 503,
                    },
                    {"provider": "Azure", "model": "openai/gpt-4.1-mini", "status": 200},
                ],
            )
        ),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            attempts_presence="PRESENT_WITH_ENTRIES",
            attempt=2,
            attempts=[
                {
                    "provider_display_name": "OpenAI",
                    "model": "openai/gpt-4.1-mini",
                    "status": 503,
                },
                {
                    "provider_display_name": "Azure",
                    "model": "openai/gpt-4.1-mini",
                    "status": 200,
                },
            ],
        ),
        authorizing_evidence=(_EV_ATTEMPTS, _EV_PROVIDER, _EV_ATTEMPT),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p10-pipeline-absent",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description="pipeline is optional.",
        raw_body=_success_body(_metadata()),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(pipeline_presence="ABSENT", pipeline=[]),
        authorizing_evidence=(_EV_PIPELINE, _EV_OPENAPI),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p11-pipeline-typed-stage-with-opaque-data",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "Documented guardrail stage. Free-form data is reduced to a digest "
            "and grants no authority."
        ),
        raw_body=_error_body(
            _metadata(
                pipeline=[
                    {
                        "type": "guardrail",
                        "name": "regex_pi_detection",
                        "data": {"action": "blocked", "detected": True},
                    }
                ]
            ),
            code=403,
        ),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            pipeline_presence="PRESENT_WITH_ENTRIES",
            envelope_kind="ERROR",
        ),
        authorizing_evidence=(_EV_PIPELINE, _EV_STAGE_ENUM, _EV_META_DOC),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p12-pipeline-unknown-stage-type-is-opaque",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "The stage-type list grows over time; an unknown type is opaque and "
            "accepted, never a rejection and never authoritative."
        ),
        raw_body=_success_body(
            _metadata(
                pipeline=[{"type": "future_stage_type", "name": "not-yet-documented"}]
            )
        ),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            pipeline_presence="PRESENT_WITH_ENTRIES",
            pipeline=[
                {
                    "stage_type": "future_stage_type",
                    "stage_type_is_documented": False,
                    "name": "not-yet-documented",
                    "data_presence": "ABSENT",
                    "data_sha256": None,
                }
            ],
        ),
        authorizing_evidence=(_EV_ADDITIVE, _EV_PIPELINE, _EV_META_DOC),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p13-unknown-additive-metadata-field",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "A new optional metadata field is preserved non-authoritatively."
        ),
        raw_body=_success_body(_metadata(future_field={"anything": 1})),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            actual_served_model="openai/gpt-4.1-mini",
            routing_strategy="direct",
        ),
        authorizing_evidence=(_EV_ADDITIVE, _EV_META_DOC),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p14-endpoint-candidates-selected-flags",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "Endpoint candidates carry display-name providers and selected flags; "
            "no total==len(available) invariant is asserted."
        ),
        raw_body=_success_body(
            _metadata(
                endpoints={
                    "total": 3,
                    "available": [
                        {
                            "provider": "Azure",
                            "model": "openai/gpt-4.1-mini",
                            "selected": True,
                        },
                        {
                            "provider": "OpenAI",
                            "model": "openai/gpt-4.1-mini",
                            "selected": False,
                        },
                    ],
                }
            )
        ),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            endpoint_collection={
                "total": 3,
                "available": [
                    {
                        "provider_display_name": "Azure",
                        "model": "openai/gpt-4.1-mini",
                        "selected": True,
                    },
                    {
                        "provider_display_name": "OpenAI",
                        "model": "openai/gpt-4.1-mini",
                        "selected": False,
                    },
                ],
            },
            exact_endpoint_response_identity=None,
            exact_endpoint_response_identity_status=(
                "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"
            ),
        ),
        authorizing_evidence=(_EV_ENDPOINTS, _EV_PROVIDER, _EV_EXACT),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p15-region-null-is-distinct-from-absent",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description="region is documented as string|null.",
        raw_body=_success_body(_metadata(region=None)),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(region_presence="NULL", region=None),
        authorizing_evidence=(_EV_OPENAPI,),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p16-params-present",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description="params is an optional loose object, digested not trusted.",
        raw_body=_success_body(
            _metadata(params={"version_group": "anthropic/claude-sonnet-4"})
        ),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(params_presence="PRESENT_WITH_ENTRIES"),
        authorizing_evidence=(_EV_OPENAPI,),
        scaffolding=True,
    ),
    OpenRouterWireCaseV2(
        case_id="orwirev2-p17-injected-endpoint-slug-gains-no-authority",
        kind=OpenRouterWireCaseKindV2.POSITIVE,
        description=(
            "An unknown field that looks exactly like an endpoint slug is "
            "accepted as opaque evidence and changes no authority."
        ),
        raw_body=_success_body(
            _metadata(endpoint_slug="azure/swedencentral", endpoint_id="ep_12345")
        ),
        expected_outcome=OpenRouterWireExpectedOutcomeV2.ACCEPTED,
        expected_fields=_expect(
            exact_endpoint_response_identity=None,
            exact_endpoint_response_identity_status=(
                "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"
            ),
            actual_served_model="openai/gpt-4.1-mini",
        ),
        authorizing_evidence=(_EV_EXACT, _EV_ADDITIVE),
        scaffolding=True,
    ),
)


def _adv(
    case_id: str,
    description: str,
    raw_body: bytes,
    code: OpenRouterWireFailureCodeV2,
    evidence: Tuple[str, ...],
    headers: Tuple[Tuple[str, str], ...] = (),
) -> OpenRouterWireCaseV2:
    return OpenRouterWireCaseV2(
        case_id=case_id,
        kind=OpenRouterWireCaseKindV2.ADVERSARIAL,
        description=description,
        raw_body=raw_body,
        headers=headers,
        expected_outcome=OpenRouterWireExpectedOutcomeV2.REJECTED,
        expected_failure_code=code,
        authorizing_evidence=evidence,
    )


_F = OpenRouterWireFailureCodeV2

_ADVERSARIAL: Tuple[OpenRouterWireCaseV2, ...] = (
    _adv(
        "orwirev2-x01-invalid-utf8",
        "Body is not valid UTF-8.",
        b'{"model": "\xff\xfe"}',
        _F.BODY_NOT_UTF8,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x02-malformed-json",
        "Body is not valid JSON.",
        b'{"model": "openai/gpt-4.1-mini",}',
        _F.BODY_NOT_JSON,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x03-duplicate-json-key",
        "Duplicate top-level object key is ambiguous and refused.",
        b'{"model": "a", "model": "b"}',
        _F.BODY_DUPLICATE_KEY,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x04-nan-literal",
        "NaN is not valid JSON and is refused.",
        b'{"model": "a", "x": NaN}',
        _F.BODY_NON_FINITE_NUMBER,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x05-infinity-literal",
        "Infinity is not valid JSON and is refused.",
        b'{"model": "a", "x": Infinity}',
        _F.BODY_NON_FINITE_NUMBER,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x06-negative-infinity-literal",
        "-Infinity is not valid JSON and is refused.",
        b'{"model": "a", "x": -Infinity}',
        _F.BODY_NON_FINITE_NUMBER,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x07-overflow-float-becomes-infinite",
        "A finite-looking literal that overflows to infinity is refused.",
        b'{"model": "a", "x": 1e999}',
        _F.BODY_NON_FINITE_NUMBER,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x08-top-level-not-object",
        "Top-level JSON array cannot be a documented envelope.",
        b'["model"]',
        _F.BODY_NOT_OBJECT,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x09-envelope-ambiguous",
        "Both a top-level error and a top-level model.",
        json.dumps({"model": "a", "error": {"code": 400}}).encode("utf-8"),
        _F.ENVELOPE_AMBIGUOUS,
        (_EV_SUCCESS, _EV_ERROR),
    ),
    _adv(
        "orwirev2-x10-envelope-unclassifiable",
        "Neither a top-level error nor a top-level model.",
        json.dumps({"object": "chat.completion"}).encode("utf-8"),
        _F.ENVELOPE_UNCLASSIFIABLE,
        (_EV_SUCCESS, _EV_ERROR),
    ),
    _adv(
        "orwirev2-x11-error-not-object",
        "Top-level error must be an object.",
        json.dumps({"error": "boom"}).encode("utf-8"),
        _F.ERROR_OBJECT_TYPE,
        (_EV_ERROR_SCHEMA,),
    ),
    _adv(
        "orwirev2-x12-success-model-wrong-type",
        "Top-level model must be a string.",
        json.dumps({"model": 7, "choices": []}).encode("utf-8"),
        _F.SUCCESS_MODEL_TYPE,
        (_EV_ACTUAL,),
    ),
    _adv(
        "orwirev2-x13-metadata-wrong-type",
        "openrouter_metadata must be an object or null.",
        _success_body(None, openrouter_metadata=["nope"]),
        _F.METADATA_TYPE,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x14-metadata-required-field-absent-on-success",
        "Success metadata binds the strict schema: is_byok is required.",
        _success_body({k: v for k, v in _metadata().items() if k != "is_byok"}),
        _F.METADATA_REQUIRED_FIELD_ABSENT,
        (_EV_OPENAPI, _EV_SUCCESS),
    ),
    _adv(
        "orwirev2-x15-requested-wrong-type",
        "requested must be a string.",
        _success_body(_metadata(requested=42)),
        _F.METADATA_FIELD_TYPE,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x16-strategy-wrong-type",
        "strategy must be a string.",
        _success_body(_metadata(strategy=1)),
        _F.METADATA_FIELD_TYPE,
        (_EV_STRATEGY_ENUM,),
    ),
    _adv(
        "orwirev2-x17-strategy-not-in-closed-enum",
        "RoutingStrategy is a closed enum; an undocumented value fails closed.",
        _success_body(_metadata(strategy="teleport")),
        _F.STRATEGY_NOT_DOCUMENTED,
        (_EV_STRATEGY_ENUM, _EV_STRATEGY),
    ),
    _adv(
        "orwirev2-x18-region-wrong-type",
        "region must be a string or null.",
        _success_body(_metadata(region=5)),
        _F.METADATA_FIELD_TYPE,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x19-attempt-wrong-type",
        "attempt must be an integer.",
        _success_body(_metadata(attempt="1")),
        _F.METADATA_FIELD_TYPE,
        (_EV_ATTEMPT,),
    ),
    _adv(
        "orwirev2-x20-attempt-boolean-is-not-integer",
        "A JSON boolean is never an acceptable integer.",
        _success_body(_metadata(attempt=True)),
        _F.METADATA_FIELD_TYPE,
        (_EV_ATTEMPT,),
    ),
    _adv(
        "orwirev2-x21-success-attempt-zero",
        "Success attempt is one-indexed; zero contradicts the documentation.",
        _success_body(_metadata(attempt=0)),
        _F.ATTEMPT_RANGE,
        (_EV_ATTEMPT,),
    ),
    _adv(
        "orwirev2-x22-error-attempt-negative",
        "A negative attempt is documented nowhere.",
        _error_body(_metadata(attempt=-1)),
        _F.ATTEMPT_RANGE,
        (_EV_ATTEMPT,),
    ),
    _adv(
        "orwirev2-x23-is-byok-wrong-type",
        "is_byok must be a boolean.",
        _success_body(_metadata(is_byok="false")),
        _F.METADATA_FIELD_TYPE,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x24-endpoints-wrong-type",
        "endpoints must be an object.",
        _success_body(_metadata(endpoints=[])),
        _F.ENDPOINTS_TYPE,
        (_EV_ENDPOINTS,),
    ),
    _adv(
        "orwirev2-x25-endpoints-total-wrong-type",
        "endpoints.total must be an integer.",
        _success_body(_metadata(endpoints={"total": "1", "available": []})),
        _F.ENDPOINTS_FIELD,
        (_EV_ENDPOINTS,),
    ),
    _adv(
        "orwirev2-x26-endpoint-entry-wrong-type",
        "endpoints.available entries must be objects.",
        _success_body(_metadata(endpoints={"total": 1, "available": ["Azure"]})),
        _F.ENDPOINT_ENTRY_TYPE,
        (_EV_ENDPOINTS,),
    ),
    _adv(
        "orwirev2-x27-endpoint-provider-wrong-type",
        "endpoint provider must be a string.",
        _success_body(
            _metadata(
                endpoints={
                    "total": 1,
                    "available": [{"provider": 1, "model": "m", "selected": True}],
                }
            )
        ),
        _F.ENDPOINT_ENTRY_FIELD,
        (_EV_ENDPOINTS, _EV_PROVIDER),
    ),
    _adv(
        "orwirev2-x28-endpoint-selected-wrong-type",
        "endpoint selected must be a boolean.",
        _success_body(
            _metadata(
                endpoints={
                    "total": 1,
                    "available": [
                        {"provider": "Azure", "model": "m", "selected": "yes"}
                    ],
                }
            )
        ),
        _F.ENDPOINT_ENTRY_FIELD,
        (_EV_ENDPOINTS,),
    ),
    _adv(
        "orwirev2-x29-attempts-wrong-type",
        "attempts must be an array.",
        _success_body(_metadata(attempts={"provider": "Azure"})),
        _F.ATTEMPTS_TYPE,
        (_EV_ATTEMPTS,),
    ),
    _adv(
        "orwirev2-x30-attempts-entry-wrong-type",
        "attempts entries must be objects.",
        _success_body(_metadata(attempts=["Azure"])),
        _F.ATTEMPTS_ENTRY_TYPE,
        (_EV_ATTEMPTS,),
    ),
    _adv(
        "orwirev2-x31-attempts-entry-missing-field",
        "attempts entries require provider, model and status.",
        _success_body(_metadata(attempts=[{"provider": "Azure", "model": "m"}])),
        _F.ATTEMPTS_ENTRY_FIELD,
        (_EV_ATTEMPTS,),
    ),
    _adv(
        "orwirev2-x32-attempts-status-wrong-type",
        "attempt status must be an integer.",
        _success_body(
            _metadata(attempts=[{"provider": "Azure", "model": "m", "status": "200"}])
        ),
        _F.ATTEMPTS_ENTRY_FIELD,
        (_EV_ATTEMPTS,),
    ),
    _adv(
        "orwirev2-x33-params-wrong-type",
        "params must be an object.",
        _success_body(_metadata(params=["quality_floor"])),
        _F.PARAMS_TYPE,
        (_EV_OPENAPI,),
    ),
    _adv(
        "orwirev2-x34-pipeline-wrong-type",
        "pipeline must be an array.",
        _success_body(_metadata(pipeline={"type": "guardrail"})),
        _F.PIPELINE_TYPE,
        (_EV_PIPELINE,),
    ),
    _adv(
        "orwirev2-x35-pipeline-stage-wrong-type",
        "pipeline stages must be objects.",
        _success_body(_metadata(pipeline=["guardrail"])),
        _F.PIPELINE_STAGE_TYPE,
        (_EV_PIPELINE,),
    ),
    _adv(
        "orwirev2-x36-pipeline-stage-missing-name",
        "pipeline stages require type and name.",
        _success_body(_metadata(pipeline=[{"type": "guardrail"}])),
        _F.PIPELINE_STAGE_FIELD,
        (_EV_PIPELINE,),
    ),
    _adv(
        "orwirev2-x37-pipeline-stage-data-wrong-type",
        "pipeline stage data must be an object when present.",
        _success_body(
            _metadata(pipeline=[{"type": "guardrail", "name": "g", "data": "opaque"}])
        ),
        _F.PIPELINE_STAGE_FIELD,
        (_EV_PIPELINE,),
    ),
    _adv(
        "orwirev2-x38-cache-status-invalid-value",
        "Cache status is documented as HIT or MISS only.",
        _success_body(),
        _F.HEADER_CACHE_STATUS_INVALID,
        (_EV_CACHE_DOC, _EV_CACHE_ATTEST),
        headers=(("X-OpenRouter-Cache-Status", "STALE"),),
    ),
    _adv(
        "orwirev2-x39-cache-status-conflicting-duplicates",
        "Conflicting duplicate authority headers are refused, not resolved.",
        _success_body(),
        _F.HEADER_CONFLICTING_DUPLICATE,
        (_EV_CACHE_ATTEST,),
        headers=(
            ("X-OpenRouter-Cache-Status", "HIT"),
            ("x-openrouter-cache-status", "MISS"),
        ),
    ),
    _adv(
        "orwirev2-x40-cache-age-not-integer",
        "Cache age must parse as a non-negative integer.",
        _success_body(),
        _F.HEADER_CACHE_INTEGER_INVALID,
        (_EV_CACHE_DOC,),
        headers=(
            ("X-OpenRouter-Cache-Status", "HIT"),
            ("X-OpenRouter-Cache-Age", "twelve"),
        ),
    ),
    _adv(
        "orwirev2-x41-cache-hit-with-metadata-present",
        "Cache hits never include openrouter_metadata.",
        _success_body(_metadata()),
        _F.CACHE_HIT_CONTRADICTS_METADATA,
        (_EV_CACHE_ABSENCE, _EV_CACHE_ATTEST),
        headers=(("X-OpenRouter-Cache-Status", "HIT"),),
    ),
    _adv(
        "orwirev2-x42-cache-hit-on-error-envelope",
        "Only successful responses are cached.",
        _error_body(),
        _F.CACHE_HIT_CONTRADICTS_ERROR_ENVELOPE,
        (_EV_CACHE_DOC, _EV_ERROR),
        headers=(("X-OpenRouter-Cache-Status", "HIT"),),
    ),
    _adv(
        "orwirev2-x43-hit-only-header-on-miss",
        "Cache-Source-Id is documented on HIT only.",
        _success_body(),
        _F.CACHE_HIT_ONLY_HEADER_ON_MISS,
        (_EV_CACHE_DOC,),
        headers=(
            ("X-OpenRouter-Cache-Status", "MISS"),
            ("X-OpenRouter-Cache-Source-Id", "gen-abc123"),
        ),
    ),
)

FROZEN_OPENROUTER_WIRE_CASES_V2: Tuple[OpenRouterWireCaseV2, ...] = tuple(
    sorted(_POSITIVE + _ADVERSARIAL, key=lambda case: case.case_id)
)
FROZEN_OPENROUTER_WIRE_CASE_SET_V2 = OpenRouterWireCaseSetV2(
    cases=FROZEN_OPENROUTER_WIRE_CASES_V2
)
OPENROUTER_WIRE_CASE_SET_ID_V2 = FROZEN_OPENROUTER_WIRE_CASE_SET_V2.case_set_id


__all__ = [
    "FROZEN_OPENROUTER_WIRE_CASES_V2",
    "FROZEN_OPENROUTER_WIRE_CASE_SET_V2",
    "OPENROUTER_WIRE_CASE_SCHEMA_V2",
    "OPENROUTER_WIRE_CASE_SET_ID_V2",
    "OPENROUTER_WIRE_CASE_SET_SCHEMA_V2",
    "OpenRouterWireCaseKindV2",
    "OpenRouterWireCaseSetV2",
    "OpenRouterWireCaseV2",
    "OpenRouterWireExpectedOutcomeV2",
]
