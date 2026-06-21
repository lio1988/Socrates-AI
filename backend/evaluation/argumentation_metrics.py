"""
Argumentation metrics (v0.1)
============================

Deterministic scoring for the Abstract Dung grounded-labeling benchmark. Each
case is scored on whether the produced labels and grounded extension match the
gold labels, after mapping generated claim ids back to the benchmark's symbolic
claim names.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from backend.epistemic.argumentation_framework import ArgumentationLabeling


@dataclass
class ArgCaseResult:
    case_id: str
    labels_correct: bool
    extension_correct: bool
    passed: bool
    expected_labels: Dict[str, str]
    actual_labels: Dict[str, str]

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "labels_correct": self.labels_correct,
            "extension_correct": self.extension_correct,
            "passed": self.passed,
            "expected_labels": self.expected_labels,
            "actual_labels": self.actual_labels,
        }


def score_arg_case(
    case, labeling: ArgumentationLabeling, name_to_cid: Dict[str, str]
) -> ArgCaseResult:
    cid_to_name = {cid: name for name, cid in name_to_cid.items()}

    actual_labels = {
        cid_to_name[cid]: lbl.value for cid, lbl in labeling.labels.items()
    }
    expected_labels = dict(case.gold.get("labels", {}))
    labels_correct = actual_labels == expected_labels

    actual_ext = sorted(cid_to_name[c] for c in labeling.grounded_extension)
    expected_ext = sorted(case.gold.get("grounded_extension", []))
    extension_correct = actual_ext == expected_ext

    passed = labels_correct and extension_correct
    return ArgCaseResult(
        case_id=case.id,
        labels_correct=labels_correct,
        extension_correct=extension_correct,
        passed=passed,
        expected_labels=expected_labels,
        actual_labels=actual_labels,
    )


def aggregate(results: List[ArgCaseResult]) -> Dict[str, float]:
    n = len(results) or 1
    return {
        "labels_correct_rate": sum(r.labels_correct for r in results) / n,
        "extension_correct_rate": sum(r.extension_correct for r in results) / n,
        "passed_rate": sum(r.passed for r in results) / n,
    }
