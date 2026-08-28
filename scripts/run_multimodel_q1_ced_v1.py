"""Q1 Condition C: one heterogeneous Socrates/CED dialogue, two model families.

The normal harness in ``run_socrates_live_v1`` builds every worker seat on the
same Flex endpoint, and its pre-dispatch guard asserts the frozen Flex model,
selector and price ceilings byte for byte.  That guard is correct for a
homogeneous run and fatal for this one, so this file keeps the same structural
checks and parameterises them per seat instead of weakening the frozen one.

Alpha is GPT-5 Mini on ``openai/flex``.  Gamma is Gemini 3.7 Flash on
``google-vertex/global/flex``.  Both endpoints advertise ``max_tokens``,
``seed``, ``response_format`` and ``structured_outputs`` in their own live
listing, which is what makes one shared CED task contract legal on both.

Condition A already showed all four families answering Q1 correctly, so this
run is a negative control: does a council preserve a unanimous correct answer,
or does deliberation talk it out of one?  That is the question this file can
answer; it cannot show improvement, because there is no headroom left to show.

Evaluator keys never appear here.  Scoring happens after collection closes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_multimodel_q1_v1 as q1
import scripts.run_socrates_live_v1 as normal
from backend.dialogues.socrates_zero.contracts import (
    ContractValidationError,
    canonical_json,
)
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    SocratesLiveOpenRouterAdapter,
)
from backend.dialogues.socrates_zero.openrouter_request_bounds_v1 import (
    EstimatorUnsupportedError,
    RequestBoundError,
    assert_request_within_bounds_v1,
    build_refusal_receipt_v1,
    measure_request_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterEndpointCapabilityProfileV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterSessionLedgerV1,
)

CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero\openrouter-multimodel-q1-ced-v1"
)

#: The three output envelopes the CED task router can ask for.
OUTPUT_ENVELOPES_V1: Tuple[int, ...] = (
    normal.SHORT_OUTPUT_TOKENS_V1,
    normal.REVISION_OUTPUT_TOKENS_V1,
    normal.SYNTHESIS_OUTPUT_TOKENS_V1,
)

#: Wire parameters the frozen Flex guard forbids, kept identical here.
FORBIDDEN_WIRE_PARAMETERS_V1: Tuple[str, ...] = (
    "temperature",
    "reasoning",
    "reasoning_effort",
    "include_reasoning",
    "tools",
    "tool_choice",
)

#: A **local experiment prompt budget**, in tokens. It is not a provider
#: limit and is deliberately unrelated to one.
#:
#: Provenance of what it replaced: the previous 65,536 was Gemini's
#: `data.endpoints[0].max_completion_tokens` — an *output* field for one
#: seat — used as an input bound for all three, then enforced by comparing
#: characters against it.
#:
#: This value is a local budget with two jobs: it is what
#: `conservative_turn_cost_bound_v1` reserves against, and it caps how much
#: accumulated dialogue one turn may carry. It is independent of every
#: endpoint's context window (400,000 / 1,048,576 / 1,047,576 tokens) and of
#: every endpoint's output limit; the context window is checked separately
#: and always applies as well.
#:
#: The value is set by the spend ceiling, not by any single request. Because
#: the byte-backed bound runs roughly 3.2x to 4x actual tokens, and the same
#: number both caps the prompt and drives the conservative cost reservation,
#: the reservation inherits that looseness: 262,144 would reserve $6.91 for
#: 64 calls, and 196,608 would reserve $5.59, both over the operator's $5.00
#: ceiling. 131,072 is the largest power of two whose 64-call reservation
#: stays under it, at $4.27.
#:
#: What that buys: 77% headroom over a scale-faithful reconstruction of the
#: Q2b turn that was refused (74,156 tokens upper bound). Whether the later
#: synthesis turn, which carries the reconstruction as well, also fits is
#: genuinely unknown. If it does not, the guard refuses it correctly, at no
#: cost, with a classified receipt — which is the behaviour this repair was
#: built to produce.
EXPERIMENT_PROMPT_BUDGET_TOKENS_V1 = 131_072

#: The cost-reservation call sites take a token count. Same value, same unit.
DECLARED_MAX_INPUT_TOKENS_V1 = EXPERIMENT_PROMPT_BUDGET_TOKENS_V1


def build_seat_policy_v1(
    key: str, output_limit_tokens: int
) -> OpenRouterFrozenExecutionPolicyV1:
    """One seat's execution policy at one declared output envelope."""

    if output_limit_tokens not in OUTPUT_ENVELOPES_V1:
        raise ContractValidationError("CED output envelope is not declared")
    spec = q1.FAMILIES_V1[key]
    if spec["output_field"] not in ("max_tokens", "max_completion_tokens"):
        raise ContractValidationError(
            f"{key}: unknown endpoint output-limit field {spec['output_field']!r}"
        )
    return OpenRouterFrozenExecutionPolicyV1(
        model=spec["model"],
        provider_only=(spec["selector"],),
        provider_order=(spec["selector"],),
        output_limit_tokens=output_limit_tokens,
        temperature=None,
        seed=normal.REDUCED_SEED_V1,
        max_price_prompt_usd_per_million=spec["prompt_ceiling"],
        max_price_completion_usd_per_million=spec["completion_ceiling"],
        max_price_request_usd="0",
        bounded_timeout_seconds=120,
    )


def build_seat_policy_family_v1(
    key: str,
) -> Dict[int, OpenRouterFrozenExecutionPolicyV1]:
    return {limit: build_seat_policy_v1(key, limit) for limit in OUTPUT_ENVELOPES_V1}


#: Where construction evidence for a locally refused request is kept. Raw
#: prompt text never goes here: a refused CED prompt holds the whole
#: dialogue, and archiving it would open a raw-prompt store outside the
#: evidence boundary this branch has kept throughout.
REFUSAL_RECEIPT_DIRECTORY_V1 = q1.RUNS / "refusal_receipts"

#: Context window in tokens for each seat's exact endpoint, read from that
#: endpoint's own retained listing rather than assumed.
SEAT_CONTEXT_WINDOW_TOKENS_V1: Dict[str, int] = {
    "gpt_5_mini": 400_000,
    "gemini_3_7_flash_standard": 1_048_576,
    "gemini_3_7_flash": 1_048_576,
    "gpt_4_1_mini": 1_047_576,
}


def assert_input_within_bound_v1(
    key: str, body: Dict[str, Any], reserved_output_tokens: int
) -> Dict[str, Any]:
    """Bound one rendered request, never comparing across units.

    Returns the measurement so a refusal can record what it saw.
    """

    context_window = SEAT_CONTEXT_WINDOW_TOKENS_V1.get(key)
    if context_window is None:
        raise ContractValidationError(f"{key}: no recorded endpoint context window")
    selector = q1.FAMILIES_V1[key]["selector"]
    try:
        measurement = measure_request_v1(
            body,
            reserved_output_tokens=reserved_output_tokens,
            context_window_tokens=context_window,
            provider_selector=selector,
        )
    except EstimatorUnsupportedError as exc:
        raise ContractValidationError(f"{key}: {exc}") from exc
    try:
        assert_request_within_bounds_v1(
            measurement, max_prompt_tokens=EXPERIMENT_PROMPT_BUDGET_TOKENS_V1
        )
    except RequestBoundError as exc:
        _persist_refusal_receipt_v1(key, body, measurement, exc)
        raise ContractValidationError(f"{key}: {exc}") from exc
    return measurement.as_record()


def _persist_refusal_receipt_v1(
    key: str, body: Dict[str, Any], measurement: Any, exc: Any
) -> None:
    """Keep construction evidence for a refused request, never its content.

    Q2b's refusals kept only a digest, which made the defect impossible to
    reproduce. The fix is not to archive the prompt: a refused CED prompt holds
    the entire dialogue, and storing it would open a raw-prompt archive outside
    the evidence boundary this branch has kept throughout. The receipt records
    the digest, the sizes, the estimator and the limits.
    """

    spec = q1.FAMILIES_V1[key]
    try:
        REFUSAL_RECEIPT_DIRECTORY_V1.mkdir(parents=True, exist_ok=True)
        receipt = build_refusal_receipt_v1(
            seat=key,
            model=spec["model"],
            phase=str(body.get("__phase", "")) or "unknown",
            task_kind="unknown",
            body=body,
            measurement=measurement,
            error=exc,
            source_artifact_references=(spec.get("evidence_file")
                                        or spec.get("evidence_path")
                                        or spec.get("retained_profile"),),
            refused_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        target = REFUSAL_RECEIPT_DIRECTORY_V1 / (
            f"refusal_{key}_{receipt['canonical_body_sha256'][:16]}.json"
        )
        target.write_text(canonical_json(receipt), encoding="utf-8")
    except OSError:
        pass  # evidence retention must never itself break a run


def seat_predispatch_guard_v1(key: str) -> Callable[..., None]:
    """Per-seat body-byte guard: the frozen Flex checks, this seat's constants."""

    spec = q1.FAMILIES_V1[key]
    expected_provider = {
        "allow_fallbacks": False,
        "max_price": {
            "completion": spec["completion_ceiling"],
            "prompt": spec["prompt_ceiling"],
            "request": "0",
        },
        "only": [spec["selector"]],
        "order": [spec["selector"]],
        "require_parameters": True,
    }

    def guard(task: Optional[Any], rendered: Any) -> None:
        if type(task) is not normal.AgentTask:
            raise ContractValidationError("CED pre-dispatch task is required")
        if type(rendered) is not normal.OpenRouterRenderedTurnV1:
            raise ContractValidationError("exact rendered-turn contract is required")
        expected_limit = normal.output_limit_for_task_v1(task)
        body = json.loads(rendered.canonical_body_json)
        assert_input_within_bound_v1(
            key, body, reserved_output_tokens=expected_limit
        )
        if body.get("model") != spec["model"]:
            raise ContractValidationError(f"{key}: rendered model drifted")
        # Which key carries the output bound is an endpoint property, not a
        # global one: the Flex endpoints use `max_tokens`, Azure uses
        # `max_completion_tokens`, and sending the wrong one under
        # `require_parameters` is what refused the S7C route.
        if body.get(spec["output_field"]) != expected_limit:
            raise ContractValidationError(f"{key}: rendered output bound drifted")
        if body.get("seed") != normal.REDUCED_SEED_V1:
            raise ContractValidationError(f"{key}: rendered seed drifted")
        for forbidden in FORBIDDEN_WIRE_PARAMETERS_V1:
            if forbidden in body:
                raise ContractValidationError(
                    f"{key}: forbidden wire parameter emitted: {forbidden}"
                )
        if body.get("provider") != expected_provider:
            raise ContractValidationError(f"{key}: rendered provider controls drifted")
        if body.get("stream") is not False:
            raise ContractValidationError(f"{key}: rendered stream control drifted")
        if body.get("response_format") != normal.ced_structured_response_format_v1(task):
            raise ContractValidationError(
                f"{key}: response schema differs from the exact CED task schema"
            )

    return guard


def conservative_ced_bound_v1() -> Dict[str, Any]:
    """Worst-case reservation for the whole council, before any spend."""

    calls = normal.NORMAL_MAXIMUM_CED_CALLS_V1
    per_seat = calls // len(q1.COUNCIL_SEATS_V1)
    seat_bounds: Dict[str, int] = {}
    total = 0
    for _alias, key in q1.COUNCIL_SEATS_V1:
        bound = q1.conservative_turn_cost_bound_v1(
            policy=build_seat_policy_v1(key, normal.SYNTHESIS_OUTPUT_TOKENS_V1),
            max_input_tokens=DECLARED_MAX_INPUT_TOKENS_V1,
        )
        seat_bounds[key] = bound
        total += per_seat * bound
    total += (calls - per_seat * len(q1.COUNCIL_SEATS_V1)) * max(seat_bounds.values())
    return {
        "ced_calls": calls,
        "seat_picodollars": seat_bounds,
        "total_picodollars": total,
        "maximum_per_call_picodollars": max(seat_bounds.values()),
    }


def build_heterogeneous_council_v1(
    ledger: OpenRouterSessionLedgerV1,
    *,
    claim_directory: Path,
    dispatch: Optional[Callable[..., Any]] = None,
) -> Tuple[Tuple[SocratesLiveOpenRouterAdapter, ...], Any]:
    """Two live seats on two different endpoints, one shared budget."""

    projector = normal.make_worker_payload_projector_v1()
    adapters: list[SocratesLiveOpenRouterAdapter] = []
    for index, (alias, key) in enumerate(q1.COUNCIL_SEATS_V1):
        spec = q1.FAMILIES_V1[key]
        profile: OpenRouterEndpointCapabilityProfileV1 = q1.load_profile_v1(key)
        family = build_seat_policy_family_v1(key)
        adapters.append(
            SocratesLiveOpenRouterAdapter(
                provider_id=normal.WORKER_PROVIDER_IDS_V1[index],
                policy=family[normal.SYNTHESIS_OUTPUT_TOKENS_V1],
                profile=profile,
                ledger=ledger,
                claim_directory=claim_directory,
                max_input_tokens=DECLARED_MAX_INPUT_TOKENS_V1,
                dispatch=dispatch,
                response_format_factory=normal.ced_structured_response_format_v1,
                structured_output_validator=normal.validate_ced_structured_output_v1,
                task_execution_policy_factory=normal._policy_for_task_factory_v1(family),
                outbound_task_state_projector=projector,
                pre_dispatch_guard=seat_predispatch_guard_v1(key),
                worker_alias=alias,
                expose_model_identity_to_worker=False,
                expected_returned_models=(spec["model"],),
                expected_provider_display_names=spec["provider_display"],
                ced_parse_repair_attempts=0,
            )
        )
    registry = normal.CouncilProviderRegistry(provider_timeout_seconds=125.0)
    for adapter in adapters:
        registry.register(adapter)
    fake = normal.FakeProvider()
    agents = [
        normal.SocraticAgent(f"agent_{index}", fake)
        for index in range(normal.NORMAL_LOGICAL_AGENTS_V1)
    ]
    ced = normal.CEDOrchestrator(
        agents,
        fake,
        registry=registry,
        shadow_scoring_mode=normal.ShadowScoringMode.ALL_PHASES,
        phase_retry=False,
        max_socratic_followups=2,
        ratification_repair="block",
        tree_expansions=0,
        ai_learning=False,
    )
    return tuple(adapters), ced


def error_retaining_dispatch_v1(
    directory: Path, inner: Callable[..., Any]
) -> Callable[..., Any]:
    """Persist the provider evidence the frozen turn record cannot hold.

    Two things are kept, both read-only observations of bytes that already
    crossed the wire. Neither changes the request.

    *Error envelopes.* OpenRouter reports upstream failures as HTTP 200 with an
    error object in the body, and the turn record keeps only the envelope
    *kind*. That is how the first heterogeneous attempt recorded ``ERROR`` and
    discarded the 487 bytes reading ``code: 429``, which in turn is how this
    file came to carry a confident and wrong schema diagnosis.

    *Finish reasons and usage.* ``OpenRouterTurnRecordV1`` is frozen and has no
    ``finish_reason`` field, so a truncated completion is indistinguishable from
    a malformed one in the run artifact. Both Gemini ``synthesis_draft`` turns
    returned JSON cut off mid-sentence with no usage block; whether that is an
    output cap consumed by reasoning tokens is decidable from
    ``finish_reason``, and only from there.

    Request headers never reach this function, so no credential can be written.
    """

    def observe(payload: Any, model: str) -> Dict[str, Any]:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        first = choices[0] if isinstance(choices, list) and choices else {}
        usage = payload.get("usage") if isinstance(payload, dict) else None
        return {
            "model_requested": model,
            "finish_reason": first.get("finish_reason")
            if isinstance(first, dict)
            else None,
            "native_finish_reason": first.get("native_finish_reason")
            if isinstance(first, dict)
            else None,
            "usage": usage if isinstance(usage, dict) else None,
        }

    def dispatch(**kwargs: Any) -> Any:
        result = inner(**kwargs)
        raw = getattr(result, "raw_response_body", None)
        if not isinstance(raw, (bytes, bytearray)):
            return result
        try:
            request = json.loads(kwargs["body_bytes"].decode("utf-8"))
        except (ValueError, UnicodeDecodeError, KeyError):
            request = {}
        try:
            payload = json.loads(bytes(raw).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return result
        directory.mkdir(parents=True, exist_ok=True)
        stamp = f"{time.time_ns()}"
        trace = directory / "finish_reasons.jsonl"
        with trace.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"stamp": stamp, **observe(payload, request.get("model", ""))}
                )
                + "\n"
            )
        if isinstance(payload, dict) and "error" in payload:
            (directory / f"provider_error_{stamp}.json").write_bytes(bytes(raw))
            (directory / f"provider_error_{stamp}.request.json").write_bytes(
                kwargs["body_bytes"]
            )
        return result

    return dispatch


def _public_audit_v1(audit: Any) -> Optional[Dict[str, Any]]:
    """Keep the CED audit fields that explain a non-proceeding outcome."""

    if not isinstance(audit, dict):
        return None
    keys = (
        "execution_mode",
        "proceeded",
        "quorum_failed",
        "blocked_phase",
        "warning",
        "provider_status_summary",
        "registry_phase_rounds",
        "task_log_count",
    )
    return {k: audit[k] for k in keys if k in audit}


def _question_v1(name: str) -> Tuple[str, str]:
    """Return (text, sha256) for the named question, checked before use.

    Q1 is the saturated logic question: all four families answered it correctly,
    so it cannot measure whether a council adds anything. Q2 is the ethics
    argument, which did spread them. Q2's evaluator key machine-checks its own
    countermodel, and a council is not worth buying if that check fails.
    """

    if name == "q1":
        return q1.QUESTION_V1, q1.QUESTION_SHA256_V1
    if name != "q2":
        raise ContractValidationError(f"unknown question {name!r}")
    import scripts.q2_ethics_question_v1 as q2

    if not q2.verify_key_v1()["key_is_sound"]:
        raise ContractValidationError("Q2 evaluator key failed its own check")
    return q2.QUESTION_V1, q2.QUESTION_SHA256_V1


def run_condition_c_v1(out: Path, question_name: str = "q1") -> Dict[str, Any]:
    """Execute one bounded heterogeneous dialogue and persist its record."""

    if out.exists():
        raise ContractValidationError(f"write-once artifact already exists: {out}")
    question_text, question_sha = _question_v1(question_name)
    plan = conservative_ced_bound_v1()
    print(f"=== council bound, question {question_name} ===")
    for key, value in plan["seat_picodollars"].items():
        print(f"  seat {q1.FAMILIES_V1[key]['label']:18s} ${q1._usd(value)} per call")
    print(f"  {plan['ced_calls']} calls total          ${q1._usd(plan['total_picodollars'])}")

    session_id = f"{question_name}-ced-hetero-{int(time.time())}"
    alpha_key = q1.COUNCIL_SEATS_V1[0][1]
    authorization = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement=(
            "Operator-authorized Q1 Condition C: one heterogeneous Socrates/CED "
            "dialogue with GPT-5 Mini and Gemini 3.7 Flash in the live seats. "
            "No baseline, no retry, no fallback."
        ),
        policy_id=build_seat_policy_v1(
            alpha_key, normal.SYNTHESIS_OUTPUT_TOKENS_V1
        ).policy_id or "",
        profile_id=q1.load_profile_v1(alpha_key).profile_id or "",
        model="multi-model",
        provider_selector="multi-endpoint",
        maximum_calls=plan["ced_calls"],
        maximum_total_spend_picodollars=plan["total_picodollars"],
        maximum_per_call_spend_picodollars=plan["maximum_per_call_picodollars"],
        session_id=session_id,
    )
    ledger = OpenRouterSessionLedgerV1(authorization)
    adapters, ced = build_heterogeneous_council_v1(
        ledger,
        claim_directory=CLAIM_STORE,
        dispatch=error_retaining_dispatch_v1(
            out.parent / "q1_condition_c_provider_errors",
            normal.dispatch_openrouter_one_live_inference_v1,
        ),
    )
    ready, warning = ced.registry.assess_readiness()
    if not ready:
        raise ContractValidationError(f"heterogeneous CED registry is not ready: {warning}")

    print(f"\n=== running {len(adapters)}-seat heterogeneous council ===")
    for alias, key in q1.COUNCIL_SEATS_V1:
        print(f"  {alias}: {q1.FAMILIES_V1[key]['label']} ({q1.FAMILIES_V1[key]['selector']})")
    started = time.perf_counter()
    error: Optional[str] = None
    final: Any = None
    try:
        final = asyncio.run(
            ced.run_registry_session(question_text, session_id=session_id)
        )
    except Exception as exc:  # retain one bounded run failure; never retry
        error = f"{type(exc).__name__}: {exc}"[:1000]
    latency_ms = round((time.perf_counter() - started) * 1000, 1)

    turns = [row for adapter in adapters for row in adapter.observability_rows()]
    if error is not None:
        status = "STOPPED_WITH_ERROR"
    elif ledger.fatal_failure is not None:
        status = "STOPPED_FATAL"
    else:
        status = "ORCHESTRATION_RETURNED"
    record = {
        "schema_version": "socrates-multimodel-q1-ced/v1",
        "condition": "C_heterogeneous_ced",
        "session_id": session_id,
        "question": question_name,
        "question_sha256": question_sha,
        "run_status": status,
        "error": error,
        "latency_ms": latency_ms,
        "council_seats": [
            {
                "alias": alias,
                "family": key,
                "model": q1.FAMILIES_V1[key]["model"],
                "provider_selector": q1.FAMILIES_V1[key]["selector"],
            }
            for alias, key in q1.COUNCIL_SEATS_V1
        ],
        "conservative_bound_usd": q1._usd(plan["total_picodollars"]),
        "calls_consumed": ledger.calls_consumed,
        "observed_cost_picodollars": ledger.observed_picodollars,
        "observed_cost_usd": q1._usd(ledger.observed_picodollars),
        "ledger_fatal_failure": ledger.fatal_failure,
        "outcome": normal._ced_outcome_summary_v1(final),
        # `_ced_outcome_summary_v1` reports *that* quorum failed, never why.
        # `_registry_fallback_final` puts the phase it blocked at, the warning
        # and the per-phase provider verdicts in `audit_summary`, and without
        # them a clean 17-of-17 run that still fails quorum is uninterpretable.
        "audit_summary": _public_audit_v1(getattr(final, "audit_summary", None)),
        "blocking_objections": [
            str(o)[:500] for o in (getattr(final, "blocking_objections", None) or [])
        ],
        "turns": turns,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical_json(record), encoding="utf-8")
    print(f"\n  status: {status}")
    if error:
        print(f"  error: {error}")
    print(f"  calls: {ledger.calls_consumed} | observed: ${q1._usd(ledger.observed_picodollars)}")
    print(f"  written: {out}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Q1 Condition C heterogeneous CED")
    parser.add_argument(
        "--out", type=Path, default=q1.RUNS / "q1_condition_c_heterogeneous_ced_v1.json"
    )
    parser.add_argument(
        "--question",
        choices=("q1", "q2"),
        default="q1",
        help="q1 is the saturated logic question; q2 is the ethics argument",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="print the conservative bound and the rendered seat wire shapes only",
    )
    args = parser.parse_args()
    if args.plan_only:
        plan = conservative_ced_bound_v1()
        for key, value in plan["seat_picodollars"].items():
            print(f"  seat {q1.FAMILIES_V1[key]['label']:18s} ${q1._usd(value)} per call")
        print(f"  {plan['ced_calls']} calls total          ${q1._usd(plan['total_picodollars'])}")
        return 0
    run_condition_c_v1(args.out, question_name=args.question)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
