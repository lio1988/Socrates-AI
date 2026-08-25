"""Hermetic canned-only observation acquisition for SocratesZero.

The runtime in this module has one authority: acquire opaque response bytes from
an in-process canned transport and describe what happened.  It cannot contact a
provider, inspect credentials, invoke a model or tool, mutate a dialogue, or
admit/apply an observation.  Provider-visible application bytes and branch-local
transport context are separate arguments all the way to the transport boundary.

Every validation follows the committed ``FIRST_ACQUISITION_GUARD_WINS`` order.
All attempts, including raised and timed-out canned attempts, increment the
canned invocation counter exactly once on transport entry.  External execution
counters are structurally fixed at zero and response content remains opaque.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import weakref
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence, Tuple, Union

from .acquisition_contracts import (
    ACQUISITION_CONTRACT_ID,
    ACQUISITION_GUARD_ORDER,
    ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION,
    CANNED_TRANSPORT_ID,
    FROZEN_ACQUISITION_FAILURE_TAXONOMY,
    FROZEN_ACQUISITION_VALIDATION_ORDER,
    FROZEN_REQUIRED_CONTROL_STATES,
    AcquisitionArtifactInclusionPolicy,
    AcquisitionAttemptOutcome,
    AcquisitionAttemptReceipt,
    AcquisitionCapabilitySnapshot,
    AcquisitionControlEvidence,
    AcquisitionControlName,
    AcquisitionControlPolicy,
    AcquisitionControlState,
    AcquisitionDataClassification,
    AcquisitionExecutionUsage,
    AcquisitionFailureCode,
    AcquisitionGuardEvaluation,
    AcquisitionGuardId,
    AcquisitionGuardStage,
    AcquisitionGuardState,
    AcquisitionHistoricalUsage,
    AcquisitionIsolationFingerprint,
    AcquisitionIsolationReceipt,
    AcquisitionIsolationScope,
    AcquisitionPrimaryResult,
    AcquisitionProviderModelBinding,
    AcquisitionRedactionStatus,
    AcquisitionResourceQuantity,
    AcquisitionRetentionPolicy,
    AcquisitionRetentionReceipt,
    AcquisitionSeedStatus,
    AcquisitionSemanticRequest,
    AcquisitionTransportAttempt,
    AcquisitionTransportMode,
    AcquisitionTransportStatus,
    AcquisitionTripwireCounters,
    CannedTransportEnvelope,
    ProviderVisibleRequestBytes,
    ResourceKnowledgeState,
    ResponseRetentionMode,
    UnadmittedAcquiredObservation,
)


CANNED_ACQUISITION_RUNTIME_VERSION = "socrateszero-canned-acquisition-runtime/v0"
CANNED_TRANSPORT_IMPLEMENTATION_ID = CANNED_TRANSPORT_ID
PROVIDER_VISIBLE_RENDERER_VERSION = "socrateszero-canonical-json-utf8/v0"
PROVIDER_VISIBLE_ENCODING = "utf-8"
CANNED_TIMEOUT_CLEANUP_ROUNDS = 2
CANNED_TIMEOUT_CLEANUP_GRACE_SECONDS = 0.05
FIRST_ACQUISITION_GUARD_ORDER = ACQUISITION_GUARD_ORDER

_FROZEN_NON_SENSITIVE_PROVIDER_MISMATCH_IDS = frozenset(
    {"phase8-wrong-seat-1"}
)
_FROZEN_NON_SENSITIVE_MODEL_MISMATCH_IDS = frozenset(
    {"phase8-recorded-model/1-wrong"}
)

_HEX_DIGITS = frozenset("0123456789abcdef")
_OUT_OF_BAND_PROVIDER_KEYS = frozenset(
    {
        "acquisition_attempt_id",
        "attempt_id",
        "attempt_index",
        "attempt_no",
        "attempt_number",
        "attempt_ordinal",
        "attempt_order",
        "api_key",
        "authorization",
        "branch_id",
        "branch_order",
        "credential",
        "credentials",
        "cookie",
        "cookies",
        "created_at",
        "cwd",
        "dispatch_order",
        "evaluated_at",
        "evaluation_order",
        "executed_at",
        "execution_order",
        "experiment_id",
        "experiment_label",
        "experiment_order",
        "experiment_outcome",
        "experiment_result",
        "file_path",
        "filesystem_path",
        "finished_at",
        "header",
        "headers",
        "invocation_order",
        "local_file_path",
        "local_filesystem_path",
        "local_path",
        "memory_address",
        "memory_state",
        "nonce",
        "pid",
        "process_id",
        "process_state",
        "random_nonce",
        "random_uuid",
        "repository_path",
        "repo_path",
        "response_id",
        "run_order",
        "sibling_branch_id",
        "sibling_id",
        "sibling_order",
        "sibling_state",
        "set_cookie",
        "started_at",
        "time_stamp",
        "timestamp",
        "transport_id",
        "transport_attempt_id",
        "transport_order",
        "transport_request_id",
        "updated_at",
        "uuid",
        "working_directory",
        "workspace_path",
    }
)


def _normalize_provider_key(key: object) -> Tuple[str, Tuple[str, ...], str]:
    """Normalize spelling variants without turning substrings into metadata."""

    text = str(key).strip()
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    normalized = re.sub(r"[^0-9A-Za-z]+", "_", text).strip("_").lower()
    parts = tuple(part for part in normalized.split("_") if part)
    return normalized, parts, "".join(parts)


def _is_out_of_band_provider_key(key: object) -> bool:
    normalized, parts, compact = _normalize_provider_key(key)
    if normalized in _OUT_OF_BAND_PROVIDER_KEYS:
        return True

    part_set = frozenset(parts)
    if "header" in part_set or "headers" in part_set:
        return True
    if "cookie" in part_set or "cookies" in part_set:
        return True
    if part_set.intersection({"credential", "credentials", "password", "secret", "secrets"}):
        return True
    if compact in {
        "apikey",
        "authorization",
        "bearertoken",
        "credentialfile",
        "credentialfiles",
        "credentialpath",
        "httpproxyauthorization",
        "privatekey",
        "proxyauthorization",
        "requestheaders",
        "secretkey",
        "setcookie",
    }:
        return True
    if "token" in part_set and part_set.intersection(
        {"access", "api", "auth", "authentication", "bearer", "credential", "secret"}
    ):
        return True
    if "key" in part_set and part_set.intersection(
        {"access", "api", "auth", "authentication", "credential", "private", "secret"}
    ):
        return True

    if "timestamp" in part_set or "nonce" in part_set or "uuid" in part_set:
        return True
    if "experiment" in part_set and part_set.intersection(
        {"id", "label", "order", "outcome", "result"}
    ):
        return True
    if "attempt" in part_set and part_set.intersection(
        {"id", "index", "no", "number", "ordinal", "order", "receipt"}
    ):
        return True
    if "order" in part_set and part_set.intersection(
        {"attempt", "branch", "dispatch", "evaluation", "execution", "experiment", "invocation", "run", "sibling", "transport"}
    ):
        return True
    if "process" in part_set and part_set.intersection({"id", "memory", "state"}):
        return True
    if "memory" in part_set and part_set.intersection({"address", "id", "state"}):
        return True
    if "path" in part_set and part_set.intersection(
        {"cwd", "file", "filesystem", "local", "repo", "repository", "working", "workspace"}
    ):
        return True
    if "sibling" in part_set and part_set.intersection(
        {"branch", "id", "order", "state"}
    ):
        return True
    if "branch" in part_set and "id" in part_set:
        return True
    if "transport" in part_set and part_set.intersection(
        {"attempt", "id", "order", "request"}
    ):
        return True
    return False


class AcquisitionRuntimeError(RuntimeError):
    """The hermetic runtime could not preserve its local safety contract."""


class CannedTransportExhausted(AcquisitionRuntimeError):
    """The ordered canned script has no entry for another invocation."""


class CannedTransportFailure(AcquisitionRuntimeError):
    """A deterministic failure injected at the in-memory transport boundary."""


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _canonical_bytes(value: object) -> bytes:
    return _canonical_json(value).encode(PROVIDER_VISIBLE_ENCODING)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_hex_digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value).issubset(_HEX_DIGITS)
    )


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}_{_sha256(_canonical_bytes(value))}"


def _project_canned_actual_identity(
    value: Optional[str],
    requested: str,
    frozen_non_sensitive_mismatches: frozenset[str],
) -> Tuple[Optional[str], bool]:
    if value is None or value == requested or value in frozen_non_sensitive_mismatches:
        return value, True
    return None, False


def _assert_no_out_of_band_keys(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if _is_out_of_band_provider_key(key):
                raise AcquisitionRuntimeError(
                    f"out-of-band key {key!r} entered provider-visible body at {path}"
                )
            _assert_no_out_of_band_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_no_out_of_band_keys(child, f"{path}[{index}]")


def build_provider_visible_request(
    application_body: Mapping[str, object],
) -> ProviderVisibleRequestBytes:
    """Freeze a public logical request as exact canonical UTF-8 application bytes."""

    _assert_no_out_of_band_keys(application_body)
    return ProviderVisibleRequestBytes(
        rendering_version=PROVIDER_VISIBLE_RENDERER_VERSION,
        canonical_request_json=_canonical_json(dict(application_body)),
    )


def render_provider_visible_request(request: AcquisitionSemanticRequest) -> bytes:
    """Return the already-frozen application body, never request identity metadata."""

    visible = request.provider_visible_request
    raw = visible.canonical_request_json.encode(PROVIDER_VISIBLE_ENCODING)
    if visible.byte_length != len(raw) or visible.sha256 != _sha256(raw):
        raise AcquisitionRuntimeError("provider-visible byte evidence does not match")
    parsed = json.loads(visible.canonical_request_json)
    if not isinstance(parsed, dict) or _canonical_json(parsed) != visible.canonical_request_json:
        raise AcquisitionRuntimeError("provider-visible body is not canonical JSON")
    _assert_no_out_of_band_keys(parsed)
    return raw


class CannedImplementationProfile(str, Enum):
    """Implementation-owned negative profiles; callers cannot supply booleans."""

    SAFE = "SAFE"
    REQUIRED_PROVIDER_IDENTITY_UNKNOWN = "REQUIRED_PROVIDER_IDENTITY_UNKNOWN"
    FALLBACK_CONTROL_UNKNOWN = "FALLBACK_CONTROL_UNKNOWN"
    RETRY_CONTROL_UNKNOWN = "RETRY_CONTROL_UNKNOWN"
    SDK_RETRY_CONTROL_UNKNOWN = "SDK_RETRY_CONTROL_UNKNOWN"
    TERMINATION_CONTROL_UNKNOWN = "TERMINATION_CONTROL_UNKNOWN"
    CANNED_ONLY_UNPROVEN = "CANNED_ONLY_UNPROVEN"
    NETWORK_PROHIBITION_UNPROVEN = "NETWORK_PROHIBITION_UNPROVEN"
    CREDENTIAL_PROHIBITION_UNPROVEN = "CREDENTIAL_PROHIBITION_UNPROVEN"
    IDENTITY_VERIFICATION_UNPROVEN = "IDENTITY_VERIFICATION_UNPROVEN"
    FALLBACK_DISABLE_UNPROVEN = "FALLBACK_DISABLE_UNPROVEN"
    RETRY_DISABLE_UNPROVEN = "RETRY_DISABLE_UNPROVEN"
    SDK_RETRY_DISABLE_UNPROVEN = "SDK_RETRY_DISABLE_UNPROVEN"
    TOOLS_DISABLE_UNPROVEN = "TOOLS_DISABLE_UNPROVEN"
    TERMINATION_UNPROVEN = "TERMINATION_UNPROVEN"
    ACCOUNTING_UNPROVEN = "ACCOUNTING_UNPROVEN"
    BUDGET_RESERVATION_UNPROVEN = "BUDGET_RESERVATION_UNPROVEN"
    REGISTRATION_UNPROVEN = "REGISTRATION_UNPROVEN"
    PROMPT_ENTROPY_INJECTION = "PROMPT_ENTROPY_INJECTION"


@dataclass(frozen=True)
class _ImplementationGuarantees:
    canned_only: bool = True
    network_prohibited: bool = True
    credentials_prohibited: bool = True
    exact_identity_verification: bool = True
    fallback_disabled: bool = True
    explicit_and_adapter_retries_disabled: bool = True
    sdk_and_hidden_retries_disabled: bool = True
    tools_disabled: bool = True
    hard_cancellation: bool = True
    complete_accounting: bool = True
    budget_reservation: bool = True
    registered: bool = True
    prompt_entropy_injection: bool = False
    control_state_overrides: Tuple[
        Tuple[AcquisitionControlName, AcquisitionControlState], ...
    ] = ()


ImplementationProfileInput = Union[
    CannedImplementationProfile,
    Sequence[CannedImplementationProfile],
]


def _normalize_profiles(
    profiles: ImplementationProfileInput,
) -> Tuple[CannedImplementationProfile, ...]:
    if isinstance(profiles, CannedImplementationProfile):
        return (profiles,)
    normalized = tuple(sorted(set(profiles), key=lambda item: item.value))
    if not normalized or any(
        not isinstance(item, CannedImplementationProfile) for item in normalized
    ):
        raise ValueError("implementation profiles must be named canned profiles")
    return normalized


def _single_profile_guarantees(
    profile: CannedImplementationProfile,
) -> _ImplementationGuarantees:
    unknown_control_by_profile = {
        CannedImplementationProfile.REQUIRED_PROVIDER_IDENTITY_UNKNOWN: (
            AcquisitionControlName.ACTUAL_PROVIDER_IDENTITY_VALIDATION
        ),
        CannedImplementationProfile.FALLBACK_CONTROL_UNKNOWN: (
            AcquisitionControlName.FALLBACK
        ),
        CannedImplementationProfile.RETRY_CONTROL_UNKNOWN: (
            AcquisitionControlName.EXPLICIT_RETRY
        ),
        CannedImplementationProfile.SDK_RETRY_CONTROL_UNKNOWN: (
            AcquisitionControlName.SDK_INTERNAL_RETRY
        ),
        CannedImplementationProfile.TERMINATION_CONTROL_UNKNOWN: (
            AcquisitionControlName.TIMEOUT_WORKER_TERMINATION
        ),
    }
    unknown_control = unknown_control_by_profile.get(profile)
    if unknown_control is not None:
        return _ImplementationGuarantees(
            control_state_overrides=(
                (unknown_control, AcquisitionControlState.UNKNOWN),
            )
        )
    if profile is CannedImplementationProfile.PROMPT_ENTROPY_INJECTION:
        return _ImplementationGuarantees(prompt_entropy_injection=True)
    values: dict[str, object] = {}
    field_by_profile = {
        CannedImplementationProfile.CANNED_ONLY_UNPROVEN: "canned_only",
        CannedImplementationProfile.NETWORK_PROHIBITION_UNPROVEN: "network_prohibited",
        CannedImplementationProfile.CREDENTIAL_PROHIBITION_UNPROVEN: "credentials_prohibited",
        CannedImplementationProfile.IDENTITY_VERIFICATION_UNPROVEN: "exact_identity_verification",
        CannedImplementationProfile.FALLBACK_DISABLE_UNPROVEN: "fallback_disabled",
        CannedImplementationProfile.RETRY_DISABLE_UNPROVEN: "explicit_and_adapter_retries_disabled",
        CannedImplementationProfile.SDK_RETRY_DISABLE_UNPROVEN: "sdk_and_hidden_retries_disabled",
        CannedImplementationProfile.TOOLS_DISABLE_UNPROVEN: "tools_disabled",
        CannedImplementationProfile.TERMINATION_UNPROVEN: "hard_cancellation",
        CannedImplementationProfile.ACCOUNTING_UNPROVEN: "complete_accounting",
        CannedImplementationProfile.BUDGET_RESERVATION_UNPROVEN: "budget_reservation",
        CannedImplementationProfile.REGISTRATION_UNPROVEN: "registered",
    }
    field = field_by_profile.get(profile)
    if field is not None:
        values[field] = False
    adverse_control_by_profile = {
        CannedImplementationProfile.CANNED_ONLY_UNPROVEN: (
            AcquisitionControlName.CANNED_ONLY_TRANSPORT,
            AcquisitionControlState.PROVEN_UNSUPPORTED,
        ),
        CannedImplementationProfile.NETWORK_PROHIBITION_UNPROVEN: (
            AcquisitionControlName.EXTERNAL_NETWORK,
            AcquisitionControlState.PROVEN_SUPPORTED,
        ),
        CannedImplementationProfile.CREDENTIAL_PROHIBITION_UNPROVEN: (
            AcquisitionControlName.CREDENTIAL_ACCESS,
            AcquisitionControlState.PROVEN_SUPPORTED,
        ),
        CannedImplementationProfile.IDENTITY_VERIFICATION_UNPROVEN: (
            AcquisitionControlName.ACTUAL_MODEL_IDENTITY_VALIDATION,
            AcquisitionControlState.PROVEN_UNSUPPORTED,
        ),
        CannedImplementationProfile.FALLBACK_DISABLE_UNPROVEN: (
            AcquisitionControlName.FALLBACK,
            AcquisitionControlState.PROVEN_SUPPORTED,
        ),
        CannedImplementationProfile.RETRY_DISABLE_UNPROVEN: (
            AcquisitionControlName.EXPLICIT_RETRY,
            AcquisitionControlState.PROVEN_SUPPORTED,
        ),
        CannedImplementationProfile.SDK_RETRY_DISABLE_UNPROVEN: (
            AcquisitionControlName.SDK_INTERNAL_RETRY,
            AcquisitionControlState.PROVEN_SUPPORTED,
        ),
        CannedImplementationProfile.TOOLS_DISABLE_UNPROVEN: (
            AcquisitionControlName.TOOLS,
            AcquisitionControlState.PROVEN_SUPPORTED,
        ),
        CannedImplementationProfile.TERMINATION_UNPROVEN: (
            AcquisitionControlName.TIMEOUT_WORKER_TERMINATION,
            AcquisitionControlState.PROVEN_UNSUPPORTED,
        ),
        CannedImplementationProfile.ACCOUNTING_UNPROVEN: (
            AcquisitionControlName.COST_REPORTING,
            AcquisitionControlState.PROVEN_UNSUPPORTED,
        ),
    }
    adverse_control = adverse_control_by_profile.get(profile)
    if adverse_control is not None:
        values["control_state_overrides"] = (adverse_control,)
    return _ImplementationGuarantees(**values)


def _profile_guarantees(
    profiles: ImplementationProfileInput,
) -> _ImplementationGuarantees:
    rows = tuple(
        _single_profile_guarantees(profile)
        for profile in _normalize_profiles(profiles)
    )
    boolean_fields = (
        "canned_only",
        "network_prohibited",
        "credentials_prohibited",
        "exact_identity_verification",
        "fallback_disabled",
        "explicit_and_adapter_retries_disabled",
        "sdk_and_hidden_retries_disabled",
        "tools_disabled",
        "hard_cancellation",
        "complete_accounting",
        "budget_reservation",
        "registered",
    )
    values = {
        name: all(getattr(row, name) for row in rows)
        for name in boolean_fields
    }
    values["prompt_entropy_injection"] = any(
        row.prompt_entropy_injection for row in rows
    )
    overrides: dict[AcquisitionControlName, AcquisitionControlState] = {}
    for row in rows:
        for name, state in row.control_state_overrides:
            previous = overrides.get(name)
            if previous is not None and previous is not state:
                raise ValueError(f"conflicting control override for {name.value}")
            overrides[name] = state
    values["control_state_overrides"] = tuple(
        sorted(overrides.items(), key=lambda item: item[0].value)
    )
    return _ImplementationGuarantees(**values)


def _control_state_for_snapshot(
    name: AcquisitionControlName,
    seed_status: AcquisitionSeedStatus,
) -> AcquisitionControlState:
    if name is AcquisitionControlName.SEED:
        return (
            AcquisitionControlState.PROVEN_SUPPORTED
            if seed_status is AcquisitionSeedStatus.SUPPORTED
            else AcquisitionControlState.PROVEN_UNSUPPORTED
        )
    allowed = dict(FROZEN_REQUIRED_CONTROL_STATES)[name]
    return allowed[0]


def build_canned_capability_snapshot(
    provider_id: str,
    adapter_id: str,
    adapter_version: str,
    adapter_revision_digest: str,
    requested_model_id: str,
    *,
    seed_status: AcquisitionSeedStatus,
    implementation_profile: ImplementationProfileInput = CannedImplementationProfile.SAFE,
) -> AcquisitionCapabilitySnapshot:
    """Build the only capability snapshot emitted by a named canned implementation."""

    guarantees = _profile_guarantees(implementation_profile)
    state_overrides = dict(guarantees.control_state_overrides)
    controls = []
    for name in AcquisitionControlName:
        state = state_overrides.get(
            name,
            _control_state_for_snapshot(name, seed_status),
        )
        evidence_payload = {
            "runtime_version": CANNED_ACQUISITION_RUNTIME_VERSION,
            "transport_id": CANNED_TRANSPORT_ID,
            "provider_id": provider_id,
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "adapter_revision_digest": adapter_revision_digest,
            "requested_model_id": requested_model_id,
            "control_name": name.value,
            "control_state": state.value,
        }
        digest = _sha256(_canonical_bytes(evidence_payload))
        controls.append(
            AcquisitionControlEvidence(
                name=name,
                state=state,
                evidence_id=f"szacqcannedevidence_{digest}",
                evidence_digest=digest,
            )
        )
    return AcquisitionCapabilitySnapshot(
        provider_id=provider_id,
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        adapter_revision_digest=adapter_revision_digest,
        requested_model_id=requested_model_id,
        transport_mode=(
            AcquisitionTransportMode.CANNED_ONLY
            if guarantees.canned_only
            else AcquisitionTransportMode.EXTERNAL
        ),
        registered_canned_transport_ids=(
            (CANNED_TRANSPORT_ID,) if guarantees.registered else ()
        ),
        controls=tuple(controls),
    )


_DIRECTIVE_BOOLEAN_FIELDS_V0 = (
    "raise_transport_error",
    "wait_for_cancellation",
    "resist_initial_cancellation",
    "completion_integrity",
    "resource_integrity",
    "retention_integrity",
    "final_receipt_integrity",
)


@dataclass(frozen=True)
class CannedTransportDirective:
    """One ordered canned outcome plus narrowly scoped negative-injection flags."""

    envelope: Optional[CannedTransportEnvelope] = None
    raise_transport_error: bool = False
    wait_for_cancellation: bool = False
    resist_initial_cancellation: bool = False
    completion_integrity: bool = True
    resource_integrity: bool = True
    retention_integrity: bool = True
    final_receipt_integrity: bool = True

    def __post_init__(self) -> None:
        if self.envelope is not None and type(self.envelope) is not CannedTransportEnvelope:
            raise TypeError("canned directive envelope must use the exact frozen type")
        if any(
            type(getattr(self, field)) is not bool
            for field in _DIRECTIVE_BOOLEAN_FIELDS_V0
        ):
            raise TypeError("canned directive flags must be exact booleans")
        selected = int(self.envelope is not None) + int(self.raise_transport_error)
        selected += int(self.wait_for_cancellation)
        if selected != 1:
            raise ValueError("exactly one canned directive outcome is required")
        if self.resist_initial_cancellation and not self.wait_for_cancellation:
            raise ValueError(
                "initial cancellation resistance requires a cancellation outcome"
            )
        if self.envelope is None and (
            not self.completion_integrity
            or not self.resource_integrity
            or not self.retention_integrity
            or not self.final_receipt_integrity
        ):
            raise ValueError("integrity injections require a returned envelope")


class CannedInvocationOutcome(str, Enum):
    RETURNED = "RETURNED"
    RAISED = "RAISED"
    CANCELLED = "CANCELLED"
    FORCED_CLEANUP = "FORCED_CLEANUP"
    SCRIPT_EXHAUSTED = "SCRIPT_EXHAUSTED"


@dataclass(frozen=True)
class CannedInvocationRecord:
    ordinal: int
    transport_attempt_id: str
    provider_visible_sha256: str
    provider_visible_length: int
    outcome: CannedInvocationOutcome
    cancellation_acknowledged: bool
    worker_terminated: bool
    completion_integrity: bool
    resource_integrity: bool
    retention_integrity: bool
    final_receipt_integrity: bool
    cancellation_requests: int = 0
    forced_cleanup: bool = False


@dataclass(frozen=True)
class AcquisitionRuntimeCounters:
    canned_transport_invocations: int = 0
    dns_calls: int = 0
    socket_calls: int = 0
    http_calls: int = 0
    credential_reads: int = 0
    provider_sdk_calls: int = 0
    live_provider_calls: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    canonical_application_calls: int = 0
    evaluator_guard_checks: int = 0

    @property
    def external_network_attempts(self) -> int:
        return self.dns_calls + self.socket_calls + self.http_calls

    def to_tripwire_counters(self) -> AcquisitionTripwireCounters:
        return AcquisitionTripwireCounters(
            canned_transport_invocations=self.canned_transport_invocations,
            external_network_attempts=self.external_network_attempts,
            credential_access_attempts=self.credential_reads,
            live_provider_calls=self.live_provider_calls,
            provider_sdk_calls=self.provider_sdk_calls,
            model_executions=self.model_calls,
            tool_calls=self.tool_calls,
            canonical_application_calls=self.canonical_application_calls,
        )

    def assert_hermetic(self) -> None:
        nonzero = {
            "dns_calls": self.dns_calls,
            "socket_calls": self.socket_calls,
            "http_calls": self.http_calls,
            "credential_reads": self.credential_reads,
            "provider_sdk_calls": self.provider_sdk_calls,
            "live_provider_calls": self.live_provider_calls,
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "canonical_application_calls": self.canonical_application_calls,
        }
        nonzero = {name: value for name, value in nonzero.items() if value}
        if nonzero:
            raise AcquisitionRuntimeError(f"non-hermetic runtime counters: {nonzero}")


class _CounterLedger:
    def __init__(self) -> None:
        self.canned_transport_invocations = 0
        self.evaluator_guard_checks = 0

    def enter_transport(self) -> int:
        self.canned_transport_invocations += 1
        return self.canned_transport_invocations

    def record_guard_check(self) -> None:
        self.evaluator_guard_checks += 1

    def snapshot(self) -> AcquisitionRuntimeCounters:
        counters = AcquisitionRuntimeCounters(
            canned_transport_invocations=self.canned_transport_invocations,
            evaluator_guard_checks=self.evaluator_guard_checks,
        )
        counters.assert_hermetic()
        return counters


_SEALED_LEDGER_ENTER_TRANSPORT = _CounterLedger.__dict__["enter_transport"]
_SEALED_LEDGER_RECORD_GUARD_CHECK = _CounterLedger.__dict__["record_guard_check"]
_SEALED_LEDGER_SNAPSHOT = _CounterLedger.__dict__["snapshot"]


def _guarantee_seal_payload(guarantees: _ImplementationGuarantees) -> Mapping[str, object]:
    return {
        "canned_only": guarantees.canned_only,
        "network_prohibited": guarantees.network_prohibited,
        "credentials_prohibited": guarantees.credentials_prohibited,
        "exact_identity_verification": guarantees.exact_identity_verification,
        "fallback_disabled": guarantees.fallback_disabled,
        "explicit_and_adapter_retries_disabled": (
            guarantees.explicit_and_adapter_retries_disabled
        ),
        "sdk_and_hidden_retries_disabled": guarantees.sdk_and_hidden_retries_disabled,
        "tools_disabled": guarantees.tools_disabled,
        "hard_cancellation": guarantees.hard_cancellation,
        "complete_accounting": guarantees.complete_accounting,
        "budget_reservation": guarantees.budget_reservation,
        "registered": guarantees.registered,
        "prompt_entropy_injection": guarantees.prompt_entropy_injection,
        "control_state_overrides": tuple(
            (name.value, state.value)
            for name, state in guarantees.control_state_overrides
        ),
    }


def _directive_seal_payload(directive: CannedTransportDirective) -> Mapping[str, object]:
    return {
        "envelope": (
            directive.envelope.model_dump(mode="json")
            if directive.envelope is not None
            else None
        ),
        "raise_transport_error": directive.raise_transport_error,
        "wait_for_cancellation": directive.wait_for_cancellation,
        "resist_initial_cancellation": directive.resist_initial_cancellation,
        "completion_integrity": directive.completion_integrity,
        "resource_integrity": directive.resource_integrity,
        "retention_integrity": directive.retention_integrity,
        "final_receipt_integrity": directive.final_receipt_integrity,
    }


def _transport_construction_fingerprint(
    profiles: Tuple[CannedImplementationProfile, ...],
    guarantees: _ImplementationGuarantees,
    capabilities: AcquisitionCapabilitySnapshot,
    script: Tuple[CannedTransportDirective, ...],
) -> str:
    return _sha256(
        _canonical_bytes(
            {
                "implementation_profiles": tuple(item.value for item in profiles),
                "guarantees": _guarantee_seal_payload(guarantees),
                "capabilities": capabilities.model_dump(mode="json"),
                "script": tuple(_directive_seal_payload(item) for item in script),
            }
        )
    )


class CannedAcquisitionTransport:
    """In-process ordered transport with class-owned operational guarantees."""

    implementation_id = CANNED_TRANSPORT_IMPLEMENTATION_ID

    def __setattr__(self, name: str, value: object) -> None:
        try:
            sealed = object.__getattribute__(self, "_sealed")
        except AttributeError:
            sealed = False
        if sealed:
            raise AttributeError("canned acquisition transport construction is sealed")
        object.__setattr__(self, name, value)

    def __init__(
        self,
        script: Sequence[Union[CannedTransportEnvelope, CannedTransportDirective]],
        *,
        provider_id: str,
        adapter_id: str,
        adapter_version: str,
        adapter_revision_digest: str,
        requested_model_id: str,
        seed_status: AcquisitionSeedStatus,
        implementation_profile: ImplementationProfileInput = CannedImplementationProfile.SAFE,
    ) -> None:
        if type(script) not in (list, tuple):
            raise TypeError("canned transport script must be an exact list or tuple")
        if len(script) == 0:
            raise ValueError("canned transport script must not be empty")
        object.__setattr__(self, "_sealed", False)
        self.implementation_profiles = _normalize_profiles(implementation_profile)
        self.implementation_profile = (
            self.implementation_profiles[0]
            if len(self.implementation_profiles) == 1
            else self.implementation_profiles
        )
        self.guarantees = _profile_guarantees(self.implementation_profiles)
        self.capabilities = build_canned_capability_snapshot(
            provider_id,
            adapter_id,
            adapter_version,
            adapter_revision_digest,
            requested_model_id,
            seed_status=seed_status,
            implementation_profile=implementation_profile,
        )
        directives = []
        for item in script:
            if type(item) is CannedTransportDirective:
                directives.append(item)
            elif type(item) is CannedTransportEnvelope:
                directives.append(CannedTransportDirective(envelope=item))
            else:
                raise TypeError(
                    "script entries must be CannedTransportEnvelope or CannedTransportDirective"
                )
        self._script = tuple(directives)
        self._ledger = _CounterLedger()
        self._records: list[CannedInvocationRecord] = []
        self._construction_fingerprint = _transport_construction_fingerprint(
            self.implementation_profiles,
            self.guarantees,
            self.capabilities,
            self._script,
        )
        object.__setattr__(self, "_sealed", True)
        _register_canned_transport_seal(self)

    @property
    def invocation_count(self) -> int:
        return self._ledger.canned_transport_invocations

    @property
    def invocation_records(self) -> Tuple[CannedInvocationRecord, ...]:
        return tuple(self._records)

    @property
    def runtime_counters(self) -> AcquisitionRuntimeCounters:
        return self._ledger.snapshot()

    def record_guard_check(self) -> None:
        self._ledger.record_guard_check()

    async def acquire(
        self,
        provider_visible_body: bytes,
        attempt: AcquisitionTransportAttempt,
    ) -> CannedTransportEnvelope:
        """Enter exactly once, then consume exactly one immutable script entry."""

        ledger = object.__getattribute__(self, "_ledger")
        script = object.__getattribute__(self, "_script")
        records = object.__getattribute__(self, "_records")
        ordinal = _SEALED_LEDGER_ENTER_TRANSPORT(ledger)
        digest = _sha256(provider_visible_body)
        if ordinal > len(script):
            records.append(
                CannedInvocationRecord(
                    ordinal=ordinal,
                    transport_attempt_id=attempt.transport_attempt_id or "",
                    provider_visible_sha256=digest,
                    provider_visible_length=len(provider_visible_body),
                    outcome=CannedInvocationOutcome.SCRIPT_EXHAUSTED,
                    cancellation_acknowledged=False,
                    worker_terminated=True,
                    completion_integrity=False,
                    resource_integrity=True,
                    retention_integrity=True,
                    final_receipt_integrity=True,
                )
            )
            raise CannedTransportExhausted("canned transport script exhausted")

        directive = script[ordinal - 1]
        common = {
            "ordinal": ordinal,
            "transport_attempt_id": attempt.transport_attempt_id or "",
            "provider_visible_sha256": digest,
            "provider_visible_length": len(provider_visible_body),
            "completion_integrity": directive.completion_integrity,
            "resource_integrity": directive.resource_integrity,
            "retention_integrity": directive.retention_integrity,
            "final_receipt_integrity": directive.final_receipt_integrity,
        }
        if directive.envelope is not None:
            records.append(
                CannedInvocationRecord(
                    **common,
                    outcome=CannedInvocationOutcome.RETURNED,
                    cancellation_acknowledged=False,
                    worker_terminated=True,
                )
            )
            return directive.envelope
        if directive.raise_transport_error:
            records.append(
                CannedInvocationRecord(
                    **common,
                    outcome=CannedInvocationOutcome.RAISED,
                    cancellation_acknowledged=False,
                    worker_terminated=True,
                )
            )
            raise CannedTransportFailure("canned transport injected an opaque error")

        blocker = asyncio.Event()
        cancellation_requests = 0
        while True:
            try:
                await blocker.wait()
            except asyncio.CancelledError:
                cancellation_requests += 1
                if (
                    directive.resist_initial_cancellation
                    and cancellation_requests == 1
                ):
                    continue
                records.append(
                    CannedInvocationRecord(
                        **common,
                        outcome=(
                            CannedInvocationOutcome.FORCED_CLEANUP
                            if cancellation_requests > 1
                            else CannedInvocationOutcome.CANCELLED
                        ),
                        cancellation_acknowledged=True,
                        worker_terminated=True,
                        cancellation_requests=cancellation_requests,
                        forced_cleanup=cancellation_requests > 1,
                    )
                )
                raise
        raise AssertionError("unreachable canned cancellation outcome")


_SEALED_CANNED_ACQUIRE = CannedAcquisitionTransport.__dict__["acquire"]
_SEALED_CANNED_SETATTR = CannedAcquisitionTransport.__dict__["__setattr__"]
_SEALED_CANNED_INVOCATION_COUNT = CannedAcquisitionTransport.__dict__["invocation_count"]
_SEALED_CANNED_INVOCATION_RECORDS = CannedAcquisitionTransport.__dict__["invocation_records"]
_SEALED_CANNED_RUNTIME_COUNTERS = CannedAcquisitionTransport.__dict__["runtime_counters"]
_SEALED_CANNED_RECORD_GUARD_CHECK = CannedAcquisitionTransport.__dict__["record_guard_check"]
_CANNED_TRANSPORT_INSTANCE_KEYS = frozenset(
    {
        "_construction_fingerprint",
        "_ledger",
        "_records",
        "_script",
        "_sealed",
        "capabilities",
        "guarantees",
        "implementation_profile",
        "implementation_profiles",
    }
)
_DIRECTIVE_BOOLEAN_FIELDS = _DIRECTIVE_BOOLEAN_FIELDS_V0


@dataclass(frozen=True)
class _CannedTransportExternalSeal:
    transport_ref: weakref.ReferenceType[CannedAcquisitionTransport]
    construction_fingerprint: str
    profiles_identity: int
    guarantees_identity: int
    capabilities_identity: int
    script_identity: int
    ledger_identity: int
    records_identity: int


_CANNED_TRANSPORT_SEAL_REGISTRY: dict[int, _CannedTransportExternalSeal] = {}


def _register_canned_transport_seal(transport: CannedAcquisitionTransport) -> None:
    state = object.__getattribute__(transport, "__dict__")
    _CANNED_TRANSPORT_SEAL_REGISTRY[id(transport)] = _CannedTransportExternalSeal(
        transport_ref=weakref.ref(transport),
        construction_fingerprint=state["_construction_fingerprint"],
        profiles_identity=id(state["implementation_profiles"]),
        guarantees_identity=id(state["guarantees"]),
        capabilities_identity=id(state["capabilities"]),
        script_identity=id(state["_script"]),
        ledger_identity=id(state["_ledger"]),
        records_identity=id(state["_records"]),
    )


def _sealed_canned_transport_state_is_valid(
    transport: CannedAcquisitionTransport,
) -> bool:
    """Validate exact constructor-owned state without virtual instance dispatch."""

    try:
        class_state = CannedAcquisitionTransport.__dict__
        if any(
            (
                class_state.get("acquire") is not _SEALED_CANNED_ACQUIRE,
                class_state.get("__setattr__") is not _SEALED_CANNED_SETATTR,
                class_state.get("invocation_count")
                is not _SEALED_CANNED_INVOCATION_COUNT,
                class_state.get("invocation_records")
                is not _SEALED_CANNED_INVOCATION_RECORDS,
                class_state.get("runtime_counters")
                is not _SEALED_CANNED_RUNTIME_COUNTERS,
                class_state.get("record_guard_check")
                is not _SEALED_CANNED_RECORD_GUARD_CHECK,
                class_state.get("implementation_id")
                != CANNED_TRANSPORT_IMPLEMENTATION_ID,
            )
        ):
            return False

        state = object.__getattribute__(transport, "__dict__")
        if type(state) is not dict or frozenset(state) != _CANNED_TRANSPORT_INSTANCE_KEYS:
            return False
        if type(state["_sealed"]) is not bool or state["_sealed"] is not True:
            return False
        registered_seal = _CANNED_TRANSPORT_SEAL_REGISTRY.get(id(transport))
        if (
            registered_seal is None
            or registered_seal.transport_ref() is not transport
            or registered_seal.construction_fingerprint
            != state["_construction_fingerprint"]
            or registered_seal.profiles_identity
            != id(state["implementation_profiles"])
            or registered_seal.guarantees_identity != id(state["guarantees"])
            or registered_seal.capabilities_identity != id(state["capabilities"])
            or registered_seal.script_identity != id(state["_script"])
            or registered_seal.ledger_identity != id(state["_ledger"])
            or registered_seal.records_identity != id(state["_records"])
        ):
            return False

        profiles = state["implementation_profiles"]
        if (
            type(profiles) is not tuple
            or not profiles
            or any(type(item) is not CannedImplementationProfile for item in profiles)
            or profiles != tuple(sorted(set(profiles), key=lambda item: item.value))
        ):
            return False
        expected_profile: object = profiles[0] if len(profiles) == 1 else profiles
        profile = state["implementation_profile"]
        if type(profile) not in (CannedImplementationProfile, tuple):
            return False
        if profile != expected_profile:
            return False

        guarantees = state["guarantees"]
        if type(guarantees) is not _ImplementationGuarantees:
            return False
        guarantee_payload = _guarantee_seal_payload(guarantees)
        if any(type(value) is not bool for key, value in guarantee_payload.items() if key != "control_state_overrides"):
            return False
        overrides = guarantees.control_state_overrides
        if type(overrides) is not tuple or any(
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not AcquisitionControlName
            or type(item[1]) is not AcquisitionControlState
            for item in overrides
        ):
            return False
        if guarantees != _profile_guarantees(profiles):
            return False

        capabilities = state["capabilities"]
        if (
            type(capabilities) is not AcquisitionCapabilitySnapshot
            or not _contract_roundtrip(capabilities)
        ):
            return False

        script = state["_script"]
        if type(script) is not tuple or not script:
            return False
        for directive in script:
            if type(directive) is not CannedTransportDirective:
                return False
            directive_state = object.__getattribute__(directive, "__dict__")
            if type(directive_state) is not dict:
                return False
            if any(
                type(directive_state.get(field)) is not bool
                for field in _DIRECTIVE_BOOLEAN_FIELDS
            ):
                return False
            envelope = directive_state.get("envelope")
            if envelope is not None and (
                type(envelope) is not CannedTransportEnvelope
                or not (
                    _contract_roundtrip(envelope)
                    or _known_false_zero_envelope_injection_is_valid(envelope)
                )
            ):
                return False
            selected = int(envelope is not None)
            selected += int(directive_state["raise_transport_error"])
            selected += int(directive_state["wait_for_cancellation"])
            if selected != 1:
                return False
            if (
                directive_state["resist_initial_cancellation"]
                and not directive_state["wait_for_cancellation"]
            ):
                return False

        ledger = state["_ledger"]
        if type(ledger) is not _CounterLedger:
            return False
        ledger_class_state = _CounterLedger.__dict__
        if any(
            (
                ledger_class_state.get("enter_transport")
                is not _SEALED_LEDGER_ENTER_TRANSPORT,
                ledger_class_state.get("record_guard_check")
                is not _SEALED_LEDGER_RECORD_GUARD_CHECK,
                ledger_class_state.get("snapshot") is not _SEALED_LEDGER_SNAPSHOT,
            )
        ):
            return False
        ledger_state = object.__getattribute__(ledger, "__dict__")
        if type(ledger_state) is not dict or frozenset(ledger_state) != frozenset(
            {"canned_transport_invocations", "evaluator_guard_checks"}
        ):
            return False
        if any(type(value) is not int or value < 0 for value in ledger_state.values()):
            return False

        records = state["_records"]
        if type(records) is not list or any(
            type(record) is not CannedInvocationRecord for record in records
        ):
            return False
        if (
            ledger_state["canned_transport_invocations"] != 0
            or ledger_state["evaluator_guard_checks"] != 0
            or records
        ):
            return False

        fingerprint = state["_construction_fingerprint"]
        if type(fingerprint) is not str or not _is_hex_digest(fingerprint):
            return False
        return fingerprint == _transport_construction_fingerprint(
            profiles,
            guarantees,
            capabilities,
            script,
        )
    except Exception:
        return False


@dataclass(frozen=True)
class IsolationSubjectSnapshot:
    subject_id: str
    runtime_digest: str

    def __post_init__(self) -> None:
        if not self.subject_id.strip():
            raise ValueError("isolation subject_id must not be blank")
        if not _is_hex_digest(self.runtime_digest):
            raise ValueError("isolation runtime_digest must be lowercase SHA-256")


@dataclass(frozen=True)
class AcquisitionIsolationSnapshot:
    source: IsolationSubjectSnapshot
    sibling: IsolationSubjectSnapshot
    production: IsolationSubjectSnapshot
    preconditions_met: bool = True
    diagnostic_mismatches: Tuple[str, ...] = ()


class IsolationProbe(Protocol):
    def __call__(self) -> Union[AcquisitionIsolationSnapshot, Mapping[str, object]]: ...


def _placeholder_isolation_snapshot(diagnostic: str) -> AcquisitionIsolationSnapshot:
    def subject(scope: str) -> IsolationSubjectSnapshot:
        digest = _sha256(_canonical_bytes({"scope": scope, "diagnostic": diagnostic}))
        return IsolationSubjectSnapshot(f"unavailable-{scope}", digest)

    return AcquisitionIsolationSnapshot(
        source=subject("source"),
        sibling=subject("sibling"),
        production=subject("production"),
        preconditions_met=False,
        diagnostic_mismatches=(diagnostic,),
    )


def _coerce_subject(scope: str, value: object) -> IsolationSubjectSnapshot:
    if isinstance(value, IsolationSubjectSnapshot):
        return value
    if isinstance(value, str):
        return IsolationSubjectSnapshot(f"{scope}-subject", value)
    if isinstance(value, Mapping):
        return IsolationSubjectSnapshot(
            str(value["subject_id"]),
            str(value.get("runtime_digest", value.get("digest"))),
        )
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return IsolationSubjectSnapshot(str(value[0]), str(value[1]))
    raise ValueError(f"invalid {scope} isolation subject")


def _capture_isolation(probe: IsolationProbe) -> AcquisitionIsolationSnapshot:
    try:
        value = probe()
        if isinstance(value, AcquisitionIsolationSnapshot):
            return value
        if not isinstance(value, Mapping):
            raise ValueError("isolation probe must return a snapshot or mapping")
        diagnostics = tuple(str(item) for item in value.get("diagnostic_mismatches", ()))
        return AcquisitionIsolationSnapshot(
            source=_coerce_subject("source", value["source"]),
            sibling=_coerce_subject("sibling", value["sibling"]),
            production=_coerce_subject("production", value["production"]),
            preconditions_met=bool(value.get("preconditions_met", True)),
            diagnostic_mismatches=diagnostics,
        )
    except Exception as exc:
        return _placeholder_isolation_snapshot(
            f"isolation_probe_error:{type(exc).__name__}"
        )


def _subject_fingerprint(subject: IsolationSubjectSnapshot) -> str:
    return _sha256(
        _canonical_bytes(
            {"subject_id": subject.subject_id, "runtime_digest": subject.runtime_digest}
        )
    )


def _build_isolation_receipt(
    request: AcquisitionSemanticRequest,
    attempt: AcquisitionTransportAttempt,
    before: AcquisitionIsolationSnapshot,
    after: AcquisitionIsolationSnapshot,
) -> AcquisitionIsolationReceipt:
    rows = []
    for scope, before_subject, after_subject in (
        (AcquisitionIsolationScope.SOURCE, before.source, after.source),
        (AcquisitionIsolationScope.SIBLING, before.sibling, after.sibling),
        (AcquisitionIsolationScope.PRODUCTION, before.production, after.production),
    ):
        rows.append(
            AcquisitionIsolationFingerprint(
                scope=scope,
                subject_id=before_subject.subject_id,
                before_digest=_subject_fingerprint(before_subject),
                after_digest=_subject_fingerprint(after_subject),
            )
        )
    return AcquisitionIsolationReceipt(
        semantic_request_id=request.semantic_request_id or "",
        transport_attempt_id=attempt.transport_attempt_id or "",
        fingerprints=tuple(rows),
    )


def _alternate_artifact_policy(
    expected: AcquisitionArtifactInclusionPolicy,
) -> AcquisitionArtifactInclusionPolicy:
    return next(item for item in AcquisitionArtifactInclusionPolicy if item is not expected)


def _build_retention_receipt(
    request: AcquisitionSemanticRequest,
    attempt: AcquisitionTransportAttempt,
    policy: AcquisitionRetentionPolicy,
    raw_response_bytes: Optional[bytes],
    *,
    integrity: bool,
    metadata_privacy_integrity: bool = True,
) -> AcquisitionRetentionReceipt:
    raw_digest = (
        _sha256(raw_response_bytes) if raw_response_bytes is not None else None
    )
    raw_length = len(raw_response_bytes) if raw_response_bytes is not None else None
    receipt_base64: Optional[str]
    response_reference: Optional[str]
    allowlisted_non_sensitive = (
        raw_digest is not None
        and raw_digest in policy.non_sensitive_raw_response_sha256_allowlist
        and metadata_privacy_integrity
    )
    if raw_response_bytes is None:
        receipt_base64 = None
        response_reference = None
    elif not allowlisted_non_sensitive:
        # Preserve only digest/length evidence when the bytes have not been
        # frozen as non-sensitive.  The receipt will fail closed below without
        # copying potentially sensitive material into any receipt or artifact.
        receipt_base64 = None
        response_reference = None
    elif policy.response_retention_mode is ResponseRetentionMode.RAW_BYTES_BASE64:
        raw = raw_response_bytes
        receipt_base64 = base64.b64encode(raw).decode("ascii")
        response_reference = None
    else:
        receipt_base64 = None
        response_reference = f"szacqraw_{raw_digest}"
    if not metadata_privacy_integrity or (
        raw_response_bytes is not None and not allowlisted_non_sensitive
    ):
        data_classification = AcquisitionDataClassification.UNKNOWN
        personal_private_data_present = True
        redaction_status = AcquisitionRedactionStatus.NOT_APPLIED
        artifact_policy = AcquisitionArtifactInclusionPolicy.EXCLUDE
    else:
        data_classification = AcquisitionDataClassification.NON_SENSITIVE_CANNED
        personal_private_data_present = False
        redaction_status = AcquisitionRedactionStatus.NOT_REQUIRED
        artifact_policy = (
            policy.artifact_inclusion_policy
            if integrity
            else _alternate_artifact_policy(policy.artifact_inclusion_policy)
        )
    visible = request.provider_visible_request
    return AcquisitionRetentionReceipt(
        policy=policy,
        retention_policy_id=policy.retention_policy_id or "",
        semantic_request_id=request.semantic_request_id or "",
        transport_attempt_id=attempt.transport_attempt_id or "",
        provider_visible_prompt_digest=visible.sha256 or "",
        provider_visible_prompt_length=visible.byte_length or 0,
        provider_visible_prompt_reference=visible.provider_visible_request_id or "",
        provider_visible_prompt_raw_retained=False,
        raw_response_digest=raw_digest,
        raw_response_length=raw_length,
        raw_response_base64=receipt_base64,
        content_addressed_response_reference=response_reference,
        data_classification=data_classification,
        credentials_inspected=False,
        credentials_retained=False,
        personal_private_data_present=personal_private_data_present,
        redaction_status=redaction_status,
        artifact_inclusion=artifact_policy,
    )


def _known(value: int) -> AcquisitionResourceQuantity:
    return AcquisitionResourceQuantity.known(value)


def _runtime_execution_usage(invocations: int) -> AcquisitionExecutionUsage:
    return AcquisitionExecutionUsage(
        canned_transport_invocations=_known(invocations),
        external_network_attempts=_known(0),
        credential_access_attempts=_known(0),
        live_provider_calls=_known(0),
        provider_sdk_calls=_known(0),
        model_executions=_known(0),
        tool_calls=_known(0),
        new_tokens=_known(0),
        new_cost_microusd=_known(0),
        external_provider_wall_time_ms=_known(0),
    )


@dataclass(frozen=True)
class _Failure:
    guard_id: AcquisitionGuardId
    code: AcquisitionFailureCode
    diagnostic: str


@dataclass(frozen=True)
class _TransportEvidence:
    invocation_count_before: int
    invocation_count_after: int
    envelope: Optional[CannedTransportEnvelope]
    record: Optional[CannedInvocationRecord]
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def invocation_delta(self) -> int:
        return self.invocation_count_after - self.invocation_count_before


@dataclass(frozen=True)
class _RunContext:
    request: AcquisitionSemanticRequest
    attempt: AcquisitionTransportAttempt
    policy: AcquisitionControlPolicy
    retention_policy: AcquisitionRetentionPolicy
    historical_usage: AcquisitionHistoricalUsage
    capability_snapshot: AcquisitionCapabilitySnapshot
    transport: CannedAcquisitionTransport
    provider_visible_body: bytes
    provider_visible_error: Optional[str]
    isolation_before: AcquisitionIsolationSnapshot
    transport_boundary_valid: bool = False


def _control_map(
    snapshot: AcquisitionCapabilitySnapshot,
) -> Mapping[AcquisitionControlName, AcquisitionControlEvidence]:
    return {item.name: item for item in snapshot.controls}


def _contract_roundtrip(value: Any) -> bool:
    try:
        return type(value).model_validate(value.model_dump(mode="python")) == value
    except Exception:
        return False


def _known_false_zero_envelope_injection_is_valid(
    envelope: CannedTransportEnvelope,
) -> bool:
    """Admit only the frozen UNKNOWN-with-zero adverse accounting injection."""

    try:
        usage = envelope.execution_usage
        if type(usage) is not AcquisitionExecutionUsage:
            return False
        quantity = usage.new_tokens
        if (
            type(quantity) is not AcquisitionResourceQuantity
            or quantity.knowledge is not ResourceKnowledgeState.UNKNOWN
            or type(quantity.value) is not int
            or quantity.value != 0
        ):
            return False
        repaired_usage_payload = usage.model_dump(mode="python")
        repaired_usage_payload["execution_usage_id"] = None
        repaired_usage_payload["new_tokens"] = (
            AcquisitionResourceQuantity.unknown().model_dump(mode="python")
        )
        repaired_usage = AcquisitionExecutionUsage.model_validate(
            repaired_usage_payload
        )
        repaired_envelope_payload = envelope.model_dump(mode="python")
        repaired_envelope_payload["execution_usage"] = repaired_usage
        repaired_envelope = CannedTransportEnvelope.model_validate(
            repaired_envelope_payload
        )
        return _contract_roundtrip(repaired_envelope)
    except Exception:
        return False


def _fail(
    guard: AcquisitionGuardId,
    code: AcquisitionFailureCode,
    diagnostic: str,
) -> _Failure:
    return _Failure(guard, code, diagnostic)


def _entropy_in_body(parsed: object, tokens: Tuple[str, ...]) -> bool:
    if isinstance(parsed, Mapping):
        for key, value in parsed.items():
            if _is_out_of_band_provider_key(key):
                return True
            if _entropy_in_body(value, tokens):
                return True
        return False
    if isinstance(parsed, (list, tuple)):
        return any(_entropy_in_body(value, tokens) for value in parsed)
    if isinstance(parsed, str):
        return any(token and token in parsed for token in tokens)
    return False


def _pre_guard_failure(guard: AcquisitionGuardId, ctx: _RunContext) -> Optional[_Failure]:
    request = ctx.request
    attempt = ctx.attempt
    policy = ctx.policy
    snapshot = ctx.capability_snapshot
    transport = ctx.transport
    controls: Mapping[AcquisitionControlName, AcquisitionControlEvidence] = {}
    guarantees: Optional[_ImplementationGuarantees] = None
    if guard not in (
        AcquisitionGuardId.P01_REQUEST_INTEGRITY,
        AcquisitionGuardId.P02_SEMANTIC_IDENTITY_INTEGRITY,
        AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY,
    ):
        if not ctx.transport_boundary_valid:
            raise AcquisitionRuntimeError("transport state used before P03 sealing")
        controls = _control_map(snapshot)
        guarantees = object.__getattribute__(transport, "guarantees")

    if guard is AcquisitionGuardId.P01_REQUEST_INTEGRITY:
        if not all(
            (
                isinstance(request, AcquisitionSemanticRequest),
                isinstance(attempt, AcquisitionTransportAttempt),
                isinstance(policy, AcquisitionControlPolicy),
                isinstance(ctx.retention_policy, AcquisitionRetentionPolicy),
                isinstance(ctx.historical_usage, AcquisitionHistoricalUsage),
                request.schema_version == ACQUISITION_SEMANTIC_REQUEST_SCHEMA_VERSION,
                request.acquisition_contract_id == ACQUISITION_CONTRACT_ID,
                request.control_policy_id == policy.control_policy_id,
                request.action_id in request.complete_legal_action_ids,
                request.request_configuration.temperature == policy.temperature,
                request.request_configuration.seed == policy.seed,
                request.request_configuration.max_output_tokens
                == policy.max_output_tokens,
                request.request_configuration.timeout_ms == policy.timeout_ms,
                request.request_configuration.fallback_allowed
                == policy.fallback_allowed,
                request.request_configuration.explicit_retry_limit
                == policy.explicit_retry_limit,
                request.request_configuration.adapter_retry_limit
                == policy.adapter_retry_limit,
                request.request_configuration.sdk_internal_retry_limit
                == policy.sdk_internal_retry_limit,
                request.request_configuration.hidden_transport_retry_limit
                == policy.hidden_transport_retry_limit,
                request.request_configuration.tools_allowed
                == policy.tools_allowed,
            )
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.INVALID_ACQUISITION_REQUEST,
                "request_or_link_integrity",
            )

    elif guard is AcquisitionGuardId.P02_SEMANTIC_IDENTITY_INTEGRITY:
        if (
            not _contract_roundtrip(request)
            or not _contract_roundtrip(attempt)
            or attempt.semantic_request_id != request.semantic_request_id
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.INVALID_SEMANTIC_IDENTITY,
                "semantic_identity_roundtrip",
            )
        identities = (
            request.semantic_request_id,
            attempt.transport_attempt_id,
            request.provider_visible_request.provider_visible_request_id,
        )
        if None in identities or len(set(identities)) != len(identities):
            return _fail(
                guard,
                AcquisitionFailureCode.IDENTITY_COLLISION,
                "semantic_transport_visible_identity_collision",
            )

    elif guard is AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY:
        if (
            not ctx.transport_boundary_valid
            or not _contract_roundtrip(snapshot)
            or snapshot != object.__getattribute__(transport, "capabilities")
            or request.capability_snapshot_id != snapshot.capability_snapshot_id
            or snapshot.provider_id != request.requested_binding.provider_id
            or snapshot.requested_model_id != request.requested_binding.model_id
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT,
                "capability_snapshot_binding",
            )

    elif guard is AcquisitionGuardId.P04_REQUIRED_CONTROL_COMPLETENESS:
        assert guarantees is not None
        effective_overrides = dict(guarantees.control_state_overrides)
        for requirement in policy.requirements:
            evidence = controls.get(requirement.name)
            effective_state = (
                effective_overrides.get(requirement.name)
                if evidence is not None
                else None
            )
            if effective_state is None and evidence is not None:
                effective_state = evidence.state
            if (
                effective_state is None
                or effective_state is AcquisitionControlState.UNKNOWN
            ):
                return _fail(
                    guard,
                    AcquisitionFailureCode.REQUIRED_CONTROL_UNKNOWN,
                    f"required_control:{requirement.name.value}",
                )

    elif guard is AcquisitionGuardId.P05_CANNED_ONLY_TRANSPORT_MODE:
        assert guarantees is not None
        if (
            policy.transport_mode is not AcquisitionTransportMode.CANNED_ONLY
            or snapshot.transport_mode is not AcquisitionTransportMode.CANNED_ONLY
            or controls[AcquisitionControlName.CANNED_ONLY_TRANSPORT].state
            is not AcquisitionControlState.PROVEN_SUPPORTED
            or not guarantees.canned_only
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.CANNED_ONLY_POLICY_VIOLATION,
                "canned_only_transport_unproven",
            )

    elif guard is AcquisitionGuardId.P06_EXTERNAL_NETWORK_PROHIBITION:
        assert guarantees is not None
        evidence = controls[AcquisitionControlName.EXTERNAL_NETWORK]
        runtime_counters = _SEALED_LEDGER_SNAPSHOT(
            object.__getattribute__(transport, "_ledger")
        )
        if (
            evidence.state is not AcquisitionControlState.PROVEN_DISABLED
            or not guarantees.network_prohibited
            or runtime_counters.external_network_attempts != 0
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.EXTERNAL_NETWORK_FORBIDDEN,
                "external_network_prohibition",
            )

    elif guard is AcquisitionGuardId.P07_CREDENTIAL_ACCESS_PROHIBITION:
        assert guarantees is not None
        evidence = controls[AcquisitionControlName.CREDENTIAL_ACCESS]
        runtime_counters = _SEALED_LEDGER_SNAPSHOT(
            object.__getattribute__(transport, "_ledger")
        )
        if (
            evidence.state is not AcquisitionControlState.PROVEN_DISABLED
            or not guarantees.credentials_prohibited
            or runtime_counters.credential_reads != 0
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.CREDENTIAL_ACCESS_FORBIDDEN,
                "credential_access_prohibition",
            )

    elif guard is AcquisitionGuardId.P08_EXACT_IDENTITY_VERIFICATION:
        assert guarantees is not None
        required = (
            AcquisitionControlName.ACTUAL_PROVIDER_IDENTITY_VALIDATION,
            AcquisitionControlName.ACTUAL_MODEL_IDENTITY_VALIDATION,
            AcquisitionControlName.ACTUAL_CONFIGURATION_IDENTITY_VALIDATION,
        )
        if not guarantees.exact_identity_verification or any(
            controls[name].state is not AcquisitionControlState.PROVEN_SUPPORTED
            for name in required
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.EXACT_IDENTITY_VERIFICATION_UNAVAILABLE,
                "exact_identity_verification_unavailable",
            )

    elif guard is AcquisitionGuardId.P09_FALLBACK_DISABLED:
        assert guarantees is not None
        if (
            policy.fallback_allowed
            or controls[AcquisitionControlName.FALLBACK].state
            is not AcquisitionControlState.PROVEN_DISABLED
            or not guarantees.fallback_disabled
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.FALLBACK_CONTROL_UNPROVEN,
                "fallback_disable_unproven",
            )

    elif guard is AcquisitionGuardId.P10_RETRY_DISABLED:
        assert guarantees is not None
        if (
            policy.explicit_retry_limit != 0
            or policy.adapter_retry_limit != 0
            or controls[AcquisitionControlName.EXPLICIT_RETRY].state
            is not AcquisitionControlState.PROVEN_DISABLED
            or controls[AcquisitionControlName.ADAPTER_RETRY].state
            is not AcquisitionControlState.PROVEN_DISABLED
            or not guarantees.explicit_and_adapter_retries_disabled
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.RETRY_CONTROL_UNPROVEN,
                "explicit_or_adapter_retry_unproven",
            )

    elif guard is AcquisitionGuardId.P11_SDK_INTERNAL_RETRY_DISABLED:
        assert guarantees is not None
        if (
            policy.sdk_internal_retry_limit != 0
            or policy.hidden_transport_retry_limit != 0
            or controls[AcquisitionControlName.SDK_INTERNAL_RETRY].state
            is not AcquisitionControlState.PROVEN_DISABLED
            or controls[AcquisitionControlName.HIDDEN_TRANSPORT_RETRY].state
            is not AcquisitionControlState.PROVEN_DISABLED
            or not guarantees.sdk_and_hidden_retries_disabled
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.SDK_INTERNAL_RETRY_CONTROL_UNPROVEN,
                "sdk_or_hidden_retry_unproven",
            )

    elif guard is AcquisitionGuardId.P12_TOOLS_DISABLED:
        assert guarantees is not None
        if (
            policy.tools_allowed
            or policy.budget.max_tool_calls != 0
            or controls[AcquisitionControlName.TOOLS].state
            is not AcquisitionControlState.PROVEN_DISABLED
            or not guarantees.tools_disabled
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.TOOLS_NOT_DISABLED,
                "tools_disable_unproven",
            )

    elif guard is AcquisitionGuardId.P13_TIMEOUT_WORKER_TERMINATION:
        assert guarantees is not None
        if (
            policy.timeout_ms <= 0
            or controls[AcquisitionControlName.TIMEOUT].state
            is not AcquisitionControlState.PROVEN_SUPPORTED
            or controls[AcquisitionControlName.TIMEOUT_WORKER_TERMINATION].state
            is not AcquisitionControlState.PROVEN_SUPPORTED
            or not guarantees.hard_cancellation
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.TIMEOUT_CANCELLATION_UNPROVEN,
                "timeout_worker_termination_unproven",
            )

    elif guard is AcquisitionGuardId.P14_RESOURCE_ACCOUNTING:
        assert guarantees is not None
        accounting_controls = (
            AcquisitionControlName.RAW_RESPONSE_CAPTURE,
            AcquisitionControlName.NEW_USAGE_ACCOUNTING,
            AcquisitionControlName.TOKEN_REPORTING,
            AcquisitionControlName.COST_REPORTING,
            AcquisitionControlName.EXTERNAL_WALL_TIME_REPORTING,
        )
        if (
            not guarantees.complete_accounting
            or not _contract_roundtrip(ctx.historical_usage)
            or any(
                controls[name].state is not AcquisitionControlState.PROVEN_SUPPORTED
                for name in accounting_controls
            )
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.RESOURCE_ACCOUNTING_INCOMPLETE,
                "resource_accounting_unproven",
            )

    elif guard is AcquisitionGuardId.P15_BUDGET_SUFFICIENCY:
        assert guarantees is not None
        budget = policy.budget
        if (
            not guarantees.budget_reservation
            or budget.max_canned_transport_invocations < 1
            or any(
                (
                    budget.max_external_network_attempts,
                    budget.max_credential_access_attempts,
                    budget.max_live_provider_calls,
                    budget.max_provider_sdk_calls,
                    budget.max_model_executions,
                    budget.max_tool_calls,
                    budget.max_new_tokens,
                    budget.max_new_cost_microusd,
                    budget.max_external_provider_wall_time_ms,
                )
            )
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.BUDGET_INCOMPLETE,
                "budget_reservation_or_zero_limits",
            )

    elif guard is AcquisitionGuardId.P16_PROMPT_BYTE_DETERMINISM:
        visible = request.provider_visible_request
        configuration = request.request_configuration
        try:
            parsed = json.loads(visible.canonical_request_json)
        except Exception:
            parsed = None
        if isinstance(parsed, Mapping):
            visible_controls_match = all(
                (
                    parsed.get("temperature") == configuration.temperature,
                    parsed.get("max_output_tokens")
                    == configuration.max_output_tokens,
                    parsed.get("tools") == [],
                    (
                        "seed" not in parsed
                        if configuration.seed.status
                        is AcquisitionSeedStatus.UNSUPPORTED
                        else parsed.get("seed") == configuration.seed.value
                    ),
                )
            )
        else:
            visible_controls_match = False
        entropy_tokens = tuple(
            item
            for item in (
                attempt.branch_id,
                attempt.experiment_id,
                attempt.transport_attempt_id or "",
                attempt.canned_transport_id,
            )
            if item
        )
        if (
            ctx.provider_visible_error is not None
            or controls[AcquisitionControlName.PROMPT_BYTE_DETERMINISM].state
            is not AcquisitionControlState.PROVEN_SUPPORTED
            or controls[AcquisitionControlName.TRANSPORT_METADATA_ISOLATION].state
            is not AcquisitionControlState.PROVEN_SUPPORTED
            or visible.rendering_version != PROVIDER_VISIBLE_RENDERER_VERSION
            or visible.sha256 != _sha256(ctx.provider_visible_body)
            or visible.byte_length != len(ctx.provider_visible_body)
            or request.request_configuration.provider_visible_metadata_digest
            != visible.sha256
            or parsed is None
            or not visible_controls_match
            or _entropy_in_body(parsed, entropy_tokens)
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.PROMPT_ENTROPY_DETECTED,
                "provider_visible_bytes_or_transport_entropy",
            )

    elif guard is AcquisitionGuardId.P17_ISOLATION_PRECONDITIONS:
        before = ctx.isolation_before
        subject_ids = (
            before.source.subject_id,
            before.sibling.subject_id,
            before.production.subject_id,
        )
        if (
            not before.preconditions_met
            or before.diagnostic_mismatches
            or len(set(subject_ids)) != 3
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.ISOLATION_PRECONDITION_FAILED,
                "isolation_preconditions",
            )

    elif guard is AcquisitionGuardId.P18_CANNED_TRANSPORT_REGISTRATION:
        assert guarantees is not None
        if (
            attempt.canned_transport_id != CANNED_TRANSPORT_ID
            or attempt.canned_transport_id
            not in snapshot.registered_canned_transport_ids
            or CANNED_TRANSPORT_IMPLEMENTATION_ID != attempt.canned_transport_id
            or not guarantees.registered
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.CANNED_TRANSPORT_UNREGISTERED,
                "canned_transport_registration",
            )
    return None


async def _invoke_transport(
    transport: CannedAcquisitionTransport,
    body: bytes,
    attempt: AcquisitionTransportAttempt,
    timeout_ms: int,
) -> _TransportEvidence:
    ledger = object.__getattribute__(transport, "_ledger")
    records = object.__getattribute__(transport, "_records")
    before = ledger.canned_transport_invocations
    envelope: Optional[CannedTransportEnvelope] = None
    timed_out = False
    error: Optional[str] = None
    task = asyncio.create_task(
        _SEALED_CANNED_ACQUIRE(transport, body, attempt),
        name=f"socrates-zero-canned-acquisition-{before + 1}",
    )

    async def terminate_task() -> None:
        for _cleanup_round in range(CANNED_TIMEOUT_CLEANUP_ROUNDS):
            task.cancel()
            done, _pending = await asyncio.wait(
                (task,),
                timeout=CANNED_TIMEOUT_CLEANUP_GRACE_SECONDS,
            )
            if done:
                try:
                    task.result()
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
                return
        raise AcquisitionRuntimeError(
            "timed-out canned task resisted deterministic forced cleanup"
        )

    try:
        done, _pending = await asyncio.wait(
            (task,), timeout=timeout_ms / 1000.0
        )
        if not done:
            timed_out = True
            await terminate_task()
        else:
            try:
                envelope = task.result()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = type(exc).__name__
    except asyncio.CancelledError:
        if not task.done():
            await terminate_task()
        raise
    frozen_records = tuple(records)
    return _TransportEvidence(
        invocation_count_before=before,
        invocation_count_after=ledger.canned_transport_invocations,
        envelope=envelope,
        record=frozen_records[-1] if len(frozen_records) > before else None,
        timed_out=timed_out,
        error=error,
    )


def _all_usage_known(usage: AcquisitionExecutionUsage) -> bool:
    return usage.complete


def _usage_values(usage: AcquisitionExecutionUsage) -> Mapping[str, Optional[int]]:
    return {
        name: getattr(usage, name).value
        for name in usage._MEASURE_FIELDS
    }


def _usage_within_budget(
    usage: AcquisitionExecutionUsage,
    policy: AcquisitionControlPolicy,
) -> bool:
    if not usage.complete:
        return False
    values = _usage_values(usage)
    budget = policy.budget
    return all(
        (
            (values["canned_transport_invocations"] or 0)
            <= budget.max_canned_transport_invocations,
            (values["external_network_attempts"] or 0)
            <= budget.max_external_network_attempts,
            (values["credential_access_attempts"] or 0)
            <= budget.max_credential_access_attempts,
            (values["live_provider_calls"] or 0) <= budget.max_live_provider_calls,
            (values["provider_sdk_calls"] or 0) <= budget.max_provider_sdk_calls,
            (values["model_executions"] or 0) <= budget.max_model_executions,
            (values["tool_calls"] or 0) <= budget.max_tool_calls,
            (values["new_tokens"] or 0) <= budget.max_new_tokens,
            (values["new_cost_microusd"] or 0) <= budget.max_new_cost_microusd,
            (values["external_provider_wall_time_ms"] or 0)
            <= budget.max_external_provider_wall_time_ms,
        )
    )


def _post_guard_failure(
    guard: AcquisitionGuardId,
    ctx: _RunContext,
    evidence: _TransportEvidence,
    execution_usage: AcquisitionExecutionUsage,
    isolation_receipt: AcquisitionIsolationReceipt,
    retention_receipt: AcquisitionRetentionReceipt,
    observation: Optional[UnadmittedAcquiredObservation],
) -> Optional[_Failure]:
    envelope = evidence.envelope
    record = evidence.record

    if guard is AcquisitionGuardId.A01_CANNED_INVOCATION_COUNT:
        reported = envelope.canned_transport_invocations if envelope is not None else None
        if (
            evidence.invocation_delta != 1
            or record is None
            or record.ordinal != evidence.invocation_count_after
            or (envelope is not None and reported != 1)
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.UNCOUNTED_CANNED_INVOCATION,
                "canned_invocation_count",
            )

    elif guard is AcquisitionGuardId.A02_TRANSPORT_COMPLETION:
        if evidence.timed_out:
            return _fail(
                guard,
                AcquisitionFailureCode.TRANSPORT_TIMEOUT,
                "transport_timeout",
            )
        if (
            evidence.error is not None
            or envelope is None
            or record is None
            or not record.completion_integrity
            or envelope.transport_attempt_id != ctx.attempt.transport_attempt_id
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.TRANSPORT_ERROR,
                "transport_error_or_forbidden_future_label",
            )
        if envelope.transport_status is not AcquisitionTransportStatus.DELIVERED:
            code = (
                AcquisitionFailureCode.TRANSPORT_TIMEOUT
                if envelope.transport_status is AcquisitionTransportStatus.TIMEOUT
                else AcquisitionFailureCode.TRANSPORT_ERROR
            )
            return _fail(guard, code, f"transport_status:{envelope.transport_status.value}")

    elif guard is AcquisitionGuardId.A03_TIMEOUT_WORKER_TERMINATION:
        if (
            envelope is None
            or envelope.timeout_fired is None
            or envelope.cancellation_requested is None
            or envelope.worker_terminated is not True
            or record is None
            or not record.worker_terminated
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.TRANSPORT_WORKER_NOT_TERMINATED,
                "timeout_worker_termination",
            )

    elif guard is AcquisitionGuardId.A04_ACTUAL_PROVIDER_IDENTITY:
        if (
            envelope is None
            or envelope.actual_provider_id is None
            or envelope.actual_provider_id != ctx.request.requested_binding.provider_id
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.ACTUAL_PROVIDER_MISMATCH,
                "actual_provider_identity",
            )

    elif guard is AcquisitionGuardId.A05_ACTUAL_MODEL_IDENTITY:
        if (
            envelope is None
            or envelope.actual_model_id is None
            or envelope.actual_model_id != ctx.request.requested_binding.model_id
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.ACTUAL_MODEL_MISMATCH,
                "actual_model_identity",
            )

    elif guard is AcquisitionGuardId.A06_ACTUAL_CONFIGURATION_IDENTITY:
        if (
            envelope is None
            or envelope.actual_configuration_digest is None
            or envelope.actual_configuration_digest
            != ctx.request.requested_binding.configuration_digest
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.ACTUAL_CONFIGURATION_MISMATCH,
                "actual_configuration_identity",
            )

    elif guard is AcquisitionGuardId.A07_FALLBACK_ACTIVATION:
        if envelope is None or envelope.fallback_used is not False:
            return _fail(
                guard,
                AcquisitionFailureCode.FALLBACK_ACTIVATED,
                "fallback_not_explicitly_zero",
            )

    elif guard is AcquisitionGuardId.A08_RETRY_ACTIVATION:
        counts = () if envelope is None else (
            envelope.explicit_retry_count,
            envelope.adapter_retry_count,
            envelope.sdk_internal_retry_count,
            envelope.hidden_transport_retry_count,
        )
        if counts != (0, 0, 0, 0):
            return _fail(
                guard,
                AcquisitionFailureCode.RETRY_ACTIVATED,
                "retry_count_not_explicitly_zero",
            )

    elif guard is AcquisitionGuardId.A09_TOOL_ACTIVATION:
        if envelope is None or envelope.tool_calls != 0:
            return _fail(
                guard,
                AcquisitionFailureCode.TOOL_ACTIVATED,
                "tool_count_not_explicitly_zero",
            )

    elif guard is AcquisitionGuardId.A10_RAW_RESPONSE_PRESENCE:
        if envelope is None or envelope.raw_response_base64 is None:
            return _fail(
                guard,
                AcquisitionFailureCode.MISSING_RAW_OBSERVATION,
                "missing_raw_response",
            )

    elif guard is AcquisitionGuardId.A11_RESPONSE_DIGEST_INTEGRITY:
        if (
            envelope is None
            or envelope.reported_raw_response_digest is None
            or envelope.reported_raw_response_digest
            != envelope.computed_raw_response_digest
            or envelope.reported_raw_response_length is None
            or envelope.reported_raw_response_length
            != envelope.computed_raw_response_length
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.INVALID_RESPONSE_DIGEST,
                "raw_response_digest_or_length",
            )

    elif guard is AcquisitionGuardId.A12_USAGE_COMPLETENESS:
        usage = envelope.execution_usage if envelope is not None else None
        if usage is None or not _all_usage_known(usage):
            return _fail(
                guard,
                AcquisitionFailureCode.USAGE_INCOMPLETE,
                "execution_usage_unknown",
            )
        values = _usage_values(usage)
        if (
            values["canned_transport_invocations"] != evidence.invocation_delta
            or (evidence.invocation_delta > 0 and values["canned_transport_invocations"] == 0)
            or envelope is None
            or envelope.historical_usage is None
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.USAGE_INCOMPLETE,
                "false_zero_or_missing_usage",
            )

    elif guard is AcquisitionGuardId.A13_RESOURCE_RECEIPT_INTEGRITY:
        tripwires = AcquisitionRuntimeCounters(
            canned_transport_invocations=evidence.invocation_delta
        ).to_tripwire_counters()
        if (
            envelope is None
            or record is None
            or not record.resource_integrity
            or envelope.execution_usage != execution_usage
            or envelope.historical_usage != ctx.historical_usage
            or envelope.source_provenance_id != ctx.historical_usage.provenance_id
            or not _usage_within_budget(execution_usage, ctx.policy)
            or any(
                (
                    tripwires.external_network_attempts,
                    tripwires.credential_access_attempts,
                    tripwires.live_provider_calls,
                    tripwires.provider_sdk_calls,
                    tripwires.model_executions,
                    tripwires.tool_calls,
                    tripwires.canonical_application_calls,
                )
            )
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.RESOURCE_RECEIPT_MISMATCH,
                "resource_receipt_integrity",
            )

    elif guard is AcquisitionGuardId.A14_ISOLATION_INTEGRITY:
        if not isolation_receipt.isolated:
            return _fail(
                guard,
                AcquisitionFailureCode.ISOLATION_FAILURE,
                "source_sibling_or_production_mutation",
            )

    elif guard is AcquisitionGuardId.A15_RETENTION_PRIVACY_INTEGRITY:
        if not retention_receipt.policy_compliant:
            return _fail(
                guard,
                AcquisitionFailureCode.RETENTION_POLICY_VIOLATION,
                "retention_policy_violation",
            )

    elif guard is AcquisitionGuardId.A16_FINAL_RECEIPT_INTEGRITY:
        if (
            record is None
            or not record.final_receipt_integrity
            or observation is None
            or observation.semantic_request_id != ctx.request.semantic_request_id
            or observation.transport_attempt_id != ctx.attempt.transport_attempt_id
            or observation.execution_usage_id != execution_usage.execution_usage_id
            or observation.historical_usage_id
            != ctx.historical_usage.historical_usage_id
            or observation.isolation_receipt_id
            != isolation_receipt.isolation_receipt_id
            or observation.retention_receipt_id
            != retention_receipt.retention_receipt_id
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.RECEIPT_MISMATCH,
                "final_receipt_link_integrity",
            )
    return None


def _guard_evaluations(
    primary_failure: Optional[_Failure],
) -> Tuple[AcquisitionGuardEvaluation, ...]:
    if primary_failure is None:
        return tuple(
            AcquisitionGuardEvaluation(
                guard_id=guard,
                stage=(
                    AcquisitionGuardStage.PRE_DISPATCH
                    if guard.value.startswith("P")
                    else AcquisitionGuardStage.POST_DISPATCH
                ),
                state=AcquisitionGuardState.PASSED,
            )
            for guard in ACQUISITION_GUARD_ORDER
        )
    primary_index = ACQUISITION_GUARD_ORDER.index(primary_failure.guard_id)
    rows = []
    for index, guard in enumerate(ACQUISITION_GUARD_ORDER):
        stage = (
            AcquisitionGuardStage.PRE_DISPATCH
            if guard.value.startswith("P")
            else AcquisitionGuardStage.POST_DISPATCH
        )
        if index < primary_index:
            rows.append(
                AcquisitionGuardEvaluation(
                    guard_id=guard,
                    stage=stage,
                    state=AcquisitionGuardState.PASSED,
                )
            )
        elif index == primary_index:
            rows.append(
                AcquisitionGuardEvaluation(
                    guard_id=guard,
                    stage=stage,
                    state=AcquisitionGuardState.FAILED,
                    failure_code=primary_failure.code,
                    diagnostic_mismatches=(primary_failure.diagnostic,),
                )
            )
        else:
            rows.append(
                AcquisitionGuardEvaluation(
                    guard_id=guard,
                    stage=stage,
                    state=AcquisitionGuardState.NOT_REACHED,
                )
            )
    return tuple(rows)


def _build_observation(
    ctx: _RunContext,
    evidence: _TransportEvidence,
    execution_usage: AcquisitionExecutionUsage,
    isolation_receipt: AcquisitionIsolationReceipt,
    retention_receipt: AcquisitionRetentionReceipt,
) -> UnadmittedAcquiredObservation:
    envelope = evidence.envelope
    if envelope is None or envelope.actual_binding is None:
        raise AcquisitionRuntimeError("observation requires delivered actual binding")
    digest = envelope.computed_raw_response_digest
    raw_length = envelope.computed_raw_response_length
    if digest is None or raw_length is None:
        raise AcquisitionRuntimeError("observation requires raw response evidence")
    return UnadmittedAcquiredObservation(
        semantic_request_id=ctx.request.semantic_request_id or "",
        transport_attempt_id=ctx.attempt.transport_attempt_id or "",
        requested_binding=ctx.request.requested_binding,
        actual_binding=envelope.actual_binding,
        raw_response_digest=digest,
        raw_response_length=raw_length,
        raw_response_reference=f"szacqraw_{digest}",
        execution_usage_id=execution_usage.execution_usage_id or "",
        historical_usage_id=ctx.historical_usage.historical_usage_id or "",
        isolation_receipt_id=isolation_receipt.isolation_receipt_id or "",
        retention_receipt_id=retention_receipt.retention_receipt_id or "",
    )


@dataclass(frozen=True)
class AcquisitionRunResult:
    provider_visible_body: bytes
    observation: Optional[UnadmittedAcquiredObservation]
    attempt_receipt: AcquisitionAttemptReceipt
    isolation_receipt: AcquisitionIsolationReceipt
    retention_receipt: AcquisitionRetentionReceipt
    runtime_counters: AcquisitionRuntimeCounters
    tripwire_counters: AcquisitionTripwireCounters
    transport_record: Optional[CannedInvocationRecord]

    @property
    def receipt(self) -> AcquisitionAttemptReceipt:
        return self.attempt_receipt

    @property
    def outcome(self) -> AcquisitionAttemptOutcome:
        return self.attempt_receipt.primary_result.outcome

    @property
    def failure_code(self) -> Optional[AcquisitionFailureCode]:
        return self.attempt_receipt.primary_result.failure_code


async def acquire_canned_observation(
    request: AcquisitionSemanticRequest,
    attempt: AcquisitionTransportAttempt,
    policy: AcquisitionControlPolicy,
    retention_policy: AcquisitionRetentionPolicy,
    transport: CannedAcquisitionTransport,
    *,
    historical_usage: AcquisitionHistoricalUsage,
    isolation_probe: IsolationProbe,
    capability_snapshot: AcquisitionCapabilitySnapshot,
) -> AcquisitionRunResult:
    """Acquire exactly one opaque canned observation, without admitting it.

    A failed pre-dispatch guard leaves the canned invocation delta at zero.  Once
    dispatch is reached, return, exception, and timeout paths all have delta one.
    Isolation is sampled before validation and again in ``finally`` so a failure
    cannot conceal source, sibling, or production mutation.
    """

    transport_type_exact = type(transport) is CannedAcquisitionTransport
    snapshot = capability_snapshot
    provider_visible_error: Optional[str] = None
    try:
        provider_visible_body = render_provider_visible_request(request)
    except Exception as exc:
        provider_visible_error = type(exc).__name__
        try:
            provider_visible_body = request.provider_visible_request.canonical_request_json.encode(
                PROVIDER_VISIBLE_ENCODING
            )
        except Exception:
            provider_visible_body = b"{}"
    isolation_before = _capture_isolation(isolation_probe)
    context = _RunContext(
        request=request,
        attempt=attempt,
        policy=policy,
        retention_policy=retention_policy,
        historical_usage=historical_usage,
        capability_snapshot=snapshot,
        transport=transport,
        provider_visible_body=provider_visible_body,
        provider_visible_error=provider_visible_error,
        isolation_before=isolation_before,
    )

    primary_failure: Optional[_Failure] = None
    evaluator_guard_checks = 0
    evidence = _TransportEvidence(
        invocation_count_before=0,
        invocation_count_after=0,
        envelope=None,
        record=None,
    )
    try:
        for guard in ACQUISITION_GUARD_ORDER:
            if not guard.value.startswith("P"):
                break
            evaluator_guard_checks += 1
            if guard is AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY:
                context = replace(
                    context,
                    transport_boundary_valid=(
                        transport_type_exact
                        and _sealed_canned_transport_state_is_valid(transport)
                    ),
                )
            primary_failure = _pre_guard_failure(guard, context)
            if primary_failure is not None:
                break
            if guard is AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY:
                guarantees = object.__getattribute__(transport, "guarantees")
                if guarantees.prompt_entropy_injection:
                    try:
                        entropy_payload = json.loads(
                            provider_visible_body.decode(PROVIDER_VISIBLE_ENCODING)
                        )
                        if not isinstance(entropy_payload, dict):
                            entropy_payload = {"body": entropy_payload}
                    except Exception:
                        entropy_payload = {}
                    entropy_payload["branch_id"] = attempt.branch_id
                    provider_visible_body = _canonical_bytes(entropy_payload)
                    context = replace(
                        context,
                        provider_visible_body=provider_visible_body,
                    )
        if primary_failure is None:
            if (
                not transport_type_exact
                or not _sealed_canned_transport_state_is_valid(transport)
            ):
                primary_failure = _fail(
                    AcquisitionGuardId.P03_CAPABILITY_SNAPSHOT_INTEGRITY,
                    AcquisitionFailureCode.INVALID_CAPABILITY_SNAPSHOT,
                    "canned_transport_state_changed_before_dispatch",
                )
            else:
                evidence = await _invoke_transport(
                    transport,
                    provider_visible_body,
                    attempt,
                    policy.timeout_ms,
                )
    finally:
        isolation_after = _capture_isolation(isolation_probe)

    invocation_delta = evidence.invocation_delta
    execution_usage = _runtime_execution_usage(invocation_delta)
    isolation_receipt = _build_isolation_receipt(
        request, attempt, isolation_before, isolation_after
    )
    envelope = evidence.envelope
    projected_actual_provider_id: Optional[str] = None
    projected_actual_model_id: Optional[str] = None
    provider_metadata_safe = True
    model_metadata_safe = True
    if envelope is not None:
        projected_actual_provider_id, provider_metadata_safe = (
            _project_canned_actual_identity(
                envelope.actual_provider_id,
                request.requested_binding.provider_id,
                _FROZEN_NON_SENSITIVE_PROVIDER_MISMATCH_IDS,
            )
        )
        projected_actual_model_id, model_metadata_safe = (
            _project_canned_actual_identity(
                envelope.actual_model_id,
                request.requested_binding.model_id,
                _FROZEN_NON_SENSITIVE_MODEL_MISMATCH_IDS,
            )
        )
    metadata_privacy_integrity = provider_metadata_safe and model_metadata_safe
    raw_response_bytes = (
        envelope.raw_response_bytes if envelope is not None else None
    )
    retention_integrity = (
        evidence.record.retention_integrity if evidence.record is not None else True
    )
    retention_receipt = _build_retention_receipt(
        request,
        attempt,
        retention_policy,
        raw_response_bytes,
        integrity=retention_integrity,
        metadata_privacy_integrity=metadata_privacy_integrity,
    )

    observation: Optional[UnadmittedAcquiredObservation] = None
    if primary_failure is None:
        for guard in ACQUISITION_GUARD_ORDER:
            if not guard.value.startswith("A"):
                continue
            evaluator_guard_checks += 1
            if guard is AcquisitionGuardId.A16_FINAL_RECEIPT_INTEGRITY:
                try:
                    observation = _build_observation(
                        context,
                        evidence,
                        execution_usage,
                        isolation_receipt,
                        retention_receipt,
                    )
                except Exception:
                    observation = None
            primary_failure = _post_guard_failure(
                guard,
                context,
                evidence,
                execution_usage,
                isolation_receipt,
                retention_receipt,
                observation,
            )
            if primary_failure is not None:
                observation = None
                break

    guard_evaluations = _guard_evaluations(primary_failure)
    if primary_failure is None:
        primary_result = AcquisitionPrimaryResult(
            outcome=AcquisitionAttemptOutcome.ACQUIRED
        )
    else:
        primary_result = AcquisitionPrimaryResult(
            outcome=AcquisitionAttemptOutcome.FAILED_CLOSED,
            primary_guard_id=primary_failure.guard_id,
            failure_code=primary_failure.code,
        )

    if evidence.timed_out:
        transport_status: Optional[AcquisitionTransportStatus] = (
            AcquisitionTransportStatus.TIMEOUT
        )
    elif evidence.error is not None:
        transport_status = AcquisitionTransportStatus.ERROR
    else:
        transport_status = envelope.transport_status if envelope is not None else None

    isolation_diagnostics = tuple(
        sorted(
            set(
                isolation_before.diagnostic_mismatches
                + isolation_after.diagnostic_mismatches
            )
        )
    )
    diagnostic_mismatches = isolation_diagnostics
    if primary_failure is not None:
        diagnostic_mismatches = tuple(
            sorted(set(diagnostic_mismatches + (primary_failure.diagnostic,)))
        )

    attempt_receipt = AcquisitionAttemptReceipt(
        validation_order_id=FROZEN_ACQUISITION_VALIDATION_ORDER.validation_order_id
        or "",
        failure_taxonomy_id=FROZEN_ACQUISITION_FAILURE_TAXONOMY.failure_taxonomy_id
        or "",
        capability_snapshot_id=snapshot.capability_snapshot_id or "",
        control_policy_id=policy.control_policy_id or "",
        semantic_request_id=request.semantic_request_id or "",
        branch_id=attempt.branch_id,
        transport_attempt_id=attempt.transport_attempt_id or "",
        attempt_ordinal=attempt.attempt_ordinal,
        provider_visible_request_digest=request.provider_visible_request.sha256 or "",
        provider_visible_request_length=request.provider_visible_request.byte_length or 0,
        actual_provider_visible_request_digest=_sha256(provider_visible_body),
        actual_provider_visible_request_length=len(provider_visible_body),
        canned_transport_id=attempt.canned_transport_id,
        requested_binding=request.requested_binding,
        actual_provider_id=projected_actual_provider_id,
        actual_model_id=projected_actual_model_id,
        actual_configuration_digest=(
            envelope.actual_configuration_digest
            if envelope is not None and metadata_privacy_integrity
            else None
        ),
        actual_binding=(
            envelope.actual_binding
            if envelope is not None and metadata_privacy_integrity
            else None
        ),
        guard_evaluations=guard_evaluations,
        transport_status=transport_status,
        reported_raw_response_digest=(
            envelope.reported_raw_response_digest if envelope is not None else None
        ),
        computed_raw_response_digest=(
            envelope.computed_raw_response_digest if envelope is not None else None
        ),
        reported_raw_response_length=(
            envelope.reported_raw_response_length if envelope is not None else None
        ),
        computed_raw_response_length=(
            envelope.computed_raw_response_length if envelope is not None else None
        ),
        raw_response_base64=(
            envelope.raw_response_base64
            if (
                envelope is not None
                and metadata_privacy_integrity
                and envelope.computed_raw_response_digest
                in retention_policy.non_sensitive_raw_response_sha256_allowlist
            )
            else None
        ),
        fallback_used=envelope.fallback_used if envelope is not None else None,
        explicit_retry_count=(
            envelope.explicit_retry_count if envelope is not None else None
        ),
        adapter_retry_count=(
            envelope.adapter_retry_count if envelope is not None else None
        ),
        sdk_internal_retry_count=(
            envelope.sdk_internal_retry_count if envelope is not None else None
        ),
        hidden_transport_retry_count=(
            envelope.hidden_transport_retry_count if envelope is not None else None
        ),
        tool_calls=envelope.tool_calls if envelope is not None else None,
        reported_execution_usage_json=(
            _canonical_json(envelope.execution_usage.model_dump(mode="json"))
            if envelope is not None and envelope.execution_usage is not None
            else None
        ),
        resource_receipt_integrity=(
            evidence.record.resource_integrity if evidence.record is not None else None
        ),
        execution_usage=execution_usage,
        historical_usage=historical_usage,
        isolation_receipt_id=isolation_receipt.isolation_receipt_id or "",
        retention_receipt_id=retention_receipt.retention_receipt_id or "",
        source_mutations=isolation_receipt.source_mutations or 0,
        sibling_mutations=isolation_receipt.sibling_mutations or 0,
        production_mutations=isolation_receipt.production_mutations or 0,
        retention_policy_compliant=bool(retention_receipt.policy_compliant),
        prompt_byte_mismatch=(
            _sha256(provider_visible_body)
            != (request.provider_visible_request.sha256 or "")
            or len(provider_visible_body)
            != (request.provider_visible_request.byte_length or 0)
        ),
        unadmitted_observation_id=(
            observation.unadmitted_observation_id if observation is not None else None
        ),
        primary_result=primary_result,
        diagnostic_mismatches=diagnostic_mismatches,
    )

    runtime_counters = AcquisitionRuntimeCounters(
        canned_transport_invocations=evidence.invocation_delta,
        evaluator_guard_checks=evaluator_guard_checks,
    )
    runtime_counters.assert_hermetic()
    return AcquisitionRunResult(
        provider_visible_body=provider_visible_body,
        observation=observation,
        attempt_receipt=attempt_receipt,
        isolation_receipt=isolation_receipt,
        retention_receipt=retention_receipt,
        runtime_counters=runtime_counters,
        tripwire_counters=runtime_counters.to_tripwire_counters(),
        transport_record=evidence.record,
    )


run_canned_acquisition = acquire_canned_observation


__all__ = [
    "CANNED_ACQUISITION_RUNTIME_VERSION",
    "CANNED_TRANSPORT_IMPLEMENTATION_ID",
    "CANNED_TIMEOUT_CLEANUP_GRACE_SECONDS",
    "CANNED_TIMEOUT_CLEANUP_ROUNDS",
    "PROVIDER_VISIBLE_RENDERER_VERSION",
    "FIRST_ACQUISITION_GUARD_ORDER",
    "AcquisitionRuntimeError",
    "CannedTransportExhausted",
    "CannedTransportFailure",
    "CannedImplementationProfile",
    "CannedTransportDirective",
    "CannedInvocationOutcome",
    "CannedInvocationRecord",
    "AcquisitionRuntimeCounters",
    "CannedAcquisitionTransport",
    "IsolationSubjectSnapshot",
    "AcquisitionIsolationSnapshot",
    "AcquisitionRunResult",
    "build_provider_visible_request",
    "render_provider_visible_request",
    "build_canned_capability_snapshot",
    "acquire_canned_observation",
    "run_canned_acquisition",
]
