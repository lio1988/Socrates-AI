"""Run exactly one arm of the controlled OpenRouter structured-output test.

Each invocation is one-shot and write-once:

1. reproduce the preserved prompt-only control locally;
2. burn an arm-attempt claim;
3. fetch the exact model's endpoint listing once, with no retry;
4. validate the exact pinned endpoint and conservative spend bound;
5. burn an exact-body claim;
6. dispatch at most one inference POST, with no retry;
7. apply the raw assistant output through unchanged CED authority;
8. persist one result file with exclusive creation.

Run ARM 1 and ARM 2 in separate processes so each transport latch has an
independent one-call ceiling.  Existing control evidence is read, never edited.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, localcontext
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
    stable_contract_id,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    FROZEN_LIVE_SEMANTIC_HEADERS_V1,
    consume_turn_claim_v1,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    dispatch_openrouter_one_live_inference_v1,
    openrouter_credential_is_present_v1,
)
from backend.dialogues.socrates_zero.openrouter_structured_socratic_experiment_v1 import (
    CONTROL_MODEL_V1,
    CONTROL_OUTPUT_TOKENS_V1,
    CONTROL_PROVIDER_SELECTOR_V1,
    CONTROL_QUESTION_V1,
    CONTROL_TIMEOUT_SECONDS_V1,
    FULL_MODEL_V1,
    PICODOLLARS_PER_USD,
    StructuredArmPriceCeilingsV1,
    assert_ced_opening_schema_parity_v1,
    assert_prompt_only_control_reconstruction_v1,
    ced_opening_response_format_v1,
    ced_opening_schema_sha256_v1,
    conservative_arm_cost_bound_picodollars_v1,
    evaluate_raw_move_through_ced_v1,
    parse_exact_endpoint_capability_v1,
    render_structured_arm_request_v1,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNNER_SOURCE = Path(__file__).resolve()
EXPERIMENT_SOURCE = (
    REPOSITORY_ROOT
    / "backend"
    / "dialogues"
    / "socrates_zero"
    / "openrouter_structured_socratic_experiment_v1.py"
)
CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    "\\"
    r"openrouter-structured-output-experiment-claim-store-v1"
)
OPENROUTER_HOST = "openrouter.ai"
MAX_ENDPOINT_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
ARM_MODELS = {"ARM_1": CONTROL_MODEL_V1, "ARM_2": FULL_MODEL_V1}
ENDPOINT_PATHS = {
    CONTROL_MODEL_V1: "/api/v1/models/openai/gpt-4.1-mini/endpoints",
    FULL_MODEL_V1: "/api/v1/models/openai/gpt-4.1/endpoints",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _header_digest(headers: Tuple[Tuple[str, str], ...]) -> str:
    return _sha256(
        canonical_json([[name.lower(), value] for name, value in headers]).encode(
            "utf-8"
        )
    )


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _canonical_nonnegative_decimal(value: str, label: str) -> Decimal:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ContractValidationError(f"{label} must be an exact decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ContractValidationError(f"{label} is malformed") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ContractValidationError(f"{label} must be finite and nonnegative")
    return parsed


def _usd_to_picodollars_ceiling(value: str) -> int:
    parsed = _canonical_nonnegative_decimal(value, "maximum arm spend")
    with localcontext() as context:
        context.prec = 60
        return int(
            (parsed * PICODOLLARS_PER_USD).quantize(
                Decimal(1), rounding=ROUND_CEILING
            )
        )


def _write_once_json(path: Path, payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = (
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        + "\n"
    ).encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ContractValidationError(
            f"write-once arm evidence already exists: {path}"
        ) from exc
    return _sha256(rendered)


class _EndpointGetLatch:
    def __init__(self) -> None:
        self.used = False

    def fetch(self, model: str) -> Dict[str, Any]:
        if self.used:
            raise ContractValidationError("endpoint capability GET already consumed")
        path = ENDPOINT_PATHS.get(model)
        if path is None:
            raise ContractValidationError("endpoint path is not allowlisted")
        self.used = True
        connection = http.client.HTTPSConnection(
            OPENROUTER_HOST,
            timeout=CONTROL_TIMEOUT_SECONDS_V1,
            context=ssl.create_default_context(),
        )
        started = time.perf_counter()
        try:
            connection.request("GET", path, headers={"Accept": "application/json"})
            response = connection.getresponse()
            raw = response.read(MAX_ENDPOINT_BYTES + 1)
            if len(raw) > MAX_ENDPOINT_BYTES:
                raise ContractValidationError("endpoint response exceeded byte cap")
            headers = tuple(
                (str(name), str(value)) for name, value in response.getheaders()
            )
            return {
                "method": "GET",
                "host": OPENROUTER_HOST,
                "path": path,
                "http_status": int(response.status),
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "body_sha256": _sha256(raw),
                "body_length": len(raw),
                "response_header_count": len(headers),
                "response_header_sha256": _header_digest(headers),
                "raw_body": raw,
            }
        finally:
            connection.close()


def _attempt_claim_id(arm: str, model: str) -> str:
    return stable_contract_id(
        "szorturnclaimv1",
        {
            "experiment": "structured-socratic-move-v1",
            "arm": arm,
            "model": model,
            "question": CONTROL_QUESTION_V1,
            "schema_sha256": ced_opening_schema_sha256_v1(),
        },
    )


def _body_claim_id(arm: str, rendered) -> str:
    return stable_contract_id(
        "szorturnclaimv1",
        {
            "experiment": "structured-socratic-move-v1",
            "arm": arm,
            "request_id": rendered.request_id,
            "body_sha256": rendered.body_sha256,
        },
    )


def _selected_endpoint_raw(raw: bytes, selector: str) -> Mapping[str, Any]:
    payload = json.loads(raw.decode("utf-8"))
    endpoints = payload["data"]["endpoints"]
    matches = [item for item in endpoints if item.get("tag") == selector]
    if len(matches) != 1:
        raise ContractValidationError("cannot retain a unique endpoint record")
    return matches[0]


def _parse_inference_payload(raw_response: bytes) -> Mapping[str, Any]:
    try:
        payload = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ContractValidationError("inference response is not UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise ContractValidationError("inference response is not a JSON object")
    return payload


def _extract_assistant_observation(
    payload: Mapping[str, Any],
) -> Tuple[Optional[str], Any, Optional[str], Optional[str]]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, None, None, "inference response has no choices"
    first = choices[0]
    message = first.get("message") if isinstance(first, Mapping) else None
    if not isinstance(message, Mapping):
        return None, None, None, "inference response has no assistant message"
    content = message.get("content")
    refusal = message.get("refusal")
    if isinstance(content, str):
        return content, refusal, "string", None
    if content is not None:
        try:
            rendered = canonical_json(content)
        except Exception as exc:
            return (
                None,
                refusal,
                type(content).__name__,
                f"assistant content is not canonical JSON: {type(exc).__name__}",
            )
        return rendered, refusal, type(content).__name__, None
    if refusal is not None:
        return None, refusal, None, "provider returned a structured-output refusal"
    return None, None, None, "inference response has no assistant content"


def _exact_usage(raw_response: bytes) -> Dict[str, Any]:
    try:
        payload = json.loads(raw_response.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, ValueError):
        return {}
    usage = payload.get("usage") if isinstance(payload, Mapping) else None
    if not isinstance(usage, Mapping):
        return {}
    cost = usage.get("cost")
    observed_cost_usd: Optional[str] = None
    observed_picodollars: Optional[int] = None
    if (
        isinstance(cost, (int, Decimal, str))
        and not isinstance(cost, bool)
        and (not isinstance(cost, str) or cost.strip() == cost)
    ):
        try:
            parsed = Decimal(cost)
        except InvalidOperation:
            parsed = Decimal("NaN")
        if parsed.is_finite() and parsed >= 0:
            observed_cost_usd = format(parsed, "f")
            scaled = parsed * PICODOLLARS_PER_USD
            if scaled == scaled.to_integral_value():
                observed_picodollars = int(scaled)
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "raw_cost": cost,
        "observed_cost_usd": observed_cost_usd,
        "observed_cost_picodollars": observed_picodollars,
    }


def run_arm(
    args: argparse.Namespace, record: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    model = ARM_MODELS[args.arm]
    if args.model != model:
        raise ContractValidationError(
            f"{args.arm} is frozen to {model}, not {args.model}"
        )
    output_path = Path(args.out).resolve()
    if output_path.exists():
        raise ContractValidationError(
            f"write-once arm evidence already exists: {output_path}"
        )

    if record is None:
        record = {}
    record.update({
        "schema_version": "socrateszero-openrouter-structured-socratic-arm/v1",
        "experiment": "structured-socratic-move-v1",
        "arm": args.arm,
        "requested_model": model,
        "question": CONTROL_QUESTION_V1,
        "role": "socrates",
        "phase": "opening",
        "provider_selector": CONTROL_PROVIDER_SELECTOR_V1,
        "automatic_retries": 0,
        "maximum_inference_dispatches": 1,
        "started_utc": _utc_now(),
        "repository_head": _git_head(),
        "execution_sources": {
            "runner_sha256": _sha256(RUNNER_SOURCE.read_bytes()),
            "experiment_module_sha256": _sha256(EXPERIMENT_SOURCE.read_bytes()),
        },
        "operator_authorization": {
            "statement": args.operator_statement,
            "prompt_usd_per_million_tokens": args.prompt_ceiling,
            "completion_usd_per_million_tokens": args.completion_ceiling,
            "request_usd": args.request_ceiling,
            "maximum_arm_spend_usd": args.maximum_arm_spend_usd,
        },
        "control": {
            "classification": "PRESERVED_PROMPT_ONLY_CONTROL_0_OF_2",
            "run_002_unchanged": True,
            "run_003_unchanged": True,
        },
        "response_format": ced_opening_response_format_v1(),
        "response_schema_sha256": ced_opening_schema_sha256_v1(),
        "endpoint_retrievals": 0,
        "inference_dispatches": 0,
        "retry_count": 0,
        "http_success": False,
        "result": "STARTED",
    })

    ceilings = StructuredArmPriceCeilingsV1(
        prompt_usd_per_million_tokens=args.prompt_ceiling,
        completion_usd_per_million_tokens=args.completion_ceiling,
        request_usd=args.request_ceiling,
    )
    maximum_arm_picodollars = _usd_to_picodollars_ceiling(
        args.maximum_arm_spend_usd
    )

    assert_ced_opening_schema_parity_v1()
    assert_prompt_only_control_reconstruction_v1()
    attempt_claim = _attempt_claim_id(args.arm, model)
    consume_turn_claim_v1(CLAIM_STORE, attempt_claim)
    record["attempt_claim_id"] = attempt_claim

    record["endpoint_retrievals"] = 1
    endpoint_result = _EndpointGetLatch().fetch(model)
    record["endpoint_http"] = {
        key: value for key, value in endpoint_result.items() if key != "raw_body"
    }
    raw_endpoint = endpoint_result["raw_body"]
    record["endpoint_raw_utf8"] = raw_endpoint.decode("utf-8", errors="strict")
    if endpoint_result["http_status"] != 200:
        raise ContractValidationError(
            f"endpoint capability GET returned HTTP {endpoint_result['http_status']}"
        )
    endpoint = parse_exact_endpoint_capability_v1(
        raw_endpoint,
        requested_model=model,
        provider_selector=CONTROL_PROVIDER_SELECTOR_V1,
    )
    record["endpoint_capability"] = endpoint.model_dump(mode="json")
    record["selected_endpoint_raw"] = _selected_endpoint_raw(
        raw_endpoint, CONTROL_PROVIDER_SELECTOR_V1
    )

    rendered = render_structured_arm_request_v1(
        model=model,
        endpoint=endpoint,
        ceilings=ceilings,
    )
    worst_case = conservative_arm_cost_bound_picodollars_v1(endpoint, ceilings)
    if worst_case > maximum_arm_picodollars:
        raise ContractValidationError(
            "conservative arm cost exceeds the operator maximum"
        )
    record["preflight"] = {
        "endpoint_capability_valid": True,
        "output_limit_parameter": endpoint.output_limit_parameter,
        "output_limit_tokens": CONTROL_OUTPUT_TOKENS_V1,
        "context_limit_tokens": endpoint.context_length,
        "endpoint_request_price_usd": endpoint.request_price_usd,
        "endpoint_request_price_state": (
            "OBSERVED"
            if endpoint.request_price_usd is not None
            else "ABSENT_UNKNOWN_NOT_PROMOTED_TO_ZERO"
        ),
        "rendered_request_price_ceiling_usd": ceilings.request_usd,
        "worst_case_picodollars": worst_case,
        "worst_case_usd": format(
            Decimal(worst_case) / PICODOLLARS_PER_USD, "f"
        ),
        "maximum_arm_spend_picodollars": maximum_arm_picodollars,
        "admitted": True,
    }
    record["request"] = {
        key: value
        for key, value in rendered.model_dump(mode="json").items()
        if key != "canonical_body_json"
    }

    body_claim = _body_claim_id(args.arm, rendered)
    record["credential_present_pre_dispatch"] = (
        openrouter_credential_is_present_v1()
    )
    if not record["credential_present_pre_dispatch"]:
        raise ContractValidationError("credential absent; no request may be made")
    consume_turn_claim_v1(CLAIM_STORE, body_claim)
    record["body_claim_id"] = body_claim

    started = time.perf_counter()
    result = dispatch_openrouter_one_live_inference_v1(
        body_bytes=rendered.canonical_body_json.encode("utf-8"),
        semantic_headers=dict(FROZEN_LIVE_SEMANTIC_HEADERS_V1),
        bounded_timeout_seconds=CONTROL_TIMEOUT_SECONDS_V1,
        process_dispatch_limit=1,
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    record["inference_dispatches"] = 1
    completion = result.completion
    record["transport"] = {
        "registration_id": result.registration.registration_id,
        "completion_id": completion.completion_id,
        "completed": completion.completed,
        "http_status": completion.http_status,
        "latency_ms": latency_ms,
        "retry_count": completion.retry_count,
        "response_body_sha256": completion.response_body_sha256,
        "response_body_length": completion.response_body_length,
        "response_header_count": completion.response_header_count,
        "response_header_evidence_sha256": (
            completion.response_header_evidence_sha256
        ),
        "failure_class": completion.failure_class,
    }
    if result.raw_response_body:
        if len(result.raw_response_body) > MAX_RESPONSE_BYTES:
            raise ContractValidationError("inference response exceeded byte cap")
        record["raw_response_utf8"] = result.raw_response_body.decode(
            "utf-8", errors="strict"
        )
    if not completion.completed:
        record["result"] = "TRANSPORT_FAILURE"
        return record
    if completion.http_status != 200:
        record["result"] = "HTTP_FAILURE"
        return record

    record["http_success"] = True
    record["usage"] = _exact_usage(result.raw_response_body)
    observed_cost = record["usage"].get("observed_cost_picodollars")
    record["cost_checks"] = {
        "observed_cost_available": observed_cost is not None,
        "observed_cost_within_preflight_bound": (
            observed_cost <= worst_case if observed_cost is not None else None
        ),
        "observed_cost_within_operator_arm_maximum": (
            observed_cost <= maximum_arm_picodollars
            if observed_cost is not None
            else None
        ),
    }
    try:
        payload = _parse_inference_payload(result.raw_response_body)
    except ContractValidationError as exc:
        record["response_parse_error"] = str(exc)
        record["acceptance"] = evaluate_raw_move_through_ced_v1(
            None, provider_id="live_seat_1"
        )
        record["acceptance"]["provider_structured_output_error"] = str(exc)
        record["result"] = "MALFORMED_HTTP_200_RESPONSE"
        return record
    record["actual_model"] = payload.get("model")
    record["actual_model_matches_requested"] = payload.get("model") == model
    record["scientific_model_identity_valid"] = (
        record["actual_model_matches_requested"] is True
    )
    record["provider_display_name"] = payload.get("provider")
    record["response_id"] = payload.get("id")
    choices = payload.get("choices") or []
    record["finish_reason"] = (
        choices[0].get("finish_reason")
        if choices and isinstance(choices[0], Mapping)
        else None
    )
    assistant_text, refusal, content_type, content_error = (
        _extract_assistant_observation(payload)
    )
    record["assistant_content_transport_type"] = content_type
    record["assistant_refusal"] = refusal
    record["assistant_output"] = assistant_text
    if assistant_text is None:
        record["assistant_content_error"] = content_error
        record["acceptance"] = evaluate_raw_move_through_ced_v1(
            None, provider_id="live_seat_1"
        )
        record["acceptance"]["provider_structured_output_error"] = content_error
        record["result"] = "NO_STRUCTURED_ASSISTANT_OUTPUT"
        return record
    record["acceptance"] = evaluate_raw_move_through_ced_v1(
        assistant_text,
        provider_id="live_seat_1",
    )
    record["result"] = "COMPLETED"
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one no-retry structured Socratic arm"
    )
    parser.add_argument("--arm", choices=tuple(ARM_MODELS), required=True)
    parser.add_argument("--model", choices=tuple(ARM_MODELS.values()), required=True)
    parser.add_argument("--prompt-ceiling", required=True)
    parser.add_argument("--completion-ceiling", required=True)
    parser.add_argument("--request-ceiling", required=True)
    parser.add_argument("--maximum-arm-spend-usd", required=True)
    parser.add_argument("--operator-statement", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    output_path = Path(args.out).resolve()
    if output_path.exists():
        raise SystemExit(f"REFUSING: write-once evidence exists: {output_path}")

    record: Dict[str, Any] = {}
    try:
        record = run_arm(args, record)
    except Exception as exc:  # one failed arm is evidence; never retry here
        record.setdefault(
            "schema_version", "socrateszero-openrouter-structured-socratic-arm/v1"
        )
        record.setdefault("experiment", "structured-socratic-move-v1")
        record.setdefault("arm", args.arm)
        record.setdefault("requested_model", ARM_MODELS[args.arm])
        record.setdefault("question", CONTROL_QUESTION_V1)
        record.setdefault("role", "socrates")
        record.setdefault("phase", "opening")
        record.setdefault("automatic_retries", 0)
        record.setdefault("retry_count", 0)
        record.setdefault("http_success", False)
        record["result"] = "FAILED_BEFORE_RESULT_COMPLETION"
        record["failure_class"] = type(exc).__name__
        record["failure_message"] = str(exc)
        record["completed_utc"] = _utc_now()
    else:
        record["completed_utc"] = _utc_now()

    artifact_sha256 = _write_once_json(output_path, record)
    summary = {
        "arm": record.get("arm"),
        "model": record.get("requested_model"),
        "result": record.get("result"),
        "http_status": (record.get("transport") or {}).get("http_status"),
        "provider_structured_output_valid": (
            record.get("acceptance") or {}
        ).get("provider_structured_output_valid"),
        "ced_schema_accepted": (record.get("acceptance") or {}).get(
            "ced_schema_accepted"
        ),
        "socratic_move_accepted": (record.get("acceptance") or {}).get(
            "socratic_move_accepted"
        ),
        "inference_dispatches": record.get("inference_dispatches", 0),
        "retry_count": record.get("retry_count", 0),
        "artifact_path": str(output_path),
        "artifact_sha256": artifact_sha256,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
