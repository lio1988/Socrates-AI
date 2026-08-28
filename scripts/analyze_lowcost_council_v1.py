"""Evaluator-side analysis of the low-cost heterogeneous CED dialogue.

Imports the evaluator key, so it must never run on a collection path.

The central measurement is deliberately not "did CED accept the move". The CED
move schema constrains strings only by `minLength: 1` and `pattern: "\\S"`, so a
single character satisfies it, and two larger open-weight models have already
been observed filling every required field with one letter each. Acceptance is
therefore evidence about shape, not about contribution, and this file scores
substance separately.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.q1_evaluator_key_v1 as key
import scripts.run_multimodel_q1_v1 as q1
from backend.dialogues.socrates_zero.contracts import canonical_json

RUNS = q1.RUNS

#: A field value counts as placeholder if it carries no proposition. One or two
#: characters cannot; neither can a bare enumerator like "A." or "1)".
PLACEHOLDER_MAX_CHARS_V1 = 3
#: Below this, a "substantive" string is really a label, not a contribution.
SUBSTANTIVE_MIN_CHARS_V1 = 40


def _strings(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            out.extend(_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            if k in ("epistemic_marker", "operator"):
                continue  # enum slots, not prose
            out.extend(_strings(v))
        return out
    return []


def classify_move_v1(content: Any) -> Dict[str, Any]:
    """Separate a real contribution from one that merely fits the schema."""
    values = _strings(content)
    if not values:
        return {"verdict": "EMPTY", "strings": 0, "placeholder_ratio": 1.0,
                "longest": 0, "total_chars": 0}
    placeholders = [v for v in values if len(v.strip()) <= PLACEHOLDER_MAX_CHARS_V1]
    ratio = len(placeholders) / len(values)
    longest = max(len(v.strip()) for v in values)
    total = sum(len(v.strip()) for v in values)
    if ratio >= 0.5 or longest < SUBSTANTIVE_MIN_CHARS_V1:
        verdict = "PLACEHOLDER"
    elif total < SUBSTANTIVE_MIN_CHARS_V1 * 2:
        verdict = "THIN"
    else:
        verdict = "SUBSTANTIVE"
    return {"verdict": verdict, "strings": len(values),
            "placeholder_ratio": round(ratio, 3), "longest": longest,
            "total_chars": total}


#: Substantive ideas the key expects a correct treatment to contain. Used to
#: separate a novel useful contribution from a paraphrase of dialogue state.
IDEA_PATTERNS_V1: Tuple[Tuple[str, str], ...] = (
    ("inconsistent", r"inconsisten|unsatisfiab|contradict"),
    ("contradiction_on_S", r"(¬|not[ _]?)a?_?s\(|approved s.*not approved s|s\(m\).*¬s\(m\)"),
    ("contraposition_of_3", r"contrapos|modus tollens"),
    ("disjunction_elimination", r"disjunct|disjunction elimination|case analys"),
    ("minimal_subset_all_six", r"all six|\{1, ?2, ?3, ?4, ?5, ?6\}|entire set"),
    ("countermodel", r"countermodel|counter-model|assignment|satisf(y|ies|ying)"),
    ("classical_logic_caveat", r"non-?classical|intuitionis|material conditional|defeasible"),
)


def ideas_in(text: str) -> set:
    low = text.lower()
    return {name for name, pat in IDEA_PATTERNS_V1 if re.search(pat, low)}


RUBRIC_V1 = (
    ("consistency_verdict", 2),
    ("keyed_contradiction", 2),
    ("derivation", 4),
    ("minimal_inconsistent_subset", 3),
    ("minimality_proof", 6),
    ("explosion_restraint", 1),
)

ERROR_FLAGS_V1 = (
    "INVALID_CONTRAPOSITION",
    "INVALID_DISJUNCTION_ELIMINATION",
    "WRONG_MINIMAL_SUBSET",
    "EXPLOSION_ABUSE",
    "UNSUPPORTED_LOGICAL_STEP",
    "SEMANTIC_ESCAPE_HATCH_INTRODUCED",
)


def main(path: Path) -> int:
    verification = key.verify_key_v1()
    if not verification["key_is_sound"]:
        raise SystemExit("evaluator key failed its own machine check")

    run = json.loads(path.read_text(encoding="utf-8"))
    seat_family = {a: f for a, f in q1.COUNCIL_SEATS_V1}
    model_label = {q1.FAMILIES_V1[f]["model"]: q1.FAMILIES_V1[f]["label"]
                   for _a, f in q1.COUNCIL_SEATS_V1}

    print(f"status : {run['run_status']} | fatal: {run['ledger_fatal_failure']}")
    print(f"outcome: {json.dumps(run['outcome'])}")
    print(f"calls  : {run['calls_consumed']} | observed: ${run['observed_cost_usd']}\n")

    by_model: Dict[str, Counter] = defaultdict(Counter)
    seen_ideas: set = set()
    rows: List[Dict[str, Any]] = []
    for index, turn in enumerate(run["turns"], 1):
        model = turn["model"]
        label = model_label.get(model, model)
        raw = turn.get("assistant_output_sanitized")
        content: Any = None
        if raw:
            try:
                content = json.loads(raw).get("content")
            except ValueError:
                content = None
        cls = classify_move_v1(content)
        accepted = turn["ced_move_accepted"]
        text = " ".join(_strings(content))
        ideas = ideas_in(text) if cls["verdict"] == "SUBSTANTIVE" else set()
        novel = ideas - seen_ideas
        if cls["verdict"] == "SUBSTANTIVE":
            seen_ideas |= ideas
        contribution = (
            "NOVEL_USEFUL" if (accepted and cls["verdict"] == "SUBSTANTIVE" and novel)
            else "REDUNDANT" if (accepted and cls["verdict"] == "SUBSTANTIVE")
            else "NONE"
        )
        by_model[label][cls["verdict"]] += 1
        by_model[label][contribution] += 1
        rows.append({
            "n": index, "seat_model": label, "phase": turn["dialogue_phase"],
            "task": turn["task_kind"], "accepted": accepted,
            "substance": cls["verdict"], "contribution": contribution,
            "novel_ideas": sorted(novel), "chars": cls["total_chars"],
            "placeholder_ratio": cls["placeholder_ratio"],
            "prompt_tokens": turn["prompt_tokens"],
            "completion_tokens": turn["completion_tokens"],
            "latency_ms": turn["latency_ms"],
            "failure": turn["failure_class"],
            "rejection": turn["ced_rejection_reason"],
        })

    print("=== per-turn ===")
    for r in rows:
        print("%2d %-17s %-22s acc=%-5s %-11s %-12s chars=%-6d %s" % (
            r["n"], r["seat_model"], r["task"], r["accepted"], r["substance"],
            r["contribution"], r["chars"], ",".join(r["novel_ideas"])[:44]))

    print("\n=== per model family ===")
    for label, counts in by_model.items():
        print("  %-17s SUBSTANTIVE=%-3d THIN=%-3d PLACEHOLDER=%-3d EMPTY=%-3d "
              "| NOVEL_USEFUL=%-3d REDUNDANT=%-3d" % (
                  label, counts["SUBSTANTIVE"], counts["THIN"],
                  counts["PLACEHOLDER"], counts["EMPTY"],
                  counts["NOVEL_USEFUL"], counts["REDUNDANT"]))

    out = path.with_name(path.stem + "_analysis.json")
    out.write_text(canonical_json({
        "schema_version": "socrates-lowcost-council-analysis/v1",
        "source": path.name,
        "key_verification": verification,
        "rubric": [{"criterion": c, "points": p} for c, p in RUBRIC_V1],
        "error_flags_checked": list(ERROR_FLAGS_V1),
        "per_turn": rows,
        "per_model": {k: dict(v) for k, v in by_model.items()},
    }), encoding="utf-8")
    print(f"\n  written: {out}")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        RUNS / "q1_lowcost_heterogeneous_ced_v1.json")
    raise SystemExit(main(target))
