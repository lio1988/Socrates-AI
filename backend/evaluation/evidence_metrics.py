"""Deterministic, gold-annotation-based metrics for the Evidence Layer v0.1
harness. No model calls. Kept entirely separate from the existing
``backend/evaluation/metrics.py`` so the v0.1 evaluation harness is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from backend.epistemic.claim import Claim
from backend.epistemic.evidence_scoring import effective_stance
from backend.reasoning.evidence_constrained_cbe import (
    FinalEpistemicAnswer,
    NO_SUPPORTED_ANSWER,
)

_BUCKET_FIELD = {
    "supported_claims": "supported_claims",
    "contested_claims": "contested_claims",
    "speculative_claims": "speculative_claims",
    "refuted_claims": "refuted_claims",
    "missing_evidence": "missing_evidence",
}


@dataclass
class EvidenceCaseResult:
    case_id: str
    expected_status: str
    actual_status: str
    status_correct: bool
    attachment_correct: bool
    bucket_correct: bool
    primary_rule_ok: bool
    passed: bool

    def to_dict(self) -> Dict:
        return {
            "case_id": self.case_id,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
            "status_correct": self.status_correct,
            "attachment_correct": self.attachment_correct,
            "bucket_correct": self.bucket_correct,
            "primary_rule_ok": self.primary_rule_ok,
            "passed": self.passed,
        }


def _attachment_correct(case, claim: Claim) -> bool:
    """Each fixture became an Evidence on the claim with a consistent stance."""
    if len(claim.evidence) != len(case.evidence_fixtures):
        return False
    want = sorted(
        str(fx.get("stance", "supporting")).lower() for fx in case.evidence_fixtures
    )
    got = sorted(effective_stance(ev).value for ev in claim.evidence)
    return want == got


def score_evidence_case(
    case, claim: Claim, status, raw_cbe: Dict, final: FinalEpistemicAnswer
) -> EvidenceCaseResult:
    gold = case.gold
    expected = gold.get("expected_status", "")
    status_correct = status.value == expected
    attachment_correct = _attachment_correct(case, claim)

    bucket = gold.get("must_appear_in")
    bucket_correct = True
    if bucket:
        ids = [b["claim_id"] for b in getattr(final, _BUCKET_FIELD[bucket])]
        bucket_correct = claim.claim_id in ids

    # Presentation rule: only WELL_SUPPORTED is eligible to be the primary
    # answer. A non-eligible claim must never appear as the primary answer.
    eligible = bool(gold.get("eligible_primary", False))
    is_primary = (
        final.primary_answer == claim.text
        and final.primary_answer != NO_SUPPORTED_ANSWER
    )
    primary_rule_ok = True if eligible else (not is_primary)

    passed = all(
        [status_correct, attachment_correct, bucket_correct, primary_rule_ok]
    )
    return EvidenceCaseResult(
        case_id=case.id,
        expected_status=expected,
        actual_status=status.value,
        status_correct=status_correct,
        attachment_correct=attachment_correct,
        bucket_correct=bucket_correct,
        primary_rule_ok=primary_rule_ok,
        passed=passed,
    )


def aggregate(results: List[EvidenceCaseResult]) -> Dict:
    n = len(results) or 1

    def rate(attr: str) -> float:
        return round(sum(1 for r in results if getattr(r, attr)) / n, 4)

    return {
        "status_correct_rate": rate("status_correct"),
        "attachment_correct_rate": rate("attachment_correct"),
        "bucket_correct_rate": rate("bucket_correct"),
        "primary_rule_ok_rate": rate("primary_rule_ok"),
        "passed_rate": rate("passed"),
    }
