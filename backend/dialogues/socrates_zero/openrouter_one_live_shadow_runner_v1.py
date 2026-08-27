"""S7B: assemble the live preflight, then execute at most one shadow call.

The preflight is a pure function of its inputs — including the raw model-detail
bytes — so the offline dry run and the live run travel the *same* code path.
The only difference is where those bytes came from. That is what makes the
frozen implementation the one that actually dispatches.

Nothing here interprets a response, prices a call, or decides a ceiling. It
composes frozen S7A/S6/S5 contracts and stops when one of them refuses.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .contracts import ContractValidationError
from .openrouter_live_request_overlay_v2 import (
    OpenRouterOperatorScopeV1,
    build_openrouter_live_request_safety_overlay_v2,
    build_openrouter_operator_price_ceiling_v1,
    derive_openrouter_live_request_modality_binding_v1,
    derive_openrouter_output_bound_evidence_v2,
    render_openrouter_live_request_v2,
)
from .openrouter_live_safety_closure_v1 import (
    FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
    FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1,
    OpenRouterCredentialAvailabilityV1,
    OpenRouterJitCredentialPresenceAttestationV1,
    OpenRouterLiveSafetyModeV1,
    OpenRouterOneLiveCallVerdictV1,
    attest_openrouter_claim_store_readiness_v1,
    attest_openrouter_transport_readiness_v1,
    build_openrouter_one_shot_transport_policy_v1,
    build_openrouter_operator_total_spend_ceiling_v1,
    compute_openrouter_worst_case_cost_bound_v1,
    consume_openrouter_one_call_authorization_v1,
    evaluate_one_live_call_preflight_v1,
)
from .openrouter_one_live_shadow_v1 import (
    OpenRouterOperatorPriceGrantV1,
    OpenRouterOperatorTotalSpendGrantV1,
    dispatch_openrouter_one_live_inference_v1,
)
from .openrouter_route_controls_renderer import prepare_openrouter_route_request_v1
from .openrouter_trusted_input_bound_v1 import (
    OpenRouterInputLimitSourceScopeV1,
    build_openrouter_p17_input_bound_proof_v1,
    build_trusted_model_input_limit_record_from_response_v1,
)

OPENROUTER_LIVE_BOUNDED_TIMEOUT_SECONDS_V1 = 30


def live_wire_payload_v1(rendered_request) -> Tuple[bytes, dict]:
    """The exact bytes and semantic headers the frozen request authorizes.

    The digest is re-derived from the bytes about to be sent and checked against
    the registered one, so "registered bytes == sent bytes" is proven at the
    dispatch boundary rather than assumed. The headers come from the request's
    own canonical header JSON: nothing optional is added, and Authorization is
    injected later by the transport and never appears here.
    """
    body_bytes = rendered_request.canonical_body_json.encode("utf-8")
    if hashlib.sha256(body_bytes).hexdigest() != rendered_request.body_sha256:
        raise ContractValidationError(
            "rendered body bytes do not reproduce the registered digest"
        )
    if len(body_bytes) != rendered_request.body_length:
        raise ContractValidationError(
            "rendered body bytes do not reproduce the registered length"
        )
    headers = json.loads(rendered_request.canonical_semantic_headers_json)
    if not isinstance(headers, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in headers.items()
    ):
        raise ContractValidationError("semantic headers must be string-to-string")
    if any(name.lower() == "authorization" for name in headers):
        raise ContractValidationError(
            "the frozen semantic headers must not carry Authorization"
        )
    return body_bytes, headers


@dataclass(frozen=True)
class S7BPreflightBundleV1:
    """Every artifact the preflight produced, and its verdict."""

    prepared: object
    price_policy: object
    overlay: object
    rendered_request: object
    output_bound: object
    modality_binding: object
    limit_record: object
    p17_proof: object
    total_spend_ceiling: object
    cost_bound: object
    transport_policy: object
    transport_readiness: object
    credential_presence: object
    claim_store_readiness: object
    preflight_result: object

    @property
    def authorized(self) -> bool:
        return (
            self.preflight_result.verdict
            is OpenRouterOneLiveCallVerdictV1.AUTHORIZED_FOR_ONE_CALL
        )


def build_s7b_preflight_v1(
    *,
    model_detail_bytes: bytes,
    preflight_execution_id: str,
    repository_root: Path,
    claim_directory: Path,
    price_grant: OpenRouterOperatorPriceGrantV1,
    total_grant: OpenRouterOperatorTotalSpendGrantV1,
    claim_store_evidence_id: str,
    credential_present: bool,
    mode: OpenRouterLiveSafetyModeV1,
    source_scope: OpenRouterInputLimitSourceScopeV1,
    synthetic_fixture_id: Optional[str] = None,
) -> S7BPreflightBundleV1:
    """Assemble the whole preflight from operator grants and JIT bytes.

    Every value that could cost money comes from an operator grant; every value
    that could bound a token count comes from the JIT response. This function
    supplies neither.
    """
    operator_scope = (
        OpenRouterOperatorScopeV1.LIVE_OPERATOR
        if mode is OpenRouterLiveSafetyModeV1.LIVE_JIT
        else OpenRouterOperatorScopeV1.SYNTHETIC_FIXTURE
    )

    prepared = prepare_openrouter_route_request_v1(repository_root=repository_root)
    price_policy = build_openrouter_operator_price_ceiling_v1(
        prepared,
        operator_scope=operator_scope,
        authorized=True,
        authorization_evidence_id=price_grant.grant_id,
        prompt_usd_per_million_tokens=price_grant.prompt_usd_per_million_tokens,
        completion_usd_per_million_tokens=(
            price_grant.completion_usd_per_million_tokens
        ),
        request_usd=price_grant.request_usd,
    )
    overlay = build_openrouter_live_request_safety_overlay_v2(prepared, price_policy)
    rendered_request = render_openrouter_live_request_v2(prepared, overlay)
    output_bound = derive_openrouter_output_bound_evidence_v2(rendered_request)
    modality_binding = derive_openrouter_live_request_modality_binding_v1(
        rendered_request
    )

    limit_record = build_trusted_model_input_limit_record_from_response_v1(
        raw_response_bytes=model_detail_bytes,
        preflight_execution_id=preflight_execution_id,
        source_scope=source_scope,
        synthetic_fixture_id=synthetic_fixture_id,
    )
    p17_proof = build_openrouter_p17_input_bound_proof_v1(
        limit_record=limit_record,
        preflight_execution_id=preflight_execution_id,
        overlay=overlay,
        rendered_request=rendered_request,
        modality_binding=modality_binding,
        output_bound=output_bound,
        provider_policy=price_policy,
    )

    total_spend_ceiling = build_openrouter_operator_total_spend_ceiling_v1(
        rendered_request,
        price_policy,
        operator_scope=operator_scope,
        authorized=True,
        authorization_evidence_id=total_grant.grant_id,
        max_spend_picodollars=total_grant.max_spend_picodollars,
    )
    cost_bound = compute_openrouter_worst_case_cost_bound_v1(
        rendered_request,
        p17_proof,
        output_bound,
        price_policy,
        modality_binding,
        total_spend_ceiling,
    )

    transport_policy = build_openrouter_one_shot_transport_policy_v1(
        rendered_request,
        bounded_timeout_seconds=OPENROUTER_LIVE_BOUNDED_TIMEOUT_SECONDS_V1,
    )
    transport_readiness = attest_openrouter_transport_readiness_v1(
        transport_policy,
        preflight_execution_id=preflight_execution_id,
        ready=True,
    )
    credential_presence = OpenRouterJitCredentialPresenceAttestationV1(
        preflight_execution_id=preflight_execution_id,
        credential_available=(
            OpenRouterCredentialAvailabilityV1.YES
            if credential_present
            else OpenRouterCredentialAvailabilityV1.NO
        ),
    )
    claim_store_readiness = attest_openrouter_claim_store_readiness_v1(
        claim_directory,
        preflight_execution_id=preflight_execution_id,
        mode=mode,
        ready=True,
        authorization_evidence_id=claim_store_evidence_id,
    )

    preflight_result = evaluate_one_live_call_preflight_v1(
        mode=mode,
        preflight_execution_id=preflight_execution_id,
        rendered_request=rendered_request,
        p17_proof=p17_proof,
        output_bound=output_bound,
        price_policy=price_policy,
        modality_binding=modality_binding,
        cost_bound=cost_bound,
        total_spend_ceiling=total_spend_ceiling,
        credential_presence=credential_presence,
        transport_policy=transport_policy,
        transport_readiness=transport_readiness,
        s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
        s6_integration=FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1,
        claim_store_readiness=claim_store_readiness,
        claim_directory=claim_directory,
        ced_authority_enabled=False,
        runtime_authority_enabled=False,
    )
    return S7BPreflightBundleV1(
        prepared=prepared,
        price_policy=price_policy,
        overlay=overlay,
        rendered_request=rendered_request,
        output_bound=output_bound,
        modality_binding=modality_binding,
        limit_record=limit_record,
        p17_proof=p17_proof,
        total_spend_ceiling=total_spend_ceiling,
        cost_bound=cost_bound,
        transport_policy=transport_policy,
        transport_readiness=transport_readiness,
        credential_presence=credential_presence,
        claim_store_readiness=claim_store_readiness,
        preflight_result=preflight_result,
    )


def consume_then_dispatch_s7b_v1(
    bundle: S7BPreflightBundleV1,
    *,
    claim_directory: Path,
):
    """Burn the authorization, then send exactly one request.

    The order is the safety property: consumption precedes dispatch, so a crash
    between them under-executes rather than leaving a reusable authorization
    behind. A provider error afterwards does not restore the claim.
    """
    if not bundle.authorized:
        raise ContractValidationError(
            "preflight did not authorize a call; no dispatch is permitted"
        )
    authorization = bundle.preflight_result.authorization

    consumption = consume_openrouter_one_call_authorization_v1(
        authorization,
        preflight_result=bundle.preflight_result,
        claim_directory=Path(claim_directory),
        rendered_request=bundle.rendered_request,
        p17_proof=bundle.p17_proof,
        output_bound=bundle.output_bound,
        price_policy=bundle.price_policy,
        modality_binding=bundle.modality_binding,
        cost_bound=bundle.cost_bound,
        total_spend_ceiling=bundle.total_spend_ceiling,
        credential_presence=bundle.credential_presence,
        transport_policy=bundle.transport_policy,
        transport_readiness=bundle.transport_readiness,
        s5_mapper=FROZEN_OPENROUTER_S5_MAPPER_CAPABILITY_V1,
        s6_integration=FROZEN_OPENROUTER_S6_INTEGRATION_CAPABILITY_V1,
        claim_store_readiness=bundle.claim_store_readiness,
    )

    body_bytes, headers = live_wire_payload_v1(bundle.rendered_request)
    result = dispatch_openrouter_one_live_inference_v1(
        body_bytes=body_bytes,
        semantic_headers=headers,
        bounded_timeout_seconds=OPENROUTER_LIVE_BOUNDED_TIMEOUT_SECONDS_V1,
    )
    return consumption, result


__all__ = [
    "OPENROUTER_LIVE_BOUNDED_TIMEOUT_SECONDS_V1",
    "S7BPreflightBundleV1",
    "build_s7b_preflight_v1",
    "consume_then_dispatch_s7b_v1",
    "live_wire_payload_v1",
]
