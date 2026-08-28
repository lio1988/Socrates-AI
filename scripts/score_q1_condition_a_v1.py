"""Evaluator-side scoring of Q1 Condition A. Runs only after collection closed.

This imports the evaluator key, so it must never be imported by a collection
process. It reads the retained collection artifact and writes a scored one.

The per-answer credits below are hand-adjudicated: the evaluator read each
answer and named the criteria it met. ``score_answer_v1`` only validates the
names and totals them, so a credit cannot drift onto a criterion that was never
declared.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.q1_evaluator_key_v1 as key
from backend.dialogues.socrates_zero.contracts import canonical_json

RUNS = (
    Path(__file__).resolve().parents[1]
    / "docs/branches/feature-socrates-zero-openrouter-live-routing-repair-v1/runs"
)

#: Hand-adjudicated credits, with the reason each withheld criterion failed.
ADJUDICATION_V1 = {
    "gpt_5_mini": {
        "credited": ("verdict", "contradiction", "derivation", "subset",
                     "removals", "countermodels"),
        "note": (
            "Only answer to prove minimality the way minimality is actually "
            "proved: six explicit truth assignments, one per removal. All six "
            "match the independently derived key exactly. Reached the "
            "contradiction by proof by cases on E or F rather than by "
            "disjunctive syllogism, which also discharges the F branch "
            "explicitly."
        ),
    },
    "claude_sonnet_5": {
        "credited": ("verdict", "contradiction", "derivation", "subset",
                     "removals"),
        "note": (
            "Derivation and all six removals are correct, but placed the "
            "subset and the removal analysis in the uncertainty field rather "
            "than the reasoning field. Justifies minimality by 'breaks a "
            "necessary link' rather than by exhibiting a satisfying "
            "assignment, which is an argument that the link is needed, not a "
            "proof that the remaining five are consistent."
        ),
    },
    "gemini_3_7_flash": {
        "credited": ("verdict", "contradiction", "derivation", "subset",
                     "removals"),
        "note": (
            "Cleanest and shortest correct derivation, correctly named the "
            "disjunctive syllogism step. Removal justifications are "
            "semi-formal ('allowing E to be false') and stop just short of "
            "exhibiting the assignments."
        ),
    },
    "gpt_4_1_mini": {
        "credited": ("verdict", "contradiction", "derivation", "subset",
                     "removals"),
        "note": (
            "Correct throughout. One imprecision outside the numbered steps: "
            "the summary says the approvals follow 'from statements 1 and 2', "
            "but statement 2 plays no part in deriving them. Removal "
            "justifications are informal, no assignments."
        ),
    },
}


def main() -> int:
    verification = key.verify_key_v1()
    if not verification["key_is_sound"]:
        raise SystemExit("evaluator key failed its own machine check")

    collection = json.loads(
        (RUNS / "q1_multimodel_collection_v1.json").read_text(encoding="utf-8")
    )
    scored = []
    for answer in collection["independent_answers"]:
        family = answer["family"]
        adjudication = ADJUDICATION_V1[family]
        parsed = json.loads(answer["answer"])
        full_text = " ".join(
            str(parsed.get(field, ""))
            for field in ("conclusion", "reasoning", "uncertainty")
        )
        result = key.score_answer_v1(full_text, credited=adjudication["credited"])
        scored.append(
            {
                "family": family,
                "label": answer["label"],
                "model": answer["model"],
                "completion_tokens": answer["completion_tokens"],
                "observed_cost_usd": answer["observed_cost_usd"]
                if "observed_cost_usd" in answer
                else None,
                "latency_ms": answer["latency_ms"],
                "score": result["score"],
                "maximum": result["maximum"],
                "criteria_met": result["criteria_met"],
                "criteria_missed": result["criteria_missed"],
                "note": adjudication["note"],
            }
        )

    scored.sort(key=lambda row: (-row["score"], row["completion_tokens"]))
    record = {
        "schema_version": "socrates-multimodel-q1-scored/v1",
        "condition": "A_independent_answers",
        "question_sha256": collection["question_sha256"],
        "key_verification": verification,
        "criteria": [
            {"name": name, "requirement": text} for name, text in key.Q1_CRITERIA_V1
        ],
        "maximum_score": key.Q1_MAXIMUM_SCORE_V1,
        "scored_answers": scored,
        "all_correct_on_core": all(
            {"verdict", "contradiction", "derivation"} <= set(row["criteria_met"])
            for row in scored
        ),
        "discriminating": len({row["score"] for row in scored}) > 1,
    }
    out = RUNS / "q1_condition_a_scored_v1.json"
    out.write_text(canonical_json(record), encoding="utf-8")

    print("=== Q1 Condition A, scored against the machine-verified key ===")
    print(f"key sound: {verification['key_is_sound']}\n")
    for row in scored:
        print(f"  {row['label']:18s} {row['score']}/{row['maximum']}  "
              f"({row['completion_tokens']:5d} completion tokens)")
        if row["criteria_missed"]:
            print(f"      missed: {', '.join(row['criteria_missed'])}")
    print(f"\n  all four correct on verdict+contradiction+derivation: "
          f"{record['all_correct_on_core']}")
    print(f"  written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
