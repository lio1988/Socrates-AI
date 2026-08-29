"""Q1 multi-model dataset point: four independent answers + heterogeneous CED.

Condition A/B collects one independent answer from each of four model families.
Condition C runs the same corrected question through a genuine repository-native
Socrates/CED dialogue with two *different* families in the live seats.

Why two seats and not four. The conservative input reservation is 400,000
tokens, and Claude Sonnet 5 charges $2/M for input, so one Claude call reserves
$0.96 against a real spend of well under a cent. A four-family council would
reserve $22.53 for one question. Two seats at the proven scale reserve $6.34
total, which fits the operator's balance. Claude and GPT-4.1 Mini therefore
appear as independent answers but not as council seats, and this file says so
rather than quietly dropping them.

Evaluator keys never appear here. Scoring happens after collection closes.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_hard_logic_live_test_v1 as hardlogic
import scripts.run_reduced_socrates_benchmark_v1 as reduced
import scripts.run_socrates_live_v1 as normal
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
    OpenRouterEndpointCapabilityProfileV1,
    OpenRouterFrozenExecutionPolicyV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterSessionLedgerV1,
    conservative_turn_cost_bound_v1,
)

RUNS = (
    Path(__file__).resolve().parents[1]
    / "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs"
)
CLAIM_STORE = Path(
    r"C:\Users\spirc\AppData\Local\SocratesZero\openrouter-multimodel-q1-v1"
)

QUESTION_V1 = hardlogic.QUESTION_V1
QUESTION_SHA256_V1 = hardlogic.QUESTION_SHA256_V1
BASELINE_SYSTEM_PROMPT_V1 = hardlogic.BASELINE_SYSTEM_PROMPT_V1
BASELINE_OUTPUT_TOKENS_V1 = 16_384
MAX_INPUT_TOKENS_V1 = 400_000

#: Every family, with the exact endpoint its own live listing verified. The
#: output-limit field differs across them, which is precisely why a per-endpoint
#: profile exists rather than a model-level capability union.
FAMILIES_V1: Dict[str, Dict[str, Any]] = {
    "gpt_5_mini": {
        "label": "GPT-5 Mini",
        "model": "openai/gpt-5-mini",
        "selector": "openai/flex",
        "output_field": "max_tokens",
        "prompt_ceiling": "0.125",
        "completion_ceiling": "1",
        "provider_display": ("OpenAI",),
        # Reconstructed from the Flex profile already retained by the hard-logic
        # run, so this experiment needs no third metadata GET.
        "retained_profile": "hard_logic_live_test_collection_v1.json",
    },
    "claude_sonnet_5": {
        "label": "Claude Sonnet 5",
        "model": "anthropic/claude-sonnet-5",
        "selector": "anthropic",
        "output_field": "max_tokens",
        "prompt_ceiling": "2",
        "completion_ceiling": "10",
        "provider_display": ("Anthropic",),
        "evidence_file": "q1_claude_sonnet_5_endpoints_v1.json",
        "evidence_tag": "anthropic",
    },
    "gemini_3_7_flash": {
        "label": "Gemini 3.7 Flash",
        "model": "google/gemini-3.7-flash",
        "selector": "google-vertex/global/flex",
        "output_field": "max_tokens",
        "prompt_ceiling": "0.1875",
        "completion_ceiling": "0.9375",
        "provider_display": ("Google",),
        "evidence_file": "q1_gemini_3_7_flash_endpoints_v1.json",
        "evidence_tag": "google-vertex/global/flex",
    },
    "gpt_4_1_mini": {
        "label": "GPT-4.1 Mini",
        "model": "openai/gpt-4.1-mini",
        "selector": "azure/swedencentral",
        "output_field": "max_completion_tokens",
        "prompt_ceiling": "0.44",
        "completion_ceiling": "1.76",
        "provider_display": ("Azure",),
        "evidence_path": (
            "docs/branches/feature-socrates-zero-openrouter-one-live-shadow-v1"
            "/evidence/s7c_model_endpoints_response_v1.json"
        ),
        "evidence_tag": "azure/swedencentral",
    },
    "qwen3_235b": {
        "label": "Qwen3 235B",
        "model": "qwen/qwen3-235b-a22b-2507",
        "selector": "deepinfra/fp8",
        "output_field": "max_tokens",
        "prompt_ceiling": "0.09",
        "completion_ceiling": "0.55",
        "provider_display": ("DeepInfra",),
        "evidence_file": "q1_qwen3_235b_endpoints_v1.json",
        "evidence_tag": "deepinfra/fp8",
    },
    "gemini_3_7_flash_standard": {
        # Same model id as `gemini_3_7_flash`; only the tier differs. The flex
        # tier is the preemptible shared pool, and it is the one that produced
        # `engine_overloaded` / HTTP 429 and `finish_reason: error`. Selection
        # here is on tier semantics plus that observed failure mode — there is
        # no direct reliability measurement of the standard tier yet, and this
        # note exists so that is not mistaken for one.
        "label": "Gemini 3.7 Flash",
        "model": "google/gemini-3.7-flash",
        "selector": "google-vertex/global",
        "output_field": "max_tokens",
        # Raised 2026-08-29 from 0.375/1.875. Google doubled the published
        # google-vertex/global price after this protocol froze, so the old
        # ceiling excluded the endpoint and the router refused the opening
        # call with HTTP 404. The endpoint, model and evidence are unchanged,
        # so the frozen Gemini baseline measured here stays comparable; only
        # what we authorise paying moves. Live listing:
        # runs/q2d_gemini_endpoints_repriced_v1.json
        "prompt_ceiling": "0.75",
        "completion_ceiling": "3.75",
        "provider_display": ("Google",),
        "evidence_file": "q1_gemini_3_7_flash_endpoints_v1.json",
        "evidence_tag": "google-vertex/global",
    },
    "qwen3_32b": {
        "label": "Qwen3 32B",
        "model": "qwen/qwen3-32b",
        "selector": "deepinfra/fp8",
        "output_field": "max_tokens",
        "prompt_ceiling": "0.08",
        "completion_ceiling": "0.28",
        "provider_display": ("DeepInfra",),
        "evidence_file": "q1_qwen3_32b_endpoints_v1.json",
        "evidence_tag": "deepinfra/fp8",
    },
    "llama_4_scout": {
        "label": "Llama 4 Scout",
        "model": "meta-llama/llama-4-scout",
        "selector": "deepinfra/fp8",
        "output_field": "max_tokens",
        "prompt_ceiling": "0.1",
        "completion_ceiling": "0.3",
        "provider_display": ("DeepInfra",),
        "evidence_file": "q1_llama_4_scout_endpoints_v1.json",
        "evidence_tag": "deepinfra/fp8",
    },
    "llama_4_maverick": {
        "label": "Llama 4 Maverick",
        "model": "meta-llama/llama-4-maverick",
        "selector": "deepinfra/base",
        "output_field": "max_tokens",
        "prompt_ceiling": "0.2",
        "completion_ceiling": "0.8",
        "provider_display": ("DeepInfra",),
        "evidence_file": "q1_llama_4_maverick_endpoints_v1.json",
        "evidence_tag": "deepinfra/base",
    },
}

#: The operator's low-cost heterogeneous council, one seat per model family.
#:
#: Every seat is pinned to an endpoint validated at endpoint level, not at the
#: model-level parameter union that refused the S7C route. Each advertises
#: `seed`, `response_format` and `structured_outputs`, and each declares its own
#: output-limit field: three take `max_tokens`, Delta takes
#: `max_completion_tokens`.
#:
#: `temperature` is omitted on every seat. Alpha's Flex endpoint does not
#: advertise it at all, and under `require_parameters: true` sending it there
#: would empty the candidate set. Beta, Gamma and Delta do support it, so this
#: is a recorded discrepancy rather than a uniform capability.
#: Q2 council. Qwen3 32B and Llama 4 Scout are out on measured behaviour: with
#: the semantic floor enforced they produced `{"question": "1"}` and five copies
#: of `"M"`, and contributed nothing across every run. Claude Sonnet 5 is out on
#: arithmetic, not ability — it reserves $0.294912 per call, so sixteen calls
#: alone are $4.72 against a $5.00 ceiling.
#:
#: The three that remain are the ones Q2 actually spread apart: Gemini answered
#: it best (only model to name the fallacy fallacy and avoid reading premise 3's
#: necessary condition as sufficient), GPT-4.1 Mini answered it worst (228
#: tokens, no countermodel, no answer to the fourth question), and GPT-5 Mini
#: sat between them. If a council adds anything, this is where it shows.
COUNCIL_SEATS_V1 = (
    ("Alpha", "gpt_5_mini"),
    ("Beta", "gemini_3_7_flash_standard"),
    ("Gamma", "gpt_4_1_mini"),
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _usd(picodollars: int) -> str:
    return format(Decimal(picodollars) / Decimal(PICODOLLARS_PER_USD), "f")


def load_profile_v1(key: str) -> OpenRouterEndpointCapabilityProfileV1:
    """Build one endpoint profile from that family's own retained listing."""
    spec = FAMILIES_V1[key]
    if "retained_profile" in spec:
        stored = json.loads(
            (RUNS / spec["retained_profile"]).read_text(encoding="utf-8")
        )["profile"]
        return OpenRouterEndpointCapabilityProfileV1(
            provider_selector=stored["provider_selector"],
            canonical_model_observed=stored["canonical_model_observed"],
            supported_parameters=tuple(stored["supported_parameters"]),
            output_limit_parameter=stored["output_limit_parameter"],
            evidence_sha256=stored["evidence_sha256"],
        )
    if "evidence_file" in spec:
        raw = (RUNS / spec["evidence_file"]).read_bytes()
    else:
        raw = (Path(__file__).resolve().parents[1] / spec["evidence_path"]).read_bytes()
    listing = json.loads(raw.decode("utf-8"))["data"]
    match = [e for e in listing["endpoints"] if e.get("tag") == spec["evidence_tag"]]
    if len(match) != 1:
        raise ContractValidationError(
            f"{key}: expected exactly one {spec['evidence_tag']!r} endpoint"
        )
    endpoint = match[0]
    supported = tuple(sorted(endpoint["supported_parameters"]))
    if spec["output_field"] not in supported:
        raise ContractValidationError(
            f"{key}: endpoint does not support {spec['output_field']}"
        )
    return OpenRouterEndpointCapabilityProfileV1(
        provider_selector=spec["selector"],
        canonical_model_observed=str(endpoint.get("name") or listing["id"]),
        supported_parameters=supported,
        output_limit_parameter=spec["output_field"],
        evidence_sha256=_sha(raw),
    )


def build_policy_v1(key: str, output_tokens: int) -> OpenRouterFrozenExecutionPolicyV1:
    """One family's execution policy. Temperature is omitted for every family.

    Three of the four endpoints do not advertise ``temperature`` at all, and with
    ``require_parameters`` that would empty the candidate set exactly as the
    first live call did. Omitting it everywhere also keeps the four conditions
    comparable instead of quietly giving one family a different sampling setup.
    """
    spec = FAMILIES_V1[key]
    return OpenRouterFrozenExecutionPolicyV1(
        model=spec["model"],
        provider_only=(spec["selector"],),
        provider_order=(spec["selector"],),
        output_limit_tokens=output_tokens,
        temperature=None,
        response_format_type="json_object",
        max_price_prompt_usd_per_million=spec["prompt_ceiling"],
        max_price_completion_usd_per_million=spec["completion_ceiling"],
        max_price_request_usd="0",
        bounded_timeout_seconds=120,
    )


def conservative_plan_v1() -> Dict[str, Any]:
    """Exact hard bound for the whole Q1 experiment, before any spend."""
    baselines: Dict[str, int] = {}
    for key in FAMILIES_V1:
        policy = build_policy_v1(key, BASELINE_OUTPUT_TOKENS_V1)
        baselines[key] = conservative_turn_cost_bound_v1(policy, MAX_INPUT_TOKENS_V1)
    baseline_total = sum(baselines.values())

    ced_calls = normal.NORMAL_MAXIMUM_CED_CALLS_V1
    per_seat = ced_calls // len(COUNCIL_SEATS_V1)
    ced_total = 0
    seat_bounds: Dict[str, int] = {}
    for _, key in COUNCIL_SEATS_V1:
        policy = build_policy_v1(key, normal.NORMAL_MAXIMUM_OUTPUT_TOKENS_V1)
        bound = conservative_turn_cost_bound_v1(policy, MAX_INPUT_TOKENS_V1)
        seat_bounds[key] = bound
        ced_total += per_seat * bound
    # A seat can be called more often than an even split, so charge the
    # remainder at the most expensive seat rather than assuming balance.
    ced_total += (ced_calls - per_seat * len(COUNCIL_SEATS_V1)) * max(
        seat_bounds.values()
    )
    return {
        "baseline_picodollars": baselines,
        "baseline_total_picodollars": baseline_total,
        "ced_calls": ced_calls,
        "ced_seat_picodollars": seat_bounds,
        "ced_total_picodollars": ced_total,
        "combined_picodollars": baseline_total + ced_total,
        "maximum_per_call_picodollars": max(
            list(baselines.values()) + list(seat_bounds.values())
        ),
    }


def run_baselines_v1(ledger: OpenRouterSessionLedgerV1, session_id: str) -> List[Dict[str, Any]]:
    """One independent answer per family. They never see each other."""
    answers: List[Dict[str, Any]] = []
    for key, spec in FAMILIES_V1.items():
        profile = load_profile_v1(key)
        policy = build_policy_v1(key, BASELINE_OUTPUT_TOKENS_V1)
        turn = OpenRouterDynamicTurnRequestV1(
            system_prompt=BASELINE_SYSTEM_PROMPT_V1,
            user_content=QUESTION_V1,
            role_seat="independent_baseline",
            dialogue_id=f"{session_id}-baseline",
            turn_id=f"{session_id}-{key}",
            dialogue_phase="baseline",
        )
        started = time.perf_counter()
        try:
            outcome = execute_bounded_text_turn_v1(
                policy=policy,
                profile=profile,
                ledger=ledger,
                claim_directory=CLAIM_STORE,
                max_input_tokens=MAX_INPUT_TOKENS_V1,
                turn=turn,
                # The proven strict schema, identical for all four families.
                # A plain {"type": "json_object"} is rejected with HTTP 400 by
                # both OpenAI-family endpoints, and using different contracts
                # per family would make the four answers incomparable anyway.
                response_format_override=reduced.baseline_response_format_v1(),
                expected_returned_models=(spec["model"],),
                expected_provider_display_names=spec["provider_display"],
            )
            failure = outcome.failure_reason
            record = outcome.record
            text = outcome.assistant_text
        except Exception as exc:  # noqa: BLE001 - a bounded failure is a result
            answers.append(
                {
                    "family": key,
                    "label": spec["label"],
                    "model": spec["model"],
                    "provider_selector": spec["selector"],
                    "failure": f"{type(exc).__name__}: {exc}"[:300],
                }
            )
            continue
        answers.append(
            {
                "family": key,
                "label": spec["label"],
                "model": spec["model"],
                "provider_selector": spec["selector"],
                "profile_id": profile.profile_id,
                "request_id": record.request_id,
                "http_status": record.http_status,
                "prompt_tokens": record.prompt_tokens,
                "completion_tokens": record.completion_tokens,
                "observed_cost_picodollars": record.observed_cost_picodollars,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "actual_served_model": record.actual_served_model,
                "provider_display_name": record.provider_display_name,
                "retry_count": 0,
                "failure": failure,
                "answer": sanitize_public_assistant_output_v1(text) if text else None,
            }
        )
    return answers


def main() -> int:
    parser = argparse.ArgumentParser(description="Q1 multi-model dataset point")
    parser.add_argument("--baselines-only", action="store_true")
    parser.add_argument(
        "--out", type=Path, default=RUNS / "q1_multimodel_collection_v1.json"
    )
    args = parser.parse_args()

    plan = conservative_plan_v1()
    print("=== conservative hard bound, computed from live endpoint profiles ===")
    for key, value in plan["baseline_picodollars"].items():
        print(f"  baseline {FAMILIES_V1[key]['label']:18s} ${_usd(value)}")
    print(f"  baselines total                ${_usd(plan['baseline_total_picodollars'])}")
    for key, value in plan["ced_seat_picodollars"].items():
        print(f"  CED seat {FAMILIES_V1[key]['label']:18s} ${_usd(value)} per call")
    print(f"  CED {plan['ced_calls']} calls                   ${_usd(plan['ced_total_picodollars'])}")
    print(f"  COMBINED                       ${_usd(plan['combined_picodollars'])}")

    session_id = f"q1-multimodel-{int(time.time())}"
    session = OpenRouterLiveTestSessionAuthorizationV1(
        operator_statement="Operator-authorized Q1 multi-model dataset point",
        policy_id=build_policy_v1("gpt_5_mini", BASELINE_OUTPUT_TOKENS_V1).policy_id or "",
        profile_id=load_profile_v1("gpt_5_mini").profile_id or "",
        model="multi-model",
        provider_selector="multi-endpoint",
        maximum_calls=4 + plan["ced_calls"],
        maximum_total_spend_picodollars=plan["combined_picodollars"],
        maximum_per_call_spend_picodollars=plan["maximum_per_call_picodollars"],
        session_id=session_id,
    )
    ledger = OpenRouterSessionLedgerV1(session)

    print("\n=== Condition A/B: four independent answers ===")
    answers = run_baselines_v1(ledger, session_id)
    for a in answers:
        if a.get("failure") or a.get("http_status") != 200:
            print(f"  {a['label']:18s} FAILED: {a.get('failure') or a.get('http_status')}")
        else:
            print(
                f"  {a['label']:18s} http={a['http_status']} "
                f"tok={a['prompt_tokens']}/{a['completion_tokens']} "
                f"${_usd(a['observed_cost_picodollars'] or 0)} "
                f"{a['latency_ms']}ms"
            )

    collection = {
        "schema_version": "socrates-multimodel-q1/v1",
        "session_id": session_id,
        "question": QUESTION_V1,
        "question_sha256": QUESTION_SHA256_V1,
        "conservative_plan": {
            k: (_usd(v) if isinstance(v, int) else v)
            for k, v in plan.items()
        },
        "council_seats": [{"alias": a, "family": f} for a, f in COUNCIL_SEATS_V1],
        "families_excluded_from_council": ["claude_sonnet_5", "gpt_4_1_mini"],
        "exclusion_reason": (
            "conservative input reservation makes a four-family council cost "
            "$22.53 against an $8.80 balance"
        ),
        "independent_answers": answers,
        "calls_consumed": ledger.calls_consumed,
        "observed_cost_picodollars": ledger.observed_picodollars,
        "observed_cost_usd": _usd(ledger.observed_picodollars),
    }
    args.out.write_text(
        canonical_json(collection), encoding="utf-8"
    )
    print(f"\n  calls: {ledger.calls_consumed} | observed: ${_usd(ledger.observed_picodollars)}")
    print(f"  written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
