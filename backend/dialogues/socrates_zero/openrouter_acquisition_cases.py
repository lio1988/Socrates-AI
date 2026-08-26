"""Frozen data-only case design for OpenRouter acquisition adapter controls v0.

This module owns evaluator-side labels, mutation declarations, the first-guard
order, and strict thresholds.  It deliberately imports no adapter, runtime,
provider, environment, credential, transport, or canonical-application path.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id


OPENROUTER_ADAPTER_CASE_SET_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-case-set/v0"
)
OPENROUTER_ADAPTER_GUARD_DESIGN_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-guard-design/v0"
)
OPENROUTER_ADAPTER_VALIDATION_ORDER_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-validation-order/v0"
)
OPENROUTER_ADAPTER_FAILURE_TAXONOMY_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-failure-taxonomy/v0"
)
OPENROUTER_ADAPTER_MUTATION_VECTOR_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-mutation-vector/v0"
)
OPENROUTER_ADAPTER_LITERAL_MUTATION_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-literal-mutation/v0"
)
OPENROUTER_ADAPTER_REQUEST_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-request/v0"
)
OPENROUTER_ADAPTER_POSITIVE_CASE_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-positive-case/v0"
)
OPENROUTER_ADAPTER_PROBE_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-probe/v0"
)
OPENROUTER_ADAPTER_THRESHOLDS_SCHEMA_V0 = (
    "socrateszero-openrouter-acquisition-thresholds/v0"
)
OPENROUTER_ADAPTER_HARNESS_ID_V0 = (
    "socrateszero-openrouter-acquisition-harness/v0"
)
OPENROUTER_ADAPTER_ID_V0 = "socrateszero-openrouter-acquisition-adapter/v0"
OPENROUTER_SELECTED_PROVIDER_V0 = "openrouter"
OPENROUTER_SELECTED_PROVIDER_DISPLAY_V0 = "OpenRouter"
OPENROUTER_SELECTED_MODEL_V0 = "openai/gpt-4.1-mini"
FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0 = "FIRST_ADAPTER_GUARD_WINS"
OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0 = (
    "szorfixture_8d2c355b7f8a3297be9c5e9de344c9bff03c2afbf4579bf93eaa136572598b77"
)
OPENROUTER_ADAPTER_BASELINE_PROJECTION_SHA256_V0 = (
    "63f28955c510351e8b5ef2606f116eb6ab22ab85177982ef0dcda000eacf3f22"
)
OPENROUTER_ADAPTER_CANDIDATE_ADAPTER_ID_V0 = (
    "socrateszero-openrouter-acquisition-adapter-controls/v0"
)
OPENROUTER_ADAPTER_SEMANTIC_REQUEST_ID_V0 = (
    "szacqrequest_3d128032b3e83fcff3fffbc809451eb1cd252c2ba6889571e3a8b975c38ecb2f"
)
OPENROUTER_ADAPTER_SOURCE_VISIBLE_REQUEST_ID_V0 = (
    "szacqvisible_ea8c396387199ef8911a21c013f4ea7cc92fb502afdb92a3a695eb8b3a9b4bab"
)
OPENROUTER_ADAPTER_CAPABILITY_SNAPSHOT_ID_V0 = (
    "szorcap_c1ad52878f6013bc37a58949decf6c28d396dbef0f133db89124e9dcf08abb15"
)
OPENROUTER_ADAPTER_ENDPOINT_POLICY_ID_V0 = (
    "szorendpoint_1fcbacda717ffe27a18aaf133a418c1be569f751e34175ce2afe50043e408015"
)
OPENROUTER_ADAPTER_ROUTE_POLICY_ID_V0 = (
    "szorroute_326db7be7fc68dc0eb22db9271d74073eaa59cffb16ff3524db847070c865071"
)
OPENROUTER_ADAPTER_CONTROL_POLICY_ID_V0 = (
    "szorcontrol_1af1db4f46a9abe6b2d66c85812beb95f66ee6d5adc8f27ff40fb19defd203e7"
)
OPENROUTER_ADAPTER_PREPARED_BODY_ID_V0 = (
    "szorbody_c0b249765331603da69c395619476b198c76584ff36f4185b0aaf4cc3c6deadd"
)
OPENROUTER_ADAPTER_TRANSPORT_POLICY_ID_V0 = (
    "szortransport_4e5e882e46753c551651592abedc9e84da5495587eb052ccce010f0ee39a3231"
)
OPENROUTER_ADAPTER_TOKEN_POLICY_ID_V0 = (
    "szortokens_1f15f1d831cc1cdc539c53ffe64fc55f9d069f56439ee9542ec1e49238fdd9a1"
)
OPENROUTER_ADAPTER_PRICING_RECORD_ID_V0 = (
    "szorprice_e8584e5c6aaa7192a05a336b771f822d9676af6107d8760d7dc598a7dcba1949"
)
OPENROUTER_ADAPTER_COST_BOUND_ID_V0 = (
    "szorcost_7da097f344dca77f26a5d0d635ef1fa4b387da7ed1f6e5e18e93fdaae5b8d11e"
)
OPENROUTER_ADAPTER_RAW_RESPONSE_EVIDENCE_ID_V0 = (
    "szorraw_7b33ff273ea5bc844820d59c5042a1992eacf5176be87328d2705669311ba464"
)
OPENROUTER_ADAPTER_IDENTITY_EVIDENCE_ID_V0 = (
    "szoridentity_5d6ee5c719780270cceff1521ca39f9dc2aa3b41970c23a952527ebcfba135e0"
)
OPENROUTER_ADAPTER_USAGE_EVIDENCE_ID_V0 = (
    "szorusage_ce4d7a352ff821264102d077de7ab5cdec4a6b487a52f2dd895256093c8966e4"
)
OPENROUTER_ADAPTER_CANNED_ENVELOPE_ID_V0 = (
    "szorenvelope_85949fb30050330411f69a9145cfa5cd04420c874fe8e2527740603dfd1f2b48"
)
OPENROUTER_ADAPTER_ATTEMPT_RECEIPT_ID_V0 = (
    "szorattempt_8d8a5e847724b6f5281865cb95f4360ccfcb42ae604359885a36cbc33e065bfa"
)
OPENROUTER_ADAPTER_POSITIVE_EXPECTATION_ROLE_V0 = (
    "FROZEN_SUCCESS_THRESHOLD_EXPECTATIONS_NOT_CANDIDATE_PROOF"
)


class _FrozenCaseContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpenRouterAdapterCaseClass(str, Enum):
    POSITIVE = "POSITIVE"
    ORTHOGONAL = "ORTHOGONAL"
    PRECEDENCE = "PRECEDENCE"


class OpenRouterAdapterGuardStage(str, Enum):
    PRE_DISPATCH = "PRE_DISPATCH"
    POST_RESPONSE = "POST_RESPONSE"


class OpenRouterAdapterGuardState(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_REACHED = "NOT_REACHED"


class OpenRouterAdapterAttemptOutcome(str, Enum):
    EVIDENCE_READY = "EVIDENCE_READY"
    REJECTED = "REJECTED"


class MutationState(str, Enum):
    PRESERVED = "PRESERVED"
    INTENTIONALLY_CHANGED = "INTENTIONALLY_CHANGED"
    DEPENDENTLY_CHANGED = "DEPENDENTLY_CHANGED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OpenRouterAdapterGuardId(str, Enum):
    P01_REQUEST_INTEGRITY = "P01_REQUEST_INTEGRITY"
    P02_SEMANTIC_INPUT_INTEGRITY = "P02_SEMANTIC_INPUT_INTEGRITY"
    P03_CONTROL_SNAPSHOT_INTEGRITY = "P03_CONTROL_SNAPSHOT_INTEGRITY"
    P04_RENDERER_VERSION = "P04_RENDERER_VERSION"
    P05_CANONICAL_BODY_INTEGRITY = "P05_CANONICAL_BODY_INTEGRITY"
    P06_ENTROPY_CREDENTIAL_FIREWALL = "P06_ENTROPY_CREDENTIAL_FIREWALL"
    P07_REQUESTED_IDENTITY = "P07_REQUESTED_IDENTITY"
    P08_ROUTE_POLICY = "P08_ROUTE_POLICY"
    P09_FALLBACK_INTENT = "P09_FALLBACK_INTENT"
    P10_RETRY_POLICY = "P10_RETRY_POLICY"
    P11_ONE_SHOT_POLICY = "P11_ONE_SHOT_POLICY"
    P12_STREAM_POLICY = "P12_STREAM_POLICY"
    P13_TOOL_POLICY = "P13_TOOL_POLICY"
    P14_TEMPERATURE = "P14_TEMPERATURE"
    P15_SEED = "P15_SEED"
    P16_OUTPUT_TOKEN_CAP = "P16_OUTPUT_TOKEN_CAP"
    P17_INPUT_TOKEN_BOUND = "P17_INPUT_TOKEN_BOUND"
    P18_PRICING_RECORD = "P18_PRICING_RECORD"
    P19_COST_BOUND = "P19_COST_BOUND"
    P20_ENDPOINT_POLICY = "P20_ENDPOINT_POLICY"
    P21_REDIRECT_POLICY = "P21_REDIRECT_POLICY"
    P22_PROXY_POLICY = "P22_PROXY_POLICY"
    P23_TIMEOUT_POLICY = "P23_TIMEOUT_POLICY"
    P24_CANNED_REGISTRATION = "P24_CANNED_REGISTRATION"
    A01_INVOCATION_COUNT = "A01_INVOCATION_COUNT"
    A02_TRANSPORT_COMPLETION = "A02_TRANSPORT_COMPLETION"
    A03_WORKER_TERMINATION = "A03_WORKER_TERMINATION"
    A04_LATE_MUTATION = "A04_LATE_MUTATION"
    A05_RAW_RESPONSE_PRESENCE = "A05_RAW_RESPONSE_PRESENCE"
    A06_RAW_RESPONSE_INTEGRITY = "A06_RAW_RESPONSE_INTEGRITY"
    A07_ENVELOPE_PARSE = "A07_ENVELOPE_PARSE"
    A08_ACTUAL_PROVIDER = "A08_ACTUAL_PROVIDER"
    A09_ACTUAL_MODEL = "A09_ACTUAL_MODEL"
    A10_ACTUAL_CONFIGURATION = "A10_ACTUAL_CONFIGURATION"
    A11_FALLBACK_STATUS = "A11_FALLBACK_STATUS"
    A12_RETRY_STATUS = "A12_RETRY_STATUS"
    A13_STREAM_STATUS = "A13_STREAM_STATUS"
    A14_TOOL_STATUS = "A14_TOOL_STATUS"
    A15_USAGE_COMPLETENESS = "A15_USAGE_COMPLETENESS"
    A16_USAGE_CONSISTENCY = "A16_USAGE_CONSISTENCY"
    A17_TOKEN_BOUNDS = "A17_TOKEN_BOUNDS"
    A18_COST_LINKAGE = "A18_COST_LINKAGE"
    A19_RETENTION_PRIVACY = "A19_RETENTION_PRIVACY"
    A20_FINAL_RECEIPT_INTEGRITY = "A20_FINAL_RECEIPT_INTEGRITY"


FROZEN_OPENROUTER_ADAPTER_KNOWN_UNRESOLVED_GUARDS_V0: Tuple[
    OpenRouterAdapterGuardId, ...
] = (
    OpenRouterAdapterGuardId.P08_ROUTE_POLICY,
    OpenRouterAdapterGuardId.P09_FALLBACK_INTENT,
    OpenRouterAdapterGuardId.P17_INPUT_TOKEN_BOUND,
    OpenRouterAdapterGuardId.P18_PRICING_RECORD,
    OpenRouterAdapterGuardId.P19_COST_BOUND,
)


class OpenRouterAdapterFailureCode(str, Enum):
    INVALID_ADAPTER_REQUEST = "INVALID_ADAPTER_REQUEST"
    INVALID_SEMANTIC_INPUT = "INVALID_SEMANTIC_INPUT"
    INVALID_CONTROL_SNAPSHOT = "INVALID_CONTROL_SNAPSHOT"
    RENDERER_VERSION_MISMATCH = "RENDERER_VERSION_MISMATCH"
    NONCANONICAL_BODY = "NONCANONICAL_BODY"
    BODY_DIGEST_OR_LENGTH_MISMATCH = "BODY_DIGEST_OR_LENGTH_MISMATCH"
    FORBIDDEN_ENTROPY = "FORBIDDEN_ENTROPY"
    CREDENTIAL_OR_HEADER_LEAKAGE = "CREDENTIAL_OR_HEADER_LEAKAGE"
    REQUESTED_IDENTITY_MISMATCH = "REQUESTED_IDENTITY_MISMATCH"
    ROUTE_POLICY_UNPROVEN = "ROUTE_POLICY_UNPROVEN"
    FALLBACK_INTENT_NOT_DISABLED = "FALLBACK_INTENT_NOT_DISABLED"
    RETRY_POLICY_UNPROVEN = "RETRY_POLICY_UNPROVEN"
    ATTEMPT_LIMIT_NOT_ONE = "ATTEMPT_LIMIT_NOT_ONE"
    STREAM_NOT_DISABLED = "STREAM_NOT_DISABLED"
    TOOLS_NOT_DISABLED = "TOOLS_NOT_DISABLED"
    TEMPERATURE_NOT_ZERO = "TEMPERATURE_NOT_ZERO"
    SEED_NOT_UNSUPPORTED_OR_EMITTED = "SEED_NOT_UNSUPPORTED_OR_EMITTED"
    OUTPUT_TOKEN_CAP_INVALID = "OUTPUT_TOKEN_CAP_INVALID"
    INPUT_BOUND_UNPROVEN = "INPUT_BOUND_UNPROVEN"
    PRICING_NOT_ESTABLISHED = "PRICING_NOT_ESTABLISHED"
    PRICING_BINDING_MISMATCH = "PRICING_BINDING_MISMATCH"
    COST_BOUND_INVALID = "COST_BOUND_INVALID"
    COST_OVERFLOW = "COST_OVERFLOW"
    ENDPOINT_MISMATCH = "ENDPOINT_MISMATCH"
    REDIRECTS_NOT_DISABLED = "REDIRECTS_NOT_DISABLED"
    PROXY_INHERITANCE_NOT_DISABLED = "PROXY_INHERITANCE_NOT_DISABLED"
    TIMEOUT_POLICY_INCOMPLETE = "TIMEOUT_POLICY_INCOMPLETE"
    CANNED_TRANSPORT_UNREGISTERED = "CANNED_TRANSPORT_UNREGISTERED"
    MULTIPLE_TRANSPORT_INVOCATIONS = "MULTIPLE_TRANSPORT_INVOCATIONS"
    TRANSPORT_TIMEOUT = "TRANSPORT_TIMEOUT"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    TRANSPORT_CANCELLED = "TRANSPORT_CANCELLED"
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
    FALSE_ZERO_USAGE = "FALSE_ZERO_USAGE"
    USAGE_INCONSISTENT = "USAGE_INCONSISTENT"
    REPORTED_USAGE_EXCEEDS_BOUND = "REPORTED_USAGE_EXCEEDS_BOUND"
    COST_LINK_MISMATCH = "COST_LINK_MISMATCH"
    RETENTION_OR_PRIVACY_VIOLATION = "RETENTION_OR_PRIVACY_VIOLATION"
    RECEIPT_MISMATCH = "RECEIPT_MISMATCH"


class OpenRouterAdapterMutationVectorV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_MUTATION_VECTOR_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_MUTATION_VECTOR_SCHEMA_V0
    request_integrity: MutationState = MutationState.PRESERVED
    semantic_input: MutationState = MutationState.PRESERVED
    control_snapshot: MutationState = MutationState.PRESERVED
    renderer_version: MutationState = MutationState.PRESERVED
    canonical_body: MutationState = MutationState.PRESERVED
    entropy_credential_firewall: MutationState = MutationState.PRESERVED
    requested_identity: MutationState = MutationState.PRESERVED
    route_policy: MutationState = MutationState.PRESERVED
    fallback_intent: MutationState = MutationState.PRESERVED
    retry_policy: MutationState = MutationState.PRESERVED
    one_shot_policy: MutationState = MutationState.PRESERVED
    stream_policy: MutationState = MutationState.PRESERVED
    tool_policy: MutationState = MutationState.PRESERVED
    temperature: MutationState = MutationState.PRESERVED
    seed: MutationState = MutationState.PRESERVED
    output_token_cap: MutationState = MutationState.PRESERVED
    input_token_bound: MutationState = MutationState.PRESERVED
    pricing_record: MutationState = MutationState.PRESERVED
    cost_bound: MutationState = MutationState.PRESERVED
    endpoint_policy: MutationState = MutationState.PRESERVED
    redirect_policy: MutationState = MutationState.PRESERVED
    proxy_policy: MutationState = MutationState.PRESERVED
    timeout_policy: MutationState = MutationState.PRESERVED
    canned_registration: MutationState = MutationState.PRESERVED
    invocation_count: MutationState = MutationState.PRESERVED
    transport_completion: MutationState = MutationState.PRESERVED
    worker_termination: MutationState = MutationState.PRESERVED
    late_mutation: MutationState = MutationState.PRESERVED
    raw_response_presence: MutationState = MutationState.PRESERVED
    raw_response_integrity: MutationState = MutationState.PRESERVED
    envelope_parse: MutationState = MutationState.PRESERVED
    actual_provider: MutationState = MutationState.PRESERVED
    actual_model: MutationState = MutationState.PRESERVED
    actual_configuration: MutationState = MutationState.PRESERVED
    fallback_status: MutationState = MutationState.PRESERVED
    retry_status: MutationState = MutationState.PRESERVED
    stream_status: MutationState = MutationState.PRESERVED
    tool_status: MutationState = MutationState.PRESERVED
    usage_completeness: MutationState = MutationState.PRESERVED
    usage_consistency: MutationState = MutationState.PRESERVED
    token_bounds: MutationState = MutationState.PRESERVED
    cost_linkage: MutationState = MutationState.PRESERVED
    retention_privacy: MutationState = MutationState.PRESERVED
    receipt_identity: MutationState = MutationState.PRESERVED


MUTATION_VECTOR_FIELD_NAMES_V0: Tuple[str, ...] = tuple(
    name
    for name in OpenRouterAdapterMutationVectorV0.model_fields
    if name != "schema_version"
)


class OpenRouterAdapterMutationPathKind(str, Enum):
    COMMITTED_SURFACE = "COMMITTED_SURFACE"
    EVALUATOR_DRAFT = "EVALUATOR_DRAFT"
    EVALUATOR_DERIVED = "EVALUATOR_DERIVED"


class OpenRouterAdapterMutationPathSpecV0(_FrozenCaseContract):
    path: str = Field(min_length=1)
    path_kind: OpenRouterAdapterMutationPathKind
    source_contract: str = Field(min_length=1)
    baseline_json: str
    guard_id: OpenRouterAdapterGuardId
    mutation_vector_field: str

    @field_validator("baseline_json")
    @classmethod
    def canonical_baseline(cls, value: str) -> str:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ContractValidationError(
                "mutation-path baseline must be valid JSON"
            ) from exc
        if canonical_json(parsed) != value:
            raise ContractValidationError(
                "mutation-path baseline must be canonical JSON"
            )
        return value

    @field_validator("mutation_vector_field")
    @classmethod
    def known_vector_field(cls, value: str) -> str:
        if value not in MUTATION_VECTOR_FIELD_NAMES_V0:
            raise ContractValidationError(
                "mutation-path registry names an unknown vector field"
            )
        return value


_FROZEN_CANONICAL_BODY_JSON_V0 = (
    "{\"max_tokens\":256,\"messages\":[{\"content\":\"Ask one concise opening "
    "Socratic question without answering the user's question.\",\"role\":\"system\"},"
    "{\"content\":\"Is knowledge merely justified true belief?\",\"role\":\"user\"}],"
    "\"model\":\"openai/gpt-4.1-mini\",\"response_format\":{\"type\":\"text\"},"
    "\"stream\":false,\"temperature\":0.0,\"tools\":[]}"
)
_FROZEN_CONTROL_CONFIGURATION_DIGEST_V0 = (
    "1af1db4f46a9abe6b2d66c85812beb95f66ee6d5adc8f27ff40fb19defd203e7"
)
_FROZEN_RAW_RESPONSE_SHA256_V0 = (
    "bc498de15ee1c21d63fce3e2e114dfe6326d8618ac2a06ed615b8fbc6983a10b"
)


def _path_spec(
    path: str,
    baseline: object,
    guard_id: OpenRouterAdapterGuardId,
    vector_field: str,
    source_contract: str,
    *,
    kind: OpenRouterAdapterMutationPathKind = (
        OpenRouterAdapterMutationPathKind.COMMITTED_SURFACE
    ),
) -> OpenRouterAdapterMutationPathSpecV0:
    return OpenRouterAdapterMutationPathSpecV0(
        path=path,
        path_kind=kind,
        source_contract=source_contract,
        baseline_json=canonical_json(baseline),
        guard_id=guard_id,
        mutation_vector_field=vector_field,
    )


_PG = OpenRouterAdapterGuardId
_PK = OpenRouterAdapterMutationPathKind
FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0: Tuple[
    OpenRouterAdapterMutationPathSpecV0, ...
] = (
    _path_spec("request.schema_version", OPENROUTER_ADAPTER_REQUEST_SCHEMA_V0, _PG.P01_REQUEST_INTEGRITY, "request_integrity", "OpenRouterAdapterRequestV0"),
    _path_spec("evaluator_draft.semantic_input.process_id", None, _PG.P02_SEMANTIC_INPUT_INTEGRITY, "semantic_input", "EvaluatorDraftSemanticInputV0", kind=_PK.EVALUATOR_DRAFT),
    _path_spec("prepared_body.renderer_version", "socrateszero-openrouter-renderer/v0", _PG.P04_RENDERER_VERSION, "renderer_version", "OpenRouterPreparedBody"),
    _path_spec("prepared_body.canonical_body_json", _FROZEN_CANONICAL_BODY_JSON_V0, _PG.P05_CANONICAL_BODY_INTEGRITY, "canonical_body", "OpenRouterPreparedBody"),
    _path_spec("evaluator_draft.prepared_body.metadata.process_id", None, _PG.P06_ENTROPY_CREDENTIAL_FIREWALL, "entropy_credential_firewall", "EvaluatorDraftPreparedBodyV0", kind=_PK.EVALUATOR_DRAFT),
    _path_spec("evaluator_draft.prepared_body.metadata.branch_id", None, _PG.P06_ENTROPY_CREDENTIAL_FIREWALL, "entropy_credential_firewall", "EvaluatorDraftPreparedBodyV0", kind=_PK.EVALUATOR_DRAFT),
    _path_spec("evaluator_draft.semantic_headers.authorization_presence", "ABSENT", _PG.P06_ENTROPY_CREDENTIAL_FIREWALL, "entropy_credential_firewall", "EvaluatorDraftSemanticHeadersV0", kind=_PK.EVALUATOR_DRAFT),
    _path_spec("route_policy.upstream_route_state", "NOT_ESTABLISHED", _PG.P08_ROUTE_POLICY, "route_policy", "OpenRouterRoutePolicy"),
    _path_spec("route_policy.application_fallback_allowed", False, _PG.P09_FALLBACK_INTENT, "fallback_intent", "OpenRouterRoutePolicy"),
    _path_spec("route_policy.adapter_fallback_allowed", False, _PG.P09_FALLBACK_INTENT, "fallback_intent", "OpenRouterRoutePolicy"),
    _path_spec("prepared_body.stream", False, _PG.P12_STREAM_POLICY, "stream_policy", "OpenRouterPreparedBody.canonical_body_json"),
    _path_spec("prepared_body.tools", [], _PG.P13_TOOL_POLICY, "tool_policy", "OpenRouterPreparedBody.canonical_body_json"),
    _path_spec("prepared_body.temperature", 0.0, _PG.P14_TEMPERATURE, "temperature", "OpenRouterPreparedBody.canonical_body_json"),
    _path_spec("prepared_body.seed", None, _PG.P15_SEED, "seed", "OpenRouterPreparedBody.canonical_body_json"),
    _path_spec("prepared_body.max_tokens", 256, _PG.P16_OUTPUT_TOKEN_CAP, "output_token_cap", "OpenRouterPreparedBody.canonical_body_json"),
    _path_spec("token_policy.provider_input_token_bound_state", "NOT_ESTABLISHED", _PG.P17_INPUT_TOKEN_BOUND, "input_token_bound", "OpenRouterTokenPolicy"),
    _path_spec("cost_bound.pricing_record.pricing_record_id", OPENROUTER_ADAPTER_PRICING_RECORD_ID_V0, _PG.P18_PRICING_RECORD, "pricing_record", "OpenRouterCostBound.pricing_record"),
    _path_spec("pricing_record.model_id", OPENROUTER_SELECTED_MODEL_V0, _PG.P18_PRICING_RECORD, "pricing_record", "OpenRouterPricingRecord"),
    _path_spec("pricing_record.output_microusd_per_million_tokens", None, _PG.P19_COST_BOUND, "cost_bound", "OpenRouterPricingRecord"),
    _path_spec("endpoint_policy.path", "/api/v1/chat/completions", _PG.P20_ENDPOINT_POLICY, "endpoint_policy", "OpenRouterEndpointPolicy"),
    _path_spec("endpoint_policy.redirects_allowed", False, _PG.P21_REDIRECT_POLICY, "redirect_policy", "OpenRouterEndpointPolicy"),
    _path_spec("endpoint_policy.environment_proxy_allowed", False, _PG.P22_PROXY_POLICY, "proxy_policy", "OpenRouterEndpointPolicy"),
    _path_spec("transport_policy.canned_cancellation_grace_ms", 50, _PG.P23_TIMEOUT_POLICY, "timeout_policy", "OpenRouterTransportPolicy"),
    _path_spec("evaluator_derived.canned_transport_registered", True, _PG.P24_CANNED_REGISTRATION, "canned_registration", "OpenRouterCannedTransportV0.implementation_id", kind=_PK.EVALUATOR_DERIVED),
    _path_spec("evaluator_derived.transport_invocation_count", 1, _PG.A01_INVOCATION_COUNT, "invocation_count", "OpenRouterCannedInvocationRecord", kind=_PK.EVALUATOR_DERIVED),
    _path_spec("envelope.transport_status", "DELIVERED", _PG.A02_TRANSPORT_COMPLETION, "transport_completion", "OpenRouterCannedResponseEnvelope"),
    _path_spec("invocation_record.worker_terminated", True, _PG.A03_WORKER_TERMINATION, "worker_termination", "OpenRouterCannedInvocationRecord"),
    _path_spec("directive.attempt_late_mutation", False, _PG.A04_LATE_MUTATION, "late_mutation", "OpenRouterCannedResponseDirective"),
    _path_spec("envelope.raw_response.raw_response_evidence_id", OPENROUTER_ADAPTER_RAW_RESPONSE_EVIDENCE_ID_V0, _PG.A05_RAW_RESPONSE_PRESENCE, "raw_response_presence", "OpenRouterCannedResponseEnvelope.raw_response"),
    _path_spec("raw_response.reported_sha256", _FROZEN_RAW_RESPONSE_SHA256_V0, _PG.A06_RAW_RESPONSE_INTEGRITY, "raw_response_integrity", "OpenRouterRawResponseEvidence"),
    _path_spec("evaluator_derived.envelope_parse_state", "COMPLETE_TYPED_ENVELOPE", _PG.A07_ENVELOPE_PARSE, "envelope_parse", "OpenRouterCannedResponseEnvelope.model_validate", kind=_PK.EVALUATOR_DERIVED),
    _path_spec("identity_evidence.actual_router_id", OPENROUTER_SELECTED_PROVIDER_V0, _PG.A08_ACTUAL_PROVIDER, "actual_provider", "OpenRouterIdentityEvidence"),
    _path_spec("identity_evidence.actual_model_id", OPENROUTER_SELECTED_MODEL_V0, _PG.A09_ACTUAL_MODEL, "actual_model", "OpenRouterIdentityEvidence"),
    _path_spec("identity_evidence.actual_configuration_digest", _FROZEN_CONTROL_CONFIGURATION_DIGEST_V0, _PG.A10_ACTUAL_CONFIGURATION, "actual_configuration", "OpenRouterIdentityEvidence"),
    _path_spec("identity_evidence.fallback_used", False, _PG.A11_FALLBACK_STATUS, "fallback_status", "OpenRouterIdentityEvidence"),
    _path_spec("envelope.adapter_retry_count", 0, _PG.A12_RETRY_STATUS, "retry_status", "OpenRouterCannedResponseEnvelope"),
    _path_spec("envelope.stream_used", False, _PG.A13_STREAM_STATUS, "stream_status", "OpenRouterCannedResponseEnvelope"),
    _path_spec("envelope.tool_calls", 0, _PG.A14_TOOL_STATUS, "tool_status", "OpenRouterCannedResponseEnvelope"),
    _path_spec("usage_evidence.token_completeness", "COMPLETE", _PG.A15_USAGE_COMPLETENESS, "usage_completeness", "OpenRouterUsageEvidence"),
    _path_spec("usage_evidence.input_tokens", 10, _PG.A15_USAGE_COMPLETENESS, "usage_completeness", "OpenRouterUsageEvidence"),
    _path_spec("usage_evidence.total_tokens", 18, _PG.A16_USAGE_CONSISTENCY, "usage_consistency", "OpenRouterUsageEvidence"),
    _path_spec("usage_evidence.output_tokens", 8, _PG.A17_TOKEN_BOUNDS, "token_bounds", "OpenRouterUsageEvidence"),
    _path_spec("attempt_receipt.usage_evidence.cost_bound_id", None, _PG.A18_COST_LINKAGE, "cost_linkage", "OpenRouterAttemptReceipt.usage_evidence"),
    _path_spec("attempt_receipt.attempt_receipt_id", OPENROUTER_ADAPTER_ATTEMPT_RECEIPT_ID_V0, _PG.A20_FINAL_RECEIPT_INTEGRITY, "receipt_identity", "OpenRouterAttemptReceipt"),
)

_MUTATION_PATH_SPEC_BY_PATH_V0 = {
    item.path: item for item in FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0
}
if len(_MUTATION_PATH_SPEC_BY_PATH_V0) != len(
    FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0
):
    raise ContractValidationError("mutation-path registry contains duplicate paths")

OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_ID_V0 = stable_contract_id(
    "oracqpaths",
    tuple(
        item.model_dump(mode="json")
        for item in FROZEN_OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_V0
    ),
)


class OpenRouterAdapterLiteralMutationV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_LITERAL_MUTATION_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_LITERAL_MUTATION_SCHEMA_V0
    path: str = Field(min_length=1)
    before_json: str
    after_json: str
    independent_authoritative_input: bool = True

    @field_validator("before_json", "after_json")
    @classmethod
    def canonical_literal(cls, value: str) -> str:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ContractValidationError("mutation literal must be valid JSON") from exc
        if canonical_json(parsed) != value:
            raise ContractValidationError("mutation literal must be canonical JSON")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "OpenRouterAdapterLiteralMutationV0":
        if self.before_json == self.after_json:
            raise ContractValidationError("mutation must change its declared literal")
        spec = _MUTATION_PATH_SPEC_BY_PATH_V0.get(self.path)
        if spec is None:
            raise ContractValidationError("mutation path is not in the frozen registry")
        if self.before_json != spec.baseline_json:
            raise ContractValidationError(
                "mutation baseline differs from the frozen candidate projection"
            )
        return self


class OpenRouterAdapterGuardDesignStepV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_GUARD_DESIGN_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_GUARD_DESIGN_SCHEMA_V0
    order_index: int = Field(ge=1, le=44, strict=True)
    guard_id: OpenRouterAdapterGuardId
    stage: OpenRouterAdapterGuardStage
    check: str = Field(min_length=3)
    failure_codes: Tuple[OpenRouterAdapterFailureCode, ...] = Field(min_length=1)

    @field_validator("failure_codes")
    @classmethod
    def unique_failures(
        cls, value: Tuple[OpenRouterAdapterFailureCode, ...]
    ) -> Tuple[OpenRouterAdapterFailureCode, ...]:
        if len(value) != len(set(value)):
            raise ContractValidationError("guard failure codes must be unique")
        return value


class OpenRouterAdapterGuardExpectationV0(_FrozenCaseContract):
    guard_id: OpenRouterAdapterGuardId
    state: OpenRouterAdapterGuardState


_G = OpenRouterAdapterGuardId
_F = OpenRouterAdapterFailureCode
_S = OpenRouterAdapterGuardStage

_GUARD_ROWS: Tuple[
    Tuple[
        OpenRouterAdapterGuardId,
        OpenRouterAdapterGuardStage,
        str,
        Tuple[OpenRouterAdapterFailureCode, ...],
    ],
    ...,
] = (
    (_G.P01_REQUEST_INTEGRITY, _S.PRE_DISPATCH, "adapter request integrity", (_F.INVALID_ADAPTER_REQUEST,)),
    (_G.P02_SEMANTIC_INPUT_INTEGRITY, _S.PRE_DISPATCH, "semantic-only input integrity", (_F.INVALID_SEMANTIC_INPUT,)),
    (_G.P03_CONTROL_SNAPSHOT_INTEGRITY, _S.PRE_DISPATCH, "capability and control snapshot integrity", (_F.INVALID_CONTROL_SNAPSHOT,)),
    (_G.P04_RENDERER_VERSION, _S.PRE_DISPATCH, "frozen renderer version", (_F.RENDERER_VERSION_MISMATCH,)),
    (_G.P05_CANONICAL_BODY_INTEGRITY, _S.PRE_DISPATCH, "canonical body schema bytes digest and length", (_F.NONCANONICAL_BODY, _F.BODY_DIGEST_OR_LENGTH_MISMATCH)),
    (_G.P06_ENTROPY_CREDENTIAL_FIREWALL, _S.PRE_DISPATCH, "recursive entropy credential and header firewall", (_F.FORBIDDEN_ENTROPY, _F.CREDENTIAL_OR_HEADER_LEAKAGE)),
    (_G.P07_REQUESTED_IDENTITY, _S.PRE_DISPATCH, "requested provider model and configuration identity", (_F.REQUESTED_IDENTITY_MISMATCH,)),
    (_G.P08_ROUTE_POLICY, _S.PRE_DISPATCH, "route policy completeness", (_F.ROUTE_POLICY_UNPROVEN,)),
    (_G.P09_FALLBACK_INTENT, _S.PRE_DISPATCH, "upstream fallback request intent", (_F.FALLBACK_INTENT_NOT_DISABLED,)),
    (_G.P10_RETRY_POLICY, _S.PRE_DISPATCH, "application registry adapter SDK and HTTP retry policy", (_F.RETRY_POLICY_UNPROVEN,)),
    (_G.P11_ONE_SHOT_POLICY, _S.PRE_DISPATCH, "one-shot attempt ceiling", (_F.ATTEMPT_LIMIT_NOT_ONE,)),
    (_G.P12_STREAM_POLICY, _S.PRE_DISPATCH, "streaming disabled", (_F.STREAM_NOT_DISABLED,)),
    (_G.P13_TOOL_POLICY, _S.PRE_DISPATCH, "tools disabled", (_F.TOOLS_NOT_DISABLED,)),
    (_G.P14_TEMPERATURE, _S.PRE_DISPATCH, "temperature exactly zero", (_F.TEMPERATURE_NOT_ZERO,)),
    (_G.P15_SEED, _S.PRE_DISPATCH, "seed unsupported and omitted", (_F.SEED_NOT_UNSUPPORTED_OR_EMITTED,)),
    (_G.P16_OUTPUT_TOKEN_CAP, _S.PRE_DISPATCH, "positive exact output-token cap", (_F.OUTPUT_TOKEN_CAP_INVALID,)),
    (_G.P17_INPUT_TOKEN_BOUND, _S.PRE_DISPATCH, "safe deterministic input-token upper bound", (_F.INPUT_BOUND_UNPROVEN,)),
    (_G.P18_PRICING_RECORD, _S.PRE_DISPATCH, "truthful immutable pricing record", (_F.PRICING_NOT_ESTABLISHED, _F.PRICING_BINDING_MISMATCH)),
    (_G.P19_COST_BOUND, _S.PRE_DISPATCH, "integer conservative cost bound", (_F.COST_BOUND_INVALID, _F.COST_OVERFLOW)),
    (_G.P20_ENDPOINT_POLICY, _S.PRE_DISPATCH, "exact logical endpoint method and content type", (_F.ENDPOINT_MISMATCH,)),
    (_G.P21_REDIRECT_POLICY, _S.PRE_DISPATCH, "redirects requested disabled", (_F.REDIRECTS_NOT_DISABLED,)),
    (_G.P22_PROXY_POLICY, _S.PRE_DISPATCH, "environment proxy inheritance requested disabled", (_F.PROXY_INHERITANCE_NOT_DISABLED,)),
    (_G.P23_TIMEOUT_POLICY, _S.PRE_DISPATCH, "bounded timeout and cancellation policy", (_F.TIMEOUT_POLICY_INCOMPLETE,)),
    (_G.P24_CANNED_REGISTRATION, _S.PRE_DISPATCH, "exact canned transport registration", (_F.CANNED_TRANSPORT_UNREGISTERED,)),
    (_G.A01_INVOCATION_COUNT, _S.POST_RESPONSE, "one canned invocation", (_F.MULTIPLE_TRANSPORT_INVOCATIONS,)),
    (_G.A02_TRANSPORT_COMPLETION, _S.POST_RESPONSE, "transport terminal completion", (_F.TRANSPORT_TIMEOUT, _F.TRANSPORT_ERROR, _F.TRANSPORT_CANCELLED)),
    (_G.A03_WORKER_TERMINATION, _S.POST_RESPONSE, "all canned tasks terminated", (_F.WORKER_NOT_TERMINATED,)),
    (_G.A04_LATE_MUTATION, _S.POST_RESPONSE, "no late receipt mutation", (_F.LATE_MUTATION_DETECTED,)),
    (_G.A05_RAW_RESPONSE_PRESENCE, _S.POST_RESPONSE, "raw response bytes present", (_F.MISSING_RAW_RESPONSE,)),
    (_G.A06_RAW_RESPONSE_INTEGRITY, _S.POST_RESPONSE, "raw response digest and length", (_F.RAW_DIGEST_OR_LENGTH_MISMATCH,)),
    (_G.A07_ENVELOPE_PARSE, _S.POST_RESPONSE, "typed response envelope parse", (_F.MALFORMED_RESPONSE_ENVELOPE,)),
    (_G.A08_ACTUAL_PROVIDER, _S.POST_RESPONSE, "actual provider identity", (_F.ACTUAL_PROVIDER_MISMATCH,)),
    (_G.A09_ACTUAL_MODEL, _S.POST_RESPONSE, "actual exact model identity", (_F.ACTUAL_MODEL_MISSING, _F.ACTUAL_MODEL_MISMATCH)),
    (_G.A10_ACTUAL_CONFIGURATION, _S.POST_RESPONSE, "actual configuration identity", (_F.ACTUAL_CONFIGURATION_MISMATCH,)),
    (_G.A11_FALLBACK_STATUS, _S.POST_RESPONSE, "fallback not activated", (_F.FALLBACK_ACTIVATED,)),
    (_G.A12_RETRY_STATUS, _S.POST_RESPONSE, "retry count zero", (_F.RETRY_ACTIVATED,)),
    (_G.A13_STREAM_STATUS, _S.POST_RESPONSE, "complete non-streaming response", (_F.STREAMING_RESPONSE_DETECTED,)),
    (_G.A14_TOOL_STATUS, _S.POST_RESPONSE, "tool-call count zero", (_F.TOOL_ACTIVATED,)),
    (_G.A15_USAGE_COMPLETENESS, _S.POST_RESPONSE, "typed complete usage and no false zero", (_F.USAGE_INCOMPLETE, _F.FALSE_ZERO_USAGE)),
    (_G.A16_USAGE_CONSISTENCY, _S.POST_RESPONSE, "input plus output equals total", (_F.USAGE_INCONSISTENT,)),
    (_G.A17_TOKEN_BOUNDS, _S.POST_RESPONSE, "reported usage within frozen bounds", (_F.REPORTED_USAGE_EXCEEDS_BOUND,)),
    (_G.A18_COST_LINKAGE, _S.POST_RESPONSE, "usage pricing and cost crosslinks", (_F.COST_LINK_MISMATCH,)),
    (_G.A19_RETENTION_PRIVACY, _S.POST_RESPONSE, "privacy-bounded retention", (_F.RETENTION_OR_PRIVACY_VIOLATION,)),
    (_G.A20_FINAL_RECEIPT_INTEGRITY, _S.POST_RESPONSE, "final immutable receipt identity", (_F.RECEIPT_MISMATCH,)),
)

FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0: Tuple[
    OpenRouterAdapterGuardDesignStepV0, ...
] = tuple(
    OpenRouterAdapterGuardDesignStepV0(
        order_index=index,
        guard_id=guard_id,
        stage=stage,
        check=check,
        failure_codes=failures,
    )
    for index, (guard_id, stage, check, failures) in enumerate(_GUARD_ROWS, start=1)
)
OPENROUTER_ADAPTER_GUARD_ORDER_V0: Tuple[OpenRouterAdapterGuardId, ...] = tuple(
    item.guard_id for item in FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0
)


class OpenRouterAdapterValidationOrderV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_VALIDATION_ORDER_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_VALIDATION_ORDER_SCHEMA_V0
    validation_order_id: Optional[str] = None
    precedence_model: Literal[
        FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0
    ] = FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0
    steps: Tuple[OpenRouterAdapterGuardDesignStepV0, ...] = Field(
        min_length=44, max_length=44
    )

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterAdapterValidationOrderV0":
        if tuple(item.guard_id for item in self.steps) != OPENROUTER_ADAPTER_GUARD_ORDER_V0:
            raise ContractValidationError("OpenRouter adapter guard order changed")
        if tuple(item.order_index for item in self.steps) != tuple(range(1, 45)):
            raise ContractValidationError("OpenRouter adapter guard indices changed")
        payload = self.model_dump(mode="json", exclude={"validation_order_id"})
        expected = stable_contract_id("oracqvalidationv0", payload)
        if self.validation_order_id is not None and self.validation_order_id != expected:
            raise ContractValidationError("validation-order ID mismatch")
        object.__setattr__(self, "validation_order_id", expected)
        return self


FROZEN_OPENROUTER_ADAPTER_VALIDATION_ORDER_V0 = OpenRouterAdapterValidationOrderV0(
    steps=FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0
)


class OpenRouterAdapterFailureTaxonomyEntryV0(_FrozenCaseContract):
    code: OpenRouterAdapterFailureCode
    guard_id: OpenRouterAdapterGuardId
    stage: OpenRouterAdapterGuardStage


class OpenRouterAdapterFailureTaxonomyV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_FAILURE_TAXONOMY_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_FAILURE_TAXONOMY_SCHEMA_V0
    failure_taxonomy_id: Optional[str] = None
    entries: Tuple[OpenRouterAdapterFailureTaxonomyEntryV0, ...]

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterAdapterFailureTaxonomyV0":
        if {item.code for item in self.entries} != set(OpenRouterAdapterFailureCode):
            raise ContractValidationError("failure taxonomy is incomplete")
        if len({item.code for item in self.entries}) != len(self.entries):
            raise ContractValidationError("failure taxonomy codes must be unique")
        positions = {
            guard_id: index
            for index, guard_id in enumerate(OPENROUTER_ADAPTER_GUARD_ORDER_V0)
        }
        ordered = tuple(
            sorted(self.entries, key=lambda item: (positions[item.guard_id], item.code.value))
        )
        object.__setattr__(self, "entries", ordered)
        payload = self.model_dump(mode="json", exclude={"failure_taxonomy_id"})
        expected = stable_contract_id("oracqtaxonomyv0", payload)
        if self.failure_taxonomy_id is not None and self.failure_taxonomy_id != expected:
            raise ContractValidationError("failure-taxonomy ID mismatch")
        object.__setattr__(self, "failure_taxonomy_id", expected)
        return self


FROZEN_OPENROUTER_ADAPTER_FAILURE_TAXONOMY_V0 = (
    OpenRouterAdapterFailureTaxonomyV0(
        entries=tuple(
            OpenRouterAdapterFailureTaxonomyEntryV0(
                code=code,
                guard_id=step.guard_id,
                stage=step.stage,
            )
            for step in FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0
            for code in step.failure_codes
        )
    )
)


def _vector(**changes: MutationState) -> OpenRouterAdapterMutationVectorV0:
    unknown = set(changes) - set(MUTATION_VECTOR_FIELD_NAMES_V0)
    if unknown:
        raise ContractValidationError(f"unknown mutation-vector fields: {sorted(unknown)!r}")
    return OpenRouterAdapterMutationVectorV0(**changes)


def _mutation(
    path: str,
    before: object,
    after: object,
    *,
    independent: bool = True,
) -> OpenRouterAdapterLiteralMutationV0:
    return OpenRouterAdapterLiteralMutationV0(
        path=path,
        before_json=canonical_json(before),
        after_json=canonical_json(after),
        independent_authoritative_input=independent,
    )


def _guard_trace(
    target: OpenRouterAdapterGuardId,
) -> Tuple[OpenRouterAdapterGuardExpectationV0, ...]:
    target_index = OPENROUTER_ADAPTER_GUARD_ORDER_V0.index(target)
    return tuple(
        OpenRouterAdapterGuardExpectationV0(
            guard_id=guard_id,
            state=(
                OpenRouterAdapterGuardState.PASSED
                if index < target_index
                else OpenRouterAdapterGuardState.FAILED
                if index == target_index
                else OpenRouterAdapterGuardState.NOT_REACHED
            ),
        )
        for index, guard_id in enumerate(OPENROUTER_ADAPTER_GUARD_ORDER_V0)
    )


class OpenRouterAdapterFixtureAvailability(str, Enum):
    CANDIDATE_GRAPH = "CANDIDATE_GRAPH"
    EXPECTATION_ONLY = "EXPECTATION_ONLY"


class OpenRouterAdapterFixtureRefV0(_FrozenCaseContract):
    ref_name: str = Field(pattern=r"^[a-z0-9-]+$")
    fixture_manifest_id: Literal[
        OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0
    ] = OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0
    availability: OpenRouterAdapterFixtureAvailability
    source_contract: str = Field(min_length=1)
    bound_ids: Tuple[str, ...] = Field(min_length=1)

    @field_validator("bound_ids")
    @classmethod
    def sorted_unique_bound_ids(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ContractValidationError("fixture bound IDs must be nonblank")
        if value != tuple(sorted(set(value))):
            raise ContractValidationError(
                "fixture bound IDs must be sorted and unique"
            )
        return value


def _fixture_ref(
    ref_name: str,
    availability: OpenRouterAdapterFixtureAvailability,
    source_contract: str,
    *bound_ids: str,
) -> OpenRouterAdapterFixtureRefV0:
    return OpenRouterAdapterFixtureRefV0(
        ref_name=ref_name,
        availability=availability,
        source_contract=source_contract,
        bound_ids=tuple(sorted(bound_ids)),
    )


_FA = OpenRouterAdapterFixtureAvailability
FROZEN_OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_V0: Tuple[
    OpenRouterAdapterFixtureRefV0, ...
] = (
    _fixture_ref("baseline-controls", _FA.CANDIDATE_GRAPH, "OpenRouterCapabilitySnapshot", OPENROUTER_ADAPTER_CAPABILITY_SNAPSHOT_ID_V0, OPENROUTER_ADAPTER_CONTROL_POLICY_ID_V0, OPENROUTER_ADAPTER_COST_BOUND_ID_V0, OPENROUTER_ADAPTER_ENDPOINT_POLICY_ID_V0, OPENROUTER_ADAPTER_PRICING_RECORD_ID_V0, OPENROUTER_ADAPTER_ROUTE_POLICY_ID_V0, OPENROUTER_ADAPTER_TOKEN_POLICY_ID_V0, OPENROUTER_ADAPTER_TRANSPORT_POLICY_ID_V0),
    _fixture_ref("baseline-request", _FA.CANDIDATE_GRAPH, "AcquisitionSemanticRequest+OpenRouterPreparedBody", OPENROUTER_ADAPTER_PREPARED_BODY_ID_V0, OPENROUTER_ADAPTER_SEMANTIC_REQUEST_ID_V0, OPENROUTER_ADAPTER_SOURCE_VISIBLE_REQUEST_ID_V0),
    _fixture_ref("complete-envelope", _FA.CANDIDATE_GRAPH, "OpenRouterAttemptReceipt", OPENROUTER_ADAPTER_ATTEMPT_RECEIPT_ID_V0, OPENROUTER_ADAPTER_CANNED_ENVELOPE_ID_V0, OPENROUTER_ADAPTER_IDENTITY_EVIDENCE_ID_V0, OPENROUTER_ADAPTER_RAW_RESPONSE_EVIDENCE_ID_V0, OPENROUTER_ADAPTER_USAGE_EVIDENCE_ID_V0),
    _fixture_ref("cooperative-envelope", _FA.EXPECTATION_ONLY, "PositiveThresholdFixtureV0", OPENROUTER_ADAPTER_CANNED_ENVELOPE_ID_V0, OPENROUTER_ADAPTER_TRANSPORT_POLICY_ID_V0),
    _fixture_ref("identity-policy", _FA.CANDIDATE_GRAPH, "OpenRouterIdentityEvidence", OPENROUTER_ADAPTER_CONTROL_POLICY_ID_V0, OPENROUTER_ADAPTER_IDENTITY_EVIDENCE_ID_V0, OPENROUTER_ADAPTER_ROUTE_POLICY_ID_V0),
    _fixture_ref("opaque-content-envelope", _FA.EXPECTATION_ONLY, "PositiveThresholdFixtureV0", OPENROUTER_ADAPTER_CANNED_ENVELOPE_ID_V0, OPENROUTER_ADAPTER_RAW_RESPONSE_EVIDENCE_ID_V0),
    _fixture_ref("sibling-a", _FA.EXPECTATION_ONLY, "PositiveThresholdSiblingAttemptV0", OPENROUTER_ADAPTER_PREPARED_BODY_ID_V0, OPENROUTER_ADAPTER_SEMANTIC_REQUEST_ID_V0),
    _fixture_ref("sibling-b", _FA.EXPECTATION_ONLY, "PositiveThresholdSiblingAttemptV0", OPENROUTER_ADAPTER_PREPARED_BODY_ID_V0, OPENROUTER_ADAPTER_SEMANTIC_REQUEST_ID_V0),
    _fixture_ref("synthetic-pricing", _FA.EXPECTATION_ONLY, "PositiveThresholdSyntheticPricingV0", OPENROUTER_ADAPTER_COST_BOUND_ID_V0, OPENROUTER_ADAPTER_PRICING_RECORD_ID_V0),
    _fixture_ref("timeout-policy", _FA.CANDIDATE_GRAPH, "OpenRouterTransportPolicy", OPENROUTER_ADAPTER_TRANSPORT_POLICY_ID_V0),
)
_FIXTURE_REF_BY_NAME_V0 = {
    item.ref_name: item
    for item in FROZEN_OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_V0
}
if len(_FIXTURE_REF_BY_NAME_V0) != len(
    FROZEN_OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_V0
):
    raise ContractValidationError("fixture-ref registry contains duplicate names")

OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_ID_V0 = stable_contract_id(
    "oracqfixtures",
    tuple(
        item.model_dump(mode="json")
        for item in FROZEN_OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_V0
    ),
)


class OpenRouterAdapterPositiveCaseV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_POSITIVE_CASE_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_POSITIVE_CASE_SCHEMA_V0
    case_id: str = Field(pattern=r"^oracqv0-s[0-9]{2}-[a-z0-9-]+$")
    case_fingerprint: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    purpose: str = Field(min_length=3)
    fixture_refs: Tuple[str, ...] = Field(min_length=1)
    attempt_count: Literal[1, 2]
    evaluator_input_attempt_count: Literal[1, 2]
    expected_attempt_receipts: Literal[1, 2]
    expected_canned_invocations: Literal[1, 2]
    expected_outcome: Literal[
        OpenRouterAdapterAttemptOutcome.EVIDENCE_READY
    ] = OpenRouterAdapterAttemptOutcome.EVIDENCE_READY
    expectation_role: Literal[
        OPENROUTER_ADAPTER_POSITIVE_EXPECTATION_ROLE_V0
    ] = OPENROUTER_ADAPTER_POSITIVE_EXPECTATION_ROLE_V0
    candidate_proof: Literal[False] = False
    required_assertions: Tuple[str, ...] = Field(min_length=1)

    @field_validator("fixture_refs", "required_assertions")
    @classmethod
    def sorted_unique_nonblank(cls, value: Tuple[str, ...]) -> Tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ContractValidationError("positive-case strings must be nonblank")
        if value != tuple(sorted(set(value))):
            raise ContractValidationError("positive-case tuples must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterAdapterPositiveCaseV0":
        if (
            self.evaluator_input_attempt_count != self.attempt_count
            or self.expected_attempt_receipts != self.attempt_count
            or self.expected_canned_invocations != self.attempt_count
        ):
            raise ContractValidationError(
                "positive topology and frozen success expectations changed"
            )
        unknown_refs = set(self.fixture_refs) - set(_FIXTURE_REF_BY_NAME_V0)
        if unknown_refs:
            raise ContractValidationError(
                f"positive case names unknown fixture refs: {sorted(unknown_refs)!r}"
            )
        payload = self.model_dump(mode="json", exclude={"case_fingerprint"})
        expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        if self.case_fingerprint is not None and self.case_fingerprint != expected:
            raise ContractValidationError("positive-case fingerprint mismatch")
        object.__setattr__(self, "case_fingerprint", expected)
        return self


class OpenRouterAdapterProbeV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_PROBE_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_PROBE_SCHEMA_V0
    probe_id: str = Field(pattern=r"^oracqv0-[op][0-9]{2}-[a-z0-9-]+$")
    probe_fingerprint: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    probe_class: Literal[
        OpenRouterAdapterCaseClass.ORTHOGONAL,
        OpenRouterAdapterCaseClass.PRECEDENCE,
    ]
    stage: OpenRouterAdapterGuardStage
    construction_rule: str = Field(min_length=3)
    literal_mutations: Tuple[OpenRouterAdapterLiteralMutationV0, ...] = Field(
        min_length=1
    )
    mutation_vector: OpenRouterAdapterMutationVectorV0
    expected_primary_failure: OpenRouterAdapterFailureCode
    expected_guard_id: OpenRouterAdapterGuardId
    expected_guard_trace: Tuple[OpenRouterAdapterGuardExpectationV0, ...] = Field(
        min_length=44, max_length=44
    )
    evaluator_input_attempt_count: Literal[1] = 1
    expected_attempt_receipts: Literal[1] = 1
    expected_canned_invocations: Literal[0, 1, 2]
    independently_probeable: bool
    expected_outcome: Literal[
        OpenRouterAdapterAttemptOutcome.REJECTED
    ] = OpenRouterAdapterAttemptOutcome.REJECTED

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterAdapterProbeV0":
        step = FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0[
            OPENROUTER_ADAPTER_GUARD_ORDER_V0.index(self.expected_guard_id)
        ]
        if self.stage is not step.stage:
            raise ContractValidationError("probe stage differs from target guard")
        if self.expected_primary_failure not in step.failure_codes:
            raise ContractValidationError("probe failure is not owned by target guard")
        if self.expected_guard_trace != _guard_trace(self.expected_guard_id):
            raise ContractValidationError("probe guard trace changed")
        orthogonal = self.probe_class is OpenRouterAdapterCaseClass.ORTHOGONAL
        if self.independently_probeable is not orthogonal:
            raise ContractValidationError("probe independence classification changed")
        if orthogonal and len(self.literal_mutations) != 1:
            raise ContractValidationError("orthogonal probes require one literal mutation")
        if not orthogonal and len(self.literal_mutations) < 2:
            raise ContractValidationError("precedence probes require multiple mutations")
        if len({item.path for item in self.literal_mutations}) != len(self.literal_mutations):
            raise ContractValidationError("probe mutation paths must be unique")
        path_specs = tuple(
            _MUTATION_PATH_SPEC_BY_PATH_V0[item.path]
            for item in self.literal_mutations
        )
        if any(
            getattr(self.mutation_vector, spec.mutation_vector_field)
            is not MutationState.INTENTIONALLY_CHANGED
            for spec in path_specs
        ):
            raise ContractValidationError(
                "mutation path metadata differs from the declared vector"
            )
        if path_specs[0].guard_id is not self.expected_guard_id:
            raise ContractValidationError(
                "first mutation path does not belong to the expected first guard"
            )
        target_index = OPENROUTER_ADAPTER_GUARD_ORDER_V0.index(
            self.expected_guard_id
        )
        if any(
            OPENROUTER_ADAPTER_GUARD_ORDER_V0.index(spec.guard_id)
            < target_index
            for spec in path_specs[1:]
        ):
            raise ContractValidationError(
                "precedence probe includes a mutation before its expected first guard"
            )
        intended = sum(
            value is MutationState.INTENTIONALLY_CHANGED
            for name, value in self.mutation_vector
            if name != "schema_version"
        )
        if intended != len(self.literal_mutations):
            raise ContractValidationError("mutation vector does not match literal count")
        if self.stage is OpenRouterAdapterGuardStage.PRE_DISPATCH:
            if self.expected_canned_invocations != 0:
                raise ContractValidationError("pre-dispatch probe cannot invoke transport")
        elif self.expected_canned_invocations not in (1, 2):
            raise ContractValidationError("post-response probe must invoke canned transport")
        prefix = "oracqv0-o" if orthogonal else "oracqv0-p"
        if not self.probe_id.startswith(prefix):
            raise ContractValidationError("probe ID and class differ")
        payload = self.model_dump(mode="json", exclude={"probe_fingerprint"})
        expected = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        if self.probe_fingerprint is not None and self.probe_fingerprint != expected:
            raise ContractValidationError("probe fingerprint mismatch")
        object.__setattr__(self, "probe_fingerprint", expected)
        return self


def _positive(
    case_id: str,
    purpose: str,
    *,
    attempts: int,
    fixture_refs: Tuple[str, ...],
    assertions: Tuple[str, ...],
) -> OpenRouterAdapterPositiveCaseV0:
    return OpenRouterAdapterPositiveCaseV0(
        case_id=case_id,
        purpose=purpose,
        fixture_refs=tuple(sorted(fixture_refs)),
        attempt_count=attempts,
        evaluator_input_attempt_count=attempts,
        expected_attempt_receipts=attempts,
        expected_canned_invocations=attempts,
        required_assertions=tuple(sorted(assertions)),
    )


def _probe(
    probe_id: str,
    probe_class: OpenRouterAdapterCaseClass,
    guard_id: OpenRouterAdapterGuardId,
    failure: OpenRouterAdapterFailureCode,
    construction_rule: str,
    mutations: Tuple[OpenRouterAdapterLiteralMutationV0, ...],
    vector: OpenRouterAdapterMutationVectorV0,
    *,
    invocations: Optional[int] = None,
) -> OpenRouterAdapterProbeV0:
    step = FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0[
        OPENROUTER_ADAPTER_GUARD_ORDER_V0.index(guard_id)
    ]
    expected_invocations = (
        0 if step.stage is OpenRouterAdapterGuardStage.PRE_DISPATCH else 1
    )
    if invocations is not None:
        expected_invocations = invocations
    return OpenRouterAdapterProbeV0(
        probe_id=probe_id,
        probe_class=probe_class,
        stage=step.stage,
        construction_rule=construction_rule,
        literal_mutations=mutations,
        mutation_vector=vector,
        expected_primary_failure=failure,
        expected_guard_id=guard_id,
        expected_guard_trace=_guard_trace(guard_id),
        expected_canned_invocations=expected_invocations,
        independently_probeable=(
            probe_class is OpenRouterAdapterCaseClass.ORTHOGONAL
        ),
    )


FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0: Tuple[
    OpenRouterAdapterPositiveCaseV0, ...
] = (
    _positive("oracqv0-s01-deterministic-body", "repeated preparation yields exact canonical body bytes digest and length", attempts=1, fixture_refs=("baseline-controls", "baseline-request", "complete-envelope"), assertions=("body_bytes_exact", "body_digest_exact", "body_length_exact")),
    _positive("oracqv0-s02-sibling-byte-equality", "two sibling attempts preserve identical semantic application bytes", attempts=2, fixture_refs=("baseline-request", "complete-envelope", "sibling-a", "sibling-b"), assertions=("attempt_ids_distinct", "body_bytes_equal", "semantic_request_ids_equal")),
    _positive("oracqv0-s03-exact-identity-config", "requested and actual provider model and configuration identities match", attempts=1, fixture_refs=("baseline-request", "complete-envelope", "identity-policy"), assertions=("configuration_match", "model_match", "provider_match")),
    _positive("oracqv0-s04-complete-usage-raw", "complete typed usage and exact raw response evidence are cross-linked", attempts=1, fixture_refs=("baseline-request", "complete-envelope", "synthetic-pricing"), assertions=("raw_bytes_recoverable", "raw_digest_exact", "usage_complete")),
    _positive("oracqv0-s05-opaque-content-retained", "assistant content remains opaque and is retained without CED interpretation", attempts=1, fixture_refs=("baseline-request", "opaque-content-envelope"), assertions=("canonical_application_not_invoked", "content_not_judged", "opaque_content_retained")),
    _positive("oracqv0-s06-synthetic-cost-mechanism", "clearly synthetic immutable pricing proves integer cost arithmetic only", attempts=1, fixture_refs=("baseline-request", "complete-envelope", "synthetic-pricing"), assertions=("cost_bound_exact", "live_pricing_not_established", "pricing_status_synthetic_only")),
    _positive("oracqv0-s07-cancellation-clean-success", "cooperative canned completion leaves no worker or late mutation", attempts=1, fixture_refs=("baseline-request", "cooperative-envelope", "timeout-policy"), assertions=("invocation_count_one", "late_mutations_zero", "workers_terminated")),
)


O = OpenRouterAdapterCaseClass.ORTHOGONAL
X = OpenRouterAdapterCaseClass.PRECEDENCE
I = MutationState.INTENTIONALLY_CHANGED
D = MutationState.DEPENDENTLY_CHANGED

_CONFIG = _FROZEN_CONTROL_CONFIGURATION_DIGEST_V0
_WRONG_CONFIG = "b" * 64
_RAW_DIGEST = _FROZEN_RAW_RESPONSE_SHA256_V0
_RECEIPT_ID = OPENROUTER_ADAPTER_ATTEMPT_RECEIPT_ID_V0


FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0: Tuple[
    OpenRouterAdapterProbeV0, ...
] = (
    _probe("oracqv0-o01-invalid-semantic-input", O, _G.P02_SEMANTIC_INPUT_INTEGRITY, _F.INVALID_SEMANTIC_INPUT, "Add only forbidden process identity to the semantic renderer input.", (_mutation("evaluator_draft.semantic_input.process_id", None, 4242),), _vector(semantic_input=I)),
    _probe("oracqv0-o02-renderer-version-mismatch", O, _G.P04_RENDERER_VERSION, _F.RENDERER_VERSION_MISMATCH, "Change only the frozen renderer version.", (_mutation("prepared_body.renderer_version", "socrateszero-openrouter-renderer/v0", "socrateszero-openrouter-renderer/v999"),), _vector(renderer_version=I)),
    _probe("oracqv0-o03-process-metadata-entropy", O, _G.P06_ENTROPY_CREDENTIAL_FIREWALL, _F.FORBIDDEN_ENTROPY, "Inject only a process identifier into an explicitly evaluator-draft prepared body.", (_mutation("evaluator_draft.prepared_body.metadata.process_id", None, 4242),), _vector(entropy_credential_firewall=I, canonical_body=D)),
    _probe("oracqv0-o04-branch-id-entropy", O, _G.P06_ENTROPY_CREDENTIAL_FIREWALL, _F.FORBIDDEN_ENTROPY, "Inject only a branch identifier into an explicitly evaluator-draft prepared body.", (_mutation("evaluator_draft.prepared_body.metadata.branch_id", None, "branch-a"),), _vector(entropy_credential_firewall=I, canonical_body=D)),
    _probe("oracqv0-o05-noncanonical-serialization", O, _G.P05_CANONICAL_BODY_INTEGRITY, _F.NONCANONICAL_BODY, "Replace only canonical compact JSON with whitespace-variant JSON.", (_mutation("prepared_body.canonical_body_json", _FROZEN_CANONICAL_BODY_JSON_V0, _FROZEN_CANONICAL_BODY_JSON_V0.replace("{\"max_tokens\":256", "{ \"max_tokens\":256")),), _vector(canonical_body=I)),
    _probe("oracqv0-o06-prepared-body-mutated", O, _G.P05_CANONICAL_BODY_INTEGRITY, _F.BODY_DIGEST_OR_LENGTH_MISMATCH, "Change prepared body bytes after its digest and length are frozen.", (_mutation("prepared_body.canonical_body_json", _FROZEN_CANONICAL_BODY_JSON_V0, _FROZEN_CANONICAL_BODY_JSON_V0.replace("\"max_tokens\":256", "\"max_tokens\":255")),), _vector(canonical_body=I)),
    _probe("oracqv0-o07-route-control-unknown", O, _G.P08_ROUTE_POLICY, _F.ROUTE_POLICY_UNPROVEN, "Change only unresolved route control evidence to UNKNOWN.", (_mutation("route_policy.upstream_route_state", "NOT_ESTABLISHED", "UNKNOWN"),), _vector(route_policy=I)),
    _probe("oracqv0-o08-fallback-intent-enabled", O, _G.P09_FALLBACK_INTENT, _F.FALLBACK_INTENT_NOT_DISABLED, "Change only application fallback intent to enabled.", (_mutation("route_policy.application_fallback_allowed", False, True),), _vector(fallback_intent=I)),
    _probe("oracqv0-o09-stream-request-enabled", O, _G.P12_STREAM_POLICY, _F.STREAM_NOT_DISABLED, "Change only request stream from false to true.", (_mutation("prepared_body.stream", False, True),), _vector(stream_policy=I, canonical_body=D)),
    _probe("oracqv0-o10-tool-request-present", O, _G.P13_TOOL_POLICY, _F.TOOLS_NOT_DISABLED, "Add only a tool declaration to the provider-visible body.", (_mutation("prepared_body.tools", [], [{"name": "forbidden-tool"}]),), _vector(tool_policy=I, canonical_body=D)),
    _probe("oracqv0-o11-temperature-mismatch", O, _G.P14_TEMPERATURE, _F.TEMPERATURE_NOT_ZERO, "Change only temperature from zero.", (_mutation("prepared_body.temperature", 0.0, 0.1),), _vector(temperature=I, canonical_body=D)),
    _probe("oracqv0-o12-seed-emitted", O, _G.P15_SEED, _F.SEED_NOT_UNSUPPORTED_OR_EMITTED, "Emit only a seed field despite the frozen unsupported state.", (_mutation("prepared_body.seed", None, 0),), _vector(seed=I, canonical_body=D)),
    _probe("oracqv0-o13-output-cap-missing", O, _G.P16_OUTPUT_TOKEN_CAP, _F.OUTPUT_TOKEN_CAP_INVALID, "Remove only the output-token cap.", (_mutation("prepared_body.max_tokens", 256, None),), _vector(output_token_cap=I, canonical_body=D, cost_bound=D)),
    _probe("oracqv0-o14-input-bound-unsafe", O, _G.P17_INPUT_TOKEN_BOUND, _F.INPUT_BOUND_UNPROVEN, "Change only the unresolved input-bound classification to an unsafe estimate.", (_mutation("token_policy.provider_input_token_bound_state", "NOT_ESTABLISHED", "UNPROVEN_ESTIMATE"),), _vector(input_token_bound=I, cost_bound=D)),
    _probe("oracqv0-o15-pricing-record-missing", O, _G.P18_PRICING_RECORD, _F.PRICING_NOT_ESTABLISHED, "Remove only the frozen unresolved pricing-record reference.", (_mutation("cost_bound.pricing_record.pricing_record_id", OPENROUTER_ADAPTER_PRICING_RECORD_ID_V0, None),), _vector(pricing_record=I, cost_bound=D)),
    _probe("oracqv0-o16-pricing-model-mismatch", O, _G.P18_PRICING_RECORD, _F.PRICING_BINDING_MISMATCH, "Change only the model bound by the pricing record.", (_mutation("pricing_record.model_id", OPENROUTER_SELECTED_MODEL_V0, "openai/gpt-4.1"),), _vector(pricing_record=I, cost_bound=D)),
    _probe("oracqv0-o17-cost-overflow", O, _G.P19_COST_BOUND, _F.COST_OVERFLOW, "Change only unresolved integer pricing to exceed the frozen arithmetic range.", (_mutation("pricing_record.output_microusd_per_million_tokens", None, 9223372036854775808),), _vector(cost_bound=I)),
    _probe("oracqv0-o18-endpoint-mismatch", O, _G.P20_ENDPOINT_POLICY, _F.ENDPOINT_MISMATCH, "Change only the logical endpoint path.", (_mutation("endpoint_policy.path", "/api/v1/chat/completions", "/api/v1/other"),), _vector(endpoint_policy=I)),
    _probe("oracqv0-o19-redirect-enabled", O, _G.P21_REDIRECT_POLICY, _F.REDIRECTS_NOT_DISABLED, "Change only redirect policy to enabled.", (_mutation("endpoint_policy.redirects_allowed", False, True),), _vector(redirect_policy=I)),
    _probe("oracqv0-o20-proxy-unknown", O, _G.P22_PROXY_POLICY, _F.PROXY_INHERITANCE_NOT_DISABLED, "Change only proxy inheritance control to UNKNOWN.", (_mutation("endpoint_policy.environment_proxy_allowed", False, "UNKNOWN"),), _vector(proxy_policy=I)),
    _probe("oracqv0-o21-timeout-policy-incomplete", O, _G.P23_TIMEOUT_POLICY, _F.TIMEOUT_POLICY_INCOMPLETE, "Remove only cancellation grace from the timeout policy.", (_mutation("transport_policy.canned_cancellation_grace_ms", 50, None),), _vector(timeout_policy=I)),
    _probe("oracqv0-o22-canned-transport-unregistered", O, _G.P24_CANNED_REGISTRATION, _F.CANNED_TRANSPORT_UNREGISTERED, "Remove only the exact canned transport registration.", (_mutation("evaluator_derived.canned_transport_registered", True, False),), _vector(canned_registration=I)),
    _probe("oracqv0-o23-credential-header-leakage", O, _G.P06_ENTROPY_CREDENTIAL_FIREWALL, _F.CREDENTIAL_OR_HEADER_LEAKAGE, "Add only a non-secret sentinel proving an Authorization header was present in evaluator draft input.", (_mutation("evaluator_draft.semantic_headers.authorization_presence", "ABSENT", "FORBIDDEN_PRESENT_SENTINEL"),), _vector(entropy_credential_firewall=I)),
    _probe("oracqv0-o24-second-transport-invocation", O, _G.A01_INVOCATION_COUNT, _F.MULTIPLE_TRANSPORT_INVOCATIONS, "Make evaluator-derived canned invocation evidence equal two for one adapter attempt.", (_mutation("evaluator_derived.transport_invocation_count", 1, 2),), _vector(invocation_count=I), invocations=2),
    _probe("oracqv0-o25-clean-transport-timeout", O, _G.A02_TRANSPORT_COMPLETION, _F.TRANSPORT_TIMEOUT, "Return a deterministic timeout with acknowledged worker termination.", (_mutation("envelope.transport_status", "DELIVERED", "TIMEOUT"),), _vector(transport_completion=I, raw_response_presence=D, raw_response_integrity=D)),
    _probe("oracqv0-o26-worker-not-terminated-after-delivery", O, _G.A03_WORKER_TERMINATION, _F.WORKER_NOT_TERMINATED, "Keep transport delivered and change only worker termination to false.", (_mutation("invocation_record.worker_terminated", True, False),), _vector(worker_termination=I)),
    _probe("oracqv0-o27-late-mutation-after-delivery", O, _G.A04_LATE_MUTATION, _F.LATE_MUTATION_DETECTED, "Keep transport delivered and change only the late-mutation directive to true.", (_mutation("directive.attempt_late_mutation", False, True),), _vector(late_mutation=I)),
    _probe("oracqv0-o28-raw-missing", O, _G.A05_RAW_RESPONSE_PRESENCE, _F.MISSING_RAW_RESPONSE, "Remove only the exact raw-response evidence link.", (_mutation("envelope.raw_response.raw_response_evidence_id", OPENROUTER_ADAPTER_RAW_RESPONSE_EVIDENCE_ID_V0, None),), _vector(raw_response_presence=I, raw_response_integrity=D, envelope_parse=D)),
    _probe("oracqv0-o29-raw-digest-mismatch", O, _G.A06_RAW_RESPONSE_INTEGRITY, _F.RAW_DIGEST_OR_LENGTH_MISMATCH, "Keep raw bytes and change only the stored digest.", (_mutation("raw_response.reported_sha256", _RAW_DIGEST, "f" * 64),), _vector(raw_response_integrity=I)),
    _probe("oracqv0-o30-malformed-envelope", O, _G.A07_ENVELOPE_PARSE, _F.MALFORMED_RESPONSE_ENVELOPE, "Change only explicitly evaluator-derived envelope parse state.", (_mutation("evaluator_derived.envelope_parse_state", "COMPLETE_TYPED_ENVELOPE", "MALFORMED"),), _vector(envelope_parse=I)),
    _probe("oracqv0-o31-provider-mismatch", O, _G.A08_ACTUAL_PROVIDER, _F.ACTUAL_PROVIDER_MISMATCH, "Change only actual provider identity.", (_mutation("identity_evidence.actual_router_id", OPENROUTER_SELECTED_PROVIDER_V0, "wrong-router"),), _vector(actual_provider=I)),
    _probe("oracqv0-o32-model-mismatch", O, _G.A09_ACTUAL_MODEL, _F.ACTUAL_MODEL_MISMATCH, "Change only actual exact-model identity.", (_mutation("identity_evidence.actual_model_id", OPENROUTER_SELECTED_MODEL_V0, "openai/gpt-4.1"),), _vector(actual_model=I)),
    _probe("oracqv0-o33-actual-model-missing", O, _G.A09_ACTUAL_MODEL, _F.ACTUAL_MODEL_MISSING, "Remove only actual exact-model identity.", (_mutation("identity_evidence.actual_model_id", OPENROUTER_SELECTED_MODEL_V0, None),), _vector(actual_model=I)),
    _probe("oracqv0-o34-configuration-mismatch", O, _G.A10_ACTUAL_CONFIGURATION, _F.ACTUAL_CONFIGURATION_MISMATCH, "Change only actual configuration digest.", (_mutation("identity_evidence.actual_configuration_digest", _CONFIG, _WRONG_CONFIG),), _vector(actual_configuration=I)),
    _probe("oracqv0-o35-fallback-used", O, _G.A11_FALLBACK_STATUS, _F.FALLBACK_ACTIVATED, "Change only actual fallback-used metadata to true.", (_mutation("identity_evidence.fallback_used", False, True),), _vector(fallback_status=I)),
    _probe("oracqv0-o36-retry-count-nonzero", O, _G.A12_RETRY_STATUS, _F.RETRY_ACTIVATED, "Change only actual adapter retry count from zero to one.", (_mutation("envelope.adapter_retry_count", 0, 1),), _vector(retry_status=I)),
    _probe("oracqv0-o37-stream-response-metadata", O, _G.A13_STREAM_STATUS, _F.STREAMING_RESPONSE_DETECTED, "Change only response stream-used metadata to true.", (_mutation("envelope.stream_used", False, True),), _vector(stream_status=I)),
    _probe("oracqv0-o38-tool-response-present", O, _G.A14_TOOL_STATUS, _F.TOOL_ACTIVATED, "Change only response tool-call count from zero to one.", (_mutation("envelope.tool_calls", 0, 1),), _vector(tool_status=I)),
    _probe("oracqv0-o39-usage-missing", O, _G.A15_USAGE_COMPLETENESS, _F.USAGE_INCOMPLETE, "Change only provider-reported usage completeness to missing.", (_mutation("usage_evidence.token_completeness", "COMPLETE", None),), _vector(usage_completeness=I, usage_consistency=D, token_bounds=D, cost_linkage=D)),
    _probe("oracqv0-o40-usage-inconsistent", O, _G.A16_USAGE_CONSISTENCY, _F.USAGE_INCONSISTENT, "Change only total tokens so input plus output no longer equals total.", (_mutation("usage_evidence.total_tokens", 18, 19),), _vector(usage_consistency=I, cost_linkage=D)),
    _probe("oracqv0-o41-false-zero-usage", O, _G.A15_USAGE_COMPLETENESS, _F.FALSE_ZERO_USAGE, "Remove only known input-token usage evidence.", (_mutation("usage_evidence.input_tokens", 10, None),), _vector(usage_completeness=I, usage_consistency=D, cost_linkage=D)),
    _probe("oracqv0-o42-reported-tokens-exceed-bound", O, _G.A17_TOKEN_BOUNDS, _F.REPORTED_USAGE_EXCEEDS_BOUND, "Change only reported output tokens above the frozen cap.", (_mutation("usage_evidence.output_tokens", 8, 257),), _vector(token_bounds=I, usage_consistency=D, cost_linkage=D)),
    _probe("oracqv0-o43-cost-link-mismatch", O, _G.A18_COST_LINKAGE, _F.COST_LINK_MISMATCH, "Change only the unresolved attempt-receipt cost-bound crosslink.", (_mutation("attempt_receipt.usage_evidence.cost_bound_id", None, "szorcost_" + "f" * 64),), _vector(cost_linkage=I, receipt_identity=D)),
    _probe("oracqv0-o44-final-receipt-mismatch", O, _G.A20_FINAL_RECEIPT_INTEGRITY, _F.RECEIPT_MISMATCH, "Change only the stored final attempt-receipt identity.", (_mutation("attempt_receipt.attempt_receipt_id", _RECEIPT_ID, "szorattempt_" + "f" * 64),), _vector(receipt_identity=I)),
)


FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0: Tuple[
    OpenRouterAdapterProbeV0, ...
] = (
    _probe("oracqv0-p01-invalid-request-plus-entropy", X, _G.P01_REQUEST_INTEGRITY, _F.INVALID_ADAPTER_REQUEST, "Change request schema and inject evaluator-draft body entropy; request integrity wins.", (_mutation("request.schema_version", OPENROUTER_ADAPTER_REQUEST_SCHEMA_V0, "socrateszero-openrouter-acquisition-request/v999"), _mutation("evaluator_draft.prepared_body.metadata.branch_id", None, "branch-a")), _vector(request_integrity=I, entropy_credential_firewall=I, canonical_body=D)),
    _probe("oracqv0-p02-noncanonical-plus-entropy", X, _G.P05_CANONICAL_BODY_INTEGRITY, _F.NONCANONICAL_BODY, "Make body serialization noncanonical and inject evaluator-draft entropy; body integrity wins.", (_mutation("prepared_body.canonical_body_json", _FROZEN_CANONICAL_BODY_JSON_V0, _FROZEN_CANONICAL_BODY_JSON_V0.replace("{\"max_tokens\":256", "{ \"max_tokens\":256")), _mutation("evaluator_draft.prepared_body.metadata.branch_id", None, "branch-a")), _vector(canonical_body=I, entropy_credential_firewall=I)),
    _probe("oracqv0-p03-route-unknown-plus-fallback-enabled", X, _G.P08_ROUTE_POLICY, _F.ROUTE_POLICY_UNPROVEN, "Keep route control unresolved and enable adapter fallback intent; route policy wins.", (_mutation("route_policy.upstream_route_state", "NOT_ESTABLISHED", "UNKNOWN"), _mutation("route_policy.adapter_fallback_allowed", False, True)), _vector(route_policy=I, fallback_intent=I)),
    _probe("oracqv0-p04-fallback-plus-stream-plus-tools", X, _G.P09_FALLBACK_INTENT, _F.FALLBACK_INTENT_NOT_DISABLED, "Enable application fallback, streaming and tools; fallback intent wins.", (_mutation("route_policy.application_fallback_allowed", False, True), _mutation("prepared_body.stream", False, True), _mutation("prepared_body.tools", [], [{"name": "forbidden-tool"}])), _vector(fallback_intent=I, stream_policy=I, tool_policy=I, canonical_body=D)),
    _probe("oracqv0-p05-timeout-plus-worker-leak-plus-late-mutation", X, _G.A02_TRANSPORT_COMPLETION, _F.TRANSPORT_TIMEOUT, "Return timeout, nontermination and late mutation; transport completion wins.", (_mutation("envelope.transport_status", "DELIVERED", "TIMEOUT"), _mutation("invocation_record.worker_terminated", True, False), _mutation("directive.attempt_late_mutation", False, True)), _vector(transport_completion=I, worker_termination=I, late_mutation=I, raw_response_presence=D, raw_response_integrity=D)),
    _probe("oracqv0-p06-missing-raw-plus-malformed-plus-identity", X, _G.A05_RAW_RESPONSE_PRESENCE, _F.MISSING_RAW_RESPONSE, "Remove the raw evidence link, change derived parse state and change model; raw presence wins.", (_mutation("envelope.raw_response.raw_response_evidence_id", OPENROUTER_ADAPTER_RAW_RESPONSE_EVIDENCE_ID_V0, None), _mutation("evaluator_derived.envelope_parse_state", "COMPLETE_TYPED_ENVELOPE", "MALFORMED"), _mutation("identity_evidence.actual_model_id", OPENROUTER_SELECTED_MODEL_V0, "openai/gpt-4.1")), _vector(raw_response_presence=I, envelope_parse=I, actual_model=I, raw_response_integrity=D)),
    _probe("oracqv0-p07-provider-plus-model-plus-config-plus-fallback", X, _G.A08_ACTUAL_PROVIDER, _F.ACTUAL_PROVIDER_MISMATCH, "Change provider, model, configuration and fallback status; provider identity wins.", (_mutation("identity_evidence.actual_router_id", OPENROUTER_SELECTED_PROVIDER_V0, "wrong-router"), _mutation("identity_evidence.actual_model_id", OPENROUTER_SELECTED_MODEL_V0, "openai/gpt-4.1"), _mutation("identity_evidence.actual_configuration_digest", _CONFIG, _WRONG_CONFIG), _mutation("identity_evidence.fallback_used", False, True)), _vector(actual_provider=I, actual_model=I, actual_configuration=I, fallback_status=I)),
    _probe("oracqv0-p08-usage-inconsistent-plus-cost-link-plus-receipt", X, _G.A16_USAGE_CONSISTENCY, _F.USAGE_INCONSISTENT, "Make usage inconsistent and change cost and receipt crosslinks; usage consistency wins.", (_mutation("usage_evidence.total_tokens", 18, 19), _mutation("attempt_receipt.usage_evidence.cost_bound_id", None, "szorcost_" + "f" * 64), _mutation("attempt_receipt.attempt_receipt_id", _RECEIPT_ID, "szorattempt_" + "f" * 64)), _vector(usage_consistency=I, cost_linkage=I, receipt_identity=I)),
)


POSITIVE_CASE_IDS_V0: Tuple[str, ...] = tuple(
    item.case_id for item in FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0
)
ORTHOGONAL_PROBE_IDS_V0: Tuple[str, ...] = tuple(
    item.probe_id for item in FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0
)
PRECEDENCE_PROBE_IDS_V0: Tuple[str, ...] = tuple(
    item.probe_id for item in FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0
)


class OpenRouterAdapterThresholdsV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_THRESHOLDS_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_THRESHOLDS_SCHEMA_V0
    thresholds_id: Optional[str] = None
    cases_total: Literal[59] = 59
    positive_cases_total: Literal[7] = 7
    required_positive_complete_case_results: Literal[7] = 7
    required_positive_attempt_receipts: Literal[8] = 8
    orthogonal_probes_total: Literal[44] = 44
    required_orthogonal_exact_primary_results: Literal[44] = 44
    precedence_probes_total: Literal[8] = 8
    required_precedence_exact_primary_results: Literal[8] = 8
    required_attempt_receipts_total: Literal[60] = 60
    required_canned_transport_invocations: Literal[34] = 34
    required_invalid_probe_constructions: Literal[0] = 0
    maximum_unexpected_failure_or_mismatch_count: Literal[0] = 0
    maximum_accepted_control_violations: Literal[0] = 0
    maximum_accepted_identity_mismatches: Literal[0] = 0
    maximum_accepted_fallback_retry_stream_tool_activations: Literal[0] = 0
    maximum_accepted_token_pricing_cost_failures: Literal[0] = 0
    maximum_accepted_raw_usage_privacy_receipt_failures: Literal[0] = 0
    maximum_unexpected_multiple_transport_invocations: Literal[0] = 0
    maximum_surviving_tasks: Literal[0] = 0
    maximum_accepted_late_mutations: Literal[0] = 0
    required_external_network_attempts: Literal[0] = 0
    required_credential_access_attempts: Literal[0] = 0
    required_provider_calls: Literal[0] = 0
    required_model_calls: Literal[0] = 0
    required_tool_calls: Literal[0] = 0
    required_canonical_application_invocations: Literal[0] = 0
    required_source_mutations: Literal[0] = 0
    required_sibling_mutations: Literal[0] = 0
    required_production_mutations: Literal[0] = 0
    required_historical_lock_mismatches: Literal[0] = 0
    required_core_lock_mismatches: Literal[0] = 0
    pricing_status: Literal["SYNTHETIC_ONLY"] = "SYNTHETIC_ONLY"
    live_model_pricing_status: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    live_pilot_readiness: Literal[
        "REQUIRES_REAUTHORIZATION"
    ] = "REQUIRES_REAUTHORIZATION"
    production_authority: Literal["none"] = "none"

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterAdapterThresholdsV0":
        payload = self.model_dump(mode="json", exclude={"thresholds_id"})
        expected = stable_contract_id("oracqthresholdsv0", payload)
        if self.thresholds_id is not None and self.thresholds_id != expected:
            raise ContractValidationError("thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self


FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0 = OpenRouterAdapterThresholdsV0()


class OpenRouterAdapterCaseSetV0(_FrozenCaseContract):
    schema_version: Literal[
        OPENROUTER_ADAPTER_CASE_SET_SCHEMA_V0
    ] = OPENROUTER_ADAPTER_CASE_SET_SCHEMA_V0
    case_set_id: Optional[str] = None
    harness_id: Literal[
        OPENROUTER_ADAPTER_HARNESS_ID_V0
    ] = OPENROUTER_ADAPTER_HARNESS_ID_V0
    adapter_id: Literal[OPENROUTER_ADAPTER_ID_V0] = OPENROUTER_ADAPTER_ID_V0
    candidate_adapter_id: Literal[
        OPENROUTER_ADAPTER_CANDIDATE_ADAPTER_ID_V0
    ] = OPENROUTER_ADAPTER_CANDIDATE_ADAPTER_ID_V0
    selected_provider: Literal[
        OPENROUTER_SELECTED_PROVIDER_V0
    ] = OPENROUTER_SELECTED_PROVIDER_V0
    selected_provider_display: Literal[
        OPENROUTER_SELECTED_PROVIDER_DISPLAY_V0
    ] = OPENROUTER_SELECTED_PROVIDER_DISPLAY_V0
    selected_model: Literal[
        OPENROUTER_SELECTED_MODEL_V0
    ] = OPENROUTER_SELECTED_MODEL_V0
    fixture_manifest_id: Literal[
        OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0
    ] = OPENROUTER_ADAPTER_FIXTURE_MANIFEST_ID_V0
    baseline_projection_sha256: Literal[
        OPENROUTER_ADAPTER_BASELINE_PROJECTION_SHA256_V0
    ] = OPENROUTER_ADAPTER_BASELINE_PROJECTION_SHA256_V0
    mutation_path_registry_id: Literal[
        OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_ID_V0
    ] = OPENROUTER_ADAPTER_MUTATION_PATH_REGISTRY_ID_V0
    fixture_ref_registry_id: Literal[
        OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_ID_V0
    ] = OPENROUTER_ADAPTER_FIXTURE_REF_REGISTRY_ID_V0
    semantic_request_id: Literal[
        OPENROUTER_ADAPTER_SEMANTIC_REQUEST_ID_V0
    ] = OPENROUTER_ADAPTER_SEMANTIC_REQUEST_ID_V0
    source_provider_visible_request_id: Literal[
        OPENROUTER_ADAPTER_SOURCE_VISIBLE_REQUEST_ID_V0
    ] = OPENROUTER_ADAPTER_SOURCE_VISIBLE_REQUEST_ID_V0
    capability_snapshot_id: Literal[
        OPENROUTER_ADAPTER_CAPABILITY_SNAPSHOT_ID_V0
    ] = OPENROUTER_ADAPTER_CAPABILITY_SNAPSHOT_ID_V0
    endpoint_policy_id: Literal[
        OPENROUTER_ADAPTER_ENDPOINT_POLICY_ID_V0
    ] = OPENROUTER_ADAPTER_ENDPOINT_POLICY_ID_V0
    route_policy_id: Literal[
        OPENROUTER_ADAPTER_ROUTE_POLICY_ID_V0
    ] = OPENROUTER_ADAPTER_ROUTE_POLICY_ID_V0
    control_policy_id: Literal[
        OPENROUTER_ADAPTER_CONTROL_POLICY_ID_V0
    ] = OPENROUTER_ADAPTER_CONTROL_POLICY_ID_V0
    prepared_body_id: Literal[
        OPENROUTER_ADAPTER_PREPARED_BODY_ID_V0
    ] = OPENROUTER_ADAPTER_PREPARED_BODY_ID_V0
    transport_policy_id: Literal[
        OPENROUTER_ADAPTER_TRANSPORT_POLICY_ID_V0
    ] = OPENROUTER_ADAPTER_TRANSPORT_POLICY_ID_V0
    token_policy_id: Literal[
        OPENROUTER_ADAPTER_TOKEN_POLICY_ID_V0
    ] = OPENROUTER_ADAPTER_TOKEN_POLICY_ID_V0
    pricing_record_id: Literal[
        OPENROUTER_ADAPTER_PRICING_RECORD_ID_V0
    ] = OPENROUTER_ADAPTER_PRICING_RECORD_ID_V0
    cost_bound_id: Literal[
        OPENROUTER_ADAPTER_COST_BOUND_ID_V0
    ] = OPENROUTER_ADAPTER_COST_BOUND_ID_V0
    raw_response_evidence_id: Literal[
        OPENROUTER_ADAPTER_RAW_RESPONSE_EVIDENCE_ID_V0
    ] = OPENROUTER_ADAPTER_RAW_RESPONSE_EVIDENCE_ID_V0
    identity_evidence_id: Literal[
        OPENROUTER_ADAPTER_IDENTITY_EVIDENCE_ID_V0
    ] = OPENROUTER_ADAPTER_IDENTITY_EVIDENCE_ID_V0
    usage_evidence_id: Literal[
        OPENROUTER_ADAPTER_USAGE_EVIDENCE_ID_V0
    ] = OPENROUTER_ADAPTER_USAGE_EVIDENCE_ID_V0
    canned_response_envelope_id: Literal[
        OPENROUTER_ADAPTER_CANNED_ENVELOPE_ID_V0
    ] = OPENROUTER_ADAPTER_CANNED_ENVELOPE_ID_V0
    attempt_receipt_id: Literal[
        OPENROUTER_ADAPTER_ATTEMPT_RECEIPT_ID_V0
    ] = OPENROUTER_ADAPTER_ATTEMPT_RECEIPT_ID_V0
    known_unresolved_mandatory_guards: Tuple[
        OpenRouterAdapterGuardId, ...
    ] = FROZEN_OPENROUTER_ADAPTER_KNOWN_UNRESOLVED_GUARDS_V0
    positive_case_semantics: Literal[
        OPENROUTER_ADAPTER_POSITIVE_EXPECTATION_ROLE_V0
    ] = OPENROUTER_ADAPTER_POSITIVE_EXPECTATION_ROLE_V0
    validation_order_id: str
    failure_taxonomy_id: str
    guard_ids: Tuple[OpenRouterAdapterGuardId, ...] = Field(
        min_length=44, max_length=44
    )
    positive_cases: Tuple[OpenRouterAdapterPositiveCaseV0, ...] = Field(
        min_length=7, max_length=7
    )
    orthogonal_probes: Tuple[OpenRouterAdapterProbeV0, ...] = Field(
        min_length=44, max_length=44
    )
    precedence_probes: Tuple[OpenRouterAdapterProbeV0, ...] = Field(
        min_length=8, max_length=8
    )
    thresholds_id: str
    total_case_count: Literal[59] = 59
    total_attempt_receipts: Literal[60] = 60
    total_canned_transport_invocations: Literal[34] = 34

    @model_validator(mode="after")
    def validate_and_identify(self) -> "OpenRouterAdapterCaseSetV0":
        if (
            self.known_unresolved_mandatory_guards
            != FROZEN_OPENROUTER_ADAPTER_KNOWN_UNRESOLVED_GUARDS_V0
        ):
            raise ContractValidationError(
                "case-set unresolved mandatory guards changed"
            )
        if self.guard_ids != OPENROUTER_ADAPTER_GUARD_ORDER_V0:
            raise ContractValidationError("case-set guard order changed")
        if self.validation_order_id != FROZEN_OPENROUTER_ADAPTER_VALIDATION_ORDER_V0.validation_order_id:
            raise ContractValidationError("case-set validation-order link changed")
        if self.failure_taxonomy_id != FROZEN_OPENROUTER_ADAPTER_FAILURE_TAXONOMY_V0.failure_taxonomy_id:
            raise ContractValidationError("case-set failure-taxonomy link changed")
        if tuple(item.case_id for item in self.positive_cases) != POSITIVE_CASE_IDS_V0:
            raise ContractValidationError("positive membership or order changed")
        if tuple(item.probe_id for item in self.orthogonal_probes) != ORTHOGONAL_PROBE_IDS_V0:
            raise ContractValidationError("orthogonal membership or order changed")
        if tuple(item.probe_id for item in self.precedence_probes) != PRECEDENCE_PROBE_IDS_V0:
            raise ContractValidationError("precedence membership or order changed")
        if self.thresholds_id != FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.thresholds_id:
            raise ContractValidationError("case-set thresholds link changed")
        referenced_fixtures = {
            ref
            for case in self.positive_cases
            for ref in case.fixture_refs
        }
        if referenced_fixtures != set(_FIXTURE_REF_BY_NAME_V0):
            raise ContractValidationError(
                "positive cases must resolve the complete frozen fixture registry"
            )
        fingerprints = tuple(item.case_fingerprint for item in self.positive_cases) + tuple(
            item.probe_fingerprint
            for item in self.orthogonal_probes + self.precedence_probes
        )
        if len(set(fingerprints)) != self.total_case_count:
            raise ContractValidationError("all case fingerprints must be unique")
        attempts = sum(item.attempt_count for item in self.positive_cases) + len(
            self.orthogonal_probes
        ) + len(self.precedence_probes)
        invocations = sum(
            item.expected_canned_invocations for item in self.positive_cases
        ) + sum(
            item.expected_canned_invocations
            for item in self.orthogonal_probes + self.precedence_probes
        )
        if attempts != self.total_attempt_receipts:
            raise ContractValidationError("case-set attempt total changed")
        if invocations != self.total_canned_transport_invocations:
            raise ContractValidationError("case-set canned invocation total changed")
        payload = self.model_dump(mode="json", exclude={"case_set_id"})
        expected = stable_contract_id("oracqcasesetv0", payload)
        if self.case_set_id is not None and self.case_set_id != expected:
            raise ContractValidationError("case-set ID mismatch")
        object.__setattr__(self, "case_set_id", expected)
        return self


FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0 = OpenRouterAdapterCaseSetV0(
    validation_order_id=(
        FROZEN_OPENROUTER_ADAPTER_VALIDATION_ORDER_V0.validation_order_id or ""
    ),
    failure_taxonomy_id=(
        FROZEN_OPENROUTER_ADAPTER_FAILURE_TAXONOMY_V0.failure_taxonomy_id or ""
    ),
    guard_ids=OPENROUTER_ADAPTER_GUARD_ORDER_V0,
    positive_cases=FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0,
    orthogonal_probes=FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0,
    precedence_probes=FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0,
    thresholds_id=FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0.thresholds_id or "",
)


def frozen_openrouter_adapter_case_set_sha256_v0() -> str:
    payload = FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0.model_dump(
        mode="json", exclude={"case_set_id"}
    )
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


__all__ = [
    "FIRST_OPENROUTER_ADAPTER_GUARD_WINS_V0",
    "FROZEN_OPENROUTER_ADAPTER_CASE_SET_V0",
    "FROZEN_OPENROUTER_ADAPTER_FAILURE_TAXONOMY_V0",
    "FROZEN_OPENROUTER_ADAPTER_GUARD_DESIGN_V0",
    "FROZEN_OPENROUTER_ADAPTER_ORTHOGONAL_PROBES_V0",
    "FROZEN_OPENROUTER_ADAPTER_POSITIVE_CASES_V0",
    "FROZEN_OPENROUTER_ADAPTER_PRECEDENCE_PROBES_V0",
    "FROZEN_OPENROUTER_ADAPTER_THRESHOLDS_V0",
    "FROZEN_OPENROUTER_ADAPTER_VALIDATION_ORDER_V0",
    "MUTATION_VECTOR_FIELD_NAMES_V0",
    "OPENROUTER_ADAPTER_GUARD_ORDER_V0",
    "OPENROUTER_ADAPTER_HARNESS_ID_V0",
    "OPENROUTER_ADAPTER_ID_V0",
    "OPENROUTER_SELECTED_MODEL_V0",
    "OPENROUTER_SELECTED_PROVIDER_V0",
    "ORTHOGONAL_PROBE_IDS_V0",
    "POSITIVE_CASE_IDS_V0",
    "PRECEDENCE_PROBE_IDS_V0",
    "MutationState",
    "OpenRouterAdapterAttemptOutcome",
    "OpenRouterAdapterCaseClass",
    "OpenRouterAdapterCaseSetV0",
    "OpenRouterAdapterFailureCode",
    "OpenRouterAdapterGuardId",
    "OpenRouterAdapterGuardStage",
    "OpenRouterAdapterGuardState",
    "OpenRouterAdapterLiteralMutationV0",
    "OpenRouterAdapterMutationVectorV0",
    "OpenRouterAdapterPositiveCaseV0",
    "OpenRouterAdapterProbeV0",
    "OpenRouterAdapterThresholdsV0",
    "frozen_openrouter_adapter_case_set_sha256_v0",
]
