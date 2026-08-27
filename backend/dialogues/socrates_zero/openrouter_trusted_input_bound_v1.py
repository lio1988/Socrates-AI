"""Trusted pre-call OpenRouter input-token upper bounds, offline and inert.

P17 needs an upper bound over the primary completion's billable
``usage.prompt_tokens`` before a live dispatch.  It does not need an exact token
count.  The retained first-party evidence supports two, and only two, limit
semantics:

* an exact-model maximum prompt-token limit, when present; or
* an exact-model whole-context limit, used conservatively without subtracting
  the separately established 256-token output cap.

The external value is intentionally absent from this module.  A live value is
authority only when it is observed from the exact first-party model-detail
source in the same preflight that consumes it.  Synthetic values remain useful
for the offline experiment but are permanently labelled test-only.

Tokenizer families, byte/character heuristics, post-call usage and ambiguous
endpoint records are not enum members and therefore cannot become authority by
construction.  This module performs no I/O, imports no provider SDK, reads no
credential, and creates no production fact at import time.
"""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Any, Dict, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import ContractValidationError, stable_contract_id
from .openrouter_pre_live_safety_v1 import (
    OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1,
)
from .openrouter_route_controls_contracts import (
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1,
    OPENROUTER_ROUTE_MODEL_V1,
)


OPENROUTER_TRUSTED_MODEL_INPUT_LIMIT_SCHEMA_V1 = (
    "socrateszero-openrouter-trusted-model-input-limit/v1"
)
OPENROUTER_P17_INPUT_BOUND_PROOF_SCHEMA_V1 = (
    "socrateszero-openrouter-p17-input-bound-proof/v1"
)

OPENROUTER_P17_PROOF_ARCHITECTURE_V1 = "READY"
OPENROUTER_P17_CURRENT_AUTHORITY_V1 = "JIT_PENDING"
OPENROUTER_P17_EXACT_MODEL_V1 = OPENROUTER_ROUTE_MODEL_V1
OPENROUTER_P17_EXACT_ENDPOINT_SELECTOR_V1 = (
    OPENROUTER_EXACT_ENDPOINT_SELECTOR_V1
)
OPENROUTER_P17_MAX_OUTPUT_TOKENS_V1 = (
    OPENROUTER_SEALED_MAX_OUTPUT_TOKENS_V1
)
OPENROUTER_P17_EXPECTED_MESSAGE_COUNT_V1 = 2

# Retained first-party source-set authority.  These are semantic-source digests,
# not the future response digest that supplies the model-specific value.
OPENROUTER_P17_RETAINED_OFFICIAL_COMMIT_V1 = (
    "4a5a458dbb6a0041db0480c17ab67c4c1a3ae0db"
)
OPENROUTER_P17_RETAINED_MANIFEST_ID_V1 = (
    "szorwirespecmanifestv2r1_"
    "a0695823f0e2968ef44706940a243fb7df934a69f986dd841f1abeee4e858d15"
)
OPENROUTER_P17_RETAINED_MANIFEST_SHA256_V1 = (
    "3915bb0aa6cd53cf4fa7f54f3137787aace529d177dbfb3ab8e685fd3a9922cb"
)

OPENROUTER_P17_OPENAPI_SOURCE_ID_V1 = (
    "szorwiresourcev2r1_"
    "61aba8cdf4e3403dbac683bea535de1bfaf96fd3292dfa9549d749a7d918a4fc"
)
OPENROUTER_P17_OPENAPI_SHA256_V1 = (
    "bd144e3de11198e6ac72f12c4d8986949d7fcd651c02f6ef671afd62429b3713"
)
OPENROUTER_P17_OPENAPI_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/"
    "evidence/sources/openapi.yaml"
)

OPENROUTER_P17_API_OVERVIEW_SOURCE_ID_V1 = (
    "szorwiresourcev2r1_"
    "0fb3a6af79da19e7e78463abb9d77d6e92a6d7ddc43317adc16683d997871729"
)
OPENROUTER_P17_API_OVERVIEW_SHA256_V1 = (
    "8647d02d0e3ccb000e8870200e0284d2516973bf0ef7cf8f8a0353219ea87d3e"
)
OPENROUTER_P17_API_OVERVIEW_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/"
    "evidence/sources/api-reference-overview.mdx"
)

OPENROUTER_P17_ROUTER_METADATA_SOURCE_ID_V1 = (
    "szorwiresourcev2r1_"
    "59d512e602085e0d93b955483bf33f81d606125c5cf6ea871cb9044df7202355"
)
OPENROUTER_P17_ROUTER_METADATA_SHA256_V1 = (
    "4e99ac8a12a5aea0ae83372f7fbd3c1e790edefb90a2a18355de5e77be3279f6"
)
OPENROUTER_P17_ROUTER_METADATA_PATH_V1 = (
    "docs/branches/feature-socrates-zero-openrouter-wire-spec-evidence-v2r1/"
    "evidence/sources/router-metadata.mdx"
)

FROZEN_OPENROUTER_P17_RETAINED_SOURCES_V1: Tuple[
    Tuple[str, str, str, str], ...
] = (
    (
        "OPENAPI",
        OPENROUTER_P17_OPENAPI_SOURCE_ID_V1,
        OPENROUTER_P17_OPENAPI_SHA256_V1,
        OPENROUTER_P17_OPENAPI_PATH_V1,
    ),
    (
        "API_OVERVIEW",
        OPENROUTER_P17_API_OVERVIEW_SOURCE_ID_V1,
        OPENROUTER_P17_API_OVERVIEW_SHA256_V1,
        OPENROUTER_P17_API_OVERVIEW_PATH_V1,
    ),
    (
        "ROUTER_METADATA",
        OPENROUTER_P17_ROUTER_METADATA_SOURCE_ID_V1,
        OPENROUTER_P17_ROUTER_METADATA_SHA256_V1,
        OPENROUTER_P17_ROUTER_METADATA_PATH_V1,
    ),
)

# The one allowed first-party JIT value source.
OPENROUTER_P17_MODEL_DETAIL_METHOD_V1 = "GET"
OPENROUTER_P17_MODEL_DETAIL_PATH_V1 = (
    "/api/v1/model/openai/gpt-4.1-mini"
)
OPENROUTER_P17_MAX_PROMPT_TOKENS_POINTER_V1 = (
    "$.data.per_request_limits.prompt_tokens"
)
OPENROUTER_P17_MODEL_CONTEXT_LENGTH_POINTER_V1 = "$.data.context_length"


class OpenRouterInputLimitSourceAuthorityV1(str, Enum):
    OPENROUTER_FIRST_PARTY = "OPENROUTER_FIRST_PARTY"
    SYNTHETIC_TEST_FIXTURE = "SYNTHETIC_TEST_FIXTURE"


class OpenRouterInputLimitSourceKindV1(str, Enum):
    MODEL_DETAIL_RESPONSE = "MODEL_DETAIL_RESPONSE"


class OpenRouterInputLimitSourceScopeV1(str, Enum):
    LIVE_JIT_SAME_PREFLIGHT = "LIVE_JIT_SAME_PREFLIGHT"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


class OpenRouterInputLimitObservationStatusV1(str, Enum):
    JIT_OBSERVED_IN_SAME_PREFLIGHT = "JIT_OBSERVED_IN_SAME_PREFLIGHT"
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"


class OpenRouterInputLimitAliasStateV1(str, Enum):
    EXACT_MODEL_NOT_ALIAS = "EXACT_MODEL_NOT_ALIAS"


class OpenRouterInputLimitKindV1(str, Enum):
    """The only retained semantic classes that can upper-bound P17."""

    MAX_PROMPT_TOKENS = "MAX_PROMPT_TOKENS"
    MODEL_CONTEXT_LIMIT = "MODEL_CONTEXT_LIMIT"


class OpenRouterInputLimitSemanticClaimV1(str, Enum):
    PRIMARY_BILLABLE_PROMPT_TOKENS_LE_MAX_PROMPT_TOKENS = (
        "PRIMARY_BILLABLE_PROMPT_TOKENS_LE_MAX_PROMPT_TOKENS"
    )
    PRIMARY_BILLABLE_PROMPT_TOKENS_LE_MODEL_CONTEXT_LIMIT = (
        "PRIMARY_BILLABLE_PROMPT_TOKENS_LE_MODEL_CONTEXT_LIMIT"
    )


class OpenRouterP17FramingCoverageV1(str, Enum):
    INCLUDED_IN_MAX_PROMPT_TOKEN_LIMIT = "INCLUDED_IN_MAX_PROMPT_TOKEN_LIMIT"
    MODEL_VISIBLE_INPUT_OCCUPIES_WHOLE_CONTEXT = (
        "MODEL_VISIBLE_INPUT_OCCUPIES_WHOLE_CONTEXT"
    )


class OpenRouterP17AuxiliaryPipelineScopeV1(str, Enum):
    PRIMARY_COMPLETION_ONLY_AUXILIARY_REQUIRES_SEPARATE_COVERAGE = (
        "PRIMARY_COMPLETION_ONLY_AUXILIARY_REQUIRES_SEPARATE_COVERAGE"
    )


class OpenRouterP17ProofMethodV1(str, Enum):
    DIRECT_MAX_PROMPT_TOKENS_V1 = "DIRECT_MAX_PROMPT_TOKENS_V1"
    WHOLE_MODEL_CONTEXT_CONSERVATIVE_INPUT_BOUND_V1 = (
        "WHOLE_MODEL_CONTEXT_CONSERVATIVE_INPUT_BOUND_V1"
    )


class OpenRouterP17ProofAuthorityV1(str, Enum):
    LIVE_JIT_ESTABLISHED = "LIVE_JIT_ESTABLISHED"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


class _FrozenInputBoundContractV1(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _require_nonblank(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must not be blank")
    if value != value.strip():
        raise ContractValidationError(
            f"{field_name} must not contain surrounding whitespace"
        )
    return value


class TrustedModelInputLimitRecordV1(_FrozenInputBoundContractV1):
    """One exact-model first-party limit fact or an explicit test fixture.

    Both candidate source values are retained so the preference rule is checked
    rather than asserted.  If ``observed_max_prompt_tokens`` exists, the record
    must use it.  Only when it is absent may the whole context be selected.
    """

    schema_version: Literal[
        OPENROUTER_TRUSTED_MODEL_INPUT_LIMIT_SCHEMA_V1
    ] = OPENROUTER_TRUSTED_MODEL_INPUT_LIMIT_SCHEMA_V1

    source_scope: OpenRouterInputLimitSourceScopeV1
    source_authority: OpenRouterInputLimitSourceAuthorityV1
    source_kind: Literal[
        OpenRouterInputLimitSourceKindV1.MODEL_DETAIL_RESPONSE
    ] = OpenRouterInputLimitSourceKindV1.MODEL_DETAIL_RESPONSE
    observation_status: OpenRouterInputLimitObservationStatusV1
    preflight_execution_id: str = Field(min_length=1)
    synthetic_fixture_id: Optional[str] = None

    source_method: Literal[
        OPENROUTER_P17_MODEL_DETAIL_METHOD_V1
    ] = OPENROUTER_P17_MODEL_DETAIL_METHOD_V1
    source_path: Literal[
        OPENROUTER_P17_MODEL_DETAIL_PATH_V1
    ] = OPENROUTER_P17_MODEL_DETAIL_PATH_V1
    source_http_status: Literal[200] = 200
    source_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_response_body_length: int = Field(strict=True, gt=0)

    retained_official_commit: Literal[
        OPENROUTER_P17_RETAINED_OFFICIAL_COMMIT_V1
    ] = OPENROUTER_P17_RETAINED_OFFICIAL_COMMIT_V1
    retained_manifest_id: Literal[
        OPENROUTER_P17_RETAINED_MANIFEST_ID_V1
    ] = OPENROUTER_P17_RETAINED_MANIFEST_ID_V1
    retained_manifest_sha256: Literal[
        OPENROUTER_P17_RETAINED_MANIFEST_SHA256_V1
    ] = OPENROUTER_P17_RETAINED_MANIFEST_SHA256_V1
    openapi_source_id: Literal[
        OPENROUTER_P17_OPENAPI_SOURCE_ID_V1
    ] = OPENROUTER_P17_OPENAPI_SOURCE_ID_V1
    openapi_sha256: Literal[
        OPENROUTER_P17_OPENAPI_SHA256_V1
    ] = OPENROUTER_P17_OPENAPI_SHA256_V1
    api_overview_source_id: Literal[
        OPENROUTER_P17_API_OVERVIEW_SOURCE_ID_V1
    ] = OPENROUTER_P17_API_OVERVIEW_SOURCE_ID_V1
    api_overview_sha256: Literal[
        OPENROUTER_P17_API_OVERVIEW_SHA256_V1
    ] = OPENROUTER_P17_API_OVERVIEW_SHA256_V1
    router_metadata_source_id: Literal[
        OPENROUTER_P17_ROUTER_METADATA_SOURCE_ID_V1
    ] = OPENROUTER_P17_ROUTER_METADATA_SOURCE_ID_V1
    router_metadata_sha256: Literal[
        OPENROUTER_P17_ROUTER_METADATA_SHA256_V1
    ] = OPENROUTER_P17_ROUTER_METADATA_SHA256_V1

    exact_model_id: Literal[
        OPENROUTER_P17_EXACT_MODEL_V1
    ] = OPENROUTER_P17_EXACT_MODEL_V1
    returned_model_id: str = Field(min_length=1)
    canonical_model_id: str = Field(min_length=1)
    alias_state: Literal[
        OpenRouterInputLimitAliasStateV1.EXACT_MODEL_NOT_ALIAS
    ] = OpenRouterInputLimitAliasStateV1.EXACT_MODEL_NOT_ALIAS

    observed_max_prompt_tokens: Optional[int] = Field(
        default=None, strict=True, gt=0
    )
    observed_model_context_length: Optional[int] = Field(
        default=None, strict=True, gt=0
    )
    limit_kind: OpenRouterInputLimitKindV1
    source_json_pointer: str
    limit_tokens: int = Field(strict=True, gt=0)
    semantic_claim: OpenRouterInputLimitSemanticClaimV1
    framing_coverage: OpenRouterP17FramingCoverageV1
    auxiliary_pipeline_scope: Literal[
        OpenRouterP17AuxiliaryPipelineScopeV1.PRIMARY_COMPLETION_ONLY_AUXILIARY_REQUIRES_SEPARATE_COVERAGE
    ] = (
        OpenRouterP17AuxiliaryPipelineScopeV1.PRIMARY_COMPLETION_ONLY_AUXILIARY_REQUIRES_SEPARATE_COVERAGE
    )
    proof_method_version: OpenRouterP17ProofMethodV1
    source_record_identity: Optional[str] = None

    @field_validator(
        "preflight_execution_id",
        "returned_model_id",
        "canonical_model_id",
        "source_json_pointer",
    )
    @classmethod
    def nonblank_fields(cls, value: str, info) -> str:
        return _require_nonblank(value, info.field_name)

    @model_validator(mode="after")
    def validate_scope_semantics_and_identify(
        self,
    ) -> "TrustedModelInputLimitRecordV1":
        if self.source_scope is OpenRouterInputLimitSourceScopeV1.LIVE_JIT_SAME_PREFLIGHT:
            if self.source_authority is not (
                OpenRouterInputLimitSourceAuthorityV1.OPENROUTER_FIRST_PARTY
            ):
                raise ContractValidationError(
                    "a live JIT limit requires first-party OpenRouter authority"
                )
            if self.observation_status is not (
                OpenRouterInputLimitObservationStatusV1.JIT_OBSERVED_IN_SAME_PREFLIGHT
            ):
                raise ContractValidationError(
                    "a live limit must be observed in the consuming preflight"
                )
            if self.synthetic_fixture_id is not None:
                raise ContractValidationError(
                    "a live JIT limit cannot carry a synthetic fixture identity"
                )
        else:
            if self.source_authority is not (
                OpenRouterInputLimitSourceAuthorityV1.SYNTHETIC_TEST_FIXTURE
            ):
                raise ContractValidationError(
                    "synthetic input-limit evidence must remain test-only"
                )
            if self.observation_status is not (
                OpenRouterInputLimitObservationStatusV1.SYNTHETIC_FIXTURE
            ):
                raise ContractValidationError(
                    "synthetic input-limit evidence must declare fixture status"
                )
            if self.synthetic_fixture_id is None:
                raise ContractValidationError(
                    "synthetic input-limit evidence requires a fixture identity"
                )
            _require_nonblank(self.synthetic_fixture_id, "synthetic_fixture_id")

        if self.returned_model_id != self.exact_model_id:
            raise ContractValidationError(
                "input-limit response model does not equal the exact requested model"
            )
        if self.canonical_model_id != self.exact_model_id:
            raise ContractValidationError(
                "input-limit canonical model does not equal the exact requested model"
            )

        if self.observed_max_prompt_tokens is not None:
            expected_kind = OpenRouterInputLimitKindV1.MAX_PROMPT_TOKENS
            expected_pointer = OPENROUTER_P17_MAX_PROMPT_TOKENS_POINTER_V1
            expected_limit = self.observed_max_prompt_tokens
            expected_claim = (
                OpenRouterInputLimitSemanticClaimV1.PRIMARY_BILLABLE_PROMPT_TOKENS_LE_MAX_PROMPT_TOKENS
            )
            expected_framing = (
                OpenRouterP17FramingCoverageV1.INCLUDED_IN_MAX_PROMPT_TOKEN_LIMIT
            )
            expected_method = OpenRouterP17ProofMethodV1.DIRECT_MAX_PROMPT_TOKENS_V1
        elif self.observed_model_context_length is not None:
            expected_kind = OpenRouterInputLimitKindV1.MODEL_CONTEXT_LIMIT
            expected_pointer = OPENROUTER_P17_MODEL_CONTEXT_LENGTH_POINTER_V1
            expected_limit = self.observed_model_context_length
            expected_claim = (
                OpenRouterInputLimitSemanticClaimV1.PRIMARY_BILLABLE_PROMPT_TOKENS_LE_MODEL_CONTEXT_LIMIT
            )
            expected_framing = (
                OpenRouterP17FramingCoverageV1.MODEL_VISIBLE_INPUT_OCCUPIES_WHOLE_CONTEXT
            )
            expected_method = (
                OpenRouterP17ProofMethodV1.WHOLE_MODEL_CONTEXT_CONSERVATIVE_INPUT_BOUND_V1
            )
        else:
            raise ContractValidationError(
                "the exact-model record contains no accepted input-limit fact"
            )

        for actual, expected, label in (
            (self.limit_kind, expected_kind, "limit kind"),
            (self.source_json_pointer, expected_pointer, "source field"),
            (self.limit_tokens, expected_limit, "selected token limit"),
            (self.semantic_claim, expected_claim, "semantic claim"),
            (self.framing_coverage, expected_framing, "framing coverage"),
            (self.proof_method_version, expected_method, "proof method"),
        ):
            if actual != expected:
                raise ContractValidationError(
                    f"{label} disagrees with the preferred retained limit semantics"
                )

        expected_identity = stable_contract_id(
            "szortrustedmodellimitrecordv1",
            self.model_dump(mode="json", exclude={"source_record_identity"}),
        )
        if self.source_record_identity not in (None, expected_identity):
            raise ContractValidationError("model input-limit record identity mismatch")
        object.__setattr__(self, "source_record_identity", expected_identity)
        return self

    @property
    def record_id(self) -> str:
        return self.source_record_identity or ""

    @property
    def is_live_jit_authority(self) -> bool:
        return self.source_scope is (
            OpenRouterInputLimitSourceScopeV1.LIVE_JIT_SAME_PREFLIGHT
        )


def _build_trusted_model_input_limit_record_from_parsed_v1(
    *,
    source_scope: OpenRouterInputLimitSourceScopeV1,
    preflight_execution_id: str,
    source_evidence_digest: str,
    source_response_body_length: int,
    returned_model_id: str,
    canonical_model_id: str,
    observed_max_prompt_tokens: Optional[int] = None,
    observed_model_context_length: Optional[int] = None,
    synthetic_fixture_id: Optional[str] = None,
) -> TrustedModelInputLimitRecordV1:
    """Construct from fields already extracted by the strict raw decoder.

    A malformed present prompt limit is refused by strict validation rather than
    silently skipped in favour of context.  ``None`` means the field was
    authoritatively absent/null; it never means zero.
    """

    if type(source_scope) is not OpenRouterInputLimitSourceScopeV1:
        raise ContractValidationError("input-limit source scope must use the exact enum")
    if observed_max_prompt_tokens is not None:
        limit_kind = OpenRouterInputLimitKindV1.MAX_PROMPT_TOKENS
        source_pointer = OPENROUTER_P17_MAX_PROMPT_TOKENS_POINTER_V1
        limit_tokens = observed_max_prompt_tokens
        semantic_claim = (
            OpenRouterInputLimitSemanticClaimV1.PRIMARY_BILLABLE_PROMPT_TOKENS_LE_MAX_PROMPT_TOKENS
        )
        framing = (
            OpenRouterP17FramingCoverageV1.INCLUDED_IN_MAX_PROMPT_TOKEN_LIMIT
        )
        proof_method = OpenRouterP17ProofMethodV1.DIRECT_MAX_PROMPT_TOKENS_V1
    elif observed_model_context_length is not None:
        limit_kind = OpenRouterInputLimitKindV1.MODEL_CONTEXT_LIMIT
        source_pointer = OPENROUTER_P17_MODEL_CONTEXT_LENGTH_POINTER_V1
        limit_tokens = observed_model_context_length
        semantic_claim = (
            OpenRouterInputLimitSemanticClaimV1.PRIMARY_BILLABLE_PROMPT_TOKENS_LE_MODEL_CONTEXT_LIMIT
        )
        framing = (
            OpenRouterP17FramingCoverageV1.MODEL_VISIBLE_INPUT_OCCUPIES_WHOLE_CONTEXT
        )
        proof_method = (
            OpenRouterP17ProofMethodV1.WHOLE_MODEL_CONTEXT_CONSERVATIVE_INPUT_BOUND_V1
        )
    else:
        raise ContractValidationError(
            "the exact-model response contains no accepted positive input limit"
        )

    live = source_scope is (
        OpenRouterInputLimitSourceScopeV1.LIVE_JIT_SAME_PREFLIGHT
    )
    return TrustedModelInputLimitRecordV1(
        source_scope=source_scope,
        source_authority=(
            OpenRouterInputLimitSourceAuthorityV1.OPENROUTER_FIRST_PARTY
            if live
            else OpenRouterInputLimitSourceAuthorityV1.SYNTHETIC_TEST_FIXTURE
        ),
        observation_status=(
            OpenRouterInputLimitObservationStatusV1.JIT_OBSERVED_IN_SAME_PREFLIGHT
            if live
            else OpenRouterInputLimitObservationStatusV1.SYNTHETIC_FIXTURE
        ),
        preflight_execution_id=preflight_execution_id,
        synthetic_fixture_id=synthetic_fixture_id,
        source_evidence_digest=source_evidence_digest,
        source_response_body_length=source_response_body_length,
        returned_model_id=returned_model_id,
        canonical_model_id=canonical_model_id,
        observed_max_prompt_tokens=observed_max_prompt_tokens,
        observed_model_context_length=observed_model_context_length,
        limit_kind=limit_kind,
        source_json_pointer=source_pointer,
        limit_tokens=limit_tokens,
        semantic_claim=semantic_claim,
        framing_coverage=framing,
        proof_method_version=proof_method,
    )


def _strict_model_detail_json_object_v1(
    raw_response_bytes: bytes,
) -> Dict[str, Any]:
    """Decode exact retained source bytes without JSON ambiguity."""

    if type(raw_response_bytes) is not bytes:
        raise ContractValidationError(
            "model-detail raw response must use the exact bytes type"
        )
    if not raw_response_bytes:
        raise ContractValidationError("model-detail raw response must not be empty")

    try:
        raw_text = raw_response_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ContractValidationError(
            "model-detail raw response must be strict UTF-8"
        ) from exc

    def _unique_object_pairs(
        pairs: Sequence[Tuple[str, Any]],
    ) -> Dict[str, Any]:
        decoded: Dict[str, Any] = {}
        for key, value in pairs:
            if key in decoded:
                raise ContractValidationError(
                    "model-detail raw response contains a duplicate object key"
                )
            decoded[key] = value
        return decoded

    def _reject_non_finite_constant(name: str) -> Any:
        del name
        raise ContractValidationError(
            "model-detail raw response contains a non-finite JSON number"
        )

    def _finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ContractValidationError(
                "model-detail raw response contains a non-finite JSON number"
            )
        return parsed

    try:
        decoded = json.loads(
            raw_text,
            object_pairs_hook=_unique_object_pairs,
            parse_constant=_reject_non_finite_constant,
            parse_float=_finite_float,
        )
    except ContractValidationError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ContractValidationError(
            "model-detail raw response must be one valid JSON value"
        ) from exc
    if type(decoded) is not dict:
        raise ContractValidationError(
            "model-detail raw response top level must be an object"
        )
    return decoded


def _strict_positive_json_int_v1(value: object, field_path: str) -> int:
    if type(value) is not int or value <= 0:
        raise ContractValidationError(
            f"{field_path} must be a positive JSON integer, not bool or float"
        )
    return value


def build_trusted_model_input_limit_record_from_response_v1(
    *,
    raw_response_bytes: bytes,
    preflight_execution_id: str,
    source_scope: OpenRouterInputLimitSourceScopeV1,
    synthetic_fixture_id: Optional[str] = None,
) -> TrustedModelInputLimitRecordV1:
    """Derive the complete trusted fact from one exact raw source response.

    The digest, byte length, returned model identity, canonical model identity,
    and both candidate limit fields are derived here.  No caller can assert
    those facts independently.  A present malformed preferred field fails; it
    never falls through to the context fallback.
    """

    if type(source_scope) is not OpenRouterInputLimitSourceScopeV1:
        raise ContractValidationError("input-limit source scope must use the exact enum")
    _require_nonblank(preflight_execution_id, "preflight_execution_id")

    envelope = _strict_model_detail_json_object_v1(raw_response_bytes)
    if "data" not in envelope:
        raise ContractValidationError(
            "model-detail raw response is missing the required data object"
        )
    data = envelope["data"]
    if type(data) is not dict:
        raise ContractValidationError(
            "model-detail raw response data must be an object"
        )

    if "id" not in data or type(data["id"]) is not str:
        raise ContractValidationError(
            "model-detail raw response data.id must be a string"
        )
    returned_model_id = data["id"]
    if returned_model_id != OPENROUTER_P17_EXACT_MODEL_V1:
        raise ContractValidationError(
            "model-detail raw response data.id is not the exact requested model"
        )

    if "canonical_slug" not in data or type(data["canonical_slug"]) is not str:
        raise ContractValidationError(
            "model-detail raw response data.canonical_slug must be a string"
        )
    canonical_model_id = data["canonical_slug"]
    if canonical_model_id != OPENROUTER_P17_EXACT_MODEL_V1:
        raise ContractValidationError(
            "model-detail raw response canonical_slug is not the exact model"
        )
    if data.get("alias_target") is not None:
        raise ContractValidationError(
            "model-detail raw response resolved an alias instead of the exact model"
        )

    if "context_length" not in data:
        raise ContractValidationError(
            "model-detail raw response is missing data.context_length"
        )
    raw_context_length = data["context_length"]
    observed_model_context_length = (
        None
        if raw_context_length is None
        else _strict_positive_json_int_v1(
            raw_context_length, "data.context_length"
        )
    )

    if "per_request_limits" not in data:
        raise ContractValidationError(
            "model-detail raw response is missing data.per_request_limits"
        )
    raw_per_request_limits = data["per_request_limits"]
    if raw_per_request_limits is None:
        observed_max_prompt_tokens = None
    else:
        if type(raw_per_request_limits) is not dict:
            raise ContractValidationError(
                "data.per_request_limits must be an object or null"
            )
        if "prompt_tokens" not in raw_per_request_limits:
            raise ContractValidationError(
                "data.per_request_limits is missing prompt_tokens"
            )
        observed_max_prompt_tokens = _strict_positive_json_int_v1(
            raw_per_request_limits["prompt_tokens"],
            "data.per_request_limits.prompt_tokens",
        )

    return _build_trusted_model_input_limit_record_from_parsed_v1(
        source_scope=source_scope,
        preflight_execution_id=preflight_execution_id,
        source_evidence_digest=hashlib.sha256(raw_response_bytes).hexdigest(),
        source_response_body_length=len(raw_response_bytes),
        returned_model_id=returned_model_id,
        canonical_model_id=canonical_model_id,
        observed_max_prompt_tokens=observed_max_prompt_tokens,
        observed_model_context_length=observed_model_context_length,
        synthetic_fixture_id=synthetic_fixture_id,
    )


def build_trusted_model_input_limit_record_v1(
    *,
    raw_response_bytes: bytes,
    preflight_execution_id: str,
    source_scope: OpenRouterInputLimitSourceScopeV1,
    synthetic_fixture_id: Optional[str] = None,
) -> TrustedModelInputLimitRecordV1:
    """Compatibility name for the strict raw-response-bound constructor."""

    return build_trusted_model_input_limit_record_from_response_v1(
        raw_response_bytes=raw_response_bytes,
        preflight_execution_id=preflight_execution_id,
        source_scope=source_scope,
        synthetic_fixture_id=synthetic_fixture_id,
    )


class OpenRouterP17InputBoundProofV1(_FrozenInputBoundContractV1):
    """A trusted limit bound to one exact future-live request identity."""

    schema_version: Literal[
        OPENROUTER_P17_INPUT_BOUND_PROOF_SCHEMA_V1
    ] = OPENROUTER_P17_INPUT_BOUND_PROOF_SCHEMA_V1
    preflight_execution_id: str = Field(min_length=1)
    limit_record: TrustedModelInputLimitRecordV1

    live_request_overlay_id: str = Field(min_length=1)
    rendered_request_id: str = Field(min_length=1)
    exact_model: Literal[
        OPENROUTER_P17_EXACT_MODEL_V1
    ] = OPENROUTER_P17_EXACT_MODEL_V1
    request_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_body_length: int = Field(strict=True, gt=0)
    message_count: int = Field(strict=True, gt=0)
    modality_binding_id: str = Field(min_length=1)
    request_modality_proof_id: str = Field(min_length=1)
    text_only: Literal[True] = True
    plugins_absent: Literal[True] = True
    tools_enabled: Literal[False] = False

    output_bound_evidence_id: str = Field(min_length=1)
    max_output_tokens: int = Field(strict=True, gt=0)
    output_tokens_subtracted_from_context: Literal[False] = False

    provider_price_policy_id: str = Field(min_length=1)
    exact_endpoint_selector: Literal[
        OPENROUTER_P17_EXACT_ENDPOINT_SELECTOR_V1
    ] = OPENROUTER_P17_EXACT_ENDPOINT_SELECTOR_V1

    max_input_tokens: int = Field(strict=True, gt=0)
    limit_kind: OpenRouterInputLimitKindV1
    proof_method_version: OpenRouterP17ProofMethodV1
    authority: OpenRouterP17ProofAuthorityV1
    auxiliary_pipeline_scope: Literal[
        OpenRouterP17AuxiliaryPipelineScopeV1.PRIMARY_COMPLETION_ONLY_AUXILIARY_REQUIRES_SEPARATE_COVERAGE
    ] = (
        OpenRouterP17AuxiliaryPipelineScopeV1.PRIMARY_COMPLETION_ONLY_AUXILIARY_REQUIRES_SEPARATE_COVERAGE
    )
    proof_id: Optional[str] = None

    @field_validator(
        "preflight_execution_id",
        "live_request_overlay_id",
        "rendered_request_id",
        "modality_binding_id",
        "request_modality_proof_id",
        "output_bound_evidence_id",
        "provider_price_policy_id",
    )
    @classmethod
    def proof_nonblank_fields(cls, value: str, info) -> str:
        return _require_nonblank(value, info.field_name)

    @field_validator("message_count", mode="before")
    @classmethod
    def exact_message_count(cls, value: object) -> object:
        if type(value) is not int or value != OPENROUTER_P17_EXPECTED_MESSAGE_COUNT_V1:
            raise ContractValidationError(
                "P17 proof must bind the exact two-message live request"
            )
        return value

    @field_validator("max_output_tokens", mode="before")
    @classmethod
    def exact_output_limit(cls, value: object) -> object:
        if type(value) is not int or value != OPENROUTER_P17_MAX_OUTPUT_TOKENS_V1:
            raise ContractValidationError(
                "P17 proof must bind the established 256-token output limit"
            )
        return value

    @model_validator(mode="after")
    def validate_bindings_and_identify(self) -> "OpenRouterP17InputBoundProofV1":
        record = self.limit_record
        if record.preflight_execution_id != self.preflight_execution_id:
            raise ContractValidationError(
                "input-limit evidence was not observed in this proof preflight"
            )
        if record.exact_model_id != self.exact_model:
            raise ContractValidationError(
                "input-limit evidence is bound to a different model"
            )
        if self.max_input_tokens != record.limit_tokens:
            raise ContractValidationError(
                "P17 maximum does not equal the trusted model-limit record"
            )
        if self.limit_kind is not record.limit_kind:
            raise ContractValidationError(
                "P17 limit kind does not equal the trusted model-limit record"
            )
        if self.proof_method_version is not record.proof_method_version:
            raise ContractValidationError(
                "P17 method does not equal the trusted model-limit record"
            )
        expected_authority = (
            OpenRouterP17ProofAuthorityV1.LIVE_JIT_ESTABLISHED
            if record.is_live_jit_authority
            else OpenRouterP17ProofAuthorityV1.SYNTHETIC_TEST_ONLY
        )
        if self.authority is not expected_authority:
            raise ContractValidationError(
                "P17 authority disagrees with the limit-record source scope"
            )

        expected_id = stable_contract_id(
            "szorp17inputboundproofv1",
            {
                "schema_version": self.schema_version,
                "preflight_execution_id": self.preflight_execution_id,
                "limit_record_id": record.source_record_identity,
                "live_request_overlay_id": self.live_request_overlay_id,
                "rendered_request_id": self.rendered_request_id,
                "exact_model": self.exact_model,
                "request_body_sha256": self.request_body_sha256,
                "request_body_length": self.request_body_length,
                "message_count": self.message_count,
                "modality_binding_id": self.modality_binding_id,
                "request_modality_proof_id": self.request_modality_proof_id,
                "text_only": self.text_only,
                "plugins_absent": self.plugins_absent,
                "tools_enabled": self.tools_enabled,
                "output_bound_evidence_id": self.output_bound_evidence_id,
                "max_output_tokens": self.max_output_tokens,
                "output_tokens_subtracted_from_context": (
                    self.output_tokens_subtracted_from_context
                ),
                "provider_price_policy_id": self.provider_price_policy_id,
                "exact_endpoint_selector": self.exact_endpoint_selector,
                "max_input_tokens": self.max_input_tokens,
                "limit_kind": self.limit_kind.value,
                "proof_method_version": self.proof_method_version.value,
                "authority": self.authority.value,
                "auxiliary_pipeline_scope": self.auxiliary_pipeline_scope.value,
            },
        )
        if self.proof_id not in (None, expected_id):
            raise ContractValidationError("P17 input-bound proof ID mismatch")
        object.__setattr__(self, "proof_id", expected_id)
        return self

    @property
    def evidence_id(self) -> str:
        return self.proof_id or ""

    @property
    def is_production_authority(self) -> bool:
        return self.authority is OpenRouterP17ProofAuthorityV1.LIVE_JIT_ESTABLISHED


def _revalidate_exact_contract_v1(value: object, expected_type, label: str):
    if type(value) is not expected_type:
        raise ContractValidationError(
            f"{label} must use the exact {expected_type.__name__} contract"
        )
    # Re-parse the serialized fields instead of trusting a possibly mutated
    # object instance.  Content IDs and all cross-field guards run again.
    return expected_type.model_validate(value.model_dump(mode="json"))


def build_openrouter_p17_input_bound_proof_v1(
    *,
    limit_record: TrustedModelInputLimitRecordV1,
    preflight_execution_id: str,
    overlay: object,
    rendered_request: object,
    modality_binding: object,
    output_bound: object,
    provider_policy: object,
) -> OpenRouterP17InputBoundProofV1:
    """Bind one trusted model-limit record to exact V2 request contracts.

    Imports are local so this P17 module remains independently importable while
    the additive overlay module is assembled.  At execution the bindings use
    exact runtime classes, not protocols or attribute-compatible substitutes.
    """

    from .openrouter_live_request_overlay_v2 import (
        OpenRouterLiveRequestModalityBindingV1,
        OpenRouterLiveRequestSafetyOverlayV2,
        OpenRouterOperatorPriceCeilingV1,
        OpenRouterOutputBoundEvidenceV2,
        OpenRouterRenderedLiveRequestV2,
    )

    record = _revalidate_exact_contract_v1(
        limit_record, TrustedModelInputLimitRecordV1, "model input-limit record"
    )
    checked_overlay = _revalidate_exact_contract_v1(
        overlay, OpenRouterLiveRequestSafetyOverlayV2, "live request overlay"
    )
    checked_request = _revalidate_exact_contract_v1(
        rendered_request, OpenRouterRenderedLiveRequestV2, "rendered live request"
    )
    checked_modality = _revalidate_exact_contract_v1(
        modality_binding,
        OpenRouterLiveRequestModalityBindingV1,
        "live request modality binding",
    )
    checked_output = _revalidate_exact_contract_v1(
        output_bound, OpenRouterOutputBoundEvidenceV2, "output-bound evidence"
    )
    checked_policy = _revalidate_exact_contract_v1(
        provider_policy, OpenRouterOperatorPriceCeilingV1, "provider price policy"
    )

    _require_nonblank(preflight_execution_id, "preflight_execution_id")
    if record.preflight_execution_id != preflight_execution_id:
        raise ContractValidationError(
            "model input-limit record is stale or belongs to another preflight"
        )
    if checked_request.live_request_overlay_id != (
        checked_overlay.live_request_overlay_id
    ):
        raise ContractValidationError(
            "rendered request is bound to a different live overlay"
        )
    if checked_overlay.price_policy_id != checked_policy.price_policy_id:
        raise ContractValidationError(
            "live overlay is bound to a different provider price policy"
        )
    if checked_request.exact_model != checked_overlay.exact_model:
        raise ContractValidationError(
            "rendered request model disagrees with the live overlay"
        )
    if checked_request.exact_model != record.exact_model_id:
        raise ContractValidationError(
            "rendered request model disagrees with the trusted limit record"
        )
    if checked_request.exact_endpoint_selector != (
        checked_overlay.exact_endpoint_selector
    ):
        raise ContractValidationError(
            "rendered request endpoint selector disagrees with the live overlay"
        )
    if checked_request.max_output_tokens != checked_overlay.max_output_tokens:
        raise ContractValidationError(
            "rendered request output limit disagrees with the live overlay"
        )
    if checked_output.max_output_tokens != checked_request.max_output_tokens:
        raise ContractValidationError(
            "output-bound evidence disagrees with the rendered request"
        )
    if (
        checked_output.rendered_request_id != checked_request.rendered_request_id
        or checked_output.live_request_overlay_id
        != checked_request.live_request_overlay_id
        or checked_output.price_policy_id != checked_request.price_policy_id
        or checked_output.body_sha256 != checked_request.body_sha256
        or checked_output.body_length != checked_request.body_length
        or checked_output.exact_model != checked_request.exact_model
    ):
        raise ContractValidationError(
            "output-bound evidence is not bound to the exact rendered request"
        )
    if (
        checked_modality.rendered_request_id != checked_request.rendered_request_id
        or checked_modality.live_request_overlay_id
        != checked_request.live_request_overlay_id
        or checked_modality.price_policy_id != checked_request.price_policy_id
        or checked_modality.body_sha256 != checked_request.body_sha256
        or checked_modality.body_length != checked_request.body_length
        or checked_modality.exact_model != checked_request.exact_model
        or checked_modality.request_modality_proof_id
        != checked_request.request_modality_proof_id
        or checked_modality.message_count != checked_request.message_count
    ):
        raise ContractValidationError(
            "modality evidence is not bound to the exact rendered request"
        )
    if checked_modality.message_count != OPENROUTER_P17_EXPECTED_MESSAGE_COUNT_V1:
        raise ContractValidationError(
            "modality binding does not describe the exact two-message request"
        )
    if checked_modality.text_only is not True:
        raise ContractValidationError(
            "P17 live candidate must retain the exact text-only modality proof"
        )

    return OpenRouterP17InputBoundProofV1(
        preflight_execution_id=preflight_execution_id,
        limit_record=record,
        live_request_overlay_id=checked_overlay.live_request_overlay_id or "",
        rendered_request_id=checked_request.rendered_request_id or "",
        exact_model=checked_request.exact_model,
        request_body_sha256=checked_request.body_sha256,
        request_body_length=checked_request.body_length,
        message_count=checked_modality.message_count,
        modality_binding_id=checked_modality.modality_binding_id or "",
        request_modality_proof_id=(
            checked_modality.request_modality_proof_id
        ),
        text_only=checked_modality.text_only,
        plugins_absent=True,
        tools_enabled=False,
        output_bound_evidence_id=checked_output.output_bound_evidence_id or "",
        max_output_tokens=checked_output.max_output_tokens,
        output_tokens_subtracted_from_context=False,
        provider_price_policy_id=checked_policy.price_policy_id or "",
        exact_endpoint_selector=checked_request.exact_endpoint_selector,
        max_input_tokens=record.limit_tokens,
        limit_kind=record.limit_kind,
        proof_method_version=record.proof_method_version,
        authority=(
            OpenRouterP17ProofAuthorityV1.LIVE_JIT_ESTABLISHED
            if record.is_live_jit_authority
            else OpenRouterP17ProofAuthorityV1.SYNTHETIC_TEST_ONLY
        ),
    )


__all__ = [
    "FROZEN_OPENROUTER_P17_RETAINED_SOURCES_V1",
    "OPENROUTER_P17_API_OVERVIEW_PATH_V1",
    "OPENROUTER_P17_API_OVERVIEW_SHA256_V1",
    "OPENROUTER_P17_API_OVERVIEW_SOURCE_ID_V1",
    "OPENROUTER_P17_CURRENT_AUTHORITY_V1",
    "OPENROUTER_P17_EXACT_ENDPOINT_SELECTOR_V1",
    "OPENROUTER_P17_EXACT_MODEL_V1",
    "OPENROUTER_P17_EXPECTED_MESSAGE_COUNT_V1",
    "OPENROUTER_P17_INPUT_BOUND_PROOF_SCHEMA_V1",
    "OPENROUTER_P17_MAX_OUTPUT_TOKENS_V1",
    "OPENROUTER_P17_MAX_PROMPT_TOKENS_POINTER_V1",
    "OPENROUTER_P17_MODEL_CONTEXT_LENGTH_POINTER_V1",
    "OPENROUTER_P17_MODEL_DETAIL_METHOD_V1",
    "OPENROUTER_P17_MODEL_DETAIL_PATH_V1",
    "OPENROUTER_P17_OPENAPI_PATH_V1",
    "OPENROUTER_P17_OPENAPI_SHA256_V1",
    "OPENROUTER_P17_OPENAPI_SOURCE_ID_V1",
    "OPENROUTER_P17_PROOF_ARCHITECTURE_V1",
    "OPENROUTER_P17_RETAINED_MANIFEST_ID_V1",
    "OPENROUTER_P17_RETAINED_MANIFEST_SHA256_V1",
    "OPENROUTER_P17_RETAINED_OFFICIAL_COMMIT_V1",
    "OPENROUTER_P17_ROUTER_METADATA_PATH_V1",
    "OPENROUTER_P17_ROUTER_METADATA_SHA256_V1",
    "OPENROUTER_P17_ROUTER_METADATA_SOURCE_ID_V1",
    "OPENROUTER_TRUSTED_MODEL_INPUT_LIMIT_SCHEMA_V1",
    "OpenRouterInputLimitAliasStateV1",
    "OpenRouterInputLimitKindV1",
    "OpenRouterInputLimitObservationStatusV1",
    "OpenRouterInputLimitSemanticClaimV1",
    "OpenRouterInputLimitSourceAuthorityV1",
    "OpenRouterInputLimitSourceKindV1",
    "OpenRouterInputLimitSourceScopeV1",
    "OpenRouterP17AuxiliaryPipelineScopeV1",
    "OpenRouterP17FramingCoverageV1",
    "OpenRouterP17InputBoundProofV1",
    "OpenRouterP17ProofAuthorityV1",
    "OpenRouterP17ProofMethodV1",
    "TrustedModelInputLimitRecordV1",
    "build_openrouter_p17_input_bound_proof_v1",
    "build_trusted_model_input_limit_record_from_response_v1",
    "build_trusted_model_input_limit_record_v1",
]
