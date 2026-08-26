"""Pure canned OpenRouter route-metadata parsing for Phase 8.5D.

The JSON accepted here is an explicitly local, normalized concept binding for
the offline canned experiment.  Its field names are not represented as the
official OpenRouter wire paths: the frozen Phase 8.5C manifest retained the
concepts below, but not a complete wire-schema snapshot.  Exact raw UTF-8 JSON
bytes are retained before any semantic interpretation; response member order
and insignificant whitespace are not treated as provider authority.

This module has no transport, environment, credential, provider, model, tool,
CED, filesystem, or documentation-fetch capability.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from enum import Enum
from typing import Dict, Iterable, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import canonical_json, stable_contract_id
from .openrouter_route_controls_contracts import (
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    OPENROUTER_ROUTE_MODEL_V1,
    OpenRouterPreparedRouteRequestV1,
)


NORMALIZED_CANNED_RESPONSE_SCHEMA_VERSION = (
    "socrateszero-openrouter-normalized-canned-response/v1"
)
ROUTER_METADATA_PARSER_SCHEMA_VERSION = (
    "socrateszero-openrouter-router-metadata-parser/v1"
)
ROUTER_METADATA_RECEIPT_SCHEMA_VERSION = (
    "socrateszero-openrouter-router-metadata-receipt/v1"
)
ROUTE_ATTESTATION_SCHEMA_VERSION = (
    "socrateszero-openrouter-route-attestation/v1"
)
ROUTE_CONTROL_RECEIPT_SCHEMA_VERSION = (
    "socrateszero-openrouter-route-control-receipt/v1"
)
RAW_RESPONSE_EVIDENCE_SCHEMA_VERSION = (
    "socrateszero-openrouter-route-raw-response-evidence/v1"
)
EXPECTED_BROAD_PROVIDER_V1 = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1.split("/", 1)[0]


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterRouteControlGuardV1(str, Enum):
    TRANSPORT_COMPLETION = "G18_TRANSPORT_COMPLETION"
    RAW_ENVELOPE_PRESENCE = "G19_RAW_ENVELOPE_PRESENCE"
    METADATA_PRESENCE = "G20_METADATA_PRESENCE"
    METADATA_SCHEMA = "G21_METADATA_SCHEMA"
    CACHE_METADATA_AVAILABILITY = "G22_CACHE_METADATA_AVAILABILITY"
    ATTEMPT_PRESENT_AND_VALID = "G23_ATTEMPT_VALIDITY"
    ATTEMPT_EQUALS_ONE = "G24_ATTEMPT_ONE"
    ACTUAL_MODEL_PRESENCE = "G25_ACTUAL_MODEL_PRESENCE"
    ACTUAL_MODEL_MATCH = "G26_ACTUAL_MODEL_MATCH"
    PROVIDER_PRESENCE = "G27_PROVIDER_PRESENCE"
    PROVIDER_COMPATIBILITY = "G28_PROVIDER_COMPATIBILITY"
    ATTEMPTS_LIST_CONSISTENCY = "G29_ATTEMPTS_CONSISTENCY"
    FALLBACK_INDICATORS_ABSENT = "G30_FALLBACK_PIPELINE_ABSENCE"
    NO_FALSE_EXACT_ENDPOINT_ATTESTATION = (
        "G31_EXACT_ENDPOINT_CLAIM_FIREWALL"
    )
    RECEIPT_AND_CLAIMS_INTEGRITY = "G32_RECEIPT_AND_CLAIMS_INTEGRITY"


class OpenRouterRouteControlFailureCodeV1(str, Enum):
    TRANSPORT_INCOMPLETE = "TRANSPORT_NOT_COMPLETE"
    RAW_RESPONSE_MISSING = "RAW_ENVELOPE_MISSING"
    ROUTER_METADATA_MISSING = "ROUTER_METADATA_MISSING"
    ROUTER_METADATA_MALFORMED = "ROUTER_METADATA_MALFORMED"
    REQUESTED_ROUTING_MISMATCH = "ROUTER_METADATA_MALFORMED"
    UNKNOWN_FIELD_AUTHORITY_OVERRIDE = "UNKNOWN_FIELD_AUTHORITY_OVERRIDE"
    CACHE_AFFECTED_OR_UNATTESTED = "CACHE_HIT_RESPONSE_REJECTED"
    CACHE_AFFECTED_METADATA_UNAVAILABLE = "CACHE_AFFECTED_METADATA_UNAVAILABLE"
    ATTEMPT_MISSING = "ATTEMPT_MISSING"
    ATTEMPT_INVALID = "ATTEMPT_INVALID"
    MULTI_ATTEMPT_ROUTING_OBSERVED = "MULTI_ATTEMPT_ROUTING_OBSERVED"
    ACTUAL_MODEL_MISSING = "ACTUAL_MODEL_MISSING"
    ACTUAL_MODEL_MISMATCH = "ACTUAL_MODEL_SUBSTITUTION"
    PROVIDER_MISSING = "PROVIDER_MISSING"
    PROVIDER_MISMATCH = "PROVIDER_SUBSTITUTION"
    ATTEMPTS_LIST_MALFORMED = "ATTEMPTS_LIST_MALFORMED"
    ATTEMPTS_LIST_INCONSISTENT = "ATTEMPTS_LIST_INCONSISTENT"
    MULTIPLE_ATTEMPTS_REPORTED = "MULTIPLE_ATTEMPTS_REPORTED"
    FALLBACK_INDICATOR_OBSERVED = "FALLBACK_INDICATOR_PRESENT"
    FORBIDDEN_PIPELINE_STAGE = "FORBIDDEN_PIPELINE_STAGE"
    FALSE_EXACT_ENDPOINT_CLAIM = "FALSE_EXACT_ENDPOINT_ATTESTATION"
    RECEIPT_INTEGRITY_FAILURE = "RECEIPT_MISMATCH"


class OpenRouterRouteControlParserError(ValueError):
    """A deterministic, raw-content-free first-guard parser failure."""

    def __init__(
        self,
        failure_code: OpenRouterRouteControlFailureCodeV1,
        guard_id: OpenRouterRouteControlGuardV1,
        *,
        raw_response_sha256: Optional[str] = None,
    ) -> None:
        self.failure_code = failure_code
        self.guard_id = guard_id
        self.raw_response_sha256 = raw_response_sha256
        super().__init__(f"{guard_id.value}: {failure_code.value}")


class AttemptsListStatusV1(str, Enum):
    ABSENT_ACCEPTED = "ABSENT_ACCEPTED"
    PRESENT_CONSISTENT = "PRESENT_CONSISTENT"


class ProviderAttestationGranularityV1(str, Enum):
    BROAD_PROVIDER_ONLY = "BROAD_PROVIDER_ONLY"


class OpenRouterRawResponseEvidenceV1(_FrozenModel):
    schema_version: Literal[
        RAW_RESPONSE_EVIDENCE_SCHEMA_VERSION
    ] = RAW_RESPONSE_EVIDENCE_SCHEMA_VERSION
    raw_response_json: str
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_response_length: int = Field(ge=1)
    evidence_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_raw_first_evidence(self) -> "OpenRouterRawResponseEvidenceV1":
        encoded = self.raw_response_json.encode("utf-8")
        if len(encoded) != self.raw_response_length:
            raise ValueError("raw response length does not match retained bytes")
        if hashlib.sha256(encoded).hexdigest() != self.raw_response_sha256:
            raise ValueError("raw response digest does not match retained bytes")
        try:
            decoded = json.loads(
                self.raw_response_json,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_json_constant,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("retained raw response must be JSON") from exc
        if not isinstance(decoded, dict):
            raise ValueError("retained raw response must be a JSON object")
        expected = stable_contract_id(
            "szorrawroutev1",
            self.model_dump(mode="json", exclude={"evidence_id"}),
        )
        if self.evidence_id is not None and self.evidence_id != expected:
            raise ValueError("raw response evidence_id does not match semantic content")
        object.__setattr__(self, "evidence_id", expected)
        return self


class OpenRouterRouterMetadataReceiptV1(_FrozenModel):
    schema_version: Literal[
        ROUTER_METADATA_RECEIPT_SCHEMA_VERSION
    ] = ROUTER_METADATA_RECEIPT_SCHEMA_VERSION
    parser_schema_version: Literal[
        ROUTER_METADATA_PARSER_SCHEMA_VERSION
    ] = ROUTER_METADATA_PARSER_SCHEMA_VERSION
    raw_response_evidence_id: str
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_metadata: Literal["PRESENT"] = "PRESENT"
    attempt: Literal[1] = 1
    attempts_list_status: AttemptsListStatusV1
    requested_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    actual_model: Literal[OPENROUTER_ROUTE_MODEL_V1] = OPENROUTER_ROUTE_MODEL_V1
    model_match: Literal["EXACT_MATCH"] = "EXACT_MATCH"
    requested_endpoint: Literal[
        OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    ] = OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    attested_provider: Literal[EXPECTED_BROAD_PROVIDER_V1] = EXPECTED_BROAD_PROVIDER_V1
    provider_attestation_granularity: Literal[
        ProviderAttestationGranularityV1.BROAD_PROVIDER_ONLY
    ] = ProviderAttestationGranularityV1.BROAD_PROVIDER_ONLY
    routing_strategy_summary: str
    exact_endpoint_response_attestation: Literal[
        "NOT_ESTABLISHED"
    ] = "NOT_ESTABLISHED"
    fallback_observation: Literal[
        "NO_OBSERVED_ROUTER_FALLBACK"
    ] = "NO_OBSERVED_ROUTER_FALLBACK"
    cache_metadata_status: Literal[
        "METADATA_PRESENT_NO_CACHE_HIT_INFERENCE"
    ] = "METADATA_PRESENT_NO_CACHE_HIT_INFERENCE"
    unknown_fields_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    unknown_field_count: int = Field(ge=0)
    parsing_result: Literal["ACCEPTED_PARTIAL_ATTESTATION"] = (
        "ACCEPTED_PARTIAL_ATTESTATION"
    )
    receipt_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterRouterMetadataReceiptV1":
        if not self.routing_strategy_summary.strip():
            raise ValueError("routing strategy summary must not be blank")
        expected = stable_contract_id(
            "szormetadatareceiptv1",
            self.model_dump(mode="json", exclude={"receipt_id"}),
        )
        if self.receipt_id is not None and self.receipt_id != expected:
            raise ValueError("metadata receipt_id does not match semantic content")
        object.__setattr__(self, "receipt_id", expected)
        return self


class OpenRouterRouteAttestationV1(_FrozenModel):
    schema_version: Literal[
        ROUTE_ATTESTATION_SCHEMA_VERSION
    ] = ROUTE_ATTESTATION_SCHEMA_VERSION
    metadata_receipt_id: str
    route_intent_id: str = Field(pattern=r"^szorrouteintent_[0-9a-f]{64}$")
    request_intent_receipt_id: str = Field(
        pattern=r"^szorrouteintentreceiptv1_[0-9a-f]{64}$"
    )
    request_exact_model_intent: Literal["PROVEN"] = "PROVEN"
    request_exact_endpoint_intent: Literal["PROVEN"] = "PROVEN"
    request_provider_fallback_disabled_intent: Literal["PROVEN"] = "PROVEN"
    request_model_fallback_disabled_intent: Literal["PROVEN"] = "PROVEN"
    response_actual_model_attestation: Literal["EXACT_MATCH"] = "EXACT_MATCH"
    response_provider_attestation: Literal["PARTIAL_BROAD_PROVIDER"] = (
        "PARTIAL_BROAD_PROVIDER"
    )
    response_exact_endpoint_attestation: Literal[
        "NOT_ESTABLISHED"
    ] = "NOT_ESTABLISHED"
    response_router_fallback_observation: Literal[
        "NO_OBSERVED_ROUTER_FALLBACK"
    ] = "NO_OBSERVED_ROUTER_FALLBACK"
    universal_no_fallback_proof: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    live_route_enforcement: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_total_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_pilot_readiness: Literal["NOT_EARNED"] = "NOT_EARNED"
    real_provider_execution: Literal[False] = False
    attestation_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterRouteAttestationV1":
        expected = stable_contract_id(
            "szorrouteattestationv1",
            self.model_dump(mode="json", exclude={"attestation_id"}),
        )
        if self.attestation_id is not None and self.attestation_id != expected:
            raise ValueError("attestation_id does not match semantic content")
        object.__setattr__(self, "attestation_id", expected)
        return self


class OpenRouterRouteControlReceiptV1(_FrozenModel):
    schema_version: Literal[
        ROUTE_CONTROL_RECEIPT_SCHEMA_VERSION
    ] = ROUTE_CONTROL_RECEIPT_SCHEMA_VERSION
    route_intent_id: str = Field(pattern=r"^szorrouteintent_[0-9a-f]{64}$")
    request_intent_receipt_id: str = Field(
        pattern=r"^szorrouteintentreceiptv1_[0-9a-f]{64}$"
    )
    raw_response: OpenRouterRawResponseEvidenceV1
    metadata_receipt: OpenRouterRouterMetadataReceiptV1
    route_attestation: OpenRouterRouteAttestationV1
    live_enforcement: Literal["NOT_PROVEN"] = "NOT_PROVEN"
    exact_endpoint_response_attestation: Literal[
        "NOT_ESTABLISHED"
    ] = "NOT_ESTABLISHED"
    p17_status: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_status: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_status: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_readiness: Literal["NOT_EARNED"] = "NOT_EARNED"
    real_provider_execution: Literal[False] = False
    receipt_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_links_and_identify(self) -> "OpenRouterRouteControlReceiptV1":
        if (
            self.metadata_receipt.raw_response_evidence_id
            != self.raw_response.evidence_id
            or self.metadata_receipt.raw_response_sha256
            != self.raw_response.raw_response_sha256
            or self.route_attestation.metadata_receipt_id
            != self.metadata_receipt.receipt_id
            or self.route_attestation.route_intent_id != self.route_intent_id
            or self.route_attestation.request_intent_receipt_id
            != self.request_intent_receipt_id
        ):
            raise ValueError("route-control receipt evidence links do not match")
        expected = stable_contract_id(
            "szorroutecontrolreceiptv1",
            self.model_dump(mode="json", exclude={"receipt_id"}),
        )
        if self.receipt_id is not None and self.receipt_id != expected:
            raise ValueError("route-control receipt_id does not match semantic content")
        object.__setattr__(self, "receipt_id", expected)
        return self


_METADATA_KEYS = frozenset(
    {
        "requested_model",
        "requested_provider_only",
        "routing_strategy",
        "actual_model",
        "provider",
        "attempt",
        "attempts",
        "pipeline",
        "fallback_observed",
    }
)
_CACHE_KEYS = frozenset(
    {
        "cache_hit",
        "cache_status",
        "cache_state",
        "cache_affected",
        "response_cache_hit",
    }
)
_FALLBACK_KEYS = frozenset(
    {
        "fallback",
        "fallback_observed",
        "fallback_used",
        "routing_strategy",
        "strategy",
        "provider_fallback",
        "model_fallback",
        "fallback_indicator",
    }
)
_EXACT_ENDPOINT_KEYS = frozenset(
    {
        "endpoint",
        "endpoint_id",
        "endpoint_slug",
        "exact_endpoint",
        "selected_endpoint",
        "selected_endpoint_id",
        "selected_endpoint_slug",
        "exact_endpoint_attested",
        "exact_endpoint_response_attestation",
    }
)
_AUTHORITY_KEYS = frozenset(
    {
        "requested_model",
        "requested_provider_only",
        "routing_strategy",
        "strategy",
        "requested",
        "selected",
        "selection",
        "summary",
        "region",
        "is_byok",
        "actual_model",
        "model",
        "provider",
        "attempt",
        "attempts",
        "pipeline",
        "live_enforcement",
        "live_readiness",
        "real_provider_execution",
        "p17",
        "p18",
        "p19",
    }
)


class _DuplicateKeyError(ValueError):
    pass


def _unique_object(pairs: Iterable[Tuple[str, object]]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError("duplicate JSON object member")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise ValueError("non-finite JSON number")


def _failure(
    code: OpenRouterRouteControlFailureCodeV1,
    guard: OpenRouterRouteControlGuardV1,
    raw_digest: Optional[str],
) -> None:
    raise OpenRouterRouteControlParserError(
        code,
        guard,
        raw_response_sha256=raw_digest,
    )


def _iter_named_values(value: object, names: frozenset[str]) -> Iterable[object]:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in names:
                yield nested
            yield from _iter_named_values(nested, names)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_named_values(nested, names)


def _contains_named_key(value: object, names: frozenset[str]) -> bool:
    sentinel = object()
    return next(iter(_iter_named_values(value, names)), sentinel) is not sentinel


def _parse_raw_object(raw: bytes, raw_digest: str) -> Tuple[Dict[str, object], str]:
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, ValueError, TypeError):
        _failure(
            OpenRouterRouteControlFailureCodeV1.ROUTER_METADATA_MALFORMED,
            OpenRouterRouteControlGuardV1.METADATA_SCHEMA,
            raw_digest,
        )
    if not isinstance(value, dict):
        _failure(
            OpenRouterRouteControlFailureCodeV1.ROUTER_METADATA_MALFORMED,
            OpenRouterRouteControlGuardV1.METADATA_SCHEMA,
            raw_digest,
        )
    return value, text


def _opaque_extras(
    envelope: Mapping[str, object], metadata: Mapping[str, object]
) -> Dict[str, object]:
    envelope_extras = {
        key: value
        for key, value in envelope.items()
        if key not in {"schema_version", "openrouter_metadata"}
    }
    metadata_extras = {
        key: value for key, value in metadata.items() if key not in _METADATA_KEYS
    }
    attempts_extras = []
    attempts = metadata.get("attempts")
    if isinstance(attempts, list):
        for entry in attempts:
            if isinstance(entry, dict):
                attempts_extras.append(
                    {
                        key: value
                        for key, value in entry.items()
                        if key not in {"attempt", "model", "provider", "outcome"}
                    }
                )
    pipeline_extras = []
    pipeline = metadata.get("pipeline")
    if isinstance(pipeline, list):
        pipeline_extras = [deepcopy(entry) for entry in pipeline]
    return {
        "envelope": envelope_extras,
        "metadata": metadata_extras,
        "attempts": attempts_extras,
        "pipeline": pipeline_extras,
    }


def _unknown_field_count(value: object) -> int:
    if isinstance(value, dict):
        return len(value) + sum(_unknown_field_count(item) for item in value.values())
    if isinstance(value, list):
        return sum(_unknown_field_count(item) for item in value)
    return 0


def build_reference_openrouter_route_response_v1(
    *,
    include_attempts: bool = False,
    metadata_extras: Optional[Mapping[str, object]] = None,
    envelope_extras: Optional[Mapping[str, object]] = None,
) -> bytes:
    """Return the canonical positive normalized canned response bytes."""

    metadata: Dict[str, object] = {
        "actual_model": OPENROUTER_ROUTE_MODEL_V1,
        "attempt": 1,
        "provider": EXPECTED_BROAD_PROVIDER_V1,
        "requested_model": OPENROUTER_ROUTE_MODEL_V1,
        "requested_provider_only": [OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1],
        "routing_strategy": "direct",
    }
    if include_attempts:
        metadata["attempts"] = [
            {
                "attempt": 1,
                "model": OPENROUTER_ROUTE_MODEL_V1,
                "outcome": "success",
                "provider": EXPECTED_BROAD_PROVIDER_V1,
            }
        ]
    if metadata_extras:
        collision = set(metadata).intersection(metadata_extras)
        if collision:
            raise ValueError("metadata extras collide with normalized concepts")
        metadata.update(metadata_extras)
    envelope: Dict[str, object] = {
        "openrouter_metadata": metadata,
        "schema_version": NORMALIZED_CANNED_RESPONSE_SCHEMA_VERSION,
    }
    if envelope_extras:
        collision = set(envelope).intersection(envelope_extras)
        if collision:
            raise ValueError("envelope extras collide with normalized concepts")
        envelope.update(envelope_extras)
    return canonical_json(envelope).encode("utf-8")


def parse_openrouter_router_metadata_v1(
    raw_response_bytes: Optional[bytes],
    prepared_request: OpenRouterPreparedRouteRequestV1,
    *,
    transport_completed: bool = True,
) -> OpenRouterRouteControlReceiptV1:
    """Parse one canonical normalized canned response with first-guard-wins.

    Only successful partial attestations are returned.  Every rejection raises
    :class:`OpenRouterRouteControlParserError`; the exception carries the
    deterministic first guard and failure code but never the raw response.
    """

    if transport_completed is not True:
        _failure(
            OpenRouterRouteControlFailureCodeV1.TRANSPORT_INCOMPLETE,
            OpenRouterRouteControlGuardV1.TRANSPORT_COMPLETION,
            None,
        )
    if raw_response_bytes is None or raw_response_bytes == b"":
        _failure(
            OpenRouterRouteControlFailureCodeV1.RAW_RESPONSE_MISSING,
            OpenRouterRouteControlGuardV1.RAW_ENVELOPE_PRESENCE,
            None,
        )
    if type(raw_response_bytes) is not bytes:
        _failure(
            OpenRouterRouteControlFailureCodeV1.ROUTER_METADATA_MALFORMED,
            OpenRouterRouteControlGuardV1.METADATA_SCHEMA,
            None,
        )
    raw_digest = hashlib.sha256(raw_response_bytes).hexdigest()
    envelope, raw_text = _parse_raw_object(raw_response_bytes, raw_digest)

    metadata_value = envelope.get("openrouter_metadata")
    if metadata_value is None:
        _failure(
            OpenRouterRouteControlFailureCodeV1.ROUTER_METADATA_MISSING,
            OpenRouterRouteControlGuardV1.METADATA_PRESENCE,
            raw_digest,
        )
    if (
        envelope.get("schema_version") != NORMALIZED_CANNED_RESPONSE_SCHEMA_VERSION
        or not isinstance(metadata_value, dict)
    ):
        _failure(
            OpenRouterRouteControlFailureCodeV1.ROUTER_METADATA_MALFORMED,
            OpenRouterRouteControlGuardV1.METADATA_SCHEMA,
            raw_digest,
        )
    metadata: Dict[str, object] = metadata_value

    requested_model = metadata.get("requested_model")
    requested_only = metadata.get("requested_provider_only")
    strategy = metadata.get("routing_strategy")
    if (
        not isinstance(requested_model, str)
        or not isinstance(requested_only, list)
        or any(not isinstance(item, str) for item in requested_only)
        or not isinstance(strategy, str)
        or not strategy.strip()
    ):
        _failure(
            OpenRouterRouteControlFailureCodeV1.ROUTER_METADATA_MALFORMED,
            OpenRouterRouteControlGuardV1.METADATA_SCHEMA,
            raw_digest,
        )
    if (
        requested_model != OPENROUTER_ROUTE_MODEL_V1
        or requested_only != [OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1]
    ):
        _failure(
            OpenRouterRouteControlFailureCodeV1.REQUESTED_ROUTING_MISMATCH,
            OpenRouterRouteControlGuardV1.METADATA_SCHEMA,
            raw_digest,
        )

    opaque = _opaque_extras(envelope, metadata)
    authority_extras = {
        "envelope": opaque["envelope"],
        "metadata": opaque["metadata"],
        "attempts": opaque["attempts"],
        "pipeline": opaque["pipeline"],
    }
    authority_without_deferred_keys = _remove_keys(
        authority_extras,
        _CACHE_KEYS | _FALLBACK_KEYS | _EXACT_ENDPOINT_KEYS,
    )
    if any(
        _contains_named_key(section, _AUTHORITY_KEYS)
        for section in authority_without_deferred_keys.values()
    ):
        _failure(
            OpenRouterRouteControlFailureCodeV1.UNKNOWN_FIELD_AUTHORITY_OVERRIDE,
            OpenRouterRouteControlGuardV1.METADATA_SCHEMA,
            raw_digest,
        )

    if _contains_named_key(envelope, _CACHE_KEYS):
        cache_code = (
            OpenRouterRouteControlFailureCodeV1.CACHE_AFFECTED_METADATA_UNAVAILABLE
            if next(_iter_named_values(envelope, frozenset({"cache_state"})), None)
            == "HIT_METADATA_UNAVAILABLE"
            else OpenRouterRouteControlFailureCodeV1.CACHE_AFFECTED_OR_UNATTESTED
        )
        _failure(
            cache_code,
            OpenRouterRouteControlGuardV1.CACHE_METADATA_AVAILABILITY,
            raw_digest,
        )

    if "attempt" not in metadata:
        _failure(
            OpenRouterRouteControlFailureCodeV1.ATTEMPT_MISSING,
            OpenRouterRouteControlGuardV1.ATTEMPT_PRESENT_AND_VALID,
            raw_digest,
        )
    attempt = metadata["attempt"]
    if type(attempt) is not int or attempt <= 0:
        _failure(
            OpenRouterRouteControlFailureCodeV1.ATTEMPT_INVALID,
            OpenRouterRouteControlGuardV1.ATTEMPT_PRESENT_AND_VALID,
            raw_digest,
        )
    if attempt != 1:
        _failure(
            OpenRouterRouteControlFailureCodeV1.MULTI_ATTEMPT_ROUTING_OBSERVED,
            OpenRouterRouteControlGuardV1.ATTEMPT_EQUALS_ONE,
            raw_digest,
        )

    if "actual_model" not in metadata or metadata["actual_model"] in (None, ""):
        _failure(
            OpenRouterRouteControlFailureCodeV1.ACTUAL_MODEL_MISSING,
            OpenRouterRouteControlGuardV1.ACTUAL_MODEL_PRESENCE,
            raw_digest,
        )
    actual_model = metadata["actual_model"]
    if not isinstance(actual_model, str) or actual_model != OPENROUTER_ROUTE_MODEL_V1:
        _failure(
            OpenRouterRouteControlFailureCodeV1.ACTUAL_MODEL_MISMATCH,
            OpenRouterRouteControlGuardV1.ACTUAL_MODEL_MATCH,
            raw_digest,
        )

    if "provider" not in metadata or metadata["provider"] in (None, ""):
        _failure(
            OpenRouterRouteControlFailureCodeV1.PROVIDER_MISSING,
            OpenRouterRouteControlGuardV1.PROVIDER_PRESENCE,
            raw_digest,
        )
    provider = metadata["provider"]
    provider_is_forbidden_endpoint_claim = (
        provider == OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
    )
    if not isinstance(provider, str) or (
        provider != EXPECTED_BROAD_PROVIDER_V1
        and not provider_is_forbidden_endpoint_claim
    ):
        _failure(
            OpenRouterRouteControlFailureCodeV1.PROVIDER_MISMATCH,
            OpenRouterRouteControlGuardV1.PROVIDER_COMPATIBILITY,
            raw_digest,
        )

    attempts_status = AttemptsListStatusV1.ABSENT_ACCEPTED
    if "attempts" in metadata:
        attempts = metadata["attempts"]
        if not isinstance(attempts, list):
            _failure(
                OpenRouterRouteControlFailureCodeV1.ATTEMPTS_LIST_MALFORMED,
                OpenRouterRouteControlGuardV1.ATTEMPTS_LIST_CONSISTENCY,
                raw_digest,
            )
        if len(attempts) > 1:
            _failure(
                OpenRouterRouteControlFailureCodeV1.MULTIPLE_ATTEMPTS_REPORTED,
                OpenRouterRouteControlGuardV1.ATTEMPTS_LIST_CONSISTENCY,
                raw_digest,
            )
        if len(attempts) != 1:
            _failure(
                OpenRouterRouteControlFailureCodeV1.ATTEMPTS_LIST_INCONSISTENT,
                OpenRouterRouteControlGuardV1.ATTEMPTS_LIST_CONSISTENCY,
                raw_digest,
            )
        entry = attempts[0]
        if (
            not isinstance(entry, dict)
            or entry.get("attempt") != attempt
            or type(entry.get("attempt")) is not int
            or entry.get("model") != actual_model
            or entry.get("provider") != provider
            or entry.get("outcome") != "success"
        ):
            _failure(
                OpenRouterRouteControlFailureCodeV1.ATTEMPTS_LIST_INCONSISTENT,
                OpenRouterRouteControlGuardV1.ATTEMPTS_LIST_CONSISTENCY,
                raw_digest,
            )
        attempts_status = AttemptsListStatusV1.PRESENT_CONSISTENT

    fallback_observed = metadata.get("fallback_observed", False)
    pipeline = metadata.get("pipeline", [])
    if type(fallback_observed) is not bool or fallback_observed or _contains_named_key(
        opaque, _FALLBACK_KEYS
    ):
        _failure(
            OpenRouterRouteControlFailureCodeV1.FALLBACK_INDICATOR_OBSERVED,
            OpenRouterRouteControlGuardV1.FALLBACK_INDICATORS_ABSENT,
            raw_digest,
        )
    if not isinstance(pipeline, list):
        _failure(
            OpenRouterRouteControlFailureCodeV1.FORBIDDEN_PIPELINE_STAGE,
            OpenRouterRouteControlGuardV1.FALLBACK_INDICATORS_ABSENT,
            raw_digest,
        )
    if any(
        not isinstance(stage, dict)
        or stage.get("stage") == "fallback"
        or _contains_named_key(stage, _FALLBACK_KEYS)
        for stage in pipeline
    ):
        _failure(
            OpenRouterRouteControlFailureCodeV1.FORBIDDEN_PIPELINE_STAGE,
            OpenRouterRouteControlGuardV1.FALLBACK_INDICATORS_ABSENT,
            raw_digest,
        )

    if strategy != "direct":
        _failure(
            OpenRouterRouteControlFailureCodeV1.FALLBACK_INDICATOR_OBSERVED,
            OpenRouterRouteControlGuardV1.FALLBACK_INDICATORS_ABSENT,
            raw_digest,
        )

    if provider_is_forbidden_endpoint_claim or _contains_named_key(
        opaque, _EXACT_ENDPOINT_KEYS
    ):
        _failure(
            OpenRouterRouteControlFailureCodeV1.FALSE_EXACT_ENDPOINT_CLAIM,
            OpenRouterRouteControlGuardV1.NO_FALSE_EXACT_ENDPOINT_ATTESTATION,
            raw_digest,
        )

    if type(prepared_request) is not OpenRouterPreparedRouteRequestV1:
        _failure(
            OpenRouterRouteControlFailureCodeV1.RECEIPT_INTEGRITY_FAILURE,
            OpenRouterRouteControlGuardV1.RECEIPT_AND_CLAIMS_INTEGRITY,
            raw_digest,
        )
    try:
        validated_prepared = OpenRouterPreparedRouteRequestV1.model_validate(
            prepared_request.model_dump(mode="json")
        )
    except (TypeError, ValueError, AttributeError):
        _failure(
            OpenRouterRouteControlFailureCodeV1.RECEIPT_INTEGRITY_FAILURE,
            OpenRouterRouteControlGuardV1.RECEIPT_AND_CLAIMS_INTEGRITY,
            raw_digest,
        )
    if validated_prepared != prepared_request:
        _failure(
            OpenRouterRouteControlFailureCodeV1.RECEIPT_INTEGRITY_FAILURE,
            OpenRouterRouteControlGuardV1.RECEIPT_AND_CLAIMS_INTEGRITY,
            raw_digest,
        )

    opaque_digest = hashlib.sha256(canonical_json(opaque).encode("utf-8")).hexdigest()
    try:
        raw_evidence = OpenRouterRawResponseEvidenceV1(
            raw_response_json=raw_text,
            raw_response_sha256=raw_digest,
            raw_response_length=len(raw_response_bytes),
        )
        metadata_receipt = OpenRouterRouterMetadataReceiptV1(
            raw_response_evidence_id=raw_evidence.evidence_id,
            raw_response_sha256=raw_digest,
            attempts_list_status=attempts_status,
            routing_strategy_summary=strategy,
            unknown_fields_sha256=opaque_digest,
            unknown_field_count=sum(
                _unknown_field_count(section) for section in opaque.values()
            ),
        )
        attestation = OpenRouterRouteAttestationV1(
            metadata_receipt_id=metadata_receipt.receipt_id,
            route_intent_id=validated_prepared.route_intent_id,
            request_intent_receipt_id=(
                validated_prepared.request_intent_receipt.receipt_id
            ),
        )
        return OpenRouterRouteControlReceiptV1(
            route_intent_id=validated_prepared.route_intent_id,
            request_intent_receipt_id=(
                validated_prepared.request_intent_receipt.receipt_id
            ),
            raw_response=raw_evidence,
            metadata_receipt=metadata_receipt,
            route_attestation=attestation,
        )
    except (TypeError, ValueError, AttributeError):
        _failure(
            OpenRouterRouteControlFailureCodeV1.RECEIPT_INTEGRITY_FAILURE,
            OpenRouterRouteControlGuardV1.RECEIPT_AND_CLAIMS_INTEGRITY,
            raw_digest,
        )


def _remove_keys(value: object, names: frozenset[str]) -> object:
    if isinstance(value, dict):
        return {
            key: _remove_keys(nested, names)
            for key, nested in value.items()
            if key not in names
        }
    if isinstance(value, list):
        return [_remove_keys(nested, names) for nested in value]
    return value


parse_openrouter_route_controls_response_v1 = parse_openrouter_router_metadata_v1


__all__ = [
    "EXPECTED_BROAD_PROVIDER_V1",
    "NORMALIZED_CANNED_RESPONSE_SCHEMA_VERSION",
    "RAW_RESPONSE_EVIDENCE_SCHEMA_VERSION",
    "ROUTER_METADATA_PARSER_SCHEMA_VERSION",
    "ROUTER_METADATA_RECEIPT_SCHEMA_VERSION",
    "ROUTE_ATTESTATION_SCHEMA_VERSION",
    "ROUTE_CONTROL_RECEIPT_SCHEMA_VERSION",
    "AttemptsListStatusV1",
    "OpenRouterRawResponseEvidenceV1",
    "OpenRouterRouteAttestationV1",
    "OpenRouterRouteControlFailureCodeV1",
    "OpenRouterRouteControlGuardV1",
    "OpenRouterRouteControlParserError",
    "OpenRouterRouteControlReceiptV1",
    "OpenRouterRouterMetadataReceiptV1",
    "ProviderAttestationGranularityV1",
    "build_reference_openrouter_route_response_v1",
    "parse_openrouter_route_controls_response_v1",
    "parse_openrouter_router_metadata_v1",
]
