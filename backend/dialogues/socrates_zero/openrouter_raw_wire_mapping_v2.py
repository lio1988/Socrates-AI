"""Deterministic offline OpenRouter raw response wire mapper v2.

Raw bytes in, typed normalized mapping out, fail-closed in between.

Every authority granted below is bound to the retained Wire Specification
Manifest v2r1 and its pinned official sources.  Nothing here rests on a
repository convention, a historical canned response shape, a previous parser
assumption, or model memory.  Where the official contract does not supply an
authority, this module emits an explicit epistemic state and no value.

Two rules deserve naming because they are the ones most easily lost:

* The exact endpoint that served a response is **not** available from the
  documented response contract.  It is emitted as
  ``UNAVAILABLE_BY_DOCUMENTED_CONTRACT`` with a ``None`` value and is never
  synthesized from the provider display label, the request-side selector, a
  selected endpoint candidate, the region, or anything else.
* Cache authority is header-borne.  The absence of router metadata is documented
  to accompany a cache hit, but absence alone never proves one.

The module is import-inert: importing it performs no filesystem write, network
access, credential lookup, environment inspection, provider call, model
execution, tool call, or CED application.

This is offline scientific machinery.  It holds no runtime authority, is not
wired into the production adapter, and does not authorize a live call.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Any, Dict, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id

# --------------------------------------------------------------- provenance --

OPENROUTER_WIRE_MAPPING_SCHEMA_V2 = "socrateszero-openrouter-raw-wire-mapping/v2"
OPENROUTER_WIRE_OBSERVATION_SCHEMA_V2 = (
    "socrateszero-openrouter-raw-wire-observation/v2"
)

#: Wire Specification Manifest v2r1 — the sole evidence boundary for this module.
OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2 = (
    "szorwirespecmanifestv2r1_"
    "a0695823f0e2968ef44706940a243fb7df934a69f986dd841f1abeee4e858d15"
)
OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2 = (
    "3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb"
)
OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_RELATIVE_PATH_V2 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1"
    "/evidence/openrouter_official_wire_specification_manifest_v2r1.json"
)
OPENROUTER_WIRE_MAPPING_OFFICIAL_REPOSITORY_V2 = "OpenRouterTeam/docs"
OPENROUTER_WIRE_MAPPING_OFFICIAL_COMMIT_V2 = (
    "4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db"
)

# ------------------------------------------------------------------- states --


class OpenRouterWireEnvelopeKindV2(str, Enum):
    """Which documented envelope the body is.

    Discriminated by the retained schemas: every documented error response
    requires a top-level ``error`` object; the normalized success response
    requires a top-level ``model``.  No ``choices``-presence heuristic is used.
    """

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class OpenRouterWirePresenceV2(str, Enum):
    """Presence distinctions the official contract makes meaningful."""

    ABSENT = "ABSENT"
    NULL = "NULL"
    PRESENT = "PRESENT"
    PRESENT_EMPTY = "PRESENT_EMPTY"
    PRESENT_WITH_ENTRIES = "PRESENT_WITH_ENTRIES"


class OpenRouterWireCacheStatusV2(str, Enum):
    """Documented values of ``X-OpenRouter-Cache-Status``."""

    HIT = "HIT"
    MISS = "MISS"


class OpenRouterWireEpistemicStatusV2(str, Enum):
    """Why an authority is absent from the mapping."""

    ESTABLISHED = "ESTABLISHED"
    ABSENT_FROM_OBSERVATION = "ABSENT_FROM_OBSERVATION"
    UNAVAILABLE_BY_DOCUMENTED_CONTRACT = "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"


class OpenRouterWireFailureCodeV2(str, Enum):
    """Every way the mapper refuses a wire observation."""

    OBSERVATION_DIGEST_MISMATCH = "OBSERVATION_DIGEST_MISMATCH"
    BODY_NOT_UTF8 = "BODY_NOT_UTF8"
    BODY_NOT_JSON = "BODY_NOT_JSON"
    BODY_DUPLICATE_KEY = "BODY_DUPLICATE_KEY"
    BODY_NON_FINITE_NUMBER = "BODY_NON_FINITE_NUMBER"
    BODY_NOT_OBJECT = "BODY_NOT_OBJECT"
    ENVELOPE_AMBIGUOUS = "ENVELOPE_AMBIGUOUS"
    ENVELOPE_UNCLASSIFIABLE = "ENVELOPE_UNCLASSIFIABLE"
    ERROR_OBJECT_TYPE = "ERROR_OBJECT_TYPE"
    SUCCESS_MODEL_TYPE = "SUCCESS_MODEL_TYPE"
    METADATA_TYPE = "METADATA_TYPE"
    METADATA_REQUIRED_FIELD_ABSENT = "METADATA_REQUIRED_FIELD_ABSENT"
    METADATA_FIELD_TYPE = "METADATA_FIELD_TYPE"
    STRATEGY_NOT_DOCUMENTED = "STRATEGY_NOT_DOCUMENTED"
    ATTEMPT_RANGE = "ATTEMPT_RANGE"
    ATTEMPTS_TYPE = "ATTEMPTS_TYPE"
    ATTEMPTS_ENTRY_TYPE = "ATTEMPTS_ENTRY_TYPE"
    ATTEMPTS_ENTRY_FIELD = "ATTEMPTS_ENTRY_FIELD"
    ENDPOINTS_TYPE = "ENDPOINTS_TYPE"
    ENDPOINTS_FIELD = "ENDPOINTS_FIELD"
    ENDPOINT_ENTRY_TYPE = "ENDPOINT_ENTRY_TYPE"
    ENDPOINT_ENTRY_FIELD = "ENDPOINT_ENTRY_FIELD"
    PARAMS_TYPE = "PARAMS_TYPE"
    PIPELINE_TYPE = "PIPELINE_TYPE"
    PIPELINE_STAGE_TYPE = "PIPELINE_STAGE_TYPE"
    PIPELINE_STAGE_FIELD = "PIPELINE_STAGE_FIELD"
    HEADER_CONFLICTING_DUPLICATE = "HEADER_CONFLICTING_DUPLICATE"
    HEADER_CACHE_STATUS_INVALID = "HEADER_CACHE_STATUS_INVALID"
    HEADER_CACHE_INTEGER_INVALID = "HEADER_CACHE_INTEGER_INVALID"
    CACHE_HIT_CONTRADICTS_METADATA = "CACHE_HIT_CONTRADICTS_METADATA"
    CACHE_HIT_CONTRADICTS_ERROR_ENVELOPE = "CACHE_HIT_CONTRADICTS_ERROR_ENVELOPE"
    CACHE_HIT_ONLY_HEADER_ON_MISS = "CACHE_HIT_ONLY_HEADER_ON_MISS"


class OpenRouterWireMappingError(ContractValidationError):
    """A wire observation was refused, with the exact guard that refused it."""

    def __init__(self, code: OpenRouterWireFailureCodeV2, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}")


def _reject(code: OpenRouterWireFailureCodeV2, detail: str) -> "NoReturn":  # noqa: F821
    raise OpenRouterWireMappingError(code, detail)


#: Guard evaluation order.  Frozen so a failing observation always reports the
#: same first cause regardless of how many things are wrong with it.
FROZEN_OPENROUTER_WIRE_GUARD_ORDER_V2: Tuple[OpenRouterWireFailureCodeV2, ...] = (
    OpenRouterWireFailureCodeV2.OBSERVATION_DIGEST_MISMATCH,
    OpenRouterWireFailureCodeV2.BODY_NOT_UTF8,
    OpenRouterWireFailureCodeV2.BODY_NOT_JSON,
    OpenRouterWireFailureCodeV2.BODY_DUPLICATE_KEY,
    OpenRouterWireFailureCodeV2.BODY_NON_FINITE_NUMBER,
    OpenRouterWireFailureCodeV2.BODY_NOT_OBJECT,
    OpenRouterWireFailureCodeV2.HEADER_CONFLICTING_DUPLICATE,
    OpenRouterWireFailureCodeV2.HEADER_CACHE_STATUS_INVALID,
    OpenRouterWireFailureCodeV2.HEADER_CACHE_INTEGER_INVALID,
    OpenRouterWireFailureCodeV2.ENVELOPE_AMBIGUOUS,
    OpenRouterWireFailureCodeV2.ENVELOPE_UNCLASSIFIABLE,
    OpenRouterWireFailureCodeV2.ERROR_OBJECT_TYPE,
    OpenRouterWireFailureCodeV2.SUCCESS_MODEL_TYPE,
    OpenRouterWireFailureCodeV2.METADATA_TYPE,
    OpenRouterWireFailureCodeV2.METADATA_REQUIRED_FIELD_ABSENT,
    OpenRouterWireFailureCodeV2.METADATA_FIELD_TYPE,
    OpenRouterWireFailureCodeV2.STRATEGY_NOT_DOCUMENTED,
    OpenRouterWireFailureCodeV2.ATTEMPT_RANGE,
    OpenRouterWireFailureCodeV2.ENDPOINTS_TYPE,
    OpenRouterWireFailureCodeV2.ENDPOINTS_FIELD,
    OpenRouterWireFailureCodeV2.ENDPOINT_ENTRY_TYPE,
    OpenRouterWireFailureCodeV2.ENDPOINT_ENTRY_FIELD,
    OpenRouterWireFailureCodeV2.ATTEMPTS_TYPE,
    OpenRouterWireFailureCodeV2.ATTEMPTS_ENTRY_TYPE,
    OpenRouterWireFailureCodeV2.ATTEMPTS_ENTRY_FIELD,
    OpenRouterWireFailureCodeV2.PARAMS_TYPE,
    OpenRouterWireFailureCodeV2.PIPELINE_TYPE,
    OpenRouterWireFailureCodeV2.PIPELINE_STAGE_TYPE,
    OpenRouterWireFailureCodeV2.PIPELINE_STAGE_FIELD,
    OpenRouterWireFailureCodeV2.CACHE_HIT_CONTRADICTS_ERROR_ENVELOPE,
    OpenRouterWireFailureCodeV2.CACHE_HIT_CONTRADICTS_METADATA,
    OpenRouterWireFailureCodeV2.CACHE_HIT_ONLY_HEADER_ON_MISS,
)
OPENROUTER_WIRE_GUARD_ORDER_ID_V2 = stable_contract_id(
    "szorwireguardsv2",
    tuple(code.value for code in FROZEN_OPENROUTER_WIRE_GUARD_ORDER_V2),
)

# ------------------------------------------------------- documented vocabulary

#: ``RoutingStrategy`` enum, retained OpenAPI ``components.schemas``.  Closed:
#: the additive statement in the router-metadata source covers new optional
#: fields and new pipeline stage types, and does not extend to strategy values.
FROZEN_OPENROUTER_ROUTING_STRATEGY_ENUM_V2: Tuple[str, ...] = (
    "direct",
    "auto",
    "free",
    "latest",
    "alias",
    "fallback",
    "pareto",
    "bodybuilder",
    "fusion",
)

#: ``PipelineStageType`` enum, retained OpenAPI.  Documented as growing: "The
#: list grows over time. Treat unknown stage types as opaque."  Unknown stage
#: types are therefore preserved non-authoritatively rather than refused.
FROZEN_OPENROUTER_PIPELINE_STAGE_TYPE_ENUM_V2: Tuple[str, ...] = (
    "guardrail",
    "plugin",
    "server_tools",
    "response_healing",
    "context_compression",
)

#: ``OpenRouterMetadata`` required properties, retained OpenAPI.  Required only
#: where the success schema binds the strict ``OpenRouterMetadata`` ref; the
#: documented error schemas bind ``openrouter_metadata`` as a loose object
#: (``additionalProperties: {}``, ``type: [object, null]``), which is why the
#: documented 404 example omits region/summary/is_byok legitimately.
FROZEN_OPENROUTER_METADATA_REQUIRED_FIELDS_V2: Tuple[str, ...] = (
    "requested",
    "strategy",
    "region",
    "summary",
    "attempt",
    "is_byok",
    "endpoints",
)
FROZEN_OPENROUTER_METADATA_KNOWN_FIELDS_V2: Tuple[str, ...] = (
    FROZEN_OPENROUTER_METADATA_REQUIRED_FIELDS_V2 + ("attempts", "params", "pipeline")
)

OPENROUTER_CACHE_STATUS_HEADER_V2 = "x-openrouter-cache-status"
OPENROUTER_CACHE_AGE_HEADER_V2 = "x-openrouter-cache-age"
OPENROUTER_CACHE_TTL_HEADER_V2 = "x-openrouter-cache-ttl"
OPENROUTER_CACHE_SOURCE_ID_HEADER_V2 = "x-openrouter-cache-source-id"
OPENROUTER_GENERATION_ID_HEADER_V2 = "x-generation-id"

#: Headers that carry authority.  A conflicting duplicate of any of these is
#: refused rather than resolved by an invented precedence rule.
FROZEN_OPENROUTER_AUTHORITY_HEADERS_V2: Tuple[str, ...] = (
    OPENROUTER_CACHE_STATUS_HEADER_V2,
    OPENROUTER_CACHE_AGE_HEADER_V2,
    OPENROUTER_CACHE_TTL_HEADER_V2,
    OPENROUTER_CACHE_SOURCE_ID_HEADER_V2,
    OPENROUTER_GENERATION_ID_HEADER_V2,
)

#: Headers documented as populated on HIT only.
FROZEN_OPENROUTER_HIT_ONLY_HEADERS_V2: Tuple[str, ...] = (
    OPENROUTER_CACHE_AGE_HEADER_V2,
    OPENROUTER_CACHE_SOURCE_ID_HEADER_V2,
)

# ------------------------------------------------------------------ contracts


class _FrozenWireContractV2(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class OpenRouterRawWireHeaderV2(_FrozenWireContractV2):
    """One observed response header, preserved verbatim and in order."""

    name: str
    value: str


class OpenRouterRawWireObservationV2(_FrozenWireContractV2):
    """The wire observation: raw body bytes plus response header evidence.

    This is the mapper's only input.  It deliberately does not accept a
    pre-normalized dictionary from another parser, so the same contract works
    unchanged on a real captured response later.

    Request material has no place here.  Nothing in this object may carry an
    Authorization header or any credential.
    """

    schema_version: Literal[
        OPENROUTER_WIRE_OBSERVATION_SCHEMA_V2
    ] = OPENROUTER_WIRE_OBSERVATION_SCHEMA_V2
    raw_body: bytes
    headers: Tuple[OpenRouterRawWireHeaderV2, ...] = ()
    raw_body_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    raw_body_length: Optional[int] = Field(default=None, ge=0)
    header_evidence_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    header_count: Optional[int] = Field(default=None, ge=0)
    observation_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterRawWireObservationV2":
        for header in self.headers:
            if header.name.strip().lower() == "authorization":
                raise ContractValidationError(
                    "response wire evidence must not carry an Authorization header"
                )
        body_sha = _sha256_bytes(self.raw_body)
        body_length = len(self.raw_body)
        header_payload = canonical_json(
            [[header.name, header.value] for header in self.headers]
        )
        header_sha = _sha256_text(header_payload)
        header_count = len(self.headers)
        declared = (
            self.raw_body_sha256,
            self.raw_body_length,
            self.header_evidence_sha256,
            self.header_count,
        )
        derived = (body_sha, body_length, header_sha, header_count)
        for declared_value, derived_value in zip(declared, derived):
            if declared_value is not None and declared_value != derived_value:
                _reject(
                    OpenRouterWireFailureCodeV2.OBSERVATION_DIGEST_MISMATCH,
                    "declared observation evidence does not match the raw bytes",
                )
        object.__setattr__(self, "raw_body_sha256", body_sha)
        object.__setattr__(self, "raw_body_length", body_length)
        object.__setattr__(self, "header_evidence_sha256", header_sha)
        object.__setattr__(self, "header_count", header_count)
        expected = stable_contract_id(
            "szorwireobservationv2",
            {
                "schema_version": self.schema_version,
                "raw_body_sha256": body_sha,
                "raw_body_length": body_length,
                "header_evidence_sha256": header_sha,
                "header_count": header_count,
            },
        )
        if self.observation_id not in (None, expected):
            raise ContractValidationError("raw wire observation ID mismatch")
        object.__setattr__(self, "observation_id", expected)
        return self


def build_openrouter_raw_wire_observation_v2(
    raw_body: bytes,
    headers: Sequence[Tuple[str, str]] = (),
) -> OpenRouterRawWireObservationV2:
    """Convenience constructor from bytes and ordered header pairs."""
    return OpenRouterRawWireObservationV2(
        raw_body=raw_body,
        headers=tuple(
            OpenRouterRawWireHeaderV2(name=name, value=value)
            for name, value in headers
        ),
    )


class OpenRouterWireUnknownFieldV2(_FrozenWireContractV2):
    """One unknown/additive field, retained without authority.

    The value itself is not copied into the mapping: only its JSON type and a
    canonical digest, which keeps aggregate artifacts lean and keeps arbitrary
    response content out of downstream evidence.
    """

    path: str
    json_type: str
    value_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class OpenRouterWireEndpointCandidateV2(_FrozenWireContractV2):
    """One ``endpoints.available[]`` record.

    ``provider_display_name`` is named for its documented granularity so it
    cannot be mistaken for an endpoint slug.
    """

    provider_display_name: str
    model: str
    selected: bool


class OpenRouterWireEndpointCollectionV2(_FrozenWireContractV2):
    """``endpoints``.  ``total`` is reported as documented.

    No ``total == len(available)`` invariant is asserted: the official evidence
    does not state one, so inventing it would be a repository convention.
    """

    total: int
    available: Tuple[OpenRouterWireEndpointCandidateV2, ...]


class OpenRouterWireAttemptRecordV2(_FrozenWireContractV2):
    """One ``attempts[]`` record at documented granularity."""

    provider_display_name: str
    model: str
    status: int


class OpenRouterWirePipelineStageV2(_FrozenWireContractV2):
    """One ``pipeline[]`` stage.

    ``stage_type_is_documented`` records whether the type is in the retained
    enum.  An unknown type is opaque and preserved, never authoritative, and
    never a rejection: the official source says the list grows over time.
    ``data`` is free-form by design and is reduced to a digest.
    """

    stage_type: str
    stage_type_is_documented: bool
    name: str
    data_presence: OpenRouterWirePresenceV2
    data_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class OpenRouterNormalizedWireMappingV2(_FrozenWireContractV2):
    """The normalized mapping.

    Four kinds of content are kept apart on purpose: raw observation evidence,
    normalized authoritative mapping, non-authoritative unknown evidence, and
    epistemic states for authorities the contract does not supply.
    """

    schema_version: Literal[
        OPENROUTER_WIRE_MAPPING_SCHEMA_V2
    ] = OPENROUTER_WIRE_MAPPING_SCHEMA_V2

    # --- raw observation evidence
    raw_observation_id: str
    raw_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_body_length: int = Field(ge=0)
    header_evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    # --- normalized authoritative mapping
    envelope_kind: OpenRouterWireEnvelopeKindV2
    actual_served_model: Optional[str] = None
    actual_served_model_status: OpenRouterWireEpistemicStatusV2
    router_metadata_presence: OpenRouterWirePresenceV2
    requested_model: Optional[str] = None
    routing_strategy: Optional[str] = None
    region_presence: OpenRouterWirePresenceV2 = OpenRouterWirePresenceV2.ABSENT
    region: Optional[str] = None
    summary: Optional[str] = None
    attempt: Optional[int] = None
    is_byok: Optional[bool] = None
    endpoint_collection: Optional[OpenRouterWireEndpointCollectionV2] = None
    params_presence: OpenRouterWirePresenceV2 = OpenRouterWirePresenceV2.ABSENT
    params_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attempts_presence: OpenRouterWirePresenceV2 = OpenRouterWirePresenceV2.ABSENT
    attempts: Tuple[OpenRouterWireAttemptRecordV2, ...] = ()
    pipeline_presence: OpenRouterWirePresenceV2 = OpenRouterWirePresenceV2.ABSENT
    pipeline: Tuple[OpenRouterWirePipelineStageV2, ...] = ()

    # --- header-borne authority
    cache_status_presence: OpenRouterWirePresenceV2 = OpenRouterWirePresenceV2.ABSENT
    cache_status: Optional[OpenRouterWireCacheStatusV2] = None
    cache_age_seconds: Optional[int] = None
    cache_ttl_seconds: Optional[int] = None
    cache_source_generation_id: Optional[str] = None
    generation_id: Optional[str] = None

    # --- epistemic states
    exact_endpoint_response_identity_status: Literal[
        OpenRouterWireEpistemicStatusV2.UNAVAILABLE_BY_DOCUMENTED_CONTRACT
    ] = OpenRouterWireEpistemicStatusV2.UNAVAILABLE_BY_DOCUMENTED_CONTRACT
    exact_endpoint_response_identity: None = None

    # --- non-authoritative evidence
    unknown_field_evidence: Tuple[OpenRouterWireUnknownFieldV2, ...] = ()

    # --- provenance
    source_manifest_id: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    source_manifest_sha256: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    guard_order_id: Literal[
        OPENROUTER_WIRE_GUARD_ORDER_ID_V2
    ] = OPENROUTER_WIRE_GUARD_ORDER_ID_V2

    mapping_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterNormalizedWireMappingV2":
        if self.exact_endpoint_response_identity is not None:
            raise ContractValidationError(
                "exact endpoint response identity must carry no value"
            )
        if (
            self.actual_served_model is not None
            and self.actual_served_model_status
            is not OpenRouterWireEpistemicStatusV2.ESTABLISHED
        ):
            raise ContractValidationError(
                "actual served model value requires an established status"
            )
        if (
            self.actual_served_model is None
            and self.actual_served_model_status
            is OpenRouterWireEpistemicStatusV2.ESTABLISHED
        ):
            raise ContractValidationError(
                "actual served model status claims more than the mapping carries"
            )
        if (self.cache_status is None) != (
            self.cache_status_presence is OpenRouterWirePresenceV2.ABSENT
        ):
            raise ContractValidationError("cache status presence disagrees with value")
        expected = stable_contract_id(
            "szorwiremappingresultv2",
            self.model_dump(mode="json", exclude={"mapping_id"}),
        )
        if self.mapping_id not in (None, expected):
            raise ContractValidationError("wire mapping ID mismatch")
        object.__setattr__(self, "mapping_id", expected)
        return self


# ------------------------------------------------------------ strict decoding


def _strict_json_object(raw_body: bytes) -> Dict[str, Any]:
    """Decode the body strictly: UTF-8, JSON, no duplicates, no non-finites."""
    try:
        text = raw_body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        _reject(OpenRouterWireFailureCodeV2.BODY_NOT_UTF8, str(exc))

    def _pairs(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
        keys = [key for key, _ in pairs]
        if len(set(keys)) != len(keys):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            _reject(
                OpenRouterWireFailureCodeV2.BODY_DUPLICATE_KEY,
                f"duplicate object keys: {duplicates}",
            )
        return dict(pairs)

    def _constant(name: str) -> Any:
        _reject(
            OpenRouterWireFailureCodeV2.BODY_NON_FINITE_NUMBER,
            f"non-finite JSON constant: {name}",
        )

    def _float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            _reject(
                OpenRouterWireFailureCodeV2.BODY_NON_FINITE_NUMBER,
                f"non-finite JSON number: {value}",
            )
        return parsed

    try:
        decoded = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_constant,
            parse_float=_float,
        )
    except OpenRouterWireMappingError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        _reject(OpenRouterWireFailureCodeV2.BODY_NOT_JSON, str(exc))
    if not isinstance(decoded, dict):
        _reject(
            OpenRouterWireFailureCodeV2.BODY_NOT_OBJECT,
            f"top-level JSON value is {type(decoded).__name__}, not an object",
        )
    return decoded


def _is_int(value: Any) -> bool:
    # JSON ``true``/``false`` decode to bool, which is an int subclass in
    # Python.  A boolean is never an acceptable integer on the wire.
    return isinstance(value, int) and not isinstance(value, bool)


def _require_str(container: Mapping[str, Any], key: str, path: str, code) -> str:
    value = container[key]
    if not isinstance(value, str):
        _reject(code, f"{path} must be a string, got {type(value).__name__}")
    return value


# --------------------------------------------------------------- header side


def _header_multimap(
    observation: OpenRouterRawWireObservationV2,
) -> Dict[str, Tuple[str, ...]]:
    grouped: Dict[str, list] = {}
    for header in observation.headers:
        grouped.setdefault(header.name.strip().lower(), []).append(header.value)
    return {name: tuple(values) for name, values in grouped.items()}


def _single_authority_header(
    grouped: Mapping[str, Tuple[str, ...]], name: str
) -> Optional[str]:
    values = grouped.get(name)
    if not values:
        return None
    distinct = set(values)
    if len(distinct) > 1:
        _reject(
            OpenRouterWireFailureCodeV2.HEADER_CONFLICTING_DUPLICATE,
            f"{name} carries conflicting duplicate values {sorted(distinct)}",
        )
    return values[0]


def _cache_integer(value: Optional[str], name: str) -> Optional[int]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped.isdigit():
        _reject(
            OpenRouterWireFailureCodeV2.HEADER_CACHE_INTEGER_INVALID,
            f"{name} must be a non-negative integer, got {value!r}",
        )
    return int(stripped)


# ------------------------------------------------------------ metadata side


def _unknown_fields(
    container: Mapping[str, Any], known: Sequence[str], prefix: str
) -> Tuple[OpenRouterWireUnknownFieldV2, ...]:
    return tuple(
        OpenRouterWireUnknownFieldV2(
            path=f"{prefix}.{key}",
            json_type=type(container[key]).__name__,
            value_sha256=_sha256_text(canonical_json(container[key])),
        )
        for key in sorted(container)
        if key not in known
    )


def _map_endpoints(value: Any) -> OpenRouterWireEndpointCollectionV2:
    if not isinstance(value, dict):
        _reject(
            OpenRouterWireFailureCodeV2.ENDPOINTS_TYPE,
            f"endpoints must be an object, got {type(value).__name__}",
        )
    for field in ("total", "available"):
        if field not in value:
            _reject(
                OpenRouterWireFailureCodeV2.ENDPOINTS_FIELD,
                f"endpoints.{field} is required by the documented schema",
            )
    if not _is_int(value["total"]):
        _reject(
            OpenRouterWireFailureCodeV2.ENDPOINTS_FIELD,
            "endpoints.total must be an integer",
        )
    if not isinstance(value["available"], list):
        _reject(
            OpenRouterWireFailureCodeV2.ENDPOINTS_FIELD,
            "endpoints.available must be an array",
        )
    candidates = []
    for index, entry in enumerate(value["available"]):
        if not isinstance(entry, dict):
            _reject(
                OpenRouterWireFailureCodeV2.ENDPOINT_ENTRY_TYPE,
                f"endpoints.available[{index}] must be an object",
            )
        for field in ("provider", "model", "selected"):
            if field not in entry:
                _reject(
                    OpenRouterWireFailureCodeV2.ENDPOINT_ENTRY_FIELD,
                    f"endpoints.available[{index}].{field} is required",
                )
        if not isinstance(entry["selected"], bool):
            _reject(
                OpenRouterWireFailureCodeV2.ENDPOINT_ENTRY_FIELD,
                f"endpoints.available[{index}].selected must be a boolean",
            )
        candidates.append(
            OpenRouterWireEndpointCandidateV2(
                provider_display_name=_require_str(
                    entry,
                    "provider",
                    f"endpoints.available[{index}].provider",
                    OpenRouterWireFailureCodeV2.ENDPOINT_ENTRY_FIELD,
                ),
                model=_require_str(
                    entry,
                    "model",
                    f"endpoints.available[{index}].model",
                    OpenRouterWireFailureCodeV2.ENDPOINT_ENTRY_FIELD,
                ),
                selected=entry["selected"],
            )
        )
    return OpenRouterWireEndpointCollectionV2(
        total=value["total"], available=tuple(candidates)
    )


def _map_attempts(value: Any) -> Tuple[OpenRouterWireAttemptRecordV2, ...]:
    if not isinstance(value, list):
        _reject(
            OpenRouterWireFailureCodeV2.ATTEMPTS_TYPE,
            f"attempts must be an array, got {type(value).__name__}",
        )
    records = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            _reject(
                OpenRouterWireFailureCodeV2.ATTEMPTS_ENTRY_TYPE,
                f"attempts[{index}] must be an object",
            )
        for field in ("provider", "model", "status"):
            if field not in entry:
                _reject(
                    OpenRouterWireFailureCodeV2.ATTEMPTS_ENTRY_FIELD,
                    f"attempts[{index}].{field} is required",
                )
        if not _is_int(entry["status"]):
            _reject(
                OpenRouterWireFailureCodeV2.ATTEMPTS_ENTRY_FIELD,
                f"attempts[{index}].status must be an integer",
            )
        records.append(
            OpenRouterWireAttemptRecordV2(
                provider_display_name=_require_str(
                    entry,
                    "provider",
                    f"attempts[{index}].provider",
                    OpenRouterWireFailureCodeV2.ATTEMPTS_ENTRY_FIELD,
                ),
                model=_require_str(
                    entry,
                    "model",
                    f"attempts[{index}].model",
                    OpenRouterWireFailureCodeV2.ATTEMPTS_ENTRY_FIELD,
                ),
                status=entry["status"],
            )
        )
    return tuple(records)


def _map_pipeline(value: Any) -> Tuple[OpenRouterWirePipelineStageV2, ...]:
    if not isinstance(value, list):
        _reject(
            OpenRouterWireFailureCodeV2.PIPELINE_TYPE,
            f"pipeline must be an array, got {type(value).__name__}",
        )
    stages = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            _reject(
                OpenRouterWireFailureCodeV2.PIPELINE_STAGE_TYPE,
                f"pipeline[{index}] must be an object",
            )
        for field in ("type", "name"):
            if field not in entry:
                _reject(
                    OpenRouterWireFailureCodeV2.PIPELINE_STAGE_FIELD,
                    f"pipeline[{index}].{field} is required",
                )
        stage_type = _require_str(
            entry,
            "type",
            f"pipeline[{index}].type",
            OpenRouterWireFailureCodeV2.PIPELINE_STAGE_FIELD,
        )
        name = _require_str(
            entry,
            "name",
            f"pipeline[{index}].name",
            OpenRouterWireFailureCodeV2.PIPELINE_STAGE_FIELD,
        )
        data_presence = OpenRouterWirePresenceV2.ABSENT
        data_sha256 = None
        if "data" in entry:
            data = entry["data"]
            if not isinstance(data, dict):
                _reject(
                    OpenRouterWireFailureCodeV2.PIPELINE_STAGE_FIELD,
                    f"pipeline[{index}].data must be an object",
                )
            data_presence = (
                OpenRouterWirePresenceV2.PRESENT_EMPTY
                if not data
                else OpenRouterWirePresenceV2.PRESENT_WITH_ENTRIES
            )
            data_sha256 = _sha256_text(canonical_json(data))
        stages.append(
            OpenRouterWirePipelineStageV2(
                stage_type=stage_type,
                stage_type_is_documented=(
                    stage_type in FROZEN_OPENROUTER_PIPELINE_STAGE_TYPE_ENUM_V2
                ),
                name=name,
                data_presence=data_presence,
                data_sha256=data_sha256,
            )
        )
    return tuple(stages)


# ------------------------------------------------------------------- mapper


def map_openrouter_raw_wire_v2(
    observation: OpenRouterRawWireObservationV2,
) -> OpenRouterNormalizedWireMappingV2:
    """Map one raw wire observation, or refuse it fail-closed."""
    if type(observation) is not OpenRouterRawWireObservationV2:
        raise ContractValidationError(
            "wire mapping requires the exact raw observation contract"
        )

    body = _strict_json_object(observation.raw_body)

    grouped = _header_multimap(observation)
    for name in FROZEN_OPENROUTER_AUTHORITY_HEADERS_V2:
        _single_authority_header(grouped, name)
    cache_status_raw = _single_authority_header(
        grouped, OPENROUTER_CACHE_STATUS_HEADER_V2
    )
    cache_status: Optional[OpenRouterWireCacheStatusV2] = None
    cache_status_presence = OpenRouterWirePresenceV2.ABSENT
    if cache_status_raw is not None:
        try:
            cache_status = OpenRouterWireCacheStatusV2(cache_status_raw.strip())
        except ValueError:
            _reject(
                OpenRouterWireFailureCodeV2.HEADER_CACHE_STATUS_INVALID,
                f"cache status must be HIT or MISS, got {cache_status_raw!r}",
            )
        cache_status_presence = OpenRouterWirePresenceV2.PRESENT
    cache_age = _cache_integer(
        _single_authority_header(grouped, OPENROUTER_CACHE_AGE_HEADER_V2),
        OPENROUTER_CACHE_AGE_HEADER_V2,
    )
    cache_ttl = _cache_integer(
        _single_authority_header(grouped, OPENROUTER_CACHE_TTL_HEADER_V2),
        OPENROUTER_CACHE_TTL_HEADER_V2,
    )
    cache_source_id = _single_authority_header(
        grouped, OPENROUTER_CACHE_SOURCE_ID_HEADER_V2
    )
    generation_id = _single_authority_header(
        grouped, OPENROUTER_GENERATION_ID_HEADER_V2
    )

    # Envelope discrimination from the retained schemas, not from a heuristic.
    has_error = "error" in body
    has_model = "model" in body
    if has_error and has_model:
        _reject(
            OpenRouterWireFailureCodeV2.ENVELOPE_AMBIGUOUS,
            "body carries both a top-level error and a top-level model",
        )
    if not has_error and not has_model:
        _reject(
            OpenRouterWireFailureCodeV2.ENVELOPE_UNCLASSIFIABLE,
            "body carries neither a top-level error nor a top-level model",
        )
    envelope = (
        OpenRouterWireEnvelopeKindV2.ERROR
        if has_error
        else OpenRouterWireEnvelopeKindV2.SUCCESS
    )
    if envelope is OpenRouterWireEnvelopeKindV2.ERROR and not isinstance(
        body["error"], dict
    ):
        _reject(
            OpenRouterWireFailureCodeV2.ERROR_OBJECT_TYPE,
            "top-level error must be an object",
        )

    actual_served_model: Optional[str] = None
    actual_status = OpenRouterWireEpistemicStatusV2.ABSENT_FROM_OBSERVATION
    if envelope is OpenRouterWireEnvelopeKindV2.SUCCESS:
        if not isinstance(body["model"], str):
            _reject(
                OpenRouterWireFailureCodeV2.SUCCESS_MODEL_TYPE,
                "top-level model must be a string",
            )
        actual_served_model = body["model"]
        actual_status = OpenRouterWireEpistemicStatusV2.ESTABLISHED

    metadata_presence = OpenRouterWirePresenceV2.ABSENT
    metadata: Optional[Dict[str, Any]] = None
    if "openrouter_metadata" in body:
        raw_metadata = body["openrouter_metadata"]
        if raw_metadata is None:
            metadata_presence = OpenRouterWirePresenceV2.NULL
        elif isinstance(raw_metadata, dict):
            metadata = raw_metadata
            metadata_presence = (
                OpenRouterWirePresenceV2.PRESENT_EMPTY
                if not raw_metadata
                else OpenRouterWirePresenceV2.PRESENT
            )
        else:
            _reject(
                OpenRouterWireFailureCodeV2.METADATA_TYPE,
                f"openrouter_metadata must be an object or null, got "
                f"{type(raw_metadata).__name__}",
            )

    requested_model: Optional[str] = None
    routing_strategy: Optional[str] = None
    region_presence = OpenRouterWirePresenceV2.ABSENT
    region: Optional[str] = None
    summary: Optional[str] = None
    attempt: Optional[int] = None
    is_byok: Optional[bool] = None
    endpoints: Optional[OpenRouterWireEndpointCollectionV2] = None
    params_presence = OpenRouterWirePresenceV2.ABSENT
    params_sha256: Optional[str] = None
    attempts_presence = OpenRouterWirePresenceV2.ABSENT
    attempts: Tuple[OpenRouterWireAttemptRecordV2, ...] = ()
    pipeline_presence = OpenRouterWirePresenceV2.ABSENT
    pipeline: Tuple[OpenRouterWirePipelineStageV2, ...] = ()
    unknown: Tuple[OpenRouterWireUnknownFieldV2, ...] = ()

    if metadata is not None:
        # Required-field enforcement applies where the success schema binds the
        # strict OpenRouterMetadata ref.  Documented error schemas bind
        # openrouter_metadata as a loose object, so requiring the seven fields
        # there would reject the documented 404 example.
        if envelope is OpenRouterWireEnvelopeKindV2.SUCCESS:
            for field in FROZEN_OPENROUTER_METADATA_REQUIRED_FIELDS_V2:
                if field not in metadata:
                    _reject(
                        OpenRouterWireFailureCodeV2.METADATA_REQUIRED_FIELD_ABSENT,
                        f"openrouter_metadata.{field} is required on success",
                    )

        if "requested" in metadata:
            requested_model = _require_str(
                metadata,
                "requested",
                "openrouter_metadata.requested",
                OpenRouterWireFailureCodeV2.METADATA_FIELD_TYPE,
            )
        if "strategy" in metadata:
            strategy_value = _require_str(
                metadata,
                "strategy",
                "openrouter_metadata.strategy",
                OpenRouterWireFailureCodeV2.METADATA_FIELD_TYPE,
            )
            if strategy_value not in FROZEN_OPENROUTER_ROUTING_STRATEGY_ENUM_V2:
                _reject(
                    OpenRouterWireFailureCodeV2.STRATEGY_NOT_DOCUMENTED,
                    f"strategy {strategy_value!r} is not in the documented enum",
                )
            routing_strategy = strategy_value
        if "region" in metadata:
            region_value = metadata["region"]
            if region_value is None:
                region_presence = OpenRouterWirePresenceV2.NULL
            elif isinstance(region_value, str):
                region_presence = OpenRouterWirePresenceV2.PRESENT
                region = region_value
            else:
                _reject(
                    OpenRouterWireFailureCodeV2.METADATA_FIELD_TYPE,
                    "openrouter_metadata.region must be a string or null",
                )
        if "summary" in metadata:
            summary = _require_str(
                metadata,
                "summary",
                "openrouter_metadata.summary",
                OpenRouterWireFailureCodeV2.METADATA_FIELD_TYPE,
            )
        if "attempt" in metadata:
            if not _is_int(metadata["attempt"]):
                _reject(
                    OpenRouterWireFailureCodeV2.METADATA_FIELD_TYPE,
                    "openrouter_metadata.attempt must be an integer",
                )
            attempt = metadata["attempt"]
            # Documented: success is one-indexed; on error 0 means no provider
            # was reached and >= 1 means attempted providers failed.  No maximum
            # is documented, so none is imposed.
            minimum = 1 if envelope is OpenRouterWireEnvelopeKindV2.SUCCESS else 0
            if attempt < minimum:
                _reject(
                    OpenRouterWireFailureCodeV2.ATTEMPT_RANGE,
                    f"attempt {attempt} is below the documented minimum {minimum} "
                    f"for a {envelope.value} envelope",
                )
        if "is_byok" in metadata:
            if not isinstance(metadata["is_byok"], bool):
                _reject(
                    OpenRouterWireFailureCodeV2.METADATA_FIELD_TYPE,
                    "openrouter_metadata.is_byok must be a boolean",
                )
            is_byok = metadata["is_byok"]
        if "endpoints" in metadata:
            endpoints = _map_endpoints(metadata["endpoints"])
        if "attempts" in metadata:
            attempts = _map_attempts(metadata["attempts"])
            attempts_presence = (
                OpenRouterWirePresenceV2.PRESENT_EMPTY
                if not attempts
                else OpenRouterWirePresenceV2.PRESENT_WITH_ENTRIES
            )
        if "params" in metadata:
            if not isinstance(metadata["params"], dict):
                _reject(
                    OpenRouterWireFailureCodeV2.PARAMS_TYPE,
                    "openrouter_metadata.params must be an object",
                )
            params_presence = (
                OpenRouterWirePresenceV2.PRESENT_EMPTY
                if not metadata["params"]
                else OpenRouterWirePresenceV2.PRESENT_WITH_ENTRIES
            )
            params_sha256 = _sha256_text(canonical_json(metadata["params"]))
        if "pipeline" in metadata:
            pipeline = _map_pipeline(metadata["pipeline"])
            pipeline_presence = (
                OpenRouterWirePresenceV2.PRESENT_EMPTY
                if not pipeline
                else OpenRouterWirePresenceV2.PRESENT_WITH_ENTRIES
            )
        unknown = _unknown_fields(
            metadata,
            FROZEN_OPENROUTER_METADATA_KNOWN_FIELDS_V2,
            "openrouter_metadata",
        )

    # Cache contradictions the official evidence actually documents.
    if cache_status is OpenRouterWireCacheStatusV2.HIT:
        if envelope is OpenRouterWireEnvelopeKindV2.ERROR:
            _reject(
                OpenRouterWireFailureCodeV2.CACHE_HIT_CONTRADICTS_ERROR_ENVELOPE,
                "only successful responses are cached, so HIT cannot accompany "
                "an error envelope",
            )
        if metadata_presence is not OpenRouterWirePresenceV2.ABSENT:
            _reject(
                OpenRouterWireFailureCodeV2.CACHE_HIT_CONTRADICTS_METADATA,
                "cache hits never include openrouter_metadata",
            )
    if cache_status is OpenRouterWireCacheStatusV2.MISS:
        for name, value in (
            (OPENROUTER_CACHE_AGE_HEADER_V2, cache_age),
            (OPENROUTER_CACHE_SOURCE_ID_HEADER_V2, cache_source_id),
        ):
            if value is not None:
                _reject(
                    OpenRouterWireFailureCodeV2.CACHE_HIT_ONLY_HEADER_ON_MISS,
                    f"{name} is documented on HIT only but accompanies MISS",
                )

    return OpenRouterNormalizedWireMappingV2(
        raw_observation_id=observation.observation_id or "",
        raw_body_sha256=observation.raw_body_sha256 or "",
        raw_body_length=observation.raw_body_length or 0,
        header_evidence_sha256=observation.header_evidence_sha256 or "",
        envelope_kind=envelope,
        actual_served_model=actual_served_model,
        actual_served_model_status=actual_status,
        router_metadata_presence=metadata_presence,
        requested_model=requested_model,
        routing_strategy=routing_strategy,
        region_presence=region_presence,
        region=region,
        summary=summary,
        attempt=attempt,
        is_byok=is_byok,
        endpoint_collection=endpoints,
        params_presence=params_presence,
        params_sha256=params_sha256,
        attempts_presence=attempts_presence,
        attempts=attempts,
        pipeline_presence=pipeline_presence,
        pipeline=pipeline,
        cache_status_presence=cache_status_presence,
        cache_status=cache_status,
        cache_age_seconds=cache_age,
        cache_ttl_seconds=cache_ttl,
        cache_source_generation_id=cache_source_id,
        generation_id=generation_id,
        unknown_field_evidence=unknown,
    )


__all__ = [
    "FROZEN_OPENROUTER_AUTHORITY_HEADERS_V2",
    "FROZEN_OPENROUTER_HIT_ONLY_HEADERS_V2",
    "FROZEN_OPENROUTER_METADATA_KNOWN_FIELDS_V2",
    "FROZEN_OPENROUTER_METADATA_REQUIRED_FIELDS_V2",
    "FROZEN_OPENROUTER_PIPELINE_STAGE_TYPE_ENUM_V2",
    "FROZEN_OPENROUTER_ROUTING_STRATEGY_ENUM_V2",
    "FROZEN_OPENROUTER_WIRE_GUARD_ORDER_V2",
    "OPENROUTER_WIRE_GUARD_ORDER_ID_V2",
    "OPENROUTER_WIRE_MAPPING_OFFICIAL_COMMIT_V2",
    "OPENROUTER_WIRE_MAPPING_OFFICIAL_REPOSITORY_V2",
    "OPENROUTER_WIRE_MAPPING_SCHEMA_V2",
    "OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2",
    "OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_RELATIVE_PATH_V2",
    "OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2",
    "OPENROUTER_WIRE_OBSERVATION_SCHEMA_V2",
    "OpenRouterNormalizedWireMappingV2",
    "OpenRouterRawWireHeaderV2",
    "OpenRouterRawWireObservationV2",
    "OpenRouterWireAttemptRecordV2",
    "OpenRouterWireCacheStatusV2",
    "OpenRouterWireEndpointCandidateV2",
    "OpenRouterWireEndpointCollectionV2",
    "OpenRouterWireEnvelopeKindV2",
    "OpenRouterWireEpistemicStatusV2",
    "OpenRouterWireFailureCodeV2",
    "OpenRouterWireMappingError",
    "OpenRouterWirePipelineStageV2",
    "OpenRouterWirePresenceV2",
    "OpenRouterWireUnknownFieldV2",
    "build_openrouter_raw_wire_observation_v2",
    "map_openrouter_raw_wire_v2",
]
