"""Evaluator-side scoring for Q2. Imports the key, so never on a collection path.

Scores the four independent answers and, when present, the council synthesis, on
the same 23-point rubric, so "did the council beat its own best seat" is a
comparison of like with like.

Credits are hand-adjudicated: the evaluator reads each answer and names the
criteria it met. This file only validates the names, totals them, and records
the error flags, so a score cannot drift onto a criterion never declared.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.q2_ethics_question_v1 as key
import scripts.run_multimodel_q1_v1 as q1
from backend.dialogues.socrates_zero.contracts import canonical_json

RUNS = q1.RUNS

#: Hand-adjudicated from the retained baseline answers.
BASELINE_ADJUDICATION_V1: Dict[str, Dict[str, Any]] = {
    "gemini_3_7_flash": {
        "credited": (
            "validity_verdict", "locates_step_4", "names_the_equivocation",
            "countermodel", "countermodel_verified", "fallacy_fallacy",
            "resists_moral_pull",
        ),
        "flags": (),
        "note": (
            "The only answer to name the fallacy fallacy explicitly and the only "
            "one that did not slide from its countermodel into 'so a fair rule "
            "exists'. Shortest of the four at 1369 completion tokens."
        ),
    },
    "gpt_5_mini": {
        "credited": (
            "validity_verdict", "locates_step_4", "names_the_equivocation",
            "countermodel", "countermodel_verified", "resists_moral_pull",
        ),
        "flags": ("NECESSARY_CONDITION_READ_AS_SUFFICIENT",),
        "note": (
            "Stated the fallacy-fallacy point correctly — 'invalidity alone does "
            "not by itself show the conclusion is false' — and then undercut it "
            "in the next sentence: 'in that model the universal conclusion is "
            "false: a fair rule exists'. Premise 3 gives a necessary condition "
            "only, so ignoring no criterion cannot establish that R is fair. "
            "Credit for the fallacy-fallacy criterion is withheld because the "
            "answer ends on the error."
        ),
    },
    "claude_sonnet_5": {
        "credited": (
            "validity_verdict", "locates_step_4", "names_the_equivocation",
            "countermodel", "countermodel_verified", "resists_moral_pull",
        ),
        "flags": ("NECESSARY_CONDITION_READ_AS_SUFFICIENT",),
        "note": (
            "Best diagnosis of the equivocation of the four, and a four-patient "
            "countermodel with an explicit sensitivity check. But wrote 'by the "
            "committee's own definition, R is fair' — the same necessary-for-"
            "sufficient slip — and never answered the fourth question at all."
        ),
    },
    "gpt_4_1_mini": {
        "credited": (
            "validity_verdict", "locates_step_4", "names_the_equivocation",
            "resists_moral_pull",
        ),
        "flags": ("COUNTERMODEL_MISSING",),
        "note": (
            "Correct on validity, the step and the diagnosis, in 228 completion "
            "tokens. Attempted neither the countermodel nor the fourth question, "
            "so half the task is simply absent."
        ),
    },
}


def score_v1(credited: Sequence[str], flags: Sequence[str]) -> Dict[str, Any]:
    valid = {name for name, _d, _p in key.CRITERIA_V1}
    unknown = sorted(set(credited) - valid)
    if unknown:
        raise ValueError(f"unknown criteria: {unknown}")
    bad_flags = sorted(set(flags) - set(key.ERROR_FLAGS_V1))
    if bad_flags:
        raise ValueError(f"unknown error flags: {bad_flags}")
    met = [(n, p) for n, _d, p in key.CRITERIA_V1 if n in set(credited)]
    return {
        "criteria_met": [n for n, _p in met],
        "criteria_missed": [
            n for n, _d, _p in key.CRITERIA_V1 if n not in set(credited)
        ],
        "score": sum(p for _n, p in met),
        "maximum": key.MAXIMUM_SCORE_V1,
        "error_flags": list(flags),
    }


def main() -> int:
    verification = key.verify_key_v1()
    if not verification["key_is_sound"]:
        raise SystemExit("Q2 evaluator key failed its own machine check")

    baselines = json.loads(
        (RUNS / "q2_ethics_baselines_v1.json").read_text(encoding="utf-8")
    )
    rows: List[Dict[str, Any]] = []
    for answer in baselines["independent_answers"]:
        family = answer["family"]
        adjudication = BASELINE_ADJUDICATION_V1[family]
        result = score_v1(adjudication["credited"], adjudication["flags"])
        rows.append(
            {
                "condition": "independent",
                "family": family,
                "label": answer["label"],
                "completion_tokens": answer["completion_tokens"],
                "note": adjudication["note"],
                **result,
            }
        )
    rows.sort(key=lambda r: (-r["score"], r["completion_tokens"]))

    record = {
        "schema_version": "socrates-q2-scored/v1",
        "question_sha256": baselines["question_sha256"],
        "key_verification": verification,
        "rubric": [
            {"criterion": n, "requirement": d, "points": p}
            for n, d, p in key.CRITERIA_V1
        ],
        "maximum_score": key.MAXIMUM_SCORE_V1,
        "scored": rows,
        "best_independent": rows[0]["label"],
        "best_independent_score": rows[0]["score"],
        "discriminating": len({r["score"] for r in rows}) > 1,
    }
    out = RUNS / "q2_ethics_scored_v1.json"
    out.write_text(canonical_json(record), encoding="utf-8")

    print("=== Q2 independent answers, scored ===")
    print(f"key machine-check: {verification['key_is_sound']}\n")
    for r in rows:
        print(f"  {r['label']:18s} {r['score']:2d}/{r['maximum']}  "
              f"({r['completion_tokens']:5d} tok)")
        if r["criteria_missed"]:
            print(f"      missed: {', '.join(r['criteria_missed'])}")
        if r["error_flags"]:
            print(f"      flags : {', '.join(r['error_flags'])}")
    print(f"\n  discriminating: {record['discriminating']}")
    print(f"  best independent: {record['best_independent']} "
          f"at {record['best_independent_score']}/{key.MAXIMUM_SCORE_V1}")
    print(f"  written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
