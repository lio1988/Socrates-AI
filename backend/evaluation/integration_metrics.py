"""
Integration metrics (v0.1)
==========================

Scores each integration case against gold: the focus claim's evidence_status,
argumentation_label and final_handling (and that evidence_balance is present),
plus the report-level clean-primary outcome. Deterministic; maps generated claim
ids back to the benchmark's symbolic names.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from backend.reasoning.ced_integration_report import CEDIntegrationReport


@dataclass
class IntegrationCaseResult:
    case_id: str
    checks: Dict[str, bool]
    passed: bool
    focus_final_handling: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "checks": self.checks,
            "passed": self.passed,
            "focus_final_handling": self.focus_final_handling,
        }


def score_integration_case(
    case, report: CEDIntegrationReport, name_to_cid: Dict[str, str]
) -> IntegrationCaseResult:
    cid_to_name = {cid: name for name, cid in name_to_cid.items()}
    gold = case.gold
    checks: Dict[str, bool] = {}
    focus_handling: Optional[str] = None

    focus_cid = name_to_cid.get(case.focus) if case.focus else None
    view = None
    if focus_cid is not None:
        view = next((v for v in report.claims if v.claim_id == focus_cid), None)
        checks["focus_present"] = view is not None
        if view is not None:
            focus_handling = view.final_handling
            if "focus_evidence_status" in gold:
                checks["evidence_status_ok"] = view.evidence_status == gold["focus_evidence_status"]
            if "focus_argumentation_label" in gold:
                checks["arg_label_ok"] = view.argumentation_label == gold["focus_argumentation_label"]
            if "focus_final_handling" in gold:
                checks["handling_ok"] = view.final_handling == gold["focus_final_handling"]
            # Per-claim evidence_balance must be present and structured.
            checks["balance_present"] = (
                isinstance(view.evidence_balance, dict)
                and "counts" in view.evidence_balance
            )

    if "has_clean_primary" in gold:
        checks["clean_primary_ok"] = (
            report.summary.get("has_clean_primary") == gold["has_clean_primary"]
        )
    if "primary_focus" in gold:
        expected = gold["primary_focus"]
        actual_cid = report.summary.get("primary_claim_id")
        actual_name = cid_to_name.get(actual_cid) if actual_cid else None
        checks["primary_ok"] = actual_name == expected

    passed = len(checks) > 0 and all(checks.values())
    return IntegrationCaseResult(
        case_id=case.id, checks=checks, passed=passed, focus_final_handling=focus_handling
    )


def aggregate(results) -> Dict[str, float]:
    n = len(results) or 1
    out: Dict[str, float] = {"passed_rate": sum(r.passed for r in results) / n}
    all_keys = set()
    for r in results:
        all_keys |= set(r.checks)
    for k in sorted(all_keys):
        vals = [r.checks[k] for r in results if k in r.checks]
        out[f"{k}_rate"] = sum(vals) / (len(vals) or 1)
    return out
