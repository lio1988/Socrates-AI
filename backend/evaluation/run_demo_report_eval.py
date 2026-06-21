"""CLI for the CED demo report v0.1 benchmark. Prints ONLY a JSON report."""

from __future__ import annotations

import json

from backend.evaluation.demo_report_harness import run_demo_benchmark


def main() -> None:
    report = run_demo_benchmark()
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
