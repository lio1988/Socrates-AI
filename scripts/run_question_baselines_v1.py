"""Independent baseline samples for any registered question.

This replaces a third near-copy of the same runner. run_q2d_baseline_replication_v1
and run_q3_baselines_v1 differ only in a pinned digest, an import and an output
filename; writing a fourth copy for Q4 would be the point at which the duplication
stops being cheaper than the parameter. The question now comes from the pinned
bundle, which re-derives its digests from the question module and refuses on drift,
so the identity guarantee is the same one the hard-coded digest gave.

Nothing else changes. Same system prompt, same strict response schema, same output
budget, same endpoints, zero retries, one sample per authorization.

Why each sample gets its own session authorization: the claim store is one-shot per
identical rendered body, and repeated identical requests to one model render
identical bytes. Sharing an authorization would mint the same claim id twice and the
second draw would be refused as a duplicate. Per-sample authorizations keep the
double-spend guard intact while still allowing a genuine repeated draw.

The dispatch latch is process-wide and takes its limit from the authorization, so
maximum_calls is the whole run's budget rather than one call; the spend ceiling below
still admits exactly one call per ledger.

The evaluator key is never imported here. Scoring happens after collection.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_multimodel_q1_v1 as q1
import scripts.run_reduced_socrates_benchmark_v1 as reduced
from backend.dialogues.socrates_zero.contracts import canonical_json
from backend.dialogues.socrates_zero.openrouter_live_session_adapter_v1 import (
    execute_bounded_text_turn_v1,
    sanitize_public_assistant_output_v1,
)
from backend.dialogues.socrates_zero.openrouter_live_session_v1 import (
    OpenRouterDynamicTurnRequestV1,
    OpenRouterLiveTestSessionAuthorizationV1,
    OpenRouterSessionLedgerV1,
    conservative_turn_cost_bound_v1,
)
from scripts.question_bundles_v1 import load_bundle_v1, load_question_module_v1

SAMPLES_PER_MODEL_V1 = 3
OUTPUT_TOKENS_V1 = 16_384
MAX_INPUT_TOKENS_V1 = 65_536


def _question_v1(name: str) -> str:
    """Return the question text, bound to its pinned bundle."""

    bundle = load_bundle_v1(name)
    module = load_question_module_v1(name)
    if module.QUESTION_SHA256_V1 != bundle["question_sha256"]:
        raise SystemExit(f"{name}: question text drifted from its pinned bundle")
    if not module.verify_key_v1()["key_is_sound"]:
        raise SystemExit(f"{name}: evaluator key failed its own machine check")
    return module.QUESTION_V1


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", required=True)
    parser.add_argument("--samples", type=int, default=SAMPLES_PER_MODEL_V1)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args(argv[1:])

    name = args.question
    samples_per_model = args.samples
    question = _question_v1(name)
    families = [family for _alias, family in q1.COUNCIL_SEATS_V1]
    bounds = {
        key: conservative_turn_cost_bound_v1(
            policy=q1.build_policy_v1(key, OUTPUT_TOKENS_V1),
            max_input_tokens=MAX_INPUT_TOKENS_V1,
        )
        for key in families
    }
    total_calls = samples_per_model * len(families)
    print(f"=== {name} baselines: {samples_per_model} samples x {len(families)} models ===")
    for key in families:
        print(
            f"  {q1.FAMILIES_V1[key]['label']:18s} "
            f"{q1.FAMILIES_V1[key]['selector']:22s} "
            f"${q1._usd(bounds[key])} per call"
        )
    worst = sum(bounds[key] * samples_per_model for key in families)
    print(f"  {total_calls} calls, worst case ${q1._usd(worst)}")
    if args.plan_only:
        return 0

    run_id = f"{name}-baselines-{int(time.time())}"
    rows: List[Dict[str, Any]] = []
    observed_total = 0

    for key in families:
        spec = q1.FAMILIES_V1[key]
        for index in range(1, samples_per_model + 1):
            session_id = f"{run_id}-{key}-{index}"
            ledger = OpenRouterSessionLedgerV1(
                OpenRouterLiveTestSessionAuthorizationV1(
                    operator_statement=(
                        f"{name} independent baseline: one draw. Protocol frozen; "
                        "only the sample index varies."
                    ),
                    policy_id=q1.build_policy_v1(key, OUTPUT_TOKENS_V1).policy_id or "",
                    profile_id=q1.load_profile_v1(key).profile_id or "",
                    model=spec["model"],
                    provider_selector=spec["selector"],
                    maximum_calls=total_calls,
                    maximum_total_spend_picodollars=bounds[key],
                    maximum_per_call_spend_picodollars=bounds[key],
                    session_id=session_id,
                )
            )
            started = time.perf_counter()
            row: Dict[str, Any] = {
                "family": key,
                "label": spec["label"],
                "model": spec["model"],
                "provider_selector": spec["selector"],
                "sample_index": index,
                "session_id": session_id,
            }
            try:
                outcome = execute_bounded_text_turn_v1(
                    policy=q1.build_policy_v1(key, OUTPUT_TOKENS_V1),
                    profile=q1.load_profile_v1(key),
                    ledger=ledger,
                    claim_directory=q1.CLAIM_STORE,
                    max_input_tokens=MAX_INPUT_TOKENS_V1,
                    turn=OpenRouterDynamicTurnRequestV1(
                        system_prompt=q1.BASELINE_SYSTEM_PROMPT_V1,
                        user_content=question,
                        role_seat="independent_baseline",
                        dialogue_id=f"{run_id}-baseline",
                        turn_id=session_id,
                        dialogue_phase="baseline",
                    ),
                    response_format_override=reduced.baseline_response_format_v1(),
                    expected_returned_models=(spec["model"],),
                    expected_provider_display_names=spec["provider_display"],
                )
            except Exception as exc:  # a bounded failure is a result, never a retry
                row["failure"] = f"{type(exc).__name__}: {exc}"[:300]
                print(f"  {spec['label']:18s} #{index} FAILED: {row['failure'][:90]}")
                rows.append(row)
                continue
            record = outcome.record
            observed_total += record.observed_cost_picodollars or 0
            row.update(
                {
                    "http_status": record.http_status,
                    "prompt_tokens": record.prompt_tokens,
                    "completion_tokens": record.completion_tokens,
                    "observed_cost_picodollars": record.observed_cost_picodollars,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "actual_served_model": record.actual_served_model,
                    "provider_display_name": record.provider_display_name,
                    "failure": outcome.failure_reason,
                    "retry_count": 0,
                    "answer": (
                        sanitize_public_assistant_output_v1(outcome.assistant_text)
                        if outcome.assistant_text
                        else None
                    ),
                }
            )
            print(
                f"  {spec['label']:18s} #{index} http={record.http_status} "
                f"tok={record.prompt_tokens}/{record.completion_tokens} "
                f"${q1._usd(record.observed_cost_picodollars or 0)} "
                f"{row['latency_ms']:.0f}ms"
            )
            rows.append(row)

    bundle = load_bundle_v1(name)
    out = q1.RUNS / f"{name}_baselines_v1.json"
    out.write_text(
        canonical_json(
            {
                "schema_version": "socrates-question-baselines/v1",
                "run_id": run_id,
                "question_name": name,
                "question_sha256": bundle["question_sha256"],
                "rubric_sha256": bundle["rubric_sha256"],
                "maximum_score": bundle["maximum_score"],
                "samples_per_model": samples_per_model,
                "conservative_bound_per_call_picodollars": bounds,
                "samples": rows,
                "observed_cost_usd": q1._usd(observed_total),
            }
        ),
        encoding="utf-8",
    )
    print(f"\n  samples: {len(rows)} | observed: ${q1._usd(observed_total)}")
    print(f"  written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
