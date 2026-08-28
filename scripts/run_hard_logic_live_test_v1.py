"""Run one frozen GPT-5 Mini baseline versus one normal Socrates/CED dialogue.

This is an additive, one-shot experiment wrapper.  It does not alter CED or
the prepared normal runner.  Both conditions are built before the first paid
POST, share one exact question and one bounded ledger, and use the proven
OpenAI Flex endpoint.  Evaluator answers are deliberately absent from this
module and are applied only after collection has closed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    execute_bounded_text_turn_v1,
    sanitize_public_assistant_output_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    PICODOLLARS_PER_USD,
    OpenRouterDynamicTurnRequestV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterRenderedTurnV1,
    OpenRouterSessionLedgerV1,
    conservative_turn_cost_bound_v1,
    render_dynamic_turn_v1,
)
from backend.dialogues.socrates_zero.openrouter_one_live_shadow_v1 import (
    dispatch_openrouter_one_live_inference_v1,
    openrouter_credential_is_present_v1,
)
from backend.dialogues.socrates_zero.openrouter_reduced_benchmark_safety_v1 import (
    REDUCED_MAX_INPUT_TOKENS_V1,
    REDUCED_MODEL_V1,
    REDUCED_PROVIDER_DISPLAY_NAME_V1,
    REDUCED_PROVIDER_SELECTOR_V1,
    assert_reduced_flex_rendered_turn_v1,
    fetch_flex_endpoint_listing_once_v1,
)
from scripts.run_reduced_socrates_benchmark_v1 import (
    _validate_baseline_output_v1,
    baseline_response_format_v1,
)
from scripts import run_socrates_live_v1 as normal


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BRANCH_RUN_DIRECTORY = (
    REPOSITORY_ROOT
    / "docs"
    / "branches"
    / "feature-socrates-zero-openrouter-live-routing-repair-v1"
    / "runs"
)
DEFAULT_COLLECTION_PATH = (
    BRANCH_RUN_DIRECTORY / "hard_logic_live_test_collection_v1.json"
)
CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    r"\openrouter-hard-logic-live-test-claims-v1"
)
RUN_ATTEMPT_LATCH_DIRECTORY = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero"
    r"\openrouter-hard-logic-live-test-attempt-v1"
)

SCHEMA_VERSION_V1 = "socrates-hard-logic-live-test/v1"
MODEL_V1 = REDUCED_MODEL_V1
PROVIDER_SELECTOR_V1 = REDUCED_PROVIDER_SELECTOR_V1
PROVIDER_DISPLAY_NAME_V1 = REDUCED_PROVIDER_DISPLAY_NAME_V1
BASELINE_CALLS_V1 = 1
CED_MAXIMUM_CALLS_V1 = normal.NORMAL_MAXIMUM_CED_CALLS_V1
MAXIMUM_LIVE_CALLS_V1 = BASELINE_CALLS_V1 + CED_MAXIMUM_CALLS_V1
BASELINE_OUTPUT_TOKENS_V1 = normal.SYNTHESIS_OUTPUT_TOKENS_V1
AUTOMATIC_RETRIES_V1 = 0

# Retained paid evidence before this experiment:
# reduced benchmark + 4096 diagnostic + completed normal Socrates run.
# Summed from every observed_cost_picodollars in the retained run collections.
# The previous value predated the first hard-logic run and understated actual
# spend by about $0.70; a ledger that flatters itself is worse than none.
PRIOR_OBSERVED_SPEND_PICODOLLARS_V1 = 858_383_365_000
HARD_CUMULATIVE_SPEND_PICODOLLARS_V1 = 8 * PICODOLLARS_PER_USD
REMAINING_SPEND_PICODOLLARS_V1 = (
    HARD_CUMULATIVE_SPEND_PICODOLLARS_V1
    - PRIOR_OBSERVED_SPEND_PICODOLLARS_V1
)

# Corrected benchmark question. The previous wording said "is not allowed to
# chair" and "is not allowed to approve", which a model could legitimately read
# deontically — as a rule about permission rather than a factual implication —
# and so escape the contradiction without any logical error. Statements 3 and 4
# are now plain material implications, which removes that escape hatch.
QUESTION_V1 = """In an organization, the following six statements are true:

1. Anyone who chairs the final review has approved both report R and report S.
2. Anyone who has approved both R and S either examined the primary evidence or filed a formal exception.
3. Anyone who filed a formal exception did not chair the final review.
4. Anyone who examined the primary evidence without interviewing source T did not approve report S.
5. Mira chaired the final review.
6. Mira did not interview source T.

Are these six statements logically consistent?

If not:

* identify the forced contradiction;
* derive it step by step;
* identify a minimal inconsistent subset;
* explain why removing any one member of that subset prevents the contradiction from being forced.

Use ordinary classical logic.

Do not use the principle of explosion to infer unrelated conclusions."""

# Filled from the exact UTF-8 question before live execution and locked by tests.
QUESTION_SHA256_V1 = (
    "ac62ad0e11f5517e361399391643c583ae166be771de13c6a8d10dda404b2ead"
)

BASELINE_SYSTEM_PROMPT_V1 = (
    "Answer the user's problem directly and concisely. State the conclusion, "
    "the reasoning that supports it, and any relevant uncertainty or "
    "limitation. Do not mention a council or evaluator."
)

# Only section labels are guarded here.  The evaluator answer itself is not
# imported, defined, or readable by this collection process.
FORBIDDEN_COLLECTION_VALUES_V1 = (
    "EVALUATOR-ONLY KEY",
    "Correct derivation:",
    "Expected minimal inconsistent subset:",
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _usd_text(picodollars: int) -> str:
    return format(
        Decimal(picodollars) / Decimal(PICODOLLARS_PER_USD), "f"
    )


def _sanitize_public_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_public_assistant_output_v1(value)
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_public_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_public_value(item) for item in value]
    return value


def _ced_outcome_summary_v1(final: Any) -> Dict[str, Any]:
    scalar = lambda value: getattr(value, "value", value)
    return {
        "final_returned": final is not None,
        "synthesis_present": bool(getattr(final, "synthesis", None)),
        "ratified": getattr(final, "ratified", None),
        "ratification_status": scalar(
            getattr(final, "ratification_status", None)
        ),
        "release_decision": scalar(getattr(final, "release_decision", None)),
        "governing_epistemic_status": scalar(
            getattr(final, "governing_epistemic_status", None)
        ),
    }


def combined_cost_bound_v1() -> Dict[str, int]:
    """Derive the exact one-baseline plus phase-aware CED P19 bound."""

    static = normal.assert_normal_static_contract_v1()
    baseline_policy = normal.build_normal_execution_policy_v1(
        BASELINE_OUTPUT_TOKENS_V1
    )
    baseline = conservative_turn_cost_bound_v1(
        baseline_policy, REDUCED_MAX_INPUT_TOKENS_V1
    )
    ced = int(static["spend"]["structural_session_bound_picodollars"])
    return {
        "baseline_picodollars": baseline,
        "ced_picodollars": ced,
        "combined_picodollars": baseline + ced,
        "maximum_per_call_picodollars": max(
            baseline,
            int(static["spend"]["maximum_per_call_picodollars"]),
        ),
    }


def assert_static_contract_v1() -> Dict[str, Any]:
    """Close all question, lifecycle, retry, and spend gates offline."""

    if _sha256_text(QUESTION_V1) != QUESTION_SHA256_V1:
        raise ContractValidationError("hard-logic question bytes drifted")
    if not QUESTION_V1.startswith(
        "In an organization, the following six statements are true:"
    ):
        raise ContractValidationError("hard-logic question is not frozen")
    # The correction exists to remove a deontic reading; reintroducing that
    # wording would silently restore the escape hatch it was meant to close.
    for deontic in ("not allowed", "allowed to", "may not", "must not"):
        if deontic in QUESTION_V1:
            raise ContractValidationError(
                "corrected hard-logic question reintroduced deontic phrasing"
            )
    visible = BASELINE_SYSTEM_PROMPT_V1 + "\n" + QUESTION_V1
    for forbidden in FORBIDDEN_COLLECTION_VALUES_V1:
        if forbidden in visible:
            raise ContractValidationError(
                "evaluator-only material reached a frozen public prompt"
            )
    if AUTOMATIC_RETRIES_V1 != 0:
        raise ContractValidationError("hard-logic experiment enabled retries")
    if CED_MAXIMUM_CALLS_V1 != 64 or MAXIMUM_LIVE_CALLS_V1 != 65:
        raise ContractValidationError("hard-logic call structure drifted")
    if BASELINE_OUTPUT_TOKENS_V1 != 16_384:
        raise ContractValidationError("baseline output envelope drifted")
    static = normal.assert_normal_static_contract_v1()
    spend = combined_cost_bound_v1()
    if spend != {
        "baseline_picodollars": 66_384_000_000,
        "ced_picodollars": 3_552_256_000_000,
        "combined_picodollars": 3_618_640_000_000,
        "maximum_per_call_picodollars": 66_384_000_000,
    }:
        raise ContractValidationError("combined P19 arithmetic drifted")
    if spend["combined_picodollars"] > REMAINING_SPEND_PICODOLLARS_V1:
        raise ContractValidationError(
            "hard-logic bound exceeds the retained operator remainder"
        )
    if (
        REMAINING_SPEND_PICODOLLARS_V1
        - spend["combined_picodollars"]
        < PICODOLLARS_PER_USD
    ):
        raise ContractValidationError("less than $1 account headroom remains")
    return {"normal": static, "spend": spend}


def _baseline_turn_v1(session_id: str) -> OpenRouterDynamicTurnRequestV1:
    return OpenRouterDynamicTurnRequestV1(
        system_prompt=BASELINE_SYSTEM_PROMPT_V1,
        user_content=QUESTION_V1,
        role_seat="direct_baseline",
        dialogue_id=f"{session_id}-baseline",
        turn_id="baseline-1",
        dialogue_phase="baseline",
    )


def _assert_collection_body_isolation_v1(rendered: OpenRouterRenderedTurnV1) -> None:
    for forbidden in FORBIDDEN_COLLECTION_VALUES_V1:
        if forbidden in rendered.canonical_body_json:
            raise ContractValidationError(
                "evaluator-only material reached a provider-bound body"
            )


def _baseline_guard_v1(
    _task: object, rendered: OpenRouterRenderedTurnV1
) -> None:
    assert_reduced_flex_rendered_turn_v1(
        rendered,
        expected_output_limit_tokens=BASELINE_OUTPUT_TOKENS_V1,
        forbidden_values=FORBIDDEN_COLLECTION_VALUES_V1,
    )
    body = json.loads(rendered.canonical_body_json)
    messages = body.get("messages")
    expected_messages = [
        {"content": BASELINE_SYSTEM_PROMPT_V1, "role": "system"},
        {"content": QUESTION_V1, "role": "user"},
    ]
    if messages != expected_messages:
        raise ContractValidationError("baseline prompt or question drifted")
    if body.get("response_format") != baseline_response_format_v1():
        raise ContractValidationError("baseline response schema drifted")


def _ced_guard_v1(task: object, rendered: OpenRouterRenderedTurnV1) -> None:
    normal._normal_predispatch_guard_v1(task, rendered)
    _assert_collection_body_isolation_v1(rendered)


def _manifest_v1(*, profile_id: str, session_id: str) -> Dict[str, Any]:
    static = assert_static_contract_v1()
    policies = normal.build_normal_policy_family_v1()
    return {
        "schema_version": SCHEMA_VERSION_V1,
        "question_sha256": QUESTION_SHA256_V1,
        "baseline_system_prompt_sha256": _sha256_text(
            BASELINE_SYSTEM_PROMPT_V1
        ),
        "baseline_response_format_sha256": _sha256_text(
            canonical_json(baseline_response_format_v1())
        ),
        "model": MODEL_V1,
        "provider_selector": PROVIDER_SELECTOR_V1,
        "profile_id": profile_id,
        "session_id": session_id,
        "conditions": ["single_gpt5_mini_baseline", "socrates_ced"],
        "baseline_calls": BASELINE_CALLS_V1,
        "ced_maximum_calls": CED_MAXIMUM_CALLS_V1,
        "maximum_live_calls": MAXIMUM_LIVE_CALLS_V1,
        "automatic_retries": AUTOMATIC_RETRIES_V1,
        "baseline_output_tokens": BASELINE_OUTPUT_TOKENS_V1,
        "ced_output_limit_by_task_kind": {
            kind.value: limit
            for kind, limit in sorted(
                normal.NORMAL_OUTPUT_LIMIT_BY_TASK_KIND_V1.items(),
                key=lambda item: item[0].value,
            )
        },
        "policy_ids_by_output_limit": {
            str(limit): policy.policy_id
            for limit, policy in sorted(policies.items())
        },
        "prior_observed_spend_picodollars": (
            PRIOR_OBSERVED_SPEND_PICODOLLARS_V1
        ),
        "hard_cumulative_spend_picodollars": (
            HARD_CUMULATIVE_SPEND_PICODOLLARS_V1
        ),
        "remaining_spend_picodollars": REMAINING_SPEND_PICODOLLARS_V1,
        "combined_cost_bound": dict(static["spend"]),
        "evaluator_material_present": False,
        "protocol_frozen_before_first_post": True,
    }


def _consume_attempt_v1(
    manifest: Mapping[str, Any],
    directory: Path = RUN_ATTEMPT_LATCH_DIRECTORY,
) -> Dict[str, Any]:
    attempt_id = "szorhardlogictestv1_" + _sha256_text(canonical_json(manifest))
    target_directory = Path(directory).resolve()
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{attempt_id}.consumed.json"
    value = {
        "attempt_id": attempt_id,
        "manifest_sha256": _sha256_text(canonical_json(manifest)),
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
            "hard-logic live test authorization was already consumed"
        ) from exc
    return {
        **value,
        "latch_path": str(target),
        "latch_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _write_once_json_v1(path: Path, value: Mapping[str, Any]) -> str:
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
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
            f"write-once hard-logic artifact already exists: {target}"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def run_hard_logic_test_v1(
    *,
    output_path: Path = DEFAULT_COLLECTION_PATH,
    endpoint_fetch=fetch_flex_endpoint_listing_once_v1,
    dispatch=dispatch_openrouter_one_live_inference_v1,
    claim_directory: Path = CLAIM_STORE,
    attempt_directory: Path = RUN_ATTEMPT_LATCH_DIRECTORY,
) -> Dict[str, Any]:
    """Collect both frozen conditions without evaluator-side scoring."""

    static = assert_static_contract_v1()
    target = Path(output_path).resolve()
    if target.exists():
        raise ContractValidationError(
            f"write-once hard-logic artifact already exists: {target}"
        )
    if dispatch is dispatch_openrouter_one_live_inference_v1 and (
        not openrouter_credential_is_present_v1()
    ):
        raise ContractValidationError("OPENROUTER_API_KEY is absent or placeholder")

    # The spend bound is closed above before this first network action.
    fetched = endpoint_fetch(bounded_timeout_seconds=30)
    if fetched.http_status != 200:
        raise ContractValidationError(
            f"fresh exact-endpoint GET failed with HTTP {fetched.http_status}"
        )

    prepared = normal.prepare_normal_live_run_v1(
        QUESTION_V1,
        fetched.raw_response_body,
        claim_directory=claim_directory,
        dispatch=dispatch,
    )
    session_id = prepared.session_id.replace(
        "normal-socrates-live-v1-", "hard-logic-live-v1-", 1
    )
    manifest = _manifest_v1(
        profile_id=prepared.profile.profile_id or "",
        session_id=session_id,
    )
    envelope = prepared.policies[normal.NORMAL_MAXIMUM_OUTPUT_TOKENS_V1]
    authorization = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement=(
            "Authorized single hard-logic comparison: one direct GPT-5 Mini "
            "baseline followed by one repository-native GPT-5 Mini Socrates/CED "
            "dialogue; zero retries; no fallback; cumulative $8 ceiling retained."
        ),
        policy_id=envelope.policy_id or "",
        profile_id=prepared.profile.profile_id or "",
        model=MODEL_V1,
        provider_selector=PROVIDER_SELECTOR_V1,
        maximum_calls=MAXIMUM_LIVE_CALLS_V1,
        maximum_total_spend_picodollars=static["spend"][
            "combined_picodollars"
        ],
        maximum_per_call_spend_picodollars=static["spend"][
            "maximum_per_call_picodollars"
        ],
        session_id=session_id,
    )
    ledger = OpenRouterSessionLedgerV1(authorization)

    # Rebind the already-verified prepared CED adapters to the fresh combined
    # experiment authorization before any task exists or POST can occur.
    prepared.session_id = session_id
    prepared.authorization = authorization
    prepared.ledger = ledger
    for adapter in prepared.adapters:
        adapter.ledger = ledger
        adapter._pre_dispatch_guard = _ced_guard_v1
    if any(adapter.ledger is not ledger for adapter in prepared.adapters):
        raise ContractValidationError("CED workers do not share the experiment ledger")
    ready, warning = prepared.ced.registry.assess_readiness()
    if not ready:
        raise ContractValidationError(f"hard-logic CED registry not ready: {warning}")

    baseline_turn = _baseline_turn_v1(session_id)
    baseline_policy = prepared.policies[BASELINE_OUTPUT_TOKENS_V1]
    rendered_baseline = render_dynamic_turn_v1(
        baseline_policy,
        prepared.profile,
        baseline_turn,
        response_format_override=baseline_response_format_v1(),
    )
    _baseline_guard_v1(None, rendered_baseline)

    # All prompts, schemas, topology, endpoint identity, and budgets are now
    # frozen. Burn the experiment latch immediately before the first paid POST.
    attempt = _consume_attempt_v1(manifest, attempt_directory)

    started = time.perf_counter()
    baseline_outcome = None
    final = None
    state = None
    error: Optional[str] = None
    baseline_phase_latency_ms: Optional[float] = None
    socrates_phase_latency_ms: Optional[float] = None
    try:
        baseline_started = time.perf_counter()
        baseline_outcome = execute_bounded_text_turn_v1(
            policy=baseline_policy,
            profile=prepared.profile,
            ledger=ledger,
            claim_directory=claim_directory,
            max_input_tokens=REDUCED_MAX_INPUT_TOKENS_V1,
            turn=baseline_turn,
            response_format_override=baseline_response_format_v1(),
            expected_returned_models=(MODEL_V1,),
            expected_provider_display_names=(PROVIDER_DISPLAY_NAME_V1,),
            pre_dispatch_guard=_baseline_guard_v1,
            dispatch=dispatch,
        )
        baseline_phase_latency_ms = round(
            (time.perf_counter() - baseline_started) * 1000, 3
        )
        if ledger.fatal_failure is None:
            socrates_started = time.perf_counter()
            final = asyncio.run(
                prepared.ced.run_registry_session(
                    QUESTION_V1, session_id=session_id
                )
            )
            socrates_phase_latency_ms = round(
                (time.perf_counter() - socrates_started) * 1000, 3
            )
    except Exception as exc:  # one retained attempt; never retry
        error = f"{type(exc).__name__}: {exc}"[:1000]
    latency_ms = round((time.perf_counter() - started) * 1000, 3)

    try:
        state = prepared.ced.get_session(session_id)
    except KeyError:
        state = None

    baseline_record = (
        baseline_outcome.record.model_dump(mode="json", exclude_none=False)
        if baseline_outcome is not None
        else None
    )
    baseline_text = (
        baseline_outcome.assistant_text
        if baseline_outcome is not None
        else None
    )
    baseline_valid, baseline_validation_error = _validate_baseline_output_v1(
        baseline_text
    )
    ced_turns = [
        row
        for adapter in prepared.adapters
        for row in adapter.observability_rows()
    ]
    all_records = (
        ([] if baseline_record is None else [baseline_record]) + ced_turns
    )
    ced_prompt_tokens = sum(
        int(row.get("prompt_tokens") or 0) for row in ced_turns
    )
    ced_completion_tokens = sum(
        int(row.get("completion_tokens") or 0) for row in ced_turns
    )
    ced_cost_picodollars = sum(
        int(row.get("observed_cost_picodollars") or 0) for row in ced_turns
    )
    baseline_cost_picodollars = int(
        (baseline_record or {}).get("observed_cost_picodollars") or 0
    )
    result: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_V1,
        "status": (
            "COLLECTION_COMPLETE"
            if error is None and ledger.fatal_failure is None
            else "COLLECTION_STOPPED"
        ),
        "question": QUESTION_V1,
        "question_sha256": QUESTION_SHA256_V1,
        "session_id": session_id,
        "manifest": manifest,
        "run_attempt": attempt,
        "endpoint_fetch": {
            "http_status": fetched.http_status,
            "latency_ms": fetched.latency_ms,
        },
        "endpoint_evidence": prepared.endpoint_evidence.model_dump(
            mode="json", exclude_none=False
        ),
        "profile": prepared.profile.model_dump(mode="json", exclude_none=False),
        "authorization": authorization.model_dump(mode="json", exclude_none=False),
        "baseline": {
            "assistant_output": (
                sanitize_public_assistant_output_v1(baseline_text)
                if isinstance(baseline_text, str)
                else None
            ),
            "provider_structured_output_valid": baseline_valid,
            "validation_error": baseline_validation_error,
            "failure_reason": (
                baseline_outcome.failure_reason
                if baseline_outcome is not None
                else "not_dispatched"
            ),
            "transport": baseline_record,
            "metrics": {
                "calls": 0 if baseline_record is None else 1,
                "prompt_tokens": (baseline_record or {}).get("prompt_tokens"),
                "completion_tokens": (baseline_record or {}).get(
                    "completion_tokens"
                ),
                "observed_cost_picodollars": baseline_cost_picodollars,
                "observed_cost_usd": _usd_text(baseline_cost_picodollars),
                "latency_ms": baseline_phase_latency_ms,
            },
        },
        "socrates": {
            "ced_outcome": _ced_outcome_summary_v1(final),
            "turns": ced_turns,
            "final": (
                final.model_dump(mode="json", exclude_none=False)
                if hasattr(final, "model_dump")
                else None
            ),
            "state": (
                state.model_dump(mode="json", exclude_none=False)
                if hasattr(state, "model_dump")
                else None
            ),
            "metrics": {
                "calls": len(ced_turns),
                "prompt_tokens": ced_prompt_tokens,
                "completion_tokens": ced_completion_tokens,
                "observed_cost_picodollars": ced_cost_picodollars,
                "observed_cost_usd": _usd_text(ced_cost_picodollars),
                "latency_ms": socrates_phase_latency_ms,
            },
        },
        "calls_consumed": ledger.calls_consumed,
        "maximum_live_calls": MAXIMUM_LIVE_CALLS_V1,
        "observed_cost_picodollars": ledger.observed_picodollars,
        "observed_cost_usd": _usd_text(ledger.observed_picodollars),
        "settled_cost_picodollars": ledger.settled_picodollars,
        "unsettled_reserved_picodollars": ledger.unsettled_reserved_picodollars,
        "committed_cost_picodollars": ledger.committed_picodollars,
        "retained_prior_spend_picodollars": (
            PRIOR_OBSERVED_SPEND_PICODOLLARS_V1
        ),
        "remaining_cumulative_after_run_picodollars": max(
            0,
            REMAINING_SPEND_PICODOLLARS_V1 - ledger.committed_picodollars,
        ),
        "latency_ms": latency_ms,
        "fatal_failure": ledger.fatal_failure,
        "error": error,
        "evaluator_material_imported_during_collection": False,
        "record_count": len(all_records),
    }
    result = _sanitize_public_value(result)
    artifact_sha256 = _write_once_json_v1(target, result)
    result["artifact_path"] = str(target)
    result["artifact_sha256"] = artifact_sha256
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the frozen one-problem hard-logic live comparison"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_COLLECTION_PATH)
    args = parser.parse_args(argv)
    result = run_hard_logic_test_v1(output_path=args.out)
    print(
        json.dumps(
            {
                "status": result["status"],
                "session_id": result["session_id"],
                "calls_consumed": result["calls_consumed"],
                "observed_cost_usd": result["observed_cost_usd"],
                "ced_outcome": result["socrates"]["ced_outcome"],
                "artifact_path": result["artifact_path"],
                "artifact_sha256": result["artifact_sha256"],
                "fatal_failure": result["fatal_failure"],
                "error": result["error"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "COLLECTION_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
