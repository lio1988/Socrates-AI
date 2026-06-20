"""Deterministic scoring metrics for the CED Evaluation Harness v0.1.

Every metric is a pure function of pipeline output + gold annotations. The
yardstick for answer quality is the existing v10.1 Socratic pressure scorer
(evaluate_answer_pressure); to reduce circularity (constraint D), revision
usefulness ALSO checks the revision text against external gold annotations
(expected/forbidden substrings and an objection requirement).

IMPORTANT (constraint C): run_score is a regression / baseline signal over
scripted cases. It does NOT prove "CED is better" in general. It reports whether
CED improved on each scripted case according to these deterministic metrics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List

from backend.reasoning.socratic_pressure import (
    SocraticPressureReport,
    evaluate_answer_pressure,
)


def _low(text: str) -> str:
    return (text or "").lower()


def pressure_composite(report: SocraticPressureReport) -> float:
    """A single deterministic quality scalar from a pressure report: the mean of
    the six 'higher-is-better' pillars, penalised by vagueness."""
    pillars = [
        report.directness_score,
        report.scope_fit_score,
        report.operational_clarity_score,
        report.practical_grounding_score,
        report.objection_strength_score,
        report.uncertainty_calibration_score,
    ]
    return round(sum(pillars) / len(pillars) - 0.5 * report.vagueness_score, 3)


def score_claim_extraction(gold, stored_claim_texts: List[str]) -> float:
    """1.0 when the expected substantive claim survived extraction and no
    forbidden wrapper text leaked into any stored claim."""
    joined = " ".join(stored_claim_texts)
    low = _low(joined)
    expected_ok = (not gold.expected_claim_contains) or (
        _low(gold.expected_claim_contains) in low
    )
    forbidden_hits = sum(1 for f in gold.forbidden_claim_contains if _low(f) in low)
    score = 1.0 if expected_ok else 0.0
    score -= 0.5 * forbidden_hits
    return round(max(0.0, min(1.0, score)), 3)


def score_elenchus_target(gold, selection) -> float:
    """1.0 when Elenchus targeted a claim whose text contains the expected
    substantive proposition."""
    if not gold.expected_elenchus_target_contains:
        return 1.0
    target_text = _low(getattr(selection, "claim_text", "") or "")
    return 1.0 if _low(gold.expected_elenchus_target_contains) in target_text else 0.0


def score_revision_usefulness(
    gold,
    pre: SocraticPressureReport,
    post: SocraticPressureReport,
    post_text: str,
) -> Dict[str, object]:
    """Two-pronged (constraint D): scorer delta AND external gold checks.

    Returns the components plus a [0,1] usefulness score = fraction of the four
    signals satisfied: quality improved, expected content present, no forbidden
    filler, and the required objection is addressed.
    """
    low = _low(post_text)
    delta = round(pressure_composite(post) - pressure_composite(pre), 3)
    improved = delta > 0
    contains_ok = (not gold.expected_revision_contains) or (
        _low(gold.expected_revision_contains) in low
    )
    forbidden_ok = all(_low(f) not in low for f in gold.forbidden_revision_contains)
    objection_ok = (not gold.must_address_objection_contains) or (
        _low(gold.must_address_objection_contains) in low
    )
    signals = [improved, contains_ok, forbidden_ok, objection_ok]
    score = round(sum(1 for s in signals if s) / len(signals), 3)
    return {
        "score": score,
        "delta": delta,
        "improved": improved,
        "contains_ok": contains_ok,
        "forbidden_ok": forbidden_ok,
        "objection_ok": objection_ok,
    }


def score_single_shot_vs_ced(
    single_shot: SocraticPressureReport,
    ced: SocraticPressureReport,
) -> Dict[str, object]:
    """Compare the single-shot answer to the CED final answer with the same
    deterministic scorer. score = 1.0 when CED is at least as good."""
    ss = pressure_composite(single_shot)
    cd = pressure_composite(ced)
    return {
        "single_shot_composite": ss,
        "ced_composite": cd,
        "delta": round(cd - ss, 3),
        "ced_at_least_single_shot": cd >= ss,
        "score": 1.0 if cd >= ss else 0.0,
    }


def score_cbe_quality(gold, cbe_dict: dict) -> float:
    """Fraction of required practical-answer fields that are present and
    non-empty in the Current Best Explanation."""
    practical = cbe_dict.get("practical_answer", {}) or {}
    required = gold.cbe_required_fields or list(practical.keys())
    if not required:
        return 0.0
    present = sum(1 for key in required if str(practical.get(key, "")).strip())
    return round(present / len(required), 3)


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    claim_extraction: float
    elenchus_target: float
    revision_usefulness: float
    revision_detail: Dict[str, object]
    single_shot_vs_ced: Dict[str, object]
    cbe_quality: float
    run_score: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RunReport:
    harness_version: str
    schema_version: str
    case_count: int
    aggregate_run_score: float
    cases: List[Dict[str, object]] = field(default_factory=list)
    disclaimer: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def case_run_score(
    claim_extraction: float,
    elenchus_target: float,
    revision_usefulness: float,
    single_shot_vs_ced_score: float,
    cbe_quality: float,
) -> float:
    parts = [
        claim_extraction,
        elenchus_target,
        revision_usefulness,
        single_shot_vs_ced_score,
        cbe_quality,
    ]
    return round(sum(parts) / len(parts), 3)
