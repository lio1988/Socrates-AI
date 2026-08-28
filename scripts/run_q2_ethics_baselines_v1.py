"""Q2 independent baselines: does the ethics question discriminate at all?

Q1 was answered correctly by all four families, so it could not measure a
council. Before spending anything on a Q2 council, this asks the cheap question
first: do the four families disagree on Q2? If they are 4/4 again the question
is useless for the real experiment and nothing further should be bought.

No evaluator key is imported here. Scoring happens after collection closes.
"""

from __future__ import annotations

import json
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

QUESTION_SHA256_V1 = "1b20ffe116ab1f78e9cd63fc5722c5b0383d71492e311977d19d6cc7f375f8ad"

#: Q2b matched baselines: exactly the three council seats, in the operator's
#: order, on exactly the endpoint profiles the council will use. Claude is not
#: here — it stays a secondary historical benchmark and is not a seat, so it
#: does not belong in a matched comparison.
FAMILIES_V1 = tuple(family for _alias, family in q1.COUNCIL_SEATS_V1)

OUTPUT_TOKENS_V1 = 16_384
OUTPUT_NAME_V1 = "q2b_matched_baselines_v1.json"
MAX_INPUT_TOKENS_V1 = 65_536


def _question() -> str:
    """Read the question without importing the evaluator key alongside it."""
    import scripts.q2_ethics_question_v1 as q2

    if q2.QUESTION_SHA256_V1 != QUESTION_SHA256_V1:
        raise SystemExit("Q2 question text drifted from its pinned digest")
    return q2.QUESTION_V1


def main() -> int:
    question = _question()
    plan: Dict[str, int] = {}
    for key in FAMILIES_V1:
        plan[key] = conservative_turn_cost_bound_v1(
            policy=q1.build_policy_v1(key, OUTPUT_TOKENS_V1),
            max_input_tokens=MAX_INPUT_TOKENS_V1,
        )
    total = sum(plan.values())
    print("=== Q2 baseline hard bound ===")
    for key, value in plan.items():
        print(f"  {q1.FAMILIES_V1[key]['label']:18s} ${q1._usd(value)}")
    print(f"  total                  ${q1._usd(total)}")

    session_id = f"q2-ethics-baselines-{int(time.time())}"
    ledger = OpenRouterSessionLedgerV1(
        OpenRouterLiveTestSessionAuthorizationV1(
            operator_statement=(
                "Q2 ethics baselines: one independent answer per family, to test "
                "whether the question discriminates before any council is bought."
            ),
            policy_id=q1.build_policy_v1("gpt_5_mini", OUTPUT_TOKENS_V1).policy_id or "",
            profile_id=q1.load_profile_v1("gpt_5_mini").profile_id or "",
            model="multi-model",
            provider_selector="multi-endpoint",
            maximum_calls=len(FAMILIES_V1),
            maximum_total_spend_picodollars=total,
            maximum_per_call_spend_picodollars=max(plan.values()),
            session_id=session_id,
        )
    )

    print("\n=== four independent answers ===")
    answers: List[Dict[str, Any]] = []
    for key in FAMILIES_V1:
        spec = q1.FAMILIES_V1[key]
        started = time.perf_counter()
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
                    dialogue_id=f"{session_id}-baseline",
                    turn_id=f"{session_id}-{key}",
                    dialogue_phase="baseline",
                ),
                response_format_override=reduced.baseline_response_format_v1(),
                expected_returned_models=(spec["model"],),
                expected_provider_display_names=spec["provider_display"],
            )
        except Exception as exc:  # a bounded failure is a result
            print(f"  {spec['label']:18s} FAILED: {type(exc).__name__}: {exc}"[:160])
            answers.append({"family": key, "label": spec["label"],
                            "failure": f"{type(exc).__name__}: {exc}"[:300]})
            continue
        record = outcome.record
        text = outcome.assistant_text
        print(
            f"  {spec['label']:18s} http={record.http_status} "
            f"tok={record.prompt_tokens}/{record.completion_tokens} "
            f"${q1._usd(record.observed_cost_picodollars or 0)} "
            f"{round((time.perf_counter() - started) * 1000)}ms"
        )
        answers.append(
            {
                "family": key,
                "label": spec["label"],
                "model": spec["model"],
                "http_status": record.http_status,
                "prompt_tokens": record.prompt_tokens,
                "completion_tokens": record.completion_tokens,
                "observed_cost_picodollars": record.observed_cost_picodollars,
                "failure": outcome.failure_reason,
                "answer": sanitize_public_assistant_output_v1(text) if text else None,
            }
        )

    out = q1.RUNS / OUTPUT_NAME_V1
    out.write_text(
        canonical_json(
            {
                "schema_version": "socrates-q2b-matched-baselines/v1",
                "session_id": session_id,
                "question": question,
                "question_sha256": QUESTION_SHA256_V1,
                "independent_answers": answers,
                "calls_consumed": ledger.calls_consumed,
                "observed_cost_usd": q1._usd(ledger.observed_picodollars),
            }
        ),
        encoding="utf-8",
    )
    print(f"\n  calls: {ledger.calls_consumed} | observed: ${q1._usd(ledger.observed_picodollars)}")
    print(f"  written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
