"""Run one approved Q2 CED diagnostic with a 4096-token output ceiling.

The exact provider-bound Q2 Socratic-opening request from the persisted reduced
benchmark is the source of truth.  This harness changes one root field only:
``max_tokens`` from 1024 to 4096.  It has a separate stable run latch, separate
turn-claim store, one POST maximum, zero retries, and distinct write-once
artifacts.  No reasoning text is ever persisted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.dialogues.agent import SocraticAgent
from backend.dialogues.ced import CEDOrchestrator
from backend.dialogues.models import (
    AgentState,
    AgentTask,
    DialogPhase,
    ProviderResponse,
    ProviderStatus,
    TaskKind,
)
from backend.dialogues.provider_registry import (
    CouncilProviderRegistry,
    FakeProvider,
    parse_and_validate_move,
)
from backend.dialogues.socrates_zero.ced_structured_output_v1 import (
    ced_structured_response_format_v1,
    validate_ced_structured_output_v1,
)
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    sanitize_public_assistant_output_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    FROZEN_LIVE_SEMANTIC_HEADERS_V1,
    OpenRouterDynamicTurnRequestV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterRenderedTurnV1,
    OpenRouterSessionLedgerV1,
    conservative_turn_cost_bound_v1,
    consume_turn_claim_v1,
    mint_turn_claim_id_v1,
    render_dynamic_turn_v1,
    validate_policy_against_profile_v1,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    dispatch_openrouter_one_live_inference_v1,
    openrouter_credential_is_present_v1,
)
from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
    REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1,
    REDUCED_MAX_INPUT_TOKENS_V1,
    REDUCED_MODEL_V1,
    REDUCED_PROVIDER_DISPLAY_NAME_V1,
    REDUCED_PROVIDER_SELECTOR_V1,
    build_reduced_flex_policy_v1,
    fetch_flex_endpoint_listing_once_v1,
    flex_profile_from_evidence_v1,
    validate_flex_endpoint_listing_v1,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUN_DIRECTORY = (
    REPOSITORY_ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-openrouter-live-routing-repair-v1"
    / "runs"
)
PRIOR_COLLECTION_PATH = RUN_DIRECTORY / "reduced_benchmark_collection_v1.json"
DEFAULT_COLLECTION_PATH = RUN_DIRECTORY / "q2_ced_4096_diagnostic_collection_v1.json"
DEFAULT_REPORT_PATH = RUN_DIRECTORY / "Q2_CED_4096_DIAGNOSTIC_REPORT.md"
DIAGNOSTIC_LATCH_DIRECTORY = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    r"\openrouter-q2-ced-4096-diagnostic-run-attempt-v1"
)
DIAGNOSTIC_CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    r"\openrouter-q2-ced-4096-diagnostic-claim-store-v1"
)

DIAGNOSTIC_SCHEMA_VERSION_V1 = "q2-ced-4096-one-call-diagnostic/v1"
REQUIRED_CLI_FLAG_V1 = "--execute-approved-one-call-diagnostic"
OPERATOR_STATEMENT_V1 = (
    "Approved one-call Q2 CED 4096-token diagnostic; zero retries; cumulative "
    "prior benchmark observed cost plus conservative diagnostic reservation "
    "must remain within the existing $8.00 hard ceiling."
)
PRIOR_COLLECTION_SHA256_V1 = (
    "939e01d7fd1b1b4d1e09e0a7b40a1a3d973ed2570467c7dec3035fe50bb243b7"
)
PRIOR_CED_BODY_SHA256_V1 = (
    "8a758dedda1614b46845c79ceab63de102e75a8b9ca5358cdc74ee190b415800"
)
DIAGNOSTIC_BODY_SHA256_V1 = (
    "51ec1776f26b2de5f0b0218be12d8a514beff6f208036d7e4edb0fadd8601e13"
)
PRIOR_AND_DIAGNOSTIC_BODY_LENGTH_V1 = 20_083
PRIOR_MESSAGES_SHA256_V1 = (
    "51c59ef1a33a38e32bb662afd545982303a8a712d67b5e3ad1b452511845a74a"
)
PRIOR_RESPONSE_FORMAT_SHA256_V1 = (
    "3b109661b3aad8dde75dcb534a4751dd7601c33c828f9ded64a8b57680278174"
)
PRIOR_PROVIDER_SHA256_V1 = (
    "545605a7f0ab409d6392498b6773dc6f639aa70c306644aa12905f9fc8cb7bf1"
)
PRIOR_SYSTEM_PROMPT_SHA256_V1 = (
    "f6d85b8b914bbdc7163721b8bfe6e9e173a7307e0b1878101866b5c1c4352479"
)
PRIOR_USER_CONTENT_SHA256_V1 = (
    "c4b4e48a11d85e662a280cdafd0cee80e3d18cdabe50bc033f1f557cdf023e60"
)
Q2_QUESTION_SHA256_V1 = (
    "1726f5eed7d420c512e247b9f984830315c9641c72ef1f9a6d55fe606d782ce4"
)
PRIOR_OBSERVED_COST_PICODOLLARS_V1 = 4_614_375_000
PRIOR_OBSERVED_COST_USD_V1 = "0.004614375"
DIAGNOSTIC_MAX_OUTPUT_TOKENS_V1 = 4096
DIAGNOSTIC_WORST_CASE_PICODOLLARS_V1 = 54_096_000_000
DIAGNOSTIC_WORST_CASE_USD_V1 = "0.054096"
CUMULATIVE_PRIOR_PLUS_RESERVATION_PICODOLLARS_V1 = 58_710_375_000
CUMULATIVE_PRIOR_PLUS_RESERVATION_USD_V1 = "0.058710375"

_SAFE_TOKEN_DETAIL_FIELDS_V1 = frozenset(
    {
        "accepted_prediction_tokens",
        "audio_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "cached_tokens",
        "image_tokens",
        "reasoning_tokens",
        "rejected_prediction_tokens",
        "text_tokens",
    }
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _canonical_digest(value: Any) -> str:
    return _sha256_text(canonical_json(value))


def _write_once(path: Path, value: Any) -> str:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ContractValidationError(f"write-once artifact already exists: {target}")
    if target.suffix.lower() == ".md":
        encoded = str(value).encode("utf-8")
    else:
        encoded = (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )
            + "\n"
        ).encode("utf-8")
    try:
        with target.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ContractValidationError(
            f"write-once artifact already exists: {target}"
        ) from exc
    return _sha256_bytes(encoded)


@dataclass(frozen=True)
class PriorQ2CedRequestV1:
    canonical_body_json: str
    body: Dict[str, Any]
    task: AgentTask
    agent_state: AgentState
    collection_sha256: str
    prior_observed_picodollars: int


@dataclass(frozen=True)
class DiagnosticPreparedV1:
    prior: PriorQ2CedRequestV1
    policy: OpenRouterFrozenExecutionPolicyV1
    profile: Any
    rendered: OpenRouterRenderedTurnV1
    endpoint_evidence: Any
    selected_endpoint: Dict[str, Any]
    parity: Dict[str, Any]
    manifest: Dict[str, Any]
    session: OpenRouterLiveTestSessionAuthorizationV1
    worst_case_picodollars: int


def _extract_embedded_task_state_v1(
    body: Mapping[str, Any],
) -> Tuple[AgentTask, AgentState]:
    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) != 2:
        raise ContractValidationError("persisted CED body must contain two messages")
    user = messages[1]
    if not isinstance(user, Mapping) or not isinstance(user.get("content"), str):
        raise ContractValidationError("persisted CED user content is absent")
    parts = user["content"].split("\n", 1)
    if len(parts) != 2:
        raise ContractValidationError("persisted CED user payload separator drifted")
    try:
        payload = json.loads(parts[1])
        task = AgentTask.model_validate(payload["task"])
        agent_state = AgentState.model_validate(payload["agent_state"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractValidationError(
            "persisted CED embedded task/state cannot be reconstructed"
        ) from exc
    return task, agent_state


def load_prior_q2_ced_request_v1(
    path: Path = PRIOR_COLLECTION_PATH,
) -> PriorQ2CedRequestV1:
    source = Path(path).resolve()
    raw = source.read_bytes()
    collection_sha = _sha256_bytes(raw)
    if collection_sha != PRIOR_COLLECTION_SHA256_V1:
        raise ContractValidationError("persisted reduced benchmark collection drifted")
    collection = json.loads(raw.decode("utf-8"))
    if collection.get("result") != "COLLECTION_COMPLETE":
        raise ContractValidationError("prior reduced benchmark did not complete")
    observed = (collection.get("ledger") or {}).get("observed_picodollars")
    if observed != PRIOR_OBSERVED_COST_PICODOLLARS_V1:
        raise ContractValidationError("prior observed benchmark cost drifted")
    if Decimal(PRIOR_OBSERVED_COST_USD_V1) * Decimal(10**12) != Decimal(observed):
        raise ContractValidationError("prior observed cost decimal is inconsistent")

    turns = (collection.get("homogeneous_q2") or {}).get("turns") or []
    matching_turns = [
        row
        for row in turns
        if isinstance(row, Mapping)
        and row.get("task_kind") == TaskKind.SOCRATIC_QUESTION.value
        and row.get("body_sha256") == PRIOR_CED_BODY_SHA256_V1
    ]
    if len(matching_turns) != 1:
        raise ContractValidationError("unique prior Q2 CED turn is unavailable")
    body_records = (collection.get("wire_evidence") or {}).get("body_records") or []
    matching_bodies = [
        row
        for row in body_records
        if isinstance(row, Mapping)
        and row.get("body_sha256") == PRIOR_CED_BODY_SHA256_V1
    ]
    if len(matching_bodies) != 1:
        raise ContractValidationError("unique prior Q2 CED body is unavailable")
    row = matching_bodies[0]
    canonical = row.get("canonical_body")
    if not isinstance(canonical, str):
        raise ContractValidationError("prior Q2 CED canonical body is absent")
    if _sha256_text(canonical) != PRIOR_CED_BODY_SHA256_V1:
        raise ContractValidationError("prior Q2 CED body digest mismatch")
    if len(canonical.encode("utf-8")) != PRIOR_AND_DIAGNOSTIC_BODY_LENGTH_V1:
        raise ContractValidationError("prior Q2 CED body length mismatch")
    body = json.loads(canonical)
    if canonical_json(body) != canonical:
        raise ContractValidationError("prior Q2 CED body is not canonical JSON")
    expected_root_keys = {
        "max_tokens",
        "messages",
        "model",
        "provider",
        "response_format",
        "seed",
        "stream",
    }
    if set(body) != expected_root_keys:
        raise ContractValidationError("prior Q2 CED root fields drifted")
    if body["max_tokens"] != 1024:
        raise ContractValidationError("prior Q2 CED output ceiling is not 1024")
    if body["model"] != REDUCED_MODEL_V1:
        raise ContractValidationError("prior Q2 CED model drifted")
    if body["seed"] != 0 or body["stream"] is not False:
        raise ContractValidationError("prior Q2 CED sampling/stream fields drifted")
    if any(key in body for key in ("reasoning", "reasoning_effort", "include_reasoning")):
        raise ContractValidationError("prior Q2 CED unexpectedly emitted reasoning")
    if _canonical_digest(body["messages"]) != PRIOR_MESSAGES_SHA256_V1:
        raise ContractValidationError("prior Q2 CED messages drifted")
    if _canonical_digest(body["response_format"]) != PRIOR_RESPONSE_FORMAT_SHA256_V1:
        raise ContractValidationError("prior Q2 CED response schema drifted")
    if _canonical_digest(body["provider"]) != PRIOR_PROVIDER_SHA256_V1:
        raise ContractValidationError("prior Q2 CED provider policy drifted")
    if _sha256_text(body["messages"][0]["content"]) != PRIOR_SYSTEM_PROMPT_SHA256_V1:
        raise ContractValidationError("prior Q2 CED system prompt drifted")
    if _sha256_text(body["messages"][1]["content"]) != PRIOR_USER_CONTENT_SHA256_V1:
        raise ContractValidationError("prior Q2 CED user context drifted")

    task, agent_state = _extract_embedded_task_state_v1(body)
    if (
        task.task_kind is not TaskKind.SOCRATIC_QUESTION
        or task.phase is not DialogPhase.OPENING
        or _sha256_text(task.question) != Q2_QUESTION_SHA256_V1
        or agent_state.agent_id != task.agent_id
    ):
        raise ContractValidationError("prior embedded Q2 opening task drifted")
    # This body was rendered before the CED acceptance contract gained its
    # semantic contribution floor, so its `response_format` legitimately differs
    # from the one generated today. The retained bytes are already pinned exactly
    # by PRIOR_RESPONSE_FORMAT_SHA256_V1 above, which is the integrity guard;
    # re-deriving the schema here would additionally freeze the live contract
    # against every future tightening, which is not this diagnostic's job.
    # What must still hold is that the historical schema targets this task.
    current = canonical_json(ced_structured_response_format_v1(task))
    if json.loads(current)["json_schema"]["name"] != (
        body["response_format"]["json_schema"]["name"]
    ):
        raise ContractValidationError(
            "prior provider schema targets a different CED task contract"
        )
    return PriorQ2CedRequestV1(
        canonical_body_json=canonical,
        body=body,
        task=task,
        agent_state=agent_state,
        collection_sha256=collection_sha,
        prior_observed_picodollars=observed,
    )


def build_diagnostic_policy_v1() -> OpenRouterFrozenExecutionPolicyV1:
    base = build_reduced_flex_policy_v1()
    payload = base.model_dump(mode="python", exclude={"policy_id"})
    payload["output_limit_tokens"] = DIAGNOSTIC_MAX_OUTPUT_TOKENS_V1
    return OpenRouterFrozenExecutionPolicyV1(**payload)


def _deep_differences_v1(
    left: Any, right: Any, path: str = "$"
) -> List[Dict[str, Any]]:
    if type(left) is not type(right):
        return [{"path": path, "before": left, "after": right}]
    if isinstance(left, Mapping):
        rows: List[Dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            nested = f"{path}.{key}"
            if key not in left:
                rows.append({"path": nested, "before": "<ABSENT>", "after": right[key]})
            elif key not in right:
                rows.append({"path": nested, "before": left[key], "after": "<ABSENT>"})
            else:
                rows.extend(_deep_differences_v1(left[key], right[key], nested))
        return rows
    if isinstance(left, list):
        if len(left) != len(right):
            return [{"path": path, "before": left, "after": right}]
        rows = []
        for index, (before, after) in enumerate(zip(left, right, strict=True)):
            rows.extend(_deep_differences_v1(before, after, f"{path}[{index}]"))
        return rows
    return [] if left == right else [{"path": path, "before": left, "after": right}]


def build_diagnostic_body_v1(
    prior: PriorQ2CedRequestV1,
    policy: OpenRouterFrozenExecutionPolicyV1,
    profile: Any,
) -> Tuple[OpenRouterRenderedTurnV1, Dict[str, Any]]:
    validate_policy_against_profile_v1(policy, profile)
    mechanical = json.loads(prior.canonical_body_json)
    mechanical["max_tokens"] = DIAGNOSTIC_MAX_OUTPUT_TOKENS_V1
    mechanical_canonical = canonical_json(mechanical)
    differences = _deep_differences_v1(prior.body, mechanical)
    expected_difference = [
        {"path": "$.max_tokens", "before": 1024, "after": 4096}
    ]
    if differences != expected_difference:
        raise ContractValidationError(
            f"diagnostic body differs beyond max_tokens: {differences!r}"
        )
    if _sha256_text(mechanical_canonical) != DIAGNOSTIC_BODY_SHA256_V1:
        raise ContractValidationError("diagnostic body digest drifted")
    if len(mechanical_canonical.encode("utf-8")) != (
        PRIOR_AND_DIAGNOSTIC_BODY_LENGTH_V1
    ):
        raise ContractValidationError("diagnostic body length drifted")
    if any(
        key in mechanical
        for key in ("reasoning", "reasoning_effort", "include_reasoning")
    ):
        raise ContractValidationError("reasoning must remain absent")

    turn = OpenRouterDynamicTurnRequestV1(
        system_prompt=prior.body["messages"][0]["content"],
        user_content=prior.body["messages"][1]["content"],
        role_seat="socrates",
        dialogue_id=str(prior.task.session_id),
        turn_id=f"{prior.task.task_id}-4096-diagnostic",
        dialogue_phase=prior.task.phase.value,
        prior_state_digest=PRIOR_CED_BODY_SHA256_V1,
    )
    rendered = render_dynamic_turn_v1(
        policy,
        profile,
        turn,
        response_format_override=prior.body["response_format"],
    )
    if rendered.canonical_body_json != mechanical_canonical:
        raise ContractValidationError(
            "independent policy renderer differs from mechanical one-field edit"
        )
    parity = {
        "proved": True,
        "deep_differences": differences,
        "prior_body_sha256": PRIOR_CED_BODY_SHA256_V1,
        "diagnostic_body_sha256": rendered.body_sha256,
        "prior_body_length": PRIOR_AND_DIAGNOSTIC_BODY_LENGTH_V1,
        "diagnostic_body_length": rendered.body_length,
        "messages_identical": mechanical["messages"] == prior.body["messages"],
        "messages_sha256": _canonical_digest(mechanical["messages"]),
        "response_format_identical": (
            mechanical["response_format"] == prior.body["response_format"]
        ),
        "response_format_sha256": _canonical_digest(mechanical["response_format"]),
        "model_identical": mechanical["model"] == prior.body["model"],
        "provider_policy_identical": (
            mechanical["provider"] == prior.body["provider"]
        ),
        "provider_policy_sha256": _canonical_digest(mechanical["provider"]),
        "seed_identical": mechanical["seed"] == prior.body["seed"] == 0,
        "stream_identical": mechanical["stream"] is prior.body["stream"] is False,
        "question_sha256": _sha256_text(prior.task.question),
        "system_prompt_sha256": _sha256_text(mechanical["messages"][0]["content"]),
        "user_context_sha256": _sha256_text(mechanical["messages"][1]["content"]),
        "reasoning_parameters_absent": True,
    }
    if not all(
        parity[key]
        for key in (
            "messages_identical",
            "response_format_identical",
            "model_identical",
            "provider_policy_identical",
            "seed_identical",
            "stream_identical",
            "reasoning_parameters_absent",
        )
    ):
        raise ContractValidationError("diagnostic body parity proof failed")
    return rendered, parity


def _selected_endpoint_record_v1(raw: bytes) -> Dict[str, Any]:
    payload = json.loads(raw.decode("utf-8"))
    data = payload.get("data") if isinstance(payload, Mapping) else None
    endpoints = data.get("endpoints") if isinstance(data, Mapping) else None
    matches = [
        dict(row)
        for row in (endpoints or [])
        if isinstance(row, Mapping)
        and row.get("tag") == REDUCED_PROVIDER_SELECTOR_V1
        and row.get("model_id") == REDUCED_MODEL_V1
    ]
    if len(matches) != 1:
        raise ContractValidationError("fresh Flex listing lacks one exact endpoint")
    return matches[0]


def stable_diagnostic_attempt_manifest_v1() -> Dict[str, Any]:
    return {
        "schema_version": "q2-ced-4096-diagnostic-run-attempt/v1",
        "operator_statement": OPERATOR_STATEMENT_V1,
        "prior_collection_sha256": PRIOR_COLLECTION_SHA256_V1,
        "prior_body_sha256": PRIOR_CED_BODY_SHA256_V1,
        "diagnostic_body_sha256": DIAGNOSTIC_BODY_SHA256_V1,
        "question_sha256": Q2_QUESTION_SHA256_V1,
        "model": REDUCED_MODEL_V1,
        "provider_selector": REDUCED_PROVIDER_SELECTOR_V1,
        "maximum_calls": 1,
        "automatic_retries": 0,
        "max_tokens": DIAGNOSTIC_MAX_OUTPUT_TOKENS_V1,
        "worst_case_picodollars": DIAGNOSTIC_WORST_CASE_PICODOLLARS_V1,
        "hard_cumulative_ceiling_picodollars": (
            REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1
        ),
    }


def stable_diagnostic_attempt_id_v1() -> str:
    return "szorq2ced4096diagnosticattemptv1_" + _canonical_digest(
        stable_diagnostic_attempt_manifest_v1()
    )


def diagnostic_attempt_latch_path_v1(
    directory: Path = DIAGNOSTIC_LATCH_DIRECTORY,
) -> Path:
    return Path(directory).resolve() / (
        f"{stable_diagnostic_attempt_id_v1()}.consumed.json"
    )


def consume_diagnostic_attempt_latch_v1(
    directory: Path = DIAGNOSTIC_LATCH_DIRECTORY,
) -> Dict[str, Any]:
    attempt_id = stable_diagnostic_attempt_id_v1()
    target_directory = Path(directory).resolve()
    target_directory.mkdir(parents=True, exist_ok=True)
    target = diagnostic_attempt_latch_path_v1(target_directory)
    value = {
        "run_attempt_id": attempt_id,
        "manifest": stable_diagnostic_attempt_manifest_v1(),
        "consumed_utc": _utc_now(),
    }
    encoded = (canonical_json(value) + "\n").encode("utf-8")
    try:
        with target.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ContractValidationError(
            "approved Q2 CED 4096 diagnostic attempt was already consumed"
        ) from exc
    return {
        "run_attempt_id": attempt_id,
        "latch_path": str(target),
        "latch_sha256": _sha256_bytes(encoded),
        "consumed_utc": value["consumed_utc"],
    }


def prepare_diagnostic_v1(
    endpoint_raw: bytes,
    *,
    prior_path: Path = PRIOR_COLLECTION_PATH,
) -> DiagnosticPreparedV1:
    prior = load_prior_q2_ced_request_v1(prior_path)
    endpoint_evidence = validate_flex_endpoint_listing_v1(endpoint_raw)
    selected_endpoint = _selected_endpoint_record_v1(endpoint_raw)
    if endpoint_evidence.maximum_output_tokens < DIAGNOSTIC_MAX_OUTPUT_TOKENS_V1:
        raise ContractValidationError(
            "exact Flex endpoint output maximum is below diagnostic 4096"
        )
    reasoning_parameter_supported = (
        "reasoning" in set(endpoint_evidence.supported_parameters)
    )
    if not reasoning_parameter_supported:
        raise ContractValidationError(
            "exact Flex endpoint no longer reports the previously observed "
            "reasoning parameter; attribution preflight fails closed"
        )
    profile = flex_profile_from_evidence_v1(endpoint_evidence)
    policy = build_diagnostic_policy_v1()
    rendered, parity = build_diagnostic_body_v1(prior, policy, profile)
    worst_case = conservative_turn_cost_bound_v1(
        policy, REDUCED_MAX_INPUT_TOKENS_V1
    )
    if worst_case != DIAGNOSTIC_WORST_CASE_PICODOLLARS_V1:
        raise ContractValidationError(
            f"diagnostic P19 bound drifted: {worst_case} picodollars"
        )
    cumulative = prior.prior_observed_picodollars + worst_case
    if cumulative != CUMULATIVE_PRIOR_PLUS_RESERVATION_PICODOLLARS_V1:
        raise ContractValidationError("cumulative prior-plus-reservation drifted")
    if cumulative > REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1:
        raise ContractValidationError("diagnostic reservation would exceed $8")

    manifest_payload = {
        "schema_version": "q2-ced-4096-diagnostic-authorization-manifest/v1",
        "operator_statement": OPERATOR_STATEMENT_V1,
        "stable_attempt_id": stable_diagnostic_attempt_id_v1(),
        "prior_collection_sha256": prior.collection_sha256,
        "prior_body_sha256": PRIOR_CED_BODY_SHA256_V1,
        "diagnostic_body_sha256": rendered.body_sha256,
        "question_sha256": _sha256_text(prior.task.question),
        "response_format_sha256": _canonical_digest(
            prior.body["response_format"]
        ),
        "policy_id": policy.policy_id,
        "profile_id": profile.profile_id,
        "model": REDUCED_MODEL_V1,
        "provider_selector": REDUCED_PROVIDER_SELECTOR_V1,
        "endpoint_output_limit_parameter": (
            endpoint_evidence.output_limit_parameter
        ),
        "endpoint_maximum_output_tokens": (
            endpoint_evidence.maximum_output_tokens
        ),
        "endpoint_reasoning_parameter_supported": (
            reasoning_parameter_supported
        ),
        "reasoning_behavior": (
            "UNCHANGED_OMITTED_FROM_PRIOR_AND_DIAGNOSTIC_REQUEST"
        ),
        "maximum_calls": 1,
        "automatic_retries": 0,
        "prior_observed_picodollars": prior.prior_observed_picodollars,
        "diagnostic_worst_case_picodollars": worst_case,
        "cumulative_prior_plus_reservation_picodollars": cumulative,
        "hard_cumulative_ceiling_picodollars": (
            REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1
        ),
    }
    manifest_digest = _canonical_digest(manifest_payload)
    manifest = {
        **manifest_payload,
        "authorization_manifest_sha256": manifest_digest,
    }
    session = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement=OPERATOR_STATEMENT_V1,
        policy_id=policy.policy_id or "",
        profile_id=profile.profile_id or "",
        model=REDUCED_MODEL_V1,
        provider_selector=REDUCED_PROVIDER_SELECTOR_V1,
        maximum_calls=1,
        maximum_total_spend_picodollars=worst_case,
        maximum_per_call_spend_picodollars=worst_case,
        session_id=f"q2-ced-4096-diagnostic-v1-{manifest_digest}",
    )
    return DiagnosticPreparedV1(
        prior=prior,
        policy=policy,
        profile=profile,
        rendered=rendered,
        endpoint_evidence=endpoint_evidence,
        selected_endpoint=selected_endpoint,
        parity=parity,
        manifest=manifest,
        session=session,
        worst_case_picodollars=worst_case,
    )


def _numeric_token_details_only_v1(value: Any) -> Dict[str, Optional[int]]:
    """Retain only named numeric token counts, never provider-owned text.

    Both values and keys from arbitrary nested mappings can contain text.  The
    diagnostic therefore projects the documented token-count names through a
    fixed allowlist and records only integer-or-null values.
    """

    if not isinstance(value, Mapping):
        return {}
    projected: Dict[str, Optional[int]] = {}
    for key in sorted(_SAFE_TOKEN_DETAIL_FIELDS_V1):
        item = value.get(key)
        if item is None:
            if key in value:
                projected[key] = None
        elif type(item) is int and item >= 0:
            projected[key] = item
    return projected


def _safe_control_reason_v1(value: Any) -> Dict[str, Optional[str]]:
    """Project a finish reason as a bounded control token, not free text."""

    if value is None:
        return {"state": "ABSENT_OR_NULL", "value": None}
    if not isinstance(value, str):
        return {"state": "NON_STRING", "value": None}
    if not value or len(value) > 64 or not all(
        character.isalnum() or character in "_-.:" for character in value
    ):
        return {"state": "UNSAFE_OR_MALFORMED", "value": None}
    return {"state": "PRESENT", "value": value}


def _message_content_state_v1(choice: Any) -> Tuple[str, Optional[str]]:
    if not isinstance(choice, Mapping):
        return "NO_CHOICE", None
    if "message" not in choice:
        return "MESSAGE_ABSENT", None
    message = choice.get("message")
    if not isinstance(message, Mapping):
        return "MESSAGE_NON_OBJECT", None
    if "content" not in message:
        return "CONTENT_ABSENT", None
    content = message.get("content")
    if content is None:
        return "CONTENT_NULL", None
    if not isinstance(content, str):
        return "CONTENT_NON_STRING", None
    if not content:
        return "CONTENT_EMPTY_STRING", content
    return "CONTENT_NONEMPTY_STRING", content


def _decimal_cost_v1(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool) or type(value) not in (int, str, Decimal):
        return None
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and result >= 0 else None


def _picodollars_to_usd_text_v1(value: Any) -> str:
    if type(value) is not int or value < 0:
        return "UNKNOWN"
    return format(Decimal(value) / Decimal(10**12), "f")


def evaluate_q2_move_through_ced_v1(
    raw_text: str,
    *,
    task: AgentTask,
) -> Dict[str, Any]:
    """Replay one visible move through CED's canonical opening authority.

    The fresh state has the exact Q2/session identity and no prior public move,
    matching the opening boundary.  The registry is deliberately empty: it
    supplies the canonical application surface but cannot dispatch anything.
    """

    meta: Dict[str, Any] = {}
    move, status, error = parse_and_validate_move(
        raw_text,
        task,
        repair_attempts=0,
        meta=meta,
    )
    provider_id = "diagnostic_openai_flex"
    response = ProviderResponse(
        provider_id=provider_id,
        agent_id=task.agent_id,
        status=status,
        raw_text=raw_text,
        parsed_move=move,
        error_message=error,
        repair_attempted=bool(meta.get("repair_attempted", False)),
        repair_succeeded=bool(meta.get("repair_succeeded", False)),
    )
    fake = FakeProvider()
    ced = CEDOrchestrator(
        [SocraticAgent(f"agent_{index}", fake) for index in range(4)],
        fake,
        registry=CouncilProviderRegistry(),
    )
    state = ced.create_session(task.question, session_id=task.session_id)
    dispatch: List[Dict[str, Any]] = []
    application = ced._apply_registry_response(
        state,
        DialogPhase.OPENING,
        task,
        response,
        dispatch,
    )
    audit_rows = ced._socratic_audit_rows.get(state.session_id, [])
    audit = dict(audit_rows[-1]) if audit_rows else None
    accepted = application.accepted_move_id is not None
    accepted_move = state.moves[-1] if accepted and state.moves else None
    accepted_content = (
        accepted_move.content
        if accepted_move is not None
        and isinstance(accepted_move.content, Mapping)
        else {}
    )
    return {
        "ced_parse_status": status.value,
        "ced_parse_accepted": status is ProviderStatus.OK,
        "ced_parse_error": error,
        "ced_repair_attempted": bool(meta.get("repair_attempted", False)),
        "ced_repair_succeeded": bool(meta.get("repair_succeeded", False)),
        "ced_acceptance_result": application.outcome.value,
        "ced_move_accepted": accepted,
        "ced_rejection_kind": application.canonical_rejection_kind,
        "ced_rejection_reason": application.canonical_rejection_reason,
        "socratic_audit": audit,
        "accepted_socratic_move": (
            {
                "exact_question": accepted_content.get("question"),
                "operator": accepted_content.get("operator"),
                "epistemic_marker": accepted_content.get("epistemic_marker"),
                "confidence": accepted_move.confidence,
            }
            if accepted_move is not None
            else None
        ),
    }


def extract_diagnostic_response_evidence_v1(
    *,
    raw: bytes,
    task: AgentTask,
    completed: bool,
    http_status: Optional[int],
) -> Tuple[Dict[str, Any], Optional[int]]:
    """Whitelist observable response facts; never persist raw reasoning text."""
    evidence: Dict[str, Any] = {
        "response_body_sha256": _sha256_bytes(raw),
        "response_body_length": len(raw),
        "message_content_state": "UNAVAILABLE",
        "content_present": False,
        "provider_structured_output_state": "NOT_REACHED",
        "provider_structured_output_valid": None,
        "provider_structured_output_error": None,
        "ced_parse_status": None,
        "ced_parse_accepted": None,
        "ced_acceptance_result": "NOT_REACHED",
        "ced_move_accepted": None,
        "ced_rejection_reason": None,
        "upstream_failure_reason": "response_not_available",
        "socratic_move": None,
        "reasoning_observability": {
            "message_reasoning_present": False,
            "message_reasoning_details_present": False,
        },
    }
    if not completed or http_status != 200 or not raw:
        if not completed:
            evidence["upstream_failure_reason"] = "transport_not_completed"
        elif http_status != 200:
            evidence["upstream_failure_reason"] = f"http_status_{http_status}"
        else:
            evidence["upstream_failure_reason"] = "empty_response_body"
        return evidence, None
    try:
        payload = json.loads(raw.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, ValueError):
        evidence["response_json_valid"] = False
        evidence["upstream_failure_reason"] = "response_not_utf8_json"
        return evidence, None
    if not isinstance(payload, Mapping):
        evidence["response_json_valid"] = False
        evidence["upstream_failure_reason"] = "response_json_not_object"
        return evidence, None
    evidence["response_json_valid"] = True
    evidence["returned_model"] = payload.get("model")
    evidence["returned_provider"] = payload.get("provider")
    evidence["returned_model_binding_ok"] = payload.get("model") == REDUCED_MODEL_V1
    evidence["returned_provider_binding_ok"] = (
        payload.get("provider") == REDUCED_PROVIDER_DISPLAY_NAME_V1
    )

    choices = payload.get("choices")
    raw_choice = choices[0] if isinstance(choices, list) and choices else None
    choice = raw_choice if isinstance(raw_choice, Mapping) else {}
    finish = _safe_control_reason_v1(choice.get("finish_reason"))
    native = _safe_control_reason_v1(
        choice.get("native_finish_reason", payload.get("native_finish_reason"))
    )
    evidence["finish_reason"] = finish["value"]
    evidence["finish_reason_state"] = finish["state"]
    evidence["native_finish_reason"] = native["value"]
    evidence["native_finish_reason_state"] = native["state"]
    content_state, content = _message_content_state_v1(raw_choice)
    evidence["message_content_state"] = content_state
    evidence["content_present"] = content_state == "CONTENT_NONEMPTY_STRING"
    if evidence["content_present"]:
        evidence["upstream_failure_reason"] = None
    else:
        evidence["provider_structured_output_state"] = "INVALID"
        evidence["provider_structured_output_valid"] = False
        evidence["provider_structured_output_error"] = "no_assistant_content"
        evidence["upstream_failure_reason"] = "no_assistant_content"
    message = choice.get("message")
    message = message if isinstance(message, Mapping) else {}
    if isinstance(content, str):
        evidence["assistant_output_sanitized"] = (
            sanitize_public_assistant_output_v1(content)
        )
        evidence["assistant_output_sha256"] = _sha256_text(content)

    reasoning = message.get("reasoning")
    reasoning_details = message.get("reasoning_details")
    reasoning_meta = evidence["reasoning_observability"]
    reasoning_meta["message_reasoning_present"] = reasoning not in (None, "")
    reasoning_meta["message_reasoning_details_present"] = reasoning_details not in (
        None,
        [],
        {},
    )

    usage = payload.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    completion_details = _numeric_token_details_only_v1(
        usage.get("completion_tokens_details")
    )
    if "completion_tokens_details" not in usage:
        completion_details_state = "ABSENT"
    elif usage.get("completion_tokens_details") is None:
        completion_details_state = "NULL"
    elif not isinstance(usage.get("completion_tokens_details"), Mapping):
        completion_details_state = "NON_OBJECT"
    elif not usage.get("completion_tokens_details"):
        completion_details_state = "EMPTY_OBJECT"
    else:
        completion_details_state = "PRESENT_OBJECT"
    direct_reasoning_tokens = usage.get("reasoning_tokens")
    if type(direct_reasoning_tokens) is not int or direct_reasoning_tokens < 0:
        direct_reasoning_tokens = None
    reasoning_tokens = direct_reasoning_tokens
    if reasoning_tokens is None:
        nested_reasoning = completion_details.get("reasoning_tokens")
        reasoning_tokens = (
            nested_reasoning
            if type(nested_reasoning) is int and nested_reasoning >= 0
            else None
        )
    evidence["usage"] = {
        "prompt_tokens": usage.get("prompt_tokens")
        if type(usage.get("prompt_tokens")) is int
        else None,
        "completion_tokens": usage.get("completion_tokens")
        if type(usage.get("completion_tokens")) is int
        else None,
        "reasoning_tokens": reasoning_tokens,
        "reasoning_tokens_source": (
            "usage.reasoning_tokens"
            if direct_reasoning_tokens is not None
            else (
                "usage.completion_tokens_details.reasoning_tokens"
                if reasoning_tokens is not None
                else "NOT_REPORTED"
            )
        ),
        "prompt_tokens_details": _numeric_token_details_only_v1(
            usage.get("prompt_tokens_details")
        ),
        "completion_tokens_details_state": completion_details_state,
        "completion_tokens_details": completion_details,
        "reasoning_tokens_details": _numeric_token_details_only_v1(
            usage.get("reasoning_tokens_details")
        ),
    }
    exact_cost = _decimal_cost_v1(usage.get("cost"))
    observed_picos: Optional[int] = None
    if exact_cost is not None:
        evidence["observed_cost_usd_decimal"] = str(exact_cost)
        scaled = exact_cost * Decimal(10**12)
        if scaled == scaled.to_integral_value():
            observed_picos = int(scaled)
            evidence["observed_cost_picodollars"] = observed_picos

    if isinstance(content, str):
        try:
            validate_ced_structured_output_v1(task, content)
        except Exception as exc:
            evidence["provider_structured_output_state"] = "INVALID"
            evidence["provider_structured_output_valid"] = False
            evidence["provider_structured_output_error"] = (
                f"{type(exc).__name__}: {exc}"
            )[:1000]
        else:
            evidence["provider_structured_output_state"] = "VALID"
            evidence["provider_structured_output_valid"] = True
            evidence["provider_structured_output_error"] = None
        try:
            ced_result = evaluate_q2_move_through_ced_v1(content, task=task)
        except Exception as exc:  # preserve a paid observation, never retry
            evidence["ced_acceptance_result"] = "APPLICATION_ERROR"
            evidence["ced_move_accepted"] = False
            evidence["ced_application_error"] = (
                f"{type(exc).__name__}: "
                f"{sanitize_public_assistant_output_v1(str(exc))}"
            )[:1000]
        else:
            evidence.update(
                {
                    key: value
                    for key, value in ced_result.items()
                    if key != "accepted_socratic_move"
                }
            )
            evidence["socratic_move"] = ced_result["accepted_socratic_move"]
    return evidence, observed_picos


def assert_observability_preflight_v1(task: AgentTask) -> Dict[str, Any]:
    """Exercise the postpaid path before the latch/socket can be reached."""

    visible = canonical_json(
        {
            "content": {
                "question": (
                    "Which distinction between selection, training, and tool "
                    "effects must be resolved before this comparison can "
                    "support a causal conclusion?"
                ),
                "operator": "distinguish",
                "epistemic_marker": "open_uncertainty",
            },
            "confidence": 0.8,
        }
    )
    raw = canonical_json(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "native_finish_reason": "stop",
                    "message": {
                        "content": visible,
                        "reasoning": "SZ_HIDDEN_REASONING_PREFLIGHT_CANARY",
                        "reasoning_details": [
                            {"text": "SZ_HIDDEN_DETAILS_PREFLIGHT_CANARY"}
                        ],
                    },
                }
            ],
            "model": REDUCED_MODEL_V1,
            "provider": REDUCED_PROVIDER_DISPLAY_NAME_V1,
            "usage": {
                "completion_tokens": 1300,
                "completion_tokens_details": {
                    "reasoning_tokens": 1100,
                    "SZ_HIDDEN_KEY_PREFLIGHT_CANARY": 7,
                },
                "cost": "0.002",
                "prompt_tokens": 2500,
            },
        }
    ).encode("utf-8")
    evidence, observed = extract_diagnostic_response_evidence_v1(
        raw=raw,
        task=task,
        completed=True,
        http_status=200,
    )
    serialized = canonical_json(evidence)
    if "SZ_HIDDEN_" in serialized:
        raise ContractValidationError(
            "observability preflight retained hidden-reasoning canary text"
        )
    if (
        observed != 2_000_000_000
        or evidence.get("finish_reason") != "stop"
        or evidence.get("native_finish_reason") != "stop"
        or evidence.get("message_content_state") != "CONTENT_NONEMPTY_STRING"
        or (evidence.get("usage") or {}).get("reasoning_tokens") != 1100
        or evidence.get("provider_structured_output_valid") is not True
        or evidence.get("ced_parse_accepted") is not True
        or evidence.get("ced_move_accepted") is not True
    ):
        raise ContractValidationError("observability preflight did not close")
    return {
        "passed": True,
        "hidden_reasoning_text_retained": False,
        "finish_reason_retained": True,
        "native_finish_reason_retained": True,
        "nested_reasoning_tokens_retained": True,
        "content_state_retained": True,
        "provider_schema_exercised": True,
        "ced_parse_exercised": True,
        "canonical_ced_acceptance_exercised": True,
    }


def execute_prepared_diagnostic_v1(
    prepared: DiagnosticPreparedV1,
    *,
    dispatch: Callable[..., Any] = dispatch_openrouter_one_live_inference_v1,
    latch_directory: Path = DIAGNOSTIC_LATCH_DIRECTORY,
    claim_directory: Path = DIAGNOSTIC_CLAIM_STORE,
) -> Dict[str, Any]:
    """Consume one latch and one claim, then perform exactly one dispatch."""
    ledger = OpenRouterSessionLedgerV1(prepared.session)
    ledger.check_admits(prepared.worst_case_picodollars)
    claim_id = mint_turn_claim_id_v1(prepared.session, prepared.rendered)
    claim_target = Path(claim_directory).resolve() / f"{claim_id}.consumed.json"
    if claim_target.exists():
        raise ContractValidationError(
            "diagnostic turn claim was already consumed; no retry is allowed"
        )
    run_latch = consume_diagnostic_attempt_latch_v1(latch_directory)
    claim_path = consume_turn_claim_v1(Path(claim_directory), claim_id)
    started = time.perf_counter()
    try:
        result = dispatch(
            body_bytes=prepared.rendered.canonical_body_json.encode("utf-8"),
            semantic_headers=dict(FROZEN_LIVE_SEMANTIC_HEADERS_V1),
            bounded_timeout_seconds=prepared.policy.bounded_timeout_seconds,
            process_dispatch_limit=1,
        )
    except Exception as exc:  # one consumed attempt; preserve and never retry
        ledger.record_dispatch(prepared.worst_case_picodollars)
        ledger.trip_fatal(f"dispatch_exception:{type(exc).__name__}")
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        response, _ = extract_diagnostic_response_evidence_v1(
            raw=b"",
            task=prepared.prior.task,
            completed=False,
            http_status=None,
        )
        response["upstream_failure_reason"] = "dispatch_exception"
        return {
            "run_attempt_latch": run_latch,
            "turn_claim": {
                "claim_id": claim_id,
                "claim_path": str(claim_path),
            },
            "transport": {
                "dispatch_attempted": True,
                "local_dispatch_count": None,
                "retry_count": 0,
                "completed": False,
                "http_status": None,
                "failure_class": type(exc).__name__,
                "latency_ms": latency_ms,
            },
            "response": response,
            "ledger": {
                "calls_consumed": ledger.calls_consumed,
                "settled_picodollars": ledger.settled_picodollars,
                "observed_picodollars": ledger.observed_picodollars,
                "unsettled_reserved_picodollars": (
                    ledger.unsettled_reserved_picodollars
                ),
                "committed_picodollars": ledger.committed_picodollars,
                "fatal_failure": ledger.fatal_failure,
                "maximum_calls": prepared.session.maximum_calls,
                "maximum_total_spend_picodollars": (
                    prepared.session.maximum_total_spend_picodollars
                ),
            },
            "cumulative_observed_picodollars": None,
            "cumulative_committed_picodollars": (
                prepared.prior.prior_observed_picodollars
                + ledger.committed_picodollars
            ),
        }
    ledger.record_dispatch(prepared.worst_case_picodollars)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    completion = result.completion
    retry_count = getattr(completion, "retry_count", 0)
    if type(retry_count) is not int or retry_count != 0:
        ledger.trip_fatal("transport_retry_observed")
    raw = bytes(result.raw_response_body)
    response, observed_picos = extract_diagnostic_response_evidence_v1(
        raw=raw,
        task=prepared.prior.task,
        completed=bool(completion.completed),
        http_status=completion.http_status,
    )
    if observed_picos is not None:
        ledger.settle_observed(observed_picos, prepared.worst_case_picodollars)
        if observed_picos > prepared.worst_case_picodollars:
            ledger.trip_fatal("observed_cost_exceeded_p19_reservation")
        if (
            prepared.prior.prior_observed_picodollars + observed_picos
            > REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1
        ):
            ledger.trip_fatal("cumulative_observed_cost_exceeded_8_usd")
    if response.get("returned_model_binding_ok") is False:
        ledger.trip_fatal("returned_model_identity_mismatch")
    if response.get("returned_provider_binding_ok") is False:
        ledger.trip_fatal("returned_provider_identity_mismatch")

    cumulative_observed = (
        prepared.prior.prior_observed_picodollars + observed_picos
        if observed_picos is not None
        else None
    )
    cumulative_committed = (
        prepared.prior.prior_observed_picodollars + ledger.committed_picodollars
    )
    return {
        "run_attempt_latch": run_latch,
        "turn_claim": {
            "claim_id": claim_id,
            "claim_path": str(claim_path),
        },
        "transport": {
            "dispatch_attempted": True,
            "local_dispatch_count": getattr(completion, "local_dispatch_count", 1),
            "retry_count": retry_count,
            "completed": bool(completion.completed),
            "http_status": completion.http_status,
            "failure_class": completion.failure_class,
            "latency_ms": latency_ms,
        },
        "response": response,
        "ledger": {
            "calls_consumed": ledger.calls_consumed,
            "settled_picodollars": ledger.settled_picodollars,
            "observed_picodollars": ledger.observed_picodollars,
            "unsettled_reserved_picodollars": ledger.unsettled_reserved_picodollars,
            "committed_picodollars": ledger.committed_picodollars,
            "fatal_failure": ledger.fatal_failure,
            "maximum_calls": prepared.session.maximum_calls,
            "maximum_total_spend_picodollars": (
                prepared.session.maximum_total_spend_picodollars
            ),
        },
        "cumulative_observed_picodollars": cumulative_observed,
        "cumulative_committed_picodollars": cumulative_committed,
    }


def classify_diagnostic_v1(execution: Mapping[str, Any]) -> Dict[str, Any]:
    transport = execution.get("transport") or {}
    response = execution.get("response") or {}
    usage = response.get("usage") or {}
    ledger = execution.get("ledger") or {}
    finish_values = {
        response.get("finish_reason"),
        response.get("native_finish_reason"),
    }
    output_limit_reached = bool(
        finish_values & {"length", "max_tokens", "max_output_tokens"}
        or usage.get("completion_tokens") == DIAGNOSTIC_MAX_OUTPUT_TOKENS_V1
    )
    route_and_session_valid = bool(
        response.get("returned_model_binding_ok") is True
        and response.get("returned_provider_binding_ok") is True
        and ledger.get("fatal_failure") is None
        and transport.get("retry_count") == 0
        and transport.get("local_dispatch_count") == 1
    )
    confirmed = bool(
        not output_limit_reached
        and route_and_session_valid
        and transport.get("completed") is True
        and transport.get("http_status") == 200
        and response.get("provider_structured_output_valid") is True
        and response.get("ced_parse_accepted") is True
        and response.get("ced_move_accepted") is True
    )
    if confirmed:
        completion_tokens = usage.get("completion_tokens")
        opening = (
            4096
            if type(completion_tokens) is int and completion_tokens <= 3072
            else 8192
        )
        policy = {
            "status": "PROPOSED_NOT_IMPLEMENTED",
            "short_socratic_moves_and_openings": opening,
            "reflection_and_reconstruction": max(8192, opening * 2),
            "synthesis_and_final_response": max(16384, opening * 4),
            "rule": (
                "phase-aware ceilings replace the global 1024 ceiling; "
                "reasoning behavior remains independently controlled"
            ),
            "evidence_basis": (
                "opening value uses this accepted call's completion-token "
                "headroom; larger-phase values are provisional multiples and "
                "require separate validation before use"
            ),
        }
        return {
            "verdict": "GENERATION_BUDGET_CONFIRMED",
            "classification": "GENERATION_BUDGET_TOO_LOW AT 1024",
            "output_limit_reached": False,
            "phase_aware_output_budget_policy": policy,
        }
    if (
        transport.get("completed") is not True
        or transport.get("http_status") != 200
    ):
        reason = "HTTP_OR_TRANSPORT_FAILURE"
    elif not route_and_session_valid:
        reason = "ROUTE_OR_SESSION_INVARIANT_FAILURE"
    elif output_limit_reached:
        reason = "4096_OUTPUT_LIMIT_REACHED"
    elif response.get("provider_structured_output_valid") is not True:
        reason = "STRUCTURED_OUTPUT_NOT_VALID"
    elif response.get("ced_parse_accepted") is not True:
        reason = "CED_PARSE_NOT_ACCEPTED"
    else:
        reason = "CED_SOCRATIC_MOVE_NOT_ACCEPTED"
    return {
        "verdict": "NOT_CONFIRMED",
        "classification": reason,
        "output_limit_reached": output_limit_reached,
        "phase_aware_output_budget_policy": None,
    }


def _endpoint_evidence_json_v1(value: Any) -> Any:
    return (
        value.model_dump(mode="json", exclude_none=False)
        if hasattr(value, "model_dump")
        else value
    )


def collect_diagnostic_v1(
    *,
    record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Live entrypoint: one fresh endpoint GET followed by at most one POST."""
    collection = {} if record is None else record
    collection.update(
        {
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION_V1,
            "started_utc": _utc_now(),
            "operator_statement": OPERATOR_STATEMENT_V1,
            "maximum_live_calls": 1,
            "automatic_retries": 0,
            "hard_cumulative_spend_usd": "8.00",
            "collection_dispatch_closed": False,
        }
    )
    try:
        if diagnostic_attempt_latch_path_v1().exists():
            raise ContractValidationError(
                "approved Q2 CED 4096 diagnostic attempt was already consumed"
            )
        prior = load_prior_q2_ced_request_v1()
        collection["prior_evidence"] = {
            "collection_path": str(PRIOR_COLLECTION_PATH.resolve()),
            "collection_sha256": prior.collection_sha256,
            "ced_body_sha256": PRIOR_CED_BODY_SHA256_V1,
            "observed_cost_picodollars": prior.prior_observed_picodollars,
            "observed_cost_usd_decimal": PRIOR_OBSERVED_COST_USD_V1,
        }
        fetched = fetch_flex_endpoint_listing_once_v1()
        endpoint_raw = fetched.raw_response_body
        collection["endpoint_http"] = {
            "http_status": fetched.http_status,
            "latency_ms": fetched.latency_ms,
            "body_sha256": _sha256_bytes(endpoint_raw),
            "body_length": len(endpoint_raw),
        }
        collection["endpoint_raw_utf8"] = endpoint_raw.decode("utf-8", errors="strict")
        if fetched.http_status != 200:
            raise ContractValidationError(
                f"fresh Flex endpoint GET returned HTTP {fetched.http_status}"
            )
        prepared = prepare_diagnostic_v1(endpoint_raw)
        collection["endpoint_evidence"] = _endpoint_evidence_json_v1(
            prepared.endpoint_evidence
        )
        collection["selected_endpoint_record"] = prepared.selected_endpoint
        collection["profile"] = prepared.profile.model_dump(mode="json")
        collection["policy"] = prepared.policy.model_dump(mode="json")
        collection["authorization_manifest"] = prepared.manifest
        collection["session_authorization"] = prepared.session.model_dump(mode="json")
        collection["body_parity"] = prepared.parity
        collection["observability_preflight"] = (
            assert_observability_preflight_v1(prepared.prior.task)
        )
        collection["diagnostic_request"] = {
            "request_id": prepared.rendered.request_id,
            "body_sha256": prepared.rendered.body_sha256,
            "body_length": prepared.rendered.body_length,
            "canonical_body": prepared.rendered.canonical_body_json,
        }
        collection["economics_preflight"] = {
            "prior_observed_picodollars": prior.prior_observed_picodollars,
            "prior_observed_usd": PRIOR_OBSERVED_COST_USD_V1,
            "diagnostic_worst_case_picodollars": prepared.worst_case_picodollars,
            "diagnostic_worst_case_usd": DIAGNOSTIC_WORST_CASE_USD_V1,
            "cumulative_prior_plus_reservation_picodollars": (
                CUMULATIVE_PRIOR_PLUS_RESERVATION_PICODOLLARS_V1
            ),
            "cumulative_prior_plus_reservation_usd": (
                CUMULATIVE_PRIOR_PLUS_RESERVATION_USD_V1
            ),
            "hard_ceiling_picodollars": REDUCED_HARD_SESSION_SPEND_PICODOLLARS_V1,
            "within_hard_ceiling": True,
        }
        if not openrouter_credential_is_present_v1():
            raise ContractValidationError(
                "OpenRouter credential absent; diagnostic POST not dispatched"
            )
        collection["execution"] = execute_prepared_diagnostic_v1(prepared)
        collection["interpretation"] = classify_diagnostic_v1(
            collection["execution"]
        )
        collection["result"] = "Q2_CED_4096_DIAGNOSTIC_COMPLETE"
        collection["completed_utc"] = _utc_now()
        collection["collection_dispatch_closed"] = True
        return collection
    except Exception as exc:
        collection["result"] = "Q2_CED_4096_DIAGNOSTIC_FAILED"
        collection["failure_class"] = type(exc).__name__
        collection["failure_message"] = sanitize_public_assistant_output_v1(
            str(exc)
        )[:1000]
        collection["completed_utc"] = _utc_now()
        collection["collection_dispatch_closed"] = True
        raise


def render_diagnostic_report_v1(collection: Mapping[str, Any]) -> str:
    parity = collection.get("body_parity") or {}
    economics = collection.get("economics_preflight") or {}
    endpoint = collection.get("endpoint_evidence") or {}
    manifest = collection.get("authorization_manifest") or {}
    execution = collection.get("execution") or {}
    transport = execution.get("transport") or {}
    ledger = execution.get("ledger") or {}
    response = execution.get("response") or {}
    usage = response.get("usage") or {}
    move = response.get("socratic_move") or {}
    reasoning = response.get("reasoning_observability") or {}
    interpretation = collection.get("interpretation") or {}
    phase_policy = interpretation.get("phase_aware_output_budget_policy") or {}
    output = response.get("assistant_output_sanitized") or "(no assistant content)"
    return "\n".join(
        [
            "# CED 4096 DIAGNOSTIC",
            "",
            f"Result: **{collection.get('result', 'UNKNOWN')}**",
            "",
            "## Request parity",
            "",
            f"- One-field parity proved: {parity.get('proved')}",
            f"- Deep differences: `{json.dumps(parity.get('deep_differences'))}`",
            f"- Prior body: `{parity.get('prior_body_sha256')}`",
            f"- Diagnostic body: `{parity.get('diagnostic_body_sha256')}`",
            f"- Messages unchanged: {parity.get('messages_identical')}",
            f"- Response schema unchanged: {parity.get('response_format_identical')}",
            f"- Provider policy unchanged: {parity.get('provider_policy_identical')}",
            f"- Reasoning parameters absent: {parity.get('reasoning_parameters_absent')}",
            "",
            "## Exact endpoint capability",
            "",
            f"- Endpoint GET HTTP: {(collection.get('endpoint_http') or {}).get('http_status')}",
            f"- Requested model: `{endpoint.get('requested_model')}`",
            f"- Dated endpoint: `{endpoint.get('dated_endpoint_model')}`",
            f"- Provider selector: `{endpoint.get('provider_selector')}`",
            f"- Provider display name: `{endpoint.get('provider_display_name')}`",
            f"- Output-limit parameter: `{endpoint.get('output_limit_parameter')}`",
            f"- Endpoint maximum output tokens: {endpoint.get('maximum_output_tokens')}",
            f"- `reasoning` parameter supported: {manifest.get('endpoint_reasoning_parameter_supported')}",
            f"- Diagnostic reasoning behavior: `{manifest.get('reasoning_behavior')}`",
            f"- Supported parameters: `{json.dumps(endpoint.get('supported_parameters'))}`",
            "",
            "## Termination and usage",
            "",
            f"- HTTP status: {transport.get('http_status')}",
            f"- Local dispatch count: {transport.get('local_dispatch_count')}",
            f"- Retry count: {transport.get('retry_count')}",
            f"- Returned model binding valid: {response.get('returned_model_binding_ok')}",
            f"- Returned provider binding valid: {response.get('returned_provider_binding_ok')}",
            f"- Fatal session failure: `{ledger.get('fatal_failure') or 'NONE'}`",
            f"- Finish reason: `{response.get('finish_reason') or 'NOT_REPORTED'}`",
            f"- Native finish reason: `{response.get('native_finish_reason') or 'NOT_REPORTED'}`",
            f"- Message content state: `{response.get('message_content_state')}`",
            f"- Prompt tokens: {usage.get('prompt_tokens')}",
            f"- Completion tokens: {usage.get('completion_tokens')}",
            f"- Reasoning tokens: {usage.get('reasoning_tokens')}",
            f"- Reasoning-token source: `{usage.get('reasoning_tokens_source')}`",
            f"- Completion token details state: `{usage.get('completion_tokens_details_state')}`",
            f"- Completion token details: `{json.dumps(usage.get('completion_tokens_details'), default=str)}`",
            f"- Latency ms: {transport.get('latency_ms')}",
            f"- Observed cost: ${response.get('observed_cost_usd_decimal', 'unknown')}",
            "",
            "## CED result",
            "",
            f"- Provider structured output state: `{response.get('provider_structured_output_state')}`",
            f"- Provider structured output valid: {response.get('provider_structured_output_valid')}",
            f"- Provider structured output error: `{response.get('provider_structured_output_error') or 'NONE'}`",
            f"- CED parse status: `{response.get('ced_parse_status') or 'NOT_REACHED'}`",
            f"- CED parse accepted: {response.get('ced_parse_accepted')}",
            f"- CED parse error: `{response.get('ced_parse_error') or 'NONE'}`",
            f"- CED canonical application: `{response.get('ced_acceptance_result')}`",
            f"- CED Socratic move accepted: {response.get('ced_move_accepted')}",
            f"- CED rejection kind: `{response.get('ced_rejection_kind') or 'NONE'}`",
            f"- CED rejection reason: `{response.get('ced_rejection_reason') or 'NONE'}`",
            f"- Upstream failure reason: `{response.get('upstream_failure_reason') or 'NONE'}`",
            f"- Question: {move.get('exact_question')}",
            f"- Operator: `{move.get('operator')}`",
            f"- Epistemic marker: `{move.get('epistemic_marker')}`",
            f"- Confidence: {move.get('confidence')}",
            "",
            "### Observable assistant content",
            "",
            "```json",
            str(output),
            "```",
            "",
            "## Reasoning privacy",
            "",
            "No reasoning text or reasoning-details payload is retained.",
            f"Reasoning field present: {reasoning.get('message_reasoning_present')}; "
            f"reasoning-details present: {reasoning.get('message_reasoning_details_present')}.",
            "",
            "## Economics",
            "",
            f"- Prior observed spend: ${economics.get('prior_observed_usd')}",
            f"- Conservative diagnostic reservation: ${economics.get('diagnostic_worst_case_usd')}",
            f"- Prior + reservation: ${economics.get('cumulative_prior_plus_reservation_usd')}",
            f"- Diagnostic observed spend: ${response.get('observed_cost_usd_decimal', 'UNKNOWN')}",
            f"- Cumulative observed spend: ${_picodollars_to_usd_text_v1(execution.get('cumulative_observed_picodollars'))}",
            f"- Cumulative committed spend: ${_picodollars_to_usd_text_v1(execution.get('cumulative_committed_picodollars'))}",
            f"- Hard ceiling: ${collection.get('hard_cumulative_spend_usd', '8.00')}",
            f"- Within hard ceiling before POST: {economics.get('within_hard_ceiling')}",
            "",
            f"# VERDICT: {interpretation.get('verdict', 'NOT_CONFIRMED')}",
            "",
            f"- Classification: `{interpretation.get('classification', 'UNKNOWN')}`",
            f"- 4096 output limit reached: {interpretation.get('output_limit_reached')}",
            "",
            "## Proposed phase-aware output budget",
            "",
            *(
                [
                    f"- Status: {phase_policy.get('status')}",
                    f"- Short Socratic moves/openings: {phase_policy.get('short_socratic_moves_and_openings')}",
                    f"- Reflection/reconstruction: {phase_policy.get('reflection_and_reconstruction')}",
                    f"- Synthesis/final response: {phase_policy.get('synthesis_and_final_response')}",
                    f"- Rule: {phase_policy.get('rule')}",
                    f"- Evidence basis: {phase_policy.get('evidence_basis')}",
                ]
                if phase_policy
                else ["Not proposed because the 4096 diagnostic was not accepted."]
            ),
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the approved one-call Q2 CED 4096 diagnostic"
    )
    parser.add_argument(
        REQUIRED_CLI_FLAG_V1,
        action="store_true",
        help="required acknowledgement of the approved one-call diagnostic",
    )
    parser.add_argument("--collection-out", default=str(DEFAULT_COLLECTION_PATH))
    parser.add_argument("--report-out", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    if not getattr(args, "execute_approved_one_call_diagnostic"):
        raise SystemExit(
            f"REFUSING: pass {REQUIRED_CLI_FLAG_V1} only for the approved "
            "one-call, zero-retry Q2 CED 4096 diagnostic"
        )
    output_paths = [Path(args.collection_out), Path(args.report_out)]
    existing = [str(path.resolve()) for path in output_paths if path.exists()]
    if existing:
        raise SystemExit(f"REFUSING: write-once output exists: {existing}")

    collection: Dict[str, Any] = {}
    try:
        collect_diagnostic_v1(record=collection)
    except Exception:
        collection_sha = _write_once(Path(args.collection_out), collection)
        report = render_diagnostic_report_v1(collection)
        report_sha = _write_once(Path(args.report_out), report)
        print(
            json.dumps(
                {
                    "result": collection.get("result"),
                    "collection_path": str(Path(args.collection_out).resolve()),
                    "collection_sha256": collection_sha,
                    "report_path": str(Path(args.report_out).resolve()),
                    "report_sha256": report_sha,
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    collection_sha = _write_once(Path(args.collection_out), collection)
    report = render_diagnostic_report_v1(collection)
    report_sha = _write_once(Path(args.report_out), report)
    print(
        json.dumps(
            {
                "result": collection["result"],
                "live_calls": collection["execution"]["ledger"]["calls_consumed"],
                "collection_path": str(Path(args.collection_out).resolve()),
                "collection_sha256": collection_sha,
                "report_path": str(Path(args.report_out).resolve()),
                "report_sha256": report_sha,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
