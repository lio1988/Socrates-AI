"""
Demo report metrics (v0.1)
==========================

Scores each demo case against expected outcomes: report-level clean-primary,
the focus claim's final_handling, a minimum surfaced-claim count, and the demo
schema marker. Deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from backend.demo.ced_demo_report import DEMO_REPORT_SCHEMA


@dataclass
class DemoCaseResult:
    case_id: str
    checks: Dict[str, bool]
    passed: bool
    focus_final_handling: str = ""

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "checks": self.checks,
            "passed": self.passed,
            "focus_final_handling": self.focus_final_handling,
        }


def score_demo_case(case, report: dict) -> DemoCaseResult:
    summary = report.get("summary", {}) or {}
    focus = report.get("focus") or {}
    claims = (report.get("integration_report", {}) or {}).get("claims", []) or []

    checks: Dict[str, bool] = {
        "schema_ok": report.get("schema_version") == DEMO_REPORT_SCHEMA,
        "clean_primary_ok": summary.get("has_clean_primary") == case.expected_has_clean_primary,
        "focus_handling_ok": focus.get("final_handling") == case.expected_focus_final_handling,
        "claim_count_ok": len(claims) >= case.expected_min_claim_count,
    }
    passed = all(checks.values())
    return DemoCaseResult(
        case_id=case.case_id,
        checks=checks,
        passed=passed,
        focus_final_handling=focus.get("final_handling", ""),
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
