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
from dataclasses import dataclass
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

_HEX_DIGITS = frozenset("0123456789abcdef")
_OUT_OF_BAND_PROVIDER_KEYS = frozenset(
    {
        "acquisition_attempt_id",
        "api_key",
        "authorization",
        "branch_id",
        "credential",
        "headers",
        "response_id",
        "transport_attempt_id",
        "transport_request_id",
    }
)


class AcquisitionRuntimeError(RuntimeError):
    """The hermetic runtime could not preserve its local safety contract."""


class CannedTransportExhausted(AcquisitionRuntimeError):
    """The ordered canned script has no entry for another invocation."""


class CannedTransportFailure(AcquisitionRuntimeError):
    """A deterministic failure injected at the in-memory transport boundary."""

    def __init__(self, failure_code: AcquisitionFailureCode) -> None:
        self.failure_code = failure_code
        super().__init__(failure_code.value)


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


def _assert_no_out_of_band_keys(value: object, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in _OUT_OF_BAND_PROVIDER_KEYS:
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


@dataclass(frozen=True)
class CannedTransportDirective:
    """One ordered canned outcome plus narrowly scoped negative-injection flags."""

    envelope: Optional[CannedTransportEnvelope] = None
    failure_code: Optional[AcquisitionFailureCode] = None
    wait_for_cancellation: bool = False
    resist_initial_cancellation: bool = False
    completion_integrity: bool = True
    resource_integrity: bool = True
    retention_integrity: bool = True
    final_receipt_integrity: bool = True

    def __post_init__(self) -> None:
        selected = int(self.envelope is not None) + int(self.failure_code is not None)
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


@dataclass(frozen=True)
class CannedInvocationRecord:
    ordinal: int
    transport_attempt_id: str
    provider_visible_sha256: str
    outcome: str
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


class CannedAcquisitionTransport:
    """In-process ordered transport with class-owned operational guarantees."""

    implementation_id = CANNED_TRANSPORT_IMPLEMENTATION_ID

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
        if not script:
            raise ValueError("canned transport script must not be empty")
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
            if isinstance(item, CannedTransportDirective):
                directives.append(item)
            elif isinstance(item, CannedTransportEnvelope):
                directives.append(CannedTransportDirective(envelope=item))
            else:
                raise TypeError(
                    "script entries must be CannedTransportEnvelope or CannedTransportDirective"
                )
        self._script = tuple(directives)
        self._ledger = _CounterLedger()
        self._records: list[CannedInvocationRecord] = []

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

        ordinal = self._ledger.enter_transport()
        digest = _sha256(provider_visible_body)
        if ordinal > len(self._script):
            self._records.append(
                CannedInvocationRecord(
                    ordinal=ordinal,
                    transport_attempt_id=attempt.transport_attempt_id or "",
                    provider_visible_sha256=digest,
                    outcome="SCRIPT_EXHAUSTED",
                    cancellation_acknowledged=False,
                    worker_terminated=True,
                    completion_integrity=False,
                    resource_integrity=True,
                    retention_integrity=True,
                    final_receipt_integrity=True,
                )
            )
            raise CannedTransportExhausted("canned transport script exhausted")

        directive = self._script[ordinal - 1]
        common = {
            "ordinal": ordinal,
            "transport_attempt_id": attempt.transport_attempt_id or "",
            "provider_visible_sha256": digest,
            "completion_integrity": directive.completion_integrity,
            "resource_integrity": directive.resource_integrity,
            "retention_integrity": directive.retention_integrity,
            "final_receipt_integrity": directive.final_receipt_integrity,
        }
        if directive.envelope is not None:
            self._records.append(
                CannedInvocationRecord(
                    **common,
                    outcome="RETURNED",
                    cancellation_acknowledged=False,
                    worker_terminated=True,
                )
            )
            return directive.envelope
        if directive.failure_code is not None:
            self._records.append(
                CannedInvocationRecord(
                    **common,
                    outcome="RAISED",
                    cancellation_acknowledged=False,
                    worker_terminated=True,
                )
            )
            raise CannedTransportFailure(directive.failure_code)

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
                self._records.append(
                    CannedInvocationRecord(
                        **common,
                        outcome=(
                            "FORCED_CLEANUP"
                            if cancellation_requests > 1
                            else "CANCELLED"
                        ),
                        cancellation_acknowledged=True,
                        worker_terminated=True,
                        cancellation_requests=cancellation_requests,
                        forced_cleanup=cancellation_requests > 1,
                    )
                )
                raise
        raise AssertionError("unreachable canned cancellation outcome")


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
) -> AcquisitionRetentionReceipt:
    raw = raw_response_bytes if raw_response_bytes is not None else b""
    raw_digest = _sha256(raw)
    if policy.response_retention_mode is ResponseRetentionMode.RAW_BYTES_BASE64:
        receipt_base64: Optional[str] = base64.b64encode(raw).decode("ascii")
        response_reference: Optional[str] = None
    else:
        receipt_base64 = None
        response_reference = f"szacqraw_{raw_digest}"
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
        raw_response_length=len(raw),
        raw_response_base64=receipt_base64,
        content_addressed_response_reference=response_reference,
        data_classification=AcquisitionDataClassification.NON_SENSITIVE_CANNED,
        credentials_inspected=False,
        credentials_retained=False,
        personal_private_data_present=False,
        redaction_status=AcquisitionRedactionStatus.NOT_REQUIRED,
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


def _control_map(
    snapshot: AcquisitionCapabilitySnapshot,
) -> Mapping[AcquisitionControlName, AcquisitionControlEvidence]:
    return {item.name: item for item in snapshot.controls}


def _contract_roundtrip(value: Any) -> bool:
    try:
        return type(value).model_validate(value.model_dump(mode="python")) == value
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
            if str(key).strip().lower() in _OUT_OF_BAND_PROVIDER_KEYS:
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
    controls = _control_map(snapshot)
    guarantees = transport.guarantees

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
            not _contract_roundtrip(snapshot)
            or snapshot != transport.capabilities
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
        evidence = controls[AcquisitionControlName.EXTERNAL_NETWORK]
        if (
            evidence.state is not AcquisitionControlState.PROVEN_DISABLED
            or not guarantees.network_prohibited
            or transport.runtime_counters.external_network_attempts != 0
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.EXTERNAL_NETWORK_FORBIDDEN,
                "external_network_prohibition",
            )

    elif guard is AcquisitionGuardId.P07_CREDENTIAL_ACCESS_PROHIBITION:
        evidence = controls[AcquisitionControlName.CREDENTIAL_ACCESS]
        if (
            evidence.state is not AcquisitionControlState.PROVEN_DISABLED
            or not guarantees.credentials_prohibited
            or transport.runtime_counters.credential_reads != 0
        ):
            return _fail(
                guard,
                AcquisitionFailureCode.CREDENTIAL_ACCESS_FORBIDDEN,
                "credential_access_prohibition",
            )

    elif guard is AcquisitionGuardId.P08_EXACT_IDENTITY_VERIFICATION:
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
        try:
            parsed = json.loads(visible.canonical_request_json)
        except Exception:
            parsed = None
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
        if (
            attempt.canned_transport_id != CANNED_TRANSPORT_ID
            or attempt.canned_transport_id
            not in snapshot.registered_canned_transport_ids
            or transport.implementation_id != attempt.canned_transport_id
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
    before = transport.invocation_count
    envelope: Optional[CannedTransportEnvelope] = None
    timed_out = False
    error: Optional[str] = None
    task = asyncio.create_task(
        transport.acquire(body, attempt),
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
    records = transport.invocation_records
    return _TransportEvidence(
        invocation_count_before=before,
        invocation_count_after=transport.invocation_count,
        envelope=envelope,
        record=records[-1] if len(records) > before else None,
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
        tripwires = ctx.transport.runtime_counters.to_tripwire_counters()
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
    capability_snapshot: Optional[AcquisitionCapabilitySnapshot] = None,
) -> AcquisitionRunResult:
    """Acquire exactly one opaque canned observation, without admitting it.

    A failed pre-dispatch guard leaves the canned invocation delta at zero.  Once
    dispatch is reached, return, exception, and timeout paths all have delta one.
    Isolation is sampled before validation and again in ``finally`` so a failure
    cannot conceal source, sibling, or production mutation.
    """

    snapshot = capability_snapshot or transport.capabilities
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
    if transport.guarantees.prompt_entropy_injection:
        try:
            entropy_payload = json.loads(provider_visible_body.decode(PROVIDER_VISIBLE_ENCODING))
            if not isinstance(entropy_payload, dict):
                entropy_payload = {"body": entropy_payload}
        except Exception:
            entropy_payload = {}
        entropy_payload["branch_id"] = attempt.branch_id
        provider_visible_body = _canonical_bytes(entropy_payload)

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
    evidence = _TransportEvidence(
        invocation_count_before=transport.invocation_count,
        invocation_count_after=transport.invocation_count,
        envelope=None,
        record=None,
    )
    try:
        for guard in ACQUISITION_GUARD_ORDER:
            if not guard.value.startswith("P"):
                break
            transport.record_guard_check()
            primary_failure = _pre_guard_failure(guard, context)
            if primary_failure is not None:
                break
        if primary_failure is None:
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
    raw_response_bytes = (
        evidence.envelope.raw_response_bytes if evidence.envelope is not None else None
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
    )

    observation: Optional[UnadmittedAcquiredObservation] = None
    if primary_failure is None:
        for guard in ACQUISITION_GUARD_ORDER:
            if not guard.value.startswith("A"):
                continue
            transport.record_guard_check()
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

    envelope = evidence.envelope
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
        canned_transport_id=attempt.canned_transport_id,
        requested_binding=request.requested_binding,
        actual_provider_id=(
            envelope.actual_provider_id if envelope is not None else None
        ),
        actual_model_id=(envelope.actual_model_id if envelope is not None else None),
        actual_configuration_digest=(
            envelope.actual_configuration_digest if envelope is not None else None
        ),
        actual_binding=envelope.actual_binding if envelope is not None else None,
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
            envelope.raw_response_base64 if envelope is not None else None
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
            primary_failure is not None
            and primary_failure.guard_id
            is AcquisitionGuardId.P16_PROMPT_BYTE_DETERMINISM
        ),
        unadmitted_observation_id=(
            observation.unadmitted_observation_id if observation is not None else None
        ),
        primary_result=primary_result,
        diagnostic_mismatches=diagnostic_mismatches,
    )

    runtime_counters = transport.runtime_counters
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
