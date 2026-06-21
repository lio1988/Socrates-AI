"""CLI for the Argumentation v0.1 benchmark. Prints ONLY a JSON report."""

from __future__ import annotations

import json

from backend.evaluation.argumentation_harness import run_arg_benchmark


def main() -> None:
    report = run_arg_benchmark()
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
