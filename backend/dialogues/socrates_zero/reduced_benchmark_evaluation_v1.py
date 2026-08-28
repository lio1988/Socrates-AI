"""Offline-only evaluation for the approved reduced Socrates benchmark.

This module intentionally contains the evaluator-only answer keys.  The live
collector must not import it: collection finishes and closes its dispatch path
before this module is loaded.  Evaluation reads only retained observable
outputs (answers, accepted moves, commitment events, and sanitized wire
evidence).  It does not call a model and does not alter CED state.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Dict, List, Optional, Set, Tuple


EVALUATION_SCHEMA_VERSION_V1 = "reduced-socrates-benchmark-evaluation/v1"
QUESTION_IDS_V1: Tuple[str, ...] = ("Q1", "Q2", "Q3")
CORRECTNESS_VALUES_V1: Tuple[str, ...] = (
    "CORRECT",
    "PARTIALLY_CORRECT",
    "INCORRECT",
)

# A unique evaluator-side tripwire.  Unlike an ordinary answer-key phrase, a
# worker cannot independently produce this value by solving the question.
HIDDEN_EVALUATOR_CANARY_V1 = (
    "SZ_EVALUATOR_ONLY_8D41E877_Q1_Q2_Q3_NEVER_PROVIDER_BOUND"
)

# Long exact passages used for the requested post-run digest/search audit.
# A passage collision is reported separately from the canary because a worker
# can independently state a correct answer in similar words.
HIDDEN_EVALUATOR_EXACT_PASSAGES_V1: Tuple[str, ...] = (
    "Assume Mira signed without checking. Then Mira violated procedure.",
    "The full 18% causal attribution is NOT justified.",
    "The perpetrator cannot be determined from the supplied evidence.",
)

_Q2_USEFUL_FEATURES: Tuple[str, ...] = (
    "rejects_full_causal_attribution",
    "selection_bias",
    "training_confound",
    "preexisting_differences_or_trends",
    "randomized_assignment",
    "training_control",
    "factorial_design",
    "quasi_experiment",
    "pretreatment_or_difference_in_differences",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _flatten_text(value: Any) -> str:
    """Project observable answer content to text without inferring new claims."""
    if value is None:
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return _flatten_text(json.loads(stripped))
            except (TypeError, ValueError):
                pass
        return stripped
    if isinstance(value, Mapping):
        return "\n".join(
            _flatten_text(item) for item in value.values() if item is not None
        )
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return "\n".join(_flatten_text(item) for item in value)
    return str(value)


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", _flatten_text(value)).strip().casefold()


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _score_q1(value: Any) -> Dict[str, Any]:
    text = _normalized(value)
    features = {
        "concludes_mira_checked": _has(
            text,
            r"\byes\b",
            r"mira (?:must|necessarily) (?:have )?checked",
            r"must conclude (?:that )?mira checked",
        ),
        "tests_without_checking_branch": _has(
            text,
            r"assum(?:e|ing|ption).{0,80}(?:without|did not|didn.t) check",
            r"if mira.{0,60}(?:without|did not|didn.t) check",
        ),
        "derives_procedure_violation": _has(
            text, r"violat(?:e|es|ed|ing).{0,40}procedure"
        ),
        "uses_chairing_conflict": _has(
            text,
            r"(?:cannot|may not|could not).{0,50}chair",
            r"chair(?:ed|ing).{0,80}contradict",
            r"contradict.{0,80}chair(?:ed|ing)",
        ),
        "uses_exhaustive_signer_condition": _has(
            text,
            r"(?:either|two possibilities|exhaustive).{0,100}(?:check|sign)",
            r"(?:only|remaining|other) (?:branch|possibility|alternative).{0,80}check",
        ),
    }
    critical = (
        features["concludes_mira_checked"],
        features["derives_procedure_violation"],
        features["uses_chairing_conflict"],
        features["uses_exhaustive_signer_condition"],
    )
    if all(critical):
        correctness = "CORRECT"
    elif features["concludes_mira_checked"] and sum(critical) >= 2:
        correctness = "PARTIALLY_CORRECT"
    else:
        correctness = "INCORRECT"
    return {
        "correctness": correctness,
        "features": features,
        "important_omissions": [
            label for label, present in features.items() if not present
        ],
        "unsupported_claims": [],
    }


def _q2_features(value: Any) -> Set[str]:
    text = _normalized(value)
    found: Set[str] = set()
    if _has(
        text,
        r"(?:not|isn.t|cannot|can.t|does not|doesn.t).{0,45}(?:justif|establish|show|prove).{0,80}(?:caus|18%)",
        r"(?:caus|18%).{0,80}(?:not justified|cannot be attributed|does not follow|not established)",
        r"(?:conclusion|claim|attribution).{0,35}(?:not|isn.t).{0,20}justif",
        r"correlation.{0,20}(?:is not|isn.t|does not imply).{0,20}caus",
    ):
        found.add("rejects_full_causal_attribution")
    if _has(
        text,
        r"selection bias",
        r"self[- ]select(?:ion|ed|ing)?",
        r"voluntar(?:y|ily).{0,90}(?:differ|motiv|select|bias|apply)",
        r"managers? who appl(?:y|ied).{0,90}(?:differ|motiv|select|bias)",
    ):
        found.add("selection_bias")
    if _has(
        text,
        r"training.{0,60}confound",
        r"confound.{0,60}training",
        r"(?:tool|ai).{0,80}(?:cannot|can.t).{0,40}(?:separat|isolat).{0,50}training",
        r"training.{0,80}(?:rather than|instead of|may explain|could explain).{0,50}(?:tool|gain|increase)",
    ):
        found.add("training_confound")
    if _has(
        text,
        r"pre[- ]?existing differ",
        r"baseline differ",
        r"different (?:pre[- ]?treatment )?trend",
        r"regression (?:to|toward) the mean",
    ):
        found.add("preexisting_differences_or_trends")
    if _has(text, r"random(?:ize|ise|ized|ised|ly assign| assignment)"):
        found.add("randomized_assignment")
    if _has(
        text,
        r"hold.{0,35}training (?:constant|fixed)",
        r"same training",
        r"control.{0,30}training",
    ):
        found.add("training_control")
    if _has(
        text,
        r"factorial",
        r"(?:2\s*[x×]\s*2|four[- ]arm).{0,50}(?:tool|training)",
        r"tool.{0,50}(?:with|without).{0,30}training.{0,50}(?:with|without)",
    ):
        found.add("factorial_design")
    if _has(
        text,
        r"quasi[- ]experiment",
        r"instrumental variable",
        r"regression discontinuity",
        r"natural experiment",
    ):
        found.add("quasi_experiment")
    if _has(
        text,
        r"pre[- ]?treatment",
        r"before[- ]and[- ]after",
        r"difference[- ]in[- ]differences",
        r"difference in differences",
        r"parallel trends",
    ):
        found.add("pretreatment_or_difference_in_differences")
    return found


def _score_q2(value: Any) -> Dict[str, Any]:
    text = _normalized(value)
    found = _q2_features(text)
    design_features = {
        "randomized_assignment",
        "training_control",
        "factorial_design",
        "quasi_experiment",
        "pretreatment_or_difference_in_differences",
    }
    has_design = bool(found & design_features)
    critical = {
        "rejects_full_causal_attribution",
        "selection_bias",
        "training_confound",
    }
    if critical <= found and has_design:
        correctness = "CORRECT"
    elif "rejects_full_causal_attribution" in found and len(critical & found) >= 2:
        correctness = "PARTIALLY_CORRECT"
    else:
        correctness = "INCORRECT"
    unsupported: List[str] = []
    if "rejects_full_causal_attribution" not in found and _has(
        text, r"(?:tool|ai).{0,30}caused.{0,25}18%", r"18%.{0,30}caused by.{0,20}(?:tool|ai)"
    ):
        unsupported.append("attributes the full 18% increase to the tool")
    return {
        "correctness": correctness,
        "features": {name: name in found for name in _Q2_USEFUL_FEATURES},
        "selection_bias": "selection_bias" in found,
        "training_confounding": "training_confound" in found,
        "distinguishing_design_present": has_design,
        "important_omissions": [name for name in sorted(critical) if name not in found]
        + ([] if has_design else ["distinguishing_evidence_or_design"]),
        "unsupported_claims": unsupported,
    }


def _score_q3(value: Any) -> Dict[str, Any]:
    text = _normalized(value)
    features = {
        "actor_indeterminate": _has(
            text,
            r"cannot (?:be )?determin(?:e|ed)",
            r"not enough evidence.{0,70}(?:who|actor|person)",
            r"insufficient evidence.{0,70}(?:who|actor|person)",
            r"cannot say (?:who|whether)",
        ),
        "token_use_distinguished": _has(
            text, r"(?:omar.s|admin) token.{0,40}(?:used|credential)"
        ),
        "workstation_or_session_distinguished": _has(
            text, r"workstation m", r"logged (?:in|on).{0,40}(?:m|workstation)"
        ),
        "human_actor_identity_distinguished": _has(
            text,
            r"(?:token|credential|session|workstation).{0,90}(?:does not|doesn.t|not).{0,35}(?:identify|prove|establish).{0,35}(?:person|human|actor|who)",
            r"credential identity.{0,80}(?:human|actor|person)",
        ),
    }
    accuses_priya = _has(text, r"priya (?:definitely |certainly )?(?:deleted|was the deleter)") and not _has(
        text, r"cannot conclude.{0,50}priya", r"does not prove.{0,50}priya"
    )
    accuses_omar = _has(text, r"omar (?:definitely |certainly )?(?:deleted|was the deleter)") and not _has(
        text, r"cannot conclude.{0,50}omar", r"does not prove.{0,50}omar"
    )
    if all(features.values()) and not accuses_priya and not accuses_omar:
        correctness = "CORRECT"
    elif features["actor_indeterminate"] and not accuses_priya and not accuses_omar:
        correctness = "PARTIALLY_CORRECT"
    else:
        correctness = "INCORRECT"
    unsupported = []
    if accuses_priya:
        unsupported.append("unsupported attribution to Priya")
    if accuses_omar:
        unsupported.append("unsupported attribution to Omar")
    return {
        "correctness": correctness,
        "features": features,
        "unsupported_attribution_to_priya": accuses_priya,
        "unsupported_attribution_to_omar": accuses_omar,
        "important_omissions": [label for label, present in features.items() if not present],
        "unsupported_claims": unsupported,
    }


def evaluate_answer_v1(question_id: str, observable_answer: Any) -> Dict[str, Any]:
    """Apply one deterministic, evaluator-key rubric to observable answer text."""
    if question_id == "Q1":
        result = _score_q1(observable_answer)
    elif question_id == "Q2":
        result = _score_q2(observable_answer)
    elif question_id == "Q3":
        result = _score_q3(observable_answer)
    else:
        raise ValueError(f"unknown reduced benchmark question: {question_id!r}")
    result.update(
        {
            "question_id": question_id,
            "rubric_kind": "DETERMINISTIC_EVALUATOR_KEY",
            "observable_answer_sha256": _sha256_text(_flatten_text(observable_answer)),
        }
    )
    return result


def classify_novel_contributions_v1(
    ced_state: Mapping[str, Any],
    provider_models: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """Classify accepted Q2 dialogue moves by first useful issue surfaced.

    This is deliberately question-specific and mechanical.  It measures the
    first accepted move that makes one of the frozen causal-rubric distinctions
    observable; it does not reward prose novelty or use a semantic judge.
    """
    seen: Set[str] = set()
    rows: List[Dict[str, Any]] = []
    for index, raw_move in enumerate(ced_state.get("moves") or []):
        if not isinstance(raw_move, Mapping):
            continue
        task_kind = str(raw_move.get("task_kind") or "")
        if task_kind in {
            "move_score",
            "section_score",
            "council_ratification",
            "objection_verification",
        }:
            continue
        features = _q2_features(raw_move.get("content"))
        new_features = sorted(features - seen)
        seen.update(features)
        provider_id = str(raw_move.get("provider_id") or "")
        rows.append(
            {
                "sequence": index,
                "move_id": raw_move.get("move_id"),
                "phase": raw_move.get("phase"),
                "role": raw_move.get("role"),
                "task_kind": task_kind or None,
                "provider_id": provider_id or None,
                "model": provider_models.get(provider_id),
                "classification": "NOVEL_USEFUL" if new_features else "REDUNDANT",
                "novel_useful_features": new_features,
                "all_key_features_present": sorted(features),
            }
        )
    return rows


def _feature_weight(features: Set[str]) -> int:
    critical = {
        "rejects_full_causal_attribution",
        "selection_bias",
        "training_confound",
    }
    return sum(2 if item in critical else 1 for item in features)


def classify_commitment_revisions_v1(
    commitment_ledger: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Score declared commitment events, never inferred edits or dialogue churn."""
    records = [dict(item) for item in commitment_ledger if isinstance(item, Mapping)]
    by_id = {
        str(item.get("commitment_id")): item
        for item in records
        if item.get("commitment_id")
    }
    rows: List[Dict[str, Any]] = []
    for item in records:
        status = str(item.get("status") or "")
        if status not in {"revised", "withdrawn", "suspended"}:
            continue
        target_id = str(item.get("target_commitment_id") or "")
        before = by_id.get(target_id, {})
        old_claim = before.get("claim") or ""
        new_claim = item.get("claim") or ""
        before_features = _q2_features(old_claim)
        after_features = _q2_features(new_claim)
        if status in {"withdrawn", "suspended"}:
            after_features = set()

        old_overclaim = _has(
            _normalized(old_claim),
            r"(?:tool|ai).{0,30}caused.{0,25}18%",
            r"18%.{0,30}caused by.{0,20}(?:tool|ai)",
        ) and "rejects_full_causal_attribution" not in before_features
        new_overclaim = _has(
            _normalized(new_claim),
            r"(?:tool|ai).{0,30}caused.{0,25}18%",
            r"18%.{0,30}caused by.{0,20}(?:tool|ai)",
        ) and "rejects_full_causal_attribution" not in after_features

        delta = _feature_weight(after_features) - _feature_weight(before_features)
        if old_overclaim and (status in {"withdrawn", "suspended"} or not new_overclaim):
            classification = "USEFUL_REVISION"
        elif new_overclaim or delta < 0:
            classification = "HARMFUL_REVISION"
        elif delta > 0:
            classification = "USEFUL_REVISION"
        else:
            classification = "NEUTRAL_REVISION"
        rows.append(
            {
                "source_move_id": item.get("source_move_id"),
                "provider_id": item.get("provider_id"),
                "model": item.get("model_id"),
                "status": status,
                "target_commitment_id": target_id or None,
                "old_claim": old_claim,
                "new_claim": new_claim,
                "classification": classification,
                "feature_delta": sorted(after_features - before_features),
                "features_removed": sorted(before_features - after_features),
            }
        )
    return rows


def hidden_evaluator_key_audit_v1(
    provider_bound_bodies: Iterable[str],
) -> Dict[str, Any]:
    """Digest and search exact retained request bodies after collection closes."""
    bodies = [str(body) for body in provider_bound_bodies]
    canary_matches = [index for index, body in enumerate(bodies) if HIDDEN_EVALUATOR_CANARY_V1 in body]
    passage_matches = {
        passage: [index for index, body in enumerate(bodies) if passage in body]
        for passage in HIDDEN_EVALUATOR_EXACT_PASSAGES_V1
    }
    passage_matches = {key: value for key, value in passage_matches.items() if value}
    manifest = [
        {"index": index, "body_length": len(body.encode("utf-8")), "body_sha256": _sha256_text(body)}
        for index, body in enumerate(bodies)
    ]
    return {
        "request_body_count": len(bodies),
        "ordered_body_manifest_sha256": _sha256_text(_canonical_json(manifest)),
        "canary_match_indices": canary_matches,
        "exact_passage_match_indices": passage_matches,
        "hidden_evaluator_canary_absent": not canary_matches,
        "exact_key_passages_absent": not passage_matches,
        "passed": not canary_matches and not passage_matches,
        "collision_note": (
            "Any exact-passage hit requires provenance review because a worker can "
            "independently produce ordinary answer language; the unique canary cannot."
        ),
    }


def _observed_cost(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    picodollars = 0
    unknown = 0
    prompt_tokens = 0
    completion_tokens = 0
    calls = 0
    for row in rows:
        calls += 1
        cost = row.get("observed_cost_picodollars")
        if isinstance(cost, int) and not isinstance(cost, bool) and cost >= 0:
            picodollars += cost
        else:
            unknown += 1
        prompt = row.get("prompt_tokens")
        completion = row.get("completion_tokens")
        if isinstance(prompt, int) and not isinstance(prompt, bool) and prompt >= 0:
            prompt_tokens += prompt
        if isinstance(completion, int) and not isinstance(completion, bool) and completion >= 0:
            completion_tokens += completion
    return {
        "calls": calls,
        "prompt_tokens_observed": prompt_tokens,
        "completion_tokens_observed": completion_tokens,
        "observed_cost_picodollars": picodollars,
        "observed_cost_usd": f"{picodollars / 10**12:.12f}",
        "requests_with_unknown_observed_cost": unknown,
    }


def build_reduced_benchmark_evaluation_v1(
    collection: Mapping[str, Any],
) -> Dict[str, Any]:
    """Evaluate the frozen reduced collection after its dispatch path is closed."""
    baselines = collection.get("baselines") or {}
    baseline_results: Dict[str, Any] = {}
    baseline_rows: List[Mapping[str, Any]] = []
    for qid in QUESTION_IDS_V1:
        row = baselines.get(qid) if isinstance(baselines, Mapping) else None
        row = row if isinstance(row, Mapping) else {}
        answer = row.get("assistant_output", row.get("text"))
        baseline_results[qid] = {
            "actual_output": answer,
            "objective_evaluation": evaluate_answer_v1(qid, answer),
            "usage": dict(row.get("usage") or {}),
            "transport": dict(row.get("transport") or {}),
        }
        usage_row = dict(row.get("usage") or {})
        if "observed_cost_picodollars" not in usage_row:
            usage_row["observed_cost_picodollars"] = row.get("observed_cost_picodollars")
        baseline_rows.append(usage_row)

    homogeneous = collection.get("homogeneous_q2") or {}
    homogeneous = homogeneous if isinstance(homogeneous, Mapping) else {}
    final = homogeneous.get("final") or {}
    final = final if isinstance(final, Mapping) else {}
    state = homogeneous.get("state") or {}
    state = state if isinstance(state, Mapping) else {}
    released_answer = final.get("answer") or ""
    synthesis = final.get("synthesis") or {}
    candidate_answer = synthesis if synthesis else released_answer
    provider_models = homogeneous.get("provider_models") or {}
    provider_models = provider_models if isinstance(provider_models, Mapping) else {}
    contributions = classify_novel_contributions_v1(state, provider_models)
    commitment_ledger = (
        (final.get("audit_summary") or {}).get("commitment_ledger")
        if isinstance(final.get("audit_summary"), Mapping)
        else []
    ) or []
    revisions = classify_commitment_revisions_v1(commitment_ledger)
    turn_rows = [
        row for row in (homogeneous.get("turns") or []) if isinstance(row, Mapping)
    ]
    wire = collection.get("wire_evidence") or {}
    wire = wire if isinstance(wire, Mapping) else {}

    evaluation = {
        "schema_version": EVALUATION_SCHEMA_VERSION_V1,
        "condition_scope": {
            "baselines": "GPT-5 Mini direct on Q1, Q2, and Q3",
            "homogeneous_socrates": "four GPT-5 Mini seats on Q2 only",
            "heterogeneous_socrates": "REMOVED_NOT_RUN",
        },
        "baselines": baseline_results,
        "homogeneous_q2": {
            "released_answer": released_answer,
            "candidate_synthesis": synthesis,
            "release_state": {
                "ratification_status": final.get("ratification_status"),
                "ratified": final.get("ratified"),
                "release_decision": final.get("release_decision"),
                "governing_epistemic_status": final.get("governing_epistemic_status"),
                "blocking_objections": final.get("blocking_objections") or [],
            },
            "released_answer_evaluation": (
                evaluate_answer_v1("Q2", released_answer)
                if released_answer
                else {
                    "question_id": "Q2",
                    "correctness": "INCORRECT",
                    "rubric_kind": "NO_RELEASED_ANSWER",
                    "unsupported_claims": [],
                }
            ),
            "candidate_synthesis_evaluation": evaluate_answer_v1("Q2", candidate_answer),
            "novel_contributions": contributions,
            "novel_useful_count": sum(
                row["classification"] == "NOVEL_USEFUL" for row in contributions
            ),
            "commitment_revisions": revisions,
            "revision_counts": {
                label: sum(row["classification"] == label for row in revisions)
                for label in (
                    "USEFUL_REVISION",
                    "NEUTRAL_REVISION",
                    "HARMFUL_REVISION",
                )
            },
            "usage": _observed_cost(turn_rows),
            "actual_live_calls": homogeneous.get("calls_consumed", len(turn_rows)),
        },
        "economics": {
            "baselines": _observed_cost(baseline_rows),
            "homogeneous_q2": _observed_cost(turn_rows),
        },
        "hidden_evaluator_key_audit": hidden_evaluator_key_audit_v1(
            wire.get("provider_bound_bodies") or []
        ),
        "scientific_scope": {
            "single_vs_homogeneous_comparison_available_for": ["Q2"],
            "heterogeneous_comparison_available": False,
            "correlated_error_metric_available": False,
            "diversity_signal": "NOT_TESTED",
            "overclaim_warning": (
                "This reduced run cannot estimate model-diversity effects, "
                "best-of-four performance, or correlated-error breaking."
            ),
        },
    }
    evaluation["evaluation_sha256"] = _sha256_text(_canonical_json(evaluation))
    return evaluation


def _markdown_code(value: Any) -> str:
    rendered = (
        value
        if isinstance(value, str)
        else json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
    )
    return f"```text\n{rendered or '(no output)'}\n```"


def render_reduced_benchmark_markdown_v1(
    collection: Mapping[str, Any], evaluation: Mapping[str, Any]
) -> str:
    """Render a compact scientific report without inventing unavailable arms."""
    baselines = evaluation.get("baselines") or {}
    homogeneous = evaluation.get("homogeneous_q2") or {}
    economics = evaluation.get("economics") or {}
    lines: List[str] = [
        "# REDUCED SOCRATES BENCHMARK COMPLETE",
        "",
        "The revoked 972-call / $655.40 session was not run. This report covers "
        "only the approved reduced session: three GPT-5 Mini baselines and one "
        "four-seat homogeneous GPT-5 Mini CED dialogue on Question 2.",
        "",
        "## Session",
        "",
        f"- Maximum live calls: {collection.get('maximum_live_calls', 151)}",
        f"- Actual live calls: {collection.get('actual_live_calls')}",
        f"- Hard spend ceiling: ${collection.get('hard_total_spend_usd', '8.00')}",
        f"- Automatic retries: {collection.get('automatic_retries', 0)}",
        f"- Model: `{collection.get('model', 'openai/gpt-5-mini')}`",
        f"- Provider route: `{collection.get('provider_selector', 'openai/flex')}`",
        "",
    ]
    for qid, title in (
        ("Q1", "FORMAL LOGIC"),
        ("Q2", "CAUSAL REASONING"),
        ("Q3", "EPISTEMIC RESTRAINT"),
    ):
        row = baselines.get(qid) or {}
        objective = row.get("objective_evaluation") or {}
        lines.extend(
            [
                f"## {qid} — {title}",
                "",
                "### GPT-5 Mini baseline",
                "",
                _markdown_code(row.get("actual_output")),
                "",
                f"Correctness: **{objective.get('correctness', 'UNAVAILABLE')}**",
                "",
            ]
        )
        if qid != "Q2":
            continue
        released = homogeneous.get("released_answer_evaluation") or {}
        candidate = homogeneous.get("candidate_synthesis_evaluation") or {}
        release_state = homogeneous.get("release_state") or {}
        lines.extend(
            [
                "### Homogeneous Socrates (four GPT-5 Mini seats)",
                "",
                _markdown_code(homogeneous.get("released_answer")),
                "",
                f"Released-answer correctness: **{released.get('correctness', 'UNAVAILABLE')}**",
                f"Candidate-synthesis correctness: **{candidate.get('correctness', 'UNAVAILABLE')}**",
                f"Ratification state: `{release_state.get('ratification_status')}`",
                f"Release decision: `{release_state.get('release_decision')}`",
                f"Calls: {homogeneous.get('actual_live_calls')}",
                f"Novel useful accepted moves: {homogeneous.get('novel_useful_count', 0)}",
                (
                    "Useful / neutral / harmful revisions: "
                    f"{(homogeneous.get('revision_counts') or {}).get('USEFUL_REVISION', 0)} / "
                    f"{(homogeneous.get('revision_counts') or {}).get('NEUTRAL_REVISION', 0)} / "
                    f"{(homogeneous.get('revision_counts') or {}).get('HARMFUL_REVISION', 0)}"
                ),
                "",
                "Selection bias identified: "
                + ("YES" if candidate.get("selection_bias") else "NO"),
                "Training confounding identified: "
                + ("YES" if candidate.get("training_confounding") else "NO"),
                "",
            ]
        )

    baseline_econ = economics.get("baselines") or {}
    ced_econ = economics.get("homogeneous_q2") or {}
    hidden = evaluation.get("hidden_evaluator_key_audit") or {}
    lines.extend(
        [
            "## Economics",
            "",
            f"- Baseline observed cost: ${baseline_econ.get('observed_cost_usd', 'unknown')}",
            f"- Homogeneous CED observed cost: ${ced_econ.get('observed_cost_usd', 'unknown')}",
            f"- Baseline calls: {baseline_econ.get('calls')}",
            f"- Homogeneous CED calls: {ced_econ.get('calls')}",
            "",
            "Observed-cost totals do not treat missing provider cost fields as zero; "
            f"unknown baseline/CED costs: {baseline_econ.get('requests_with_unknown_observed_cost')} / "
            f"{ced_econ.get('requests_with_unknown_observed_cost')}.",
            "",
            "## Hidden evaluator-key boundary",
            "",
            f"- Exact provider-bound bodies searched: {hidden.get('request_body_count')}",
            f"- Unique evaluator canary absent: {hidden.get('hidden_evaluator_canary_absent')}",
            f"- Exact evaluator passages absent: {hidden.get('exact_key_passages_absent')}",
            f"- Ordered body-manifest digest: `{hidden.get('ordered_body_manifest_sha256')}`",
            "",
            "## Scientific conclusion",
            "",
            "This reduced experiment can compare GPT-5 Mini direct answering with "
            "homogeneous GPT-5 Mini CED only for Question 2. It cannot measure "
            "model diversity, best-of-four performance, or correlated-error breaking. "
            "The heterogeneous and GPT-4.1-mini control arms were removed to remain "
            "inside the $8.00 hard ceiling.",
            "",
        ]
    )
    return "\n".join(lines)


__all__ = [
    "CORRECTNESS_VALUES_V1",
    "EVALUATION_SCHEMA_VERSION_V1",
    "HIDDEN_EVALUATOR_CANARY_V1",
    "HIDDEN_EVALUATOR_EXACT_PASSAGES_V1",
    "QUESTION_IDS_V1",
    "build_reduced_benchmark_evaluation_v1",
    "classify_commitment_revisions_v1",
    "classify_novel_contributions_v1",
    "evaluate_answer_v1",
    "hidden_evaluator_key_audit_v1",
    "render_reduced_benchmark_markdown_v1",
]
