"""CLI for the CED Evaluation Harness v0.1 (scripted mode).

    python -m backend.evaluation.run_eval

Prints a deterministic JSON RunReport. No live model calls, no web.
"""

from __future__ import annotations

import json

from backend.evaluation.harness import run_benchmark


def main() -> None:
    report = run_benchmark()
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
