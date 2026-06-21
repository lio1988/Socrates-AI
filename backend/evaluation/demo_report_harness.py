"""
Demo report harness (v0.1)
==========================

Deterministic, local, no-live-call harness for the CED demo report. It loads the
expected-outcomes benchmark, calls ``build_demo_report(case_id)`` for each row,
and scores the result. It exercises the full read-only pipeline (raw CBE +
evidence audit + grounded argumentation + integration report) through the demo
service without any model/provider calls.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

from backend.demo.ced_demo_report import build_demo_report, DEMO_REPORT_SCHEMA
from backend.evaluation import demo_report_metrics as DM

DEMO_EVAL_SCHEMA_VERSION = "ced_demo_report_eval_v0.1"
DEMO_HARNESS_VERSION = "ced_demo_report_harness_v0.1"

_DATA = os.path.join(os.path.dirname(__file__), "data", "ced_demo_report_benchmark_v0.json")

_DISCLAIMER = (
    "CED demo report v0.1 (scripted local fixtures, deterministic). Wraps the "
    "read-only raw CBE + evidence audit + grounded argumentation + integration "
    "report; not a live answer and makes no web/API/model calls."
)


@dataclass
class DemoBenchCase:
    case_id: str
    expected_has_clean_primary: bool
    expected_focus_final_handling: str
    expected_min_claim_count: int

    @classmethod
    def from_dict(cls, d: dict) -> "DemoBenchCase":
        return cls(
            case_id=d["case_id"],
            expected_has_clean_primary=bool(d.get("expected_has_clean_primary", False)),
            expected_focus_final_handling=str(d.get("expected_focus_final_handling", "")),
            expected_min_claim_count=int(d.get("expected_min_claim_count", 1)),
        )


def load_demo_benchmark(path: str = _DATA) -> List[DemoBenchCase]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    schema = data.get("schema_version")
    if schema != DEMO_EVAL_SCHEMA_VERSION:
        raise ValueError(
            f"Demo benchmark schema mismatch: expected "
            f"{DEMO_EVAL_SCHEMA_VERSION!r}, got {schema!r}"
        )
    return [DemoBenchCase.from_dict(c) for c in data.get("cases", [])]


def run_demo_case(case: DemoBenchCase) -> DM.DemoCaseResult:
    report = build_demo_report(case.case_id)
    return DM.score_demo_case(case, report)


@dataclass
class DemoRunReport:
    schema_version: str
    harness: str
    case_count: int
    aggregate: Dict[str, float]
    cases: List[DM.DemoCaseResult]
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "harness": self.harness,
            "demo_report_schema": DEMO_REPORT_SCHEMA,
            "case_count": self.case_count,
            "aggregate": self.aggregate,
            "cases": [c.to_dict() for c in self.cases],
            "disclaimer": self.disclaimer,
        }


def run_demo_benchmark(path: str = _DATA) -> DemoRunReport:
    cases = load_demo_benchmark(path)
    results = [run_demo_case(c) for c in cases]
    return DemoRunReport(
        schema_version=DEMO_EVAL_SCHEMA_VERSION,
        harness=DEMO_HARNESS_VERSION,
        case_count=len(results),
        aggregate=DM.aggregate(results),
        cases=results,
    )
