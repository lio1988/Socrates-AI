"""
Demo: run a full Socrates AI reasoning session on the mock model roster.

    python run_demo.py "Should a small team adopt microservices?"

Produces a Current Best Explanation with surviving claims, disagreements,
rejected hypotheses and a reasoning trace — no API key required.
"""

import json
import sys

from backend.config import DEFAULT_CONFIG
from backend.orchestrator.reasoning_loop import ReasoningLoop
from backend.constitution import audit, constitution_document


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else \
        "Is consensus among AI models a reliable signal of truth?"

    loop = ReasoningLoop(DEFAULT_CONFIG)
    cbe = loop.run(question)

    print("=" * 70)
    print("CURRENT BEST EXPLANATION")
    print("=" * 70)
    print(json.dumps(cbe.to_dict(), indent=2, ensure_ascii=False))

    print("\n" + "=" * 70)
    print("CONSTITUTION AUDIT")
    print("=" * 70)
    violations = audit(loop.graph, loop.rotation.history,
                       DEFAULT_CONFIG.num_agents)
    if violations:
        for v in violations:
            print(f"  VIOLATION [{v.principle}]: {v.detail}")
    else:
        print("  No constitutional violations detected.")
    print(f"  Rotation: {loop.rotation.domination_report()}")


if __name__ == "__main__":
    main()
