"""Offline contracts for bounded OpenRouter wire-specification source evidence.

This module is import-inert and has no transport implementation.  It freezes the
Phase 8.5D-S public-source plan, retrieval limits, canonicalization policy, and
content-addressed retrieval/snapshot receipts before any documentation fetch.
It does not parse provider responses and has no credential, provider, model,
tool, CED, adapter, or runtime integration.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from enum import Enum
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import Dict, Iterable, Literal, Optional, Tuple
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id


OPENROUTER_WIRE_SOURCE_PLAN_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-source-plan/v1"
)
OPENROUTER_WIRE_SOURCE_PLAN_RECORD_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-source-plan-record/v1"
)
OPENROUTER_WIRE_RETRIEVAL_POLICY_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-retrieval-policy/v1"
)
OPENROUTER_WIRE_CANONICALIZATION_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-source-canonicalization/v1"
)
OPENROUTER_WIRE_RETRIEVAL_EVENT_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-retrieval-event/v1"
)
OPENROUTER_WIRE_RETRIEVAL_LOG_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-retrieval-log/v1"
)
OPENROUTER_WIRE_RETAINED_SNAPSHOT_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-retained-source-snapshot/v1"
)
OPENROUTER_WIRE_RAW_FRAGMENT_SCHEMA_V1 = (
    "socrateszero-openrouter-wire-raw-fragment-range/v1"
)

OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "evidence/openrouter_wire_source_plan_v1.json"
)
OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "evidence/openrouter_wire_retrieval_log_v1.json"
)
OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v1/"
    "evidence/sources"
)

OPENROUTER_WIRE_SPECIFICATION_HYPOTHESIS_V1 = (
    "Current official OpenRouter public sources contain sufficient exact "
    "response-schema evidence to build a content-addressed manifest in which "
    "every future authoritative normalized field is linked to an official "
    "source path, JSON type, presence rule, nullability rule, envelope kind, "
    "semantic meaning and either a directly documented or demonstrably "
    "lossless mapping."
)


class _FrozenSourceContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterWireSourceClassV1(str, Enum):
    OPENAPI = "OFFICIAL_OPENROUTER_PUBLIC_OPENAPI_SCHEMA"
    ROUTER_METADATA = "OFFICIAL_OPENROUTER_ROUTER_METADATA_DOCUMENTATION"
    CHAT_REFERENCE = "OFFICIAL_OPENROUTER_CHAT_REFERENCE"
    CACHE = "OFFICIAL_OPENROUTER_RESPONSE_CACHE_DOCUMENTATION"
    PROVIDER_ROUTING = "OFFICIAL_OPENROUTER_PROVIDER_ROUTING_DOCUMENTATION"
    MODEL_FALLBACKS = "OFFICIAL_OPENROUTER_MODEL_FALLBACK_DOCUMENTATION"


class OpenRouterWireSourceStabilityV1(str, Enum):
    PROTOCOL_SCHEMA = "PROTOCOL_SCHEMA"
    DOCUMENTED_BEHAVIOR = "DOCUMENTED_BEHAVIOR"
    MUTABLE_METADATA = "MUTABLE_METADATA"


class OpenRouterWireExtractFormatV1(str, Enum):
    OPENAPI_YAML_COMPONENTS = "OPENAPI_YAML_COMPONENTS"
    MARKDOWN_SECTIONS = "MARKDOWN_SECTIONS"
    HTML_VISIBLE_SECTIONS = "HTML_VISIBLE_SECTIONS"
    JSON = "JSON"


class OpenRouterWireRetrievalStatusV1(str, Enum):
    RETAINED = "RETAINED"
    FETCH_FAILED = "FETCH_FAILED"
    REDIRECT_REJECTED = "REDIRECT_REJECTED"
    STATUS_REJECTED = "STATUS_REJECTED"
    MEDIA_TYPE_REJECTED = "MEDIA_TYPE_REJECTED"
    SIZE_REJECTED = "SIZE_REJECTED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class OpenRouterWireRetrievalErrorCodeV1(str, Enum):
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    TLS_ERROR = "TLS_ERROR"
    REDIRECT_POLICY_REJECTED = "REDIRECT_POLICY_REJECTED"
    HTTP_STATUS_REJECTED = "HTTP_STATUS_REJECTED"
    MEDIA_TYPE_REJECTED = "MEDIA_TYPE_REJECTED"
    SOURCE_SIZE_REJECTED = "SOURCE_SIZE_REJECTED"
    TOTAL_SIZE_REJECTED = "TOTAL_SIZE_REJECTED"
    STRICT_UTF8_REJECTED = "STRICT_UTF8_REJECTED"
    REQUIRED_EXTRACTION_FAILED = "REQUIRED_EXTRACTION_FAILED"
    CANONICALIZATION_FAILED = "CANONICALIZATION_FAILED"


def _validate_official_locator(locator: str, allowed_domains: Tuple[str, ...]) -> str:
    parsed = urlsplit(locator)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in allowed_domains
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        raise ContractValidationError("source locator is not an allowed canonical URL")
    return locator


def _strict_json_object_pairs(
    pairs: Iterable[Tuple[str, object]],
) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractValidationError("duplicate JSON member in source extract")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> None:
    raise ContractValidationError("non-finite JSON value in source extract")


def _normalize_json_value(value: object) -> object:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, dict):
        normalized: Dict[str, object] = {}
        for key, item in value.items():
            normalized_key = unicodedata.normalize("NFC", key)
            if normalized_key in normalized:
                raise ContractValidationError(
                    "JSON members collide after Unicode normalization"
                )
            normalized[normalized_key] = _normalize_json_value(item)
        return normalized
    return value


def _validate_utc_timestamp(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ContractValidationError("timestamp is not strict UTC second precision") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ContractValidationError("timestamp is not canonical UTC")
    return value


def _validate_retained_evidence_path(value: str) -> str:
    if "\\" in value:
        raise ContractValidationError("retained evidence path is not POSIX relative")
    path = PurePosixPath(value)
    required_root = PurePosixPath(OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1)
    if (
        value != path.as_posix()
        or path.is_absolute()
        or ".." in path.parts
        or path == required_root
        or path.parts[: len(required_root.parts)] != required_root.parts
    ):
        raise ContractValidationError("retained evidence path escapes its frozen root")
    return value


def _parse_media_type_header_v1(value: str) -> str:
    if not value or "\r" in value or "\n" in value:
        raise ContractValidationError("Content-Type header is empty or unsafe")
    base = value.split(";", 1)[0].strip().lower()
    if not re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", base):
        raise ContractValidationError("Content-Type header has no valid base media type")
    return base


class _VisibleHTMLExtractorV1(HTMLParser):
    _excluded = frozenset(("script", "style", "noscript", "nav", "svg"))
    _blocks = frozenset(
        (
            "article",
            "aside",
            "blockquote",
            "br",
            "dd",
            "div",
            "dl",
            "dt",
            "figcaption",
            "figure",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "header",
            "hr",
            "li",
            "main",
            "ol",
            "p",
            "pre",
            "section",
            "table",
            "tbody",
            "td",
            "th",
            "thead",
            "tr",
            "ul",
        )
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._excluded_depth = 0
        self._parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, Optional[str]]],
    ) -> None:
        del attrs
        normalized = tag.lower()
        if normalized in self._excluded:
            self._excluded_depth += 1
        elif not self._excluded_depth and normalized in self._blocks:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        if normalized in self._excluded:
            if self._excluded_depth:
                self._excluded_depth -= 1
        elif not self._excluded_depth and normalized in self._blocks:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._excluded_depth:
            self._parts.append(data)

    def visible_text(self) -> str:
        lines: list[str] = []
        for line in "".join(self._parts).splitlines():
            collapsed = re.sub(r"[\t\f\v ]+", " ", line).strip()
            if collapsed:
                lines.append(collapsed)
        return "\n".join(lines)


class OpenRouterWireCanonicalizationPolicyV1(_FrozenSourceContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_CANONICALIZATION_SCHEMA_V1
    ] = OPENROUTER_WIRE_CANONICALIZATION_SCHEMA_V1
    policy_id: Optional[str] = None
    input_encoding: Literal["UTF-8_STRICT"] = "UTF-8_STRICT"
    unicode_normalization: Literal["NFC"] = "NFC"
    newline_policy: Literal["CRLF_AND_CR_TO_LF"] = "CRLF_AND_CR_TO_LF"
    trailing_horizontal_whitespace: Literal["PRESERVE"] = "PRESERVE"
    boundary_blank_lines: Literal["REMOVE"] = "REMOVE"
    terminal_newline: Literal["EXACTLY_ONE_LF"] = "EXACTLY_ONE_LF"
    json_key_order: Literal["SORT_LEXICOGRAPHIC"] = "SORT_LEXICOGRAPHIC"
    yaml_key_order: Literal["PRESERVE_SOURCE_ORDER"] = "PRESERVE_SOURCE_ORDER"
    html_policy: Literal[
        "VISIBLE_TEXT_FROM_PREDECLARED_SECTIONS_ONLY"
    ] = "VISIBLE_TEXT_FROM_PREDECLARED_SECTIONS_ONLY"
    html_whitespace_policy: Literal[
        "COLLAPSE_RENDERED_HORIZONTAL_RUNS_AND_EMPTY_LINES"
    ] = "COLLAPSE_RENDERED_HORIZONTAL_RUNS_AND_EMPTY_LINES"
    volatile_elements: Tuple[str, ...] = (
        "script",
        "style",
        "noscript",
        "nav",
        "svg",
    )
    duplicate_json_members: Literal["REJECT"] = "REJECT"
    invalid_utf8_or_content: Literal["REJECT"] = "REJECT"
    semantic_token_rewriting: Literal[False] = False

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterWireCanonicalizationPolicyV1":
        expected = stable_contract_id(
            "szorwirecanonv1",
            self.model_dump(mode="json", exclude={"policy_id"}),
        )
        if self.policy_id not in (None, expected):
            raise ContractValidationError("canonicalization policy ID mismatch")
        object.__setattr__(self, "policy_id", expected)
        return self


FROZEN_OPENROUTER_WIRE_CANONICALIZATION_POLICY_V1 = (
    OpenRouterWireCanonicalizationPolicyV1()
)


def canonicalize_openrouter_wire_extract_v1(
    raw_extract: bytes,
    extract_format: OpenRouterWireExtractFormatV1,
) -> bytes:
    """Canonicalize one already bounded, relevant source extract."""

    if type(raw_extract) is not bytes or not raw_extract:
        raise ContractValidationError("source extract must be non-empty bytes")
    try:
        text = raw_extract.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractValidationError("source extract is not strict UTF-8") from exc
    if "\x00" in text:
        raise ContractValidationError("source extract contains NUL")
    if extract_format is OpenRouterWireExtractFormatV1.JSON:
        try:
            parsed = json.loads(
                text,
                object_pairs_hook=_strict_json_object_pairs,
                parse_constant=_reject_json_constant,
            )
            canonical = canonical_json(_normalize_json_value(parsed))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ContractValidationError("source JSON extract is invalid") from exc
        return (canonical + "\n").encode("utf-8")
    normalized = unicodedata.normalize(
        "NFC", text.replace("\r\n", "\n").replace("\r", "\n")
    )
    if extract_format is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS:
        parser = _VisibleHTMLExtractorV1()
        try:
            parser.feed(normalized)
            parser.close()
        except Exception as exc:
            raise ContractValidationError("source HTML extract is invalid") from exc
        if parser._excluded_depth:
            raise ContractValidationError("source HTML extract has an unclosed excluded tag")
        normalized = unicodedata.normalize("NFC", parser.visible_text())
    lines = normalized.split("\n")
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        raise ContractValidationError("canonical source extract is empty")
    return ("\n".join(lines) + "\n").encode("utf-8")


class OpenRouterWireRetrievalPolicyV1(_FrozenSourceContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_RETRIEVAL_POLICY_SCHEMA_V1
    ] = OPENROUTER_WIRE_RETRIEVAL_POLICY_SCHEMA_V1
    policy_id: Optional[str] = None
    allowed_official_domains: Tuple[Literal["openrouter.ai"], ...] = (
        "openrouter.ai",
    )
    maximum_official_document_fetches: Literal[6] = 6
    maximum_public_page_inspections: Literal[0] = 0
    maximum_redirects_per_source: Literal[1] = 1
    redirect_policy: Literal[
        "SAME_ORIGIN_HTTPS_ONLY_OTHERWISE_FAIL_CLOSED"
    ] = "SAME_ORIGIN_HTTPS_ONLY_OTHERWISE_FAIL_CLOSED"
    maximum_response_bytes_per_source: Literal[8388608] = 8_388_608
    maximum_total_response_bytes: Literal[20971520] = 20_971_520
    total_retained_evidence_byte_cap: Literal[1048576] = 1_048_576
    retrieval_timeout_seconds: Literal[20] = 20
    retry_count: Literal[0] = 0
    authenticated_requests: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    provider_inference_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    paid_requests: Literal[0] = 0
    ced_runtime_tool_calls: Literal[0] = 0

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterWireRetrievalPolicyV1":
        if tuple(sorted(self.allowed_official_domains)) != self.allowed_official_domains:
            raise ContractValidationError("official source domains are not canonical")
        expected = stable_contract_id(
            "szorwireretrievalpolicyv1",
            self.model_dump(mode="json", exclude={"policy_id"}),
        )
        if self.policy_id not in (None, expected):
            raise ContractValidationError("retrieval policy ID mismatch")
        object.__setattr__(self, "policy_id", expected)
        return self


FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1 = OpenRouterWireRetrievalPolicyV1()


class OpenRouterWireSourcePlanRecordV1(_FrozenSourceContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_SOURCE_PLAN_RECORD_SCHEMA_V1
    ] = OPENROUTER_WIRE_SOURCE_PLAN_RECORD_SCHEMA_V1
    plan_record_id: Optional[str] = None
    source_key: str = Field(pattern=r"^ORWIRE-S0[1-9]-[A-Z0-9-]+$")
    source_class: OpenRouterWireSourceClassV1
    source_role: str = Field(min_length=1)
    canonical_public_locator: str
    expected_media_types: Tuple[str, ...]
    expected_evidence_scope: Tuple[str, ...]
    retrieval_method: Literal[
        "HTTPS_GET_PUBLIC_UNAUTHENTICATED"
    ] = "HTTPS_GET_PUBLIC_UNAUTHENTICATED"
    required_anchors: Tuple[str, ...]
    extract_format: OpenRouterWireExtractFormatV1
    stability: OpenRouterWireSourceStabilityV1
    revalidation_trigger: str = Field(min_length=1)
    expiry_rule: str = Field(min_length=1)
    drift_behavior: Literal["FAIL_CLOSED"] = "FAIL_CLOSED"
    missing_source_behavior: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    limitations: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireSourcePlanRecordV1":
        _validate_official_locator(
            self.canonical_public_locator,
            FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.allowed_official_domains,
        )
        tuple_fields = (
            self.expected_media_types,
            self.expected_evidence_scope,
            self.required_anchors,
        )
        if any(not values or len(values) != len(set(values)) for values in tuple_fields):
            raise ContractValidationError("source-plan tuple is empty or duplicated")
        expected = stable_contract_id(
            "szorwiresourceplanrecordv1",
            self.model_dump(mode="json", exclude={"plan_record_id"}),
        )
        if self.plan_record_id not in (None, expected):
            raise ContractValidationError("source-plan record ID mismatch")
        object.__setattr__(self, "plan_record_id", expected)
        return self


FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_RECORDS_V1 = (
    OpenRouterWireSourcePlanRecordV1(
        source_key="ORWIRE-S01-OPENAPI",
        source_class=OpenRouterWireSourceClassV1.OPENAPI,
        source_role="Typed response metadata, child schemas, and response envelopes",
        canonical_public_locator="https://openrouter.ai/openapi.yaml",
        expected_media_types=("application/yaml", "text/yaml", "text/plain"),
        expected_evidence_scope=(
            "OpenRouterMetadata",
            "EndpointInfo",
            "RouterAttempt",
            "PipelineStage",
            "chat completions success and error schemas",
        ),
        required_anchors=(
            "OpenRouterMetadata",
            "EndpointInfo",
            "RouterAttempt",
            "PipelineStage",
            "/chat/completions",
        ),
        extract_format=OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS,
        stability=OpenRouterWireSourceStabilityV1.PROTOCOL_SCHEMA,
        revalidation_trigger="ON_OPENAPI_RESPONSE_DIGEST_CHANGE",
        expiry_rule="FAIL_CLOSED_AFTER_UNVERIFIED_SCHEMA_DRIFT",
        limitations="A schema may omit behavioral invariants required by the future route attestation.",
    ),
    OpenRouterWireSourcePlanRecordV1(
        source_key="ORWIRE-S02-ROUTER-METADATA",
        source_class=OpenRouterWireSourceClassV1.ROUTER_METADATA,
        source_role="Router metadata placement, fields, cache/error behavior, and stability",
        canonical_public_locator="https://openrouter.ai/docs/guides/features/router-metadata.md",
        expected_media_types=("text/markdown", "text/plain"),
        expected_evidence_scope=(
            "metadata opt-in and placement",
            "field semantics",
            "pipeline",
            "cache hits",
            "error responses",
            "stability and additive fields",
        ),
        required_anchors=(
            "Enabling Router Metadata",
            "Field Reference",
            "Pipeline",
            "Cache Hits",
            "Error Responses",
            "Stability",
        ),
        extract_format=OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS,
        stability=OpenRouterWireSourceStabilityV1.DOCUMENTED_BEHAVIOR,
        revalidation_trigger="ON_ROUTER_METADATA_DOCUMENT_DIGEST_CHANGE",
        expiry_rule="FAIL_CLOSED_AFTER_UNVERIFIED_DOCUMENT_DRIFT",
        limitations="Documentation prose cannot supply a JSON type or invariant absent from a typed schema.",
    ),
    OpenRouterWireSourcePlanRecordV1(
        source_key="ORWIRE-S03-CHAT-REFERENCE",
        source_class=OpenRouterWireSourceClassV1.CHAT_REFERENCE,
        source_role="Chat Completions success/error envelope and served-model fields",
        canonical_public_locator=(
            "https://openrouter.ai/docs/api/api-reference/chat/"
            "send-chat-completion-request.md"
        ),
        expected_media_types=("text/markdown", "text/plain"),
        expected_evidence_scope=(
            "success response envelope",
            "error response envelope",
            "served model",
            "choices and usage",
        ),
        required_anchors=("Responses", "ChatResult", "model", "error"),
        extract_format=OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS,
        stability=OpenRouterWireSourceStabilityV1.PROTOCOL_SCHEMA,
        revalidation_trigger="ON_CHAT_REFERENCE_DIGEST_CHANGE",
        expiry_rule="FAIL_CLOSED_AFTER_UNVERIFIED_SCHEMA_DRIFT",
        limitations="Generated reference prose may not define every error union or metadata placement.",
    ),
    OpenRouterWireSourcePlanRecordV1(
        source_key="ORWIRE-S04-RESPONSE-CACHE",
        source_class=OpenRouterWireSourceClassV1.CACHE,
        source_role="Response-cache request intent, response headers, and metadata omission",
        canonical_public_locator="https://openrouter.ai/docs/guides/features/response-caching",
        expected_media_types=("text/html",),
        expected_evidence_scope=(
            "cache disable request intent",
            "cache status response headers",
            "cache-hit metadata omission",
        ),
        required_anchors=(
            "Request and Response Headers",
            "Cache Hits",
            "X-OpenRouter-Cache",
        ),
        extract_format=OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS,
        stability=OpenRouterWireSourceStabilityV1.DOCUMENTED_BEHAVIOR,
        revalidation_trigger="ON_RESPONSE_CACHE_DOCUMENT_DIGEST_CHANGE",
        expiry_rule="FAIL_CLOSED_AFTER_UNVERIFIED_DOCUMENT_DRIFT",
        limitations="Response caching is distinct from provider prompt caching.",
    ),
    OpenRouterWireSourcePlanRecordV1(
        source_key="ORWIRE-S05-PROVIDER-ROUTING",
        source_class=OpenRouterWireSourceClassV1.PROVIDER_ROUTING,
        source_role="Provider selector and identity-granularity terminology",
        canonical_public_locator="https://openrouter.ai/docs/guides/routing/provider-selection.md",
        expected_media_types=("text/markdown", "text/plain"),
        expected_evidence_scope=(
            "specific endpoint selectors",
            "base provider slugs",
            "only and fallback request controls",
        ),
        required_anchors=(
            "Specific Endpoints",
            "Base Slugs",
            "Only",
            "Disabling Fallbacks",
        ),
        extract_format=OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS,
        stability=OpenRouterWireSourceStabilityV1.DOCUMENTED_BEHAVIOR,
        revalidation_trigger="ON_PROVIDER_ROUTING_DOCUMENT_DIGEST_CHANGE",
        expiry_rule="FAIL_CLOSED_AFTER_UNVERIFIED_DOCUMENT_DRIFT",
        limitations="Request selector terminology does not by itself define response provider granularity.",
    ),
    OpenRouterWireSourcePlanRecordV1(
        source_key="ORWIRE-S06-MODEL-FALLBACKS",
        source_class=OpenRouterWireSourceClassV1.MODEL_FALLBACKS,
        source_role="Model-fallback ordering and fallback-behavior terminology",
        canonical_public_locator=(
            "https://openrouter.ai/docs/guides/routing/model-fallbacks"
        ),
        expected_media_types=("text/html",),
        expected_evidence_scope=(
            "model fallback order",
            "fallback behavior after model or provider failure",
        ),
        required_anchors=("How It Works", "Fallback Behavior"),
        extract_format=OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS,
        stability=OpenRouterWireSourceStabilityV1.DOCUMENTED_BEHAVIOR,
        revalidation_trigger="ON_MODEL_FALLBACK_DOCUMENT_DIGEST_CHANGE",
        expiry_rule="FAIL_CLOSED_AFTER_UNVERIFIED_DOCUMENT_DRIFT",
        limitations=(
            "Request fallback behavior cannot by itself prove response attempt "
            "cardinality, ordering, or identity semantics."
        ),
    ),
)


class OpenRouterWireSourcePlanV1(_FrozenSourceContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_SOURCE_PLAN_SCHEMA_V1
    ] = OPENROUTER_WIRE_SOURCE_PLAN_SCHEMA_V1
    source_plan_id: Optional[str] = None
    hypothesis: Literal[
        OPENROUTER_WIRE_SPECIFICATION_HYPOTHESIS_V1
    ] = OPENROUTER_WIRE_SPECIFICATION_HYPOTHESIS_V1
    retrieval_policy: OpenRouterWireRetrievalPolicyV1 = (
        FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1
    )
    canonicalization_policy: OpenRouterWireCanonicalizationPolicyV1 = (
        FROZEN_OPENROUTER_WIRE_CANONICALIZATION_POLICY_V1
    )
    source_records: Tuple[OpenRouterWireSourcePlanRecordV1, ...] = (
        FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_RECORDS_V1
    )
    no_silent_source_substitution: Literal[True] = True
    missing_or_ambiguous_evidence: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireSourcePlanV1":
        if len(self.source_records) != self.retrieval_policy.maximum_official_document_fetches:
            raise ContractValidationError("planned sources must equal the fetch limit")
        keys = tuple(item.source_key for item in self.source_records)
        locators = tuple(item.canonical_public_locator for item in self.source_records)
        if len(set(keys)) != len(keys) or len(set(locators)) != len(locators):
            raise ContractValidationError("source plan keys or locators are duplicated")
        expected = stable_contract_id(
            "szorwiresourceplanv1",
            self.model_dump(mode="json", exclude={"source_plan_id"}),
        )
        if self.source_plan_id not in (None, expected):
            raise ContractValidationError("source-plan ID mismatch")
        object.__setattr__(self, "source_plan_id", expected)
        return self


FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1 = OpenRouterWireSourcePlanV1()


class OpenRouterWireRedirectOutcomeV1(str, Enum):
    FOLLOWED_SAME_ORIGIN_HTTPS = "FOLLOWED_SAME_ORIGIN_HTTPS"
    REJECTED_BY_POLICY = "REJECTED_BY_POLICY"


class OpenRouterWireRedirectHopV1(_FrozenSourceContractV1):
    schema_version: Literal[
        "socrateszero-openrouter-wire-redirect-hop/v1"
    ] = "socrateszero-openrouter-wire-redirect-hop/v1"
    redirect_hop_id: Optional[str] = None
    ordinal: int = Field(ge=1)
    source_locator: str
    http_status: Literal[301, 302, 303, 307, 308]
    target_locator: str
    outcome: Optional[OpenRouterWireRedirectOutcomeV1] = None

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireRedirectHopV1":
        _validate_official_locator(
            self.source_locator,
            FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.allowed_official_domains,
        )
        try:
            parsed = urlsplit(self.target_locator)
            target_port = parsed.port
        except ValueError as exc:
            raise ContractValidationError("redirect target is malformed") from exc
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or target_port is not None and not 1 <= target_port <= 65535
            or "\r" in self.target_locator
            or "\n" in self.target_locator
        ):
            raise ContractValidationError("redirect target is malformed or unsafe")
        try:
            _validate_official_locator(
                self.target_locator,
                FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.allowed_official_domains,
            )
        except ContractValidationError:
            expected_outcome = OpenRouterWireRedirectOutcomeV1.REJECTED_BY_POLICY
        else:
            expected_outcome = (
                OpenRouterWireRedirectOutcomeV1.FOLLOWED_SAME_ORIGIN_HTTPS
            )
        if self.outcome not in (None, expected_outcome):
            raise ContractValidationError("redirect outcome contradicts policy")
        object.__setattr__(self, "outcome", expected_outcome)
        expected_id = stable_contract_id(
            "szorwireredirecthopv1",
            self.model_dump(mode="json", exclude={"redirect_hop_id"}),
        )
        if self.redirect_hop_id not in (None, expected_id):
            raise ContractValidationError("redirect-hop ID mismatch")
        object.__setattr__(self, "redirect_hop_id", expected_id)
        return self


def _validate_redirect_chain_v1(
    planned_locator: str,
    hops: Tuple[OpenRouterWireRedirectHopV1, ...],
) -> Tuple[str, bool]:
    if len(hops) > FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.maximum_redirects_per_source:
        raise ContractValidationError("retrieval redirect limit exceeded")
    expected_source = planned_locator
    seen = {planned_locator}
    rejected = False
    for ordinal, hop in enumerate(hops, start=1):
        if hop.ordinal != ordinal or hop.source_locator != expected_source or rejected:
            raise ContractValidationError("redirect chain is not contiguous and canonical")
        if hop.target_locator in seen:
            raise ContractValidationError("redirect chain contains a loop")
        seen.add(hop.target_locator)
        if hop.outcome is OpenRouterWireRedirectOutcomeV1.REJECTED_BY_POLICY:
            rejected = True
        else:
            expected_source = hop.target_locator
    return expected_source, rejected


class OpenRouterWireRawFragmentRangeV1(_FrozenSourceContractV1):
    """One exact contiguous byte range copied from an HTTP response body."""

    schema_version: Literal[
        OPENROUTER_WIRE_RAW_FRAGMENT_SCHEMA_V1
    ] = OPENROUTER_WIRE_RAW_FRAGMENT_SCHEMA_V1
    fragment_id: Optional[str] = None
    ordinal: int = Field(ge=1)
    source_byte_start: int = Field(ge=0)
    source_byte_end_exclusive: int = Field(ge=1)
    retained_byte_start: int = Field(ge=0)
    retained_byte_end_exclusive: int = Field(ge=1)
    byte_length: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireRawFragmentRangeV1":
        if (
            self.source_byte_end_exclusive - self.source_byte_start
            != self.byte_length
            or self.retained_byte_end_exclusive - self.retained_byte_start
            != self.byte_length
        ):
            raise ContractValidationError("raw fragment range length mismatch")
        expected = stable_contract_id(
            "szorwirerawfragmentv1",
            self.model_dump(mode="json", exclude={"fragment_id"}),
        )
        if self.fragment_id not in (None, expected):
            raise ContractValidationError("raw fragment ID mismatch")
        object.__setattr__(self, "fragment_id", expected)
        return self


def _validate_full_source_structure_v1(
    response_content: bytes,
    extract_format: OpenRouterWireExtractFormatV1,
) -> None:
    try:
        text = response_content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractValidationError("official source response is not strict UTF-8") from exc
    if extract_format is OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS:
        required_roots = (r"(?m)^openapi:\s*3\.", r"(?m)^paths:\s*$", r"(?m)^components:\s*$")
        if not all(re.search(pattern, text) for pattern in required_roots):
            raise ContractValidationError("OpenAPI YAML response lacks required root structure")
    elif extract_format is OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS:
        if not re.search(r"(?m)^#{1,6}[ \t]+\S", text):
            raise ContractValidationError("Markdown response has no document heading")
    elif extract_format is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS:
        if not re.search(r"(?is)<(?:html|main|article|section|h[1-6])(?:\s|>)", text):
            raise ContractValidationError("HTML response has no document structure")


def _validate_retained_fragment_structure_v1(
    fragment_bytes: bytes,
    extract_format: OpenRouterWireExtractFormatV1,
) -> None:
    try:
        text = fragment_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractValidationError("retained source fragment is not strict UTF-8") from exc
    if extract_format is OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS:
        meaningful = tuple(
            line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
        )
        if (
            not meaningful
            or any(line[: len(line) - len(line.lstrip())].find("\t") >= 0 for line in meaningful)
            or not re.match(r"^\s*[^\s:#][^\r\n]*:\s*(?:#.*)?$", meaningful[0])
        ):
            raise ContractValidationError("retained OpenAPI fragment is not a YAML mapping block")
    elif extract_format is OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS:
        if not re.search(r"(?m)^#{1,6}[ \t]+\S", text):
            raise ContractValidationError("retained Markdown fragment has no heading")
    elif extract_format is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS:
        if not re.search(r"(?is)<(?:main|article|section|h[1-6])(?:\s|>)", text):
            raise ContractValidationError("retained HTML fragment has no visible section")


def _canonicalize_fragment_bundle_v1(
    retained_raw: bytes,
    fragments: Tuple[OpenRouterWireRawFragmentRangeV1, ...],
    extract_format: OpenRouterWireExtractFormatV1,
) -> Tuple[bytes, Tuple[bytes, ...]]:
    if extract_format is OpenRouterWireExtractFormatV1.JSON and len(fragments) != 1:
        raise ContractValidationError("JSON evidence must be one exact source range")
    canonical_fragments: list[bytes] = []
    for fragment in fragments:
        fragment_bytes = retained_raw[
            fragment.retained_byte_start : fragment.retained_byte_end_exclusive
        ]
        _validate_retained_fragment_structure_v1(fragment_bytes, extract_format)
        canonical_fragments.append(
            canonicalize_openrouter_wire_extract_v1(fragment_bytes, extract_format)
        )
    return b"\n".join(canonical_fragments), tuple(canonical_fragments)


def _retained_source_paths_v1(
    record: OpenRouterWireSourcePlanRecordV1,
) -> Tuple[str, str]:
    raw_extension = {
        OpenRouterWireExtractFormatV1.OPENAPI_YAML_COMPONENTS: "yaml",
        OpenRouterWireExtractFormatV1.MARKDOWN_SECTIONS: "md",
        OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS: "html",
        OpenRouterWireExtractFormatV1.JSON: "json",
    }[record.extract_format]
    canonical_extension = (
        "txt"
        if record.extract_format is OpenRouterWireExtractFormatV1.HTML_VISIBLE_SECTIONS
        else raw_extension
    )
    directory = f"{OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1}/{record.source_key}"
    return (
        f"{directory}/raw_source_extract.{raw_extension}",
        f"{directory}/canonical_extract.{canonical_extension}",
    )


class OpenRouterWireRetainedSourceSnapshotV1(_FrozenSourceContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_RETAINED_SNAPSHOT_SCHEMA_V1
    ] = OPENROUTER_WIRE_RETAINED_SNAPSHOT_SCHEMA_V1
    snapshot_id: Optional[str] = None
    source_plan_id: Literal[
        FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
    ] = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
    plan_record_id: str
    source_key: str
    canonical_public_locator: str
    retrieved_utc: str
    retrieval_method: Literal["HTTPS_GET_PUBLIC_UNAUTHENTICATED"]
    http_status: Literal[200] = 200
    final_resolved_locator: str
    redirect_chain: Tuple[OpenRouterWireRedirectHopV1, ...] = ()
    raw_content_type_header: str = Field(min_length=1, max_length=512)
    media_type: str = Field(pattern=r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$")
    response_content_bytes: int = Field(ge=1, le=8_388_608)
    raw_source_representation: Literal[
        "CONCATENATED_EXACT_SOURCE_BYTE_RANGES"
    ] = "CONCATENATED_EXACT_SOURCE_BYTE_RANGES"
    raw_fragment_ranges: Tuple[OpenRouterWireRawFragmentRangeV1, ...]
    raw_source_byte_length: int = Field(ge=1, le=1_048_576)
    raw_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_extract_byte_length: int = Field(ge=1, le=1_048_576)
    canonical_extract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    retained_raw_evidence_path: str
    retained_canonical_extract_path: str
    relevant_anchors: Tuple[str, ...]
    missing_required_anchors: Tuple[str, ...] = ()
    extract_format: OpenRouterWireExtractFormatV1
    stability: OpenRouterWireSourceStabilityV1
    revalidation_trigger: str
    expiry_rule: str
    drift_behavior: Literal["FAIL_CLOSED"] = "FAIL_CLOSED"
    limitations: str

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireRetainedSourceSnapshotV1":
        plan_by_id = {
            item.plan_record_id: item
            for item in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records
        }
        plan = plan_by_id.get(self.plan_record_id)
        if (
            plan is None
            or self.source_key != plan.source_key
            or self.canonical_public_locator != plan.canonical_public_locator
            or self.retrieval_method != plan.retrieval_method
            or self.extract_format is not plan.extract_format
            or self.stability is not plan.stability
            or self.revalidation_trigger != plan.revalidation_trigger
            or self.expiry_rule != plan.expiry_rule
            or self.limitations != plan.limitations
        ):
            raise ContractValidationError("retained snapshot diverges from source plan")
        _validate_official_locator(
            self.final_resolved_locator,
            FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.allowed_official_domains,
        )
        expected_final_locator, rejected_redirect = _validate_redirect_chain_v1(
            plan.canonical_public_locator,
            self.redirect_chain,
        )
        if rejected_redirect or self.final_resolved_locator != expected_final_locator:
            raise ContractValidationError("retained source final locator is unexplained")
        if self.media_type != _parse_media_type_header_v1(self.raw_content_type_header):
            raise ContractValidationError("retained source media type is not header-derived")
        if self.media_type not in plan.expected_media_types:
            raise ContractValidationError("retained source media type is not predeclared")
        _validate_utc_timestamp(self.retrieved_utc)
        _validate_retained_evidence_path(self.retained_raw_evidence_path)
        _validate_retained_evidence_path(self.retained_canonical_extract_path)
        if self.retained_raw_evidence_path == self.retained_canonical_extract_path:
            raise ContractValidationError("raw and canonical evidence paths are identical")
        expected_paths = _retained_source_paths_v1(plan)
        if (
            self.retained_raw_evidence_path,
            self.retained_canonical_extract_path,
        ) != expected_paths:
            raise ContractValidationError("retained source paths are not the frozen paths")
        if not self.raw_fragment_ranges:
            raise ContractValidationError("retained source has no exact raw fragments")
        if tuple(item.ordinal for item in self.raw_fragment_ranges) != tuple(
            range(1, len(self.raw_fragment_ranges) + 1)
        ):
            raise ContractValidationError("raw fragment ordinals are not canonical")
        expected_retained_start = 0
        prior_source_end = -1
        for fragment in self.raw_fragment_ranges:
            if (
                fragment.retained_byte_start != expected_retained_start
                or fragment.source_byte_start <= prior_source_end
                or fragment.source_byte_end_exclusive > self.response_content_bytes
            ):
                raise ContractValidationError("raw fragment ranges overlap or leave a gap")
            expected_retained_start = fragment.retained_byte_end_exclusive
            prior_source_end = fragment.source_byte_end_exclusive - 1
        if expected_retained_start != self.raw_source_byte_length:
            raise ContractValidationError("raw fragment ranges do not cover retained bytes")
        expected_present = tuple(
            anchor for anchor in plan.required_anchors if anchor in self.relevant_anchors
        )
        expected_missing = tuple(
            anchor for anchor in plan.required_anchors if anchor not in self.relevant_anchors
        )
        if (
            self.relevant_anchors != expected_present
            or self.missing_required_anchors != expected_missing
        ):
            raise ContractValidationError(
                "present and missing anchors do not canonically partition the source plan"
            )
        expected = stable_contract_id(
            "szorwiresnapshotv1",
            self.model_dump(mode="json", exclude={"snapshot_id"}),
        )
        if self.snapshot_id not in (None, expected):
            raise ContractValidationError("retained snapshot ID mismatch")
        object.__setattr__(self, "snapshot_id", expected)
        return self


def build_openrouter_wire_retained_source_snapshot_v1(
    *,
    plan_record: OpenRouterWireSourcePlanRecordV1,
    retrieved_utc: str,
    final_resolved_locator: str,
    redirect_chain: Tuple[OpenRouterWireRedirectHopV1, ...],
    raw_content_type_header: str,
    response_content: bytes,
    raw_source_ranges: Tuple[Tuple[int, int], ...],
) -> Tuple[OpenRouterWireRetainedSourceSnapshotV1, bytes, bytes]:
    """Verify and construct one snapshot plus the exact bytes it binds."""

    if type(response_content) is not bytes or not response_content:
        raise ContractValidationError("response content must be non-empty bytes")
    _validate_full_source_structure_v1(response_content, plan_record.extract_format)
    policy = FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1
    if len(response_content) > policy.maximum_response_bytes_per_source:
        raise ContractValidationError("response content exceeds the frozen source limit")
    if not raw_source_ranges:
        raise ContractValidationError("source extraction produced no raw byte range")
    fragments: list[OpenRouterWireRawFragmentRangeV1] = []
    retained_parts: list[bytes] = []
    retained_start = 0
    prior_source_end = -1
    for ordinal, source_range in enumerate(raw_source_ranges, start=1):
        if len(source_range) != 2:
            raise ContractValidationError("source byte range is malformed")
        source_start, source_end = source_range
        if (
            type(source_start) is not int
            or type(source_end) is not int
            or source_start < 0
            or source_end <= source_start
            or source_end > len(response_content)
            or source_start < prior_source_end
        ):
            raise ContractValidationError("source byte ranges overlap or escape response")
        fragment_bytes = response_content[source_start:source_end]
        retained_end = retained_start + len(fragment_bytes)
        fragments.append(
            OpenRouterWireRawFragmentRangeV1(
                ordinal=ordinal,
                source_byte_start=source_start,
                source_byte_end_exclusive=source_end,
                retained_byte_start=retained_start,
                retained_byte_end_exclusive=retained_end,
                byte_length=len(fragment_bytes),
                sha256=sha256_bytes_v1(fragment_bytes),
            )
        )
        retained_parts.append(fragment_bytes)
        retained_start = retained_end
        prior_source_end = source_end
    retained_raw = b"".join(retained_parts)
    if len(retained_raw) > policy.total_retained_evidence_byte_cap:
        raise ContractValidationError("retained raw source exceeds the evidence cap")
    canonical_extract, canonical_fragments = _canonicalize_fragment_bundle_v1(
        retained_raw,
        tuple(fragments),
        plan_record.extract_format,
    )
    if (
        len(retained_raw) + len(canonical_extract)
        > policy.total_retained_evidence_byte_cap
    ):
        raise ContractValidationError("retained source pair exceeds the evidence cap")
    present_anchors = tuple(
        anchor
        for anchor in plan_record.required_anchors
        if any(anchor.encode("utf-8") in fragment for fragment in canonical_fragments)
    )
    missing_anchors = tuple(
        anchor for anchor in plan_record.required_anchors if anchor not in present_anchors
    )
    raw_path, canonical_path = _retained_source_paths_v1(plan_record)
    snapshot = OpenRouterWireRetainedSourceSnapshotV1(
        plan_record_id=plan_record.plan_record_id or "",
        source_key=plan_record.source_key,
        canonical_public_locator=plan_record.canonical_public_locator,
        retrieved_utc=retrieved_utc,
        retrieval_method=plan_record.retrieval_method,
        final_resolved_locator=final_resolved_locator,
        redirect_chain=redirect_chain,
        raw_content_type_header=raw_content_type_header,
        media_type=_parse_media_type_header_v1(raw_content_type_header),
        response_content_bytes=len(response_content),
        raw_fragment_ranges=tuple(fragments),
        raw_source_byte_length=len(retained_raw),
        raw_source_sha256=sha256_bytes_v1(retained_raw),
        canonical_extract_byte_length=len(canonical_extract),
        canonical_extract_sha256=sha256_bytes_v1(canonical_extract),
        retained_raw_evidence_path=raw_path,
        retained_canonical_extract_path=canonical_path,
        relevant_anchors=present_anchors,
        missing_required_anchors=missing_anchors,
        extract_format=plan_record.extract_format,
        stability=plan_record.stability,
        revalidation_trigger=plan_record.revalidation_trigger,
        expiry_rule=plan_record.expiry_rule,
        limitations=plan_record.limitations,
    )
    verify_openrouter_wire_retained_source_bytes_v1(
        snapshot,
        retained_raw,
        canonical_extract,
    )
    return snapshot, retained_raw, canonical_extract


def verify_openrouter_wire_retained_source_bytes_v1(
    snapshot: OpenRouterWireRetainedSourceSnapshotV1,
    retained_raw: bytes,
    canonical_extract: bytes,
) -> None:
    """Recompute every retained-byte digest and semantic anchor observation."""

    if type(retained_raw) is not bytes or type(canonical_extract) is not bytes:
        raise ContractValidationError("retained evidence must be exact bytes")
    if (
        len(retained_raw) != snapshot.raw_source_byte_length
        or sha256_bytes_v1(retained_raw) != snapshot.raw_source_sha256
        or len(canonical_extract) != snapshot.canonical_extract_byte_length
        or sha256_bytes_v1(canonical_extract)
        != snapshot.canonical_extract_sha256
    ):
        raise ContractValidationError("retained source bytes do not match snapshot")
    for fragment in snapshot.raw_fragment_ranges:
        fragment_bytes = retained_raw[
            fragment.retained_byte_start : fragment.retained_byte_end_exclusive
        ]
        if (
            len(fragment_bytes) != fragment.byte_length
            or sha256_bytes_v1(fragment_bytes) != fragment.sha256
        ):
            raise ContractValidationError("retained raw fragment digest mismatch")
    expected_canonical, canonical_fragments = _canonicalize_fragment_bundle_v1(
        retained_raw,
        snapshot.raw_fragment_ranges,
        snapshot.extract_format,
    )
    if expected_canonical != canonical_extract:
        raise ContractValidationError("retained canonical extract is not reproducible")
    plan = next(
        item
        for item in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records
        if item.plan_record_id == snapshot.plan_record_id
    )
    expected_present = tuple(
        anchor
        for anchor in plan.required_anchors
        if any(anchor.encode("utf-8") in fragment for fragment in canonical_fragments)
    )
    expected_missing = tuple(
        anchor for anchor in plan.required_anchors if anchor not in expected_present
    )
    if (
        snapshot.relevant_anchors != expected_present
        or snapshot.missing_required_anchors != expected_missing
    ):
        raise ContractValidationError("retained source anchor observations are false")


class OpenRouterWireRetrievalEventV1(_FrozenSourceContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_RETRIEVAL_EVENT_SCHEMA_V1
    ] = OPENROUTER_WIRE_RETRIEVAL_EVENT_SCHEMA_V1
    event_id: Optional[str] = None
    sequence: int = Field(ge=1, le=6)
    plan_record_id: str
    source_key: str
    started_utc: str
    completed_utc: str
    status: OpenRouterWireRetrievalStatusV1
    redirect_chain: Tuple[OpenRouterWireRedirectHopV1, ...] = ()
    http_status: Optional[int] = Field(default=None, ge=100, le=599)
    final_resolved_locator: Optional[str] = None
    raw_content_type_header: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=512,
    )
    media_type: Optional[str] = Field(
        default=None,
        pattern=r"^[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+$",
    )
    response_content_bytes: Optional[int] = Field(
        default=None,
        ge=1,
        le=8_388_608,
    )
    retained_snapshot_id: Optional[str] = None
    response_bytes_received: int = Field(ge=0, le=8_388_609)
    error_code: Optional[OpenRouterWireRetrievalErrorCodeV1] = None

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireRetrievalEventV1":
        plan_by_id = {
            item.plan_record_id: item
            for item in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records
        }
        plan = plan_by_id.get(self.plan_record_id)
        if plan is None or plan.source_key != self.source_key:
            raise ContractValidationError("retrieval event is not bound to the source plan")
        _validate_utc_timestamp(self.started_utc)
        _validate_utc_timestamp(self.completed_utc)
        if self.completed_utc < self.started_utc:
            raise ContractValidationError("retrieval event completes before it starts")
        redirect_final_locator, rejected_redirect = _validate_redirect_chain_v1(
            plan.canonical_public_locator,
            self.redirect_chain,
        )
        if self.final_resolved_locator is not None:
            _validate_official_locator(
                self.final_resolved_locator,
                FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.allowed_official_domains,
            )
        content_type_pair_is_partial = (self.raw_content_type_header is None) != (
            self.media_type is None
        )
        if content_type_pair_is_partial:
            raise ContractValidationError("retrieval Content-Type evidence is incomplete")
        if self.raw_content_type_header is not None and self.media_type != (
            _parse_media_type_header_v1(self.raw_content_type_header)
        ):
            raise ContractValidationError("retrieval media type is not header-derived")
        if (
            self.status is OpenRouterWireRetrievalStatusV1.REDIRECT_REJECTED
        ) != rejected_redirect:
            raise ContractValidationError("rejected redirect evidence is inconsistent")
        retained = self.status is OpenRouterWireRetrievalStatusV1.RETAINED
        retained_fields = (
            self.http_status,
            self.final_resolved_locator,
            self.raw_content_type_header,
            self.media_type,
            self.response_content_bytes,
            self.retained_snapshot_id,
        )
        if retained and (any(value is None for value in retained_fields) or self.error_code is not None):
            raise ContractValidationError("retained retrieval event is incomplete")
        if retained and (
            self.http_status != 200
            or self.media_type not in plan.expected_media_types
            or self.final_resolved_locator
            != redirect_final_locator
        ):
            raise ContractValidationError("retained retrieval event contradicts the source plan")
        if retained and self.response_bytes_received != self.response_content_bytes:
            raise ContractValidationError("retained retrieval byte count is inconsistent")
        if not retained and self.error_code is None:
            raise ContractValidationError("failed retrieval event lacks an error code")
        if not retained and self.retained_snapshot_id is not None:
            raise ContractValidationError("failed retrieval event names a retained snapshot")
        absent_response_fields = (
            self.response_content_bytes,
        )
        if self.status is OpenRouterWireRetrievalStatusV1.FETCH_FAILED:
            if (
                self.error_code
                not in {
                    OpenRouterWireRetrievalErrorCodeV1.NETWORK_ERROR,
                    OpenRouterWireRetrievalErrorCodeV1.TIMEOUT,
                    OpenRouterWireRetrievalErrorCodeV1.TLS_ERROR,
                }
                or self.http_status is not None
                or self.final_resolved_locator is not None
                or self.raw_content_type_header is not None
                or any(value is not None for value in absent_response_fields)
                or self.response_bytes_received != 0
                or rejected_redirect
            ):
                raise ContractValidationError("fetch-failed event violates its field matrix")
        elif self.status is OpenRouterWireRetrievalStatusV1.REDIRECT_REJECTED:
            if (
                self.error_code
                is not OpenRouterWireRetrievalErrorCodeV1.REDIRECT_POLICY_REJECTED
                or self.http_status != self.redirect_chain[-1].http_status
                or self.final_resolved_locator != redirect_final_locator
                or self.raw_content_type_header is not None
                or any(value is not None for value in absent_response_fields)
                or self.response_bytes_received != 0
            ):
                raise ContractValidationError("redirect-rejected event violates its field matrix")
        elif self.status is OpenRouterWireRetrievalStatusV1.STATUS_REJECTED:
            if (
                self.error_code
                is not OpenRouterWireRetrievalErrorCodeV1.HTTP_STATUS_REJECTED
                or self.http_status in (None, 200)
                or self.final_resolved_locator != redirect_final_locator
                or any(value is not None for value in absent_response_fields)
                or self.response_bytes_received != 0
                or rejected_redirect
            ):
                raise ContractValidationError("status-rejected event violates its field matrix")
        elif self.status is OpenRouterWireRetrievalStatusV1.MEDIA_TYPE_REJECTED:
            if (
                self.error_code
                is not OpenRouterWireRetrievalErrorCodeV1.MEDIA_TYPE_REJECTED
                or self.http_status != 200
                or self.final_resolved_locator != redirect_final_locator
                or (
                    self.media_type is not None
                    and self.media_type in plan.expected_media_types
                )
                or any(value is not None for value in absent_response_fields)
                or self.response_bytes_received != 0
                or rejected_redirect
            ):
                raise ContractValidationError("media-rejected event violates its field matrix")
        elif self.status is OpenRouterWireRetrievalStatusV1.SIZE_REJECTED:
            if (
                self.error_code
                not in {
                    OpenRouterWireRetrievalErrorCodeV1.SOURCE_SIZE_REJECTED,
                    OpenRouterWireRetrievalErrorCodeV1.TOTAL_SIZE_REJECTED,
                }
                or self.http_status != 200
                or self.final_resolved_locator != redirect_final_locator
                or self.media_type not in plan.expected_media_types
                or any(value is not None for value in absent_response_fields)
                or self.response_bytes_received < 0
                or rejected_redirect
            ):
                raise ContractValidationError("size-rejected event violates its field matrix")
        elif self.status is OpenRouterWireRetrievalStatusV1.EXTRACTION_FAILED:
            if (
                self.error_code
                not in {
                    OpenRouterWireRetrievalErrorCodeV1.STRICT_UTF8_REJECTED,
                    OpenRouterWireRetrievalErrorCodeV1.REQUIRED_EXTRACTION_FAILED,
                    OpenRouterWireRetrievalErrorCodeV1.CANONICALIZATION_FAILED,
                }
                or self.http_status != 200
                or self.final_resolved_locator != redirect_final_locator
                or self.media_type not in plan.expected_media_types
                or any(value is None for value in absent_response_fields)
                or self.response_bytes_received != self.response_content_bytes
                or rejected_redirect
            ):
                raise ContractValidationError("extraction-failed event violates its field matrix")
        expected = stable_contract_id(
            "szorwirefetcheventv1",
            self.model_dump(mode="json", exclude={"event_id"}),
        )
        if self.event_id not in (None, expected):
            raise ContractValidationError("retrieval event ID mismatch")
        object.__setattr__(self, "event_id", expected)
        return self


class OpenRouterWireRetrievalLogV1(_FrozenSourceContractV1):
    schema_version: Literal[
        OPENROUTER_WIRE_RETRIEVAL_LOG_SCHEMA_V1
    ] = OPENROUTER_WIRE_RETRIEVAL_LOG_SCHEMA_V1
    retrieval_log_id: Optional[str] = None
    source_plan_id: Literal[
        FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
    ] = FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_plan_id
    retrieval_policy_id: Literal[
        FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.policy_id
    ] = FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.policy_id
    events: Tuple[OpenRouterWireRetrievalEventV1, ...]
    snapshots: Tuple[OpenRouterWireRetainedSourceSnapshotV1, ...]
    official_public_document_fetches: int = Field(ge=0, le=6)
    official_public_page_inspections: Literal[0] = 0
    redirects: int = Field(ge=0, le=6)
    failed_documentation_fetches: int = Field(ge=0, le=6)
    official_public_response_bytes_received: int = Field(ge=0, le=20_971_520)
    retained_raw_source_bytes: int = Field(ge=0, le=1_048_576)
    retained_canonical_extract_bytes: int = Field(ge=0, le=1_048_576)
    total_retained_evidence_bytes: int = Field(ge=0, le=1_048_576)
    authenticated_api_calls: Literal[0] = 0
    credential_accesses: Literal[0] = 0
    provider_inference_calls: Literal[0] = 0
    model_executions: Literal[0] = 0
    paid_requests: Literal[0] = 0
    ced_runtime_tool_calls: Literal[0] = 0

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterWireRetrievalLogV1":
        if len(self.events) != len(FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records):
            raise ContractValidationError("retrieval log does not cover the frozen source plan")
        if tuple(item.sequence for item in self.events) != tuple(range(1, len(self.events) + 1)):
            raise ContractValidationError("retrieval events are not in canonical sequence")
        if tuple(item.plan_record_id for item in self.events) != tuple(
            item.plan_record_id
            for item in FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.source_records
        ):
            raise ContractValidationError("retrieval events do not follow source-plan order")
        prior_completed: Optional[str] = None
        for event in self.events:
            if prior_completed is not None and event.started_utc < prior_completed:
                raise ContractValidationError("retrieval events overlap or move backward")
            prior_completed = event.completed_utc
        if self.official_public_document_fetches != len(self.events):
            raise ContractValidationError("documentation fetch count is not event-derived")
        retained_events = tuple(
            item
            for item in self.events
            if item.status is OpenRouterWireRetrievalStatusV1.RETAINED
        )
        if tuple(item.retained_snapshot_id for item in retained_events) != tuple(
            item.snapshot_id for item in self.snapshots
        ):
            raise ContractValidationError("retrieval snapshots do not match retained events")
        for event, snapshot in zip(retained_events, self.snapshots):
            if (
                snapshot.plan_record_id != event.plan_record_id
                or snapshot.source_key != event.source_key
                or snapshot.retrieved_utc != event.completed_utc
                or snapshot.redirect_chain != event.redirect_chain
                or snapshot.final_resolved_locator != event.final_resolved_locator
                or snapshot.raw_content_type_header
                != event.raw_content_type_header
                or snapshot.media_type != event.media_type
                or snapshot.response_content_bytes != event.response_content_bytes
            ):
                raise ContractValidationError("retrieval event and snapshot bytes diverge")
        observed_failures = sum(
            item.status is not OpenRouterWireRetrievalStatusV1.RETAINED
            for item in self.events
        )
        observed_redirects = sum(
            len(item.redirect_chain) for item in self.events
        )
        observed_response_bytes = sum(
            item.response_bytes_received for item in self.events
        )
        observed_raw_bytes = sum(
            item.raw_source_byte_length for item in self.snapshots
        )
        observed_canonical_bytes = sum(
            item.canonical_extract_byte_length for item in self.snapshots
        )
        observed_retained_bytes = observed_raw_bytes + observed_canonical_bytes
        if (
            self.failed_documentation_fetches != observed_failures
            or self.redirects != observed_redirects
            or self.official_public_response_bytes_received
            != observed_response_bytes
            or self.retained_raw_source_bytes != observed_raw_bytes
            or self.retained_canonical_extract_bytes != observed_canonical_bytes
            or self.total_retained_evidence_bytes != observed_retained_bytes
            or observed_retained_bytes
            > FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1.total_retained_evidence_byte_cap
        ):
            raise ContractValidationError("retrieval activity counters are not derived")
        expected = stable_contract_id(
            "szorwireretrievallogv1",
            self.model_dump(mode="json", exclude={"retrieval_log_id"}),
        )
        if self.retrieval_log_id not in (None, expected):
            raise ContractValidationError("retrieval-log ID mismatch")
        object.__setattr__(self, "retrieval_log_id", expected)
        return self


def render_openrouter_wire_source_plan_v1() -> bytes:
    return (
        canonical_json(FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1.model_dump(mode="json"))
        + "\n"
    ).encode("utf-8")


def render_openrouter_wire_retrieval_log_v1(
    retrieval_log: OpenRouterWireRetrievalLogV1,
) -> bytes:
    return (
        canonical_json(retrieval_log.model_dump(mode="json")) + "\n"
    ).encode("utf-8")


def sha256_bytes_v1(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = [
    "FROZEN_OPENROUTER_WIRE_CANONICALIZATION_POLICY_V1",
    "FROZEN_OPENROUTER_WIRE_RETRIEVAL_POLICY_V1",
    "FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_RECORDS_V1",
    "FROZEN_OPENROUTER_WIRE_SOURCE_PLAN_V1",
    "OPENROUTER_WIRE_RETAINED_SOURCE_DIRECTORY_V1",
    "OPENROUTER_WIRE_RETRIEVAL_LOG_RELATIVE_PATH_V1",
    "OPENROUTER_WIRE_SOURCE_PLAN_RELATIVE_PATH_V1",
    "OPENROUTER_WIRE_SPECIFICATION_HYPOTHESIS_V1",
    "OpenRouterWireCanonicalizationPolicyV1",
    "OpenRouterWireExtractFormatV1",
    "OpenRouterWireRetainedSourceSnapshotV1",
    "OpenRouterWireRawFragmentRangeV1",
    "OpenRouterWireRedirectHopV1",
    "OpenRouterWireRedirectOutcomeV1",
    "OpenRouterWireRetrievalErrorCodeV1",
    "OpenRouterWireRetrievalEventV1",
    "OpenRouterWireRetrievalLogV1",
    "OpenRouterWireRetrievalPolicyV1",
    "OpenRouterWireRetrievalStatusV1",
    "OpenRouterWireSourceClassV1",
    "OpenRouterWireSourcePlanRecordV1",
    "OpenRouterWireSourcePlanV1",
    "OpenRouterWireSourceStabilityV1",
    "canonicalize_openrouter_wire_extract_v1",
    "build_openrouter_wire_retained_source_snapshot_v1",
    "verify_openrouter_wire_retained_source_bytes_v1",
    "render_openrouter_wire_retrieval_log_v1",
    "render_openrouter_wire_source_plan_v1",
    "sha256_bytes_v1",
]
