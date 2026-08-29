"""Q3 baselines: three independent samples per model.

Nothing about the protocol changes. Same question, same system prompt, same
strict response schema, same output budget, same endpoints, zero retries. The
only thing that varies is the sample index.

Why each sample gets its own session authorization: the claim store is
one-shot per identical rendered body, and five identical requests to the same
model render identical bytes. Sharing one authorization would mint the same
claim id five times and the second sample would be refused as a duplicate. A
per-sample authorization keeps the double-spend guard intact while allowing a
genuine repeated draw.

The evaluator key is not imported here. Scoring happens after collection.
"""

from __future__ import annotations

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

QUESTION_SHA256_V1 = "05453cb1a979966e14620e1e323fc667d463a74e4ad64edc34be74acb0347620"
SAMPLES_PER_MODEL_V1 = 3
OUTPUT_TOKENS_V1 = 16_384
MAX_INPUT_TOKENS_V1 = 65_536


def _question() -> str:
    import scripts.q3_ethics_question_v1 as q2

    if q2.QUESTION_SHA256_V1 != QUESTION_SHA256_V1:
        raise SystemExit("Q3 question text drifted from its pinned digest")
    if not q2.verify_key_v1()["key_is_sound"]:
        raise SystemExit("evaluator key failed its own machine check")
    return q2.QUESTION_V1


def main() -> int:
    question = _question()
    families = [family for _alias, family in q1.COUNCIL_SEATS_V1]
    bounds = {
        key: conservative_turn_cost_bound_v1(
            policy=q1.build_policy_v1(key, OUTPUT_TOKENS_V1),
            max_input_tokens=MAX_INPUT_TOKENS_V1,
        )
        for key in families
    }
    print("=== Q3 baselines: 3 samples x 3 models ===")
    for key in families:
        print(f"  {q1.FAMILIES_V1[key]['label']:18s} "
              f"{q1.FAMILIES_V1[key]['selector']:22s} "
              f"${q1._usd(bounds[key])} per call")

    run_id = f"q3-baselines-{int(time.time())}"
    samples: List[Dict[str, Any]] = []
    observed_total = 0

    for key in families:
        spec = q1.FAMILIES_V1[key]
        for index in range(1, SAMPLES_PER_MODEL_V1 + 1):
            session_id = f"{run_id}-{key}-{index}"
            ledger = OpenRouterSessionLedgerV1(
                OpenRouterLiveTestSessionAuthorizationV1(
                    operator_statement=(
                        "Q2d replication and stability benchmark: one independent "
                        "baseline draw. Protocol frozen; only the sample index varies."
                    ),
                    policy_id=q1.build_policy_v1(key, OUTPUT_TOKENS_V1).policy_id or "",
                    profile_id=q1.load_profile_v1(key).profile_id or "",
                    model=spec["model"],
                    provider_selector=spec["selector"],
                    # The dispatch latch is process-wide and takes its
                    # limit from here, so a per-sample value of 1 would
                    # exhaust it on the first call. The spend ceiling
                    # below still admits exactly one call per ledger.
                    maximum_calls=SAMPLES_PER_MODEL_V1 * 3,
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
                samples.append(row)
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
            samples.append(row)

    out = q1.RUNS / "q3_baselines_v1.json"
    out.write_text(
        canonical_json(
            {
                "schema_version": "socrates-q3-baselines/v1",
                "run_id": run_id,
                "question_sha256": QUESTION_SHA256_V1,
                "samples_per_model": SAMPLES_PER_MODEL_V1,
                "conservative_bound_per_call_picodollars": bounds,
                "samples": samples,
                "observed_cost_usd": q1._usd(observed_total),
            }
        ),
        encoding="utf-8",
    )
    print(f"\n  samples: {len(samples)} | observed: ${q1._usd(observed_total)}")
    print(f"  written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
