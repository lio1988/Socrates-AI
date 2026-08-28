"""Pure contracts for the controlled structured-output Socratic experiment.

This is deliberately an experiment surface, not a new CED schema or execution
phase.  The provider-facing JSON Schema is generated from a strict Pydantic
wire model whose enums are the existing CED enums, and parity checks bind its
field sets to the frozen recorded-observation surface.  Returned text still
travels through the unchanged CED parser and Socratic firewall.

No function in this module reads credentials, touches the network, writes a
file, or dispatches a model call.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from typing import Any, Dict, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..agent import SocraticAgent
from ..ced import CEDOrchestrator
from ..ced_canonical_successor_contracts import (
    RECORDED_SOCRATIC_CONTENT_FIELDS,
    RECORDED_SOCRATIC_ENVELOPE_FIELDS,
)
from ..models import (
    AgentState,
    AgentTask,
    DialogPhase,
    EpistemicMarker,
    ProviderResponse,
    ProviderStatus,
    TaskKind,
)
from ..provider_registry import (
    CouncilProviderRegistry,
    FakeProvider,
    parse_and_validate_move,
)
from ..reasoning_prompts import build_reasoning_system_prompt
from ..socratic import MaieuticOperator, validate_socratic_content
from .contracts import ContractValidationError, canonical_json, stable_contract_id
from .openrouter_live_session_adapter_v1 import build_turn_user_content_v1
from .openrouter_live_session_v1 import (
    FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1,
    OpenRouterDynamicTurnRequestV1,
    OpenRouterFrozenExecutionPolicyV1,
    render_dynamic_turn_v1,
)


CONTROL_QUESTION_V1 = "Is knowledge merely justified true belief?"
CONTROL_SESSION_ID_V1 = "socrates-live-1787878466"
CONTROL_TASK_ID_V1 = "task_c53c0c317cc0"
CONTROL_AGENT_ID_V1 = "agent_3"
CONTROL_PROVIDER_ID_V1 = "live_seat_1"
CONTROL_MODEL_V1 = "openai/gpt-4.1-mini"
FULL_MODEL_V1 = "openai/gpt-4.1"
CONTROL_PROVIDER_SELECTOR_V1 = "azure/swedencentral"
CONTROL_OUTPUT_TOKENS_V1 = 256
CONTROL_TIMEOUT_SECONDS_V1 = 30

CONTROL_SYSTEM_PROMPT_SHA256_V1 = (
    "4488425fa6e791b6dc35962994372772f111f8e8c5bbe1f36b7f477bb4113914"
)
CONTROL_PROMPT_ONLY_BODY_SHA256_V1 = (
    "e4326be947ff2314d9b4ec5e33341cbc597a191396cb2357c23e90764ea9cc50"
)
CONTROL_PROMPT_ONLY_REQUEST_ID_V1 = (
    "szorturnrequestv1_"
    "d5564cedd491b21cb690fe085b6ed880534ae4f7497256611813555c429e80d5"
)

STRUCTURED_SCHEMA_NAME_V1 = "ced_socratic_opening_move"
STRUCTURED_REQUEST_SCHEMA_V1 = (
    "socrateszero-openrouter-structured-socratic-request/v1"
)
PICODOLLARS_PER_USD = 10**12

_OPENING_CONTENT_FIELDS = frozenset(
    {"question", "operator", "epistemic_marker"}
)
_REQUIRED_ENDPOINT_PARAMETERS = frozenset(
    {"response_format", "structured_outputs", "temperature"}
)


class _StrictWireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CedOpeningSocraticContentV1(_StrictWireModel):
    """The phase-specific content CED accepts for an opening question."""

    question: str = Field(min_length=1, pattern=r"\S")
    operator: MaieuticOperator
    epistemic_marker: EpistemicMarker


class CedOpeningSocraticMoveV1(_StrictWireModel):
    """The frozen provider-visible opening envelope, before CED-owned fields."""

    content: CedOpeningSocraticContentV1
    confidence: float = Field(ge=0.0, le=1.0)


def ced_opening_response_format_v1() -> Dict[str, Any]:
    """Generate the exact provider wrapper from the strict CED wire model."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": STRUCTURED_SCHEMA_NAME_V1,
            "strict": True,
            "schema": CedOpeningSocraticMoveV1.model_json_schema(),
        },
    }


def ced_opening_schema_sha256_v1() -> str:
    return hashlib.sha256(
        canonical_json(ced_opening_response_format_v1()).encode("utf-8")
    ).hexdigest()


def _resolve_local_ref(schema: Mapping[str, Any], node: Mapping[str, Any]):
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return node
    if not ref.startswith("#/"):
        raise ContractValidationError("structured schema contains a non-local ref")
    current: Any = schema
    for part in ref[2:].split("/"):
        if not isinstance(current, Mapping) or part not in current:
            raise ContractValidationError("structured schema contains a broken ref")
        current = current[part]
    if not isinstance(current, Mapping):
        raise ContractValidationError("structured schema ref is not an object")
    return current


def assert_ced_opening_schema_parity_v1() -> None:
    """Prove field, enum, nesting, and canonical-parser parity.

    The generic legacy parser accepts some noncanonical supersets (for example
    it defaults an absent confidence).  This schema intentionally binds the
    stricter frozen recorded-observation surface used for canonical evidence.
    """

    wrapper = ced_opening_response_format_v1()
    if set(wrapper) != {"type", "json_schema"}:
        raise ContractValidationError("response_format wrapper fields drifted")
    if wrapper["type"] != "json_schema":
        raise ContractValidationError("response_format is not strict JSON Schema")
    config = wrapper["json_schema"]
    if set(config) != {"name", "strict", "schema"} or config["strict"] is not True:
        raise ContractValidationError("strict JSON Schema wrapper drifted")

    schema = config["schema"]
    outer_properties = schema.get("properties")
    if not isinstance(outer_properties, Mapping):
        raise ContractValidationError("structured schema lacks outer properties")
    outer_fields = frozenset(outer_properties)
    if outer_fields != RECORDED_SOCRATIC_ENVELOPE_FIELDS:
        raise ContractValidationError("outer fields differ from frozen CED evidence")
    if frozenset(schema.get("required") or ()) != outer_fields:
        raise ContractValidationError("every outer field must be required")
    if schema.get("additionalProperties") is not False:
        raise ContractValidationError("outer additional properties must be false")
    if "epistemic_marker" in outer_properties:
        raise ContractValidationError("epistemic_marker must never be top-level")

    content_schema = _resolve_local_ref(schema, outer_properties["content"])
    content_properties = content_schema.get("properties")
    if not isinstance(content_properties, Mapping):
        raise ContractValidationError("structured schema lacks content properties")
    content_fields = frozenset(content_properties)
    if content_fields != _OPENING_CONTENT_FIELDS:
        raise ContractValidationError("opening content fields drifted")
    if not content_fields <= RECORDED_SOCRATIC_CONTENT_FIELDS:
        raise ContractValidationError("opening fields exceed frozen CED evidence")
    if frozenset(content_schema.get("required") or ()) != content_fields:
        raise ContractValidationError("every opening content field must be required")
    if content_schema.get("additionalProperties") is not False:
        raise ContractValidationError("content additional properties must be false")

    operator_schema = _resolve_local_ref(schema, content_properties["operator"])
    marker_schema = _resolve_local_ref(
        schema, content_properties["epistemic_marker"]
    )
    if set(operator_schema.get("enum") or ()) != {
        item.value for item in MaieuticOperator
    }:
        raise ContractValidationError("operator enum differs from CED")
    if set(marker_schema.get("enum") or ()) != {
        item.value for item in EpistemicMarker
    }:
        raise ContractValidationError("marker enum differs from CED")

    sample = canonical_json(
        {
            "content": {
                "question": "What distinction would change what follows?",
                "operator": "distinguish",
                "epistemic_marker": "open_uncertainty",
            },
            "confidence": 0.5,
        }
    )
    CedOpeningSocraticMoveV1.model_validate_json(sample, strict=True)
    fixture = build_control_opening_fixture_v1()
    move, status, error = parse_and_validate_move(sample, fixture.task)
    if status is not ProviderStatus.OK or move is None or error is not None:
        raise ContractValidationError("schema-valid sample failed the CED parser")
    validation = validate_socratic_content(move.content, followup=False)
    if not validation.accepted:
        raise ContractValidationError("schema-valid sample failed Socratic content")


class _RosterAdapter:
    """Offline-only roster identity used to reconstruct the preserved task."""

    provider_name = "OpenRouter (control reconstruction)"
    is_fake = False

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        self.model = CONTROL_MODEL_V1
        self.model_id = CONTROL_MODEL_V1

    def is_available(self) -> bool:
        return True

    def authoritative_model_id(self) -> str:
        return self.model_id

    async def generate_agent_move(self, task, agent_state):  # pragma: no cover
        raise RuntimeError("offline roster adapter cannot dispatch")


@dataclass(frozen=True)
class ControlOpeningFixtureV1:
    ced: CEDOrchestrator
    state: Any
    task: AgentTask
    agent_state: AgentState


def build_control_opening_fixture_v1() -> ControlOpeningFixtureV1:
    """Reconstruct the exact substantive task used by control run 003."""

    registry = CouncilProviderRegistry()
    registry.register(_RosterAdapter("live_seat_0"))
    registry.register(_RosterAdapter("live_seat_1"))
    fake = FakeProvider()
    agents = [SocraticAgent(f"agent_{index}", fake) for index in range(4)]
    ced = CEDOrchestrator(agents, fake, registry=registry)
    state = ced.create_session(CONTROL_QUESTION_V1, session_id=CONTROL_SESSION_ID_V1)
    specs = ced._prepare_registry_phase(state, DialogPhase.OPENING)
    if len(specs) != 1:
        raise ContractValidationError("control opening no longer has exactly one task")
    task = ced._build_registry_phase_task(
        state, DialogPhase.OPENING, specs[0], 0
    ).model_copy(update={"task_id": CONTROL_TASK_ID_V1})
    if (
        task.agent_id != CONTROL_AGENT_ID_V1
        or task.role.value != "socrates"
        or task.phase is not DialogPhase.OPENING
        or task.task_kind is not TaskKind.SOCRATIC_QUESTION
        or task.round_number != 0
        or task.slot_index != 0
        or task.attempt_index != 0
    ):
        raise ContractValidationError("control opening task semantics drifted")
    return ControlOpeningFixtureV1(
        ced=ced,
        state=state,
        task=task,
        agent_state=state.agent_states[task.agent_id],
    )


def assert_prompt_only_control_reconstruction_v1() -> None:
    """Refuse unless current code reproduces the preserved run-003 request."""

    fixture = build_control_opening_fixture_v1()
    system_prompt = build_reasoning_system_prompt(
        fixture.task.role,
        fixture.task.phase,
        fixture.task.task_kind,
        model=CONTROL_MODEL_V1,
    )
    if hashlib.sha256(system_prompt.encode("utf-8")).hexdigest() != (
        CONTROL_SYSTEM_PROMPT_SHA256_V1
    ):
        raise ContractValidationError("control system prompt no longer reproduces")
    turn = OpenRouterDynamicTurnRequestV1(
        system_prompt=system_prompt,
        user_content=build_turn_user_content_v1(fixture.task, fixture.agent_state),
        role_seat="socrates",
        dialogue_id=CONTROL_SESSION_ID_V1,
        turn_id=CONTROL_TASK_ID_V1,
        dialogue_phase="opening",
    )
    policy = OpenRouterFrozenExecutionPolicyV1(
        model=CONTROL_MODEL_V1,
        provider_only=(CONTROL_PROVIDER_SELECTOR_V1,),
        provider_order=(CONTROL_PROVIDER_SELECTOR_V1,),
        output_limit_tokens=CONTROL_OUTPUT_TOKENS_V1,
        max_price_prompt_usd_per_million="0.50",
        max_price_completion_usd_per_million="2.00",
        max_price_request_usd="0",
        bounded_timeout_seconds=CONTROL_TIMEOUT_SECONDS_V1,
    )
    rendered = render_dynamic_turn_v1(
        policy, FROZEN_AZURE_SWEDENCENTRAL_PROFILE_V1, turn
    )
    if rendered.body_sha256 != CONTROL_PROMPT_ONLY_BODY_SHA256_V1:
        raise ContractValidationError("control body no longer reproduces")
    if rendered.request_id != CONTROL_PROMPT_ONLY_REQUEST_ID_V1:
        raise ContractValidationError("control request identity no longer reproduces")


class ExactEndpointCapabilityV1(_StrictWireModel):
    requested_model: str
    data_model: str
    endpoint_model: str
    endpoint_name: str
    provider_selector: str
    provider_name: str
    status: int
    supported_parameters: Tuple[str, ...]
    output_limit_parameter: str
    maximum_output_tokens: int
    context_length: int
    prompt_price_usd_per_token: str
    completion_price_usd_per_token: str
    request_price_usd: Optional[str] = None
    listing_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    listing_length: int = Field(gt=0)


def _exact_nonnegative_decimal(value: Any, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ContractValidationError(f"{label} must be an exact decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ContractValidationError(f"{label} is malformed") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ContractValidationError(f"{label} must be finite and nonnegative")
    return value


def parse_exact_endpoint_capability_v1(
    raw_bytes: bytes,
    *,
    requested_model: str,
    provider_selector: str = CONTROL_PROVIDER_SELECTOR_V1,
) -> ExactEndpointCapabilityV1:
    """Validate one exact endpoint record, never a model-level union."""

    if requested_model not in (CONTROL_MODEL_V1, FULL_MODEL_V1):
        raise ContractValidationError("experiment model is not one of the two arms")
    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        raise ContractValidationError("endpoint evidence must be nonempty bytes")
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContractValidationError("endpoint evidence is not UTF-8 JSON") from exc
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, Mapping) or data.get("id") != requested_model:
        raise ContractValidationError("endpoint listing is for another model")
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list):
        raise ContractValidationError("endpoint listing lacks endpoint records")
    matches = [
        item
        for item in endpoints
        if isinstance(item, Mapping)
        and item.get("tag") == provider_selector
        and item.get("model_id") == requested_model
    ]
    if len(matches) != 1:
        raise ContractValidationError("exact selected endpoint is not unique")
    endpoint = matches[0]
    if type(endpoint.get("status")) is not int or endpoint["status"] != 0:
        raise ContractValidationError("exact selected endpoint is not healthy")
    parameters = endpoint.get("supported_parameters")
    if not isinstance(parameters, list) or not all(
        isinstance(item, str) and item for item in parameters
    ):
        raise ContractValidationError("endpoint parameter list is malformed")
    parameter_set = set(parameters)
    missing = sorted(_REQUIRED_ENDPOINT_PARAMETERS - parameter_set)
    if missing:
        raise ContractValidationError(
            f"exact endpoint lacks required parameters: {missing}"
        )
    if "max_completion_tokens" in parameter_set:
        output_parameter = "max_completion_tokens"
    elif "max_tokens" in parameter_set:
        output_parameter = "max_tokens"
    else:
        raise ContractValidationError("exact endpoint has no output-limit parameter")
    maximum_output = endpoint.get("max_completion_tokens")
    if type(maximum_output) is not int or maximum_output < CONTROL_OUTPUT_TOKENS_V1:
        raise ContractValidationError("endpoint output maximum is below 256")
    context_length = endpoint.get("context_length")
    if type(context_length) is not int or context_length <= 0:
        raise ContractValidationError("endpoint context length is invalid")
    pricing = endpoint.get("pricing")
    if not isinstance(pricing, Mapping):
        raise ContractValidationError("endpoint pricing is absent")
    prompt_price = _exact_nonnegative_decimal(pricing.get("prompt"), "prompt price")
    completion_price = _exact_nonnegative_decimal(
        pricing.get("completion"), "completion price"
    )
    request_price = pricing.get("request")
    if request_price is not None:
        request_price = _exact_nonnegative_decimal(request_price, "request price")
    return ExactEndpointCapabilityV1(
        requested_model=requested_model,
        data_model=str(data["id"]),
        endpoint_model=str(endpoint["model_id"]),
        endpoint_name=str(endpoint.get("name") or ""),
        provider_selector=provider_selector,
        provider_name=str(endpoint.get("provider_name") or ""),
        status=int(endpoint["status"]),
        supported_parameters=tuple(parameters),
        output_limit_parameter=output_parameter,
        maximum_output_tokens=maximum_output,
        context_length=context_length,
        prompt_price_usd_per_token=prompt_price,
        completion_price_usd_per_token=completion_price,
        request_price_usd=request_price,
        listing_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        listing_length=len(raw_bytes),
    )


class StructuredArmPriceCeilingsV1(_StrictWireModel):
    prompt_usd_per_million_tokens: str
    completion_usd_per_million_tokens: str
    request_usd: str

    @field_validator(
        "prompt_usd_per_million_tokens",
        "completion_usd_per_million_tokens",
        "request_usd",
    )
    @classmethod
    def validate_decimal(cls, value: str, info) -> str:
        return _exact_nonnegative_decimal(value, info.field_name)


class StructuredArmRenderedRequestV1(_StrictWireModel):
    schema_version: str = STRUCTURED_REQUEST_SCHEMA_V1
    requested_model: str
    provider_selector: str
    output_limit_parameter: str
    output_limit_tokens: int
    response_schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    system_prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    user_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dialogue_context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    body_length: int = Field(gt=0)
    canonical_body_json: str
    request_id: str


def validate_endpoint_prices_within_operator_ceilings_v1(
    endpoint: ExactEndpointCapabilityV1,
    ceilings: StructuredArmPriceCeilingsV1,
) -> None:
    prompt_per_million = Decimal(endpoint.prompt_price_usd_per_token) * 1_000_000
    completion_per_million = (
        Decimal(endpoint.completion_price_usd_per_token) * 1_000_000
    )
    if prompt_per_million > Decimal(ceilings.prompt_usd_per_million_tokens):
        raise ContractValidationError("endpoint prompt price exceeds operator ceiling")
    if completion_per_million > Decimal(
        ceilings.completion_usd_per_million_tokens
    ):
        raise ContractValidationError(
            "endpoint completion price exceeds operator ceiling"
        )
    if endpoint.request_price_usd is not None and Decimal(
        endpoint.request_price_usd
    ) > Decimal(ceilings.request_usd):
        raise ContractValidationError("endpoint request price exceeds operator ceiling")


def conservative_arm_cost_bound_picodollars_v1(
    endpoint: ExactEndpointCapabilityV1,
    ceilings: StructuredArmPriceCeilingsV1,
) -> int:
    def per_token(value: str) -> int:
        with localcontext() as context:
            context.prec = 60
            return int(
                (
                    Decimal(value) * PICODOLLARS_PER_USD / 1_000_000
                ).quantize(Decimal(1), rounding=ROUND_CEILING)
            )

    with localcontext() as context:
        context.prec = 60
        request = int(
            (Decimal(ceilings.request_usd) * PICODOLLARS_PER_USD).quantize(
                Decimal(1), rounding=ROUND_CEILING
            )
        )
    return (
        endpoint.context_length
        * per_token(ceilings.prompt_usd_per_million_tokens)
        + CONTROL_OUTPUT_TOKENS_V1
        * per_token(ceilings.completion_usd_per_million_tokens)
        + request
    )


def render_structured_arm_request_v1(
    *,
    model: str,
    endpoint: ExactEndpointCapabilityV1,
    ceilings: StructuredArmPriceCeilingsV1,
) -> StructuredArmRenderedRequestV1:
    """Render the controlled arm while preserving the exact control task."""

    assert_ced_opening_schema_parity_v1()
    assert_prompt_only_control_reconstruction_v1()
    if model != endpoint.requested_model:
        raise ContractValidationError("arm model differs from endpoint evidence")
    validate_endpoint_prices_within_operator_ceilings_v1(endpoint, ceilings)
    fixture = build_control_opening_fixture_v1()
    system_prompt = build_reasoning_system_prompt(
        fixture.task.role,
        fixture.task.phase,
        fixture.task.task_kind,
        model=model,
    )
    user_content = build_turn_user_content_v1(fixture.task, fixture.agent_state)
    response_format = ced_opening_response_format_v1()
    body = {
        "messages": [
            {"content": system_prompt, "role": "system"},
            {"content": user_content, "role": "user"},
        ],
        "model": model,
        "provider": {
            "allow_fallbacks": False,
            "max_price": {
                "completion": ceilings.completion_usd_per_million_tokens,
                "prompt": ceilings.prompt_usd_per_million_tokens,
                "request": ceilings.request_usd,
            },
            "only": [CONTROL_PROVIDER_SELECTOR_V1],
            "order": [CONTROL_PROVIDER_SELECTOR_V1],
            "require_parameters": True,
        },
        "response_format": response_format,
        "stream": False,
        "temperature": 0.0,
        endpoint.output_limit_parameter: CONTROL_OUTPUT_TOKENS_V1,
    }
    canonical = canonical_json(body)
    encoded = canonical.encode("utf-8")
    body_sha = hashlib.sha256(encoded).hexdigest()
    request_id = stable_contract_id(
        "szorstructuredrequestv1",
        {
            "model": model,
            "provider_selector": CONTROL_PROVIDER_SELECTOR_V1,
            "body_sha256": body_sha,
            "response_schema_sha256": ced_opening_schema_sha256_v1(),
        },
    )
    return StructuredArmRenderedRequestV1(
        requested_model=model,
        provider_selector=CONTROL_PROVIDER_SELECTOR_V1,
        output_limit_parameter=endpoint.output_limit_parameter,
        output_limit_tokens=CONTROL_OUTPUT_TOKENS_V1,
        response_schema_sha256=ced_opening_schema_sha256_v1(),
        system_prompt_sha256=hashlib.sha256(
            system_prompt.encode("utf-8")
        ).hexdigest(),
        user_content_sha256=hashlib.sha256(
            user_content.encode("utf-8")
        ).hexdigest(),
        dialogue_context_sha256=hashlib.sha256(
            canonical_json(fixture.task.context).encode("utf-8")
        ).hexdigest(),
        body_sha256=body_sha,
        body_length=len(encoded),
        canonical_body_json=canonical,
        request_id=request_id,
    )


def evaluate_raw_move_through_ced_v1(
    raw_text: Optional[str],
    *,
    provider_id: str = CONTROL_PROVIDER_ID_V1,
) -> Dict[str, Any]:
    """Measure provider schema, CED schema, and Socratic acceptance separately."""

    observed: Dict[str, Any] = {
        "question": None,
        "operator": None,
        "epistemic_marker": None,
        "top_level_epistemic_marker": None,
        "confidence": None,
    }
    try:
        raw_value = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        raw_value = None
    if isinstance(raw_value, Mapping):
        raw_content = raw_value.get("content")
        if isinstance(raw_content, Mapping):
            observed["question"] = raw_content.get("question")
            observed["operator"] = raw_content.get("operator")
            observed["epistemic_marker"] = raw_content.get("epistemic_marker")
        observed["top_level_epistemic_marker"] = raw_value.get(
            "epistemic_marker"
        )
        observed["confidence"] = raw_value.get("confidence")

    provider_valid = True
    provider_error: Optional[str] = None
    wire: Optional[CedOpeningSocraticMoveV1] = None
    try:
        wire = CedOpeningSocraticMoveV1.model_validate_json(raw_text, strict=True)
    except Exception as exc:  # the exact validation error is evidence
        provider_valid = False
        provider_error = f"{type(exc).__name__}: {exc}"

    fixture = build_control_opening_fixture_v1()
    meta: Dict[str, Any] = {}
    move, status, error = parse_and_validate_move(
        raw_text, fixture.task, meta=meta
    )
    response = ProviderResponse(
        provider_id=provider_id,
        agent_id=fixture.task.agent_id,
        status=status,
        raw_text=raw_text,
        parsed_move=move,
        error_message=error,
        repair_attempted=bool(meta.get("repair_attempted", False)),
        repair_succeeded=bool(meta.get("repair_succeeded", False)),
    )
    dispatch: list[Dict[str, Any]] = []
    application = fixture.ced._apply_registry_response(
        fixture.state,
        DialogPhase.OPENING,
        fixture.task,
        response,
        dispatch,
    )
    audit_rows = fixture.ced._socratic_audit_rows.get(
        fixture.state.session_id, []
    )
    audit = audit_rows[-1] if audit_rows else None
    return {
        "provider_structured_output_valid": provider_valid,
        "provider_structured_output_error": provider_error,
        "ced_schema_accepted": status is ProviderStatus.OK,
        "ced_schema_status": status.value,
        "ced_schema_reason": error,
        "ced_repair_attempted": bool(meta.get("repair_attempted", False)),
        "ced_repair_succeeded": bool(meta.get("repair_succeeded", False)),
        "socratic_move_accepted": application.accepted_move_id is not None,
        "accepted_move_id": application.accepted_move_id,
        "canonical_rejection_kind": application.canonical_rejection_kind,
        "canonical_rejection_reason": application.canonical_rejection_reason,
        "socratic_audit": audit,
        # Observation is deliberately separate from authority.  Invalid output
        # still has reportable raw fields, but only the three acceptance flags
        # above decide whether any of them count as an accepted move.
        "provider_validated_fields": (
            {
                "question": wire.content.question,
                "operator": wire.content.operator.value,
                "epistemic_marker": wire.content.epistemic_marker.value,
                "confidence": wire.confidence,
            }
            if wire is not None
            else None
        ),
        "raw_field_observation": dict(observed),
        **observed,
    }


__all__ = [
    "CONTROL_AGENT_ID_V1",
    "CONTROL_MODEL_V1",
    "CONTROL_OUTPUT_TOKENS_V1",
    "CONTROL_PROMPT_ONLY_BODY_SHA256_V1",
    "CONTROL_PROMPT_ONLY_REQUEST_ID_V1",
    "CONTROL_PROVIDER_SELECTOR_V1",
    "CONTROL_QUESTION_V1",
    "CONTROL_SESSION_ID_V1",
    "CONTROL_SYSTEM_PROMPT_SHA256_V1",
    "CONTROL_TASK_ID_V1",
    "CONTROL_TIMEOUT_SECONDS_V1",
    "CedOpeningSocraticMoveV1",
    "ExactEndpointCapabilityV1",
    "FULL_MODEL_V1",
    "PICODOLLARS_PER_USD",
    "StructuredArmPriceCeilingsV1",
    "StructuredArmRenderedRequestV1",
    "assert_ced_opening_schema_parity_v1",
    "assert_prompt_only_control_reconstruction_v1",
    "build_control_opening_fixture_v1",
    "ced_opening_response_format_v1",
    "ced_opening_schema_sha256_v1",
    "conservative_arm_cost_bound_picodollars_v1",
    "evaluate_raw_move_through_ced_v1",
    "parse_exact_endpoint_capability_v1",
    "render_structured_arm_request_v1",
    "validate_endpoint_prices_within_operator_ceilings_v1",
]
