"""A CouncilProviderRegistry adapter that runs on the proven live transport.

CED stays the transition authority. This is a worker: it takes whatever task and
agent state CED hands it, renders a dynamic turn against the frozen execution
policy, spends one bounded claim, dispatches exactly once, and returns the
model's text. Everything CED already does with that text is unchanged.

Prompt composition deliberately reuses the repository's own builders rather than
inventing a second prompt dialect, so the harness measures Socrates as it is.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from pydantic import ValidationError

from ..models import AgentState, AgentTask, ProviderResponse, ProviderStatus
from ..provider_registry import BaseProviderAdapter, parse_and_validate_move
from ..semantic_floor import SemanticFloorError, assert_move_content_floor
from ..reasoning_prompts import build_reasoning_system_prompt
from .contracts import ContractValidationError, canonical_json
from .openrouter_live_session_v1 import (
    FROZEN_LIVE_SEMANTIC_HEADERS_V1,
    OpenRouterDynamicTurnRequestV1,
    OpenRouterEndpointCapabilityProfileV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterRenderedTurnV1,
    OpenRouterSessionLedgerV1,
    OpenRouterTurnRecordV1,
    conservative_turn_cost_bound_v1,
    consume_turn_claim_v1,
    mint_turn_claim_id_v1,
    render_dynamic_turn_v1,
    validate_policy_against_profile_v1,
)


ResponseFormatFactoryV1 = Callable[[AgentTask], Mapping[str, Any]]
StructuredOutputValidatorV1 = Callable[[AgentTask, str], Any]
TaskExecutionPolicyFactoryV1 = Callable[
    [AgentTask], OpenRouterFrozenExecutionPolicyV1
]
OutboundTaskStateProjectorV1 = Callable[
    [Dict[str, Any], Dict[str, Any]],
    Tuple[Mapping[str, Any], Mapping[str, Any]],
]
PreDispatchGuardV1 = Callable[
    [Optional[AgentTask], OpenRouterRenderedTurnV1], None
]

COMPLETION_ENVELOPE_EXHAUSTED_FAILURE_V1 = (
    "completion_envelope_exhausted_before_valid_visible_payload"
)

#: The response carried no attributable model or provider identity at all.
#: OpenRouter returns upstream errors inside HTTP 200, and such a body has a
#: top-level ``error`` and no top-level ``model``, so nothing can be bound to
#: the seat. This is not a wrong identity; it is an absent one.
RETURNED_IDENTITY_ABSENT_FAILURE_V1 = "returned_identity_absent_error_envelope"

#: Both identities were present and both were wrong. Distinguished from the
#: single-field cases so an auditor can see at a glance whether one field
#: drifted or the whole attribution did.
RETURNED_MODEL_AND_PROVIDER_MISMATCH_V1 = "returned_model_and_provider_mismatch"

#: Every returned-identity verdict eligible to trip the session fatal latch.
#: A well-formed ERROR envelope on the first council attempt remains rejected,
#: but may consume the already-authorized same-seat retry before this latch is
#: tripped. A repeated absence, an absence outside a council task, and every
#: present-but-wrong identity remain immediately fatal. No unattributed text is
#: ever returned as assistant output.
RETURNED_IDENTITY_FATAL_FAILURES_V1: Tuple[str, ...] = (
    RETURNED_IDENTITY_ABSENT_FAILURE_V1,
    RETURNED_MODEL_AND_PROVIDER_MISMATCH_V1,
    "returned_model_identity_mismatch",
    "returned_provider_identity_mismatch",
)

_PUBLIC_SECRET_PATTERNS_V1: Tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bsk-(?:or-v1-)?[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(
        r"(?i)(\b(?:api[_-]?key|authorization)\b[\"']?\s*[:=]\s*[\"']?)"
        r"[^\"'\s,}]{8,}"
    ),
)


def sanitize_public_assistant_output_v1(text: str) -> str:
    """Retain all visible assistant text while masking credential-shaped data."""

    if not isinstance(text, str):
        raise ContractValidationError("assistant output must be text")
    sanitized = text
    for pattern in _PUBLIC_SECRET_PATTERNS_V1:
        if pattern.groups:
            sanitized = pattern.sub(r"\1[REDACTED]", sanitized)
        else:
            sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


_SAFE_PUBLIC_EXCEPTION_NAMES_V1 = frozenset(
    {
        "ConnectionError",
        "ContractValidationError",
        "EstimatorUnsupportedError",
        "JSONDecodeError",
        "KeyError",
        "OpenRouterDispatchBudgetExceeded",
        "OSError",
        "RequestBoundError",
        "RuntimeError",
        "SemanticFloorError",
        "TimeoutError",
        "TypeError",
        "ValidationError",
        "ValueError",
    }
)
_SAFE_PUBLIC_EXCEPTION_CONTEXTS_V1 = frozenset(
    {"orchestration", "provider_turn", "structured_output"}
)
_SAFE_PYDANTIC_ERROR_TYPES_V1 = frozenset(
    {
        "assertion_error",
        "bool_parsing",
        "bool_type",
        "dict_type",
        "enum",
        "extra_forbidden",
        "float_parsing",
        "float_type",
        "greater_than",
        "greater_than_equal",
        "int_parsing",
        "int_type",
        "invalid_key",
        "is_instance_of",
        "is_subclass_of",
        "json_invalid",
        "json_type",
        "less_than",
        "less_than_equal",
        "list_type",
        "literal_error",
        "mapping_type",
        "missing",
        "model_attributes_type",
        "multiple_of",
        "none_required",
        "set_type",
        "string_pattern_mismatch",
        "string_too_long",
        "string_too_short",
        "string_type",
        "too_long",
        "too_short",
        "tuple_type",
        "union_tag_invalid",
        "union_tag_not_found",
        "url_parsing",
        "url_type",
        "uuid_parsing",
        "uuid_type",
        "value_error",
    }
)


def safe_public_exception_code_v1(exc: BaseException, *, context: str) -> str:
    """Return a finite-domain error code without provider-controlled text.

    Exception messages are intentionally excluded.  Pydantic validation errors
    retain only counts by a fixed allowlist of machine error types; locations,
    messages, URLs and input values never enter the returned code.
    """

    if context not in _SAFE_PUBLIC_EXCEPTION_CONTEXTS_V1:
        raise ContractValidationError("public exception-code context is unsupported")
    name = type(exc).__name__
    safe_name = name if name in _SAFE_PUBLIC_EXCEPTION_NAMES_V1 else "OtherError"
    if isinstance(exc, ValidationError):
        try:
            issues = exc.errors(include_input=False, include_url=False)
        except TypeError:  # pragma: no cover - compatibility with old Pydantic
            issues = exc.errors()
        counts: Counter[str] = Counter()
        for issue in issues:
            error_type = issue.get("type") if isinstance(issue, Mapping) else None
            if error_type not in _SAFE_PYDANTIC_ERROR_TYPES_V1:
                error_type = "other"
            counts[str(error_type)] += 1
        summary = ",".join(
            f"{error_type}={counts[error_type]}" for error_type in sorted(counts)
        ) or "none=0"
        return f"{context}:ValidationError:{summary}"
    return f"{context}:{safe_name}"


_SAFE_CED_REJECTION_CODES_V1: Mapping[str, str] = {
    "empty response": "ced_invalid_json:empty_response",
    "json parse failed": "ced_invalid_json:json_parse_failed",
    "top-level JSON is not an object": "ced_schema_error:top_level_not_object",
    (
        "schema validation failed: epistemic_marker is required"
    ): "ced_schema_error:epistemic_marker_required",
    (
        "schema validation failed: epistemic_marker is not permitted "
        "for this task kind"
    ): "ced_schema_error:epistemic_marker_not_permitted",
    (
        "schema validation failed: epistemic_marker must be a string"
    ): "ced_schema_error:epistemic_marker_not_string",
    (
        "schema validation failed: epistemic_marker is not canonical"
    ): "ced_schema_error:epistemic_marker_not_canonical",
}


def _safe_ced_rejection_code_v1(
    status: ProviderStatus,
    raw_error: Optional[str],
    *,
    semantic_floor_rejected: bool,
) -> str:
    """Map CED parser diagnostics to fixed codes, never their raw message."""

    if semantic_floor_rejected:
        return "ced_schema_error:semantic_floor_rejected"
    exact = _SAFE_CED_REJECTION_CODES_V1.get(raw_error or "")
    if exact is not None:
        return exact
    if status is ProviderStatus.INVALID_JSON:
        if isinstance(raw_error, str) and raw_error.startswith(
            "json parse failed after repair:"
        ):
            return "ced_invalid_json:repair_failed"
        return "ced_invalid_json:unrecognized"
    if status is ProviderStatus.SCHEMA_ERROR:
        return "ced_schema_error:validation_failed"
    if isinstance(status, ProviderStatus):
        return f"ced_rejected:{status.value}"
    return "ced_rejected:unrecognized"


#: Where a pre-dispatch refusal parks its accounting record.  The exception
#: itself is re-raised unchanged, so callers that depend on the exception type
#: keep working; this only makes the attempt recoverable for the artifact.
PRE_DISPATCH_RECORD_ATTRIBUTE_V1 = "openrouter_pre_dispatch_record_v1"


@dataclass(frozen=True)
class OpenRouterBoundedTextOutcomeV1:
    """One bounded POST outcome shared by CED seats and direct baselines."""

    #: None only when the turn was refused before it could be rendered.  The
    #: record is never None: every attempted call is accounted for exactly once.
    rendered: Optional[OpenRouterRenderedTurnV1]
    record: OpenRouterTurnRecordV1
    assistant_text: Optional[str]
    raw_response_body: bytes
    failure_reason: Optional[str]


def build_turn_user_content_v1(
    task: AgentTask,
    agent_state: AgentState,
    *,
    outbound_task_state_projector: Optional[
        OutboundTaskStateProjectorV1
    ] = None,
) -> str:
    """Only canonical public task/state fields reach the provider."""
    task_payload = task.model_dump(mode="json", exclude_none=True)
    state_payload = agent_state.model_dump(mode="json", exclude_none=True)
    if outbound_task_state_projector is not None:
        projected = outbound_task_state_projector(task_payload, state_payload)
        if not isinstance(projected, tuple) or len(projected) != 2:
            raise ContractValidationError(
                "outbound task/state projector must return exactly two objects"
            )
        projected_task, projected_state = projected
        if not isinstance(projected_task, Mapping) or not isinstance(
            projected_state, Mapping
        ):
            raise ContractValidationError(
                "outbound task/state projection must return JSON objects"
            )
        # Detach the projection from caller-owned mutable objects and prove it
        # is canonical JSON before it enters the message body.
        try:
            task_payload = json.loads(canonical_json(dict(projected_task)))
            state_payload = json.loads(canonical_json(dict(projected_state)))
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                "outbound task/state projection is not canonical JSON"
            ) from exc
    payload: Dict[str, Any] = {
        "task": task_payload,
        "agent_state": state_payload,
        "response_contract": {
            "format": "json_object",
            "required": ["content", "confidence"],
            "content_must_be_object": True,
        },
    }
    return (
        "You are one bounded Socratic council provider. Return exactly one JSON "
        "object and no markdown. Do not invent protocol authority.\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def _default_dispatcher_v1() -> Callable[..., Any]:
    from .openrouter_one_live_shadow_v1 import (
        dispatch_openrouter_one_live_inference_v1,
    )

    return dispatch_openrouter_one_live_inference_v1


def execute_bounded_text_turn_v1(
    *,
    policy: OpenRouterFrozenExecutionPolicyV1,
    profile: OpenRouterEndpointCapabilityProfileV1,
    ledger: OpenRouterSessionLedgerV1,
    claim_directory: Path,
    max_input_tokens: int,
    turn: OpenRouterDynamicTurnRequestV1,
    response_format_override: Optional[Mapping[str, Any]],
    expected_returned_models: Tuple[str, ...],
    expected_provider_display_names: Tuple[str, ...],
    task: Optional[AgentTask] = None,
    pre_dispatch_guard: Optional[PreDispatchGuardV1] = None,
    dispatch: Optional[Callable[..., Any]] = None,
) -> OpenRouterBoundedTextOutcomeV1:
    """Execute one text-only turn with one claim and fail-closed identity.

    The caller supplies the task-derived structured-output schema.  This helper
    merely verifies that it is strict and seals it into the request; it does not
    own or recreate any CED schema.  Both expected identity sets are mandatory,
    so a successful HTTP response can never silently pass without exact route
    evidence.
    """

    task_kind_value = None
    if task is not None and task.task_kind is not None:
        task_kind_value = str(
            getattr(task.task_kind, "value", task.task_kind)
        )

    # Every attempted call must leave exactly one terminal accounting record.
    #
    # Until this block existed, a record was first constructed at the dispatch
    # boundary, so any refusal before it — an identity check, a rendering
    # failure, the pre-dispatch guard, a ledger refusal, a claim collision —
    # raised straight past ``turn_records.append`` and the attempt vanished.
    # ``generate_agent_move`` turned it into a ProviderResponse the council
    # acted on, while the artifact showed nothing at all.
    #
    # That is exactly what happened to the Gemini seat at reconstruction in the
    # exploratory Q2 run: ledger calls and turn records both stood at 12, no
    # finish-reason line and no error envelope were written, which together rule
    # out transport and provider failure and leave a pre-dispatch refusal that
    # nothing recorded. Which refusal it was is not recoverable, and that
    # irrecoverability is the defect.
    #
    # The reservation is deliberately not taken here: nothing has been
    # dispatched, so nothing may be charged. Only the accounting is emitted.
    stage = "identity_validation"
    rendered = None
    try:
        validate_policy_against_profile_v1(policy, profile)
        if not expected_returned_models or not all(
            isinstance(value, str) and value.strip()
            for value in expected_returned_models
        ):
            raise ContractValidationError(
                "expected returned-model identities are required"
            )
        if not expected_provider_display_names or not all(
            isinstance(value, str) and value.strip()
            for value in expected_provider_display_names
        ):
            raise ContractValidationError(
                "expected provider display identities are required"
            )
        stage = "render"
        rendered = render_dynamic_turn_v1(
            policy,
            profile,
            turn,
            response_format_override=response_format_override,
        )
        if pre_dispatch_guard is not None:
            stage = "pre_dispatch_guard"
            pre_dispatch_guard(task, rendered)
        stage = "cost_bound"
        # Reserve against what this request actually is, not against the
        # ceiling it is allowed to reach.
        #
        # The body is already rendered here, so its size is known. Reserving
        # the full ceiling on every call forced one number to serve two
        # incompatible jobs: a prompt bound loose enough for a long dialogue,
        # and a reservation tight enough to stay under the operator's spend
        # ceiling. That conflict refused all eleven ratification and
        # objection-verification calls of one council run, so the dialogue
        # completed every phase and then never voted.
        #
        # Using the measured size is strictly more accurate and never
        # under-reserves: the byte count is still an upper bound on tokens,
        # and the ceiling still applies as a cap.
        measured_input_tokens = min(
            int(max_input_tokens),
            len(rendered.canonical_body_json.encode("utf-8")) + 64,
        )
        worst_case = conservative_turn_cost_bound_v1(policy, measured_input_tokens)
        stage = "ledger_admission"
        ledger.check_admits(worst_case)
        stage = "claim_mint"
        claim_id = mint_turn_claim_id_v1(ledger.authorization, rendered)
        stage = "claim_consume"
        consume_turn_claim_v1(Path(claim_directory), claim_id)
    except Exception as exc:
        # Opt-in diagnostic. Refusals here are sanitised to a class name for the
        # record, which is right for evidence and wrong for debugging: three
        # separate times this refusal was diagnosed by guessing, twice
        # incorrectly, because the message never surfaced anywhere. Setting
        # SOCRATES_DEBUG_PREDISPATCH=1 prints it to stderr. Nothing is written to
        # any artifact, so the privacy boundary is unchanged.
        if os.environ.get("SOCRATES_DEBUG_PREDISPATCH"):
            import traceback

            print(
                f"[pre-dispatch refusal] stage={stage} seat={turn.role_seat} "
                f"phase={turn.dialogue_phase} model={policy.model}: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            traceback.print_exc()
        # Attach the accounting record to the exception and re-raise the
        # original, unchanged.  Swallowing these into a returned outcome would
        # be a real weakening: an evaluator-canary leak and a duplicate claim
        # consumption must both hard-stop, and callers rely on the exception
        # type to do it.  Accounting is added; control flow is not altered.
        setattr(
            exc,
            PRE_DISPATCH_RECORD_ATTRIBUTE_V1,
            OpenRouterTurnRecordV1(
                dialogue_id=turn.dialogue_id,
                turn_id=turn.turn_id,
                role_seat=turn.role_seat,
                dialogue_phase=turn.dialogue_phase,
                task_kind=task_kind_value,
                model=policy.model,
                provider_selector=profile.provider_selector,
                request_id=(getattr(rendered, "request_id", None) or ""),
                body_sha256=(getattr(rendered, "body_sha256", None) or "0" * 64),
                transport_completed=False,
                worst_case_picodollars=0,
                failure_class=(
                    f"pre_dispatch_refusal:{stage}:{type(exc).__name__}"
                ),
            ),
        )
        raise

    dispatcher = dispatch or _default_dispatcher_v1()
    started = time.perf_counter()
    try:
        result = dispatcher(
            body_bytes=rendered.canonical_body_json.encode("utf-8"),
            semantic_headers=dict(FROZEN_LIVE_SEMANTIC_HEADERS_V1),
            bounded_timeout_seconds=policy.bounded_timeout_seconds,
            process_dispatch_limit=ledger.authorization.maximum_calls,
        )
    except Exception as exc:
        # The transport's process latch is the one known refusal guaranteed to
        # happen before a socket opens.  Any other exception is conservatively
        # treated as an attempted/possibly charged POST and keeps its P19
        # reservation forever.
        from .openrouter_one_live_shadow_v1 import (
            OpenRouterDispatchBudgetExceeded,
        )

        if isinstance(exc, OpenRouterDispatchBudgetExceeded):
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            setattr(
                exc,
                PRE_DISPATCH_RECORD_ATTRIBUTE_V1,
                OpenRouterTurnRecordV1(
                    dialogue_id=turn.dialogue_id,
                    turn_id=turn.turn_id,
                    role_seat=turn.role_seat,
                    dialogue_phase=turn.dialogue_phase,
                    task_kind=task_kind_value,
                    model=policy.model,
                    provider_selector=profile.provider_selector,
                    request_id=rendered.request_id or "",
                    body_sha256=rendered.body_sha256,
                    transport_completed=False,
                    latency_ms=latency_ms,
                    worst_case_picodollars=0,
                    failure_class=(
                        "dispatch_refusal:process_budget:"
                        "OpenRouterDispatchBudgetExceeded"
                    ),
                ),
            )
            raise
        ledger.record_dispatch(worst_case)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        record = OpenRouterTurnRecordV1(
            dialogue_id=turn.dialogue_id,
            turn_id=turn.turn_id,
            role_seat=turn.role_seat,
            dialogue_phase=turn.dialogue_phase,
            task_kind=task_kind_value,
            model=policy.model,
            provider_selector=profile.provider_selector,
            request_id=rendered.request_id or "",
            body_sha256=rendered.body_sha256,
            transport_completed=False,
            latency_ms=latency_ms,
            worst_case_picodollars=worst_case,
            failure_class=f"dispatch_exception:{type(exc).__name__}",
        )
        return OpenRouterBoundedTextOutcomeV1(
            rendered=rendered,
            record=record,
            assistant_text=None,
            raw_response_body=b"",
            failure_reason=record.failure_class,
        )

    # The dispatch attempt is consumed regardless of HTTP/provider success.
    ledger.record_dispatch(worst_case)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    completion = result.completion
    raw = bytes(result.raw_response_body)
    retry_count = getattr(completion, "retry_count", 0)
    if type(retry_count) is not int or retry_count != 0:
        retry_count = int(retry_count) if type(retry_count) is int else 1

    record_fields: Dict[str, Any] = dict(
        dialogue_id=turn.dialogue_id,
        turn_id=turn.turn_id,
        role_seat=turn.role_seat,
        dialogue_phase=turn.dialogue_phase,
        task_kind=task_kind_value,
        model=policy.model,
        provider_selector=profile.provider_selector,
        request_id=rendered.request_id or "",
        body_sha256=rendered.body_sha256,
        response_body_sha256=hashlib.sha256(raw).hexdigest(),
        response_body_length=len(raw),
        http_status=completion.http_status,
        transport_completed=completion.completed,
        retry_count=retry_count,
        latency_ms=latency_ms,
        worst_case_picodollars=worst_case,
        failure_class=completion.failure_class,
    )
    if retry_count != 0:
        record_fields["failure_class"] = "transport_retry_observed"
        ledger.trip_fatal("transport_retry_observed")

    payload: Optional[Mapping[str, Any]] = None
    try:
        decoded = json.loads(raw.decode("utf-8"), parse_float=Decimal)
        if isinstance(decoded, Mapping):
            payload = decoded
    except (UnicodeDecodeError, ValueError):
        payload = None

    accounting_failure: Optional[str] = None
    if payload is not None:
        usage = payload.get("usage")
        if isinstance(usage, Mapping):
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            if type(prompt_tokens) is int and prompt_tokens >= 0:
                record_fields["prompt_tokens"] = prompt_tokens
            if type(completion_tokens) is int and completion_tokens >= 0:
                record_fields["completion_tokens"] = completion_tokens
            cost = usage.get("cost")
            try:
                exact_cost = (
                    Decimal(cost)
                    if type(cost) in (int, str, Decimal)
                    else None
                )
            except InvalidOperation:
                exact_cost = None
            if exact_cost is not None and exact_cost.is_finite() and exact_cost >= 0:
                record_fields["observed_cost_usd_decimal"] = str(exact_cost)
                scaled = exact_cost * Decimal(10**12)
                within_p19 = scaled <= Decimal(worst_case)
                record_fields["observed_cost_within_p19_bound"] = within_p19
                if scaled == scaled.to_integral_value():
                    observed = int(scaled)
                    record_fields["observed_cost_picodollars"] = observed
                    ledger.settle_observed(observed, worst_case)
                    within_session = ledger.committed_picodollars <= (
                        ledger.authorization.maximum_total_spend_picodollars
                    )
                    record_fields[
                        "committed_cost_within_session_ceiling"
                    ] = within_session
                    if not within_session:
                        accounting_failure = (
                            "observed_session_cost_exceeds_authorized_total"
                        )
                        ledger.trip_fatal(accounting_failure)
                if not within_p19:
                    accounting_failure = accounting_failure or (
                        "observed_cost_exceeds_p19_reservation"
                    )
                    ledger.trip_fatal(accounting_failure)

    if accounting_failure is not None:
        record_fields["failure_class"] = accounting_failure

    if not completion.completed:
        record = OpenRouterTurnRecordV1(**record_fields)
        return OpenRouterBoundedTextOutcomeV1(
            rendered=rendered,
            record=record,
            assistant_text=None,
            raw_response_body=raw,
            failure_reason=(
                accounting_failure
                or f"transport_failed:{completion.failure_class}"
            ),
        )
    if retry_count != 0:
        record = OpenRouterTurnRecordV1(**record_fields)
        return OpenRouterBoundedTextOutcomeV1(
            rendered=rendered,
            record=record,
            assistant_text=None,
            raw_response_body=raw,
            failure_reason=accounting_failure or "transport_retry_observed",
        )
    if completion.http_status != 200:
        record = OpenRouterTurnRecordV1(**record_fields)
        return OpenRouterBoundedTextOutcomeV1(
            rendered=rendered,
            record=record,
            assistant_text=None,
            raw_response_body=raw,
            failure_reason=accounting_failure or f"http_{completion.http_status}",
        )

    from .openrouter_one_live_shadow_runner_v1 import s5_observation_from_live_v1
    from .openrouter_raw_wire_mapping_v2 import map_openrouter_raw_wire_v2

    try:
        observation = s5_observation_from_live_v1(result)
        mapping = map_openrouter_raw_wire_v2(observation)
    except ContractValidationError:
        record_fields["s5_envelope_kind"] = "REFUSED"
        ledger.trip_fatal("raw_mapping_refused")
        record = OpenRouterTurnRecordV1(**record_fields)
        return OpenRouterBoundedTextOutcomeV1(
            rendered=rendered,
            record=record,
            assistant_text=None,
            raw_response_body=raw,
            failure_reason="raw_mapping_refused",
        )

    record_fields["s5_envelope_kind"] = getattr(
        mapping.envelope_kind, "value", str(mapping.envelope_kind)
    )
    # The comparison operands and the mapper's own epistemic verdict, recorded
    # before any conclusion is drawn from them. Both are server-side
    # configuration or a closed enum; neither is provider-controlled text.
    record_fields["actual_served_model_status"] = getattr(
        mapping.actual_served_model_status,
        "value",
        str(mapping.actual_served_model_status),
    )
    record_fields["router_metadata_presence"] = getattr(
        mapping.router_metadata_presence,
        "value",
        str(mapping.router_metadata_presence),
    )
    record_fields["expected_model_identity"] = ",".join(expected_returned_models)
    record_fields["expected_provider_identity"] = ",".join(
        expected_provider_display_names
    )

    actual_model = mapping.actual_served_model
    model_present = actual_model is not None
    model_ok = actual_model in expected_returned_models
    if model_present:
        record_fields["actual_served_model"] = (
            actual_model if model_ok else "unrecognized_model"
        )
    record_fields["returned_model_binding_ok"] = model_ok

    provider_display = payload.get("provider") if payload is not None else None
    provider_present = isinstance(provider_display, str)
    provider_ok = provider_display in expected_provider_display_names
    if provider_present:
        record_fields["provider_display_name"] = (
            provider_display if provider_ok else "unrecognized_provider"
        )
    record_fields["returned_provider_binding_ok"] = provider_ok

    assistant_text: Optional[str] = None
    if payload is not None:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            message = first.get("message") if isinstance(first, Mapping) else None
            content = message.get("content") if isinstance(message, Mapping) else None
            if isinstance(content, str):
                assistant_text = content
                sanitized = sanitize_public_assistant_output_v1(content)
                record_fields["assistant_text_excerpt"] = sanitized[:600]
                record_fields["assistant_output_sanitized"] = sanitized
                record_fields["assistant_output_sha256"] = hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest()

    failure: Optional[str] = accounting_failure
    # An unattributable response and a wrongly attributed one are distinct. A
    # top-level ERROR envelope contains no candidate answer to trust, so the
    # first council attempt can reject it and use the already-planned same-seat
    # retry. Missing identity anywhere else, a repeated ERROR envelope, and all
    # present-but-wrong identities still trip the fatal latch.
    if not model_present or not provider_present:
        failure = failure or RETURNED_IDENTITY_ABSENT_FAILURE_V1
    elif not model_ok and not provider_ok:
        failure = failure or RETURNED_MODEL_AND_PROVIDER_MISMATCH_V1
    elif not model_ok:
        failure = failure or "returned_model_identity_mismatch"
    elif not provider_ok:
        failure = failure or "returned_provider_identity_mismatch"
    elif (
        (assistant_text is None or not assistant_text.strip())
        and record_fields.get("s5_envelope_kind") == "SUCCESS"
        and record_fields.get("completion_tokens") == policy.output_limit_tokens
    ):
        failure = failure or COMPLETION_ENVELOPE_EXHAUSTED_FAILURE_V1
    elif assistant_text is None:
        failure = failure or "no_assistant_content"
    if failure is not None:
        record_fields["failure_class"] = failure
        retryable_first_attempt_error_envelope = (
            failure == RETURNED_IDENTITY_ABSENT_FAILURE_V1
            and task is not None
            and task.attempt_index == 0
            and record_fields.get("s5_envelope_kind") == "ERROR"
        )
        if (
            failure in RETURNED_IDENTITY_FATAL_FAILURES_V1
            and not retryable_first_attempt_error_envelope
        ):
            ledger.trip_fatal(failure)

    record = OpenRouterTurnRecordV1(**record_fields)
    return OpenRouterBoundedTextOutcomeV1(
        rendered=rendered,
        record=record,
        assistant_text=assistant_text if failure is None else None,
        raw_response_body=raw,
        failure_reason=failure,
    )


# ---------------------------------------------------------------------------
# Objection rulings re-entering the dialogue.
#
# Measured over three ratified councils: 80% of calls and ~60% of generated
# tokens are evaluator output no seat ever sees. Almost all of that is quality
# scores, which must stay hidden - a seat that can see what the scorer rewards
# optimises for the scorer. Nine outputs per run are different: objection
# verifications, which decide whether an objection raised by a seat holds
# against the task text, and carry `condition_tested`, `objection_holds`,
# `rationale` and `cited_spans`.
#
# Those are not performance judgements and there is no score in them to chase.
# Withholding them costs the dialectic directly: in the Q4 council the seats
# circled the same specification gap for six rounds while six reasoned rulings
# on exactly that gap were produced and discarded - two of which contradicted
# each other on whether the task settled the question. Neither reached the room.
#
# So rulings are recorded when they come back and injected into later
# deliberation contexts. The ledger is process-wide because the three seats hold
# separate adapters within one run, and it is keyed by session so two runs in a
# process cannot bleed into each other.
#: What a failure means depends on which attempt it was, and the three are not
#: the same failure. Recording them under one name throws away the only thing
#: that distinguishes a seat that did not understand from one that will not
#: comply.
#:
#: 0 - IGNORANCE. It did not know. Nothing is held against it; the question is
#:     put again, to the same seat, because it may simply not have understood.
#: 1 - BETRAYAL. It was asked again and failed again. This is no longer not
#:     knowing: it is persisting after being told, so the question passes to a
#:     different seat.
#: 2 - NON_CONFORMANCE. It did not come into line with what the room requires.
#:     The council stops asking and records the fact about the seat, because a
#:     seat that reliably will not answer is evidence about that seat and must
#:     not be silently absorbed as though the round had merely been unlucky.
#:
#: The three are kept apart in the evidence precisely so reliability can be read
#: off the dialogue itself rather than inferred from separate baselines.
ATTEMPT_FAILURE_CLASSES_V1 = ("ignorance", "betrayal", "non_conformance")


def attempt_failure_class_v1(attempt_index: Optional[int]) -> Optional[str]:
    """Name a rejected attempt by what that attempt means, not by its number."""
    if not isinstance(attempt_index, int) or attempt_index < 0:
        return None
    if attempt_index >= len(ATTEMPT_FAILURE_CLASSES_V1):
        return ATTEMPT_FAILURE_CLASSES_V1[-1]
    return ATTEMPT_FAILURE_CLASSES_V1[attempt_index]


OBJECTION_RULING_CONTEXT_KEY_V1 = "objection_rulings_so_far"
OBJECTION_RULING_FIELDS_V1 = (
    "condition_tested",
    "objection_holds",
    "objection_targets",
    "rationale",
    "cited_spans",
)
_OBJECTION_RULINGS_V1: Dict[str, List[Dict[str, Any]]] = {}


def reset_objection_rulings_v1(session_id: Optional[str] = None) -> None:
    """Drop recorded rulings, for one session or all of them."""
    if session_id is None:
        _OBJECTION_RULINGS_V1.clear()
    else:
        _OBJECTION_RULINGS_V1.pop(session_id, None)


def recorded_objection_rulings_v1(session_id: str) -> Tuple[Dict[str, Any], ...]:
    return tuple(dict(row) for row in _OBJECTION_RULINGS_V1.get(session_id, ()))


def _record_objection_ruling_v1(task: AgentTask, content: Any) -> None:
    """Keep the allowlisted fields of one verification, never the score."""
    if not isinstance(content, Mapping):
        return
    kept = {
        field: content[field]
        for field in OBJECTION_RULING_FIELDS_V1
        if field in content
    }
    if "rationale" not in kept:
        return
    schema = task.output_schema if isinstance(task.output_schema, Mapping) else {}
    kept["objection_id"] = schema.get("_objection")
    _OBJECTION_RULINGS_V1.setdefault(task.session_id or "", []).append(kept)


def _with_objection_rulings_v1(task: AgentTask) -> AgentTask:
    """Return the task with prior rulings visible, or the task unchanged.

    Evaluator tasks are left alone: the rulings are for the room, not for the
    scorer, and feeding a verifier its own prior verdicts would make the second
    one dependent on the first.
    """
    rulings = _OBJECTION_RULINGS_V1.get(task.session_id or "")
    if not rulings:
        return task
    if getattr(task.task_kind, "name", "") in {
        "OBJECTION_VERIFICATION",
        "MOVE_SCORE",
        "SECTION_SCORE",
    }:
        return task
    context = dict(task.context or {})
    if OBJECTION_RULING_CONTEXT_KEY_V1 in context:
        return task
    context[OBJECTION_RULING_CONTEXT_KEY_V1] = [dict(row) for row in rulings]
    return task.model_copy(update={"context": context})


class SocratesLiveOpenRouterAdapter(BaseProviderAdapter):
    """One council seat, served by the proven one-shot live transport."""

    provider_name = "OpenRouter (live harness)"
    is_fake = False

    def __init__(
        self,
        *,
        provider_id: str,
        policy: OpenRouterFrozenExecutionPolicyV1,
        profile: OpenRouterEndpointCapabilityProfileV1,
        ledger: OpenRouterSessionLedgerV1,
        claim_directory: Path,
        max_input_tokens: int,
        enabled: bool = True,
        dispatch: Optional[Callable[..., Any]] = None,
        response_format_factory: Optional[ResponseFormatFactoryV1] = None,
        pre_dispatch_guard: Optional[PreDispatchGuardV1] = None,
        worker_alias: Optional[str] = None,
        expose_model_identity_to_worker: bool = True,
        expected_returned_models: Optional[Tuple[str, ...]] = None,
        expected_provider_display_names: Optional[Tuple[str, ...]] = None,
        ced_parse_repair_attempts: int = 1,
        structured_output_validator: Optional[StructuredOutputValidatorV1] = None,
        task_execution_policy_factory: Optional[
            TaskExecutionPolicyFactoryV1
        ] = None,
        outbound_task_state_projector: Optional[
            OutboundTaskStateProjectorV1
        ] = None,
    ) -> None:
        # The credential is never read here; the transport owns the one read
        # site and only presence is ever observable from outside it.
        super().__init__(api_key=None, enabled=enabled)
        validate_policy_against_profile_v1(policy, profile)
        self.provider_id = str(provider_id).strip()
        if not self.provider_id:
            raise ValueError("provider_id is required")
        self.policy = policy
        self.profile = profile
        self.ledger = ledger
        self.claim_directory = Path(claim_directory)
        self.max_input_tokens = int(max_input_tokens)
        alias = str(worker_alias or "").strip()
        if not expose_model_identity_to_worker and not alias:
            raise ValueError("an anonymous worker requires a public alias")
        self.worker_alias = alias or self.provider_id
        self.expose_model_identity_to_worker = bool(expose_model_identity_to_worker)
        # CED deliberately reads `.model` for worker-visible roster/transcript
        # labels.  Keep the exact route separately in `.model_id`, which is the
        # evaluator-side authority used for independence checks.
        self.model = (
            policy.model
            if self.expose_model_identity_to_worker
            else self.worker_alias
        )
        self.model_id = policy.model
        self.provider_name = (
            "OpenRouter (live harness)"
            if self.expose_model_identity_to_worker
            else f"Council worker {self.worker_alias}"
        )
        self._dispatch = dispatch
        self._response_format_factory = response_format_factory
        self._pre_dispatch_guard = pre_dispatch_guard
        self.expected_returned_models = tuple(
            expected_returned_models or (policy.model,)
        )
        self.expected_provider_display_names = tuple(
            expected_provider_display_names or ()
        )
        if type(ced_parse_repair_attempts) is not int or (
            ced_parse_repair_attempts not in (0, 1)
        ):
            raise ValueError("CED parse repair attempts must be 0 or 1")
        self.ced_parse_repair_attempts = ced_parse_repair_attempts
        self._structured_output_validator = structured_output_validator
        if task_execution_policy_factory is not None and not callable(
            task_execution_policy_factory
        ):
            raise ValueError("task execution policy factory must be callable")
        self._task_execution_policy_factory = task_execution_policy_factory
        self._outbound_task_state_projector = outbound_task_state_projector
        if response_format_factory is not None and not (
            self.expected_provider_display_names
        ):
            raise ValueError(
                "strict structured turns require an expected provider display name"
            )
        if (response_format_factory is None) != (
            structured_output_validator is None
        ):
            raise ValueError(
                "structured response-format and validator callbacks are a pair"
            )
        self.turn_records: List[OpenRouterTurnRecordV1] = []
        self.last_raw_response: Optional[bytes] = None

    def is_available(self) -> bool:
        from .openrouter_one_live_shadow_v1 import (
            openrouter_credential_is_present_v1,
        )

        if self._dispatch is not None:
            return self.enabled
        return self.enabled and openrouter_credential_is_present_v1()

    def authoritative_model_id(self) -> Optional[str]:
        return self.model_id

    def _dispatcher(self) -> Callable[..., Any]:
        if self._dispatch is not None:
            return self._dispatch
        return _default_dispatcher_v1()

    def _execution_policy_for_task(
        self, task: AgentTask
    ) -> OpenRouterFrozenExecutionPolicyV1:
        """Resolve a lower-or-equal output envelope without route drift."""

        if self._task_execution_policy_factory is None:
            return self.policy
        selected = self._task_execution_policy_factory(task)
        if type(selected) is not OpenRouterFrozenExecutionPolicyV1:
            raise ContractValidationError(
                "task policy factory must return the exact execution policy"
            )
        validate_policy_against_profile_v1(selected, self.profile)
        fixed_fields = self.policy.model_dump(
            mode="json", exclude={"output_limit_tokens", "policy_id"}
        )
        selected_fixed_fields = selected.model_dump(
            mode="json", exclude={"output_limit_tokens", "policy_id"}
        )
        if selected_fixed_fields != fixed_fields:
            raise ContractValidationError(
                "task policy may change only output_limit_tokens"
            )
        if selected.output_limit_tokens > self.policy.output_limit_tokens:
            raise ContractValidationError(
                "task policy exceeds the authorized output envelope"
            )
        return selected

    async def _produce_raw_text(
        self, task: AgentTask, agent_state: AgentState
    ) -> str:
        """Render, budget-check, claim, dispatch once, map, record.

        Order matters: the budget is checked and the claim burned *before* any
        socket opens, so a crash under-executes rather than double-spending.
        """
        execution_policy = self._execution_policy_for_task(task)
        turn = OpenRouterDynamicTurnRequestV1(
            system_prompt=build_reasoning_system_prompt(
                task.role,
                task.phase,
                task.task_kind,
                model=(
                    execution_policy.model
                    if self.expose_model_identity_to_worker
                    else None
                ),
            ),
            user_content=build_turn_user_content_v1(
                task,
                agent_state,
                outbound_task_state_projector=(
                    self._outbound_task_state_projector
                ),
            ),
            role_seat=str(getattr(task.role, "value", task.role) or "unknown"),
            dialogue_id=str(task.session_id),
            turn_id=str(task.task_id),
            dialogue_phase=str(getattr(task.phase, "value", task.phase) or "unknown"),
        )
        # Backwards-compatible legacy path stays json_object. New benchmark
        # runs inject the exact task-derived CED JSON Schema through the factory.
        response_format = (
            None
            if self._response_format_factory is None
            else self._response_format_factory(task)
        )

        expected_providers = self.expected_provider_display_names
        if not expected_providers:
            # Compatibility for the original Azure harness.  Strict benchmark
            # construction always supplies the exact expected display name.
            expected_providers = ("Azure",)
        try:
            outcome = execute_bounded_text_turn_v1(
            policy=execution_policy,
            profile=self.profile,
            ledger=self.ledger,
            claim_directory=self.claim_directory,
            max_input_tokens=self.max_input_tokens,
            turn=turn,
            response_format_override=response_format,
            expected_returned_models=self.expected_returned_models,
            expected_provider_display_names=expected_providers,
            task=task,
            pre_dispatch_guard=self._pre_dispatch_guard,
            dispatch=self._dispatcher(),
            )
        except Exception as exc:
            # A refusal before the dispatch boundary still has to appear in the
            # evidence exactly once.  Without this, the attempt raised straight
            # past the append and vanished from the artifact entirely.
            record = getattr(exc, PRE_DISPATCH_RECORD_ATTRIBUTE_V1, None)
            if record is not None:
                self.turn_records.append(record)
            raise
        self.turn_records.append(outcome.record)
        self.last_raw_response = outcome.raw_response_body
        if outcome.failure_reason is not None:
            raise RuntimeError(outcome.failure_reason)
        if outcome.assistant_text is None:
            raise RuntimeError("no_assistant_content")
        return outcome.assistant_text

    async def generate_agent_move(
        self, task: AgentTask, agent_state: AgentState
    ) -> ProviderResponse:
        start = time.perf_counter()
        # Substituted once, before anything downstream reads the task, so the
        # render and the pre-dispatch guard both see the same object.
        task = _with_objection_rulings_v1(task)
        # Recorded because request sizes cannot answer this. Two runs of the
        # same council diverge on their own - the seat answers differ, and every
        # later prompt inherits the difference - so a bigger body is not
        # evidence that a ruling was carried. The count is.
        carried_rulings = len(
            (task.context or {}).get(OBJECTION_RULING_CONTEXT_KEY_V1) or ()
        )
        if not self.is_available():
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.MISSING_KEY,
                error_message="live provider unavailable",
            )
        try:
            raw = await self._produce_raw_text(task, agent_state)
        except Exception as exc:  # noqa: BLE001 - a bounded provider failure
            return ProviderResponse(
                provider_id=self.provider_id,
                agent_id=task.agent_id,
                status=ProviderStatus.ERROR,
                error_message=safe_public_exception_code_v1(
                    exc, context="provider_turn"
                ),
                latency_ms=round((time.perf_counter() - start) * 1000, 3),
            )
        meta: Dict[str, Any] = {}
        provider_valid: Optional[bool] = None
        provider_error: Optional[str] = None
        if self._structured_output_validator is not None:
            try:
                self._structured_output_validator(task, raw)
                provider_valid = True
            except Exception as exc:  # provider-schema evidence, not CED authority
                provider_valid = False
                provider_error = safe_public_exception_code_v1(
                    exc, context="structured_output"
                )
        move, status, err = parse_and_validate_move(
            raw,
            task,
            repair_attempts=self.ced_parse_repair_attempts,
            meta=meta,
        )
        if move is not None and status is ProviderStatus.OK:
            _record_objection_ruling_v1(task, move.content)
        accepted = status is ProviderStatus.OK
        # Semantic contribution floor.
        #
        # `parse_and_validate_move` accepts any non-empty string, so a seat that
        # cannot meet a move contract can fill every required field with one
        # letter and be recorded as contributing.  That is not hypothetical:
        # four open-weight seats returned `{"question": "M"}` and
        # `{"commitments": ["S", "R", "T"]}` and every one was accepted.
        #
        # The floor is applied here rather than in the CED acceptance authority
        # because `provider_registry`, `socratic` and `ced` are all under the
        # canonical-successor blob lock, and moving it there is a deliberate
        # change to frozen core that needs its own authorization.  Enforcing it
        # at this adapter keeps CED semantics untouched: a move that asserts
        # nothing never reaches the council at all, so `ced_move_accepted`
        # stops meaning "was syntactically well-formed".
        semantic_floor_rejected = False
        if accepted:
            try:
                assert_move_content_floor(json.loads(raw).get("content"))
            except SemanticFloorError:
                semantic_floor_rejected = True
            except (ValueError, AttributeError):
                pass  # raw already parsed once above; nothing new to learn here
        if semantic_floor_rejected:
            move = None
            status = ProviderStatus.SCHEMA_ERROR
            accepted = False
        rejection_code = (
            None
            if accepted
            else _safe_ced_rejection_code_v1(
                status,
                err,
                semantic_floor_rejected=semantic_floor_rejected,
            )
        )
        if self.turn_records:
            last = self.turn_records[-1]
            updated = last.model_dump(mode="python", exclude={"record_id"})
            updated.update(
                {
                    "provider_structured_output_valid": provider_valid,
                    "provider_structured_output_error": provider_error,
                    "ced_move_accepted": accepted,
                    "ced_rejection_reason": rejection_code,
                }
            )
            self.turn_records[-1] = OpenRouterTurnRecordV1(**updated)
        if self.turn_records:
            record_id = self.turn_records[-1].record_id
            self.__dict__.setdefault("_rulings_in_context_v1", {})[
                record_id
            ] = carried_rulings
            self.__dict__.setdefault("_attempt_meaning_v1", {})[record_id] = {
                "attempt_index": task.attempt_index,
                "failure_class": (
                    None if accepted
                    else attempt_failure_class_v1(task.attempt_index)
                ),
            }
        return ProviderResponse(
            provider_id=self.provider_id,
            agent_id=task.agent_id,
            status=status,
            raw_text=raw,
            parsed_move=move,
            error_message=rejection_code,
            latency_ms=round((time.perf_counter() - start) * 1000, 3),
            repair_attempted=meta.get("repair_attempted", False),
            repair_succeeded=meta.get("repair_succeeded", False),
        )

    def observability_rows(self) -> List[Dict[str, Any]]:
        """Per-turn rows for a live view. No credentials, no reasoning traces."""
        carried = self.__dict__.get("_rulings_in_context_v1", {})
        rows = []
        for record in self.turn_records:
            row = record.model_dump(mode="json", exclude_none=False)
            row["objection_rulings_in_context"] = carried.get(record.record_id, 0)
            meaning = self.__dict__.get("_attempt_meaning_v1", {}).get(
                record.record_id, {}
            )
            row["attempt_index"] = meaning.get("attempt_index")
            row["attempt_failure_class"] = meaning.get("failure_class")
            rows.append(row)
        return rows

    def session_totals(self) -> Dict[str, Any]:
        return {
            "calls_consumed": self.ledger.calls_consumed,
            "call_limit": self.ledger.authorization.maximum_calls,
            "settled_picodollars": self.ledger.settled_picodollars,
            "unsettled_reserved_picodollars": (
                self.ledger.unsettled_reserved_picodollars
            ),
            "observed_picodollars": self.ledger.observed_picodollars,
            "fatal_failure": self.ledger.fatal_failure,
            "total_ceiling_picodollars": (
                self.ledger.authorization.maximum_total_spend_picodollars
            ),
        }


__all__ = [
    "RETURNED_IDENTITY_ABSENT_FAILURE_V1",
    "RETURNED_IDENTITY_FATAL_FAILURES_V1",
    "RETURNED_MODEL_AND_PROVIDER_MISMATCH_V1",
    "OpenRouterBoundedTextOutcomeV1",
    "OutboundTaskStateProjectorV1",
    "PreDispatchGuardV1",
    "ResponseFormatFactoryV1",
    "StructuredOutputValidatorV1",
    "TaskExecutionPolicyFactoryV1",
    "SocratesLiveOpenRouterAdapter",
    "build_turn_user_content_v1",
    "execute_bounded_text_turn_v1",
    "safe_public_exception_code_v1",
    "sanitize_public_assistant_output_v1",
]
