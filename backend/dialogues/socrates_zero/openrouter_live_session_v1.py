"""Normal live test harness: frozen execution policy + dynamic per-turn content.

The scientific phases proved one exact request could be dispatched safely. That
is not a usable system: every new question required a new freeze. This module
separates the two halves so it stops being one.

* **Frozen execution policy** — model, provider selector, fallback, streaming,
  tools, output bound, price ceilings, transport behaviour. Content addressed
  once. A new question never changes it.
* **Dynamic turn content** — system prompt, user content, role, phase, dialogue
  and turn identity. Free to change every turn; each turn simply mints its own
  content-addressed request identity.

Between them sits an **endpoint capability profile**. The first live call failed
with HTTP 404 because the model-level ``supported_parameters`` is the *union*
across endpoints: it advertised ``max_tokens`` while the pinned endpoint
``azure/swedencentral`` accepts only ``max_completion_tokens``, and
``require_parameters`` then emptied the candidate set. The profile records what
that one endpoint actually supports, and the renderer emits the parameter the
endpoint names rather than the one the model family advertises.

Spending is bounded twice. A session authorization caps calls and total spend;
beneath it each turn still mints and atomically consumes its own single-use
claim, so the per-request one-shot protection proven in the pilot is automated
rather than removed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ContractValidationError, canonical_json, stable_contract_id

OPENROUTER_EXECUTION_POLICY_SCHEMA_V1 = (
    "socrateszero-openrouter-execution-policy/v1"
)
OPENROUTER_ENDPOINT_PROFILE_SCHEMA_V1 = (
    "socrateszero-openrouter-endpoint-profile/v1"
)
OPENROUTER_DYNAMIC_TURN_SCHEMA_V1 = (
    "socrateszero-openrouter-dynamic-turn-request/v1"
)
OPENROUTER_RENDERED_TURN_SCHEMA_V1 = (
    "socrateszero-openrouter-rendered-turn/v1"
)
OPENROUTER_SESSION_AUTHORIZATION_SCHEMA_V1 = (
    "socrateszero-openrouter-live-test-session-authorization/v1"
)
OPENROUTER_TURN_RECORD_SCHEMA_V1 = "socrateszero-openrouter-turn-record/v1"

PICODOLLARS_PER_USD = 10**12

#: What the pinned endpoint actually accepts, taken from the retained first-party
#: endpoint listing rather than from the model-level union that misled the pilot.
FROZEN_AZURE_SWEDENCENTRAL_SUPPORTED_PARAMETERS_V1: Tuple[str, ...] = (
    "max_completion_tokens",
    "response_format",
    "seed",
    "structured_outputs",
    "temperature",
    "tool_choice",
    "tools",
    "top_p",
)

#: Body keys the router does not treat as a capability-checked parameter. The
#: successful live call carried all three, which is the evidence for this set.
FROZEN_NON_CAPABILITY_BODY_KEYS_V1: Tuple[str, ...] = (
    "messages",
    "model",
    "provider",
    "stream",
)


class _FrozenLiveContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _nonblank(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{label} must be nonblank text")
    return value


# ----------------------------------------------------- endpoint profile -----


class OpenRouterEndpointCapabilityProfileV1(_FrozenLiveContract):
    """What one pinned endpoint accepts, and which output parameter it names.

    Exists because the model-level capability union is not a safe substitute
    when ``provider.only`` pins a single endpoint.
    """

    schema_version: Literal[
        OPENROUTER_ENDPOINT_PROFILE_SCHEMA_V1
    ] = OPENROUTER_ENDPOINT_PROFILE_SCHEMA_V1
    provider_selector: str = Field(min_length=1)
    canonical_model_observed: str = Field(min_length=1)
    supported_parameters: Tuple[str, ...]
    output_limit_parameter: str = Field(min_length=1)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    profile_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterEndpointCapabilityProfileV1":
        if self.output_limit_parameter not in self.supported_parameters:
            raise ContractValidationError(
                "the output-limit parameter must be one the endpoint supports"
            )
        expected = stable_contract_id(
            "szorendpointprofilev1",
            self.model_dump(mode="json", exclude={"profile_id"}),
        )
        if self.profile_id not in (None, expected):
            raise ContractValidationError("endpoint profile ID mismatch")
        object.__setattr__(self, "profile_id", expected)
        return self


#: The route the pilot proved, with the digest of the endpoint listing that
#: established it.
FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1 = OpenRouterEndpointCapabilityProfileV1(
    provider_selector="azure/swedencentral",
    canonical_model_observed="openai/gpt-4.1-mini-2025-04-14",
    supported_parameters=FROZEN_AZURE_SWEDENCENTRAL_SUPPORTED_PARAMETERS_V1,
    output_limit_parameter="max_completion_tokens",
    evidence_sha256=(
        "73d8f9131da4652f2437cd48cb961c60b559970a64e85d0d2dab2835bc177046"
    ),
)


# ------------------------------------------------------ execution policy -----


class OpenRouterFrozenExecutionPolicyV1(_FrozenLiveContract):
    """Everything a new question must never change.

    Content addressed, so a turn record can prove which policy produced it and a
    reviewer can see at a glance that no question altered the routing, the
    ceilings or the retry semantics.
    """

    schema_version: Literal[
        OPENROUTER_EXECUTION_POLICY_SCHEMA_V1
    ] = OPENROUTER_EXECUTION_POLICY_SCHEMA_V1
    model: str = Field(min_length=1)
    provider_only: Tuple[str, ...]
    provider_order: Tuple[str, ...]
    allow_fallbacks: Literal[False] = False
    require_parameters: Literal[True] = True
    stream: Literal[False] = False
    tools_enabled: Literal[False] = False
    output_limit_tokens: int = Field(gt=0, le=32768)
    # ``None`` is an explicit instruction to omit temperature from the wire.
    # Some exact endpoints (notably OpenAI Flex) do not advertise that
    # parameter.  Keeping 0.0 as the default preserves the proven Azure route.
    temperature: Optional[float] = 0.0
    # Optional and capability-checked.  The reduced Flex benchmark uses seed=0
    # because that exact endpoint advertises seed but not temperature.
    seed: Optional[int] = None
    response_format_type: Literal["json_object", "text"] = "json_object"
    max_price_prompt_usd_per_million: str = Field(min_length=1)
    max_price_completion_usd_per_million: str = Field(min_length=1)
    max_price_request_usd: str = Field(min_length=1)
    bounded_timeout_seconds: int = Field(gt=0, le=120)
    maximum_local_dispatches: Literal[1] = 1
    automatic_retries: Literal[0] = 0
    policy_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def refuse_float_money(cls, data):
        if isinstance(data, dict):
            for field in (
                "max_price_prompt_usd_per_million",
                "max_price_completion_usd_per_million",
                "max_price_request_usd",
            ):
                value = data.get(field)
                if value is not None and type(value) is not str:
                    raise ContractValidationError(
                        f"{field} must be a decimal string: float money is not "
                        "an authority"
                    )
        return data

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterFrozenExecutionPolicyV1":
        if self.provider_only != self.provider_order:
            raise ContractValidationError(
                "provider only and order must pin the same endpoint"
            )
        identity_payload = self.model_dump(mode="json", exclude={"policy_id"})
        # Preserve every historical v1 policy identity.  ``seed`` was added as
        # an omitted-wire extension; its None default did not exist in the
        # original contract payload and therefore must not perturb old IDs.
        if self.seed is None:
            identity_payload.pop("seed", None)
        expected = stable_contract_id(
            "szorexecutionpolicyv1", identity_payload
        )
        if self.policy_id not in (None, expected):
            raise ContractValidationError("execution policy ID mismatch")
        object.__setattr__(self, "policy_id", expected)
        return self


def validate_policy_against_profile_v1(
    policy: OpenRouterFrozenExecutionPolicyV1,
    profile: OpenRouterEndpointCapabilityProfileV1,
) -> Tuple[str, ...]:
    """Refuse a policy that would emit a parameter this endpoint rejects.

    Runs once when a session is built, not per turn: the parameter set is part
    of the frozen half and cannot drift as questions change. Returns the
    capability-checked keys it verified, so a caller can show its work.
    """
    if type(policy) is not OpenRouterFrozenExecutionPolicyV1:
        raise ContractValidationError("capability check requires the exact policy")
    if type(profile) is not OpenRouterEndpointCapabilityProfileV1:
        raise ContractValidationError("capability check requires the exact profile")
    if tuple(policy.provider_only) != (profile.provider_selector,):
        raise ContractValidationError(
            "policy pins a different endpoint than the capability profile"
        )
    emitted = [profile.output_limit_parameter, "response_format"]
    if policy.temperature is not None:
        emitted.append("temperature")
    if policy.seed is not None:
        emitted.append("seed")
    if policy.tools_enabled:
        emitted.extend(["tools", "tool_choice"])
    unsupported = [
        name for name in emitted if name not in profile.supported_parameters
    ]
    if unsupported:
        raise ContractValidationError(
            f"endpoint {profile.provider_selector} does not support "
            f"{sorted(unsupported)}; refusing before any inference"
        )
    return tuple(emitted)


# --------------------------------------------------------- dynamic turn -----


class OpenRouterDynamicTurnRequestV1(_FrozenLiveContract):
    """Everything a turn is free to change.

    No field here can reach the execution policy: the renderer composes them
    into the message array and nowhere else.
    """

    schema_version: Literal[
        OPENROUTER_DYNAMIC_TURN_SCHEMA_V1
    ] = OPENROUTER_DYNAMIC_TURN_SCHEMA_V1
    system_prompt: str = Field(min_length=1)
    user_content: str = Field(min_length=1)
    role_seat: str = Field(min_length=1)
    dialogue_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    dialogue_phase: str = Field(min_length=1)
    prior_state_digest: Optional[str] = None
    turn_content_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterDynamicTurnRequestV1":
        expected = stable_contract_id(
            "szordynamicturnv1",
            self.model_dump(mode="json", exclude={"turn_content_id"}),
        )
        if self.turn_content_id not in (None, expected):
            raise ContractValidationError("dynamic turn content ID mismatch")
        object.__setattr__(self, "turn_content_id", expected)
        return self


class OpenRouterRenderedTurnV1(_FrozenLiveContract):
    """One turn's exact wire bytes and their identity."""

    schema_version: Literal[
        OPENROUTER_RENDERED_TURN_SCHEMA_V1
    ] = OPENROUTER_RENDERED_TURN_SCHEMA_V1
    policy_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    turn_content_id: str = Field(min_length=1)
    canonical_body_json: str = Field(min_length=1)
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(gt=0)
    semantic_headers_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterRenderedTurnV1":
        body = self.canonical_body_json.encode("utf-8")
        if hashlib.sha256(body).hexdigest() != self.body_sha256:
            raise ContractValidationError("rendered turn digest does not match")
        if len(body) != self.body_length:
            raise ContractValidationError("rendered turn length does not match")
        expected = stable_contract_id(
            "szorturnrequestv1",
            {
                "policy_id": self.policy_id,
                "profile_id": self.profile_id,
                "turn_content_id": self.turn_content_id,
                "body_sha256": self.body_sha256,
            },
        )
        if self.request_id not in (None, expected):
            raise ContractValidationError("rendered turn request ID mismatch")
        object.__setattr__(self, "request_id", expected)
        return self


FROZEN_LIVE_SEMANTIC_HEADERS_V1: Tuple[Tuple[str, str], ...] = (
    ("Content-Type", "application/json"),
    ("X-OpenRouter-Cache", "false"),
    ("X-OpenRouter-Metadata", "enabled"),
)


def render_dynamic_turn_v1(
    policy: OpenRouterFrozenExecutionPolicyV1,
    profile: OpenRouterEndpointCapabilityProfileV1,
    turn: OpenRouterDynamicTurnRequestV1,
    *,
    response_format_override: Optional[Mapping[str, Any]] = None,
) -> OpenRouterRenderedTurnV1:
    """Compose frozen policy with dynamic content into exact wire bytes.

    The output-limit parameter is named by the *profile*, not by the policy, so
    a route whose endpoint calls it something else is served correctly without
    touching the policy.
    """
    validate_policy_against_profile_v1(policy, profile)

    response_format: Mapping[str, Any]
    if response_format_override is None:
        response_format = {"type": policy.response_format_type}
    else:
        if not isinstance(response_format_override, Mapping):
            raise ContractValidationError(
                "response-format override must be a JSON object"
            )
        candidate = dict(response_format_override)
        json_schema = candidate.get("json_schema")
        if candidate.get("type") != "json_schema" or not isinstance(
            json_schema, Mapping
        ):
            raise ContractValidationError(
                "response-format override must use json_schema"
            )
        if json_schema.get("strict") is not True:
            raise ContractValidationError(
                "response-format override must set json_schema.strict=true"
            )
        if not isinstance(json_schema.get("name"), str) or not str(
            json_schema["name"]
        ).strip():
            raise ContractValidationError(
                "response-format override must name its schema"
            )
        schema = json_schema.get("schema")
        if not isinstance(schema, Mapping) or schema.get("type") != "object":
            raise ContractValidationError(
                "response-format override must carry an object JSON Schema"
            )
        if schema.get("additionalProperties") is not False:
            raise ContractValidationError(
                "strict response schema must forbid root additional properties"
            )
        # Canonicalization below is the final JSON-serializability check.  Make
        # a detached JSON value so a caller cannot mutate the sealed body later.
        try:
            response_format = json.loads(canonical_json(candidate))
        except (TypeError, ValueError) as exc:
            raise ContractValidationError(
                "response-format override is not canonical JSON"
            ) from exc

    body = {
        "messages": [
            {"content": turn.system_prompt, "role": "system"},
            {"content": turn.user_content, "role": "user"},
        ],
        "model": policy.model,
        "provider": {
            "allow_fallbacks": policy.allow_fallbacks,
            "max_price": {
                "completion": policy.max_price_completion_usd_per_million,
                "prompt": policy.max_price_prompt_usd_per_million,
                "request": policy.max_price_request_usd,
            },
            "only": list(policy.provider_only),
            "order": list(policy.provider_order),
            "require_parameters": policy.require_parameters,
        },
        "response_format": response_format,
        "stream": policy.stream,
        profile.output_limit_parameter: policy.output_limit_tokens,
    }
    if policy.temperature is not None:
        body["temperature"] = policy.temperature
    if policy.seed is not None:
        body["seed"] = policy.seed
    if policy.tools_enabled:
        raise ContractValidationError(
            "tools are disabled in this harness; enabling them is a policy change"
        )

    canonical = canonical_json(body)
    encoded = canonical.encode("utf-8")
    header_json = canonical_json(dict(FROZEN_LIVE_SEMANTIC_HEADERS_V1))
    return OpenRouterRenderedTurnV1(
        policy_id=policy.policy_id or "",
        profile_id=profile.profile_id or "",
        turn_content_id=turn.turn_content_id or "",
        canonical_body_json=canonical,
        body_sha256=hashlib.sha256(encoded).hexdigest(),
        body_length=len(encoded),
        semantic_headers_sha256=hashlib.sha256(
            header_json.encode("utf-8")
        ).hexdigest(),
    )


# --------------------------------------------------- session authorization ---


class OpenRouterLiveTestSessionAuthorizationV1(_FrozenLiveContract):
    """An operator's bounded authorization for a whole test session.

    Authorizes *minting* per-turn claims, never dispatch on its own. Each turn
    still consumes its own single-use claim, so the one-shot protection the
    pilot proved is automated rather than traded away.
    """

    schema_version: Literal[
        OPENROUTER_SESSION_AUTHORIZATION_SCHEMA_V1
    ] = OPENROUTER_SESSION_AUTHORIZATION_SCHEMA_V1
    operator_statement: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider_selector: str = Field(min_length=1)
    maximum_calls: int = Field(gt=0, le=1000)
    maximum_total_spend_picodollars: int = Field(gt=0)
    maximum_per_call_spend_picodollars: int = Field(gt=0)
    session_id: str = Field(min_length=1)
    authorization_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterLiveTestSessionAuthorizationV1":
        if (
            self.maximum_per_call_spend_picodollars
            > self.maximum_total_spend_picodollars
        ):
            raise ContractValidationError(
                "per-call ceiling cannot exceed the session total"
            )
        expected = stable_contract_id(
            "szorlivesessionauthv1",
            self.model_dump(mode="json", exclude={"authorization_id"}),
        )
        if self.authorization_id not in (None, expected):
            raise ContractValidationError("session authorization ID mismatch")
        object.__setattr__(self, "authorization_id", expected)
        return self


class OpenRouterSessionBudgetExceeded(ContractValidationError):
    """Raised before a dispatch that would breach a session bound."""


class OpenRouterSessionFatalError(ContractValidationError):
    """Raised before dispatch after route/retry evidence invalidates a session."""


class OpenRouterSessionLedgerV1:
    """Mutable spend/call accounting for one session. Operational, not evidence.

    Deliberately not content addressed: it is physical state, and replaying
    evidence must never reset it.
    """

    def __init__(
        self, authorization: OpenRouterLiveTestSessionAuthorizationV1
    ) -> None:
        self.authorization = authorization
        self.calls_consumed = 0
        self.settled_picodollars = 0
        self.unsettled_reserved_picodollars = 0
        self.observed_picodollars = 0
        self.fatal_failure: Optional[str] = None

    def trip_fatal(self, reason: str) -> None:
        """Permanently stop later POSTs while retaining the first causal reason."""

        if not isinstance(reason, str) or not reason.strip():
            raise ContractValidationError("fatal session reason must be nonblank")
        if self.fatal_failure is None:
            self.fatal_failure = reason.strip()

    @property
    def committed_picodollars(self) -> int:
        """What the session must assume it has spent right now.

        Settled cost is what the provider actually reported. Anything dispatched
        but not yet reported is carried at its conservative worst case, so an
        in-flight call can never be accounted at zero. Once a call reports, its
        reservation is released and replaced by the truth.
        """
        return self.settled_picodollars + self.unsettled_reserved_picodollars

    def check_admits(self, worst_case_picodollars: int) -> None:
        """Refuse before the network if either session bound would break.

        The per-call ceiling is checked against the *conservative* worst case, so
        no single call can run away regardless of how cheap the session has been
        so far. The session total is checked against settled cost plus anything
        still in flight plus this call's worst case.
        """
        auth = self.authorization
        if self.fatal_failure is not None:
            raise OpenRouterSessionFatalError(
                f"session fatally stopped: {self.fatal_failure}"
            )
        if self.calls_consumed >= auth.maximum_calls:
            raise OpenRouterSessionBudgetExceeded(
                f"session call limit {auth.maximum_calls} reached"
            )
        if worst_case_picodollars > auth.maximum_per_call_spend_picodollars:
            raise OpenRouterSessionBudgetExceeded(
                "worst-case cost exceeds the per-call ceiling"
            )
        projected = self.committed_picodollars + worst_case_picodollars
        if projected > auth.maximum_total_spend_picodollars:
            raise OpenRouterSessionBudgetExceeded(
                "worst-case cost would exceed the session total ceiling"
            )

    def record_dispatch(self, worst_case_picodollars: int) -> None:
        """A dispatch attempt is consumed whether or not it succeeds."""
        self.calls_consumed += 1
        self.unsettled_reserved_picodollars += worst_case_picodollars

    def settle_observed(
        self, observed_picodollars: int, reserved_picodollars: int
    ) -> None:
        """Replace one call's reservation with its reported cost.

        A call that never reports keeps its reservation forever, which is the
        safe direction: an unreported call is assumed expensive, not free.
        """
        self.unsettled_reserved_picodollars = max(
            0, self.unsettled_reserved_picodollars - reserved_picodollars
        )
        self.settled_picodollars += observed_picodollars
        self.observed_picodollars += observed_picodollars


def mint_turn_claim_id_v1(
    session: OpenRouterLiveTestSessionAuthorizationV1,
    rendered: OpenRouterRenderedTurnV1,
) -> str:
    """One claim identity per turn, beneath one session authorization."""
    return "szorturnclaimv1_" + hashlib.sha256(
        canonical_json(
            {
                "session_authorization_id": session.authorization_id,
                "request_id": rendered.request_id,
                "body_sha256": rendered.body_sha256,
            }
        ).encode("utf-8")
    ).hexdigest()


def consume_turn_claim_v1(claim_directory: Path, claim_id: str) -> Path:
    """Atomically burn one turn claim, or refuse.

    Exclusive creation, then fsync. An existing claim is a refusal even when its
    bytes would be identical: the same turn is never dispatched twice.
    """
    if not claim_id.startswith("szorturnclaimv1_") or len(claim_id) != len(
        "szorturnclaimv1_"
    ) + 64:
        raise ContractValidationError("invalid turn claim ID")
    directory = Path(claim_directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{claim_id}.consumed.json"
    try:
        with target.open("xb") as handle:
            handle.write(canonical_json({"claim_id": claim_id}).encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ContractValidationError(
            "turn claim already consumed; no automatic retry is allowed"
        ) from exc
    return target


# ------------------------------------------------------------ observability --


class OpenRouterTurnRecordV1(_FrozenLiveContract):
    """What one turn did, in the terms a reviewer needs.

    No credential, no hidden reasoning trace, no duplicated raw body — digests
    and counts only.
    """

    schema_version: Literal[
        OPENROUTER_TURN_RECORD_SCHEMA_V1
    ] = OPENROUTER_TURN_RECORD_SCHEMA_V1
    dialogue_id: str
    turn_id: str
    role_seat: str
    dialogue_phase: str
    task_kind: Optional[str] = None
    model: str
    provider_selector: str
    request_id: str
    body_sha256: str
    response_body_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    response_body_length: Optional[int] = Field(default=None, ge=0)
    http_status: Optional[int] = None
    transport_completed: bool
    retry_count: int = Field(default=0, ge=0)
    latency_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    observed_cost_picodollars: Optional[int] = None
    observed_cost_usd_decimal: Optional[str] = None
    observed_cost_within_p19_bound: Optional[bool] = None
    committed_cost_within_session_ceiling: Optional[bool] = None
    worst_case_picodollars: int
    actual_served_model: Optional[str] = None
    provider_display_name: Optional[str] = None
    returned_model_binding_ok: Optional[bool] = None
    returned_provider_binding_ok: Optional[bool] = None
    #: Why the served-model authority is what it is. A binding failure reads
    #: identically whether the returned identity was *wrong* or simply never
    #: *present*, and one live incident cost a full audit to tell those apart.
    #: The mapper already knew; these carry what it knew.
    actual_served_model_status: Optional[str] = None
    router_metadata_presence: Optional[str] = None
    #: The operands the comparison actually used. Server-side configuration,
    #: never provider-controlled text.
    expected_model_identity: Optional[str] = None
    expected_provider_identity: Optional[str] = None
    provider_structured_output_valid: Optional[bool] = None
    provider_structured_output_error: Optional[str] = None
    s5_envelope_kind: Optional[str] = None
    s6_binding: Optional[str] = None
    ced_move_accepted: Optional[bool] = None
    ced_rejection_reason: Optional[str] = None
    #: The model's own public output, truncated. Not a reasoning trace and
    #: never a credential: it is what CED itself judged.
    assistant_text_excerpt: Optional[str] = None
    #: Complete public assistant content after credential-shaped substrings have
    #: been redacted.  This is visible output, never a hidden reasoning field.
    assistant_output_sanitized: Optional[str] = None
    assistant_output_sha256: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    failure_class: Optional[str] = None
    record_id: Optional[str] = None

    @model_validator(mode="after")
    def identify(self) -> "OpenRouterTurnRecordV1":
        identity_payload = self.model_dump(
            mode="json", exclude={"record_id", "latency_ms"}
        )
        # New optional evidence enriches future records without invalidating
        # historical v1 identities.  Omitted values and the transport's
        # historical zero-retry invariant are not injected into old payloads.
        for field in (
            "response_body_sha256",
            "response_body_length",
            "task_kind",
            "observed_cost_usd_decimal",
            "observed_cost_within_p19_bound",
            "committed_cost_within_session_ceiling",
            "returned_model_binding_ok",
            "returned_provider_binding_ok",
            "actual_served_model_status",
            "router_metadata_presence",
            "expected_model_identity",
            "expected_provider_identity",
            "provider_structured_output_valid",
            "provider_structured_output_error",
            "assistant_output_sanitized",
            "assistant_output_sha256",
        ):
            if identity_payload.get(field) is None:
                identity_payload.pop(field, None)
        if self.retry_count == 0:
            identity_payload.pop("retry_count", None)
        expected = stable_contract_id(
            "szorturnrecordv1",
            identity_payload,
        )
        if self.record_id not in (None, expected):
            raise ContractValidationError("turn record ID mismatch")
        object.__setattr__(self, "record_id", expected)
        return self


# ------------------------------------------------------------- cost bound ---


def conservative_turn_cost_bound_v1(
    policy: OpenRouterFrozenExecutionPolicyV1,
    max_input_tokens: int,
) -> int:
    """The proven conservative worst case, in integer picodollars.

    Uses the operator's ceilings, not observed prices, and the context-limit
    input bound the JIT preflight established. It is deliberately loose: no
    tighter token bound has been established by evidence, and inventing one to
    make the arithmetic comfortable is exactly what the phase rules forbid.
    """
    from decimal import ROUND_CEILING, Decimal, localcontext

    def per_token(usd_per_million: str) -> int:
        with localcontext() as context:
            context.prec = 60
            scaled = (
                Decimal(usd_per_million) * PICODOLLARS_PER_USD / 1_000_000
            ).quantize(Decimal(1), rounding=ROUND_CEILING)
        return int(scaled)

    def flat(usd: str) -> int:
        with localcontext() as context:
            context.prec = 60
            return int(
                (Decimal(usd) * PICODOLLARS_PER_USD).quantize(
                    Decimal(1), rounding=ROUND_CEILING
                )
            )

    return (
        max_input_tokens * per_token(policy.max_price_prompt_usd_per_million)
        + policy.output_limit_tokens
        * per_token(policy.max_price_completion_usd_per_million)
        + flat(policy.max_price_request_usd)
    )


__all__ = [
    "FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1",
    "FROZEN_AZURE_SWEDENCENTRAL_SUPPORTED_PARAMETERS_V1",
    "FROZEN_LIVE_SEMANTIC_HEADERS_V1",
    "FROZEN_NON_CAPABILITY_BODY_KEYS_V1",
    "OpenRouterDynamicTurnRequestV1",
    "OpenRouterEndpointCapabilityProfileV1",
    "OpenRouterFrozenExecutionPolicyV1",
    "OpenRouterLiveTestSessionAuthorizationV1",
    "OpenRouterRenderedTurnV1",
    "OpenRouterSessionBudgetExceeded",
    "OpenRouterSessionFatalError",
    "OpenRouterSessionLedgerV1",
    "OpenRouterTurnRecordV1",
    "conservative_turn_cost_bound_v1",
    "consume_turn_claim_v1",
    "mint_turn_claim_id_v1",
    "render_dynamic_turn_v1",
    "validate_policy_against_profile_v1",
]
