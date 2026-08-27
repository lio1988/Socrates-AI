"""Deterministic offline evaluator for OpenRouter raw wire-mapping v2.

Runs the frozen case set through the mapper, derives the safety metrics rather
than asserting them, and renders one content-addressed authoritative artifact
plus a replay execution and lock.

Thresholds are predeclared in this module and content addressed, so they cannot
be tuned after seeing a result without changing an identity that the artifact
carries.

Nothing here performs network, provider, model, credential or CED activity, and
the artifact's zero claims are cross-checked against live tripwire
instrumentation rather than trusted.

The module is import-inert: building an artifact requires an explicit call.
"""

from __future__ import annotations

import ast
import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .acquisition_tripwires import (
    assert_acquisition_artifact_tripwires_v0,
    require_clean_acquisition_boundary_tripwire_v0,
)
from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_raw_wire_mapping_cases_v2 import (
    FROZEN_OPENROUTER_WIRE_CASES_V2,
    OPENROUTER_WIRE_CASE_SET_ID_V2,
    OpenRouterWireCaseKindV2,
    OpenRouterWireCaseV2,
    OpenRouterWireExpectedOutcomeV2,
)
from .openrouter_raw_wire_mapping_v2 import (
    OPENROUTER_WIRE_GUARD_ORDER_ID_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_RELATIVE_PATH_V2,
    OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2,
    FROZEN_OPENROUTER_METADATA_KNOWN_FIELDS_V2,
    OpenRouterNormalizedWireMappingV2,
    OpenRouterWireCacheStatusV2,
    OpenRouterWireFailureCodeV2,
    OpenRouterWireMappingError,
    build_openrouter_raw_wire_observation_v2,
    map_openrouter_raw_wire_v2,
)

OPENROUTER_WIRE_EVALUATION_SCHEMA_V2 = (
    "socrateszero-openrouter-raw-wire-mapping-evaluation/v2"
)
OPENROUTER_WIRE_CASE_RESULT_SCHEMA_V2 = (
    "socrateszero-openrouter-raw-wire-case-result/v2"
)
OPENROUTER_WIRE_REPLAY_EXECUTION_SCHEMA_V2 = (
    "socrateszero-openrouter-raw-wire-replay-execution/v2"
)
OPENROUTER_WIRE_REPLAY_LOCK_SCHEMA_V2 = (
    "socrateszero-openrouter-raw-wire-replay-lock/v2"
)

OPENROUTER_WIRE_ARTIFACT_RELATIVE_PATH_V2 = (
    "docs/branches/feature-socrates-zero-openrouter-raw-wire-mapping-v2"
    "/artifacts/socrateszero_openrouter_raw_wire_mapping_v2.json"
)
OPENROUTER_WIRE_REPLAY_EXECUTION_RELATIVE_PATH_V2 = (
    "docs/branches/feature-socrates-zero-openrouter-raw-wire-mapping-v2"
    "/artifacts/socrateszero_openrouter_raw_wire_mapping_replay_execution_v2.json"
)
OPENROUTER_WIRE_REPLAY_LOCK_RELATIVE_PATH_V2 = (
    "docs/branches/feature-socrates-zero-openrouter-raw-wire-mapping-v2"
    "/artifacts/socrateszero_openrouter_raw_wire_mapping_replay_lock_v2.json"
)

#: Normalized fields that carry authority.  Used to prove mechanically that
#: unknown/additive content cannot move any of them.
FROZEN_OPENROUTER_WIRE_AUTHORITATIVE_FIELDS_V2: Tuple[str, ...] = (
    "envelope_kind",
    "actual_served_model",
    "actual_served_model_status",
    "router_metadata_presence",
    "requested_model",
    "routing_strategy",
    "region_presence",
    "region",
    "summary",
    "attempt",
    "is_byok",
    "endpoint_collection",
    "attempts_presence",
    "attempts",
    "pipeline_presence",
    "cache_status_presence",
    "cache_status",
    "cache_age_seconds",
    "cache_ttl_seconds",
    "cache_source_generation_id",
    "generation_id",
    "exact_endpoint_response_identity",
    "exact_endpoint_response_identity_status",
)


class _FrozenEvaluationContractV2(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class OpenRouterWireHypothesisStatusV2(str, Enum):
    SUPPORTED = "SUPPORTED"
    FALSIFIED = "FALSIFIED"


class OpenRouterWireActualOutcomeV2(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    INVALID_FIXTURE_CONSTRUCTION = "INVALID_FIXTURE_CONSTRUCTION"


class OpenRouterWireBoundaryCountersV2(_FrozenEvaluationContractV2):
    """Instrumented boundary evidence.  Cross-checked, never trusted."""

    external_network_attempts: int = Field(ge=0)
    credential_access_attempts: int = Field(ge=0)
    live_provider_calls: int = Field(ge=0)
    provider_sdk_calls: int = Field(ge=0)
    model_executions: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    canonical_application_calls: int = Field(ge=0)
    official_source_retrievals: int = Field(ge=0)


class OpenRouterWireThresholdsV2(_FrozenEvaluationContractV2):
    """Predeclared before authoritative execution and content addressed."""

    required_positive_cases_accepted: int = 17
    required_adversarial_cases_rejected: int = 43
    required_unexpected_results: int = 0
    required_invalid_fixture_constructions: int = 0
    maximum_false_authority_grants: int = 0
    maximum_endpoint_identity_synthesis: int = 0
    maximum_requested_to_actual_substitutions: int = 0
    maximum_provider_display_to_endpoint_substitutions: int = 0
    maximum_metadata_absence_cache_hit_inferences: int = 0
    maximum_unknown_field_authority_escalations: int = 0
    maximum_repository_convention_mappings: int = 0
    maximum_historical_canned_shape_dependencies: int = 0
    maximum_external_activity: int = 0
    thresholds_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterWireThresholdsV2":
        expected = stable_contract_id(
            "szorwirethresholdsv2",
            self.model_dump(mode="json", exclude={"thresholds_id"}),
        )
        if self.thresholds_id not in (None, expected):
            raise ContractValidationError("wire thresholds ID mismatch")
        object.__setattr__(self, "thresholds_id", expected)
        return self


FROZEN_OPENROUTER_WIRE_THRESHOLDS_V2 = OpenRouterWireThresholdsV2()
OPENROUTER_WIRE_THRESHOLDS_ID_V2 = FROZEN_OPENROUTER_WIRE_THRESHOLDS_V2.thresholds_id


class OpenRouterWireCaseResultV2(_FrozenEvaluationContractV2):
    schema_version: Literal[
        OPENROUTER_WIRE_CASE_RESULT_SCHEMA_V2
    ] = OPENROUTER_WIRE_CASE_RESULT_SCHEMA_V2
    case_id: str
    kind: OpenRouterWireCaseKindV2
    case_fingerprint: str
    raw_observation_id: str
    expected_outcome: OpenRouterWireExpectedOutcomeV2
    actual_outcome: OpenRouterWireActualOutcomeV2
    expected_failure_code: Optional[OpenRouterWireFailureCodeV2] = None
    actual_failure_code: Optional[OpenRouterWireFailureCodeV2] = None
    mapping_id: Optional[str] = None
    field_mismatches: Tuple[str, ...] = ()
    endpoint_identity_synthesized: bool = False
    requested_substituted_for_actual: bool = False
    provider_display_substituted_for_endpoint: bool = False
    cache_hit_inferred_from_absence: bool = False
    unknown_field_authority_escalated: bool = False
    result_matches_expectation: bool


class OpenRouterWireMetricsV2(_FrozenEvaluationContractV2):
    total_cases: int = Field(ge=0)
    positive_cases: int = Field(ge=0)
    adversarial_cases: int = Field(ge=0)
    accepted_as_expected: int = Field(ge=0)
    rejected_as_expected: int = Field(ge=0)
    unexpected_results: int = Field(ge=0)
    invalid_fixture_constructions: int = Field(ge=0)
    guard_code_mismatches: int = Field(ge=0)
    field_mismatches: int = Field(ge=0)
    endpoint_identity_synthesis: int = Field(ge=0)
    requested_to_actual_substitutions: int = Field(ge=0)
    provider_display_to_endpoint_substitutions: int = Field(ge=0)
    metadata_absence_cache_hit_inferences: int = Field(ge=0)
    unknown_field_authority_escalations: int = Field(ge=0)
    repository_convention_mappings: int = Field(ge=0)
    historical_canned_shape_dependencies: int = Field(ge=0)
    distinct_guards_exercised: int = Field(ge=0)
    all_thresholds_pass: bool


class OpenRouterRawWireMappingArtifactV2(_FrozenEvaluationContractV2):
    schema_version: Literal[
        OPENROUTER_WIRE_EVALUATION_SCHEMA_V2
    ] = OPENROUTER_WIRE_EVALUATION_SCHEMA_V2
    source_manifest_id: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_ID_V2
    source_manifest_sha256: Literal[
        OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    ] = OPENROUTER_WIRE_MAPPING_SOURCE_MANIFEST_SHA256_V2
    case_set_id: str
    guard_order_id: Literal[
        OPENROUTER_WIRE_GUARD_ORDER_ID_V2
    ] = OPENROUTER_WIRE_GUARD_ORDER_ID_V2
    thresholds: OpenRouterWireThresholdsV2
    thresholds_id: str
    boundary_counters: OpenRouterWireBoundaryCountersV2
    case_results: Tuple[OpenRouterWireCaseResultV2, ...]
    metrics: OpenRouterWireMetricsV2
    exact_endpoint_response_identity_status: Literal[
        "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"
    ] = "UNAVAILABLE_BY_DOCUMENTED_CONTRACT"
    p17_input_token_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p18_pricing_record: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    p19_total_cost_bound: Literal["NOT_ESTABLISHED"] = "NOT_ESTABLISHED"
    runtime_authority: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    live_openrouter_execution: Literal["NOT_AUTHORIZED"] = "NOT_AUTHORIZED"
    hypothesis_status: OpenRouterWireHypothesisStatusV2
    artifact_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterRawWireMappingArtifactV2":
        if self.thresholds_id != self.thresholds.thresholds_id:
            raise ContractValidationError("artifact thresholds identity disagrees")
        if self.case_set_id != OPENROUTER_WIRE_CASE_SET_ID_V2:
            raise ContractValidationError("artifact case-set identity changed")
        expected_metrics = _derive_metrics_v2(self.case_results)
        if self.metrics != expected_metrics:
            raise ContractValidationError("artifact metrics are not fully derived")
        supported = (
            self.metrics.all_thresholds_pass
            and self.boundary_counters.model_dump(mode="python")
            == {
                name: 0
                for name in OpenRouterWireBoundaryCountersV2.model_fields
            }
        )
        expected_status = (
            OpenRouterWireHypothesisStatusV2.SUPPORTED
            if supported
            else OpenRouterWireHypothesisStatusV2.FALSIFIED
        )
        if self.hypothesis_status is not expected_status:
            raise ContractValidationError("artifact hypothesis status is not derived")
        assert_acquisition_artifact_tripwires_v0(self.boundary_counters)
        expected = stable_contract_id(
            "szorwireartifactv2",
            self.model_dump(mode="json", exclude={"artifact_id"}),
        )
        if self.artifact_id not in (None, expected):
            raise ContractValidationError("wire mapping artifact ID mismatch")
        object.__setattr__(self, "artifact_id", expected)
        return self


# ------------------------------------------------------------ safety probes --


def _decoded_body(case: OpenRouterWireCaseV2) -> Optional[Dict[str, Any]]:
    try:
        decoded = json.loads(case.raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _stripped_of_unknown(body: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only what the mapper is allowed to read."""
    stripped: Dict[str, Any] = {
        key: value
        for key, value in body.items()
        if key in ("model", "error", "openrouter_metadata")
    }
    metadata = stripped.get("openrouter_metadata")
    if isinstance(metadata, dict):
        stripped["openrouter_metadata"] = {
            key: value
            for key, value in metadata.items()
            if key in FROZEN_OPENROUTER_METADATA_KNOWN_FIELDS_V2
        }
    return stripped


def _authoritative_subset(mapping: OpenRouterNormalizedWireMappingV2) -> Dict[str, Any]:
    dumped = mapping.model_dump(mode="json")
    return {
        name: dumped[name] for name in FROZEN_OPENROUTER_WIRE_AUTHORITATIVE_FIELDS_V2
    }


def _probe_case_safety(
    case: OpenRouterWireCaseV2, mapping: OpenRouterNormalizedWireMappingV2
) -> Dict[str, bool]:
    """Derive the safety flags from the observation, never from a claim."""
    body = _decoded_body(case)

    endpoint_synthesized = mapping.exact_endpoint_response_identity is not None

    wire_model = body.get("model") if body else None
    requested_substituted = mapping.actual_served_model is not None and (
        not isinstance(wire_model, str) or mapping.actual_served_model != wire_model
    )

    metadata = (body or {}).get("openrouter_metadata")
    source_providers = []
    if isinstance(metadata, dict):
        endpoints = metadata.get("endpoints")
        if isinstance(endpoints, dict) and isinstance(endpoints.get("available"), list):
            source_providers += [
                entry.get("provider")
                for entry in endpoints["available"]
                if isinstance(entry, dict)
            ]
        if isinstance(metadata.get("attempts"), list):
            source_providers += [
                entry.get("provider")
                for entry in metadata["attempts"]
                if isinstance(entry, dict)
            ]
    mapped_providers = [
        candidate.provider_display_name
        for candidate in (
            mapping.endpoint_collection.available if mapping.endpoint_collection else ()
        )
    ] + [record.provider_display_name for record in mapping.attempts]
    provider_substituted = mapped_providers != [
        provider for provider in source_providers if isinstance(provider, str)
    ]

    header_names = {name.strip().lower() for name, _ in case.headers}
    cache_inferred = (
        mapping.cache_status is OpenRouterWireCacheStatusV2.HIT
        and "x-openrouter-cache-status" not in header_names
    )

    escalated = False
    if body is not None:
        stripped = _stripped_of_unknown(body)
        try:
            stripped_mapping = map_openrouter_raw_wire_v2(
                build_openrouter_raw_wire_observation_v2(
                    json.dumps(stripped).encode("utf-8"), case.headers
                )
            )
        except (OpenRouterWireMappingError, ContractValidationError):
            escalated = True
        else:
            escalated = _authoritative_subset(stripped_mapping) != _authoritative_subset(
                mapping
            )

    return {
        "endpoint_identity_synthesized": endpoint_synthesized,
        "requested_substituted_for_actual": requested_substituted,
        "provider_display_substituted_for_endpoint": provider_substituted,
        "cache_hit_inferred_from_absence": cache_inferred,
        "unknown_field_authority_escalated": escalated,
    }


def evaluate_openrouter_wire_case_v2(
    case: OpenRouterWireCaseV2,
) -> OpenRouterWireCaseResultV2:
    """Evaluate one frozen case deterministically."""
    if type(case) is not OpenRouterWireCaseV2:
        raise ContractValidationError("evaluation requires the exact frozen case type")
    try:
        observation = build_openrouter_raw_wire_observation_v2(
            case.raw_body, case.headers
        )
    except ContractValidationError:
        return OpenRouterWireCaseResultV2(
            case_id=case.case_id,
            kind=case.kind,
            case_fingerprint=case.case_fingerprint or "",
            raw_observation_id="",
            expected_outcome=case.expected_outcome,
            actual_outcome=OpenRouterWireActualOutcomeV2.INVALID_FIXTURE_CONSTRUCTION,
            expected_failure_code=case.expected_failure_code,
            result_matches_expectation=False,
        )

    try:
        mapping = map_openrouter_raw_wire_v2(observation)
    except OpenRouterWireMappingError as exc:
        matches = (
            case.expected_outcome is OpenRouterWireExpectedOutcomeV2.REJECTED
            and exc.code is case.expected_failure_code
        )
        return OpenRouterWireCaseResultV2(
            case_id=case.case_id,
            kind=case.kind,
            case_fingerprint=case.case_fingerprint or "",
            raw_observation_id=observation.observation_id or "",
            expected_outcome=case.expected_outcome,
            actual_outcome=OpenRouterWireActualOutcomeV2.REJECTED,
            expected_failure_code=case.expected_failure_code,
            actual_failure_code=exc.code,
            result_matches_expectation=matches,
        )

    dumped = mapping.model_dump(mode="json")
    mismatches = tuple(
        name
        for name, expected_json in case.expected_fields
        if canonical_json(dumped.get(name)) != expected_json
    )
    safety = _probe_case_safety(case, mapping)
    matches = (
        case.expected_outcome is OpenRouterWireExpectedOutcomeV2.ACCEPTED
        and not mismatches
        and not any(safety.values())
    )
    return OpenRouterWireCaseResultV2(
        case_id=case.case_id,
        kind=case.kind,
        case_fingerprint=case.case_fingerprint or "",
        raw_observation_id=observation.observation_id or "",
        expected_outcome=case.expected_outcome,
        actual_outcome=OpenRouterWireActualOutcomeV2.ACCEPTED,
        expected_failure_code=case.expected_failure_code,
        mapping_id=mapping.mapping_id,
        field_mismatches=mismatches,
        result_matches_expectation=matches,
        **safety,
    )


# ------------------------------------------------------- static provenance --


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


#: Marker fragments are split so this detector's own source never contains the
#: literals it searches for.  Without the split the scan matches itself, which is
#: exactly the false positive this pair of counters exists to rule out.
_HISTORICAL_MARKERS: Tuple[str, ...] = (
    "openrouter_acquisition" + "_cases",
    "FROZEN_OPENROUTER_" + "ADAPTER",
    "openrouter_acquisition" + "_evaluation",
)
_CONVENTION_MARKERS: Tuple[str, ...] = (
    "openrouter_route_controls" + "_parser",
    "FROZEN_OPENROUTER_" + "ROUTE_CONTROL",
    "openrouter_route_controls" + "_evaluation",
)
_SCANNED_RUNTIME_MODULES: Tuple[str, ...] = (
    "openrouter_raw_wire_mapping_v2.py",
    "openrouter_raw_wire_mapping_cases_v2.py",
    "openrouter_raw_wire_mapping_evaluation_v2.py",
)


def _imported_module_names(source: str) -> set:
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(("." * node.level) + (node.module or ""))
    return modules


def _static_dependency_counts(root: Optional[Path] = None) -> Tuple[int, int]:
    """Count repository-convention and historical-canned-shape dependencies.

    Imports are the authoritative signal; the text scan is a second net for a
    dependency expressed without an import.
    """
    repository_root = _repository_root() if root is None else Path(root)
    runtime_dir = repository_root / "backend" / "dialogues" / "socrates_zero"
    convention = 0
    historical = 0
    for name in _SCANNED_RUNTIME_MODULES:
        path = runtime_dir / name
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        modules = _imported_module_names(source)
        if any(
            marker in source or any(marker in module for module in modules)
            for marker in _HISTORICAL_MARKERS
        ):
            historical += 1
        if any(
            marker in source or any(marker in module for module in modules)
            for marker in _CONVENTION_MARKERS
        ):
            convention += 1
    return convention, historical


def _derive_metrics_v2(
    results: Tuple[OpenRouterWireCaseResultV2, ...],
    static_counts: Optional[Tuple[int, int]] = None,
) -> OpenRouterWireMetricsV2:
    convention, historical = (
        _static_dependency_counts() if static_counts is None else static_counts
    )
    accepted = sum(
        result.actual_outcome is OpenRouterWireActualOutcomeV2.ACCEPTED
        and result.result_matches_expectation
        for result in results
    )
    rejected = sum(
        result.actual_outcome is OpenRouterWireActualOutcomeV2.REJECTED
        and result.result_matches_expectation
        for result in results
    )
    unexpected = sum(not result.result_matches_expectation for result in results)
    invalid = sum(
        result.actual_outcome
        is OpenRouterWireActualOutcomeV2.INVALID_FIXTURE_CONSTRUCTION
        for result in results
    )
    guard_mismatches = sum(
        result.actual_outcome is OpenRouterWireActualOutcomeV2.REJECTED
        and result.actual_failure_code is not result.expected_failure_code
        for result in results
    )
    metrics = {
        "total_cases": len(results),
        "positive_cases": sum(
            result.kind is OpenRouterWireCaseKindV2.POSITIVE for result in results
        ),
        "adversarial_cases": sum(
            result.kind is OpenRouterWireCaseKindV2.ADVERSARIAL for result in results
        ),
        "accepted_as_expected": accepted,
        "rejected_as_expected": rejected,
        "unexpected_results": unexpected,
        "invalid_fixture_constructions": invalid,
        "guard_code_mismatches": guard_mismatches,
        "field_mismatches": sum(len(result.field_mismatches) for result in results),
        "endpoint_identity_synthesis": sum(
            result.endpoint_identity_synthesized for result in results
        ),
        "requested_to_actual_substitutions": sum(
            result.requested_substituted_for_actual for result in results
        ),
        "provider_display_to_endpoint_substitutions": sum(
            result.provider_display_substituted_for_endpoint for result in results
        ),
        "metadata_absence_cache_hit_inferences": sum(
            result.cache_hit_inferred_from_absence for result in results
        ),
        "unknown_field_authority_escalations": sum(
            result.unknown_field_authority_escalated for result in results
        ),
        "repository_convention_mappings": convention,
        "historical_canned_shape_dependencies": historical,
        "distinct_guards_exercised": len(
            {
                result.actual_failure_code
                for result in results
                if result.actual_failure_code is not None
            }
        ),
    }
    thresholds = FROZEN_OPENROUTER_WIRE_THRESHOLDS_V2
    passes = (
        metrics["accepted_as_expected"]
        == thresholds.required_positive_cases_accepted
        and metrics["rejected_as_expected"]
        == thresholds.required_adversarial_cases_rejected
        and metrics["unexpected_results"] == thresholds.required_unexpected_results
        and metrics["invalid_fixture_constructions"]
        == thresholds.required_invalid_fixture_constructions
        and metrics["guard_code_mismatches"] == 0
        and metrics["field_mismatches"] == 0
        and metrics["endpoint_identity_synthesis"]
        <= thresholds.maximum_endpoint_identity_synthesis
        and metrics["requested_to_actual_substitutions"]
        <= thresholds.maximum_requested_to_actual_substitutions
        and metrics["provider_display_to_endpoint_substitutions"]
        <= thresholds.maximum_provider_display_to_endpoint_substitutions
        and metrics["metadata_absence_cache_hit_inferences"]
        <= thresholds.maximum_metadata_absence_cache_hit_inferences
        and metrics["unknown_field_authority_escalations"]
        <= thresholds.maximum_unknown_field_authority_escalations
        and metrics["repository_convention_mappings"]
        <= thresholds.maximum_repository_convention_mappings
        and metrics["historical_canned_shape_dependencies"]
        <= thresholds.maximum_historical_canned_shape_dependencies
    )
    return OpenRouterWireMetricsV2(**metrics, all_thresholds_pass=passes)


def evaluate_openrouter_wire_case_set_v2() -> Tuple[OpenRouterWireCaseResultV2, ...]:
    return tuple(
        evaluate_openrouter_wire_case_v2(case)
        for case in FROZEN_OPENROUTER_WIRE_CASES_V2
    )


def build_openrouter_raw_wire_mapping_artifact_v2(
    root: Optional[Path] = None,
) -> OpenRouterRawWireMappingArtifactV2:
    """Build the authoritative artifact.  Requires an active boundary tripwire."""
    snapshot = require_clean_acquisition_boundary_tripwire_v0()
    results = evaluate_openrouter_wire_case_set_v2()
    metrics = _derive_metrics_v2(results, _static_dependency_counts(root))
    counters = OpenRouterWireBoundaryCountersV2(
        external_network_attempts=snapshot.external_network_attempts,
        credential_access_attempts=snapshot.credential_access_attempts,
        live_provider_calls=snapshot.live_provider_calls,
        provider_sdk_calls=snapshot.provider_sdk_calls,
        model_executions=snapshot.model_executions,
        tool_calls=snapshot.tool_calls,
        canonical_application_calls=snapshot.canonical_application_calls,
        official_source_retrievals=0,
    )
    supported = metrics.all_thresholds_pass and all(
        value == 0 for value in counters.model_dump(mode="python").values()
    )
    return OpenRouterRawWireMappingArtifactV2(
        case_set_id=OPENROUTER_WIRE_CASE_SET_ID_V2,
        thresholds=FROZEN_OPENROUTER_WIRE_THRESHOLDS_V2,
        thresholds_id=OPENROUTER_WIRE_THRESHOLDS_ID_V2 or "",
        boundary_counters=counters,
        case_results=results,
        metrics=metrics,
        hypothesis_status=(
            OpenRouterWireHypothesisStatusV2.SUPPORTED
            if supported
            else OpenRouterWireHypothesisStatusV2.FALSIFIED
        ),
    )


def render_openrouter_raw_wire_mapping_artifact_v2(
    artifact: OpenRouterRawWireMappingArtifactV2,
) -> bytes:
    if type(artifact) is not OpenRouterRawWireMappingArtifactV2:
        raise ContractValidationError("artifact must use the exact frozen v2 type")
    return canonical_json(artifact.model_dump(mode="json")).encode("utf-8") + b"\n"


def load_openrouter_raw_wire_mapping_artifact_v2(
    path: Path,
) -> OpenRouterRawWireMappingArtifactV2:
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractValidationError("wire artifact is unavailable or malformed") from exc
    artifact = OpenRouterRawWireMappingArtifactV2.model_validate(value)
    if Path(path).read_bytes() != render_openrouter_raw_wire_mapping_artifact_v2(
        artifact
    ):
        raise ContractValidationError("wire artifact bytes are not canonical")
    return artifact


# ------------------------------------------------------------------ replay --


class OpenRouterWireReplayExecutionV2(_FrozenEvaluationContractV2):
    schema_version: Literal[
        OPENROUTER_WIRE_REPLAY_EXECUTION_SCHEMA_V2
    ] = OPENROUTER_WIRE_REPLAY_EXECUTION_SCHEMA_V2
    source_artifact_id: str
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recomputed_artifact_id: str
    recomputed_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    case_set_id: str
    ordered_case_result_fingerprints: Tuple[str, ...]
    semantic_equality: bool
    artifact_id_equality: bool
    byte_identity: bool
    official_source_retrievals: Literal[0] = 0
    execution_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterWireReplayExecutionV2":
        expected = stable_contract_id(
            "szorwirereplayexecutionv2",
            self.model_dump(mode="json", exclude={"execution_id"}),
        )
        if self.execution_id not in (None, expected):
            raise ContractValidationError("wire replay execution ID mismatch")
        object.__setattr__(self, "execution_id", expected)
        return self


class OpenRouterWireReplayLockV2(_FrozenEvaluationContractV2):
    schema_version: Literal[
        OPENROUTER_WIRE_REPLAY_LOCK_SCHEMA_V2
    ] = OPENROUTER_WIRE_REPLAY_LOCK_SCHEMA_V2
    artifact_id: str
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_execution_id: str
    replay_execution_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_equality: bool
    artifact_id_equality: bool
    byte_identity: bool
    lock_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterWireReplayLockV2":
        if not (self.semantic_equality and self.artifact_id_equality and self.byte_identity):
            raise ContractValidationError(
                "a replay lock requires deterministic replay in all three senses"
            )
        expected = stable_contract_id(
            "szorwirereplaylockv2",
            self.model_dump(mode="json", exclude={"lock_id"}),
        )
        if self.lock_id not in (None, expected):
            raise ContractValidationError("wire replay lock ID mismatch")
        object.__setattr__(self, "lock_id", expected)
        return self


def replay_openrouter_raw_wire_mapping_v2(
    artifact_path: Path,
) -> Tuple[OpenRouterWireReplayExecutionV2, OpenRouterWireReplayLockV2]:
    """Reload the persisted artifact and rebuild it from the frozen inputs."""
    source_bytes = Path(artifact_path).read_bytes()
    source_artifact = load_openrouter_raw_wire_mapping_artifact_v2(Path(artifact_path))
    recomputed = build_openrouter_raw_wire_mapping_artifact_v2()
    recomputed_bytes = render_openrouter_raw_wire_mapping_artifact_v2(recomputed)
    execution = OpenRouterWireReplayExecutionV2(
        source_artifact_id=source_artifact.artifact_id or "",
        source_artifact_sha256=hashlib.sha256(source_bytes).hexdigest(),
        recomputed_artifact_id=recomputed.artifact_id or "",
        recomputed_artifact_sha256=hashlib.sha256(recomputed_bytes).hexdigest(),
        case_set_id=OPENROUTER_WIRE_CASE_SET_ID_V2,
        ordered_case_result_fingerprints=tuple(
            result.case_fingerprint for result in recomputed.case_results
        ),
        semantic_equality=recomputed == source_artifact,
        artifact_id_equality=recomputed.artifact_id == source_artifact.artifact_id,
        byte_identity=recomputed_bytes == source_bytes,
    )
    lock = OpenRouterWireReplayLockV2(
        artifact_id=source_artifact.artifact_id or "",
        artifact_sha256=hashlib.sha256(source_bytes).hexdigest(),
        replay_execution_id=execution.execution_id or "",
        replay_execution_sha256=hashlib.sha256(
            render_openrouter_wire_replay_execution_v2(execution)
        ).hexdigest(),
        semantic_equality=execution.semantic_equality,
        artifact_id_equality=execution.artifact_id_equality,
        byte_identity=execution.byte_identity,
    )
    return execution, lock


def render_openrouter_wire_replay_execution_v2(
    execution: OpenRouterWireReplayExecutionV2,
) -> bytes:
    return canonical_json(execution.model_dump(mode="json")).encode("utf-8") + b"\n"


def render_openrouter_wire_replay_lock_v2(lock: OpenRouterWireReplayLockV2) -> bytes:
    return canonical_json(lock.model_dump(mode="json")).encode("utf-8") + b"\n"


def write_once_v2(path: Path, payload: bytes) -> str:
    """Write evidence exactly once and return its digest."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise ContractValidationError(
            f"write-once evidence already exists: {target}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "FROZEN_OPENROUTER_WIRE_AUTHORITATIVE_FIELDS_V2",
    "FROZEN_OPENROUTER_WIRE_THRESHOLDS_V2",
    "OPENROUTER_WIRE_ARTIFACT_RELATIVE_PATH_V2",
    "OPENROUTER_WIRE_CASE_RESULT_SCHEMA_V2",
    "OPENROUTER_WIRE_EVALUATION_SCHEMA_V2",
    "OPENROUTER_WIRE_REPLAY_EXECUTION_RELATIVE_PATH_V2",
    "OPENROUTER_WIRE_REPLAY_LOCK_RELATIVE_PATH_V2",
    "OPENROUTER_WIRE_THRESHOLDS_ID_V2",
    "OpenRouterRawWireMappingArtifactV2",
    "OpenRouterWireActualOutcomeV2",
    "OpenRouterWireBoundaryCountersV2",
    "OpenRouterWireCaseResultV2",
    "OpenRouterWireHypothesisStatusV2",
    "OpenRouterWireMetricsV2",
    "OpenRouterWireReplayExecutionV2",
    "OpenRouterWireReplayLockV2",
    "OpenRouterWireThresholdsV2",
    "build_openrouter_raw_wire_mapping_artifact_v2",
    "evaluate_openrouter_wire_case_set_v2",
    "evaluate_openrouter_wire_case_v2",
    "load_openrouter_raw_wire_mapping_artifact_v2",
    "render_openrouter_raw_wire_mapping_artifact_v2",
    "render_openrouter_wire_replay_execution_v2",
    "render_openrouter_wire_replay_lock_v2",
    "replay_openrouter_raw_wire_mapping_v2",
    "write_once_v2",
]
