"""CLI entry point for the Evidence Layer v0.1 harness.

Usage:
    python -m backend.evaluation.run_evidence_eval

Prints ONLY a single JSON object (the run report) to stdout so the output is
machine-parseable. No live model/API calls.
"""

from __future__ import annotations

import json

from backend.evaluation.evidence_harness import run_evidence_benchmark


def main() -> None:
    report = run_evidence_benchmark()
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
