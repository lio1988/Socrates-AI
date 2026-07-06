"""
Phase 26S — Evidence Claim Gates.

Leaderboards are not enough. This module evaluates explicit claims against an
EvidenceHarnessReport using deterministic thresholds.

It answers: supported, not_supported, or insufficient.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .learning_evidence_harness import EvidenceHarnessReport, SystemEvidenceResult, evidence_harness_summary
from .learning_foundation import sanitize_public_payload


def _stable_json(value: Any) -> str:
    return json.dumps(sanitize_public_payload(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def claim_gate_hash(value: Any, *, prefix: str = "") -> str:
    digest = hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:16]}" if prefix else digest


class EvidenceClaimKind(str, Enum):
    SYSTEM_BEATS_BASELINE = "system_beats_baseline"
    SYSTEM_MEETS_THRESHOLD = "system_meets_threshold"
    SYSTEM_HAS_COVERAGE = "system_has_coverage"
    CONFIDENCE_IS_USEFUL = "confidence_is_useful"


class EvidenceClaimVerdict(str, Enum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    INSUFFICIENT = "insufficient"


class EvidenceClaimPolicy(BaseModel):
    min_task_count: int = 10
    min_coverage: float = 0.80
    min_accuracy: float = 0.70
    min_score_ratio: float = 0.70
    min_accuracy_margin: float = 0.05
    min_score_ratio_margin: float = 0.05
    min_confidence_gap: float = 0.05

    @classmethod
    def strict(cls) -> "EvidenceClaimPolicy":
        return cls()

    @classmethod
    def small_sample(cls) -> "EvidenceClaimPolicy":
        return cls(min_task_count=1, min_coverage=0.0, min_accuracy=0.0, min_score_ratio=0.0)


class EvidenceClaim(BaseModel):
    claim_id: str
    kind: EvidenceClaimKind
    target_system_id: str
    baseline_system_id: Optional[str] = None
    statement: str
    policy: EvidenceClaimPolicy = Field(default_factory=EvidenceClaimPolicy.strict)


class EvidenceClaimResult(BaseModel):
    claim_id: str
    verdict: EvidenceClaimVerdict
    statement: str
    reasons: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    required: Dict[str, Any] = Field(default_factory=dict)


class EvidenceClaimGateReport(BaseModel):
    report_id: str
    harness_id: str
    claim_count: int
    supported_count: int
    not_supported_count: int
    insufficient_count: int
    results: List[EvidenceClaimResult] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True, indent=2)


def _system(report: EvidenceHarnessReport, system_id: str) -> Optional[SystemEvidenceResult]:
    for system in report.systems:
        if system.system_id == system_id:
            return system
    return None


def _base_reasons(system: Optional[SystemEvidenceResult], policy: EvidenceClaimPolicy) -> List[str]:
    if system is None:
        return ["target system is missing from evidence report"]
    reasons: List[str] = []
    if system.task_count < policy.min_task_count:
        reasons.append(f"task_count {system.task_count} < required {policy.min_task_count}")
    if system.coverage < policy.min_coverage:
        reasons.append(f"coverage {system.coverage:.3f} < required {policy.min_coverage:.3f}")
    return reasons


def evaluate_system_meets_threshold(claim: EvidenceClaim, report: EvidenceHarnessReport) -> EvidenceClaimResult:
    system = _system(report, claim.target_system_id)
    reasons = _base_reasons(system, claim.policy)
    if system is None:
        return _claim_result(claim, EvidenceClaimVerdict.INSUFFICIENT, reasons, {})
    metrics = {
        "accuracy": system.report.accuracy,
        "score_ratio": system.score_ratio,
        "coverage": system.coverage,
        "task_count": system.task_count,
    }
    if reasons:
        return _claim_result(claim, EvidenceClaimVerdict.INSUFFICIENT, reasons, metrics)
    failures: List[str] = []
    if system.report.accuracy < claim.policy.min_accuracy:
        failures.append(f"accuracy {system.report.accuracy:.3f} < required {claim.policy.min_accuracy:.3f}")
    if system.score_ratio < claim.policy.min_score_ratio:
        failures.append(f"score_ratio {system.score_ratio:.3f} < required {claim.policy.min_score_ratio:.3f}")
    verdict = EvidenceClaimVerdict.NOT_SUPPORTED if failures else EvidenceClaimVerdict.SUPPORTED
    return _claim_result(claim, verdict, failures or ["thresholds met"], metrics)


def evaluate_system_has_coverage(claim: EvidenceClaim, report: EvidenceHarnessReport) -> EvidenceClaimResult:
    system = _system(report, claim.target_system_id)
    if system is None:
        return _claim_result(claim, EvidenceClaimVerdict.INSUFFICIENT, ["target system is missing from evidence report"], {})
    metrics = {"coverage": system.coverage, "task_count": system.task_count}
    if system.task_count < claim.policy.min_task_count:
        return _claim_result(claim, EvidenceClaimVerdict.INSUFFICIENT, [f"task_count {system.task_count} < required {claim.policy.min_task_count}"], metrics)
    if system.coverage >= claim.policy.min_coverage:
        return _claim_result(claim, EvidenceClaimVerdict.SUPPORTED, ["coverage threshold met"], metrics)
    return _claim_result(claim, EvidenceClaimVerdict.NOT_SUPPORTED, [f"coverage {system.coverage:.3f} < required {claim.policy.min_coverage:.3f}"], metrics)


def evaluate_system_beats_baseline(claim: EvidenceClaim, report: EvidenceHarnessReport) -> EvidenceClaimResult:
    target = _system(report, claim.target_system_id)
    baseline = _system(report, claim.baseline_system_id or "")
    reasons = _base_reasons(target, claim.policy)
    if baseline is None:
        reasons.append("baseline system is missing from evidence report")
    elif baseline.task_count < claim.policy.min_task_count:
        reasons.append(f"baseline task_count {baseline.task_count} < required {claim.policy.min_task_count}")
    if target is None or baseline is None:
        return _claim_result(claim, EvidenceClaimVerdict.INSUFFICIENT, reasons, {})

    metrics = {
        "target_accuracy": target.report.accuracy,
        "baseline_accuracy": baseline.report.accuracy,
        "accuracy_margin": target.report.accuracy - baseline.report.accuracy,
        "target_score_ratio": target.score_ratio,
        "baseline_score_ratio": baseline.score_ratio,
        "score_ratio_margin": target.score_ratio - baseline.score_ratio,
        "target_coverage": target.coverage,
        "baseline_coverage": baseline.coverage,
        "task_count": target.task_count,
    }
    if reasons:
        return _claim_result(claim, EvidenceClaimVerdict.INSUFFICIENT, reasons, metrics)

    failures: List[str] = []
    if metrics["accuracy_margin"] < claim.policy.min_accuracy_margin:
        failures.append(f"accuracy_margin {metrics['accuracy_margin']:.3f} < required {claim.policy.min_accuracy_margin:.3f}")
    if metrics["score_ratio_margin"] < claim.policy.min_score_ratio_margin:
        failures.append(f"score_ratio_margin {metrics['score_ratio_margin']:.3f} < required {claim.policy.min_score_ratio_margin:.3f}")
    verdict = EvidenceClaimVerdict.NOT_SUPPORTED if failures else EvidenceClaimVerdict.SUPPORTED
    return _claim_result(claim, verdict, failures or ["target beats baseline by required margins"], metrics)


def evaluate_confidence_is_useful(claim: EvidenceClaim, report: EvidenceHarnessReport) -> EvidenceClaimResult:
    system = _system(report, claim.target_system_id)
    reasons = _base_reasons(system, claim.policy)
    if system is None:
        return _claim_result(claim, EvidenceClaimVerdict.INSUFFICIENT, reasons, {})
    metrics = {
        "confidence_gap": system.confidence_gap,
        "confidence_on_pass": system.confidence_on_pass,
        "confidence_on_fail": system.confidence_on_fail,
    }
    if system.confidence_gap is None:
        reasons.append("confidence gap is unavailable")
    if reasons:
        return _claim_result(claim, EvidenceClaimVerdict.INSUFFICIENT, reasons, metrics)
    if system.confidence_gap >= claim.policy.min_confidence_gap:
        return _claim_result(claim, EvidenceClaimVerdict.SUPPORTED, ["confidence gap threshold met"], metrics)
    return _claim_result(claim, EvidenceClaimVerdict.NOT_SUPPORTED, [f"confidence_gap {system.confidence_gap:.3f} < required {claim.policy.min_confidence_gap:.3f}"], metrics)


def _claim_result(claim: EvidenceClaim, verdict: EvidenceClaimVerdict, reasons: List[str], metrics: Dict[str, Any]) -> EvidenceClaimResult:
    return EvidenceClaimResult(
        claim_id=claim.claim_id,
        verdict=verdict,
        statement=claim.statement,
        reasons=reasons,
        metrics=sanitize_public_payload(metrics),
        required=sanitize_public_payload(claim.policy.model_dump(mode="json")),
    )


EVALUATORS = {
    EvidenceClaimKind.SYSTEM_MEETS_THRESHOLD: evaluate_system_meets_threshold,
    EvidenceClaimKind.SYSTEM_HAS_COVERAGE: evaluate_system_has_coverage,
    EvidenceClaimKind.SYSTEM_BEATS_BASELINE: evaluate_system_beats_baseline,
    EvidenceClaimKind.CONFIDENCE_IS_USEFUL: evaluate_confidence_is_useful,
}


def evaluate_evidence_claim(claim: EvidenceClaim, report: EvidenceHarnessReport) -> EvidenceClaimResult:
    return EVALUATORS[claim.kind](claim, report)


def run_evidence_claim_gates(claims: List[EvidenceClaim], report: EvidenceHarnessReport) -> EvidenceClaimGateReport:
    results = [evaluate_evidence_claim(claim, report) for claim in sorted(claims, key=lambda c: c.claim_id)]
    supported = sum(1 for result in results if result.verdict == EvidenceClaimVerdict.SUPPORTED)
    not_supported = sum(1 for result in results if result.verdict == EvidenceClaimVerdict.NOT_SUPPORTED)
    insufficient = sum(1 for result in results if result.verdict == EvidenceClaimVerdict.INSUFFICIENT)
    payload = {
        "harness_id": report.harness_id,
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "results": [result.model_dump(mode="json") for result in results],
    }
    gate_report = EvidenceClaimGateReport(
        report_id=claim_gate_hash(payload, prefix="claim_gate_"),
        harness_id=report.harness_id,
        claim_count=len(results),
        supported_count=supported,
        not_supported_count=not_supported,
        insufficient_count=insufficient,
        results=results,
    )
    gate_report.summary = evidence_claim_gate_summary(gate_report, report)
    return gate_report


def make_default_ced_vs_baseline_claims(
    *,
    ced_system_id: str = "ced",
    baseline_system_id: str = "baseline",
    policy: Optional[EvidenceClaimPolicy] = None,
) -> List[EvidenceClaim]:
    policy = policy or EvidenceClaimPolicy.strict()
    return [
        EvidenceClaim(
            claim_id="ced_has_sufficient_coverage",
            kind=EvidenceClaimKind.SYSTEM_HAS_COVERAGE,
            target_system_id=ced_system_id,
            statement="CED has enough coverage on the shared task set.",
            policy=policy,
        ),
        EvidenceClaim(
            claim_id="ced_meets_quality_threshold",
            kind=EvidenceClaimKind.SYSTEM_MEETS_THRESHOLD,
            target_system_id=ced_system_id,
            statement="CED meets the minimum accuracy and score thresholds.",
            policy=policy,
        ),
        EvidenceClaim(
            claim_id="ced_beats_baseline",
            kind=EvidenceClaimKind.SYSTEM_BEATS_BASELINE,
            target_system_id=ced_system_id,
            baseline_system_id=baseline_system_id,
            statement="CED beats the baseline by required margins.",
            policy=policy,
        ),
        EvidenceClaim(
            claim_id="ced_confidence_is_useful",
            kind=EvidenceClaimKind.CONFIDENCE_IS_USEFUL,
            target_system_id=ced_system_id,
            statement="CED confidence is meaningfully higher on passing answers than failing answers.",
            policy=policy,
        ),
    ]


def evidence_claim_gate_summary(gate_report: EvidenceClaimGateReport, harness_report: Optional[EvidenceHarnessReport] = None) -> Dict[str, Any]:
    return sanitize_public_payload({
        "report_id": gate_report.report_id,
        "harness_id": gate_report.harness_id,
        "claim_count": gate_report.claim_count,
        "supported_count": gate_report.supported_count,
        "not_supported_count": gate_report.not_supported_count,
        "insufficient_count": gate_report.insufficient_count,
        "supported_claims": [r.claim_id for r in gate_report.results if r.verdict == EvidenceClaimVerdict.SUPPORTED],
        "not_supported_claims": [r.claim_id for r in gate_report.results if r.verdict == EvidenceClaimVerdict.NOT_SUPPORTED],
        "insufficient_claims": [r.claim_id for r in gate_report.results if r.verdict == EvidenceClaimVerdict.INSUFFICIENT],
        "harness": evidence_harness_summary(harness_report) if harness_report else None,
    })
